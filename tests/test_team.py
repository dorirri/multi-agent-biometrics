"""v3 six-agent team: protocol, schemas, leakage and limits. The fake LLM is used only in these tests."""
import json
import threading
import pytest
from pydantic import ValidationError
from triage.io import ROOT,read_jsonl
from triage.team.agents import Team
from triage.team.baselines import rules
from triage.team.llm import LocalLLM
from triage.team.schemas import Conclusion,FinalVerification,Verification,fallback
from triage.team.store import StateStore
from triage.team.tools import Toolbox

DATA=ROOT/'experiments/v3_team/data'
pytestmark=pytest.mark.skipif(not (DATA/'incidents.jsonl').exists(),reason='v3 data not prepared')
FORBIDDEN=['scenario_class','scenario_subtype','visual_source_label','source_artifact','source_id','"split"','latent_nuisance','fraud_ring','oulu_file','true/','false/']

def report(agent):
    return {'liveness_analyst':{'liveness_assessment':'live','models_agree':True,'frame_quality':'ok','suspected_artifact':'none','risk':'low','confidence':80,'evidence_ids':['L1','L2'],'findings':'x'},
            'channel_analyst':{'virtual_camera_signs':False,'emulator_signs':False,'hooking_signs':False,'stream_anomalies':[],'channel_risk':'low','confidence':80,'evidence_ids':['C1'],'findings':'x'},
            'session_analyst':{'attempts_last_hour':0,'linked_accounts':0,'ip_category':'residential','session_risk':'low','confidence':80,'evidence_ids':['S1'],'findings':'x'}}[agent]

class FakeLLM:
    def __init__(self,overrides=None):
        self.overrides=overrides or {};self.payloads=[];self.calls=0;self.threads=set();self.lock=threading.Lock()
    def call(self,agent,task,payload,model):
        with self.lock:
            self.calls+=1;self.payloads.append((agent,json.dumps(payload)));self.threads.add(threading.get_ident())
        key=(agent,'final' if model.__name__=='FinalVerification' else 'recheck' if 'verifier_question' in payload else 'close' if 'limits_check' in payload else 'first')
        raw=self.overrides.get(key) or self.overrides.get(agent)
        if callable(raw):raw=raw(payload)
        if raw is None and model.__name__=='ManualConclusion':raw={'verdict':'manual_review','attack_type':'unknown','risk_level':'medium','confidence':50,'recommendation':'escalate','evidence':{},'contradictions':[],'operator_report':'r'}
        if raw is None:
            raw={'orchestrator':{'tasks':[{'agent':a,'focus':'f'} for a in ['liveness_analyst','channel_analyst','session_analyst']],'priority_signal':'none','rationale':'r'},
                 'verifier':{'decision':'accept','recheck_agent':'none','recheck_question':'','contradictions':[],'missing_data':[],'rationale':'r'},
                 'conclusion':{'verdict':'bona_fide','attack_type':'none','risk_level':'low','confidence':70,'recommendation':'allow','evidence':{'liveness_analyst':['L1']},'contradictions':[],'operator_report':'ok'}}.get(agent) or report(agent)
            if key==('orchestrator','close'):raw={'final_status':'completed','limits_respected':True,'journal_note':'n'}
        if raw=='FAIL':return None,{'kind':'llm','agent':agent,'status':'error','request_sent':True,'seconds':0}
        return model.model_validate(raw),{'kind':'llm','agent':agent,'status':'ok','request_sent':True,'seconds':0,'input_tokens':1,'output_tokens':1}

def incident(split='debug',pred=lambda i:True):
    return next(i for i in read_jsonl(DATA/'incidents.jsonl') if i['split']==split and pred(i))

def team(llm,**kw):return Team(llm,Toolbox(DATA),StateStore(),**kw)

def test_happy_path_uses_six_agents_and_plan_budget():
    llm=FakeLLM();c,tr=team(llm).run(incident())
    assert c.verdict=='bona_fide' and not tr['events']
    agents={s['agent'] for s in tr['steps']}
    assert agents=={'orchestrator','liveness_analyst','channel_analyst','session_analyst','verifier','conclusion'}
    # Plan table 4: 7 LLM + 14 tool calls; the liveness agent has one extra tool (second PAD model).
    assert tr['llm_calls']==7 and tr['tool_calls']==15

def test_analysts_run_in_parallel_threads():
    llm=FakeLLM();team(llm).run(incident())
    assert len(llm.threads)>=2

def test_agent_inputs_never_contain_labels_or_dataset_paths():
    llm=FakeLLM()
    for inc in [i for i in read_jsonl(DATA/'incidents.jsonl') if i['split']=='debug']:team(llm).run(inc)
    for agent,payload in llm.payloads:
        for bad in FORBIDDEN:assert bad not in payload,(agent,bad)

def test_single_recheck_cycle_then_final_schema():
    asks={'decision':'recheck','recheck_agent':'channel_analyst','recheck_question':'q','contradictions':[],'missing_data':[],'rationale':'r'}
    llm=FakeLLM({('verifier','first'):asks});c,tr=team(llm).run(incident())
    assert [e['kind'] for e in tr['events']]==['recheck'] and c.verdict=='bona_fide'
    assert tr['llm_calls']==9 and tr['llm_calls']+tr['tool_calls']<=25
    with pytest.raises(ValidationError):FinalVerification.model_validate(asks)

def test_any_llm_failure_gives_manual_review():
    for agent in ['orchestrator','liveness_analyst','verifier','conclusion']:
        c,tr=team(FakeLLM({agent:'FAIL'})).run(incident())
        assert c.verdict=='manual_review' and c.recommendation=='escalate',agent

def test_verifier_manual_review_forces_manual_conclusion():
    mr={'decision':'manual_review','recheck_agent':'none','recheck_question':'','contradictions':[],'missing_data':[],'rationale':'r'}
    c,_=team(FakeLLM({'verifier':mr})).run(incident())
    assert c.verdict=='manual_review'

def test_orchestrator_can_only_downgrade():
    close={'final_status':'manual_review','limits_respected':True,'journal_note':'n'}
    c,tr=team(FakeLLM({('orchestrator','close'):close})).run(incident())
    assert c.verdict=='manual_review' and tr['events'][0]['kind']=='orchestrator_downgrade'

def test_agents_can_only_cite_their_own_evidence():
    from triage.team.schemas import LivenessReport,EvidenceMap
    with pytest.raises(ValidationError):LivenessReport.model_validate(dict(report('liveness_analyst'),evidence_ids=['C1']))
    with pytest.raises(ValidationError):EvidenceMap(channel_analyst=['C3'])
    with pytest.raises(ValidationError):EvidenceMap(L1=['text'])

def test_step_and_time_limits():
    c,tr=team(FakeLLM(),max_steps=5).run(incident())
    assert c.verdict=='manual_review' and tr['events'][-1]['reason']=='step_limit'

def test_recommendation_must_fit_verdict():
    base={'attack_type':'virtual_camera','risk_level':'high','confidence':90,'evidence':{},'contradictions':[],'operator_report':'r'}
    Conclusion(verdict='injection_attack',recommendation='block_escalate',**base)
    for v,r in [('injection_attack','reverify'),('injection_attack','allow'),('presentation_attack','allow'),('presentation_attack','reverify'),('manual_review','allow')]:
        with pytest.raises(ValidationError):Conclusion(verdict=v,recommendation=r,**dict(base,attack_type='unknown'))
    Conclusion(verdict='bona_fide',recommendation='reverify',**dict(base,attack_type='none'))
    with pytest.raises(ValidationError):Verification(decision='recheck',recheck_agent='none',recheck_question='',contradictions=[],missing_data=[],rationale='r')
    assert fallback('x').recommendation=='escalate'

def test_tools_history_is_strictly_prior_and_archive_only_for_similar_cases():
    tools=Toolbox(DATA);inc=incident('evaluation',lambda i:i['history_available'])
    import sqlite3
    with sqlite3.connect(DATA/'history.sqlite') as db:
        later=db.execute('select count(*) from attempts where account_id=? and ts>=?',(inc['session']['account_id'],inc['session']['timestamp'])).fetchone()[0]
    assert later==0
    labels={l['incident_id']:l['split'] for l in read_jsonl(DATA/'labels.jsonl')}
    assert {labels[i['incident_id']] for i in read_jsonl(DATA/'incidents.jsonl') if i['incident_id'] in {x for x in labels if labels[x]=='archive'}}=={'archive'}
    assert len(tools._archive_features())==sum(v=='archive' for v in labels.values())

def test_splits_disjoint_by_person_and_frame():
    labels=read_jsonl(DATA/'labels.jsonl')
    ev={l['user'] for l in labels if l['split']=='evaluation'};dev={l['user'] for l in labels if l['split']!='evaluation'}
    assert ev.isdisjoint(dev)
    assert len({l['source_id'] for l in labels})==len(labels)

def test_untrusted_text_detected_and_rules_signature():
    tools=Toolbox(DATA)
    inc=incident('archive',lambda i:i['device'] and 'SYSTEM OVERRIDE' in i['device']['client_note'])
    assert tools.parse_metadata(inc)['values']['instruction_like_text_detected']
    vc=incident('archive',lambda i:i['device'] and 'OBS' in i['device']['camera_name'] or (i['device'] and 'ManyCam' in i['device']['camera_name']))
    assert 'virtual_camera' in tools.signature_lookup(vc)['values']['categories'] and rules(tools,vc).verdict=='injection_attack'

def test_local_llm_only_loopback(monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL','https://api.example.com/v1')
    with pytest.raises(RuntimeError):LocalLLM()

def test_v3_evaluation_artifacts_when_available():
    from scripts.v3_run import current_hashes
    from triage.io import read_json
    run=ROOT/'results/v3_evaluation'
    if not (run/'completion.json').exists():pytest.skip('v3 evaluation not run')
    freeze=read_json(DATA/'freeze.json')
    assert read_json(run/'config.json')['hashes']==freeze['hashes']==current_hashes()
    rows=read_jsonl(run/'predictions.jsonl');ids={i['incident_id'] for i in read_jsonl(DATA/'incidents.jsonl') if i['split']=='evaluation'}
    for m in ['A_minifas','A_thesis','B','C','T']:assert {r['incident_id'] for r in rows if r['method']==m}==ids
    for t in read_jsonl(run/'traces.jsonl'):
        if t['method']!='T':continue
        tr=t['trace'];assert tr['llm_calls']+tr['tool_calls']<=25 and sum(e['kind']=='recheck' for e in tr['events'])<=1
        for s in tr['steps']:
            if s['kind']=='llm':assert s['request']['temperature']==0 and s['request']['seed']==8217
    for r in rows:Conclusion.model_validate({k:r[k] for k in Conclusion.model_fields})
