# 🏗️ Архитектура Ukido AI Assistant v0.7.6

## 📊 Полная диаграмма архитектуры

```mermaid
graph TB
    %% Стили
    classDef client fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef api fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef router fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef generator fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef storage fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef knowledge fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef helper fill:#e0f2f1,stroke:#004d40,stroke-width:2px
    classDef external fill:#ffebee,stroke:#b71c1c,stroke-width:2px

    %% Клиентский уровень
    User[👤 Пользователь<br/>Родитель 7-14 лет]:::client
    
    %% API Gateway
    FastAPI[FastAPI Server<br/>main.py<br/>Port: 8000]:::api
    
    %% Основной Pipeline
    Router[🧭 Gemini Router<br/>router.py<br/>$0.30/1M токенов]:::router
    Generator[🤖 Claude Generator<br/>response_generator.py<br/>$0.25/$1.25 за 1M]:::generator
    
    %% Хранилища состояния
    History[📚 History Manager<br/>history_manager.py<br/>LIMIT: 10 messages]:::storage
    SocialState[🤝 Social State<br/>social_state.py<br/>Tracking greetings]:::storage
    
    %% База знаний
    Knowledge[(📖 Knowledge Base<br/>data/documents_compressed/<br/>13 документов)]:::knowledge
    Summaries[📋 Summaries<br/>data/summaries.json<br/>Краткие описания]:::knowledge
    
    %% Вспомогательные модули
    SocialResp[💬 Social Responder<br/>social_responder.py]:::helper
    StdResponses[📝 Standard Responses<br/>standard_responses.py]:::helper
    Config[⚙️ Config<br/>config.py]:::helper
    
    %% API клиенты
    GeminiClient[Gemini Client<br/>gemini_cached_client.py<br/>With caching]:::external
    OpenRouterClient[OpenRouter Client<br/>openrouter_client.py<br/>For Claude API]:::external
    
    %% Внешние сервисы
    GeminiAPI[Google Gemini API<br/>2.5 Flash]:::external
    ClaudeAPI[Claude API<br/>3.5 Haiku<br/>via OpenRouter]:::external

    %% Связи - Основной поток
    User -->|POST /chat| FastAPI
    FastAPI -->|1. Route request| Router
    Router -->|Check history| History
    Router -->|Check greetings| SocialState
    Router -->|Load summaries| Summaries
    Router -->|API call| GeminiClient
    GeminiClient -->|Request| GeminiAPI
    
    %% Поток Router результатов
    Router -->|success| Generator
    Router -->|offtopic + social| SocialResp
    Router -->|offtopic - social| StdResponses
    Router -->|need_simplification| StdResponses
    
    %% Generator поток
    Generator -->|Get history| History
    Generator -->|Load docs| Knowledge
    Generator -->|API call| OpenRouterClient
    OpenRouterClient -->|Request| ClaudeAPI
    
    %% Обратный поток
    Generator -->|Response| FastAPI
    SocialResp -->|Response| FastAPI
    StdResponses -->|Response| FastAPI
    FastAPI -->|JSON response| User
    
    %% Сохранение состояния
    FastAPI -->|Save message| History
    FastAPI -->|Update state| SocialState
    
    %% Конфигурация
    Config -.->|Settings| FastAPI
    Config -.->|Settings| Router
    Config -.->|Settings| Generator
```

## 🔄 Детальный Flow обработки запроса

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant R as Router
    participant G as Generator
    participant H as History
    participant S as SocialState
    participant KB as Knowledge Base

    U->>API: POST /chat {message, user_id}
    API->>H: get_history(user_id)
    H-->>API: last 10 messages
    
    API->>R: route(message, history, user_id)
    
    alt Ультра-краткий вопрос ("А?")
        R->>R: Expand from context
    end
    
    R->>S: check social state
    S-->>R: greeted/not greeted
    
    R->>R: Decompose questions
    R->>R: Group related questions
    R->>KB: Select documents (max 4)
    R->>R: Classify intent
    
    alt status = "success"
        R-->>API: {status, documents, questions, social_context}
        API->>G: generate(route_result, history)
        G->>KB: Load full documents
        G->>G: Check repeated greetings
        G->>G: Generate 100-150 words
        G-->>API: response_text
    else status = "offtopic" with social
        R-->>API: {status, message, social_context}
        API->>API: Add social prefix/suffix
        API-->>API: response_text
    else status = "offtopic" without social
        R-->>API: {status, message}
        API-->>API: standard_response
    else status = "need_simplification"
        R-->>API: {status, message}
        API-->>API: simplification_message
    end
    
    API->>H: add_message(user, assistant)
    API->>S: update_state(user_id)
    API-->>U: JSON {response, documents, intent}
```

## 📁 Структура компонентов

```mermaid
graph LR
    subgraph "Core Pipeline"
        M[main.py<br/>180 строк]
        R[router.py<br/>662 строки]
        G[response_generator.py<br/>284 строки]
    end
    
    subgraph "State Management"
        H[history_manager.py]
        S[social_state.py]
    end
    
    subgraph "Response Helpers"
        SR[social_responder.py]
        STD[standard_responses.py]
    end
    
    subgraph "API Clients"
        GC[gemini_cached_client.py]
        OC[openrouter_client.py]
    end
    
    subgraph "Configuration"
        C[config.py]
        E[.env]
    end
    
    subgraph "Knowledge Base"
        D1[courses_detailed.md]
        D2[pricing.md]
        D3[faq.md]
        D4[conditions.md]
        D5[methodology.md]
        D6[...еще 8 документов]
    end
```

## 💰 Экономическая модель

```mermaid
pie title Распределение стоимости на запрос ($0.0015)
    "Gemini Router" : 20
    "Claude Generator" : 80
```

## 🎯 Классификация запросов

```mermaid
graph TD
    Input[Входящее сообщение]
    
    Input --> Social{Социальный<br/>интент?}
    Social -->|Да, порог > 0.7| SocialCheck{Повторное<br/>приветствие?}
    SocialCheck -->|Да| RepeatGreeting[Мы уже поздоровались]
    SocialCheck -->|Нет| SocialResponse[Социальный ответ]
    
    Social -->|Нет| Business{Бизнес<br/>вопрос?}
    Business -->|Да| Decompose[Декомпозиция]
    Decompose --> Group[Группировка]
    Group --> Docs[Подбор документов]
    Docs --> Success[status: success]
    
    Business -->|Нет| Offtopic[status: offtopic]
    
    Input --> Complex{Слишком<br/>сложно?}
    Complex -->|> 3 вопросов| Simplify[status: need_simplification]
    Complex -->|<= 3 вопросов| Override[Override → success]
```

## 🔧 Конфигурационные параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| HISTORY_LIMIT | 10 | Максимум сообщений в истории |
| TEMPERATURE | 0.7 | Креативность генерации |
| SEED | 42 | Для воспроизводимости |
| SOCIAL_THRESHOLD | 0.7 | Порог для социальных интентов |
| MAX_DOCUMENTS | 4 | Максимум документов для контекста |
| RESPONSE_LENGTH | 100-150 слов | Целевая длина ответа |
| CACHE_TTL | Session | Время жизни кеша Gemini |

## 📊 Метрики производительности

```mermaid
gantt
    title Время обработки запроса (среднее)
    dateFormat X
    axisFormat %s
    
    section Pipeline
    Router (Gemini)      :active, 0, 2s
    Generator (Claude)   :active, 2, 7s
    
    section Быстрый путь
    Social in Router     :done, 0, 0.1s
```

## 🚀 Оптимизации v0.7.6

1. **Удален Quick Regex** - все через Router для консистентности
2. **Кеширование Gemini** - экономия на повторных запросах
3. **In-memory хранилища** - без БД для скорости
4. **Социалка в Router** - экономия вызовов Claude
5. **Ограничение истории** - баланс контекст/стоимость
6. **Группировка вопросов** - оптимальный подбор документов

---
*Диаграмма актуальна для версии 0.7.6 от 17.08.2025*