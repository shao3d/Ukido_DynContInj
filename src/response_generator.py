from pathlib import Path
from typing import List, Dict, Optional
from config import Config
from openrouter_client import OpenRouterClient
from standard_responses import DEFAULT_FALLBACK
from offers_catalog import get_offer, get_tone_adaptation, get_dynamic_example
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
        cfg = Config()
        # Используем Claude 3.5 Haiku для одноэтапной генерации с естественным стилем
        self.client = OpenRouterClient(
            cfg.OPENROUTER_API_KEY,
            seed=cfg.SEED,
            max_tokens=400,  # Ограничено для соблюдения лимита 100-150 слов
            temperature=0.1,  # Минимальная температура для точности
            model="anthropic/claude-3.5-haiku",  # Claude Haiku для качественных ответов
        )
        self.docs_dir = docs_dir or (Path(__file__).parent.parent / "data" / "documents_compressed")
        self.history_limit = cfg.HISTORY_LIMIT  # Используем настройку из конфига

    async def generate(
        self,
        router_result: Dict,
        history: Optional[List[Dict[str, str]]] = None,
        current_message: Optional[str] = None,
    ) -> str:
        if router_result.get("status") != "success":
            return DEFAULT_FALLBACK

        docs = router_result.get("documents") or []
        questions = router_result.get("decomposed_questions") or []
        if not docs or not questions:
            return DEFAULT_FALLBACK

        # Получаем user_signal для персонализации
        user_signal = router_result.get("user_signal", "exploring_only")
        
        doc_texts = self._load_docs(docs)
        
        # ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ: Если документов не загрузилось - отказываемся отвечать
        if not doc_texts:
            print("⚠️ ЗАЩИТА: Нет загруженных документов для генерации ответа")
            return "К сожалению, у меня нет информации по этому вопросу. Расскажите, что именно вас интересует о школе Ukido?"
        
        # Проверяем необходимость CTA ПЕРЕД генерацией
        cta_text = None
        cta_offer = None  # Сохраняем для fallback
        offer = get_offer(user_signal, history)
        if offer and offer["priority"] in ["high", "medium"]:
            print(f"🎯 DEBUG: Есть offer для {user_signal}, проверяем нужно ли добавлять...")
            should_add = self._should_add_offer(user_signal, history, offer, current_message)
            print(f"🎯 DEBUG: _should_add_offer вернул: {should_add}")
            if should_add:
                print(f"🎯 DEBUG: Будем встраивать CTA для {user_signal} органично")
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
                print(f"🎯 DEBUG: CTA НЕ будет добавлен для {user_signal}")
        
        # Одноэтапная генерация с Claude Haiku + dynamic few-shot + CTA (если нужен)
        messages = self._build_messages(doc_texts, questions, history or [], router_result, cta_text)

        try:
            reply = await self.client.chat(messages)
            cleaned = (reply or "").strip()
            if not cleaned:
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
            
            # Базовая очистка ответа
            sanitized = self._strip_source_citations(cleaned)
            polished = self._remove_question_headings(sanitized)
            humanized = self._humanize_missing_info(polished)
            no_labels = self._strip_service_labels(humanized)
            no_cta = self._strip_generic_cta(no_labels)
            
            # Финальная санитизация (убираем восклицания и дедупликация)
            final_text = self._final_sanitize(no_cta)
            
            # Постпроцессинг: исправляем приветствие с точкой на восклицательный знак
            if final_text.startswith("Привет."):
                final_text = "Привет!" + final_text[7:]
                print("✅ Исправлено приветствие: Привет. → Привет!")
            
            # Проверяем, встроил ли Claude CTA (если мы его запрашивали)
            if cta_text and cta_offer:
                if not self._verify_cta_included(final_text, cta_text):
                    # Fallback: Claude не встроил CTA, добавляем механически
                    print(f"⚠️ Claude не встроил CTA для {user_signal}, используем fallback")
                    final_text = self._inject_offer(final_text, cta_offer, user_signal)
                else:
                    print(f"✅ CTA успешно встроен органично для {user_signal}")
                    # Добавляем невидимый маркер для отслеживания
                    marker = self._get_cta_marker(user_signal)
                    if marker:
                        final_text += f"\n{marker}"
            
            return final_text
        except Exception as e:
            print(f"❌ Ошибка генерации ответа: {e}")
            return "Извините, временная техническая неполадка. Попробуйте еще раз."

    def _load_docs(self, docs: List[str]) -> Dict[str, str]:
        """Читает документы целиком из data/documents_compressed.
        Загружаем ВСЕ уникальные документы, выбранные Router (до 4 штук)."""
        texts: Dict[str, str] = {}
        
        # Дедупликация - убираем повторы
        unique_docs = list(dict.fromkeys(docs))  # Сохраняем порядок
        
        # Загружаем ВСЕ уникальные документы (Router уже ограничил до 4)
        docs_to_load = unique_docs
        
        for name in docs_to_load:
            try:
                path = self.docs_dir / name
                content = path.read_text(encoding="utf-8")
                texts[name] = content
            except FileNotFoundError:
                print(f"⚠️ Документ не найден: {name} ({self.docs_dir})")
            except Exception as e:
                print(f"⚠️ Ошибка чтения {name}: {e}")
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
            "КРИТИЧЕСКИ ВАЖНО - ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ:\n"
            "• ИСПОЛЬЗУЙ ТОЛЬКО информацию из предоставленных документов\n"
            "• НИКОГДА не выдумывай факты, цифры, детали\n"
            "• Если информации НЕТ в документах, отвечай ТОЛЬКО:\n"
            "  'К сожалению, у меня нет информации по этому вопросу. Могу рассказать о [релевантная тема из документов]'\n"
            "• НЕ придумывай: адреса, парковки, детали инфраструктуры, специфические условия\n"
            "• Все факты, цифры, цены — СТРОГО из документов\n"
            "• НЕ ИСПОЛЬЗУЙ ЭМОДЗИ В ОТВЕТАХ"
        )
        
        # Добавляем адаптацию тона если есть
        if tone_adaptation.get("style"):
            system_role += f"\n\nАДАПТАЦИЯ ТОНА:\n{tone_adaptation['style']}"
            # ВАЖНО: Усиливаем консистентность тона для user_signal
            tone_map = {
                "price_sensitive": "КРИТИЧНО: Родитель чувствителен к цене!\n"
                "ОБЯЗАТЕЛЬНО НАЧНИ ПЕРВОЕ ПРЕДЛОЖЕНИЕ СО СКИДКИ!\n"
                "Примеры правильного начала:\n"
                "• 'У нас есть скидка 10% при оплате всего курса сразу, что снижает стоимость до...'\n"
                "• 'Хорошая новость - доступна рассрочка без процентов на 3 месяца...'\n"
                "• 'Скидка 15% для второго ребёнка делает обучение доступнее...'\n"
                "Затем объясни ценность и ROI. Меньше эмпатии - больше конкретных выгод!",
                "anxiety_about_child": "КРИТИЧНО: Родитель тревожится за ребенка! ПЕРВОЕ ПРЕДЛОЖЕНИЕ ОБЯЗАТЕЛЬНО должно быть эмпатичным.\n\n⚠️ ВАЖНО - Вариативность формулировок:\n• НЕ используй слово 'понимаем' больше 1 раза за весь диалог\n• Каждый раз выбирай РАЗНУЮ формулировку эмпатии\n\nВарианты для первого предложения (выбирай разные):\n• 'Понимаем, как вам тяжело видеть, что ребенок страдает...' (использовать ТОЛЬКО 1 раз)\n• 'Это действительно непростая ситуация для любого родителя...'\n• 'Ваши переживания абсолютно естественны и обоснованы...'\n• 'Многие родители проходят через похожие чувства...'\n• 'Такие опасения знакомы большинству заботливых родителей...'\n• 'Родительская тревога в такой ситуации совершенно понятна...'\n• 'Важно, что вы так внимательны к состоянию ребенка...'\n• 'Детские переживания всегда отзываются в родительском сердце...'\n\nПОТОМ расскажи как школа помогает с подобными проблемами. Используй мягкий, поддерживающий тон.",
                "ready_to_buy": "НАЧНИ с конкретного действия: 'Для записи на курс...' или 'Следующий шаг - это...' БЕЗ лишней воды!",
                "exploring_only": "Будь информативным БЕЗ навязчивых предложений записаться. Это пассивные исследователи - дай им информацию без давления."
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
            word_limit = "150-180"  # Расширенный лимит когда нужно встроить CTA
        else:
            word_limit = "100-150"  # Стандартный лимит без CTA
        
        system_content += (
            "Стиль ответа:\n"
            "• Естественный разговорный язык от лица школы (используй 'мы', 'у нас', 'наши')\n"
            "• Короткие предложения, простые слова вместо канцелярских\n"
            f"• СТРОГО {word_limit} слов! Каждое слово свыше максимума - это НАРУШЕНИЕ\n"
            f"• Если получается больше {word_limit.split('-')[1]} слов - сократи детали, оставь только главное\n"
            "• НЕ ИСПОЛЬЗУЙ ЭМОДЗИ\n"
            "• ВАЖНО: Избегай шаблонных фраз! НЕ начинай с 'Мы понимаем', 'Мы точно понимаем' и подобных.\n"
            "  Вместо этого используй разнообразные начала: факты, вопросы, прямые ответы\n\n"
            "КРИТИЧЕСКИ ВАЖНО - Структура ответа:\n"
            "• ПЕРВЫЕ 2 ПРЕДЛОЖЕНИЯ должны содержать ключевую информацию!\n"
            "• Начинай с главного ответа, а не с вводных слов\n"
            "• Если родитель раздражён - первое предложение должно снизить напряжение\n"
            "• КРИТИЧНО для price_sensitive: ПЕРВОЕ ПРЕДЛОЖЕНИЕ ОБЯЗАТЕЛЬНО СО СКИДКОЙ!\n"
            "• Детали и пояснения - только после ключевой информации\n\n"
            "Примеры хороших начал:\n"
            "• Вопрос о цене → 'Месяц обучения стоит 6,000 грн. За эти деньги ребёнок получает...'\n"
            "• Сомнения в пользе → 'Дети учатся выступать публично и управлять эмоциями. После курса 85% становятся увереннее...'\n"
            "• Раздражение → 'Понимаем ваши опасения о цене. Давайте разберём что входит в стоимость...'\n\n"
            "Факты и цифры:\n"
            "• Все цифры, цены, проценты - ТОЛЬКО из документов, точно\n"
            "• Не выдумывай, не добавляй от себя\n"
            "• Если чего-то нет - скажи 'В наших материалах этого нет'\n"
            "• ВАЖНО: Смягчай слишком точные проценты и коэффициенты:\n"
            "  - Вместо '85%', '76%', '82%' → 'большинство', 'многие', 'около 80%'\n"
            "  - Вместо 'в 2.3 раза' → 'в два раза', 'значительно', 'существенно'\n"
            "  - НИКОГДА не говори '4.3 гривны эффекта' → используй 'окупается многократно'\n"
            "  - Используй: 'более половины', '7 из 10', 'подавляющее большинство'\n"
            "• НЕ используй псевдоточные цифры с десятичными (2.3, 4.3, 1.7)\n"
            "• Конкретные цены (6000 грн) оставляй как есть - это реальные тарифы\n\n"
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
        
        # Добавляем инструкцию по органичному встраиванию CTA если нужно
        if cta_text:
            cta_instruction = "\n\n💡 Добавление информации о пробном занятии:\n"
            cta_instruction += f"В конце ответа естественно упомяни: '{cta_text}'\n"
            cta_instruction += "Встрой это в последние 1-2 предложения твоего ответа.\n"
            cta_instruction += "Пример хорошей интеграции: '...и чтобы вы могли сами убедиться в нашем подходе, первое занятие проводится бесплатно.'\n"
            cta_instruction += "НЕ добавляй как отдельный абзац - сделай частью последнего предложения.\n"
            
            system_content += cta_instruction

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
        
        # Добавляем специальную инструкцию для price_sensitive
        price_instruction = ""
        if router_result.get("user_signal") == "price_sensitive":
            # Получаем оригинальное сообщение пользователя
            original_msg = router_result.get("original_message", "").lower().strip()
            
            # Проверяем длину оригинального сообщения
            word_count = len(original_msg.split())
            
            # Также проверяем декомпозированные вопросы
            questions_text = " ".join(questions).lower()
            price_keywords = ["цен", "стои", "скидк", "дорог", "оплат", "рассрочк", "грн", "гривен", "тысяч", "бюджет"]
            
            # Отладка для понимания логики
            print(f"🔍 DEBUG price_sensitive: original='{original_msg}', words={word_count}")
            
            # Умная логика: короткие реплики о цене всегда требуют скидки в начале
            if word_count <= 2 and any(keyword in original_msg for keyword in ["дорог", "скок", "стои", "цен"]):
                # Ультра-короткая эмоциональная реакция на цену - ОБЯЗАТЕЛЬНО скидки в начале
                price_instruction = (
                    "КРИТИЧНО: Короткая эмоциональная реакция на цену!\n"
                    "ОБЯЗАТЕЛЬНО начни ПЕРВОЕ ПРЕДЛОЖЕНИЕ со скидки или рассрочки!\n"
                    "Примеры для коротких реплик:\n"
                    "• 'Дорого' → 'Хорошая новость - есть скидка 10% при оплате курса сразу...'\n"
                    "• 'Скок стоит' → 'Месяц занятий от 6,000 грн, но с учётом скидки 10%...'\n\n"
                )
            elif any(keyword in questions_text for keyword in price_keywords):
                # Вопрос о цене - скидки в начале
                price_instruction = (
                    "⚠️ КРИТИЧНО: Родитель чувствителен к цене и спрашивает о стоимости!\n"
                    "ОБЯЗАТЕЛЬНО начни ПЕРВОЕ ПРЕДЛОЖЕНИЕ со скидки или рассрочки!\n"
                    "Примеры: 'Хорошая новость - у нас есть скидка 10% при оплате курса...'\n"
                    "или 'Доступна рассрочка без процентов на 3 месяца...'\n\n"
                )
            else:
                # Вопрос НЕ о цене - упомяни скидки мягко в середине или конце
                price_instruction = (
                    "Родитель чувствителен к цене, но вопрос не о стоимости.\n"
                    "Сначала ответь на вопрос по существу, затем мягко упомяни доступные скидки или рассрочку.\n"
                    "Пример: после основного ответа добавь 'Кстати, у нас сейчас есть скидка 10%...'\n\n"
                )
        
        messages.append(
            {
                "role": "user",
                "content": (
                    social_instruction +
                    price_instruction +
                    "Ответь на вопросы естественным живым языком. "
                    "ВАЖНО: Объём СТРОГО 100-150 слов (не больше!). Не повторяй то, что уже было сказано.\n"
                    "НЕ ИСПОЛЬЗУЙ ЭМОДЗИ.\n"
                    "Аспекты для учёта:\n" + questions_block
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
        text_out = re.sub(r"\n{3,}", "\n\n", text_out)
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
        
        # Контекстная проверка: не дублировать информацию из вопроса пользователя
        # Используем current_message если передан, иначе берём из истории
        if current_message:
            last_user_msg = current_message.lower()
        else:
            last_user_msg = ""
            for msg in reversed(history):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "").lower()
                    break
        
        # Если пользователь ПРЯМО спрашивает о скидках - пропускаем CTA про скидки
        if user_signal == "price_sensitive":
            # Проверяем только прямые вопросы о скидках/рассрочке
            skip_phrases = ["скидки", "скидка", "рассрочк", "есть ли скидк", "какие скидк"]
            print(f"🔍 DEBUG _should_add_offer для price_sensitive:")
            print(f"   last_user_msg: '{last_user_msg}'")
            print(f"   skip_phrases: {skip_phrases}")
            
            for phrase in skip_phrases:
                if phrase in last_user_msg:
                    print(f"   ✅ Найдена фраза '{phrase}' в сообщении пользователя")
                    print("🔄 Контекст: Пользователь прямо спрашивает про скидки, пропускаем CTA")
                    return False
            print(f"   ❌ Контекстная проверка пройдена, проверяем rate limiting...")
        
        # Для price_sensitive - не чаще чем каждое второе сообщение
        if user_signal == "price_sensitive":
            # Проверяем последние 2 сообщения ассистента
            recent_count = 0
            for msg in history[-4:]:  # Последние 2 пары сообщений
                if msg.get("role") == "assistant" and "[CTA_PRICE]" in msg.get("content", ""):
                    recent_count += 1
            
            # Если CTA был в предыдущем сообщении - пропускаем (через одно)
            if recent_count >= 1:
                print("🔄 Rate limiting: CTA для price_sensitive был в предыдущем сообщении")
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
            # Ждём минимум 2 сообщения с anxiety, чтобы сначала построить доверие
            if anxiety_count < 2:
                print(f"🕑 Задержка CTA для anxiety: только {anxiety_count} сообщений с этим сигналом, нужно минимум 2")
                return False
            
            # Контекстная проверка - не дублируем информацию о пробном занятии
            last_user_msg = history[-1].get("content", "").lower() if history else ""
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
                # Проверяем разные варианты CTA для anxiety
                anxiety_cta_markers = [
                    "[CTA_ANXIETY]",
                    "родителей стеснительных детей",
                    "пробное занятие",
                    "Волнение перед новым опытом естественно",
                    "Первое занятие всегда бесплатное",
                    "подходит ли наш подход вашему ребенку"
                ]
                if any(marker in msg_content for marker in anxiety_cta_markers):
                    print("🔄 Rate limiting: CTA для anxiety был недавно, пропускаем")
                    return False
        
        # Для ready_to_buy - rate limiting и контекстная проверка
        if user_signal == "ready_to_buy":
            # Контекстная проверка - если пользователь уже говорит о записи
            last_user_msg = history[-1].get("content", "").lower() if history else ""
            recording_phrases = ["записалась", "записался", "отправил", "заполнил", "зарегистрировал"]
            if any(phrase in last_user_msg for phrase in recording_phrases):
                print("🔄 Контекст: Пользователь уже записался, пропускаем CTA")
                return False
            
            # Rate limiting - не чаще чем каждое второе сообщение
            recent_count = 0
            for msg in history[-4:]:  # Последние 2 пары сообщений
                if msg.get("role") == "assistant" and "[CTA_READY]" in msg.get("content", ""):
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
            transition = "!\n\n"  # Восклицательный знак для urgency
        else:
            transition = ".\n\n"  # Обычная точка
        
        # Определяем маркер в зависимости от user_signal
        markers = {
            "anxiety_about_child": "[CTA_ANXIETY] ",
            "price_sensitive": "[CTA_PRICE] ",
            "ready_to_buy": "[CTA_READY] ",
            "exploring_only": ""
        }
        marker = markers.get(user_signal, "")
        
        # Добавляем предложение с маркером
        return f"{response_trimmed}{transition}{marker}{offer['text']}"
    
    def _count_cta_occurrences(self, user_signal: str, history: list) -> int:
        """Подсчитывает, сколько раз CTA для данного сигнала уже был показан
        
        Args:
            user_signal: Тип сигнала пользователя
            history: История диалога
            
        Returns:
            Количество показов CTA
        """
        if not history:
            return 0
            
        # Определяем маркер для подсчёта
        markers = {
            "anxiety_about_child": "[CTA_ANXIETY]",
            "price_sensitive": "[CTA_PRICE]",
            "ready_to_buy": "[CTA_READY]",
            "exploring_only": "[CTA_EXPLORE]"
        }
        marker = markers.get(user_signal)
        
        if not marker:
            return 0
            
        count = 0
        for msg in history:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if marker in content:
                    count += 1
                    
        return count
    
    def _verify_cta_included(self, response: str, cta_text: str) -> bool:
        """Проверяет, включил ли Claude CTA в ответ
        
        Args:
            response: Сгенерированный ответ
            cta_text: Оригинальный текст CTA
            
        Returns:
            True если ключевые элементы CTA присутствуют
        """
        # Извлекаем ключевые слова из CTA
        key_phrases = self._extract_key_info(cta_text)
        
        if not key_phrases:
            return False
            
        response_lower = response.lower()
        found_count = 0
        
        for phrase in key_phrases:
            if phrase.lower() in response_lower:
                found_count += 1
        
        # Считаем успешным если найдено >50% ключевых фраз
        return found_count >= len(key_phrases) * 0.5
    
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
                examples = [
                    {"role": "user", "content": "Здравствуйте! Хочу записать ребёнка на курс. Что нужно сделать?"},
                    {"role": "assistant", "content": "Привет! Для записи нужны только паспорт родителя и свидетельство о рождении ребёнка. Группы стартуют каждый понедельник, занятия проходят онлайн два раза в неделю. Оплата возможна картой или переводом, есть рассрочка на 3 месяца. Чтобы вы могли убедиться в нашем подходе, первое занятие проводится бесплатно - переходите на ukido.ua/trial и выбирайте удобное время."},
                    {"role": "user", "content": "Запишите нас на курс лидерства"},  
                    {"role": "assistant", "content": "Курс \"Капитан Проектов\" для подростков 11-14 лет развивает лидерские навыки через работу над реальными проектами. Занятия онлайн два раза в неделю по 90 минут, стоимость 8000 грн в месяц. Записаться на пробное занятие можно прямо сейчас на ukido.ua/trial - осталось всего несколько мест в ближайшей группе."}
                ]
            elif user_signal == "anxiety_about_child":
                examples = [
                    {"role": "user", "content": "Мой ребёнок очень стеснительный, боюсь не справится"},
                    {"role": "assistant", "content": "Понимаем вашу тревогу - многие родители приходят именно с такой проблемой. У нас маленькие группы до 6 детей, что создаёт безопасную атмосферу. Педагоги специально обучены работе со стеснительными детьми - начинаем с парных упражнений, постепенно вовлекая в групповую работу. 80% наших застенчивых учеников уже через месяц активно участвуют в занятиях, а чтобы вы сами увидели нашу методику в действии, первое занятие мы проводим бесплатно."}
                ]
            elif user_signal == "price_sensitive":
                examples = [
                    {"role": "user", "content": "Сколько стоит обучение? Дорого наверное?"},
                    {"role": "assistant", "content": "У нас есть скидка 10% при оплате полного курса - так месяц обучения обойдётся в 5400 грн вместо 6000. Доступна беспроцентная рассрочка на 3 месяца через банк или наша внутренняя на 5 месяцев. Для второго ребёнка скидка 15%. Это инвестиция в навыки, которые пригодятся всю жизнь, и чтобы вы могли оценить качество обучения, первое занятие проводим бесплатно."}
                ]
            else:  # exploring_only
                examples = [
                    {"role": "user", "content": "Добрый день! Расскажите подробнее о вашей методике"},
                    {"role": "assistant", "content": "Привет! Наша методика основана на практике - 80% времени дети активно участвуют в упражнениях и проектах. Мы развиваем навыки через игру и реальные ситуации: дети учатся выступать, работать в команде, управлять эмоциями. Каждое занятие включает разминку, основную активность и рефлексию. Используем современные инструменты вроде Miro для визуализации идей, и чтобы вы сами увидели как это работает, приглашаем на бесплатное пробное занятие."}
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
        if "ukido.ua" in cta_text.lower():
            keywords.append("ukido.ua")
        if "рассрочк" in cta_text.lower():
            keywords.append("рассрочк")
        if "запись" in cta_text.lower() or "запиш" in cta_text.lower():
            keywords.append("запис")
            
        return keywords
    
    def _get_cta_marker(self, user_signal: str) -> str:
        """Возвращает невидимый маркер для отслеживания CTA
        
        Args:
            user_signal: Тип сигнала пользователя
            
        Returns:
            HTML-комментарий с маркером (невидим для пользователя)
        """
        markers = {
            "anxiety_about_child": "[CTA_ANXIETY]",
            "price_sensitive": "[CTA_PRICE]",
            "ready_to_buy": "[CTA_READY]",
            "exploring_only": "[CTA_EXPLORE]"
        }
        marker = markers.get(user_signal, "[CTA]")
        # Возвращаем как HTML-комментарий, который не будет виден пользователю
        return f"<!-- {marker} -->"
