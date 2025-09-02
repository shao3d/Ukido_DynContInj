import requests
import json
import time

# Телеграфный стиль - короткие сообщения < 5 слов
messages = [
    "Запишите на курс.",
    "Когда старт?",
    "Цена?",
    "Оплачу. Реквизиты?",
    "Документы какие?",
    "Пробное есть?"
]

base_url = "http://localhost:8000"
user_id = "test_quick_buyer"

# Очистка истории
requests.post(f"{base_url}/clear_history/{user_id}")
print("=" * 60)
print("📝 Тест: Быстрый покупатель (телеграфный стиль)")
print("📋 Короткие сообщения < 5 слов должны триггерить ready_to_buy")
print("=" * 60)

for i, msg in enumerate(messages, 1):
    print(f"\n[{i}/{len(messages)}] USER: {msg}")
    
    response = requests.post(
        f"{base_url}/chat",
        json={"message": msg, "user_id": user_id}
    )
    
    if response.status_code == 200:
        data = response.json()
        bot_response = data.get("response", "")
        intent = data.get("intent", "unknown")
        signal = data.get("user_signal", "unknown")
        
        # Сокращаем ответ для читаемости
        if len(bot_response) > 150:
            bot_response = bot_response[:150] + "..."
        
        print(f"BOT: {bot_response}")
        print(f"Signal: {signal} | Intent: {intent}")
        
        # Проверяем наличие implicit questions для ready_to_buy
        if signal == "ready_to_buy" and "?" in bot_response:
            print("✅ Implicit question сгенерирован")
    
    time.sleep(1)

print("\n" + "=" * 60)
print("✅ Тест завершён")
