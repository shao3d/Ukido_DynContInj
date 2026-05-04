"""
router.py - Псевдо-двухэтапный LLM роутер для выбора документов
Версия 2.0: Декомпозиция + Классификация в одном промпте
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from openrouter_client import OpenRouterClient
from gemini_cached_client import GeminiCachedClient
from config import Config
from social_intents import has_business_signals_extended
from social_state import SocialStateManager  # Нужен для отслеживания повторных приветствий
# Удалены неиспользуемые импорты после рефакторинга:
# detect_social_intent, SocialIntent - больше не нужны (Gemini обрабатывает)
# SocialResponder - больше не нужен (обработка в main.py)
from standard_responses import get_offtopic_response, DEFAULT_FALLBACK, NEED_SIMPLIFICATION_MESSAGE


class Router:
    """Роутер для классификации запросов и выбора документов"""
    
    def __init__(self, use_cache: bool = True, social_state: Optional[SocialStateManager] = None):
        """Инициализация роутера с загрузкой саммари

        Args:
            use_cache: Использовать ли кешированный клиент для Gemini
            social_state: Опциональный экземпляр SocialStateManager для синхронизации состояний
        """
        config = Config()
        
        # Используем кешированный клиент для Gemini если включено
        if use_cache:
            self.client = GeminiCachedClient(
                config.OPENROUTER_API_KEY,
                seed=config.SEED,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                model=config.MODEL
            )
        else:
            self.client = OpenRouterClient(
                config.OPENROUTER_API_KEY,
                seed=config.SEED,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                model=config.MODEL
            )
        
        self.summaries = self._load_summaries()
        self.use_cache = use_cache
        # Социальные компоненты теперь обрабатываются в main.py
        # после получения ответа от Gemini
        self._social_state = social_state or SocialStateManager()  # Используем переданный экземпляр или создаём новый

        # Проверяем что саммари загрузились
        if not self.summaries:
            print("⚠️ Внимание: summaries.json не загружен!")
    
    def _is_recent_session(self, history: List[Dict[str, str]]) -> bool:
        """Проверяет, была ли недавняя активность в диалоге (в пределах часа)
        
        Args:
            history: История диалога
            
        Returns:
            True если последнее сообщение было недавно (сессия активна)
        """
        # Если истории нет или она пустая - считаем новой сессией
        if not history:
            return False
            
        # Упрощенная проверка: если в истории есть сообщения, считаем сессию активной
        # В реальном проекте здесь можно добавить проверку временных меток
        return len(history) > 0
    
    def _load_summaries(self) -> dict:
        """Загружает summaries.json из data/"""
        try:
            # Путь: src/ -> корень проекта -> data/summaries.json
            path = Path(__file__).parent.parent / "data" / "summaries.json"
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"✅ Загружено {len(data)} саммари документов")
                return data
        except FileNotFoundError:
            print(f"❌ Файл summaries.json не найден")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return {}
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return {}
    
    
    async def route(self, user_message: str, history: Optional[List[Dict[str, str]]] = None, user_id: str = "anonymous") -> dict:
        """
        Анализирует запрос и возвращает решение о маршрутизации
        
        Args:
            user_message: Текущее сообщение пользователя
            history: История диалога формата [{"role": "user/assistant", "content": "..."}]
            user_id: Идентификатор пользователя для отслеживания социального состояния
            
        Returns:
            Для success: {"status": "success", "documents": ["doc1.md", "doc2.md"], "decomposed_questions": [...]}
            Для других: {"status": "...", "message": "...", "decomposed_questions": [...]}
        """
        # Сохраняем оригинальное сообщение для передачи в response_generator
        original_message = user_message
        
        # Защита от None
        if history is None:
            history = []
        
        # MVP: Дедупликация точных дубликатов вопросов
        user_message = self._deduplicate_questions(user_message)

        # СПЕЦИАЛЬНАЯ ОБРАБОТКА УЛЬТРА-КРАТКИХ КОНТЕКСТУАЛЬНЫХ ВОПРОСОВ
        ultra_short_patterns = ["а?", "и?", "и всё?", "а дальше?", "и что?", "ну и?"]
        if user_message.strip().lower() in ultra_short_patterns and history:
            # Ищем последний ответ ассистента
            last_assistant_msg = None
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg.get("content", "")
                    break
            
            if last_assistant_msg:
                print(f"🔍 Обнаружен ультра-краткий вопрос '{user_message}' - восстанавливаем контекст из истории")
                # Определяем тему из последнего ответа
                if "цен" in last_assistant_msg.lower() or "стои" in last_assistant_msg.lower():
                    expanded_question = "Расскажите подробнее о ценах и скидках"
                elif "курс" in last_assistant_msg.lower():
                    expanded_question = "Расскажите подробнее о курсах"
                else:
                    expanded_question = "Расскажите подробнее"
                
                # Подменяем вопрос на расширенный
                user_message = expanded_question
                print(f"📝 Расширенный вопрос: {expanded_question}")

        # Проверяем был ли fuzzy matching для статистики
        _, was_fuzzy_matched = has_business_signals_extended(user_message)
        
        # Логируем что все запросы теперь идут в Gemini для умной классификации
        print(f"ℹ️ Routing to Gemini: {user_message[:50]}..." if len(user_message) > 50 else f"ℹ️ Routing to Gemini: {user_message}")
        
        # ВАЖНО: Больше НЕ блокируем mixed интенты!
        # Gemini сам определит social_context, user_signal и status
        # Это решает проблему с фразами типа "Спасибо, запишите нас"
        
        try:
            # Получаем ответ от Gemini с ПРАВИЛЬНЫМ кешированием
            if self.use_cache and isinstance(self.client, GeminiCachedClient):
                # Используем разделение на статичную и динамическую части
                static_prompt = self._build_static_prompt()  # Кешируется
                dynamic_prompt = self._build_dynamic_prompt(user_message, history)  # Не кешируется
                
                response = await self.client.chat_with_prefix_cache(
                    static_prefix=static_prompt,
                    dynamic_suffix=dynamic_prompt,
                    model_params={"temperature": 0.3, "max_tokens": 500}
                )
            else:
                # Обычный метод (для обратной совместимости)
                prompts = self._build_router_prompts(user_message, history)
                messages = [
                    {"role": "system", "content": prompts["system"]},
                    {"role": "user", "content": prompts["user"]},
                ]
                response = await self.client.chat(messages)
            
            # Проверяем что ответ не пустой
            if not response or response.strip() == "":
                print("⚠️ Пустой ответ от Gemini")
                return self._fallback_response()
            
            # Парсим JSON из ответа
            try:
                # Очищаем от markdown code blocks (```json...```)
                cleaned_response = response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                
                # Валидация структуры ответа
                if not isinstance(result, dict):
                    raise ValueError("Response is not a dict")
                    
                if "status" not in result:
                    raise ValueError("Missing 'status' field")
                
                # Гарантируем наличие decomposed_questions (всегда список)
                if "decomposed_questions" not in result or not isinstance(result.get("decomposed_questions"), list):
                    result["decomposed_questions"] = []
                
                # Проверяем корректность статуса
                valid_statuses = ["success", "offtopic", "need_simplification"]
                valid_signals = ["price_sensitive", "anxiety_about_child", "ready_to_buy", "exploring_only"]
                valid_languages = ["ru", "uk", "en"]
                
                # Проверяем и добавляем detected_language если отсутствует
                if "detected_language" not in result or result.get("detected_language") not in valid_languages:
                    result["detected_language"] = "ru"  # По умолчанию русский
                    print(f"⚠️ Добавлен detected_language по умолчанию: ru")
                
                # Обработка случая, когда Gemini путает status и user_signal
                if result["status"] in valid_signals and result["status"] not in valid_statuses:
                    # Gemini вернул user_signal вместо status - исправляем
                    actual_signal = result["status"]
                    result["status"] = "success"  # По умолчанию success для обычных запросов
                    if "user_signal" not in result:
                        result["user_signal"] = actual_signal
                    print(f"⚠️ Исправлена путаница status/signal: {actual_signal} → success")
                
                if result["status"] not in valid_statuses:
                    raise ValueError(f"Invalid status: {result['status']}")
                
                # Дополнительная валидация: проверяем соответствие количества вопросов статусу
                if "decomposed_questions" in result:
                    questions_count = len(result["decomposed_questions"])
                    # MVP: допускаем до 3 вопросов в статусе success, 4+ → need_simplification
                    if result["status"] == "success" and questions_count > 3:
                        print(f"⚠️ Предупреждение: статус 'success' с {questions_count} вопросами! Исправляем на 'need_simplification'")
                        result["status"] = "need_simplification"
                        result["message"] = NEED_SIMPLIFICATION_MESSAGE
                        if "documents" in result:
                            del result["documents"]

                    # Коррекция: если модель вернула need_simplification при 1–3 вопросах, выполняем один повторный запрос с жёсткой подсказкой
                    if result.get("status") == "need_simplification" and 1 <= questions_count <= 3:
                        print("🔁 Повторный запрос: need_simplification при ≤3 вопросах. Требуем success.")
                        strict_hint = (
                            "\n=== КОРРЕКЦИЯ (СТРОГО) ===\n"
                            "Если в decomposed_questions РОВНО 1, 2 или 3 вопроса — ОБЯЗАТЕЛЬНО верни status: \"success\".\n"
                            "Подбери документы по правилам: максимум 4 на весь ответ; по одному основному (primary) на каждый вопрос и, при необходимости, один общий support-документ, если он покрывает 2+ вопросов.\n"
                            "Верни ТОЛЬКО валидный JSON по формату ниже, без markdown и текста.\n"
                        )
                        prompts2 = self._build_router_prompts(user_message, history, extra_hint=strict_hint)
                        
                        # Повторный запрос с кешированием
                        if self.use_cache and isinstance(self.client, GeminiCachedClient):
                            response2 = await self.client.chat_with_cache(
                                system_content=prompts2["system"],
                                user_message=prompts2["user"],
                                history=None
                            )
                        else:
                            messages2 = [
                                {"role": "system", "content": prompts2["system"]},
                                {"role": "user", "content": prompts2["user"]},
                            ]
                            response2 = await self.client.chat(messages2)
                        if response2 and response2.strip():
                            cleaned2 = response2.strip()
                            if cleaned2.startswith("```json"):
                                cleaned2 = cleaned2[7:]
                            if cleaned2.endswith("```"):
                                cleaned2 = cleaned2[:-3]
                            cleaned2 = cleaned2.strip()
                            try:
                                result2 = json.loads(cleaned2)
                                if isinstance(result2, dict) and result2.get("status") in ["success", "offtopic", "need_simplification"]:
                                    # Гарантируем наличие decomposed_questions в ответе повтора
                                    if "decomposed_questions" not in result2 or not isinstance(result2.get("decomposed_questions"), list):
                                        result2["decomposed_questions"] = []
                                    result = result2
                                    print("✅ Повторный запрос принят.")
                            except Exception:
                                print("⚠️ Повторный ответ не удалось распарсить, оставляем исходный.")
                
                # ФИНАЛЬНАЯ ПРОВЕРКА: если всё ещё need_simplification при ≤3 вопросах
                # Принудительно меняем на success (Gemini иногда упрямится)
                if result.get("status") == "need_simplification":
                    questions_count = len(result.get("decomposed_questions", []))
                    if 1 <= questions_count <= 3:
                        print(f"⚠️ OVERRIDE: need_simplification при {questions_count} вопросах → success")
                        result["status"] = "success"
                        # Пытаемся подобрать документы на основе ключевых слов
                        if questions_count > 0:
                            # Простая эвристика для подбора документов
                            question_text = " ".join(result["decomposed_questions"]).lower()
                            result["documents"] = []
                            if "скидк" in question_text or "цен" in question_text or "стои" in question_text:
                                result["documents"].append("pricing.md")
                            if "блогер" in question_text or "реклам" in question_text or "сотруднич" in question_text:
                                result["documents"].append("partners.md")
                            if not result["documents"]:
                                result["documents"] = ["faq.md"]  # Fallback документ
                
                # Для success должны быть documents, для остальных - message
                if result["status"] == "success":
                    if "documents" not in result or not isinstance(result["documents"], list):
                        raise ValueError("Success status requires 'documents' list")
                    # Дедупликация и ограничение до 4 документов (MVP)
                    docs_in = result.get("documents", [])
                    seen = set()
                    docs_dedup = []
                    for d in docs_in:
                        if isinstance(d, str) and d not in seen:
                            seen.add(d)
                            docs_dedup.append(d)
                    if len(docs_dedup) > 4:
                        print(f"ℹ️ Обрезаем список документов до 4 (было {len(docs_dedup)})")
                        docs_dedup = docs_dedup[:4]
                    
                    # 🔴 ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ: Если документов нет или пустой список → offtopic
                    if not docs_dedup:
                        print("⚠️ ЗАЩИТА: Нет документов для ответа → переключаем на offtopic")
                        result["status"] = "offtopic"
                        result["message"] = get_offtopic_response()
                        del result["documents"]
                    else:
                        result["documents"] = docs_dedup
                        # Выводим статус и документы для success
                        print(f"✅ Статус: {result['status']}")
                        print(f"📋 Выбранные документы: {', '.join(result['documents'])}")
                        if "decomposed_questions" in result:
                            print(f"🔍 Декомпозированные вопросы: {result['decomposed_questions']}")
                else:
                    # Для offtopic используем заготовленную фразу вместо генерации
                    if result["status"] == "offtopic":
                        result["message"] = get_offtopic_response()
                        print(f"ℹ️ Статус: offtopic (используем заготовленную фразу)")
                    elif "message" not in result or not isinstance(result["message"], str):
                        raise ValueError(f"{result['status']} status requires 'message' string")
                    else:
                        # Выводим статус для остальных типов ответов
                        print(f"ℹ️ Статус: {result['status']}")
                    if "decomposed_questions" in result:
                        print(f"🔍 Декомпозированные вопросы: {result['decomposed_questions']}")
                
                # Добавляем флаг fuzzy_matched в результат
                result["fuzzy_matched"] = was_fuzzy_matched
                
                # Добавляем оригинальное сообщение пользователя для умной обработки в response_generator
                result["original_message"] = original_message
                
                # MVP: Проверяем повторные приветствия для mixed запросов
                if result.get("status") == "success" and result.get("social_context") == "greeting":
                    # Проверяем, было ли уже приветствие в этой сессии
                    if self._social_state.has_greeted(user_id):
                        print(f"🔍 DEBUG: Mixed запрос с повторным приветствием от {user_id[:8]}...")
                        result["social_context"] = "repeated_greeting"
                    else:
                        # Первое приветствие в mixed запросе - отмечаем
                        self._social_state.mark_greeted(user_id)
                        print(f"ℹ️ Router: Первое приветствие в mixed запросе от {user_id[:8]}...")
                
                # Проверка на acknowledgment (соглашательские ответы и смайлики)
                if result.get("status") == "offtopic" and not result.get("social_context"):
                    # Паттерны для acknowledgment
                    acknowledgment_patterns = [
                        "ок", "окей", "okay", "ok", "хорошо", "ладно", "понял", "поняла",
                        "понятно", "ясно", "спасибо", "спс", "благодарю", "принято",
                        "согласен", "согласна", "да", "угу", "ага", "👍", "👌", "✅",
                        ":)", ";)", ":-))", ")", "))", "😊", "🙂", "👍🏻", "💯"
                    ]
                    
                    # Проверяем, является ли сообщение acknowledgment
                    clean_msg = user_message.strip().lower().replace("!", "").replace(".", "")
                    if clean_msg in acknowledgment_patterns or (len(clean_msg) < 10 and not "?" in clean_msg):
                        result["social_context"] = "acknowledgment"
                        print(f"ℹ️ Router: Определен acknowledgment для сообщения '{user_message}'")
                
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️ Невалидный ответ от Gemini: {e}")
                return self._fallback_response()
                
        except Exception as e:
            print(f"❌ Ошибка при вызове Gemini: {e}")
            return self._fallback_response()
    
    def _deduplicate_questions(self, text: str) -> str:
        """
        Удаляет точные дубликаты вопросов из текста
        MVP подход: нормализация и удаление идентичных предложений
        """
        import re
        
        # Разбиваем на предложения по знакам препинания
        sentences = re.split(r'[.!?]+', text)
        
        # Нормализуем и дедуплицируем
        seen = {}
        unique_sentences = []
        
        for sentence in sentences:
            # Нормализация: lowercase, убираем лишние пробелы, знаки препинания по краям
            normalized = sentence.lower().strip()
            normalized = re.sub(r'\s+', ' ', normalized)  # Множественные пробелы в один
            normalized = re.sub(r'[,;:\-–—]', '', normalized)  # Убираем второстепенную пунктуацию
            
            # Пропускаем пустые
            if not normalized:
                continue
            
            # Если не видели такое предложение - добавляем оригинал
            if normalized not in seen:
                seen[normalized] = sentence.strip()
                unique_sentences.append(sentence.strip())
        
        # Собираем обратно с правильными знаками
        result = []
        for i, sent in enumerate(unique_sentences):
            if sent:
                # Добавляем знак вопроса, если его нет и предложение вопросительное
                if not re.search(r'[.!?]$', sent):
                    # Паттерны для acknowledgment и смайликов - им НЕ нужен вопросительный знак
                    acknowledgment_patterns = [
                        "ок", "окей", "okay", "ok", "хорошо", "ладно", "понял", "поняла",
                        "понятно", "ясно", "спасибо", "спс", "благодарю", "принято",
                        "согласен", "согласна", "да", "угу", "ага", "👍", "👌", "✅",
                        ":)", ";)", ":-))", ")", "))", "😊", "🙂", "👍🏻", "💯"
                    ]
                    
                    # Проверяем, является ли сообщение acknowledgment или смайликом
                    clean_sent = sent.strip().lower()
                    is_acknowledgment = clean_sent in acknowledgment_patterns
                    # Проверяем на эмодзи (Unicode категории для эмодзи)
                    is_emoji = len(sent.strip()) <= 3 and any(ord(c) > 127 for c in sent.strip())
                    
                    if is_acknowledgment or is_emoji:
                        # Для acknowledgment и эмодзи НЕ добавляем знаки препинания
                        pass
                    else:
                        # Эвристика: если есть вопросительные слова или короткое предложение
                        question_words = ['как', 'что', 'где', 'когда', 'почему', 'зачем', 'сколько', 
                                        'какой', 'какая', 'какие', 'кто', 'куда', 'откуда']
                        if any(sent.lower().startswith(word) for word in question_words) or len(sent.split()) <= 5:
                            sent += '?'
                        else:
                            sent += '.'
                result.append(sent)
        
        deduplicated = ' '.join(result)
        
        # Логируем если были дубликаты
        if len(unique_sentences) < len(sentences) - 1:  # -1 учитывая пустые
            print(f"🔄 Дедупликация: {len(sentences)} предложений → {len(unique_sentences)} уникальных")
            print(f"   Оригинал: {text[:100]}...")
            print(f"   После: {deduplicated[:100]}...")
        
        return deduplicated
    
    def _build_static_prompt(self) -> str:
        """Статичная часть промпта для кеширования (без истории и текущего сообщения)"""
        static_content = ""
        # Роль и правила
        static_content += self._get_role_section()
        # База знаний (summaries)
        static_content += self._get_summaries_section()
        # Инструкции по декомпозиции и классификации
        static_content += self._get_decomposition_section()
        static_content += self._get_classification_section()
        # Формат ответа
        static_content += self._get_response_format_section()
        return static_content
    
    def _build_dynamic_prompt(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Динамическая часть промпта (история и текущий запрос)"""
        dynamic_content = ""
        # История диалога
        dynamic_content += self._get_history_section(history)
        # Текущий запрос
        dynamic_content += f"\n=== ТЕКУЩИЙ ЗАПРОС ===\nUser: {user_message}\n\n"
        dynamic_content += "Теперь проанализируйте этот запрос согласно инструкциям выше и верните JSON-ответ.\n"
        return dynamic_content
    
    def _build_router_prompts(self, user_message: str, history: List[Dict[str, str]], extra_hint: Optional[str] = None) -> Dict[str, str]:
        """
        Возвращает два блока промпта: system и user.
        system — роль и строгие правила/формат.
        user — база знаний, история, текущий запрос, инструкции по шагам (+extra_hint).
        """
        # System: роль + формат ответа как строгие правила
        system_content = self._get_role_section()
        system_content += self._get_response_format_section()

        # User: база знаний + история + текущий запрос + этапы
        user_content = ""
        user_content += self._get_summaries_section()
        user_content += self._get_history_section(history)
        user_content += f"\n=== ТЕКУЩИЙ ЗАПРОС ===\nUser: {user_message}\n\n"
        user_content += self._get_decomposition_section()
        user_content += self._get_classification_section()
        if extra_hint:
            user_content += extra_hint + "\n\n"
        return {"system": system_content, "user": user_content}
    
    def _get_role_section(self) -> str:
        """Секция с ролью и основными правилами"""
        return """Ты - представитель детской школы soft skills Ukido.

ТРИ ЭТАПА АНАЛИЗА:
1. ОПРЕДЕЛЕНИЕ ЯЗЫКА - определить язык сообщения пользователя
2. ДЕКОМПОЗИЦИЯ - извлечь все вопросы
3. КЛАССИФИКАЦИЯ - статус и документы

ПРАВИЛА:
- Максимум 3 вопроса для success
- 4+ вопроса → need_simplification
- Максимум 4 документа
- ВАЖНО: Будь толерантен к вопросам о школе
- Критика = вопрос → success (см. правило КРИТИКА в декомпозиции)

ОПРЕДЕЛЕНИЕ ЯЗЫКА (КРИТИЧЕСКИ ВАЖНО!):
Определи основной язык сообщения пользователя и ОБЯЗАТЕЛЬНО верни в поле "detected_language":
- 'uk' если есть хотя бы ОДНА из букв: і, ї, є, ґ (это украинский!)
- 'en' если текст полностью на латинице без кириллицы
- 'ru' только если это чистая кириллица БЕЗ украинских букв
Примеры:
- "Привіт" → detected_language: "uk" (есть буква і)
- "Hello" → detected_language: "en" (латиница)
- "Привет" → detected_language: "ru" (чистая кириллица без укр. букв)

"""
    
    def _get_summaries_section(self) -> str:
        """Секция с саммари документов"""
        return f"""=== БАЗА ЗНАНИЙ (ДОСТУПНЫЕ ДОКУМЕНТЫ) ===
{json.dumps(self.summaries, ensure_ascii=False, indent=2)}

"""
    
    def _get_history_section(self, history: List[Dict[str, str]]) -> str:
        """Секция с историей диалога"""
        if not history:
            return ""
            
        section = "=== ИСТОРИЯ ДИАЛОГА ===\n"
        section += "(последние 10 сообщений для понимания контекста)\n\n"

        # Берём только последние 10 сообщений
        recent_history = history[-10:] if len(history) > 10 else history
        
        # Ищем предыдущий user_signal в истории
        previous_signal = None
        for msg in recent_history:
            content = msg.get("content", "").lower()
            # Ищем маркеры price_sensitive в предыдущих сообщениях
            if msg.get("role") == "user":
                # Проверяем "развод" только в контексте денег/цены
                if "развод" in content:
                    # Если "развод" упоминается с денежным контекстом - это price_sensitive
                    if any(money_word in content for money_word in ["деньги", "цена", "стоит", "оплата", "платить", "грн", "гривен", "тысяч"]):
                        previous_signal = "price_sensitive"
                        break
                    # Иначе игнорируем (это про доверие, а не про цену)
                elif any(marker in content for marker in ["дорого", "30 тысяч", "лабуда", "золотые уроки", "с ума сошли"]):
                    previous_signal = "price_sensitive"
                    break

        for msg in recent_history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            section += f"{role}: {content}\n"

        section += """
ИСПОЛЬЗУЙ ИСТОРИЮ ДЛЯ:
- Понимания контекста неполных вопросов ("А это платно?" → о чём "это"?)
- Добавления контекста к оторванным вопросам
- Понимания что уже обсуждалось
- Ультра-краткие реплики ("А?", "И?", "И всё?", "А дальше?") - ВСЕГДА восстанови из контекста!
"""
        
        # Добавляем указание о сохранении сигнала если он был price_sensitive с негативом
        if previous_signal == "price_sensitive":
            section += """
ВАЖНО: В истории был price_sensitive сигнал.
СОХРАНЯЙ price_sensitive ТОЛЬКО если продолжается негатив к цене.
Если текущее сообщение - просто вопрос без негатива, используй exploring_only.
"""
        
        return section
    
    def _get_decomposition_section(self) -> str:
        """Секция для этапа декомпозиции с примерами"""
        return """
=== ЭТАП 1: ДЕКОМПОЗИЦИЯ ===

Извлеки ВСЕ вопросы из запроса:
1. Явные (с "?")
2. Скрытые ("интересует", "хочу узнать", "расскажите")
3. Контекстные ("А?", "И?", "Дальше?" - восстанови из истории)

КРИТИКА = ВОПРОС! Любая критика содержит скрытый вопрос → status: success
- "Не нужны навыки общения" → ["Зачем детям навыки общения?"] + roi_and_future.md
- "Это НЕ работает" → ["Какие доказательства эффективности?"] + student_results.md
- "Лучше бы математику" → ["Чем soft skills важнее математики?"] + methodology.md
- "Не верю в soft skills" → ["Почему soft skills важны?"] + methodology.md, student_results.md
- "Онлайн - это НЕ обучение" → ["Какие преимущества онлайн?"] + online_format_benefits.md
- "Это не секта?" → ["Легитимность школы?"] + ukido_philosophy.md, safety_and_trust.md

ИГНОРИРУЙ только:
- Приветствия/прощания/благодарности БЕЗ информации
- Мат и оскорбления
- Явный оффтопик (погода, политика) БЕЗ упоминания детей/обучения

ПРИМЕРЫ ДЕКОМПОЗИЦИИ:

Запрос: "Привет! Сколько стоит курс для 10-летнего и есть ли скидки?"
→ 1. "Сколько стоит курс?" 2. "Для 10 лет подходит?" 3. "Какие скидки?"

ВАЖНО: Объединяй связанные вопросы!
Запрос: "У меня двое детей 8 и 12 лет, младший стеснительный, старший гиперактивный"
→ "Какие курсы подойдут для стеснительного 8 лет и гиперактивного 12 лет?"

С контекстом:
История: обсуждали пробный урок
Запрос: "А это платно?"
→ "Пробный урок платный?"

Оффтопик игнорируем:
"У вас есть курсы? Какая погода?" → только ["Какие курсы есть?"]

4+ вопроса = need_simplification:
"Сколько стоит, кто ведет, сколько детей, расписание?" → 4 вопроса → need_simplification

СОЦИАЛЬНЫЙ КОНТЕКСТ (отмечай, но не включай в вопросы):
- greeting (привет), thanks (спасибо), apology (извините), farewell (до свидания)
"Привет! Сколько стоит?" → social_context: "greeting", вопросы: ["Сколько стоит?"]

ВАЖНО: "Давайте" в контексте действий НЕ является приветствием:
- "Давайте попробуем" - НЕ greeting, это согласие на действие → social_context: null
- "Давайте запишемся" - НЕ greeting, это готовность к записи → social_context: null
- "Звучит убедительно. Давайте попробуем" - НЕ greeting → social_context: null
- Только "Давайте познакомимся" может быть greeting

ВАЖНО: Короткие эмоциональные восклицания НЕ являются приветствиями:
- "Интересно!" - НЕ greeting, это реакция на информацию → social_context: null
- "Отлично!" - НЕ greeting, это одобрение → social_context: null
- "Понятно!" - НЕ greeting, это подтверждение понимания → social_context: null
- "Интересно! А есть ли..." - НЕ greeting, это вопрос после реакции → social_context: null

КРИТИЧЕСКИ ВАЖНО для ready_to_buy сигналов:
Если фраза содержит маркеры готовности БЕЗ явного вопроса, ВСЕГДА добавляй implicit вопрос:
- "Спасибо, запишите нас" → ["Как оформить запись на курс?"]
- "Мы согласны" → ["На что именно вы согласны - записаться на курс или нужны детали?"]
- "Действуем" → ["Какие конкретные шаги вы хотите предпринять?"]
- "Регистрируйте меня" → ["Как зарегистрироваться на курс?"]
- "Давайте", "Идёт", "Подходит" → ["Что именно подходит - хотите записаться на курс?"]
- "Благодарю! Регистрируйте" → ["Как оформить регистрацию на курс?"]

ТРАНСПОРТ = ВОПРОС О ФОРМАТЕ:
Слова "забирать/привозить/довозить" → implicit: ["Занятия онлайн или нужно приезжать?"]
Примеры: "После работы забирать буду", "Кто будет привозить?", "Во сколько забрать?"

КРИТИЧЕСКИ ВАЖНО - ЗАВЕРШЁННЫЕ ДЕЙСТВИЯ:
Если пользователь сообщает о УЖЕ выполненном действии - НЕ объясняй, как это сделать!
Вместо этого подтверди и спроси о следующих шагах:
- "Оплатила перевод" → ["Что нужно сделать после оплаты?", "Когда будет подтверждение?"]
- "Заполнил форму" → ["Что дальше после заполнения формы?", "Когда с нами свяжутся?"]
- "Записались на пробное" → ["Как подготовиться к пробному занятию?", "Что взять с собой?"]
- "Отправил документы" → ["Когда будет обработка документов?", "Что дальше?"]
НЕ НАДО: ["Как оплатить?"] если уже написано "Оплатила"!

КРИТИЧЕСКИ ВАЖНО для mixed социальных интентов:
Если есть приветствие/благодарность + ЛЮБАЯ информация о детях/проблемах/интересах:
- status: "success" (НЕ offtopic!)
- social_context: "greeting"/"thanks" (отмечаем социальный контекст)
- ОБЯЗАТЕЛЬНО генерируй implicit вопросы из информации:
  * "Добрый день! У меня трое детей" → ["Какие курсы подойдут для троих детей?"]
  * "Привет! Мой ребенок стеснительный" → ["Как помочь стеснительному ребенку?"]
  * "Здравствуйте! Интересует курс для 10-летнего" → ["Какой курс подходит для 10-летнего?"]
  * "Спасибо! У меня двое детей 7 и 12 лет" → ["Какие курсы для детей 7 и 12 лет?"]
  * "Добрый день! Расскажите о вашей школе" → ["Расскажите о школе Ukido"]
  * "Здравствуйте! Расскажите про вашу методику" → ["Расскажите про методику обучения"]
  * "Привет! Покажите ваши курсы" → ["Какие курсы есть в школе?"]
  * "Добрый день! Объясните, как проходят занятия" → ["Как проходят занятия?"]

ВАЖНО: Императивы "расскажите", "покажите", "объясните", "опишите" после приветствия - 
это ВСЕГДА вопросы о школе, НЕ игнорировать их!

Это нужно для уточнения намерений пользователя и предоставления конкретной информации.

РЕЗУЛЬТАТ ДЕКОМПОЗИЦИИ:
Список чётких вопросов БЕЗ социальных элементов + отдельное поле social_context.
ПОМНИ: Если получилось больше 3 вопросов - это нормально на этапе декомпозиции! 
Статус need_simplification будет определён на следующем этапе.

"""
    
    def _get_classification_section(self) -> str:
        """Секция для этапа классификации"""
        return """
=== ЭТАП 2: КЛАССИФИКАЦИЯ И ВЫБОР ДОКУМЕНТОВ ===

ЗАДАЧА: На основе декомпозированных вопросов определить статус и выбрать документы.

ШАГ 1: ПОДСЧЁТ ШКОЛЬНЫХ ВОПРОСОВ
- Посчитай ТОЧНОЕ количество вопросов из декомпозиции (decomposed_questions)
- Все вопросы из декомпозиции - школьные (оффтопик уже отфильтрован)
- ВАЖНО: считай именно количество элементов в списке декомпозированных вопросов!

ШАГ 2: ОПРЕДЕЛЕНИЕ СТАТУСА
- 0 вопросов → offtopic
- 1-3 вопроса → success ✅
- 4+ вопросов → need_simplification

СПЕЦИАЛЬНЫЕ ПРАВИЛА ДЛЯ СОЦИАЛЬНЫХ ИНТЕНТОВ:

ЧИСТО социальные (БЕЗ какой-либо информации) → status: "offtopic" + social_context:
- Только приветствие ("Привет", "Добрый день") → offtopic + social_context: "greeting"
- Только благодарность ("Спасибо", "Благодарю") → offtopic + social_context: "thanks"
- Только прощание ("До свидания", "Пока") → offtopic + social_context: "farewell"

MIXED социальные (приветствие + ЛЮБАЯ информация) → status: "success" + social_context:
- "Привет! Сколько стоит?" → success + social_context: "greeting"
- "Спасибо, запишите нас" → success + ready_to_buy + social_context: "thanks"
- "Добрый день! У меня трое детей" → success + social_context: "greeting" (implicit вопросы!)
- "Здравствуйте! Ребенок стеснительный" → success + social_context: "greeting" (implicit вопросы!)

ПОМНИ: Если после приветствия есть ЛЮБАЯ информация о детях/проблемах - это success с implicit вопросами!

ПРАВИЛО: ЗАПИСЬ/РЕГИСТРАЦИЯ/СОГЛАСИЕ/ДЕЙСТВИЕ после социального = ready_to_buy!
Слова-маркеры ready_to_buy: запишите, запись, регистрируйте, регистрация, согласны, действуем, идёт, подходит, давайте, попробуем, попробовать, пробное занятие, пробный урок

КРИТИКА → SUCCESS: См. правило "КРИТИКА = ВОПРОС" в декомпозиции

ВАЖНО: При сомнениях между offtopic и success - выбирай success!

ШАГ 3: ВЫБОР ДОКУМЕНТОВ (только для status: "success")
ЦЕЛЬ: покрыть все вопросы при лимите максимум 4 документа.

🔴 КРИТИЧЕСКИ ВАЖНО - ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ:
Если для вопроса НЕТ релевантных документов в базе знаний → status: "offtopic"!
НЕ ВЫДУМЫВАЙ информацию! Если в документах нет данных о:
- Парковке, транспорте, как добраться (физический адрес)
- Футболе, спортивных секциях (мы только soft skills)
- Питании, столовой, кафе  
→ ОБЯЗАТЕЛЬНО возвращай status: "offtopic"

ВАЖНО: Вопросы про онлайн-формат обучения - это SUCCESS!
Ukido - это онлайн-школа, работающая через Zoom. Вопросы про:
- Онлайн-формат, дистанционное обучение
- Платформу, технические требования
- Возможность учиться из дома
→ Это ВСЕГДА status: "success", документы: ["conditions.md", "safety_and_trust.md"]

АЛГОРИТМ ВЫБОРА:
1) Для каждого вопроса выбери 1-2 документа:
   - 1 основной документ (primary) - максимально релевантный
   - 1 дополнительный (support) - если нужен для полного ответа
   - Если НЕТ подходящих документов → status: "offtopic"
2) После дедупликации должно быть:
   - 1 вопрос → 1-2 уникальных документа
   - 2 вопроса → 2-4 уникальных документа  
   - 3 вопроса → 3-4 уникальных документа
3) Используй из саммари:
   - trigger_words (ключевые слова)
   - typical_questions (типичные вопросы)
   - core_topics (основные темы)
   - related_docs (связанные документы)

ПРАВИЛА ВЫБОРА ДОКУМЕНТОВ:
- "Сколько стоит?" → pricing.md
- "Кто преподаватели?" → teachers_team.md  
- "Какие курсы?" → courses_detailed.md
- "Как проходят занятия?" → methodology.md
- "Есть ли пробный урок?" → faq.md
- "Какое расписание?" → conditions.md
- "Как записаться?" → faq.md
- "Что развиваете?" → ukido_philosophy.md + methodology.md

ОПЕРАЦИОННЫЕ РЕПЛИКИ (только если есть информация):
- Запись, контакты, условия → faq.md, conditions.md
- Документы школы (лицензия, сертификаты) → safety_and_trust.md

ОБЪЕДИНЕНИЕ ДОКУМЕНТОВ:
- Убери дубликаты (если для двух вопросов нужен один документ)
- Максимум 4 документа на весь ответ
- Первые по приоритету - документы для первых вопросов
- Если НЕТ релевантных документов → НЕ включай никакие документы и верни status: "offtopic"

ШАГ 4: ОПРЕДЕЛЕНИЕ СИГНАЛА ПОЛЬЗОВАТЕЛЯ
Проанализируй декомпозированные вопросы и определи ОДИН основной сигнал состояния пользователя:

СИГНАЛЫ:
- "price_sensitive" - СКЕПТИЧЕСКИЕ или НЕГАТИВНЫЕ вопросы о цене ШКОЛЫ ("дорого", "почему так много"), торг, сомнения в ценности НАШИХ КУРСОВ
- "anxiety_about_child" - ЯВНАЯ ТРЕВОГА родителя о проблемах ребенка (плач, истерики, травля, отвержение)
- "ready_to_buy" - готовность к записи: явные запросы на запись ИЛИ краткие деловые вопросы о логистике
- "exploring_only" - общие вопросы о школе, методологии, курсах БЕЗ тревоги и БЕЗ негатива к цене

ВАЖНО: Агрессивный тон с упоминанием денег ("развод на деньги", "лабуда", "бабло тянете") = price_sensitive
НО: "Это не развод?" без денежного контекста = вопрос о доверии/легитимности, НЕ price_sensitive
КРИТИЧНО: Если пользователь жалуется на цены НЕ связанные со школой (бензин, продукты, другие услуги) - это НЕ price_sensitive!
  Примеры offtopic (НЕ price_sensitive):
  - "Бензин так подорожал" - offtopic про транспорт
  - "В магазине всё дорого" - offtopic про продукты
  - "Квартплата выросла" - offtopic про жильё
  Только жалобы на НАШИ цены = price_sensitive

ПРАВИЛА ОПРЕДЕЛЕНИЯ:
1. Анализируй ВСЕ декомпозированные вопросы в совокупности
2. ВАЖНО: Учитывай стиль общения - краткий телеграфный стиль (< 5 слов) часто = ready_to_buy
3. КРИТИЧНО: Просьбы повторить ("не расслышала", "повторите", "еще раз") СОХРАНЯЮТ предыдущий сигнал
4. ИНЕРЦИЯ price_sensitive (ОГРАНИЧЕННАЯ!): 
   - Сохраняй price_sensitive ТОЛЬКО если был ЯВНЫЙ НЕГАТИВ ("дорого!", "грабеж", "30 тысяч?!")
   - НЕ сохраняй инерцию для нейтральных вопросов о скидках/рассрочке
   - ОБЯЗАТЕЛЬНО сбрасывай price_sensitive при позитивных фразах:
     * "подходит", "качество важнее", "записывайте"
     * "ладно, черт с ними с деньгами", "деньги найдем"
     * "хорошо, согласны", "давайте попробуем"
5. ПЕРЕХОДЫ СИГНАЛОВ:
   - exploring_only → ready_to_buy: при словах "записать", "trial", "book us", "пробное", "попробуем", "попробовать", "давайте попробуем", "хочу попробовать", "запишите на пробное"
   - price_sensitive → ready_to_buy: ОБЯЗАТЕЛЬНО при позитивном принятии цены
   - price_sensitive → exploring_only: когда негатив ушел, остались информационные вопросы
   - price_sensitive → price_sensitive: ТОЛЬКО если продолжается явный негатив
   - Многодетные родители: вопросы о скидках = exploring_only (НЕ price_sensitive!)
6. Выбирай наиболее приоритетный сигнал по порядку: ready_to_buy > anxiety_about_child > price_sensitive > exploring_only
7. Если не можешь однозначно определить - используй "exploring_only"

КРИТИЧЕСКИ ВАЖНО ДЛЯ OFFTOPIC:
Если сообщение offtopic (не о школе), ВСЕГДА анализируй историю диалога и СОХРАНЯЙ накопленный user_signal!
- Если в истории был anxiety_about_child → сохрани anxiety_about_child для offtopic
- Если в истории был price_sensitive → сохрани price_sensitive для offtopic  
- Если в истории был ready_to_buy → сохрани ready_to_buy для offtopic
- ТОЛЬКО если истории нет или был exploring_only → используй exploring_only для offtopic

МАРКЕРЫ price_sensitive (ТОЛЬКО ЯВНЫЙ НЕГАТИВ К ЦЕНЕ!):
- ЯВНЫЙ негатив: "дорого", "дорогова-то", "с ума сошли", "30 тысяч?!", "почему так много", "золотые уроки", "грабеж", "неадекватная цена"
- Торг и скептицизм: "а дешевле?", "за что такие деньги", "оно того стоит?"
- Подозрения С деньгами: "развод на деньги", "бабло тянете", "наживаетесь на родителях"
- Сравнение с негативом: "у других дешевле", "везде дешевле", "завышенная цена"

КРИТИЧНО - НЕ price_sensitive (это exploring_only):
- Нейтральные вопросы: "Сколько стоит?", "Какая цена?", "Цена?"
- Информационные запросы: "Какие скидки?", "Есть ли скидки?", "Скидка для троих?"
- Уточнения по оплате: "Есть рассрочка?", "Можно частями?", "Как оплатить?"
- Простые расчеты: "Если 15% на каждого - получается X?"
- Позитивный контекст: "Цена не важна", "Деньги найдем", "Качество важнее денег"

МАРКЕРЫ ready_to_buy:
- Явные: "хочу записать", "запишите нас", "как записаться", "где записаться", "book us"
- С социальными словами (КРИТИЧНО!):
  * "Спасибо, запишите нас" - благодарность + готовность
  * "Благодарю! Регистрируйте меня" - благодарность + действие
  * "Спасибо. Мы согласны." - благодарность + согласие
  * "Спасибо. Действуем." - благодарность + решение
- Слова согласия и действия: "согласны", "действуем", "идёт", "подходит", "давайте", "регистрируйте"
- Контекстуальные краткие (телеграфный стиль):
  * "Курс [название]. Когда старт?" - проверка доступности
  * "Онлайн есть?" - проверка формата (SUCCESS! мы онлайн-школа)
  * "Цена? Сроки?" - финальная проверка перед решением
  * "Оплата?", "Ссылку" - подготовка к записи
  * "Какие документы нужны?" - процедура записи (SUCCESS: faq.md или pricing.md)
  * "Trial есть?" - современный сленг готовности
- Паттерн: фокус на ПРОЦЕССЕ и ЛОГИСТИКЕ, а не на сути курсов

МАРКЕРЫ anxiety_about_child (ТОЛЬКО ЯВНАЯ ТРЕВОГА!):
- КРИТИЧЕСКИЕ проблемы: "не слушается", "дерется", "истерики", "агрессивный", "отбился от рук"
- Травля и буллинг: "травят", "буллинг", "обижают", "издеваются", "бьют", "унижают", "изгой"
- Эмоциональный кризис: "плачет каждый день", "не хочет жить", "депрессия", "панические атаки"
- Родительская паника: "ПОМОГИТЕ!", "что делать???", "не знаю как помочь", "совсем отчаялась"
- Множественные восклицательные знаки + проблема: "Сын не слушается!!!", "Помогите!!!"
ВАЖНО: Простое упоминание "стеснительный", "тихий", "застенчивый" БЕЗ тревоги = exploring_only!
ВАЖНО: "У меня внучка стеснительная" - это ОПИСАНИЕ характера, НЕ тревога = exploring_only!

ПРАВИЛО IMPLICIT QUESTIONS: ready_to_buy БЕЗ вопросов → добавь уточняющий вопрос!

МАРКЕРЫ exploring_only (украинские родители-исследователи):
- Общие вопросы: "расскажите подробнее", "что это за школа", "чем именно занимаетесь"
- Методология: "какие навыки", "какая программа", "что дает ребенку", "какая методика"
- Сравнение: "чем отличаетесь", "почему именно вы", "какой подход", "что особенного"
- Пассивный интерес: "просто интересуюсь", "на будущее", "может быть потом", "хочу узнать"
- Информационный запрос: "пришлите информацию", "где почитать", "есть ли материалы"
- Временные маркеры: "пока думаем", "еще не решили", "рассматриваем варианты"
ВАЖНО: Отличие от price_sensitive - нет фокуса на цене, скидках или недоверия
ВАЖНО: Отличие от ready_to_buy - нет вопросов о логистике, записи или конкретных датах
- БЕЗ упоминания цены, проблем ребенка или готовности записаться

СТИЛЬ КАК ИНДИКАТОР:
- Телеграфный стиль (1-3 слова) + логистика = ready_to_buy с вероятностью 80%
- Развернутые вопросы с объяснениями = exploring_only или anxiety_about_child
- Простые вопросы о цене БЕЗ негатива = exploring_only
- Вопросы о цене С негативом ("дорого", "почему так много") = price_sensitive

"""
    
    def _get_response_format_section(self) -> str:
        """Минимальный формат JSON-ответа"""
        return (
            "=== ФОРМАТ JSON ОТВЕТА (МИНИМАЛЬНЫЙ) ===\n\n"
            "1) success:\n{\n  \"status\": \"success\",\n  \"detected_language\": \"uk\",  // ОБЯЗАТЕЛЬНО: ru, uk или en\n  \"documents\": [\"doc1.md\", ...],\n  \"decomposed_questions\": [\"Вопрос 1?\", ...],\n  \"user_signal\": \"price_sensitive\",  // ОБЯЗАТЕЛЬНО: один из 4 сигналов\n  \"social_context\": \"greeting\"  // опционально, если был социальный контекст\n}\n\n"
            "2) offtopic:\n{\n  \"status\": \"offtopic\",\n  \"detected_language\": \"ru\",  // ОБЯЗАТЕЛЬНО: ru, uk или en\n  \"decomposed_questions\": [],\n  \"user_signal\": \"anxiety_about_child\",  // СОХРАНЯЙ сигнал из истории! НЕ всегда exploring_only!\n  \"social_context\": \"farewell\"  // опционально\n}\n"
            "ВАЖНО: для offtopic НЕ генерируй message - используется заготовленная фраза\n\n"
            "3) need_simplification:\n{\n  \"status\": \"need_simplification\",\n  \"detected_language\": \"en\",  // ОБЯЗАТЕЛЬНО: ru, uk или en\n  \"message\": \"Пожалуйста, задавайте не более трёх вопросов за раз. Например, начните с самого важного для вас.\",\n  \"decomposed_questions\": [\"Вопрос 1?\", ...],\n  \"user_signal\": \"exploring_only\",  // определи сигнал даже для need_simplification\n  \"social_context\": \"apology\"  // опционально\n}\n\n"
            "Только валидный JSON, без markdown и комментариев. Поле decomposed_questions всегда присутствует.\n"
            "Поле detected_language ОБЯЗАТЕЛЬНО (ru|uk|en).\n"
            "Поле user_signal ОБЯЗАТЕЛЬНО (price_sensitive|anxiety_about_child|ready_to_buy|exploring_only).\n"
            "Поле social_context добавляй ТОЛЬКО если был социальный контекст (greeting/thanks/apology/farewell).\n"
        )
    
    def _fallback_response(self) -> dict:
        """Универсальный ответ при любых ошибках"""
        return {
            "status": "offtopic",
            "message": DEFAULT_FALLBACK,
            "decomposed_questions": [],
            "user_signal": "exploring_only",
            "detected_language": "ru"
        }
