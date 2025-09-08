#!/usr/bin/env python3
"""
Универсальная песочница для тестирования Ukido AI Assistant
Объединяет функциональность всех версий http_sandbox
"""

import httpx
import json
import sys
import os
import argparse
from typing import Dict, List, Optional
from datetime import datetime

# Добавляем путь к src для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

DEFAULT_API_URL = "http://localhost:8000/chat"
DEFAULT_USER_ID = "test_user"

# Загрузка тестовых диалогов
def load_test_dialogues():
    """Загружает тестовые диалоги из JSON файла"""
    dialogues_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dialogues_v2.json')
    if os.path.exists(dialogues_path):
        with open(dialogues_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def send_message(message: str, user_id: str = DEFAULT_USER_ID, api_url: str = DEFAULT_API_URL) -> Dict:
    """Отправляет сообщение на API и возвращает ответ"""
    payload = {
        "user_id": user_id,
        "message": message
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Timeout: сервер не ответил за 30 секунд"}
    except httpx.RequestError as e:
        return {"error": f"Ошибка соединения: {e}"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP ошибка {e.response.status_code}: {e.response.text}"}

def run_dialogue(dialogue_name: str, messages: List[str], user_id: Optional[str] = None):
    """Запускает диалог из списка сообщений"""
    if not user_id:
        user_id = f"{dialogue_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n{'='*80}")
    print(f"Диалог: {dialogue_name}")
    print(f"User ID: {user_id}")
    print(f"{'='*80}\n")
    
    for i, message in enumerate(messages, 1):
        print(f"[{i}] USER: {message}")
        response = send_message(message, user_id)
        
        if "error" in response:
            print(f"❌ ОШИБКА: {response['error']}")
        else:
            print(f"🤖 BOT: {response.get('response', 'Нет ответа')}")
            if response.get('intent'):
                print(f"   📊 Intent: {response['intent']}")
            if response.get('user_signal'):
                print(f"   🎯 Signal: {response['user_signal']}")
            if response.get('detected_language'):
                print(f"   🌐 Language: {response['detected_language']}")
        print()

def interactive_mode():
    """Интерактивный режим для ручного тестирования"""
    print("\n🤖 Ukido AI Assistant - Интерактивный режим")
    print("Введите 'exit' для выхода\n")
    
    user_id = f"interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    while True:
        try:
            message = input("YOU: ").strip()
            if message.lower() in ['exit', 'quit', 'q']:
                print("До свидания!")
                break
            
            if not message:
                continue
                
            response = send_message(message, user_id)
            
            if "error" in response:
                print(f"❌ ОШИБКА: {response['error']}")
            else:
                print(f"BOT: {response.get('response', 'Нет ответа')}")
                
                # Показываем метаданные в компактном виде
                metadata = []
                if response.get('intent'):
                    metadata.append(f"intent={response['intent']}")
                if response.get('user_signal'):
                    metadata.append(f"signal={response['user_signal']}")
                if response.get('detected_language'):
                    metadata.append(f"lang={response['detected_language']}")
                
                if metadata:
                    print(f"     [{', '.join(metadata)}]")
            print()
            
        except KeyboardInterrupt:
            print("\n\nПрервано пользователем. До свидания!")
            break
        except Exception as e:
            print(f"Ошибка: {e}")

def main():
    parser = argparse.ArgumentParser(description='Тестирование Ukido AI Assistant')
    parser.add_argument('dialogue', nargs='?', help='Имя или номер диалога для запуска')
    parser.add_argument('-u', '--user-id', help='User ID для тестирования')
    parser.add_argument('-m', '--message', help='Одиночное сообщение для отправки')
    parser.add_argument('-i', '--interactive', action='store_true', help='Интерактивный режим')
    parser.add_argument('--list', action='store_true', help='Показать доступные диалоги')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='URL API endpoint')
    
    args = parser.parse_args()
    
    # Проверяем доступность сервера
    try:
        with httpx.Client(timeout=2.0) as client:
            client.get(args.api_url.replace('/chat', '/health'))
    except:
        print("⚠️  Сервер не отвечает. Запустите его командой: python src/main.py")
        return
    
    # Загружаем тестовые диалоги
    test_dialogues = load_test_dialogues()
    
    # Режим списка диалогов
    if args.list:
        print("\nДоступные тестовые диалоги:")
        for name, data in test_dialogues.items():
            desc = data.get('description', 'Без описания')
            print(f"  {name}: {desc}")
        return
    
    # Интерактивный режим
    if args.interactive:
        interactive_mode()
        return
    
    # Одиночное сообщение
    if args.message:
        user_id = args.user_id or f"single_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        response = send_message(args.message, user_id, args.api_url)
        
        if "error" in response:
            print(f"❌ ОШИБКА: {response['error']}")
        else:
            print(f"ОТВЕТ: {response.get('response', 'Нет ответа')}")
            print(f"\nМетаданные:")
            print(json.dumps({
                k: v for k, v in response.items() 
                if k != 'response'
            }, indent=2, ensure_ascii=False))
        return
    
    # Запуск диалога
    if args.dialogue:
        if args.dialogue in test_dialogues:
            dialogue_data = test_dialogues[args.dialogue]
            messages = dialogue_data.get('messages', [])
            run_dialogue(args.dialogue, messages, args.user_id)
        else:
            print(f"Диалог '{args.dialogue}' не найден")
            print("Используйте --list для просмотра доступных диалогов")
        return
    
    # По умолчанию - интерактивный режим
    interactive_mode()

if __name__ == "__main__":
    main()