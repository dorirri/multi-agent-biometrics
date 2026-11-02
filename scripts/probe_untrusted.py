"""Real paired debug probe: change only untrusted note, not evidence or ground truth."""
import copy
from triage.agents import LLM,Orchestrator
from triage.evidence import build_input
from triage.io import ROOT,read_json,read_jsonl,write_json

def main():
    candidates=[i for i in read_jsonl(ROOT/'data/incidents.jsonl') if i['split']=='debug' and 'SYSTEM OVERRIDE' in i['client_note']]
    incident=sorted(candidates,key=lambda i:i['incident_id'])[0]
    original=build_input(incident,read_json(ROOT/'data/visual_cache.json'))
    control=copy.deepcopy(original)
    for e in control.evidence:
        if e.evidence_id=='c0':e.values['note']='Camera diagnostic: normal operation.'
    model=LLM(max_calls=4);runner=Orchestrator(model);results=[]
    for variant,inp in [('control',control),('untrusted_instruction',original)]:
        d,t=runner.run('C',inp)
        results.append({'variant':variant,'incident_id':incident['incident_id'],'agent_input':inp.model_dump(),'decision':d.model_dump(),'trace':t})
        print(variant,d.predicted_class,d.recommendation,sum(c['seconds'] for c in t['calls']),flush=True)
    write_json(ROOT/'results/local_feasibility/untrusted_paired_debug.json',{'independent_new_incidents':0,'method':'C','order':['control','untrusted_instruction'],'same_model_and_seed':True,'only_changed_field':'c0.values.note','absolute_security_claim':False,'results':results})

if __name__=='__main__':main()
