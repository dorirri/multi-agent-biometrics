"""All numeric tables and plots come from immutable saved run artifacts."""
import argparse
import csv
import os
from pathlib import Path
from collections import Counter
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.metrics import CLASSES

RUS={'bona_fide':'Доброкачественный','presentation_attack':'Предъявление','injection_attack':'Внедрение','manual_review':'Ручная проверка','live':'Live','spoof':'Spoof'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);args=p.parse_args()
    run=ROOT/'results'/args.run_id;preds=read_jsonl(run/'predictions.jsonl');sample=read_json(run/'sample.json');config=read_json(run/'config.json')
    with (run/'metrics.csv').open(encoding='utf-8-sig') as f:metrics=list(csv.DictReader(f))
    lookup={(r['method'],r['metric']):float(r['value']) if r['value'] else None for r in metrics}
    methods=sorted(set(r['method'] for r in preds));n=sample['n']
    figdir=ROOT/'figures'/args.run_id;figdir.mkdir(parents=True,exist_ok=True)
    reportdir=ROOT/'report_materials'/args.run_id;reportdir.mkdir(parents=True,exist_ok=True)
    def save(fig,name):
        fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=180);fig.savefig(figdir/(name+'.svg'));plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4));counts=sample['counts']
    ax.bar([RUS[x] for x in CLASSES],[counts.get(x,0) for x in CLASSES],color=['#338877','#dd9944','#aa5577'])
    ax.set(ylabel='Инциденты, шт.',title=f'Сценарные классы: n={n}; уникальных медиаисточников={sample["unique_media_sources"]}')
    save(fig,'class_distribution')
    for method,m in read_json(run/'confusion_matrices.json').items():
        fig,ax=plt.subplots(figsize=(8,4));a=np.array(m['counts']);im=ax.imshow(a,cmap='Blues',vmin=0)
        ax.set_xticks(range(len(m['columns'])),[RUS[x] for x in m['columns']],rotation=15,ha='right');ax.set_yticks(range(len(m['rows'])),[RUS[x] for x in m['rows']])
        ax.set(xlabel='Решение метода',ylabel='Исходная визуальная метка' if method=='A' else 'Истинный сценарный класс',title=f'Метод {method}: матрица ошибок, n={m["n"]}')
        for (y,x),v in np.ndenumerate(a):ax.text(x,y,str(v),ha='center',va='center',color='white' if v>a.max()/2 else 'black')
        fig.colorbar(im,ax=ax,label='Инциденты, шт.');save(fig,'confusion_'+method)
    fig,ax=plt.subplots(figsize=(9,4));x=np.arange(len(methods));width=.24
    for j,(key,label) in enumerate([('attack_allow_rate','Пропуск среди атак'),('benign_reject_or_escalate_rate','Отклонение/эскалация среди benign'),('manual_review_rate','Ручная проверка среди всех')]):
        ax.bar(x+(j-1)*width,[100*lookup[m,key] for m in methods],width,label=label)
    ax.set_xticks(x,methods);ax.set(ylabel='Доля, %',ylim=(0,105),title=f'Рекомендации триажа, n={n} на метод');ax.legend(fontsize=8);save(fig,'triage_rates')
    fig,ax=plt.subplots(figsize=(8,4))
    if all(m in methods for m in ['D','E']):
        keys=['attack_allow_rate','benign_reject_or_escalate_rate','manual_review_rate','macro_f1'];xx=np.arange(len(keys))
        for j,m in enumerate(['D','E']):ax.bar(xx+(j-.5)*.35,[lookup[m,k] for k in keys],.35,label=m)
        ax.set_xticks(xx,['Пропуск атак','Ложная тревога','Ручная проверка','Macro-F1']);ax.set(ylabel='Доля / F1',title=f'Вклад верификатора, n={n} на метод');ax.legend()
    else:
        ax.axis('off');ax.text(.5,.6,'Сравнение D и E не выполнено',ha='center',fontsize=16);ax.text(.5,.4,'Нет измеренных LLM-решений; гипотеза о верификаторе не проверена.\nn = 0 для D/E в этом прогоне.',ha='center')
    save(fig,'verifier_ablation')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    axes[0].bar(methods,[1000*lookup[m,'triage_mean_seconds'] for m in methods]);axes[0].set(ylabel='Время триажа, мс/инцидент',title=f'Только триаж, n={n} на метод')
    cache=read_json(ROOT/'data/visual_cache.json');times=[cache[s]['feature_seconds'] for s in sample['sources']]
    axes[1].bar(['PAD на уникальный источник'],[np.mean(times)*1000]);axes[1].set(ylabel='Время извлечения признаков, мс/источник',title=f'CPU, источников={len(times)}; 1–3 кадра')
    save(fig,'latency')
    fig,ax=plt.subplots(figsize=(8,4));xx=np.arange(len(methods))
    ax.bar(xx-.18,[lookup[m,'known_input_tokens_per_incident'] for m in methods],.36,label='Входные');ax.bar(xx+.18,[lookup[m,'known_output_tokens_per_incident'] for m in methods],.36,label='Выходные')
    ax.set_xticks(xx,methods);ax.set(ylabel='Известные токены/инцидент, шт.',title=f'Фактический расход: n={n} на метод; C–E отсутствуют' if not set('CDE')&set(methods) else f'Фактический расход, n={n} на метод');ax.legend();save(fig,'tokens')
    # Portable CSV tables retain all denominators.
    (reportdir/'all_metrics.csv').write_bytes((run/'metrics.csv').read_bytes())
    columns=['attack_allow_rate','benign_reject_or_escalate_rate','manual_review_rate','coverage','selective_accuracy','macro_f1','triage_mean_seconds','calls_per_incident']
    lines=['# Измеренные результаты','',f'Run: `{args.run_id}`, split: {config["split"]}. Инцидентов на метод: {n}; уникальных медиаисточников: {sample["unique_media_sources"]}.','', '| Метод | '+' | '.join(columns)+' |','|---|'+'---:|'*len(columns)]
    for m in methods:
        vals=[lookup.get((m,k)) for k in columns]
        lines.append('| '+m+' | '+' | '.join('—' if v is None else f'{v:.6f}' for v in vals)+' |')
    lines+=['','У A macro-F1 относится к бинарной задаче и приведён отдельно в CSV; с трёхклассовым F1 его не сравнивать. Нулевой расход A/B — отсутствие LLM-вызовов. Неизмеренные C/D/E не имеют нулевого качества.','',f'Суммарное время извлечения PAD на уникальных источниках: {sum(times):.6f} с. Признаки вычислены один раз и повторно используются всеми методами. Кэшированное время на инцидент не означает повторного inference.']
    if not set('CDE')&set(methods):lines+=['','**Основная гипотеза не проверена:** LLM API и бюджет не были предоставлены на момент прогона. Пилот LLM, токены, сравнение C/D/E и эмпирический тест устойчивости LLM к текстовой инструкции отсутствуют.']
    (reportdir/'results_summary.md').write_text('\n'.join(lines),encoding='utf-8')
    labels={r['incident_id']:r for r in read_jsonl(ROOT/'data/labels.jsonl')}
    cases=[]
    for r in preds:
        t=labels[r['incident_id']];expected=t['visual_source_label'] if r['method']=='A' else t['scenario_class']
        unsafe_allow=t['scenario_class']!='bona_fide' and r['recommendation']=='allow'
        if r['predicted_class']!=expected or unsafe_allow:
            cases.append({'incident_id':r['incident_id'],'method':r['method'],'true_scenario':t['scenario_class'],'visual_source_label':t['visual_source_label'],'prediction':r['predicted_class'],'recommendation':r['recommendation'],'stress':t['stress'],'rationale':r['rationale'],'source_id':t['source_id'],'error_kind':'unsafe_scenario_allow' if unsafe_allow else 'visual_error_or_review' if r['method']=='A' else 'scenario_error_or_review'})
    write_json(reportdir/'actual_error_cases.json',cases)
    errors=['# Реальные ошибки и отказы от решения','', 'Выбраны первые различные типы исходов из сохранённого прогона; без изменения правил после просмотра.']
    seen=set()
    for r in cases:
        key=(r['method'],r['true_scenario'],r['prediction'],r['stress'])
        if key in seen:continue
        seen.add(key)
        errors+=['',f'## {r["incident_id"]} — метод {r["method"]}',f'Истинный сценарий: {r["true_scenario"]}; визуальная метка источника: {r["visual_source_label"]}; прогноз: {r["prediction"]}; рекомендация: {r["recommendation"]}.',f'Стресс-условие: {r["stress"]}. Обоснование метода: {r["rationale"]}.']
        if r['true_scenario']=='injection_attack' and r['method']=='A':errors.append('PAD оценивает внешний вид, поэтому live-материал при сценарной подмене может быть пропущен. Это ограничение постановки, а не измеренная устойчивость к реальному внедрению.')
        elif r['prediction']=='manual_review':errors.append('Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.')
        else:errors.append('Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.')
        if len(seen)>=8:break
    (reportdir/'error_analysis.md').write_text('\n'.join(errors),encoding='utf-8')
    write_json(reportdir/'hypotheses.json',{'multiagent_better_than_single':'not_tested' if not all(m in methods for m in 'CDE') else 'inspect measured comparison; no significance claim','verifier_improves_triage':'not_tested' if not all(m in methods for m in 'DE') else 'inspect measured comparison; no significance claim','rule_attack_allow_rate':lookup.get(('B','attack_allow_rate')),'pad_attack_allow_rate':lookup.get(('A','attack_allow_rate')),'no_statistical_significance_claim':True})
    print('Figures:',figdir,'Report materials:',reportdir)

if __name__=='__main__':main()
