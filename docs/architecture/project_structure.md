# Ukido AI Assistant - Project Structure
*Generated on 2025-08-15*

## 📁 Directory Structure

```
Ukido_DynContInj/
│
├── 📂 .claude/                    # Claude Code configuration
│   └── commands/                   # Custom slash commands
│       ├── primer.md              # Project primer command
│       └── tree.md                # Tree visualization command
│
├── 📂 src/                        # Source code (core pipeline)
│   ├── main.py                    # Main FastAPI orchestrator
│   ├── router.py                  # Gemini router (intent classification)
│   ├── response_generator.py     # Claude generator (final responses)
│   ├── social_responder.py       # Social response generation
│   ├── social_state.py           # Session greeting tracking
│   ├── social_intents.py         # Social intent definitions
│   ├── history_manager.py        # Dialog history management
│   ├── standard_responses.py     # Pre-defined offtopic responses
│   ├── config.py                  # System configuration
│   ├── models.py                  # Data models
│   ├── openrouter_client.py      # OpenRouter API client
│   └── gemini_cached_client.py   # Gemini API client with caching
│
├── 📂 data/                       # Knowledge base
│   ├── documents/                 # Original documents
│   │   ├── courses_detailed.md
│   │   ├── pricing.md
│   │   ├── faq.md
│   │   ├── conditions.md
│   │   ├── teachers_team.md
│   │   ├── methodology.md
│   │   ├── ukido_philosophy.md
│   │   ├── safety_and_trust.md
│   │   └── roi_and_future_benefits.md
│   ├── documents_compressed/      # Compressed versions for prompts
│   └── summaries.json            # Document summaries
│
├── 📂 tests/                      # Test suite
│   ├── test_scenarios_stress.json # Stress test scenarios
│   ├── test_fullchain_with_report.py
│   ├── test_stress_with_report.py
│   ├── test_memory_v2.py
│   └── reports/                   # Test reports
│       └── old/                   # Historical reports
│
├── 📂 docs/                       # Documentation
│   ├── design.md
│   ├── progress.md
│   ├── requirements.md
│   └── router_spec.md
│
├── 📂 scripts/                    # Utility scripts
│   └── analyze_test_results.py
│
├── 📄 Core Files
│   ├── CLAUDE.md                  # Main project context for Claude
│   ├── CLAUDE_history.md          # Version history
│   ├── Sandbox_testing.md         # Testing sandbox documentation
│   ├── requirements.txt           # Python dependencies
│   ├── .env                       # Environment variables (not in git)
│   └── tach.toml                  # Tach configuration
│
├── 📄 Testing Tools
│   ├── sandbox_v2.py              # Interactive testing sandbox
│   ├── collaborative_test.py     # Collaborative testing framework
│   ├── interactive_test.py       # Interactive REPL testing
│   ├── cost_tracker.py           # Cost tracking utilities
│   └── golden_responses.py       # Golden response management
│
├── 📄 Architecture Files
│   ├── architecture_diagram.md
│   ├── architecture_interactive.html
│   ├── simple_architecture.md
│   └── Autonomous_System_Optimization.md
│
└── 📄 Test Scripts (Various)
    ├── test_mama_blogger.py
    ├── test_mixed_greetings.py
    ├── test_new_architecture.py
    └── [other test files...]
```

## 🏗️ Architecture Overview

### Core Pipeline (2 components)
1. **Gemini Router** (`src/router.py`)
   - Intent classification
   - Document selection
   - Social context detection
   - Offtopic handling

2. **Claude Generator** (`src/response_generator.py`)
   - Final response generation
   - Style: from school perspective ("мы")
   - 100-150 word responses

### Key Features
- **No Quick Regex** (removed in v0.7.1)
- **History Management**: Last 10 messages
- **Social State Tracking**: Per-session greetings
- **Document Retrieval**: Smart selection from knowledge base
- **Cost Optimization**: ~$0.0015 per response

### Testing Infrastructure
- **Sandbox V2**: Interactive collaborative debugging
- **Stress Tests**: 10 comprehensive scenarios
- **Performance Metrics**: Latency, cost, quality tracking
- **Golden Responses**: Regression detection

## 📊 Statistics
- **Total Python files**: ~30
- **Test scenarios**: 10 stress tests
- **Documents**: 13 knowledge base files
- **Architecture version**: 0.7.3
- **Response time**: 7-10 seconds average
- **Cost per query**: ~$0.0015

## 🔧 Development Tools
- **Language**: Python 3.x
- **Framework**: FastAPI
- **LLMs**: Gemini 2.5 Flash, Claude 3.5 Haiku
- **Testing**: pytest, custom sandbox
- **Version Control**: Git (not initialized yet)