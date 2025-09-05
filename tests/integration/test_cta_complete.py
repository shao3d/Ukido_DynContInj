#!/usr/bin/env python3
"""
Полный тест SimpleCTABlocker
Проверяет все аспекты блокировки CTA
"""

import httpx
import asyncio
import time
import json

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

API_URL = "http://localhost:8000/chat"

def check_cta(response_text: str) -> tuple[bool, str]:
    """Проверяет наличие CTA и возвращает его тип"""
    text_lower = response_text.lower()
    
    cta_markers = {
        'discount': ['скидк', 'рассрочк', 'оплат', 'стоимост', 'дешевле', 'инвестици'],
        'trial': ['пробное', 'бесплатн', 'попробовать', 'ukido.ua'],
        'soft': ['если интересно', 'можем провести', 'обращайтесь', 'рады помочь']
    }
    
    for cta_type, markers in cta_markers.items():
        for marker in markers:
            if marker in text_lower:
                return True, cta_type
    
    return False, None


async def test_payment_blocking():
    """Тест 1: Блокировка после оплаты"""
    print(f"\n{BLUE}═══ ТЕСТ 1: Блокировка после оплаты ═══{RESET}")
    
    user_id = f"test_payment_{int(time.time())}"
    passed = True
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Сообщение 1: Вопрос о стеснительности (anxiety_about_child)
        print(f"\n{YELLOW}1. Стеснительный ребёнок (должен быть CTA про пробное):{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id, 
            "message": "Здравствуйте! У меня дочь 11 лет, очень стеснительная. Подойдут ли ваши курсы?"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {GREEN if has_cta else RED}{has_cta} ({cta_type}){RESET}")
        print(f"   Фрагмент: {result['response'][:100]}...")
        
        # Сообщение 2: Вопрос о цене (price_sensitive)
        print(f"\n{YELLOW}2. Вопрос о цене (должен быть CTA про скидки):{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "А сколько это стоит? Не слишком ли дорого?"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {GREEN if has_cta else RED}{has_cta} ({cta_type}){RESET}")
        print(f"   Signal: {result.get('user_signal', 'unknown')}")
        
        # Сообщение 3: ОПЛАТА
        print(f"\n{YELLOW}3. Сообщение об оплате:{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "Хорошо, я только что оплатила курс через ваш сайт. Что дальше?"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {RED if has_cta else GREEN}{has_cta} ({cta_type}){RESET}")
        if has_cta:
            print(f"   {RED}❌ ОШИБКА: CTA не должен быть после оплаты!{RESET}")
            passed = False
        
        # Сообщение 4: Обычный вопрос после оплаты
        print(f"\n{YELLOW}4. Вопрос после оплаты (НЕ должно быть CTA):{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "Какие материалы нужны для занятий?"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {RED if has_cta else GREEN}{has_cta} ({cta_type}){RESET}")
        if has_cta:
            print(f"   {RED}❌ ОШИБКА: CTA всё ещё показывается после оплаты!{RESET}")
            passed = False
        
        # Сообщение 5: Вопрос про второго ребёнка (price_sensitive контекст)
        print(f"\n{YELLOW}5. Вопрос про второго ребёнка (НЕ должно быть CTA про оплату):{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "У вас есть курсы для младшего ребёнка 7 лет? Может быть скидка для второго?"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {RED if has_cta and cta_type == 'discount' else GREEN}{has_cta} ({cta_type}){RESET}")
        if has_cta and cta_type == 'discount':
            print(f"   {RED}❌ ОШИБКА: CTA про скидки после оплаты!{RESET}")
            passed = False
    
    print(f"\n{BLUE}Результат теста 1: {GREEN if passed else RED}{'ПРОЙДЕН' if passed else 'ПРОВАЛЕН'}{RESET}")
    return passed


async def test_hard_refusal_blocking():
    """Тест 2: Блокировка после жёсткого отказа"""
    print(f"\n{BLUE}═══ ТЕСТ 2: Блокировка после жёсткого отказа ═══{RESET}")
    
    user_id = f"test_refusal_{int(time.time())}"
    passed = True
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Сообщение 1: Обычный вопрос
        print(f"\n{YELLOW}1. Обычный вопрос (должен быть CTA):{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "Добрый день! Расскажите о вашей школе"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {GREEN if has_cta else YELLOW}{has_cta} ({cta_type}){RESET}")
        
        # Сообщение 2: ЖЁСТКИЙ ОТКАЗ
        print(f"\n{YELLOW}2. Жёсткий отказ:{RESET}")
        resp = await client.post(API_URL, json={
            "user_id": user_id,
            "message": "Не надо мне ничего предлагать! Я просто смотрю"
        })
        result = resp.json()
        has_cta, cta_type = check_cta(result["response"])
        print(f"   CTA: {RED if has_cta else GREEN}{has_cta} ({cta_type}){RESET}")
        
        # Следующие 5 сообщений - проверяем блокировку
        for i in range(3, 8):
            questions = [
                "Какая у вас методика обучения?",
                "Сколько детей в группе?",
                "Какие навыки развиваете?",
                "Есть ли домашние задания?",
                "Как проходят занятия онлайн?"
            ]
            print(f"\n{YELLOW}{i}. Вопрос после отказа (НЕ должно быть CTA, {i-2}/7):{RESET}")
            resp = await client.post(API_URL, json={
                "user_id": user_id,
                "message": questions[i-3]
            })
            result = resp.json()
            has_cta, cta_type = check_cta(result["response"])
            print(f"   CTA: {RED if has_cta else GREEN}{has_cta} ({cta_type}){RESET}")
            if has_cta:
                print(f"   {RED}❌ ОШИБКА: CTA показан несмотря на отказ!{RESET}")
                passed = False
    
    print(f"\n{BLUE}Результат теста 2: {GREEN if passed else RED}{'ПРОЙДЕН' if passed else 'ПРОВАЛЕН'}{RESET}")
    return passed


async def test_cta_variety():
    """Тест 3: Вариативность CTA"""
    print(f"\n{BLUE}═══ ТЕСТ 3: Вариативность CTA ═══{RESET}")
    
    user_id = f"test_variety_{int(time.time())}"
    cta_texts = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        price_messages = [
            "Это дорого для нас",
            "Дороговато получается",
            "Надо подумать о бюджете",
            "Сложно сразу такую сумму",
            "Не потяну финансово"
        ]
        
        for i, msg in enumerate(price_messages):
            print(f"\n{YELLOW}Запрос {i+1}/5: {msg}{RESET}")
            resp = await client.post(API_URL, json={
                "user_id": user_id,
                "message": msg
            })
            result = resp.json()
            response_text = result["response"]
            has_cta, cta_type = check_cta(response_text)
            
            if has_cta:
                # Извлекаем CTA фрагмент
                for line in response_text.split('.'):
                    if any(word in line.lower() for word in ['скидк', 'рассрочк', 'инвестиц', 'дешевле']):
                        cta_texts.append(line.strip())
                        print(f"   CTA найден: {line[:60]}...")
                        break
            
            # Небольшая пауза
            await asyncio.sleep(0.5)
    
    # Анализ вариативности
    unique_cta = len(set(cta_texts))
    total_cta = len(cta_texts)
    
    print(f"\n{YELLOW}Результаты:{RESET}")
    print(f"   Всего CTA: {total_cta}")
    print(f"   Уникальных: {unique_cta}")
    
    passed = unique_cta >= 3
    print(f"\n{BLUE}Результат теста 3: {GREEN if passed else RED}{'ПРОЙДЕН (хорошая вариативность)' if passed else 'ПРОВАЛЕН (мало вариативности)'}{RESET}")
    return passed


async def main():
    """Запуск всех тестов"""
    print(f"{GREEN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║       ПОЛНОЕ ТЕСТИРОВАНИЕ SimpleCTABlocker v2.0             ║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    
    results = {
        "payment_blocking": False,
        "refusal_blocking": False,
        "cta_variety": False
    }
    
    # Запускаем тесты
    results["payment_blocking"] = await test_payment_blocking()
    await asyncio.sleep(1)
    
    results["refusal_blocking"] = await test_hard_refusal_blocking()
    await asyncio.sleep(1)
    
    results["cta_variety"] = await test_cta_variety()
    
    # Итоговый отчёт
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║                     ИТОГОВЫЙ ОТЧЁТ                          ║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\n📊 Результаты:")
    print(f"   • Блокировка после оплаты: {GREEN if results['payment_blocking'] else RED}{'✅ ПРОЙДЕН' if results['payment_blocking'] else '❌ ПРОВАЛЕН'}{RESET}")
    print(f"   • Блокировка после отказа: {GREEN if results['refusal_blocking'] else RED}{'✅ ПРОЙДЕН' if results['refusal_blocking'] else '❌ ПРОВАЛЕН'}{RESET}")
    print(f"   • Вариативность CTA: {GREEN if results['cta_variety'] else RED}{'✅ ПРОЙДЕН' if results['cta_variety'] else '❌ ПРОВАЛЕН'}{RESET}")
    
    print(f"\n📈 Общий результат: {total_passed}/{total_tests} тестов пройдено")
    
    if total_passed == total_tests:
        print(f"\n{GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! SimpleCTABlocker работает корректно!{RESET}")
    else:
        print(f"\n{RED}⚠️ Есть проблемы. Требуется доработка.{RESET}")


if __name__ == "__main__":
    print("Убедитесь, что сервер запущен на http://localhost:8000")
    asyncio.run(main())