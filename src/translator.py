"""
translator.py - Умный переводчик с защитой терминов и кешированием
Версия 2.0: Пост-перевод готовых ответов
"""

import logging
from typing import Optional, Dict
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
    translation_cache: Dict[str, str] = {}
    
    # Счётчики для метрик
    translation_count = 0
    cache_hits = 0
    
    def __init__(self, openrouter_client):
        """
        Инициализация переводчика
        
        Args:
            openrouter_client: Клиент для вызова OpenRouter API
        """
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
            
        Returns:
            Переведённый текст или оригинал при ошибке
        """
        
        # Если язык тот же - не переводим
        if target_language == source_language or target_language == 'ru':
            return text
            
        # Проверяем кеш
        cache_key = f"{target_language}:{text[:100]}"  # Первые 100 символов как ключ
        if cache_key in self.translation_cache:
            logger.info(f"✅ Использован кеш перевода для {target_language}")
            self.cache_hits += 1
            return self.translation_cache[cache_key]
        
        # НЕ защищаем термины заранее - используем тот же подход, что и в translate_stream
        
        # Формируем промпт для перевода
        lang_map = {
            'uk': 'Ukrainian',
            'en': 'English'
        }
        
        # Создаём список терминов для инструкции
        protected_terms_list = ', '.join(self.PROTECTED_TERMS)
        
        system_prompt = f"""You are a professional translator for an educational platform.
Translate the following text from Russian to {lang_map.get(target_language, 'English')}.

CRITICAL RULES:
1. Preserve the marketing persuasiveness and emotional tone
2. Maintain the conversational, friendly style
3. For Ukrainian: use modern Ukrainian, not surzhyk or russisms
4. For English: use American English, casual but professional
5. Preserve all formatting (line breaks, bullet points, etc.)

NEVER translate these terms (keep them exactly as they are):
{protected_terms_list}

Also NEVER translate:
- URLs and email addresses
- Numbers and prices
- Any English technical terms

Context: This is a response from an AI assistant for a children's soft skills school."""

        user_prompt = f"Translate to {lang_map.get(target_language)}:\n\n{text}"  # Используем чистый текст
        
        if user_context:
            user_prompt += f"\n\nUser's original question: {user_context}"
        
        try:
            logger.info(f"🔄 Начинаю перевод на {target_language}...")
            logger.debug(f"Исходный текст (первые 100 символов): {text[:100]}...")
            
            # Вызываем GPT-4o Mini для перевода
            response = await self.client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.3,  # Низкая температура для консистентности
                max_tokens=3000  # Увеличено для полных переводов
            )
            
            logger.debug(f"Получен ответ от API: {response[:100]}...")
            
            # Нормализуем двойные переводы строк для единообразия с русским форматированием
            translated = response.replace('\n\n', '\n')
            
            # Сохраняем в кеш (только короткие фразы)
            if len(text) < 200:
                self.translation_cache[cache_key] = translated
                
            logger.info(f"✅ Успешный перевод на {target_language}")
            logger.debug(f"Переведённый текст (первые 100 символов): {translated[:100]}...")
            self.translation_count += 1
            return translated
            
        except Exception as e:
            logger.error(f"❌ Ошибка перевода: {e}")
            # Fallback - возвращаем оригинал
            return text
    
    def _protect_terms(self, text: str) -> str:
        """
        Защищает термины от перевода
        
        Args:
            text: Исходный текст
            
        Returns:
            Текст с защищёнными терминами
        """
        protected = text
        for term in self.PROTECTED_TERMS:
            # Используем регулярные выражения для точного совпадения слов
            pattern = r'\b' + re.escape(term) + r'\b'
            protected = re.sub(pattern, f'[PROTECTED]{term}[/PROTECTED]', protected, flags=re.IGNORECASE)
        return protected
    
    def _restore_terms(self, text: str) -> str:
        """
        Восстанавливает защищённые термины
        
        Args:
            text: Текст с защищёнными терминами
            
        Returns:
            Текст с восстановленными терминами
        """
        # Удаляем все теги PROTECTED (может быть несколько слоёв)
        # Используем более агрессивный подход для удаления всех вложенных тегов
        max_iterations = 10  # Защита от бесконечного цикла
        iterations = 0
        
        while ('[PROTECTED]' in text or '[/PROTECTED]' in text) and iterations < max_iterations:
            # Сначала удаляем все открывающие теги
            text = text.replace('[PROTECTED]', '')
            # Затем удаляем все закрывающие теги
            text = text.replace('[/PROTECTED]', '')
            iterations += 1
            
        return text
    
    def detect_language(self, text: str) -> str:
        """
        Определяет язык текста (вспомогательный метод)
        
        Args:
            text: Текст для анализа
            
        Returns:
            Код языка: 'ru', 'uk' или 'en'
        """
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
    
    async def translate_stream(
        self, 
        text: str, 
        target_language: str,
        user_context: str = None
    ):
        """
        Стримит перевод текста в реальном времени
        
        Args:
            text: Текст для перевода
            target_language: Целевой язык ('uk', 'en')
            user_context: Контекст пользователя
            
        Yields:
            Части переведённого текста
        """
        # Если русский язык - возвращаем как есть
        if target_language == 'ru':
            yield text
            return
            
        # Мапинг языков для промпта
        lang_map = {
            'uk': 'Ukrainian',
            'en': 'English'
        }
        
        # НЕ защищаем термины заранее! Пусть GPT-4o Mini сам работает с чистым текстом
        # Это решает проблему вложенных тегов
        
        # Создаём список терминов для инструкции
        protected_terms_list = ', '.join(self.PROTECTED_TERMS)
        
        system_prompt = f"""You are a professional translator for an educational platform.
Translate the following text from Russian to {lang_map.get(target_language, 'English')}.

CRITICAL RULES:
1. Preserve the marketing persuasiveness and emotional tone
2. Maintain the conversational, friendly style
3. For Ukrainian: use modern Ukrainian, not surzhyk or russisms
4. For English: use American English, casual but professional
5. Preserve all formatting (line breaks, bullet points, etc.)

NEVER translate these terms (keep them exactly as they are):
{protected_terms_list}

Also NEVER translate:
- URLs and email addresses
- Numbers and prices
- Any English technical terms

Context: This is a response from an AI assistant for a children's soft skills school."""

        user_prompt = f"Translate to {lang_map.get(target_language)}:\n\n{text}"  # Используем чистый текст
        
        if user_context:
            user_prompt += f"\n\nUser's original question: {user_context}"
        
        try:
            # Импортируем функцию стриминга
            from openrouter_client_stream import chat_stream
            
            # Стримим перевод - теперь без тегов!
            async for chunk in chat_stream(
                self.client,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=3000  # Увеличено для полных переводов
            ):
                # Нормализуем двойные переводы строк в одинарные для единообразия
                if chunk:
                    # Заменяем двойные переводы строк на одинарные
                    normalized_chunk = chunk.replace('\n\n', '\n')
                    yield normalized_chunk
                
            logger.info(f"✅ Успешный стриминг перевода на {target_language}")
            self.translation_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга перевода: {e}")
            # Fallback - возвращаем оригинал
            yield text