# Ukido AI Assistant v0.12.12 - Production Ready

## ⚡ Критично для старта

```bash
# 1. Проверь ветку (юмор только в feature/zhvanetsky-humor)
git status  # Должно быть: On branch feature/zhvanetsky-humor

# 2. Запуск сервера
python src/main.py
# ✅ Должно быть: "🎭 Система юмора Жванецкого инициализирована (вероятность: 33.0%)"

# 3. Быстрый тест диалога
python http_sandbox_simple.py dialog_5
cat test_results/dialog_5_simple.md  # Проверь результат
```

## 🎯 Суть проекта за 30 секунд

**Что это:** AI-чатбот для детской школы soft skills Ukido
**Для кого:** Родители детей 7-14 лет из Украины  
**Ключевая фича:** Адаптивные ответы под эмоциональное состояние родителя

## 🏗️ Архитектура: Flow обработки запроса

```
USER MESSAGE 
    ↓
[1] ROUTER (Gemini 2.5 Flash) - router.py
    - Декомпозирует вопросы на атомарные части
    - Определяет intent: success/offtopic/need_simplification
    - Определяет user_signal: price_sensitive/anxiety/ready_to_buy/exploring
    - Выбирает до 4 документов из knowledge_base/ (16 MD файлов)
    - Определяет social_context: greeting/thanks/farewell/apology
    - Генерирует implicit_questions для ready_to_buy без явных вопросов
    ↓
[2] MAIN ORCHESTRATOR - main.py
    - Сохраняет в history_manager.py (LRU Cache 1000 users, 10 msgs/user)
    - HOTFIX (строки 159-179): восстанавливает user_signal для offtopic
    - Обновляет social_state.py (pure_social блокирует юмор)
    - Решает: генерировать ответ или использовать стандартный
    ↓
[3a] Если SUCCESS → GENERATOR (Claude Haiku) - response_generator.py
     - Генерирует ответ на основе документов + вопросов
     - Адаптирует тон через tone_map под user_signal
     - Dynamic few-shot примеры из offers_catalog.py
     - Добавляет CTA с rate limiting (1 раз в 2 сообщения)
     
[3b] Если OFFTOPIC → HUMOR/STANDARD - zhvanetsky_humor.py или standard_responses.py
     - check_user_signal() блокирует для anxiety/price_sensitive
     - 33% шанс юмора через random.random() < 0.33
     - Rate limiting: max 3 шутки/час на пользователя
     - Иначе стандартная фраза из списка
    ↓
RESPONSE TO USER
```

## 🎯 State Machine - Критичные детали

### 4 сигнала и их приоритеты:
1. **ready_to_buy** > 2. **anxiety_about_child** > 3. **price_sensitive** > 4. **exploring_only**

### Ключевые правила сигналов:
- **price_sensitive**: 
  - ИНЕРЦИЯ 85% - сохраняется почти весь диалог
  - Сбрасывается ТОЛЬКО при явном принятии цены
  - Блокирует юмор полностью
- **anxiety_about_child**: 
  - БЛОКИРУЕТ юмор даже на offtopic
  - Требует эмпатии в первом предложении ("Многие родители...")
  - Триггеры: "боится", "плачет", "стеснительный", "замкнутый"
- **ready_to_buy**: 
  - ВСЕГДА генерирует implicit_question если нет явного вопроса
  - Определяется по телеграфному стилю (< 5 слов)
  - Юмор разрешён, но редко срабатывает
- **exploring_only**: 
  - Дефолт для всего неопределенного
  - Максимальная вероятность юмора

### Критические переходы:
- `exploring → anxiety`: при словах "боится", "стеснительный", "плачет"
- `price_sensitive → ready_to_buy`: ТОЛЬКО при явном принятии цены ("ладно, черт с деньгами")
- **HOTFIX**: Router часто сбрасывает сигнал на exploring для offtopic → main.py восстанавливает

## ⚠️ Критические места и Gotchas

### 1. HOTFIX user_signal (main.py:159-179)
**Проблема:** Gemini игнорирует инструкцию сохранять user_signal для offtopic
**Решение:** Глобальный словарь `chat.user_signals_history` хранит последний signal
**Влияние:** Без этого теряется контекст диалога при offtopic

### 2. Блокировка юмора
**Файлы:** main.py:210-225, zhvanetsky_humor.py:check_user_signal()
**Правило:** anxiety_about_child и price_sensitive ВСЕГДА блокируют юмор
**Проверка:** Диалоги 3 и 4 должны НЕ содержать юмор на offtopic

### 3. Детерминизм vs Случайность
**Файл:** config.py:DETERMINISTIC_MODE
**Дефолт:** False (случайный юмор в production)
**Для тестов:** Установи True для воспроизводимости

### 4. Эмодзи удалены
**Файлы:** offers_catalog.py, response_generator.py
**Инструкция:** "НЕ ИСПОЛЬЗУЙ ЭМОДЗИ В ОТВЕТАХ"
**Остаток:** Сервер может возвращать 💚 в старых CTA - это кеш

## 📋 Структура кода - только критичное

```
src/
├── main.py                 # Оркестратор + HOTFIX для user_signal (159-179)
├── router.py               # Gemini роутер (600+ строк промпта!)
├── response_generator.py   # Claude генератор + tone_map + few-shot
├── history_manager.py      # LRU Cache: OrderedDict на 1000 users
├── zhvanetsky_humor.py     # Юмор + check_user_signal() + rate limiting  
├── offers_catalog.py       # CTA + few-shot примеры + rate limiting
├── social_state.py         # Отслеживание pure_social (блокирует юмор)
└── knowledge_base/         # 16 MD документов (методика, цены, FAQ...)
    ├── methodology.md      # Основа для exploring вопросов
    ├── pricing.md          # Для price_sensitive
    └── faq.md              # Частые вопросы

http_sandbox_simple.py      # ✅ ИСПОЛЬЗУЙ для тестов (requests, 150 строк)
test_humor_dialogues.json   # 9 полных диалогов по 6-7 сообщений
test_results/               # Сюда сохраняются MD файлы с результатами
```

## 🧪 Как тестировать

### Быстрый тест диалога:
```bash
python http_sandbox_simple.py dialog_5  # exploring → anxiety переход
# Результат в test_results/dialog_5_simple.md
```

### Что проверять:
1. **Переходы сигналов** - смотри "Сигналы:" в MD файле
2. **Блокировка юмора** - anxiety/price_sensitive не должны шутить
3. **Эмпатия** - "Многие родители..." для anxiety
4. **CTA не дублируются** - rate limiting 1 раз в 2 сообщения

### Все 9 тест-диалогов:

| ID | Название | Сигнал | Что проверять |
|----|----------|--------|---------------|
| dialog_1 | Мама-исследователь | exploring_only | Юмор 1-2/3 на offtopic |
| dialog_2 | Решительный папа | ready_to_buy | Implicit questions, юмор после записи |
| dialog_3 | Тревожная мама | anxiety_about_child | БЕЗ юмора, эмпатия 100% |
| dialog_4 | Скептик-торговец | price_sensitive | БЕЗ юмора, работа со скидками |
| dialog_5 | Переходная мама | exploring → anxiety | Переход на 4-м, блокировка юмора |
| dialog_6 | Быстрый покупатель | ready_to_buy | Телеграфный стиль, implicit questions |
| dialog_7 | Активная мама | exploring → ready_to_buy | Переход при "запишите" |
| dialog_8 | Быстрый скептик | exploring → price_sensitive | Переход на 2-м при "дорого" |
| dialog_9 | Весёлый исследователь | exploring_only | Максимум юмора на offtopic |

## 🔧 Текущий статус и проблемы

### ✅ Что работает:
- State Machine с HOTFIX
- Блокировка юмора для чувствительных сигналов  
- Простая HTTP песочница
- CTA с rate limiting

### ⚠️ Известные проблемы:
1. **Router путает offtopic** - вопросы о программировании часто success
2. **Timeout в сложной песочнице** - используй простую
3. **Английские слова в ответах** - "torture" вместо "мучение"

## 🚀 Production конфигурация

```python
# src/config.py
MODEL_ROUTER = "google/gemini-2.5-flash"
MODEL_ANSWER = "anthropic/claude-3.5-haiku"  
MODEL_HUMOR = "anthropic/claude-3.5-haiku"
DETERMINISTIC_MODE = False  # True для тестов
MAX_HISTORY_SIZE = 10
CACHE_SIZE = 1000  # LRU для пользователей
```

## 📈 Критические изменения (только важные)

### v0.12.12 - Простая песочница + Удаление эмодзи
- `http_sandbox_simple.py` - 150 строк вместо 800+, работает без багов
- Удалены все эмодзи из ответов

### v0.12.5 - HOTFIX блокировки юмора  
- main.py:159-179 - восстановление user_signal из истории
- Без этого юмор генерировался для anxiety (критично!)

### v0.12.0 - Production Ready MVP
- LRU Cache на 1000 пользователей
- State Machine 98% точность

## 📚 Документация для углубления

- `HTTP_SANDBOX_TESTING_GUIDE.md` - детальная инструкция по тестированию
- `TESTING_METHODOLOGY.md` - методология тестирования диалогов
- `router.py:600-650` - критические правила определения сигналов

---

**Статус:** Production Ready с HOTFIX для user_signal
**Ветка для юмора:** feature/zhvanetsky-humor
**Тестирование:** http_sandbox_simple.py
**Критично:** HOTFIX в main.py:159-179 держит State Machine