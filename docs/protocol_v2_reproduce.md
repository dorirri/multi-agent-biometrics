# Повторение v2 и передача

Этот run — exploratory follow-up по уже просмотренным данным v1. Единственный исходный оценочный запуск v2: local_protocol_v2. Повторение команд воспроизводит процедуру, но не добавляет независимых наблюдений и не должно использоваться для выбора лучшего результата.

V1: triage/agents.py и scripts/run.py; v2: triage/protocol_v2.py и scripts/run_protocol_v2.py. Оригинал сохранён дополнительно в snapshots/protocol_v1_before_v2.zip. Точный текстовый diff: docs/protocol_v2_code.diff. Содержательные SYSTEM/ROLES импортируются из v1 без изменений, merge — из triage/rules.py. Основной протокол v2 и правило context-before-visual: docs/protocol_v2_plan.md.

На исходной машине модель и runtime уже есть. Денежная стоимость API 0 USD; ключи не требуются. При повторении из ZIP сначала выполнить установку Python и публичную загрузку модели по docs/local_backend.md (около 1.12 ГБ), поскольку веса и runtime из передачи исключены. Для триажа используется включённый кэш реального PAD; исходные лица не нужны, если не повторять само извлечение PAD.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1 -LogDirectory results/repeat_v2_server
.\.runtime\python.exe -m pytest -q
.\.runtime\python.exe scripts/run_protocol_v2.py --run-id repeat_protocol_v2 --split evaluation --subset-file data/local_evaluation_selection.json --pilot-run protocol_v2_debug --max-api-calls 162
.\.runtime\python.exe scripts/compare_protocols.py --new-run repeat_protocol_v2 --baseline-run local_evaluation_v1
```

Не менять frozen-файлы. Runner проверяет data/protocol_v2_freeze.json до evaluation. Новая debug-фаза при изменении реализации требует новой версии и freeze, не перезаписи сохранённого v2. Для исходного повторения готовые debug-результаты включены в архив. Run_id не перезаписываются.

При остановке процесса сохраняются predictions/traces/errors, completion со статусом partial, список завершённых пар method/incident и inflight. Использовать только matched ID конкретного метода; не сравнивать разные подмножества как общую n=18 оценку. Если HTTP-вызов прерван до получения usage, его незавершённые токены помечены неизвестными, не выдумываются.

Фактические таблицы/парные переходы: report_materials/local_protocol_v2/. Краткая защита: defense_notes.md. Статус верхнего уровня обновлён, прежний STATUS сохранён в снимке. Исходные результаты, графики и выводы v1 не редактировались.
