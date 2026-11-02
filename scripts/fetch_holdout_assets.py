"""Fetch exact recorded PAD/LLM/runtime assets, without refreshing model revisions."""
from triage.io import ROOT,read_json
from scripts.prepare_holdout import download

if __name__=='__main__':
    assets=read_json(ROOT/'report_materials/local_protocol_v2_holdout/asset_manifest.json')
    for asset in assets:
        print('Asset',asset['path'],'bytes',asset.get('bytes','unknown'),flush=True)
        download(asset['url'],ROOT/asset['path'],asset['sha256'])
    print('Recorded model/runtime hashes verified; extract runtime ZIP as documented.')
