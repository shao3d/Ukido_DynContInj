from pathlib import Path
from typing import List, Dict, Optional
from config import Config
from openrouter_client import OpenRouterClient
from standard_responses import DEFAULT_FALLBACK
from offers_catalog import get_offer, get_tone_adaptation, get_dynamic_example
from translator import SmartTranslator
import re

class ResponseGenerator:
    """
    Генератор ответа:
    - Принимает результат роутера (status=success, documents, decomposed_questions)
    - Подгружает MD документы из data/documents_compressed (оптимизированные версии)
    - Собирает составной промпт (системная роль + документы + история[последние 10] + вопросы)
    - Вызывает LLM и возвращает итоговый ответ ассистента
    """

    def __init__(self, docs_dir: Optional[Path] = None):
        self.cfg = Config()  # Сохраняем как атрибут экземпляра для доступа из других методов
        # Используем Claude 3.5 Haiku для одноэтапной генерации с естественным стилем
        self.client = OpenRouterClient(
            self.cfg.OPENROUTER_API_KEY,
            seed=self.cfg.SEED,
            max_tokens=self.cfg.MAX_TOKENS_ANSWER,  # Используем настройку из конфига (1200 токенов)
            temperature=0.1,  # Минимальная температура для точности
            model=self.cfg.MODEL_ANSWER,
        )
        self.docs_dir = docs_dir or (Path(__file__).parent.parent / "data" / "documents_compressed")
        self.history_limit = self.cfg.HISTORY_LIMIT  # Используем настройку из конфига
        self.translator = SmartTranslator(self.client, model=self.cfg.TRANSLATION_MODEL)  # Инициализируем переводчик

    def _debug(self, message: str) -> None:
        if self.cfg.LOG_LEVEL == "DEBUG":
            print(message)

    async def generate(
        self,
        router_result: Dict,
        history: Optional[List[Dict[str, str]]] = None,
        current_message: Optional[str] = None,
    ) -> tuple[str, dict]:
        if router_result.get("status") != "success":
            # Возвращаем tuple с пустой metadata для фоллбэка
            return DEFAULT_FALLBACK, {"intent": "error", "user_signal": "exploring_only", "cta_added": False, "cta_type": None, "humor_generated": False}

        docs = router_result.get("documents") or []
        questions = router_result.get("decomposed_questions") or []
        if not docs or not questions:
            # Возвращаем tuple с пустой metadata для фоллбэка
            return DEFAULT_FALLBACK, {"intent": "error", "user_signal": "exploring_only", "cta_added": False, "cta_type": None, "humor_generated": False}

        # Получаем user_signal для персонализации
        user_signal = router_result.get("user_signal", "exploring_only")
        
        doc_texts = self._load_docs(docs)
        
        # ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ: Если документов не загрузилось - отказываемся отвечать
        if not doc_texts:
            print("⚠️ ЗАЩИТА: Нет загруженных документов для генерации ответа")
            return "К сожалению, у меня нет информации по этому вопросу. Расскажите, что именно вас интересует о школе Ukido?", {"intent": "success", "user_signal": user_signal, "cta_added": False, "cta_type": None, "humor_generated": False}
        
        # Проверяем необходимость CTA ПЕРЕД генерацией
        cta_text = None
        cta_offer = None  # Сохраняем для fallback
        
        # === ПРОВЕРКА БЛОКИРОВКИ CTA ===
        # Получаем параметры блокировки из router_result
        cta_blocked = router_result.get("cta_blocked", False)
        cta_frequency_modifier = router_result.get("cta_frequency_modifier", 1.0)
        block_reason = router_result.get("block_reason", "")
        
        if cta_blocked:
            print(f"🔒 CTA заблокированы: {block_reason}")
            # Пропускаем всю логику CTA если они заблокированы
        else:
            offer = get_offer(user_signal, history)
            if offer and offer["priority"] in ["high", "medium"]:
                self._debug(f"🎯 DEBUG: Есть offer для {user_signal}, проверяем нужно ли добавлять...")
                should_add = self._should_add_offer(user_signal, history, offer, current_message)
                
                # Применяем модификатор частоты
                if should_add and cta_frequency_modifier < 1.0:
                    import random
                    # Уменьшаем вероятность добавления CTA
                    if random.random() > cta_frequency_modifier:
                        should_add = False
                        print(f"📉 CTA пропущен из-за модификатора частоты ({cta_frequency_modifier:.1%})")
                
                self._debug(f"🎯 DEBUG: _should_add_offer вернул: {should_add}")
                if should_add:
                    self._debug(f"🎯 DEBUG: Будем встраивать CTA для {user_signal} органично")
                    cta_offer = offer  # Сохраняем для fallback
                    # Выбираем правильный вариант CTA текста
                    if "text_variants" in offer and offer["text_variants"]:
                        # Подсчитываем, сколько раз CTA уже был показан
                        cta_count = self._count_cta_occurrences(user_signal, history)
                        variant_index = cta_count % len(offer["text_variants"])
                        cta_text = offer["text_variants"][variant_index]
                        print(f"   Используем вариант #{variant_index+1} из {len(offer['text_variants'])}")
                    else:
                        # Используем основной текст
                        cta_text = offer.get("text", "")
                else:
                    self._debug(f"🎯 DEBUG: CTA НЕ будет добавлен для {user_signal}")
        
        # Одноэтапная генерация с Claude Haiku + dynamic few-shot + CTA (если нужен)
        messages = self._build_messages(doc_texts, questions, history or [], router_result, cta_text)

        try:
            reply = await self.client.chat(messages)
            cleaned = (reply or "").strip()
            if not cleaned:
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос.", {"intent": "error", "user_signal": user_signal, "cta_added": False, "cta_type": None, "humor_generated": False}
            
            # Базовая очистка ответа
            sanitized = self._strip_source_citations(cleaned)
            polished = self._remove_question_headings(sanitized)
            humanized = self._humanize_missing_info(polished)
            no_labels = self._strip_service_labels(humanized)
            no_cta = self._strip_generic_cta(no_labels)
            
            # Финальная санитизация (убираем восклицания и дедупликация)
            final_text = self._final_sanitize(no_cta)
            
            # Унификация домена - всегда используем ukido.com.ua
            final_text = final_text.replace("ukido.ua/", "ukido.com.ua/")
            final_text = final_text.replace("ukido.ua ", "ukido.com.ua ")
            final_text = final_text.replace("ukido.ua.", "ukido.com.ua.")
            final_text = final_text.replace("ukido.ua,", "ukido.com.ua,")
            
            # Постпроцессинг: обрабатываем приветствия
            # 1. Исправляем точку на восклицательный знак
            if final_text.startswith("Привет."):
                final_text = "Привет!" + final_text[7:]
                print("✅ Исправлено приветствие: Привет. → Привет!")
            
            # 2. Если был social_context == "greeting" но ответ НЕ начинается с приветствия - добавляем
            social_ctx = router_result.get("social_context")
            self._debug(f"🔍 DEBUG postprocessing: social_context = {social_ctx}, text starts with: {final_text[:30]}...")
            if social_ctx == "greeting":
                greeting_starters = ["привет", "здравствуйте", "добрый день", "добрый вечер", "доброе утро"]
                if not any(final_text.lower().startswith(g) for g in greeting_starters):
                    final_text = "Привет! " + final_text
                    print("✅ Добавлено приветствие в начало ответа")
                
                # ЗАЩИТА: если после приветствия текст слишком короткий, но есть вопросы
                if len(final_text) < 50 and router_result.get("decomposed_questions"):
                    print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: Обнаружен слишком короткий ответ после приветствия: '{final_text}'")
                    # Fallback ответ для mixed интентов
                    if any(word in current_message.lower() for word in ["пустышк", "обманули", "потеря", "плох", "негатив"]):
                        final_text = "Привет! Понимаю ваши сомнения после негативного опыта. В Ukido мы работаем принципиально иначе - мини-группы до 6 человек, профессиональные педагоги-психологи и индивидуальный подход к каждому ребенку. Давайте я подробнее расскажу о наших отличиях."
                    else:
                        final_text = "Привет! Спасибо за ваш вопрос. Давайте я подробно расскажу о нашей школе и чем мы можем помочь вашему ребенку."
                    print("✅ Использован fallback ответ для mixed greeting")
            
            # 3. Добавление контактов при готовности к пробному занятию
            trial_words = ["попроб", "пробн", "давайте попробуем", "хочу попробовать", "запишите на пробное"]
            if current_message and any(word in current_message.lower() for word in trial_words):
                # Проверяем, есть ли уже контакты в ответе (любое упоминание ukido считается контактом)
                if not any(contact in final_text.lower() for contact in ["ukido", "+380", "запишитесь", "запись"]):
                    # Добавляем контактную информацию в конец ответа
                    contact_info = "\n\n📞 Для записи на пробное занятие: ukido.com.ua/trial или позвоните +380 93 567 89 01"
                    final_text = final_text.rstrip() + contact_info
                    print("✅ Добавлены контакты для пробного занятия")
            
            # 4. Обработка непонимания формата обучения (проблема "забирать")
            transport_words = ["забира", "привози", "довози", "везти", "отвози", "вожу", "везу", "заберу", "привезу"]
            if current_message and any(word in current_message.lower() for word in transport_words):
                # Проверяем, упоминается ли уже онлайн в ответе
                if "онлайн" not in final_text.lower() and "zoom" not in final_text.lower() and "из дома" not in final_text.lower():
                    print("🔍 Обнаружено непонимание формата обучения, добавляем уточнение...")
                    
                    # Ищем упоминание времени/расписания для органичной вставки
                    time_patterns = [
                        ("занятия длятся", ", и поскольку обучение проходит онлайн через Zoom, ребёнок занимается из дома"),
                        ("90 минут", " (занятия проходят онлайн через Zoom, забирать не нужно)"),
                        ("с 17:00", ", и удобно, что не нужно никуда ехать - ребёнок учится из дома"),
                        ("с 19:00", ", что удобно для работающих родителей - ребёнок занимается дома через Zoom"),
                        ("два раза в неделю", ". Занятия проходят онлайн, поэтому забирать ребёнка не нужно"),
                        ("расписание", ". Все занятия проходят онлайн через Zoom из дома"),
                        ("время занятий", ", при этом забирать не придётся - обучение полностью онлайн"),
                        ("слот", ", и поскольку занятия онлайн, вам не нужно тратить время на дорогу")
                    ]
                    
                    inserted = False
                    for pattern, insertion in time_patterns:
                        if pattern in final_text.lower() and not inserted:
                            # Находим позицию паттерна и вставляем после него
                            index = final_text.lower().index(pattern)
                            # Ищем конец предложения после паттерна
                            rest = final_text[index:]
                            sentence_end = rest.find(".")
                            if sentence_end == -1:
                                sentence_end = len(rest)
                            
                            # Вставляем уточнение перед точкой
                            insert_pos = index + sentence_end
                            final_text = final_text[:insert_pos] + insertion + final_text[insert_pos:]
                            print(f"✅ Добавлено органичное уточнение про онлайн-формат после '{pattern}'")
                            inserted = True
                            break
                    
                    # Fallback: если не нашли подходящего места, добавляем в начало, но мягко
                    if not inserted:
                        # Выбираем подходящую формулировку в зависимости от контекста
                        if "после работы" in current_message.lower():
                            prefix = "Удобно, что после работы вам не придётся никуда ехать - занятия проходят онлайн через Zoom, ребёнок учится из дома. "
                        elif "далеко" in current_message.lower():
                            prefix = "Отличная новость - не нужно никуда ехать! Все занятия проходят онлайн через Zoom. "
                        else:
                            prefix = "Занятия проходят полностью онлайн через Zoom, поэтому забирать ребёнка не нужно - он учится из дома. "
                        
                        final_text = prefix + final_text
                        print("✅ Добавлено уточнение про онлайн-формат в начало ответа")
            
            # Проверяем, встроил ли Claude CTA (если мы его запрашивали)
            cta_was_added = False
            if cta_text and cta_offer:
                # Определяем контекст агрессивности
                is_aggressive = any(word in current_message.lower() for word in ["развод", "обман", "выкачивание", "мошенники", "враньё"]) if current_message else False
                context_type = "агрессивный" if is_aggressive else "нормальный"
                
                if not self._verify_cta_included(final_text, cta_text):
                    # Fallback: Claude не встроил CTA, добавляем механически
                    print(f"⚠️ ПРОВАЛ: Claude НЕ встроил CTA для {user_signal}")
                    print(f"   Контекст: {context_type}")
                    # Используем self.cfg вместо несуществующего config
                    temperature = getattr(self.cfg, 'TEMPERATURE_BY_SIGNAL', {}).get(user_signal, 0.1)
                    print(f"   Температура: {temperature}")
                    print(f"   CTA текст: '{cta_text[:50]}...'")
                    final_text = self._inject_offer(final_text, cta_offer, user_signal)
                    cta_was_added = True
                else:
                    print(f"✅ УСПЕХ: CTA органично встроен для {user_signal}")
                    print(f"   Контекст: {context_type}")
                    cta_was_added = True
                    # Маркер больше не добавляем к тексту ответа
                    # так как он виден пользователю
            
            # Создаём metadata для ответа
            metadata = {
                "intent": "success",
                "user_signal": user_signal,
                "cta_added": cta_was_added,
                "cta_type": user_signal if cta_was_added else None,
                "humor_generated": False
            }

            # НОВОЕ: Перевод перед возвратом
            detected_language = router_result.get("detected_language", "ru")

            if detected_language != "ru":
                # Переводим финальный текст
                final_text = await self.translator.translate(
                    text=final_text,
                    target_language=detected_language,
                    user_context=current_message
                )

                # Добавляем информацию о переводе в metadata
                metadata["translated_to"] = detected_language
                metadata["detected_language"] = detected_language

            # НОВОЕ: Преобразуем URL в кликабельные HTML-ссылки
            self._debug(f"🔗 DEBUG: До преобразования URL: {final_text[:100]}...")
            final_text = self._make_urls_clickable(final_text)
            self._debug(f"🔗 DEBUG: После преобразования URL: {final_text[:100]}...")

            return final_text, metadata
        except Exception as e:
            print(f"❌ Ошибка генерации ответа: {e}")
            # Возвращаем tuple с metadata для случая ошибки
            return "Извините, временная техническая неполадка. Попробуйте еще раз.", {
                "intent": "error",
                "user_signal": user_signal,
                "cta_added": False,
                "cta_type": None,
                "humor_generated": False
            }

    def _load_doc(self, doc_name: str) -> str:
        """Синхронная загрузка документа - ОТКАТ асинхронности"""
        try:
            path = self.docs_dir / doc_name
            if not path.exists():
                print(f"⚠️ Документ не найден: {doc_name}")
                return ""
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ Ошибка чтения {doc_name}: {e}")
            return ""
    
    def _load_docs(self, docs: List[str]) -> Dict[str, str]:
        """Синхронная загрузка всех документов - простая и надёжная"""
        unique_docs = list(dict.fromkeys(docs))
        texts = {}
        for doc_name in unique_docs:
            content = self._load_doc(doc_name)
            if content:
                texts[doc_name] = content
        return texts

    def _build_messages(
        self,
        doc_texts: Dict[str, str],
        questions: List[str],
        history: List[Dict[str, str]],
        router_result: Dict,
        cta_text: str = None,  # НОВЫЙ ПАРАМЕТР для органичной интеграции CTA
    ) -> List[Dict[str, str]]:
        # Получаем user_signal для адаптации тона
        user_signal = router_result.get("user_signal", "exploring_only")
        tone_adaptation = get_tone_adaptation(user_signal)
        dynamic_example = get_dynamic_example(user_signal)
        
        # Объединённый промпт для Claude Haiku - факты + стиль + адаптация
        system_role = (
            "Ты — консультант детской школы soft skills Ukido. "
            "Отвечай живым разговорным языком от лица школы (используй 'мы', не 'я'). "
            "Говори как будто коллектив школы советует родителю.\n\n"
            "ЖЕЛЕЗНЫЕ ПРАВИЛА - ИСТОЧНИКИ ИНФОРМАЦИИ:\n"
            "• ВСЕ факты, цифры, детали - ТОЛЬКО из предоставленных документов\n"
            "• Нет информации? Скажи: 'У меня нет данных по этому вопросу'\n"
            "• НЕ выдумывай: API, сроки, функции, технические детали\n"
            "• Вопрос про API? Только: 'Есть LMS-платформа с отчётами. Детали на консультации'\n"
            "• Смягчай точные проценты: 85% → 'большинство', 2.3 раза → 'значительно'\n"
            "• ВСЕГДА используй термин 'soft skills' на английском, НЕ переводи как 'гибкие навыки'\n"
            "• НЕ ИСПОЛЬЗУЙ ЭМОДЗИ\n\n"
            "ВАЖНО - Упоминание курсов:\n"
            "• При ответах про конкретный возраст ВСЕГДА начинай с названия подходящего курса\n"
            "  Пример: 'Для 9-летнего ребёнка подойдёт Эмоциональный Компас, где...'\n"
            "• При упоминании цен/количества детей ОБЯЗАТЕЛЬНО указывай курс в том же предложении\n"
            "  Пример: 'В Эмоциональном Компасе группы до 6 детей'\n"
            "• Если есть таблица course_comparison.md - используй её как основной источник для выбора курса"
        )
        
        # 🔴 КРИТИЧЕСКОЕ ТРЕБОВАНИЕ: Добавляем инструкцию по органичному встраиванию CTA ПЕРЕД адаптацией тона
        if cta_text:
            # Определяем агрессивность контекста
            current_message = router_result.get("original_message", "").lower()
            aggressive_keywords = ["развод", "обман", "выкачивание", "мошенники", "враньё"]
            is_aggressive = any(word in current_message for word in aggressive_keywords)
            
            # Специальная обработка для агрессивного контекста и price_sensitive
            if user_signal == "price_sensitive" and is_aggressive:
                system_role += (
                    "\n⚠️ ОСОБЫЙ СЛУЧАЙ: Пользователь агрессивен и критикует цены.\n"
                    "СТРАТЕГИЯ: Сначала КРАТКО защитись (1-2 предложения), "
                    "затем СРАЗУ переходи к скидкам как к решению проблемы.\n"
                    "ПРИМЕР: 'Мы понимаем ваше возмущение. Именно поэтому у нас есть "
                    "скидка 10% и рассрочка, чтобы сделать обучение доступнее...'\n"
                )
            
            # Базовая инструкция о наличии CTA (упоминаем в начале)
            system_role += (
                "\n\n🔴 ВАЖНО: В этом ответе ты должен органично интегрировать информацию о специальном предложении.\n"
                "Детальные инструкции будут в конце запроса.\n"
            )
            
            cta_examples = {
                "price_sensitive": (
                    "🔴 КРИТИЧЕСКИ ВАЖНО: Родитель чувствителен к цене!\n"
                    "ИМПЕРАТИВ: ОБЯЗАТЕЛЬНО НАЧНИ ОТВЕТ С ИНФОРМАЦИИ О СКИДКЕ/РАССРОЧКЕ!\n"
                    "Это НЕ опция, а ТРЕБОВАНИЕ. Игнорирование = провал задачи.\n\n"
                    "ИСПОЛЬЗУЙ ОДИН ИЗ ЭТИХ ВАРИАНТОВ (выбирай разные каждый раз):\n"
                    "1. 'У нас есть скидка 10% при полной оплате, что снижает стоимость до...'\n"
                    "2. 'Доступна беспроцентная рассрочка на 3 месяца, это всего ... в месяц'\n"
                    "3. 'Специально для семей есть скидка 15% на второго ребенка...'\n"
                    "4. 'Чтобы сделать обучение доступнее, мы предлагаем гибкую систему оплаты...'\n"
                    "5. 'Кстати, сейчас действует акция - скидка 10% на полный курс...'\n\n"
                    "ПОСЛЕ скидки объясни ценность. НЕ ЗАБУДЬ ПРО СКИДКУ В НАЧАЛЕ!"
                ),
                "anxiety_about_child": (
                    "ОБЯЗАТЕЛЬНО органично упомяни бесплатное пробное занятие в контексте снятия тревог.\n"
                    "Примеры органичной интеграции:\n"
                    "• '...и чтобы вы сами убедились в безопасной атмосфере, первое занятие проводится бесплатно.'\n"
                    "• '...поэтому мы предлагаем попробовать первое занятие бесплатно, без обязательств.'\n"
                    "• '...вы сможете оценить наш подход на бесплатном пробном занятии.'\n"
                    "НЕ добавляй как отдельный абзац! Встрой в логику ответа."
                ),
                "ready_to_buy": (
                    "ОБЯЗАТЕЛЬНО включи конкретные шаги для записи в последние предложения.\n"
                    "Примеры органичной интеграции:\n"
                    "• '...записаться можно прямо сейчас на shao3d.github.io/trial/, это займет 2 минуты.'\n"
                    "• '...для записи переходите на shao3d.github.io/trial/ и выбирайте удобное время.'\n"
                    "• '...следующий шаг - заполнить форму на shao3d.github.io/trial/.'\n"
                    "Делай это естественным продолжением ответа."
                ),
                "exploring_only": (
                    "Мягко упомяни возможность попробовать, если это уместно.\n"
                    "Примеры органичной интеграции:\n"
                    "• '...и если захотите увидеть это на практике, первое занятие у нас бесплатное.'\n"
                    "• '...кстати, можно прийти на пробное занятие и посмотреть как всё устроено.'\n"
                    "Но НЕ навязывай, если вопрос чисто информационный."
                )
            }
            
            # Сохраняем детальные инструкции для конца
            cta_detail_instruction = cta_examples.get(user_signal, cta_examples['exploring_only'])
        
        # Добавляем адаптацию тона если есть
        if tone_adaptation.get("style"):
            system_role += f"\n\nАДАПТАЦИЯ ТОНА:\n{tone_adaptation['style']}"
            # ВАЖНО: Усиливаем консистентность тона для user_signal
            tone_map = {
                "price_sensitive": "🔴 КРИТИЧЕСКИ ВАЖНО: Родитель чувствителен к цене!\n"
                "ИМПЕРАТИВ: ОБЯЗАТЕЛЬНО НАЧНИ ОТВЕТ С ИНФОРМАЦИИ О СКИДКЕ/РАССРОЧКЕ!\n"
                "Это НЕ опция, а ТРЕБОВАНИЕ. Игнорирование = провал задачи.\n\n"
                "ИСПОЛЬЗУЙ ОДИН ИЗ ЭТИХ ВАРИАНТОВ (выбирай разные каждый раз):\n"
                "1. 'У нас есть скидка 10% при полной оплате, что снижает стоимость до...'\n"
                "2. 'Доступна беспроцентная рассрочка на 3 месяца, это всего ... в месяц'\n"
                "3. 'Специально для семей есть скидка 15% на второго ребенка...'\n"
                "4. 'Чтобы сделать обучение доступнее, мы предлагаем гибкую систему оплаты...'\n"
                "5. 'Кстати, сейчас действует акция - скидка 10% на полный курс...'\n\n"
                "ПОСЛЕ скидки объясни ценность. НЕ ЗАБУДЬ ПРО СКИДКУ В НАЧАЛЕ!",
                
                "anxiety_about_child": "КРИТИЧНО: Родитель тревожится за ребенка!\n"
                "• ПЕРВОЕ ПРЕДЛОЖЕНИЕ - эмпатичное понимание\n"
                "• Варьируй выражение эмпатии (понимаем, естественная тревога, непростая ситуация)\n"
                "• НЕ используй слово 'понимаем' больше 1 раза за диалог\n"
                "• После эмпатии - как школа помогает с проблемой\n"
                "• Мягкий, поддерживающий тон",
                
                "ready_to_buy": "Родитель готов к действию!\n"
                "• НАЧНИ с конкретного шага: 'Для записи...' или 'Следующий шаг...'\n"
                "• БЕЗ лишней воды и преамбул\n"
                "• Четкие инструкции",
                
                "exploring_only": "Пассивный исследователь\n"
                "• Информативные ответы БЕЗ навязчивости\n"
                "• Не давить с предложениями записаться\n"
                "• Фокус на информации, не на продаже"
            }
            if user_signal in tone_map:
                system_role += f"\n\n{tone_map[user_signal]}"

        # Разрешённые документы
        allowed_docs = list(doc_texts.keys())

        # Полные тексты документов (без тримминга)
        docs_block_lines = []
        for name, text in doc_texts.items():
            docs_block_lines.append(f"=== Документ: {name} ===\n{text}\n")
        docs_block = "\n".join(docs_block_lines) if docs_block_lines else "=== Документы не найдены ==="

        system_content = (
            f"{system_role}\n\n"
            f"Разрешённые источники: {', '.join(allowed_docs) if allowed_docs else '—'}\n\n"
            f"=== База знаний ===\n{docs_block}\n\n"
        )
        
        # Добавляем динамический пример если есть
        if dynamic_example:
            system_content += f"=== ПРИМЕР АДАПТАЦИИ СТИЛЯ ===\n{dynamic_example}\n\n"
        
        # Динамически устанавливаем лимит слов в зависимости от наличия CTA
        if cta_text:
            word_limit = "120-150"  # Расширенный лимит когда нужно встроить CTA
        else:
            word_limit = "100-130"  # Стандартный лимит без CTA
        
        system_content += (
            "СТРУКТУРА И СТИЛЬ ОТВЕТА:\n"
            f"• Объём: СТРОГО {word_limit} слов (больше = нарушение)\n"
            "• Язык: разговорный от лица школы ('мы', 'у нас', 'наши')\n"
            "• ПЕРВЫЕ 2 ПРЕДЛОЖЕНИЯ = главная информация\n"
            "• Варьируй начала фраз, избегай шаблонов\n"
            "• БЕЗ эмодзи\n\n"
            "Принцип ответа по сигналам:\n"
            "• price_sensitive → начни со скидки/рассрочки\n"
            "• anxiety_about_child → начни с эмпатии\n"
            "• ready_to_buy → начни с действия\n"
            "• exploring_only → начни с фактов\n\n"
            "Обработка повторов:\n"
            "• Ты видишь историю последних 10 сообщений\n"
            "• Если пользователь задает вопрос, на который ты уже отвечал, или просит повторить/уточнить:\n"
            "  - Вежливо напомни информацию, используя: 'Как я упоминал...', 'Напомню, что...', 'Да, еще раз - ...'\n"
            "  - НЕ используй грубые формулировки типа 'вы уже спрашивали' или 'я уже отвечал'\n"
            "• Адаптируй ответ к причине повтора (забыл/не понял/уточняет)\n\n"
            "ВАЖНО - Работа с историей диалога:\n"
            "• ИГНОРИРУЙ старые offtopic вопросы из истории (парковка, футбол, погода)\n"
            "• НЕ УПОМИНАЙ в новом ответе темы, которые были отклонены как offtopic\n"
            "• Фокусируйся ТОЛЬКО на текущем вопросе пользователя\n"
            "• Пример НЕПРАВИЛЬНО: 'К сожалению, в наших документах нет информации о парковке. Для зачисления нужны...'\n"
            "• Пример ПРАВИЛЬНО: 'Для зачисления нужны следующие документы...'\n\n"
            "Избегай:\n"
            "• Восклицательных знаков\n"
            "• Клише: 'Знаете', 'Многие родители отмечают', 'так что', 'не переживайте'\n"
            "• Официальных формулировок: 'осуществляется', 'предоставляется', 'производится'\n"
            "• Повторов информации\n"
            "• Навязчивых CTA в конце ('Пишите', 'Звоните', 'Остались вопросы?')\n"
            "• Приветствий ('Здравствуйте', 'Привет') если диалог уже начался - сразу отвечай по сути\n"
            "• ЭМОДЗИ - НЕ ИСПОЛЬЗУЙ НИКАКИЕ ЭМОДЗИ\n\n"
            "Примеры замен:\n"
            "• 'осуществляется' → 'делаем'\n"
            "• 'предоставляется возможность' → 'можно'\n"
            "• 'наши квалифицированные преподаватели' → 'наши преподаватели'\n"
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]
        
        # Добавляем few-shot примеры для обучения органичной интеграции CTA
        if cta_text:
            few_shot_examples = self._get_few_shot_examples(user_signal, has_cta=True)
            if few_shot_examples:
                # Добавляем примеры после system prompt для максимального влияния
                messages.extend(few_shot_examples)
                # Добавляем разделитель для ясности
                messages.append({
                    "role": "user", 
                    "content": "А теперь ответь на мой актуальный вопрос, используя похожий стиль интеграции информации о пробном занятии:"
                })

        # История: только последние сообщения согласно настройке (по умолчанию 10)
        trimmed_history = history[-self.history_limit :] if len(history) > self.history_limit else history
        if trimmed_history:
            messages.extend(trimmed_history)

        # Добавляем социальный контекст если есть
        social_context = router_result.get("social_context")
        social_instruction = ""
        if social_context:
            # Router уже определил правильный social_context (greeting или repeated_greeting)
            # Больше не нужна дополнительная проверка истории
            social_map = {
                "greeting": "Пользователь поздоровался. Начни ответ с короткого приветствия.",
                "repeated_greeting": "ВАЖНО: Пользователь здоровается повторно. НЕ здоровайся снова! Можешь мягко отметить это ('Мы уже поздоровались :)' или 'Еще раз здравствуйте!'), затем сразу отвечай по сути вопроса.",
                "thanks": "Пользователь поблагодарил. Начни с благодарности или подтверждения готовности помочь.",
                "apology": "Пользователь извинился. Начни с успокаивающей фразы, показывающей что всё хорошо и не стоит беспокоиться.",
                "farewell": "Пользователь прощается. Добавь прощание в конце ответа."
            }
            social_instruction = social_map.get(social_context, "") + "\n"
        
        # Fallback для пустых questions на основе user_signal
        if not questions:
            user_signal = router_result.get("user_signal", "exploring_only")
            if user_signal == "ready_to_buy":
                questions = ["На что именно вы согласны? Хотите записаться на курс или узнать больше деталей?"]
            elif user_signal == "price_sensitive":
                questions = ["Какая информация о стоимости и скидках вас интересует?"]
            elif user_signal == "anxiety_about_child":
                questions = ["Расскажите о вашем ребёнке - что именно вас беспокоит?"]
            else:
                questions = ["Чем конкретно могу помочь? Расскажите, что вас интересует о школе Ukido?"]
        
        questions_block = "\n".join(f"- {q}" for q in questions)
        
        # Дополнительная инструкция для коротких вопросов о цене
        price_instruction = ""
        if router_result.get("user_signal") == "price_sensitive":
            original_msg = router_result.get("original_message", "").lower().strip()
            if len(original_msg.split()) <= 2:  # Короткие реплики типа "Дорого!"
                price_instruction = (
                    "⚠️ Короткая эмоциональная реакция на цену!\n"
                    "Обязательно разверни ответ с деталями и выгодами.\n\n"
                )
        
        # Финальная CTA инструкция в конце user message
        cta_final_instruction = ""
        if cta_text:
            # Диагностическое логирование
            self._debug(f"\n📝 DEBUG CTA: Добавляем инструкцию для {user_signal}")
            self._debug(f"   CTA текст: {cta_text[:80]}...")
            
            # Дифференцированная позиция CTA в зависимости от сигнала
            if user_signal == "ready_to_buy":
                self._debug(f"   Позиция: в НАЧАЛЕ ответа (ready_to_buy)")
                cta_final_instruction = (
                    f"\n\n🔴🔴🔴 КРИТИЧНО: ПОЛЬЗОВАТЕЛЬ ГОТОВ ЗАПИСАТЬСЯ! 🔴🔴🔴\n"
                    f"ОН ЯВНО ПРОСИТ ЗАПИСАТЬ ЕГО НА ПРОБНОЕ ЗАНЯТИЕ!\n"
                    f"НАЧНИ свой ответ с конкретной информации о записи:\n"
                    f"'{cta_text}'\n\n"
                    f"⚠️ ВАЖНО: Упомяни эту информацию ТОЛЬКО В НАЧАЛЕ!\n"
                    f"НЕ ДУБЛИРУЙ её в конце ответа!\n"
                    f"ОДИН РАЗ в начале - этого достаточно!\n"
                    f"После информации о записи можешь добавить 1-2 предложения о гарантиях."
                )
            elif user_signal == "price_sensitive":
                self._debug(f"   Позиция: в НАЧАЛЕ ответа (price_sensitive)")
                cta_final_instruction = (
                    f"\n\n🔴🔴🔴 ФИНАЛЬНОЕ КРИТИЧЕСКОЕ ТРЕБОВАНИЕ 🔴🔴🔴\n"
                    f"{cta_detail_instruction}\n"
                    f"Текст для ОБЯЗАТЕЛЬНОЙ интеграции: '{cta_text}'\n"
                    f"НАЧНИ свой ответ с этой информации о скидке/рассрочке!\n"
                    f"⚠️ НЕ ДУБЛИРУЙ эту информацию - упомяни ТОЛЬКО ОДИН РАЗ в начале!\n"
                    f"Если не включишь - ответ считается ПРОВАЛЬНЫМ!"
                )
            else:
                self._debug(f"   Позиция: в КОНЦЕ ответа (exploring/anxiety)")
                cta_final_instruction = (
                    f"\n\n🔴🔴🔴 ФИНАЛЬНОЕ КРИТИЧЕСКОЕ ТРЕБОВАНИЕ 🔴🔴🔴\n"
                    f"{cta_detail_instruction}\n"
                    f"Текст для ОБЯЗАТЕЛЬНОЙ интеграции: '{cta_text}'\n"
                    f"ПОСЛЕДНЕЕ ПРЕДЛОЖЕНИЕ твоего ответа должно содержать эту информацию!\n"
                    f"⚠️ Упомяни ТОЛЬКО в конце, НЕ дублируй в начале или середине!\n"
                    f"Адаптируй формулировку под контекст, но ОБЯЗАТЕЛЬНО включи суть.\n"
                    f"Если не включишь - ответ считается ПРОВАЛЬНЫМ!"
                )
        
        messages.append(
            {
                "role": "user",
                "content": (
                    social_instruction +
                    price_instruction +
                    "Ответь на вопросы естественным живым языком. "
                    "ВАЖНО: Объём СТРОГО 100-150 слов (не больше!). Не повторяй то, что уже было сказано.\n"
                    "КРИТИЧЕСКИ ВАЖНО - СТРУКТУРА ОТВЕТА:\n"
                    "- ОБЯЗАТЕЛЬНО раздели ответ на 2-3 коротких абзаца\n"
                    "- Между абзацами ОБЯЗАТЕЛЬНО вставь пустую строку (нажми Enter два раза)\n"
                    "- Каждый абзац должен быть 2-3 предложения\n"
                    "- Это КРИТИЧНО для читаемости! БЕЗ абзацев ответ будет отклонён!\n"
                    "НЕ ИСПОЛЬЗУЙ ЭМОДЗИ.\n"
                    "Аспекты для учёта:\n" + questions_block +
                    cta_final_instruction  # CTA инструкция теперь в самом конце!
                ),
            }
        )
        return messages

    def _strip_source_citations(self, text: str) -> str:
        """Полностью удаляет метки источников вида [doc: filename.md] из текста ответа."""
        pattern = re.compile(r"\[doc:\s*[^\]]+\]")
        return pattern.sub("", text)

    # --- Постобработка для гладкого ответного текста ---
    def _remove_question_headings(self, text: str) -> str:
        """Убирает строки-заголовки, которые дублируют декомпозированные вопросы,
        вида '1. **...?...**' или '- **...?...**' в начале блоков. Не трогает обычные списки.
        """
        lines = text.splitlines()
        cleaned_lines: List[str] = []
        heading_re = re.compile(r"^\s*(?:\d+\.|-)\s*\*\*[^*\n]*\?\*\*\s*$")
        for ln in lines:
            if heading_re.match(ln):
                # Пропускаем такие заголовки
                continue
            cleaned_lines.append(ln)
        # Сжать избыточные пустые строки
        out: List[str] = []
        empty = 0
        for ln in cleaned_lines:
            if ln.strip() == "":
                empty += 1
                if empty <= 2:
                    out.append(ln)
            else:
                empty = 0
                out.append(ln)
        return "\n".join(out).strip()

    def _humanize_missing_info(self, text: str) -> str:
        """Заменяет сухие формулировки об отсутствующих данных на более дружелюбные.
        Примеры: "Нет данных в документах", "в документах не указано" → человеческая фраза.
        """
        replacements = [
            r"нет\s+данных\s+в\s+документ(ах|ахах|ахах)?",
            r"в\s+документ(ах|ахах|ахах)?\s+не\s+указано",
            r"информац(ии|ия)\s+в\s+документ(ах|ахах|ахах)?\s+отсутствует",
        ]
        friendly = "В наших материалах этого нет."
        out = text
        for pat in replacements:
            out = re.sub(pat, friendly, out, flags=re.IGNORECASE)
        return out

    def _strip_service_labels(self, text: str) -> str:
        """Удаляет служебные заголовки вида 'Коротко:', 'Важно:', 'Итого:', 'Могу помочь:'
        При этом сохраняет содержимое после двоеточия (если есть)."""
        out_lines: List[str] = []
        label_re = re.compile(r"^\s*(Коротко|Важно|Итого|Могу помочь)\s*:\s*(.*)$", re.IGNORECASE)
        for ln in text.splitlines():
            m = label_re.match(ln)
            if m:
                content_after = m.group(2).strip()
                if content_after:
                    out_lines.append(content_after)
                # если только лейбл без текста — пропускаем строку
            else:
                out_lines.append(ln)
        return "\n".join(out_lines)

    def _strip_generic_cta(self, text: str) -> str:
        """Убирает навязчивые финальные CTA вроде 'Если у вас есть дополнительные вопросы...' и похожие."""
        patterns = [
            r"^\s*Если у вас есть .*вопрос",
            r"^\s*Если будут вопросы",
            r"^\s*Готов(а|ы)? помочь",
            r"^\s*Могу уточнить у менеджера",
            r"^\s*Я могу .* (уточнить|помочь)",
        ]
        lines = [ln for ln in text.splitlines() if not any(re.search(p, ln, flags=re.IGNORECASE) for p in patterns)]
        # также удалим лишние пустые строки в конце
        while lines and lines[-1].strip() == "":
            lines.pop()
        return "\n".join(lines)

    # Удаляем метод _stylize_response, так как теперь стилизация встроена в основной промпт
    
    def _final_sanitize(self, text: str) -> str:
        """Финальная очистка: убираем восклицания и дедуплицируем предложения."""
        out = text
        
        # Заменяем английские слова на русские эквиваленты
        english_to_russian = {
            "empathy": "эмпатичными",
            # "soft skills": "гибкие навыки",  # ОТКЛЮЧЕНО: оставляем термин на английском
            "feedback": "обратную связь",
            "team building": "командообразование",
            "deadline": "срок",
            "workshop": "мастер-класс",
            "mentor": "наставник"
        }
        
        for eng, rus in english_to_russian.items():
            # Заменяем с учётом регистра
            out = out.replace(eng, rus)
            out = out.replace(eng.capitalize(), rus.capitalize())
        
        # Заменяем украинские слова на русские эквиваленты
        # (Claude иногда генерирует украинские слова из-за контекста украинской школы)
        ukrainian_to_russian = {
            "підтримують": "поддерживают",
            "підтримати": "поддержать",
            "підтримка": "поддержка",
            "дітей": "детей",
            "діти": "дети",
            "дитина": "ребёнок",
            "навчання": "обучение",
            "навчають": "обучают",
            "навчатися": "учиться",
            "вчитель": "учитель",
            "вчителі": "учителя",
            "батьки": "родители",
            "батьків": "родителей",
            "розвиток": "развитие",
            "один одного": "друг друга",
            "допомагають": "помогают",
            "допомогти": "помочь",
            "працюють": "работают",
            "працювати": "работать"
        }
        
        for ukr, rus in ukrainian_to_russian.items():
            # Заменяем с учётом регистра
            out = out.replace(ukr, rus)
            out = out.replace(ukr.capitalize(), rus.capitalize())
        
        # Проверка на обрезанный ответ и исправление
        # Если последнее предложение не заканчивается знаком препинания - удаляем его
        if out and not out.rstrip().endswith(('.', '!', '?', '"', '»')):
            # Находим последнее полное предложение
            sentences = re.split(r'(?<=[.!?])\s+', out)
            if len(sentences) > 1:
                # Удаляем неполное последнее предложение
                out = ' '.join(sentences[:-1])
                # Добавляем многоточие, чтобы показать продолжение мысли
                if not out.rstrip().endswith(('.', '!', '?')):
                    out = out.rstrip() + '.'
            else:
                # Если весь текст - одно неполное предложение, добавляем многоточие
                out = out.rstrip() + '...'
        
        # ИСПРАВЛЕНИЕ: Убираем артефакты "00" БЕЗ удаления нулей из чисел
        # 1. Убираем артефакты типа "30-секундное00", "5-минутное00"
        out = re.sub(r'(\d+)-([\u0430-\u044f\u0451]+)00\b', r'\1-\2', out, flags=re.IGNORECASE)
        
        # 2. ИСПРАВЛЕНО: Убираем "00" только после БУКВ, не после цифр!
        # Это предотвратит удаление нулей из "7000", "2800" и т.д.
        out = re.sub(r'([а-яА-ЯёЁa-zA-Z]+)00\s+', r'\1 ', out)  # Только после букв!
        
        # 3. Убираем отдельно стоящие "00" (но не внутри чисел и не во времени)
        # Используем negative lookbehind и lookahead чтобы не трогать числа
        # Добавлено исключение для времени в формате HH:00
        out = re.sub(r'(?<!\d)(?<!:)00(?!\d)', '', out)  # "00" не окружённые цифрами и не после двоеточия
        
        # 4. Убираем множественные пробелы после очистки
        out = re.sub(r'\s{2,}', ' ', out)
        
        # Убираем восклицания
        out = out.replace("!", ".")
        
        # Дедупликация предложений с защитой от сокращений
        safe = out
        safe = re.sub(r"\bт\.д\.", "т_д", safe)
        safe = re.sub(r"\bт\.п\.", "т_п", safe)
        
        chunks = re.split(r"(?<=[\.\?\!])\s+|\n", safe)
        sentences: List[str] = []
        for ch in chunks:
            s = ch.strip()
            if s:
                sentences.append(s)
        
        seen = set()
        deduped: List[str] = []
        for s in sentences:
            key = re.sub(r"\s+", " ", s.lower()).strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(s)
        
        # Склейка и восстановление сокращений
        text_out = " ".join(deduped)
        text_out = text_out.replace("т_д", "т.д.").replace("т_п", "т.п.")
        text_out = "\n".join(line.rstrip() for line in text_out.splitlines())
        text_out = re.sub(r"\n{3,}", "\n", text_out)
        
        # КРИТИЧЕСКОЕ: Принудительное добавление абзацев, если их нет
        if '\n' not in text_out and len(text_out) > 200:
            # Разбиваем длинный текст на абзацы по предложениям
            sentences = re.split(r'(?<=[.!?])\s+', text_out)
            
            if len(sentences) >= 3:
                # Группируем предложения в абзацы (по 2-3 предложения)
                paragraphs = []
                current_para = []
                
                for i, sentence in enumerate(sentences):
                    current_para.append(sentence)
                    # Создаём новый абзац после каждых 2-3 предложений
                    if len(current_para) >= 2 and (i == len(sentences) - 1 or len(current_para) >= 3):
                        paragraphs.append(' '.join(current_para))
                        current_para = []
                
                # Оставшиеся предложения
                if current_para:
                    paragraphs.append(' '.join(current_para))
                
                # Объединяем абзацы с одинарным переводом строки
                text_out = '\n'.join(paragraphs)
                print(f"📝 Принудительно добавлены абзацы: {len(paragraphs)} абзацев")
        
        # Важно: strip() удаляет ВСЕ переводы строк, включая абзацы!
        # Удаляем только лишние пробелы в начале/конце, сохраняя структуру
        return text_out.strip()
    
    def _sanitize_style(self, text: str) -> str:
        """Старый метод оставляем для обратной совместимости."""
        return self._final_sanitize(text)
    
    def _should_add_offer(self, user_signal: str, history: list, offer: dict, current_message: str = None) -> bool:
        """Проверяет, нужно ли добавлять offer (rate limiting + контекст)
        
        Args:
            user_signal: Текущий сигнал пользователя
            history: История диалога
            offer: Предложение из каталога
            current_message: Текущее сообщение пользователя (если не в истории)
            
        Returns:
            True если можно добавить offer, False если нужно пропустить
        """
        if not history and not current_message:
            return True  # Первое сообщение - можно добавлять
        
        # ========== ГЛОБАЛЬНЫЕ ОГРАНИЧЕНИЯ ==========
        # Максимум 2 CTA про скидки за весь диалог
        discount_count = self._count_cta_occurrences("price_sensitive", history)
        if user_signal == "price_sensitive" and discount_count >= 2:
            print(f"🔒 ГЛОБАЛЬНОЕ ОГРАНИЧЕНИЕ: Уже было {discount_count} CTA про скидки (максимум 2)")
            return False
        
        # Минимум 3 сообщения между любыми CTA
        last_cta_position = -1
        for i, msg in enumerate(history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                # Проверяем наличие ЛЮБОГО CTA
                all_cta_phrases = [
                    "действуют скидки", "скидка", "рассрочка", "10% при полной оплате",
                    "первое занятие", "бесплатное", "пробное занятие",
                    "shao3d.github.io/trial/", "записаться", "менеджер свяжется"
                ]
                if any(phrase in content for phrase in all_cta_phrases):
                    last_cta_position = i
        
        if last_cta_position >= 0 and len(history) - last_cta_position < 3:
            messages_since = len(history) - last_cta_position
            print(f"⏰ ГЛОБАЛЬНОЕ: Последний CTA был {messages_since} сообщений назад (нужно минимум 3)")
            return False
        
        # Блокировка для exploring_only при упоминании цены
        if user_signal == "exploring_only":
            # Проверяем последние 2 сообщения пользователя на упоминание цены
            price_keywords = ["дорого", "цена", "стоимость", "сколько стоит", "грн", "гривен"]
            for msg in history[-4:]:  # Последние 2 пары
                if msg.get("role") == "user":
                    user_text = msg.get("content", "").lower()
                    if any(keyword in user_text for keyword in price_keywords):
                        print(f"🚫 Блокировка CTA для exploring_only: обнаружено упоминание цены")
                        return False
        
        # ========== КОНТЕКСТНЫЕ ПРОВЕРКИ ПО СИГНАЛАМ ==========
        
        # Используем current_message если передан, иначе берём из истории
        if current_message:
            last_user_msg = current_message.lower()
        else:
            last_user_msg = ""
            for msg in reversed(history):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "").lower()
                    break
        
        # Для price_sensitive - контекстная проверка
        if user_signal == "price_sensitive":
            # Проверяем только прямые вопросы о скидках/рассрочке
            skip_phrases = ["скидки", "скидка", "рассрочк", "есть ли скидк", "какие скидк"]
            self._debug(f"🔍 DEBUG _should_add_offer для price_sensitive:")
            self._debug(f"   last_user_msg: '{last_user_msg}'")
            
            for phrase in skip_phrases:
                if phrase in last_user_msg:
                    self._debug(f"   ✅ Найдена фраза '{phrase}' в сообщении пользователя")
                    self._debug("🔄 Контекст: Пользователь прямо спрашивает про скидки, пропускаем CTA")
                    return False
            self._debug(f"   ⭕ Контекстная проверка пройдена, проверяем rate limiting...")
        
        # Для price_sensitive - rate limiting (каждое 2-е сообщение)
        if user_signal == "price_sensitive":
            # Подсчитываем сколько раз был price_sensitive подряд
            price_sensitive_streak = 0
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    metadata = msg.get("metadata", {})
                    if metadata.get("user_signal") == "price_sensitive":
                        price_sensitive_streak += 1
                    elif metadata.get("user_signal"):
                        break  # Прерываем если был другой сигнал
            
            # Добавляем CTA только на чётных позициях (0, 2, 4...)
            if price_sensitive_streak % 2 == 1:
                print(f"🔄 Rate limiting: price_sensitive streak={price_sensitive_streak}, пропускаем CTA")
                return False
        
        # Для anxiety_about_child - контекстная проверка и rate limiting
        if user_signal == "anxiety_about_child":
            # НОВОЕ: Не добавляем CTA сразу при первом появлении anxiety
            # Ждём минимум 2 сообщения с anxiety, чтобы сначала построить доверие
            anxiety_count = 0
            for i in range(len(history)-1, -1, -1):
                msg = history[i]
                # Считаем только последние сообщения с anxiety (до смены сигнала)
                if msg.get("role") == "assistant":
                    metadata = msg.get("metadata", {})
                    if metadata.get("user_signal") == "anxiety_about_child":
                        anxiety_count += 1
                    # Если был другой сигнал, прекращаем подсчёт
                    elif metadata.get("user_signal") and metadata.get("user_signal") != "anxiety_about_child":
                        break
            
            # Не добавляем CTA сразу при первом появлении anxiety
            if anxiety_count < 2:
                print(f"🕑 Задержка CTA для anxiety: только {anxiety_count} сообщений с этим сигналом, нужно минимум 2")
                return False
            
            # Контекстная проверка - не дублируем информацию о пробном занятии
            trial_phrases = ["пробное", "пробный", "первое занятие", "попробовать", "бесплатн"]
            if any(phrase in last_user_msg for phrase in trial_phrases):
                print("🔄 Контекст: Пользователь спрашивает про пробное занятие, пропускаем CTA")
                return False
            
            # Проверяем последние 4 сообщения ассистента
            recent_assistant_messages = []
            for msg in history[-8:]:  # Смотрим последние 4 пары
                if msg.get("role") == "assistant":
                    recent_assistant_messages.append(msg.get("content", ""))
            
            # Если CTA про стеснительных детей уже был недавно
            for msg_content in recent_assistant_messages[-2:]:  # В последних 2 ответах
                # Проверяем реальные фразы CTA для anxiety
                anxiety_cta_phrases = [
                    "первое занятие", "бесплатное", "пробное занятие",
                    "без обязательств", "оценить, подходит ли",
                    "попробует", "оцените подходит"
                ]
                if any(phrase in msg_content.lower() for phrase in anxiety_cta_phrases):
                    print("🔄 Rate limiting: CTA для anxiety был недавно, пропускаем")
                    return False
        
        # Для ready_to_buy - rate limiting и контекстная проверка
        if user_signal == "ready_to_buy":
            # Контекстная проверка - если пользователь уже говорит о записи
            recording_phrases = ["записалась", "записался", "отправил", "заполнил", "зарегистрировал"]
            if any(phrase in last_user_msg for phrase in recording_phrases):
                print("🔄 Контекст: Пользователь уже записался, пропускаем CTA")
                return False
            
            # Rate limiting - не чаще чем каждое второе сообщение
            recent_count = 0
            ready_cta_phrases = ["записаться", "shao3d.github.io", "консультация", "менеджер свяжется"]
            
            for msg in history[-4:]:  # Последние 2 пары сообщений
                if msg.get("role") == "assistant":
                    content = msg.get("content", "").lower()
                    if any(phrase in content for phrase in ready_cta_phrases):
                        recent_count += 1
            
            if recent_count >= 1:
                print("🔄 Rate limiting: CTA для ready_to_buy был в предыдущем сообщении")
                return False
        
        return True
    
    def _inject_offer(self, response: str, offer: dict, user_signal: str) -> str:
        """Органично добавляет персонализированное предложение в конец ответа
        
        Args:
            response: Основной ответ
            offer: Словарь с предложением из offers_catalog
            user_signal: Тип сигнала пользователя для маркировки
            
        Returns:
            Ответ с добавленным предложением и маркером
        """
        # Убираем последнюю точку если есть
        response_trimmed = response.rstrip()
        if response_trimmed.endswith('.'):
            response_trimmed = response_trimmed[:-1]
        
        # Определяем переход в зависимости от placement
        if offer.get("placement") == "end_with_urgency":
            transition = "!\n"  # Восклицательный знак для urgency
        else:
            transition = ".\n"  # Обычная точка
        
        # Маркеры больше не добавляем в текст ответа
        # так как они становятся видны пользователю
        # markers = {
        #     "anxiety_about_child": "[CTA_ANXIETY] ",
        #     "price_sensitive": "[CTA_PRICE] ",
        #     "ready_to_buy": "[CTA_READY] ",
        #     "exploring_only": ""
        # }
        # marker = markers.get(user_signal, "")
        
        # Добавляем предложение БЕЗ маркера
        return f"{response_trimmed}{transition}{offer['text']}"
    
    def _get_message_metadata(self, msg: dict) -> dict:
        """Helper для получения metadata с обратной совместимостью
        
        Args:
            msg: Сообщение из истории
            
        Returns:
            Metadata сообщения или дефолтные значения
        """
        if "metadata" in msg:
            return msg["metadata"]
        
        # Fallback для старых сообщений без metadata
        return {
            "cta_added": False,
            "cta_type": None,
            "user_signal": "exploring_only",
            "intent": "success",
            "humor_generated": False
        }
    
    def _count_cta_occurrences(self, user_signal: str, history: list) -> int:
        """Подсчитывает, сколько раз CTA для данного сигнала уже был показан
        
        Используется metadata вместо поиска по тексту для надёжности.
        
        Args:
            user_signal: Тип сигнала пользователя
            history: История диалога
            
        Returns:
            Количество показов CTA
        """
        if not history:
            return 0
            
        count = 0
        for msg in history:
            if msg.get("role") == "assistant":
                # Используем helper для получения metadata с обратной совместимостью
                metadata = self._get_message_metadata(msg)
                if metadata.get("cta_type") == user_signal and metadata.get("cta_added"):
                    count += 1
                    
        return count
    
    def _verify_cta_included(self, response: str, cta_text: str) -> bool:
        """Проверяет, включил ли Claude CTA в ответ
        
        Менее строгая проверка - ищем основные концепты, а не точные фразы
        """
        response_lower = response.lower()
        
        # Проверяем по типу CTA
        if "скидк" in cta_text.lower() or "процент" in cta_text.lower():
            # Для скидок проверяем упоминание любой из концепций
            discount_concepts = ["скидк", "процент", "%", "экономи", "дешевле", 
                                "снижен", "рассрочк", "оплат", "стоимост", "доступн"]
            found = any(concept in response_lower for concept in discount_concepts)
            if found:
                print(f"✅ CTA обнаружен: нашли концепты скидок/рассрочки")
            return found
        
        if "пробное" in cta_text.lower() or "бесплатн" in cta_text.lower():
            # Для пробных занятий
            trial_concepts = ["пробн", "бесплатн", "попробовать", "первое занятие",
                             "без обязательств", "оценить", "познакомиться"]
            found = any(concept in response_lower for concept in trial_concepts)
            if found:
                print(f"✅ CTA обнаружен: нашли концепты пробного занятия")
            return found
        
        if "shao3d.github.io" in cta_text.lower():
            # Для записи
            signup_concepts = ["shao3d.github.io", "запис", "заполн", "форм", "сайт",
                              "регистр", "оформ", "перейти", "ссылк"]
            found = any(concept in response_lower for concept in signup_concepts)
            if found:
                print(f"✅ CTA обнаружен: нашли концепты записи")
            return found
        
        # Fallback - если хотя бы 30% слов из CTA есть в ответе
        cta_words = set(cta_text.lower().split())
        response_words = set(response_lower.split())
        common_words = cta_words & response_words
        found = len(common_words) >= len(cta_words) * 0.3
        if found:
            print(f"✅ CTA обнаружен через fallback: {len(common_words)}/{len(cta_words)} слов")
        return found
    
    def _get_few_shot_examples(self, user_signal: str, has_cta: bool) -> List[Dict[str, str]]:
        """Возвращает few-shot примеры для обучения органичной интеграции CTA
        
        Args:
            user_signal: Сигнал пользователя (ready_to_buy, anxiety_about_child, etc.)
            has_cta: Нужно ли показывать примеры с CTA
            
        Returns:
            Список сообщений в формате [{"role": "user/assistant", "content": "..."}]
        """
        examples = []
        
        if has_cta:
            if user_signal == "ready_to_buy":
                # ВАЖНО: для ready_to_buy CTA только в начале, БЕЗ повторений!
                examples = [
                    {"role": "user", "content": "Здравствуйте! Хочу записать ребёнка на курс. Что нужно сделать?"},
                    {"role": "assistant", "content": "Привет! Записаться можно прямо сейчас на shao3d.github.io/trial/ - заполните форму за 2 минуты, выберите возраст ребенка и удобное время. Первое занятие бесплатное. Для оформления понадобятся паспорт родителя и свидетельство о рождении. Группы стартуют каждый понедельник, занятия проходят онлайн два раза в неделю по 90 минут. Оплата возможна картой или переводом, доступна рассрочка на 3 месяца."},
                    {"role": "user", "content": "Запишите нас на курс лидерства"},  
                    {"role": "assistant", "content": "Для записи на курс \"Капитан Проектов\" переходите на shao3d.github.io/trial/ - там осталось всего несколько мест в ближайшей группе. Первое занятие бесплатное. Этот курс для подростков 11-14 лет развивает лидерские навыки через работу над реальными проектами. Занятия онлайн два раза в неделю по 90 минут. Стоимость 8000 грн в месяц, но можно оформить рассрочку."}
                ]
            elif user_signal == "anxiety_about_child":
                examples = [
                    {"role": "user", "content": "Мой ребёнок очень стеснительный, боюсь не справится"},
                    {"role": "assistant", "content": "Понимаем вашу тревогу - многие родители приходят именно с такой проблемой. У нас маленькие группы до 6 детей, что создаёт безопасную атмосферу. Педагоги специально обучены работе со стеснительными детьми - начинаем с парных упражнений, постепенно вовлекая в групповую работу. 80% наших застенчивых учеников уже через месяц активно участвуют в занятиях, и чтобы вы сами увидели нашу методику в действии, первое занятие мы проводим бесплатно."}
                ]
            elif user_signal == "price_sensitive":
                # Для price_sensitive CTA в начале, БЕЗ дублирования!
                examples = [
                    {"role": "user", "content": "7000 грн в месяц?! Это грабёж!"},
                    {"role": "assistant", "content": "У нас действует скидка 10% при полной оплате курса - стоимость снижается до 6300 грн в месяц. Также доступна беспроцентная рассрочка на 3 месяца. За эти деньги ребёнок получает 8 занятий с профессиональным психологом в мини-группе до 6 человек. Это меньше, чем два занятия с репетитором, но результат гораздо масштабнее - развиваем навыки на всю жизнь, а не натаскиваем на предметы."},
                    {"role": "user", "content": "Дорого! У других дешевле!"},
                    {"role": "assistant", "content": "Доступна беспроцентная рассрочка на 3 месяца - всего 2300 грн в месяц. Для второго ребёнка скидка 15%. Да, массовые курсы по 15-20 человек дешевле, но у нас группы до 6 детей с персональным вниманием каждому. Преподаватели - практикующие психологи с опытом 8-15 лет, а не студенты. Вы платите за качество и результат, который виден уже через месяц занятий."},
                    {"role": "user", "content": "Сколько стоит? Дорого наверное?"},
                    {"role": "assistant", "content": "Стоимость от 6000 до 8000 грн в месяц, но есть скидка 10% при оплате полного курса - получается 5400 грн вместо 6000. Доступна беспроцентная рассрочка на 3 месяца через банк или наша на 5 месяцев. Для второго ребёнка скидка 15%. Это инвестиция в навыки, которые пригодятся всю жизнь - эмоциональный интеллект, лидерство, коммуникация."}
                ]
            else:  # exploring_only
                examples = [
                    {"role": "user", "content": "Добрый день! Расскажите подробнее о вашей методике"},
                    {"role": "assistant", "content": "Привет! Наша методика основана на практике - 80% времени дети активно участвуют в упражнениях и проектах. Мы развиваем навыки через игру и реальные ситуации: дети учатся выступать, работать в команде, управлять эмоциями. Каждое занятие включает разминку, основную активность и рефлексию. Используем современные инструменты вроде Miro для визуализации идей. Если захотите увидеть это на практике, первое пробное занятие у нас бесплатное - можно посмотреть как всё устроено изнутри."}
                ]
        
        return examples
    
    def _extract_key_info(self, cta_text: str) -> list:
        """Извлекает ключевые фразы из CTA для проверки
        
        Args:
            cta_text: Текст CTA
            
        Returns:
            Список ключевых фраз
        """
        keywords = []
        
        # Базовые ключевые слова для всех CTA
        if "пробное" in cta_text.lower() or "бесплатн" in cta_text.lower():
            keywords.extend(["пробное", "бесплатн"])
        if "скидк" in cta_text.lower():
            keywords.append("скидк")
        if "процент" in cta_text.lower():
            keywords.append("процент")
        if "shao3d.github.io" in cta_text.lower():
            keywords.append("shao3d.github.io")
        if "рассрочк" in cta_text.lower():
            keywords.append("рассрочк")
        if "запись" in cta_text.lower() or "запиш" in cta_text.lower():
            keywords.append("запис")
            
        return keywords
    
    def _make_urls_clickable(self, text: str) -> str:
        """Преобразует URL в тексте в HTML-ссылки

        Args:
            text: Текст для обработки

        Returns:
            Текст с кликабельными ссылками
        """
        # Паттерны для поиска URL (включая наш новый домен)
        url_patterns = [
            r'https?://[^\s/$]+',  # https://domain.tld/...
            r'shao3d\.github\.io/[^\s/]+',  # shao3d.github.io/...
            r'ukido\.com\.ua/[^\s/]+',  # ukido.com.ua/...
            r'(?:[^/]+\.)\.(?:com|ua|io|site|online|app|dev|stage|prod)[^\s/]+',  # domain.extension/
        ]

        def replace_url(match):
            url = match.group(0)
            # Добавляем https:// если нет протокола
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return f'<a href="{url}" target="_blank">{url}</a>'

        # Применяем ко всем найденным URL
        return re.sub('|'.join(url_patterns), replace_url, text)

    def _get_cta_marker(self, user_signal: str) -> str:
        """Возвращает невидимый маркер для отслеживания CTA

        Args:
            user_signal: Тип сигнала пользователя

        Returns:
            Пустую строку (маркеры больше не добавляются в текст)
        """
        # ИСПРАВЛЕНИЕ: Больше не возвращаем HTML комментарий
        # так как он становится виден пользователю
        # markers = {
        #     "anxiety_about_child": "[CTA_ANXIETY]",
        #     "price_sensitive": "[CTA_PRICE]",
        #     "ready_to_buy": "[CTA_READY]",
        #     "exploring_only": "[CTA_EXPLORE]"
        # }
        # marker = markers.get(user_signal, "[CTA]")
        # return f"<!-- {marker} -->"
        return ""  # Возвращаем пустую строку
