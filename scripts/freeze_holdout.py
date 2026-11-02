import hashlib
import time
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.evidence import build_input
from scripts.run_holdout import DATA,behavior_hashes
from scripts.run_protocol_v2 import current_hashes

def main():
    target=DATA/'holdout_freeze.json'
    if target.exists():raise SystemExit('Holdout already frozen')
    assert current_hashes()==read_json(ROOT/'data/protocol_v2_freeze.json')['hashes']
    incidents=read_jsonl(DATA/'incidents.jsonl');labels=read_jsonl(DATA/'labels.jsonl');cache=read_json(DATA/'visual_cache.json')
    assert len(incidents)==18 and len(set(i['source_id'] for i in incidents))==8
    oldids={i['incident_id'] for i in read_jsonl(ROOT/'data/incidents.jsonl')}
    assert not oldids&{i['incident_id'] for i in incidents}
    for incident in incidents:
        text=build_input(incident,cache).model_dump_json()
        for forbidden in ['source_id','scenario_class','visual_source_label','provider_path','Selfie_','source_manifest','downloads/','scenario_delivery','group_id']:
            assert forbidden not in text
    inputs=[p for p in DATA.glob('*') if p.is_file()]+[ROOT/'docs/holdout_protocol.md']
    write_json(target,{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'before_first_evaluation_call':True,'n':18,'class_counts':{c:sum(l['scenario_class']==c for l in labels) for c in ['bona_fide','presentation_attack','injection_attack']},'media_sources':8,'generator_seed':20261102,'behavior_hashes':behavior_hashes(),'original_v2_freeze_sha256':hashlib.sha256((ROOT/'data/protocol_v2_freeze.json').read_bytes()).hexdigest(),'input_hashes':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'new_data_only':True,'source_and_scenario_names_filtered_from_agent_input':True})
    print('New media, incidents, labels, PAD, generator and unchanged v2 frozen')

if __name__=='__main__':main()
