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
    
    def add_message(self, user_id: str, role: str, content: str):
        """Добавляет сообщение в историю с LRU механизмом"""
        
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
        
        # Добавляем сообщение
        self.storage[user_id].append({
            "role": role,
            "content": content
        })
        
        # Обрезаем если больше лимита сообщений (HISTORY_LIMIT из конфига)
        if len(self.storage[user_id]) > self.max_messages:
            self.storage[user_id] = self.storage[user_id][-self.max_messages:]
    
    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        """Возвращает историю пользователя"""
        return self.storage.get(user_id, [])