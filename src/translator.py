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
    
    def __init__(self, openrouter_client, model: Optional[str] = None):
        """
        Инициализация переводчика
        
        Args:
            openrouter_client: Клиент для вызова OpenRouter API
        """
        self.client = openrouter_client
        self.model = model or getattr(openrouter_client, "model", "anthropic/claude-3.5-haiku")
        
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
        
        system_prompt = self._build_translation_prompt(target_language, lang_map, protected_terms_list)

        # Формируем user prompt в зависимости от языка
        if target_language == 'en':
            user_prompt = f"Rewrite as natural American English:\n\n{text}"
        else:
            user_prompt = f"Translate to {lang_map.get(target_language)}:\n\n{text}"
        
        if user_context:
            user_prompt += f"\n\nUser's original question: {user_context}"
        
        try:
            logger.info(f"🔄 Начинаю перевод на {target_language}...")
            logger.debug(f"Исходный текст (первые 100 символов): {text[:100]}...")
            
            # Вызываем Claude Haiku для перевода
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
            
            # Сохраняем форматирование абзацев
            translated = response
            
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
    
    def _build_translation_prompt(self, target_language: str, lang_map: dict, protected_terms_list: str) -> str:
        """
        Создаёт промпт для перевода с few-shot примерами
        
        Args:
            target_language: Целевой язык ('uk' или 'en')
            lang_map: Маппинг кодов языков на названия
            protected_terms_list: Список защищённых терминов
            
        Returns:
            Системный промпт для перевода
        """
        target_lang_name = lang_map.get(target_language, 'English')
        
        if target_language == 'en':
            # Улучшенный промпт для английского с few-shot примерами
            return f"""You are a native English copywriter for Ukido, a children's soft skills school.

YOUR TASK: Rewrite this Russian text as natural American English that sounds like it was originally written by a native speaker for American parents.

DO NOT translate word-by-word. REFRAME the meaning naturally.

TONE: Warm, friendly, professional — like a knowledgeable teacher explaining to a parent over coffee.

STYLE RULES:
- Use short sentences and active voice
- Use contractions: "we're", "you'll", "it's", "don't"
- Avoid formal/corporate language ("is provided" → "we offer")
- Avoid passive voice ("classes are conducted" → "classes happen")
- Sound like a real person, not a brochure
- Keep the informative, helpful tone of the original

BEFORE/AFTER EXAMPLES (based on actual Ukido content):

Russian: "Первое занятие бесплатно. Длительность 90 минут."
❌ Bad: "The first lesson is provided free of charge. The duration is 90 minutes."
✅ Good: "First class is free — it's a full 90-minute session."

Russian: "Группы до 6 детей, что позволяет уделить внимание каждому."
❌ Bad: "Groups of up to 6 children, which allows paying attention to each one."
✅ Good: "We keep groups small (6 kids max) so every child gets real attention."

Russian: "Большинство застенчивых детей показывают прогресс через месяц."
❌ Bad: "The majority of shy children demonstrate progress after one month."
✅ Good: "Most shy kids start opening up within a month — we see it all the time."

Russian: "Занятия проходят онлайн через Zoom, забирать никуда не нужно."
❌ Bad: "Classes are conducted online via Zoom, there is no need to pick up anywhere."
✅ Good: "Classes are on Zoom, so no driving — your kid learns from home."

Russian: "Мы работаем с детьми с особыми потребностями после консультации."
❌ Bad: "We work with children with special needs after a consultation."
✅ Good: "We welcome kids with special needs — just schedule a quick chat with us first."

Russian: "Занятия 2 раза в неделю по 90 минут."
❌ Bad: "Classes are held 2 times per week for 90 minutes each."
✅ Good: "Classes run twice a week, 90 minutes each."

KEEP EXACTLY AS-IS (never translate):
{protected_terms_list}
- All URLs, emails, phone numbers, prices in UAH (грн)

Preserve all formatting (line breaks, bullet points, paragraphs).

CRITICAL: Return ONLY the rewritten English text.
DO NOT add any explanations, comments, or descriptions of what you did.
DO NOT say things like "The rewrite captures..." or "I've used...".
Just output the final English text, nothing else."""
        else:
            # Промпт для украинского (оставляем похожим на старый, но улучшенный)
            return f"""You are a professional translator for Ukido, a children's soft skills school.
Translate the following text from Russian to modern {target_lang_name}.

CRITICAL RULES:
1. Use modern Ukrainian, NOT surzhyk or russisms
2. Preserve the warm, conversational tone
3. Keep the informative style with specific details
4. Maintain all formatting (line breaks, bullet points)
5. Sound natural, like a Ukrainian teacher talking to parents

NEVER translate these terms (keep exactly as-is):
{protected_terms_list}

Also keep unchanged:
- URLs and email addresses
- Numbers and prices
- Technical terms in English

Context: This is a response from an AI assistant for a children's soft skills school.

CRITICAL: Return ONLY the translated {target_lang_name} text.
DO NOT add any explanations, comments, or descriptions of what you did.
DO NOT say things like "Here's the translation..." or "The translation follows...".
Just output the final {target_lang_name} text, nothing else."""

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
        
        # Создаём список терминов для инструкции
        protected_terms_list = ', '.join(self.PROTECTED_TERMS)
        
        # Используем общий метод для построения промпта
        system_prompt = self._build_translation_prompt(target_language, lang_map, protected_terms_list)

        # Формируем user prompt в зависимости от языка
        if target_language == 'en':
            user_prompt = f"Rewrite as natural American English:\n\n{text}"
        else:
            user_prompt = f"Translate to {lang_map.get(target_language)}:\n\n{text}"
        
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
                # Сохраняем форматирование абзацев
                if chunk:
                    yield chunk
                
            logger.info(f"✅ Успешный стриминг перевода на {target_language}")
            self.translation_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга перевода: {e}")
            # Fallback - возвращаем оригинал
            yield text
