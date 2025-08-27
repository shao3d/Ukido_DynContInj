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
except ImportError:
    # Для случаев, когда модуль импортируется как часть пакета
    from .zhvanetsky_golden import get_mixed_examples, format_examples_for_prompt
    from .zhvanetsky_safety import SafetyChecker, TopicClassifier

logger = logging.getLogger(__name__)


class ZhvanetskyGenerator:
    """Генератор юмора в стиле Жванецкого."""
    
    HUMOR_PROMPT_TEMPLATE = """Ты - дружелюбный консультант детской школы soft skills Ukido.

Контекст диалога:
{dialogue_context}

Родитель спросил не по теме школы: "{message}"

ДВУХЭТАПНЫЙ ПРОЦЕСС СОЗДАНИЯ ШУТКИ:

ШАГ 1: Найди парадокс или абсурд в теме "{message}":
- Какое противоречие есть в этой теме?
- Что в ней неожиданного с точки зрения ребёнка или родителя?
- Какая бытовая ситуация с этим связана?

ШАГ 2: Обыграй через конкретную жизненную ситуацию в школе:
- Представь реальную сценку с детьми
- Используй конкретные детали (автобус, перемена, домашка)
- Говори от лица родителя или ребёнка, НЕ от лица школы

СТРОГО ЗАПРЕЩЕНО:
❌ Структура "X? У нас Y - тоже X, только..."
❌ Фразы "Мы учим/развиваем/готовим"
❌ Прямое упоминание "soft skills", "лидерство", "коммуникация"
❌ Философские обобщения и абстракции
❌ Копирование метафор из примеров

ТРЕБУЕТСЯ:
✅ Конкретная бытовая ситуация (уроки, перемена, родительское собрание)
✅ Неожиданный поворот через детскую логику
✅ Максимум 2 предложения
✅ Юмор БЕЗ назидательности

Примеры ТОЛЬКО для понимания стиля абсурда (НЕ копировать):
{examples}

Ответь ТОЛЬКО готовой шуткой, без объяснений процесса.

Твой ответ в стиле Жванецкого:"""

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
            
            # Получаем примеры для этой категории
            examples = get_mixed_examples(topic_category)
            formatted_examples = format_examples_for_prompt(examples)
            
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
            
            # Формируем промпт
            prompt = self.HUMOR_PROMPT_TEMPLATE.format(
                dialogue_context=dialogue_context,
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
                is_valid, error_reason = self.safety_checker.validate_humor_response(response)
                
                if is_valid:
                    # Успешная генерация (mark_humor_used вызывается в main.py)
                    self.successful_generated += 1
                    
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
            # Увеличиваем температуру для большей креативности
            temperature = getattr(self.config, 'ZHVANETSKY_TEMPERATURE', 1.0)
            
            # Вызываем OpenRouter API через наш client
            messages = [{"role": "user", "content": prompt}]
            
            # Используем async метод chat с параметрами для креативности
            response = await self.client.chat(
                messages=messages,
                max_tokens=150,
                temperature=temperature,
                top_p=0.95,  # Добавляем top_p для большей вариативности
                frequency_penalty=0.5,  # Штраф за повторение слов
                presence_penalty=0.3,   # Поощрение новых тем
                model="anthropic/claude-3.5-haiku"
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
            'sport': "Спорт развивает тело, мы развиваем личность. Что важнее для марафона жизни?",
            'weather': "Погода меняется каждый день, характер ребёнка тоже. Но мы учим управлять вторым.",
            'tech': "Технологии упрощают жизнь, soft skills её усложняют. Но интереснее же со вторым!",
            'food': "Еда питает тело, знания - душу. У нас меню для второго.",
            'transport': "Транспорт везёт тело, мы везём в будущее. Билет недорогой.",
            'general': "Интересная тема! Но умение её обсудить - это уже наша специализация."
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