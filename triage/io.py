import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
def write_jsonl(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
