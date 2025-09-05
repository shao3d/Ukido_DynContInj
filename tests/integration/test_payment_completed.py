import requests
import json

base_url = "http://localhost:8000"
user_id = "test_payment"

# Очистка истории
requests.post(f"{base_url}/clear_history/{user_id}")
print("=" * 60)
print("📝 Тест: Распознавание завершённых действий")
print("=" * 60)

# Тестируем завершённые действия
test_messages = [
    "Оплатила перевод. Жду подтверждения",
    "Заполнил форму на сайте. Что дальше?",
    "Записались на пробное. Как подготовиться?"
]

for msg in test_messages:
    print(f"\nUSER: {msg}")
    
    response = requests.post(
        f"{base_url}/chat",
        json={"message": msg, "user_id": user_id}
    )
    
    if response.status_code == 200:
        data = response.json()
        bot_response = data.get("response", "")
        intent = data.get("intent", "unknown")
        signal = data.get("user_signal", "unknown")
        
        # Сокращаем для читаемости
        if len(bot_response) > 200:
            bot_response = bot_response[:200] + "..."
        
        print(f"BOT: {bot_response}")
        print(f"Intent: {intent} | Signal: {signal}")
        
        # Проверяем, распознано ли завершённое действие
        if "Как оплатить" in bot_response or "способы оплаты" in bot_response:
            print("❌ Система объясняет КАК платить вместо подтверждения")
        elif intent == "offtopic":
            print("❌ Определено как offtopic вместо success")
        else:
            print("✅ Корректно обработано завершённое действие")

print("\n" + "=" * 60)
