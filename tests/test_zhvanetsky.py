"""
Тесты для системы юмора Жванецкого.
Проверяет безопасность, классификацию и генерацию.
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from zhvanetsky_safety import SafetyChecker, TopicClassifier
from zhvanetsky_humor import ZhvanetskyGenerator, should_use_zhvanetsky, generate_zhvanetsky_response
from zhvanetsky_golden import get_examples_for_category, get_mixed_examples, format_examples_for_prompt


class TestSafetyChecker:
    """Тесты для системы безопасности."""
    
    def setup_method(self):
        self.safety_checker = SafetyChecker()
    
    def test_unsafe_topics_detected(self):
        """Проверка обнаружения небезопасных тем."""
        unsafe_messages = [
            "Мой ребёнок заболел гриппом",
            "После развода всё сложно",
            "Война это ужасно",
            "У нас большие долги по кредитам",
            "Вчера была авария на дороге"
        ]
        
        for message in unsafe_messages:
            assert not self.safety_checker.is_safe_topic(message), f"Should detect unsafe: {message}"
    
    def test_safe_topics_allowed(self):
        """Проверка разрешения безопасных тем."""
        safe_messages = [
            "Какая погода будет завтра?",
            "Люблю футбол!",
            "Новый iPhone вышел",
            "Пицца или борщ на обед?",
            "В метро пробки сегодня"
        ]
        
        for message in safe_messages:
            assert self.safety_checker.is_safe_topic(message), f"Should allow safe: {message}"
    
    def test_forbidden_user_signals(self):
        """Проверка запрета юмора для определённых сигналов."""
        assert not self.safety_checker.check_user_signal("anxiety_about_child")
        assert not self.safety_checker.check_user_signal("price_sensitive")
        assert self.safety_checker.check_user_signal("exploring_only")
        assert self.safety_checker.check_user_signal("ready_to_buy")
    
    def test_mood_analysis(self):
        """Проверка анализа настроения диалога."""
        # Негативная история
        negative_history = [
            {"role": "user", "content": "Это просто ужасно!"},
            {"role": "assistant", "content": "Чем могу помочь?"},
            {"role": "user", "content": "Всё плохо, не нравится"}
        ]
        assert self.safety_checker.analyze_dialogue_mood(negative_history) == 'negative'
        
        # Позитивная история
        positive_history = [
            {"role": "user", "content": "Спасибо, очень интересно!"},
            {"role": "assistant", "content": "Рад помочь!"},
            {"role": "user", "content": "Отлично, здорово!"}
        ]
        assert self.safety_checker.analyze_dialogue_mood(positive_history) == 'positive'
        
        # Нейтральная история
        neutral_history = [
            {"role": "user", "content": "Расскажите о курсах"},
            {"role": "assistant", "content": "У нас есть разные программы"}
        ]
        assert self.safety_checker.analyze_dialogue_mood(neutral_history) == 'neutral'
    
    def test_rate_limiting(self):
        """Проверка rate limiting."""
        user_id = "test_user_123"
        
        # Первые 3 раза должны пройти
        for i in range(3):
            assert self.safety_checker.check_rate_limit(user_id)
            self.safety_checker.mark_humor_used(user_id)
        
        # 4-й раз должен быть заблокирован
        assert not self.safety_checker.check_rate_limit(user_id)
    
    def test_probability_calculation(self):
        """Проверка расчёта вероятности."""
        # Для exploring_only вероятность выше
        prob_exploring = self.safety_checker.calculate_probability(
            user_signal="exploring_only",
            mood="neutral",
            is_first_message=False,
            base_probability=0.33
        )
        assert prob_exploring > 0.33
        
        # Для ready_to_buy вероятность ниже
        prob_ready = self.safety_checker.calculate_probability(
            user_signal="ready_to_buy",
            mood="neutral",
            is_first_message=False,
            base_probability=0.33
        )
        assert prob_ready < 0.33
        
        # При негативном настроении вероятность 0
        prob_negative = self.safety_checker.calculate_probability(
            user_signal="exploring_only",
            mood="negative",
            is_first_message=False,
            base_probability=0.33
        )
        assert prob_negative == 0.0
        
        # Для первого сообщения вероятность ниже
        prob_first = self.safety_checker.calculate_probability(
            user_signal="exploring_only",
            mood="neutral",
            is_first_message=True,
            base_probability=0.33
        )
        assert prob_first < prob_exploring
    
    def test_response_validation(self):
        """Проверка валидации сгенерированных ответов."""
        # Хороший ответ
        good_response = "Футбол? У нас тоже команда - только мяч это идеи, а ворота - будущее вашего ребёнка."
        is_valid, error = self.safety_checker.validate_humor_response(good_response)
        assert is_valid
        assert error is None
        
        # Слишком длинный ответ
        long_response = "А" * 350
        is_valid, error = self.safety_checker.validate_humor_response(long_response)
        assert not is_valid
        assert error == "too_long"
        
        # Без связи со школой
        no_school = "Футбол это круто, все любят футбол, давайте поговорим о футболе."
        is_valid, error = self.safety_checker.validate_humor_response(no_school)
        assert not is_valid
        assert error == "no_school_reference"
        
        # С негативом
        negative = "Футбол для идиотов. У нас учат думать, а не бегать как дураки."
        is_valid, error = self.safety_checker.validate_humor_response(negative)
        assert not is_valid
        assert error == "negative_content"


class TestTopicClassifier:
    """Тесты для классификатора тем."""
    
    def test_sport_classification(self):
        """Проверка классификации спортивных тем."""
        sport_messages = [
            "Как думаете, выиграет ли наша команда в футболе?",
            "Начал заниматься боксом",
            "Плавание полезно для здоровья",
            "Йога помогает расслабиться"
        ]
        
        for message in sport_messages:
            assert TopicClassifier.classify(message) == 'sport', f"Should classify as sport: {message}"
    
    def test_weather_classification(self):
        """Проверка классификации погодных тем."""
        weather_messages = [
            "Сегодня дождь целый день",
            "Когда же снег пойдёт?",
            "Жарко очень на улице",
            "Туман с утра был"
        ]
        
        for message in weather_messages:
            assert TopicClassifier.classify(message) == 'weather', f"Should classify as weather: {message}"
    
    def test_tech_classification(self):
        """Проверка классификации технологических тем."""
        tech_messages = [
            "ChatGPT всё знает",
            "Новый iPhone купил",
            "В TikTok залипаю часами",
            "Интернет опять не работает"
        ]
        
        for message in tech_messages:
            assert TopicClassifier.classify(message) == 'tech', f"Should classify as tech: {message}"
    
    def test_general_classification(self):
        """Проверка классификации общих тем."""
        general_messages = [
            "Что вы об этом думаете?",
            "Интересная история",
            "Вчера было весело",
            "Как дела?"
        ]
        
        for message in general_messages:
            assert TopicClassifier.classify(message) == 'general', f"Should classify as general: {message}"


class TestZhvanetskyGenerator:
    """Тесты для генератора юмора."""
    
    def setup_method(self):
        self.generator = ZhvanetskyGenerator(client=None, config=None)
    
    def test_dialogue_context_extraction(self):
        """Проверка извлечения контекста диалога."""
        history = [
            {"role": "user", "content": "Какие курсы есть?"},
            {"role": "assistant", "content": "У нас есть курсы лидерства..."},
            {"role": "user", "content": "А цена какая?"},
            {"role": "assistant", "content": "Стоимость от 5000 грн..."}
        ]
        
        context = self.generator._extract_dialogue_context(history)
        assert "2 вопроса" in context
        assert "курсы" in context
        assert "цены" in context
    
    def test_mock_response_generation(self):
        """Проверка генерации mock ответов."""
        # Для каждой категории должен быть mock ответ
        categories = ['sport', 'weather', 'tech', 'food', 'transport', 'general']
        
        for category in categories:
            response = self.generator._get_mock_response(category)
            assert response is not None
            assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_generate_humor_with_mock(self):
        """Проверка генерации юмора с mock клиентом."""
        response = await self.generator.generate_humor(
            message="Как насчёт футбола?",
            history=[],
            user_signal="exploring_only",
            user_id="test_user",
            timeout=1.0
        )
        
        assert response is not None
        assert "развива" in response  # Должно быть упоминание развития
    
    def test_metrics_collection(self):
        """Проверка сбора метрик."""
        # Начальные метрики
        metrics = self.generator.get_metrics()
        assert metrics['total_generated'] == 0
        assert metrics['success_rate'] == 0.0
        
        # После генерации
        self.generator.total_generated = 10
        self.generator.successful_generated = 8
        self.generator.total_generation_time = 15.0
        
        metrics = self.generator.get_metrics()
        assert metrics['total_generated'] == 10
        assert metrics['successful_generated'] == 8
        assert metrics['success_rate'] == 0.8
        assert metrics['average_generation_time'] == 1.5


class TestGoldenExamples:
    """Тесты для золотого запаса примеров."""
    
    def test_get_examples_for_category(self):
        """Проверка получения примеров для категории."""
        # Для существующей категории
        sport_examples = get_examples_for_category('sport', count=2)
        assert len(sport_examples) == 2
        assert all('topic' in ex and 'example' in ex for ex in sport_examples)
        
        # Для несуществующей категории возвращает general
        unknown_examples = get_examples_for_category('unknown_category', count=2)
        assert len(unknown_examples) == 2
    
    def test_get_mixed_examples(self):
        """Проверка получения смешанных примеров."""
        # С указанием категории
        mixed = get_mixed_examples('sport')
        assert len(mixed) == 4
        
        # Без указания категории
        mixed_general = get_mixed_examples()
        assert len(mixed_general) == 4
    
    def test_format_examples_for_prompt(self):
        """Проверка форматирования примеров для промпта."""
        examples = [
            {"topic": "футбол", "example": "Пример про футбол"},
            {"topic": "погода", "example": "Пример про погоду"}
        ]
        
        formatted = format_examples_for_prompt(examples)
        assert "1. Тема: футбол" in formatted
        assert "2. Тема: погода" in formatted
        assert "Пример про футбол" in formatted
        assert "Пример про погоду" in formatted


class TestIntegration:
    """Интеграционные тесты."""
    
    @pytest.mark.asyncio
    async def test_should_use_zhvanetsky_full_flow(self):
        """Проверка полного флоу определения возможности использования юмора."""
        config = Mock()
        config.ZHVANETSKY_ENABLED = True
        config.ZHVANETSKY_PROBABILITY = 1.0  # Всегда использовать для теста
        
        # Хороший случай - должен разрешить
        with patch('zhvanetsky_humor.SafetyChecker') as MockSafetyChecker:
            mock_checker = MockSafetyChecker.return_value
            mock_checker.should_use_humor.return_value = (True, {'probability': 1.0})
            
            can_use, context = await should_use_zhvanetsky(
                message="Как насчёт футбола?",
                user_signal="exploring_only",
                history=[],
                user_id="test_user",
                config=config,
                is_pure_social=False
            )
            
            assert can_use
            assert 'probability' in context
    
    @pytest.mark.asyncio
    async def test_generate_zhvanetsky_response_full_flow(self):
        """Проверка полного флоу генерации юмора."""
        config = Mock()
        config.ZHVANETSKY_TIMEOUT = 3.0
        config.ZHVANETSKY_TEMPERATURE = 0.75
        
        response = await generate_zhvanetsky_response(
            message="Что думаете про погоду?",
            history=[],
            user_signal="exploring_only",
            user_id="test_user",
            client=None,  # Используем mock
            config=config
        )
        
        assert response is not None
        assert len(response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])