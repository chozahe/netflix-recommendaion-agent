# Netflix Recommendation Agent

Локальная мультиагентная система рекомендаций контента Netflix с **agentic search** и новым **AI-first chat flow**: система умеет не только отвечать на один запрос, но и вести многоходовый диалог с уточнениями, памятью сессии и refinement после негативного фидбека.

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
- chat CLI с памятью сессии
- FastAPI chat API
- file-based session memory
- feedback-aware refinement
- bounded post-retrieval enrichment hooks
- role-based model configuration через `.env`

---

## Архитектура

### Общая схема

```text
User Message
   ↓
ConversationService
   ├─ session memory (JSON files)
   ├─ turn classification
   ├─ clarification / refinement handling
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
ConversationResponse / one-shot answer
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
- `needs_clarification`
- `clarification_question`
- `missing_slots`

Если запрос слишком расплывчатый, Analyst может не запускать поиск сразу, а запросить уточнение. Если LLM-ответ пустой или невалидный — **минимальный fallback**: запрос передаётся Searcher как есть.

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

### 4. Conversation service

Новый слой над пайплайном управляет чатом:
- создаёт сессии
- хранит turns / shown_titles / rejected_titles
- решает, нужен ли clarification turn
- обрабатывает негативный feedback и запускает refinement
- отдаёт структурированный `ConversationResponse`

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
`query`, `content_type`, `hard_constraints`, `soft_preferences`, `topic_hypotheses`, `genre_hypotheses`, `mood_hypotheses`, `language`, `explanation`, `needs_clarification`, `clarification_question`, `missing_slots`

### `ConversationResponse`
`type`, `session_id`, `message`, `recommendations`, `state`

### `SessionMemory`
JSON-память сессии: `state`, `turns`, `shown_titles`, `rejected_titles`, `current_intent`, `last_recommendations`, `feedback_signals`

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
├── api/              # FastAPI chat API
├── chat/             # Interactive CLI chat
├── contracts/        # Pydantic-схемы между этапами
├── conversation/     # Clarification / classifier / service
├── evals/            # Local eval runner
├── llm/              # Universal provider routing
├── memory/           # Session models + file store
├── monitoring/       # structlog + prometheus
├── orchestration/    # Pipeline wiring + fallbacks
├── runtime/          # Local bootstrap (логи)
├── search/           # Catalog retrieval + text normalization + enrichment hooks
├── tools/            # CrewAI tools (3 шт.)
├── chat_main.py      # Chat CLI entrypoint
├── config.py         # Настройки из .env
└── main.py           # One-shot CLI entrypoint

data/
├── netflix_titles.csv

knowledge/
├── clarification_policy.md
├── enrichment_policy.md
└── feedback_policy.md

prompts/
├── analyst.md
├── searcher.md
└── finalizer.md

tests/
├── agents/
├── api/
├── chat/
├── contracts/
├── conversation/
├── evals/
├── llm/
├── memory/
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

# one-shot CLI
python -m app.main "что-нибудь мрачное про космос"

# chat CLI
python -m app.chat_main
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
SESSIONS_DIR=memory/sessions

METRICS_PORT=8001
API_HOST=127.0.0.1
API_PORT=8000
WEB_ENRICHMENT_ENABLED=true
WEB_ENRICHMENT_MAX_TITLES=3
WEB_ENRICHMENT_TIMEOUT_SECONDS=5
LOG_FILE=logs/app.log
```

---

## Тесты и evals

```bash
pytest -v                         # все тесты
python -m app.evals.run_evals     # one-shot + clarification smoke
python -m app.chat_main           # interactive chat
```

---

## API

### Endpoints

- `POST /sessions` — создать chat session
- `POST /chat` — отправить сообщение в сессию
- `GET /sessions/{session_id}` — посмотреть состояние сессии
- `DELETE /sessions/{session_id}` — удалить сессию

Пример запуска:

```bash
uvicorn app.api.server:app --host 127.0.0.1 --port 8000
```

## Session memory

Сессии хранятся как локальные JSON-файлы в `memory/sessions/` (или в `SESSIONS_DIR`).
Это даёт простой локальный state без внешней БД.

## Bounded enrichment

Web enrichment пока опциональный и строго ограниченный:
- не запускается до CSV retrieval
- максимум один enrichment pass
- максимум 2-3 shortlisted titles
- управляется feature flag'ом и timeout'ом

## Пример multi-turn диалога

```text
User: хочу что-нибудь мрачное
Agent: Это должен быть фильм или сериал?
User: фильм
Agent: ... рекомендации ...
User: это слишком старое
Agent: Окей, давайте попробуем что-то поновее или ближе к вашим пожеланиям.
```

## Мониторинг

- **Prometheus:** `http://localhost:8001/metrics`
- **Логи:** `logs/app.log` + stdout

---

## Что покрыто тестами

- contracts (AnalystIntent, ConversationResponse, SearchResult, Candidate)
- runtime bootstrap
- text normalization
- catalog search (title, description routes)
- search tools (FilterCandidates)
- conversation classifier / clarification / session store
- chat API happy path
- feedback refinement smoke flow
- one-shot CLI compatibility
- LLM backend routing (openai/anthropic classification)
- timeouts / guardrails
- orchestration helpers (build_searcher_input)
- Analyst fallback
- Searcher fallback
- eval scaffolding
