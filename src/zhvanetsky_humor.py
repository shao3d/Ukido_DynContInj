"""
Модуль генерации юмора в стиле Михаила Жванецкого для offtopic запросов.
Использует Claude Haiku для генерации с учётом контекста и золотого запаса примеров.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.zhvanetsky_golden import get_mixed_examples, format_examples_for_prompt
from src.zhvanetsky_safety import SafetyChecker, TopicClassifier

logger = logging.getLogger(__name__)


class ZhvanetskyGenerator:
    """Генератор юмора в стиле Жванецкого."""
    
    HUMOR_PROMPT_TEMPLATE = """Ты - дружелюбный консультант детской школы soft skills Ukido.

Контекст диалога:
{dialogue_context}

Родитель спросил не по теме школы: "{message}"

Используя стиль Михаила Жванецкого из примеров ниже, создай ОДНУ короткую шутку-ответ (максимум 2 предложения), которая:
1. Мягко и доброжелательно отвечает на вопрос с юмором
2. Содержит неожиданный поворот мысли в стиле Жванецкого
3. Обязательно связывает тему с пользой обучения soft skills в нашей школе
4. НЕ содержит негатива, сарказма или обидных слов

Примеры стиля Жванецкого для вдохновения:
{examples}

ВАЖНО: Ответ должен быть ТОЛЬКО шуткой, без дополнительных объяснений.

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
            
            # Добавляем информацию о user_signal в контекст
            signal_context = {
                'exploring_only': ", родитель изучает варианты",
                'ready_to_buy': ", родитель готов к действию",
                'neutral': ""
            }
            dialogue_context += signal_context.get(user_signal, "")
            
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
                    # Отмечаем успешную генерацию
                    self.safety_checker.mark_humor_used(user_id)
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
            # Используем температуру из конфига или дефолтную
            temperature = getattr(self.config, 'ZHVANETSKY_TEMPERATURE', 0.75)
            
            response = await self.client.generate(
                prompt=prompt,
                max_tokens=150,
                temperature=temperature,
                model="anthropic/claude-3-haiku"  # Явно указываем модель
            )
            
            return response.strip()
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


async def should_use_zhvanetsky(message: str,
                               user_signal: str,
                               history: List[Dict],
                               user_id: str,
                               config,
                               is_pure_social: bool = False) -> Tuple[bool, Dict]:
    """
    Проверяет, нужно ли использовать юмор Жванецкого.
    
    Args:
        message: Сообщение пользователя
        user_signal: Сигнал пользователя
        history: История диалога
        user_id: ID пользователя
        config: Конфигурация
        is_pure_social: Чистый социальный интент
        
    Returns:
        (use_humor, context)
    """
    # Проверяем, включена ли функция
    if not getattr(config, 'ZHVANETSKY_ENABLED', False):
        return False, {'reason': 'feature_disabled'}
    
    # Используем SafetyChecker для комплексной проверки
    safety_checker = SafetyChecker()
    return safety_checker.should_use_humor(
        message=message,
        user_signal=user_signal,
        history=history,
        user_id=user_id,
        is_pure_social=is_pure_social
    )


async def generate_zhvanetsky_response(message: str,
                                      history: List[Dict],
                                      user_signal: str,
                                      user_id: str,
                                      client=None,
                                      config=None) -> Optional[str]:
    """
    Главная функция для генерации юмора Жванецкого.
    
    Args:
        message: Offtopic сообщение
        history: История диалога
        user_signal: Сигнал пользователя
        user_id: ID пользователя
        client: Клиент Claude
        config: Конфигурация
        
    Returns:
        Сгенерированная шутка или None
    """
    generator = ZhvanetskyGenerator(client=client, config=config)
    
    timeout = getattr(config, 'ZHVANETSKY_TIMEOUT', 3.0)
    
    return await generator.generate_humor(
        message=message,
        history=history,
        user_signal=user_signal,
        user_id=user_id,
        timeout=timeout
    )