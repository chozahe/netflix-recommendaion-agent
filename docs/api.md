# API — FastAPI endpoints

## Обзор

HTTP API для программного взаимодействия с рекомендательной системой.

**Файлы:** `app/api/`

---

## Запуск

```bash
uvicorn app.api.server:app --host 127.0.0.1 --port 8000
```

---

## Endpoints

### POST /sessions

Создать новую chat-сессию.

**Request:** body не требуется

**Response:**
```json
{
  "session_id": "abc123-def456-...",
  "state": "idle"
}
```

---

### POST /chat

Отправить сообщение в сессию.

**Request:**
```json
{
  "session_id": "abc123-def456-...",
  "message": "хочу фильм про космос"
}
```

**Response:**
```json
{
  "type": "recommendations",
  "session_id": "abc123-def456-...",
  "message": "Вот несколько фильмов про космос...",
  "recommendations": [
    {
      "title": "Interstellar",
      "reason": null,
      "poster_url": "https://..."
    }
  ],
  "state": "recommended"
}
```

**Типы ответов:**

| type | Описание |
|---|---|
| `clarification` | Уточняющий вопрос |
| `recommendations` | Рекомендации |
| `refined_recommendations` | Уточнённые рекомендации после фидбека |

**Ошибки:**
- `404` — session_not_found

---

### GET /sessions/{session_id}

Получить состояние сессии.

**Response:**
```json
{
  "session_id": "abc123-def456-...",
  "state": "recommended",
  "turns": [
    {"role": "user", "message": "хочу фильм про космос"},
    {"role": "assistant", "message": "..."}
  ],
  "shown_titles": ["Interstellar", "Gravity"],
  "rejected_titles": [],
  "current_intent": { ... AnalystIntent ... },
  "last_recommendations": [ ... ],
  "feedback_signals": [],
  "clarification_count": 0,
  "accepted_soft_preferences": {},
  "rejected_soft_preferences": {},
  "external_signal_history": [],
  "analytics": { ... SessionAnalytics ... }
}
```

---

### DELETE /sessions/{session_id}

Удалить сессию.

**Response:**
```json
{
  "status": "deleted",
  "session_id": "abc123-def456-..."
}
```

---

## Схемы

**Файл:** `app/api/schemas.py`

| Схема | Описание |
|---|---|
| `ChatRequest` | session_id + message |
| `ChatResponse` | type + session_id + message + recommendations + state |
| `SessionResponse` | session_id + state |
| `SessionStateResponse` | полная сессия |

---

## Как работает

```
POST /chat
    ↓
ConversationService.handle_message(session_id, message)
    ↓
    ├─ load_session(session_id)
    ├─ classify: feedback? clarification? new query?
    ├─ run_analyst() / run_searcher() / run_finalizer()
    ├─ update session memory + analytics
    ├─ save_session(session)
    └─ return ConversationResponse
    ↓
ChatResponse.model_validate(response.model_dump())
```

---

## Отличие от CLI

| | CLI | API |
|---|---|---|
| Entry point | `app/chat_main.py` | `app/api/server.py` |
| Session management | Автоматическая одна сессия | Клиент управляет session_id |
| Metrics | ✅ setup_metrics() | ❌ не поднимается |
| Logging | ✅ setup_logging() | ❌ не поднимается |
| Poster rendering | `kitten icat` inline | JSON poster_url |
