"""New compact archive; keep all earlier archives and experiments unchanged."""
import hashlib
import io
import zipfile
from triage.io import ROOT,write_json

def forbidden(name):
    from pathlib import PurePosixPath
    return name.startswith(('.runtime/','.venv/','downloads/','models/','data/media/')) or (PurePosixPath(name).name.startswith('.env') and PurePosixPath(name).name!='.env.example')

def main():
    target=ROOT/'research_triage_protocol_v2.zip'
    if target.exists():raise SystemExit('Do not overwrite the final v2 archive')
    files=[ROOT/n for n in ['README.md','requirements.txt','requirements-lock.txt','pytest.ini','.gitignore','.env.example']]
    for root in ['triage','scripts','tests','docs','report_materials','results','figures']:
        files.extend(p for p in (ROOT/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.zip'])
    files.extend(p for p in (ROOT/'data').glob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md'])
    files.extend([ROOT/'snapshots/protocol_v1_before_v2.zip',ROOT/'snapshots/protocol_v1_manifest.json'])
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for file in sorted(set(files)):
            name=file.relative_to(ROOT).as_posix()
            if forbidden(name):raise RuntimeError('Forbidden archive path')
            z.write(file,name)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None and not any(forbidden(n) for n in z.namelist())
        with zipfile.ZipFile(io.BytesIO(z.read('snapshots/protocol_v1_before_v2.zip'))) as snapshot:
            assert snapshot.testzip() is None and not any(forbidden(n) for n in snapshot.namelist())
    write_json(ROOT/'protocol_v2_handoff_archive.json',{'path':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':len(set(files)),'includes_original_snapshot':True,'runtime_weights_faces_secrets_excluded':True})
    print(target,target.stat().st_size,'bytes; outer and nested snapshot integrity checked')

if __name__=='__main__':main()
