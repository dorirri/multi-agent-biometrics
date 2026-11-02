"""Public source discovery, deduplication, unchanged generator logic and real PAD."""
import argparse
import ast
import hashlib
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path
import cv2
import numpy as np
from triage.io import ROOT,read_json,write_json,write_jsonl

EXP=ROOT/'experiments/local_protocol_v2_holdout'
DATA=EXP/'data'
DATASET='AxonData/face-anti-spoofing-dataset'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
SEED=20261102

def fetch_json(url):
    with OPENER.open(urllib.request.Request(url,headers={'User-Agent':'ResearchTriage/1.0'}),timeout=40) as r:return json.load(r)

def download(url,target,expected=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with OPENER.open(urllib.request.Request(url,headers={'User-Agent':'ResearchTriage/1.0'}),timeout=90) as r,target.with_suffix(target.suffix+'.part').open('wb') as f:
            while chunk:=r.read(1024*1024):f.write(chunk)
        target.with_suffix(target.suffix+'.part').replace(target)
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    if expected and sha!=expected:raise ValueError('Media SHA mismatch')
    return sha

def phash(img):
    a=cv2.resize(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32)
    d=cv2.dct(a)[:8,:8];bits=d>np.median(d.reshape(-1)[1:])
    return int(''.join('1' if b else '0' for b in bits.flat),2)

def frames(source):
    if source['kind']=='image':return [(0,cv2.imread(str(ROOT/source['path'])))]
    cap=cv2.VideoCapture(str(ROOT/source['path']));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));out=[]
    for frac in [.2,.5,.8]:
        idx=int(max(0,count-1)*frac);cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,img=cap.read();out.append((idx,img if ok else None))
    cap.release();return out

def obtain():
    DATA.mkdir(parents=True,exist_ok=True)
    info=fetch_json('https://huggingface.co/api/datasets/'+DATASET);rev=info['sha']
    tree=fetch_json(f'https://huggingface.co/api/datasets/{DATASET}/tree/{rev}?recursive=true&limit=1000')
    old=read_json(ROOT/'data/source_manifest.json');oldsha={s['sha256'] for s in old}
    oldpaths={urllib.parse.unquote(s['url'].split('/main/')[-1]) for s in old}
    excluded=[x['path'] for x in tree if x.get('lfs',{}).get('oid') in oldsha]
    real=sorted([x for x in tree if x['path'].startswith('Selfies/') and x['path'].endswith('.jpg') and x.get('lfs',{}).get('oid') not in oldsha],key=lambda x:x['path'])[:4]
    categories=['3D_paper_mask ','Cutout_attacks','Latex_mask','Silicone_mask']
    attacks=[]
    for category in categories:
        pool=sorted([x for x in tree if x['path'].startswith(category+'/') and x['path'].lower().endswith(('.mp4','.mov')) and x.get('lfs',{}).get('oid') not in oldsha],key=lambda x:x['path'])
        if pool:attacks.append(pool[0])
    selected=real+attacks
    assert len(real)==4 and len(attacks)==4,'Need eight genuinely unused source candidates'
    size=sum(x['size'] for x in selected);assert size<220_000_000
    print('Selected source bytes:',size,flush=True)
    base=f'https://huggingface.co/datasets/{DATASET}/resolve/{rev}/'
    card=ROOT/'downloads/holdout/dataset_card.md';download(base+'README.md',card)
    write_json(DATA/'discovery.json',{'dataset':DATASET,'revision':rev,'license':'CC-BY-NC-4.0 declared in card; public sample for noncommercial research','card_sha256':hashlib.sha256(card.read_bytes()).hexdigest(),'excluded_old_hash_matches':excluded,'selection_rule':'first four lexicographic unused Selfies; first lexicographic video in predeclared 3D paper, cutout, latex, silicone categories; no PAD or LLM outputs used','selected_bytes':size,'selection_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'no_subject_independence_claim':True})
    manifest=[]
    for i,x in enumerate(selected):
        sid=f'h{i:02d}';p=ROOT/'downloads/holdout'/(sid+Path(x['path']).suffix.lower());url=base+urllib.parse.quote(x['path'],safe='/')
        print('Download',sid,x['size'],flush=True);sha=download(url,p,x['lfs']['oid'])
        assert sha not in oldsha
        manifest.append({'source_id':sid,'group_id':'axon_additional_public_sample','split':'holdout','visual_label':'live' if i<4 else 'spoof','kind':'image' if i<4 else 'video','path':p.relative_to(ROOT).as_posix(),'url':url,'provider_path':x['path'],'dataset_revision':rev,'sha256':sha,'bytes':x['size'],'license':'CC-BY-NC-4.0','status':'downloaded'})
    write_json(DATA/'source_manifest.json',manifest)
    # Decoded frames are compared too; no scores/classes from PAD are consulted here.
    old_frames=[]
    for f in read_json(ROOT/'data/frame_manifest.json'):
        img=cv2.imread(str(ROOT/f['path']))
        if img is not None:old_frames.append((f['source_id'],img,phash(img)))
    samples=[];audits=[];decoded=[]
    for s in manifest:
        for idx,img in frames(s):
            if img is None:raise ValueError('Undecodable source frame')
            p=ROOT/'downloads/holdout_frames'/f'{s["source_id"]}_{idx}.jpg';p.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(p),img)
            digest=hashlib.sha256(img.tobytes()).hexdigest();h=phash(img)
            nearest=min(((h^o[2]).bit_count(),o[0]) for o in old_frames)
            audits.append({'source_id':s['source_id'],'frame_index':idx,'nearest_old_source':nearest[1],'phash_distance_old':nearest[0],'phash64':f'{h:016x}','decoded_pixel_sha256':digest})
            decoded.append({'source_id':s['source_id'],'frame_index':idx,'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
            samples.append((s['source_id'],img))
    # Save contact sheet for local visual inspection only, never in transfer archive.
    thumbnails=[]
    for name,img,_ in old_frames:thumbnails.append((name,img))
    thumbnails+=samples
    tiles=[]
    for name,img in thumbnails:
        tile=np.full((180,180,3),245,np.uint8);scale=min(176/img.shape[1],150/img.shape[0]);im=cv2.resize(img,(int(img.shape[1]*scale),int(img.shape[0]*scale)));tile[:im.shape[0],:im.shape[1]]=im;cv2.putText(tile,name,(6,172),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1);tiles.append(tile)
    while len(tiles)%8:tiles.append(np.full((180,180,3),245,np.uint8))
    sheet=np.vstack([np.hstack(tiles[i:i+8]) for i in range(0,len(tiles),8)])
    cv2.imwrite(str(ROOT/'downloads/holdout_contact_sheet.jpg'),sheet)
    write_json(DATA/'frame_manifest.json',decoded)
    write_json(DATA/'overlap_audit.json',{'old_sources_checked':len(old),'old_decoded_frames_checked':len(old_frames),'new_sources':len(manifest),'exact_source_hash_overlap':[],'new_source_hashes_unique':len(set(s['sha256'] for s in manifest))==len(manifest),'frame_phash_audit':audits,'potential_near_duplicates_threshold_le_8':[a for a in audits if a['phash_distance_old']<=8],'identity_independence_not_proven':True,'limitations':'64-bit whole-frame pHash is not identity matching; changes in crop/background can evade it. Visual inspection required before acceptance.'})
    print('Downloaded and dedup audited; contact sheet ready',flush=True)

def generate():
    # Parameterize ONLY the original cohort loop, retaining the exact scenario AST.
    original=ROOT/'scripts/generate.py';tree=ast.parse(original.read_text(encoding='utf-8'));changes=0
    for node in ast.walk(tree):
        if isinstance(node,ast.For) and isinstance(node.target,ast.Tuple) and [x.id for x in node.target.elts if isinstance(x,ast.Name)]==['split','n']:
            node.iter=ast.parse("[('holdout',18)]",mode='eval').body;changes+=1
    assert changes==1
    ast.fix_missing_locations(tree);ns={'__name__':'holdout_original_generator'};exec(compile(tree,str(original),'exec'),ns);ns['ROOT']=EXP;ns['main'](SEED)
    write_json(DATA/'generation_config.json',{'seed':SEED,'n':18,'per_class':6,'unique_sources':8,'generator_source':'scripts/generate.py','generator_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'only_parameterization':"cohort loop [('debug',10),('evaluation',60)] -> [('holdout',18)]; ROOT/output directory; random scenario logic unchanged",'rng_warmup_debug_removed':True,'synthetic_fields':['delivery scenario','channel','history','client note','controlled tool fault'],'no_model_output_selection':True})

def extract_pad():
    from triage.pad import PAD
    pad=PAD();cache={};model_sha=hashlib.sha256((ROOT/'models/MiniFASNetV2.onnx').read_bytes()).hexdigest()
    for s in read_json(DATA/'source_manifest.json'):
        images=frames(s);outputs=[];start=time.perf_counter()
        for idx,img in images:
            t=time.perf_counter();entry={'frame_index':idx}
            try:entry.update(status='ok',values=pad.predict(img))
            except Exception as exc:entry.update(status='error',error=str(exc))
            entry['seconds']=time.perf_counter()-t;outputs.append(entry)
        vals=[o['values'] for o in outputs if o['status']=='ok']
        if vals:
            scores=np.mean([v['softmax'] for v in vals],axis=0)
            values={'pad_label':'live' if int(scores.argmax())==1 else 'spoof','live_score':float(scores[1]),'frame_count':len(outputs),'valid_frame_count':len(vals),'live_score_range':float(max(v['live_score'] for v in vals)-min(v['live_score'] for v in vals)),'scores_calibrated':False}
        else:values={}
        cache[s['source_id']]={'status':'ok' if len(vals)==len(outputs) and vals else 'error','values':values,'frames':outputs,'feature_seconds':time.perf_counter()-start,'model_sha256':model_sha,'source_sha256':s['sha256']}
        print('Real PAD',s['source_id'],cache[s['source_id']]['status'],flush=True)
    write_json(DATA/'visual_cache.json',cache)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['obtain','generate','pad']);a=p.parse_args()
    {'obtain':obtain,'generate':generate,'pad':extract_pad}[a.stage]()
