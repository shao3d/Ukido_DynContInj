# 📋 План реализации HTTP API песочницы

## 📌 Цель
Создать универсальную песочницу для тестирования Ukido AI Assistant через HTTP API на основе существующей `sandbox_v2.py`, которая обеспечит полный функционал системы (включая юмор Жванецкого) без дублирования кода.

## 🎯 Основные требования

### 1. Функциональные требования
- ✅ Работа с реальным запущенным сервером через HTTP API
- ✅ Поддержка всех функций системы (включая юмор, метрики, историю)
- ✅ Интерактивный и пакетный режимы тестирования
- ✅ Визуализация результатов с цветным выводом
- ✅ Сохранение и анализ результатов тестирования

### 2. Нефункциональные требования
- Простота использования (аналогично sandbox_v2.py)
- Читаемый и информативный вывод
- Минимальные зависимости
- Совместимость с существующими тестовыми данными

## 🏗️ Архитектура

### Имя файла: `http_sandbox.py`

### Основные компоненты (на основе `sandbox_v2.py`):

```python
# Переиспользуем структуры из sandbox_v2.py
@dataclass
class ProcessingResult:
    """Результат обработки (как в sandbox_v2.py)"""
    user_message: str
    response: str
    router_status: str  # intent из HTTP response
    social_context: Optional[str]
    documents: List[str]
    questions: List[str]  # decomposed_questions
    router_time: float
    generator_time: float  # latency из сервера
    total_time: float
    source: str  # "http_api"
    user_signal: Optional[str]
    # Новые поля для HTTP версии:
    is_humor: bool = False
    raw_response: dict = None

@dataclass
class ValidationResult:
    """Результат проверки (как в sandbox_v2.py)"""
    passed: List[str]
    failed: List[str]
    
    @property
    def is_valid(self) -> bool:
        return len(self.failed) == 0

class HTTPSandbox:
    """Главный класс песочницы (аналог SandboxV2)"""
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = httpx.AsyncClient()
        # НЕ создаём Router/ResponseGenerator - используем HTTP API
        
    async def process_message(self, message: str, user_id: str = "test_user", 
                             show_details: bool = True) -> ProcessingResult:
        """Аналог process_message из SandboxV2, но через HTTP"""
        
    def validate_result(self, result: ProcessingResult) -> ValidationResult:
        """Копируем логику валидации из SandboxV2"""
        
    def show_result(self, result: ProcessingResult, 
                   validation: Optional[ValidationResult] = None):
        """Адаптируем show_result из SandboxV2 с детекцией юмора"""
        
    async def get_metrics(self) -> dict:
        """Новый метод для получения метрик"""
```

## 📦 Режимы работы (как в sandbox_v2.py)

### 1. Интерактивный режим (interactive_mode)
```bash
python http_sandbox.py
```
- Полностью копируем функционал из sandbox_v2.py
- Те же команды: `/quit`, `/clear`, `/user <id>`, `/validate`, `/details`
- ДОБАВЛЯЕМ: `/metrics` - показать метрики сервера
- ДОБАВЛЯЕМ: `/health` - проверить здоровье сервера
- Цветной вывод через класс Colors из sandbox_v2.py

### 2. Одиночное сообщение (single_message_mode)
```bash
python http_sandbox.py -m "Расскажите о курсах" [user_id]
```
- Копируем логику из sandbox_v2.py
- Те же параметры командной строки
- Возвращаем exit code: 0 если валидация прошла

### 3. Пакетное тестирование (run_test_scenarios)
```bash
python http_sandbox.py --test [scenarios.json]
```
- Копируем функцию run_test_scenarios из sandbox_v2.py
- По умолчанию используем тот же test_scenarios в коде
- Возможность загрузки из внешнего JSON

### 4. Режим мониторинга (НОВЫЙ)
```bash
python http_sandbox.py --monitor
```
- Периодически запрашивает /metrics
- Отображает динамику в реальном времени
- Подсвечивает изменения

## 🎨 Визуализация

### Используем класс Colors из sandbox_v2.py:
```python
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    # ДОБАВЛЯЕМ для юмора:
    PURPLE = '\033[95m'  # Для юмора Жванецкого
```

### Адаптация show_result из sandbox_v2.py:
- Сохраняем существующий формат вывода
- ДОБАВЛЯЕМ детекцию юмора (если в тексте есть паттерны юмора)
- ДОБАВЛЯЕМ подсветку юмора фиолетовым цветом
- ДОБАВЛЯЕМ отображение is_humor флага

### Детекция юмора:
```python
def detect_humor(text: str) -> bool:
    """Определяет, содержит ли текст юмор Жванецкого"""
    humor_patterns = [
        "У нас", "Мы забиваем", "Что важнее",
        "развиваем", "превращаем", "учим"
    ]
    return any(pattern in text for pattern in humor_patterns)
```

### Визуальные индикаторы юмора:
- 🎭 Эмодзи в начале строки с юмором
- Фиолетовый цвет текста (Colors.PURPLE)
- Дополнительная строка: `[🎭 Юмор Жванецкого сработал!]`

## 📊 Интеграция с тестовыми данными

### Поддерживаемые форматы:
1. **test_comprehensive_dialogues.json** - 15 сценариев диалогов
2. **test_scenarios.json** - простые тест-кейсы
3. **Custom JSON** - произвольный формат

### Структура тестового сценария:
```json
{
  "id": "scenario_1",
  "name": "Мама в маршрутке",
  "messages": [
    {
      "user_id": "mom_1",
      "message": "Дорого. Скок стоит?",
      "expected": {
        "intent": "success",
        "signal": "price_sensitive",
        "has_discount": true
      }
    }
  ]
}
```

## 🔧 Дополнительные функции

### 1. Сравнение ответов
- До/после изменений
- С юмором / без юмора
- Разные user_signals

### 2. Стресс-тестирование
```bash
python http_sandbox.py --stress --users 10 --messages 100
```
- Параллельные запросы
- Измерение производительности
- Проверка лимитов

### 3. Экспорт результатов
- JSON для программной обработки
- Markdown для документации
- CSV для анализа в Excel

### 4. Проверка здоровья системы
```bash
python http_sandbox.py --health
```
- Статус сервера
- Конфигурация
- Доступность API

## 📝 Команды в интерактивном режиме

### Базовые (из sandbox_v2.py):
- `/quit` или `/exit` - выход
- `/clear` - очистить историю
- `/user <id>` - сменить user_id
- `/validate` - включить/выключить валидацию
- `/details` - показать/скрыть детали

### Новые команды:
- `/help` - список всех команд
- `/metrics` - показать метрики сервера
- `/health` - проверить здоровье сервера
- `/save_failed` - показать сохранённые проблемные кейсы
- `/humor stats` - статистика юмора за сессию

## 🔌 Интеграция с CI/CD

### GitHub Actions совместимость:
```yaml
- name: Run API tests
  run: |
    python src/main.py &
    sleep 5
    python http_sandbox.py --test tests/scenarios.json --report
```

## 📈 Метрики и отчёты

### Собираемые метрики:
- Общее количество запросов
- Распределение по intent/signal
- Частота юмора
- Среднее время ответа
- Успешность генерации

### Формат отчёта:
```markdown
# Test Report - 2025-08-23

## Summary
- Total tests: 15
- Passed: 14 (93%)
- Failed: 1 (7%)

## Humor Statistics
- Generated: 4/12 offtopic (33%)
- Success rate: 80%
- Avg time: 1.6s

## Details
...
```

## ⚠️ Обработка ошибок

### Graceful degradation:
- Сервер недоступен → предложение запустить
- Timeout → повтор с увеличенным лимитом
- Invalid JSON → показ raw ответа
- Network error → retry с backoff

## 🚀 Последовательность реализации

### Этап 1: Копирование базы из sandbox_v2.py (30 мин)
1. Создать файл `http_sandbox.py`
2. Скопировать из sandbox_v2.py:
   - Класс Colors (добавить PURPLE для юмора)
   - Dataclass ProcessingResult (адаптировать)
   - Dataclass ValidationResult (без изменений)
   - Структуру main() функции
3. Заменить импорты Router/ResponseGenerator на httpx
4. **ДОБАВИТЬ**: Автодетекция сервера при запуске

### Этап 2: Адаптация process_message (1ч)
1. Заменить вызов router.route() на HTTP POST /chat
2. Парсинг JSON ответа в ProcessingResult
3. Измерение времени ответа
4. Детекция юмора в ответе

### Этап 3: Копирование режимов работы (1ч)
1. Скопировать interactive_mode() с адаптацией
2. Скопировать single_message_mode() с адаптацией
3. Скопировать run_test_scenarios() с адаптацией
   - **ДОБАВИТЬ**: Прогресс-бар для batch тестов
4. Добавить новые команды (/metrics, /health, /save_failed)

### Этап 4: Адаптация валидации и вывода (30 мин)
1. Скопировать validate_result() с небольшими изменениями
   - **ДОБАВИТЬ**: Автосохранение failed кейсов в failed_cases.json
2. Адаптировать show_result() для подсветки юмора
   - **ДОБАВИТЬ**: Эмодзи 🎭 для визуального выделения
3. Добавить detect_humor() функцию

### Этап 5: Новый функционал (1.5ч)
1. **Автодетекция сервера**:
   - Проверка доступности при запуске
   - Helpful сообщения если сервер не запущен
   - Предложение команды для запуска
2. Добавить get_metrics() метод
3. Реализовать monitor_mode() для --monitor
4. **Прогресс-бар для batch тестов**:
   - Показывать `[=====>    ] 5/10 (50%)`
   - Обновлять после каждого теста
5. **Сохранение проблемных кейсов**:
   - Автоматически в failed_cases.json
   - С timestamp и причиной ошибки

### Этап 6: Тестирование и полировка (30 мин)
1. Протестировать все режимы работы
2. Проверить детекцию юмора
3. Убедиться в совместимости с test_comprehensive_dialogues.json
4. Написать краткую документацию в начале файла

## 📚 Зависимости

### Обязательные:
- `httpx` - асинхронный HTTP клиент (уже в requirements.txt)
- Встроенные: `asyncio`, `json`, `time`, `sys`, `dataclasses`

### НЕ нужны (используем встроенные ANSI коды):
- ~~colorama~~ - используем класс Colors из sandbox_v2.py
- ~~rich~~ - избыточно для нашей задачи

### Важно:
- HTTP песочница НЕ импортирует модули из src/
- Работает только через HTTP API
- Это гарантирует полный функционал включая юмор

## ✅ Критерии готовности

1. Все режимы работы функционируют
2. Юмор корректно определяется и подсвечивается
3. Метрики собираются и отображаются
4. Тесты из `test_comprehensive_dialogues.json` проходят
5. Документация написана
6. Код покрыт комментариями

## 🎯 Ожидаемый результат

Универсальный инструмент для тестирования Ukido AI Assistant, который:
- Заменяет старую песочницу для полноценного тестирования
- Работает с реальным production функционалом
- Удобен для использования в Claude Code
- Подходит для CI/CD pipeline
- Предоставляет богатую визуализацию и аналитику

## 🔑 Ключевые отличия от sandbox_v2.py

1. **Источник данных**:
   - sandbox_v2.py: Прямые вызовы Router и ResponseGenerator
   - http_sandbox.py: HTTP API вызовы к серверу

2. **Полнота функционала**:
   - sandbox_v2.py: НЕТ системы юмора (не инициализирована)
   - http_sandbox.py: ЕСТЬ весь функционал включая юмор

3. **Новые возможности**:
   - Просмотр метрик сервера (/metrics)
   - Мониторинг в реальном времени (--monitor)
   - Детекция и подсветка юмора

4. **Совместимость**:
   - Те же режимы работы и команды
   - Тот же формат вывода
   - Те же цвета и стиль

---

## 📋 Примеры кода для ключевых функций

### Автодетекция сервера:
```python
async def check_server_health(base_url: str) -> bool:
    """Проверяет доступность сервера при запуске"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health", timeout=2.0)
            return response.status_code == 200
    except:
        return False

# При запуске:
if not await check_server_health(base_url):
    print(f"{Colors.RED}❌ Сервер не доступен на {base_url}{Colors.ENDC}")
    print(f"{Colors.YELLOW}💡 Запустите сервер командой:{Colors.ENDC}")
    print(f"   python src/main.py")
    print(f"\n{Colors.DIM}Или используйте --start-server для автозапуска{Colors.ENDC}")
    sys.exit(1)
```

### Прогресс-бар:
```python
def show_progress(current: int, total: int, width: int = 40):
    """Показывает прогресс-бар в консоли"""
    percent = current / total
    filled = int(width * percent)
    bar = '=' * filled + '>' + ' ' * (width - filled - 1)
    print(f"\r[{bar}] {current}/{total} ({percent*100:.0f}%)", end='', flush=True)
```

### Автосохранение failed кейсов:
```python
def save_failed_case(result: ProcessingResult, validation: ValidationResult):
    """Сохраняет проблемный кейс для анализа"""
    failed_case = {
        "timestamp": datetime.now().isoformat(),
        "message": result.user_message,
        "response": result.response,
        "failed_checks": validation.failed,
        "user_signal": result.user_signal,
        "is_humor": result.is_humor
    }
    
    # Дозапись в файл
    with open("failed_cases.json", "a") as f:
        json.dump(failed_case, f)
        f.write("\n")
```

---

**Время реализации**: ~4.5 часа (с учётом новых функций)
**Приоритет**: Высокий
**Автор плана**: Claude Code
**Дата**: 23.08.2025 (обновлено)