# Observability — Netflix Recommendation Agent

## Обзор

Система наблюдаемости состоит из **трёх уровней**, каждый из которых решает свою задачу:

| Уровень | Что даёт | Где смотреть |
|---|---|---|
| **Prometheus metrics** | Агрегаты: сколько сессий, ходов, ошибок, какая latency | `http://localhost:8001/metrics` |
| **Structured logs** | Timeline событий: что произошло, когда, с какими параметрами | `logs/app.log` + stdout |
| **Session analytics** | Детали конкретного диалога: ходы, рекомендации, preferences, fallbacks | `memory/sessions/*.json` + HTML report |

## Стек

| Компонент | Библиотека | Назначение |
|---|---|---|
| Метрики | `prometheus-client` | Счётчики и гистограммы, HTTP-экспорт |
| Логи | `structlog` | Структурированные события с контекстом |
| Аналитика сессий | `pydantic` + JSON files | Хранение analytics прямо в памяти сессии |
| HTML report | Стандартный Python (без зависимостей) | Генерация визуального отчёта |

## 1. Prometheus Metrics

### Что это

Prometheus — стандарт индустрии для экспорта метрик приложения. Библиотека `prometheus_client` поднимает лёгкий HTTP-сервер, который отдаёт текущие значения всех счётчиков в текстовом формате. Это **не UI** и **не база данных** — это endpoint, который можно скрейпить.

### Какие метрики экспортируются

#### One-shot CLI (`app.main`)
- `netflix_agent_requests_total{status}` — число one-shot запросов (success/error)
- `netflix_agent_request_duration_seconds` — гистограмма длительности запросов
- `netflix_agent_tokens_total{agent}` — использование токенов (объявлена, пока не заполняется)

#### Chat CLI (`app.chat_main`)
- `netflix_agent_chat_sessions_total` — число запущенных чат-сессий
- `netflix_agent_chat_turns_total{status,type}` — число ходов, разбитое по статусу и типу ответа
- `netflix_agent_chat_turn_duration_seconds` — гистограмма длительности каждого хода
- `netflix_agent_clarifications_total` — сколько раз система просила уточнение
- `netflix_agent_refinements_total` — сколько refinement-раундов после фидбека
- `netflix_agent_recommendations_total` — сколько recommendation-раундов
- `netflix_agent_fallbacks_total{stage}` — fallback'и по стадиям: `analyst`, `searcher`

### Как посмотреть

```bash
# Запустить чат
python -m app.chat_main

# В другом терминале
curl http://localhost:8001/metrics

# Или в реальном времени
watch -n 1 'curl -s http://localhost:8001/metrics | grep netflix_agent_chat'
```

### Как обновляются

Метрики обновляются **в момент выполнения**:
- Новый ход → `CHAT_TURNS_TOTAL.inc()` + `CHAT_TURN_DURATION.observe()`
- Clarification → `CLARIFICATIONS_TOTAL.inc()`
- Refinement → `REFINEMENTS_TOTAL.inc()`
- Recommendation → `RECOMMENDATIONS_TOTAL.inc()`
- Fallback → `FALLBACKS_TOTAL.labels(stage="...").inc()`

Сервер метрик работает в фоновом потоке — значения всегда актуальны.

### Важное правило

`session_id` **не используется** в Prometheus labels. Это high-cardinality данные, которые убивают производительность Prometheus. Детали по конкретной сессии хранятся в JSON-файлах и логах.

## 2. Structured Logs

### Что это

`structlog` пишет события в машиночитаемом формате с привязанным контекстом. В отличие от обычных логов, каждое событие — это набор ключей, а не просто строка.

### Где пишутся

- **Файл:** `logs/app.log` (структурированный, для разбора)
- **Stdout:** терминал (для живой отладки)

### Какие события логируются

#### Session lifecycle
- `chat_session_started` — сессия создана
- `chat_turn_started` — новый ход начался
- `chat_turn_completed` — ход завершён успешно
- `chat_turn_failed` — ошибка обработки хода
- `chat_session_ended` — пользователь вышел из чата

#### Business events
- `clarification_requested` — система попросила уточнение
- `recommendations_generated` — сгенерированы рекомендации
- `refinement_generated` — запущен refinement после фидбека

#### Pipeline stages
- `analyst_started` / `analyst_finished` / `analyst_fallback_used`
- `searcher_started` / `searcher_finished` / `searcher_fallback_used`
- `finalizer_started` / `finalizer_finished`

### Какие поля в каждом событии

Обязательные поля session-level событий:
- `session_id` — идентификатор сессии
- `turn_index` — номер хода
- `state` — текущее состояние сессии
- `response_type` — тип ответа (clarification/recommendations/refined_recommendations)
- `latency_ms` — время обработки хода
- `clarification_count` — сколько было уточнений
- `recommendation_count` — сколько рекомендаций в ответе
- `shown_titles_count` — сколько тайтлов показано за сессию
- `feedback_signals_count` — сколько фидбек-сигналов
- `accepted_preferences_keys` — ключи принятых preferences
- `rejected_preferences_keys` — ключи отвергнутых preferences
- `external_signal_count` — число внешних сигналов

Дополнительные поля:
- `user_message_length` — длина входящего сообщения
- `has_posters` — есть ли постеры в ответе
- `enrichment_used` — использовалось ли web enrichment
- `error` — текст ошибки (только для failed events)

### Как смотреть

```bash
# Живой просмотр
tail -f logs/app.log

# Фильтр по session_id
grep "session_id=abc-123" logs/app.log

# Фильтр по событию
grep "clarification_requested" logs/app.log

# Фильтр по ошибкам
grep "chat_turn_failed" logs/app.log
```

## 3. Session Analytics

### Что это

Каждая сессия автоматически собирает аналитику в поле `analytics` внутри своего JSON-файла. Это **не отдельная БД** — это часть `SessionMemory`, которая уже сохраняется на диск.

### Где хранится

`memory/sessions/<session_id>.json`

### Структура analytics

```json
{
  "analytics": {
    "started_at": "2026-05-04T00:00:00+00:00",
    "last_updated_at": "2026-05-04T00:05:00+00:00",
    "turn_count": 5,
    "user_turn_count": 5,
    "assistant_turn_count": 5,
    "clarification_turn_count": 1,
    "recommendation_round_count": 2,
    "refinement_round_count": 1,
    "error_count": 0,
    "total_latency_ms": 45000,
    "last_latency_ms": 8000,
    "last_response_type": "recommendations",
    "recommended_titles_count": 8,
    "unique_titles_count": 6,
    "fallback_count": 0,
    "enrichment_used_count": 1
  }
}
```

### Когда обновляется

| Событие | Что обновляется |
|---|---|
| Создание сессии | `started_at`, `last_updated_at` |
| Начало хода | `turn_count`, `user_turn_count`, `last_updated_at` |
| Успешный ответ | `assistant_turn_count`, `last_latency_ms`, `total_latency_ms`, `last_response_type` |
| Clarification | `clarification_turn_count` |
| Recommendation round | `recommendation_round_count`, `recommended_titles_count`, `unique_titles_count` |
| Refinement | `refinement_round_count` |
| Ошибка | `error_count`, `last_updated_at` |
| Fallback | `fallback_count` |
| Enrichment | `enrichment_used_count` |

### Чем отличается от метрик

| | Metrics | Session Analytics |
|---|---|---|
| Формат | Агрегаты (счётчики, гистограммы) | Детали конкретной сессии |
| Хранение | In-memory, экспортируется по HTTP | JSON-файл на диске |
| Cardinality | Low (labels: status, type, stage) | High (каждая сессия уникальна) |
| Назначение | Операционный мониторинг | Разбор конкретного диалога |
| Можно ли в Grafana | Да | Нет (но можно через HTML report) |

## 4. HTML Report

### Что это

Offline-генератор отчёта, который читает все session JSON и строит красивую HTML-страницу. **Не требует новых зависимостей** — работает на стандартном Python.

### Как запустить

```bash
python -m app.observability.report
```

Генерирует `logs/observability_report.html`.

### Что показывает

**Summary cards:**
- Общее число сессий
- Общее число ходов
- Среднее число ходов на сессию
- Число recommendation/clarification/refinement раундов
- Средняя latency
- Число ошибок, fallback'ов, enrichment usage

**По каждой сессии (раскрывающийся блок):**
- Session ID, state, timestamps
- Turn breakdown (user/assistant)
- Clarification/refinement/recommendation counts
- Latency (total + last)
- Fallback/enrichment usage
- Shown/rejected titles
- Accepted/rejected preferences
- External signals
- Last recommendations
- Raw JSON snapshot

### Как пользоваться

1. Поработать в чате: `python -m app.chat_main`
2. Сгенерировать отчёт: `python -m app.observability.report`
3. Открыть `logs/observability_report.html` в браузере

## Архитектура observability

```
User → chat_main.py
         │
         ├─ setup_logging()        → structlog → logs/app.log + stdout
         ├─ setup_metrics(port)    → prometheus_client → :8001/metrics
         │
         └─ run_chat()
              │
              ├─ ConversationService.handle_message()
              │    ├─ session.analytics.mark_turn_started()
              │    ├─ session.analytics.mark_turn_completed()
              │    ├─ session.analytics.mark_clarification()
              │    ├─ session.analytics.mark_recommendation_round()
              │    ├─ session.analytics.mark_refinement()
              │    ├─ session.analytics.mark_error()
              │    ├─ session.analytics.mark_fallback()
              │    ├─ session.analytics.mark_enrichment_used()
              │    └─ _logger.info("chat_turn_...", ...)
              │
              ├─ CHAT_TURNS_TOTAL.labels(...).inc()
              ├─ CHAT_TURN_DURATION.observe(...)
              ├─ CLARIFICATIONS_TOTAL.inc()
              ├─ REFINEMENTS_TOTAL.inc()
              └─ RECOMMENDATIONS_TOTAL.inc()

pipeline.py (analyst/searcher fallback)
         └─ FALLBACKS_TOTAL.labels(stage="...").inc()

observability/report.py
         └─ читает memory/sessions/*.json → logs/observability_report.html
```

## Быстрый старт

```bash
# 1. Запустить чат
python -m app.chat_main

# 2. В другом терминале смотреть метрики
curl http://localhost:8001/metrics | grep netflix_agent_chat

# 3. После сессии сгенерировать отчёт
python -m app.observability.report
open logs/observability_report.html  # macOS
xdg-open logs/observability_report.html  # Linux
```

## Конфигурация

Все настройки observability — через `.env`:

| Переменная | По умолчанию | Что делает |
|---|---|---|
| `METRICS_PORT` | `8001` | Порт Prometheus endpoint |
| `LOG_FILE` | `logs/app.log` | Путь к файлу логов |
| `SESSIONS_DIR` | `memory/sessions` | Директория session JSON |
