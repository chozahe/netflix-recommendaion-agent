# Netflix Recommendation Agent

Мультиагентная система рекомендаций контента Netflix.

## Архитектура

Система использует 3 агента:

1. **Preference Analyst** — анализирует пользовательский запрос  
2. **Netflix Search Specialist** — ищет фильмы и сериалы в датасете  
3. **Recommendation Finalizer** — формирует финальные рекомендации  

Каждый агент использует свою модель и параметры из `.env`.

## LLM API

Используется OpenAI-compatible API через OpenCode Go.

```env
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
ANALYST_MODEL=qwen3.5-plus
SEARCH_MODEL=deepseek-v4-pro
FINALIZER_MODEL=deepseek-v4-flash
```

## Система памяти

Используется семантическая база знаний на ChromaDB.
В неё загружаются markdown-файлы из папки `kb`.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main "хочу фильм про космос"
```

## Метрики

После запуска доступны метрики Prometheus:

```text
http://localhost:8001/metrics
```

## Структура проекта

```text
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

```bash
python -m app.evals.run_evals
```

