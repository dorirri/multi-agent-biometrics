"""Local CPU PAD; original detector and boundary-shift crop, ONNX V2 logits."""
import hashlib
import math
import time
import cv2
import numpy as np
import onnxruntime as ort
from triage.io import ROOT,read_json,write_json

class PAD:
    def __init__(self):
        self.det=cv2.dnn.readNetFromCaffe(str(ROOT/'models/deploy.prototxt'),str(ROOT/'models/detector.caffemodel'))
        opts=ort.SessionOptions();opts.intra_op_num_threads=2
        self.net=ort.InferenceSession(str(ROOT/'models/MiniFASNetV2.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
        self.name=self.net.get_inputs()[0].name

    def predict(self,img):
        if img is None:raise ValueError('unreadable_frame')
        h,w=img.shape[:2]
        aspect=w/h
        resized=cv2.resize(img,(int(192*math.sqrt(aspect)),int(192/math.sqrt(aspect)))) if w*h>=192**2 else img
        self.det.setInput(cv2.dnn.blobFromImage(resized,1,mean=(104,117,123)),'data')
        out=self.det.forward('detection_out').reshape(-1,7)
        found=out[out[:,2]>=.6]
        if len(found)!=1:raise ValueError('face_count_'+str(len(found)))
        row=found[0]
        x,y,xr,yr=row[3:7]*[w,h,w,h]
        bw,bh=xr-x+1,yr-y+1
        if bw<=0 or bh<=0:raise ValueError('invalid_bbox')
        scale=min((h-1)/bh,(w-1)/bw,2.7)
        nw,nh=bw*scale,bh*scale
        cx,cy=x+bw/2,y+bh/2
        l,t,r,b=cx-nw/2,cy-nh/2,cx+nw/2,cy+nh/2
        if l<0:r-=l;l=0
        if t<0:b-=t;t=0
        if r>w-1:l-=r-w+1;r=w-1
        if b>h-1:t-=b-h+1;b=h-1
        crop=img[int(t):int(b)+1,int(l):int(r)+1]
        tensor=cv2.resize(crop,(80,80)).astype(np.float32).transpose(2,0,1)[None]
        logits=self.net.run(None,{self.name:tensor})[0].reshape(-1)
        if logits.shape!=(3,) or not np.isfinite(logits).all():raise ValueError('invalid_logits')
        soft=np.exp(logits-logits.max());soft/=soft.sum()
        idx=int(soft.argmax())
        return {'pad_label':'live' if idx==1 else 'spoof','live_score':float(soft[1]),'softmax':soft.tolist(),'face_count':len(found),'detector_score':float(row[2]),'blur_laplacian_var':float(cv2.Laplacian(crop,cv2.CV_64F).var()),'brightness':float(crop.mean()),'scores_calibrated':False}

def extract():
    pad=PAD();rows={};frame_manifest=[]
    modelhash=hashlib.sha256((ROOT/'models/MiniFASNetV2.onnx').read_bytes()).hexdigest()
    for s in read_json(ROOT/'data/source_manifest.json'):
        if s['status']!='downloaded':continue
        frames=[]
        if s['kind']=='image':frames=[(0,cv2.imread(str(ROOT/s['path'])))]
        else:
            cap=cv2.VideoCapture(str(ROOT/s['path']));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for frac in [.2,.5,.8]:
                idx=int(max(0,count-1)*frac);cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
                ok,img=cap.read();frames.append((idx,img if ok else None))
            cap.release()
        outputs=[];start=time.perf_counter()
        for j,(idx,img) in enumerate(frames):
            entry={'frame_index':idx};t=time.perf_counter()
            try:entry.update(status='ok',values=pad.predict(img))
            except Exception as e:entry.update(status='error',error=str(e))
            entry['seconds']=time.perf_counter()-t;outputs.append(entry)
            if img is not None:
                p=ROOT/'data/media'/f'{s["source_id"]}_{j}.jpg';p.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(p),img)
                frame_manifest.append({'source_id':s['source_id'],'frame_index':idx,'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        vals=[x['values'] for x in outputs if x['status']=='ok']
        if vals:
            scores=np.mean([v['softmax'] for v in vals],axis=0)
            value={'pad_label':'live' if int(scores.argmax())==1 else 'spoof','live_score':float(scores[1]),'frame_count':len(outputs),'valid_frame_count':len(vals),'live_score_range':float(max(v['live_score'] for v in vals)-min(v['live_score'] for v in vals)),'scores_calibrated':False}
        else:value={}
        rows[s['source_id']]={'status':'ok' if len(vals)==len(outputs) and vals else 'error','values':value,'frames':outputs,'feature_seconds':time.perf_counter()-start,'model_sha256':modelhash,'source_sha256':s['sha256']}
        print(s['source_id'],rows[s['source_id']]['status'],value,flush=True)
    write_json(ROOT/'data/visual_cache.json',rows);write_json(ROOT/'data/frame_manifest.json',frame_manifest)

if __name__=='__main__':extract()
