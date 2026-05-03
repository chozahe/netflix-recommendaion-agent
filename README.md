# Netflix Recommendation Agent

Локальная мультиагентная система рекомендаций контента Netflix с **agentic search**: пользовательский запрос сначала превращается в структурированный intent, затем проверяется через реальные данные Netflix, а в конце оформляется в дружелюбный ответ.

---

## Что это за проект

Проект решает простую, но важную задачу: **не просто красиво отвечать пользователю, а находить рекомендации только среди реально существующих тайтлов**.

Для этого система разделена на три роли:

1. **Analyst** — понимает, что именно хочет пользователь (без внешних инструментов, силами LLM)
2. **Searcher** — ищет подходящие фильмы и сериалы в реальном каталоге Netflix через tools
3. **Finalizer** — формирует финальный ответ на естественном языке

Ключевая идея: минималистичная архитектура без лишних слоёв. Никакой ChromaDB, никаких kb-файлов, никаких детерминированных экстракторов. Analyst думает сам, Searcher ищет через tools, Finalizer оформляет.

Проект ориентирован на **локальный запуск**, без Docker.

---

## Основные возможности

- рекомендации по естественному запросу на русском или английском
- поиск только по реальному каталогу `data/netflix_titles.csv`
- поддержка описательных запросов вроде:
  - `что-нибудь мрачное про космос`
  - `легкий сериал на вечер`
  - `indian series after 2018`
- поддержка запросов, похожих на поиск по названию:
  - `interstellar`
  - `stranger things`
- локальные evals и тесты
- role-based model configuration через `.env`

---

## Архитектура

### Общая схема

```text
User Query
   ↓
Analyst (LLM-only, без tools)
   ↓
AnalystIntent (strict JSON contract)
   ↓
Searcher (3 tools: NetflixSearch, FilterCandidates, InspectCandidate)
   ↓
SearchResult (verified candidates)
   ↓
Finalizer (без tools)
   ↓
User-facing answer
```

### 1. Analyst

**Задача:** превратить пользовательский текст в структурированный search intent.

Analyst — это LLM-агент **без инструментов**. Он полагается только на своё понимание языка, жанров, настроений, стран и контентных типов. Он не ищет фильмы, не обращается к внешним данным — только анализирует запрос и выдаёт JSON.

Выход: `AnalystIntent` с полями:
- `content_type` (Movie / TV Show / null)
- `hard_constraints` (год, страна, рейтинг — только то, что явно сказал пользователь)
- `soft_preferences` (настроения, темы)
- `genre_hypotheses`, `mood_hypotheses`, `topic_hypotheses`
- `language` (ru / en)
- `explanation`

Если LLM-ответ пустой или невалидный — **минимальный fallback**: запрос передаётся Searcher как есть.

### 2. Searcher

**Searcher — центральный агент системы.**

Получает `AnalystIntent` и работает через три инструмента:

- **NetflixSearchTool** — поиск по CSV (5 режимов: title, description, listed_in, cast, hybrid)
- **FilterCandidatesTool** — пост-фильтрация найденных кандидатов
- **InspectCandidateTool** — инспекция конкретного тайтла (почему matched)

Searcher может: выбрать route, перепробывать другой при слабых результатах, отобрать лучших кандидатов.

Если Searcher не справляется — **fallback search** через NetflixSearchTool напрямую.

### 3. Finalizer

Получает проверенные данные от Searcher и пишет дружелюбный ответ. Не добавляет фактов, которых нет в Searcher output.

---

## Search architecture

### Deterministic retrieval layer

Обычный Python-код (`app/search/catalog.py`):

- нормализует текст (`app/search/text.py`)
- ищет по `title`, `description`, `listed_in`, `cast`
- применяет hard filters
- возвращает кандидатов с match-features

### Agentic search loop

Поведение Searcher-агента: какой route выбрать, когда повторить, когда ослабить ограничения, каких кандидатов считать лучшими.

**Код отвечает за retrieval primitives, агент — за search strategy.**

---

## Tools

### `NetflixSearchTool`

Поиск по каталогу Netflix. 5 режимов: `title`, `description`, `listed_in`, `cast`, `hybrid`. Hard-фильтры: content_type, year_from/to, country, rating, genre.

### `FilterCandidatesTool`

Применяет жёсткие фильтры к уже найденным кандидатам.

### `InspectCandidateTool`

Показывает match-features конкретного тайтла: почему он попал в выдачу.

---

## Контракты между этапами

### `AnalystIntent`
`query`, `content_type`, `hard_constraints`, `soft_preferences`, `topic_hypotheses`, `genre_hypotheses`, `mood_hypotheses`, `language`, `explanation`

### `Candidate`
Тайтл + match_features (title_exact, description_overlap, listed_in_overlap, etc.)

### `SearchResult`
`status`, `selected`, `discarded`, `explanation`

---

## Guardrails и fallback-механизмы

### Guardrails (`.env`)

- `LLM_TIMEOUT_SECONDS` — таймаут на вызов LLM
- `ANALYST_MAX_ITER` — максимум итераций Analyst
- `SEARCHER_MAX_ITER` — максимум итераций Searcher
- `FINALIZER_MAX_ITER` — максимум итераций Finalizer

### Fallbacks

- **Analyst fallback** — минимальный intent (пустые constraints, raw query → Searcher)
- **Searcher fallback** — прямой вызов NetflixSearchTool

---

## LLM / модели / OpenCode Go

Проект работает через **OpenCode Go**: `OPENAI_BASE_URL=https://opencode.ai/zen/go/v1`

### Рекомендуемый baseline

```env
ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-pro
FINALIZER_MODEL=openai/deepseek-v4-flash
```

### Быстрый профиль

```env
ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-flash
FINALIZER_MODEL=openai/deepseek-v4-flash
```

---

## Стек технологий

| Компонент | Технология | Зачем |
|---|---|---|
| Agent orchestration | CrewAI | Линейный пайплайн и tools |
| LLM integration | LangChain + OpenAI-compatible client | Работа с OpenCode Go |
| Search/filtering | pandas | Работа с Netflix CSV |
| Validation | Pydantic | Контракты между этапами |
| Logging | structlog | Структурированные логи |
| Metrics | prometheus-client | Метрики запросов |
| Testing | pytest | Unit/integration tests |

---

## Структура проекта

```text
app/
├── agents/           # Сборка агентов и загрузка prompt'ов
├── contracts/        # Pydantic-схемы между этапами
├── evals/            # Local eval runner
├── llm/              # Universal provider routing
├── monitoring/       # structlog + prometheus
├── orchestration/    # Pipeline wiring + fallbacks
├── runtime/          # Local bootstrap (логи)
├── search/           # Catalog retrieval + text normalization
├── tools/            # CrewAI tools (3 шт.)
├── config.py         # Настройки из .env
└── main.py           # CLI entrypoint

data/
├── netflix_titles.csv

prompts/
├── analyst.md
├── searcher.md
└── finalizer.md

tests/
├── agents/
├── contracts/
├── evals/
├── llm/
├── runtime/
├── search/
└── tools/
```

---

## Как запустить проект

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактировать .env: вставить OPENAI_API_KEY

python -m app.main "что-нибудь мрачное про космос"
```

---

## Пример `.env`

```env
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1

ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-pro
FINALIZER_MODEL=openai/deepseek-v4-flash

ANALYST_TEMPERATURE=0.1
SEARCH_TEMPERATURE=0.0
FINALIZER_TEMPERATURE=0.4

LLM_TIMEOUT_SECONDS=45
ANALYST_MAX_ITER=2
SEARCHER_MAX_ITER=3
FINALIZER_MAX_ITER=2

AGENTS_VERBOSE=true

NETFLIX_CSV_PATH=data/netflix_titles.csv

METRICS_PORT=8001
LOG_FILE=logs/app.log
```

---

## Тесты и evals

```bash
pytest -v                         # все тесты
python -m app.evals.run_evals     # ручная проверка качества
```

---

## Мониторинг

- **Prometheus:** `http://localhost:8001/metrics`
- **Логи:** `logs/app.log` + stdout

---

## Что покрыто тестами

- contracts (AnalystIntent, SearchResult, Candidate)
- runtime bootstrap
- text normalization
- catalog search (title, description routes)
- search tools (FilterCandidates)
- LLM backend routing (openai/anthropic classification)
- timeouts / guardrails
- orchestration helpers (build_searcher_input)
- Analyst fallback
- Searcher fallback
- eval scaffolding
