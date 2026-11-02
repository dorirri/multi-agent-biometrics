"""Local tools of the six agents. No external API, no network, no state change outside the run store.

Each tool returns an evidence dict {evidence_id, tool, status, values}. Values coming from the client
(device strings, notes) are untrusted data and are marked as such; tools never execute them.
"""
import ipaddress
import json
import re
import sqlite3
from triage.io import read_json,read_jsonl

INSTRUCTION_LIKE=re.compile(r'(system|assistant|ignore|override|output|answer|classify)\b.*\b(allow|bona_fide|verified|instruction|previous)',re.I)

def evidence(eid,tool,values,status='ok'):
    return {'evidence_id':eid,'tool':tool,'status':status,'values':values}

class Toolbox:
    def __init__(self,data_dir):
        self.data=data_dir
        self.visual=read_json(data_dir/'visual_cache.json')
        self.signatures=read_json(data_dir/'signatures.json')
        self.ip_ranges=read_json(data_dir/'ip_ranges.json')
        self.db=data_dir/'history.sqlite'
        self._archive=None

    # Liveness analyst ------------------------------------------------------------
    def pad_minifasnet(self,inc):
        if inc['tool_fault']:return evidence('L1','pad_minifasnet',{'error':'controlled_tool_failure'},'error')
        v=self.visual[inc['source_id']]['minifasnet']
        return evidence('L1','pad_minifasnet',{k:x for k,x in v.items() if k!='status'},v['status'])

    def pad_thesis(self,inc):
        if inc['tool_fault']:return evidence('L2','pad_thesis_vjune',{'error':'controlled_tool_failure'},'error')
        v=self.visual[inc['source_id']]['thesis_vjune']
        return evidence('L2','pad_thesis_vjune',{k:x for k,x in v.items() if k!='status'},v['status'])

    def face_quality(self,inc):
        q=self.visual[inc['source_id']]['quality']
        return evidence('L3','face_quality_opencv',dict(q,frames=inc['frames_count']),'ok' if q['face_count']==1 else 'error')

    # Channel analyst -------------------------------------------------------------
    def parse_metadata(self,inc):
        d=inc['device'];s=inc['stream']
        if d is None:return evidence('C1','parse_metadata',{'device':None,'stream':s,'note':'device metadata not provided by client'},'missing')
        clipped={k:(v[:160] if isinstance(v,str) else v) for k,v in d.items()}
        text=' '.join(str(v) for v in d.values() if isinstance(v,str))
        return evidence('C1','parse_metadata',{'device':clipped,'stream':s,'untrusted_client_fields':['device_model','camera_name','build_fingerprint','runtime_flags','client_note'],'instruction_like_text_detected':bool(INSTRUCTION_LIKE.search(text))})

    def signature_lookup(self,inc):
        d=inc['device']
        if d is None:return evidence('C2','signature_lookup',{'checked':False},'missing')
        hits=[]
        fields={'camera_name':d['camera_name'] or '','build_fingerprint':d['build_fingerprint'] or '','runtime_flags':' '.join(d['runtime_flags'])}
        for category,patterns in self.signatures.items():
            for pattern in patterns:
                for field,value in fields.items():
                    if pattern.lower() in value.lower():hits.append({'category':category,'pattern':pattern,'field':field})
        return evidence('C2','signature_lookup',{'checked':True,'fields_checked':list(fields),'hits':hits,'categories':sorted({h['category'] for h in hits})})

    # Session analyst -------------------------------------------------------------
    def _query(self,sql,args):
        with sqlite3.connect(f'file:{self.db}?mode=ro',uri=True) as db:return db.execute(sql,args).fetchall()

    def history_query(self,inc):
        if not inc['history_available']:return evidence('S1','history_query',{'error':'history service unavailable'},'unavailable')
        s=inc['session'];t=s['timestamp']
        rows=self._query('select outcome,count(*) from attempts where account_id=? and ts<? and ts>=? group by outcome',(s['account_id'],t,t-3600))
        older=self._query('select count(*) from attempts where account_id=? and ts<? and outcome="success"',(s['account_id'],t-3600))[0][0]
        hour=dict(rows)
        return evidence('S1','history_query',{'account_attempts_last_hour':sum(hour.values()),'by_outcome_last_hour':hour,'account_successes_before_last_hour':older})

    def linked_accounts(self,inc):
        if not inc['history_available']:return evidence('S2','linked_accounts',{'error':'history service unavailable'},'unavailable')
        s=inc['session'];t=s['timestamp']
        q=lambda col,val,window:self._query(f'select count(distinct account_id) from attempts where {col}=? and ts<? and ts>=? and account_id!=?',(val,t,t-window,s['account_id']))[0][0]
        devices_on_ip=self._query('select count(distinct device_id) from attempts where ip=? and ts<? and ts>=?',(s['ip'],t,t-86400))[0][0]
        return evidence('S2','linked_accounts',{'other_accounts_same_device_1h':q('device_id',s['device_id'],3600),'other_accounts_same_ip_1h':q('ip',s['ip'],3600),'other_accounts_same_ip_24h':q('ip',s['ip'],86400),'distinct_devices_same_ip_24h':devices_on_ip})

    def ip_info(self,inc):
        """Local range table only (no reputation API by design)."""
        addr=inc['session']['ip'];cat='unknown'
        for name,prefix in self.ip_ranges.items():
            if addr.startswith(prefix):cat=name
        ip=ipaddress.ip_address(addr)
        return evidence('S3','ip_info_local',{'category':cat,'shared_address_space_rfc6598':ip in ipaddress.ip_network('100.64.0.0/10'),'source':'local synthetic range table'})

    # Verifier --------------------------------------------------------------------
    def schema_validate(self,reports,tool_evidence):
        out={}
        for agent,(report,status) in reports.items():
            known={e['evidence_id'] for e in tool_evidence.get(agent,[])}
            unknown=sorted(set(report.get('evidence_ids',[]))-known) if report else []
            out[agent]={'status':status,'valid':status=='done' and not unknown,'unknown_evidence_ids':unknown}
        return evidence('V1','schema_validate',out)

    def consistency_rules(self,reports,tool_evidence):
        """Deterministic rules. report_errors: an analyst claim contradicts tool facts (grounds for recheck).
        cross_signal_conflicts: signal groups disagree; this is informative (e.g. live face + virtual camera
        is the typical injection pattern) and is passed to the conclusion, not treated as an error."""
        by={e['evidence_id']:e for es in tool_evidence.values() for e in es}
        conflicts=[];errors=[];L1,L2,L3,C1,C2,S2=(by.get(k) for k in ['L1','L2','L3','C1','C2','S2'])
        labels=[e['values'].get('pad_label') for e in (L1,L2) if e and e['status']=='ok']
        cats=set(C2['values'].get('categories',[])) if C2 and C2['status']=='ok' else set()
        if len(set(labels))>1:conflicts.append('R1 liveness models disagree (MiniFASNet vs thesis model)')
        if labels and all(x=='live' for x in labels) and cats&{'virtual_camera','emulator','hooking'}:conflicts.append('R2 live appearance but injection-tool signature in channel')
        if 'spoof' in labels and cats&{'virtual_camera','emulator','hooking'}:conflicts.append('R3 spoof appearance and injection signature: attack mechanism attribution conflict')
        stream=(C1 or {}).get('values',{}).get('stream') or {}
        if (stream.get('attestation')=='invalid' or stream.get('capture_binding')=='mismatch') and labels and all(x=='live' for x in labels):
            conflicts.append('R4 live appearance but failed attestation or capture binding')
        if L3 and L3['status']!='ok':conflicts.append('R5 face quality tool reports no single face')
        if S2 and S2['status']=='ok' and S2['values']['other_accounts_same_device_1h']>=3:conflicts.append('R6 device used by several other accounts within one hour')
        missing=[e['evidence_id'] for e in by.values() if e['status']!='ok']
        lv=reports.get('liveness_analyst',(None,None))[0];ch=reports.get('channel_analyst',(None,None))[0]
        if lv and labels and lv['liveness_assessment']=='live' and all(x=='spoof' for x in labels):errors.append('E1 liveness_analyst claims live although every model says spoof')
        if lv and labels and lv['liveness_assessment']=='spoof' and all(x=='live' for x in labels):errors.append('E1 liveness_analyst claims spoof although every model says live')
        if lv and len(labels)==2 and lv['models_agree']!=(labels[0]==labels[1]):errors.append('E2 liveness_analyst misreports model agreement')
        if ch and 'virtual_camera' in cats and not ch['virtual_camera_signs']:errors.append('E3 channel_analyst denies virtual camera despite signature hit')
        if ch and 'emulator' in cats and not ch['emulator_signs']:errors.append('E3 channel_analyst denies emulator despite signature hit')
        if ch and 'hooking' in cats and not ch['hooking_signs']:errors.append('E3 channel_analyst denies hooking despite signature hit')
        if ch and C2 and C2['status']=='ok' and not cats&{'virtual_camera','dual_use_camera'} and ch['virtual_camera_signs']:errors.append('E4 channel_analyst reports virtual camera without any signature hit')
        return evidence('V2','consistency_rules',{'report_errors':errors,'cross_signal_conflicts':conflicts,'missing_or_failed_evidence':missing})

    # Conclusion ------------------------------------------------------------------
    def attack_reference(self):
        return evidence('K1','attack_reference',{
            'presentation_attack':{'standard':'ISO/IEC 30107','instruments':{'print':'printed photo held to camera','screen_replay':'photo/video shown on a display','mask':'paper, latex or silicone mask'},'typical_signals':'PAD spoof; physical camera and normal channel'},
            'injection_attack':{'standard':'CEN/TS 18099','instruments':{'virtual_camera':'virtual webcam driver feeds prepared video','emulator':'emulated device replaces camera','hooking':'instrumentation framework substitutes frames','stream_substitution':'tampered stream without software signature'},'typical_signals':'PAD may say live; channel signatures, failed attestation or capture binding, timing anomalies'},
            'notes':['PAD scores are uncalibrated','dual-use camera apps and rooted phones also occur for genuine users','shared mobile carrier addresses (CGNAT) link unrelated accounts']})

    def _archive_features(self):
        if self._archive is None:
            labels={l['incident_id']:l for l in read_jsonl(self.data/'labels.jsonl') if l['split']=='archive'}
            self._archive=[(self.features(i),labels[i['incident_id']]) for i in read_jsonl(self.data/'incidents.jsonl') if i['incident_id'] in labels]
        return self._archive

    def features(self,inc):
        ev={e['evidence_id']:e for e in [self.pad_minifasnet(inc),self.pad_thesis(inc),self.signature_lookup(inc),self.parse_metadata(inc),self.linked_accounts(inc)]}
        stream=ev['C1']['values'].get('stream') or {}
        return {'minifasnet':ev['L1']['values'].get('pad_label','error'),'thesis':ev['L2']['values'].get('pad_label','error'),'signature':','.join(c for c in ev['C2']['values'].get('categories',[]) if c!='root') or 'none','attestation':stream.get('attestation','missing'),'binding':stream.get('capture_binding','missing'),'ring':ev['S2']['status']=='ok' and ev['S2']['values']['other_accounts_same_device_1h']>=3}

    def similar_incidents(self,inc,k=3):
        """Nearest resolved incidents from the archive split (debug/archive users only, never evaluation)."""
        f=self.features(inc)
        scored=sorted(self._archive_features(),key=lambda x:-sum(f[key]==x[0][key] for key in f))[:k]
        return evidence('K2','similar_incidents',{'query':f,'matches':[{'features':a,'resolved_class':l['scenario_class'],'resolved_attack_type':l['scenario_subtype'] or 'none','matching_features':sum(f[key]==a[key] for key in f)} for a,l in scored]})
