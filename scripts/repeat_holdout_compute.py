"""Explicit computational reproduction in a NEW run; never overwrite original data/cache."""
import argparse
import hashlib
import time
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.protocol_v2 import LocalLLMV2
from scripts.run_holdout import DATA,behavior_hashes,Methods
from scripts.run_protocol_v2 import current_hashes,run_cases

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--recompute-pad',action='store_true');args=p.parse_args()
    run=ROOT/'results'/args.run_id
    if run.exists():raise SystemExit('Use a new run_id; do not select a best repeat')
    freeze=read_json(DATA/'holdout_freeze.json')
    assert behavior_hashes()==freeze['behavior_hashes'] and current_hashes()==read_json(ROOT/'data/protocol_v2_freeze.json')['hashes']
    run.mkdir(parents=True);cache=read_json(DATA/'visual_cache.json')
    if args.recompute_pad:
        for source in read_json(DATA/'source_manifest.json'):
            assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest()==source['sha256']
        from scripts import prepare_holdout as preparation
        dest=run/'recomputed_PAD';dest.mkdir()
        write_json(dest/'source_manifest.json',read_json(DATA/'source_manifest.json'))
        preparation.DATA=dest
        preparation.extract_pad()  # same frozen PAD implementation and frame positions
        cache=read_json(dest/'visual_cache.json')
    incidents=read_jsonl(DATA/'incidents.jsonl');labels=read_jsonl(DATA/'labels.jsonl')
    write_json(run/'config.json',{'run_id':args.run_id,'reproduction_of':'local_protocol_v2_holdout','not_independent_observations':True,'original_freeze':freeze,'recomputed_PAD':args.recompute_pad,'original_data_cache_preserved':True,'cost_usd':0,'temperature':0,'seed':8217,'timeout_seconds':40,'max_tokens':600})
    write_json(run/'sample.json',read_json(ROOT/'results/local_protocol_v2_holdout/sample.json'))
    model=LocalLLMV2(max_calls=162)
    run_cases(run,incidents,cache,list('BCDE'),Methods(model,time.monotonic()+1800),labels)

if __name__=='__main__':main()
