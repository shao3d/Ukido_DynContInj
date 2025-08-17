# Команды для разработки Ukido AI Assistant

## Запуск и тестирование

### Запуск сервера
```bash
python src/main.py
# Сервер запустится на http://0.0.0.0:8000
```

### Интерактивное тестирование (рекомендуется)
```bash
# Новая песочница v2 - основной инструмент тестирования
python sandbox_v2.py

# Тест одного сообщения
python sandbox_v2.py -m "Привет! Есть курсы?"

# Автоматические тесты
python sandbox_v2.py --test
```

### Collaborative тестирование
```bash
# Прогон диалога из test_scenarios_stress.json
python collaborative_test.py 1  # По номеру
python collaborative_test.py "Забывчивая бабушка"  # По имени
```

### Стресс-тесты
```bash
python tests/test_stress_with_report.py
# Отчеты сохраняются в tests/reports/
```

## Установка зависимостей
```bash
pip install -r requirements.txt
```

## Настройка окружения
```bash
# Создайте .env файл на основе .env.example
cp .env.example .env
# Добавьте OPENROUTER_API_KEY
```

## Специальные тесты
```bash
# Тест смешанных приветствий
python test_mixed_greetings.py

# Тест мама-блогер (5 вопросов)
python test_mama_blogger.py

# Тест с историей диалога
python test_with_history.py
```

## Анализ результатов
```bash
python scripts/analyze_test_results.py
```

## Утилиты системы Darwin (macOS)
- `ls -la` - список файлов с правами доступа
- `grep -r "pattern" .` - поиск по файлам
- `find . -name "*.py"` - поиск файлов по маске
- `tail -f` - отслеживание логов в реальном времени
- `ps aux | grep python` - проверка запущенных процессов
- `lsof -i :8000` - проверка занятости порта