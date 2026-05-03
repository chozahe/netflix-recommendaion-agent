# Контракты — Pydantic-схемы

## Обзор

Все данные между компонентами передаются через строго типизированные Pydantic-модели. Это обеспечивает валидацию и самодокументируемость.

**Файлы:** `app/contracts/`

---

## AnalystIntent

**Файл:** `app/contracts/analyst.py`

Структурированное намерение пользователя. Выход Analyst'а, вход Searcher'а.

```python
class AnalystIntent(BaseModel):
    query: str                                    # оригинальный запрос
    content_type: str | None = None               # "Movie" / "TV Show" / None
    hard_constraints: dict = {}                   # явные требования
    soft_preferences: dict = {}                   # описательные подсказки
    topic_hypotheses: list[str] = []              # вероятиные темы
    genre_hypotheses: list[str] = []              # вероятные жанры
    mood_hypotheses: list[str] = []               # настроения
    language: str = "ru"                          # "ru" или "en"
    explanation: str = ""                         # пояснение
    needs_clarification: bool = False             # нужен ли уточняющий вопрос
    clarification_question: str | None = None     # вопрос
    missing_slots: list[str] = []                 # недостающие поля
    confidence: float = 1.0                       # уверенность 0.0–1.0
    external_signals: list[str] = []              # сигналы для внешней проверки
    clarification_count: int = 0                  # счётчик уточнений
```

### hard_constraints

Ключи: `year_from`, `year_to`, `country`, `rating`

### soft_preferences

Ключи: `pace`, `mood`, `topic` и другие описательные категории.

### external_signals

Формат: `prefix:value`

| Prefix | Пример | Описание |
|---|---|---|
| `era:` | `era:1980s` | Временная эпоха |
| `actor:` | `actor:winona_ryder` | Актёр |
| `vibe:` | `vibe:mysterious` | Настроение/атмосфера |

---

## ConversationResponse

**Файл:** `app/contracts/conversation.py`

Ответ ConversationService. Возвращается пользователю в CLI и API.

```python
class ConversationResponse(BaseModel):
    type: str                                     # "clarification" / "recommendations" / "refined_recommendations"
    session_id: str                               # ID сессии
    message: str                                  # текст ответа
    recommendations: list[StoredRecommendation]   # рекомендации
    state: str                                    # текущее состояние сессии
```

---

## SearchResult

**Файл:** `app/contracts/search.py`

Результат работы Searcher'а.

```python
class SearchResult(BaseModel):
    status: str                                   # "ok" / "no_results"
    selected: list[Candidate]                     # выбранные кандидаты
    discarded: list[Candidate]                    # отброшенные
    explanation: str                              # пояснение
```

---

## Candidate

**Файл:** `app/contracts/search.py`

Один кандидат из каталога.

```python
class Candidate(BaseModel):
    title: str
    type: str | None = None                       # "Movie" / "TV Show"
    release_year: int | None = None
    description: str | None = None
    listed_in: str | None = None                  # жанры/категории
    cast: str | None = None
    country: str | None = None
    rating: str | None = None
    duration: str | None = None
    match_features: dict | None = None            # features скоринга
```

### match_features

```json
{
  "title_exact": true,
  "title_prefix": false,
  "title_overlap": 2,
  "description_overlap": 5,
  "listed_in_overlap": 1,
  "cast_overlap": 0,
  "mode": "hybrid"
}
```

---

## StoredRecommendation

**Файл:** `app/memory/models.py`

Рекомендация, сохранённая в памяти сессии.

```python
class StoredRecommendation(BaseModel):
    title: str
    reason: str | None = None
    poster_url: str | None = None
```

---

## FeedbackSignal

**Файл:** `app/contracts/feedback.py`

Сигнал фидбека от пользователя.

```python
class FeedbackSignal(BaseModel):
    kind: str                                     # "age" / "pace" / "type" / "generic_rejection"
    value: str | None = None                      # конкретное значение
    values: list[str]                             # все распознанные сигналы
    requires_refinement: bool                     # нужен ли refinement
```

### Примеры

| Сообщение пользователя | kind | value | values |
|---|---|---|---|
| "это слишком старое" | age | newer | ["age:newer"] |
| "слишком медленно" | pace | faster | ["pace:faster"] |
| "хочу сериал вместо фильма" | type | "сериал вместо фильма" | [] |
| "отстой" | generic_rejection | None | [] |

---

## SessionMemory

**Файл:** `app/memory/models.py`

Полная память сессии. См. [memory.md](memory.md) для полной структуры.

---

## ConversationTurn

**Файл:** `app/memory/models.py`

Один ход в диалоге.

```python
class ConversationTurn(BaseModel):
    role: str      # "user" или "assistant"
    message: str   # текст
```

---

## Поток контрактов

```
User message
    ↓
ConversationService.handle_message()
    ↓
run_analyst() → AnalystIntent
    ↓
run_searcher(intent) → SearchResult (JSON)
    ↓
maybe_enrich_search_output() → enriched dict
    ↓
_extract_recommendations() → list[StoredRecommendation]
    ↓
run_finalizer() → {message, posters}
    ↓
_merge_posters() → StoredRecommendation.poster_url
    ↓
ConversationResponse(type, session_id, message, recommendations, state)
    ↓
CLI / API → пользователь
```
