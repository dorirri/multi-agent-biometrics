# Реальные ошибки и отказы от решения

Выбраны первые различные типы исходов из сохранённого прогона; без изменения правил после просмотра.

## 466cfecad11e42016a4acbf48cafc3dd — метод C
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: presentation_attack; рекомендация: reject.
Стресс-условие: normal. Обоснование метода: The visual evidence shows a live score of 0.9999836683273315, indicating a live stream. The channel evidence confirms the use of a virtual camera, which is inconsistent with the live stream. The history evidence shows a timestamp gap of 251 ms, suggesting a device change, which is also inconsistent with the live stream. These inconsistencies suggest a presentation attack..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 466cfecad11e42016a4acbf48cafc3dd — метод D
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: presentation_attack; рекомендация: reject.
Стресс-условие: normal. Обоснование метода: Predefined conservative analyst merge.
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 71c6d2f1c67a0faa2fbca11f157b6636 — метод C
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: bona_fide; рекомендация: allow.
Стресс-условие: normal. Обоснование метода: The visual evidence shows a live score of 0.9999836683273315, indicating a high probability of a live event. The channel evidence confirms the camera is functioning normally. The history evidence shows a consistent pattern of successful outcomes, suggesting the system is functioning as expected. There are no contradictions or missing data that would suggest an attack or unsafe behavior..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 71c6d2f1c67a0faa2fbca11f157b6636 — метод D
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: presentation_attack; рекомендация: reject.
Стресс-условие: normal. Обоснование метода: Predefined conservative analyst merge.
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 71c6d2f1c67a0faa2fbca11f157b6636 — метод E
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: bona_fide; рекомендация: allow.
Стресс-условие: normal. Обоснование метода: The visual evidence shows a live PAD appearance with a high score of 0.9999836683273315. This indicates a live PAD, which is a benign occurrence. There are no contradictions or missing data that would suggest an attack or unsafe behavior..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 908ed4ffed802aea883bf9eca2ff4fe1 — метод C
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: presentation_attack; рекомендация: reject.
Стресс-условие: normal. Обоснование метода: The visual evidence shows a live score of 0.9986513257026672, indicating a live stream. The channel evidence confirms the presence of a virtual camera, which is not normal operation. The history evidence shows a timestamp gap of 604 ms, suggesting a device change. These inconsistencies and contradictions strongly indicate a presentation attack..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 33f5f7116849d1844af0e2912f529cc2 — метод C
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: bona_fide; рекомендация: allow.
Стресс-условие: missing_channel. Обоснование метода: The visual evidence shows a live score of 0.9986513257026672, indicating a high probability of a live event. The channel and history evidence are missing, but the live score is still valid. There are no contradictions found. The evidence is consistent and supports the conclusion that the event is bona fide..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.

## 33f5f7116849d1844af0e2912f529cc2 — метод D
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: presentation_attack; рекомендация: reject.
Стресс-условие: missing_channel. Обоснование метода: Predefined conservative analyst merge.
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.