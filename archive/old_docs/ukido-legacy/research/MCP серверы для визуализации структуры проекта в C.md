<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# MCP серверы для визуализации структуры проекта в Claude Code

## 🎯 Идеальные решения для вашей задачи

**Отличная новость!** Есть несколько готовых MCP серверов именно для визуализации архитектуры проектов из-под Claude Code.

### 1. **C4 PlantUML MCP Server** — архитектурные диаграммы ⭐⭐⭐⭐⭐

**Что это:** MCP сервер для создания архитектурных диаграмм через естественный язык[^1]

**Установка:**

```bash
git clone https://github.com/tarastclair/c4-plantuml-mcp-server
cd c4-plantuml-mcp-server
npm install && npm run build
```

**Конфигурация Claude Code:**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/your/project"]
    },
    "c4-plantuml": {
      "command": "node", 
      "args": ["path/to/c4-plantuml-mcp-server/build/index.js"]
    }
  }
}
```

**Что получите:**

- **Context диаграммы** — высокоуровневый обзор системы[^1]
- **Container диаграммы** — детализация компонентов[^1]
- **Component диаграммы** — внутренняя архитектура[^1]
- **Автогенерация PNG** из PUML файлов[^1]


### 2. **Dependency Analysis MCP Server** — граф зависимостей ⭐⭐⭐⭐⭐

**Что это:** Анализ структуры кода с генерацией графов зависимостей[^2]

**Установка:**

```bash
npm install dependency-mcp-server
npm run build
```

**Конфигурация:**

```json
{
  "mcpServers": {
    "DependencyMCP": {
      "command": "node",
      "args": ["path/to/dependency-mcp/dist/index.js"],
      "env": {
        "MAX_LINES_TO_READ": "1000",
        "CACHE_DIR": ".dependency-cache",
        "CACHE_TTL": "3600000"
      }
    }
  }
}
```

**Инструменты:**

- **`analyze_dependencies`** — граф зависимостей всего проекта
- **`get_dependency_graph`** — экспорт в JSON или DOT формат[^2]
- **`get_file_metadata`** — детальная информация по файлу[^2]
- **`get_architectural_score`** — оценка архитектуры[^2]


### 3. **Code Analysis MCP с Neo4j** — глубокий анализ ⭐⭐⭐⭐

**Что это:** Комплексный анализ кода через граф базу данных[^3]

**Возможности:**

- **Анализ качества кода** — complexity, duplication, coverage[^3]
- **Структурный анализ** — call graphs, dependency maps[^3]
- **Естественные вопросы** — "покажи все классы связанные с авторизацией"[^3]

**Требования:**

- Neo4j база данных
- Python с зависимостями


## 🚀 Практический пример использования

### Быстрый старт с C4 PlantUML:

**1. Попросите Claude Code проанализировать ваш проект:**

```
Проанализируй структуру моего Python проекта и создай Context диаграмму C4 показывающую основные компоненты и их взаимодействия
```

**2. Claude автоматически:**

- Прочитает файлы через filesystem MCP
- Определит архитектуру
- Создаст .puml файл
- Сгенерирует PNG диаграмму

**3. Получите интерактивные диаграммы:**

- Context (система в целом)
- Container (сервисы/модули)
- Component (классы/функции)
- Code (детали реализации)[^1]


### Dependency Analysis в действии:

```
Проанализируй зависимости в моем проекте и покажи:
1. Граф импортов между модулями
2. Циклические зависимости  
3. Архитектурные проблемы
```

**Claude выдаст:**

- Визуальный граф в DOT формате[^2]
- JSON с метаданными[^2]
- Оценку архитектуры[^2]
- Рекомендации по улучшению[^2]


## 📊 Альтернативные MCP серверы

### 4. **Code Documentation MCP** (AWS)

- Автоматическое создание документации[^4]
- Анализ через repomix[^4]
- Структурированные планы документации[^4]


### 5. **AntV Chart MCP Server**

- **25+ типов диаграмм** для визуализации данных[^5]
- Интеграция с популярными форматами[^5]
- Экспорт в различные форматы[^5]


### 6. **Python Code Graph Extraction MCP**

- Специализирован на **Python проектах**[^6]
- Анализ import/export связей[^6]
- Легковесная реализация[^6]


## 🛠️ Быстрая установка (рекомендованный путь)

### Для начала — C4 PlantUML:

```bash
# 1. Установка
git clone https://github.com/tarastclair/c4-plantuml-mcp-server
cd c4-plantuml-mcp-server
npm install && npm run build

# 2. Добавление в Claude Code
claude mcp add c4-plantuml --scope local node build/index.js
claude mcp add filesystem --scope local npx -y @modelcontextprotocol/server-filesystem /path/to/your/project

# 3. Проверка
claude mcp list
```


### Использование:

```
Создай архитектурную диаграмму моего проекта показывая:
- Основные модули и их назначение  
- Потоки данных между компонентами
- Внешние зависимости и API
```

Claude автоматически создаст красивые диаграммы и сохранит их как PNG файлы.

**Результат:** вы получите **профессиональные архитектурные диаграммы** прямо из Claude Code без необходимости изучать PlantUML синтаксис или пользоваться внешними сервисами!

<div style="text-align: center">⁂</div>

[^1]: https://lobehub.com/mcp/tarastclair-c4-plantuml-mcp-server

[^2]: https://playbooks.com/mcp/mkearl-dependency-tracker

[^3]: https://playbooks.com/mcp/davidvc-code-analysis

[^4]: https://awslabs.github.io/mcp/servers/code-doc-gen-mcp-server

[^5]: https://github.com/antvis/mcp-server-chart

[^6]: https://lobehub.com/mcp/yourusername-python-mcp-new

[^7]: https://towardsdatascience.com/model-context-protocol-mcp-tutorial-build-your-first-mcp-server-in-6-steps/

[^8]: https://milvus.io/ai-quick-reference/can-claude-code-generate-diagrams-or-visualizations

[^9]: https://docs.anthropic.com/en/docs/claude-code/mcp

[^10]: https://www.youtube.com/watch?v=xuhmyPaHKe8

[^11]: https://zapier.com/blog/how-to-use-claude-artifacts-to-visualize-data/

[^12]: https://apidog.com/blog/how-to-quickly-build-a-mcp-server-for-claude-code/

[^13]: https://github.com/modelcontextprotocol/servers

[^14]: https://www.reddit.com/r/ClaudeAI/comments/1hnejza/instantly_visualize_any_codebase_as_an/

[^15]: https://modelcontextprotocol.io/docs/concepts/architecture

[^16]: https://www.reddit.com/r/ClaudeAI/comments/1jxdlzj/simple_visualization_of_model_context_protocol_mcp/

[^17]: https://developers.flow.com/tutorials/ai-plus-flow/claude-code

[^18]: https://github.com/JudiniLabs/mcp-code-graph

[^19]: https://github.com/modelcontextprotocol/inspector

[^20]: https://www.anthropic.com/news/analysis-tool

[^21]: https://www.anthropic.com/engineering/claude-code-best-practices

[^22]: https://blog.dailydoseofds.com/p/visual-guide-to-model-context-protocol

[^23]: https://www.flexos.work/leadwithai/in-5-steps-build-a-data-visualization-generator-with-claude-artifacts

[^24]: https://dev.to/rushier/how-to-use-claude-ai-drawio-to-create-architecture-diagrams-for-projects-17i1

[^25]: https://modelcontextprotocol.io/examples

[^26]: https://memgraph.com/blog/introducing-memgraph-mcp-server

[^27]: https://www.youtube.com/watch?v=vzGkSn59rDU

[^28]: https://lobehub.com/mcp/xoniks-mcp-visualization-duckdb

[^29]: https://dev.to/copilotkit/30-mcp-ideas-with-complete-source-code-d8e

[^30]: https://mcpservers.org

[^31]: https://www.youtube.com/watch?v=fLKH8HefqSo

[^32]: https://docs.anthropic.com/en/docs/claude-code/sdk

[^33]: https://github.com/punkpeye/awesome-mcp-servers

[^34]: https://github.com/zilliztech/claude-context

[^35]: https://github.com/github/github-mcp-server

