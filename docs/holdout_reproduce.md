# Просмотр результатов и полный повтор — разные режимы

Архив **не полностью автономный**: исходные лица, веса, Python runtime и llama.cpp binaries не включены. Включены frozen-входы/разметка, реальные результаты PAD, все LLM-ответы, метрики, PNG/SVG и исходный код. Никаких платных API, ключей или обучения.

## Без моделей и медиа
Открыть report_materials/local_protocol_v2_holdout/summary.md, CSV, figures/*.png/*.svg и error_examples.md. Для простого просмотра Python не нужен. При необходимости заново построить таблицы/графики только из сохранённых predictions/traces:

```powershell
python -m pip install numpy==2.2.6 matplotlib==3.10.8
python scripts/report_holdout.py --run-id local_protocol_v2_holdout
```

Эта команда не загружает модели, не выполняет inference и не обращается к LLM. Она перезаписывает только производные материалы указанного run_id, не predictions/traces или frozen input.

## Полный вычислительный повтор
Требуются Python 3.11 x64 + requirements-lock.txt, прежние PAD assets и Qwen2.5-1.5B-Instruct Q4_K_M / llama.cpp b12032. На исходной машине они уже есть. На новой машине fetch_holdout_assets.py получает только точные записанные URL/revision/SHA-256 из asset_manifest.json, без обновления исходных manifests. Около 1.12 ГБ LLM + 25 МБ runtime + несколько МБ PAD. Не использовать другую модель или preprocessing ради скорости.

Исходные новые медиа публичны в AxonData/face-anti-spoofing-dataset, CC BY-NC 4.0 для публичного sample. Загружаются только 8 frozen URL с commit revision и проверкой SHA-256; около 180 МБ. Полный коммерческий набор не нужен. Provider labels не независимо переаннотированы. Если ссылки исчезнут, это внешний блокер полного повторения, а не основание подменить источники.

```powershell
python -m pip install -r requirements-lock.txt
python scripts/fetch_holdout_assets.py
Expand-Archive -LiteralPath downloads/llama-b12032-bin-win-cpu-x64.zip -DestinationPath .runtime/llama-b12032
python scripts/fetch_holdout_media.py
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1 -LogDirectory results/repeat_holdout_server
python scripts/repeat_holdout_compute.py --run-id repeat_holdout --recompute-pad
python scripts/report_holdout.py --run-id repeat_holdout
```

На текущей машине вместо python использовать .\.runtime\python.exe. `--recompute-pad` вызывает тот же frozen PAD на реальных новых фото/видео. Кэш записывается только в results/repeat_holdout/recomputed_PAD/, исходный holdout cache/inputs не меняются. Затем реальная локальная LLM; B/C/D/E неизменны. Без `--recompute-pad` повторяется только триаж на переданном кэше PAD. Generation params: temperature=0, seed=8217, 600 токенов, 40 с, одна проверка, CPU threads=6/context=8192.

Точный сценарный seed 20261102, исходный генератор и единственная AST-параметризация cohort loop/выходного каталога записаны в generation_config.json. Unit-test воспроизводит incidents/labels побайтно из исходного генератора в отдельном временном каталоге. Скрипт prepare_holdout.py не запускать поверх frozen data для «улучшения» выборки; он документирует исходное получение и подготовку, а не отбор после ответов.

Каждый повтор — новый run_id, это те же наблюдения, не дополнительная независимая выборка. Не выбирать лучший из повторов. Исходный initial runner run_holdout.py содержит абсолютный лимит времени конкретного задания; для будущего повторения использовать repeat_holdout_compute.py. Тайминги/малые floating-point значения могут различаться по CPU/версиям, а inference не обещает битовую детерминированность.

Полное восстановление исходного состояния до holdout: snapshots/protocol_v2_before_holdout.zip. Новая заморозка: experiments/local_protocol_v2_holdout/data/holdout_freeze.json. Старые и новые наборы не смешиваются в одной метрике; новые медиа не означают независимость людей или проверку реальных атак внедрения.
