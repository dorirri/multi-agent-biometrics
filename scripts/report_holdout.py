"""Read-only result analysis, explicit denominators, separate old/new samples."""
import csv
import argparse
import json
import os
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json,write_jsonl
from triage.metrics import evaluate,CLASSES
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})

DATA=ROOT/'experiments/local_protocol_v2_holdout/data'
RUN=ROOT/'results/local_protocol_v2_holdout'
OUT=ROOT/'report_materials/local_protocol_v2_holdout'
FIG=OUT/'figures'
RU={'bona_fide':'Доброкачественный','presentation_attack':'Предъявление','injection_attack':'Внедрение','manual_review':'Ручная проверка'}

def csv_save(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
        w.writerows({k:'N/A' if v is None else v for k,v in r.items()} for r in rows)

def extra_metrics(rows,labels):
    out=[];truth={l['incident_id']:l['scenario_class'] for l in labels}
    for m in 'BCDE':
        rr=[r for r in rows if r['method']==m];n=len(rr)
        if not rr:continue
        def add(name,num,den):out.append({'method':m,'metric':name,'value':num/den if den else None,'numerator':num,'denominator':den,'n':n})
        for cls in ['presentation_attack','injection_attack']:
            subset=[r for r in rr if truth[r['incident_id']]==cls]
            add(cls+'_allow_rate',sum(r['recommendation']=='allow' for r in subset),len(subset))
        benign=[r for r in rr if truth[r['incident_id']]=='bona_fide']
        add('benign_escalate_rate',sum(r['recommendation']=='escalate' for r in benign),len(benign))
        add('predicted_injection_rate',sum(r['predicted_class']=='injection_attack' for r in rr),n)
        add('correct_auto_count_per_all',sum(r['predicted_class']==truth[r['incident_id']] and r['predicted_class']!='manual_review' for r in rr),n)
        add('total_calls',sum(r['calls'] for r in rr),1)
        add('total_input_tokens_known',sum(r['input_tokens'] for r in rr),1)
        add('total_output_tokens_known',sum(r['output_tokens'] for r in rr),1)
        add('usage_missing_calls',sum(r.get('usage_missing_calls',0) for r in rr),1)
        add('triage_total_seconds',sum(r['triage_seconds'] for r in rr),1)
    return out

def main():
    global RUN,OUT,FIG
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='local_protocol_v2_holdout');args=parser.parse_args()
    RUN=ROOT/'results'/args.run_id;OUT=ROOT/'report_materials'/args.run_id;FIG=OUT/'figures'
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(exist_ok=True)
    predictions=read_jsonl(RUN/'predictions.jsonl');labels=read_jsonl(DATA/'labels.jsonl');incidents=read_jsonl(DATA/'incidents.jsonl')
    truth={l['incident_id']:l for l in labels};traces={(t['method'],t['incident_id']):t for t in read_jsonl(RUN/'traces.jsonl')}
    expected=set(i['incident_id'] for i in incidents);completion=read_json(RUN/'completion.json')
    sets={m:{r['incident_id'] for r in predictions if r['method']==m} for m in 'BCDE'}
    common=set.intersection(*sets.values());complete=completion['completed'] and all(s==expected for s in sets.values())
    pending=[{'method':m,'incident_id':iid,'status':'not_completed','reason':'see completion/inflight/time budget'} for m in 'BCDE' for iid in sorted(expected-sets[m])]
    write_jsonl(OUT/'unfinished_cases.jsonl',pending)
    available,_=evaluate(predictions,labels);available+=extra_metrics(predictions,labels);csv_save(OUT/'metrics_all_available.csv',available)
    primary=[r for r in predictions if r['incident_id'] in common]
    metrics,matrices=evaluate(primary,labels);metrics+=extra_metrics(primary,labels)
    csv_save(OUT/'metrics.csv',metrics);write_json(OUT/'confusion_matrices.json',matrices)
    cm_rows=[{'method':m,'true_class':a,'predicted_class':b,'count':d['counts'][i][j],'method_n':d['n']} for m,d in matrices.items() for i,a in enumerate(d['rows']) for j,b in enumerate(d['columns'])]
    csv_save(OUT/'confusion_matrices.csv',cm_rows)
    lookup={(r['method'],r['metric']):r for r in metrics}
    def frac(m,k):
        r=lookup.get((m,k))
        return 'N/A' if not r or r['value'] is None else f'{r["numerator"]}/{r["denominator"]} ({r["value"]:.3f})'
    def value(m,k):
        r=lookup.get((m,k));return r['value'] if r else None
    attribution=[]
    for m in 'BCDE':
        rr=[r for r in primary if r['method']==m];inj=[r for r in rr if truth[r['incident_id']]['scenario_class']=='injection_attack']
        attribution.append({'method':m,'n':len(rr),'predicted_injection_count':sum(r['predicted_class']=='injection_attack' for r in rr),'true_injection_n':len(inj),'correct_injection':sum(r['predicted_class']=='injection_attack' for r in inj),'injection_rejected_as_presentation':sum(r['predicted_class']=='presentation_attack' for r in inj),'injection_allowed':sum(r['recommendation']=='allow' for r in inj),'injection_review':sum(r['predicted_class']=='manual_review' for r in inj)})
    csv_save(OUT/'mechanism_attribution.csv',attribution)
    def save(fig,name):
        fig.tight_layout();fig.savefig(FIG/(name+'.png'),dpi=180);fig.savefig(FIG/(name+'.svg'));plt.close(fig)
    if common:
        fig,axes=plt.subplots(1,3,figsize=(13,4));methods=list('BCDE')
        for ax,key,title in zip(axes,['attack_allow_rate','benign_reject_rate','manual_review_rate'],['Опасные допуски среди атак','Доброкачественные: жёсткий отказ','Ручная проверка среди всех']):
            heights=[100*(value(m,key) or 0) for m in methods];ax.bar(methods,heights,color=['#779966','#4477aa','#cc9944','#aa5577'])
            for x,m,h in zip(range(4),methods,heights):
                rr=lookup[m,key];ax.text(x,h+2,f'{rr["numerator"]}/{rr["denominator"]}',ha='center')
            ax.set(title=title,ylabel='Доля, %',ylim=(0,112))
        fig.suptitle(f'Новые источники: общий завершённый набор n={len(common)} на метод');save(fig,'holdout_rates')
        fig,axes=plt.subplots(2,2,figsize=(12,9))
        for ax,m in zip(axes.flat,methods):
            d=matrices[m];a=np.array(d['counts']);ax.imshow(a,cmap='Blues',vmin=0)
            ax.set_xticks(range(4),[RU[c] for c in d['columns']],rotation=20,ha='right');ax.set_yticks(range(3),[RU[c] for c in d['rows']]);ax.set(title=f'{m}, n={d["n"]}',xlabel='Решение',ylabel='Сценарная истина')
            for (y,x),v in np.ndenumerate(a):ax.text(x,y,str(v),ha='center',va='center',color='white' if v>a.max()/2 else 'black')
        fig.suptitle('Матрицы ошибок: новые медиа, числа инцидентов');save(fig,'holdout_confusion_BCDE')
        fig,axes=plt.subplots(1,2,figsize=(10,4));axes[0].bar(methods,[value(m,'triage_mean_seconds') for m in methods]);axes[0].set(ylabel='Секунды/инцидент',title='Время триажа, без PAD')
        axes[1].bar(methods,[value(m,'known_input_tokens_per_incident')+value(m,'known_output_tokens_per_incident') for m in methods]);axes[1].set(ylabel='Известные токены/инцидент, шт.',title='Входные и выходные токены');save(fig,'holdout_time_tokens')
    # Old and new cohorts are separate, never pooled or paired.
    oldids=set(read_json(ROOT/'results/local_protocol_v2/sample.json')['incident_ids'])
    oldrows=[r for r in read_jsonl(ROOT/'results/local_protocol_v2/predictions.jsonl') if r['method'] in 'CDE']
    oldrows += [r for r in read_jsonl(ROOT/'results/local_evaluation_v1/predictions.jsonl') if r['method']=='B' and r['incident_id'] in oldids]
    oldlabels=read_jsonl(ROOT/'data/labels.jsonl');om,_=evaluate(oldrows,oldlabels);om+=extra_metrics(oldrows,oldlabels);oldlookup={(r['method'],r['metric']):r for r in om}
    comparison=[]
    for cohort,ll in [('old_v2',oldlookup),('new_holdout',lookup)]:
        for m in 'BCDE':
            if (m,'macro_f1') not in ll:continue
            comparison.append({'cohort':cohort,'method':m,'n':ll[m,'macro_f1']['n'],'macro_f1':ll[m,'macro_f1']['value'],'attacks_allowed':ll[m,'attack_allow_rate']['numerator'],'attack_n':ll[m,'attack_allow_rate']['denominator'],'benign_hard_reject':ll[m,'benign_reject_rate']['numerator'],'benign_n':ll[m,'benign_reject_rate']['denominator'],'manual_review':ll[m,'manual_review_rate']['numerator'],'coverage':ll[m,'coverage']['value'],'predicted_injection_count':ll[m,'predicted_injection_rate']['numerator']})
    csv_save(OUT/'old_new_separate_cohorts.csv',comparison)
    # Select first distinct observed failure types; no editing or rerunning answers.
    examples=[];seen=set()
    # Diverse, distinct incident IDs; first observed case meeting each criterion.
    ordered=[]
    used_ids=set()
    criteria=[lambda r:r['method']=='B' and truth[r['incident_id']]['scenario_class']!='bona_fide' and r['recommendation']=='allow',lambda r:r['method']=='C' and truth[r['incident_id']]['scenario_class']=='presentation_attack' and r['recommendation']=='allow',lambda r:r['method']=='D' and truth[r['incident_id']]['scenario_class']=='injection_attack' and r['predicted_class']=='presentation_attack',lambda r:r['method']=='E' and truth[r['incident_id']]['scenario_class']=='injection_attack' and r['recommendation']=='allow',lambda r:r['method'] in 'CDE' and truth[r['incident_id']]['scenario_class']=='bona_fide' and r['recommendation']=='reject']
    for criterion in criteria:
        first=next((r for r in primary if r['incident_id'] not in used_ids and criterion(r)),None)
        if first is not None:ordered.append(first)
        if first is not None:used_ids.add(first['incident_id'])
    ordered+=primary
    selected_ids=set()
    for r in ordered:
        gt=truth[r['incident_id']]['scenario_class']
        if r['predicted_class']==gt:continue
        key=(r['method'],gt,r['predicted_class'])
        if key in seen or r['incident_id'] in selected_ids:continue
        selected_ids.add(r['incident_id'])
        seen.add(key);t=traces[r['method'],r['incident_id']]
        ev={e['evidence_id']:e for e in t['agent_input']['evidence']}
        for call in t['trace']['calls']:
            for e in json.loads(call['request']['messages'][1]['content'])['evidence']:ev[e['evidence_id']]=e
        examples.append({'incident_id':r['incident_id'],'method':r['method'],'true_class':gt,'predicted_class':r['predicted_class'],'recommendation':r['recommendation'],'evidence_ids':r['evidence_ids'],'rationale':r['rationale'],'evidence':list(ev.values()),'agent_outputs':[{'role':c['role'],'status':c['status'],'final_stage':c['final_stage'],'raw_response':c.get('raw_response')} for c in t['trace']['calls']],'trace_location':f'results/{RUN.name}/traces.jsonl; method={r["method"]}; incident_id={r["incident_id"]}'})
        if len(examples)==5:break
    write_json(OUT/'error_examples.json',examples)
    notes=['# Реальные примеры ошибок','', 'Первые различные типы ошибок из сохранённого прогона; иллюстративный разбор, не отдельная случайная оценка. Ссылки evidence_id относятся к указанному incident_id. Ни один ответ не исправлялся.']
    for e in examples:
        notes+=['',f'## {e["incident_id"]} / {e["method"]}',f'Истина: {e["true_class"]}; прогноз: {e["predicted_class"]}; действие: {e["recommendation"]}. Evidence: {", ".join(e["evidence_ids"])}.',f'Обоснование: {e["rationale"]}',f'Источник проверки: {e["trace_location"]}. Полные значения свидетельств в error_examples.json.', 'Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.']
    (OUT/'error_examples.md').write_text('\n'.join(notes),encoding='utf-8')
    lines=['# Проверка замороженного v2 на новых медиа','',f'Статус: {"ПОЛНОСТЬЮ ЗАВЕРШЁН" if complete else "ЧАСТИЧНЫЙ"}. Ожидалось 18 инцидентов / 8 новых источников. Завершённые случаи: '+str({m:len(s) for m,s in sets.items()})+'. Общий набор для сравнения методов: '+str(len(common))+'.','', '| Метод | Macro-F1 | Опасные allow | PA allow | Injection allow | Benign hard reject | Benign non-allow | Review | Coverage | Верные auto |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in 'BCDE':
        f=value(m,'macro_f1');lines.append('| '+m+' | '+('N/A' if f is None else f'{f:.4f}')+' | '+' | '.join(frac(m,k) for k in ['attack_allow_rate','presentation_attack_allow_rate','injection_attack_allow_rate','benign_reject_rate','benign_reject_or_escalate_rate','manual_review_rate','coverage','selective_accuracy'])+' |')
    lines+=['','## Фактические вычисления','', '| Метод | Вызовы | Известные in/out токены | Usage отсутствует, вызовов | Сумма времени, с | Среднее, с/инцидент |','|---|---:|---:|---:|---:|---:|']
    for m in 'BCDE':
        rr=[r for r in primary if r['method']==m]
        if rr:lines.append(f'| {m} | {sum(r["calls"] for r in rr)} | {sum(r["input_tokens"] for r in rr)}/{sum(r["output_tokens"] for r in rr)} | {sum(r.get("usage_missing_calls",0) for r in rr)} | {sum(r["triage_seconds"] for r in rr):.3f} | {sum(r["triage_seconds"] for r in rr)/len(rr):.3f} |')
    lines+=['','Стоимость API — 0 USD. Локальная энергия/CPU не монетизировались. PAD извлечён отдельно один раз на новые источники; повторные инциденты используют тот же кэш. Реальные source-level ошибки PAD сохранены в visual_cache.json и не приводили к исключению источников.']
    lines+=['','Все доли: числитель/знаменатель и значение. Нулевой знаменатель — N/A. Precision/recall/F1 по трём классам и их знаменатели — metrics.csv. Абстенция даёт FN истинному классу; macro-F1 — среднее трёх F1 по прежнему определению. «Верные auto» — selective accuracy, всегда рядом с coverage. Токены — известный usage; отсутствие usage отражено в метриках, не заменено выдуманной оценкой.','', '## Ответы на исследовательские вопросы']
    lines += [f'- {r["method"]}: предсказаний injection_attack={r["predicted_injection_count"]}; верно атрибутировано {r["correct_injection"]}/{r["true_injection_n"]}; отвергнуто injection как presentation={r["injection_rejected_as_presentation"]}; injection allow={r["injection_allowed"]}.' for r in attribution]
    if common:
        e=lookup['E','attack_allow_rate'];lines += ['',f'Риск опасных допусков E: {e["numerator"]}/{e["denominator"]}. '+('Риск сохраняется на новых источниках.' if e['numerator'] else 'В этом малом наборе allow атак не наблюдались; это не доказательство безопасности.'),'', 'Относительно правил B (на той же новой выборке):']
        for m in 'CDE':lines.append(f'- {m}: macro-F1={value(m,"macro_f1"):.4f} против B={value("B","macro_f1"):.4f}; allow атак {frac(m,"attack_allow_rate")} против {frac("B","attack_allow_rate")}; hard reject benign {frac(m,"benign_reject_rate")} против {frac("B","benign_reject_rate")}; review {frac(m,"manual_review_rate")} против {frac("B","manual_review_rate")}.')
        lines+=['','Меньший allow может сопровождаться большим review/hard reject; правильное reject не означает правильного различения presentation/injection.']
    lines+=['','## Прежняя и новая выборки — отдельно','', '| Выборка | Метод | n | Macro-F1 | Attack allow | Benign hard reject | Review |','|---|---|---:|---:|---:|---:|---:|']
    for r in comparison:lines.append(f'| {r["cohort"]} | {r["method"]} | {r["n"]} | {r["macro_f1"]:.4f} | {r["attacks_allowed"]}/{r["attack_n"]} | {r["benign_hard_reject"]}/{r["benign_n"]} | {r["manual_review"]}/{r["n"]} |')
    lines+=['','Это разные случаи, не парное улучшение и не объединённая метрика. Новые PA представлены бумажной/вырезанной/латексной/силиконовой атакой, прежние — display replay; также новый seed synthetic metadata. Различие нельзя приписать только одному фактору.','', '## Ограничения','', 'Новые файлы того же публичного поставщика, не доказанная независимость людей. 8 источников повторяются в 18 инцидентах. Метки визуального материала предоставлены источником и не аудированы независимо. Telemetry и delivery синтетические; injection сценарная, не проверка реального capture pipeline. Маленькая квантованная модель, один прогон, без обучения/подбора. Статистическая значимость не заявляется. Время PAD здесь исключает сохранение JPEG, прежний feature timer включал запись: сравнение PAD-time между сериями ограничено. LLM-таймер и generation parameters сохранены; prefix cache/CPU фон влияют на latency.','', 'При partial основные цифры относятся только к общим завершённым ID; все остальные сохранены в predictions/traces и metrics_all_available.csv, незавершённые пары — unfinished_cases.jsonl. Их не выдаём за полные n=18. Архив не полностью автономный: веса, runtime и исходные лица не включены; для полного вычислительного повтора нужны разрешённые загрузки.']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    write_json(OUT/'analysis_scope.json',{'completed':complete,'expected_n':18,'completed_by_method':{m:len(s) for m,s in sets.items()},'common_completed_n':len(common),'common_incident_ids':sorted(common),'old_new_not_pooled':True,'new_sources':8,'source_identity_independence_claim':False})
    print('Holdout metrics, figures and report materials saved:',OUT)

if __name__=='__main__':main()
