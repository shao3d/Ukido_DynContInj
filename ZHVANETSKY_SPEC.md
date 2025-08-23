# 🎭 Спецификация интеграции юмора Жванецкого в Ukido AI Assistant

## 📋 Оглавление
1. [Концепция](#концепция)
2. [Архитектура решения](#архитектура-решения)
3. [Детальная реализация](#детальная-реализация)
4. [Безопасность и контроль](#безопасность-и-контроль)
5. [Метрики и мониторинг](#метрики-и-мониторинг)
6. [План внедрения](#план-внедрения)

## 🎯 Концепция

### Философия подхода
Юмор Жванецкого - это не просто шутки, а **особый стиль мышления** с неожиданными поворотами, которые заставляют улыбнуться и задуматься. Для школы soft skills это демонстрация навыка нестандартного мышления.

### Ключевые принципы
- **Редкость** - максимум 10% от offtopic запросов
- **Уместность** - только при позитивном настроении
- **Безопасность** - трёхуровневая проверка
- **Органичность** - связь с контекстом диалога
- **Экономичность** - 80%+ из кэша после месяца

## 🏗️ Архитектура решения

### Высокоуровневый флоу
```
User Message
    ↓
Gemini Router → offtopic
    ↓
main.py: Проверка условий
    ↓
[mood_ok + topic_safe + 10% random + not_used]
    ↓
ZhvanetskyAI: Проверка кэша
    ↓
Кэш miss → Claude Haiku генерация
Кэш hit → Адаптация под контекст
    ↓
Ответ с юмором
```

### Компоненты системы

```
src/zhvanetsky/
├── __init__.py
├── zhvanetsky_ai.py      # Основной генератор
├── humor_cache.py        # Семантический кэш
├── safety_checker.py     # Проверки безопасности
└── humor_tracker.py      # Отслеживание использования
```

## 💻 Детальная реализация

### 1. zhvanetsky_ai.py - Генератор юмора

```python
class ZhvanetskyAI:
    def __init__(self, client):
        self.client = client  # Claude Haiku клиент
        self.cache = HumorCache()
        self.prompt_template = """
Ты - консультант детской школы soft skills Ukido. 
Родитель спросил не по теме: "{message}"

Ответь ОДНОЙ фразой в стиле Михаила Жванецкого:
- Мягкая ирония с неожиданным поворотом
- Связь с пользой нашей школы в конце
- Доброжелательный тон

Примеры стиля:
- "Футбол? У нас тоже командная игра, только мяч - это идеи"
- "Пробки? Знаю способ - пока стоите, ребёнок развивается"

Ответ:"""
    
    async def generate_humor(self, message: str, context: dict) -> str:
        # 1. Проверяем кэш
        cache_key = self.cache.get_semantic_key(message)
        if cached := self.cache.find_similar(cache_key):
            return self.cache.adapt_cached(cached, message)
        
        # 2. Генерируем новую шутку
        prompt = self.prompt_template.format(
            message=message,
            mood=context.get("mood", "friendly")
        )
        
        response = await self.client.generate(
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        
        # 3. Сохраняем в кэш
        if self.validate_response(response):
            self.cache.save(cache_key, response, context)
            return response
        
        return None  # Fallback на стандартный offtopic
```

### 2. humor_cache.py - Динамический кэш

```python
class HumorCache:
    def __init__(self, max_size=500):
        self.cache = OrderedDict()  # LRU-подобная структура
        self.max_size = max_size
        self.hit_count = 0
        self.miss_count = 0
    
    def get_semantic_key(self, message: str) -> str:
        """Создаёт семантический ключ для сообщения"""
        # Извлекаем ключевые слова и тему
        topic = self.extract_topic(message)
        keywords = self.extract_keywords(message)
        return f"{topic}:{':'.join(sorted(keywords))}"
    
    def find_similar(self, key: str) -> Optional[dict]:
        """Ищет похожую шутку в кэше"""
        if key in self.cache:
            self.hit_count += 1
            return self.cache[key]
        
        # Fuzzy matching для похожих ключей
        for cached_key, value in self.cache.items():
            if self.semantic_similarity(key, cached_key) > 0.8:
                self.hit_count += 1
                return value
        
        self.miss_count += 1
        return None
    
    def adapt_cached(self, cached: dict, new_message: str) -> str:
        """Адаптирует кэшированную шутку под новый контекст"""
        base_joke = cached["response"]
        
        # Простая адаптация - замена ключевых слов
        old_keywords = cached["keywords"]
        new_keywords = self.extract_keywords(new_message)
        
        adapted = base_joke
        for old, new in zip(old_keywords, new_keywords):
            if old != new and old in adapted:
                adapted = adapted.replace(old, new)
        
        return adapted
```

### 3. safety_checker.py - Система безопасности

```python
class SafetyChecker:
    # Небезопасные темы для юмора
    UNSAFE_TOPICS = [
        "болезнь", "болеет", "больница", "врач", "лечение",
        "умер", "погиб", "авария", "катастрофа", "беда",
        "проблема", "кризис", "плохо", "ужасно",
        "нет денег", "банкрот", "долги", "развод"
    ]
    
    # Индикаторы негативного настроения
    NEGATIVE_MARKERS = [
        "дорого", "обман", "плохо", "ужасно", 
        "не нравится", "возмутительно", "разочарован"
    ]
    
    def validate_humor_context(self, user_signal: str, 
                              history: list, 
                              message: str) -> dict:
        """Полная валидация контекста для юмора"""
        
        result = {
            "safe": True,
            "appropriate": True,
            "mood": "neutral",
            "topic": None,
            "reason": None
        }
        
        # 1. Проверка user_signal
        if user_signal in ["anxiety_about_child", "price_sensitive"]:
            result["appropriate"] = False
            result["reason"] = f"inappropriate_signal:{user_signal}"
            return result
        
        # 2. Проверка истории на негатив
        mood = self.check_dialogue_mood(history)
        result["mood"] = mood
        
        if mood == "negative":
            result["appropriate"] = False
            result["reason"] = "negative_mood"
            return result
        
        # 3. Проверка безопасности темы
        if not self.is_safe_topic(message):
            result["safe"] = False
            result["reason"] = "unsafe_topic"
            return result
        
        # 4. Определение темы для контекста
        result["topic"] = self.classify_topic(message)
        
        return result
    
    def get_humor_probability(self, user_history: list, 
                            user_signal: str) -> float:
        """Адаптивная вероятность юмора"""
        base_probability = 0.1  # 10% базовая
        
        # Увеличиваем для дружелюбных
        if user_signal == "exploring_only":
            base_probability *= 1.2
        
        # Увеличиваем если были позитивные реакции
        positive_count = sum(1 for msg in user_history 
                           if any(word in msg.lower() 
                                 for word in ["спасибо", "отлично", "здорово"]))
        
        if positive_count >= 2:
            base_probability *= 1.5
        
        return min(base_probability, 0.15)  # Максимум 15%
```

### 4. humor_tracker.py - Отслеживание использования

```python
class HumorTracker:
    def __init__(self):
        self.usage = {}  # user_id -> usage_data
        self.global_stats = {
            "total_shown": 0,
            "total_successful": 0,
            "topics": defaultdict(int)
        }
    
    def was_used(self, user_id: str) -> bool:
        """Проверка использования для пользователя"""
        return user_id in self.usage
    
    def mark_used(self, user_id: str, topic: str = None):
        """Отметка использования"""
        self.usage[user_id] = {
            "timestamp": datetime.now(),
            "topic": topic,
            "success": None  # Определяется по следующему сообщению
        }
        self.global_stats["total_shown"] += 1
        if topic:
            self.global_stats["topics"][topic] += 1
    
    def update_success(self, user_id: str, continued: bool):
        """Обновление успешности (продолжил ли диалог)"""
        if user_id in self.usage:
            self.usage[user_id]["success"] = continued
            if continued:
                self.global_stats["total_successful"] += 1
    
    def get_success_rate(self) -> float:
        """Общий процент успешности"""
        if self.global_stats["total_shown"] == 0:
            return 0.0
        return self.global_stats["total_successful"] / self.global_stats["total_shown"]
```

### 5. Интеграция в main.py

```python
# main.py - добавления после строки 177

# Импорты в начале файла
from zhvanetsky import ZhvanetskyAI, SafetyChecker, HumorTracker

# Инициализация после строки 50
if config.HUMOR_ENABLED:
    zhvanetsky_ai = ZhvanetskyAI(
        client=OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model="anthropic/claude-3-haiku"  # Дешевле для юмора
        )
    )
    safety_checker = SafetyChecker()
    humor_tracker = HumorTracker()

# В блоке обработки offtopic (строка ~177)
if result["intent"] == "offtopic":
    # Проверяем возможность использования юмора
    if config.HUMOR_ENABLED and not humor_tracker.was_used(request.user_id):
        
        # Валидация контекста
        humor_context = safety_checker.validate_humor_context(
            user_signal=result.get("user_signal", "exploring_only"),
            history=history_list,
            message=request.message
        )
        
        if humor_context["safe"] and humor_context["appropriate"]:
            # Адаптивная вероятность
            probability = safety_checker.get_humor_probability(
                user_history=history_list,
                user_signal=result.get("user_signal")
            )
            
            if random.random() < probability:
                # Генерируем юмор
                try:
                    humor_response = await zhvanetsky_ai.generate_humor(
                        message=request.message,
                        context=humor_context
                    )
                    
                    if humor_response:
                        # Отмечаем использование
                        humor_tracker.mark_used(
                            request.user_id, 
                            humor_context["topic"]
                        )
                        
                        # Логирование
                        logger.info(
                            f"🎭 Humor: user={request.user_id}, "
                            f"topic={humor_context['topic']}, "
                            f"mood={humor_context['mood']}"
                        )
                        
                        # Возвращаем с метаданными
                        return JSONResponse({
                            "response": humor_response,
                            "intent": "offtopic",
                            "humor_used": True,
                            "confidence": result.get("confidence", 1.0)
                        })
                        
                except Exception as e:
                    logger.error(f"Humor generation failed: {e}")
    
    # Стандартный offtopic если юмор не использован
    response_text = standard_responses.get_offtopic_response()
```

## 🔐 Безопасность и контроль

### Трёхуровневая система проверок

#### Уровень 1: User Signal
- ❌ `anxiety_about_child` - никогда не шутим
- ❌ `price_sensitive` - никогда не шутим  
- ✅ `exploring_only` - можно, даже чуть чаще
- ✅ `ready_to_buy` - можно, но редко

#### Уровень 2: Dialogue Mood
- Анализ последних 3 сообщений
- Поиск негативных маркеров
- Проверка общей тональности

#### Уровень 3: Topic Safety
- Blacklist опасных тем
- Проверка контекста упоминаний
- Валидация уместности

### Fallback стратегия
Если что-то пошло не так:
1. Логируем ошибку
2. Возвращаем стандартный offtopic
3. Не прерываем основной флоу

## 📊 Метрики и мониторинг

### Ключевые метрики

```python
# Добавить в /metrics endpoint
"humor_metrics": {
    "enabled": config.HUMOR_ENABLED,
    "total_shown": humor_tracker.global_stats["total_shown"],
    "success_rate": humor_tracker.get_success_rate(),
    "cache_hit_rate": zhvanetsky_ai.cache.get_hit_rate(),
    "topics": humor_tracker.global_stats["topics"],
    "avg_generation_time": zhvanetsky_ai.avg_generation_time
}
```

### A/B тестирование
```python
# Можно включать для части пользователей
def should_enable_humor(user_id: str) -> bool:
    # Например, для 50% пользователей
    return hash(user_id) % 2 == 0
```

### Логирование
- Каждое использование юмора
- Причины отказа от юмора
- Ошибки генерации
- Метрики кэша

## 📅 План внедрения

### Фаза 1: MVP (4-6 часов)
1. **Создание базовой структуры** (1 час)
   - Файлы zhvanetsky/*.py
   - Базовые классы

2. **Реализация SafetyChecker** (1 час)
   - Проверки безопасности
   - Адаптивная вероятность

3. **Простой генератор** (1 час)
   - Промпт для Claude Haiku
   - Базовая генерация

4. **Интеграция в main.py** (1 час)
   - Подключение в offtopic блок
   - Конфигурация

5. **Тестирование** (2 часа)
   - Unit тесты
   - Ручное тестирование

### Фаза 2: Оптимизация (2-3 часа)
1. **Реализация кэша** (1 час)
   - Семантические ключи
   - Адаптация шуток

2. **Метрики** (30 мин)
   - Добавление в /metrics
   - Логирование

3. **Тонкая настройка** (1.5 часа)
   - Улучшение промпта
   - Настройка вероятностей

### Фаза 3: Production (2 часа)
1. **Мониторинг** (1 час)
   - Dashboard метрик
   - Алерты

2. **A/B тестирование** (1 час)
   - Разделение пользователей
   - Сбор статистики

## 🎯 Критерии успеха MVP

1. **Функциональность**
   - ✅ Генерирует юмор для offtopic
   - ✅ Не ломает основной pipeline
   - ✅ Можно отключить одним флагом

2. **Безопасность**
   - ✅ 0 неуместных шуток
   - ✅ Не активируется при негативе
   - ✅ Fallback на стандартный ответ

3. **Производительность**
   - ✅ <2 сек на генерацию
   - ✅ <$0.001 за шутку
   - ✅ 50%+ cache hit после недели

4. **Качество**
   - ✅ Шутки в стиле Жванецкого
   - ✅ Связь с контекстом школы
   - ✅ Позитивные реакции пользователей

## 🚀 Команды для начала работы

```bash
# Создание новой ветки
git checkout -b feature/zhvanetsky-humor

# Создание структуры
mkdir -p src/zhvanetsky
touch src/zhvanetsky/__init__.py
touch src/zhvanetsky/zhvanetsky_ai.py
touch src/zhvanetsky/humor_cache.py
touch src/zhvanetsky/safety_checker.py
touch src/zhvanetsky/humor_tracker.py

# Создание тестов
mkdir -p tests/unit/zhvanetsky
touch tests/unit/zhvanetsky/test_safety_checker.py
touch tests/unit/zhvanetsky/test_humor_cache.py

# Запуск тестов
python -m pytest tests/unit/zhvanetsky/ -v
```

## 📝 Примеры промптов для Claude Haiku

### Базовый промпт
```
Ты консультант детской школы soft skills Ukido.
Родитель спросил про {topic}: "{message}"

Ответь одной фразой в стиле Жванецкого - с мягкой иронией и неожиданным поворотом, связав с пользой нашей школы.

Пример: "Футбол? У нас тоже 22 человека бегают - только за знаниями, и никто не промахивается мимо будущего."

Твой ответ:
```

### Промпт с контекстом
```
Контекст: родитель в хорошем настроении, изучает школу
Тема вопроса: {topic}
Вопрос: "{message}"

Создай дружелюбную шутку в стиле Жванецкого (1-2 предложения), которая:
1. Отвечает на вопрос с юмором
2. Поворачивает к пользе наших курсов
3. Не обижает и не высмеивает

Ответ:
```

## 🔄 Обратная связь и итерации

После запуска собираем:
1. Количество использований
2. Реакции пользователей (продолжают ли диалог)
3. Какие темы работают лучше
4. Оптимальная вероятность

На основе данных:
- Корректируем промпты
- Настраиваем вероятности
- Расширяем/сужаем список тем
- Улучшаем кэширование

---

**Документ подготовлен**: 21.08.2025
**Версия**: 1.0
**Для реализации в**: v0.13.0