from pathlib import Path
from typing import List, Dict, Optional, Set
from config import Config
from openrouter_client import OpenRouterClient, OpenRouterError
from standard_responses import DEFAULT_FALLBACK
from offers_catalog import get_offer, get_tone_adaptation, get_dynamic_example
from translator import SmartTranslator, TranslationError
from localization import has_cyrillic, looks_russian
import html
import json
import re
from urllib.parse import urlparse

# SEC-03: пунктуация, которую отрезаем с конца URL (конец предложения,
# закрывающая скобка) — в ссылку она не входит.
_TRAILING_PUNCT = frozenset(['.', ',', ';', ':', '!', '?', ')', ']', '}'])

# Грубые обвинения/возмущение по стеммам (не точным подстрокам: раньше
# «выкачивать» не матчилось «выкачивание», и ветка особой обработки
# агрессии не срабатывала никогда). В агрессивном контексте CTA-предложения
# запрещены — скидка в ответ на «вы мошенники» звучит невпопад.
_AGGRESSIVE_RE = re.compile(
    r"(?:развод\w*|обман\w*|выкачива\w*|мошенник\w*|врань\w*|шарлатан\w*|"
    r"лабуда|лохотрон\w*|граб[её]ж|нажива[ею]\w*|"
    r"розвод\w*|шахра\w*|обдира\w*|знуща\w*|"
    r"scam|rip[\s-]?off|fraud\w*|con[-\s]?art)",
    re.IGNORECASE,
)


def is_aggressive_message(text: str) -> bool:
    """True, если сообщение несёт обвинения/грубое возмущение."""
    return bool(text) and bool(_AGGRESSIVE_RE.search(text))

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
        # Клиент по умолчанию на низкой температуре (её же наследует
        # переводчик); генерация ответа переопределяет её per-call через
        # config.ANSWER_TEMPERATURE (P1: 0.1 давала «брошюрный» стиль).
        self.client = OpenRouterClient(
            self.cfg.OPENROUTER_API_KEY,
            seed=self.cfg.SEED,
            max_tokens=self.cfg.MAX_TOKENS_ANSWER,  # Используем настройку из конфига (1200 токенов)
            temperature=0.1,  # Дефолт клиента: точность (переводы и прочие per-call без температуры)
            model=self.cfg.MODEL_ANSWER,
        )
        self.docs_dir = docs_dir or (Path(__file__).parent.parent / "data" / "documents_compressed")
        self.history_limit = self.cfg.HISTORY_LIMIT  # Используем настройку из конфига
        self.translator = SmartTranslator(self.client, model=self.cfg.TRANSLATION_MODEL)  # Инициализируем переводчик
        # SEC-01: allowlist имён документов (ленивый кэш, см. _load_summaries_keys).
        # Тесты могут подменить напрямую.
        self._allowed_docs: Optional[Set[str]] = None

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
        
        # Одноэтапная генерация с Gemini + dynamic few-shot + CTA (если нужен)
        messages = self._build_messages(doc_texts, questions, history or [], router_result, cta_text)

        try:
            reply = await self.client.chat(
                messages, temperature=self.cfg.ANSWER_TEMPERATURE
            )
            cleaned = (reply or "").strip()
            if not cleaned:
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос.", {"intent": "error", "user_signal": user_signal, "cta_added": False, "cta_type": None, "humor_generated": False}
            
            # Базовая очистка ответа
            sanitized = self._strip_source_citations(cleaned)
            polished = self._remove_question_headings(sanitized)
            humanized = self._humanize_missing_info(polished)
            no_labels = self._strip_service_labels(humanized)
            no_cta = self._strip_generic_cta(no_labels)
            no_markdown = self._strip_markdown_formatting(no_cta)

            # Финальная санитизация (точечные стражи; абзацы/эмоции сохраняем)
            final_text = self._final_sanitize(no_markdown)
            
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
            # Кроме случая, когда пользователь сам сообщил о завершённом действии —
            # предлагать запись уже записавшемуся = «меню человеку с тарелкой супа»
            trial_words = ["попроб", "пробн", "давайте попробуем", "хочу попробовать", "запишите на пробное",
                           # LANG-07: uk-формы записи на пробное
                           "спроб", "хочу спробувати", "запишіть на пробне", "записатися на пробне",
                           "try it", "want to try", "trial class", "free class", "sign us up"]
            trial_url = self.cfg.TRIAL_SIGNUP_URL
            if (current_message and not router_result.get("user_completed_action")
                    and any(word in current_message.lower() for word in trial_words)):
                # Проверяем, есть ли уже контакты в ответе (любое упоминание ukido считается контактом)
                guard_tokens = ["ukido", "запишитесь", "запись", trial_url.lower()]
                if not any(contact in final_text.lower() for contact in guard_tokens):
                    final_text = final_text.rstrip() + self._build_contact_suffix()
                    print("✅ Добавлены контакты для пробного занятия")
            
            # 4. Обработка непонимания формата обучения (проблема "забирать")
            # EN-фразы намеренно конкретные: голое "pick up" ловит "pick up skills"
            transport_words = ["забира", "привози", "довози", "везти", "отвози", "вожу", "везу", "заберу", "привезу",
                               "pick him up", "pick her up", "pick them up", "pick up my kid",
                               "pick up my child", "pick up my son", "pick up my daughter",
                               "drop him off", "drop her off", "drop them off",
                               "drive him to", "drive her to", "take him to class", "take her to class"]
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
                        if "после работы" in current_message.lower() or "after work" in current_message.lower():
                            prefix = "Удобно, что после работы вам не придётся никуда ехать - занятия проходят онлайн через Zoom, ребёнок учится из дома. "
                        elif "далеко" in current_message.lower() or "far away" in current_message.lower() or "far from" in current_message.lower():
                            prefix = "Отличная новость - не нужно никуда ехать! Все занятия проходят онлайн через Zoom. "
                        else:
                            prefix = "Занятия проходят полностью онлайн через Zoom, поэтому забирать ребёнка не нужно - он учится из дома. "
                        
                        final_text = prefix + final_text
                        print("✅ Добавлено уточнение про онлайн-формат в начало ответа")
            
            # Проверяем, встроила ли модель CTA (если мы его запрашивали)
            cta_was_added = False
            if cta_text and cta_offer:
                # Определяем контекст агрессивности (единая стемм-проверка)
                is_aggressive = is_aggressive_message(current_message)
                context_type = "агрессивный" if is_aggressive else "нормальный"
                
                if not self._verify_cta_included(final_text, cta_text):
                    # Fallback: модель не встроила CTA, добавляем механически
                    print(f"⚠️ ПРОВАЛ: модель НЕ встроила CTA для {user_signal}")
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
                # BUG-01: translated_to ставится ТОЛЬКО при реальном успехе.
                # Сбой помечается translation_failed — финальный шлюз в main.py
                # повторит попытку, а не пропустит русский текст как «готовый».
                try:
                    final_text = await self.translator.translate(
                        text=final_text,
                        target_language=detected_language,
                        user_context=current_message
                    )
                except TranslationError as exc:
                    print(f"⚠️ BUG-01: перевод на {detected_language} не удался: {exc}")
                    metadata["translation_failed"] = True
                    metadata["detected_language"] = detected_language
                else:
                    # BUG-01: «тихий» сбой — модель не перевела, а вернула
                    # русский текст без исключения. Проверяем язык результата:
                    # en — кириллица недопустима; uk — кириллица нормальна, но
                    # нужно именно украинское, а не русское. Иначе не помечаем
                    # translated_to и отдаём шлюзу повторить/извиниться.
                    if (detected_language == "en" and has_cyrillic(final_text)) or (
                        detected_language == "uk" and looks_russian(final_text)
                    ):
                        print(f"⚠️ BUG-01: перевод на {detected_language} вернул исходный язык")
                        metadata["translation_failed"] = True
                        metadata["detected_language"] = detected_language
                    else:
                        # Добавляем информацию о переводе в metadata
                        metadata["translated_to"] = detected_language
                        metadata["detected_language"] = detected_language

            # Markdown может вернуться и из перевода (EN-ответы с **...**):
            # снимаем разметку ПОСЛЕ перевода тоже, чат рендерит её сырым текстом.
            final_text = self._strip_markdown_formatting(final_text)

            # НОВОЕ: Преобразуем URL в кликабельные HTML-ссылки
            self._debug(f"🔗 DEBUG: До преобразования URL: {final_text[:100]}...")
            final_text = self._make_urls_clickable(final_text)
            self._debug(f"🔗 DEBUG: После преобразования URL: {final_text[:100]}...")

            return final_text, metadata
        except OpenRouterError as e:
            # BUG-04: модель не ответила — честная ошибка, а не строка сбоя
            # как контент. Текст русским: шлюз в main.py переведёт при нужде.
            print(f"❌ BUG-04: генерация невозможна ({type(e).__name__}): {e}")
            return "Извините, временная техническая неполадка. Попробуйте еще раз.", {
                "intent": "error",
                "user_signal": user_signal,
                "cta_added": False,
                "cta_type": None,
                "humor_generated": False
            }
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

    def _load_summaries_keys(self) -> Set[str]:
        """Allowlist имён документов по ключам summaries.json (защита SEC-01).

        Канонический список документов. Если summaries.json недоступен —
        fallback на *.md-файлы, реально лежащие в docs_dir (злоумышленник
        всё равно не может подсунуть туда файлы через чат).
        """
        if self._allowed_docs is not None:
            return self._allowed_docs
        try:
            path = Path(__file__).parent.parent / "data" / "summaries.json"
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._allowed_docs = {k for k in data.keys() if isinstance(k, str)}
        except Exception as e:
            print(f"⚠️ SEC-01: allowlist из summaries.json недоступен ({e}), fallback на файлы docs_dir")
            self._allowed_docs = {p.name for p in self.docs_dir.glob("*.md")}
        return self._allowed_docs

    def _is_allowed_doc(self, doc_name: str) -> bool:
        """SEC-01: строгая проверка имени документа ДО чтения с диска.

        Имена документов приходят от LLM (см. router.py), поэтому каждое имя
        обязано: быть плоским именем .md-файла, входить в allowlist и после
        resolve() оставаться внутри docs_dir (защита от ../ и симлинков).
        """
        if not isinstance(doc_name, str) or not doc_name:
            return False
        if not doc_name.endswith(".md"):
            return False
        if "/" in doc_name or "\\" in doc_name or "\x00" in doc_name:
            return False
        if doc_name not in self._load_summaries_keys():
            return False
        try:
            resolved = (self.docs_dir / doc_name).resolve()
            if not resolved.is_relative_to(self.docs_dir.resolve()):
                return False
        except Exception:
            return False
        return True

    def _load_doc(self, doc_name: str) -> str:
        """Синхронная загрузка документа - ОТКАТ асинхронности"""
        if not self._is_allowed_doc(doc_name):
            print(f"⛔ SEC-01: отклонено имя документа: {doc_name!r}")
            return ""
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
        
        # Объединённый промпт для Gemini - факты + стиль + адаптация
        system_role = (
            "Ты — консультант детской школы soft skills Ukido в онлайн-чате. "
            "Пиши так, как заботливый администратор пишет родителю в мессенджере: "
            "тепло, просто и по делу (от лица школы — 'мы', не 'я').\n"
            "Живой разговорный текст, не буклет. Можно эмоциональные оттенки "
            "и уместные восклицательные знаки — но без сюсюканья и эмодзи.\n"
            "Пиши уверенно и ободряюще: факты из наших материалов приводи "
            "утвердительно. Одна короткая честная оговорка уместна, но не "
            "превращай ответ в юридический документ: без «мы не можем "
            "гарантировать», «мы не знаем», извинений за наши же факты и "
            "трёх оговорок подряд.\n\n"
            "ЖЕЛЕЗНЫЕ ПРАВИЛА - ИСТОЧНИКИ ИНФОРМАЦИИ:\n"
            "• ВСЕ факты, цифры, детали - ТОЛЬКО из предоставленных документов\n"
            "• Нет информации? Скажи: 'У меня нет данных по этому вопросу'\n"
            "• НЕ выдумывай: API, сроки, функции, технические детали\n"
            "• Сравнение с другими школами: не гадай о чужих ценах, но уверенно "
            "объясняй, из чего складывается наша цена и какую ценность она даёт\n"
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
        
        # Добавляем мягкую инструкцию по органичному встраиванию CTA ПЕРЕД адаптацией тона.
        # CTA сюда доходит только после проверок уместности (агрессивный контекст
        # отсекается в _should_add_offer), поэтому императивы «начни со скидки»
        # больше не нужны и вредны: они заставляли модель открывать скидкой
        # даже ответ на вопрос «а что вы вообще делаете на занятиях».
        if cta_text:
            # Базовая инструкция о наличии CTA (упоминаем в начале)
            system_role += (
                "\n\nВ этом ответе ты можешь органично интегрировать информацию о специальном предложении.\n"
                "Детальные инструкции будут в конце запроса.\n"
            )

            cta_examples = {
                "price_sensitive": (
                    "Родитель чувствителен к цене.\n"
                    "Упомяни ОДИН РАЗ подходящий вариант оплаты ТАМ, где он отвечает на вопрос:\n"
                    "• 'При полной оплате курса действует скидка 10%, это заметно снижает итоговую стоимость.'\n"
                    "• 'Есть беспроцентная рассрочка на 3 месяца — платёж делится на удобные части.'\n"
                    "• 'Для второго ребёнка из семьи — скидка 15%.'\n"
                    "• 'Чтобы сделать обучение доступнее, у нас гибкая система оплаты.'\n"
                    "• 'Сейчас действует скидка 10% при оплате полного курса.'\n\n"
                    "НЕ начинай ответ со скидки, если вопрос о другом или родитель раздражён: "
                    "сначала ответь по сути, финансовые варианты — как уместное дополнение."
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
                "price_sensitive": "Родитель чувствителен к цене.\n"
                "• Сначала ответь по сути вопроса и обоснуй ценность.\n"
                "• Варианты оплаты (скидка 10% при полной оплате, рассрочка на 3 месяца, "
                "15% на второго ребёнка) упомяни ОДИН РАЗ и только если они к месту.\n"
                "• НЕ начинай ответ со скидки, если вопрос не о цене.\n"
                "• Без канцелярита: не «высокая стоимость обоснована», а живое объяснение, "
                "что входит в цену (мини-группы, опытные педагоги, обратная связь).",
                
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
                if (user_signal == "price_sensitive"
                        and is_aggressive_message(router_result.get("original_message"))):
                    # Возмущённому и недоверчивому родителю про скидки/рассрочку
                    # не говорим вообще — CTA для этого контекста уже заблокированы,
                    # но и тон-инструкция не должна подталкивать к ним.
                    system_role += (
                        "\n\nПользователь возмущён и не доверяет школе.\n"
                        "• Сначала ответь на возражение по существу, спокойно и с достоинством.\n"
                        "• НЕ предлагай скидки, рассрочку и вообще не упоминай оплату — это усилит недоверие.\n"
                        "• Опирайся на факты, восстанавливающие доверие: квалификация педагогов, "
                        "методика, результаты учеников.\n"
                    )
                else:
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
        
        # Мягкий ориентир объёма (P1): жёсткий корсет «СТРОГО N слов» ломал
        # сильные модели (мета-артефакты «(53 words)») и усреднял стиль Lite.
        word_limit = "90-150" if cta_text else "70-120"

        system_content += (
            "СТРУКТУРА И СТИЛЬ ОТВЕТА:\n"
            f"• Объём: ориентировочно {word_limit} слов; на простой вопрос отвечай короче\n"
            "• Язык: разговорный от лица школы ('мы', 'у нас', 'наши')\n"
            "• Главное — ближе к началу ответа\n"
            "• Абзацы по 1-3 предложения, между ними пустая строка\n"
            "• Варьируй начала фраз, избегай шаблонов\n"
            "• БЕЗ эмодзи\n\n"
            "Принцип ответа по сигналам:\n"
            "• price_sensitive → сначала суть вопроса, про скидку/рассрочку — если уместно\n"
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
            "• НЕ опровергай факты, которые школа уже привела в этом диалоге: "
            "если они из наших материалов — они верны. Уточнять детали можно, отрекаться — нет\n"
            "• ИГНОРИРУЙ старые offtopic вопросы из истории (парковка, футбол, погода)\n"
            "• НЕ УПОМИНАЙ в новом ответе темы, которые были отклонены как offtopic\n"
            "• Фокусируйся ТОЛЬКО на текущем вопросе пользователя\n"
            "• Пример НЕПРАВИЛЬНО: 'К сожалению, в наших документах нет информации о парковке. Для зачисления нужны...'\n"
            "• Пример ПРАВИЛЬНО: 'Для зачисления нужны следующие документы...'\n\n"
            "Избегай:\n"
            "• Избытка восклицательных знаков (один уместный — можно)\n"
            "• Клише: 'Знаете', 'Многие родители отмечают', 'так что', 'не переживайте'\n"
            "• Официальных формулировок: 'осуществляется', 'предоставляется', 'производится'\n"
            "• Повторов информации\n"
            "• Навязчивых CTA в конце ('Пишите', 'Звоните', 'Остались вопросы?')\n"
            "• Приветствий ('Здравствуйте', 'Привет') если диалог уже начался - сразу отвечай по сути\n"
            "• Markdown-разметки ('**жирный**', '# заголовки') — чат покажет её сырым текстом\n"
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

        # Завершённое действие на success-ветке: модель ДОЛЖНА знать, что
        # действие выполнено. Раньше это чинилось префиксом-склейкой поверх
        # сгенерированного текста — получалось «вы записаны! Заполните форму…».
        completed_action = router_result.get("user_completed_action")
        if completed_action:
            action_names = {
                "paid": "оплату",
                "registered": "запись",
                "trial_completed": "пробное занятие",
                "form_filled": "заявку/форму",
            }
            action_done = action_names.get(completed_action, "действие")
            social_instruction += (
                f"ВАЖНО: пользователь УЖЕ выполнил действие ({action_done}). "
                "НЕ предлагай и НЕ объясняй, как выполнить его снова. "
                "Коротко подтверди факт первым предложением и расскажи только о "
                "следующих шагах (подтверждение, связь менеджера, что будет дальше).\n"
            )
        if social_context:
            # Router уже определил правильный social_context (greeting или repeated_greeting)
            # Больше не нужна дополнительная проверка истории.
            # ВАЖНО: именно += — не перезаписывать инструкцию завершённого
            # действия выше (иначе «Привет! Я оплатила» теряла её).
            social_map = {
                "greeting": "Пользователь поздоровался. Начни ответ с короткого приветствия.",
                "repeated_greeting": "Пользователь здоровается повторно. Не здоровайся снова — можешь мягко отметить это ('Мы уже поздоровались' или 'Ещё раз здравствуйте!'), затем сразу отвечай по сути вопроса.",
                "thanks": "Пользователь поблагодарил. Начни с благодарности или подтверждения готовности помочь.",
                "apology": "Пользователь извинился. Начни с успокаивающей фразы, показывающей что всё хорошо и не стоит беспокоиться.",
                "farewell": "Пользователь прощается. Добавь прощание в конце ответа."
            }
            social_instruction += social_map.get(social_context, "") + "\n"
        
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
            
            # Дифференцированная позиция CTA в зависимости от сигнала.
            # Без кричащих императивов («ПРОВАЛ», 🔴🔴🔴): они провоцировали
            # шаблонные ответы и протечку плейсхолдеров. Одна спокойная просьба
            # встроить ОДИН РАЗ — достаточна для моделей уровня Flash.
            if user_signal == "ready_to_buy":
                self._debug(f"   Позиция: в НАЧАЛЕ ответа (ready_to_buy)")
                cta_final_instruction = (
                    f"\n\nПользователь готов записаться. Начни ответ с конкретного шага записи:\n"
                    f"'{cta_text}'\n\n"
                    f"Упомяни это один раз в начале, не дублируй в конце.\n"
                    f"После шага записи можешь добавить 1-2 предложения о гарантиях."
                )
            elif user_signal == "price_sensitive":
                self._debug(f"   Позиция: по смыслу (price_sensitive)")
                cta_final_instruction = (
                    f"\n\n{cta_detail_instruction}\n"
                    f"Информация для интеграции (один раз, там где это отвечает на вопрос): '{cta_text}'\n"
                    f"Не начинай и не заканчивай ею, если она не по теме вопроса."
                )
            else:
                self._debug(f"   Позиция: в КОНЦЕ ответа (exploring/anxiety)")
                cta_final_instruction = (
                    f"\n\n{cta_detail_instruction}\n"
                    f"Информация для интеграции: '{cta_text}'\n"
                    f"Уместнее всего — последним предложением, как естественное завершение. Один раз, без дублирования."
                )
        
        messages.append(
            {
                "role": "user",
                "content": (
                    social_instruction +
                    price_instruction +
                    "Ответь на вопросы естественным живым языком, "
                    "как заботливый администратор пишет родителю в мессенджере. "
                    "Не повторяй то, что уже было сказано. "
                    "Раздели ответ на 1-3 коротких абзаца через пустую строку. "
                    "НЕ ИСПОЛЬЗУЙ ЭМОДЗИ.\n"
                    "Аспекты для учёта:\n" + questions_block +
                    cta_final_instruction  # CTA инструкция теперь в самом конце!
                ),
            }
        )
        return messages

    def _build_contact_suffix(self) -> str:
        """Контакты записи на пробное — только из Config.

        Раньше здесь был захардкожен телефон, которого нет в базе знаний:
        такие детали берутся из единственного источника (TRIAL_SIGNUP_URL /
        CONTACT_PHONE), пустой телефон в ответ не попадает.
        """
        suffix = f"\n\nЗаписаться на пробное занятие: {self.cfg.TRIAL_SIGNUP_URL}"
        if self.cfg.CONTACT_PHONE:
            suffix += f" или позвоните {self.cfg.CONTACT_PHONE}"
        return suffix

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

    def _strip_markdown_formatting(self, text: str) -> str:
        """Чат рендерит ответ как plain text: markdown заголовки и **жирный**
        выглядят сырым мусором. Сильные модели (haiku и др.) структурируют
        ответ разметкой — снимаем её точечно, содержимое сохраняя."""
        out = re.sub(r"^#{1,6}\s+(.*)$", r"\1", text, flags=re.MULTILINE)
        out = out.replace("**", "")
        out = re.sub(r"^__([^_]+)__$", r"\1", out, flags=re.MULTILINE)
        return out

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
    
    @staticmethod
    def _replace_terms(text: str, mapping: Dict[str, str]) -> str:
        """Заменяет слова/фразы по границам слов, сохраняя регистр.

        BUG-17/LANG-A4: в отличие от `str.replace`, не подменяет подстроки
        внутри других слов. Порядок ключей — от длинных к коротким, чтобы
        «team building» срабатывал раньше «team».
        """
        if not text or not mapping:
            return text
        keys = sorted(mapping, key=len, reverse=True)
        pattern = re.compile(
            r"(?<!\w)(" + "|".join(re.escape(key) for key in keys) + r")(?!\w)",
            re.IGNORECASE,
        )

        def repl(match: "re.Match") -> str:
            source = match.group(0)
            target = mapping[source.lower()]
            if source.isupper() and len(source) > 1:
                return target.upper()
            if source[:1].isupper():
                return target[:1].upper() + target[1:]
            return target

        return pattern.sub(repl, text)

    def _final_sanitize(self, text: str) -> str:
        """Финальные стражи: термины, обрезанный хвост, известные артефакты.

        P1: отсюда удалены ампутация восклицательных знаков, регэксп-
        дедупликация предложений и механическая нарезка абзацев — они
        сглаживали ответ в «безэмоциональный бетон», а вместе со схлопыванием
        `\s{2,}` уничтожали абзацные разрывы, которые даёт модель (дедуп
        склеивал всё в одну строку, а «принудительные абзацы» рубили её
        заново по 2-3 предложения). Живость текста делает промпт генератора,
        здесь остаются только точечные фактические стражи.
        """
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

        # Заменяем украинские слова на русские эквиваленты
        # (модель иногда генерирует украинские слова из-за контекста украинской школы)
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

        # BUG-17/LANG-A4: только по границам слов. Раньше `str.replace`
        # подменял подстроки и калечил слова («mentor» → «наставникing»,
        # «діти» внутри «дітей»). Регистр сохраняем: lower / Capitalized / UPPER.
        out = self._replace_terms(out, english_to_russian)
        out = self._replace_terms(out, ukrainian_to_russian)

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
        out = re.sub(r'(\d+)-([а-яёіїєґ]+)00\b', r'\1-\2', out, flags=re.IGNORECASE)

        # 2. ИСПРАВЛЕНО: Убираем "00" только после БУКВ, не после цифр!
        # Это предотвратит удаление нулей из "7000", "2800" и т.д.
        out = re.sub(r'([а-яА-ЯёЁa-zA-Z]+)00\s+', r'\1 ', out)  # Только после букв!

        # 3. Убираем отдельно стоящие "00" (но не внутри чисел и не во времени)
        # Используем negative lookbehind и lookahead чтобы не трогать числа
        # Добавлено исключение для времени в формате HH:00
        out = re.sub(r'(?<!\d)(?<!:)00(?!\d)', '', out)  # "00" не окружённые цифрами и не после двоеточия

        # Убираем множественные пробелы/табы, но НЕ абзацные разрывы (\n\n):
        # раньше \s{2,} склеивал абзацы в один блок
        out = re.sub(r'[^\S\n]{2,}', ' ', out)
        # Нормализуем 3+ перевода строки до стандартного абзаца
        out = re.sub(r"\n{3,}", "\n\n", out)
        # Важно: strip() только по краям, абзацную структуру сохраняем
        return "\n".join(line.rstrip() for line in out.splitlines()).strip()
    
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
                    "shao3d.github.io/trial/", "записаться", "менеджер свяжется",
                    # LANG-07: uk-зеркало (история хранится переведённой)
                    "діють знижки", "знижк", "розстрочк", "10% при повній оплаті",
                    "перше заняття", "безкоштовн", "пробне заняття",
                    "записатися", "менеджер зв'яжеться", "менеджер зв’яжеться",
                    "10% off", "% off", "discount", "installment", "first class",
                    "free trial", "sign up", "we'll contact", "we will contact",
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
            price_keywords = ["дорого", "цена", "стоимость", "сколько стоит", "грн", "гривен",
                              # LANG-06: uk
                              "дорого", "ціна", "вартість", "скільки коштує", "гривень",
                              "price", "cost", "expensive", "how much", "uah"]
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

        # Грубые обвинения («лабуда», «деньги выкачиваете»): любой CTA здесь
        # звучит невпопад — сначала снять возражение, предложения потом.
        if is_aggressive_message(last_user_msg):
            print("🚫 Агрессивный контекст: CTA пропускаем")
            return False

        # Для price_sensitive - контекстная проверка
        if user_signal == "price_sensitive":
            # Проверяем только прямые вопросы о скидках/рассрочке
            skip_phrases = ["скидки", "скидка", "рассрочк", "есть ли скидк", "какие скидк",
                            # LANG-07: uk-зеркало прямых вопросов про скидки
                            "знижк", "розстрочк", "є знижк", "які знижк",
                            "discount", "discounts", "installment", "payment plan"]
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
            trial_phrases = ["пробное", "пробный", "первое занятие", "попробовать", "бесплатн",
                             # LANG-07: uk-зеркало (пробное занятие)
                             "пробн", "перше заняття", "спробувати", "безкоштовн",
                             "trial", "free class", "try it", "first class", "check it out"]
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
                    "попробует", "оцените подходит",
                    # LANG-07: uk-зеркало CTA для тревожных родителей
                    "перше заняття", "безкоштовн", "пробне заняття",
                    "без зобов'язань", "без зобов’язань",
                    "оцінити", "спробує", "оцініть",
                    "first class", "free trial", "no obligation",
                    "try it", "see if it fits", "check us out"
                ]
                if any(phrase in msg_content.lower() for phrase in anxiety_cta_phrases):
                    print("🔄 Rate limiting: CTA для anxiety был недавно, пропускаем")
                    return False
        
        # Для ready_to_buy - rate limiting и контекстная проверка
        if user_signal == "ready_to_buy":
            # Контекстная проверка - если пользователь уже говорит о записи
            recording_phrases = ["записалась", "записался", "отправил", "заполнил", "зарегистрировал",
                                 # LANG-07: uk-зеркало (пользователь уже записался)
                                 "записавс", "записалас", "відправив", "відправила",
                                 "заповнив", "заповнила", "зареєстрував", "зареєструвала",
                                 "signed up", "already registered", "filled the form", "already paid"]
            if any(phrase in last_user_msg for phrase in recording_phrases):
                print("🔄 Контекст: Пользователь уже записался, пропускаем CTA")
                return False
            
            # Rate limiting - не чаще чем каждое второе сообщение
            recent_count = 0
            ready_cta_phrases = ["записаться", "shao3d.github.io", "консультация", "менеджер свяжется",
                                 # LANG-07: uk-зеркало CTA записи
                                 "записатися", "записатись", "консультація", "менеджер зв'яжеться",
                                 "менеджер зв’яжеться", "менеджер зв",
                                 "sign up", "shao3d.github.io", "consultation", "we'll contact", "we will contact"]
            
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
        """Проверяет, включила ли модель CTA в ответ
        
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

        SEC-03 fix:
        - URL матчится целиком (со всеми `/` пути), висячая пунктуация
          в ссылку не входит;
        - href и текст экранируются через html.escape;
        - кликабельными становятся только хосты из allowlist, чужое
          остаётся plain text (URL формирует LLM — доверять ему домен нельзя).

        Args:
            text: Текст для обработки

        Returns:
            Текст с кликабельными ссылками
        """
        url_pattern = re.compile(
            r'https?://[^\s<>"\']+'
            r'|(?<![\w@/\-.])'
            r'(?:ukido\.com\.ua|shao3d\.github\.io|[A-Za-z0-9-]+\.beyondhorizon\.dev)'
            r'(?:/[^\s<>"\']*)?'
        )
        return url_pattern.sub(self._linkify_match, text)

    def _is_allowed_url_host(self, host: str) -> bool:
        """SEC-03: host-allowlist для кликабельных ссылок."""
        host = (host or "").lower().rstrip(".")
        if host in ("ukido.com.ua", "shao3d.github.io"):
            return True
        if host == "beyondhorizon.dev" or host.endswith(".beyondhorizon.dev"):
            return True
        # Поддомены своего домена тоже свои (www.ukido.com.ua и т.п.)
        if host.endswith(".ukido.com.ua"):
            return True
        return False

    def _linkify_match(self, match) -> str:
        """SEC-03: один URL → безопасный <a> либо экранированный plain text."""
        raw = match.group(0)
        url = raw if raw.startswith(("http://", "https://")) else "https://" + raw
        # Отрезаем висячую пунктуацию конца предложения
        trail = ""
        while url and url[-1] in _TRAILING_PUNCT:
            trail = url[-1] + trail
            url = url[:-1]
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            return html.escape(raw)
        if not self._is_allowed_url_host(host):
            return html.escape(raw)
        safe = html.escape(url, quote=True)
        return (
            f'<a href="{safe}" target="_blank" rel="noopener">{safe}</a>'
            + html.escape(trail)
        )

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
