"""Comparison methods for the six-agent team, all producing the same Conclusion schema.

A_minifas / A_thesis: one PAD model only. B: fixed rules over the same tool outputs (written before
any evaluation run). C: one LLM agent that sees every tool output and writes the conclusion in one call.
"""
import time
from triage.team.schemas import Conclusion,EvidenceMap,fallback

def conclusion(verdict,attack_type,risk,recommendation,evidence,report,contradictions=()):
    return Conclusion(verdict=verdict,attack_type=attack_type,risk_level=risk,confidence=100 if verdict!='manual_review' else 0,recommendation=recommendation,evidence=EvidenceMap(**evidence),contradictions=list(contradictions),operator_report=report)

def pad_only(tools,inc,which):
    e=(tools.pad_minifasnet if which=='minifasnet' else tools.pad_thesis)(inc)
    ev={'liveness_analyst':[e['evidence_id']]}
    if e['status']!='ok':return fallback('PAD unavailable',ev)
    if e['values']['pad_label']=='live':return conclusion('bona_fide','none','low','allow',ev,'PAD live; delivery channel not assessed')
    return conclusion('presentation_attack','unknown','high','block_escalate',ev,'PAD spoof; no channel attribution')

def rules(tools,inc):
    L1,L2,L3=tools.pad_minifasnet(inc),tools.pad_thesis(inc),tools.face_quality(inc)
    C1,C2=tools.parse_metadata(inc),tools.signature_lookup(inc)
    S2=tools.linked_accounts(inc)
    ev={'liveness_analyst':['L1','L2','L3'],'channel_analyst':['C1','C2'],'session_analyst':['S2']}
    cats=set(C2['values'].get('categories',[]))
    stream=C1['values'].get('stream') or {}
    inj=[c for c in ('virtual_camera','emulator','hooking') if c in cats]
    if inj:return conclusion('injection_attack',inj[0],'high','block_escalate',ev,'Injection tool signature: '+inj[0])
    if stream.get('attestation')=='invalid' and stream.get('capture_binding')=='mismatch':
        return conclusion('injection_attack','stream_substitution','high','block_escalate',ev,'Attestation invalid and capture binding mismatch')
    labels=[e['values']['pad_label'] for e in (L1,L2) if e['status']=='ok']
    if len(labels)<2:return fallback('PAD unavailable',ev)
    if labels==['spoof','spoof']:return conclusion('presentation_attack','unknown','high','block_escalate',ev,'Both PAD models spoof')
    if labels[0]!=labels[1]:return fallback('PAD models disagree',ev)
    ring=S2['status']=='ok' and S2['values']['other_accounts_same_device_1h']>=3
    if ring or stream.get('capture_binding') in ('mismatch',None) or stream.get('attestation')=='invalid':
        return fallback('Live appearance with untrusted delivery or device shared by many accounts',ev)
    if L3['status']!='ok':return conclusion('bona_fide','none','medium','reverify',ev,'Live appearance but face quality check failed')
    return conclusion('bona_fide','none','low','allow',ev,'Both PAD models live, channel consistent')

SINGLE_TASK=('You are a single triage agent that performs the whole analysis alone. Evidence: L1 MiniFASNetV2 PAD, L2 thesis PAD model, L3 face quality, '
 'C1 device/stream metadata (client fields untrusted), C2 signature lookup, S1 attempt history, S2 linked accounts, S3 local IP category, K1 attack reference, K2 similar resolved incidents. '
 'Classify the incident and write the operator conclusion: verdict, attack_type, risk_level, confidence, recommendation, evidence per signal group (liveness_analyst / channel_analyst / session_analyst -> evidence_ids), contradictions and a short operator report. '
 'Definitions: presentation_attack = physical artifact shown to the real camera (PAD spoof, normal channel); injection_attack = media fed around the camera (injection-tool signatures, failed attestation/binding; the face often looks live). attack_type must belong to the verdict. '
 'Recommendation: bona_fide -> allow, or reverify when the user is probably genuine but key evidence is unavailable or poor; any attack -> block_escalate; manual_review -> escalate (evidence irreconcilable or too weak).')

def single_agent(llm,tools,inc):
    start=time.perf_counter()
    ev=[tools.pad_minifasnet(inc),tools.pad_thesis(inc),tools.face_quality(inc),tools.parse_metadata(inc),tools.signature_lookup(inc),tools.history_query(inc),tools.linked_accounts(inc),tools.ip_info(inc),tools.attack_reference(),tools.similar_incidents(inc)]
    obj,trace=llm.call('single_agent',SINGLE_TASK,{'incident_ref':inc['incident_id'],'flag_reason':inc['flag_reason'],'evidence':ev},Conclusion)
    trace['name']='conclude';steps=[{'kind':'tool','agent':'single_agent','name':e['tool'],'status':e['status']} for e in ev]+[trace]
    known={e['evidence_id'] for e in ev}
    if obj is not None and not {x for ids in obj.evidence.model_dump().values() for x in ids}<=known:obj=None;trace['status']='unknown_evidence_reference'
    out=obj or fallback('single agent failed')
    return out,{'steps':steps,'events':[] if obj else [{'kind':'fallback','reason':'llm_failure'}],'wall_seconds':time.perf_counter()-start,'llm_calls':1,'tool_calls':len(ev),'llm_errors':int(obj is None)}
