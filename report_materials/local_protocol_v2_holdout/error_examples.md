# Реальные примеры ошибок

Первые различные типы ошибок из сохранённого прогона; иллюстративный разбор, не отдельная случайная оценка. Ссылки evidence_id относятся к указанному incident_id. Ни один ответ не исправлялся.

## 0d77bbc258a6f4bca0ba72b8bf221db4 / B
Истина: injection_attack; прогноз: bona_fide; действие: allow. Evidence: v0, c1.
Обоснование: Live appearance and matching attested channel
Источник проверки: results/local_protocol_v2_holdout/traces.jsonl; method=B; incident_id=0d77bbc258a6f4bca0ba72b8bf221db4. Полные значения свидетельств в error_examples.json.
Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.

## 13a844bd1006772fe30a406c66844bdb / C
Истина: presentation_attack; прогноз: bona_fide; действие: allow. Evidence: v0, c0, c1, h0.
Обоснование: All evidence provided is consistent and does not contradict each other. The visual evidence shows a live score of 0.94, indicating a live stream. The channel evidence confirms the camera is functioning normally. The history evidence shows no previous events that would suggest an attack. There are no missing data points. The rationale is based on the consistency of the evidence and the absence of any contradictions.
Источник проверки: results/local_protocol_v2_holdout/traces.jsonl; method=C; incident_id=13a844bd1006772fe30a406c66844bdb. Полные значения свидетельств в error_examples.json.
Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.

## d86639940fbc3407cc7f836fe976fe5a / D
Истина: injection_attack; прогноз: presentation_attack; действие: reject. Evidence: c0, c1, h0, t0, v0.
Обоснование: Predefined conservative analyst merge
Источник проверки: results/local_protocol_v2_holdout/traces.jsonl; method=D; incident_id=d86639940fbc3407cc7f836fe976fe5a. Полные значения свидетельств в error_examples.json.
Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.

## b055a52160fa51adeea3db2aa0a9cd63 / E
Истина: injection_attack; прогноз: bona_fide; действие: allow. Evidence: v0.
Обоснование: The visual evidence shows a live score of 0.9821286201477051, which is above the threshold of 0.5. This indicates that the image is likely a live video stream. The frame count is 1, which is sufficient to establish the presence of a live video stream. There are no missing or contradictory pieces of evidence.
Источник проверки: results/local_protocol_v2_holdout/traces.jsonl; method=E; incident_id=b055a52160fa51adeea3db2aa0a9cd63. Полные значения свидетельств в error_examples.json.
Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.

## 9c9a0063d62b6056f58fda8e8813aef2 / D
Истина: bona_fide; прогноз: presentation_attack; действие: reject. Evidence: c0, c1, h0, v0.
Обоснование: Predefined conservative analyst merge
Источник проверки: results/local_protocol_v2_holdout/traces.jsonl; method=D; incident_id=9c9a0063d62b6056f58fda8e8813aef2. Полные значения свидетельств в error_examples.json.
Если инъекция отвергнута как presentation, рекомендация reject не подтверждает распознавание механизма. Если выдан allow при сценарной атаке, это unsafe на данном генераторе; real-world inference о захвате канала не делается. Manual review сохраняется в общем знаменателе.