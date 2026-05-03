# Память — SessionMemory, FileSessionStore, Merge

## Обзор

Память проекта — это file-based session storage. Каждая сессия сохраняется как JSON-файл на диск. Никакой внешней БД.

---

## SessionMemory

**Файл:** `app/memory/models.py`

### Структура

```python
class SessionMemory(BaseModel):
    session_id: str                           # UUID
    state: str = "idle"                       # idle / awaiting_clarification / recommended / refining
    turns: list[ConversationTurn]             # история сообщений
    shown_titles: list[str]                   # показанные тайтлы
    rejected_titles: list[str]                # отклонённые тайтлы
    current_intent: AnalystIntent | None      # текущий интент
    last_recommendations: list[StoredRecommendation]  # последние рекомендации
    feedback_signals: list[FeedbackSignal]    # сигналы фидбека
    clarification_count: int = 0              # число уточнений
    accepted_soft_preferences: dict           # принятые preferences
    rejected_soft_preferences: dict           # отклонённые preferences
    external_signal_history: list[str]        # история external signals
    analytics: SessionAnalytics               # аналитика сессии
```

### ConversationTurn

```python
class ConversationTurn(BaseModel):
    role: str      # "user" или "assistant"
    message: str   # текст сообщения
```

### StoredRecommendation

```python
class StoredRecommendation(BaseModel):
    title: str
    reason: str | None = None
    poster_url: str | None = None
```

### SessionAnalytics

```python
class SessionAnalytics(BaseModel):
    started_at: str                    # ISO timestamp
    last_updated_at: str               # ISO timestamp
    turn_count: int                    # общее число ходов
    user_turn_count: int               # ходы пользователя
    assistant_turn_count: int          # ходы ассистента
    clarification_turn_count: int      # уточнения
    recommendation_round_count: int    # recommendation раунды
    refinement_round_count: int        # refinement раунды
    error_count: int                   # ошибки
    total_latency_ms: int              # суммарная latency
    last_latency_ms: int               # latency последнего хода
    last_response_type: str            # тип последнего ответа
    recommended_titles_count: int      # всего рекомендовано тайтлов
    unique_titles_count: int           # уникальных тайтлов
    fallback_count: int                # fallback'и
    enrichment_used_count: int         # использования enrichment
```

### Методы SessionAnalytics

| Метод | Что делает |
|---|---|
| `mark_started()` | Устанавливает started_at и last_updated_at |
| `mark_turn_started()` | turn_count++, user_turn_count++, last_updated_at |
| `mark_turn_completed(latency_ms, response_type)` | assistant_turn_count++, latency, last_response_type |
| `mark_clarification()` | clarification_turn_count++ |
| `mark_recommendation_round(titles, unique)` | recommendation_round_count++, counts |
| `mark_refinement()` | refinement_round_count++ |
| `mark_error()` | error_count++, last_updated_at |
| `mark_fallback()` | fallback_count++ |
| `mark_enrichment_used()` | enrichment_used_count++ |

---

## FileSessionStore

**Файл:** `app/memory/session_store.py`

### Назначение

CRUD-операции над session JSON файлами.

### Методы

| Метод | Описание |
|---|---|
| `create_session()` | Создаёт новую сессию с UUID, инициализирует analytics |
| `load_session(session_id)` | Загружает сессию из JSON |
| `save_session(session)` | Сохраняет сессию в JSON |
| `delete_session(session_id)` | Удаляет файл сессии |

### Формат файлов

```
memory/sessions/
├── abc123-def456-...json
├── xyz789-uvw012-...json
└── ...
```

Каждый файл — валидный JSON с indent=2.

### Инициализация analytics

При `create_session()` автоматически вызывается `session.analytics.mark_started()`:

```python
def create_session(self) -> SessionMemory:
    session = SessionMemory(session_id=str(uuid4()))
    session.analytics.mark_started()
    self.save_session(session)
    return session
```

---

## Merge Helpers

**Файл:** `app/memory/merge.py`

### merge_clarification_answer()

Принимает ответ пользователя на уточняющий вопрос и merge'ит его в текущий intent сессии.

Использует LLM-провайдер для парсинга ответа в структурированный AnalystIntent.

### is_relaxed_clarification_answer()

Детектит relaxed-ответы:

```python
RELAXED_MARKERS = {"любое", "пофиг", "не важно", "anything", "doesn't matter", "whatever"}
```

Если ответ содержит relaxed-маркер → прекращаем clarification, строим рекомендации.

---

## Поток данных: жизненный цикл сессии

```
1. start_session()
   → FileSessionStore.create_session()
   → SessionMemory(session_id=uuid, analytics.mark_started())
   → save → memory/sessions/{id}.json

2. handle_message("хочу фильм")
   → load_session(id)
   → session.turns.append(ConversationTurn(role="user", message="..."))
   → session.analytics.mark_turn_started()
   → ... обработка ...
   → session.analytics.mark_turn_completed(latency_ms=..., response_type="...")
   → save_session(session)

3. handle_message("exit")
   → завершение цикла
   → сессия остаётся на диске для последующего анализа
```

---

## Где используется

| Компонент | Как использует память |
|---|---|
| `ConversationService` | Основной потребитель: load/save, turn classification, preference memory |
| `chat/cli.py` | start_session(), handle_message() |
| `api/server.py` | create_session, handle_message, load_session, delete_session |
| `observability/report.py` | Читает все session JSON для генерации отчёта |
| Тесты | Создают временные сессии для проверки логики |
