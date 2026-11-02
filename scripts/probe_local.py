"""Read-only hardware/server probe; no environment values or credential files."""
import ctypes
import json
import os
import platform
import shutil
import socket
import urllib.request
import winreg
from pathlib import Path

class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','total_page','available_page','total_virtual','available_virtual','extended']]

def main():
    m=Memory();m.length=ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    info={'ram_total_gib':m.total/2**30,'ram_available_gib':m.available/2**30,'cpu_threads':os.cpu_count(),'cpu':platform.processor(),'disk_free_gib':shutil.disk_usage('.').free/2**30,'servers':{},'model_files':[]}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as k:
            info['cpu_model']=winreg.QueryValueEx(k,'ProcessorNameString')[0].strip()
    except OSError:info['cpu_model']=None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for port,route in [(11434,'/api/tags'),(1234,'/v1/models'),(8080,'/v1/models')]:
        try:
            with opener.open(f'http://127.0.0.1:{port}{route}',timeout=2) as r:info['servers'][str(port)]=json.load(r)
        except Exception as e:info['servers'][str(port)]={'available':False,'error_type':type(e).__name__}
    home=Path.home()
    for p in [home/'.ollama/models',home/'.cache/lm-studio/models',home/'.lmstudio/models',home/'.cache/huggingface/hub']:
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and (f.suffix=='.gguf' or f.name.startswith('sha256-') or f.suffix=='.safetensors'):
                    info['model_files'].append({'path':str(f),'bytes':f.stat().st_size})
    print(json.dumps(info,indent=2))
    root=Path(__file__).resolve().parents[1]
    (root/'results/local_feasibility').mkdir(exist_ok=True)
    (root/'results/local_feasibility/hardware.json').write_text(json.dumps(info,indent=2),encoding='utf-8')

if __name__=='__main__':main()
