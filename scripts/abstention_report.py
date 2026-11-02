"""Audit coordination stops separately from JSON/network errors, without changing decisions."""
import argparse
import csv
import json
import os
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def mechanism(r,trace):
    if r['predicted_class']!='manual_review':return 'automatic'
    if r.get('errors',0):return 'api_or_validation_error'
    if r['rationale'] in ('Repeated recheck request; pipeline terminated','Recheck limit reached'):
        return 'recheck_protocol_stop'
    if r['rationale']=='An analyst abstained':
        requests=0
        for c in trace['trace']['calls']:
            try:requests+=json.loads(c.get('raw_response','{}')).get('request_check','none')!='none'
            except (ValueError,TypeError):pass
        if requests>1:return 'recheck_protocol_stop'
        return 'conservative_analyst_merge'
    return 'model_abstention'

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',default='local_evaluation_v1');args=p.parse_args()
    run=ROOT/'results'/args.run_id;rows=read_jsonl(run/'predictions.jsonl');sample=read_json(run/'sample.json')
    traces={(t['incident_id'],t['method']):t for t in read_jsonl(run/'traces.jsonl')}
    out=ROOT/'report_materials'/args.run_id;out.mkdir(exist_ok=True)
    counts={m:Counter(mechanism(r,traces[r['incident_id'],r['method']]) for r in rows if r['method']==m) for m in 'CDE'}
    write_json(out/'abstention_mechanisms.json',{m:dict(c) for m,c in counts.items()})
    with (out/'abstention_mechanisms.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['method','mechanism','count','all_incidents']);w.writeheader()
        w.writerows({'method':m,'mechanism':k,'count':v,'all_incidents':sample['n']} for m,c in counts.items() for k,v in c.items())
    text=['# Причины manual_review и корректность протокола','', 'Ошибки API/JSON/evidence_id и нарушение лимита повторной проверки — разные события. Валидный JSON не означает, что модель соблюла ограничение на инструменты. Все исходы остаются в общем знаменателе.','', '| Метод | Автоматически | Повторный запрос сверх лимита | Abstention аналитика → merge | Прямой abstention модели | Ошибка API/валидации |','|---|---:|---:|---:|---:|---:|---:|']
    for m,c in counts.items():
        text.append('| '+m+' | '+' | '.join(str(c[k]) for k in ['automatic','recheck_protocol_stop','conservative_analyst_merge','model_abstention','api_or_validation_error'])+' |')
    text+=['','Отказ recheck_protocol_stop сформирован оркестратором при повторном запросе или конкуренции запросов аналитиков за единственную проверку. Новая проверка сверх лимита не выполнялась. Это несовместимость поведения модели с выбранной политикой координации, а не подтверждение атаки и не обязательно осторожное reasoning.','', 'Для D одной финальной строки An analyst abstained недостаточно: анализируются raw request_check аналитиков. Если несколько запросов превышают общий лимит, причина отнесена к recheck_protocol_stop; в остальных случаях — к conservative_analyst_merge. Это отчётная классификация причин, она не меняет итоговые прогнозы.','', 'В D правило conservative_analyst_merge распространяет abstention любого аналитика на итог. Поэтому низкая автоматизация D может определяться выбранной политикой объединения и обработки инструментов, а не только классификационным reasoning.','', 'Результат характеризует данную модель, prompts и конкретный bounded protocol. Улучшение инструкций управления инструментами возможно только в следующем exploratory эксперименте с новым run_id; ответы этого прогона вручную не исправлялись.']
    (out/'abstention_analysis.md').write_text('\n'.join(text),encoding='utf-8')
    fig,ax=plt.subplots(figsize=(9,4));bottom=np.zeros(3)
    for k,label in [('automatic','Автоматическое решение'),('recheck_protocol_stop','Лимит проверок / конфликт запросов'),('conservative_analyst_merge','Отказ аналитика → объединение'),('model_abstention','Прямой отказ модели'),('api_or_validation_error','Ошибка API/валидации')]:
        values=np.array([counts[m][k] for m in 'CDE']);ax.bar(list('CDE'),values,bottom=bottom,label=label);bottom+=values
    ax.set(ylabel='Инциденты, шт.',title=f'Исходы и причины ручной проверки, n={sample["n"]} на метод');ax.legend(fontsize=8,bbox_to_anchor=(1.02,1),loc='upper left');fig.tight_layout()
    directory=ROOT/'figures'/args.run_id;directory.mkdir(exist_ok=True)
    fig.savefig(directory/'abstention_mechanisms.png',dpi=180);fig.savefig(directory/'abstention_mechanisms.svg');plt.close(fig)
    print('Abstention audit written')

if __name__=='__main__':main()
