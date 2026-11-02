import hashlib
import io
import zipfile
from triage.io import ROOT,write_json

def forbidden(name):
    from pathlib import PurePosixPath
    return name.startswith(('.runtime/','.venv/','downloads/','models/','data/media/')) or (PurePosixPath(name).name.startswith('.env') and PurePosixPath(name).name!='.env.example') or PurePosixPath(name).suffix.lower() in ['.gguf','.onnx','.caffemodel','.mp4','.mov','.jpg','.jpeg']

def main():
    target=ROOT/'research_triage_holdout_handoff.zip'
    if target.exists():raise SystemExit('Never overwrite an existing handoff archive')
    files=[ROOT/n for n in ['README.md','requirements.txt','requirements-lock.txt','pytest.ini','.gitignore','.env.example']]
    for root in ['triage','scripts','tests','docs','report_materials','results','figures']:
        files.extend(p for p in (ROOT/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.zip'])
    files.extend(p for p in (ROOT/'data').glob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md'])
    files.extend(p for p in (ROOT/'experiments/local_protocol_v2_holdout').rglob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md'])
    files.extend([ROOT/'snapshots/protocol_v2_before_holdout.zip',ROOT/'snapshots/protocol_v2_before_holdout_manifest.json'])
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(set(files)):
            name=p.relative_to(ROOT).as_posix()
            if forbidden(name):raise RuntimeError('Forbidden archive asset: '+name)
            z.write(p,name)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None and not any(forbidden(n) for n in z.namelist())
        with zipfile.ZipFile(io.BytesIO(z.read('snapshots/protocol_v2_before_holdout.zip'))) as nested:
            assert nested.testzip() is None and not any(forbidden(n) for n in nested.namelist())
    write_json(ROOT/'holdout_handoff_archive.json',{'path':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':len(set(files)),'includes_saved_results_without_models':True,'fully_autonomous':False,'external_downloads_for_full_compute':['public media approximately 180 MB','Qwen GGUF approximately 1.12 GB','PAD weights/detector','llama.cpp runtime/Python dependencies'],'weights_runtime_faces_secrets_excluded':True})
    print(target,target.stat().st_size,'bytes; integrity and exclusions checked')

if __name__=='__main__':main()
