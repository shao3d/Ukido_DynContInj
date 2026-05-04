"""
Система безопасности для юмора Жванецкого.
Проверяет уместность юмора в зависимости от контекста и темы.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class SafetyChecker:
    """Проверка безопасности и уместности юмора."""
    
    # Блеклист тем, над которыми нельзя шутить
    BLACKLIST_PATTERNS = [
        # Здоровье и болезни
        r'\b(болезн\w*|болеет|болею|болит|болел\w*|заболел\w*|больниц\w*|врач\w*|лечен\w*|операци\w*|диагноз\w*|лекарств\w*|таблетк\w*|укол\w*|скорая|симптом\w*|температур\w*|грипп\w*|ковид\w*|covid\w*|вирус\w*)\b',
        
        # Трагедии и несчастья
        r'\b(умер\w*|погиб\w*|смерт\w*|похорон\w*|кладбищ\w*|могил\w*|траге\w*|авари\w*|катастроф\w*|несчастн\w*|покойн\w*|усоп\w*|скончал\w*)\b',
        
        # Война и насилие
        r'\b(война|войн\w*|бомб\w*|оружи\w*|убив\w*|убий\w*|стрел\w*|взрыв\w*|террор\w*|напад\w*|атак\w*|ракет\w*|снаряд\w*|окоп\w*|фронт\w*)\b',
        
        # Финансовые проблемы
        r'\b(банкрот\w*|долг\w*|кредит\w*|нет денег|безработ\w*|уволен\w*|нищ\w*|бедн\w*|голод\w*|коллектор\w*|просрочк\w*)\b',
        
        # Семейные проблемы
        r'\b(развод\w*|расста\w*|изменя\w*|предател\w*|ссор\w*|сканда\w*|алимент\w*|раздел\w*|бросил\w*|ушел от|ушла от)\b',
        
        # Криминал
        r'\b(украл\w*|воров\w*|мошенн\w*|обман\w*|полици\w*|тюрьм\w*|арест\w*|суд\w*|преступ\w*|наркот\w*)\b',
        
        # Психологические проблемы
        r'\b(депресс\w*|суицид\w*|самоубий\w*|психиатр\w*|психушк\w*|сошел с ума|нервн\w*|паник\w*|истерик\w*)\b'
    ]
    
    # Темы, требующие особой осторожности
    SENSITIVE_TOPICS = [
        r'\b(религи|церков|священ|молитв|бог|аллах|будд|христ|мусульм|иуде|свят)\b',
        r'\b(политик|президент|правительств|министр|выбор|партии|оппозиц)\b',
        r'\b(национальност|раса|этнос|мигрант|беженц)\b'
    ]
    
    # Индикаторы негативного настроения в диалоге
    NEGATIVE_MOOD_MARKERS = [
        'не нравится', 'плохо', 'ужасно', 'отвратительно',
        'возмутительно', 'разочарован', 'обман', 'развод для лохов',
        'кошмар', 'безобразие', 'позор', 'стыд',
        'надоело', 'достало', 'бесит', 'раздражает'
    ]
    
    # Позитивные маркеры для увеличения вероятности
    POSITIVE_MOOD_MARKERS = [
        'спасибо', 'отлично', 'здорово', 'супер', 
        'классно', 'интересно', 'круто', 'замечательно',
        'понравилось', 'рад', 'доволен', 'хорошо'
    ]
    
    def __init__(self):
        self.user_humor_count = defaultdict(list)  # user_id -> список timestamp
        
    def is_safe_topic(self, message: str) -> bool:
        """
        Проверяет, безопасна ли тема для юмора.
        
        Args:
            message: Сообщение пользователя
            
        Returns:
            True если тема безопасна
        """
        message_lower = message.lower()
        
        # Проверяем блеклист
        for pattern in self.BLACKLIST_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return False
        
        return True
    
    def check_user_signal(self, user_signal: str) -> bool:
        """
        Проверяет, подходит ли user_signal для юмора.
        
        Args:
            user_signal: Сигнал пользователя
            
        Returns:
            True если можно шутить
        """
        # Никогда не шутим при тревоге или чувствительности к цене
        forbidden_signals = ["anxiety_about_child", "price_sensitive"]
        result = user_signal not in forbidden_signals
        
        # Отладочный вывод
        print(f"🔍 DEBUG check_user_signal: signal='{user_signal}', forbidden={forbidden_signals}, can_use_humor={result}")
        
        return result
    
    def analyze_dialogue_mood(self, history: List[Dict]) -> str:
        """
        Анализирует настроение в истории диалога.
        
        Args:
            history: История сообщений
            
        Returns:
            'positive', 'negative' или 'neutral'
        """
        if not history:
            return 'neutral'
        
        # Анализируем последние 5 сообщений
        recent_messages = history[-5:] if len(history) >= 5 else history
        
        positive_count = 0
        negative_count = 0
        
        for msg in recent_messages:
            if msg.get('role') == 'user':
                text = msg.get('content', '').lower()
                
                # Проверяем негативные маркеры
                for marker in self.NEGATIVE_MOOD_MARKERS:
                    if marker in text:
                        negative_count += 1
                        break
                
                # Проверяем позитивные маркеры
                for marker in self.POSITIVE_MOOD_MARKERS:
                    if marker in text:
                        positive_count += 1
                        break
        
        if negative_count > 0:
            return 'negative'
        elif positive_count >= 2:
            return 'positive'
        else:
            return 'neutral'
    
    def check_rate_limit(self, user_id: str, max_per_hour: int = 3) -> bool:
        """
        Проверяет rate limit для пользователя.
        
        Args:
            user_id: ID пользователя
            max_per_hour: Максимум шуток в час
            
        Returns:
            True если можно показать шутку
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Очищаем старые записи
        if user_id in self.user_humor_count:
            self.user_humor_count[user_id] = [
                ts for ts in self.user_humor_count[user_id] 
                if ts > hour_ago
            ]
        
        # Проверяем количество
        if len(self.user_humor_count.get(user_id, [])) >= max_per_hour:
            return False
        
        return True
    
    def mark_humor_used(self, user_id: str):
        """Отмечает использование юмора для пользователя."""
        self.user_humor_count[user_id].append(datetime.now())
    
    def calculate_probability(self, 
                            user_signal: str, 
                            mood: str,
                            is_first_message: bool = False,
                            base_probability: float = 0.33) -> float:
        """
        Рассчитывает адаптивную вероятность использования юмора.
        
        Args:
            user_signal: Сигнал пользователя
            mood: Настроение диалога
            is_first_message: Первое ли это сообщение
            base_probability: Базовая вероятность
            
        Returns:
            Финальная вероятность (0.0 - 1.0)
        """
        probability = base_probability
        
        # Модификаторы по user_signal
        if user_signal == "exploring_only":
            probability *= 1.25  # Увеличиваем для исследователей (было 1.2)
        elif user_signal == "ready_to_buy":
            probability *= 0.9  # Чуть уменьшаем для готовых купить (было 0.8)
        
        # Модификаторы по настроению
        if mood == 'positive':
            probability *= 1.2  # Увеличено с 1.1 для демо
        elif mood == 'negative':
            probability = 0.0  # Никогда при негативе
        
        # Осторожнее в начале диалога (но не слишком)
        if is_first_message:
            probability *= 0.95  # Изменено с 0.9 → 0.95 для MVP демонстраций
        
        # Ограничиваем максимум до 90% для MVP демонстраций
        return min(probability, 0.90)  # Увеличено до 90% для достижения 50% юмора в offtopic
    
    def validate_humor_response(self, response: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует сгенерированный юмористический ответ.
        
        Args:
            response: Сгенерированный ответ
            
        Returns:
            (is_valid, error_reason)
        """
        # КРИТИЧЕСКАЯ ПРОВЕРКА: блокируем метаданные
        if "Этот ответ:" in response:
            logger.error("🚫 Обнаружены метаданные 'Этот ответ:' в ответе юмора")
            return False, "metadata_detected"
        
        if "✅" in response or "❌" in response or "✓" in response:
            logger.error("🚫 Обнаружены галочки/крестики в ответе юмора")
            return False, "checkmarks_detected"
        
        # Проверка на аналитические фразы
        analytical_phrases = ["Отражает парадокс", "Показывает абсурд", "Легко и с юмором", 
                            "Не упоминает напрямую", "В стиле Жванецкого", "Короткий и емкий"]
        response_lower = response.lower()
        for phrase in analytical_phrases:
            if phrase.lower() in response_lower:
                logger.error(f"🚫 Обнаружена аналитическая фраза: '{phrase}'")
                return False, "analytical_metadata"
        
        # Проверка длины (увеличено для более философских размышлений)
        if len(response) > 600:  # Увеличено с 400 для парадоксов Жванецкого
            return False, "too_long"
        
        sentences = response.count('.') + response.count('!') + response.count('?')
        if sentences > 5:  # Увеличено с 3 для развёрнутых парадоксов
            return False, "too_many_sentences"
        
        # Проверка на связь со школой (ОСЛАБЛЕНА для MVP)
        # Закомментировано: слишком строгая проверка отклоняет хорошие шутки
        # school_keywords = ['навык', 'учим', 'учат', 'развив', 'ребен', 'ребёнок',
        #                   'дети', 'детей', 'школ', 'ukido', 'курс', 'заняти',
        #                   'soft skills', 'софт скилл']
        # 
        response_lower = response.lower()
        # has_school_reference = any(keyword in response_lower for keyword in school_keywords)
        # 
        # if not has_school_reference:
        #     return False, "no_school_reference"
        
        # Проверка на негативные слова
        negative_words = ['плохо', 'ужасно', 'кошмар', 'идиот', 'дурак', 'тупой']
        has_negative = any(word in response_lower for word in negative_words)
        
        if has_negative:
            return False, "negative_content"
        
        return True, None
    
    def should_use_humor(self,
                         message: str,
                         user_signal: str,
                         history: List[Dict],
                         user_id: str,
                         is_pure_social: bool = False,
                         base_probability: float = 0.33,
                         message_count: int = 0) -> Tuple[bool, Dict]:
        """
        Комплексная проверка - можно ли использовать юмор.
        
        Args:
            message: Сообщение пользователя
            user_signal: Сигнал пользователя
            history: История диалога
            user_id: ID пользователя
            is_pure_social: Чистый социальный интент
            
        Returns:
            (can_use_humor, context_dict)
        """
        context = {
            'safe_topic': True,
            'appropriate_signal': True,
            'good_mood': True,
            'within_rate_limit': True,
            'probability': 0.0,
            'reason': None
        }

        # Блокировка юмора для первого сообщения пользователя
        if message_count <= 1:
            print(f"🛡️ Zhvanetsky humor blocked: first message protection for user {user_id}")
            context['reason'] = 'first_message_protection'
            return False, context

        # Никогда для чистых социальных интентов
        if is_pure_social:
            context['reason'] = 'pure_social_intent'
            return False, context
        
        # Блокируем юмор для коротких сообщений (acknowledgments)
        clean_msg = message.strip()
        if len(clean_msg) < 10 and "?" not in clean_msg:
            context['reason'] = 'short_acknowledgment_message'
            return False, context
        
        # Проверка темы
        if not self.is_safe_topic(message):
            context['safe_topic'] = False
            context['reason'] = 'unsafe_topic'
            return False, context
        
        # Проверка user_signal
        if not self.check_user_signal(user_signal):
            context['appropriate_signal'] = False
            context['reason'] = f'inappropriate_signal:{user_signal}'
            return False, context
        
        # Проверка настроения
        mood = self.analyze_dialogue_mood(history)
        if mood == 'negative':
            context['good_mood'] = False
            context['reason'] = 'negative_mood'
            return False, context
        
        # Проверка rate limit
        if not self.check_rate_limit(user_id):
            context['within_rate_limit'] = False
            context['reason'] = 'rate_limit_exceeded'
            return False, context
        
        # Рассчитываем вероятность
        is_first = len(history) <= 2
        probability = self.calculate_probability(user_signal, mood, is_first, base_probability)
        context['probability'] = probability
        context['mood'] = mood
        
        # Применяем вероятность
        import random
        if random.random() > probability:
            context['reason'] = 'probability_check_failed'
            return False, context
        
        return True, context


class TopicClassifier:
    """Классификатор тем для offtopic сообщений."""
    
    TOPIC_PATTERNS = {
        'sport': [
            r'\b(футбол|баскетбол|волейбол|теннис|бокс|плаван|бег|фитнес|йог|спорт|тренировк|матч|игр|команд)\w*\b',
        ],
        'weather': [
            r'\b(погод|дождь|снег|солнц|ветер|холод|жарк|тепл|мороз|туман|гроз|ливень|метель)\w*\b',
        ],
        'tech': [
            r'\b(компьютер|телефон|интернет|сайт|приложени|программ|код|iphone|айфон|андроид|гаджет|девайс|chatgpt|ai|tiktok|instagram|соцсет|крипт|биткоин|метавселен)\w*\b',
        ],
        'food': [
            r'\b(еда|есть|кушать|завтрак|обед|ужин|борщ|суп|пицц|кофе|чай|сладк|торт|диет|вегетариан|доставк|ресторан|кафе)\w*\b',
        ],
        'transport': [
            r'\b(машин|автомобил|автобус|метро|такси|самолет|поезд|велосипед|самокат|пробк|дорог|светофор|парковк)\w*\b',
        ]
    }
    
    @classmethod
    def classify(cls, message: str) -> str:
        """
        Классифицирует сообщение по теме.
        
        Args:
            message: Сообщение для классификации
            
        Returns:
            Название категории или 'general'
        """
        message_lower = message.lower()
        
        for category, patterns in cls.TOPIC_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return category
        
        return 'general'