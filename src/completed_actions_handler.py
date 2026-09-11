"""
Обработчик завершённых действий пользователя.
Детектирует и корректирует offtopic для действий относящихся к школе.
MVP версия для Ukido AI Assistant.
"""

import random
import re
from typing import Dict, List, Optional


def _norm(s: str) -> str:
    """Нижний регистр + ё→е (иначе «счёт» не матчит «счет»)."""
    return s.lower().replace('ё', 'е')


# BUG-02 fix: чужие места/темы — действия с ними никогда не наши.
# Проверяются для ВСЕХ типов (оплата интернета, запись в бассейн,
# форма в поликлинике, пробное в автошколе — всё мимо).
NON_SCHOOL_EXCLUSIONS = [
    'бассейн', 'поликлиник', 'больниц', 'стоматолог', 'кружок', 'секци',
    'садик', 'детский сад', 'футбол', 'football', 'хоккей', 'танц', 'музык',
    'вокал', 'художествен', 'автошкол', 'театр', 'кино',
    'налогов', 'кредит', 'ипотек', 'аренд', 'интернет', 'жкх',
    'свет', 'воду', 'электрич',
    # LANG-05: украинские варианты тех же чужих контекстов
    'поліклінік', 'лікарн', 'гурток', 'садок', 'дитячий садок', 'хокей',
    'музик', 'автошкол', 'кіно', 'податков', 'іпотек', 'оренд', 'жкг',
    'світло', 'воду', 'електрич',
    'gas', 'groceries', 'supermarket', 'restaurant', 'taxi', 'parking',
    'rent', 'utilities',
]

# BUG-02 fix: отрицание/незавершённость НЕПОСРЕДСТВЕННО перед триггером
# (окно ≤3 слов): «ещё не оплатили», "haven't paid for", «хотим записаться».
_NEG_RU = (r'(?:\bне\b|\bнет\b|еще не|пока не|не успели|не смогли|'
           r'не получилось|не вышло|собираюсь|собираемся|планирую|'
           r'планируем|хочу|хотим|думаем|будем|буду|скоро|завтра)')
_NEG_EN = (r"(?:\bnot\b|n[’']t\b|\bnever\b|going to|\bgonna\b|want to|"
           r"\bwanna\b|plan to|planning to|\bwill\b|'ll\b|\bsoon\b|\btomorrow\b)")
# LANG-05: украинские отрицания/планы
_NEG_UK = (r'(?:\bне\b|\bні\b|ще не|поки не|не встигли|не змогли|'
           r'не вийшло|збираюся|збираємося|планую|плануємо|хочу|хочемо|'
           r'думаємо|будемо|буду|скоро|завтра)')


def is_negated_before(message_lower: str, keyword: str) -> bool:
    """True, если перед триггером в окне ≤3 слов стоит отрицание/план."""
    for neg in (_NEG_RU, _NEG_EN, _NEG_UK):
        if re.search(neg + r'[\W_]+(?:\w+[\W_]+){0,3}' + re.escape(keyword),
                      message_lower):
            return True
    return False


def is_conditional_after(message_lower: str, keyword: str) -> bool:
    """True для сослагательного: «записались бы» / «записалися б». Намерение ≠ действие."""
    return re.search(re.escape(keyword) + r'\s+(?:бы|б)\b', message_lower) is not None


# F2/BUG-02: сослагательная частица ПЕРЕД триггером («мы бы записались»,
# «я би записався», «would have paid») — тоже намерение, а не действие.
# Окно ≤3 слов, как у отрицаний.
_COND_BEFORE_RU = r'(?:\bбы\b)'
_COND_BEFORE_UK = r'(?:\bби\b|\bб\b)'
_COND_BEFORE_EN = r'(?:\bwould\b)'


def is_conditional_before(message_lower: str, keyword: str) -> bool:
    """True, если перед триггером в окне ≤3 слов стоит сослагательное «бы/би/would»."""
    for cond in (_COND_BEFORE_RU, _COND_BEFORE_UK, _COND_BEFORE_EN):
        if re.search(cond + r'[\W_]+(?:\w+[\W_]+){0,3}' + re.escape(keyword),
                      message_lower):
            return True
    return False


# BUG-02 fix: триггеры, самодостаточные без школьного контекста.
# Оплата — всегда требует контекст (строго: речь о деньгах, не врём).
# Пробное/форма/документы — все триггеры конкретные фразы, контекста не надо.
STRONG_TYPES = {'trial', 'form', 'documents'}
STRONG_TRIGGERS = {
    'registration': {
        'записали ребенка', 'записал сына', 'записала дочь',
        'подал заявку', 'подала заявку', 'оформил запись', 'оформила запись',
        # LANG-05: uk-варианты
        'записали дитину', 'записав сина', 'записала доньку',
        'подав заявку', 'подала заявку', 'оформив запис', 'оформила запис',
        'signed up', 'i registered', "i've registered", 'registered for',
        'enrolled', 'already registered',
    },
}


class CompletedActionsHandler:
    """
    Обработчик завершённых действий пользователя.
    Детектирует и корректирует offtopic для действий относящихся к школе.
    """
    
    def __init__(self):
        # Паттерны для быстрой детекции
        self.ACTION_PATTERNS = {
            'payment': {
                'keywords': ['оплатил', 'оплатила', 'перевел', 'перевела',
                            'отправил деньги', 'заплатил', 'заплатила', 'внес оплату',
                            'внесла оплату', 'сделал перевод', 'сделала перевод',
                            # LANG-05: uk-триггеры
                            'оплатив', 'оплатила', 'переказав', 'переказала',
                            'відправив гроші', 'заплатив', 'заплатила',
                            'вніс оплату', 'внесла оплату', 'зробив переказ',
                            'зробила переказ',
                            # EN триггеры
                            'i paid', 'i have paid', "i've paid", 'paid for',
                            'made the payment', 'payment sent', 'sent the money',
                            'transferred the money'],
                'school_context': ['курс', 'занятие', 'обучение', 'счет',
                                   'заняття', 'навчання', 'рахунок',
                                   'course', 'class', 'lesson', 'invoice'],
                # Слова-исключения, которые указывают на НЕ школьный контекст
                'exclusion_words': ['бензин', 'продукт', 'магазин', 'кафе', 'ресторан',
                                   'такси', 'парковк', 'штраф', 'коммунал',
                                   # LANG-05: uk
                                   'бензин', 'продукти', 'магазин', 'кафе', 'ресторан',
                                   'таксі', 'парковк', 'штраф', 'комунал',
                                   'gas', 'gasoline', 'groceries', 'supermarket',
                                   'restaurant', 'taxi', 'parking ticket', 'rent', 'utilities'],
                'responses': [
                    "Отлично! Оплата обрабатывается. Менеджер свяжется с вами в течение часа для подтверждения. Есть ещё вопросы?",
                    "Спасибо! Как только платёж пройдёт (обычно до 30 минут), вы получите подтверждение на email. Чем ещё могу помочь?",
                    "Хорошо! После подтверждения оплаты менеджер отправит вам доступы к занятиям. Что ещё вас интересует?"
                ],
                'responses_en': [
                    "Great! Your payment is being processed. Our manager will contact you within an hour to confirm. Any other questions?",
                    "Thank you! Once the payment goes through (usually within 30 minutes), you'll get a confirmation email. Anything else I can help with?",
                    "All set! After the payment is confirmed, our manager will send you the class access details. What else would you like to know?"
                ],
                'implicit_questions': [
                    "Когда будет подтверждение оплаты?",
                    "Что происходит после оплаты?",
                    "Как получить доступ к занятиям?"
                ],
                'implicit_questions_en': [
                    "When will the payment be confirmed?",
                    "What happens after payment?",
                    "How do I get access to the classes?"
                ]
            },
            'registration': {
                'keywords': ['записался', 'записались', 'записалась', 'зарегистрировал',
                            'зарегистрировала', 'зарегистрировались', 'подал заявку',
                            'подала заявку', 'оформил запись', 'оформила запись',
                            # LANG-05: uk-триггеры
                            'записався', 'записалися', 'записалася', 'зареєструвався',
                            'зареєструвала', 'зареєструвалися', 'подав заявку',
                            'подала заявку', 'оформив запис', 'оформила запис',
                            # EN триггеры
                            'signed up', 'i registered', "i've registered",
                            'registered for', 'enrolled'],
                'school_context': ['курс', 'занятие', 'пробное', 'группа', 'запис',
                                   'заняття', 'пробне', 'група',
                                   'course', 'class', 'trial', 'group', 'sign'],
                'responses': [
                    "Прекрасно! Ваша запись принята. Менеджер свяжется для уточнения деталей. Какие у вас есть вопросы?",
                    "Отлично! Вы записаны. За день до занятия придёт напоминание с ссылкой на Zoom. Что ещё хотите узнать?",
                    "Супер! Запись оформлена. В ближайшее время с вами свяжется менеджер. Чем ещё могу помочь?"
                ],
                'responses_en': [
                    "Wonderful! Your spot is reserved. Our manager will reach out to confirm the details. Do you have any questions?",
                    "Great, you're signed up! You'll get a reminder with the Zoom link the day before the class. Anything else you'd like to know?",
                    "Awesome! Your registration is complete. Our manager will contact you shortly. What else can I help with?"
                ],
                'implicit_questions': [
                    "Когда начинаются занятия?",
                    "Что нужно подготовить к первому занятию?",
                    "Как проходят занятия?"
                ],
                'implicit_questions_en': [
                    "When do the classes start?",
                    "What should we prepare for the first class?",
                    "How do the classes work?"
                ]
            },
            'form': {
                'keywords': ['заполнил форму', 'заполнила форму', 'отправил анкету',
                            'отправила анкету', 'заполнил заявку', 'заполнила заявку',
                            'оформил заявку', 'оформила заявку', 'заполнил на сайте',
                            'заполнила на сайте',
                            # LANG-05: uk-триггеры
                            'заповнив форму', 'заповнила форму', 'відправив анкету',
                            'відправила анкету', 'заповнив заявку', 'заповнила заявку',
                            'оформив заявку', 'оформила заявку', 'заповнив на сайті',
                            'заповнила на сайті',
                            # EN триггеры
                            'filled the form', 'filled out the form', 'filled in the form',
                            'completed the form', 'submitted the form',
                            'sent the application', 'submitted the application'],
                'school_context': ['сайт', 'форм', 'анкет', 'заявк',
                                   'form', 'application', 'website', 'site'],
                'responses': [
                    "Спасибо! Мы получили вашу заявку. Менеджер обработает её и свяжется с вами в течение дня. Есть дополнительные вопросы?",
                    "Отлично! Заявка в обработке. Обычно мы отвечаем в течение 2-3 часов в рабочее время. Чем ещё могу помочь?",
                    "Хорошо! Ваша форма получена. Менеджер скоро с вами свяжется для уточнения деталей. Что ещё вас интересует?"
                ],
                'responses_en': [
                    "Thank you! We've received your request. Our manager will process it and get in touch within a day. Any other questions?",
                    "Great! Your request is being processed. We usually reply within 2-3 hours during business hours. Anything else I can help with?",
                    "Got it! Your form has been received. Our manager will contact you soon to confirm the details. What else would you like to know?"
                ],
                'implicit_questions': [
                    "Когда со мной свяжется менеджер?",
                    "Какие следующие шаги?",
                    "Что происходит после заполнения формы?"
                ],
                'implicit_questions_en': [
                    "When will the manager contact me?",
                    "What are the next steps?",
                    "What happens after submitting the form?"
                ]
            },
            'trial': {
                'keywords': ['был на пробном', 'была на пробном', 'были на пробном',
                            'посетил пробное', 'посетила пробное', 'посетили пробное',
                            'прошли пробное', 'прошёл пробное', 'прошла пробное',
                            'закончили пробное', 'закончил пробное', 'закончила пробное',
                            # LANG-05: uk-триггеры
                            'був на пробному', 'була на пробному', 'були на пробному',
                            'відвідав пробне', 'відвідала пробне', 'відвідали пробне',
                            'пройшли пробне', 'пройшов пробне', 'пройшла пробне',
                            'закінчили пробне', 'закінчив пробне', 'закінчила пробне',
                            # EN триггеры
                            'attended the trial', 'was at the trial', 'went to the trial',
                            'did the trial', 'finished the trial', 'took the trial class'],
                'school_context': ['занятие', 'урок', 'пробн',
                                   'заняття', 'пробне',
                                   'class', 'lesson', 'trial'],
                'responses': [
                    "Здорово! Надеемся, занятие понравилось. Готовы записаться на полный курс? Могу рассказать о скидках для новых учеников.",
                    "Отлично! Как вам пробное занятие? Если готовы продолжить, у нас есть специальное предложение для тех, кто прошёл пробный урок.",
                    "Супер! Рады, что попробовали. Хотите узнать о программе полного курса или есть вопросы по организации занятий?"
                ],
                'responses_en': [
                    "Great! We hope you enjoyed the class. Ready to sign up for the full course? I can tell you about our new-student discounts.",
                    "Awesome! How did you like the trial class? If you're ready to continue, we have a special offer for trial-class graduates.",
                    "Glad you tried it out! Want to hear about the full course program, or do you have questions about how classes are organized?"
                ],
                'implicit_questions': [
                    "Как записаться на полный курс?",
                    "Какие есть скидки после пробного?",
                    "Когда можно начать обучение?"
                ],
                'implicit_questions_en': [
                    "How do I sign up for the full course?",
                    "Are there discounts after the trial?",
                    "When can we start?"
                ]
            },
            'documents': {
                'keywords': ['отправил документы', 'отправила документы', 'прислал документы',
                            'прислала документы', 'загрузил документы', 'загрузила документы',
                            'выслал документы', 'выслала документы',
                            # LANG-05: uk-триггеры
                            'відправив документи', 'відправила документи',
                            'надіслав документи', 'надіслала документи',
                            'завантажив документи', 'завантажила документи',
                            'вислав документи', 'вислала документи',
                            # EN триггеры
                            'sent the documents', 'sent my documents', 'submitted the documents',
                            'uploaded the documents', 'emailed the documents'],
                'school_context': ['документ', 'файл', 'скан', 'копи',
                                   'копі', 'document', 'file', 'scan', 'copy'],
                'responses': [
                    "Спасибо! Документы получены. Менеджер проверит их и свяжется с вами. Есть ещё вопросы?",
                    "Отлично! Мы получили ваши документы. Обработка займёт до одного рабочего дня. Чем ещё могу помочь?"
                ],
                'responses_en': [
                    "Thank you! Documents received. Our manager will review them and get in touch. Any other questions?",
                    "Great! We've got your documents. The review takes up to one business day. Anything else I can help with?"
                ],
                'implicit_questions': [
                    "Когда будет обработка документов?",
                    "Нужны ли дополнительные документы?",
                    "Что происходит после проверки документов?"
                ],
                'implicit_questions_en': [
                    "When will the documents be processed?",
                    "Are any additional documents needed?",
                    "What happens after the review?"
                ]
            }
        }
        
        # Фразы для неопределённых случаев
        self.UNCERTAIN_RESPONSES = [
            "Спасибо за информацию! Чем могу помочь дальше?",
            "Хорошо! Какие у вас есть вопросы по нашим курсам?",
            "Отлично! Что вас интересует - расписание, программа или условия обучения?"
        ]
        # BUG-02 fix: явное «Ukido» — школьный контекст для всех типов.
        # Добавляем программно, чтобы не разъехалось по пяти спискам.
        for _patterns in self.ACTION_PATTERNS.values():
            for _marker in ('ukido', 'укидо'):
                if _marker not in _patterns['school_context']:
                    _patterns['school_context'].append(_marker)
    
    def detect_completed_action(self, message: str, route_result: Dict, history: List) -> Dict:
        """
        Главный метод обработки.
        Проверяет только offtopic сообщения и корректирует при необходимости.
        
        Args:
            message: Сообщение пользователя
            route_result: Результат от Router
            history: История диалога
            
        Returns:
            Корректированный или оригинальный результат Router
        """
        # 1. Работаем только с offtopic
        if route_result.get('status') != 'offtopic':
            return route_result

        # 2. Быстрые проверки для исключения
        message_lower = _norm(message)

        # BUG-02/BUG-09 fix: вопрос — не подтверждение. Проверяем только '?',
        # грубый список слов-маркеров («как», «что», ...) удалён: он отсекал
        # и настоящие подтверждения («Оплатил, как договаривались»).
        if '?' in message_lower:
            return route_result

        # Длинные нарративы не подтверждаем (порог поднят с 10 до 25 слов —
        # короткие подтверждения вида «Оплатил курс вчера вечером» проходят).
        if len(message.split()) > 25:
            return route_result

        # Явное «Ukido» — школа названа, чужие-контексты не проверяем
        # («записались в школу Ukido» — наше, даже со словом «школа»).
        explicit_school = 'ukido' in message_lower or 'укидо' in message_lower

        # 3. Проверяем паттерны действий
        detected_action = None

        for action_type, patterns in self.ACTION_PATTERNS.items():
            keywords = [_norm(kw) for kw in patterns['keywords']]
            matched = [kw for kw in keywords if kw and kw in message_lower]
            if not matched:
                continue

            # 4. Чужие места/темы — никогда не наши действия
            if not explicit_school:
                exclusions = [_norm(w) for w in
                              list(patterns.get('exclusion_words', []))
                              + NON_SCHOOL_EXCLUSIONS]
                if any(ex in message_lower for ex in exclusions):
                    continue

            # 5. Отрицание/план/условие рядом с триггером — не действие.
            # Условие ловим с обеих сторон: «записались бы» и «мы бы записались».
            matched = [kw for kw in matched
                       if not is_negated_before(message_lower, kw)]
            matched = [kw for kw in matched
                       if not is_conditional_after(message_lower, kw)]
            matched = [kw for kw in matched
                       if not is_conditional_before(message_lower, kw)]
            if not matched:
                continue

            # 6. Школьный контекст — в САМОМ сообщении (вне спана триггера),
            # иначе — только в сообщениях user из истории.
            # BUG-02 fix: ответы ассистента больше не считаются контекстом
            # (там «Ukido» почти всегда — фильтр был вакуумным).
            # Оплата требует контекст всегда; пробное/форма/документы и
            # сильные триггеры записи — самодостаточны.
            strong = (action_type in STRONG_TYPES
                      or any(kw in STRONG_TRIGGERS.get(action_type, ())
                             for kw in matched))
            if not strong:
                contexts = [_norm(c) for c in patterns['school_context']]
                masked = message_lower
                for kw in matched:
                    masked = masked.replace(kw, ' ')
                if not any(ctx in masked for ctx in contexts):
                    if not self._check_school_context_in_history(history):
                        continue

            detected_action = action_type
            break

        # 4. Если не нашли действие — оставляем offtopic
        if not detected_action:
            return route_result
        
        # 5. Корректируем результат Router'а
        corrected_result = route_result.copy()
        corrected_result['status'] = 'success'
        corrected_result['_action_detected'] = detected_action  # Для отладки
        corrected_result['_correction_applied'] = 'completed_action'  # Маркер корректировки
        
        # Выбираем подходящий ответ (для EN — из двуязычного словаря,
        # без LLM-перевода; для uk остаётся русский + перевод на шлюзе)
        action_data = self.ACTION_PATTERNS[detected_action]
        if route_result.get('detected_language') == 'en' and 'responses_en' in action_data:
            corrected_result['completed_action_response'] = random.choice(action_data['responses_en'])
            corrected_result['decomposed_questions'] = action_data.get(
                'implicit_questions_en', action_data['implicit_questions'])
        else:
            # Вместо прямой замены message, создаём специальное поле для генератора
            corrected_result['completed_action_response'] = random.choice(action_data['responses'])

            # Генерируем implicit вопросы
            corrected_result['decomposed_questions'] = action_data['implicit_questions']
        
        # Добавляем релевантные документы
        if detected_action == 'payment':
            corrected_result['documents'] = ['pricing.md', 'conditions.md']
        elif detected_action in ['registration', 'trial']:
            corrected_result['documents'] = ['schedule.md', 'methodology.md']
        elif detected_action == 'form':
            corrected_result['documents'] = ['faq.md', 'conditions.md']
        else:
            corrected_result['documents'] = ['faq.md']
        
        # Логируем для отладки
        print(f"🔧 Completed action detected: '{detected_action}' for message: '{message[:50]}...'")
        print(f"   Documents: {corrected_result['documents']}")
        
        return corrected_result
    
    def _check_school_context_in_history(self, history: List) -> bool:
        """
        Проверяет последние 3 пары сообщений на контекст школы.

        BUG-02 fix: смотрятся ТОЛЬКО сообщения пользователя. Ответы
        ассистента исключены — в них «Ukido»/«soft skills» почти всегда,
        из-за чего фильтр пропускал всё подряд.

        Args:
            history: История сообщений

        Returns:
            True если найден контекст школы
        """
        if not history:
            return False
        
        # Ключевые слова, указывающие на контекст школы
        school_keywords = [
            'курс', 'занятие', 'обучение', 'ребенок', 'ребёнок', 'дети', 'детей',
            'программа', 'учитель', 'преподаватель', 'урок', 'группа', 'запись',
            'цена', 'стоимость', 'оплата', 'расписание', 'zoom', 'онлайн',
            'методика', 'навык', 'skill', 'ukido', 'укидо', 'школа',
            # LANG-05: uk-контекст школы
            'заняття', 'навчання', 'дитина', 'діти', 'дітей', 'програма',
            'вчитель', 'викладач', 'група', 'запис', 'ціна', 'вартість',
            'оплата', 'розклад', 'онлайн', 'методика', 'навичк',
            'course', 'class', 'lesson', 'child', 'kid', 'program', 'teacher',
            'group', 'price', 'cost', 'payment', 'schedule', 'online', 'school',
            'trial', 'soft skills'
        ]
        
        # Проверяем последние 6 сообщений (3 пары user-assistant),
        # но читаем только реплики user (см. docstring выше).
        recent_messages = history[-6:] if len(history) >= 6 else history

        for msg in recent_messages:
            if msg.get('role') != 'user':
                continue
            content = _norm(msg.get('content', ''))
            if any(keyword in content for keyword in school_keywords):
                return True

        return False
    
    def get_uncertain_response(self) -> str:
        """
        Возвращает вежливый уточняющий вопрос для неопределённых случаев.
        
        Returns:
            Случайная фраза для уточнения
        """
        return random.choice(self.UNCERTAIN_RESPONSES)