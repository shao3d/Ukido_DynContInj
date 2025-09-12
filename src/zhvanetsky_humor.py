"""
Модуль генерации юмора в стиле Михаила Жванецкого для offtopic запросов.
Использует Claude Haiku для генерации с учётом контекста и золотого запаса примеров.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    from zhvanetsky_golden import get_mixed_examples, format_examples_for_prompt
    from zhvanetsky_safety import SafetyChecker, TopicClassifier
    from zhvanetsky_online_examples import get_online_examples
except ImportError:
    # Для случаев, когда модуль импортируется как часть пакета
    from .zhvanetsky_golden import get_mixed_examples, format_examples_for_prompt
    from .zhvanetsky_safety import SafetyChecker, TopicClassifier
    try:
        from .zhvanetsky_online_examples import get_online_examples
    except ImportError:
        def get_online_examples(count=3):
            return []

logger = logging.getLogger(__name__)


class ZhvanetskyGenerator:
    """Генератор юмора в стиле Жванецкого."""
    
    HUMOR_PROMPT_TEMPLATE = """Ты - дружелюбный консультант детской ОНЛАЙН школы soft skills Ukido.
ВАЖНО: Школа работает ПОЛНОСТЬЮ ОНЛАЙН через Zoom, офис в Киеве только для консультаций.

Контекст диалога:
{dialogue_context}

Родитель спросил не по теме школы: "{message}"

🚨 КРИТИЧНО: ОТВЕТ ДОЛЖЕН БЫТЬ РОВНО 2 ПРЕДЛОЖЕНИЯ! НЕ 3, НЕ 4 - РОВНО 2!

СУТЬ СТИЛЯ ЖВАНЕЦКОГО:
Жванецкий НЕ шутит каламбурами. Он находит философский парадокс в обыденном.
Его юмор - это горькая правда жизни, сказанная с любовью и точностью.

КАК СОЗДАТЬ ОТВЕТ В СТИЛЕ ЖВАНЕЦКОГО:

1. Найди ПАРАДОКС в вопросе "{message}":
   - Что в этом вопросе одновременно правда и абсурд?
   - Какое противоречие современной жизни это отражает?
   - Как это связано с вечной борьбой родителей за будущее детей?

2. Вырази через КОНКРЕТНЫЙ ОБРАЗ онлайн-обучения:
   - НЕ объясняй шутку, а нарисуй картину
   - Используй СВЕЖИЕ детали: микрофон на mute как новая валюта, фон как статус
   - Покажи абсурд через НОВУЮ обыденность, не из примеров

СТРОГО ЗАПРЕЩЕНО:
❌ Структура "X? У нас Y - тоже X, только..."
❌ Фразы "Мы учим/развиваем/готовим"
❌ Прямое упоминание "soft skills", "лидерство", "коммуникация"
❌ Философские обобщения и абстракции
❌ Копирование метафор из примеров
❌ Упоминание автобусов, перемен, классных комнат, физического присутствия в школе

КРИТИЧЕСКИ ВАЖНО - ИЗБЕГАЙ ЭТИХ ЗАЕЗЖЕННЫХ КЛИШЕ:
⛔ НЕ упоминай кота на клавиатуре или как участника урока
⛔ НЕ говори про ребёнка в пижаме на уроке
⛔ НЕ используй фразу "смотрит в экран"
⛔ НЕ повторяй шутки про "все делают вид что..."
⛔ Найди НОВЫЙ парадокс, которого НЕТ в примерах!

ТРЕБУЕТСЯ:
✅ Философский парадокс через бытовую деталь
✅ Конкретный образ, а не абстракция 
✅ Горькая правда с любовью к жизни
✅ МАКСИМУМ 2 ПРЕДЛОЖЕНИЯ! НЕ БОЛЬШЕ! РОВНО 2!
✅ ВСЕГДА обращайся на "вы" к родителю
✅ Каждое предложение - законченная мысль с точкой

ПРИМЕРЫ ПРАВИЛЬНОЙ КРАТКОСТИ И НОВИЗНЫ:
"Записываемся онлайн, чтобы учиться офлайн от экрана. Логика железная."
"Учим детей будущему, которого сами боимся. Но уверенно учим."
"Ребёнок знает 5 языков программирования и не знает, как завязать шнурки. Приоритеты."

Твои примеры для вдохновения (адаптируй под вопрос):
{examples}

КРИТИЧЕСКИ ВАЖНО:
⚠️ Верни ТОЛЬКО текст шутки - ничего больше!
⚠️ НЕ пиши "Этот ответ:", НЕ добавляй галочки ✅, НЕ объясняй свою логику
⚠️ НЕ заключай ответ в кавычки
⚠️ Просто напиши шутку в стиле Жванецкого и ВСЁ!

Твой ответ (ТОЛЬКО шутка, без метаданных):"""

    def __init__(self, client=None, config=None):
        """
        Инициализация генератора.
        
        Args:
            client: Клиент для Claude Haiku
            config: Конфигурация
        """
        self.client = client
        self.config = config
        self.safety_checker = SafetyChecker()
        self.topic_classifier = TopicClassifier()
        
        # Метрики
        self.total_generated = 0
        self.successful_generated = 0
        self.total_generation_time = 0.0
        
        # Динамическая ротация примеров
        from collections import defaultdict
        self.used_examples_per_user = defaultdict(set)  # user_id -> set of used example indices
        self.last_humor_per_user = defaultdict(list)     # user_id -> list of last 3 generated humors
    
    def _extract_dialogue_context(self, history: List[Dict], limit: int = 5) -> str:
        """
        Извлекает контекст из истории диалога.
        
        Args:
            history: История сообщений
            limit: Максимум сообщений для анализа
            
        Returns:
            Строка с кратким описанием контекста
        """
        if not history:
            return "Начало диалога, родитель только зашёл."
        
        recent = history[-limit:] if len(history) >= limit else history
        
        # Анализируем тематику
        topics_discussed = []
        questions_count = 0
        
        for msg in recent:
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if '?' in content:
                    questions_count += 1
                
                # Простое определение тем
                if any(word in content.lower() for word in ['курс', 'программ', 'заняти']):
                    topics_discussed.append('курсы')
                elif any(word in content.lower() for word in ['цен', 'стои', 'скидк']):
                    topics_discussed.append('цены')
                elif any(word in content.lower() for word in ['учител', 'преподават', 'педагог']):
                    topics_discussed.append('преподаватели')
        
        # Формируем описание
        context_parts = []
        
        if questions_count == 0:
            context_parts.append("Родитель пока не задавал вопросов о школе")
        elif questions_count == 1:
            context_parts.append("Родитель задал один вопрос")
        else:
            context_parts.append(f"Родитель активно интересуется, задал {questions_count} вопроса")
        
        if topics_discussed:
            context_parts.append(f"обсуждали: {', '.join(set(topics_discussed))}")
        
        # Определяем общее настроение
        mood = self.safety_checker.analyze_dialogue_mood(history)
        if mood == 'positive':
            context_parts.append("настроение позитивное")
        elif mood == 'neutral':
            context_parts.append("спокойный тон")
        
        return ". ".join(context_parts) + "."
    
    def _extract_key_words(self, message: str) -> str:
        """Извлекает ключевые слова из сообщения для контекста."""
        # Простое извлечение существительных и глаголов
        import re
        words = re.findall(r'\b[а-яА-ЯёЁa-zA-Z]{3,}\b', message)
        return ', '.join(words[:3]) if words else message[:20]
    
    def _get_time_context(self) -> str:
        """Определяет временной контекст."""
        from datetime import datetime
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "утро"
        elif 12 <= hour < 18:
            return "день"
        elif 18 <= hour < 23:
            return "вечер"
        else:
            return "ночь"
    
    def _convert_to_formal(self, text: str) -> str:
        """
        Конвертирует обращения на "ты" в обращения на "вы".
        
        Args:
            text: Текст для конвертации
            
        Returns:
            Текст с формальными обращениями
        """
        import re
        
        # Словарь замен для всех падежей и форм
        replacements = {
            # Основные местоимения (с учетом регистра)
            r'\bты\b': 'вы',
            r'\bТы\b': 'Вы',
            r'\bтебя\b': 'вас',
            r'\bТебя\b': 'Вас',
            r'\bтебе\b': 'вам',
            r'\bТебе\b': 'Вам',
            r'\bтобой\b': 'вами',
            r'\bТобой\b': 'Вами',
            r'\bтобою\b': 'вами',
            r'\bТобою\b': 'Вами',
            
            # Притяжательные местоимения
            r'\bтвой\b': 'ваш',
            r'\bТвой\b': 'Ваш',
            r'\bтвоя\b': 'ваша',
            r'\bТвоя\b': 'Ваша',
            r'\bтвоё\b': 'ваше',
            r'\bТвоё\b': 'Ваше',
            r'\bтвое\b': 'ваше',
            r'\bТвое\b': 'Ваше',
            r'\bтвои\b': 'ваши',
            r'\bТвои\b': 'Ваши',
            
            # Склонения притяжательных
            r'\bтвоего\b': 'вашего',
            r'\bТвоего\b': 'Вашего',
            r'\bтвоей\b': 'вашей',
            r'\bТвоей\b': 'Вашей',
            r'\bтвоих\b': 'ваших',
            r'\bТвоих\b': 'Ваших',
            r'\bтвоему\b': 'вашему',
            r'\bТвоему\b': 'Вашему',
            r'\bтвоим\b': 'вашим',
            r'\bТвоим\b': 'Вашим',
            r'\bтвоими\b': 'вашими',
            r'\bТвоими\b': 'Вашими',
            
            # Глагольные формы (самые частые)
            r'\bслушай\b': 'слушайте',
            r'\bСлушай\b': 'Слушайте',
            r'\bсмотри\b': 'смотрите',
            r'\bСмотри\b': 'Смотрите',
            r'\bзнаешь\b': 'знаете',
            r'\bЗнаешь\b': 'Знаете',
            r'\bпонимаешь\b': 'понимаете',
            r'\bПонимаешь\b': 'Понимаете',
            r'\bдумаешь\b': 'думаете',
            r'\bДумаешь\b': 'Думаете',
            r'\bхочешь\b': 'хотите',
            r'\bХочешь\b': 'Хотите',
            r'\bможешь\b': 'можете',
            r'\bМожешь\b': 'Можете',
        }
        
        # Применяем замены
        result = text
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result)
        
        # Логируем если были изменения
        if result != text:
            logger.info(f"✅ Конвертация на 'вы': было '{text[:50]}...' → стало '{result[:50]}...'")
        
        return result
    
    async def generate_humor(self, 
                           message: str,
                           history: List[Dict],
                           user_signal: str,
                           user_id: str,
                           timeout: float = 3.0) -> Optional[str]:
        """
        Генерирует юмористический ответ в стиле Жванецкого.
        
        Args:
            message: Offtopic сообщение пользователя
            history: История диалога
            user_signal: Сигнал пользователя
            user_id: ID пользователя
            timeout: Таймаут генерации
            
        Returns:
            Сгенерированная шутка или None при ошибке
        """
        start_time = datetime.now()
        
        try:
            # Классифицируем тему
            topic_category = self.topic_classifier.classify(message)
            
            # Получаем примеры с динамической ротацией
            old_examples = get_mixed_examples(topic_category)
            online_examples = get_online_examples(5)  # Больше примеров для выбора
            
            # Фильтруем уже использованные примеры для этого пользователя
            all_available_examples = []
            for i, ex in enumerate(online_examples + old_examples):
                example_id = f"example_{i}"
                if example_id not in self.used_examples_per_user[user_id]:
                    all_available_examples.append((example_id, ex))
            
            # Если использовали все примеры - сбрасываем историю
            if len(all_available_examples) < 3:
                self.used_examples_per_user[user_id].clear()
                all_available_examples = [(f"example_{i}", ex) for i, ex in enumerate(online_examples + old_examples)]
            
            # Выбираем случайные 3-4 примера
            import random
            selected = random.sample(all_available_examples, min(4, len(all_available_examples)))
            
            # Запоминаем использованные
            for example_id, _ in selected:
                self.used_examples_per_user[user_id].add(example_id)
            
            # Форматируем примеры
            formatted_examples = "\n".join([ex["example"] if isinstance(ex, dict) else ex for _, ex in selected])
            
            # Извлекаем контекст диалога
            dialogue_context = self._extract_dialogue_context(history)
            
            # Добавляем расширенный контекст
            key_words = self._extract_key_words(message)
            time_context = self._get_time_context()
            message_number = len(history)
            
            # Добавляем информацию о user_signal и контексте
            signal_context = {
                'exploring_only': ", родитель изучает варианты",
                'ready_to_buy': ", родитель готов к действию",
                'neutral': ""
            }
            dialogue_context += signal_context.get(user_signal, "")
            dialogue_context += f", время: {time_context}"
            dialogue_context += f", сообщение №{message_number + 1}"
            dialogue_context += f", ключевые слова: {key_words}"
            
            # Добавляем информацию о последних сгенерированных шутках для избежания повторов
            last_humor_context = ""
            if user_id in self.last_humor_per_user and self.last_humor_per_user[user_id]:
                last_3_humors = self.last_humor_per_user[user_id][-3:]
                last_humor_context = "\n\nПоследние шутки этому пользователю (НЕ ПОВТОРЯЙ ИХ ТЕМЫ И ОБРАЗЫ):\n"
                for humor in last_3_humors:
                    # Берём первые 50 символов каждой шутки как напоминание
                    last_humor_context += f"- {humor[:50]}...\n"
            
            # Формируем промпт с дополнительным контекстом
            prompt = self.HUMOR_PROMPT_TEMPLATE.format(
                dialogue_context=dialogue_context + last_humor_context,
                message=message,
                examples=formatted_examples
            )
            
            # Генерируем через Claude Haiku
            if self.client:
                response = await asyncio.wait_for(
                    self._call_claude_haiku(prompt),
                    timeout=timeout
                )
            else:
                # Fallback для тестирования без клиента
                response = self._get_mock_response(topic_category)
            
            # Валидируем ответ
            if response:
                # КРИТИЧЕСКИЙ ПАРСИНГ: убираем метаданные если Claude их добавил
                # Убираем всё после "Этот ответ:" или галочек
                if "Этот ответ:" in response:
                    response = response.split("Этот ответ:")[0].strip()
                    logger.warning("⚠️ Обнаружены метаданные 'Этот ответ:', удалены из ответа")
                
                # Убираем текст с галочками
                if "✅" in response:
                    # Ищем первую галочку и обрезаем всё начиная с неё
                    response = response.split("✅")[0].strip()
                    logger.warning("⚠️ Обнаружены галочки ✅, метаданные удалены")
                
                # Убираем кавычки в начале и конце, если есть
                if response.startswith('"') and response.endswith('"'):
                    response = response[1:-1].strip()
                    logger.info("📝 Убраны кавычки из ответа")
                elif response.startswith('"'):
                    response = response[1:].strip()
                elif response.endswith('"'):
                    response = response[:-1].strip()
                
                # Постпроцессинг: конвертируем "ты" в "вы"
                response = self._convert_to_formal(response)
                
                # Отладочное логирование длины и структуры
                sentences = response.count('.') + response.count('!') + response.count('?')
                logger.info(f"🎭 Generated humor: {len(response)} chars, {sentences} sentences")
                
                is_valid, error_reason = self.safety_checker.validate_humor_response(response)
                
                if is_valid:
                    # Успешная генерация (mark_humor_used вызывается в main.py)
                    self.successful_generated += 1
                    
                    # Сохраняем сгенерированную шутку для избежания повторов
                    if user_id not in self.last_humor_per_user:
                        self.last_humor_per_user[user_id] = []
                    self.last_humor_per_user[user_id].append(response)
                    # Храним только последние 5 шуток
                    if len(self.last_humor_per_user[user_id]) > 5:
                        self.last_humor_per_user[user_id] = self.last_humor_per_user[user_id][-5:]
                    
                    # Логируем успех
                    generation_time = (datetime.now() - start_time).total_seconds()
                    self.total_generation_time += generation_time
                    logger.info(f"🎭 Humor generated: topic={topic_category}, time={generation_time:.2f}s")
                    
                    return response
                else:
                    logger.warning(f"Humor validation failed: {error_reason}")
                    return None
            
        except asyncio.TimeoutError:
            logger.error(f"Humor generation timeout after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Humor generation error: {e}")
            return None
        finally:
            self.total_generated += 1
        
        return None
    
    async def _call_claude_haiku(self, prompt: str) -> Optional[str]:
        """
        Вызывает Claude Haiku для генерации.
        
        Args:
            prompt: Промпт для генерации
            
        Returns:
            Сгенерированный текст
        """
        if not self.client:
            return None
        
        try:
            # УВЕЛИЧИВАЕМ температуру для настоящей креативности Жванецкого
            temperature = getattr(self.config, 'ZHVANETSKY_TEMPERATURE', 1.2)  # Было 1.0
            
            # Вызываем OpenRouter API через наш client
            messages = [{"role": "user", "content": prompt}]
            
            # Параметры для максимальной креативности в стиле Жванецкого
            response = await self.client.chat(
                messages=messages,
                max_tokens=100,  # Ограничиваем для краткости
                temperature=1.0,  # Снизили для более контролируемой креативности
                top_p=0.95,  # Немного сузили выбор слов
                frequency_penalty=1.2,  # УВЕЛИЧИЛИ штраф за повторения!
                presence_penalty=0.8,   # Больше поощрения оригинальности
                model="anthropic/claude-3-haiku"  # Старая версия для эксперимента
            )
            
            # response уже является строкой
            if response:
                return response.strip()
            
            return None
        except Exception as e:
            logger.error(f"Claude Haiku call failed: {e}")
            return None
    
    def _get_mock_response(self, topic_category: str) -> str:
        """
        Возвращает mock ответ для тестирования.
        
        Args:
            topic_category: Категория темы
            
        Returns:
            Mock шутка
        """
        mock_responses = {
            'sport': "Спорт? Сидим дома, учим лидерство. Парадокс? Нет, современность.",
            'weather': "Погода не влияет на онлайн-урок. Но влияет на настроение мамы на фоне. А это важнее.",
            'tech': "Технологии должны упрощать жизнь. Должны. Но у нас родители час ищут кнопку 'поднять руку'.",
            'food': "Ребёнок ест во время урока. В школе - нельзя. Дома - можно. Дома на уроке - философский тупик.",
            'transport': "Дорога в школу - ноль метров. От кровати до компьютера. И всё равно опаздывают.",
            'general': "Мы готовим детей к будущему. К какому - не знаем. Но готовим уверенно."
        }
        
        return mock_responses.get(topic_category, mock_responses['general'])
    
    def get_metrics(self) -> Dict:
        """
        Возвращает метрики работы генератора.
        
        Returns:
            Словарь с метриками
        """
        success_rate = 0.0
        avg_time = 0.0
        
        if self.total_generated > 0:
            success_rate = self.successful_generated / self.total_generated
            avg_time = self.total_generation_time / self.total_generated
        
        return {
            'total_generated': self.total_generated,
            'successful_generated': self.successful_generated,
            'success_rate': success_rate,
            'average_generation_time': avg_time
        }


# Удалены устаревшие функции should_use_zhvanetsky и generate_zhvanetsky_response
# Теперь используем глобальные синглтоны в main.py