"""
persistence_manager.py - Менеджер персистентности состояний для MVP
Сохраняет и восстанавливает состояния диалогов при рестарте сервера
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Управляет сохранением и загрузкой состояний диалогов"""
    
    def __init__(self, base_path: str = "data/persistent_states", 
                 max_age_days: int = 7,
                 max_files: int = 10000):
        """
        Инициализация менеджера персистентности
        
        Args:
            base_path: Путь к папке для хранения состояний
            max_age_days: Максимальный возраст файлов в днях
            max_files: Максимальное количество файлов
        """
        self.base_path = Path(base_path)
        self.max_age_days = max_age_days
        self.max_files = max_files
        
        # Создаём папку если не существует
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Очищаем старые файлы при старте
        self._cleanup_old_files()
        
        print(f"💾 PersistenceManager инициализирован: {self.base_path}")
        print(f"   - Максимальный возраст файлов: {max_age_days} дней")
        print(f"   - Максимум файлов: {max_files}")
    
    def _sanitize_user_id(self, user_id: str) -> str:
        """
        Очищает user_id от опасных символов
        
        Args:
            user_id: Исходный идентификатор пользователя
            
        Returns:
            Безопасный идентификатор для имени файла
        """
        # Оставляем только буквы, цифры, подчёркивания и дефисы
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', user_id)
        # Ограничиваем длину
        return safe_id[:100]
    
    def _get_file_path(self, user_id: str) -> Path:
        """
        Возвращает путь к файлу состояния пользователя
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            Путь к JSON файлу
        """
        safe_id = self._sanitize_user_id(user_id)
        return self.base_path / f"{safe_id}.json"
    
    def save_state(self, user_id: str, state_data: Dict[str, Any]) -> bool:
        """
        Сохраняет состояние пользователя в файл
        
        Args:
            user_id: Идентификатор пользователя
            state_data: Данные для сохранения
            
        Returns:
            True если успешно сохранено
        """
        try:
            file_path = self._get_file_path(user_id)
            
            # Добавляем метаданные
            state_data['user_id'] = user_id
            state_data['last_updated'] = datetime.now().isoformat()
            
            # Сохраняем в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            # Проверяем размер файла (не больше 100KB)
            if file_path.stat().st_size > 100 * 1024:
                logger.warning(f"Файл состояния для {user_id} превышает 100KB")
                # Обрезаем историю если слишком большая
                if 'history' in state_data and len(state_data['history']) > 10:
                    state_data['history'] = state_data['history'][-10:]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния для {user_id}: {e}")
            return False
    
    def load_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает состояние пользователя из файла
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            Данные состояния или None если не найдено
        """
        try:
            file_path = self._get_file_path(user_id)
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Проверяем актуальность данных
            if 'last_updated' in state_data:
                last_updated = datetime.fromisoformat(state_data['last_updated'])
                if datetime.now() - last_updated > timedelta(days=self.max_age_days):
                    logger.info(f"Состояние для {user_id} устарело, удаляем")
                    file_path.unlink()
                    return None
            
            logger.info(f"Загружено состояние для {user_id}")
            return state_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Повреждён JSON для {user_id}: {e}")
            # Удаляем повреждённый файл
            try:
                self._get_file_path(user_id).unlink()
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки состояния для {user_id}: {e}")
            return None
    
    def delete_state(self, user_id: str) -> bool:
        """
        Удаляет состояние пользователя
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            True если успешно удалено
        """
        try:
            file_path = self._get_file_path(user_id)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Удалено состояние для {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления состояния для {user_id}: {e}")
            return False
    
    def _cleanup_old_files(self):
        """Удаляет старые файлы при старте"""
        try:
            now = datetime.now()
            cutoff_time = now - timedelta(days=self.max_age_days)
            
            deleted_count = 0
            for file_path in self.base_path.glob("*.json"):
                try:
                    # Проверяем время модификации файла
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Не удалось удалить {file_path}: {e}")
            
            if deleted_count > 0:
                print(f"🧹 Удалено {deleted_count} старых файлов состояний")
            
            # Проверяем общее количество файлов
            files = list(self.base_path.glob("*.json"))
            if len(files) > self.max_files:
                # Сортируем по времени модификации и удаляем старейшие
                files.sort(key=lambda f: f.stat().st_mtime)
                to_delete = len(files) - self.max_files
                for file_path in files[:to_delete]:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except:
                        pass
                print(f"🧹 Удалено {to_delete} файлов для соблюдения лимита")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке старых файлов: {e}")
    
    def save_all_states(self, states: Dict[str, Dict[str, Any]]) -> int:
        """
        Массовое сохранение всех состояний (для graceful shutdown)
        
        Args:
            states: Словарь {user_id: state_data}
            
        Returns:
            Количество успешно сохранённых состояний
        """
        saved_count = 0
        for user_id, state_data in states.items():
            if self.save_state(user_id, state_data):
                saved_count += 1
        
        print(f"💾 Сохранено {saved_count}/{len(states)} состояний при shutdown")
        return saved_count
    
    def load_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Загружает все сохранённые состояния при старте
        
        Returns:
            Словарь {user_id: state_data}
        """
        states = {}
        loaded_count = 0
        
        try:
            for file_path in self.base_path.glob("*.json"):
                try:
                    # Извлекаем user_id из имени файла
                    user_id = file_path.stem
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    
                    # Проверяем актуальность
                    if 'last_updated' in state_data:
                        last_updated = datetime.fromisoformat(state_data['last_updated'])
                        if datetime.now() - last_updated > timedelta(days=self.max_age_days):
                            file_path.unlink()
                            continue
                    
                    states[user_id] = state_data
                    loaded_count += 1
                    
                except Exception as e:
                    logger.warning(f"Не удалось загрузить {file_path}: {e}")
            
            print(f"📂 Загружено {loaded_count} сохранённых состояний")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке состояний: {e}")
        
        return states
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по сохранённым состояниям
        
        Returns:
            Словарь со статистикой
        """
        try:
            files = list(self.base_path.glob("*.json"))
            total_size = sum(f.stat().st_size for f in files)
            
            return {
                "total_files": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_file": min(files, key=lambda f: f.stat().st_mtime).name if files else None,
                "newest_file": max(files, key=lambda f: f.stat().st_mtime).name if files else None,
                "base_path": str(self.base_path)
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"error": str(e)}


# Вспомогательные функции для интеграции

def create_state_snapshot(history_manager, user_signals_history: Dict, 
                          social_state_manager, user_id: str) -> Dict[str, Any]:
    """
    Создаёт снимок состояния для пользователя
    
    Args:
        history_manager: Менеджер истории
        user_signals_history: Словарь сигналов пользователей
        social_state_manager: Менеджер социальных состояний
        user_id: Идентификатор пользователя
        
    Returns:
        Снимок состояния для сохранения
    """
    state = {
        "history": history_manager.get_history(user_id) if history_manager else [],
        "user_signal": user_signals_history.get(user_id, "exploring_only"),
        "greeting_exchanged": False,
        "message_count": len(history_manager.get_history(user_id)) if history_manager else 0
    }
    
    # Добавляем социальное состояние если есть
    if social_state_manager:
        try:
            social_state = social_state_manager.get(user_id)
            state["greeting_exchanged"] = social_state.greeting_exchanged
            state["language"] = social_state.language
        except:
            pass

    return state


def restore_state_snapshot(state_data: Dict[str, Any], history_manager, 
                           user_signals_history: Dict, social_state_manager, 
                           user_id: str):
    """
    Восстанавливает состояние из снимка
    
    Args:
        state_data: Данные снимка
        history_manager: Менеджер истории
        user_signals_history: Словарь сигналов пользователей  
        social_state_manager: Менеджер социальных состояний
        user_id: Идентификатор пользователя
    """
    # Восстанавливаем историю
    if history_manager and 'history' in state_data:
        for msg in state_data['history']:
            history_manager.add_message(user_id, msg['role'], msg['content'])
    
    # Восстанавливаем user_signal
    if 'user_signal' in state_data:
        user_signals_history[user_id] = state_data['user_signal']
    
    # Восстанавливаем социальное состояние
    if social_state_manager and state_data.get('greeting_exchanged'):
        social_state_manager.mark_greeted(user_id)

    # Восстанавливаем память языка сессии
    if social_state_manager and state_data.get('language') in ('ru', 'uk', 'en'):
        social_state_manager.set_language(user_id, state_data['language'])
    
    logger.info(f"Восстановлено состояние для {user_id}: "
                f"{len(state_data.get('history', []))} сообщений, "
                f"signal={state_data.get('user_signal')}")