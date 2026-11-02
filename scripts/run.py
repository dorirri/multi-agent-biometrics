import argparse
import hashlib
import importlib.metadata
import os
import platform
import time
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json,write_jsonl
from triage.evidence import build_input
from triage.rules import rules,pad_only
from triage.metrics import save_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['debug','evaluation'],default='debug');p.add_argument('--methods',nargs='+',choices=list('ABCDE'),default=['A','B']);p.add_argument('--run-id',required=True);p.add_argument('--limit',type=int);p.add_argument('--max-api-calls',type=int,default=100);p.add_argument('--pilot-run');p.add_argument('--subset-file');args=p.parse_args()
    run=ROOT/'results'/args.run_id
    if run.exists():raise SystemExit('run_id exists; do not overwrite results')
    use_llm=bool(set(args.methods)&set('CDE'));llm=None
    if use_llm:
        if args.split=='evaluation' and not args.pilot_run:raise SystemExit('Evaluation with LLM requires --pilot-run pointing to measured debug pilot')
        if args.pilot_run:
            pilot=read_json(ROOT/'results'/args.pilot_run/'config.json')
            if pilot['split']!='debug' or not set('CDE')<=set(pilot['methods']):raise SystemExit('A complete CDE debug pilot is required')
            pilot_done=read_json(ROOT/'results'/args.pilot_run/'completion.json')
            pilot_preds=read_jsonl(ROOT/'results'/args.pilot_run/'predictions.jsonl')
            if not pilot_done.get('completed') or not any(r['method'] in 'CDE' and r['calls'] and not r['errors'] for r in pilot_preds):
                raise SystemExit('Pilot must complete and include successful real LLM calls before evaluation')
        from triage.agents import LLM,Orchestrator
        llm=LLM(args.max_api_calls);orchestrator=Orchestrator(llm)
    incidents=[r for r in read_jsonl(ROOT/'data/incidents.jsonl') if r['split']==args.split]
    if args.subset_file:
        selection=read_json(ROOT/args.subset_file)
        selected=set(selection['incident_ids'])
        incidents=[r for r in incidents if r['incident_id'] in selected]
        if len(incidents)!=len(selected):raise SystemExit('Subset has unknown IDs or wrong split')
    incidents=incidents[:args.limit] if args.limit else incidents
    labels=[r for r in read_jsonl(ROOT/'data/labels.jsonl') if r['incident_id'] in {i['incident_id'] for i in incidents}]
    cache=read_json(ROOT/'data/visual_cache.json')
    run.mkdir(parents=True)
    write_json(run/'environment_packages.json',{d.metadata['Name']:d.version for d in importlib.metadata.distributions()})
    paths=list((ROOT/'triage').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))+[ROOT/'docs/experiment_protocol.md',ROOT/'requirements.txt',ROOT/'data/incidents.jsonl',ROOT/'data/labels.jsonl',ROOT/'data/visual_cache.json']
    if (ROOT/'docs/local_protocol_addendum.md').exists():paths.append(ROOT/'docs/local_protocol_addendum.md')
    if args.subset_file:paths.append(ROOT/args.subset_file)
    write_json(run/'config.json',{'run_id':args.run_id,'split':args.split,'methods':args.methods,'python':platform.python_version(),'platform':platform.platform(),'versions':{x:importlib.metadata.version(x) for x in ['numpy','opencv-python-headless','onnxruntime','pydantic','matplotlib','pytest']},'llm_model':llm.model if llm else None,'llm_base_url_configured':bool(llm),'backend':'local' if use_llm else None,'api_price_verified':False,'cost_usd':0,'local_compute_cost_monetized':False,'temperature':0,'seed':8217,'structured_decoding':'JSON schema grammar' if use_llm else None,'max_calls_per_method':4,'max_completion_tokens_per_call':600,'max_completion_tokens_per_method':2400,'timeout_seconds':40,'max_api_calls_run':args.max_api_calls,'pilot_run':args.pilot_run,'subset_file':args.subset_file,'local_backend_manifest':read_json(ROOT/'data/local_backend_manifest.json') if use_llm and (ROOT/'data/local_backend_manifest.json').exists() else None,'hashes':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in paths},'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    write_json(run/'sample.json',{'n':len(incidents),'unique_media_sources':len(set(i['source_id'] for i in incidents)),'counts':dict(Counter(r['scenario_class'] for r in labels)),'incident_ids':[i['incident_id'] for i in incidents],'sources':sorted(set(i['source_id'] for i in incidents)),'stress_counts':dict(Counter(r['stress'] for r in labels))})
    predictions=[];traces=[];errors=[]
    tool_errors=[]
    for i in incidents:
        v=cache[i['source_id']]
        if i['tool_fault'] or v['status']!='ok':
            tool_errors.append({'incident_id':i['incident_id'],'source_id':i['source_id'],'controlled_failure':bool(i['tool_fault']),'source_status':v['status'],'frame_errors':[f.get('error') for f in v['frames'] if f['status']!='ok']})
    write_jsonl(run/'tool_errors.jsonl',tool_errors)
    for i in incidents:
        inp=build_input(i,cache)
        for method in args.methods:
            t=time.perf_counter();trace={'calls':[],'rechecks':0}
            if method=='A':d=pad_only(inp.evidence)
            elif method=='B':d=rules(inp.evidence).model_dump()
            else:
                obj,trace=orchestrator.run(method,inp);d=obj.model_dump()
            elapsed=time.perf_counter()-t
            calls=trace['calls'];bad=[c for c in calls if c['status']!='ok']
            for c in bad:errors.append({'incident_id':i['incident_id'],'method':method,'error_type':c.get('error_type')})
            predictions.append(dict(incident_id=i['incident_id'],method=method,**d,triage_seconds=elapsed,feature_seconds=cache[i['source_id']]['feature_seconds'],calls=sum(c.get('request_sent',False) for c in calls),input_tokens=sum(c.get('input_tokens') or 0 for c in calls),output_tokens=sum(c.get('output_tokens') or 0 for c in calls),usage_missing_calls=sum(c.get('request_sent',False) and c.get('input_tokens') is None for c in calls),errors=len(bad)))
            traces.append({'incident_id':i['incident_id'],'method':method,'agent_input':inp.model_dump(),'trace':trace})
            # Incremental checkpoints survive interruption without losing measured failures.
            write_jsonl(run/'predictions.jsonl',predictions);write_jsonl(run/'traces.jsonl',traces);write_jsonl(run/'errors.jsonl',errors)
            print(i['incident_id'][:8],method,d['predicted_class'],round(elapsed,3),flush=True)
    save_metrics(run,predictions,labels)
    write_json(run/'completion.json',{'completed':True,'predictions':len(predictions),'api_calls':llm.calls if llm else 0,'unique_sources_feature_seconds':sum(cache[s]['feature_seconds'] for s in set(i['source_id'] for i in incidents)),'tool_error_source_count':sum(cache[s]['status']!='ok' for s in set(i['source_id'] for i in incidents))})

if __name__=='__main__':main()
