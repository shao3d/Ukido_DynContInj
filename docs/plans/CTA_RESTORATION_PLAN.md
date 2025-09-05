# 🔧 План восстановления системы CTA через metadata
**Версия:** 2.0  
**Дата создания:** 03.09.2025  
**Обновлено:** 03.09.2025 (добавлены критические уточнения)  
**Цель:** Восстановить работу CTA без видимых маркеров для всех платформ

## 📊 Анализ текущей ситуации

### Что сломано:
1. **Маркеры закомментированы** в `response_generator.py` строки 810-815
2. **Rate limiting не работает** - метод `_count_cta_occurrences` ищет фразы вместо маркеров
3. **CTA повторяется 3+ раз** вместо максимум 2
4. **Tracking не работает** - нет способа отследить добавленные CTA

### Что УЖЕ исправлено (Phase 1 - НЕ ТРОГАТЬ!):
✅ **CTA инструкция усилена** - перемещена выше в промпте, сделана императивной  
✅ **Few-shot примеры обновлены** - показывают органичную интеграцию  
✅ **Метод `_build_messages()` обновлён** - word limit увеличен до 150-180 для CTA  
⚠️ **Claude МОЖЕТ интегрировать органично** - но без tracking мы не контролируем rate limiting

### Что работало раньше (до коммита 1075940):
- Claude органично интегрировал CTA в ~80% случаев
- HTML маркеры `<!-- [CTA_PRICE] -->` были невидимы в web, но видны в Telegram
- Rate limiting работал через подсчёт маркеров
- Fallback добавлял CTA механически в 20% случаев

## 🎯 Новая архитектура: metadata в истории

### Концепция:
Вместо маркеров в тексте, сохранять метаданные в history_manager для каждого сообщения.

```python
# Старая структура:
{"role": "assistant", "content": "текст с <!-- [CTA_PRICE] -->"}

# Новая структура:
{
    "role": "assistant",
    "content": "чистый текст без маркеров",
    "metadata": {
        "intent": "success",
        "user_signal": "price_sensitive", 
        "cta_added": True,
        "cta_type": "price_sensitive",
        "humor_generated": False
    }
}
```

## 📋 Пошаговый план внедрения

### Step 1: Расширение history_manager.py

**Файл:** `src/history_manager.py`

**Изменения:**
1. Обновить метод добавления в историю для поддержки metadata
2. Добавить helper методы для работы с metadata

**Детали реализации:**
```python
def add_message(self, user_id: str, role: str, content: str, metadata: dict = None):
    """Добавляет сообщение в историю с metadata"""
    message = {
        "role": role,
        "content": content
    }
    if metadata:
        message["metadata"] = metadata
    
    if user_id not in self.history:
        self.history[user_id] = deque(maxlen=self.max_history_size)
    
    self.history[user_id].append(message)
```

### Step 2: Обновление main.py

**Файл:** `src/main.py`  
**ВАЖНО:** Найти точные строки через `grep -n "response_generator.generate" src/main.py`

**Изменения:**
1. Изменить получение ответа от response_generator (вернёт tuple)
2. Передавать metadata в history_manager
3. **ВНИМАНИЕ:** Метод async, нужен await!

**Точки изменения:**
```python
# Найти строку где вызывается generate() - примерно строка ~380-420
# БЫЛО:
final_text = await response_generator.generate(...)

# СТАНЕТ:
final_text, response_metadata = await response_generator.generate(...)

# Найти где сохраняется в историю - примерно строка ~440-450
# БЫЛО:
chat.history[user_id].append({
    "role": "assistant",
    "content": final_text
})

# СТАНЕТ:
chat.history[user_id].append({
    "role": "assistant",
    "content": final_text,
    "metadata": response_metadata
})
```

### Step 3: Рефакторинг response_generator.py

**Файл:** `src/response_generator.py`

#### 3.1 Метод generate() (строки ~50-150)
**Изменения:**
- Возвращать tuple `(text, metadata)` вместо просто `text`
- Собирать metadata о CTA

```python
async def generate(...) -> Tuple[str, dict]:
    # ... генерация ...
    
    metadata = {
        "intent": router_result.get("intent"),
        "user_signal": router_result.get("user_signal"),
        "cta_added": cta_was_added,
        "cta_type": user_signal if cta_was_added else None,
        "humor_generated": False
    }
    
    return final_text, metadata
```

#### 3.2 Метод _count_cta_occurrences() (строки 820-860)
**Полная замена метода:**
```python
def _count_cta_occurrences(self, user_signal: str, history: list) -> int:
    """Подсчитывает CTA через metadata, не через текст"""
    count = 0
    for msg in history:
        if msg.get("role") == "assistant":
            metadata = msg.get("metadata", {})
            if metadata.get("cta_type") == user_signal and metadata.get("cta_added"):
                count += 1
    return count
```

#### 3.3 Метод _should_add_offer() (строки 588-723)
**Изменения:**
- Использовать новый _count_cta_occurrences
- Убрать поиск по фразам

#### 3.4 Метод _inject_offer() (строки 790-820)
**Изменения:**
- НЕ добавлять маркеры в текст
- Удалить/закомментировать строки с маркерами
- Возвращать только чистый текст с CTA

#### 3.5 Метод _get_cta_marker() (строка ~960)
**Изменения:**
- Удалить метод полностью ИЛИ
- Вернуть пустую строку `return ""`
- Этот метод больше не нужен!

### Step 4: Обратная совместимость

**Добавить в response_generator.py:**
```python
def _get_message_metadata(self, msg: dict) -> dict:
    """Helper для обратной совместимости со старыми сообщениями"""
    if "metadata" in msg:
        return msg["metadata"]
    
    # Fallback для старых сообщений без metadata
    return {
        "cta_added": False,
        "cta_type": None,
        "user_signal": "exploring_only"
    }
```

### Step 5: Обновление логики сохранения test_results

**Файл:** `http_sandbox_universal.py`  
**Изменения:** 
- НЕ сохранять маркеры в MD файлы
- Сохранять metadata отдельной строкой для анализа

```python
# В функции сохранения результатов
# Вместо сохранения маркеров в тексте, добавить:
if metadata and metadata.get('cta_added'):
    md_content += f"**CTA:** {metadata.get('cta_type')} (органично интегрирован)\n"
```

### Step 6: Тестирование

**Тестовые сценарии:**
1. Запустить `test_aggressive_skeptic.json` - проверить что CTA не повторяется > 2 раз
2. Проверить органичную интеграцию CTA
3. Убедиться что в test_results/*.md нет HTML комментариев
4. Протестировать с разными user_signal

**Команда для теста:**
```bash
python http_sandbox_universal.py --file test_aggressive_skeptic.json dialog_aggressive_skeptic
```

## ⚠️ Критические моменты

### НЕ ЗАБЫТЬ:
1. **Обновить все места** где используется history - может быть несколько
2. **Сохранить backward compatibility** - старые диалоги без metadata
3. **НЕ удалять** инструкцию Claude для органичной интеграции - она УЖЕ работает!
4. **НЕ трогать** `_build_messages()` - он УЖЕ обновлён в Phase 1
5. **Протестировать** rate limiting для каждого user_signal
6. **Проверить async/await** в main.py при изменении generate()

### УДАЛИТЬ/ИЗМЕНИТЬ:
1. Все закомментированные строки с маркерами (810-815)
2. Поиск CTA по фразам в _count_cta_occurrences (текущая хрупкая логика)
3. Метод _get_cta_marker() или вернуть пустую строку
4. Логику добавления HTML комментариев в _inject_offer()

## 📈 Метрики успеха

- ✅ CTA не повторяется больше 2 раз для price_sensitive
- ✅ CTA не повторяется больше 1 раза для anxiety_about_child
- ✅ Claude органично интегрирует CTA в 70%+ случаев
- ✅ Нет видимых маркеров ни в каких выводах
- ✅ Rate limiting работает корректно
- ✅ Старые диалоги не ломаются

## 🔍 Проверка результата

После внедрения проверить:
1. В файлах test_results/*.md больше нет `<!-- [CTA_*] -->`
2. CTA появляется органично внутри текста
3. Повторения CTA ограничены правильно
4. metadata сохраняется в history

## 📝 Дополнительные улучшения (опционально)

1. **Логирование metadata** в test_results для анализа
2. **Dashboard** для мониторинга CTA эффективности
3. **A/B тестирование** разных CTA формулировок

## 🔑 Ключевые изменения от v1.0 к v2.0

1. **Добавлено:** Информация что Phase 1 (усиление инструкции) УЖЕ сделана
2. **Уточнено:** Нужно использовать grep для поиска точных строк в main.py
3. **Добавлено:** Обработка метода _get_cta_marker()
4. **Добавлено:** Step 5 - обновление логики сохранения test_results
5. **Уточнено:** async/await важность в main.py
6. **Добавлено:** Предупреждение НЕ трогать _build_messages()

---

**Статус:** План готов к выполнению  
**Приоритет:** Высокий  
**Время на внедрение:** ~2-3 часа  
**Риск:** Средний (есть fallback для старых данных)  
**Важно:** Phase 1 уже выполнена, не переделывать!