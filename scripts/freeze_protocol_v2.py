import difflib
import time
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.schemas import Decision
from triage.agents import SYSTEM,ROLES
from triage.protocol_v2 import FinalDecision,FINAL_INSTRUCTION,INITIAL_INSTRUCTION,ALLOCATION_RULE

def prepare():
    write_json(ROOT/'data/protocol_v2_initial.schema.json',Decision.model_json_schema())
    write_json(ROOT/'data/protocol_v2_final.schema.json',FinalDecision.model_json_schema())
    write_json(ROOT/'data/protocol_v2_prompts.json',{'classification_system_unchanged':SYSTEM,'classification_roles_unchanged':ROLES,'final_stage_instruction':FINAL_INSTRUCTION,'initial_stage_instruction':INITIAL_INSTRUCTION,'D_allocation_rule':ALLOCATION_RULE})
    incidents=read_jsonl(ROOT/'data/incidents.jsonl');first=read_json(ROOT/'data/local_pilot_selection.json')['incident_ids'][0]
    fault=sorted(i['incident_id'] for i in incidents if i['split']=='debug' and i['tool_fault'])[0]
    write_json(ROOT/'data/protocol_v2_debug_selection.json',{'split':'debug','incident_ids':[first,fault],'selection_rule':'saved complete debug ID plus first lexicographic debug controlled PAD-failure ID; no evaluation answers used'})
    diff=''.join(difflib.unified_diff((ROOT/'triage/agents.py').read_text(encoding='utf-8').splitlines(True),(ROOT/'triage/protocol_v2.py').read_text(encoding='utf-8').splitlines(True),fromfile='v1/triage/agents.py',tofile='v2/triage/protocol_v2.py'))
    (ROOT/'docs/protocol_v2_code.diff').write_text(diff,encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');args=p.parse_args()
    if args.freeze:
        from scripts.run_protocol_v2 import current_hashes
        target=ROOT/'data/protocol_v2_freeze.json'
        if target.exists():raise SystemExit('Do not rewrite the frozen version')
        if not read_json(ROOT/'results/protocol_v2_debug/completion.json')['completed']:raise SystemExit('Complete debug first')
        write_json(target,{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'after_debug_before_evaluation':True,'hashes':current_hashes()})
        print('V2 frozen')
    else:prepare();print('Schemas, prompts, debug selection, exact code diff prepared')
