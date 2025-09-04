#!/usr/bin/env python3
"""
test_cta_blocker.py - Тестирование SimpleCTABlocker
Проверяет блокировку CTA после оплаты и отказов
"""

import asyncio
import json
import httpx
import time
from typing import Dict, List

# Конфигурация
API_URL = "http://localhost:8000/chat"
HEADERS = {"Content-Type": "application/json"}

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


async def send_message(user_id: str, message: str) -> Dict:
    """Отправка сообщения в API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                API_URL,
                headers=HEADERS,
                json={"user_id": user_id, "message": message}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"{RED}❌ Ошибка отправки: {e}{RESET}")
            return None


def check_for_cta(response_text: str) -> bool:
    """Проверка наличия CTA в ответе"""
    cta_markers = [
        "скидк",
        "рассрочка",
        "ukido.ua",
        "запис",
        "пробное занятие",
        "бесплатн",
        "консультаци",
        "оплат",
        "стоимост"
    ]
    
    text_lower = response_text.lower()
    for marker in cta_markers:
        if marker in text_lower:
            return True
    return False


async def test_payment_blocking():
    """Тест 1: Блокировка CTA после оплаты"""
    print(f"\n{BLUE}═══ ТЕСТ 1: Блокировка после оплаты ══════════════════════════{RESET}")
    
    test_user_id = f"test_payment_{int(time.time())}"
    
    # Шаг 1: Обычный вопрос (должен быть CTA)
    print(f"\n{YELLOW}→ Шаг 1: Спрашиваем про цены{RESET}")
    response = await send_message(test_user_id, "Сколько стоит обучение? Дорого ли у вас?")
    
    if response:
        has_cta = check_for_cta(response["response"])
        print(f"Ответ (фрагмент): {response['response'][:200]}...")
        print(f"CTA обнаружен: {GREEN if has_cta else RED}{has_cta}{RESET}")
        
        if has_cta:
            print(f"{GREEN}✓ Шаг 1 пройден: CTA показан для price_sensitive{RESET}")
        else:
            print(f"{RED}✗ Шаг 1 провален: CTA должен был быть показан{RESET}")
    
    # Шаг 2: Сообщаем об оплате
    print(f"\n{YELLOW}→ Шаг 2: Сообщаем об оплате{RESET}")
    response = await send_message(test_user_id, "Я только что оплатил курс через сайт")
    
    if response:
        print(f"Ответ (фрагмент): {response['response'][:200]}...")
        print(f"{GREEN}✓ SimpleCTABlocker должен был зафиксировать оплату{RESET}")
    
    # Шаг 3: Снова спрашиваем про цены (НЕ должно быть CTA)
    print(f"\n{YELLOW}→ Шаг 3: Снова спрашиваем про курсы{RESET}")
    response = await send_message(test_user_id, "Какие у вас есть курсы для детей 10 лет?")
    
    if response:
        has_cta = check_for_cta(response["response"])
        print(f"Ответ (фрагмент): {response['response'][:200]}...")
        print(f"CTA обнаружен: {RED if has_cta else GREEN}{has_cta}{RESET}")
        
        if not has_cta:
            print(f"{GREEN}✓ Шаг 3 пройден: CTA заблокирован после оплаты{RESET}")
        else:
            print(f"{RED}✗ Шаг 3 провален: CTA должен быть заблокирован{RESET}")
    
    # Итог теста 1
    print(f"\n{BLUE}════════════════════════════════════════════════════════════════{RESET}")


async def test_refusal_blocking():
    """Тест 2: Блокировка CTA после отказа"""
    print(f"\n{BLUE}═══ ТЕСТ 2: Блокировка после отказа ═══════════════════════════{RESET}")
    
    test_user_id = f"test_refusal_{int(time.time())}"
    
    # Шаг 1: Обычный вопрос (должен быть CTA)
    print(f"\n{YELLOW}→ Шаг 1: Спрашиваем про методику{RESET}")
    response = await send_message(test_user_id, "Как вы учите детей? Какая методика?")
    
    if response:
        has_cta = check_for_cta(response["response"])
        print(f"Ответ (фрагмент): {response['response'][:200]}...")
        print(f"CTA обнаружен: {GREEN if has_cta else RED}{has_cta}{RESET}")
    
    # Шаг 2: Жёсткий отказ
    print(f"\n{YELLOW}→ Шаг 2: Жёсткий отказ{RESET}")
    response = await send_message(test_user_id, "Не надо мне ничего предлагать, отстаньте с вашими курсами")
    
    if response:
        print(f"Ответ (фрагмент): {response['response'][:200]}...")
        print(f"{GREEN}✓ SimpleCTABlocker должен был зафиксировать отказ{RESET}")
    
    # Шаг 3-5: Следующие сообщения (НЕ должно быть CTA)
    for i in range(3, 6):
        print(f"\n{YELLOW}→ Шаг {i}: Проверка блокировки (сообщение {i-2}/3){RESET}")
        questions = [
            "Расскажите про преподавателей",
            "Какое расписание занятий?",
            "Сколько детей в группе?"
        ]
        response = await send_message(test_user_id, questions[i-3])
        
        if response:
            has_cta = check_for_cta(response["response"])
            print(f"Ответ (фрагмент): {response['response'][:200]}...")
            print(f"CTA обнаружен: {RED if has_cta else GREEN}{has_cta}{RESET}")
            
            if not has_cta:
                print(f"{GREEN}✓ CTA заблокирован после отказа{RESET}")
            else:
                print(f"{RED}✗ CTA должен быть заблокирован{RESET}")
    
    # Итог теста 2
    print(f"\n{BLUE}════════════════════════════════════════════════════════════════{RESET}")


async def test_cta_variety():
    """Тест 3: Вариативность CTA"""
    print(f"\n{BLUE}═══ ТЕСТ 3: Вариативность CTA ══════════════════════════════════{RESET}")
    
    test_user_id = f"test_variety_{int(time.time())}"
    cta_texts = []
    
    # Отправляем 5 сообщений и собираем CTA
    for i in range(5):
        print(f"\n{YELLOW}→ Запрос {i+1}/5{RESET}")
        
        # Чередуем вопросы чтобы вызвать price_sensitive
        if i % 2 == 0:
            message = "Это дорого для меня, есть ли скидки?"
        else:
            message = "Дороговато получается, что можете предложить?"
        
        response = await send_message(test_user_id, message)
        
        if response:
            # Извлекаем CTA из ответа
            text = response["response"]
            if check_for_cta(text):
                # Пытаемся найти конкретный CTA текст
                cta_start_markers = ["Кстати,", "Доступна", "Напоминаем", "У нас", "Это инвестиция", "Стоимость", "Многие родители"]
                for marker in cta_start_markers:
                    if marker in text:
                        # Извлекаем CTA (обычно это последний абзац или предложение)
                        idx = text.find(marker)
                        cta_part = text[idx:idx+150]  # Берём фрагмент
                        cta_texts.append(cta_part)
                        print(f"CTA: {cta_part}...")
                        break
            
            # Небольшая задержка между запросами
            await asyncio.sleep(0.5)
    
    # Анализ вариативности
    unique_cta = len(set(cta_texts))
    total_cta = len(cta_texts)
    
    print(f"\n{YELLOW}Результаты вариативности:{RESET}")
    print(f"Всего CTA собрано: {total_cta}")
    print(f"Уникальных CTA: {unique_cta}")
    
    if unique_cta >= 3:
        print(f"{GREEN}✓ Тест пройден: хорошая вариативность ({unique_cta} разных CTA){RESET}")
    else:
        print(f"{RED}✗ Тест провален: низкая вариативность ({unique_cta} разных CTA){RESET}")
    
    print(f"\n{BLUE}════════════════════════════════════════════════════════════════{RESET}")


async def main():
    """Запуск всех тестов"""
    print(f"{GREEN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║           ТЕСТИРОВАНИЕ SimpleCTABlocker v1.0                ║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    
    print(f"\n{YELLOW}Убедитесь, что сервер запущен на http://localhost:8000{RESET}")
    print(f"{YELLOW}Команда: python src/main.py{RESET}\n")
    
    input("Нажмите Enter для начала тестов...")
    
    # Запускаем тесты последовательно
    await test_payment_blocking()
    await asyncio.sleep(1)
    
    await test_refusal_blocking()
    await asyncio.sleep(1)
    
    await test_cta_variety()
    
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║                    ТЕСТИРОВАНИЕ ЗАВЕРШЕНО                   ║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════╝{RESET}")


if __name__ == "__main__":
    asyncio.run(main())