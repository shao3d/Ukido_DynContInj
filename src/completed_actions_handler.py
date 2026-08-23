"""
Обработчик завершённых действий пользователя.
Детектирует и корректирует offtopic для действий относящихся к школе.
MVP версия для Ukido AI Assistant.
"""

import random
from typing import Dict, List, Optional


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
                            # EN триггеры
                            'i paid', 'i have paid', "i've paid", 'paid for',
                            'made the payment', 'payment sent', 'sent the money',
                            'transferred the money'],
                'school_context': ['курс', 'занятие', 'обучение', 'счет',
                                   'course', 'class', 'lesson', 'invoice'],
                # Слова-исключения, которые указывают на НЕ школьный контекст
                'exclusion_words': ['бензин', 'продукт', 'магазин', 'кафе', 'ресторан',
                                   'такси', 'парковк', 'штраф', 'коммунал',
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
                            # EN триггеры
                            'signed up', 'i registered', "i've registered",
                            'registered for', 'enrolled'],
                'school_context': ['курс', 'занятие', 'пробное', 'группа', 'запис',
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
                            # EN триггеры
                            'attended the trial', 'was at the trial', 'went to the trial',
                            'did the trial', 'finished the trial', 'took the trial class'],
                'school_context': ['занятие', 'урок', 'пробн',
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
                            # EN триггеры
                            'sent the documents', 'sent my documents', 'submitted the documents',
                            'uploaded the documents', 'emailed the documents'],
                'school_context': ['документ', 'файл', 'скан', 'копи',
                                   'document', 'file', 'scan', 'copy'],
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
        message_lower = message.lower()
        
        # Исключаем вопросы
        question_markers = ['?', 'как', 'что', 'когда', 'где', 'почему', 'зачем', 
                           'сколько', 'какой', 'какая', 'какие', 'куда', 'откуда']
        if any(word in message_lower for word in question_markers):
            return route_result
        
        # Исключаем длинные сообщения (вероятно не действия)
        if len(message.split()) > 10:
            return route_result
        
        # 3. Проверяем паттерны действий
        detected_action = None
        is_school_related = False
        
        for action_type, patterns in self.ACTION_PATTERNS.items():
            # Проверяем ключевые слова действия
            if any(keyword in message_lower for keyword in patterns['keywords']):
                detected_action = action_type
                
                # Проверяем слова-исключения (если есть)
                if 'exclusion_words' in patterns:
                    if any(excl in message_lower for excl in patterns['exclusion_words']):
                        # Найдено исключающее слово - это НЕ про школу
                        detected_action = None
                        continue
                
                # Специальная проверка для слов "перевод" и "оплатил" - требуют явный контекст
                if detected_action == 'payment':
                    # Проверяем, есть ли в сообщении только общие слова оплаты без контекста
                    payment_only_words = ['оплатил', 'оплатила', 'перевел', 'перевела', 'перевод',
                                          'i paid', 'paid', 'payment sent', 'made the payment']
                    has_only_payment = any(word in message_lower for word in payment_only_words)
                    has_school_context = any(word in message_lower for word in
                                             ['курс', 'занят', 'обучен', 'школ', 'ukido',
                                              'course', 'class', 'lesson', 'school', 'ukido'])
                    
                    if has_only_payment and not has_school_context:
                        # Проверяем историю на наличие контекста школы
                        if not self._check_school_context_in_history(history):
                            # Нет контекста школы ни в сообщении, ни в истории - пропускаем
                            detected_action = None
                            continue
                
                # Проверяем контекст школы в самом сообщении
                if any(context in message_lower for context in patterns['school_context']):
                    is_school_related = True
                    break
                
                # Проверяем контекст в истории (последние 3 пары сообщений)
                if self._check_school_context_in_history(history):
                    is_school_related = True
                    break
        
        # 4. Если не нашли действие или оно не про школу - оставляем offtopic
        if not detected_action or not is_school_related:
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
        print(f"   School context: {is_school_related}, Documents: {corrected_result['documents']}")
        
        return corrected_result
    
    def _check_school_context_in_history(self, history: List) -> bool:
        """
        Проверяет последние 3 пары сообщений на контекст школы.
        
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
            'course', 'class', 'lesson', 'child', 'kid', 'program', 'teacher',
            'group', 'price', 'cost', 'payment', 'schedule', 'online', 'school',
            'trial', 'soft skills'
        ]
        
        # Проверяем последние 6 сообщений (3 пары user-assistant)
        recent_messages = history[-6:] if len(history) >= 6 else history
        
        for msg in recent_messages:
            content = msg.get('content', '').lower()
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