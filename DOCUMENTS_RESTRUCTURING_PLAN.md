# План реструктуризации документов Ukido - Инструкция для следующей сессии

**Версия:** 1.0  
**Дата создания:** 31.08.2025  
**Цель:** Преобразовать монолитные документы в структурированную систему знаний для улучшения контекстного понимания

## 🎯 Главная задача

Преобразовать текущие документы из `data/documents_compressed/` в новую структуру, которая позволит:
1. Устранить противоречия в данных
2. Обеспечить контекстный выбор курса
3. Поддержать множественных детей в диалоге
4. Сохранить backward compatibility

## 📁 Целевая структура директорий

```
data/
├── documents_compressed/       # ОСТАВЛЯЕМ для backward compatibility
│   └── [существующие файлы]
│
├── structured_knowledge/       # НОВАЯ структура
│   ├── courses/
│   │   ├── young_speaker/
│   │   │   ├── metadata.yaml
│   │   │   ├── description.md
│   │   │   ├── methodology.md
│   │   │   ├── results.md
│   │   │   └── requirements.md
│   │   ├── emotional_compass/
│   │   │   └── [аналогичная структура]
│   │   └── project_captain/
│   │       └── [аналогичная структура]
│   │
│   ├── rules/
│   │   ├── course_selection.yaml
│   │   ├── pricing_rules.yaml
│   │   ├── discount_logic.yaml
│   │   └── age_mapping.yaml
│   │
│   ├── contexts/
│   │   ├── parent_anxious.md
│   │   ├── parent_ready_to_buy.md
│   │   ├── parent_price_sensitive.md
│   │   └── parent_exploring.md
│   │
│   ├── facts/
│   │   ├── school_info.yaml
│   │   ├── location.yaml
│   │   ├── schedule.yaml
│   │   └── teachers.yaml
│   │
│   └── graph/
│       ├── entities.yaml
│       ├── relationships.yaml
│       └── priorities.yaml
```

## 📋 Пошаговый алгоритм реструктуризации

### Этап 1: Анализ существующих документов (30 минут)

1. **Прочитать все файлы из `documents_compressed/`**
   ```python
   files_to_analyze = [
       "courses_detailed.md",
       "pricing.md", 
       "faq.md",
       "methodology.md",
       "conditions.md",
       "teachers_team.md",
       "safety_and_trust.md",
       "results_and_certificates.md",
       "roi_and_future_benefits.md",
       "partnership_opportunities.md",
       "course_comparison.md"  # Недавно добавленный
   ]
   ```

2. **Создать карту содержимого**
   - Какая информация где находится
   - Какие данные дублируются
   - Где есть противоречия

### Этап 2: Извлечение структурированных данных (1 час)

#### 2.1 Создать metadata.yaml для каждого курса

**Файл:** `structured_knowledge/courses/young_speaker/metadata.yaml`
```yaml
course_id: young_speaker
name: "Юный Оратор"
age_range:
  min: 7
  max: 10
  optimal: [7, 8]  # Оптимальный возраст
  acceptable: [9, 10]  # Допустимый, но есть альтернативы
  
group_size:
  standard: 6  # Унифицированный размер
  original: 8  # Исходный размер (для справки)
  
price:
  monthly: 6000
  full_course: 18000
  currency: "UAH"
  
duration:
  months: 3
  lessons: 24
  lesson_minutes: 90
  per_week: 2
  
schedule:
  times: ["17:00", "19:00"]
  days: ["weekdays", "saturday"]
  
homework:
  average_minutes: 12  # Среднее между 10-15
  type: "practice_exercises"
```

#### 2.2 Извлечь описания курсов

**Файл:** `structured_knowledge/courses/young_speaker/description.md`
```markdown
# Юный Оратор - Описание курса

## Для кого
Дети 7-10 лет, которые:
- Боятся выступать публично
- Стесняются высказывать мнение
- Имеют проблемы с дикцией
- Хотят стать увереннее

## Что развиваем
- Навыки публичных выступлений
- Чёткую и выразительную речь
- Уверенность в себе
- Умение структурировать мысли

## Уникальность
Безопасная среда для первых выступлений с постепенным усложнением от парных упражнений к групповым презентациям.
```

#### 2.3 Создать правила выбора

**Файл:** `structured_knowledge/rules/course_selection.yaml`
```yaml
# Правила выбора курса на основе возраста и потребностей

selection_rules:
  - rule_id: "age_7_8_default"
    condition:
      age: [7, 8]
      problem: null
    recommendation: "young_speaker"
    confidence: 1.0
    
  - rule_id: "age_9_10_speech"
    condition:
      age: [9, 10]
      problem: ["страх выступлений", "стеснительность", "дикция"]
    recommendation: "young_speaker"
    confidence: 0.9
    
  - rule_id: "age_9_10_emotions"
    condition:
      age: [9, 10]
      problem: ["эмоции", "конфликты", "агрессия", "плач"]
    recommendation: "emotional_compass"
    confidence: 0.95
    
  - rule_id: "age_9_10_default"
    condition:
      age: [9, 10]
      problem: null
    recommendation: "emotional_compass"
    confidence: 0.8
    alternative: "young_speaker"
    
  - rule_id: "age_11_12_leadership"
    condition:
      age: [11, 12]
      problem: ["лидерство", "самостоятельность", "проекты"]
    recommendation: "project_captain"
    confidence: 0.95
    
  - rule_id: "age_11_12_emotions"
    condition:
      age: [11, 12]
      problem: ["эмоции", "незрелость", "конфликты"]
    recommendation: "emotional_compass"
    confidence: 0.85
    
  - rule_id: "age_13_14_default"
    condition:
      age: [13, 14]
      problem: null
    recommendation: "project_captain"
    confidence: 1.0

# Правила для множественных детей
multiple_children_rules:
  - rule_id: "siblings_discount"
    condition:
      children_count: ">=2"
    action: "apply_sibling_discount"
    discount_percent: 15
    
  - rule_id: "different_ages"
    condition:
      age_difference: ">3"
    action: "recommend_different_courses"
    note: "Дети с разницей больше 3 лет обычно нуждаются в разных курсах"
```

#### 2.4 Создать контекстные шаблоны

**Файл:** `structured_knowledge/contexts/parent_anxious.md`
```markdown
# Контекст: Тревожный родитель

## Индикаторы
- Использует слова: "боюсь", "переживаю", "тревожусь", "волнуюсь"
- Упоминает: "плачет", "стесняется", "боится", "замкнутый"
- Задаёт много уточняющих вопросов о безопасности

## Стиль ответа
- Начинать с эмпатии и понимания
- Подчёркивать безопасность и поддержку
- Приводить конкретные примеры успеха похожих детей
- Упоминать квалификацию преподавателей
- Предлагать пробное занятие для знакомства

## Примеры формулировок
- "Понимаем вашу тревогу, это естественно для заботливого родителя..."
- "В нашей практике много детей начинали с похожими сложностями..."
- "Преподаватели имеют психологическое образование и опыт работы с тревожными детьми..."
```

### Этап 3: Создание графа знаний (1 час)

**Файл:** `structured_knowledge/graph/entities.yaml`
```yaml
entities:
  courses:
    - id: young_speaker
      type: course
      name: "Юный Оратор"
      
    - id: emotional_compass
      type: course
      name: "Эмоциональный Компас"
      
    - id: project_captain
      type: course
      name: "Капитан Проектов"
  
  problems:
    - id: shyness
      type: problem
      name: "Стеснительность"
      keywords: ["стесняется", "застенчивый", "робкий", "тихий"]
      
    - id: public_speaking_fear
      type: problem
      name: "Страх публичных выступлений"
      keywords: ["боится выступать", "страх сцены", "волнуется у доски"]
      
    - id: emotional_instability
      type: problem
      name: "Эмоциональная нестабильность"
      keywords: ["плачет", "истерики", "не контролирует эмоции", "вспыльчивый"]
      
    - id: conflicts
      type: problem
      name: "Конфликты со сверстниками"
      keywords: ["дерётся", "ссорится", "не ладит", "конфликтует"]
      
  age_groups:
    - id: age_7_8
      type: age_group
      range: [7, 8]
      
    - id: age_9_10
      type: age_group
      range: [9, 10]
      
    - id: age_11_12
      type: age_group
      range: [11, 12]
      
    - id: age_13_14
      type: age_group
      range: [13, 14]
```

**Файл:** `structured_knowledge/graph/relationships.yaml`
```yaml
relationships:
  - from: young_speaker
    to: shyness
    type: solves
    confidence: 0.9
    
  - from: young_speaker
    to: public_speaking_fear
    type: solves
    confidence: 0.95
    
  - from: young_speaker
    to: age_7_8
    type: optimal_for
    confidence: 1.0
    
  - from: young_speaker
    to: age_9_10
    type: suitable_for
    confidence: 0.7
    
  - from: emotional_compass
    to: emotional_instability
    type: solves
    confidence: 0.95
    
  - from: emotional_compass
    to: conflicts
    type: solves
    confidence: 0.9
    
  - from: emotional_compass
    to: age_9_10
    type: optimal_for
    confidence: 0.9
    
  - from: emotional_compass
    to: age_11_12
    type: suitable_for
    confidence: 0.8
    
  - from: project_captain
    to: age_11_12
    type: optimal_for
    confidence: 0.9
    
  - from: project_captain
    to: age_13_14
    type: optimal_for
    confidence: 1.0
```

### Этап 4: Миграция общей информации (30 минут)

**Файл:** `structured_knowledge/facts/school_info.yaml`
```yaml
school:
  name: "Ukido"
  type: "Детская онлайн-школа soft skills"
  location:
    office: "Киев, ул. Саксаганского 121, офис 305"
    metro: "Университет"
    purpose: "Только для консультаций"
    note: "Обучение 100% онлайн"
    
  format:
    type: "online"
    platform: "Zoom"
    group_size: 6  # Унифицированный размер
    
  parking:
    free_spots: 5
    paid_nearby: true
    
  license:
    number: "№12345"
    issued_by: "МОН Украины"
    date: "01.01.2023"
    validity: "бессрочно"
```

### Этап 5: Создание индексов и связей (30 минут)

**Файл:** `structured_knowledge/indexes.yaml`
```yaml
# Индексы для быстрого поиска

by_age:
  7: [young_speaker]
  8: [young_speaker]
  9: [young_speaker, emotional_compass]
  10: [young_speaker, emotional_compass]
  11: [emotional_compass, project_captain]
  12: [emotional_compass, project_captain]
  13: [project_captain]
  14: [project_captain]

by_problem:
  shyness: [young_speaker]
  public_speaking: [young_speaker]
  emotions: [emotional_compass]
  conflicts: [emotional_compass]
  leadership: [project_captain]
  projects: [project_captain]

by_price:
  budget: [young_speaker]  # 6000
  medium: [emotional_compass]  # 7000
  premium: [project_captain]  # 8000
```

### Этап 6: Создание адаптеров для backward compatibility (30 минут)

**Файл:** `structured_knowledge/adapters.py`
```python
class DocumentAdapter:
    """
    Адаптер для поддержки старого кода, который ожидает 
    documents_compressed/*.md файлы
    """
    
    def get_document(self, doc_name: str) -> str:
        """
        Возвращает документ в старом формате, 
        собирая его из новой структуры
        """
        if doc_name == "courses_detailed.md":
            return self._build_courses_detailed()
        elif doc_name == "pricing.md":
            return self._build_pricing()
        # и так далее...
        
    def _build_courses_detailed(self) -> str:
        """Собирает courses_detailed.md из новых структур"""
        young_speaker = self._load_course("young_speaker")
        emotional_compass = self._load_course("emotional_compass")
        project_captain = self._load_course("project_captain")
        
        return f"""
# КУРСЫ UKIDO

## ЮНЫЙ ОРАТОР (7-10 лет)
{young_speaker}

## ЭМОЦИОНАЛЬНЫЙ КОМПАС (9-12 лет)
{emotional_compass}

## КАПИТАН ПРОЕКТОВ (11-14 лет)
{project_captain}
"""
```

## ⚠️ Критические моменты

### 1. НЕ УДАЛЯТЬ старые документы
- Оставить `documents_compressed/` без изменений
- Новая структура должна работать параллельно

### 2. Валидация данных
После каждого этапа проверять:
- Нет ли потери информации
- Все ли факты перенесены
- Сохранилась ли консистентность

### 3. Приоритеты
1. Сначала курсы (самое важное)
2. Потом правила выбора
3. Потом контексты
4. В последнюю очередь - общая информация

### 4. Тестирование
После каждого курса:
```python
# Проверить, что старый код всё ещё работает
response = router.route("Что есть для 9-летнего?")
assert "emotional_compass" in response["documents"]

# Проверить новую структуру
course = load_yaml("courses/emotional_compass/metadata.yaml")
assert course["age_range"]["min"] == 9
```

## 📊 Ожидаемые результаты

### После реструктуризации:
1. ✅ Один источник правды для каждого факта
2. ✅ Чёткие правила выбора курса
3. ✅ Контекстные шаблоны для разных типов родителей
4. ✅ Граф знаний для навигации
5. ✅ Backward compatibility через адаптеры

### Метрики успеха:
- Нет противоречий в размерах групп
- Правильный выбор курса в 95% случаев
- Поддержка множественных детей
- Старый код продолжает работать

## 🚀 Порядок выполнения в следующей сессии

1. **Начать с этого файла** - прочитать и понять план
2. **Создать структуру директорий** - все папки из схемы
3. **Мигрировать Юный Оратор** - как пилотный курс
4. **Проверить работоспособность** - старый код должен работать
5. **Мигрировать остальные курсы** - по той же схеме
6. **Создать правила и граф** - на основе мигрированных данных
7. **Написать адаптеры** - для backward compatibility
8. **Протестировать всё вместе** - старое и новое

## 📝 Заметки для реализатора

- Используй YAML для структурированных данных (легче читать/редактировать)
- Markdown для текстовых описаний
- Сохраняй все оригинальные данные, даже если кажутся избыточными
- Документируй все неоднозначности и принятые решения
- При сомнениях - сохраняй оба варианта с пометкой

---

**Время выполнения:** 4-5 часов
**Сложность:** Средняя
**Риски:** Минимальные (backward compatibility)