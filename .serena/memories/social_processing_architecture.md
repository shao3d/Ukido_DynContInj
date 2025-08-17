# Архитектура обработки социальных запросов в Ukido AI Assistant (v0.7.6)

## ⚠️ ВАЖНО: Quick Regex ПОЛНОСТЬЮ УДАЛЕН
- **Quick Regex был удален в версии 0.7.1** 
- В config.py НЕТ переменной USE_QUICK_REGEX
- Файл quick_social_detector.py больше НЕ используется

## Актуальная обработка социальных запросов

### 1. Чистая социалка (без бизнес-вопросов)
**Путь**: User → Gemini Router → Локальный ответ
- Router определяет социальный интент через `detect_social_intent()` (src/social_intents.py)
- Порог confidence: 0.7
- Проверка отсутствия бизнес-сигналов: `has_business_signals_extended()`
- Router САМ генерирует ответ через `social_responder.py`
- Возвращает: `status: "offtopic"`, `message: готовый_ответ`, `social_context: тип_интента`
- **Стоимость**: ~$0.00003 (только Gemini)
- **Время**: 1.0-2.2 сек

### 2. Mixed запросы (социалка + бизнес)
**Путь**: User → Gemini Router → Claude Generator
- Router видит бизнес-сигналы И социальный контекст
- Классифицирует как `status: "success"`
- Добавляет `social_context` для Claude
- Claude генерирует полный ответ с учетом социального контекста
- **Стоимость**: ~$0.0003 (Gemini + Claude)
- **Время**: 5.8-6.4 сек

### 3. Offtopic без социалки
**Путь**: User → Gemini Router → Стандартная фраза
- Router определяет `status: "offtopic"`
- Нет социального контекста
- Используется заготовленная фраза из `standard_responses.py`
- **Стоимость**: ~$0.00003 (только Gemini)

## Ключевые компоненты

### src/router.py (строки 129-148)
```python
# Определение социальных интентов
det = detect_social_intent(user_message)
if det.intent != SocialIntent.UNKNOWN and det.confidence >= 0.7 and not has_business:
    # Router сам обрабатывает чистую социалку
    reply = self._social_responder.respond(user_id, det.intent)
    return {
        "status": "offtopic",
        "message": reply,
        "social_context": det.intent.value
    }
```

### src/social_intents.py
- Содержит паттерны для определения социальных интентов
- НЕ является "Quick Regex детектором"
- Используется ВНУТРИ Router'а

### src/social_responder.py
- Генерирует локальные ответы на социальные запросы
- Отслеживает повторные приветствия через social_state
- Работает БЕЗ вызова LLM

## Экономика
- **30-40% запросов** - чистая социалка, обрабатывается локально Router'ом
- **Экономия**: избегаем вызова Claude ($0.0003) для этих запросов
- **Итоговая экономия**: ~40% от общей стоимости API-вызовов

## Отладка
- Ищите в логах: "Router: Обнаружен социальный интент"
- Для mixed: "Mixed запрос с повторным приветствием"
- Время обработки: router_social = 0.00s в логах (локальная генерация)