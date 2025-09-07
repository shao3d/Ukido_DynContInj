# Multi-stage build для оптимизации размера
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Создаем непривилегированного пользователя
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Копируем установленные пакеты из builder
COPY --from=builder /root/.local /home/appuser/.local

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Создаем необходимые директории
RUN mkdir -p static data/persistent_states && \
    chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Добавляем локальные пакеты в PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Экспонируем порт (Railway автоматически использует переменную PORT)
EXPOSE 8000

# Healthcheck для Railway (используем httpx вместо requests)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; import os; port=os.getenv('PORT', '8000'); httpx.get(f'http://localhost:{port}/health')" || exit 1

# Запускаем приложение
# Используем sh -c чтобы переменная окружения PORT правильно раскрылась
CMD ["sh", "-c", "python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]