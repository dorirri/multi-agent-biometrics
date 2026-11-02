"""One actual local LLM call on debug only; retains raw response and validation."""
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.evidence import build_input
from triage.agents import LLM

def main():
    candidates=[i for i in read_jsonl(ROOT/'data/incidents.jsonl') if i['split']=='debug' and i['tool_fault'] is None and i['channel'] is not None and i['history'] is not None]
    incident=sorted(candidates,key=lambda i:i['incident_id'])[0]
    write_json(ROOT/'data/local_pilot_selection.json',{'split':'debug','incident_ids':[incident['incident_id']],'selection':'First lexicographic complete debug input, before LLM response'})
    inp=build_input(incident,read_json(ROOT/'data/visual_cache.json'))
    d,trace=LLM(max_calls=1).call('single',inp.evidence)
    write_json(ROOT/'results/local_feasibility/structured_smoke.json',{'incident_id':incident['incident_id'],'agent_input':inp.model_dump(),'decision':d.model_dump(),'trace':trace})
    print('status=',trace['status'],'seconds=',round(trace['seconds'],3),'input_tokens=',trace['input_tokens'],'output_tokens=',trace['output_tokens'],'error=',trace.get('error_type'))
    print(d.model_dump_json())
    if trace['status']!='ok':raise SystemExit('Local structured smoke failed; inspect saved trace before more calls')

if __name__=='__main__':main()
