"""Small, auditable public downloads. No credential files or authentication."""
import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(url, path):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        req = urllib.request.Request(url, headers={'User-Agent': 'ResearchTriage/1.0'})
        with OPENER.open(req, timeout=120) as r, path.with_suffix(path.suffix+'.part').open('wb') as f:
            while block := r.read(1024*1024):
                f.write(block)
        path.with_suffix(path.suffix+'.part').replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    urls = {
        'models/MiniFASNetV2.onnx': 'https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx',
        'models/deploy.prototxt': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/resources/detection_model/deploy.prototxt',
        'models/detector.caffemodel': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/resources/detection_model/Widerface-RetinaFace.caffemodel',
        'downloads/PAD_LICENSE': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/LICENSE',
        'downloads/ONNX_LICENSE': 'https://raw.githubusercontent.com/yakhyo/face-anti-spoofing/main/LICENSE',
        'downloads/axon_card.md': 'https://huggingface.co/datasets/AxonData/Display_replay_attacks/raw/main/README.md',
        'downloads/upstream_test.py': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/test.py',
        'downloads/upstream_predict.py': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/src/anti_spoof_predict.py',
        'downloads/upstream_crop.py': 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/src/generate_patches.py',
        'downloads/onnx_inference.py': 'https://raw.githubusercontent.com/yakhyo/face-anti-spoofing/main/onnx_inference.py',
    }
    manifest=[]
    for i, name in enumerate(['image_T1.jpg','image_F1.jpg','image_F2.jpg']):
        manifest.append(dict(source_id=f'd{i}',group_id='upstream_demo',split='debug',visual_label='live' if i==0 else 'spoof',path=f'downloads/d{i}.jpg',url='https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/images/sample/'+name,kind='image',license='Apache-2.0 repository; image rights not separately documented'))
    tree_url='https://huggingface.co/api/datasets/AxonData/Display_replay_attacks/tree/main?recursive=true&limit=100'
    with OPENER.open(tree_url,timeout=30) as r:
        tree=json.load(r)
    media=[x for x in tree if x['path'].lower().endswith(('.jpg','.mp4','.mov'))]
    total=sum(x['size'] for x in media)
    print('Axon public sample bytes:',total,flush=True)
    assert total < 200_000_000, 'Review unexpectedly large download before proceeding'
    for i,x in enumerate(media):
        sid=f'a{i:02d}'
        manifest.append(dict(source_id=sid,group_id='axon_public_sample',split='evaluation',visual_label='live' if '/Real/' in x['path'] else 'spoof',path=f'downloads/{sid}'+pathlib.Path(x['path']).suffix.lower(),url='https://huggingface.co/datasets/AxonData/Display_replay_attacks/resolve/main/'+urllib.parse.quote(x['path'],safe='/'),kind='image' if x['path'].endswith('.jpg') else 'video',license='CC-BY-4.0 declared in dataset card',expected_sha256=x.get('lfs',{}).get('oid')))
    errors=[]
    for path,url in urls.items():
        try:
            print('Download',path,flush=True)
            get(url,ROOT/path)
        except Exception as e:
            errors.append({'path':path,'error':type(e).__name__})
    for m in manifest:
        try:
            print('Download',m['source_id'],flush=True)
            m['sha256']=get(m['url'],ROOT/m['path'])
            if m.get('expected_sha256'):
                assert m['sha256']==m['expected_sha256']
            m['status']='downloaded'
        except Exception as e:
            m['status']='error';m['error']=type(e).__name__
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data/source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'data/download_errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    print('Complete. Errors:',errors,flush=True)

if __name__=='__main__':main()
