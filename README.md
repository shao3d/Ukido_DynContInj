# 🤖 Ukido AI Assistant

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Production-ready AI chatbot for Ukido soft skills school with multilingual support, real-time streaming interface, and HubSpot CRM integration.

## 🎯 Key Features

### Core Capabilities
- **🌐 Multilingual Support**: Russian, Ukrainian, and English with real-time translation
- **💬 Web Chat Interface**: Beautiful SSE-powered chat with live streaming responses
- **🤖 Two-stage AI Architecture**: Gemini for routing + Claude for generation
- **😄 Zhvanetsky Humor Engine**: Context-aware humor for offtopic queries (80% probability)
- **💾 State Persistence**: Full conversation history and user state preservation
- **🐳 Docker Ready**: One-click deployment with Railway support
- **🎯 HubSpot CRM Integration**: Automated trial lesson signup and contact management

### Technical Features
- **Smart Intent Classification**: Business, social, and mixed intents handling
- **Adaptive Tone System**: 4 user emotional states (ready_to_buy, anxiety, price_sensitive, exploring)
- **CTA Intelligence**: Smart call-to-action blocking based on user behavior
- **Context Memory**: Maintains last 10 messages with offtopic filtering
- **Protected Terms**: Preserves brand names during translation (Ukido, soft skills, Zoom)
- **HubSpot API**: Direct integration with HubSpot CRM for contact creation/updates
- **Production Pipeline**: Chat → CTA → Trial Form → Railway → HubSpot CRM
- **Optimized Performance**: 5-7 seconds response time, ~$0.0015 per query

## 🏗️ Architecture

### System Architecture (v0.17.0)
```mermaid
graph TB
    subgraph "Frontend"
        U[👤 Parent User<br/>RU/UK/EN]
        W[🌐 Web Interface<br/>SSE Streaming]
        TF[📝 Trial Form<br/>GitHub Pages]
    end

    subgraph "API Layer"
        API[FastAPI Server<br/>ukidoschool.up.railway.app<br/>SSE + REST]
    end

    subgraph "AI Processing"
        R[🤖 Gemini 2.5 Flash<br/>Router & Classifier<br/>$0.30/1M tokens]
        G[🤖 Claude 3.5 Haiku<br/>Response Generator<br/>$0.25/$1.25/1M tokens]
    end

    subgraph "Core Components"
        SD[Social Detector<br/>50+ patterns]
        HM[History Manager<br/>10 messages context]
        SS[Social State<br/>User tracking]
        SR[Social Responder<br/>Local generation]
        ZH[🎭 Zhvanetsky Humor<br/>80% probability]
        TR[🌍 Translator<br/>RU/UK/EN support]
        CB[CTA Blocker<br/>Smart filtering]
        HS[🎯 HubSpot Client<br/>CRM Integration]
    end

    subgraph "Knowledge Base"
        KB[(Documents<br/>13 MD files<br/>Fuzzy matching 85%)]
        SM[Summaries.json<br/>Quick search]
    end

    subgraph "Persistence"
        PM[State Manager<br/>User sessions]
    end

    subgraph "External Services"
        HB[(HubSpot CRM<br/>Contact Management)]
    end

    U -->|SSE/REST| W
    W -->|POST /chat| API
    TF -->|POST /trial-signup| API
    API -->|Route| R

    R --> SD
    R --> HM
    R --> SS
    R --> KB
    R --> SM

    R -->|Business query| G
    R -->|Social only| SR
    R -->|Offtopic| ZH

    G --> HM
    G --> TR
    G --> CB
    G --> PM

    API -->|Create Contact| HS
    HS --> HB

    API -->|Stream/JSON| W
    W -->|Real-time| U
    G -->|CTA → Trial Form| TF

    style HB fill:#ffecb3
    style HS fill:#e8f5e9
    
    style U fill:#e1f5fe
    style W fill:#c5e1a5
    style API fill:#fff3e0
    style R fill:#f3e5f5
    style G fill:#f3e5f5
    style KB fill:#e8f5e9
    style ZH fill:#ffecb3
    style TR fill:#b3e5fc
```

### Request Flow (v0.17.0)
```mermaid
sequenceDiagram
    participant U as 👤 Parent
    participant W as 🌐 Web UI
    participant TF as 📝 Trial Form
    participant API as FastAPI Server
    participant T as 🌍 Translator
    participant R as Gemini Router
    participant SR as Social Responder
    participant ZH as 🎭 Zhvanetsky
    participant G as Claude Generator
    participant HS as 🎯 HubSpot Client
    participant KB as Knowledge Base
    participant HB as 🎯 HubSpot CRM

    U->>+W: Type message (RU/UK/EN)
    W->>+API: POST /chat (SSE stream)
    API->>+T: Detect language
    T-->>API: Language detected

    API->>+R: Route message

    alt Pure Social (30-40% queries)
        Note over R: Social intent ≥0.7<br/>No business signals
        R->>SR: Generate local response
        SR-->>R: Social response (1-2 sec)
        R-->>API: {"status": "offtopic", "message": "..."}
    else Mixed/Business Query
        R->>KB: Search documents
        KB-->>R: Relevant docs + summaries

        alt Business query
            R-->>API: RouterResponse (success)
            API->>+G: Generate with context
            Note over G: - History: 10 messages<br/>- Emotional state<br/>- CTA blocking<br/>- 100-150 words
            G-->>-API: Generated response with CTA
            API->>T: Translate if needed
            T-->>API: Final language
            API-->>-W: Stream response (SSE)
            W-->>-U: Display real-time + CTA
            U->>+TF: Click CTA → Trial Form
            TF->>+API: POST /trial-signup
            API->>+HS: Create/Update HubSpot Contact
            HS->>+HB: API call to HubSpot CRM
            HB-->>HS: Contact created/updated
            HS-->>API: Success response
            API-->>TF: {"success": true, "contact_id": "..."}
            TF-->>U: "Спасибо за заявку!"
        else Offtopic (non-social)
            R->>ZH: Generate humor (80%)
            ZH-->>R: Zhvanetsky response
            R-->>API: {"status": "offtopic", "message": "..."}
        end
    end

    Note over U: Pure Social: 1-2 sec, ~$0.00003<br/>Business: 5-7 sec, ~$0.0015<br/>Trial signup: <1 sec<br/>Savings: 40% on API costs
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- API Key for OpenRouter (required)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/shao3d/Ukido_DynContInj.git
cd Ukido_DynContInj
```

2. Install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys:
# OPENROUTER_API_KEY=sk-or-v1-xxxxx
# HUBSPOT_PRIVATE_APP_TOKEN=pat-eu1-xxxxx
# HUBSPOT_PORTAL_ID=1234567
```

4. Run the server:
```bash
python src/main.py
```

5. Open the web interface:
- **Web Chat**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 🐳 Docker Deployment

```bash
# Build and run with Docker
docker build -t ukido-assistant .
docker run -p 8000:8000 --env-file .env ukido-assistant
```

### 🌐 Production Deployment (Railway)

1. **Deploy to Railway**:
   ```bash
   git push origin main
   # Railway will auto-detect and deploy
   ```

2. **Configure Environment Variables** in Railway:
   ```
   OPENROUTER_API_KEY=sk-or-v1-xxxxx
   HUBSPOT_PRIVATE_APP_TOKEN=pat-eu1-xxxxx
   HUBSPOT_PORTAL_ID=1234567
   ```

3. **Access the application**:
   - **Chat**: https://ukidoschool.up.railway.app
   - **Trial Form**: https://shao3d.github.io/trial/
   - **API Docs**: https://ukidoschool.up.railway.app/docs

## 📡 API Endpoints

### Core Chat API
- **`POST /chat`** - Main chat endpoint
  - Request: `{"user_id": "string", "message": "string"}`
  - Response: `{"response": "string", "intent": "string", "user_signal": "string", "humor_generated": bool}`

### Trial Signup API
- **`POST /trial-signup`** - HubSpot CRM integration
  - Request: `{"firstName": "string", "lastName": "string", "email": "string", "phone": "string"}`
  - Response: `{"success": bool, "message": "string", "contact_id": "string", "action": "string"}`

### System Endpoints
- **`GET /chat/stream`** - SSE streaming for real-time responses
- **`GET /health`** - Health check endpoint
- **`GET /metrics`** - System performance metrics

## 🧪 Testing

### Interactive Sandbox
```bash
# Interactive mode
python sandbox_v2.py

# Test single message
python sandbox_v2.py -m "Привет! Какие курсы есть?"

# Run automated tests
python sandbox_v2.py --test
```

### Stress Testing
```bash
python tests/test_stress_with_report.py
```

### Dialogue Testing
```bash
python collaborative_test.py 1  # By scenario number
python collaborative_test.py "Забывчивая бабушка"  # By name
```

## 📊 Architecture Diagrams

### 🎨 Интерактивные визуализации:
- **[Простые диаграммы](https://shao3d.github.io/Ukido_DynContInj/simple-diagrams.html)** - чистый Mermaid.js без зависимостей
- **[Конвертер в Excalidraw](https://shao3d.github.io/Ukido_DynContInj/mermaid-to-excalidraw.html)** - превратите диаграммы в рисунки
- **[Интерактивные диаграммы](https://shao3d.github.io/Ukido_DynContInj/)** - с zoom и навигацией (экспериментальная)
- **[GitDiagram](https://gitdiagram.com/shao3d/Ukido_DynContInj)** - автоматическая визуализация структуры репозитория

### Processing States (v0.17.0)
```mermaid
stateDiagram-v2
    [*] --> Initial: User sends message
    Initial --> LanguageDetection: Detect RU/UK/EN
    LanguageDetection --> SocialCheck: Analyze intent

    SocialCheck --> PureSocial: Confidence ≥0.7 & No business
    SocialCheck --> MixedIntent: Social + Business signals
    SocialCheck --> BusinessIntent: Pure business query

    PureSocial --> LocalResponse: Social Responder
    LocalResponse --> Translation: Check language
    Translation --> [*]: Stream response (1-2 sec)

    MixedIntent --> RouterProcessing: Gemini Router
    BusinessIntent --> RouterProcessing: Gemini Router

    RouterProcessing --> DocumentSearch: Find relevant docs
    DocumentSearch --> Classification: Classify query type

    Classification --> Success: Valid business query
    Classification --> Offtopic: Non-school topic
    Classification --> Simplification: Too complex

    Success --> GenerateResponse: Claude Generator
    GenerateResponse --> EmotionalState: Apply user state
    EmotionalState --> CTABlocking: Check CTA rules
    CTABlocking --> Translation2: Translate if needed
    Translation2 --> [*]: Stream response (5-7 sec)

    Success --> CTA: Insert trial lesson link
    CTA --> TrialForm: User fills form
    TrialForm --> TrialSignup: POST /trial-signup
    TrialSignup --> HubSpotAPI: Create contact
    HubSpotAPI --> [*]: Success response

    Offtopic --> ZhvanetskyCheck: 80% probability
    ZhvanetskyCheck --> HumorGeneration: Generate humor
    ZhvanetskyCheck --> StandardResponse: Use template
    HumorGeneration --> [*]: Return humor response
    StandardResponse --> [*]: Return standard message

    Simplification --> GenerateResponse: Simplified context
```

### Query Distribution (v0.17.0)
```mermaid
pie title "Query Types Distribution (Based on Testing)"
    "Business queries (courses/prices)" : 30
    "Social intents (greetings/thanks)" : 35
    "Mixed (social + business)" : 15
    "Schedule & timing questions" : 8
    "Teacher information" : 5
    "Offtopic with humor" : 5
    "Trial lesson signups" : 2
    "Complex multi-questions" : 0
```

### Data Structure (v0.17.0)
```mermaid
erDiagram
    USER ||--o{ MESSAGE : sends
    USER ||--|| USER_STATE : maintains
    USER ||--|| HISTORY : tracks
    MESSAGE ||--|| LANGUAGE : detected_in
    MESSAGE ||--|| SOCIAL_INTENT : contains
    MESSAGE ||--|| ROUTER_RESULT : processed_by
    ROUTER_RESULT ||--|| CLASSIFICATION : produces
    ROUTER_RESULT ||--o{ DOCUMENT : searches
    CLASSIFICATION ||--|| RESPONSE_TYPE : determines
    RESPONSE_TYPE ||--|| GENERATOR : routes_to
    GENERATOR ||--|| RESPONSE : creates
    RESPONSE ||--|| TRANSLATION : may_require
    RESPONSE ||--|| STREAMING : delivered_via
    HISTORY ||--o{ MESSAGE : stores_last_10
    USER_STATE ||--|| EMOTIONAL_STATE : includes
    EMOTIONAL_STATE ||--|| CTA_BLOCKING : influences

    USER {
        string user_id
        string language_preference
        timestamp last_greeting
        int message_count
    }

    MESSAGE {
        string content
        string language
        timestamp created_at
        float social_confidence
    }

    RESPONSE {
        string content
        string status
        float cost
        int response_time_ms
    }

    CONTACT {
        string contact_id
        string email
        string firstName
        string lastName
        string phone
        timestamp created_at
    }
```

The architecture diagrams above are created using Mermaid and are automatically rendered by GitHub in the README.
For high-resolution PNG versions, check the `docs/diagrams/` folder.

## 📁 Project Structure

```
├── src/
│   ├── main.py              # FastAPI server & orchestrator
│   ├── router.py             # Gemini intent classifier
│   ├── response_generator.py # Claude response generator
│   ├── hubspot_client.py     # 🆕 HubSpot CRM API client
│   ├── history_manager.py    # Conversation history
│   └── social_state.py       # Social intent tracking
├── data/
│   ├── persistent_states/      # User session persistence
│   └── documents_compressed/   # Knowledge base (13 documents)
├── tests/
│   ├── integration/          # Integration tests
│   └── reports/              # Test reports
├── docs/
│   ├── architecture/         # Architecture documentation
│   └── diagrams/            # Auto-generated diagrams
├── sandbox_v2.py            # Interactive testing tool
└── trial/                   # 🆕 Trial lesson form (GitHub Pages)
```

## 🔧 Configuration

Key settings in `src/config.py`:
- `HISTORY_LIMIT = 10` - Messages to keep in context
- `TEMPERATURE = 0.7` - Response creativity
- `USE_QUICK_REGEX = False` - Regex pre-processing (disabled)

## 📈 Performance Metrics

- **Response Time**: 5-7 seconds average
- **Cost**: ~$0.0015 per interaction
- **Accuracy**: 95%+ intent classification
- **Context Retention**: Last 10 messages

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 Version History

- **v0.17.0** (2025-10-16): 🎯 **HubSpot CRM Integration** - Full trial signup automation
  - POST /trial-signup endpoint with HubSpot API integration
  - Production pipeline: Chat → CTA → Trial Form → Railway → HubSpot CRM
  - GitHub Pages trial form integration (shao3d.github.io/trial/)
  - Contact creation/update with ID tracking
  - Railway deployment with environment variables
- **v0.16.1** (2025-01-10): Full multilingual support (RU/UK/EN) with streaming translation
- **v0.15.0** (2025-01-07): SSE web interface and Docker deployment
- **v0.14.x**: Production optimizations and bug fixes
- **v0.13.x**: Zhvanetsky humor engine integration
- **v0.12.x**: State persistence and advanced CTA blocking
- Earlier versions: Initial architecture and core features

## 🌿 Branch Structure

- **main**: Latest stable version with all features
- **feature/multilingual-v2**: Active development (merged)
- **archive/***: Historical feature branches for reference

## 🏫 About Ukido

Ukido is a soft skills school for children aged 7-14, focusing on emotional intelligence, leadership, and communication skills development.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Ukido team for domain expertise
- OpenRouter for Claude API access
- Google AI for Gemini API
- FastAPI community for the excellent framework

---

**Built with ❤️ for better parent-school communication**