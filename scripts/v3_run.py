"""Run v3 methods on a split. Never overwrites a run; evaluation requires a frozen debug-tested state."""
import argparse
import hashlib
import platform
import time
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json,write_jsonl
from triage.team.agents import Team
from triage.team.baselines import pad_only,rules,single_agent
from triage.team.llm import LocalLLM
from triage.team.store import StateStore
from triage.team.tools import Toolbox

DATA=ROOT/'experiments/v3_team/data'
METHODS=['A_minifas','A_thesis','B','C','T']

def frozen_paths():
    return sorted(list((ROOT/'triage/team').glob('*.py'))+[ROOT/'scripts/v3_run.py',ROOT/'scripts/v3_prepare_oulu.py']+[DATA/n for n in ['incidents.jsonl','labels.jsonl','visual_cache.json','history.sqlite','signatures.json','ip_ranges.json','source_manifest.json','generation_config.json']])

def current_hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen_paths()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-id',required=True);p.add_argument('--split',choices=['debug','evaluation'],required=True)
    p.add_argument('--methods',nargs='+',choices=METHODS,default=METHODS);p.add_argument('--limit',type=int)
    p.add_argument('--max-seconds',type=float,default=None,help='per-incident time limit of the team (plan: 90)')
    p.add_argument('--sequential',action='store_true',help='run analysts one after another (ablation of parallelism)')
    args=p.parse_args()
    run=ROOT/'results'/args.run_id
    if run.exists():raise SystemExit('run_id exists; do not overwrite results')
    if args.split=='evaluation':
        freeze=DATA/'freeze.json'
        if not freeze.exists():raise SystemExit('Evaluation requires experiments/v3_team/data/freeze.json (scripts/v3_freeze.py after a debug run)')
        if read_json(freeze)['hashes']!=current_hashes():raise SystemExit('Code/data changed after freeze')
        if args.max_seconds!=read_json(freeze)['max_seconds']:raise SystemExit('Time limit differs from frozen value')
    incidents=[i for i in read_jsonl(DATA/'incidents.jsonl') if i['split']==args.split][:args.limit]
    ids={i['incident_id'] for i in incidents}
    labels=[l for l in read_jsonl(DATA/'labels.jsonl') if l['incident_id'] in ids]
    run.mkdir(parents=True)
    tools=Toolbox(DATA);store=StateStore(run/'state.sqlite')
    llm=LocalLLM() if set(args.methods)&{'C','T'} else None
    team=Team(llm,tools,store,max_seconds=args.max_seconds,parallel=not args.sequential) if llm else None
    write_json(run/'config.json',{'run_id':args.run_id,'split':args.split,'methods':args.methods,'n':len(incidents),'llm_model':llm.model if llm else None,'llm_backend':'llama.cpp b12032 (dde879bc4) macOS arm64, Metal, 3 slots, ctx 24576' if llm else None,'temperature':0,'seed':8217,'max_tokens_per_call':llm.max_tokens if llm else None,'timeout_per_call':llm.timeout if llm else None,'max_steps_per_incident':25,'max_seconds_per_incident':args.max_seconds,'parallel_analysts':not args.sequential,'cost_usd':0,'python':platform.python_version(),'platform':platform.platform(),'hashes':current_hashes(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    write_json(run/'sample.json',{'n':len(incidents),'incident_ids':sorted(ids),'counts':dict(Counter(l['scenario_class'] for l in labels)),'subtypes':dict(Counter(str(l['scenario_subtype']) for l in labels)),'stress':dict(Counter(l['stress'] for l in labels)),'unique_frames':len({i['source_id'] for i in incidents})})
    predictions=[];traces=[]
    for inc in incidents:
        for m in args.methods:
            t=time.perf_counter()
            if m=='A_minifas':c,tr=pad_only(tools,inc,'minifasnet'),{'steps':[],'llm_calls':0,'tool_calls':1,'llm_errors':0}
            elif m=='A_thesis':c,tr=pad_only(tools,inc,'thesis'),{'steps':[],'llm_calls':0,'tool_calls':1,'llm_errors':0}
            elif m=='B':c,tr=rules(tools,inc),{'steps':[],'llm_calls':0,'tool_calls':6,'llm_errors':0}
            elif m=='C':c,tr=single_agent(llm,tools,inc)
            else:c,tr=team.run(inc)
            sec=time.perf_counter()-t
            llm_steps=[s for s in tr['steps'] if s['kind']=='llm']
            predictions.append(dict(incident_id=inc['incident_id'],method=m,**c.model_dump(),seconds=sec,llm_calls=tr['llm_calls'],tool_calls=tr['tool_calls'],llm_errors=tr['llm_errors'],input_tokens=sum(s.get('input_tokens') or 0 for s in llm_steps),output_tokens=sum(s.get('output_tokens') or 0 for s in llm_steps),fallback=next((e['reason'] for e in tr.get('events',[]) if e['kind']=='fallback'),None)))
            traces.append({'incident_id':inc['incident_id'],'method':m,'trace':tr})
            write_jsonl(run/'predictions.jsonl',predictions);write_jsonl(run/'traces.jsonl',traces)
            print(inc['incident_id'][:8],m,c.verdict,c.recommendation,round(sec,1),flush=True)
    write_json(run/'completion.json',{'completed':True,'predictions':len(predictions),'llm_calls':llm.calls if llm else 0,'ended_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

if __name__=='__main__':main()
