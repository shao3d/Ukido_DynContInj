# 🌐 План реализации мультиязычности v2.0
**Дата создания:** 08.01.2025  
**Модель перевода:** GPT-4o Mini  
**Базовая ветка:** feature/simple-sse-ui

## 📋 Контекст и цель

### Проблема
Система отвечает только на русском языке, даже когда пользователи пишут на украинском или английском. Попытки решить через промпты провалились из-за доминирования русскоязычной базы знаний (98% контекста).

### Решение
Двухэтапный подход:
1. Router определяет язык запроса
2. Финальный перевод готового ответа через GPT-4o Mini

## 🚀 Пошаговый план реализации

### Шаг 1: Создание новой ветки
```bash
git checkout feature/simple-sse-ui
git pull origin feature/simple-sse-ui
git checkout -b feature/multilingual-v2
```

### Шаг 2: Модификация Router (src/router.py)

#### 2.1 Добавить определение языка в промпт (~строка 50-100)
```python
# В системный промпт Router добавить:
"""
LANGUAGE DETECTION:
Determine the primary language of the user's message:
- 'ru' for Russian (default)
- 'uk' for Ukrainian
- 'en' for English
- If mixed or unclear, use the most dominant language
- For emojis/short confirmations, use 'ru' as default

Add to your response:
"detected_language": "uk" // or "en" or "ru"
"""
```

#### 2.2 Обновить формат ответа Router (~строка 400-450)
```python
# В схему ответа добавить:
{
    "status": "success/offtopic/need_simplification",
    "detected_language": "uk",  # НОВОЕ ПОЛЕ
    "user_signal": "exploring_only",
    # ... остальные поля
}
```

### Шаг 3: Добавление переводчика (src/translator.py) - НОВЫЙ ФАЙЛ

```python
# src/translator.py
import logging
from typing import Optional, List
import re

logger = logging.getLogger(__name__)

class SmartTranslator:
    """Умный переводчик с защитой терминов и кешированием"""
    
    # Термины, которые НЕ переводим
    PROTECTED_TERMS = {
        'Ukido', 'ukido', 'UKIDO',
        'soft skills', 'Soft Skills', 'SOFT SKILLS',
        'Zoom', 'zoom', 'ZOOM',
        'online', 'Online', 'ONLINE'
    }
    
    # Кеш популярных фраз (заполнится в процессе работы)
    translation_cache = {}
    
    def __init__(self, openrouter_client):
        self.client = openrouter_client
        self.model = "openai/gpt-4o-mini"  # Оптимальный баланс цена/качество
        
    async def translate(
        self, 
        text: str, 
        target_language: str,
        source_language: str = 'ru',
        user_context: Optional[str] = None
    ) -> str:
        """
        Переводит текст с сохранением маркетинговой силы
        
        Args:
            text: Исходный текст на русском
            target_language: Целевой язык ('uk' или 'en')
            source_language: Исходный язык (по умолчанию 'ru')
            user_context: Контекст пользователя для лучшего перевода
        """
        
        # Если язык тот же - не переводим
        if target_language == source_language or target_language == 'ru':
            return text
            
        # Проверяем кеш
        cache_key = f"{target_language}:{text[:100]}"  # Первые 100 символов как ключ
        if cache_key in self.translation_cache:
            logger.info(f"✅ Использован кеш перевода для {target_language}")
            return self.translation_cache[cache_key]
        
        # Защищаем термины
        protected_text = self._protect_terms(text)
        
        # Формируем промпт для перевода
        lang_map = {
            'uk': 'Ukrainian',
            'en': 'English'
        }
        
        system_prompt = f"""You are a professional translator for an educational platform.
Translate the following text from Russian to {lang_map.get(target_language, 'English')}.

CRITICAL RULES:
1. Preserve the marketing persuasiveness and emotional tone
2. Keep ALL terms in [PROTECTED] tags exactly as they are
3. Maintain the conversational, friendly style
4. For Ukrainian: use modern Ukrainian, not surzhyk or russisms
5. For English: use American English, casual but professional
6. Preserve all formatting (line breaks, bullet points, etc.)

NEVER translate:
- Brand names (Ukido)
- Technical terms in [PROTECTED] tags
- URLs and email addresses
- Numbers and prices

Context: This is a response from an AI assistant for a children's soft skills school."""

        user_prompt = f"Translate to {lang_map.get(target_language)}:\n\n{protected_text}"
        
        if user_context:
            user_prompt += f"\n\nUser's original question: {user_context}"
        
        try:
            # Вызываем GPT-4o Mini для перевода
            response = await self.client.generate(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Низкая температура для консистентности
                max_tokens=1500
            )
            
            # Восстанавливаем защищённые термины
            translated = self._restore_terms(response)
            
            # Сохраняем в кеш (только короткие фразы)
            if len(text) < 200:
                self.translation_cache[cache_key] = translated
                
            logger.info(f"✅ Успешный перевод на {target_language}")
            return translated
            
        except Exception as e:
            logger.error(f"❌ Ошибка перевода: {e}")
            # Fallback - возвращаем оригинал
            return text
    
    def _protect_terms(self, text: str) -> str:
        """Защищает термины от перевода"""
        protected = text
        for term in self.PROTECTED_TERMS:
            # Используем регулярные выражения для точного совпадения слов
            pattern = r'\b' + re.escape(term) + r'\b'
            protected = re.sub(pattern, f'[PROTECTED]{term}[/PROTECTED]', protected, flags=re.IGNORECASE)
        return protected
    
    def _restore_terms(self, text: str) -> str:
        """Восстанавливает защищённые термины"""
        return re.sub(r'\[PROTECTED\](.*?)\[/PROTECTED\]', r'\1', text)
```

### Шаг 4: Интеграция в response_generator.py

#### 4.1 Импорт и инициализация (~строка 10-30)
```python
from translator import SmartTranslator

class ResponseGenerator:
    def __init__(self, ...):
        # ... существующий код
        self.translator = SmartTranslator(self.client)
```

#### 4.2 Модификация метода generate (~строка 32-250)
```python
async def generate(self, router_result: Dict, history: Optional[List[Dict[str, str]]] = None, current_message: Optional[str] = None) -> tuple[str, dict]:
    # ... существующая генерация ответа ...
    
    # НОВОЕ: Перевод перед возвратом
    detected_language = router_result.get("detected_language", "ru")
    
    if detected_language != "ru":
        # Переводим финальный текст
        final_text = await self.translator.translate(
            text=final_text,
            target_language=detected_language,
            user_context=current_message
        )
        
        # Добавляем информацию о переводе в metadata
        metadata["translated_to"] = detected_language
        
    return final_text, metadata
```

### Шаг 5: Обработка edge cases

#### 5.1 Сохранение языка в истории (src/history_manager.py)
```python
# Добавить в сохранение истории:
def add_message(self, user_id: str, role: str, content: str, metadata: Dict = None):
    # ... существующий код
    if metadata and "detected_language" in metadata:
        # Сохраняем язык для контекста
        message["language"] = metadata["detected_language"]
```

#### 5.2 Обработка смешанных языков (src/router.py)
```python
# Добавить в Router логику majority voting:
def detect_primary_language(self, text: str) -> str:
    """Определяет доминирующий язык в тексте"""
    # Подсчёт символов каждого алфавита
    cyrillic_ru = len(re.findall(r'[а-яА-ЯёЁ]', text))
    cyrillic_uk = len(re.findall(r'[іїєґІЇЄҐ]', text))  # Уникальные украинские
    latin = len(re.findall(r'[a-zA-Z]', text))
    
    # Если есть украинские буквы - украинский
    if cyrillic_uk > 0:
        return 'uk'
    # Если латиница доминирует - английский
    elif latin > cyrillic_ru:
        return 'en'
    # По умолчанию - русский
    else:
        return 'ru'
```

### Шаг 6: Тестовые сценарии

#### test_multilingual.py
```python
import asyncio
import httpx

async def test_multilingual():
    """Тестирует мультиязычность системы"""
    
    test_cases = [
        # Украинский
        {"user_id": "test_uk", "message": "Привіт! Розкажіть про школу"},
        {"user_id": "test_uk", "message": "Які курси у вас є?"},
        {"user_id": "test_uk", "message": "Дякую"},
        
        # Английский
        {"user_id": "test_en", "message": "Hello! Tell me about your school"},
        {"user_id": "test_en", "message": "What courses do you have?"},
        {"user_id": "test_en", "message": "Thanks"},
        
        # Смешанный
        {"user_id": "test_mix", "message": "Привет! What about soft skills курсы?"},
        
        # Смайлики после украинского
        {"user_id": "test_emoji", "message": "Розкажіть про ціни"},
        {"user_id": "test_emoji", "message": "👍"},
        
        # Confusion detection
        {"user_id": "test_conf", "message": "Привіт!"},
        {"user_id": "test_conf", "message": "Что? Не понимаю"},
    ]
    
    async with httpx.AsyncClient() as client:
        for test in test_cases:
            response = await client.post(
                "http://localhost:8000/chat",
                json=test
            )
            result = response.json()
            print(f"User: {test['message']}")
            print(f"Lang: {result.get('detected_language', 'unknown')}")
            print(f"Bot: {result['response'][:100]}...")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_multilingual())
```

### Шаг 7: Конфигурация

#### Добавить в config.py
```python
# Настройки мультиязычности
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "openai/gpt-4o-mini")
TRANSLATION_ENABLED = os.getenv("TRANSLATION_ENABLED", "true").lower() == "true"
TRANSLATION_CACHE_SIZE = 1000  # Количество кешированных переводов
SUPPORTED_LANGUAGES = ["ru", "uk", "en"]
DEFAULT_LANGUAGE = "ru"
```

### Шаг 8: Метрики и мониторинг

#### Добавить в main.py (метрики)
```python
# В endpoint /metrics добавить:
translation_stats = {
    "translations_total": translator.translation_count,
    "cache_hits": translator.cache_hits,
    "languages_detected": {
        "uk": uk_count,
        "en": en_count,
        "ru": ru_count
    }
}
```

## 🧪 Чек-лист тестирования

- [ ] Украинский запрос → украинский ответ
- [ ] Английский запрос → английский ответ
- [ ] Русский запрос → русский ответ (без перевода)
- [ ] Смешанный язык → majority language
- [ ] Смайлик после украинского → остаёмся на украинском
- [ ] Защита терминов (Ukido, soft skills) работает
- [ ] Кеширование переводов работает
- [ ] Fallback при ошибке перевода
- [ ] Confusion detection ("что?", "не понимаю")
- [ ] SSE стриминг работает с переводом

## 📊 Ожидаемые метрики

- **Дополнительная латентность:** +1.5-2 секунды
- **Дополнительная стоимость:** +$0.00015 за запрос
- **Качество перевода:** 85-90% для украинского, 95% для английского
- **Cache hit rate:** 30-40% после прогрева

## ⚠️ Известные ограничения

1. **Украинский язык** - GPT-4o Mini не идеален, возможны русизмы
2. **Контекст теряется** - перевод не знает полной истории диалога
3. **Маркетинговые фразы** - могут потерять убедительность
4. **Числительные** - нужно следить за склонениями

## 🔧 Отладка

### Логирование
```python
LOG_LEVEL=DEBUG python src/main.py

# Ключевые маркеры в логах:
🔍 Language detected: uk
🌐 Translating to Ukrainian
✅ Translation cached
❌ Translation failed, using original
```

### Быстрый тест
```bash
# Украинский
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_uk","message":"Привіт! Які у вас курси?"}'

# Английский  
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_en","message":"Hello! What courses do you have?"}'
```

## 📝 Коммит после реализации

```bash
git add .
git commit -m "feat: Мультиязычность v2 через пост-перевод

- Добавлено определение языка в Router
- Реализован SmartTranslator с GPT-4o Mini
- Защита терминов (Ukido, soft skills)
- Кеширование популярных переводов
- Поддержка украинского и английского языков
- Обработка edge cases (смайлики, confusion)

Tested with: uk, en, mixed languages
Cost impact: +$0.00015 per request
Latency impact: +1.5-2 seconds"

git push origin feature/multilingual-v2
```

## 🚀 Следующие улучшения (после MVP)

1. **Параллельная база знаний** на украинском
2. **Fine-tuning модели** на украинских текстах школы
3. **Векторный поиск** похожих переводов
4. **A/B тестирование** качества переводов
5. **Автоопределение языка** по IP/геолокации

---
**Автор плана:** Claude (Anthropic)  
**Проверено:** 08.01.2025  
**Статус:** Ready for implementation