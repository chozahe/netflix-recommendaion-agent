# Наблюдаемость — Metrics, Logs, Analytics, Report

## Обзор

Система наблюдаемости состоит из трёх уровней, каждый решает свою задачу:

| Уровень | Что даёт | Где смотреть |
|---|---|---|
| Prometheus metrics | Агрегаты: счётчики, гистограммы | `http://localhost:8001/metrics` |
| Structured logs | Timeline событий с контекстом | `logs/app.log` + stdout |
| Session analytics | Детали конкретной сессии | `memory/sessions/*.json` |

Дополнительно: HTML-отчёт для визуального просмотра.

---

## 1. Prometheus Metrics

**Файл:** `app/monitoring/metrics.py`

### Как работает

`prometheus_client` поднимает HTTP-сервер в фоновом потоке. При запросе `:8001/metrics` отдаёт текущие значения всех счётчиков.

### Сервер метрик

```python
def setup_metrics(port: int) -> None:
    try:
        start_http_server(port)
    except OSError:
        pass  # уже запущен
```

Запускается в:
- `app/main.py` — one-shot CLI
- `app/chat_main.py` — chat CLI

### Все метрики

#### One-shot CLI

| Метрика | Тип | Labels | Описание |
|---|---|---|---|
| `netflix_agent_requests_total` | Counter | `status` | Число запросов (success/error) |
| `netflix_agent_request_duration_seconds` | Histogram | — | Длительность запросов |
| `netflix_agent_tokens_total` | Counter | `agent` | Использование токенов (объявлена, не заполняется) |

#### Chat CLI

| Метрика | Тип | Labels | Описание |
|---|---|---|---|
| `netflix_agent_chat_sessions_total` | Counter | — | Число запущенных сессий |
| `netflix_agent_chat_turns_total` | Counter | `status`, `type` | Число ходов |
| `netflix_agent_chat_turn_duration_seconds` | Histogram | — | Длительность хода |
| `netflix_agent_clarifications_total` | Counter | — | Число clarification запросов |
| `netflix_agent_refinements_total` | Counter | — | Число refinement раундов |
| `netflix_agent_recommendations_total` | Counter | — | Число recommendation раундов |
| `netflix_agent_fallbacks_total` | Counter | `stage` | Fallback'и (analyst/searcher) |

### Когда обновляются

| Событие | Что инкрементится | Где |
|---|---|---|
| Новая сессия | `CHAT_SESSIONS_TOTAL.inc()` | `app/chat/cli.py` |
| Ход завершён | `CHAT_TURNS_TOTAL.labels(status, type).inc()` | `app/chat/cli.py` |
| Latency хода | `CHAT_TURN_DURATION.observe(seconds)` | `app/chat/cli.py` |
| Clarification | `CLARIFICATIONS_TOTAL.inc()` | `app/chat/cli.py` |
| Refinement | `REFINEMENTS_TOTAL.inc()` | `app/chat/cli.py` |
| Recommendations | `RECOMMENDATIONS_TOTAL.inc()` | `app/chat/cli.py` |
| Analyst fallback | `FALLBACKS_TOTAL.labels(stage="analyst").inc()` | `app/orchestration/pipeline.py` |
| Searcher fallback | `FALLBACKS_TOTAL.labels(stage="searcher").inc()` | `app/orchestration/pipeline.py` |

### Важное правило

`session_id` **не используется** в Prometheus labels. Это high-cardinality данные. Детали по сессии хранятся в JSON и логах.

---

## 2. Structured Logs

**Файл:** `app/monitoring/logger.py`

### Как работает

`structlog` настраивается с процессорами:
- `add_logger_name` — имя логгера
- `add_log_level` — уровень (info/warning/error)
- `TimeStamper(fmt="iso")` — ISO timestamp
- `StackInfoRenderer` — stack info
- `format_exc_info` — форматирование exceptions

### Куда пишет

| Destination | Формат | Назначение |
|---|---|---|
| `logs/app.log` | Структурированный | Для разбора и поиска |
| stdout | Человекочитаемый | Для живой отладки |

### События

#### Session lifecycle

| Событие | Когда | Поля |
|---|---|---|
| `chat_session_started` | При создании сессии | `session_id` |
| `chat_turn_started` | В начале handle_message | `session_id`, `turn_index`, `state`, `user_message_length` |
| `chat_turn_completed` | После успешного ответа | `session_id`, `turn_index`, `response_type`, `latency_ms` |
| `chat_turn_failed` | При исключении | `session_id`, `turn_index`, `error`, `latency_ms` |
| `chat_session_ended` | При выходе из чата | `session_id` |

#### Business events

| Событие | Когда |
|---|---|
| `clarification_requested` | Когда возвращается clarification |
| `recommendations_generated` | Когда возвращаются рекомендации |
| `refinement_generated` | Когда запускается refinement |

#### Pipeline stages

| Событие | Когда |
|---|---|
| `analyst_started` / `analyst_finished` | Начало/конец работы Analyst |
| `analyst_fallback_used` | При ошибке Analyst |
| `searcher_started` / `searcher_finished` | Начало/конец работы Searcher |
| `searcher_fallback_used` | При ошибке Searcher |
| `finalizer_started` / `finalizer_finished` | Начало/конец работы Finalizer |

#### System

| Событие | Когда |
|---|---|
| `system_started` | При запуске приложения |
| `request_received` / `request_completed` | One-shot CLI запросы |
| `request_failed` | Ошибка one-shot запроса |
| `chat_cli_started` | Запуск chat CLI |
| `chat_loop_started` / `chat_loop_error` | Цикл чата |

---

## 3. Session Analytics

**Файл:** `app/memory/models.py` — `SessionAnalytics`

### Что это

Встроенный в `SessionMemory` блок аналитики. Автоматически обновляется при каждом ходе.

### Где хранится

Внутри каждого session JSON: `memory/sessions/{session_id}.json`

### Как обновляется

Через методы `SessionAnalytics`:

```python
session.analytics.mark_turn_started()
# ... обработка ...
session.analytics.mark_turn_completed(latency_ms=5000, response_type="recommendations")
session.analytics.mark_recommendation_round(titles_count=3, unique_titles=10)
```

### Отличие от метрик

| | Metrics | Session Analytics |
|---|---|---|
| Детальность | Агрегаты по всем сессиям | Детали одной сессии |
| Хранение | In-memory | JSON на диске |
| Переживает рестарт | Нет | Да |
| Cardinality | Low | High |

---

## 4. HTML Report

**Файл:** `app/observability/report.py`

### Что делает

Читает все session JSON, строит HTML-страницу с обзором и деталями.

### Запуск

```bash
python -m app.observability.report
```

Генерирует `logs/observability_report.html`.

### Что показывает

**Summary cards:**
- Число сессий, ходов, clarifications, refinements
- Средняя latency
- Число ошибок, fallback'ов, enrichment usage

**По каждой сессии (раскрывающийся блок):**
- Session ID, state, timestamps
- Turn breakdown
- Latency
- Shown/rejected titles
- Preferences
- External signals
- Raw JSON snapshot

### Зависимости

Ноль новых зависимостей. Только стандартная библиотека: `json`, `pathlib`, `datetime`.

---

## Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `METRICS_PORT` | 8001 | Порт Prometheus endpoint |
| `LOG_FILE` | logs/app.log | Путь к файлу логов |
| `SESSIONS_DIR` | memory/sessions | Директория session JSON |

---

## Быстрый старт

```bash
# 1. Запустить чат
python -m app.chat_main

# 2. В другом терминале смотреть метрики
curl http://localhost:8001/metrics | grep netflix_agent_chat

# 3. Смотреть логи
tail -f logs/app.log

# 4. После сессии сгенерировать отчёт
python -m app.observability.report
```
