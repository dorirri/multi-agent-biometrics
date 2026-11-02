"""Build handoff status and additional machine-readable provenance."""
import csv
import importlib.metadata
from triage.io import ROOT,read_json,read_jsonl,write_json
from triage.schemas import AgentInput,Decision

def main():
    run=ROOT/'results/evaluation_ab_v1';sample=read_json(run/'sample.json');complete=read_json(run/'completion.json')
    with (run/'metrics.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    metrics={(r['method'],r['metric']):r for r in rows}
    def rate(m,k):
        r=metrics[m,k];return f'{100*float(r["value"]):.1f}% ({r["numerator"]}/{r["denominator"]})'
    cache=read_json(ROOT/'data/visual_cache.json');manifest=read_json(ROOT/'data/source_manifest.json');faults=read_jsonl(run/'tool_errors.jsonl')
    source_audit=[]
    for s in manifest:
        v=cache[s['source_id']]
        source_audit.append({'source_id':s['source_id'],'split':s['split'],'visual_label':s['visual_label'],'pad_status':v['status'],'pad_label':v['values'].get('pad_label'),'frames':len(v['frames']),'feature_seconds':v['feature_seconds'],'visual_correct':v['values'].get('pad_label')==s['visual_label'] if v['status']=='ok' else None})
    write_json(ROOT/'report_materials/source_level_pad_audit.json',source_audit)
    write_json(ROOT/'data/agent_input.schema.json',AgentInput.model_json_schema());write_json(ROOT/'data/decision.schema.json',Decision.model_json_schema())
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name'].lower() not in ['pip','setuptools','wheel']}
    (ROOT/'requirements-lock.txt').write_text(''.join(f'{k}=={v}\n' for k,v in sorted(packages.items(),key=lambda x:x[0].lower())),encoding='utf-8')
    text=f'''# Статус для передачи в чат подготовки отчёта

## Ключевой факт
Реально выполнены локальный нейросетевой PAD и сравнение A/B. **LLM API, модель и разрешённый бюджет пользователь не предоставил к моменту выполнения. C/D/E не запущены; преимущество многоагентности и вклад верификатора НЕ проверены.** Код настоящих LLM-ролей и их ограниченного оркестратора реализован; test doubles используются только в тестах, в predictions их нет.

## Реальные данные и запуски
- PAD: {len(source_audit)} уникальных источников, {sum(r['frames'] for r in source_audit)} кадров суммарно, CPU; исходных отказов инструмента {sum(r['pad_status']!='ok' for r in source_audit)}.
- Отладка `debug_ab_v1`: 10 инцидентов, 3 исходных кадра разработчика, A/B, 20 прогнозов.
- Оценка `evaluation_ab_v1`: {sample['n']} инцидентов, {sample['unique_media_sources']} уникальных медиаисточников AxonData (5 real JPG + 5 replay видео, 20 извлечённых кадров), A/B, {complete['predictions']} прогнозов.
- Разметка: по 20 bona_fide / presentation_attack / injection_attack. Телеметрия и доставка синтетические. Повторное использование изображений не создаёт независимых наблюдений.
- Контролируемая недоступность PAD включена в {len(faults)} инцидентов и учтена в метриках. Реальный PAD inference на исходниках не отказал.
- LLM-вызовы: {complete['api_calls']}; фактическая стоимость этих запусков API: 0. Цены и стоимость будущих LLM-запусков неизвестны.

## Главные измерения
| Показатель | A: только PAD | B: правила |
|---|---:|---:|
| Атаки с рекомендацией allow / все сценарные атаки | {rate('A','attack_allow_rate')} | {rate('B','attack_allow_rate')} |
| Benign с reject/escalate / все benign | {rate('A','benign_reject_or_escalate_rate')} | {rate('B','benign_reject_or_escalate_rate')} |
| Manual review / все инциденты | {rate('A','manual_review_rate')} | {rate('B','manual_review_rate')} |
| Coverage | {rate('A','coverage')} | {rate('B','coverage')} |

B: трёхклассовый macro-F1 = {float(metrics['B','macro_f1']['value']):.6f}; selective accuracy = {rate('B','selective_accuracy')}. A: бинарный визуальный macro-F1 = {float(metrics['A','macro_f1_binary']['value']):.6f}; selective accuracy = {rate('A','selective_accuracy')}. Эти F1/accuracy относятся к разным задачам и напрямую не сравниваются. Source-level PAD audit совпал с визуальными метками всех источников sample; это маленькая демонстрационная выборка, а не доказательство качества.

Суммарное измеренное PAD-время на 10 уникальных оценочных источниках: {complete['unique_sources_feature_seconds']:.6f} с; включает inference/сохранение кадров, исключает загрузку модели. Средний триаж A: {float(metrics['A','triage_mean_seconds']['value'])*1000:.6f} мс, B: {float(metrics['B','triage_mean_seconds']['value'])*1000:.6f} мс; такие малые величины шумны. Кэшированные времена на повторных инцидентах не означают дополнительные PAD-вычисления.

Показатель error_rate в CSV относится к ошибкам LLM-вызовов (для A/B их нет). Ошибки/контролируемые отказы PAD вынесены в tool_errors.jsonl и сохранены в общем знаменателе, а не потеряны из-за нулевого API error_rate.

## Интерпретация
На данном сконструированном наборе правила уменьшили пропуск сценарных атак ценой существенно большей ручной проверки и эскалации benign. Это наблюдаемый компромисс, а не доказательство превосходства всех систем с контекстом. Большая часть injection не определяется автоматически: у B recall injection = {float(metrics['B','recall_injection_attack']['value']):.2f}. Высокий визуальный score не подтверждает подлинность канала или личности. Не заявлять статистическую значимость, реальную устойчивость к внедрению, абсолютную prompt-injection защиту и положительный результат многоагентной гипотезы.

## Что взять для IMRAD
Протокол: docs/experiment_protocol.md. Methods: docs/methods.md и report_materials/implementation.md. Данные/ограничения: docs/data_card.md и docs/limitations.md. Таблицы, результаты и реальные ошибки: report_materials/evaluation_ab_v1/. Источники: report_materials/sources.md. Русские PNG/SVG: figures/evaluation_ab_v1/. График D/E честно обозначает отсутствие измерений, его нельзя выдавать за выполненную абляцию.

## Что осталось
Подключить LLM_BASE_URL, LLM_MODEL, LLM_API_KEY и согласованный LLM_BUDGET_USD; выполнить debug-пилот C/D/E, измерить расход/скорость, выбрать доступный объём, затем оценку с неизменными prompts/rules. Команды в README. Если методы меняются после просмотра evaluation, следующий анализ следует объявить exploratory; существующие A/B правила и выводы после оценки не менялись.

Финальная проверка тестов сохраняется в results/validation_v1/. Не путать тестовый mock с фактическим LLM inference. Архив: research_triage_handoff.zip, состав формируется scripts/package.py. Исходные изображения, видео, веса и секреты исключены.
'''
    (ROOT/'report_materials/STATUS.md').write_text(text,encoding='utf-8')
    print('Handoff status written.')

if __name__=='__main__':main()
