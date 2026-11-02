"""Freeze v3 code, prompts and data after a completed debug run, before the single evaluation run."""
import argparse
import time
from triage.io import ROOT,read_json,write_json
from scripts.v3_run import DATA,current_hashes

def main():
    p=argparse.ArgumentParser();p.add_argument('--debug-run',required=True);p.add_argument('--max-seconds',type=float,default=90.0);args=p.parse_args()
    run=ROOT/'results'/args.debug_run
    if read_json(run/'config.json')['split']!='debug' or not read_json(run/'completion.json')['completed']:raise SystemExit('A completed debug run is required')
    if (DATA/'freeze.json').exists():raise SystemExit('Already frozen; do not refreeze after looking at evaluation results')
    write_json(DATA/'freeze.json',{'debug_run':args.debug_run,'max_seconds':args.max_seconds,'max_steps':25,'hashes':current_hashes(),'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Frozen',len(current_hashes()),'files')

if __name__=='__main__':main()
