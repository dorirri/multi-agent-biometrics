import json
import pytest
from pydantic import ValidationError
from triage.schemas import Decision
from triage.evidence import build_input
from triage.protocol_v2 import FinalDecision,LocalLLMV2,OrchestratorV2,validate
from triage.rules import decision
from triage.io import read_json,read_jsonl

def fixture():
    incident={'incident_id':'debug-only','source_id':'s','channel':{'virtual_camera':False,'attestation':'valid','capture_binding':'match','timestamp_gap_ms':20,'device_change':False},'history':[{'seconds_before':600,'outcome':'success'}],'client_note':'normal','tool_fault':None}
    cache={'s':{'status':'ok','values':{'pad_label':'live','live_score':.9},'feature_seconds':.1}}
    return incident,cache,build_input(incident,cache)

class Stub:
    """Unit tests only; no experiment runner references this class."""
    def __init__(self,manual=False):self.seen=[];self.manual=manual
    def call(self,role,evidence,extra=None,final=False):
        self.seen.append((role,final))
        cls='manual_review' if self.manual else 'presentation_attack' if role=='context' else 'bona_fide'
        d=decision(cls,[evidence[0].evidence_id],'test fixture')
        d.request_check='none' if final else 'visual_summary'
        d=(FinalDecision if final else Decision).model_validate(d.model_dump())
        return d,{'role':role,'final_stage':final,'status':'ok','seconds':0,'request_sent':False,'input_tokens':0,'output_tokens':0,'test_double':True}

def test_final_schema_and_validation_forbid_new_request():
    _,_,inp=fixture();raw=decision('bona_fide',['v0'],'test').model_dump()
    schema=FinalDecision.model_json_schema()
    assert schema['properties']['request_check']['const']=='none'
    raw['request_check']='consistency'
    with pytest.raises(ValidationError):validate(raw,inp.evidence,True)
    assert validate(raw,inp.evidence,False).request_check=='consistency'

@pytest.mark.parametrize('method,limit',[('C',2),('D',3),('E',4)])
def test_actual_check_and_call_budget(method,limit):
    _,_,inp=fixture();stub=Stub();d,tr=OrchestratorV2(stub).run(method,inp)
    assert tr['rechecks']==1 and len(tr['checks'])==1
    assert tr['checks'][0]['status']=='ok' and len(stub.seen)<=limit
    assert d.request_check=='none'
    if method=='E':assert stub.seen[:2]==[('visual',True),('context',True)]
    assert stub.seen[-1][1] is True

def test_competing_requests_context_priority_and_no_artificial_review():
    _,_,inp=fixture();stub=Stub();d,tr=OrchestratorV2(stub).run('D',inp)
    assert stub.seen==[('visual',False),('context',False),('context',True)]
    assert tr['events'][0]['selected_role']=='context'
    assert tr['events'][0]['unexecuted_requests']==[{'role':'visual','check':'visual_summary'}]
    assert d.predicted_class=='presentation_attack'  # unchanged original merge

@pytest.mark.parametrize('method',list('CDE'))
def test_substantive_review_is_preserved(method):
    _,_,inp=fixture();d,tr=OrchestratorV2(Stub(manual=True)).run(method,inp)
    assert d.predicted_class=='manual_review' and d.recommendation=='escalate'
    assert all(c['status']=='ok' for c in tr['calls'])

@pytest.mark.parametrize('method',list('CDE'))
def test_tool_unavailable_never_means_allow(method):
    _,_,inp=fixture()
    def unavailable(*args):raise TimeoutError('test-only failure')
    d,tr=OrchestratorV2(Stub(),unavailable).run(method,inp)
    assert d.predicted_class=='manual_review' and d.recommendation=='escalate'
    assert len(tr['checks'])==1 and tr['checks'][0]['status']=='error'

def test_real_client_final_schema_transport_and_invalid_responses(monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL','http://127.0.0.1:8080/v1')
    _,_,inp=fixture();raw=decision('bona_fide',['v0'],'test').model_dump();requests=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'choices':[{'message':{'content':payload}}],'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode()
    class Transport:
        def open(self,request,timeout):
            requests.append(json.loads(request.data));assert timeout==40;return Response()
    client=LocalLLMV2(max_calls=3);client.opener=Transport()
    raw['request_check']='consistency';payload=json.dumps(raw)
    d,t=client.call('single',inp.evidence,final=True)
    assert t['status']=='error' and d.predicted_class=='manual_review'
    assert requests[0]['response_format']['schema']['properties']['request_check']['const']=='none'
    assert requests[0]['temperature']==0 and requests[0]['seed']==8217 and requests[0]['max_tokens']==600
    payload='{"predicted_class":"bona_fide"'  # never salvage a class
    d,t=client.call('single',inp.evidence)
    assert t['error_type']=='JSONDecodeError' and d.recommendation=='escalate'

def test_run_call_limit_fail_closed(monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL','http://127.0.0.1:8080/v1')
    _,_,inp=fixture();client=LocalLLMV2(max_calls=0)
    d,tr=OrchestratorV2(client).run('E',inp)
    assert client.calls==0 and d.predicted_class=='manual_review'
    assert len(tr['calls'])<=4 and not any(c.get('request_sent') for c in tr['calls'])

def test_partial_run_checkpoint_survives_interruption(tmp_path):
    from scripts.run_protocol_v2 import run_cases
    incident,cache,_=fixture()
    def stop(_):raise RuntimeError('simulated interruption after checkpoint')
    labels=[{'incident_id':incident['incident_id'],'scenario_class':'bona_fide','visual_source_label':'live'}]
    with pytest.raises(RuntimeError):run_cases(tmp_path,[incident],cache,list('CDE'),OrchestratorV2(Stub()),labels,stop)
    assert len(read_jsonl(tmp_path/'predictions.jsonl'))==1
    completion=read_json(tmp_path/'completion.json')
    assert not completion['completed'] and completion['status']=='partial'
    assert completion['completed_incidents_per_method']=={'C':1}
    assert len(read_jsonl(tmp_path/'traces.jsonl'))==1

def test_actual_v2_artifacts_when_available():
    from triage.io import ROOT
    from scripts.run_protocol_v2 import current_hashes
    run=ROOT/'results/local_protocol_v2'
    if not (run/'completion.json').exists():pytest.skip('Single v2 evaluation has not finished')
    assert current_hashes()==read_json(ROOT/'data/protocol_v2_freeze.json')['hashes']
    rows=read_jsonl(run/'predictions.jsonl');ids=set(read_json(ROOT/'data/local_evaluation_selection.json')['incident_ids'])
    if read_json(run/'completion.json')['completed']:
        for m in 'CDE':assert {r['incident_id'] for r in rows if r['method']==m}==ids
    for tr in read_jsonl(run/'traces.jsonl'):
        assert tr['trace']['rechecks']<=1 and len(tr['trace']['checks'])<=1
        assert len(tr['trace']['calls'])<=4
        for c in tr['trace']['calls']:
            if c['final_stage']:
                assert c['request']['response_format']['schema']['properties']['request_check']['const']=='none'
                if c['status']=='ok':assert json.loads(c['raw_response']).get('request_check','none')=='none'
    # Snapshot preservation checks exclude deliberately updated STATUS only.
    import hashlib
    manifest=read_json(ROOT/'snapshots/protocol_v1_manifest.json')
    for name,sha in manifest.items():
        if name.startswith(('results/local_evaluation_v1/','report_materials/local_evaluation_v1/')) or name in ['triage/agents.py','triage/schemas.py','triage/rules.py']:
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha
