#!/usr/bin/env python3
"""
Песочница v2.0 - Чистая реализация под текущую архитектуру
Без Quick Regex, только Router → Claude pipeline
"""

import asyncio
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Импортируем только то, что реально используется
from router import Router
from response_generator import ResponseGenerator
from history_manager import HistoryManager
from social_state import SocialStateManager
from config import Config

# ====== ЦВЕТА ДЛЯ КРАСИВОГО ВЫВОДА ======
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

# ====== РЕЗУЛЬТАТ ОБРАБОТКИ ======
@dataclass
class ProcessingResult:
    """Результат обработки одного сообщения"""
    user_message: str
    response: str
    router_status: str
    social_context: Optional[str]
    documents: List[str]
    questions: List[str]
    router_time: float
    generator_time: float
    total_time: float
    source: str  # "router_social", "claude", "fallback"

# ====== ВАЛИДАЦИЯ ======
@dataclass 
class ValidationResult:
    """Результат проверки ответа"""
    passed: List[str]
    failed: List[str]
    
    @property
    def is_valid(self) -> bool:
        return len(self.failed) == 0

# ====== ОСНОВНОЙ КЛАСС ПЕСОЧНИЦЫ ======
class SandboxV2:
    """Чистая песочница для текущей архитектуры"""
    
    def __init__(self):
        self.config = Config()
        self.router = Router(use_cache=True)
        self.response_generator = ResponseGenerator()
        self.history = HistoryManager()
        self.social_state = SocialStateManager()
    
    async def process_message(
        self,
        message: str,
        user_id: str = "test_user",
        show_details: bool = True
    ) -> ProcessingResult:
        """
        Обрабатывает одно сообщение через pipeline
        Эмулирует точную логику из main.py
        """
        start_time = time.time()
        
        # Получаем историю
        history_messages = self.history.get_history(user_id)
        
        if show_details:
            print(f"\n{Colors.DIM}━━━ Pipeline Start ━━━{Colors.ENDC}")
        
        # ====== ШАГ 1: ROUTER ======
        router_start = time.time()
        try:
            # ВАЖНО: передаем user_id для отслеживания социального состояния
            route_result = await self.router.route(message, history_messages, user_id)
            router_time = time.time() - router_start
            
            if show_details:
                print(f"{Colors.YELLOW}Router:{Colors.ENDC} {router_time:.2f}s")
                print(f"  Status: {route_result.get('status')}")
                if route_result.get('social_context'):
                    print(f"  Social: {route_result['social_context']}")
        except Exception as e:
            print(f"{Colors.RED}❌ Router failed: {e}{Colors.ENDC}")
            route_result = {
                "status": "offtopic",
                "message": "Временная проблема. Попробуйте позже."
            }
            router_time = time.time() - router_start
        
        # Извлекаем данные из результата роутера
        status = route_result.get("status", "offtopic")
        social_context = route_result.get("social_context")
        documents = route_result.get("documents", [])
        questions = route_result.get("decomposed_questions", [])
        
        # ====== ШАГ 2: ГЕНЕРАЦИЯ ОТВЕТА ======
        generator_time = 0
        source = "fallback"
        
        if status == "success":
            # Claude генерирует ответ
            generator_start = time.time()
            try:
                response = await self.response_generator.generate(
                    {
                        "status": status,
                        "documents": documents,
                        "decomposed_questions": questions,
                        "social_context": social_context,
                    },
                    history_messages
                )
                generator_time = time.time() - generator_start
                source = "claude"
                
                if show_details:
                    print(f"{Colors.GREEN}Generator:{Colors.ENDC} {generator_time:.2f}s")
                    print(f"  Docs: {documents}")
                    print(f"  Length: {len(response)} chars")
            except Exception as e:
                print(f"{Colors.RED}❌ Generator failed: {e}{Colors.ENDC}")
                response = "Извините, не удалось сформировать ответ."
                generator_time = time.time() - generator_start
        else:
            # Offtopic или need_simplification
            response = route_result.get("message", "К сожалению, я могу помочь только с вопросами о нашей школе.")
            
            # Добавляем социальный контекст если есть
            if social_context == "greeting":
                response = f"Здравствуйте! {response}"
            elif social_context == "farewell":
                response = "До свидания! Будем рады видеть вас в нашей школе!"
            
            source = "router_social" if social_context else "fallback"
        
        # ====== ШАГ 3: СОХРАНЕНИЕ В ИСТОРИЮ ======
        self.history.add_message(user_id, "user", message)
        self.history.add_message(user_id, "assistant", response)
        
        total_time = time.time() - start_time
        
        if show_details:
            print(f"{Colors.DIM}━━━ Pipeline End: {total_time:.2f}s ━━━{Colors.ENDC}\n")
        
        return ProcessingResult(
            user_message=message,
            response=response,
            router_status=status,
            social_context=social_context,
            documents=documents,
            questions=questions,
            router_time=router_time,
            generator_time=generator_time,
            total_time=total_time,
            source=source
        )
    
    def validate_result(self, result: ProcessingResult, context: Dict = None) -> ValidationResult:
        """
        Валидирует результат обработки
        
        Args:
            result: Результат обработки
            context: Дополнительный контекст (например, история)
        """
        passed = []
        failed = []
        
        message_lower = result.user_message.lower()
        response_lower = result.response.lower()
        
        # Проверка 1: Приветствие
        if any(word in message_lower for word in ["привет", "здравств", "добр"]):
            if any(word in response_lower for word in ["здравств", "привет", "добр"]):
                passed.append("✅ Приветствие есть")
            else:
                failed.append("❌ Нет приветствия в ответе")
        
        # Проверка 2: Mixed запросы
        has_greeting = any(word in message_lower for word in ["привет", "здравств"])
        has_business = any(word in message_lower for word in ["курс", "цен", "скидк", "заняти"])
        
        if has_greeting and has_business:
            if len(result.response) > 100:
                passed.append("✅ Mixed запрос обработан полностью")
            else:
                failed.append("❌ Mixed запрос обработан частично")
        
        # Проверка 3: Контекстуальные вопросы
        if message_lower.strip() in ["а?", "и?", "и всё?"]:
            if result.router_status == "success" and len(result.response) > 50:
                passed.append("✅ Контекстуальный вопрос обработан")
            else:
                failed.append("❌ Контекст не использован для 'А?'")
        
        # Проверка 4: Прощание
        if any(word in message_lower for word in ["пока", "до свидан", "до связи"]):
            if "за рамками" not in response_lower and "не могу помочь" not in response_lower:
                passed.append("✅ Корректное прощание")
            else:
                failed.append("❌ Некорректное прощание с offtopic")
        
        # Проверка 5: Источник ответа
        if result.source == "claude" and result.router_status == "success":
            passed.append("✅ Claude обработал успешно")
        elif result.source == "router_social" and result.social_context:
            passed.append("✅ Router обработал социалку")
        
        return ValidationResult(passed=passed, failed=failed)
    
    def show_result(self, result: ProcessingResult, validation: Optional[ValidationResult] = None):
        """Красиво отображает результат"""
        print(f"\n{Colors.CYAN}╔══════════════════════════════════════════════╗")
        print(f"║            РЕЗУЛЬТАТ ОБРАБОТКИ               ║")
        print(f"╚══════════════════════════════════════════════╝{Colors.ENDC}")
        
        print(f"\n👤 {Colors.BOLD}Вопрос:{Colors.ENDC} {result.user_message}")
        print(f"🤖 {Colors.BOLD}Ответ:{Colors.ENDC} {result.response[:150]}{'...' if len(result.response) > 150 else ''}")
        
        print(f"\n{Colors.BOLD}📊 Метрики:{Colors.ENDC}")
        print(f"  • Статус: {result.router_status}")
        print(f"  • Источник: {result.source}")
        if result.social_context:
            print(f"  • Социальный контекст: {result.social_context}")
        if result.documents:
            print(f"  • Документы: {', '.join(result.documents)}")
        print(f"  • Время: {result.total_time:.2f}s (Router: {result.router_time:.2f}s, Generator: {result.generator_time:.2f}s)")
        
        if validation:
            print(f"\n{Colors.BOLD}✔️ Валидация:{Colors.ENDC}")
            for check in validation.passed:
                print(f"  {check}")
            for check in validation.failed:
                print(f"  {check}")

# ====== ТЕСТОВЫЕ СЦЕНАРИИ ======
async def run_test_scenarios():
    """Запускает набор тестовых сценариев"""
    sandbox = SandboxV2()
    
    scenarios = [
        {
            "name": "Mixed: Приветствие + вопрос",
            "messages": ["Привет! Есть курсы для детей 10 лет?"]
        },
        {
            "name": "Повторное приветствие",
            "messages": [
                "Привет!",
                "Сколько стоит обучение?",
                "Привет!"
            ]
        },
        {
            "name": "Контекстуальный вопрос",
            "messages": [
                "Расскажите про цены",
                "А?"
            ]
        },
        {
            "name": "Прощание",
            "messages": [
                "Какие есть курсы?",
                "Спасибо! До свидания!"
            ]
        }
    ]
    
    print(f"{Colors.HEADER}{'='*50}")
    print("      ТЕСТОВЫЕ СЦЕНАРИИ - SANDBOX V2")
    print(f"{'='*50}{Colors.ENDC}\n")
    
    for scenario in scenarios:
        print(f"\n{Colors.BOLD}📋 Сценарий: {scenario['name']}{Colors.ENDC}")
        print("-" * 50)
        
        user_id = f"test_{scenario['name'].replace(' ', '_').lower()}"
        
        for i, message in enumerate(scenario['messages'], 1):
            print(f"\n{Colors.DIM}Сообщение {i}/{len(scenario['messages'])}:{Colors.ENDC}")
            
            result = await sandbox.process_message(message, user_id, show_details=False)
            validation = sandbox.validate_result(result)
            
            sandbox.show_result(result, validation)
            
            await asyncio.sleep(0.5)

# ====== ИНТЕРАКТИВНЫЙ РЕЖИМ ======
async def interactive_mode():
    """Интерактивный режим тестирования"""
    sandbox = SandboxV2()
    
    print(f"{Colors.HEADER}{'='*50}")
    print("         SANDBOX V2 - ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print(f"{'='*50}{Colors.ENDC}")
    
    config = Config()
    print(f"\n{Colors.BOLD}Конфигурация:{Colors.ENDC}")
    print(f"  • Архитектура: Router (Gemini) → Generator (Claude)")
    print(f"  • Лимит истории: {config.HISTORY_LIMIT} сообщений")
    print(f"  • Модель Router: Gemini 2.5 Flash")
    print(f"  • Модель Generator: Claude 3.5 Haiku")
    
    print(f"\n{Colors.BOLD}Команды:{Colors.ENDC}")
    print("  • /clear - очистить историю")
    print("  • /user <id> - сменить пользователя")
    print("  • /validate - включить/выключить валидацию")
    print("  • /details - показать/скрыть детали")
    print("  • /quit - выход\n")
    
    user_id = "interactive_user"
    show_details = True
    validate = True
    
    while True:
        try:
            user_input = input(f"{Colors.BOLD}User [{user_id}]: {Colors.ENDC}").strip()
            
            if not user_input:
                continue
            
            # Обработка команд
            if user_input.lower() == '/quit':
                print("До свидания!")
                break
            elif user_input.lower() == '/clear':
                sandbox.history = HistoryManager()
                sandbox.social_state = SocialStateManager()
                print("✅ История очищена")
                continue
            elif user_input.lower().startswith('/user'):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    user_id = parts[1]
                    print(f"✅ Пользователь: {user_id}")
                continue
            elif user_input.lower() == '/validate':
                validate = not validate
                print(f"✅ Валидация: {'включена' if validate else 'выключена'}")
                continue
            elif user_input.lower() == '/details':
                show_details = not show_details
                print(f"✅ Детали: {'показывать' if show_details else 'скрывать'}")
                continue
            
            # Обработка сообщения
            result = await sandbox.process_message(user_input, user_id, show_details)
            
            if validate:
                validation = sandbox.validate_result(result)
                sandbox.show_result(result, validation)
            else:
                sandbox.show_result(result)
            
        except KeyboardInterrupt:
            print("\n\nПрервано пользователем")
            break
        except Exception as e:
            print(f"{Colors.RED}❌ Ошибка: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()

# ====== РЕЖИМ ОДНОГО СООБЩЕНИЯ ======
async def single_message_mode(message: str, user_id: str = "cli_user", validate: bool = True):
    """Обрабатывает одно сообщение и выходит"""
    sandbox = SandboxV2()
    
    print(f"{Colors.CYAN}╔══════════════════════════════════════════════╗")
    print(f"║         SANDBOX V2 - SINGLE MESSAGE          ║")
    print(f"╚══════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    # Обрабатываем сообщение
    result = await sandbox.process_message(message, user_id, show_details=True)
    
    # Валидация если нужна
    if validate:
        validation = sandbox.validate_result(result)
        sandbox.show_result(result, validation)
    else:
        sandbox.show_result(result)
    
    # Возвращаем код выхода: 0 если все ок, 1 если есть ошибки валидации
    if validate:
        return 0 if validation.is_valid else 1
    return 0

# ====== ГЛАВНАЯ ФУНКЦИЯ ======
async def main():
    """Точка входа"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            await run_test_scenarios()
        elif sys.argv[1] in ["--message", "-m"] and len(sys.argv) > 2:
            # Режим одного сообщения для collaborative debugging
            message = sys.argv[2]
            user_id = sys.argv[3] if len(sys.argv) > 3 else "cli_user"
            exit_code = await single_message_mode(message, user_id)
            sys.exit(exit_code)
        elif sys.argv[1] == "--help":
            print("Использование:")
            print("  python sandbox_v2.py                      - интерактивный режим")
            print("  python sandbox_v2.py --test               - запуск тестов")
            print("  python sandbox_v2.py -m 'message' [user]  - обработать одно сообщение")
            print("  python sandbox_v2.py --help               - эта справка")
            print("\nПримеры:")
            print("  python sandbox_v2.py -m 'Привет!'")
            print("  python sandbox_v2.py -m 'Есть курсы?' user123")
        else:
            print(f"Неизвестная команда: {sys.argv[1]}")
            print("Используйте --help для справки")
    else:
        await interactive_mode()

if __name__ == "__main__":
    asyncio.run(main())