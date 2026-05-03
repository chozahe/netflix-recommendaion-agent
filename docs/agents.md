# Агенты — Analyst, Searcher, Finalizer

## Как создаются агенты

Все агенты собираются в `app/agents/definitions.py` через функцию `build_*_agent()`.
Промпты загружаются из `prompts/*.md` в `app/agents/__init__.py`.

```python
def build_analyst_agent() -> Agent:
    return Agent(
        role="Preference Analyst",
        goal="Extract structured search intent from user queries",
        backstory=ANALYST_PROMPT,   # из prompts/analyst.md
        tools=[],                    # нет инструментов
        llm=create_analyst_llm(),    # из app/llm/factory.py
        verbose=settings.agents_verbose,
        allow_delegation=False,
        max_iter=settings.analyst_max_iter,
    )
```

## 1. Analyst

**Файл:** `app/agents/definitions.py:14-24`
**Промпт:** `prompts/analyst.md`
**Модель по умолчанию:** `qwen3.5-plus` (температура 0.1)

### Задача

Превратить пользовательский текст в строгий JSON-интент.

### Вход

Пользовательский запрос, например: `"посоветуй сериал с вайбом 80-х и Вайноной Райдер"`

### Выход — AnalystIntent

| Поле | Тип | Описание |
|---|---|---|
| `query` | str | Оригинальный запрос |
| `content_type` | str \| None | "Movie", "TV Show" или null |
| `hard_constraints` | dict | Явные требования: year_from, year_to, country, rating |
| `soft_preferences` | dict | Описательные подсказки: moods, topics |
| `topic_hypotheses` | list[str] | Вероятные темы |
| `genre_hypotheses` | list[str] | Вероятные жанры Netflix |
| `mood_hypotheses` | list[str] | Настроения (dark, suspenseful...) |
| `language` | str | "ru" или "en" |
| `explanation` | str | Краткое пояснение интерпретации |
| `needs_clarification` | bool | Нужен ли уточняющий вопрос |
| `clarification_question` | str \| None | Вопрос если clarification нужен |
| `missing_slots` | list[str] | Какие поля блокируют поиск |
| `confidence` | float | Уверенность 0.0–1.0 |
| `external_signals` | list[str] | Сигналы для внешней проверки (era:1980s, actor:winona_ryder) |
| `clarification_count` | int | Счётчик уточнений |

### Правила

1. Не придумывает hard constraints — только то, что сказал пользователь
2. Определяет язык: кириллица → ru
3. Мапит темы на Netflix-категории (космос → Sci-Fi & Fantasy)
4. Если запрос слишком размытый — ставит `needs_clarification=true`
5. Сигналы, которых нет в CSV (эра, актёр, вайб) — в `external_signals`
6. При rejection предыдущих рекомендаций — переинтерпретирует запрос

### Fallback

Если LLM вернул пустой или невалидный ответ:
```python
build_fallback_intent(query)  # минимальный intent, raw query → Searcher
```

### Где вызывается

- `app/orchestration/pipeline.py:93` — `run_analyst()`
- `app/conversation/service.py:114` — первый вызов
- `app/conversation/service.py:91` — повторный после clarification

---

## 2. Searcher

**Файл:** `app/agents/definitions.py:28-42`
**Промпт:** `prompts/searcher.md`
**Модель по умолчанию:** `deepseek-v4-pro` (температура 0.0)

### Задача

Найти реальные тайтлы из Netflix CSV, используя инструменты.

### Инструменты

| Тулз | Описание |
|---|---|
| `NetflixSearch` | Поиск по CSV (5 режимов) |
| `FilterCandidates` | Фильтрация кандидатов |
| `InspectCandidate` | Инспекция match-features |

### Вход

```json
{
  "query": "оригинальный запрос",
  "intent": { ... AnalystIntent ... },
  "last_tool_result": {}
}
```

### Выход — SearchResult

| Поле | Тип | Описание |
|---|---|---|
| `status` | str | "ok" или "no_results" |
| `selected` | list[Candidate] | Выбранные рекомендации (до 5) |
| `discarded` | list[Candidate] | Отброшенные кандидаты |
| `explanation` | str | Пояснение выбора |

### Стратегия поиска

1. Начинает с `hybrid` или `description` для описательных запросов
2. Использует hard constraints из intent
3. Если результаты слабые — пробует другой route
4. Может inspect'ить кандидатов перед финальным выбором
5. Web enrichment — только после CSV retrieval, максимум 1 pass, 2-3 тайтла

### Fallback

Если агент не справляется:
```python
build_fallback_search_result(intent)  # прямой вызов NetflixSearchTool
```

### Где вызывается

- `app/orchestration/pipeline.py:168` — `run_searcher()`
- `app/conversation/service.py:220` — внутри `_build_recommendation_response()`

---

## 3. Finalizer

**Файл:** `app/agents/definitions.py:46-56`
**Промпт:** `prompts/finalizer.md`
**Модель по умолчанию:** `deepseek-v4-flash` (температура 0.4)

### Задача

Сформировать дружелюбный ответ на естественном языке из проверенных данных.

### Инструменты

| Тулз | Описание |
|---|---|
| `PosterLookup` | Поиск URL постера для верифицированного тайтла |

### Вход

- Оригинальный запрос
- Explanation из AnalystIntent
- SearchResult от Searcher

### Выход

```json
{
  "message": "текст ответа на естественном языке",
  "posters": [
    {"title": "Stranger Things", "poster_url": "https://..."}
  ]
}
```

### Правила

1. Не добавляет фактов, которых нет в SearchResult
2. PosterLookup — только для уже верифицированных тайтлов
3. Возвращает строгий JSON

### Где вызывается

- `app/orchestration/pipeline.py:195` — `run_finalizer()`
- `app/conversation/service.py:224` — внутри `_build_recommendation_response()`

---

## Ролевая конфигурация моделей

Каждый агент использует свою модель через `.env`:

```env
ANALYST_MODEL=openai/qwen3.5-plus       # качество анализа
SEARCH_MODEL=openai/deepseek-v4-pro     # качество поиска
FINALIZER_MODEL=openai/deepseek-v4-flash # скорость генерации
```

Фабрика LLM в `app/llm/factory.py` создаёт нужный экземпляр для каждого агента.

## Guardrails

| Параметр | Значение по умолчанию | Описание |
|---|---|---|
| `ANALYST_MAX_ITER` | 2 | Максимум итераций Analyst |
| `SEARCHER_MAX_ITER` | 3 | Максимум итераций Searcher |
| `FINALIZER_MAX_ITER` | 2 | Максимум итераций Finalizer |
| `LLM_TIMEOUT_SECONDS` | 45 | Таймаут на вызов LLM |
| `AGENTS_VERBOSE` | true | Подробный вывод CrewAI |
