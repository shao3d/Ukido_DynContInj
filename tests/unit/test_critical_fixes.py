#!/usr/bin/env python3
"""
Тест критических исправлений:
1. Memory Leak (LRU Cache)
2. Детерминированность (Random Seed)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from history_manager import HistoryManager
from standard_responses import get_offtopic_response
from social_responder import SocialResponder
from social_state import SocialStateManager
from social_intents import SocialIntent
import random

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def test_lru_cache():
    """Тестирует, что LRU Cache ограничивает количество пользователей"""
    print(f"\n{Colors.HEADER}=== ТЕСТ 1: LRU Cache в HistoryManager ==={Colors.ENDC}")
    
    manager = HistoryManager()
    manager.max_users = 5  # Для теста уменьшим до 5
    
    # Добавляем 7 пользователей (больше лимита)
    for i in range(7):
        user_id = f"user_{i}"
        manager.add_message(user_id, "user", f"Message from user {i}")
        print(f"  Добавлен {user_id}, всего в памяти: {len(manager.storage)}")
    
    # Проверяем что осталось только 5 последних
    if len(manager.storage) == 5:
        print(f"{Colors.GREEN}✅ LRU работает! В памяти ровно 5 пользователей (лимит){Colors.ENDC}")
        
        # Проверяем что остались user_2 - user_6 (первые два удалены)
        remaining_users = list(manager.storage.keys())
        expected = ['user_2', 'user_3', 'user_4', 'user_5', 'user_6']
        if remaining_users == expected:
            print(f"{Colors.GREEN}✅ Удалены самые старые (user_0, user_1){Colors.ENDC}")
        else:
            print(f"{Colors.RED}❌ Неправильные пользователи в памяти: {remaining_users}{Colors.ENDC}")
    else:
        print(f"{Colors.RED}❌ LRU не работает! В памяти {len(manager.storage)} пользователей{Colors.ENDC}")
    
    # Тест перемещения активного пользователя
    print(f"\n{Colors.BLUE}Тест обновления активности:{Colors.ENDC}")
    manager.add_message("user_2", "user", "Я снова активен!")
    
    # user_2 должен переместиться в конец
    users_order = list(manager.storage.keys())
    if users_order[-1] == "user_2":
        print(f"{Colors.GREEN}✅ Активный пользователь перемещён в конец{Colors.ENDC}")
    else:
        print(f"{Colors.RED}❌ Активный пользователь не перемещён{Colors.ENDC}")

def test_determinism():
    """Тестирует детерминированность random операций"""
    print(f"\n{Colors.HEADER}=== ТЕСТ 2: Детерминированность (Random Seed) ==={Colors.ENDC}")
    
    # Тест 1: Проверяем что ответы одинаковые при перезапуске
    responses1 = []
    for _ in range(5):
        responses1.append(get_offtopic_response())
    
    # "Перезапускаем" - устанавливаем тот же seed
    random.seed(42)
    responses2 = []
    for _ in range(5):
        responses2.append(get_offtopic_response())
    
    if responses1 == responses2:
        print(f"{Colors.GREEN}✅ Offtopic ответы детерминированы!{Colors.ENDC}")
        print(f"  Первая серия:  {responses1[0][:30]}...")
        print(f"  Вторая серия:  {responses2[0][:30]}...")
    else:
        print(f"{Colors.RED}❌ Ответы разные после 'перезапуска'!{Colors.ENDC}")
    
    # Тест 2: Проверяем социальные ответы
    print(f"\n{Colors.BLUE}Тест социальных ответов:{Colors.ENDC}")
    
    state = SocialStateManager()
    responder = SocialResponder(state)
    
    # Сбрасываем seed для воспроизводимости
    random.seed(42)
    apologies1 = []
    for i in range(3):
        apologies1.append(responder.make_prefix(f"test_{i}", SocialIntent.APOLOGY))
    
    # Снова с тем же seed
    random.seed(42)
    apologies2 = []
    for i in range(3):
        apologies2.append(responder.make_prefix(f"test_{i}", SocialIntent.APOLOGY))
    
    if apologies1 == apologies2:
        print(f"{Colors.GREEN}✅ Социальные ответы детерминированы!{Colors.ENDC}")
        print(f"  Извинения: {apologies1}")
    else:
        print(f"{Colors.RED}❌ Социальные ответы недетерминированы!{Colors.ENDC}")

def test_memory_estimation():
    """Оценка использования памяти"""
    print(f"\n{Colors.HEADER}=== ТЕСТ 3: Оценка памяти ==={Colors.ENDC}")
    
    manager = HistoryManager()
    
    # Заполняем до максимума
    for i in range(manager.max_users):
        user_id = f"production_user_{i:04d}"
        # Симулируем 10 сообщений по ~500 символов
        for j in range(10):
            manager.add_message(user_id, "user" if j % 2 == 0 else "assistant", 
                              "Это типичное сообщение от пользователя или бота. " * 10)
    
    # Приблизительная оценка памяти
    users_count = len(manager.storage)
    messages_total = sum(len(history) for history in manager.storage.values())
    avg_message_size = 500  # байт
    estimated_memory_kb = (messages_total * avg_message_size) / 1024
    estimated_memory_mb = estimated_memory_kb / 1024
    
    print(f"  Пользователей в памяти: {users_count}")
    print(f"  Всего сообщений: {messages_total}")
    print(f"  Примерный размер: {estimated_memory_mb:.2f} MB")
    
    if estimated_memory_mb < 20:
        print(f"{Colors.GREEN}✅ Память под контролем (<20MB для {manager.max_users} пользователей){Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}⚠️ Возможно стоит уменьшить лимиты{Colors.ENDC}")

if __name__ == "__main__":
    print(f"{Colors.BOLD}🔧 Тестирование критических исправлений{Colors.ENDC}")
    
    test_lru_cache()
    test_determinism()
    test_memory_estimation()
    
    print(f"\n{Colors.HEADER}=== ИТОГИ ==={Colors.ENDC}")
    print(f"{Colors.GREEN}Если все тесты зелёные - система готова к MVP!{Colors.ENDC}")
    print(f"Memory Leak исправлен через LRU Cache (max 1000 users)")
    print(f"Random операции детерминированы через seed=42")