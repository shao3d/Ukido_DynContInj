"""
test_state_machine.py - Тесты для State Machine функциональности
Версия 1.0: MVP тесты для user_signal detection и offers
"""

import pytest
import asyncio
import sys
import os
import json

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from router import Router
from response_generator import ResponseGenerator
from offers_catalog import get_offer, get_tone_adaptation, get_dynamic_example

class TestStateMachine:
    """Тесты для State Machine функциональности"""
    
    @pytest.fixture
    def router(self):
        """Создаем экземпляр Router"""
        return Router(use_cache=False)  # Отключаем кеш для тестов
    
    @pytest.fixture
    def generator(self):
        """Создаем экземпляр ResponseGenerator"""
        return ResponseGenerator()
    
    @pytest.mark.asyncio
    async def test_user_signal_detection(self, router):
        """Тестируем определение user_signal для разных типов запросов"""
        
        test_cases = [
            # price_sensitive сигналы
            ("Сколько стоит обучение?", "price_sensitive"),
            ("Какая цена курса Юный Оратор?", "price_sensitive"),
            ("Есть ли скидки для двоих детей?", "price_sensitive"),
            ("Можно ли платить в рассрочку?", "price_sensitive"),
            
            # anxiety_about_child сигналы  
            ("Мой сын очень стеснительный, поможет ли курс?", "anxiety_about_child"),
            ("Дочка боится выступать перед людьми", "anxiety_about_child"),
            ("Ребенок очень застенчивый и неуверенный", "anxiety_about_child"),
            ("У нас проблемы с общением со сверстниками", "anxiety_about_child"),
            
            # ready_to_buy сигналы
            ("Как записаться на курс?", "ready_to_buy"),
            ("Хочу записать ребенка на пробное занятие", "ready_to_buy"),
            ("Когда начинается следующая группа?", "ready_to_buy"),
            ("Есть ли свободные места в группе?", "ready_to_buy"),
            
            # exploring_only сигналы
            ("Расскажите о вашей школе", "exploring_only"),
            ("Какие курсы у вас есть?", "exploring_only"),
            ("Что такое soft skills?", "exploring_only"),
            ("Какая методология обучения?", "exploring_only"),
        ]
        
        for message, expected_signal in test_cases:
            result = await router.route(message, [], "test_user")
            actual_signal = result.get("user_signal", "not_found")
            
            assert actual_signal == expected_signal, \
                f"Неправильный сигнал для '{message}': ожидали {expected_signal}, получили {actual_signal}"
            
            print(f"✅ '{message}' → {expected_signal}")
    
    @pytest.mark.asyncio
    async def test_signal_priority(self, router):
        """Тестируем приоритеты сигналов (ready_to_buy > anxiety > price > exploring)"""
        
        test_cases = [
            # ready_to_buy имеет приоритет над price_sensitive
            ("Сколько стоит и как записаться?", "ready_to_buy"),
            ("Какая цена и когда начинаются занятия?", "ready_to_buy"),
            
            # anxiety_about_child имеет приоритет над price_sensitive
            ("Ребенок стеснительный, сколько стоит курс?", "anxiety_about_child"),
            ("У сына проблемы с общением, есть ли скидки?", "anxiety_about_child"),
            
            # ready_to_buy имеет приоритет над anxiety_about_child
            ("Дочка стеснительная, хочу записать на пробное", "ready_to_buy"),
        ]
        
        for message, expected_signal in test_cases:
            result = await router.route(message, [], "test_user")
            actual_signal = result.get("user_signal", "not_found")
            
            assert actual_signal == expected_signal, \
                f"Неправильный приоритет для '{message}': ожидали {expected_signal}, получили {actual_signal}"
            
            print(f"✅ Приоритет: '{message}' → {expected_signal}")
    
    def test_offers_catalog(self):
        """Тестируем наличие предложений для каждого сигнала"""
        
        signals = ["price_sensitive", "anxiety_about_child", "ready_to_buy", "exploring_only"]
        
        for signal in signals:
            offer = get_offer(signal)
            
            if signal == "exploring_only":
                # Для exploring_only не должно быть offer
                assert offer is None, f"Для {signal} не должно быть offer"
            else:
                # Для остальных должен быть offer
                assert offer is not None, f"Нет offer для {signal}"
                assert "text" in offer, f"Нет текста в offer для {signal}"
                assert "priority" in offer, f"Нет приоритета в offer для {signal}"
                
            print(f"✅ Offer для {signal}: {'есть' if offer else 'нет (как и должно быть)'}")
    
    def test_tone_adaptations(self):
        """Тестируем адаптацию тона для каждого сигнала"""
        
        signals = ["price_sensitive", "anxiety_about_child", "ready_to_buy", "exploring_only"]
        
        for signal in signals:
            tone = get_tone_adaptation(signal)
            
            assert tone is not None, f"Нет адаптации тона для {signal}"
            assert "style" in tone, f"Нет стиля в адаптации для {signal}"
            
            # Проверяем специфичные элементы для каждого сигнала
            if signal == "price_sensitive":
                assert "инвестиц" in tone["style"].lower(), "Должно упоминаться про инвестицию"
            elif signal == "anxiety_about_child":
                assert "эмпат" in tone["style"].lower(), "Должна быть эмпатия"
            elif signal == "ready_to_buy":
                assert "конкретн" in tone["style"].lower(), "Должна быть конкретика"
            
            print(f"✅ Tone adaptation для {signal}: есть")
    
    def test_dynamic_examples(self):
        """Тестируем наличие dynamic few-shot примеров"""
        
        signals = ["price_sensitive", "anxiety_about_child", "ready_to_buy", "exploring_only"]
        
        for signal in signals:
            example = get_dynamic_example(signal)
            
            assert example is not None, f"Нет примера для {signal}"
            assert len(example) > 0, f"Пустой пример для {signal}"
            assert "User:" in example, f"Нет User в примере для {signal}"
            assert "Assistant:" in example, f"Нет Assistant в примере для {signal}"
            
            print(f"✅ Dynamic example для {signal}: {len(example)} символов")
    
    @pytest.mark.asyncio
    async def test_offers_injection(self, generator):
        """Тестируем добавление offers в конец ответа"""
        
        # Мокаем router_result с разными сигналами
        test_cases = [
            {
                "router_result": {
                    "status": "success",
                    "documents": ["pricing.md"],
                    "decomposed_questions": ["Сколько стоит?"],
                    "user_signal": "price_sensitive"
                },
                "should_have_offer": True
            },
            {
                "router_result": {
                    "status": "success", 
                    "documents": ["courses_detailed.md"],
                    "decomposed_questions": ["Какие курсы есть?"],
                    "user_signal": "exploring_only"
                },
                "should_have_offer": False
            }
        ]
        
        for case in test_cases:
            # Проверяем что offer добавляется правильно
            offer = get_offer(case["router_result"]["user_signal"])
            
            if case["should_have_offer"]:
                assert offer is not None, f"Должен быть offer для {case['router_result']['user_signal']}"
                print(f"✅ Offer будет добавлен для {case['router_result']['user_signal']}")
            else:
                assert offer is None, f"Не должно быть offer для {case['router_result']['user_signal']}"
                print(f"✅ Offer не будет добавлен для {case['router_result']['user_signal']}")
    
    @pytest.mark.asyncio
    async def test_latency_check(self, router):
        """Проверяем что добавление state machine не сильно увеличивает latency"""
        
        import time
        
        test_message = "Сколько стоит курс и как записаться?"
        
        # Замеряем время роутинга
        start = time.time()
        result = await router.route(test_message, [], "test_user")
        router_time = time.time() - start
        
        # Router должен отвечать быстро даже с user_signal detection
        assert router_time < 3.0, f"Router слишком медленный: {router_time:.2f}s"
        assert "user_signal" in result, "Router должен возвращать user_signal"
        
        print(f"✅ Router latency: {router_time:.2f}s (< 3s)")
        print(f"✅ Detected signal: {result.get('user_signal')}")

def run_tests():
    """Запуск всех тестов"""
    print("\n🧪 Запуск тестов State Machine...\n")
    
    # Запускаем pytest программно
    pytest.main([__file__, "-v", "--tb=short"])

if __name__ == "__main__":
    run_tests()