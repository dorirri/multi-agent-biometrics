"""Summarize the measured shared A–E subset; preserve original full A/B results."""
import argparse
import csv
import json
from collections import Counter
from triage.io import ROOT,read_json,read_jsonl,write_json

def table_metrics(run):
    with (run/'metrics.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    return {(r['method'],r['metric']):r for r in rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',default='local_evaluation_v1');args=p.parse_args()
    run=ROOT/'results'/args.run_id;config=read_json(run/'config.json');sample=read_json(run/'sample.json');done=read_json(run/'completion.json')
    if not done['completed']:raise SystemExit('Cannot summarize incomplete run as completed')
    preds=read_jsonl(run/'predictions.jsonl');traces=read_jsonl(run/'traces.jsonl');metrics=table_metrics(run)
    labels={r['incident_id']:r for r in read_jsonl(ROOT/'data/labels.jsonl')};n=sample['n']
    out=ROOT/'report_materials'/args.run_id;out.mkdir(exist_ok=True)
    def val(m,k):return float(metrics[m,k]['value']) if metrics[m,k]['value'] else None
    def fraction(m,k):
        r=metrics[m,k];return f'{100*float(r["value"]):.1f}% ({r["numerator"]}/{r["denominator"]})' if r['value'] else '—'
    lines=['# Общая оценочная выборка A–E','',f'Run `{args.run_id}`: n={n} на каждый метод, уникальных медиаисточников {sample["unique_media_sources"]}. Все методы используют один список ID, зафиксированный до первого C/D/E evaluation-ответа.','', '| Метод | Пропуск атак | Benign reject/escalate | Manual review | Coverage | Macro-F1 (3 класса) | Среднее время триажа, с | Вызовы | Входные/выходные токены |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in 'ABCDE':
        rows=[r for r in preds if r['method']==m]
        mf='— (бинарная задача)' if m=='A' else f'{val(m,"macro_f1"):.4f}'
        lines.append('| '+m+' | '+' | '.join([fraction(m,'attack_allow_rate'),fraction(m,'benign_reject_or_escalate_rate'),fraction(m,'manual_review_rate'),fraction(m,'coverage'),mf,f'{val(m,"triage_mean_seconds"):.3f}',str(sum(r['calls'] for r in rows)),f'{sum(r["input_tokens"] for r in rows)}/{sum(r["output_tokens"] for r in rows)}'])+' |')
    lines+=['','Общие показатели рекомендаций используют сценарную метку. A binary F1/selective accuracy относятся только к исходной визуальной метке и напрямую с B–E не сравниваются. Abstention включён в знаменатели и даёт FN для F1. API cost=0 USD. CPU/энергия не монетизированы. Время признаков отдельно; один общий кэш PAD.','', 'Порядок методов фиксирован A/B/C/D/E; прогретый prefix cache llama.cpp влияет на латентность. Число токенов/вызовов различается, поэтому сравнение E/D не изолирует только наличие верификатора при равном фактическом compute.']
    (out/'comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    by={(r['incident_id'],r['method']):r for r in preds}
    transitions=Counter()
    for iid in sample['incident_ids']:
        gt=labels[iid]['scenario_class'];d=by[iid,'D']['predicted_class'];e=by[iid,'E']['predicted_class']
        transitions[('D_correct' if d==gt else 'D_review' if d=='manual_review' else 'D_wrong')+' -> '+('E_correct' if e==gt else 'E_review' if e=='manual_review' else 'E_wrong')]+=1
    differences={'E_minus_D_macro_f1':val('E','macro_f1')-val('D','macro_f1'),'E_minus_C_macro_f1':val('E','macro_f1')-val('C','macro_f1'),'E_minus_D_attack_allow_rate':val('E','attack_allow_rate')-val('D','attack_allow_rate'),'E_minus_D_review_rate':val('E','manual_review_rate')-val('D','manual_review_rate'),'paired_D_to_E_outcomes':dict(transitions),'n':n,'no_significance_claim':True}
    write_json(out/'verifier_comparison.json',differences)
    error_examples=[];semantic=[]
    for tr in traces:
        if tr['method'] not in 'CDE':continue
        for c in tr['trace']['calls']:
            raw=c.get('raw_response','')
            try:d=json.loads(raw)
            except Exception:continue
            rationale=d.get('rationale','')
            if 'probab' in rationale.lower() and ('score' in rationale.lower() or 'live' in rationale.lower()):
                semantic.append({'incident_id':tr['incident_id'],'method':tr['method'],'role':c['role'],'issue':'Potential unsupported probability interpretation of uncalibrated score; requires manual reading','rationale':rationale})
    write_json(out/'semantic_reasoning_flags.json',semantic)
    for m in 'CDE':
        candidates=[r for r in preds if r['method']==m and r['predicted_class']!=labels[r['incident_id']]['scenario_class']]
        for r in candidates[:3]:
            error_examples.append({'incident_id':r['incident_id'],'method':m,'ground_truth':labels[r['incident_id']]['scenario_class'],'predicted_class':r['predicted_class'],'recommendation':r['recommendation'],'stress':labels[r['incident_id']]['stress'],'errors':r['errors'],'rationale':r['rationale'],'contradictions':r.get('contradictions',[]),'missing_data':r.get('missing_data',[])})
    write_json(out/'actual_llm_error_examples.json',error_examples)
    untrusted=[]
    for rid in [config['pilot_run'],args.run_id]:
        for r in read_jsonl(ROOT/'results'/rid/'predictions.jsonl'):
            if r['method'] in 'CDE' and labels[r['incident_id']]['stress']=='untrusted_text':
                untrusted.append({'run_id':rid,'split':labels[r['incident_id']]['split'],'incident_id':r['incident_id'],'method':r['method'],'truth':labels[r['incident_id']]['scenario_class'],'prediction':r['predicted_class'],'action':r['recommendation'],'rationale':r['rationale'],'errors':r['errors']})
    write_json(out/'untrusted_text_observations.json',untrusted)
    valid=sum(c['status']=='ok' for tr in traces for c in tr['trace']['calls']);call_count=sum(r['calls'] for r in preds);errors=sum(r['errors'] for r in preds)
    all_seconds=sum(r['triage_seconds'] for r in preds)
    hypotheses={'multiagent_full_vs_single':{'macro_f1_delta_E_minus_C':differences['E_minus_C_macro_f1'],'interpretation':'descriptive comparison only; consult safety/coverage/cost jointly'},'verifier_vs_merge':differences,'observational_only':True,'synthetic_injection_not_real_channel_validation':True}
    write_json(out/'hypotheses.json',hypotheses)
    old=table_metrics(ROOT/'results/evaluation_ab_v1')
    status=f'''# Актуальный статус проекта: локальный эксперимент выполнен

Платные вызовы запрещены. Все C/D/E реально выполнены на локальной Qwen2.5-1.5B-Instruct Q4_K_M через llama.cpp b12032 на CPU; детерминированная имитация не использовалась. Стоимость API **0 USD**, ключи и бюджет не нужны. Runtime и модель исключены из архива.

## Что реально запущено
- Исходный PAD: 13 источников / 23 кадра, CPU, 0 отказов на исходных медиа. Из них оценка AxonData: 5 real-фото и 5 replay-видео / 20 кадров.
- Исходные A/B: debug 10, evaluation 60, run evaluation_ab_v1 сохранён отдельно и не изменён.
- Local smoke: один реальный структурированный ответ, 10.879 с, 816/166 токенов; JSON и ссылки валидны.
- Один debug-инцидент каждым A–E: local_pilot_one_v1; C/D/E = 4.955/20.724/33.004 с, 8 реальных вызовов, все валидны.
- Дополнительный debug-пилот: {config['pilot_run']}. Основная выборка выбрана по его скорости, а не качеству; frozen IDs в data/local_evaluation_selection.json.
- Общая оценка A/B/C/D/E: {args.run_id}, **n={n} на метод**, уникальных медиаисточников **{sample['unique_media_sources']}**, сценарных классов {sample['counts']}.
- В оценке {call_count} реальных локальных LLM-запросов; валидных ответов {valid}, ошибок {errors}. Все отказы сохранены в общем знаменателе. Сумма времени триажа методов {all_seconds:.2f} с; модель загружается отдельно. Фактические входные/выходные токены: {sum(r['input_tokens'] for r in preds)}/{sum(r['output_tokens'] for r in preds)}.

## Основные результаты общей выборки
{chr(10).join(lines[4:11])}

E−D macro-F1: {differences['E_minus_D_macro_f1']:+.4f}; E−C: {differences['E_minus_C_macro_f1']:+.4f}. Это описательные разности, не статистическая значимость. Преимущество системы нельзя объявлять по одному F1 без пропуска атак, coverage, ложных тревог и расходов. Подробные таблицы, парные переходы D→E и примеры ошибок находятся в report_materials/{args.run_id}/.

## Отдельный исходный A/B n=60
A: пропуск 18/40 (45%), benign escalate 2/20 (10%), review 6/60 (10%). B: пропуск 3/40 (7.5%), benign escalate 13/20 (65%), review 30/60 (50%), macro-F1 0.548818. Эти числа относятся к полному набору и не подставляются в сравнение с локальными C/D/E меньшего размера.

## Ограничения
Телеметрия и доставка синтетические; сценарные injection не являются реальными зарегистрированными атаками. Связанные повторы изображений зависимы. Маленькая 1.5B модель и квантование ограничивают перенос результата. Корректная JSON-схема не гарантирует корректное reasoning: в smoke обнаружено толкование некалиброванного score как вероятности; дополнительные кандидаты отмечены в semantic_reasoning_flags.json без автоматического признания всех их ошибками. Обоснования вручную не исправлялись. Наблюдения на недоверенном тексте сохранены отдельно; это не доказательство абсолютной защиты. Времена зависят от прогрева/prefix cache и фиксированного порядка методов. Формальная статистическая значимость не проверялась.

## Файлы для отчёта и повторения
Начать с report_materials/{args.run_id}/comparison.md, results_summary.md, verifier_comparison.json, actual_llm_error_examples.json и untrusted_text_observations.json. Графики: figures/{args.run_id}/, PNG/SVG на русском. Протокол до C/D/E: docs/local_protocol_addendum.md. Настройка без ключей: docs/local_backend.md. Исходный протокол и полные A/B сохранены. Старые сообщения о незапущенных C/D/E в каталоге evaluation_ab_v1 описывают именно тот прежний запуск, а не текущее состояние.

Проверки тестов сохраняются в results/validation_local_v1/. Архив: research_triage_handoff.zip; код, frozen sample, кэш PAD, результаты, графики и материалы включены; runtime, веса, исходные лица и секреты исключены.
'''
    (ROOT/'report_materials/STATUS.md').write_text(status,encoding='utf-8')
    print('Local comparison and current STATUS saved:',out)

if __name__=='__main__':main()
