# Тулзы — инструменты агентов

## Обзор

В проекте 4 тулза, построенных на `crewai.tools.BaseTool`. Каждый тулз — это Python-класс с методом `_run()`, который CrewAI вызывает когда LLM решает использовать инструмент.

| Тулз | Агент | Назначение |
|---|---|---|
| `NetflixSearch` | Searcher | Поиск по CSV-каталогу |
| `FilterCandidates` | Searcher | Фильтрация найденных кандидатов |
| `InspectCandidate` | Searcher | Инспекция match-features |
| `PosterLookup` | Finalizer | Поиск URL постера |

## Как работает вызов тулза

```
1. LLM видит description тулза в своём системном промпте
2. LLM решает вызвать тулз и генерирует JSON с аргументами
3. CrewAI парсит вызов и запускает Tool._run(**args)
4. Результат (JSON-строка) возвращается LLM
5. LLM продолжает reasoning или формирует ответ
```

---

## 1. NetflixSearch

**Файл:** `app/tools/netflix_search.py`
**Агент:** Searcher

### Назначение

Поиск по `data/netflix_titles.csv` (8807 строк) через `CatalogSearchEngine`.

### Входные параметры

| Параметр | Тип | Описание |
|---|---|---|
| `content_type` | str \| None | "Movie" или "TV Show" |
| `year_from` | int \| None | Минимальный год |
| `year_to` | int \| None | Максимальный год |
| `country` | str \| None | Страна (частичное совпадение) |
| `rating` | str \| None | Возрастной рейтинг (точное совпадение) |
| `genre` | str \| None | Жанр (частичное совпадение в listed_in) |
| `text_query` | str \| None | Текстовый запрос |
| `mode` | str | Режим: title, description, listed_in, cast, hybrid |
| `limit` | int | Максимум результатов (default 10, max 20) |

### Режимы поиска

| Режим | Как работает | Когда использовать |
|---|---|---|
| `title` | Точное совпадение названия + префикс + token overlap | Поиск по названию ("interstellar") |
| `description` | Token overlap по описанию | Описательные запросы ("про космос") |
| `listed_in` | Token overlap по жанрам/категориям | Поиск по жанру ("sci-fi series") |
| `cast` | Token overlap по актёрам | Поиск по актёру ("with Leonardo DiCaprio") |
| `hybrid` | Комбинация всех режимов с весами | Универсальный режим по умолчанию |

### Скоринг в hybrid-режиме

```
score = (100 × title_exact) + (20 × title_prefix) +
        (8 × title_overlap) + (10 × description_overlap) +
        (6 × listed_in_overlap) + (4 × cast_overlap)
```

### Выход

```json
{
  "count": 5,
  "filters_applied": ["content_type=Movie", "mode=hybrid", "text~космос"],
  "results": [
    {
      "title": "Interstellar",
      "type": "Movie",
      "release_year": 2014,
      "description": "...",
      "listed_in": "...",
      "cast": "...",
      "match_features": {
        "title_exact": false,
        "title_prefix": false,
        "title_overlap": 1,
        "description_overlap": 3,
        "listed_in_overlap": 0,
        "cast_overlap": 0,
        "mode": "hybrid"
      }
    }
  ]
}
```

---

## 2. FilterCandidates

**Файл:** `app/tools/filter_candidates.py`
**Агент:** Searcher

### Назначение

Применить жёсткие фильтры к уже найденным кандидатам без повторного поиска.

### Входные параметры

| Параметр | Тип | Описание |
|---|---|---|
| `candidates` | list[dict] | Кандидаты из предыдущего поиска |
| `content_type` | str \| None | Фильтр по типу |
| `year_from` | int \| None | Минимальный год |
| `year_to` | int \| None | Максимальный год |
| `country` | str \| None | Страна |
| `rating` | str \| None | Рейтинг |
| `genre` | str \| None | Жанр |

### Как фильтрует

- `content_type` — точное совпадение по полю `type`
- `year_from/to` — сравнение `release_year >= / <=`
- `country` — substring match (case-insensitive)
- `rating` — точное совпадение
- `genre` — substring match в `listed_in` (case-insensitive)

### Выход

```json
{
  "count": 3,
  "results": [ ... отфильтрованные кандидаты ... ]
}
```

---

## 3. InspectCandidate

**Файл:** `app/tools/inspect_candidate.py`
**Агент:** Searcher

### Назначение

Показать, почему конкретный кандидат попал в выдачу — компактная сводка match-features.

### Входные параметры

| Параметр | Тип | Описание |
|---|---|---|
| `candidate` | dict | Один кандидат из результатов поиска |

### Выход

```json
{
  "title": "Stranger Things",
  "type": "TV Show",
  "release_year": 2016,
  "match_features": {
    "title_exact": false,
    "title_prefix": false,
    "title_overlap": 2,
    "description_overlap": 1,
    "listed_in_overlap": 3,
    "cast_overlap": 0,
    "mode": "hybrid"
  },
  "summary": "Stranger Things — genre overlap=3, description overlap=1"
}
```

Полезно когда Searcher хочет понять: "почему этот тайтл вообще здесь?"

---

## 4. PosterLookup

**Файл:** `app/tools/poster_lookup.py`
**Агент:** Finalizer

### Назначение

Найти URL постера для уже верифицированного тайтла через web search.

### Входные параметры

| Параметр | Тип | Описание |
|---|---|---|
| `title` | str | Название тайтла (обязательно) |
| `content_type` | str \| None | "Movie" или "TV Show" |
| `release_year` | int \| None | Год выпуска для точности |

### Как ищет постер

1. Строит поисковый запрос: `"Title" film 2014`
2. Ищет через DuckDuckGo (`search_web`)
3. Приоритизирует источники: Wikipedia > IMDb/Rotten Tomatoes > Britannica > другие
4. Для Wikipedia — парсит infobox и извлекает theatrical poster
5. Для остальных — извлекает `og:image` из HTML
6. Фильтрует логотипы (проверяет URL на logo/wordmark/brand)
7. Если ничего не найдено — возвращает `null`

### Выход

```json
{
  "poster_url": "https://upload.wikimedia.org/wikipedia/en/..."
}
```

или

```json
{
  "poster_url": null
}
```

### Важное правило

PosterLookup **не должен** использоваться для поиска новых тайтлов. Только для тех, что уже вернул Searcher.

---

## Зависимости тулзов

```
NetflixSearch
    └─ CatalogSearchEngine (app/search/catalog.py)
         ├─ normalize_text, tokenize_query (app/search/text.py)
         └─ pandas DataFrame

FilterCandidates
    └─ filter_candidate_rows (чистая функция)

InspectCandidate
    └─ match_features из результатов поиска

PosterLookup
    └─ search_poster (app/search/image_search.py)
         ├─ search_web (app/search/web_search.py) → duckduckgo_search
         └─ curl_cffi (опционально, для impersonate Chrome)
```
