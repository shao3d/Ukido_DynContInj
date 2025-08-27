"""
main.py - FastAPI сервер чатбота для школы Ukido (версия 0.7.3)
Минималистичная версия: Router (Gemini) → Generator (Claude)
"""

import os
import random
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys

# Добавляем путь к src для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router import Router
from response_generator import ResponseGenerator
from history_manager import HistoryManager
from social_intents import SocialIntent
from social_responder import SocialResponder
from social_state import SocialStateManager
from config import Config
from standard_responses import DEFAULT_FALLBACK, get_error_response
from datetime import datetime
from typing import Dict

# === ДЕТЕРМИНИРОВАННОСТЬ ДЛЯ ВОСПРОИЗВОДИМОСТИ ===
# Устанавливаем глобальный seed для всех random операций
config = Config()
if config.DETERMINISTIC_MODE:
    random.seed(config.SEED)  # Теперь все random.choice() будут предсказуемыми
    print(f"🎲 Random seed установлен: {config.SEED} (детерминированный режим)")
else:
    # Используем системную энтропию для настоящей случайности
    print("🎲 Случайный режим активен (системная энтропия)")

# === ИНИЦИАЛИЗАЦИЯ ===
app = FastAPI(title="Ukido Chatbot API", version="0.8.0-state-machine")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === ПРОСТЫЕ МЕТРИКИ ===
signal_stats = {
    "price_sensitive": 0,
    "anxiety_about_child": 0, 
    "ready_to_buy": 0,
    "exploring_only": 0
}
request_count = 0
total_latency = 0.0
start_time = datetime.now()

# === МОДЕЛИ ДАННЫХ ===
class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    relevant_documents: List[str] = []
    intent: str = ""
    confidence: float = 0.0
    decomposed_questions: List[str] = []
    fuzzy_matched: Optional[bool] = None
    social: Optional[str] = None
    user_signal: Optional[str] = None  # Добавляем user_signal в ответ


# === ГЛОБАЛЬНЫЕ КОМПОНЕНТЫ ===
router = Router(use_cache=True)
response_generator = ResponseGenerator()
history = HistoryManager()
social_state = SocialStateManager()
social_responder = SocialResponder(social_state)

# === ГЛОБАЛЬНЫЙ СИНГЛТОН ДЛЯ ЮМОРА ЖВАНЕЦКОГО ===
zhvanetsky_generator = None
zhvanetsky_safety_checker = None

if config.ZHVANETSKY_ENABLED:
    try:
        from zhvanetsky_humor import ZhvanetskyGenerator
        from zhvanetsky_safety import SafetyChecker
        from openrouter_client import OpenRouterClient
        
        # Создаём OpenRouter client для Haiku
        zhvanetsky_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model="anthropic/claude-3.5-haiku",
            temperature=config.ZHVANETSKY_TEMPERATURE
        )
        
        # Создаём глобальные синглтоны
        zhvanetsky_safety_checker = SafetyChecker()
        zhvanetsky_generator = ZhvanetskyGenerator(
            client=zhvanetsky_client,
            config=config
        )
        
        print(f"🎭 Система юмора Жванецкого инициализирована (вероятность: {config.ZHVANETSKY_PROBABILITY * 100}%)")
    except Exception as e:
        print(f"⚠️ Не удалось инициализировать систему юмора: {e}")
        config.ZHVANETSKY_ENABLED = False


# === ЭНДПОИНТЫ ===
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной эндпоинт для общения с чатботом - версия с State Machine"""
    global signal_stats, request_count, total_latency
    
    # Засекаем время для метрик
    import time
    start = time.time()
    
    # Получаем историю если есть
    history_messages = []
    if history:
        history_messages = history.get_history(request.user_id)
    
    # === PIPELINE: Router (Gemini) → Generator (Claude) ===
    
    # Всё идет в Router
    print(f"ℹ️ Routing: {request.message[:50]}..." if len(request.message) > 50 else f"ℹ️ Routing: {request.message}")
    
    try:
        # Передаем user_id в Router для отслеживания социального состояния
        route_result = await router.route(request.message, history_messages, request.user_id)
        
        if config.LOG_LEVEL == "DEBUG":
            print(f"🔍 DEBUG Router result: {route_result}")
    except Exception as e:
        print(f"❌ Router failed: {e}")
        route_result = {
            "status": "offtopic",
            "message": "Временная проблема. Попробуйте позже.",
            "decomposed_questions": []
        }
    
    # Обрабатываем результат роутера
    status = route_result.get("status", "offtopic")
    message = route_result.get("message", "")
    documents = route_result.get("documents", [])
    decomposed_questions = route_result.get("decomposed_questions", [])
    social_context = route_result.get("social_context")  # Новое поле от Gemini
    fuzzy_matched = route_result.get("fuzzy_matched", False)
    user_signal = route_result.get("user_signal", "exploring_only")  # Получаем user_signal
    
    # HOTFIX: Восстанавливаем user_signal для offtopic из предыдущих успешных запросов
    # Проблема: Gemini 2.5 Flash игнорирует инструкцию сохранять user_signal для offtopic
    if status == "offtopic" and user_signal == "exploring_only":
        # Храним историю сигналов в глобальной переменной для каждого пользователя
        if not hasattr(chat, 'user_signals_history'):
            chat.user_signals_history = {}
        
        # Получаем последний известный сигнал для этого пользователя
        if request.user_id in chat.user_signals_history:
            last_signal = chat.user_signals_history[request.user_id]
            if last_signal != "exploring_only":
                original_signal = user_signal
                user_signal = last_signal
                print(f"🔧 HOTFIX: Восстановлен user_signal='{user_signal}' из истории (Router вернул '{original_signal}')")
    
    # Сохраняем текущий сигнал для будущих offtopic
    if status == "success" and user_signal != "exploring_only":
        if not hasattr(chat, 'user_signals_history'):
            chat.user_signals_history = {}
        chat.user_signals_history[request.user_id] = user_signal
        print(f"💾 Сохранён user_signal='{user_signal}' для user_id='{request.user_id}'")
    
    # Отладочный вывод
    print(f"🔍 DEBUG: Router returned user_signal='{user_signal}', status='{status}'")
    
    # Собираем метрики
    if user_signal in signal_stats:
        signal_stats[user_signal] += 1
    
    # Генерация ответа в зависимости от статуса
    if status == "success":
        documents_used = documents if isinstance(documents, list) else []
        try:
            # Передаем социальный контекст и user_signal в генератор
            response_text = await response_generator.generate(
                {
                    "status": status,
                    "documents": documents_used,
                    "decomposed_questions": decomposed_questions,
                    "social_context": social_context,  # Передаем контекст
                    "user_signal": user_signal,  # Передаем user_signal для персонализации
                    "original_message": request.message,  # Добавляем оригинальное сообщение
                },
                history_messages,
                request.message,  # Передаём текущее сообщение отдельно для корректной проверки CTA
            )
            
            # === ОБРАБОТКА СОЦИАЛЬНЫХ ИНТЕНТОВ ДЛЯ SUCCESS СЛУЧАЕВ ===
            # Правило: Бизнес-интент ВСЕГДА приоритетнее социального
            
            # 1. Farewell для success - добавляем прощание в КОНЕЦ ответа
            if social_context == "farewell":
                # Проверяем, нет ли уже прощания в ответе
                farewell_markers = ["до свидания", "до встречи", "всего доброго", "удачи", "до связи"]
                if not any(marker in response_text.lower() for marker in farewell_markers):
                    farewells = [
                        "\n\nДо свидания! Будем рады видеть вас в нашей школе!",
                        "\n\nВсего доброго! Обращайтесь, если появятся вопросы!",
                        "\n\nДо встречи! Надеемся увидеть вашего ребенка на занятиях!",
                        "\n\nУдачи вам! До связи!"
                    ]
                    response_text += random.choice(farewells)
                    if config.LOG_LEVEL == "DEBUG":
                        print(f"✅ Added farewell to success response")
            
            # 2. Thanks для success - добавляем короткий префикс
            elif social_context == "thanks":
                # Проверяем, нет ли уже благодарности в начале
                thanks_markers = ["рад", "пожалуйста", "всегда пожалуйста"]
                if not any(response_text.lower().startswith(marker) for marker in thanks_markers):
                    thanks_prefixes = ["Рады помочь! ", "Пожалуйста! "]
                    response_text = random.choice(thanks_prefixes) + response_text
                    if config.LOG_LEVEL == "DEBUG":
                        print(f"✅ Added thanks prefix to success response")
                        
        except Exception as e:
            print(f"❌ ResponseGenerator failed: {e}")
            response_text = get_error_response("generation_failed")
    else:
        # Для offtopic и need_simplification тоже обрабатываем социальный контекст
        # Определяем, нужно ли добавлять offtopic сообщение
        pure_social_intents = ["greeting", "thanks", "farewell", "apology"]
        is_pure_social = social_context in pure_social_intents and status == "offtopic"
        
        if is_pure_social:
            # Для чистых социальных интентов НЕ используем offtopic сообщение
            base_message = ""
        else:
            base_message = message if message else DEFAULT_FALLBACK
        documents_used = []
        
        # === ИНТЕГРАЦИЯ ЮМОРА ЖВАНЕЦКОГО ===
        # Проверяем возможность использования юмора для content offtopic
        if status == "offtopic" and not is_pure_social and zhvanetsky_generator and zhvanetsky_safety_checker:
            # Отладочный вывод
            print(f"🔍 DEBUG main.py: Checking humor for offtopic. user_signal='{user_signal}', is_pure_social={is_pure_social}")
            
            # Используем глобальный SafetyChecker для проверки
            can_use_humor, humor_context = zhvanetsky_safety_checker.should_use_humor(
                message=request.message,
                user_signal=user_signal,
                history=history_messages,
                user_id=request.user_id,
                is_pure_social=is_pure_social
            )
            
            if can_use_humor:
                try:
                    # Генерируем юмор через глобальный генератор
                    humor_response = await zhvanetsky_generator.generate_humor(
                        message=request.message,
                        history=history_messages,
                        user_signal=user_signal,
                        user_id=request.user_id,
                        timeout=config.ZHVANETSKY_TIMEOUT
                    )
                    
                    if humor_response:
                        # Используем юмористический ответ вместо стандартного
                        base_message = humor_response
                        # Отмечаем использование юмора для rate limiting
                        zhvanetsky_safety_checker.mark_humor_used(request.user_id)
                        print(f"🎭 Zhvanetsky humor used for user {request.user_id}")
                    else:
                        # Fallback на стандартный offtopic
                        from standard_responses import get_offtopic_response
                        base_message = get_offtopic_response()
                        
                except Exception as e:
                    print(f"❌ Zhvanetsky generation failed: {e}")
                    from standard_responses import get_offtopic_response
                    base_message = get_offtopic_response()
        
        # Добавляем социальные элементы к offtopic/need_simplification ответам
        if social_context:
            if social_context == "greeting":
                # Проверяем, было ли уже приветствие
                if not social_state.has_greeted(request.user_id):
                    if is_pure_social:
                        # Для чистого приветствия используем полноценный ответ
                        greetings = [
                            "Здравствуйте! Я помощник школы Ukido. Чем могу помочь?",
                            "Добрый день! Рад помочь с вопросами о наших курсах.",
                            "Приветствую! Готов рассказать о программах школы Ukido."
                        ]
                        response_text = random.choice(greetings)
                    else:
                        # Для mixed случаев добавляем префикс
                        response_text = f"Здравствуйте! {base_message}"
                    social_state.mark_greeted(request.user_id)
                else:
                    response_text = base_message if base_message else "Я на связи. Чем помочь?"
            elif social_context == "thanks":
                if is_pure_social:
                    # Для чистой благодарности используем полноценный ответ
                    thanks_responses = [
                        "Пожалуйста! Обращайтесь, если будут вопросы.",
                        "Рады помочь! Если нужна дополнительная информация - спрашивайте.",
                        "Всегда пожалуйста! Готов ответить на другие вопросы."
                    ]
                    response_text = random.choice(thanks_responses)
                else:
                    # Для mixed случаев добавляем префикс
                    response_text = f"Пожалуйста! {base_message}"
            elif social_context == "apology":
                if is_pure_social:
                    # Для чистого извинения используем полноценный ответ
                    apology_responses = [
                        "Ничего страшного! Чем могу помочь?",
                        "Всё в порядке! Готов ответить на ваши вопросы.",
                        "Не переживайте! Расскажите, что вас интересует."
                    ]
                    response_text = random.choice(apology_responses)
                else:
                    # Для mixed случаев добавляем префикс
                    response_text = f"Ничего страшного! {base_message}"
            elif social_context == "repeated_greeting":
                # Для повторного приветствия НЕ добавляем социальный префикс
                response_text = base_message
            elif social_context == "farewell":
                # Для прощания используем ТОЛЬКО прощальную фразу, без offtopic сообщения
                farewells = [
                    "Было приятно помочь! До свидания!",
                    "Спасибо за обращение! Всего доброго!",
                    "Рады были проконсультировать! До встречи!",
                    "Удачи вам! До свидания!",
                    "Будем рады видеть вас в нашей школе! До связи!"
                ]
                response_text = random.choice(farewells)
                # ВАЖНО: НЕ добавляем base_message для прощания!
            else:
                response_text = base_message
        else:
            response_text = base_message
    
    # === СОХРАНЕНИЕ В ИСТОРИЮ ===
    if history:
        history.add_message(request.user_id, "user", request.message)
        history.add_message(request.user_id, "assistant", response_text)
    
    # Собираем финальные метрики
    latency = time.time() - start
    request_count += 1
    total_latency += latency
    
    if config.LOG_LEVEL == "DEBUG":
        print(f"⏱️ Latency: {latency:.2f}s | Signal: {user_signal}")
    
    # === ВОЗВРАТ РЕЗУЛЬТАТА ===
    return ChatResponse(
        response=response_text,
        relevant_documents=documents_used if 'documents_used' in locals() else [],
        intent=status,
        confidence=1.0,  # MVP: всегда 1.0 для совместимости
        decomposed_questions=decomposed_questions,
        fuzzy_matched=fuzzy_matched,
        social=social_context,  # Социальный контекст от Gemini
        user_signal=user_signal,  # Возвращаем user_signal в ответе
    )


@app.get("/metrics")
async def get_metrics():
    """Endpoint для просмотра метрик State Machine"""
    global signal_stats, request_count, total_latency, start_time
    
    uptime = (datetime.now() - start_time).total_seconds()
    avg_latency = total_latency / request_count if request_count > 0 else 0
    
    # Вычисляем проценты для каждого сигнала
    percentages = {}
    if request_count > 0:
        for signal, count in signal_stats.items():
            percentages[signal] = f"{(count / request_count * 100):.1f}%"
    
    # Добавляем метрики Жванецкого если включено
    zhvanetsky_metrics = {}
    if zhvanetsky_generator:
        zhvanetsky_metrics = zhvanetsky_generator.get_metrics()
        zhvanetsky_metrics["enabled"] = True
        zhvanetsky_metrics["probability"] = config.ZHVANETSKY_PROBABILITY
    else:
        zhvanetsky_metrics = {"enabled": False}
    
    return {
        "uptime_seconds": round(uptime, 2),
        "total_requests": request_count,
        "avg_latency": round(avg_latency, 3),
        "signal_distribution": signal_stats,
        "signal_percentages": percentages,
        "most_common_signal": max(signal_stats, key=signal_stats.get) if request_count > 0 and signal_stats else None,
        "zhvanetsky_humor": zhvanetsky_metrics
    }


@app.get("/health")
async def health_check():
    """Проверка состояния сервера"""
    return {"status": "healthy", "version": "0.8.0-state-machine"}


@app.post("/clear_history/{user_id}")
async def clear_history(user_id: str):
    """Очищает историю конкретного пользователя"""
    global history
    if history:
        history.clear_user_history(user_id)
        return {"status": "success", "message": f"History cleared for user {user_id}"}
    return {"status": "error", "message": "History manager not available"}


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"service": "Ukido Chatbot API", "version": "0.7.3"}


# === ЗАПУСК ===
if __name__ == "__main__":
    import uvicorn
    
    # Логирование конфигурации при старте
    print("=" * 50)
    print("🚀 Ukido AI Assistant v0.7.3")
    print("📝 Архитектура: Router → Generator")
    print(f"📝 Уровень логирования: {config.LOG_LEVEL}")
    print(f"💾 Лимит истории: {config.HISTORY_LIMIT} сообщений")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)