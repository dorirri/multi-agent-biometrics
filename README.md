# Многоагентный триаж биометрических инцидентов

Исследовательский проект для AI/ML: локальный готовый PAD + структурированные свидетельства + специализированные LLM-роли. Система только рекомендует `allow`, `reject` или `escalate`. Никакой проверки личности, блокировок аккаунтов и производственных биометрических вызовов.

**Статус:** подключена настоящая бесплатная локальная Qwen2.5-1.5B-Instruct через llama.cpp на CPU. Платные/удалённые LLM-вызовы запрещены и блокируются клиентом. Ключи и денежный бюджет не нужны. Актуальные команды — в `docs/local_backend.md`; фактически выполненные сравнения — в `report_materials/STATUS.md` и `results/`. Полные A/B n=60 сохранены отдельно от общего подмножества A–E.

Выполнены четыре серии (все завершены, ответы не исправлялись):

| Серия | run_id | Методы | n | Итог |
|---|---|---|---:|---|
| A/B полная | `evaluation_ab_v1` | A, B | 60 | B: пропуск атак 3/40 при review 30/60 |
| Протокол v1 | `local_evaluation_v1` | A–E | 18 | Лучший Macro-F1 у правил B (0,598); E 0,148, D 0 автоматических решений |
| Протокол v2 | `local_protocol_v2` | C, D, E | 18 (те же) | Macro-F1 C/D/E 0,350/0,413/0,494, но у E опасных allow 5/12 |
| Holdout v2 | `local_protocol_v2_holdout` | B–E | 18 (8 новых источников) | Macro-F1 B/C/D/E 0,315/0,311/0,259/0,267; ни один метод не предсказал injection_attack |
| **v3: 6 агентов по плану** | `v3_evaluation` | A_minifas, A_thesis, B, C, T | 48 (OULU-NPU, 48 кадров, 16 человек) | Macro-F1 B/C/T 0,665/0,678/0,638; опасных allow 4/13/6 из 32; внедрение распознано C/T 13/16; T убрал 7 из 13 опасных допусков C, не добавив новых |

**v3** — реализация состава агентов из исходного плана: оркестратор с общей памятью SQLite, параллельные агенты живости / канала / сессии, верификатор с одной адресной перепроверкой, агент заключения (вердикт, тип атаки, риск, уверенность, рекомендация allow / reverify / block_escalate / escalate, отчёт оператору). LLM Qwen2.5-7B через llama.cpp на macOS (Metal); PAD — MiniFASNetV2 и модель магистерской работы V_june. Описание и воспроизведение — [docs/v3_team.md](docs/v3_team.md), результаты — [report_materials/v3_evaluation/](report_materials/v3_evaluation/summary.md). Кадры OULU-NPU в репозиторий не входят (лицензия).

## Быстрая проверка без моделей (macOS / Linux / Windows)

Сохранённые результаты, кэш PAD и тесты не требуют весов, медиа или LLM-сервера:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q      # 56 passed
```

Хеш-проверки заморозки (`data/protocol_v2_freeze.json`, `holdout_freeze.json`, `snapshots/*.json`) посчитаны на Windows по файлам с CRLF. `.gitattributes` закрепляет эти окончания строк при checkout на любой ОС; не меняйте окончания строк в `data/`, `results/`, `report_materials/`, `experiments/` вручную.

Для полного повтора LLM-части на macOS/Linux вместо `scripts/start_local.ps1` можно запустить llama.cpp вручную с теми же параметрами (сборка отличается от b12032 / Windows x64, поэтому ответы могут отличаться):

```bash
llama-server -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 \
  --alias qwen2.5-1.5b-instruct-q4_k_m -c 8192 -np 1 -t 6 -tb 6 -ngl 0 --seed 8217
```

## Установка

Python 3.11 x64, CPU. Стандартный вариант Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

На текущей машине установлен переносимый Python в `.runtime` внутри проекта, потому что системная команда Python была заглушкой Microsoft Store. Для команд ниже вместо `python` используйте `.\.runtime\python.exe` (или `.\.venv\Scripts\python.exe`). Runtime, зависимости и веса не включены в архив; на другой машине Python нужно установить отдельно. На момент работы стандартный curl не смог подключиться к настроенному прокси; публичные файлы успешно получены прямым HTTPS. `scripts/download.py` использует прямой HTTPS без системного прокси. Если политика вашей сети требует прокси, измените конфигурацию OPENER под разрешённый доступ.

## Данные и воспроизведение

```powershell
python scripts/download.py
python scripts/generate.py --seed 8217
python -m triage.pad
python -m pytest -q
python scripts/run.py --run-id debug_ab_v1 --split debug --methods A B
python scripts/run.py --run-id evaluation_ab_v1 --split evaluation --methods A B
python scripts/report.py --run-id evaluation_ab_v1
python scripts/package.py
```

Существующие run_id не перезаписываются. Для повторения используйте новый ID. Отдельные повторные прогоны не являются новыми независимыми инцидентами. Загрузка: около 164 МБ открытого AxonData sample + небольшие веса/детектор/примеры. UniAttackData не используется: требует лицензионной заявки. Прямые URL и SHA-256 в `data/source_manifest.json`; при повторной загрузке изменившегося файла сверяйте SHA-256 с переданным manifest. `download.py` может заново записать manifest фактически полученных файлов, поэтому оригинал сохраняйте для сравнения.

В данных 10 отладочных и 60 оценочных инцидентов. Оценка — на 5 real-фото и 5 replay-видео, по 3 кадра из видео; телеметрия и способ доставки синтетические. Исходные фото/видео и извлечённые лица исключены из архива. См. `docs/data_card.md`; не считайте 60 инцидентов 60 независимыми источниками.

`visual_cache.json` содержит реальные результаты PAD и позволяет воспроизвести сравнение методов без повторного inference и без передачи лиц в LLM. Для независимого воспроизведения самого PAD нужны публичные исходники и веса по команде загрузки. Изменив данные/веса, заново извлеките признаки. Исходная визуальная метка и сценарный ground truth лежат только в `labels.jsonl`/manifest, отдельно от агентного входа.

## LLM: local CPU, API cost = 0

Платные и внешние LLM-вызовы запрещены пользователем. Активный клиент `triage.agents.LLM` допускает только loopback host (127.0.0.1, localhost, ::1). Никаких API-ключей и LLM_BUDGET_USD не требуется; Authorization не отправляется. Стоимость API = 0, денежная стоимость CPU/электроэнергии не оценивалась. Прежние документы о платном API относятся только к исходному незапущенному плану; активная инструкция — эта.

Реальный backend: llama.cpp b12032 / commit dde879bc4, Windows x64 CPU. Модель Qwen/Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, 1117320736 байт. Точный revision и SHA-256 в data/local_backend_manifest.json. Модель загружена из официального Qwen-репозитория; не обучается. Лицензии Apache-2.0 модели и MIT runtime сохранены в docs/third_party. Runtime скачивается отдельно, не входит в архив.

RAM проверена Windows GlobalMemoryStatusEx: всего 31.553 ГиБ, свободно 13.790 ГиБ в момент проверки. CPU: 12 логических потоков. Доступно 332.940 ГиБ диска. Реестр показывает Intel UHD Graphics; выделенный дискретный GPU и VRAM не подтверждены. WMI запрещён политикой среды. Стандартные каталоги Ollama/LM Studio/HF и localhost-порты 11434/1234/8080 проверены: ранее доступных моделей/серверов не обнаружено. Это не полный поиск всех файлов компьютера.

Запуск сервера: host 127.0.0.1, port 8080, context 8192, один slot, CPU threads 6, batch threads 6, GPU layers 0, seed 8217. Вызовы последовательны в порядке A/B/C/D/E. KV/prefix caching runtime используется штатно; времена зависят от прогрева/порядка, это не чистый speed benchmark архитектур. Температура 0 и seed не гарантируют одинаковых результатов на другом CPU/runtime.

Лимиты сохранены: 40 с на вызов, 600 выходных токенов, максимум 4 вызова/2400 выходных токенов на метод, максимум одна адресная перепроверка. JSON Schema grammar применяется одинаково C/D/E. Она ограничивает синтаксис и допустимые значения, но не выбирает класс и не подменяет модель правилами. Не гарантирует правильность reasoning, логических связей или ссылок evidence_id; их проверяет Pydantic и код.

## Повторение

Требуется Node.js для загрузчика и обычный Python 3.11 с requirements-lock.txt. На исходной машине доступен переносимый .runtime/python.exe. Объявленный размер загрузки модели около 1.12 ГБ, runtime около 24.6 МБ.

```powershell
node scripts/bootstrap_local.cjs
Expand-Archive -LiteralPath downloads/llama-b12032-bin-win-cpu-x64.zip -DestinationPath .runtime/llama-b12032
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
python scripts/local_smoke.py
python scripts/run.py --run-id repeat_local_pilot --split debug --methods A B C D E --max-api-calls 90
```

Нет необходимости задавать какие-либо LLM_* переменные. При настройке другого loopback-сервера используйте LLM_BASE_URL и LLM_MODEL; удалённый адрес блокируется до отправки запроса.

Для точного повторения сравнения используйте сохранённый data/local_evaluation_selection.json и новый run_id; не запускайте повторный selection на существующем frozen-файле:

```powershell
python scripts/run.py --run-id repeat_local_evaluation --split evaluation --methods A B C D E --subset-file data/local_evaluation_selection.json --pilot-run repeat_local_pilot --max-api-calls 270
python scripts/report.py --run-id repeat_local_evaluation
```

Число 270 — верхняя граница вызовов для n≤30 (до 9 суммарно C+D+E на инцидент), не фактический расход. Для нового исследования размер выбирается скриптом select_local_subset.py после пилота, до evaluation. Старые eval-ответы нельзя использовать для подбора нового удобного набора. Полный A/B n=60 сохранён отдельно. Повторные прогоны не увеличивают число независимых наблюдений.

Остановка после работы: завершите только PID собственного llama-server.exe, записанный в каталоге логов, предварительно сверив executable path. Не завершайте все процессы с похожим именем. Исходные логи первой сессии находятся в results/local_feasibility/.

Первый smoke: 10.879 с, 816 входных/166 выходных токенов, валидный JSON и evidence_id. Smoke относится к debug, не включается в качество evaluation. В его reasoning обнаружено ошибочное толкование некалиброванного PAD score как вероятности — это содержательная ошибка модели при корректной JSON-схеме. Не исправлялась вручную.

## Структура и материалы

- `triage/` — схемы, PAD, фильтр свидетельств, правила, настоящие LLM-вызовы, оркестратор, метрики.
- `scripts/` — загрузка, генерация с seed, запуск, графики/таблицы и безопасный архив.
- `docs/experiment_protocol.md` — протокол до оценки; `methods.md`, `data_card.md`, `limitations.md` — методика и ограничения.
- `data/` — manifest, входные сценарии, отдельная разметка, кэш реального inference.
- `results/<run_id>/` — конфигурация/версии/хеши, состав, predictions, traces, errors, metrics с числителями и знаменателями.
- `figures/<run_id>/` — автоматически построенные русские PNG/SVG.
- `report_materials/` — статус, проверенные источники, описание фактической реализации, измеренные таблицы и реальные ошибки.
- `tests/` — схемы, утечки, разделение, ссылки, метрики, отказы, перепроверка, недоверенный текст. Тестовые LLM-ответы используются только для unit-тестов.

Архив `research_triage_handoff.zip` содержит только код, конфигурации без секретов, manifest, кэш признаков, результаты, графики и материалы отчёта. Не включает runtime/venv, ключи, большие веса, исходные/извлечённые изображения. Скрипт архивации использует явный список разрешённых папок, а не всё содержимое рабочей директории.

Пользовательский отчёт и презентация здесь не создаются. Для IMRAD начните с `report_materials/STATUS.md`, затем `results_summary.md`, `error_analysis.md`, протокола и ограничений. Apache notices готового PAD и ONNX-источника сохранены в `docs/third_party/`.
