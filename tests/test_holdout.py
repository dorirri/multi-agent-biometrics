import hashlib
import json
from pathlib import Path
from triage.io import ROOT,read_json,read_jsonl
from triage.evidence import build_input
from scripts.run_holdout import DATA,behavior_hashes
from scripts.run_protocol_v2 import current_hashes

def test_holdout_frozen_behavior_and_sources_disjoint():
    freeze=read_json(DATA/'holdout_freeze.json')
    assert behavior_hashes()==freeze['behavior_hashes']
    assert current_hashes()==read_json(ROOT/'data/protocol_v2_freeze.json')['hashes']
    new=read_json(DATA/'source_manifest.json');old=read_json(ROOT/'data/source_manifest.json')
    assert len(new)==8 and len({s['sha256'] for s in new})==8
    assert not {s['sha256'] for s in new}&{s['sha256'] for s in old}
    assert not {s['url'] for s in new}&{s['url'] for s in old}
    assert all(s['provider_path'].startswith(('Selfies/','3D_paper_mask /','Cutout_attacks/','Latex_mask/','Silicone_mask/')) for s in new)
    assert len(read_json(DATA/'overlap_audit.json')['potential_near_duplicates_threshold_le_8'])==0

def test_holdout_inputs_have_no_truth_or_paths():
    cache=read_json(DATA/'visual_cache.json');incidents=read_jsonl(DATA/'incidents.jsonl');labels=read_jsonl(DATA/'labels.jsonl')
    assert len(incidents)==18 and len({i['source_id'] for i in incidents})==8
    for cls in ['bona_fide','presentation_attack','injection_attack']:assert sum(l['scenario_class']==cls for l in labels)==6
    assert not {i['incident_id'] for i in incidents}&{i['incident_id'] for i in read_jsonl(ROOT/'data/incidents.jsonl')}
    for i in incidents:
        text=build_input(i,cache).model_dump_json()
        for bad in ['source_id','scenario_class','visual_source_label','provider_path','Selfie_','scenario_delivery','downloads/','group_id']:assert bad not in text
        assert i['history'] is None or all(e['seconds_before']>0 for e in i['history'])

def test_holdout_exact_generator_logic_reproduces(tmp_path,monkeypatch):
    from scripts import prepare_holdout as p
    target=tmp_path/'data';target.mkdir()
    (target/'source_manifest.json').write_bytes((DATA/'source_manifest.json').read_bytes())
    monkeypatch.setattr(p,'EXP',tmp_path);monkeypatch.setattr(p,'DATA',target)
    p.generate()
    for name in ['incidents.jsonl','labels.jsonl']:
        # write_text emits OS-native newlines; the frozen files were produced on Windows (CRLF).
        assert (target/name).read_bytes().replace(b'\r\n',b'\n')==(DATA/name).read_bytes().replace(b'\r\n',b'\n')

def test_holdout_result_contract_when_complete():
    import pytest
    run=ROOT/'results/local_protocol_v2_holdout'
    if not (run/'completion.json').exists():pytest.skip('Holdout still running')
    complete=read_json(run/'completion.json');rows=read_jsonl(run/'predictions.jsonl');ids={i['incident_id'] for i in read_jsonl(DATA/'incidents.jsonl')}
    if complete['completed']:
        assert len(rows)==72
        for m in 'BCDE':assert {r['incident_id'] for r in rows if r['method']==m}==ids
    for t in read_jsonl(run/'traces.jsonl'):
        evidence={e['evidence_id'] for e in t['agent_input']['evidence']}
        if t['trace']['checks']:evidence.add('t0')
        assert t['trace']['rechecks']<=1 and len(t['trace']['calls'])<=4
        row=next(r for r in rows if r['method']==t['method'] and r['incident_id']==t['incident_id'])
        assert set(row['evidence_ids'])<=evidence
        assert sum(c.get('output_tokens') or 0 for c in t['trace']['calls'])<=2400
        for c in t['trace']['calls']:
            assert c['request']['temperature']==0 and c['request']['seed']==8217 and c['request']['max_tokens']==600
            if c['final_stage'] and c['status']=='ok':assert json.loads(c['raw_response']).get('request_check','none')=='none'

def test_holdout_reporting_zero_denominators_and_examples():
    import csv
    import pytest
    p=ROOT/'report_materials/local_protocol_v2_holdout'
    if not (p/'metrics.csv').exists():pytest.skip('Report not generated')
    rows=list(csv.DictReader((p/'metrics.csv').open(encoding='utf-8-sig')))
    for r in rows:
        if float(r['denominator'])==0:assert r['value']=='N/A'
    examples=read_json(p/'error_examples.json')
    assert 3<=len(examples)<=5 and len({e['incident_id'] for e in examples})==len(examples)
    for e in examples:assert set(e['evidence_ids'])<={x['evidence_id'] for x in e['evidence']}
