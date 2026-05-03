# ConversationService — управление диалогом

## Назначение

`ConversationService` — слой над агентным пайплайном, который превращает набор отдельных агентов в связный многоходовый диалог с памятью, уточнениями и обработкой фидбека.

**Файл:** `app/conversation/service.py`

---

## Жизненный цикл сессии

```
start_session()
    ↓
handle_message("хочу фильм про космос")
    ├─ run_analyst() → AnalystIntent
    ├─ needs_clarification? → вернуть вопрос
    └─ иначе → _build_recommendation_response()
         ├─ run_searcher() → SearchResult
         ├─ maybe_enrich_search_output() → reranked
         ├─ run_finalizer() → message + posters
         └─ сохранить сессию
    ↓
handle_message("это слишком старое")
    ├─ _parse_feedback() → negative feedback detected
    ├─ _handle_feedback() → refinement
    ├─ _build_refined_intent() → обновить constraints
    └─ _build_recommendation_response() → новые рекомендации
    ↓
handle_message("exit")
    └─ завершение
```

---

## Состояния сессии

| State | Описание | Когда |
|---|---|---|
| `idle` | Начальное состояние | При создании сессии |
| `awaiting_clarification` | Ждём ответ на уточняющий вопрос | Analyst решил что запрос размытый |
| `recommended` | Рекомендации показаны | После успешного recommendation round |
| `refining` | Обработка фидбека | После негативного отзыва пользователя |

---

## Clarification (уточнения)

### Политика

- Максимум **2 уточнения** до первой рекомендации
- Analyst решает, нужен ли clarification
- Если пользователь отвечает `любое / пофиг / не важно` — прекращаем уточнения сразу
- После relaxed-ответа строим intent из того, что есть

### Flow

```
User: "хочу что-нибудь мрачное"
Analyst: needs_clarification=true, question="Это фильм или сериал?"
    ↓ state = awaiting_clarification

User: "фильм"
    ↓ merged_intent → run_analyst() → recommendations
    ↓ state = recommended
```

### Relaxed-answer detection

Функция `is_relaxed_clarification_answer()` в `app/memory/merge.py` детектит:
- `любое`, `пофиг`, `не важно`, `anything`, `doesn't matter`

При обнаружении → сразу строим рекомендации без повторного Analyst.

---

## Feedback handling

### Детекция негативного фидбека

`_parse_feedback()` в `app/conversation/service.py:270` ищет маркеры:

| Маркер | Kind | Value |
|---|---|---|
| "стар", "old" | age | newer |
| "медлен", "slow" | pace | faster |
| "сериал", "фильм" | type | текст сообщения |

### Обработка

1. Если фидбек конкретный → `_build_refined_intent()` → новый поиск
2. Если фидбек слишком общий → просим уточнить

### Refinement intent

`_build_refined_intent()` обновляет:
- `hard_constraints["year_from"] = max(..., 2018)` при "старое"
- `soft_preferences["pace"] = ["fast"]` при "медленное"
- `content_type = "TV Show" / "Movie"` при явном указании типа
- Переиспользует `accepted_soft_preferences` из памяти сессии

---

## Preference memory

### Что сохраняется

| Тип | Где хранится | Когда обновляется |
|---|---|---|
| Accepted soft preferences | `session.accepted_soft_preferences` | При успешных рекомендациях |
| Rejected soft preferences | `session.rejected_soft_preferences` | При негативном фидбеке |
| External signals | `session.external_signal_history` | При каждом Analyst intent |

### Как используется

`_remember_intent_preferences()` извлекает soft preferences из intent и добавляет в память сессии. При refinement — переиспользует accepted preferences.

---

## Recommendation response

`_build_recommendation_response()` — основной путь генерации рекомендаций:

```python
def _build_recommendation_response(session, intent, message, response_type):
    # 1. Поиск
    search_output = run_searcher(intent)

    # 2. Enrichment (опционально)
    enriched_output = maybe_enrich_search_output(intent, search_output)

    # 3. Извлечение рекомендаций
    recommendations = _extract_recommendations(enriched_output)

    # 4. Finalizer + постеры
    finalizer_output = run_finalizer(message, intent, enriched_output)
    recommendations = _merge_posters(recommendations, finalizer_output["posters"])

    # 5. Обновление памяти
    _remember_intent_preferences(session, intent)
    session.last_recommendations = recommendations
    session.shown_titles.extend(new_titles)
    session.state = "recommended"

    # 6. Сохранение
    self.store.save_session(session)

    return ConversationResponse(...)
```

---

## Analytics (наблюдаемость)

Каждый ход обновляет `session.analytics`:

| Событие | Что обновляется |
|---|---|
| Начало хода | `turn_count++`, `user_turn_count++`, `last_updated_at` |
| Успешный ответ | `assistant_turn_count++`, `last_latency_ms`, `total_latency_ms`, `last_response_type` |
| Clarification | `clarification_turn_count++` |
| Recommendation | `recommendation_round_count++`, `recommended_titles_count`, `unique_titles_count` |
| Refinement | `refinement_round_count++` |
| Ошибка | `error_count++` |
| Fallback | `fallback_count++` |
| Enrichment | `enrichment_used_count++` |

---

## Structured logging

Каждое значимое событие логируется через `structlog`:

| Событие | Когда |
|---|---|
| `chat_session_started` | При создании сессии |
| `chat_turn_started` | В начале handle_message |
| `chat_turn_completed` | После успешного ответа |
| `chat_turn_failed` | При исключении |
| `clarification_requested` | Когда возвращается clarification |
| `recommendations_generated` | Когда возвращаются рекомендации |
| `refinement_generated` | Когда запускается refinement |

Поля в каждом событии: `session_id`, `turn_index`, `state`, `response_type`, `latency_ms`, `clarification_count`, `recommendation_count` и др.

---

## Зависимости

```
ConversationService
    ├─ FileSessionStore (app/memory/session_store.py)
    ├─ run_analyst, run_searcher, run_finalizer (app/orchestration/pipeline.py)
    ├─ maybe_enrich_search_output (app/orchestration/pipeline.py)
    ├─ merge_clarification_answer, is_relaxed_clarification_answer (app/memory/merge.py)
    ├─ get_logger (app/monitoring/logger.py)
    └─ SessionMemory, ConversationTurn, StoredRecommendation (app/memory/models.py)
```
