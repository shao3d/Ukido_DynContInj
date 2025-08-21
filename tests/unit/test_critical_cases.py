#!/usr/bin/env python3
import asyncio
import httpx

async def test_critical_cases():
    """Тестирует критические случаи после оптимизации"""
    url = "http://localhost:8000/chat"
    
    test_cases = [
        {
            "name": "Price sensitive",
            "message": "30 тысяч?! Это развод какой-то!",
            "expected_signal": "price_sensitive"
        },
        {
            "name": "Anxiety about child",
            "message": "Мой ребенок очень стеснительный, его травят в школе",
            "expected_signal": "anxiety_about_child"
        },
        {
            "name": "Exploring only",
            "message": "Просто интересуюсь, расскажите о вашей школе",
            "expected_signal": "exploring_only"
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for test in test_cases:
            print(f"\n{test['name']}: '{test['message']}'")
            
            response = await client.post(url, json={
                "message": test["message"],
                "user_id": f"test_{test['name']}"
            })
            result = response.json()
            
            actual_signal = result.get('user_signal')
            if actual_signal == test['expected_signal']:
                print(f"✅ Signal правильный: {actual_signal}")
            else:
                print(f"❌ Signal неверный: {actual_signal} (ожидался {test['expected_signal']})")

if __name__ == "__main__":
    asyncio.run(test_critical_cases())
