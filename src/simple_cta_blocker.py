"""
SimpleCTABlocker - минималистичное решение для блокировки неуместных CTA
MVP версия: только критичный функционал без персистентности
"""

from typing import Dict, Set, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SimpleCTABlocker:
    """
    Минималистичный блокировщик CTA для MVP.
    Отслеживает завершённые действия и отказы в памяти (без персистентности).
    """
    
    def __init__(self):
        # Хранение только в памяти на время сессии
        self.completed_actions: Dict[str, Set[str]] = {}  # user_id -> set(['paid', 'registered', etc])
        self.refusals: Dict[str, Dict] = {}  # user_id -> {'count': 0, 'block_until_message': 0}
        
        # Триггеры для детекции завершённых действий
        self.COMPLETION_TRIGGERS = {
            'paid': ['оплатил', 'заплатил', 'внёс оплату', 'перевёл деньги', 'оплачено', 'внесла оплату',
                     'i paid', "i've paid", 'paid for the course', 'made the payment', 'payment sent'],
            'registered': ['записался', 'записалась', 'зарегистрировал', 'записали ребенка', 'записал сына', 'записала дочь',
                           'signed up', 'i registered', "i've registered", 'already registered', 'enrolled'],
            'trial_completed': ['были на пробном', 'прошли пробное', 'посетили пробный урок',
                                'attended the trial', 'did the trial', 'went to the trial'],
            'form_filled': ['заполнил форму', 'заполнила анкету', 'отправил заявку',
                            'filled the form', 'filled out the form', 'submitted the form']
        }

        # Триггеры для детекции отказов
        self.HARD_REFUSALS = [
            'не надо', 'не нужно', 'отстаньте', 'достали', 'надоели',
            'хватит предлагать', 'прекратите', 'не интересно',
            'no thanks', 'stop offering', 'stop pushing', 'leave me alone',
            'not interested', "don't need", 'do not need'
        ]

        self.SOFT_REFUSALS = [
            'я подумаю', 'потом решу', 'позже', 'не сейчас', 'может потом',
            'надо подумать', 'посоветуюсь с мужем', 'посоветуюсь с женой',
            "i'll think about it", 'maybe later', 'not now', 'need to think',
            'talk to my husband', 'talk to my wife', 'ask my husband', 'ask my wife'
        ]
        
        logger.info("🔧 SimpleCTABlocker инициализирован (MVP версия)")
    
    def check_completed_action(self, user_id: str, message: str) -> Optional[str]:
        """
        Проверяет, содержит ли сообщение информацию о завершённом действии.
        Возвращает тип действия или None.
        """
        message_lower = message.lower()
        
        for action_type, triggers in self.COMPLETION_TRIGGERS.items():
            if any(trigger in message_lower for trigger in triggers):
                # Сохраняем завершённое действие
                if user_id not in self.completed_actions:
                    self.completed_actions[user_id] = set()
                
                self.completed_actions[user_id].add(action_type)
                logger.info(f"✅ Пользователь {user_id}: зафиксировано действие '{action_type}'")
                return action_type
        
        return None
    
    def check_refusal(self, user_id: str, message: str, current_message_count: int) -> Optional[str]:
        """
        Проверяет, содержит ли сообщение отказ от предложений.
        Возвращает тип отказа ('hard' или 'soft') или None.
        """
        message_lower = message.lower()
        
        # Проверяем жёсткие отказы
        if any(refusal in message_lower for refusal in self.HARD_REFUSALS):
            # Блокируем на 7 сообщений
            self.refusals[user_id] = {
                'count': self.refusals.get(user_id, {}).get('count', 0) + 1,
                'block_until_message': current_message_count + 7,
                'type': 'hard'
            }
            logger.info(f"🚫 Пользователь {user_id}: жёсткий отказ, CTA заблокированы до сообщения {current_message_count + 7}")
            return 'hard'
        
        # Проверяем мягкие отказы
        if any(refusal in message_lower for refusal in self.SOFT_REFUSALS):
            # Блокируем на 3 сообщения
            self.refusals[user_id] = {
                'count': self.refusals.get(user_id, {}).get('count', 0) + 1,
                'block_until_message': current_message_count + 3,
                'type': 'soft'
            }
            logger.info(f"🟡 Пользователь {user_id}: мягкий отказ, CTA заблокированы до сообщения {current_message_count + 3}")
            return 'soft'
        
        return None
    
    def should_block_cta(self, user_id: str, current_message_count: int, user_signal: str = None) -> Tuple[bool, str]:
        """
        Определяет, нужно ли блокировать CTA для пользователя.
        Возвращает (should_block, reason).
        """
        
        # Проверяем завершённые действия
        if user_id in self.completed_actions:
            actions = self.completed_actions[user_id]
            
            # Если оплатил - блокируем CTA про оплату и скидки
            if 'paid' in actions and user_signal in ['price_sensitive', 'ready_to_buy']:
                logger.info(f"🔒 Блокировка CTA для {user_id}: уже оплатил курс")
                return True, "user_already_paid"
            
            # Если записался - не предлагаем записаться снова
            if 'registered' in actions and user_signal == 'ready_to_buy':
                logger.info(f"🔒 Блокировка CTA для {user_id}: уже записан")
                return True, "user_already_registered"
            
            # Если прошёл пробное - не предлагаем пробное снова
            if 'trial_completed' in actions:
                # Можем предложить полный курс, но не пробное
                pass
        
        # Проверяем отказы
        if user_id in self.refusals:
            refusal_data = self.refusals[user_id]
            if current_message_count < refusal_data['block_until_message']:
                remaining = refusal_data['block_until_message'] - current_message_count
                logger.info(f"🔒 Блокировка CTA для {user_id}: отказ, осталось {remaining} сообщений")
                return True, f"user_refused_{refusal_data['type']}"
        
        return False, ""
    
    def get_cta_frequency_modifier(self, user_id: str) -> float:
        """
        Возвращает модификатор частоты CTA на основе истории отказов.
        1.0 = нормальная частота, 0.5 = в два раза реже, и т.д.
        """
        if user_id not in self.refusals:
            return 1.0
        
        refusal_count = self.refusals[user_id].get('count', 0)
        
        if refusal_count >= 3:
            return 0.2  # Очень редко (20% от нормы)
        elif refusal_count >= 2:
            return 0.4  # Реже (40% от нормы)
        elif refusal_count >= 1:
            return 0.7  # Немного реже (70% от нормы)
        
        return 1.0
    
    def get_user_status(self, user_id: str) -> Dict:
        """
        Возвращает полный статус пользователя для отладки.
        """
        return {
            'completed_actions': list(self.completed_actions.get(user_id, set())),
            'refusal_data': self.refusals.get(user_id, {}),
            'has_paid': 'paid' in self.completed_actions.get(user_id, set()),
            'has_registered': 'registered' in self.completed_actions.get(user_id, set())
        }
    
    def clear_user_data(self, user_id: str):
        """
        Очищает данные пользователя (для тестирования).
        """
        if user_id in self.completed_actions:
            del self.completed_actions[user_id]
        if user_id in self.refusals:
            del self.refusals[user_id]
        logger.info(f"🗑️ Данные пользователя {user_id} очищены")