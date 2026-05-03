# Обзор проекта — Netflix Recommendation Agent

## Что это

Локальная мультиагентная система рекомендаций Netflix. Система принимает запрос на естественном языке (русский или английский), понимает намерение пользователя, ищет реальные тайтлы в каталоге `data/netflix_titles.csv` и формирует персонализированный ответ.

## Ключевая идея

**Никаких выдуманных рекомендаций.** Все тайтлы берутся только из реального CSV-каталога. LLM-агенты управляют стратегией, но не придумывают фильмы.

## Архитектура: 3-агентный пайплайн

```
User Message
    ↓
ConversationService (управление сессией, память, классификация)
    ↓
Analyst (LLM-only, без инструментов)
    ↓
AnalystIntent (структурированный JSON-интент)
    ↓
Searcher (3 инструмента: NetflixSearch, FilterCandidates, InspectCandidate)
    ↓
SearchResult (верифицированные кандидаты из CSV)
    ↓
Finalizer (+ PosterLookup для постеров)
    ↓
ConversationResponse (ответ + рекомендации с optional poster_url)
```

### Аналитик (Analyst)

- **Роль:** Превращает текст пользователя в машиночитаемый интент
- **Инструменты:** Нет. Работает только через LLM
- **Выход:** `AnalystIntent` — JSON с полями: content_type, hard_constraints, soft_preferences, genre/mood/topic гипотезы, external_signals, needs_clarification и др.
- **Fallback:** Если LLM не справляется — создаётся минимальный intent с raw query

### Поисковик (Searcher)

- **Роль:** Ищет реальные тайтлы в каталоге Netflix
- **Инструменты:** NetflixSearch, FilterCandidates, InspectCandidate
- **Стратегия:** Выбирает режим поиска (title/description/listed_in/cast/hybrid), при слабых результатах пробует другой route
- **Fallback:** Прямой вызов NetflixSearchTool без агента

### Финализатор (Finalizer)

- **Роль:** Формирует дружелюбный ответ на естественном языке
- **Инструменты:** PosterLookup
- **Правило:** Не добавляет фактов, которых нет в SearchResult

## ConversationService

Слой над пайплайном, который управляет многоходовым диалогом:

- Создаёт сессии с уникальным `session_id`
- Хранит историю ходов, показанные/отклонённые тайтлы
- Обрабатывает clarification (до 2 уточнений)
- Обрабатывает негативный фидбек → refinement с обновлением preferences
- Собирает session-level analytics (turns, latency, clarifications, fallbacks...)
- Merge'ит постеры из Finalizer в рекомендации

## Режимы работы

### One-shot CLI
```bash
python -m app.main "хочу фильм про космос"
```
Один запрос → один ответ. Без памяти сессии.

### Chat CLI
```bash
python -m app.chat_main
```
Интерактивный диалог с памятью сессии, clarification, feedback, refinement.

### FastAPI
```bash
uvicorn app.api.server:app --host 127.0.0.1 --port 8000
```
HTTP API с endpoints: POST /sessions, POST /chat, GET /sessions/{id}, DELETE /sessions/{id}

## Наблюдаемость

Три уровня:
1. **Prometheus metrics** — агрегаты на `:8001/metrics`
2. **Structured logs** — события в `logs/app.log`
3. **Session analytics** — детали в `memory/sessions/*.json`

HTML-отчёт: `python -m app.observability.report`

## Стек

| Компонент | Технология |
|---|---|
| Оркестрация | CrewAI |
| LLM | LangChain + OpenAI-compatible / Anthropic-style adapter |
| Поиск | pandas |
| Валидация | Pydantic |
| Логи | structlog |
| Метрики | prometheus-client |
| Web enrichment | duckduckgo_search |
| Постеры | curl_cffi + regex parsing |
| Тесты | pytest |

## Структура проекта

```
app/
├── agents/           # Сборка агентов + загрузка промптов
├── api/              # FastAPI сервер
├── chat/             # CLI chat интерфейс
├── contracts/        # Pydantic-схемы (AnalystIntent, SearchResult, etc.)
├── conversation/     # ConversationService, clarification, classifier
├── evals/            # Eval runner
├── llm/              # LLM provider routing (OpenAI / Anthropic style)
├── memory/           # SessionMemory, FileSessionStore, merge helpers
├── monitoring/       # structlog + prometheus metrics
├── observability/    # HTML report generator
├── orchestration/    # Pipeline wiring, fallbacks, enrichment
├── runtime/          # Bootstrap (создание директорий)
├── search/           # CatalogSearchEngine, text normalization, enrichment, web search, image search
├── tools/            # CrewAI tools (4 штуки)
├── chat_main.py      # Chat CLI entrypoint
├── config.py         # Настройки из .env
└── main.py           # One-shot CLI entrypoint

data/netflix_titles.csv       # Каталог (8807 строк)
knowledge/                    # Policy notes (не загружаются в runtime)
prompts/                      # Промпты для агентов
memory/sessions/              # JSON-файлы сессий
logs/                         # Логи + HTML report
```

## Файлы конфигурации

- `.env` — все настройки (модели, температуры, таймауты, пути)
- `requirements.txt` — зависимости
- `AGENTS.md` — архитектурная документация для разработчиков
- `OBSERVABILITY.md` — гайд по системе наблюдаемости
