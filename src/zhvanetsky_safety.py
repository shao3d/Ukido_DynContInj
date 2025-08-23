"""
Система безопасности для юмора Жванецкого.
Проверяет уместность юмора в зависимости от контекста и темы.
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

class SafetyChecker:
    """Проверка безопасности и уместности юмора."""
    
    # Блеклист тем, над которыми нельзя шутить
    BLACKLIST_PATTERNS = [
        # Здоровье и болезни
        r'\b(болезн|болеет|болею|болит|болел|заболел|больниц|врач|лечен|операци|диагноз|лекарств|таблетк|укол|скорая|симптом|температура|грипп|ковид|covid|вирус)\b',
        
        # Трагедии и несчастья
        r'\b(умер|погиб|смерт|похорон|кладбищ|могил|траге|авари|катастроф|несчастн|покойн|усоп|скончал)\b',
        
        # Война и насилие
        r'\b(война|войн|бомб|оружи|убив|убий|стрел|взрыв|террор|напад|атак|ракет|снаряд|окоп|фронт)\b',
        
        # Финансовые проблемы
        r'\b(банкрот|долг|кредит|нет денег|безработ|уволен|нищ|бедн|голод|коллектор|просрочк)\b',
        
        # Семейные проблемы
        r'\b(развод|расста|изменя|предател|ссор|сканда|алимент|раздел|бросил|ушел от|ушла от)\b',
        
        # Криминал
        r'\b(украл|воров|мошенн|обман|полици|тюрьм|арест|суд|преступ|наркот)\b',
        
        # Психологические проблемы
        r'\b(депресс|суицид|самоубий|психиатр|психушк|сошел с ума|нервн|паник|истерик)\b'
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
        return user_signal not in forbidden_signals
    
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
            probability *= 1.2  # Увеличиваем для исследователей
        elif user_signal == "ready_to_buy":
            probability *= 0.8  # Уменьшаем для готовых купить
        
        # Модификаторы по настроению
        if mood == 'positive':
            probability *= 1.1
        elif mood == 'negative':
            probability = 0.0  # Никогда при негативе
        
        # Осторожнее в начале диалога
        if is_first_message:
            probability *= 0.5
        
        # Ограничиваем максимум
        return min(probability, 0.5)  # Не больше 50%
    
    def validate_humor_response(self, response: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует сгенерированный юмористический ответ.
        
        Args:
            response: Сгенерированный ответ
            
        Returns:
            (is_valid, error_reason)
        """
        # Проверка длины
        if len(response) > 300:
            return False, "too_long"
        
        sentences = response.count('.') + response.count('!') + response.count('?')
        if sentences > 3:
            return False, "too_many_sentences"
        
        # Проверка на связь со школой
        school_keywords = ['навык', 'учим', 'учат', 'развив', 'ребен', 'ребёнок',
                          'дети', 'детей', 'школ', 'ukido', 'курс', 'заняти',
                          'soft skills', 'софт скилл']
        
        response_lower = response.lower()
        has_school_reference = any(keyword in response_lower for keyword in school_keywords)
        
        if not has_school_reference:
            return False, "no_school_reference"
        
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
                         is_pure_social: bool = False) -> Tuple[bool, Dict]:
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
        
        # Никогда для чистых социальных интентов
        if is_pure_social:
            context['reason'] = 'pure_social_intent'
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
        probability = self.calculate_probability(user_signal, mood, is_first)
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
            r'\b(футбол|баскетбол|волейбол|теннис|бокс|плаван|бег|фитнес|йог|спорт|тренировк|матч|игр|команд)\b',
        ],
        'weather': [
            r'\b(погод|дождь|снег|солнц|ветер|холод|жарк|тепл|мороз|туман|гроз|ливень|метель)\b',
        ],
        'tech': [
            r'\b(компьютер|телефон|интернет|сайт|приложени|программ|код|iphone|айфон|андроид|гаджет|девайс|chatgpt|ai|tiktok|instagram|соцсет|крипт|биткоин|метавселен)\b',
        ],
        'food': [
            r'\b(еда|есть|кушать|завтрак|обед|ужин|борщ|суп|пицц|кофе|чай|сладк|торт|диет|вегетариан|доставк|ресторан|кафе)\b',
        ],
        'transport': [
            r'\b(машин|автомобил|автобус|метро|такси|самолет|поезд|велосипед|самокат|пробк|дорог|светофор|парковк)\b',
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