# Проверенные источники

Проверено 2026-11-02 локальная дата (UTC-время запусков записывается отдельно).

| Источник | URL | Назначение / проверенное содержание |
|---|---|---|
| Minivision, Silent-Face-Anti-Spoofing | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing | Официальный PAD, Apache 2.0; ограничения камер/сценариев |
| Официальный test.py | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/test.py | Индекс 1 real, остальные fake |
| Официальный predict | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/anti_spoof_predict.py | BGR detector preprocessing и softmax |
| Официальный crop | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/generate_patches.py | Boundary-shift расширенного bbox |
| Yakhyo ONNX inference | https://github.com/yakhyo/face-anti-spoofing/blob/main/onnx_inference.py | ONNX, float32 NCHW, live index 1, scale 2.7 |
| ONNX V2 weights | https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx | Фактически загруженные веса, хеш в кэше |
| AxonData public sample | https://huggingface.co/datasets/AxonData/Display_replay_attacks | 5 real JPG + 5 replay видео; публичная карточка CC BY 4.0 |
| Sample tree API | https://huggingface.co/api/datasets/AxonData/Display_replay_attacks/tree/main?recursive=true&limit=100 | Размеры до загрузки; LFS хеши |
| UniAttackData official access | https://sites.google.com/view/face-anti-spoofing-challenge/dataset-download/uniattackdatacvpr2024 | Требуются соглашение и заявка; не используется |
| UniAttackData paper | https://arxiv.org/abs/2401.17699 | Контекст объединения физических/цифровых атак; это не свидетельство доступа к данным |
| Qwen official GGUF | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | Instruction-модель 1.5B, Q4_K_M, Apache-2.0; точная ревизия и хеш сохранены |
| llama.cpp pinned CPU release | https://github.com/ggml-org/llama.cpp/releases/tag/b12032 | CPU Windows x64 runtime, MIT |
| llama.cpp server pinned docs | https://github.com/ggml-org/llama.cpp/blob/b12032/tools/server/README.md | Loopback chat/completions, JSON Schema grammar, server parameters |

Не использованы случайные фотографии из поисковика, закрытые зеркала датасетов и ключи авторизации Codex. Полный manifest содержит прямые URL каждого реально полученного медиафайла.
