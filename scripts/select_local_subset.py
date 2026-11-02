"""Freeze one shared evaluation subset using pilot speed, never predictions' quality."""
import argparse
import hashlib
import math
import random
import time
from triage.io import ROOT,read_json,read_jsonl,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--pilot-run',required=True);p.add_argument('--budget-seconds',type=int,default=1500);args=p.parse_args()
    target=ROOT/'data/local_evaluation_selection.json'
    if target.exists():raise SystemExit('Selection is already frozen; do not overwrite it')
    pilot=ROOT/'results'/args.pilot_run
    if not read_json(pilot/'completion.json')['completed']:raise SystemExit('Pilot incomplete')
    rows=[r for r in read_jsonl(pilot/'predictions.jsonl') if r['method'] in 'CDE']
    ids=set(r['incident_id'] for r in rows)
    seconds=sum(r['triage_seconds'] for r in rows)/len(ids)
    n=min(30,3*math.floor(args.budget_seconds/(seconds*1.5)/3))
    if n<6:raise SystemExit('Projected throughput insufficient even for 6 incidents; stop for feasibility review')
    rng=random.Random(94017);labels=[r for r in read_jsonl(ROOT/'data/labels.jsonl') if r['split']=='evaluation']
    chosen=[]
    for cls in ['bona_fide','presentation_attack','injection_attack']:
        pool=sorted(r['incident_id'] for r in labels if r['scenario_class']==cls);rng.shuffle(pool);chosen+=pool[:n//3]
    write_json(target,{'incident_ids':chosen,'split':'evaluation','n':n,'per_class':n//3,'seed':94017,'selected_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selection_rule':'stratified random sample by scenario class; no model predictions used for selection','pilot_run':args.pilot_run,'pilot_incidents':len(ids),'pilot_mean_CDE_seconds_per_incident':seconds,'time_budget_seconds':args.budget_seconds,'time_safety_factor':1.5,'projected_seconds_with_safety_factor':n*seconds*1.5,'agents_sha256':hashlib.sha256((ROOT/'triage/agents.py').read_bytes()).hexdigest(),'rules_sha256':hashlib.sha256((ROOT/'triage/rules.py').read_bytes()).hexdigest()})
    print('Frozen n=',n,'pilot C+D+E seconds/incident=',round(seconds,3),'projected seconds with margin=',round(n*seconds*1.5))

if __name__=='__main__':main()
