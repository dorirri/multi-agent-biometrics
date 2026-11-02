# Бесплатная локальная LLM

Платные и внешние LLM-вызовы запрещены пользователем. Активный клиент `triage.agents.LLM` допускает только loopback host (127.0.0.1, localhost, ::1). Никаких API-ключей и LLM_BUDGET_USD не требуется; Authorization не отправляется. Стоимость API = 0, денежная стоимость CPU/электроэнергии не оценивалась. Прежние документы о платном API относятся только к исходному незапущенному плану; активная инструкция — эта.

Реальный backend: llama.cpp b12032 / commit dde879bc4, Windows x64 CPU. Модель Qwen/Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, 1117320736 байт. Точный revision и SHA-256 в data/local_backend_manifest.json. Модель загружена из официального Qwen-репозитория; не обучается. Лицензии Apache-2.0 модели и MIT runtime сохранены в docs/third_party. Runtime скачивается отдельно, не входит в архив.

RAM проверена Windows GlobalMemoryStatusEx: всего 31.553 ГиБ, свободно 13.790 ГиБ в момент проверки. CPU: Intel Core i5-13420H (имя подтверждено реестром), 12 логических потоков. Доступно 332.940 ГиБ диска. Реестр показывает Intel UHD Graphics; выделенный дискретный GPU и VRAM не подтверждены. WMI запрещён политикой среды. Стандартные каталоги Ollama/LM Studio/HF и localhost-порты 11434/1234/8080 проверены: ранее доступных моделей/серверов не обнаружено. Это не полный поиск всех файлов компьютера.

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
