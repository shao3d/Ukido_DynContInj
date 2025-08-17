# Design: Dynamic Context Injection для Ukido Bot

## 1. Общая архитектура

### 1.1 Высокоуровневая архитектура
```
[Pipedream] → [FastAPI Server] → [OpenRouter API]
                    ↓
            [Document Manager]
            [Router (LLM-based)]
            [Response Generator]
```

### 1.2 Поток обработки запроса
1. FastAPI получает POST запрос от Pipedream
2. Валидация входных данных
3. Router анализирует запрос и выбирает релевантные документы
4. Response Generator формирует промпт с выбранными документами
5. Отправка промпта в OpenRouter API (google/gemini-2.5-flash)
6. Возврат структурированного ответа Pipedream

## 2. Технические решения

### 2.1 Хранение документов
**Решение**: In-memory хранилище

**Обоснование**:
- 13 документов ~200KB - оптимально для хранения в памяти
- Мгновенный доступ (микросекунды vs миллисекунды для диска)
- Это production подход для небольших данных
- Обновление через перезапуск сервера

**Реализация**:
```python
class DocumentManager:
    def __init__(self):
        self.documents = {}  # {"filename": "content"}
        self.summaries = {}  # {"filename": {...summary data...}}
        self._load_all_documents()
```

### 2.2 Формат саммари документов
**Решение**: Структурированный JSON с метаданными

**Структура саммари** (будет заполнена после анализа документов):
```json
{
  "document_id": "courses_detailed.md",
  "metadata": {
    "title": "Название документа",
    "category": "courses|pricing|methodology|team|etc",
    "summary": "Краткое описание содержимого для LLM",
    "key_topics": ["список", "ключевых", "тем"],
    "typical_questions": [
      "Примеры вопросов, на которые отвечает документ"
    ],
    "priority": 1  // 1-высокий, 2-средний, 3-низкий
  }
}
```

**Обоснование**:
- Структурированный формат позволяет LLM лучше понимать контент
- key_topics помогают в быстром поиске
- typical_questions дают примеры для matching

### 2.3 Router - выбор релевантных документов
**Решение**: LLM-based роутер с google/gemini-2.5-flash

**Алгоритм работы**:
1. Формируем промпт с вопросом пользователя и всеми саммари
2. LLM анализирует и возвращает 1-2 наиболее релевантных документа
3. Добавляем confidence score для оценки уверенности

**Промпт для роутера** (концепция):
```
Ты - роутер для выбора релевантных документов школы Ukido.
Вопрос пользователя: {question}

Доступные документы:
{summaries}

Выбери 1-2 наиболее релевантных документа для ответа на вопрос.
Верни JSON: {"documents": ["file1.md", "file2.md"], "confidence": 0.95}
```

### 2.4 Response Generator
**Решение**: Промпт с контекстом выбранных документов

**Структура промпта**:
1. Системный промпт с tone of voice школы
2. Контекст из выбранных документов
3. Вопрос пользователя
4. Инструкции по формату ответа

## 3. Структура классов (ООП подход)

### 3.1 DocumentManager
```python
class DocumentManager:
    """Управляет загрузкой и хранением документов"""
    
    def __init__(self, docs_path: str):
        self.docs_path = docs_path
        self.documents = {}
        self.summaries = {}
    
    def load_all_documents(self) -> None:
        """Загружает все .md файлы из папки"""
    
    def get_document(self, filename: str) -> str:
        """Возвращает содержимое документа"""
    
    def get_summaries(self) -> dict:
        """Возвращает все саммари для роутера"""
```

### 3.2 Router
```python
class Router:
    """LLM-based роутер для выбора документов"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "google/gemini-2.5-flash"
    
    async def select_documents(self, query: str, summaries: dict) -> dict:
        """Выбирает 1-2 релевантных документа"""
        # Returns: {"documents": [...], "confidence": float}
```

### 3.3 ResponseGenerator
```python
class ResponseGenerator:
    """Генерирует ответы с использованием контекста"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "google/gemini-2.5-flash"
    
    async def generate_response(self, query: str, context: str) -> str:
        """Генерирует ответ на основе контекста"""
```

### 3.4 UkidoBot - главный класс
```python
class UkidoBot:
    """Главный класс, объединяющий всю логику"""
    
    def __init__(self, docs_path: str, api_key: str):
        self.doc_manager = DocumentManager(docs_path)
        self.router = Router(api_key)
        self.generator = ResponseGenerator(api_key)
    
    async def process_message(self, user_message: dict) -> dict:
        """Обрабатывает сообщение пользователя"""
```

## 4. API Endpoints

### 4.1 Основной endpoint
```python
POST /chat
- Принимает запрос от Pipedream
- Валидирует данные
- Вызывает UkidoBot.process_message()
- Возвращает структурированный ответ
```

### 4.2 Служебные endpoints
```python
GET /health
- Проверка состояния сервиса
```

## 5. Обработка ошибок

### 5.1 Уровни обработки
1. **Валидация входных данных** - Pydantic модели
2. **API ошибки** - Retry с exponential backoff
3. **Бизнес-логика** - Fallback ответы
4. **Системные ошибки** - Graceful degradation

### 5.2 Fallback стратегия
При недоступности OpenRouter:
```python
FALLBACK_RESPONSE = """
Извините, я временно не могу обработать ваш запрос. 
Пожалуйста, посетите наш сайт ukido.com.ua или напишите на info@ukido.com.ua

Наши основные курсы:
- Юный Оратор (7-10 лет)
- Эмоциональный Компас (9-12 лет)  
- Капитан Проектов (11-14 лет)
"""
```

## 6. Структура проекта

```
Ukido_DynContInj/
├── docs/
│   ├── requirements.md
│   ├── design.md
│   └── progress.md
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic модели
│   ├── document_manager.py  # Класс DocumentManager
│   ├── router.py            # Класс Router
│   ├── generator.py         # Класс ResponseGenerator
│   ├── bot.py               # Класс UkidoBot
│   └── config.py            # Конфигурация
├── data/
│   ├── documents/           # 13 .md файлов школы
│   └── summaries.json       # Саммари документов
├── tests/
│   └── test_*.py
├── requirements.txt
├── .env
└── README.md
```

## 7. Конфигурация и переменные окружения

### 7.1 .env файл
```
OPENROUTER_API_KEY=your_api_key
DOCS_PATH=./data/documents
PORT=8000
LOG_LEVEL=INFO
```

### 7.2 config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    docs_path: str = "./data/documents"
    port: int = 8000
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
```

## 8. План реализации

### Этап 1: Базовая структура
1. Создать структуру проекта
2. Настроить FastAPI приложение
3. Реализовать DocumentManager
4. Создать саммари документов

### Этап 2: Роутер
1. Реализовать Router класс
2. Интегрировать OpenRouter API
3. Протестировать выбор документов

### Этап 3: Генерация ответов
1. Реализовать ResponseGenerator
2. Создать UkidoBot класс
3. Настроить обработку ошибок

### Этап 4: Тестирование и оптимизация
1. Написать тесты
2. Оптимизировать промпты
3. Подготовить к деплою

## 9. Метрики и мониторинг

### 9.1 Что измеряем
- Latency каждого компонента
- Accuracy выбора документов
- Token usage
- Error rate

### 9.2 Логирование
```python
import logging

logger = logging.getLogger("ukido_bot")
# Структурированное логирование для каждого этапа
```

---

*Документ версии 1.0*  
*Дата создания: 2024-08-05*