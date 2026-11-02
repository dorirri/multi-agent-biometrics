"""Single exploratory run, immutable input subset, incremental checkpoints."""
import argparse
import hashlib
import importlib.metadata
import platform
import time
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json,write_jsonl
from triage.evidence import build_input
from triage.metrics import save_metrics
from triage.protocol_v2 import LocalLLMV2,OrchestratorV2

def frozen_paths():
    return [ROOT/p for p in ['triage/protocol_v2.py','triage/agents.py','triage/schemas.py','triage/rules.py','triage/evidence.py','triage/metrics.py','scripts/run_protocol_v2.py','scripts/freeze_protocol_v2.py','tests/test_protocol_v2.py','docs/protocol_v2_plan.md','data/incidents.jsonl','data/labels.jsonl','data/visual_cache.json','data/local_evaluation_selection.json','data/local_backend_manifest.json','data/local_server_config.json','data/protocol_v2_debug_selection.json','data/protocol_v2_initial.schema.json','data/protocol_v2_final.schema.json','data/protocol_v2_prompts.json']]

def current_hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen_paths()}

def run_cases(run,incidents,cache,methods,orchestrator,labels,after_checkpoint=None):
    predictions=[];traces=[];errors=[];finished=False;interruption=None;inflight=None
    def checkpoint():
        write_jsonl(run/'predictions.jsonl',predictions);write_jsonl(run/'traces.jsonl',traces);write_jsonl(run/'errors.jsonl',errors)
    try:
        for incident in incidents:
            inp=build_input(incident,cache)
            for method in methods:
                inflight={'incident_id':incident['incident_id'],'method':method,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
                write_json(run/'inflight.json',inflight)
                start=time.perf_counter();d,tr=orchestrator.run(method,inp);seconds=time.perf_counter()-start
                calls=tr['calls'];bad=[c for c in calls if c['status']!='ok']
                errors.extend({'incident_id':incident['incident_id'],'method':method,'error_type':c.get('error_type')} for c in bad)
                errors.extend({'incident_id':incident['incident_id'],'method':method,'error_type':'AdditionalToolFailure'} for c in tr['checks'] if c['status']!='ok')
                predictions.append(dict(incident_id=incident['incident_id'],method=method,**d.model_dump(),triage_seconds=seconds,feature_seconds=cache[incident['source_id']]['feature_seconds'],calls=sum(c.get('request_sent',False) for c in calls),input_tokens=sum(c.get('input_tokens') or 0 for c in calls),output_tokens=sum(c.get('output_tokens') or 0 for c in calls),usage_missing_calls=sum(c.get('request_sent',False) and c.get('input_tokens') is None for c in calls),errors=len(bad),tool_errors=sum(c['status']!='ok' for c in tr['checks'])))
                traces.append({'incident_id':incident['incident_id'],'method':method,'agent_input':inp.model_dump(),'trace':tr})
                checkpoint()
                inflight=None;write_json(run/'inflight.json',None)
                print(incident['incident_id'][:8],method,d.predicted_class,round(seconds,3),flush=True)
                if after_checkpoint:after_checkpoint(predictions)
        finished=True
    except BaseException as exc:
        interruption=type(exc).__name__;raise
    finally:
        checkpoint()
        if predictions:save_metrics(run,predictions,labels)
        counts=dict(Counter(p['method'] for p in predictions))
        write_json(run/'completion.json',{'completed':finished,'status':'completed' if finished else 'partial','expected_incidents_per_method':len(incidents),'completed_incidents_per_method':counts,'predictions':len(predictions),'api_calls':sum(p['calls'] for p in predictions),'interruption_type':interruption,'inflight_pair':inflight,'inflight_usage_unknown':inflight is not None,'completed_pairs':[{'incident_id':p['incident_id'],'method':p['method']} for p in predictions],'ended_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--split',choices=['debug','evaluation'],required=True);p.add_argument('--subset-file',required=True);p.add_argument('--max-api-calls',type=int,default=162);p.add_argument('--pilot-run');args=p.parse_args()
    run=ROOT/'results'/args.run_id
    if run.exists():raise SystemExit('Do not overwrite an existing run_id')
    if args.split=='evaluation':
        if args.subset_file!='data/local_evaluation_selection.json':raise SystemExit('V2 evaluation requires the original frozen 18 IDs')
        frozen=read_json(ROOT/'data/protocol_v2_freeze.json')
        if frozen['hashes']!=current_hashes():raise SystemExit('Frozen code/schema/prompt/data mismatch')
        if not args.pilot_run:raise SystemExit('A completed debug run is required')
        if read_json(ROOT/'results'/args.pilot_run/'config.json')['split']!='debug' or not read_json(ROOT/'results'/args.pilot_run/'completion.json')['completed']:raise SystemExit('Debug pilot not complete')
    ids=set(read_json(ROOT/args.subset_file)['incident_ids'])
    incidents=[i for i in read_jsonl(ROOT/'data/incidents.jsonl') if i['split']==args.split and i['incident_id'] in ids]
    if len(incidents)!=len(ids):raise SystemExit('Missing incident IDs or incorrect split')
    labels=[r for r in read_jsonl(ROOT/'data/labels.jsonl') if r['incident_id'] in ids];cache=read_json(ROOT/'data/visual_cache.json')
    run.mkdir(parents=True)
    llm=LocalLLMV2(max_calls=args.max_api_calls)
    write_json(run/'config.json',{'run_id':args.run_id,'protocol_version':2,'exploratory_follow_up':True,'baseline_run':'local_evaluation_v1','split':args.split,'methods':list('CDE'),'subset_file':args.subset_file,'pilot_run':args.pilot_run,'backend':'local','model':llm.model,'local_backend_manifest':read_json(ROOT/'data/local_backend_manifest.json'),'server_config':read_json(ROOT/'data/local_server_config.json'),'python':platform.python_version(),'versions':{n:importlib.metadata.version(n) for n in ['numpy','onnxruntime','pydantic']},'temperature':0,'seed':8217,'max_tokens_per_call':600,'max_calls_per_method':4,'max_checks_per_method':1,'timeout_seconds':40,'max_api_calls_run':args.max_api_calls,'cost_usd':0,'hashes':current_hashes(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    write_json(run/'sample.json',{'n':len(incidents),'counts':dict(Counter(r['scenario_class'] for r in labels)),'unique_media_sources':len(set(i['source_id'] for i in incidents)),'sources':sorted(set(i['source_id'] for i in incidents)),'incident_ids':[i['incident_id'] for i in incidents],'stress_counts':dict(Counter(r['stress'] for r in labels))})
    run_cases(run,incidents,cache,list('CDE'),OrchestratorV2(llm),labels)

if __name__=='__main__':main()
