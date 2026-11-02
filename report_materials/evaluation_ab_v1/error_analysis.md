# Реальные ошибки и отказы от решения

Выбраны первые различные типы исходов из сохранённого прогона; без изменения правил после просмотра.

## 68227a1e054bfa8fa5846551f25f751d — метод A
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: live; рекомендация: allow.
Стресс-условие: normal. Обоснование метода: Binary PAD argmax; no delivery attribution.
PAD оценивает внешний вид, поэтому live-материал при сценарной подмене может быть пропущен. Это ограничение постановки, а не измеренная устойчивость к реальному внедрению.

## 68227a1e054bfa8fa5846551f25f751d — метод B
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Live score does not establish trustworthy delivery.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 466cfecad11e42016a4acbf48cafc3dd — метод B
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Live score does not establish trustworthy delivery.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 513c6bbf61451be638416b34599b8db6 — метод B
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: missing_history. Обоснование метода: Live score does not establish trustworthy delivery.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 5ae1d927b5a12fa293af1fde9f3288e3 — метод B
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: missing_history. Обоснование метода: Spoof appearance and delivery anomaly conflict on attack attribution.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## b4430f04e3615e3de195f99b223515ed — метод A
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: pad_tool_failure. Обоснование метода: PAD unavailable.
PAD оценивает внешний вид, поэтому live-материал при сценарной подмене может быть пропущен. Это ограничение постановки, а не измеренная устойчивость к реальному внедрению.

## b4430f04e3615e3de195f99b223515ed — метод B
Истинный сценарий: injection_attack; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: pad_tool_failure. Обоснование метода: Visual tool unavailable.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 6021de47716521e1d6119de7bbf069ff — метод A
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: pad_tool_failure. Обоснование метода: PAD unavailable.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.