"""
history_manager.py - Хранение истории диалогов
MVP версия: с LRU Cache для предотвращения memory leak
"""

from typing import List, Dict
from collections import OrderedDict
from config import Config

class HistoryManager:
    """Менеджер истории диалогов с ограничением количества пользователей"""
    
    def __init__(self):
        """Инициализация хранилища с LRU механизмом"""
        # OrderedDict помнит порядок добавления для LRU
        self.storage = OrderedDict()  # {user_id: [messages]}
        config = Config()
        self.max_messages = config.HISTORY_LIMIT  # Используем настройку из конфига
        # Максимальное количество пользователей в памяти
        self.max_users = 1000  # Достаточно для MVP, ~10MB памяти
    
    def add_message(self, user_id: str, role: str, content: str, metadata: dict = None):
        """Добавляет сообщение в историю с LRU механизмом и опциональными метаданными"""
        
        # Если пользователь уже есть - перемещаем в конец (он активный)
        if user_id in self.storage:
            self.storage.move_to_end(user_id)
        else:
            # Новый пользователь - проверяем лимит
            if len(self.storage) >= self.max_users:
                # Удаляем самого старого неактивного пользователя
                oldest_user = next(iter(self.storage))
                del self.storage[oldest_user]
                print(f"⚠️ LRU: Удалена история пользователя {oldest_user[:8]}... (неактивен)")
            
            # Создаём список для нового пользователя
            self.storage[user_id] = []
        
        # Добавляем сообщение с опциональными метаданными
        message = {
            "role": role,
            "content": content
        }
        if metadata:
            message["metadata"] = metadata
        
        self.storage[user_id].append(message)
        
        # Обрезаем если больше лимита сообщений (HISTORY_LIMIT из конфига)
        if len(self.storage[user_id]) > self.max_messages:
            self.storage[user_id] = self.storage[user_id][-self.max_messages:]
    
    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        """Возвращает историю пользователя"""
        return self.storage.get(user_id, [])
    
    def get_message_metadata(self, msg: dict) -> dict:
        """Helper для получения metadata из сообщения с обратной совместимостью"""
        if "metadata" in msg:
            return msg["metadata"]
        
        # Fallback для старых сообщений без metadata
        return {
            "cta_added": False,
            "cta_type": None,
            "user_signal": "exploring_only"
        }
    
    def clear_user_history(self, user_id: str):
        """Очищает историю конкретного пользователя"""
        if user_id in self.storage:
            del self.storage[user_id]
            print(f"🧹 История пользователя {user_id} очищена")