"""
Chainlit адаптер для Ukido AI Assistant v0.13.5
Обеспечивает стриминг и красивый UI для чатбота
"""

import chainlit as cl
import sys
import os
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Добавляем путь к src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем КЛАССЫ, а не экземпляры
from src.router import Router
from src.response_generator import ResponseGenerator  
from src.history_manager import HistoryManager
from src.persistence_manager import PersistenceManager, create_state_snapshot, restore_state_snapshot
from src.social_state import SocialStateManager
from src.simple_cta_blocker import SimpleCTABlocker
from src.config import Config
from src.standard_responses import get_offtopic_response

# Инициализация глобальных компонентов
config = Config()
router = Router(use_cache=True)
response_generator = ResponseGenerator()
history_manager = HistoryManager()
persistence_manager = PersistenceManager(base_path="data/persistent_states")
social_state = SocialStateManager()
simple_cta_blocker = SimpleCTABlocker()

# Глобальный словарь для user_signals (как в main.py)
user_signals_history = {}

# Опционально: инициализация юмора Жванецкого
zhvanetsky_generator = None
zhvanetsky_safety_checker = None

if config.ZHVANETSKY_ENABLED:
    try:
        from src.zhvanetsky_humor import ZhvanetskyGenerator
        from src.zhvanetsky_safety import SafetyChecker
        from src.openrouter_client import OpenRouterClient
        
        zhvanetsky_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model="anthropic/claude-3.5-haiku",
            temperature=config.ZHVANETSKY_TEMPERATURE
        )
        
        zhvanetsky_safety_checker = SafetyChecker()
        zhvanetsky_generator = ZhvanetskyGenerator(
            client=zhvanetsky_client,
            config=config
        )
        print(f"🎭 Юмор Жванецкого активирован в Chainlit (вероятность: {config.ZHVANETSKY_PROBABILITY * 100}%)")
    except Exception as e:
        print(f"⚠️ Юмор Жванецкого не загружен: {e}")

@cl.on_chat_start
async def start_chat():
    """Инициализация новой сессии чата"""
    
    # Используем session.id как user_id
    user_id = cl.context.session.id
    
    # Сохраняем в сессию
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("message_count", 0)
    cl.user_session.set("greeting_exchanged", False)
    
    # Пытаемся восстановить состояние
    saved_state = persistence_manager.load_state(user_id)
    if saved_state:
        # Восстанавливаем через функцию из main.py
        restore_state_snapshot(
            saved_state, 
            history_manager, 
            user_signals_history,
            social_state, 
            user_id
        )
        cl.user_session.set("user_signal", saved_state.get("user_signal", "exploring_only"))
        cl.user_session.set("message_count", saved_state.get("message_count", 0))
        cl.user_session.set("greeting_exchanged", saved_state.get("greeting_exchanged", False))
        
        await cl.Message(
            content="🔄 Восстановлен предыдущий диалог. Продолжим с того места, где остановились!"
        ).send()
    else:
        cl.user_session.set("user_signal", "exploring_only")
        
        # Приветственное сообщение
        welcome_message = """👋 Здравствуйте! Я AI-помощник школы Ukido.
        
Я помогу вам узнать о:
• 🎓 Курсах soft skills для детей 7-14 лет
• 💰 Стоимости и условиях обучения  
• 👩‍🏫 Преподавателях и методике
• 📅 Расписании занятий

Чем могу помочь?"""
        
        await cl.Message(content=welcome_message).send()

@cl.on_message
async def main(message: cl.Message):
    """Обработка сообщений пользователя с стримингом"""
    
    # Получаем данные сессии
    user_id = cl.user_session.get("user_id")
    message_count = cl.user_session.get("message_count", 0) + 1
    cl.user_session.set("message_count", message_count)
    
    user_signal = cl.user_session.get("user_signal", "exploring_only")
    greeting_exchanged = cl.user_session.get("greeting_exchanged", False)
    
    # Создаём сообщение для стриминга
    msg = cl.Message(content="")
    await msg.send()
    
    try:
        # Показываем индикатор обработки
        await msg.stream_token("🔍 ")
        await asyncio.sleep(0.3)
        
        # Получаем историю
        history_messages = history_manager.get_history(user_id)
        
        # === ЭТАП 1: ROUTER ===
        router_result = await router.route(
            message.content, 
            history_messages, 
            user_id
        )
        
        # Извлекаем данные из результата роутера
        intent = router_result.get("intent", "success")
        new_signal = router_result.get("user_signal", user_signal)
        documents = router_result.get("documents", [])
        decomposed_questions = router_result.get("decomposed_questions", [])
        
        # HOTFIX: Сохраняем user_signal (как в main.py)
        if new_signal and new_signal != user_signal:
            user_signals_history[user_id] = new_signal
            cl.user_session.set("user_signal", new_signal)
            user_signal = new_signal  # Обновляем локальную переменную
        
        # Начинаем стриминг (пока без токенов)
        
        # === ЭТАП 2: ГЕНЕРАЦИЯ ОТВЕТА ===
        response_text = ""
        response_metadata = {}
        
        if intent == "offtopic":
            # Обработка offtopic с юмором
            humor_generated = False
            
            if zhvanetsky_generator and config.ZHVANETSKY_ENABLED:
                # Проверяем можно ли использовать юмор
                if zhvanetsky_safety_checker:
                    can_use_humor = zhvanetsky_safety_checker.check_user_signal(new_signal)
                    if can_use_humor:
                        try:
                            # Показываем индикатор юмора
                            await msg.stream_token("🎭 ")
                            await asyncio.sleep(0.2)
                            
                            # Генерируем юмор
                            humor_response = await zhvanetsky_generator.generate_humor(
                                message.content,
                                history_messages[-5:] if history_messages else [],
                                new_signal,
                                is_greeting=(not greeting_exchanged and social_state.is_greeting(message.content))
                            )
                            
                            if humor_response and humor_response.strip():
                                response_text = humor_response
                                humor_generated = True
                                response_metadata = {"humor_generated": True}
                        except Exception as e:
                            print(f"⚠️ Ошибка генерации юмора: {e}")
            
            # Если юмор не сгенерирован - стандартный ответ
            if not response_text:
                response_text = get_offtopic_response()
                response_metadata = {"humor_generated": False}
                
        elif intent == "need_simplification":
            response_text = "Я заметил несколько вопросов. Давайте разберём их по порядку. С чего начнём?"
            response_metadata = {"intent": "need_simplification"}
            
        else:  # success
            # Подготовка данных для генератора
            router_data = {
                "status": "success",
                "documents": documents,
                "decomposed_questions": decomposed_questions,
                "user_signal": new_signal,
                "cta_blocked": False,  # Упрощаем для MVP
                "cta_frequency_modifier": 1.0,
                "social_context": {"greeting_exchanged": greeting_exchanged}
            }
            
            # Генерация ответа
            response_text, response_metadata = await response_generator.generate(
                router_data,
                history=history_messages,
                current_message=message.content
            )
        
        # === ЭТАП 3: СТРИМИНГ ОТВЕТА ===
        # Разбиваем текст на слова для плавного стриминга
        words = response_text.split()
        
        # Стримим по 2-3 слова за раз для плавности
        for i in range(0, len(words), 2):
            chunk = " ".join(words[i:min(i+2, len(words))])
            if i > 0:
                chunk = " " + chunk  # Добавляем пробел между чанками
            await msg.stream_token(chunk)
            await asyncio.sleep(0.03)  # Задержка для эффекта печати
        
        # Завершаем стриминг
        await msg.update()
        
        # === ЭТАП 4: СОХРАНЕНИЕ СОСТОЯНИЯ ===
        # Добавляем в историю
        history_manager.add_message(user_id, "user", message.content)
        history_manager.add_message(user_id, "assistant", response_text)
        
        # Обновляем greeting status
        if social_state.is_greeting(message.content):
            cl.user_session.set("greeting_exchanged", True)
            social_state.mark_greeted(user_id)
        
        # Сохраняем состояние (как в main.py)
        state_snapshot = create_state_snapshot(
            history_manager,
            user_signals_history, 
            social_state,
            user_id
        )
        persistence_manager.save_state(user_id, state_snapshot)
        
    except Exception as e:
        error_msg = f"😔 Извините, произошла ошибка: {str(e)}"
        # Для ошибок создаём новое сообщение
        await cl.Message(content=error_msg).send()
        print(f"❌ Ошибка в Chainlit: {e}")
        import traceback
        traceback.print_exc()

@cl.on_stop
async def stop_chat():
    """Сохранение при завершении чата"""
    user_id = cl.user_session.get("user_id")
    if user_id:
        try:
            state_snapshot = create_state_snapshot(
                history_manager,
                user_signals_history,
                social_state, 
                user_id
            )
            persistence_manager.save_state(user_id, state_snapshot)
            print(f"💾 Состояние сохранено для {user_id}")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения: {e}")

if __name__ == "__main__":
    cl.run()