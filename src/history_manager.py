"""
history_manager.py - Хранение истории диалогов
MVP версия: только добавление и получение
"""

from typing import List, Dict
from config import Config

class HistoryManager:
    """Менеджер истории диалогов"""
    
    def __init__(self):
        """Инициализация хранилища"""
        self.storage = {}  # {user_id: [messages]}
        config = Config()
        self.max_messages = config.HISTORY_LIMIT  # Используем настройку из конфига
    
    def add_message(self, user_id: str, role: str, content: str):
        """Добавляет сообщение в историю"""
        # Создаём список для нового пользователя
        if user_id not in self.storage:
            self.storage[user_id] = []
        
        # Добавляем сообщение
        self.storage[user_id].append({
            "role": role,
            "content": content
        })
        
        # Обрезаем если больше лимита (HISTORY_LIMIT из конфига)
        if len(self.storage[user_id]) > self.max_messages:
            self.storage[user_id] = self.storage[user_id][-self.max_messages:]
    
    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        """Возвращает историю пользователя"""
        return self.storage.get(user_id, [])