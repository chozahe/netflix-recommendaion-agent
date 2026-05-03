# Netflix Recommendation Agent

Локальная мультиагентная система рекомендаций контента Netflix с **agentic search** и новым **AI-first chat flow**: система умеет не только отвечать на один запрос, но и вести многоходовый диалог с уточнениями, памятью сессии, refinement после негативного фидбека и optional poster lookup для уже проверенных рекомендаций.

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
- feedback-aware refinement with reusable preference memory
- Analyst-led clarification with a maximum of 2 clarification turns
- DB-first post-retrieval enrichment that only reranks verified CSV candidates
- role-based model configuration через `.env`
- finalizer-driven poster lookup только для уже подтверждённых тайтлов
- optional `poster_url` в ответах API/CLI-рекомендациях
- chat CLI пытается показать постер inline через `kitten icat`, а при неудаче печатает URL
- session-level observability: analytics, structured logs, Prometheus metrics, HTML report

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
Finalizer (+ PosterLookup for verified titles only)
   ↓
ConversationResponse with optional poster_url / one-shot answer
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
- `confidence`
- `external_signals`
- `clarification_count`

Если запрос слишком расплывчатый, именно Analyst решает, нужен ли clarification. Локальный код больше не short-circuit'ит такие решения до Analyst. Если LLM-ответ пустой или невалидный — **минимальный fallback**: запрос передаётся Searcher как есть.

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

Теперь Finalizer может вызывать **PosterLookupTool**: он ищет poster URL только для тех тайтлов, которые уже вернул Searcher. Инструмент не открывает новые рекомендации и не добавляет внешние факты — только пытается обогатить уже подтверждённый shortlist ссылками на постеры. Сам Finalizer возвращает строгий JSON вида `message + posters`, а `ConversationService` merge'ит `poster_url` обратно в `recommendations`.

### 4. Conversation service

Новый слой над пайплайном управляет чатом:
- создаёт сессии
- хранит turns / shown_titles / rejected_titles
- хранит `clarification_count`, accepted/rejected soft preferences и external signal history
- применяет bounded clarification policy (не больше 2 уточнений до первой рекомендации)
- если пользователь отвечает `любое / пофиг / не важно`, прекращает уточнения и сразу ищет
- обрабатывает негативный feedback, обновляет preference memory и запускает refinement
- merge'ит `posters` из Finalizer output обратно в `StoredRecommendation.poster_url`
- отдаёт структурированный `ConversationResponse`
- автоматически собирает session-level analytics: число ходов, latency, clarifications, refinements, fallbacks, enrichment usage

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

### `PosterLookupTool`

Инструмент Finalizer'а. Принимает только уже проверенный `title` (+ опционально `content_type`, `release_year`) и возвращает JSON `{"poster_url": ...}`.

Текущая реализация:
- использует bounded web lookup c `duckduckgo`
- сначала пытается найти poster через Wikipedia infobox
- затем fallback'ается на `og:image` у найденных страниц
- мягко деградирует в `null`, если постер не найден или lookup сломался
- не должен использоваться для поиска новых тайтлов

---

## Контракты между этапами

### `AnalystIntent`
`query`, `content_type`, `hard_constraints`, `soft_preferences`, `topic_hypotheses`, `genre_hypotheses`, `mood_hypotheses`, `language`, `explanation`, `needs_clarification`, `clarification_question`, `missing_slots`, `confidence`, `external_signals`, `clarification_count`

### `ConversationResponse`
`type`, `session_id`, `message`, `recommendations`, `state`

`recommendations` теперь сериализуются как `StoredRecommendation` с optional `poster_url`.

### `SessionMemory`
JSON-память сессии: `session_id`, `state`, `turns`, `shown_titles`, `rejected_titles`, `current_intent`, `last_recommendations`, `feedback_signals`, `clarification_count`, `accepted_soft_preferences`, `rejected_soft_preferences`, `external_signal_history`, `analytics`

`analytics` содержит: `started_at`, `last_updated_at`, `turn_count`, `user_turn_count`, `assistant_turn_count`, `clarification_turn_count`, `recommendation_round_count`, `refinement_round_count`, `error_count`, `total_latency_ms`, `last_latency_ms`, `last_response_type`, `recommended_titles_count`, `unique_titles_count`, `fallback_count`, `enrichment_used_count`

### `StoredRecommendation`
`title`, `reason`, `poster_url`

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
| Metrics | prometheus-client | Метрики запросов и чат-сессий |
| Session analytics | Pydantic models + JSON files | Наблюдаемость на уровне сессий |
| Observability report | HTML generator | Визуальный просмотр всех сессий |
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
├── monitoring/       # structlog + prometheus + session metrics
├── observability/    # HTML report generator for session analytics
├── orchestration/    # Pipeline wiring + fallbacks
├── runtime/          # Local bootstrap (логи)
├── search/           # Catalog retrieval + text normalization + enrichment hooks + poster lookup helpers
├── tools/            # CrewAI tools (NetflixSearch, FilterCandidates, InspectCandidate, PosterLookup)
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
# если установлен kitty, CLI попробует показать постеры inline через kitten icat
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
WEB_ENRICHMENT_PROVIDER=duckduckgo
WEB_ENRICHMENT_MAX_TITLES=3
WEB_ENRICHMENT_SEARCH_RESULTS=5
WEB_ENRICHMENT_TIMEOUT_SECONDS=5
TMDB_API_KEY=
LOG_FILE=logs/app.log
```

`PosterLookupTool` в текущем flow использует `WEB_ENRICHMENT_PROVIDER=duckduckgo` и `WEB_ENRICHMENT_TIMEOUT_SECONDS`. `TMDB_API_KEY` уже добавлен в конфиг как optional helper setting, но default Finalizer flow на него пока не опирается.

---

## Тесты и evals

```bash
pytest -v                         # все тесты
python -m app.evals.run_evals     # one-shot + clarification smoke
python -m app.chat_main           # interactive chat
python -m app.observability.report # generate HTML observability report
```

---

## API

### Endpoints

- `POST /sessions` — создать chat session
- `POST /chat` — отправить сообщение в сессию
- `GET /sessions/{session_id}` — посмотреть состояние сессии
- `DELETE /sessions/{session_id}` — удалить сессию

`ConversationResponse.recommendations[]` может содержать optional `poster_url` для уже подтверждённых рекомендаций.

Пример запуска:

```bash
uvicorn app.api.server:app --host 127.0.0.1 --port 8000
```

## Session memory

Сессии хранятся как локальные JSON-файлы в `memory/sessions/` (или в `SESSIONS_DIR`).
Это даёт простой локальный state без внешней БД.

## Bounded enrichment

Web enrichment опциональный и строго ограниченный:
- не запускается до CSV retrieval
- работает только по top shortlisted DB candidates
- максимум один enrichment pass
- максимум 2-3 shortlisted titles
- по умолчанию использует бесплатный no-key provider `duckduckgo`
- оценивает только bounded search-result snippets/titles на первом этапе
- может валидировать era / actor / vibe-like external signals
- **никогда не добавляет новые titles из web**, а только помогает rerank'ить уже найденные CSV-кандидаты
- при timeout / provider failure мягко деградирует к `no enrichment`
- управляется feature flag'ом, provider config и timeout'ом

## Пример multi-turn диалога

```text
User: хочу что-нибудь мрачное
Agent: Это должен быть фильм или сериал?
User: фильм
Agent: ... рекомендации ...
User: это слишком старое
Agent: Окей, давайте попробуем что-то поновее или ближе к вашим пожеланиям.
```

## Пример association-style запроса

```text
User: посоветуй сериал с вайбом 80-х и Вайноной Райдер
Analyst: выделяет content_type=TV Show, confidence, external_signals вроде era:1980s / actor:winona_ryder / vibe:mysterious
Searcher: ищет только по CSV каталогу и выбирает shortlist реальных Netflix titles
Enrichment: при необходимости делает bounded DuckDuckGo search по top DB candidates, проверяет snippets на era/actor/vibe сигналы и rerank'ит shortlist, не добавляя новые titles
Finalizer: формирует ответ только из проверенного shortlist
```

## Observability

Система наблюдаемости состоит из трёх уровней:

### 1. Prometheus metrics (агрегаты)

При запуске chat CLI или API автоматически поднимается HTTP-сервер метрик на порту `METRICS_PORT` (по умолчанию `8001`).

Доступные метрики:
- `netflix_agent_requests_total{status}` — общее число one-shot запросов
- `netflix_agent_request_duration_seconds` — длительность one-shot запросов
- `netflix_agent_chat_sessions_total` — число запущенных чат-сессий
- `netflix_agent_chat_turns_total{status,type}` — число ходов в чате
- `netflix_agent_chat_turn_duration_seconds` — длительность хода
- `netflix_agent_clarifications_total` — число clarification-запросов
- `netflix_agent_refinements_total` — число refinement-раундов
- `netflix_agent_recommendations_total` — число recommendation-раундов
- `netflix_agent_fallbacks_total{stage}` — число fallback'ов по стадиям (analyst/searcher)

**Как посмотреть:**
```bash
curl http://localhost:8001/metrics
```

Prometheus — это стандартный способ экспорта метрик приложения по HTTP. Это не UI и не база данных, а текстовый endpoint с текущими значениями счётчиков. Можно подключить Grafana для визуализации, но для локального использования достаточно `curl`.

### 2. Structured logs (события)

Все события логируются через `structlog` в файл `logs/app.log` и в stdout.

Основные события:
- `chat_session_started` / `chat_session_ended`
- `chat_turn_started` / `chat_turn_completed` / `chat_turn_failed`
- `clarification_requested`
- `recommendations_generated`
- `refinement_generated`
- `analyst_started` / `analyst_finished` / `analyst_fallback_used`
- `searcher_started` / `searcher_finished` / `searcher_fallback_used`
- `finalizer_started` / `finalizer_finished`

Каждое событие содержит: `session_id`, `turn_index`, `state`, `response_type`, `latency_ms`, `clarification_count`, `recommendation_count` и другие контекстные поля.

### 3. Session analytics (детали по сессии)

Каждая сессия автоматически собирает аналитику в поле `analytics` внутри JSON-файла сессии (`memory/sessions/*.json`).

Это позволяет постфактум разобрать любой диалог: сколько было ходов, сколько clarifications, какая latency, какие тайтлы рекомендовались, какие preferences накопились.

### HTML Report (визуальный просмотр)

Для удобного просмотра всех сессий есть offline HTML-отчёт:

```bash
python -m app.observability.report
```

Генерирует `logs/observability_report.html` с:
- summary cards: общее число сессий, ходов, clarifications, refinements, errors, fallbacks
- таблица сессий с раскрывающимися деталями
- по каждой сессии: state, timestamps, latency, рекомендации, preferences, external signals
- raw JSON snapshot для глубокого анализа

**Не требует новых зависимостей** — работает на стандартном Python.

---

## Что покрыто тестами

- contracts (AnalystIntent, ConversationResponse, SearchResult, Candidate, StoredRecommendation.poster_url)
- runtime bootstrap
- text normalization
- catalog search (title, description routes)
- search tools (FilterCandidates, PosterLookup)
- poster/image lookup helpers (`image_search`, `tmdb_search`)
- conversation classifier / clarification / session store
- conversation poster merge flow
- chat API happy path
- chat CLI poster rendering fallback
- feedback refinement smoke flow
- one-shot CLI compatibility
- LLM backend routing (openai/anthropic classification)
- timeouts / guardrails
- orchestration helpers (build_searcher_input)
- Analyst fallback
- Searcher fallback
- eval scaffolding
