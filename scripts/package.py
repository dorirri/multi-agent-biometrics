"""Allowlist archive: never includes credentials, runtimes, model weights or raw faces."""
import hashlib
import zipfile
from triage.io import ROOT,write_json

def main():
    target=ROOT/'research_triage_handoff.zip'
    roots=['triage','scripts','tests','docs','report_materials','results','figures']
    files=[ROOT/x for x in ['README.md','requirements.txt','requirements-lock.txt','pytest.ini','.gitignore','.env.example'] if (ROOT/x).exists()]
    for name in roots:
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.zip'])
    files.extend(p for p in (ROOT/'data').glob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md'])
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for path in sorted(set(files)):
            assert not path.name.startswith('.env') or path.name=='.env.example'
            z.write(path,path.relative_to(ROOT).as_posix())
    write_json(ROOT/'handoff_archive.json',{'path':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':len(set(files)),'excluded':['.runtime','.venv','.env and other secrets','downloads','models','data/media','raw images and video']})
    print(target,target.stat().st_size,'bytes')

if __name__=='__main__':main()
