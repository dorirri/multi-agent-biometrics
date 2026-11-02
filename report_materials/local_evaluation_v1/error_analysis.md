# Реальные ошибки и отказы от решения

Выбраны первые различные типы исходов из сохранённого прогона; без изменения правил после просмотра.

## 466cfecad11e42016a4acbf48cafc3dd — метод B
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Live score does not establish trustworthy delivery.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 466cfecad11e42016a4acbf48cafc3dd — метод C
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Repeated recheck request; pipeline terminated.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 466cfecad11e42016a4acbf48cafc3dd — метод D
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: An analyst abstained.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 466cfecad11e42016a4acbf48cafc3dd — метод E
Истинный сценарий: bona_fide; визуальная метка источника: live; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Repeated recheck request; pipeline terminated.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 841166a2962420c7d0a0d77ea2c863be — метод C
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Repeated recheck request; pipeline terminated.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 841166a2962420c7d0a0d77ea2c863be — метод D
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: An analyst abstained.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## 841166a2962420c7d0a0d77ea2c863be — метод E
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: manual_review; рекомендация: escalate.
Стресс-условие: normal. Обоснование метода: Repeated recheck request; pipeline terminated.
Это отказ от автоматизации, учтённый в coverage и в знаменателях всех общих метрик.

## c890784c9e0844d4edee0905c9bf8d14 — метод C
Истинный сценарий: presentation_attack; визуальная метка источника: spoof; прогноз: bona_fide; рекомендация: allow.
Стресс-условие: normal. Обоснование метода: The visual evidence shows a spoofed pad label, indicating a spoofed device. The channel evidence confirms the device is not virtual. The history evidence shows a consistent pattern of successful events. The check evidence confirms the live score is within the expected range. There are no contradictions or missing data that would suggest an attack. The evidence supports the device being genuine and the events being normal..
Результат относится к данным поставщика и синтетическому контексту; причинную интерпретацию и перенос на реальные каналы делать нельзя.