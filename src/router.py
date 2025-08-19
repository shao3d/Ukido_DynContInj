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
from social_intents import detect_social_intent, SocialIntent, has_business_signals_extended
from social_state import SocialStateManager
from social_responder import SocialResponder
from standard_responses import get_offtopic_response, DEFAULT_FALLBACK, NEED_SIMPLIFICATION_MESSAGE


class Router:
    """Роутер для классификации запросов и выбора документов"""
    
    def __init__(self, use_cache: bool = True):
        """Инициализация роутера с загрузкой саммари
        
        Args:
            use_cache: Использовать ли кешированный клиент для Gemini
        """
        config = Config()
        
        # Используем кешированный клиент для Gemini если включено
        if use_cache:
            self.client = GeminiCachedClient(
                config.OPENROUTER_API_KEY,
                seed=config.SEED,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE
            )
        else:
            self.client = OpenRouterClient(
                config.OPENROUTER_API_KEY,
                seed=config.SEED,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                model="google/gemini-2.5-flash"
            )
        
        self.summaries = self._load_summaries()
        self.use_cache = use_cache
        # Социальные компоненты
        self._social_state = SocialStateManager()
        self._social_responder = SocialResponder(self._social_state)

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
        # Защита от None
        if history is None:
            history = []

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

        # Предварительно определяем наличие бизнес-сигналов (для mixed-гейта)
        has_business, was_fuzzy_matched = has_business_signals_extended(user_message)

        # Сначала проверяем социальные интенты (быстрый путь) — только если НЕТ бизнес-сигналов
        det = detect_social_intent(user_message)
        if det.intent != SocialIntent.UNKNOWN and det.confidence >= 0.7 and not has_business:
            # Логирование социального интента
            print(f"ℹ️ Router: Обнаружен социальный интент '{det.intent.value}' для user {user_id[:8]}...")
            
            # Проверка повторного приветствия
            if det.intent == SocialIntent.GREETING:
                if self._social_state.has_greeted(user_id):
                    # Проверяем, не прошло ли много времени с последнего сообщения
                    if self._is_recent_session(history):
                        print(f"🔍 DEBUG: Повторное приветствие от {user_id[:8]}...")
                        # Передаем Claude для умного ответа на повторное приветствие
                        return {
                            "status": "success",
                            "social_context": "repeated_greeting",
                            "documents": [],
                            "decomposed_questions": ["повторное приветствие"]
                        }
                    else:
                        # Новая сессия после долгой паузы
                        print(f"ℹ️ Router: Новая сессия для {user_id[:8]}... (долгая пауза)")
                        self._social_state.mark_greeted(user_id)
                else:
                    # Первое приветствие в сессии
                    self._social_state.mark_greeted(user_id)
                    print(f"ℹ️ Router: Первое приветствие от {user_id[:8]}...")
            
            # Генерируем социальный ответ
            reply = self._social_responder.respond(user_id, det.intent)
            
            # Возвращаем как offtopic с сообщением и социальным контекстом
            return {
                "status": "offtopic", 
                "message": reply, 
                "social_context": det.intent.value,
                "decomposed_questions": [], 
                "fuzzy_matched": was_fuzzy_matched
            }


        # Строим промпт согласно новой архитектуре (разделяем роли)
        prompts = self._build_router_prompts(user_message, history)
        
        try:
            # Получаем ответ от Gemini с кешированием если включено
            if self.use_cache and isinstance(self.client, GeminiCachedClient):
                # Используем кешированный метод для Gemini
                response = await self.client.chat_with_cache(
                    system_content=prompts["system"],
                    user_message=prompts["user"],
                    history=None  # История уже включена в user_message
                )
            else:
                # Обычный метод
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
                
                
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️ Невалидный ответ от Gemini: {e}")
                return self._fallback_response()
                
        except Exception as e:
            print(f"❌ Ошибка при вызове Gemini: {e}")
            return self._fallback_response()
    
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

ДВА ЭТАПА АНАЛИЗА:
1. ДЕКОМПОЗИЦИЯ - извлечь все вопросы
2. КЛАССИФИКАЦИЯ - статус и документы

ПРАВИЛА:
- Максимум 3 вопроса для success
- 4+ вопроса = need_simplification
- Максимум 4 документа
- ВАЖНО: Будь толерантен к вопросам о школе
- Скептические вопросы (например, "это не секта?") классифицируй как success и выбирай ukido_philosophy.md или safety_and_trust.md

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

        for msg in recent_history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            section += f"{role}: {content}\n"

        section += """
ИСПОЛЬЗУЙ ИСТОРИЮ ДЛЯ:
- Понимания контекста неполных вопросов ("А это платно?" → о чём "это"?)
- Добавления контекста к оторванным вопросам
- Понимания что уже обсуждалось
- КРИТИЧНО: Для ультра-кратких реплик ("А?", "И всё?", "А дальше?") - 
  это ВСЕГДА контекстуальные вопросы о предыдущей теме!
  НЕ offtopic! Восстанови смысл из истории!
  
ОСОБОЕ ПРАВИЛО ДЛЯ "А?":
Если пользователь написал только "А?" - это ВСЕГДА просьба уточнить/продолжить последний ответ.
Посмотри последний ответ Assistant и определи, о чём спрашивают.
Пример: если говорили о ценах → "А?" = "Расскажите подробнее о ценах"
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

ВАЖНО для кратких реплик:
- "А?" / "И?" = продолжение темы из истории
- "Это как?" = просьба объяснить подробнее
- ВСЕГДА проверяй контекст!

ИГНОРИРУЙ только:
- Приветствия/прощания/благодарности
- Мат и оскорбления
- Явный оффтопик (погода, политика)

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

Ультра-краткие вопросы (ВСЕГДА используй контекст истории):
- "А?" → продолжи/уточни предыдущий ответ
- "И?" → что еще по этой теме
- "И всё?" → дай больше информации
- "А дальше?" → что после этого
- "И что это даёт?" → какая польза/результат от обсуждаемого

Оффтопик игнорируем:
"У вас есть курсы? Какая погода?" → только ["Какие курсы есть?"]

4+ вопроса = need_simplification:
"Сколько стоит, кто ведет, сколько детей, расписание?" → 4 вопроса → need_simplification

СОЦИАЛЬНЫЙ КОНТЕКСТ (отмечай, но не включай в вопросы):
- greeting (привет), thanks (спасибо), apology (извините), farewell (до свидания)
"Привет! Сколько стоит?" → social_context: "greeting", вопросы: ["Сколько стоит?"]

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

ВАЖНО: При сомнениях между offtopic и success - выбирай success!

ПРИМЕРЫ ПОДСЧЁТА:
- ["Какая цена?", "Есть ли скидки?"] → 2 вопроса → success ✅
- ["Какая цена?", "Кто преподаватели?", "Когда занятия?"] → 3 вопроса → success ✅
- ["Какая цена?", "Есть ли скидки?", "Кто преподаватели?", "Когда занятия?"] → 4 вопроса → need_simplification ⚠️
- [] → 0 вопросов → offtopic ❌

ШАГ 3: ВЫБОР ДОКУМЕНТОВ (только для status: "success")
ЦЕЛЬ: покрыть все вопросы при лимите максимум 4 документа.

АЛГОРИТМ ВЫБОРА:
1) Для каждого вопроса выбери 1-2 документа:
   - 1 основной документ (primary) - максимально релевантный
   - 1 дополнительный (support) - если нужен для полного ответа
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

ОПЕРАЦИОННЫЕ РЕПЛИКИ (всегда школьные, status: "success"):
- «Запишите нас», «Записаться на пробный», «Давайте попробуем»,
- «Отправьте ссылку», «Дайте контакт/почту», «Хочу записаться», «Как записаться»,
- Операционные вопросы о записи и условиях → faq.md, conditions.md
- Вопросы о документах школы: «покажите лицензию», «есть ли лицензия», «сертификаты», «разрешения»,
  «документы на образовательную деятельность» → это ШКОЛЬНЫЕ вопросы → safety_and_trust.md, faq.md

ОБЪЕДИНЕНИЕ ДОКУМЕНТОВ:
- Убери дубликаты (если для двух вопросов нужен один документ)
- Максимум 4 документа на весь ответ
- Первые по приоритету - документы для первых вопросов

ШАГ 4: ОПРЕДЕЛЕНИЕ СИГНАЛА ПОЛЬЗОВАТЕЛЯ
Проанализируй декомпозированные вопросы и определи ОДИН основной сигнал состояния пользователя:

СИГНАЛЫ:
- "price_sensitive" - вопросы о ценах, стоимости, скидках, способах оплаты, рассрочке, подозрения в обмане
- "anxiety_about_child" - упоминание проблем ребенка (стеснительность, неуверенность, страхи, травмы, сложности)
- "ready_to_buy" - готовность к записи: явные запросы на запись ИЛИ краткие деловые вопросы о логистике
- "exploring_only" - общие вопросы о школе, методологии, курсах без конкретной готовности к покупке

ВАЖНО: Агрессивный тон ("развод", "лабуда", "бабло тянете") часто = price_sensitive (недоверие к цене)

ПРАВИЛА ОПРЕДЕЛЕНИЯ:
1. Анализируй ВСЕ декомпозированные вопросы в совокупности
2. ВАЖНО: Учитывай стиль общения - краткий телеграфный стиль (< 5 слов) часто = ready_to_buy
3. УСИЛЕННАЯ ИНЕРЦИЯ для price_sensitive: Если диалог начался с агрессивных вопросов о цене - сохраняй price_sensitive с вероятностью 85%
   - Вопросы про "отзывы", "гарантии", "реально работает" от агрессивного родителя = продолжение price_sensitive
   - Меняй на exploring_only ТОЛЬКО если тон стал нейтральным и вопросы не про ценность
4. ПЕРЕХОДЫ СИГНАЛОВ:
   - exploring_only → ready_to_buy: при словах "записать", "trial", "book us", "пробное"
   - price_sensitive → ready_to_buy: при переходе от скидок к записи ("подходит", "записывайте")
   - Многодетные родители: сначала price_sensitive (скидки), потом ready_to_buy (запись)
5. Выбирай наиболее приоритетный сигнал по порядку: ready_to_buy > anxiety_about_child > price_sensitive > exploring_only
6. Если не можешь однозначно определить - используй "exploring_only"

МАРКЕРЫ price_sensitive:
- Агрессивные вопросы о цене: "дорого", "с ума сошли", "30 тысяч?!", "почему так много"
- Подозрения в обмане: "развод", "лабуда", "бабло тянете", "маркетинговая чушь"
- Требование доказательств ценности: "реально работает?", "покажите отзывы", "гарантии какие"
- Скептицизм к результатам: "толк какой", "и что это даст", "зачем переплачивать"
- ВАЖНО: сохраняй price_sensitive на протяжении всего агрессивного диалога

МАРКЕРЫ ready_to_buy:
- Явные: "хочу записать", "запишите нас", "как записаться", "где записаться", "book us"
- Контекстуальные краткие (телеграфный стиль):
  * "Курс [название]. Когда старт?" - проверка доступности
  * "Онлайн есть?" - проверка формата  
  * "Цена? Сроки?" - финальная проверка перед решением
  * "Оплата?", "Ссылку", "Документы?" - подготовка к записи
  * "Trial есть?" - современный сленг готовности
- Паттерн: фокус на ПРОЦЕССЕ и ЛОГИСТИКЕ, а не на сути курсов

ПРИМЕРЫ:
price_sensitive: "30 тысяч?!", "развод для родителей?", "реально работает?"
anxiety_about_child: "сын стеснительный", "боится выступать", "неуверенный"
ready_to_buy: "запишите нас", "когда старт?", "онлайн есть?", "trial?"
exploring_only: "расскажите о школе", "какая методология?", "чем занимаетесь?", "что за курсы?", "какие навыки развиваете?"

МАРКЕРЫ exploring_only (украинские родители-исследователи):
- "расскажите подробнее", "что это за школа", "чем именно занимаетесь"
- "какие навыки", "какая программа", "что дает ребенку"
- "чем отличаетесь", "почему именно вы", "какой подход"
- БЕЗ упоминания цены, проблем ребенка или готовности записаться

СТИЛЬ КАК ИНДИКАТОР:
- Телеграфный стиль (1-3 слова) + логистика = ready_to_buy с вероятностью 80%
- Развернутые вопросы с объяснениями = exploring_only или anxiety_about_child
- Краткие вопросы о цене БЕЗ других вопросов = price_sensitive
- Краткие вопросы о цене С вопросами о процессе = ready_to_buy

"""
    
    def _get_response_format_section(self) -> str:
        """Минимальный формат JSON-ответа"""
        return (
            "=== ФОРМАТ JSON ОТВЕТА (МИНИМАЛЬНЫЙ) ===\n\n"
            "1) success:\n{\n  \"status\": \"success\",\n  \"documents\": [\"doc1.md\", ...],\n  \"decomposed_questions\": [\"Вопрос 1?\", ...],\n  \"user_signal\": \"price_sensitive\",  // ОБЯЗАТЕЛЬНО: один из 4 сигналов\n  \"social_context\": \"greeting\"  // опционально, если был социальный контекст\n}\n\n"
            "2) offtopic:\n{\n  \"status\": \"offtopic\",\n  \"decomposed_questions\": [],\n  \"user_signal\": \"exploring_only\",  // для offtopic всегда exploring_only\n  \"social_context\": \"farewell\"  // опционально\n}\n"
            "ВАЖНО: для offtopic НЕ генерируй message - используется заготовленная фраза\n\n"
            "3) need_simplification:\n{\n  \"status\": \"need_simplification\",\n  \"message\": \"Пожалуйста, задавайте не более трёх вопросов за раз. Например, начните с самого важного для вас.\",\n  \"decomposed_questions\": [\"Вопрос 1?\", ...],\n  \"user_signal\": \"exploring_only\",  // определи сигнал даже для need_simplification\n  \"social_context\": \"apology\"  // опционально\n}\n\n"
            "Только валидный JSON, без markdown и комментариев. Поле decomposed_questions всегда присутствует.\n"
            "Поле user_signal ОБЯЗАТЕЛЬНО (price_sensitive|anxiety_about_child|ready_to_buy|exploring_only).\n"
            "Поле social_context добавляй ТОЛЬКО если был социальный контекст (greeting/thanks/apology/farewell).\n"
        )
    
    def _fallback_response(self) -> dict:
        """Универсальный ответ при любых ошибках"""
        return {
            "status": "offtopic",
            "message": DEFAULT_FALLBACK,
            "decomposed_questions": [],
            "user_signal": "exploring_only"
        }