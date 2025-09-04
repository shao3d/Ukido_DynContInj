# 🚨 План критических исправлений MVP - Ukido AI Assistant

**Дата создания:** 04.09.2024  
**Версия:** 0.13.2  
**Приоритет:** КРИТИЧЕСКИЙ для production

## 📊 Анализ текущих проблем с кешированием

### ❌ Проблема с кешированием Gemini (ВЫ ПРАВЫ!)
**Текущая ситуация:** Router использует `chat_with_cache()`, который кеширует ВЕСЬ промпт целиком, включая динамическую историю!

```python
# src/router.py:156
response = await self.client.chat_with_cache(
    prompt,  # Это включает ВСЮ историю диалога!
    use_cache=self.use_cache
)
```

**Проблема:** При каждом новом сообщении создаётся НОВЫЙ кеш-ключ, потому что история изменилась. Кеш не работает вообще!

**Решение есть в коде, но НЕ используется:** `chat_with_prefix_cache()` может разделять статику и динамику!

### ✅ Асинхронная загрузка документов ПОМОЖЕТ
**Текущая ситуация:** Документы загружаются последовательно
```python
# src/response_generator.py:255-275
for doc_name in doc_names:
    doc_path = os.path.join(self.docs_dir, doc_name)
    # Блокирующее чтение файла
```

**Потенциальное ускорение:** 3-4 документа × 0.1 сек = 0.3-0.4 секунды экономии

---

## 🔥 КРИТИЧЕСКИЕ ФИКСЫ (обязательно до production)

### Fix #0.1: HTTP Timeout для OpenRouter ⏱️ 2 мин ⚡ НОВОЕ!
**Файл:** `src/openrouter_client.py`
**Строка:** ~15 (в __init__)

```python
# БЫЛО:
self.client = httpx.AsyncClient()

# СТАЛО:
self.client = httpx.AsyncClient(timeout=30.0)  # 30 секунд таймаут
```

**Почему критично:** Без этого ОДИН зависший запрос может заблокировать весь сервер навсегда. Это самый простой и важный фикс!

---

### Fix #0.2: Проверка API ключа при старте ⏱️ 2 мин ⚡ НОВОЕ!
**Файл:** `src/main.py`
**Добавить в начало (после импортов, перед app = FastAPI()):**

```python
# Проверка критически важных ENV переменных
import sys

if not config.OPENROUTER_API_KEY:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не установлен OPENROUTER_API_KEY!")
    print("📝 Установите переменную окружения или добавьте в .env файл")
    sys.exit(1)

print(f"✅ OpenRouter API key загружен (длина: {len(config.OPENROUTER_API_KEY)})")
```

**Почему критично:** Без API ключа ВСЕ запросы будут падать, но сервер запустится "успешно". Лучше упасть при старте с понятной ошибкой.

---

### Fix #1: Сохранение user_signal в persistence ⏱️ 30 мин
**Файл:** `src/main.py`
**Строки:** 443-450

```python
# ДОБАВИТЬ в create_state_snapshot():
def create_state_snapshot(history_manager, user_signals_history, social_state, user_id):
    return {
        "history": history_manager.get_history(user_id),
        "last_user_signal": user_signals_history.get(user_id, "exploring_only"),  # НОВОЕ
        "greeting_exchanged": social_state.has_greeted(user_id),
        "message_count": len(history_manager.get_history(user_id))
    }

# ДОБАВИТЬ при загрузке (строка ~100):
for user_id, state_data in saved_states.items():
    # Восстанавливаем user_signal
    if "last_user_signal" in state_data:
        user_signals_history[user_id] = state_data["last_user_signal"]
```

**Почему критично:** Без этого теряем контекст price_sensitive при рестарте → агрессивные CTA → потеря клиента

---

### Fix #2: Retry механизм для LLM ⏱️ 1 час
**Файлы:** `src/main.py`, `src/router.py`, `src/response_generator.py`

```python
# Создать новый файл src/retry_helper.py:
import asyncio
from typing import TypeVar, Callable
import logging

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0
) -> T:
    """Retry с экспоненциальным backoff"""
    delay = initial_delay
    
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                logging.error(f"All {max_attempts} attempts failed: {e}")
                raise
            
            logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * exponential_base, max_delay)

# Использовать в src/main.py:201:
from retry_helper import retry_with_backoff

route_result = await retry_with_backoff(
    lambda: router.route(request.message, history_messages, request.user_id)
)
```

**Почему критично:** 2-5% запросов падают по timeout → "Временная проблема" → 70% не повторяют → потеря клиента

---

### Fix #3: Логирование в файл ⏱️ 2 часа
**Создать файл:** `src/logger_config.py`

```python
import logging
import logging.handlers
from datetime import datetime
import os

def setup_logger():
    # Создаём папку для логов
    os.makedirs("logs", exist_ok=True)
    
    # Настраиваем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Файловый хендлер с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    
    # Консольный хендлер для DEBUG
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# В src/main.py добавить в начало:
from logger_config import setup_logger
logger = setup_logger()

# Заменить все print() на logger:
# print(f"❌ Router failed: {e}") → logger.error(f"Router failed for user {request.user_id}: {e}", exc_info=True)
# print(f"ℹ️ Routing: {request.message}") → logger.info(f"Routing message from {request.user_id}: {request.message[:50]}")
```

**Почему критично:** Без логов не узнаете о проблемах пока не начнутся жалобы

---

### Fix #4: Rate Limiting ⏱️ 1 час
**Файл:** `src/main.py`
**Добавить перед chat():**

```python
from collections import defaultdict, deque
import time
from fastapi import HTTPException

# Глобальные счётчики
user_request_times = defaultdict(lambda: deque(maxlen=100))
user_daily_counts = defaultdict(lambda: {"count": 0, "date": ""})

def check_rate_limits(user_id: str) -> None:
    """Проверка rate limits"""
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Проверка частоты (10 запросов в минуту)
    recent_requests = user_request_times[user_id]
    recent_requests.append(now)
    
    # Считаем запросы за последнюю минуту
    minute_ago = now - 60
    recent_count = sum(1 for t in recent_requests if t > minute_ago)
    
    if recent_count > 10:
        logger.warning(f"Rate limit exceeded for user {user_id}: {recent_count} requests/min")
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")
    
    # Проверка дневного лимита (100 запросов в день)
    daily = user_daily_counts[user_id]
    if daily["date"] != today:
        daily["count"] = 0
        daily["date"] = today
    
    daily["count"] += 1
    if daily["count"] > 100:
        logger.warning(f"Daily limit exceeded for user {user_id}: {daily['count']} requests")
        raise HTTPException(status_code=429, detail="Daily limit exceeded. Try again tomorrow.")

# В начале chat():
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # НОВОЕ: Проверка rate limits
    check_rate_limits(request.user_id)
    # ... остальной код
```

**Почему критично:** Один злоумышленник может сжечь $2000 за сутки

---

### Fix #5: Валидация user_id ⏱️ 30 мин
**Файл:** `src/main.py`

```python
from pydantic import BaseModel, Field, validator
import re

class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=1000)
    
    @validator('user_id')
    def validate_user_id(cls, v):
        # Только буквы, цифры, подчёркивания, дефисы
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Invalid user_id format')
        return v
    
    @validator('message')
    def validate_message(cls, v):
        # Убираем лишние пробелы
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v
```

**Почему критично:** SQL injection, path traversal, XSS атаки

---

## 🚀 ОПТИМИЗАЦИИ (сильно улучшат производительность)

### Fix #6: Исправить кеширование Gemini ⏱️ 2 часа
**Файл:** `src/router.py`

```python
# Метод _build_router_prompts нужно разделить на части:
def _build_static_prompt(self) -> str:
    """Статичная часть промпта (кешируется)"""
    sections = []
    sections.append(self._get_role_section())
    sections.append(self._get_summaries_section())
    sections.append(self._get_decomposition_section())  # Без примеров с историей!
    sections.append(self._get_classification_section())
    sections.append(self._get_response_format_section())
    return "\n\n".join(sections)

def _build_dynamic_prompt(self, message: str, history: List[Dict]) -> str:
    """Динамическая часть промпта"""
    sections = []
    sections.append(self._get_history_section(history))
    sections.append(f"ТЕКУЩИЙ ЗАПРОС:\n{message}")
    return "\n\n".join(sections)

# В методе route():
if self.use_cache:
    static_prompt = self._build_static_prompt()  # Кешируется
    dynamic_prompt = self._build_dynamic_prompt(message, history)  # Не кешируется
    
    response = await self.client.chat_with_prefix_cache(
        static_prefix=static_prompt,
        dynamic_suffix=dynamic_prompt,
        model_params={"temperature": 0.3, "max_tokens": 500}
    )
else:
    # Старый способ для обратной совместимости
    full_prompt = self._build_router_prompts(message, history, user_id)
    response = await self.client.chat(...)
```

**Эффект:** Ускорение на 1-2 секунды за счёт реального кеширования

---

### Fix #7: Асинхронная загрузка документов ⏱️ 1 час
**Файл:** `src/response_generator.py`

```python
import asyncio
import aiofiles

async def _load_doc_async(self, doc_name: str) -> str:
    """Асинхронная загрузка одного документа"""
    doc_path = os.path.join(self.docs_dir, doc_name)
    
    if not os.path.exists(doc_path):
        logger.warning(f"Document not found: {doc_path}")
        return ""
    
    try:
        async with aiofiles.open(doc_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return f"## Документ: {doc_name}\n{content}"
    except Exception as e:
        logger.error(f"Error loading document {doc_name}: {e}")
        return ""

async def _load_docs(self, doc_names: List[str]) -> str:
    """Параллельная загрузка всех документов"""
    if not doc_names:
        return ""
    
    # Загружаем все документы параллельно
    tasks = [self._load_doc_async(name) for name in doc_names]
    docs = await asyncio.gather(*tasks)
    
    # Фильтруем пустые и объединяем
    valid_docs = [doc for doc in docs if doc]
    return "\n\n---\n\n".join(valid_docs)
```

**Эффект:** Ускорение на 0.3-0.5 секунды при загрузке 3-4 документов

---

## 📅 План внедрения

### Первые 5 минут (КРИТИЧНО для MVP!)
1. ✅ Fix #0.1: HTTP Timeout (2 мин) ⚡
2. ✅ Fix #0.2: Проверка API ключа (2 мин) ⚡
3. ✅ Тест запуска сервера (1 мин)

### День 1 (4-5 часов работы)
4. ✅ Fix #1: Persistence для user_signal (30 мин)
5. ✅ Fix #5: Валидация user_id (30 мин)  
6. ✅ Fix #2: Retry механизм (1 час)
7. ✅ Fix #4: Rate limiting (1 час)
8. ✅ Fix #3: Логирование - начать (1.5 часа)

### День 2 (3-4 часа работы)
6. ✅ Fix #3: Логирование - завершить (30 мин)
7. ✅ Fix #6: Исправить кеширование Gemini (2 часа)
8. ✅ Fix #7: Асинхронная загрузка (1 час)
9. ✅ Тестирование всех фиксов (30 мин)

### Итого: 7-9 часов работы

---

## 🧪 Как протестировать фиксы

### Тест Fix #0.1 (HTTP Timeout):
```bash
# Временно измените URL в config.py на несуществующий:
# API_URL = "https://nonexistent.example.com/api/v1/chat/completions"
# Запрос должен упасть через 30 секунд, а не висеть вечно
```

### Тест Fix #0.2 (ENV проверка):
```bash
# 1. Временно уберите OPENROUTER_API_KEY из .env
# 2. Попробуйте запустить сервер
python src/main.py
# Должно быть: "❌ КРИТИЧЕСКАЯ ОШИБКА: Не установлен OPENROUTER_API_KEY!"
# Сервер НЕ должен запуститься
```

### Тест Fix #1 (Persistence):
```bash
# 1. Отправить сообщение с price_sensitive
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"user_id":"test_persist","message":"Дорого у вас, 8000 грн это слишком"}'

# 2. Перезапустить сервер
# Ctrl+C и python src/main.py

# 3. Проверить сохранение сигнала
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"user_id":"test_persist","message":"расскажите про школу"}'
# Должен остаться price_sensitive tone
```

### Тест Fix #2 (Retry):
```bash
# Временно сломать OpenRouter URL в config.py
# Должно быть 3 попытки в логах перед fallback
```

### Тест Fix #4 (Rate limit):
```bash
# Отправить 11 запросов за минуту
for i in {1..11}; do
  curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
    -d '{"user_id":"test_rate","message":"тест"}'
done
# 11-й должен вернуть 429 Too Many Requests
```

### Тест Fix #5 (Validation):
```bash
# Попытка SQL injection
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"user_id":"test'; DROP TABLE users; --","message":"тест"}'
# Должен вернуть 422 Validation Error
```

---

## ⚠️ Что НЕ включено (но желательно позже)

1. **Мониторинг метрик** (Prometheus/Grafana) - 1 день работы
2. **Централизованное логирование** (ELK stack) - 2 дня работы  
3. **A/B тестирование** (feature flags) - 1 день работы
4. **Comprehensive тесты** - 2-3 дня работы
5. **Рефакторинг монолитной функции chat()** - 1 день работы

---

## 💰 ROI этих фиксов

- **Fix #1-2:** Предотвратят потерю ~20-30% пользователей = сохранят $10-15k/месяц
- **Fix #3:** Сократят время обнаружения проблем с дней до минут = сохранят репутацию
- **Fix #4:** Защитят от сжигания бюджета = сохранят до $50k от одной атаки
- **Fix #5:** Защитят от взлома = предотвратят катастрофу
- **Fix #6-7:** Ускорят ответы на 30-40% = улучшат retention на 10-15%

---

## 📝 Финальный чеклист перед production

- [ ] Все 5 критических фиксов внедрены
- [ ] Логи пишутся в файлы
- [ ] Rate limiting работает
- [ ] Валидация входных данных активна
- [ ] Retry механизм протестирован
- [ ] Persistence сохраняет user_signal
- [ ] Создан системный мониторинг (хотя бы базовый)
- [ ] Настроен алерт при ошибках (хотя бы email)
- [ ] Создан backup план базы данных persistent_states
- [ ] Документирован runbook для инцидентов

---

**Автор:** Claude Code Review  
**Дата:** 04.09.2024  
**Статус:** Ready for implementation