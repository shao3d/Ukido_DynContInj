"""
SimpleCTABlocker - минималистичное решение для блокировки неуместных CTA
MVP версия: только критичный функционал без персистентности
"""

from typing import Dict, Set, Optional, Tuple
import logging

from completed_actions_handler import (
    NON_SCHOOL_EXCLUSIONS,
    is_conditional_after,
    is_negated_before,
)

logger = logging.getLogger(__name__)


class SimpleCTABlocker:
    """
    Минималистичный блокировщик CTA для MVP.
    Отслеживает завершённые действия и отказы в памяти (без персистентности).
    """

    # BUG-03 fix: длительности блока и окно восстановления — в СОБСТВЕННЫХ
    # сообщениях пользователя, а не в длине истории (она обрезается лимитом).
    HARD_BLOCK_MESSAGES = 7
    SOFT_BLOCK_MESSAGES = 3
    # После стольких сообщений без отказов частота CTA полностью
    # восстанавливается (decay модификатора).
    RECOVERY_MESSAGES = 10

    def __init__(self):
        # Хранение только в памяти на время сессии
        self.completed_actions: Dict[str, Set[str]] = {}  # user_id -> set(['paid', 'registered', etc])
        self.refusals: Dict[str, Dict] = {}  # user_id -> {'count': 0, 'block_until_seq': 0, ...}
        # BUG-03 fix: монотонный счётчик сообщений на пользователя.
        # В отличие от len(history) он не упирается в HISTORY_LIMIT,
        # поэтому порог block_until_seq всегда достижим.
        self._message_seq: Dict[str, int] = {}  # user_id -> seq
        
        # Триггеры для детекции завершённых действий
        self.COMPLETION_TRIGGERS = {
            'paid': ['оплатил', 'заплатил', 'внёс оплату', 'перевёл деньги', 'оплачено', 'внесла оплату',
                      # LANG-05: uk
                      'оплатив', 'оплатила', 'сплатив', 'заплатив', 'вніс оплату',
                      'внесла оплату', 'переказав гроші', 'оплачено',
                      'i paid', "i've paid", 'paid for the course', 'made the payment', 'payment sent'],
            'registered': ['записался', 'записалась', 'записались', 'зарегистрировал',
                           'зарегистрировала', 'зарегистрировались', 'записали ребенка',
                           'записал сына', 'записала дочь',
                            # LANG-05: uk
                            'записався', 'записалася', 'записалися', 'зареєструвався',
                            'зареєструвала', 'зареєструвалися', 'записали дитину',
                            'записав сина', 'записала доньку',
                            'signed up', 'i registered', "i've registered", 'already registered', 'enrolled'],
            'trial_completed': ['были на пробном', 'прошли пробное', 'посетили пробный урок',
                                # LANG-05: uk
                                'були на пробному', 'пройшли пробне', 'відвідали пробний урок',
                                'attended the trial', 'did the trial', 'went to the trial'],
            'form_filled': ['заполнил форму', 'заполнила анкету', 'отправил заявку',
                            # LANG-05: uk
                            'заповнив форму', 'заповнила анкету', 'відправив заявку',
                            'надіслав заявку',
                            'filled the form', 'filled out the form', 'submitted the form']
        }

        # Триггеры для детекции отказов
        self.HARD_REFUSALS = [
            'не надо', 'не нужно', 'отстаньте', 'достали', 'надоели',
            'хватит предлагать', 'прекратите', 'не интересно',
            # LANG-05: uk
            'не треба', 'не потрібно', 'відчепіться', 'дістали', 'набридли',
            'досить пропонувати', 'припиніть', 'не цікаво',
            'no thanks', 'stop offering', 'stop pushing', 'leave me alone',
            'not interested', "don't need", 'do not need'
        ]

        self.SOFT_REFUSALS = [
            'я подумаю', 'потом решу', 'позже', 'не сейчас', 'может потом',
            'надо подумать', 'посоветуюсь с мужем', 'посоветуюсь с женой',
            # LANG-05: uk
            'я подумаю', 'потім вирішу', 'пізніше', 'не зараз', 'може потім',
            'треба подумати', 'пораджуся з чоловіком', 'пораджуся з дружиною',
            "i'll think about it", 'maybe later', 'not now', 'need to think',
            'talk to my husband', 'talk to my wife', 'ask my husband', 'ask my wife'
        ]
        
        logger.info("🔧 SimpleCTABlocker инициализирован (MVP версия)")
    
    def check_completed_action(self, user_id: str, message: str) -> Optional[str]:
        """
        Проверяет, содержит ли сообщение информацию о завершённом действии.
        Возвращает тип действия или None.

        BUG-02 fix: отрицания («ещё не оплатили»), условия («записались бы»)
        и чужие контексты («записались в бассейн») действиями не считаются.
        Нормализация ё→е — чтобы «внёс» тоже матчился.
        """
        message_lower = message.lower().replace('ё', 'е')

        # Вопрос — не утверждение («Оплатил?» ≠ «Оплатил»).
        if '?' in message_lower:
            return None

        for action_type, triggers in self.COMPLETION_TRIGGERS.items():
            matched = [t for t in triggers
                       if t.replace('ё', 'е') in message_lower]
            if not matched:
                continue

            # Чужой контекст — не наше действие (кроме явного «Ukido»)
            if 'ukido' not in message_lower and 'укидо' not in message_lower:
                if any(ex in message_lower for ex in NON_SCHOOL_EXCLUSIONS):
                    continue

            # Отрицание/план/условие рядом с триггером — не действие
            alive = [t for t in matched
                     if not is_negated_before(message_lower, t.replace('ё', 'е'))
                     and not is_conditional_after(message_lower, t.replace('ё', 'е'))]
            if not alive:
                continue

            # Сохраняем завершённое действие
            if user_id not in self.completed_actions:
                self.completed_actions[user_id] = set()

            self.completed_actions[user_id].add(action_type)
            logger.info(f"✅ Пользователь {user_id}: зафиксировано действие '{action_type}'")
            return action_type

        return None
    
    def _next_seq(self, user_id: str) -> int:
        """Следующий номер сообщения пользователя (монотонный, без потолка)."""
        self._message_seq[user_id] = self._message_seq.get(user_id, 0) + 1
        return self._message_seq[user_id]

    def _current_seq(self, user_id: str) -> int:
        """Текущий номер сообщения пользователя (без инкремента)."""
        return self._message_seq.get(user_id, 0)

    def check_refusal(self, user_id: str, message: str, current_message_count: int = 0) -> Optional[str]:
        """
        Проверяет, содержит ли сообщение отказ от предложений.
        Возвращает тип отказа ('hard' или 'soft') или None.

        BUG-03 fix: каждое обработанное сообщение двигает внутренний счётчик;
        срок блока отсчитывается от него, а не от длины истории.
        Параметр current_message_count оставлен для совместимости и в
        вычислении срока больше не участвует.
        """
        seq = self._next_seq(user_id)
        message_lower = message.lower()

        # Проверяем жёсткие отказы
        if any(refusal in message_lower for refusal in self.HARD_REFUSALS):
            # Блокируем на HARD_BLOCK_MESSAGES собственных сообщений
            self.refusals[user_id] = {
                'count': self.refusals.get(user_id, {}).get('count', 0) + 1,
                'block_until_seq': seq + self.HARD_BLOCK_MESSAGES,
                'last_refusal_seq': seq,
                'type': 'hard'
            }
            logger.info(f"🚫 Пользователь {user_id}: жёсткий отказ, CTA заблокированы на {self.HARD_BLOCK_MESSAGES} сообщений")
            return 'hard'

        # Проверяем мягкие отказы
        if any(refusal in message_lower for refusal in self.SOFT_REFUSALS):
            # Блокируем на SOFT_BLOCK_MESSAGES собственных сообщений
            self.refusals[user_id] = {
                'count': self.refusals.get(user_id, {}).get('count', 0) + 1,
                'block_until_seq': seq + self.SOFT_BLOCK_MESSAGES,
                'last_refusal_seq': seq,
                'type': 'soft'
            }
            logger.info(f"🟡 Пользователь {user_id}: мягкий отказ, CTA заблокированы на {self.SOFT_BLOCK_MESSAGES} сообщения")
            return 'soft'

        return None
    
    def should_block_cta(self, user_id: str, current_message_count: int = 0, user_signal: str = None) -> Tuple[bool, str]:
        """
        Определяет, нужно ли блокировать CTA для пользователя.
        Возвращает (should_block, reason).

        BUG-03 fix: сверяется с внутренним счётчиком (см. check_refusal),
        current_message_count оставлен для совместимости и игнорируется.
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
            block_until = refusal_data.get('block_until_seq', 0)
            seq = self._current_seq(user_id)
            if seq < block_until:
                remaining = block_until - seq
                logger.info(f"🔒 Блокировка CTA для {user_id}: отказ, осталось {remaining} сообщений")
                return True, f"user_refused_{refusal_data['type']}"

        return False, ""
    
    def get_cta_frequency_modifier(self, user_id: str) -> float:
        """
        Возвращает модификатор частоты CTA на основе истории отказов.
        1.0 = нормальная частота, 0.5 = в два раза реже, и т.д.

        BUG-03 fix: штраф за отказы затухает — после RECOVERY_MESSAGES
        сообщений без отказов частота полностью восстанавливается (1.0).
        Раньше 0.2 оставалось навсегда.
        """
        if user_id not in self.refusals:
            return 1.0

        refusal_data = self.refusals[user_id]
        since_last = self._current_seq(user_id) - refusal_data.get('last_refusal_seq', 0)
        if since_last >= self.RECOVERY_MESSAGES:
            return 1.0

        refusal_count = refusal_data.get('count', 0)

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
            'message_seq': self._current_seq(user_id),
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
        if user_id in self._message_seq:
            del self._message_seq[user_id]
        logger.info(f"🗑️ Данные пользователя {user_id} очищены")