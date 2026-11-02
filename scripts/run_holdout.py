"""New-data adapter; frozen B and v2 behavior are imported unchanged."""
import argparse
import hashlib
import platform
import time
from datetime import datetime,timezone
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.protocol_v2 import LocalLLMV2,OrchestratorV2
from triage.rules import rules
from scripts.run_protocol_v2 import current_hashes,run_cases

EXP=ROOT/'experiments/local_protocol_v2_holdout';DATA=EXP/'data'
class HoldoutDeadline(Exception):pass

def behavior_hashes():
    files=list((ROOT/'triage').glob('*.py'))+[ROOT/'scripts/generate.py',ROOT/'scripts/prepare_holdout.py',ROOT/'scripts/run_holdout.py']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

class Methods:
    def __init__(self,llm,deadline):self.v2=OrchestratorV2(llm);self.deadline=deadline
    def run(self,method,inp):
        if time.monotonic()+160>self.deadline:raise HoldoutDeadline('Insufficient reserved time for next method')
        if method=='B':return rules(inp.evidence),{'calls':[],'rechecks':0,'checks':[],'events':[],'new_independent_sources':0,'protocol_version':2,'deterministic_baseline':True}
        return self.v2.run(method,inp)

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',default='local_protocol_v2_holdout');p.add_argument('--max-seconds',type=int,default=1800);args=p.parse_args()
    run=ROOT/'results'/args.run_id
    if run.exists():raise SystemExit('Never overwrite or silently resume an existing run')
    freeze=read_json(DATA/'holdout_freeze.json')
    assert current_hashes()==read_json(ROOT/'data/protocol_v2_freeze.json')['hashes'],'Original v2 freeze changed'
    assert behavior_hashes()==freeze['behavior_hashes'],'Holdout behavior changed after freeze'
    for path,digest in freeze['input_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    incidents=read_jsonl(DATA/'incidents.jsonl');labels=read_jsonl(DATA/'labels.jsonl');cache=read_json(DATA/'visual_cache.json')
    run.mkdir(parents=True);llm=LocalLLMV2(max_calls=162)
    # Hard overall limit leaves reporting time; original per-call timeout is unchanged.
    global_stop=datetime(2026,11,2,9,22,tzinfo=timezone.utc).timestamp()
    allowance=min(args.max_seconds,max(0,global_stop-time.time()));deadline=time.monotonic()+allowance
    write_json(run/'config.json',{'run_id':args.run_id,'split':'holdout','methods':list('BCDE'),'protocol_version':2,'original_behavior_unchanged':True,'holdout_freeze':freeze,'model':llm.model,'model_manifest':read_json(ROOT/'data/local_backend_manifest.json'),'server_parameters':read_json(ROOT/'data/local_server_config.json'),'actual_server_logs':'results/holdout_server','python':platform.python_version(),'temperature':0,'seed':8217,'max_tokens_per_call':600,'timeout_seconds':40,'max_llm_calls_per_method':4,'max_checks_per_method':1,'max_calls_run':162,'run_budget_seconds':allowance,'reserve_before_next_method_seconds':160,'cost_usd':0,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    write_json(run/'sample.json',{'n':len(incidents),'incident_ids':[i['incident_id'] for i in incidents],'counts':dict(Counter(l['scenario_class'] for l in labels)),'unique_media_sources':len(set(i['source_id'] for i in incidents)),'sources':sorted(set(i['source_id'] for i in incidents)),'stress_counts':dict(Counter(l['stress'] for l in labels))})
    try:run_cases(run,incidents,cache,list('BCDE'),Methods(llm,deadline),labels)
    except HoldoutDeadline:
        completion=read_json(run/'completion.json');completion.update(budget_stopped_before_llm_call=True,inflight_usage_unknown=False)
        write_json(run/'completion.json',completion);print('Partial run saved due to time reserve',flush=True)

if __name__=='__main__':main()
