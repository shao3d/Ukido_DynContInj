"""
main.py - FastAPI сервер чатбота для школы Ukido (версия 0.7.3)
Минималистичная версия: Router (Gemini) → Generator (Claude)
"""

import os
import random
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

# === ИНИЦИАЛИЗАЦИЯ ===
app = FastAPI(title="Ukido Chatbot API", version="0.7.3")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# === ГЛОБАЛЬНЫЕ КОМПОНЕНТЫ ===
router = Router(use_cache=True)
response_generator = ResponseGenerator()
history = HistoryManager()
social_state = SocialStateManager()
social_responder = SocialResponder(social_state)
config = Config()


# === ЭНДПОИНТЫ ===
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной эндпоинт для общения с чатботом - ULTRA минималистичная версия"""
    
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
    
    # Генерация ответа в зависимости от статуса
    if status == "success":
        documents_used = documents if isinstance(documents, list) else []
        try:
            # Передаем социальный контекст в генератор
            response_text = await response_generator.generate(
                {
                    "status": status,
                    "documents": documents_used,
                    "decomposed_questions": decomposed_questions,
                    "social_context": social_context,  # Передаем контекст
                },
                history_messages,
            )
        except Exception as e:
            print(f"❌ ResponseGenerator failed: {e}")
            response_text = get_error_response("generation_failed")
    else:
        # Для offtopic и need_simplification тоже обрабатываем социальный контекст
        # НО! Если это прощание (farewell), то игнорируем offtopic message
        if social_context == "farewell":
            base_message = ""  # Для прощания НЕ используем offtopic сообщение
        else:
            base_message = message if message else DEFAULT_FALLBACK
        documents_used = []
        
        # Добавляем социальные элементы к offtopic/need_simplification ответам
        if social_context:
            if social_context == "greeting":
                # Проверяем, было ли уже приветствие
                if not social_state.has_greeted(request.user_id):
                    greetings = ["Здравствуйте!", "Добрый день!", "Приветствуем!"]
                    response_text = f"{random.choice(greetings)} {base_message}"
                    social_state.mark_greeted(request.user_id)
                else:
                    response_text = base_message
            elif social_context == "thanks":
                thanks_responses = ["Пожалуйста!", "Рады помочь!", "Всегда пожалуйста!"]
                response_text = f"{random.choice(thanks_responses)} {base_message}"
            elif social_context == "apology":
                apology_responses = ["Ничего страшного!", "Всё в порядке!", "Не переживайте!"]
                response_text = f"{random.choice(apology_responses)} {base_message}"
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
    
    # === ВОЗВРАТ РЕЗУЛЬТАТА ===
    return ChatResponse(
        response=response_text,
        relevant_documents=documents_used if 'documents_used' in locals() else [],
        intent=status,
        confidence=1.0,  # MVP: всегда 1.0 для совместимости
        decomposed_questions=decomposed_questions,
        fuzzy_matched=fuzzy_matched,
        social=social_context,  # Социальный контекст от Gemini
    )


@app.get("/health")
async def health_check():
    """Проверка состояния сервера"""
    return {"status": "healthy", "version": "0.7.3"}


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