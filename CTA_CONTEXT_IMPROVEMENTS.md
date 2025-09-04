# 🎯 План улучшения контекстной осведомлённости CTA

**Версия:** 1.0  
**Дата создания:** 04.09.2025  
**Цель:** Сделать систему CTA умной, контекстной и не навязчивой  
**Приоритет:** Высокий

## 📊 Текущие проблемы

1. **Неуместные CTA** - предлагаем записаться тем, кто уже оплатил
2. **Игнорирование отказов** - продолжаем предлагать после "не интересно"
3. **Повторение одинаковых CTA** - раздражает пользователей
4. **Отсутствие памяти о действиях** - не помним что пользователь уже сделал

## 🔧 Решение 1: Детекция завершённых действий

### Новые файлы для создания:

#### `src/completed_actions_tracker.py`
```python
from typing import Dict, List, Set, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

class CompletedActionsTracker:
    """Отслеживает завершённые действия пользователей"""
    
    def __init__(self, storage_dir: Path = None):
        self.storage_dir = storage_dir or Path("data/user_actions")
        self.storage_dir.mkdir(exist_ok=True)
        self.completed_actions: Dict[str, Set[str]] = {}
        self.action_timestamps: Dict[str, Dict[str, datetime]] = {}
        
        # Типы завершённых действий
        self.COMPLETED_ACTIONS = {
            "paid_course": ["оплатил", "заплатил", "внёс оплату", "перевёл деньги"],
            "registered_trial": ["записался", "зарегистрировался на пробное"],
            "filled_form": ["заполнил форму", "отправил анкету"],
            "installed_zoom": ["установил zoom", "настроил камеру"],
            "received_access": ["получил доступ", "вошёл в кабинет"]
        }
        
    def detect_completed_action(self, message: str) -> Optional[str]:
        """Определяет тип завершённого действия из сообщения"""
        message_lower = message.lower()
        
        for action_type, triggers in self.COMPLETED_ACTIONS.items():
            if any(trigger in message_lower for trigger in triggers):
                return action_type
        return None
    
    def add_completed_action(self, user_id: str, action_type: str):
        """Добавляет завершённое действие для пользователя"""
        if user_id not in self.completed_actions:
            self.completed_actions[user_id] = set()
            self.action_timestamps[user_id] = {}
            
        self.completed_actions[user_id].add(action_type)
        self.action_timestamps[user_id][action_type] = datetime.now()
        self._save_to_disk(user_id)
    
    def has_completed(self, user_id: str, action_type: str) -> bool:
        """Проверяет, выполнил ли пользователь действие"""
        return action_type in self.completed_actions.get(user_id, set())
    
    def get_cta_restrictions(self, user_id: str) -> Dict[str, bool]:
        """Возвращает ограничения на CTA на основе завершённых действий"""
        restrictions = {
            "block_trial_cta": False,
            "block_payment_cta": False,
            "block_form_cta": False
        }
        
        if self.has_completed(user_id, "registered_trial"):
            restrictions["block_trial_cta"] = True
            
        if self.has_completed(user_id, "paid_course"):
            restrictions["block_payment_cta"] = True
            restrictions["block_trial_cta"] = True  # Уже оплатил - не нужно пробное
            
        if self.has_completed(user_id, "filled_form"):
            restrictions["block_form_cta"] = True
            
        return restrictions
```

### Интеграция в `src/main.py`:
```python
# Добавить импорт
from completed_actions_tracker import CompletedActionsTracker

# В начале файла после других инициализаций
actions_tracker = CompletedActionsTracker()

# В методе process_message, после получения router_result:
# Строка ~200
completed_action = actions_tracker.detect_completed_action(message)
if completed_action:
    actions_tracker.add_completed_action(user_id, completed_action)
    print(f"📝 Зафиксировано завершённое действие: {completed_action}")

# Передать ограничения в response_generator
cta_restrictions = actions_tracker.get_cta_restrictions(user_id)
response_data = await response_gen.generate(
    router_result,
    filtered_history, 
    message,
    cta_restrictions=cta_restrictions  # НОВЫЙ параметр
)
```

### Изменения в `src/offers_catalog.py`:
```python
def should_add_cta(user_signal: str, user_id: str, message_count: int, 
                   cta_restrictions: Dict[str, bool] = None) -> bool:
    """Определяет, нужно ли добавлять CTA с учётом ограничений"""
    
    # Проверяем ограничения на основе завершённых действий
    if cta_restrictions:
        if user_signal == "ready_to_buy" and cta_restrictions.get("block_trial_cta"):
            return False  # Не предлагать пробное тем, кто уже записался
        
        if user_signal == "price_sensitive" and cta_restrictions.get("block_payment_cta"):
            return False  # Не предлагать скидки тем, кто уже оплатил
    
    # Существующая логика rate limiting...
```

## 🔧 Решение 2: Блокировка CTA после отказа

### Новый файл `src/refusal_tracker.py`:
```python
from typing import Dict, Set, Optional
from datetime import datetime, timedelta

class RefusalTracker:
    """Отслеживает отказы пользователей и блокирует навязчивые CTA"""
    
    def __init__(self):
        self.refusals: Dict[str, Dict] = {}  # user_id -> {timestamp, count, block_until}
        
        # Негативные сигналы
        self.NEGATIVE_SIGNALS = [
            "не интересно", "не надо", "отстаньте", "дорого и всё",
            "не нужно", "спасибо, нет", "не буду", "не хочу",
            "достали", "надоели", "хватит", "прекратите",
            "не предлагайте", "я подумаю", "потом решу"
        ]
        
        # Мягкие отказы (блокировка на 3 сообщения)
        self.SOFT_REFUSAL = ["подумаю", "потом", "позже", "не сейчас"]
        
        # Жёсткие отказы (блокировка на 10 сообщений)
        self.HARD_REFUSAL = ["отстаньте", "достали", "надоели", "хватит"]
    
    def detect_refusal(self, message: str) -> Optional[str]:
        """Определяет тип отказа: soft, hard или None"""
        message_lower = message.lower()
        
        # Сначала проверяем жёсткие отказы
        if any(signal in message_lower for signal in self.HARD_REFUSAL):
            return "hard"
        
        # Затем мягкие
        if any(signal in message_lower for signal in self.SOFT_REFUSAL):
            return "soft"
        
        # Затем общие негативные
        if any(signal in message_lower for signal in self.NEGATIVE_SIGNALS):
            return "soft"
        
        return None
    
    def add_refusal(self, user_id: str, refusal_type: str, message_count: int):
        """Добавляет отказ и устанавливает блокировку"""
        
        if user_id not in self.refusals:
            self.refusals[user_id] = {
                "count": 0,
                "last_refusal": None,
                "block_until_message": 0
            }
        
        self.refusals[user_id]["count"] += 1
        self.refusals[user_id]["last_refusal"] = datetime.now()
        
        # Устанавливаем блокировку
        if refusal_type == "hard":
            block_for = 10  # Блокируем на 10 сообщений
        else:
            block_for = 3   # Блокируем на 3 сообщения
        
        self.refusals[user_id]["block_until_message"] = message_count + block_for
        
        print(f"🚫 Зафиксирован отказ ({refusal_type}): CTA заблокированы на {block_for} сообщений")
    
    def is_cta_blocked(self, user_id: str, current_message_count: int) -> bool:
        """Проверяет, заблокированы ли CTA для пользователя"""
        
        if user_id not in self.refusals:
            return False
        
        user_refusal = self.refusals[user_id]
        
        # Проверяем, не истекла ли блокировка
        if current_message_count >= user_refusal["block_until_message"]:
            # Блокировка истекла, но уменьшаем частоту CTA
            return False
        
        return True
    
    def get_cta_frequency_modifier(self, user_id: str) -> float:
        """Возвращает модификатор частоты CTA после отказов"""
        
        if user_id not in self.refusals:
            return 1.0  # Нормальная частота
        
        refusal_count = self.refusals[user_id]["count"]
        
        if refusal_count >= 3:
            return 0.2  # Очень редко (20% от нормальной частоты)
        elif refusal_count >= 2:
            return 0.5  # Реже (50% от нормальной частоты)
        elif refusal_count >= 1:
            return 0.7  # Немного реже (70% от нормальной частоты)
        
        return 1.0
```

### Интеграция в `src/main.py`:
```python
# Добавить импорт
from refusal_tracker import RefusalTracker

# В начале файла
refusal_tracker = RefusalTracker()

# В методе process_message, после router:
# Строка ~210
refusal_type = refusal_tracker.detect_refusal(message)
if refusal_type:
    message_count = len(chat.history.get(user_id, []))
    refusal_tracker.add_refusal(user_id, refusal_type, message_count)

# Проверяем блокировку перед генерацией ответа
is_cta_blocked = refusal_tracker.is_cta_blocked(user_id, message_count)
cta_frequency = refusal_tracker.get_cta_frequency_modifier(user_id)

# Передаём в response_generator
response_data = await response_gen.generate(
    router_result,
    filtered_history,
    message,
    cta_restrictions=cta_restrictions,
    cta_blocked=is_cta_blocked,  # НОВЫЙ параметр
    cta_frequency=cta_frequency   # НОВЫЙ параметр  
)
```

## 🔧 Решение 3: Трекинг уникальности CTA

### Новый файл `src/cta_variety_manager.py`:
```python
from typing import Dict, List, Set, Optional, Tuple
from collections import deque
import random

class CTAVarietyManager:
    """Управляет разнообразием CTA, избегая повторений"""
    
    def __init__(self):
        self.shown_cta: Dict[str, deque] = {}  # user_id -> deque последних CTA
        self.cta_variants = self._init_variants()
        
    def _init_variants(self) -> Dict[str, List[Dict]]:
        """Инициализирует варианты CTA для каждого сигнала"""
        return {
            "price_sensitive": [
                {
                    "id": "discount_10",
                    "text": "У нас действуют скидки: 10% при полной оплате курса",
                    "strength": "medium"
                },
                {
                    "id": "installment_3",
                    "text": "Доступна беспроцентная рассрочка на 3 месяца",
                    "strength": "medium"
                },
                {
                    "id": "discount_sibling",
                    "text": "Для второго ребёнка из семьи скидка 15%",
                    "strength": "soft"
                },
                {
                    "id": "compare_value",
                    "text": "Это дешевле, чем 2 занятия с репетитором, но эффект на годы",
                    "strength": "soft"
                },
                {
                    "id": "roi_investment",
                    "text": "Исследования показывают: soft skills окупаются в 4 раза",
                    "strength": "soft"
                }
            ],
            "ready_to_buy": [
                {
                    "id": "trial_simple",
                    "text": "Запись на пробное занятие открыта на ukido.ua/trial",
                    "strength": "medium"
                },
                {
                    "id": "trial_urgency",
                    "text": "В группах осталось всего несколько мест - запишитесь на ukido.ua/trial",
                    "strength": "strong"
                },
                {
                    "id": "trial_fast",
                    "text": "Заполнение формы займёт 2 минуты на ukido.ua/trial",
                    "strength": "soft"
                }
            ],
            "anxiety_about_child": [
                {
                    "id": "free_trial_soft",
                    "text": "Чтобы развеять сомнения, первое занятие проводим бесплатно",
                    "strength": "soft"
                },
                {
                    "id": "guarantee_return",
                    "text": "У нас есть гарантия возврата денег в первые 7 дней",
                    "strength": "medium"
                },
                {
                    "id": "individual_approach",
                    "text": "Можем подобрать индивидуальный формат для вашего ребёнка",
                    "strength": "soft"
                }
            ],
            "exploring_only": [
                {
                    "id": "free_trial_explore",
                    "text": "Если интересно, первое пробное занятие у нас бесплатное",
                    "strength": "soft"
                },
                {
                    "id": "more_info",
                    "text": "Подробнее о программах можно узнать на ukido.ua",
                    "strength": "soft"
                },
                {
                    "id": "consultation",
                    "text": "Можем провести бесплатную консультацию по выбору курса",
                    "strength": "soft"
                }
            ]
        }
    
    def get_next_cta(self, user_id: str, user_signal: str, 
                     message_count: int) -> Optional[Dict]:
        """Выбирает следующий CTA, избегая повторений"""
        
        # Инициализация истории для нового пользователя
        if user_id not in self.shown_cta:
            self.shown_cta[user_id] = deque(maxlen=5)  # Помним последние 5 CTA
        
        # Получаем варианты для сигнала
        available_variants = self.cta_variants.get(user_signal, [])
        if not available_variants:
            return None
        
        # Фильтруем уже показанные
        shown_ids = {cta["id"] for cta in self.shown_cta[user_id]}
        unseen_variants = [v for v in available_variants if v["id"] not in shown_ids]
        
        # Если все показаны, берём самый давний
        if not unseen_variants:
            # Сбрасываем историю, но оставляем последний
            if self.shown_cta[user_id]:
                last_shown = self.shown_cta[user_id][-1]
                unseen_variants = [v for v in available_variants if v["id"] != last_shown["id"]]
            else:
                unseen_variants = available_variants
        
        # Выбираем силу CTA в зависимости от прогресса диалога
        if message_count <= 3:
            preferred_strength = "soft"
        elif message_count <= 6:
            preferred_strength = "medium"  
        else:
            preferred_strength = "strong"
        
        # Фильтруем по силе (с fallback)
        strength_filtered = [v for v in unseen_variants if v["strength"] == preferred_strength]
        if not strength_filtered:
            strength_filtered = unseen_variants
        
        # Выбираем случайный из подходящих
        selected = random.choice(strength_filtered)
        
        # Запоминаем показанный
        self.shown_cta[user_id].append({
            "id": selected["id"],
            "signal": user_signal,
            "message_count": message_count
        })
        
        return selected
    
    def get_cta_history_stats(self, user_id: str) -> Dict:
        """Возвращает статистику по показанным CTA"""
        if user_id not in self.shown_cta:
            return {"total_shown": 0, "unique_shown": 0, "last_cta": None}
        
        history = list(self.shown_cta[user_id])
        unique_ids = set(cta["id"] for cta in history)
        
        return {
            "total_shown": len(history),
            "unique_shown": len(unique_ids),
            "last_cta": history[-1] if history else None,
            "signals_used": list(set(cta["signal"] for cta in history))
        }
```

### Интеграция в `src/offers_catalog.py`:
```python
# В начале файла
from cta_variety_manager import CTAVarietyManager

variety_manager = CTAVarietyManager()

def get_offer(user_signal: str, message_count: int, 
              last_user_message: str = None, has_cta: bool = True,
              user_id: str = None) -> Tuple[Optional[str], Optional[str]]:
    """Возвращает CTA с учётом вариативности"""
    
    if not has_cta or not user_id:
        return None, None
    
    # Получаем уникальный CTA
    cta_variant = variety_manager.get_next_cta(user_id, user_signal, message_count)
    
    if not cta_variant:
        # Fallback на старую логику
        return _get_default_cta(user_signal)
    
    # Логируем для отладки
    stats = variety_manager.get_cta_history_stats(user_id)
    print(f"📊 CTA Stats: показано {stats['total_shown']}, уникальных {stats['unique_shown']}")
    print(f"   Выбран: {cta_variant['id']} (сила: {cta_variant['strength']})")
    
    return cta_variant["text"], user_signal
```

## 📋 Полный план внедрения

### Этап 1: Подготовка (30 минут)
1. Создать директорию `data/user_actions` для хранения данных
2. Создать три новых файла: 
   - `src/completed_actions_tracker.py`
   - `src/refusal_tracker.py`
   - `src/cta_variety_manager.py`

### Этап 2: Интеграция трекеров (45 минут)
1. Добавить импорты в `src/main.py`
2. Инициализировать трекеры
3. Добавить вызовы detect/track в process_message
4. Передать параметры в response_generator

### Этап 3: Модификация offers_catalog.py (30 минут)
1. Интегрировать variety_manager
2. Модифицировать should_add_cta для учёта блокировок
3. Обновить get_offer для вариативности

### Этап 4: Обновление response_generator.py (20 минут)
1. Добавить параметры cta_blocked, cta_frequency
2. Учитывать их при принятии решения о добавлении CTA
3. Логировать причины блокировки

### Этап 5: Тестирование (40 минут)
1. Тест завершённых действий
2. Тест отказов и блокировок  
3. Тест вариативности CTA
4. Интеграционный тест всех компонентов

## 🧪 Тестовые сценарии

### Тест 1: Завершённые действия
```bash
# Шаг 1: Пользователь оплатил
curl -X POST http://localhost:8000/chat \
  -d '{"user_id":"test_completed","message":"Я только что оплатил курс"}'
# Ожидание: система запомнит оплату

# Шаг 2: Следующее сообщение
curl -X POST http://localhost:8000/chat \
  -d '{"user_id":"test_completed","message":"Какие у вас есть курсы?"}'
# Ожидание: НЕ должно быть CTA про оплату/скидки
```

### Тест 2: Отказы
```bash
# Шаг 1: Мягкий отказ
curl -X POST http://localhost:8000/chat \
  -d '{"user_id":"test_refusal","message":"Спасибо, я подумаю"}'
# Ожидание: CTA блокированы на 3 сообщения

# Шаг 2-4: Следующие сообщения без CTA
# Шаг 5: CTA снова появляются, но реже
```

### Тест 3: Вариативность
```bash
# 5 запросов подряд с price_sensitive контекстом
for i in {1..5}; do
  curl -X POST http://localhost:8000/chat \
    -d '{"user_id":"test_variety","message":"Это дорого для меня"}'
done
# Ожидание: 5 разных формулировок CTA
```

## 📊 Метрики успеха

1. **Уместность CTA:** 0% неуместных предложений после оплаты
2. **Уважение отказов:** 100% блокировка после явного отказа
3. **Вариативность:** минимум 5 уникальных CTA на каждый сигнал
4. **Конверсия:** ожидаемый рост на 15-20% за счёт персонализации

## ⚠️ Важные замечания

1. **Персистентность:** Все трекеры должны сохранять данные на диск
2. **GDPR:** Данные о действиях пользователей - персональные, нужно согласие
3. **Производительность:** Кэшировать часто используемые данные в памяти
4. **Fallback:** Всегда иметь запасной вариант если трекеры сломались

## 🚀 Дополнительные улучшения (будущее)

1. **ML-модель** для предсказания оптимального момента CTA
2. **A/B тестирование** разных формулировок с автовыбором лучших
3. **Эмоциональный анализ** для тонкой настройки силы CTA
4. **Интеграция с CRM** для синхронизации реальных статусов

---

**Статус:** Готов к реализации  
**Время на внедрение:** ~3 часа  
**Сложность:** Средняя  
**Риски:** Минимальные (все изменения обратимы)  
**ROI:** Высокий (ожидаемый рост конверсии 15-20%)