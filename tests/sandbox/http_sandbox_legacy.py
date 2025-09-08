#!/usr/bin/env python3
"""
HTTP API Песочница для тестирования Ukido AI Assistant через реальный сервер
Версия: 1.0 (MVP)

Основные возможности:
- Работа с production сервером через HTTP API
- Полный функционал системы (включая юмор Жванецкого)
- Три режима работы: интерактивный, single message, batch testing
- Детальный анализ ответов для отладки

Использование:
    # Интерактивный режим
    python http_sandbox.py
    
    # Одно сообщение
    python http_sandbox.py -m "Сколько стоит курс?"
    
    # Batch тестирование
    python http_sandbox.py --test
"""

import asyncio
import httpx
import json
import sys
import time
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import argparse

# ====== ЦВЕТА ДЛЯ ВЫВОДА ======
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    PURPLE = '\033[95m'  # Для юмора

# ====== РЕЗУЛЬТАТ ОБРАБОТКИ ======
@dataclass
class ProcessingResult:
    """Результат обработки сообщения через HTTP API"""
    user_message: str
    response_text: str
    intent: str
    user_signal: Optional[str]
    social_context: Optional[str]
    documents: List[str]
    questions: List[str]
    total_time: float
    fuzzy_matched: bool = False
    confidence: float = 1.0
    # Дополнительные поля для анализа
    is_humor: bool = False
    raw_response: Dict[str, Any] = None

# ====== ОСНОВНОЙ КЛАСС ПЕСОЧНИЦЫ ======
class HTTPSandbox:
    """HTTP песочница для тестирования через API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_stats = {
            "total_requests": 0,
            "success_count": 0,
            "offtopic_count": 0,
            "humor_detected": 0,
            "avg_response_time": 0.0,
            "signals": {}
        }
        
    async def check_server_health(self) -> bool:
        """Проверяет доступность сервера"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=2.0)
                return response.status_code == 200
        except:
            return False
    
    async def process_message(
        self,
        message: str,
        user_id: str = "test_user",
        show_details: bool = True
    ) -> ProcessingResult:
        """Отправляет сообщение на сервер и обрабатывает ответ с retry логикой"""
        
        start_time = time.time()
        max_retries = 3
        timeout_seconds = 15.0  # Увеличиваем timeout до 15 секунд
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    # Показываем индикатор ожидания для длительных запросов
                    if attempt > 0:
                        print(f"{Colors.YELLOW}⏳ Повторная попытка {attempt + 1}/{max_retries}...{Colors.ENDC}")
                    
                    response = await client.post(
                        f"{self.base_url}/chat",
                        json={"user_id": user_id, "message": message},
                        timeout=timeout_seconds
                    )
                
                    if response.status_code != 200:
                        print(f"{Colors.RED}❌ Server error: {response.status_code}{Colors.ENDC}")
                        if response.status_code == 500 and attempt < max_retries - 1:
                            await asyncio.sleep(1)  # Пауза перед retry
                            continue
                        return None
                
                    # Безопасный парсинг JSON
                    try:
                        data = response.json()
                    except json.JSONDecodeError as e:
                        print(f"{Colors.YELLOW}⚠️ Некорректный JSON в ответе: {e}{Colors.ENDC}")
                        # Пытаемся вернуть хотя бы текст ответа
                        data = {
                            "response": response.text[:500] if response.text else "Пустой ответ от сервера",
                            "intent": "error",
                            "error": str(e)
                        }
                    
                    total_time = time.time() - start_time
                    
                    # Валидация обязательных полей
                    if not isinstance(data, dict):
                        print(f"{Colors.YELLOW}⚠️ Ответ не является JSON объектом{Colors.ENDC}")
                        data = {"response": str(data), "intent": "error"}
                    
                    # Проверка наличия текста ответа
                    response_text = data.get("response", "")
                    if not response_text:
                        response_text = data.get("message", "")  # Fallback на альтернативное поле
                        if not response_text:
                            response_text = "Не совсем понял вопрос. Расскажите, что вас интересует о школе Ukido?"
                    
                    # Детекция юмора по паттернам
                    is_humor = self._detect_humor(response_text)
                    
                    # Обновляем статистику сессии
                    self._update_stats(data, total_time, is_humor)
                    
                    # Создаём результат с безопасными значениями по умолчанию
                    result = ProcessingResult(
                        user_message=message,
                        response_text=response_text,
                        intent=data.get("intent", "unknown"),
                        user_signal=data.get("user_signal"),
                        social_context=data.get("social"),
                        documents=data.get("relevant_documents", data.get("documents", [])),
                        questions=data.get("decomposed_questions", data.get("questions", [])),
                        total_time=total_time,
                        fuzzy_matched=data.get("fuzzy_matched", False),
                        confidence=data.get("confidence", 1.0),
                        is_humor=is_humor,
                        raw_response=data
                    )
                    
                    if show_details:
                        self._show_processing_details(result)
                    
                    return result
                
            except httpx.ConnectError:
                if attempt == 0:
                    print(f"{Colors.RED}❌ Не удалось подключиться к серверу{Colors.ENDC}")
                    print(f"{Colors.YELLOW}💡 Запустите сервер командой:{Colors.ENDC}")
                    print(f"   python src/main.py")
                return None
                
            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    print(f"{Colors.YELLOW}⏱️ Timeout после {timeout_seconds}с, повторяем...{Colors.ENDC}")
                    await asyncio.sleep(0.5)
                    continue
                else:
                    print(f"{Colors.RED}❌ Timeout: запрос превысил {timeout_seconds} секунд после {max_retries} попыток{Colors.ENDC}")
                    return None
                    
            except Exception as e:
                print(f"{Colors.RED}❌ Ошибка: {type(e).__name__}: {str(e)}{Colors.ENDC}")
                if attempt < max_retries - 1 and "timeout" in str(e).lower():
                    await asyncio.sleep(0.5)
                    continue
                return None
        
        return None
    
    def _detect_humor(self, text: str) -> bool:
        """Определяет наличие юмора Жванецкого в тексте
        
        Юмор Жванецкого характеризуется специфическими конструкциями,
        а не просто упоминанием школы. Проверяем более точные паттерны.
        """
        # Более точные паттерны, характерные для юмора Жванецкого
        humor_patterns = [
            # Ироничные конструкции
            "а что вы хотели",
            "как в анекдоте", 
            "знаете что смешно",
            "забавная история",
            
            # Парадоксальные сравнения 
            "это как",
            "представьте себе",
            "вы не поверите",
            
            # Характерные обороты Жванецкого
            "мы тут такие",
            "у нас тут такая",
            "знаете, у нас",
            
            # Явные маркеры юмора
            "шутка", "смешно", "забавно",
            "прикол", "анекдот"
        ]
        
        text_lower = text.lower()
        
        # Также проверяем наличие явных маркеров того, что это НЕ юмор
        serious_markers = [
            "методика", "программа", "образование",
            "педагог", "психолог", "сертификат",
            "квалификация", "опыт работы", "магистр"
        ]
        
        # Если много серьёзных маркеров, это вряд ли юмор
        serious_count = sum(1 for marker in serious_markers if marker in text_lower)
        if serious_count >= 3:
            return False
            
        # Проверяем наличие юмористических паттернов
        return any(pattern.lower() in text_lower for pattern in humor_patterns)
    
    def _update_stats(self, response_data: dict, time_taken: float, is_humor: bool):
        """Обновляет статистику сессии"""
        self.session_stats["total_requests"] += 1
        
        intent = response_data.get("intent", "unknown")
        if intent == "success":
            self.session_stats["success_count"] += 1
        elif intent == "offtopic":
            self.session_stats["offtopic_count"] += 1
        
        if is_humor:
            self.session_stats["humor_detected"] += 1
        
        # Обновляем среднее время
        n = self.session_stats["total_requests"]
        prev_avg = self.session_stats["avg_response_time"]
        self.session_stats["avg_response_time"] = (prev_avg * (n-1) + time_taken) / n
        
        # Считаем сигналы
        signal = response_data.get("user_signal", "unknown")
        if signal not in self.session_stats["signals"]:
            self.session_stats["signals"][signal] = 0
        self.session_stats["signals"][signal] += 1
    
    def _show_processing_details(self, result: ProcessingResult):
        """Показывает детали обработки для анализа"""
        print(f"\n{Colors.DIM}{'='*60}{Colors.ENDC}")
        print(f"{Colors.CYAN}⏱️  Response time:{Colors.ENDC} {result.total_time:.2f}s")
        print(f"{Colors.CYAN}📊 Intent:{Colors.ENDC} {result.intent}")
        
        if result.user_signal:
            signal_icon = self._get_signal_icon(result.user_signal)
            print(f"{Colors.CYAN}🎯 Signal:{Colors.ENDC} {signal_icon} {result.user_signal}")
        
        if result.social_context:
            print(f"{Colors.CYAN}👋 Social:{Colors.ENDC} {result.social_context}")
        
        if result.documents:
            print(f"{Colors.CYAN}📚 Documents:{Colors.ENDC} {', '.join(result.documents)}")
        
        if result.questions:
            print(f"{Colors.CYAN}❓ Questions:{Colors.ENDC}")
            for q in result.questions:
                print(f"   • {q}")
        
        if result.fuzzy_matched:
            print(f"{Colors.YELLOW}🔍 Fuzzy matching used{Colors.ENDC}")
        
        if result.is_humor:
            print(f"{Colors.PURPLE}🎭 Юмор Жванецкого detected!{Colors.ENDC}")
    
    def _get_signal_icon(self, signal: str) -> str:
        """Возвращает иконку для user_signal"""
        icons = {
            "price_sensitive": "💰",
            "anxiety_about_child": "😟",
            "ready_to_buy": "✅",
            "exploring_only": "🔍"
        }
        return icons.get(signal, "❓")
    
    def show_result(self, result: ProcessingResult):
        """Показывает результат обработки"""
        if not result:
            return
        
        print(f"\n{Colors.BOLD}=== RESPONSE ==={Colors.ENDC}")
        
        # Подсвечиваем юмор фиолетовым
        if result.is_humor:
            print(f"{Colors.PURPLE}🎭 {result.response_text}{Colors.ENDC}")
        else:
            print(result.response_text)
        
        # Аналитический блок
        self._show_analysis(result)
    
    def _show_analysis(self, result: ProcessingResult):
        """Показывает аналитику для Claude"""
        print(f"\n{Colors.DIM}--- Analysis for Claude ---{Colors.ENDC}")
        
        # Проверки соответствия
        checks = []
        
        # Проверка user_signal
        if "скольк" in result.user_message.lower() or "цен" in result.user_message.lower():
            if result.user_signal == "price_sensitive":
                checks.append(f"{Colors.GREEN}✓ Correctly detected price sensitivity{Colors.ENDC}")
            else:
                checks.append(f"{Colors.YELLOW}⚠ Expected price_sensitive, got {result.user_signal}{Colors.ENDC}")
        
        # Проверка anxiety
        anxiety_words = ["боится", "стеснительный", "тревожный", "переживаю"]
        if any(word in result.user_message.lower() for word in anxiety_words):
            if result.user_signal == "anxiety_about_child":
                checks.append(f"{Colors.GREEN}✓ Correctly detected anxiety{Colors.ENDC}")
            else:
                checks.append(f"{Colors.YELLOW}⚠ Missed anxiety signal{Colors.ENDC}")
        
        # Проверка ready_to_buy
        if "запишите" in result.user_message.lower() or "готов" in result.user_message.lower():
            if result.user_signal == "ready_to_buy":
                checks.append(f"{Colors.GREEN}✓ Correctly detected purchase intent{Colors.ENDC}")
            else:
                checks.append(f"{Colors.YELLOW}⚠ Missed ready_to_buy signal{Colors.ENDC}")
        
        # Проверка социальных интентов
        if result.social_context:
            if result.social_context == "greeting" and ("привет" in result.user_message.lower() or "здравств" in result.user_message.lower()):
                checks.append(f"{Colors.GREEN}✓ Correctly detected greeting{Colors.ENDC}")
            elif result.social_context == "thanks" and "спасиб" in result.user_message.lower():
                checks.append(f"{Colors.GREEN}✓ Correctly detected thanks{Colors.ENDC}")
        
        # Выводим результаты проверок
        if checks:
            for check in checks:
                print(f"  {check}")
        
        # Рекомендации
        recommendations = []
        
        if result.intent == "offtopic" and not result.is_humor and len(result.response_text) < 50:
            recommendations.append("💡 Generic offtopic response could be more helpful")
        
        if result.user_signal == "anxiety_about_child" and not any(word in result.response_text.lower() for word in ["понимаю", "важно"]):
            recommendations.append("💡 Consider adding empathy for anxious parent")
        
        if result.user_signal == "price_sensitive" and "скидк" not in result.response_text.lower():
            recommendations.append("💡 Consider mentioning discounts for price-sensitive user")
        
        if result.user_signal == "ready_to_buy" and not result.questions:
            recommendations.append("💡 Ready to buy user should get implicit questions")
        
        if recommendations:
            print(f"\n  {Colors.CYAN}Recommendations:{Colors.ENDC}")
            for rec in recommendations:
                print(f"  {rec}")
    
    def show_session_stats(self):
        """Показывает статистику сессии"""
        print(f"\n{Colors.BOLD}=== SESSION STATISTICS ==={Colors.ENDC}")
        print(f"Total requests: {self.session_stats['total_requests']}")
        print(f"Success rate: {self.session_stats['success_count']}/{self.session_stats['total_requests']}")
        print(f"Offtopic: {self.session_stats['offtopic_count']}")
        if self.session_stats['humor_detected'] > 0:
            print(f"{Colors.PURPLE}🎭 Humor detected: {self.session_stats['humor_detected']} times{Colors.ENDC}")
        print(f"Avg response time: {self.session_stats['avg_response_time']:.2f}s")
        
        if self.session_stats['signals']:
            print(f"\nUser signals distribution:")
            for signal, count in self.session_stats['signals'].items():
                icon = self._get_signal_icon(signal)
                print(f"  {icon} {signal}: {count}")

# ====== РЕЖИМЫ РАБОТЫ ======

async def interactive_mode(sandbox: HTTPSandbox):
    """Интерактивный режим - ввод сообщений с клавиатуры"""
    print(f"{Colors.HEADER}🚀 HTTP Sandbox - Interactive Mode{Colors.ENDC}")
    print(f"Commands: /quit, /clear, /user <id>, /stats, /help")
    print(f"{Colors.DIM}Connecting to {sandbox.base_url}...{Colors.ENDC}")
    
    if not await sandbox.check_server_health():
        print(f"{Colors.RED}❌ Server not available at {sandbox.base_url}{Colors.ENDC}")
        print(f"{Colors.YELLOW}💡 Start server with: python src/main.py{Colors.ENDC}")
        return
    
    print(f"{Colors.GREEN}✅ Connected to server{Colors.ENDC}\n")
    
    user_id = "test_user"
    message_count = 0
    
    while True:
        try:
            # Промпт с номером сообщения
            prompt = f"{Colors.CYAN}[{message_count}] You:{Colors.ENDC} "
            user_input = input(prompt)
            
            # Обработка команд
            if user_input.lower() in ['/quit', '/exit', '/q']:
                sandbox.show_session_stats()
                print(f"{Colors.YELLOW}Goodbye!{Colors.ENDC}")
                break
            
            elif user_input.lower() == '/clear':
                print("\033[2J\033[H")  # Clear screen
                print(f"{Colors.GREEN}Screen cleared{Colors.ENDC}")
                continue
            
            elif user_input.lower().startswith('/user '):
                user_id = user_input[6:].strip()
                print(f"{Colors.GREEN}Switched to user: {user_id}{Colors.ENDC}")
                continue
            
            elif user_input.lower() == '/stats':
                sandbox.show_session_stats()
                continue
            
            elif user_input.lower() == '/help':
                print(f"{Colors.CYAN}Available commands:{Colors.ENDC}")
                print("  /quit - exit sandbox")
                print("  /clear - clear screen")
                print("  /user <id> - switch user ID")
                print("  /stats - show session statistics")
                print("  /help - show this help")
                continue
            
            elif user_input.startswith('/'):
                print(f"{Colors.YELLOW}Unknown command. Type /help for commands{Colors.ENDC}")
                continue
            
            # Обработка сообщения
            result = await sandbox.process_message(user_input, user_id, show_details=True)
            if result:
                sandbox.show_result(result)
                message_count += 1
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Interrupted{Colors.ENDC}")
            break
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.ENDC}")

async def single_message_mode(sandbox: HTTPSandbox, message: str, user_id: str = "test_user"):
    """Режим одного сообщения"""
    print(f"{Colors.HEADER}🚀 HTTP Sandbox - Single Message{Colors.ENDC}")
    
    if not await sandbox.check_server_health():
        print(f"{Colors.RED}❌ Server not available{Colors.ENDC}")
        print(f"{Colors.YELLOW}💡 Start server with: python src/main.py{Colors.ENDC}")
        return 1
    
    result = await sandbox.process_message(message, user_id, show_details=True)
    if result:
        sandbox.show_result(result)
        return 0 if result.intent == "success" else 1
    return 1

async def dialogue_test_mode(sandbox: HTTPSandbox, dialogue_id: int):
    """Режим тестирования диалогов из test_humor_scenarios.json"""
    print(f"{Colors.HEADER}🚀 HTTP Sandbox - Dialogue Test Mode{Colors.ENDC}")
    
    if not await sandbox.check_server_health():
        print(f"{Colors.RED}❌ Server not available{Colors.ENDC}")
        print(f"{Colors.YELLOW}💡 Start server with: python src/main.py{Colors.ENDC}")
        return
    
    # Загружаем сценарии диалогов
    scenarios_file = "test_humor_scenarios.json"
    if not os.path.exists(scenarios_file):
        print(f"{Colors.RED}❌ File {scenarios_file} not found{Colors.ENDC}")
        return
    
    with open(scenarios_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        scenarios = data.get('test_scenarios', data.get('scenarios', []))
    
    # Находим нужный диалог
    dialogue = None
    for scenario in scenarios:
        # Поддерживаем как числовые ID (5), так и строковые (dialog_5)
        scenario_id = str(scenario.get('id', ''))
        if scenario_id == str(dialogue_id) or scenario_id == f"dialog_{dialogue_id}":
            dialogue = scenario
            break
    
    if not dialogue:
        print(f"{Colors.RED}❌ Dialogue with ID {dialogue_id} not found{Colors.ENDC}")
        print(f"Available IDs: {', '.join(str(s['id']) for s in scenarios)}")
        return
    
    # Выводим информацию о диалоге
    print(f"\n{Colors.BOLD}=== SCENARIO {dialogue['id']}: {dialogue['name']} ==={Colors.ENDC}")
    print(f"{Colors.CYAN}Description:{Colors.ENDC} {dialogue['description']}")
    if 'expected_signal' in dialogue:
        print(f"{Colors.CYAN}Expected signal:{Colors.ENDC} {dialogue['expected_signal']}")
    if 'expected_humor' in dialogue:
        print(f"{Colors.CYAN}Expected humor:{Colors.ENDC} {dialogue['expected_humor']}")
    elif 'expected_humor_count' in dialogue:
        print(f"{Colors.CYAN}Expected humor:{Colors.ENDC} {dialogue['expected_humor_count']}")
    print(f"{Colors.DIM}{'='*60}{Colors.ENDC}\n")
    
    # Статистика для диалога
    dialogue_stats = {
        "total_messages": len(dialogue['messages']),
        "offtopic_count": 0,
        "humor_detected": 0,
        "signal_correct": True,
        "current_signal": None,
        "failed_messages": 0
    }
    
    user_id = f"humor_test_{dialogue_id}"
    
    # Очищаем историю для этого user_id перед началом теста
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{sandbox.base_url}/clear_history/{user_id}")
            if response.status_code == 200:
                print(f"{Colors.GREEN}✓ History cleared for {user_id}{Colors.ENDC}\n")
    except:
        pass  # Если не удалось очистить, продолжаем (возможно старая версия сервера)
    
    # Проходим по всем сообщениям диалога
    for i, msg_data in enumerate(dialogue['messages'], 1):
        print(f"{Colors.BOLD}[Message {i}/{len(dialogue['messages'])}]{Colors.ENDC}")
        
        # Поддерживаем как строки, так и объекты
        if isinstance(msg_data, str):
            message = msg_data
            print(f"{Colors.CYAN}USER:{Colors.ENDC} {message}")
        else:
            message = msg_data['message']
            print(f"{Colors.CYAN}USER:{Colors.ENDC} {message}")
            print(f"{Colors.DIM}Expected: {msg_data.get('expected_intent', 'N/A')}")
            if msg_data.get('is_offtopic'):
                print(f"          Offtopic=True, Humor possible={msg_data.get('humor_possible', False)}{Colors.ENDC}")
            else:
                print(f"{Colors.ENDC}")
        
        # Отправляем сообщение
        result = await sandbox.process_message(
            message,
            user_id,
            show_details=False  # Не показываем детали, покажем свои
        )
        
        if result:
            # Показываем ответ
            if result.is_humor:
                print(f"{Colors.PURPLE}🎭 ASSISTANT: {result.response_text}{Colors.ENDC}")
                dialogue_stats["humor_detected"] += 1
            else:
                print(f"{Colors.GREEN}ASSISTANT:{Colors.ENDC} {result.response_text}")
            
            # Анализ соответствия
            print(f"\n{Colors.DIM}Analysis:{Colors.ENDC}")
            
            # Intent (только если у нас есть ожидаемое значение)
            if isinstance(msg_data, dict) and 'expected_intent' in msg_data:
                if result.intent == msg_data['expected_intent']:
                    print(f"  {Colors.GREEN}✓ Intent: {result.intent}{Colors.ENDC}")
                else:
                    print(f"  {Colors.RED}✗ Intent: got {result.intent}, expected {msg_data['expected_intent']}{Colors.ENDC}")
            else:
                print(f"  Intent: {result.intent}")
            
            # Signal tracking
            if result.user_signal:
                dialogue_stats["current_signal"] = result.user_signal
                print(f"  Signal: {result.user_signal}")
            
            # Offtopic tracking
            if isinstance(msg_data, dict) and msg_data.get('is_offtopic'):
                dialogue_stats["offtopic_count"] += 1
                
                # Проверка юмора
                if msg_data.get('humor_possible'):
                    if result.is_humor:
                        print(f"  {Colors.PURPLE}🎭 HUMOR DETECTED (good!){Colors.ENDC}")
                    else:
                        print(f"  {Colors.DIM}No humor (33% chance){Colors.ENDC}")
                elif msg_data.get('block_reason'):
                    if result.is_humor:
                        print(f"  {Colors.RED}✗ HUMOR SHOULD BE BLOCKED ({msg_data['block_reason']}){Colors.ENDC}")
                    else:
                        print(f"  {Colors.GREEN}✓ Humor correctly blocked ({msg_data['block_reason']}){Colors.ENDC}")
            
            # Signal change tracking
            if isinstance(msg_data, dict) and msg_data.get('signal_change'):
                print(f"  {Colors.YELLOW}Signal change expected: → {msg_data['signal_change']}{Colors.ENDC}")
            
            print(f"\n{Colors.DIM}{'─'*60}{Colors.ENDC}\n")
            
            # Небольшая задержка между сообщениями
            await asyncio.sleep(0.5)
        else:
            # Детальная диагностика ошибки
            print(f"{Colors.RED}❌ Ошибка: {Colors.ENDC}")
            print(f"{Colors.RED}✗ Request failed{Colors.ENDC}")
            dialogue_stats["failed_messages"] += 1
            
            # Логируем проблемное сообщение для дальнейшего анализа
            if isinstance(msg_data, dict):
                print(f"{Colors.DIM}  Expected intent: {msg_data.get('expected_intent', 'N/A')}{Colors.ENDC}")
                print(f"{Colors.DIM}  Message type: {type(msg_data['message']) if 'message' in msg_data else type(msg_data)}{Colors.ENDC}")
    
    # Итоговая статистика по диалогу
    print(f"\n{Colors.BOLD}=== DIALOGUE SUMMARY ==={Colors.ENDC}")
    print(f"Total messages: {dialogue_stats['total_messages']}")
    print(f"Offtopic messages: {dialogue_stats['offtopic_count']}")
    
    # Показываем статистику ошибок если были
    if dialogue_stats.get('failed_messages', 0) > 0:
        print(f"{Colors.RED}Failed messages: {dialogue_stats['failed_messages']}{Colors.ENDC}")
    
    if dialogue_stats['offtopic_count'] > 0:
        humor_rate = (dialogue_stats['humor_detected'] / dialogue_stats['offtopic_count']) * 100
        print(f"{Colors.PURPLE}🎭 Humor detected: {dialogue_stats['humor_detected']}/{dialogue_stats['offtopic_count']} offtopic ({humor_rate:.0f}%){Colors.ENDC}")
        
        # Оценка соответствия ожиданиям
        if dialogue['expected_humor_count'] == "0 (блокировка по сигналу)":
            if dialogue_stats['humor_detected'] == 0:
                print(f"{Colors.GREEN}✓ Humor correctly blocked as expected{Colors.ENDC}")
            else:
                print(f"{Colors.RED}✗ Humor should have been blocked!{Colors.ENDC}")
        else:
            print(f"Expected: {dialogue['expected_humor_count']}")
            if humor_rate >= 20 and humor_rate <= 50:
                print(f"{Colors.GREEN}✓ Humor rate is within expected range{Colors.ENDC}")
            elif humor_rate < 20:
                print(f"{Colors.YELLOW}⚠ Humor rate is lower than expected{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠ Humor rate is higher than expected{Colors.ENDC}")
    
    print(f"\nFinal signal: {dialogue_stats['current_signal']}")
    if 'expected_signal' in dialogue:
        print(f"Expected signal pattern: {dialogue['expected_signal']}")

async def batch_test_mode(sandbox: HTTPSandbox, test_file: str = None):
    """Режим batch тестирования"""
    print(f"{Colors.HEADER}🚀 HTTP Sandbox - Batch Test Mode{Colors.ENDC}")
    
    if not await sandbox.check_server_health():
        print(f"{Colors.RED}❌ Server not available{Colors.ENDC}")
        print(f"{Colors.YELLOW}💡 Start server with: python src/main.py{Colors.ENDC}")
        return
    
    # Загрузка тестовых сценариев
    if test_file and os.path.exists(test_file):
        print(f"Loading scenarios from: {test_file}")
        with open(test_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            test_scenarios = test_data.get('scenarios', [])
            print(f"Loaded {len(test_scenarios)} scenarios\n")
    else:
        # Тестовые сценарии по умолчанию
        test_scenarios = [
            {"id": "price_1", "message": "Сколько стоит курс?", "user_id": "test_price"},
            {"id": "anxiety_1", "message": "Мой ребенок очень стеснительный, подойдут ли ему занятия?", "user_id": "test_anxiety"},
            {"id": "ready_1", "message": "Хочу записать ребенка на курс лидерства", "user_id": "test_ready"},
            {"id": "exploring_1", "message": "Расскажите о вашей школе", "user_id": "test_explore"},
            {"id": "greeting_1", "message": "Привет!", "user_id": "test_social"},
            {"id": "offtopic_1", "message": "Какая погода завтра?", "user_id": "test_offtopic"},
            {"id": "mixed_1", "message": "Добрый день! Сколько стоит курс эмоционального интеллекта?", "user_id": "test_mixed"},
        ]
    
    print(f"Running {len(test_scenarios)} test scenarios...\n")
    
    results = []
    categories = {}  # Группировка по категориям
    
    for i, scenario in enumerate(test_scenarios, 1):
        category = scenario.get('category', 'default')
        print(f"{Colors.CYAN}[{i}/{len(test_scenarios)}] {category.upper()}: {scenario['id']}{Colors.ENDC}")
        print(f"Message: \"{scenario['message']}\"")
        
        result = await sandbox.process_message(
            scenario['message'],
            scenario.get('user_id', 'test_user'),
            show_details=False
        )
        
        if result:
            # Анализ результата относительно ожиданий
            expected = scenario.get('expected', {})
            checks_passed = []
            checks_failed = []
            
            # Проверка intent
            if 'intent' in expected:
                if result.intent == expected['intent']:
                    checks_passed.append(f"intent={result.intent}")
                else:
                    checks_failed.append(f"intent: got {result.intent}, expected {expected['intent']}")
            
            # Проверка user_signal
            if 'user_signal' in expected:
                if result.user_signal == expected['user_signal']:
                    checks_passed.append(f"signal={result.user_signal}")
                else:
                    checks_failed.append(f"signal: got {result.user_signal}, expected {expected['user_signal']}")
            
            # Проверка social
            if 'social' in expected:
                if result.social_context == expected['social']:
                    checks_passed.append(f"social={result.social_context}")
                else:
                    checks_failed.append(f"social: got {result.social_context}, expected {expected['social']}")
            
            # Проверка ключевых слов в ответе
            if 'should_have' in expected:
                found_words = [word for word in expected['should_have'] if word in result.response_text.lower()]
                missing_words = [word for word in expected['should_have'] if word not in result.response_text.lower()]
                if found_words:
                    checks_passed.append(f"keywords: {', '.join(found_words)}")
                if missing_words:
                    checks_failed.append(f"missing keywords: {', '.join(missing_words)}")
            
            # Вывод результатов проверки
            if checks_passed:
                print(f"{Colors.GREEN}  ✓ {', '.join(checks_passed)}{Colors.ENDC}")
            if checks_failed:
                for fail in checks_failed:
                    print(f"{Colors.RED}  ✗ {fail}{Colors.ENDC}")
            
            # Детекция юмора для offtopic
            if result.intent == "offtopic":
                if result.is_humor:
                    print(f"{Colors.PURPLE}  🎭 HUMOR DETECTED!{Colors.ENDC}")
                    # Показываем первые 100 символов юмора
                    humor_preview = result.response_text[:100] + "..." if len(result.response_text) > 100 else result.response_text
                    print(f"{Colors.PURPLE}     \"{humor_preview}\"{Colors.ENDC}")
                elif category in ["pure_offtopic", "humor_test"]:
                    print(f"{Colors.DIM}  No humor (33% chance expected){Colors.ENDC}")
            
            # Сохраняем результат
            results.append({
                "scenario": scenario,
                "result": result,
                "passed": len(checks_failed) == 0
            })
            
            # Группировка по категориям
            if category not in categories:
                categories[category] = {"passed": 0, "failed": 0, "total": 0}
            categories[category]["total"] += 1
            if len(checks_failed) == 0:
                categories[category]["passed"] += 1
            else:
                categories[category]["failed"] += 1
        else:
            print(f"{Colors.RED}  ✗ Request failed{Colors.ENDC}")
        
        print()
    
    # Итоговая статистика
    print(f"\n{Colors.BOLD}=== BATCH TEST SUMMARY ==={Colors.ENDC}")
    
    # Статистика по категориям
    if categories:
        print(f"\n{Colors.CYAN}Results by category:{Colors.ENDC}")
        for cat_name, cat_stats in categories.items():
            pass_rate = (cat_stats['passed'] / cat_stats['total'] * 100) if cat_stats['total'] > 0 else 0
            color = Colors.GREEN if pass_rate >= 70 else Colors.YELLOW if pass_rate >= 40 else Colors.RED
            print(f"  {cat_name}: {color}{cat_stats['passed']}/{cat_stats['total']} ({pass_rate:.0f}%){Colors.ENDC}")
    
    # Общая статистика
    total_passed = sum(1 for r in results if r.get('passed', False))
    print(f"\n{Colors.CYAN}Overall:{Colors.ENDC}")
    print(f"  Total tests: {len(results)}")
    print(f"  Passed: {total_passed}/{len(results)} ({total_passed/len(results)*100:.0f}%)")
    
    # Статистика юмора
    humor_count = sum(1 for r in results if r['result'].is_humor)
    humor_scenarios = [r for r in results if r['scenario'].get('category') == 'humor_test']
    if humor_scenarios:
        humor_detected = sum(1 for r in humor_scenarios if r['result'].is_humor)
        print(f"\n{Colors.PURPLE}Humor statistics:{Colors.ENDC}")
        print(f"  Humor tests: {len(humor_scenarios)}")
        print(f"  Humor detected: {humor_detected}/{len(humor_scenarios)} ({humor_detected/len(humor_scenarios)*100:.0f}%)")
        print(f"  Expected ~33%, got {humor_detected/len(humor_scenarios)*100:.0f}%")
    
    # Критические проблемы
    critical_issues = []
    
    # Проверяем проблемы с сигналами
    signal_issues = [r for r in results 
                     if r['scenario'].get('expected', {}).get('user_signal') 
                     and r['result'].user_signal != r['scenario']['expected']['user_signal']]
    
    if signal_issues:
        critical_issues.append(f"User signal detection: {len(signal_issues)} failures")
    
    if critical_issues:
        print(f"\n{Colors.RED}⚠️  CRITICAL ISSUES FOUND:{Colors.ENDC}")
        for issue in critical_issues:
            print(f"  • {issue}")
        
        # Детальные рекомендации
        print(f"\n{Colors.YELLOW}📋 RECOMMENDATIONS:{Colors.ENDC}")
        if signal_issues:
            print(f"  1. Fix user_signal detection in router.py")
            print(f"     Failed signals: {', '.join(set(r['scenario']['expected']['user_signal'] for r in signal_issues))}")
            print(f"     Check prompt in router.py lines ~180-220")

# ====== ГЛАВНАЯ ФУНКЦИЯ ======

async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='HTTP Sandbox for Ukido AI Assistant')
    parser.add_argument('-m', '--message', help='Send single message')
    parser.add_argument('-u', '--user', default='test_user', help='User ID')
    parser.add_argument('--test', nargs='?', const=True, help='Run batch tests, optionally with test file')
    parser.add_argument('--dialogue', type=str, help='Run dialogue test by ID from test_humor_scenarios.json')
    parser.add_argument('--url', default='http://localhost:8000', help='Server URL')
    
    args = parser.parse_args()
    
    # Создаём песочницу
    sandbox = HTTPSandbox(base_url=args.url)
    
    # Выбираем режим работы
    if args.message:
        # Single message mode
        exit_code = await single_message_mode(sandbox, args.message, args.user)
        sys.exit(exit_code)
    elif args.dialogue:
        # Dialogue test mode
        await dialogue_test_mode(sandbox, args.dialogue)
    elif args.test:
        # Batch test mode
        test_file = args.test if isinstance(args.test, str) else None
        await batch_test_mode(sandbox, test_file)
    else:
        # Interactive mode
        await interactive_mode(sandbox)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Goodbye!{Colors.ENDC}")