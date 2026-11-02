"""Paired exploratory v1/v2 comparison. No mutation of baseline artifacts."""
import argparse
import csv
import json
import os
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json,write_jsonl
from triage.metrics import evaluate
from scripts.abstention_report import mechanism as mechanism_v1
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})

def cause(row,trace,version):
    if row['predicted_class']!='manual_review':return 'automatic'
    if version==1:
        c=mechanism_v1(row,trace)
        return {'api_or_validation_error':'technical_llm_error','model_abstention':'model_or_merge_review','conservative_analyst_merge':'model_or_merge_review'}.get(c,c)
    if row.get('errors'):return 'technical_llm_error'
    if row.get('tool_errors') or any(c['status']!='ok' for c in trace['trace'].get('checks',[])):return 'technical_tool_error'
    if row['rationale']=='Analysts disagree on attack type':return 'merge_conflict'
    return 'model_or_merge_review'

def unsafe(row,truth):return truth!='bona_fide' and row['recommendation']=='allow'
def state(row,truth):
    if row['predicted_class']=='manual_review':return 'review'
    if unsafe(row,truth):return 'unsafe_allow'
    if row['predicted_class']==truth:return 'correct_auto'
    return 'other_wrong_auto'

def summary(rows,labels,method,version):
    metrics,_=evaluate(rows,list(labels.values()))
    lookup={m['metric']:m for m in metrics};n=len(rows)
    attacks=[r for r in rows if labels[r['incident_id']]['scenario_class']!='bona_fide'];benign=[r for r in rows if labels[r['incident_id']]['scenario_class']=='bona_fide']
    auto=[r for r in rows if r['predicted_class']!='manual_review']
    return {'method':method,'version':version,'n':n,'attack_denominator':len(attacks),'benign_denominator':len(benign),'macro_f1':lookup['macro_f1']['value'],'attacks_allowed':sum(r['recommendation']=='allow' for r in attacks),'benign_reject':sum(r['recommendation']=='reject' for r in benign),'benign_escalate':sum(r['recommendation']=='escalate' for r in benign),'manual_review':n-len(auto),'auto_count':len(auto),'coverage':len(auto)/n,'correct_auto':sum(r['predicted_class']==labels[r['incident_id']]['scenario_class'] for r in auto),'selective_accuracy':lookup['selective_accuracy']['value'],'calls':sum(r['calls'] for r in rows),'input_tokens':sum(r['input_tokens'] for r in rows),'output_tokens':sum(r['output_tokens'] for r in rows),'usage_missing_calls':sum(r.get('usage_missing_calls',0) for r in rows),'triage_seconds_total':sum(r['triage_seconds'] for r in rows),'triage_seconds_mean':sum(r['triage_seconds'] for r in rows)/n,'invalid_calls':sum(r['errors'] for r in rows)}

def save_csv(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--new-run',default='local_protocol_v2');p.add_argument('--baseline-run',default='local_evaluation_v1');args=p.parse_args()
    olddir=ROOT/'results'/args.baseline_run;newdir=ROOT/'results'/args.new_run
    before=read_jsonl(olddir/'predictions.jsonl');after=read_jsonl(newdir/'predictions.jsonl')
    labels={r['incident_id']:r for r in read_jsonl(ROOT/'data/labels.jsonl')}
    oldmap={(r['method'],r['incident_id']):r for r in before};newmap={(r['method'],r['incident_id']):r for r in after}
    traces=[{(t['method'],t['incident_id']):t for t in read_jsonl(d/'traces.jsonl')} for d in [olddir,newdir]]
    complete=read_json(newdir/'completion.json')['completed'];expected=set(read_json(ROOT/'data/local_evaluation_selection.json')['incident_ids'])
    out=ROOT/'report_materials'/args.new_run;out.mkdir(parents=True,exist_ok=True)
    figs=ROOT/'figures'/args.new_run;figs.mkdir(parents=True,exist_ok=True)
    summaries=[];pairs=[];causes=[];transitions=[];safety=[];available=[]
    states=['review','correct_auto','unsafe_allow','other_wrong_auto'];matrices={}
    for method in 'CDE':
        ids=[i for i in read_json(olddir/'sample.json')['incident_ids'] if (method,i) in newmap]
        if not ids:continue
        if not set(ids)<=expected:raise ValueError('Unknown evaluation ID')
        if complete and set(ids)!=expected:raise ValueError('Completed run has unequal subsets')
        available.append(method)
        oldrows=[oldmap[method,i] for i in ids];newrows=[newmap[method,i] for i in ids]
        summaries.extend([summary(oldrows,labels,method,'v1'),summary(newrows,labels,method,'v2')])
        counts=[Counter(),Counter()];matrix=np.zeros((4,4),dtype=int)
        for iid in ids:
            a=oldmap[method,iid];b=newmap[method,iid];gt=labels[iid]['scenario_class']
            ca=cause(a,traces[0][method,iid],1);cb=cause(b,traces[1][method,iid],2)
            counts[0][ca]+=1;counts[1][cb]+=1
            sa,sb=state(a,gt),state(b,gt);matrix[states.index(sa),states.index(sb)]+=1
            pairs.append({'method':method,'incident_id':iid,'ground_truth':gt,'v1_class':a['predicted_class'],'v2_class':b['predicted_class'],'v1_recommendation':a['recommendation'],'v2_recommendation':b['recommendation'],'v1_cause':ca,'v2_cause':cb,'v1_state':sa,'v2_state':sb,'v1_unsafe_allow':unsafe(a,gt),'v2_unsafe_allow':unsafe(b,gt),'introduced_unsafe_allow':not unsafe(a,gt) and unsafe(b,gt),'eliminated_unsafe_allow':unsafe(a,gt) and not unsafe(b,gt),'coordination_review_to_unsafe_allow':ca=='recheck_protocol_stop' and unsafe(b,gt)})
        for version,c in zip(['v1','v2'],counts):
            causes.extend({'method':method,'version':version,'cause':k,'count':v,'denominator':len(ids)} for k,v in c.items())
        for x,sa in enumerate(states):
            for y,sb in enumerate(states):transitions.append({'method':method,'v1_state':sa,'v2_state':sb,'count':int(matrix[x,y]),'denominator':len(ids)})
        matrices[method]={'states':states,'counts':matrix.tolist(),'n':len(ids)}
        subset=[r for r in pairs if r['method']==method]
        safety.append({'method':method,'matched_n':len(ids),'new_unsafe_allow':sum(r['introduced_unsafe_allow'] for r in subset),'eliminated_unsafe_allow':sum(r['eliminated_unsafe_allow'] for r in subset),'coordination_review_to_unsafe_allow':sum(r['coordination_review_to_unsafe_allow'] for r in subset),'v1_unsafe_allow':sum(r['v1_unsafe_allow'] for r in subset),'v2_unsafe_allow':sum(r['v2_unsafe_allow'] for r in subset)})
    save_csv(out/'before_after_metrics.csv',summaries);save_csv(out/'paired_incidents.csv',pairs);save_csv(out/'paired_transitions.csv',transitions);save_csv(out/'manual_review_causes.csv',causes);save_csv(out/'safety_changes.csv',safety)
    write_json(out/'paired_transition_matrices.json',matrices);write_jsonl(out/'new_dangerous_allows.jsonl',[r for r in pairs if r['introduced_unsafe_allow']])
    lookup={(r['method'],r['version']):r for r in summaries}
    lines=['# До/после: exploratory follow-up протокола','',f'Статус: {"завершён" if complete else "ЧАСТИЧНЫЙ"}. Сравнение только по совпадающим ID внутри каждого метода. Это повторные данные после просмотра ошибок v1; статистическая значимость не заявляется.','', '| Метод | Версия | n | Macro-F1 | Атаки allow | Benign reject | Benign escalate | Review | Coverage | Верных auto | Вызовы | Токены in/out | Время, с |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f'| {r["method"]} | {r["version"]} | {r["n"]} | {r["macro_f1"]:.4f} | {r["attacks_allowed"]}/{r["attack_denominator"]} | {r["benign_reject"]}/{r["benign_denominator"]} | {r["benign_escalate"]}/{r["benign_denominator"]} | {r["manual_review"]}/{r["n"]} | {r["coverage"]:.3f} | {r["correct_auto"]}/{r["auto_count"]} | {r["calls"]} | {r["input_tokens"]}/{r["output_tokens"]} | {r["triage_seconds_total"]:.2f} |')
    lines+=['','Benign reject и escalate разделены: hard reject нельзя смешивать с нагрузкой ручной проверки. Верных auto — число решений с правильным трёхклассовым predicted_class; coverage имеет знаменатель все совпадающие инциденты. Abstention даёт FN в F1. Токены суммируются только из полученного usage; если usage_missing_calls в CSV больше нуля, сумма неполная, а не выдуманная оценка.','', '## Проверка опасных замен','', '| Метод | Новых unsafe allow | Устранено unsafe allow | Координационный review → unsafe allow |','|---|---:|---:|---:|']
    for r in safety:lines.append(f'| {r["method"]} | {r["new_unsafe_allow"]} | {r["eliminated_unsafe_allow"]} | {r["coordination_review_to_unsafe_allow"]} |')
    increased=[r['method'] for r in safety if r['v2_unsafe_allow']>r['v1_unsafe_allow']]
    verdict=('Рост числа опасных допусков наблюдается в методах '+', '.join(increased)+'. Гипотеза уменьшения координационных отказов БЕЗ ухудшения опасных допусков для этих методов не поддержана.') if increased else 'Общее число опасных допусков не выросло ни в одном из сравниваемых методов; новые индивидуальные опасные решения всё равно проверяются в paired_incidents.csv. Это описательный результат малой повторной выборки, не доказательство безопасности.'
    lines+=['',verdict,'', '## Ограничения','', 'Изменение совместное: финальная схема, stage-инструкции, распределение одной проверки и fail-closed при техническом отказе. Содержательные SYSTEM/ROLES и merge сохранены. Сравнение не изолирует одну компоненту. Маленькая квантованная LLM, 18 зависимых инцидентов / 8 источников, синтетическая телеметрия и доставка. Порядок методов и prefix cache влияют на время. JSON schema не исправляет семантические ошибки классификации. API cost=0; локальное электричество/CPU не монетизируются.']
    if not complete:lines+=['','**Нельзя сравнивать разные method-specific подмножества как одну общую оценку на 18.** Незавершённые случаи не подменены выдуманными решениями.']
    (out/'comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    write_json(out/'hypotheses.json',{'exploratory':True,'completed':complete,'unsafe_allow_increased_methods':increased,'per_method_safety_changes':safety,'no_significance_claim':True,'not_new_independent_observations':True})
    # Every plot is generated from the same matched saved rows.
    def save(fig,name):
        fig.tight_layout();fig.savefig(figs/(name+'.png'),dpi=180);fig.savefig(figs/(name+'.svg'));plt.close(fig)
    x=np.arange(len(available));fig,axes=plt.subplots(2,3,figsize=(13,7))
    panels=[('macro_f1',None,'Macro-F1'),('attacks_allowed','attack_denominator','Пропущенные атаки, доля'),('benign_reject','benign_denominator','Доброкачественные: отклонить, доля'),('benign_escalate','benign_denominator','Доброкачественные: эскалировать, доля'),('manual_review','n','Ручная проверка, доля'),('coverage',None,'Автоматические решения, доля')]
    for ax,(key,den,title) in zip(axes.flat,panels):
        for offset,ver,color in [(-.18,'v1','#4477aa'),(.18,'v2','#ee9944')]:
            vals=[lookup[m,ver][key]/lookup[m,ver][den] if den else lookup[m,ver][key] for m in available]
            ax.bar(x+offset,vals,.36,label=ver,color=color)
        ax.set_xticks(x,[m+' (n='+str(lookup[m,'v2']['n'])+')' for m in available]);ax.set(title=title,ylim=(0,1.05));ax.legend()
    fig.suptitle('Протокол до/после: те же ID, exploratory follow-up',fontsize=13);save(fig,'protocol_before_after')
    fig,axes=plt.subplots(1,len(available),figsize=(6*len(available),5),squeeze=False)
    ru=['Ручная проверка','Верно автоматически','Опасный допуск','Другая автоошибка']
    for ax,m in zip(axes.flat,available):
        a=np.array(matrices[m]['counts']);ax.imshow(a,cmap='Blues',vmin=0)
        ax.set_xticks(range(4),ru,rotation=35,ha='right');ax.set_yticks(range(4),ru);ax.set(title=f'{m}: парные переходы, n={matrices[m]["n"]}',xlabel='v2',ylabel='v1')
        for (i,j),v in np.ndenumerate(a):ax.text(j,i,str(v),ha='center',va='center',color='white' if v>a.max()/2 else 'black')
    save(fig,'paired_transitions')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for offset,ver in [(-.18,'v1'),(.18,'v2')]:
        axes[0].bar(x+offset,[lookup[m,ver]['triage_seconds_mean'] for m in available],.36,label=ver)
        axes[1].bar(x+offset,[(lookup[m,ver]['input_tokens']+lookup[m,ver]['output_tokens'])/lookup[m,ver]['n'] for m in available],.36,label=ver)
    for ax in axes:ax.set_xticks(x,available);ax.legend()
    axes[0].set(ylabel='Секунды/инцидент',title='Среднее время триажа');axes[1].set(ylabel='Токены in+out / инцидент, шт.',title='Фактический расход токенов');save(fig,'protocol_time_tokens')
    # Current status is explicitly updated; baseline STATUS is retained in snapshot.
    status=['# Актуальный статус: exploratory follow-up протокола v2','',verdict,'',f'Run: {args.new_run}; статус {"completed" if complete else "partial"}. Исходный local_evaluation_v1 и A/B на 60 инцидентах не изменялись. Снимок v1: snapshots/protocol_v1_before_v2.zip. Новая логика отдельным модулем triage/protocol_v2.py; заморозка data/protocol_v2_freeze.json.','',*lines[4:4+2+len(summaries)],'', 'Главный файл для обновления отчёта: [comparison.md](local_protocol_v2/comparison.md). Подробные парные переходы: paired_incidents.csv / paired_transitions.csv; новые опасные allow: new_dangerous_allows.jsonl. Графики PNG/SVG: figures/local_protocol_v2/.','', 'Не называть результат независимым тестом или статистически значимым улучшением. Изменены одновременно схема и управление стадиями/проверкой; качество модели не подгонялось, один evaluation-прогон. Отказы не выкинуты из знаменателей. При partial используются только совпадающие method-specific ID, не фиктивные 18 на метод.','', 'Проверки debug: results/protocol_v2_debug_validation/. Итоговые проверки: results/protocol_v2_final_validation/. Инструкция для защиты: report_materials/local_protocol_v2/defense_notes.md. Архив передачи: research_triage_protocol_v2.zip. Исходные веса, runtime, секреты и лица исключены.']
    (ROOT/'report_materials/STATUS.md').write_text('\n'.join(status),encoding='utf-8')
    defense=['# Краткая инструкция для защиты','', '1. **Что было сломано.** В v1 разрешённый tool request оставался доступным даже после исчерпания единственной проверки. Повторные/конкурирующие запросы приводили к системному review; у D 18/18 review и E 15/18, а не успешная классификация всех атак.','', '2. **Что изменили.** State-dependent действия: финальный JSON допускает только request_check=none в constrained decoder и валидаторе. D программно отдаёт одну проверку context раньше visual и не считает невыполненный второй запрос ошибкой. В E инструменты принадлежат только verifier. Содержательные классы, данные, модель и merge не меняли.','', '3. **Как проверили.** До evaluation — тесты конкурентных запросов, запрета request_check в final, содержательного review, невалидного JSON, отказа инструмента, лимитов и partial checkpoint; два реальных debug-инцидента. Затем SHA-256 freeze и один прогон на прежних 18 ID.','', '4. **Что измерили.** Macro-F1, опасные allow/12, benign reject и escalate отдельно/6, review/18, coverage, верные auto, причины отказов, фактические вызовы/токены/секунды. Парные переходы показывают, куда исчезли отказы: в правильные решения или ошибочные допуски.','', '5. **Что получилось.** '+verdict,'', '6. **Чего не утверждаем.** Это exploratory анализ тех же зависимых данных после просмотра ошибок, не новое независимое подтверждение. Совместный эффект схемы и координации; статистической значимости и работоспособности на реальном внедрении не заявляем.','', 'Для чисел показать comparison.md и таблицу safety_changes.csv; для одного конкретного опасного перехода — new_dangerous_allows.jsonl и соответствующий trace. Не защищать архитектуру обещаниями: ухудшение является допустимым измеренным результатом.']
    (out/'defense_notes.md').write_text('\n'.join(defense),encoding='utf-8')
    print('Paired comparison saved:',out)

if __name__=='__main__':main()
