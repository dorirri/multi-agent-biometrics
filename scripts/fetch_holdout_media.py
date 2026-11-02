"""Fetch only frozen public media, with exact URL/SHA; no labels passed to LLM."""
from triage.io import ROOT,read_json
from scripts.prepare_holdout import DATA,download

if __name__=='__main__':
    for source in read_json(DATA/'source_manifest.json'):
        print('Fetch and verify',source['source_id'],source['bytes'],flush=True)
        download(source['url'],ROOT/source['path'],source['sha256'])
    print('All frozen media hashes match. No model inference has been run.')
