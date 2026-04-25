# Netflix Recommendation Agent

Мультиагентная система рекомендаций контента Netflix.

## Архитектура

Система использует 3 агента:

1. **Preference Analyst** — анализирует пользовательский запрос  
2. **Netflix Search Specialist** — ищет фильмы и сериалы в датасете  
3. **Recommendation Finalizer** — формирует финальные рекомендации  

Каждый агент использует свою модель и параметры из `.env`.

---

## LLM API

Используется OpenAI-compatible API через OpenCode Go.

```env
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1

ANALYST_MODEL=glm-5.1
SEARCH_MODEL=glm-5.1
FINALIZER_MODEL=glm-5.1
```
## Система памяти

Используется семантическая база знаний на ChromaDB.
В неё загружаются markdown-файлы из папки kb.

## Запуск
```Bash
cp .env.example .env
docker compose up --build
```

## Проверка пользователя контейнера
```Bash
docker compose run --rm netflix-agent whoami
```

Ожидаемый результат:

```Bash
appuser
```
## Метрики

После запуска доступны метрики Prometheus:

```
http://localhost:8001/metrics
```
## Структура проекта

```
app/
├── tools/
├── knowledge/
├── monitoring/
├── evals/
├── llm/
├── config.py
└── main.py

data/
kb/
logs/
chroma_db/
```

## Evals
```
python -m app.evals.run_evals
```

