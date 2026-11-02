"""Metrics, tables and figures for a v3 run, computed only from saved predictions/traces and labels."""
import argparse
import csv
import json
import os
from collections import Counter,defaultdict
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from triage.io import ROOT,read_json,read_jsonl,write_json

CLASSES=['bona_fide','presentation_attack','injection_attack']
COLS=CLASSES+['manual_review']
RUS={'bona_fide':'Подлинный','presentation_attack':'Предъявление','injection_attack':'Внедрение','manual_review':'Ручная проверка'}
SUBTYPE_TARGET={'virtual_camera':'virtual_camera','emulator':'emulator','hooking':'hooking','stealth':'stream_substitution','print':'print','screen_replay':'screen_replay'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})

def frac(num,den):return {'num':num,'den':den,'value':num/den if den else None}
def fmt(m):return 'N/A' if m['value'] is None else f"{m['num']}/{m['den']} ({m['value']:.3f})"

def evaluate(preds,labels):
    out={};matrices={}
    for method in sorted({p['method'] for p in preds}):
        rows=[p for p in preds if p['method']==method];truth=lambda p:labels[p['incident_id']]['scenario_class']
        att=[p for p in rows if truth(p)!='bona_fide'];bf=[p for p in rows if truth(p)=='bona_fide'];auto=[p for p in rows if p['verdict']!='manual_review']
        m={'n':len(rows)}
        f1=[]
        for c in CLASSES:
            tp=sum(p['verdict']==c and truth(p)==c for p in rows);fp=sum(p['verdict']==c and truth(p)!=c for p in rows);fn=sum(p['verdict']!=c and truth(p)==c for p in rows)
            m['precision_'+c]=frac(tp,tp+fp);m['recall_'+c]=frac(tp,tp+fn);m['f1_'+c]=frac(2*tp,2*tp+fp+fn);f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
        m['macro_f1']=sum(f1)/3
        m['attack_allow']=frac(sum(p['recommendation']=='allow' for p in att),len(att))
        m['attack_reverify']=frac(sum(p['recommendation']=='reverify' for p in att),len(att))
        m['benign_allow']=frac(sum(p['recommendation']=='allow' for p in bf),len(bf))
        m['benign_reverify']=frac(sum(p['recommendation']=='reverify' for p in bf),len(bf))
        m['benign_block']=frac(sum(p['recommendation']=='block_escalate' for p in bf),len(bf))
        m['manual_review']=frac(len(rows)-len(auto),len(rows));m['coverage']=frac(len(auto),len(rows))
        m['selective_accuracy']=frac(sum(p['verdict']==truth(p) for p in auto),len(auto))
        ia=[p for p in rows if truth(p)=='injection_attack']
        m['injection_as_presentation']=frac(sum(p['verdict']=='presentation_attack' for p in ia),len(ia))
        typed=[p for p in rows if truth(p)!='bona_fide' and p['verdict']==truth(p)]
        m['attack_type_correct_given_class']=frac(sum(p['attack_type']==SUBTYPE_TARGET[labels[p['incident_id']]['scenario_subtype']] for p in typed),len(typed))
        right=[p['confidence'] for p in auto if p['verdict']==truth(p)];wrong=[p['confidence'] for p in auto if p['verdict']!=truth(p)]
        m['mean_confidence_correct']=float(np.mean(right)) if right else None;m['mean_confidence_wrong']=float(np.mean(wrong)) if wrong else None
        m['risk_high_on_attacks']=frac(sum(p['risk_level']=='high' for p in att),len(att))
        m['mean_seconds']=float(np.mean([p['seconds'] for p in rows]));m['max_seconds']=float(max(p['seconds'] for p in rows))
        m['llm_calls']=sum(p['llm_calls'] for p in rows);m['tool_calls']=sum(p['tool_calls'] for p in rows)
        m['input_tokens']=sum(p['input_tokens'] for p in rows);m['output_tokens']=sum(p['output_tokens'] for p in rows)
        m['llm_errors']=sum(p['llm_errors'] for p in rows);m['fallbacks']=dict(Counter(p['fallback'] for p in rows if p['fallback']))
        if method.startswith('A_'):
            vis=lambda p:labels[p['incident_id']]['visual_source_label']
            live=[p for p in rows if vis(p)=='live'];spoof=[p for p in rows if vis(p)=='spoof']
            m['pad_bpcer']=frac(sum(p['verdict']!='bona_fide' for p in live),len(live));m['pad_apcer']=frac(sum(p['verdict']=='bona_fide' for p in spoof),len(spoof))
        out[method]=m
        matrices[method]=[[sum(truth(p)==r and p['verdict']==c for p in rows) for c in COLS] for r in CLASSES]
    return out,matrices

def team_audit(traces):
    share=Counter();events=Counter();rechecks=Counter();walls=[];analyst_overlap=[]
    for t in traces:
        if t['method']!='T':continue
        tr=t['trace'];walls.append(tr['wall_seconds'])
        for s in tr['steps']:share[(s['agent'],s['kind'])]+=1
        for e in tr['events']:
            events[e['kind']]+=1
            if e['kind']=='recheck':rechecks[e['agent']]+=1
        par=[s['seconds'] for s in tr['steps'] if s['kind']=='llm' and s['agent'] in ('liveness_analyst','channel_analyst','session_analyst') and s.get('name')=='analyse']
        if len(par)==3:analyst_overlap.append((sum(par),max(par)))
    total=sum(share.values());agents=sorted({a for a,_ in share})
    load={a:{'llm':share[(a,'llm')],'tool':share[(a,'tool')],'share':(share[(a,'llm')]+share[(a,'tool')])/total if total else None} for a in agents}
    return {'load':load,'events':dict(events),'rechecks_by_agent':dict(rechecks),'analyst_llm_seconds_sum_vs_max':{'sum':float(np.sum([a for a,_ in analyst_overlap])) if analyst_overlap else None,'max':float(np.sum([b for _,b in analyst_overlap])) if analyst_overlap else None},'mean_wall_seconds':float(np.mean(walls)) if walls else None}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);args=p.parse_args()
    run=ROOT/'results'/args.run_id;preds=read_jsonl(run/'predictions.jsonl');traces=read_jsonl(run/'traces.jsonl')
    labels={l['incident_id']:l for l in read_jsonl(ROOT/'experiments/v3_team/data/labels.jsonl')}
    metrics,matrices=evaluate(preds,labels);audit=team_audit(traces)
    out=ROOT/'report_materials'/args.run_id;fig=ROOT/'figures'/args.run_id;out.mkdir(parents=True,exist_ok=True);fig.mkdir(parents=True,exist_ok=True)
    write_json(out/'metrics.json',metrics);write_json(out/'confusion_matrices.json',{'rows':CLASSES,'columns':COLS,'methods':matrices});write_json(out/'team_audit.json',audit)
    with (out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['method','metric','numerator','denominator','value'])
        for m,vals in metrics.items():
            for k,v in vals.items():
                if isinstance(v,dict) and 'den' in v:w.writerow([m,k,v['num'],v['den'],'N/A' if v['value'] is None else v['value']])
                elif not isinstance(v,dict):w.writerow([m,k,'','',v])
    methods=list(metrics);n=metrics[methods[0]]['n']
    lines=[f'# Run {args.run_id}','',f'n = {n} инцидентов на метод; {dict(Counter(labels[i]["scenario_class"] for i in {p["incident_id"] for p in preds}))}.','',
           '| Метод | Macro-F1 | Пропуск атак (allow) | Атаки → reverify | Benign block | Benign allow | Ручная проверка | Selective acc. | Внедрение распознано | Внедрение → предъявление | Тип атаки верен |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in methods:
        v=metrics[m];lines.append(f"| {m} | {v['macro_f1']:.3f} | {fmt(v['attack_allow'])} | {fmt(v['attack_reverify'])} | {fmt(v['benign_block'])} | {fmt(v['benign_allow'])} | {fmt(v['manual_review'])} | {fmt(v['selective_accuracy'])} | {fmt(v['recall_injection_attack'])} | {fmt(v['injection_as_presentation'])} | {fmt(v['attack_type_correct_given_class'])} |")
    lines+=['','| Метод | LLM-вызовы | Вызовы инструментов | Токены вход/выход | Среднее время, с | Макс., с | Ошибки LLM | Fallback |','|---|---:|---:|---:|---:|---:|---:|---|']
    for m in methods:
        v=metrics[m];lines.append(f"| {m} | {v['llm_calls']} | {v['tool_calls']} | {v['input_tokens']}/{v['output_tokens']} | {v['mean_seconds']:.1f} | {v['max_seconds']:.1f} | {v['llm_errors']} | {v['fallbacks'] or '—'} |")
    for m in methods:
        if m.startswith('A_'):lines.append(f"\n{m}: APCER {fmt(metrics[m]['pad_apcer'])}, BPCER {fmt(metrics[m]['pad_bpcer'])} (по визуальной метке OULU).")
    if audit['load']:
        lines+=['','## Команда T: распределение нагрузки (план, табл. 4: доля одного агента ≤ 40%)','','| Агент | LLM | Инструменты | Доля |','|---|---:|---:|---:|']
        for a,v in audit['load'].items():lines.append(f"| {a} | {v['llm']} | {v['tool']} | {v['share']:.1%} |")
        lines+=['',f"События: {audit['events']}; перепроверки по агентам: {audit['rechecks_by_agent']}. Сумма времени LLM трёх анализаторов {audit['analyst_llm_seconds_sum_vs_max']['sum']:.0f} с против {audit['analyst_llm_seconds_sum_vs_max']['max']:.0f} с по самому медленному (параллельный запуск)." if audit['analyst_llm_seconds_sum_vs_max']['sum'] else '']
    cache=read_json(ROOT/'experiments/v3_team/data/visual_cache.json');pad=Counter()
    for iid in {p['incident_id'] for p in preds}:
        l=labels[iid];c=cache[l['source_id']]
        if c['minifasnet']['status']=='ok':pad[(c['minifasnet']['pad_label'],c['thesis_vjune']['pad_label'],l['visual_source_label'],l['source_artifact'])]+=1
    write_json(out/'pad_disagreement.json',[{'minifasnet':a,'thesis_vjune':b,'oulu_label':v,'artifact':art,'n':n} for (a,b,v,art),n in sorted(pad.items())])
    lines+=['','## Расхождения PAD-моделей (кадры инцидентов, без учёта контролируемых сбоев)','','| MiniFASNetV2 | V_june | Метка OULU | Артефакт | n |','|---|---|---|---|---:|']
    lines+=[f'| {a} | {b} | {v} | {art} | {n} |' for (a,b,v,art),n in sorted(pad.items())]
    lines+=['','Allow на атаке — опасный допуск. Reverify — повторная попытка, не допуск. Ручная проверка — отказ от автоматического решения, учитывается в знаменателях. Статистическая значимость не заявляется.']
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    # Figures
    show=[m for m in methods if m in ('B','C','T')]
    if show:
        f,axes=plt.subplots(1,len(show),figsize=(5*len(show),4))
        for ax,m in zip(np.atleast_1d(axes),show):
            a=np.array(matrices[m]);ax.imshow(a,cmap='Blues',vmin=0)
            ax.set_xticks(range(4),[RUS[c] for c in COLS],rotation=25,ha='right');ax.set_yticks(range(3),[RUS[c] for c in CLASSES]);ax.set_title(f'Метод {m}')
            for (y,x),v in np.ndenumerate(a):ax.text(x,y,str(v),ha='center',va='center',color='white' if v>a.max()/2 else 'black')
        f.tight_layout();f.savefig(fig/'confusion.png',dpi=160);f.savefig(fig/'confusion.svg');plt.close(f)
    f,ax=plt.subplots(figsize=(9,4));x=np.arange(len(methods));keys=[('attack_allow','Пропуск атак'),('benign_block','Блокировка подлинных'),('manual_review','Ручная проверка')]
    for j,(k,lab) in enumerate(keys):ax.bar(x+(j-1)*.26,[100*(metrics[m][k]['value'] or 0) for m in methods],.26,label=lab)
    ax.set_xticks(x,methods);ax.set_ylabel('%');ax.set_title(f'Исходы триажа, n={n} на метод');ax.legend(fontsize=8);f.tight_layout();f.savefig(fig/'rates.png',dpi=160);f.savefig(fig/'rates.svg');plt.close(f)
    if audit['load']:
        f,ax=plt.subplots(figsize=(8,4));names=list(audit['load']);ax.bar(names,[100*audit['load'][a]['share'] for a in names]);ax.axhline(40,color='red',ls='--',label='порог 40%')
        ax.set_ylabel('Доля вызовов, %');ax.set_title('Команда T: распределение вызовов LLM и инструментов');ax.tick_params(axis='x',rotation=20);ax.legend();f.tight_layout();f.savefig(fig/'load_share.png',dpi=160);f.savefig(fig/'load_share.svg');plt.close(f)
    print((out/'summary.md').read_text())

if __name__=='__main__':main()
