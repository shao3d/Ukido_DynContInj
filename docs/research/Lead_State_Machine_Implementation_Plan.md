# План технической реализации машины состояний для Ukido AI Assistant

## 🎯 Цель
Реализовать легковесную машину состояний для определения степени готовности лида к покупке и адаптации ответов под его эмоциональное состояние, **без увеличения latency**.

## ⏱️ Timeline: 2 дня

- **День 1**: Backend изменения (Router + Generator)
- **День 2**: Streaming, кеширование, тестирование

## 📋 Техническая спецификация

### Архитектура изменений

```
[User Message] 
    ↓
[Gemini Router] (+200 токенов в промпт)
    ├── Стандартная классификация
    └── NEW: user_signal detection
    ↓
[Claude Generator] (+300 токенов dynamic)
    ├── Стандартная генерация
    └── NEW: Dynamic few-shot based on signal
    ↓
[Streaming Response] (NEW)
    └── Отдача по частям для снижения perceived latency
```

## 📝 Детальный план реализации

### День 1 - Утро (4 часа)

#### 1.1 Обновление Gemini Router (1.5 часа)

**Файл:** `src/router.py`

**Изменения в промпте (добавить после определения документов):**

```python
# В методе route() класса Router, строка ~150
# После секции с выбором документов добавить:

router_prompt_addition = """
7. ОПРЕДЕЛЕНИЕ КЛЮЧЕВОГО СИГНАЛА ПОЛЬЗОВАТЕЛЯ:
Проанализируй сообщение и определи ОДИН основной сигнал состояния пользователя:

- "price_sensitive" - если спрашивает о ценах, скидках, способах оплаты, рассрочке
- "anxiety_about_child" - если упоминает проблемы ребенка (стеснительность, неуверенность, сложности в общении)
- "ready_to_buy" - если спрашивает как записаться, когда начало, есть ли места
- "exploring_only" - если задает общие вопросы о школе, методологии, курсах без конкретики

Возвращай в поле "user_signal" только одно значение из списка выше.
Если не можешь однозначно определить - используй "exploring_only".

Примеры:
- "Сколько стоит курс Юный Оратор?" → "price_sensitive"
- "У меня сын очень стеснительный, поможет ли ваш курс?" → "anxiety_about_child"
- "Как записаться на пробное занятие?" → "ready_to_buy"
- "Расскажите о вашей школе" → "exploring_only"
"""
```

**Изменения в response схеме:**

```python
# В классе RouterResponse (models.py), добавить поле:
user_signal: Optional[str] = Field(
    default="exploring_only",
    description="Ключевой сигнал состояния пользователя"
)
```

#### 1.2 Создание каталога предложений (0.5 часа)

**Новый файл:** `src/offers_catalog.py`

```python
OFFERS_CATALOG = {
    "price_sensitive": {
        "text": "💰 Кстати, у нас есть калькулятор выгоды, который покажет, как вложение в soft skills окупится в будущем. Хотите посчитать для вашего случая?",
        "priority": "medium",
        "placement": "end"
    },
    "anxiety_about_child": {
        "text": "📚 Специально для родителей стеснительных детей мы подготовили бесплатный мини-курс '5 упражнений для развития уверенности'. Можно начать заниматься дома уже сегодня. Отправить вам на email?",
        "priority": "high",
        "placement": "end"
    },
    "ready_to_buy": {
        "text": "🎯 Отличная новость! Запись на пробное занятие открыта, и у нас как раз есть 3 свободных места в группе. Вот прямая ссылка для записи: [ukido.ua/trial]. Места разбирают быстро, не откладывайте!",
        "priority": "high",
        "placement": "end_with_urgency"
    },
    "exploring_only": {
        "text": "📋 Чтобы подобрать идеальный курс для вашего ребенка, предлагаем пройти короткий тест из 5 вопросов. Это займет 2 минуты. Интересно?",
        "priority": "low",
        "placement": "end"
    }
}

# Tone adaptations based on signal
TONE_ADAPTATIONS = {
    "price_sensitive": {
        "prefix": "",
        "style": "Подчеркивай ценность и окупаемость инвестиции в развитие ребенка."
    },
    "anxiety_about_child": {
        "prefix": "Понимаем вашу заботу о ребенке. ",
        "style": "Начинай с эмпатии, давай конкретные гарантии и примеры успеха похожих детей."
    },
    "ready_to_buy": {
        "prefix": "Отлично, что вы готовы начать! ",
        "style": "Будь конкретным, давай четкие инструкции, создавай ощущение urgency."
    },
    "exploring_only": {
        "prefix": "",
        "style": "Будь информативным и дружелюбным, без давления."
    }
}
```

#### 1.3 Обновление Response Generator (2 часа)

**Файл:** `src/response_generator.py`

**Добавить импорты:**
```python
from src.offers_catalog import OFFERS_CATALOG, TONE_ADAPTATIONS
```

**Изменения в методе generate():**

```python
# Строка ~100, после получения route_result
async def generate(self, route_result: dict, history: List[dict]) -> str:
    # Получаем user_signal
    user_signal = route_result.get("user_signal", "exploring_only")
    
    # Добавляем dynamic few-shot в промпт
    dynamic_examples = self._get_dynamic_examples(user_signal)
    
    # Модифицируем system prompt
    tone_adaptation = TONE_ADAPTATIONS.get(user_signal, {})
    
    # Добавляем в основной промпт
    if dynamic_examples:
        prompt = f"{prompt}\n\nПРИМЕРЫ АДАПТАЦИИ ТОНА:\n{dynamic_examples}"
    
    if tone_adaptation.get("style"):
        prompt = f"{prompt}\n\nСТИЛЬ ОТВЕТА: {tone_adaptation['style']}"
    
    # Генерируем ответ
    response = await self._call_claude(prompt, documents, history)
    
    # Добавляем предложение в конец
    offer = OFFERS_CATALOG.get(user_signal)
    if offer and offer["priority"] in ["high", "medium"]:
        response = self._inject_offer(response, offer)
    
    return response

def _get_dynamic_examples(self, user_signal: str) -> str:
    """Возвращает 1-2 примера для dynamic few-shot"""
    
    examples = {
        "price_sensitive": """
Пример диалога с родителем, чувствительным к цене:
User: Дорого ли у вас обучение?
Assistant: Давайте посмотрим на это как на инвестицию. Курс "Юный Оратор" стоит 6000 грн в месяц, 
но навыки публичных выступлений помогут вашему ребенку всю жизнь - от школьных презентаций 
до будущей карьеры. У нас есть скидки при полной оплате (10%) и для второго ребенка (15%).
[В конце органично предложи калькулятор ROI]
""",
        
        "anxiety_about_child": """
Пример диалога с тревожным родителем:
User: Мой сын очень стеснительный, не знаю, справится ли
Assistant: Понимаем вашу тревогу - многие родители приходят именно с такой проблемой. 
В наших группах максимум 6 детей, что создает камерную, безопасную атмосферу. 
Педагоги специально обучены работе со стеснительными детьми. 76% наших учеников 
избавляются от страха публичных выступлений уже через 2 месяца.
[В конце предложи мини-курс по уверенности]
""",
        
        "ready_to_buy": """
Пример диалога с готовым к покупке:
User: Хочу записать дочку, что нужно сделать?
Assistant: Отлично! Вот простые шаги: 1) Выберите удобное время пробного занятия 
2) Заполните короткую форму на сайте 3) Получите подтверждение на email. 
Пробное занятие бесплатное, после него решите, подходит ли формат.
[Дай прямую ссылку и подчеркни, что места ограничены]
""",
        
        "exploring_only": """
Пример информативного диалога:
User: Расскажите про вашу школу
Assistant: Ukido - это школа развития soft skills для детей 7-14 лет. 
Мы помогаем детям стать увереннее, научиться выступать публично, 
управлять эмоциями и работать в команде. У нас 3 основных курса, 
каждый решает конкретные задачи развития.
[В конце предложи тест на подбор курса]
"""
    }
    
    return examples.get(user_signal, "")

def _inject_offer(self, response: str, offer: dict) -> str:
    """Органично добавляет предложение в конец ответа"""
    
    # Убираем последнюю точку если есть
    if response.rstrip().endswith('.'):
        response = response.rstrip()[:-1]
    
    # Добавляем переход и предложение
    transition = ". \n\n" if offer["placement"] == "end" else "! \n\n"
    
    return f"{response}{transition}{offer['text']}"
```

### День 1 - Вечер (4 часа)

#### 1.4 Реализация streaming (2 часа)

**Файл:** `src/main.py`

**Изменения для поддержки streaming:**

```python
from fastapi.responses import StreamingResponse
import asyncio

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming версия эндпоинта"""
    
    async def generate_stream():
        # Получаем результат от Router (это быстро, не стримим)
        route_result = await router.route(
            request.message, 
            history.get_history(request.user_id),
            request.user_id
        )
        
        # Начинаем streaming от Claude
        if route_result["status"] == "success":
            # Отправляем метаданные первым чанком
            yield f"data: {json.dumps({'type': 'metadata', 'signal': route_result.get('user_signal')})}\n\n"
            
            # Стримим основной ответ
            async for chunk in response_generator.generate_stream(route_result, history_messages):
                yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Небольшая задержка для smooth streaming
            
            # Добавляем offer в конце
            offer = OFFERS_CATALOG.get(route_result.get("user_signal"))
            if offer:
                yield f"data: {json.dumps({'type': 'offer', 'text': offer['text']})}\n\n"
        else:
            # Для offtopic отправляем сразу весь ответ
            yield f"data: {json.dumps({'type': 'complete', 'text': route_result['message']})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Для nginx
        }
    )
```

#### 1.5 Smart caching (2 часа)

**Новый файл:** `src/cache_manager.py`

```python
from typing import Optional, Dict, List
import hashlib
import json
from datetime import datetime, timedelta

class SmartCache:
    def __init__(self):
        # In-memory cache для MVP (позже можно Redis)
        self.cache = {}
        self.cache_ttl = timedelta(hours=1)
        
        # Паттерны для быстрого определения документов
        self.quick_patterns = {
            "price_sensitive": {
                "keywords": ["цен", "стои", "оплат", "скидк", "рассрочк"],
                "documents": ["pricing.md"],
                "signal": "price_sensitive"
            },
            "schedule": {
                "keywords": ["расписан", "когда", "время", "начало", "старт"],
                "documents": ["conditions.md"],
                "signal": "exploring_only"
            },
            "courses": {
                "keywords": ["оратор", "эмоциональн", "капитан", "курс"],
                "documents": ["courses_detailed.md"],
                "signal": "exploring_only"
            },
            "anxiety": {
                "keywords": ["стеснительн", "застенчив", "боится", "тревож"],
                "documents": ["methodology.md", "teachers_team.md"],
                "signal": "anxiety_about_child"
            }
        }
    
    def get_quick_match(self, message: str) -> Optional[Dict]:
        """Быстрое определение по ключевым словам"""
        message_lower = message.lower()
        
        for pattern_name, pattern_data in self.quick_patterns.items():
            if any(keyword in message_lower for keyword in pattern_data["keywords"]):
                return {
                    "documents": pattern_data["documents"],
                    "user_signal": pattern_data["signal"],
                    "cached": True,
                    "pattern": pattern_name
                }
        
        return None
    
    def get_cached_response(self, message: str, user_id: str) -> Optional[str]:
        """Получить закешированный ответ если есть"""
        cache_key = self._generate_key(message, user_id)
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if datetime.now() - entry["timestamp"] < self.cache_ttl:
                return entry["response"]
        
        return None
    
    def cache_response(self, message: str, user_id: str, response: str):
        """Закешировать ответ"""
        cache_key = self._generate_key(message, user_id)
        
        self.cache[cache_key] = {
            "response": response,
            "timestamp": datetime.now()
        }
    
    def _generate_key(self, message: str, user_id: str) -> str:
        """Генерация ключа для кеша"""
        # Нормализуем сообщение
        normalized = message.lower().strip()
        # Убираем знаки препинания
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        
        # Хешируем
        return hashlib.md5(f"{user_id}:{normalized}".encode()).hexdigest()
```

### День 2 - Утро (4 часа)

#### 2.1 Интеграция кеширования (1 час)

**Файл:** `src/main.py`

```python
from src.cache_manager import SmartCache

# Инициализация
cache = SmartCache()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Проверяем quick patterns
    quick_match = cache.get_quick_match(request.message)
    
    if quick_match:
        # Пропускаем Router для частых вопросов
        route_result = {
            "status": "success",
            "documents": quick_match["documents"],
            "user_signal": quick_match["user_signal"],
            "message": "",
            "decomposed_questions": [request.message]
        }
        print(f"⚡ Quick match: {quick_match['pattern']}")
    else:
        # Стандартный путь через Router
        route_result = await router.route(request.message, history_messages, request.user_id)
    
    # Остальная логика без изменений...
```

#### 2.2 Connection pooling и оптимизация (1 час)

**Файл:** `src/openrouter_client.py`

```python
import httpx
from typing import Optional

class OpenRouterClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        
        # Persistent connection pool
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0
            ),
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://ukido.ua",
                "X-Title": "Ukido AI Assistant"
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
```

#### 2.3 Метрики и мониторинг (2 часа)

**Новый файл:** `src/metrics.py`

```python
from datetime import datetime
from typing import Dict, List
import json

class MetricsCollector:
    def __init__(self):
        self.metrics = []
    
    def track_request(self, 
                      user_id: str,
                      message: str,
                      user_signal: str,
                      latency: float,
                      cached: bool = False):
        """Трекаем каждый запрос"""
        
        self.metrics.append({
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "message_length": len(message),
            "user_signal": user_signal,
            "latency": latency,
            "cached": cached
        })
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        if not self.metrics:
            return {}
        
        total = len(self.metrics)
        signals_count = {}
        latencies = []
        cache_hits = 0
        
        for m in self.metrics:
            signals_count[m["user_signal"]] = signals_count.get(m["user_signal"], 0) + 1
            latencies.append(m["latency"])
            if m["cached"]:
                cache_hits += 1
        
        return {
            "total_requests": total,
            "avg_latency": sum(latencies) / len(latencies),
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "cache_hit_rate": cache_hits / total,
            "signals_distribution": signals_count,
            "signals_percentages": {
                k: f"{v/total*100:.1f}%" 
                for k, v in signals_count.items()
            }
        }
    
    def save_to_file(self, filepath: str = "metrics.json"):
        """Сохранить метрики в файл"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "stats": self.get_stats(),
                "raw_data": self.metrics[-100:]  # Последние 100 записей
            }, f, indent=2, ensure_ascii=False)
```

### День 2 - Вечер (4 часа)

#### 2.4 Тестирование (2 часа)

**Новый файл:** `tests/test_state_machine.py`

```python
import pytest
import asyncio
from src.router import Router
from src.response_generator import ResponseGenerator
from src.cache_manager import SmartCache

class TestStateMachine:
    
    @pytest.fixture
    def router(self):
        return Router()
    
    @pytest.fixture
    def generator(self):
        return ResponseGenerator()
    
    @pytest.fixture
    def cache(self):
        return SmartCache()
    
    @pytest.mark.asyncio
    async def test_user_signals_detection(self, router):
        """Тестируем определение сигналов"""
        
        test_cases = [
            ("Сколько стоит обучение?", "price_sensitive"),
            ("Мой сын очень стеснительный", "anxiety_about_child"),
            ("Как записаться на курс?", "ready_to_buy"),
            ("Расскажите о школе", "exploring_only"),
            ("Есть ли скидки для двоих детей?", "price_sensitive"),
            ("Дочка боится выступать", "anxiety_about_child"),
        ]
        
        for message, expected_signal in test_cases:
            result = await router.route(message, [], "test_user")
            assert result.get("user_signal") == expected_signal, \
                f"Failed for '{message}': expected {expected_signal}, got {result.get('user_signal')}"
    
    @pytest.mark.asyncio
    async def test_dynamic_few_shot(self, generator):
        """Тестируем dynamic few-shot примеры"""
        
        signals = ["price_sensitive", "anxiety_about_child", "ready_to_buy", "exploring_only"]
        
        for signal in signals:
            examples = generator._get_dynamic_examples(signal)
            assert len(examples) > 0, f"No examples for {signal}"
            assert "User:" in examples, f"No user example in {signal}"
            assert "Assistant:" in examples, f"No assistant example in {signal}"
    
    def test_cache_patterns(self, cache):
        """Тестируем quick patterns"""
        
        test_cases = [
            ("Какая цена?", "price_sensitive"),
            ("Когда начинаются занятия?", "exploring_only"),
            ("Ребенок стеснительный", "anxiety_about_child"),
        ]
        
        for message, expected_signal in test_cases:
            result = cache.get_quick_match(message)
            assert result is not None, f"No match for '{message}'"
            assert result["user_signal"] == expected_signal
    
    @pytest.mark.asyncio
    async def test_latency_requirements(self, router, generator):
        """Проверяем что latency в пределах нормы"""
        
        import time
        
        # Router должен отвечать быстро
        start = time.time()
        route_result = await router.route("Сколько стоит?", [], "test")
        router_time = time.time() - start
        assert router_time < 3.0, f"Router too slow: {router_time}s"
        
        # Generator с учетом streaming первого чанка
        start = time.time()
        # Имитируем получение первого чанка
        # В реальности это будет первые 50 токенов
        first_chunk_time = 2.0  # целевое время
        assert first_chunk_time < 3.0, f"First chunk too slow: {first_chunk_time}s"
```

#### 2.5 A/B тестирование (2 часа)

**Новый файл:** `src/ab_testing.py`

```python
import random
from typing import Dict

class ABTestManager:
    def __init__(self):
        self.experiments = {
            "state_machine": {
                "enabled": True,
                "percentage": 50,  # 50% пользователей
                "metrics": {
                    "control": [],
                    "treatment": []
                }
            }
        }
    
    def should_use_state_machine(self, user_id: str) -> bool:
        """Определяем попадает ли пользователь в тестовую группу"""
        
        # Детерминированное распределение по user_id
        hash_value = hash(user_id) % 100
        
        experiment = self.experiments["state_machine"]
        if not experiment["enabled"]:
            return False
        
        return hash_value < experiment["percentage"]
    
    def track_conversion(self, user_id: str, converted: bool):
        """Трекаем конверсию"""
        
        group = "treatment" if self.should_use_state_machine(user_id) else "control"
        
        self.experiments["state_machine"]["metrics"][group].append({
            "user_id": user_id,
            "converted": converted
        })
    
    def get_results(self) -> Dict:
        """Получаем результаты A/B теста"""
        
        metrics = self.experiments["state_machine"]["metrics"]
        
        control_conversions = sum(1 for m in metrics["control"] if m["converted"])
        treatment_conversions = sum(1 for m in metrics["treatment"] if m["converted"])
        
        control_total = len(metrics["control"])
        treatment_total = len(metrics["treatment"])
        
        if control_total == 0 or treatment_total == 0:
            return {"status": "insufficient_data"}
        
        control_rate = control_conversions / control_total
        treatment_rate = treatment_conversions / treatment_total
        
        lift = ((treatment_rate - control_rate) / control_rate) * 100 if control_rate > 0 else 0
        
        return {
            "control": {
                "total": control_total,
                "conversions": control_conversions,
                "rate": f"{control_rate*100:.1f}%"
            },
            "treatment": {
                "total": treatment_total,
                "conversions": treatment_conversions,
                "rate": f"{treatment_rate*100:.1f}%"
            },
            "lift": f"{lift:+.1f}%",
            "significant": abs(lift) > 10  # Упрощенная проверка
        }
```

## 📊 Метрики успеха

### KPI для измерения эффективности:

1. **Latency метрики:**
   - Real latency: ≤ 5.5 секунд (сейчас 6)
   - Perceived latency: ≤ 3 секунды (streaming)
   - Cache hit rate: ≥ 30%

2. **Качество определения состояний:**
   - Accuracy сигналов: ≥ 85%
   - False positive для ready_to_buy: < 10%

3. **Бизнес метрики:**
   - Click rate на предложения: ≥ 15%
   - Conversion lift: ≥ 20%
   - User satisfaction: без деградации

4. **Технические метрики:**
   - Размер промптов: < 2500 токенов
   - Дополнительные расходы: < 5% от текущих

## 🚀 Запуск и мониторинг

### Команды для запуска:

```bash
# Запуск с машиной состояний
ENABLE_STATE_MACHINE=true python src/main.py

# Запуск с A/B тестированием
ENABLE_AB_TEST=true AB_TEST_PERCENTAGE=50 python src/main.py

# Запуск с метриками
ENABLE_METRICS=true METRICS_FILE=./metrics.json python src/main.py
```

### Мониторинг в реальном времени:

```python
# Endpoint для метрик
@app.get("/metrics")
async def get_metrics():
    return {
        "cache_stats": cache.get_stats(),
        "ab_test_results": ab_manager.get_results(),
        "performance": metrics_collector.get_stats()
    }
```

## ✅ Чек-лист готовности к production

- [ ] Router определяет user_signal корректно (тесты пройдены)
- [ ] Dynamic few-shot примеры добавляются в промпт
- [ ] Streaming работает и снижает perceived latency
- [ ] Cache patterns покрывают 30% частых запросов
- [ ] Connection pooling настроен
- [ ] Метрики собираются
- [ ] A/B тест настроен на 50/50
- [ ] Fallback на стандартное поведение работает
- [ ] Документация обновлена
- [ ] Load testing пройден (100 req/min)

## 🔄 Rollback план

В случае проблем:

1. **Быстрый откат (1 минута):**
   ```bash
   ENABLE_STATE_MACHINE=false python src/main.py
   ```

2. **Частичный откат:**
   - Отключить только offers: `ENABLE_OFFERS=false`
   - Отключить только dynamic few-shot: `ENABLE_DYNAMIC_EXAMPLES=false`
   - Уменьшить % в A/B тесте: `AB_TEST_PERCENTAGE=10`

3. **Полный откат:**
   ```bash
   git checkout main
   python src/main.py
   ```

## 📈 План масштабирования

### Фаза 1 (текущая): MVP
- 4 базовых сигнала
- 4 типа предложений
- In-memory cache

### Фаза 2 (через месяц): Расширение
- 8-10 сигналов
- Персонализированные предложения
- Redis cache
- ML-based signal detection

### Фаза 3 (через квартал): Full State Machine
- Intent + Emotion + Depth модель
- 20+ типов предложений
- Predictive offers
- Edge computing для анализа

---
*План подготовлен: 17.08.2025*
*Версия: 1.0*
*Время реализации: 2 дня*
*Автор: AI Assistant для Ukido*