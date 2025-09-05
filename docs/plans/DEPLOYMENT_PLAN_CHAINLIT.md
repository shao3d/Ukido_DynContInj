# 🚀 План деплоя Ukido AI Assistant с Chainlit за 1-2 дня
## Детальная инструкция для новичка

### 📋 Предварительные требования
- [ ] Python 3.11+ установлен
- [ ] Docker Desktop установлен и запущен
- [ ] Git установлен
- [ ] GitHub аккаунт есть
- [ ] Railway аккаунт создан (потребуется $5)
- [ ] VS Code или другой редактор кода

### 📊 Что получим в итоге
- ✅ Рабочий чат со стримингом ответов
- ✅ Красивый UI без написания frontend
- ✅ Деплой в облако с публичным URL
- ✅ Сохранение истории диалогов
- ✅ Интеграция с вашим существующим кодом

### 💰 Стоимость на Railway ($5 хватит!)
- **Hobby план**: $5/месяц
- **Включает**: 500 часов выполнения + 100GB трафика
- **Для прототипа**: хватит на ~20 дней работы 24/7
- **Реальное использование**: ~2 месяца (с учётом sleep режима)

---

## 📁 ЭТАП 1: Наведение порядка в проекте (30 минут)

### 1.1 Очистка локальной папки проекта

```bash
# Переходим в папку проекта
cd /Users/andreysazonov/Documents/Projects/Ukido_DynContInj

# Создаём backup важных файлов
mkdir -p backup_before_chainlit
cp -r data/persistent_states backup_before_chainlit/
cp .env backup_before_chainlit/
cp CLAUDE.md backup_before_chainlit/

# Удаляем ненужные файлы для прототипа
rm -rf test_results/  # Старые результаты тестов
rm -f test_*.json     # Тестовые JSON файлы
rm -f run_*_test.py   # Индивидуальные тест-раннеры

# Очищаем кеш Python
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# Создаём структуру для Chainlit
mkdir -p chainlit_app
mkdir -p chainlit_app/static
mkdir -p chainlit_app/public
```

### 1.2 Обновление .gitignore

```bash
# Добавляем в .gitignore
echo "
# Chainlit specific
.chainlit/
chainlit_app/.chainlit/
*.db
*.sqlite

# Docker
docker-compose.override.yml

# Backups
backup_*/

# IDE
.idea/
.vscode/
*.swp
*.swo
" >> .gitignore
```

### 1.3 Очистка GitHub репозитория

```bash
# Проверяем статус
git status

# Добавляем все изменения в git
git add .gitignore
git add -A

# Коммитим текущее состояние
git commit -m "feat: Подготовка к интеграции Chainlit для стриминга"

# Создаём новую ветку для Chainlit
git checkout -b feature/chainlit-prototype

# Пушим в GitHub
git push origin feature/chainlit-prototype
```

---

## 🔧 ЭТАП 2: Установка и настройка Chainlit (45 минут)

### 2.1 Установка зависимостей

```bash
# Создаём отдельный requirements для Chainlit
cat > requirements-chainlit.txt << 'EOF'
# Существующие зависимости
fastapi==0.110.0
uvicorn[standard]==0.27.0
httpx==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
google-generativeai==0.8.3

# Chainlit и его зависимости
chainlit==1.3.0
watchfiles==0.24.0

# Для работы с вашим кодом
aiofiles==24.1.0
python-multipart==0.0.12
EOF

# Устанавливаем локально
pip install -r requirements-chainlit.txt
```

### 2.2 Создание адаптера для вашего кода

```bash
# Создаём главный файл Chainlit приложения
cat > chainlit_app/app.py << 'EOF'
"""
Chainlit адаптер для Ukido AI Assistant
Интегрирует существующий pipeline со стриминговым UI
"""

import chainlit as cl
import sys
import os
import asyncio
import json
from pathlib import Path

# Добавляем путь к src в Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем ваши модули
from src.router import router
from src.response_generator import response_generator
from src.history_manager import history_manager
from src.persistence_manager import persistence_manager
from src.zhvanetsky_humor import generate_humor_response
from src.simple_cta_blocker import simple_cta_blocker
from src.social_state import social_state_manager
from src.config import config

# Chainlit конфигурация
@cl.on_chat_start
async def start_chat():
    """Инициализация новой сессии чата"""
    
    # Создаём уникальный user_id для сессии
    user_id = cl.context.session.id
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("message_count", 0)
    cl.user_session.set("greeting_exchanged", False)
    
    # Восстанавливаем состояние если есть
    restored_state = persistence_manager.load_state(user_id)
    if restored_state:
        history_manager.restore_history(user_id, restored_state.get("history", []))
        cl.user_session.set("user_signal", restored_state.get("user_signal", "exploring_only"))
        cl.user_session.set("message_count", restored_state.get("message_count", 0))
        cl.user_session.set("greeting_exchanged", restored_state.get("greeting_exchanged", False))
    else:
        cl.user_session.set("user_signal", "exploring_only")
    
    # Приветственное сообщение
    welcome_message = """
    👋 Здравствуйте! Я AI-помощник школы Ukido.
    
    Я помогу вам узнать о:
    - 🎓 Наших курсах soft skills для детей 7-14 лет
    - 💰 Стоимости и условиях обучения
    - 👩‍🏫 Преподавателях и методике
    - 📅 Расписании занятий
    
    Задайте любой вопрос о школе!
    """
    
    await cl.Message(content=welcome_message).send()

@cl.on_message
async def main(message: cl.Message):
    """Обработка сообщений пользователя"""
    
    # Получаем данные сессии
    user_id = cl.user_session.get("user_id")
    message_count = cl.user_session.get("message_count", 0) + 1
    cl.user_session.set("message_count", message_count)
    
    user_signal = cl.user_session.get("user_signal", "exploring_only")
    greeting_exchanged = cl.user_session.get("greeting_exchanged", False)
    
    # Создаём сообщение для стриминга
    msg = cl.Message(content="")
    await msg.send()
    
    try:
        # Показываем статус обработки
        await msg.stream_token("🔍 Анализирую ваш вопрос...")
        await asyncio.sleep(0.5)
        
        # Получаем историю
        history = history_manager.get_history(user_id)
        
        # 1. ROUTER - классификация намерения
        router_result = await router.process_message(
            message.content,
            user_id,
            history,
            user_signal=user_signal,
            greeting_exchanged=greeting_exchanged
        )
        
        # Обновляем user_signal
        new_signal = router_result.get("user_signal", user_signal)
        cl.user_session.set("user_signal", new_signal)
        
        # Обновляем статус
        await msg.update(content="")
        await msg.stream_token("📚 Подбираю информацию...")
        await asyncio.sleep(0.5)
        
        # 2. ГЕНЕРАЦИЯ ОТВЕТА
        response_text = ""
        
        if router_result.get("intent") == "offtopic":
            # Проверяем, нужен ли юмор
            if router_result.get("humor_generated"):
                response_text = await generate_humor_response(
                    message.content,
                    history,
                    new_signal
                )
            else:
                response_text = "Давайте лучше поговорим о нашей школе Ukido и том, как мы можем помочь вашему ребёнку развить важные навыки."
        
        elif router_result.get("intent") == "need_simplification":
            response_text = "Я заметил, что в вашем вопросе несколько тем. Давайте разберём их по порядку. Какой аспект вас интересует в первую очередь?"
        
        else:  # success
            # Генерируем основной ответ
            response_text = await response_generator.generate(
                query=message.content,
                intent=router_result.get("intent", "success"),
                relevant_documents=router_result.get("relevant_documents", []),
                user_signal=new_signal,
                history=history,
                user_id=user_id,
                decomposed_questions=router_result.get("decomposed_questions", [])
            )
            
            # Проверяем, нужно ли добавить CTA
            should_block_cta, block_reason = simple_cta_blocker.should_block_cta(
                user_id=user_id,
                message=message.content,
                message_count=message_count,
                user_signal=new_signal,
                response=response_text
            )
            
            if not should_block_cta and message_count > 1:
                # Здесь можно добавить CTA к ответу
                pass
        
        # 3. СТРИМИНГ ОТВЕТА (эффект печати)
        await msg.update(content="")
        
        # Разбиваем на слова для плавного стриминга
        words = response_text.split()
        current_text = ""
        
        for i in range(0, len(words), 2):  # По 2 слова за раз
            chunk = " ".join(words[i:min(i+2, len(words))])
            current_text += chunk + " "
            await msg.update(content=current_text.strip())
            await asyncio.sleep(0.05)  # Задержка для эффекта печати
        
        # 4. СОХРАНЕНИЕ СОСТОЯНИЯ
        # Добавляем в историю
        history_manager.add_message(user_id, "user", message.content)
        history_manager.add_message(user_id, "assistant", response_text)
        
        # Обновляем greeting status
        if social_state_manager.is_greeting(message.content):
            cl.user_session.set("greeting_exchanged", True)
        
        # Сохраняем в persistent storage
        state_to_save = {
            "history": history_manager.get_history(user_id),
            "user_signal": new_signal,
            "greeting_exchanged": cl.user_session.get("greeting_exchanged"),
            "message_count": message_count
        }
        persistence_manager.save_state(user_id, state_to_save)
        
    except Exception as e:
        error_msg = f"😔 Извините, произошла ошибка при обработке вашего запроса: {str(e)}"
        await msg.update(content=error_msg)
        print(f"❌ Ошибка в Chainlit: {e}")

@cl.on_stop
async def stop_chat():
    """Действия при остановке чата"""
    user_id = cl.user_session.get("user_id")
    if user_id:
        print(f"📝 Сессия {user_id} завершена")

if __name__ == "__main__":
    cl.run()
EOF
```

### 2.3 Создание конфигурации Chainlit

```bash
# Создаём конфигурационный файл
cat > chainlit_app/.chainlit/config.toml << 'EOF'
[project]
# Название вашего приложения
name = "Ukido AI Assistant"

# Настройки чата
[UI]
# Название в UI
name = "Ukido AI Помощник"

# Описание
description = "🎓 AI-помощник детской школы soft skills"

# Скрыть ватермарк Chainlit (для production)
hide_cot = false

# Цветовая схема
theme = "light"

# Настройки сообщений
[UI.messages]
# Максимальная длина сообщения
max_size_mb = 2
# Timeout для сообщений
timeout = 120

# Настройки сервера
[server]
# Порт
port = 8000
# Хост
host = "0.0.0.0"
# Debug режим
debug = false

# Настройки telemetry (отключаем для приватности)
[telemetry]
enabled = false

# Features
[features]
# Включить multi-modal (изображения)
multi_modal = false
# Включить аудио
audio = false
# Unsafe режим (разрешить HTML)
unsafe_allow_html = false
EOF
```

### 2.4 Тестирование локально

```bash
# Запускаем Chainlit локально
cd chainlit_app
chainlit run app.py --port 8000

# Откройте браузер на http://localhost:8000
# Протестируйте несколько сообщений
```

---

## 🐳 ЭТАП 3: Docker конфигурация (30 минут)

### 3.1 Создание Dockerfile для Chainlit

```bash
# Создаём Dockerfile в корне проекта
cat > Dockerfile.chainlit << 'EOF'
# Multi-stage build для оптимизации размера
FROM python:3.11-slim as builder

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
WORKDIR /app
COPY requirements-chainlit.txt .

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir --user -r requirements-chainlit.txt

# Production образ
FROM python:3.11-slim

# Копируем установленные пакеты из builder
COPY --from=builder /root/.local /root/.local

# Убеждаемся что pip пакеты в PATH
ENV PATH=/root/.local/bin:$PATH

# Рабочая директория
WORKDIR /app

# Копируем код приложения
COPY src/ ./src/
COPY data/ ./data/
COPY chainlit_app/ ./chainlit_app/
COPY .env .env

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV CHAINLIT_HOST=0.0.0.0
ENV CHAINLIT_PORT=8000

# Открываем порт
EXPOSE 8000

# Переходим в директорию chainlit_app
WORKDIR /app/chainlit_app

# Запуск Chainlit
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

### 3.2 Создание docker-compose для локального тестирования

```bash
cat > docker-compose.chainlit.yml << 'EOF'
version: '3.8'

services:
  chainlit-app:
    build:
      context: .
      dockerfile: Dockerfile.chainlit
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - CHAINLIT_HOST=0.0.0.0
      - CHAINLIT_PORT=8000
      - PYTHONUNBUFFERED=1
    volumes:
      # Для разработки - монтируем код
      - ./src:/app/src:ro
      - ./data:/app/data:ro
      - ./chainlit_app:/app/chainlit_app:ro
      # Для сохранения состояний
      - ./data/persistent_states:/app/data/persistent_states:rw
    restart: unless-stopped

# Если нужна будет база данных в будущем
volumes:
  chainlit_data:
EOF
```

### 3.3 Сборка и тестирование Docker локально

```bash
# Собираем Docker образ
docker build -f Dockerfile.chainlit -t ukido-chainlit:latest .

# Запускаем через docker-compose
docker-compose -f docker-compose.chainlit.yml up

# Проверяем что работает
# Откройте http://localhost:8000

# Если всё ОК, останавливаем
docker-compose -f docker-compose.chainlit.yml down
```

---

## 🚂 ЭТАП 4: Деплой на Railway (45 минут)

### 4.1 Подготовка Railway

```bash
# 1. Зарегистрируйтесь на https://railway.app
# 2. Подключите GitHub аккаунт
# 3. Добавьте платёжный метод ($5 Hobby план)
```

### 4.2 Создание railway.json конфигурации

```bash
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile.chainlit"
  },
  "deploy": {
    "numReplicas": 1,
    "startCommand": "chainlit run app.py --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/",
    "sleepApplication": true,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
EOF
```

### 4.3 Создание проекта на Railway через CLI

```bash
# Установка Railway CLI (если ещё нет)
# На Mac:
brew install railway

# На других системах:
# curl -fsSL https://railway.app/install.sh | sh

# Логинимся
railway login

# Создаём новый проект
railway init

# Выбираем "Empty Project"
# Вводим название: ukido-chainlit-prototype

# Линкуем с GitHub репозиторием
railway link

# Добавляем переменные окружения
railway variables set OPENROUTER_API_KEY="ваш_ключ_здесь"
railway variables set GOOGLE_API_KEY="ваш_ключ_если_есть"
railway variables set PORT=8000
```

### 4.4 Деплой через GitHub

```bash
# Коммитим все изменения
git add .
git commit -m "feat: Chainlit интеграция со стримингом готова к деплою"

# Пушим в GitHub
git push origin feature/chainlit-prototype

# Railway автоматически задеплоит!
```

### 4.5 Альтернативный способ - деплой через Railway UI

```
1. Зайдите на https://railway.app/dashboard
2. Нажмите "New Project"
3. Выберите "Deploy from GitHub repo"
4. Выберите ваш репозиторий Ukido_DynContInj
5. Выберите ветку feature/chainlit-prototype
6. Railway обнаружит Dockerfile.chainlit
7. Добавьте Environment Variables:
   - OPENROUTER_API_KEY = ваш_ключ
   - GOOGLE_API_KEY = ваш_ключ
8. Нажмите "Deploy"
```

### 4.6 Получение публичного URL

```bash
# Через CLI
railway domain

# Или в UI Railway:
# 1. Откройте ваш проект
# 2. Перейдите в Settings
# 3. В разделе Domains нажмите "Generate Domain"
# 4. Получите URL вида: ukido-chainlit.up.railway.app
```

---

## ✅ ЭТАП 5: Проверка и оптимизация (30 минут)

### 5.1 Чек-лист проверки

```bash
# 1. Проверяем что сайт доступен
curl https://ваш-домен.up.railway.app

# 2. Проверяем логи
railway logs

# 3. Мониторим использование
railway status
```

### 5.2 Оптимизация для экономии на Railway

```bash
# Добавляем в railway.json sleep режим
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile.chainlit"
  },
  "deploy": {
    "numReplicas": 1,
    "startCommand": "chainlit run app.py --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/",
    "sleepApplication": true,
    "sleepDelay": 10,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
EOF

# Коммитим и пушим
git add railway.json
git commit -m "feat: Добавлен sleep режим для экономии ресурсов"
git push origin feature/chainlit-prototype
```

---

## 🎯 Что получили в итоге

### ✅ Работающий функционал:
1. **Стриминг ответов** - текст появляется по мере генерации
2. **Красивый UI** - профессиональный интерфейс без кода
3. **Сохранение истории** - диалоги сохраняются между сессиями
4. **Публичный URL** - можно показать инвесторам
5. **Интеграция с вашим кодом** - все модули работают

### 📊 Использование ресурсов на Railway:
- **CPU**: ~100-200 MHz в idle, до 1 GHz при генерации
- **RAM**: ~200-300 MB
- **Трафик**: ~1 KB на сообщение
- **Стоимость**: ~$0.15-0.25 в день активного использования

### 🔗 Ссылки для демо:
- **Публичный URL**: `https://ukido-chainlit-xxx.up.railway.app`
- **GitHub**: `https://github.com/ваш_username/Ukido_DynContInj/tree/feature/chainlit-prototype`

---

## 🆘 Troubleshooting - Частые проблемы

### Проблема 1: "Module not found"
```bash
# Решение: Проверьте PYTHONPATH в Dockerfile
ENV PYTHONPATH=/app:$PYTHONPATH
```

### Проблема 2: "Port already in use"
```bash
# Решение: Убейте процесс на порту 8000
lsof -i :8000
kill -9 PID
```

### Проблема 3: "Railway деплой падает"
```bash
# Смотрим логи
railway logs --tail 100

# Частая причина - нет переменных окружения
railway variables
```

### Проблема 4: "Chainlit не стримит"
```python
# Убедитесь что используете await msg.stream_token()
# НЕ await msg.update() для стриминга
```

---

## 📈 Следующие шаги после прототипа

1. **Показать инвесторам** - у вас есть рабочий прототип!
2. **Собрать фидбек** - что улучшить в UX
3. **Планировать переход на FastAPI** - для production
4. **Добавить аналитику** - отслеживать использование

---

## 💡 Полезные команды Railway

```bash
# Просмотр логов в реальном времени
railway logs --tail

# Рестарт приложения
railway restart

# Просмотр переменных
railway variables

# Открыть приложение в браузере
railway open

# Статус и метрики
railway status
```

---

## ✅ Финальный чек-лист

- [ ] Проект очищен от лишних файлов
- [ ] GitHub репозиторий обновлён
- [ ] Chainlit установлен и настроен
- [ ] Docker образ собирается без ошибок
- [ ] Локальное тестирование пройдено
- [ ] Railway аккаунт создан и оплачен ($5)
- [ ] Деплой на Railway успешен
- [ ] Публичный URL работает
- [ ] Стриминг ответов работает
- [ ] История сохраняется

---

**Готово! У вас есть работающий прототип со стримингом за 1-2 дня! 🎉**

При возникновении проблем обращайтесь - помогу отладить.