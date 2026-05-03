# Поиск — Catalog, Enrichment, Web Search

## Обзор

Поисковый слой состоит из трёх частей:

1. **CatalogSearchEngine** — детерминированный поиск по CSV
2. **Enrichment** — опциональный reranking через web search
3. **Web Search** — bounded DuckDuckGo lookup

---

## 1. CatalogSearchEngine

**Файл:** `app/search/catalog.py`

### Что делает

Ищет по `data/netflix_titles.csv` (8807 строк) с применением фильтров и скорингом.

### Инициализация

```python
engine = CatalogSearchEngine(df)  # pandas DataFrame
```

При инициализации заполняет пустые значения в колонках:
`title`, `country`, `rating`, `duration`, `listed_in`, `description`, `cast`

### Метод search()

```python
results = engine.search(
    query="космос",
    mode="hybrid",
    hard_filters={"content_type": "Movie", "year_from": 2010},
    limit=10
)
```

### Порядок выполнения

1. **Применяет hard filters** — отсеивает строки по content_type, year, country, rating, genre
2. **Нормализует запрос** — `normalize_text()` → lowercase, убирает пунктуацию
3. **Токенизирует запрос** — `tokenize_query()` → список токенов длиной > 1
4. **Скорит каждого кандидата** — `_score_candidate()` по выбранному режиму
5. **Фильтрует по score > 0** — убирает нерелевантные
6. **Сортирует по score** — descending
7. **Возвращает top N** — максимум `min(limit, 20)`

### Режимы скоринга

| Режим | Формула |
|---|---|
| `title` | `100×exact + 25×prefix + 10×overlap` |
| `description` | `10×description_overlap` |
| `listed_in` | `10×listed_in_overlap` |
| `cast` | `10×cast_overlap` |
| `hybrid` | `100×exact + 20×prefix + 8×title_overlap + 10×desc_overlap + 6×listed_in + 4×cast` |

### Match features

Каждый кандидат возвращается с `match_features`:

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

## 2. Text Normalization

**Файл:** `app/search/text.py`

### normalize_text()

- Lowercase
- Убирает пунктуацию
- Убирает лишние пробелы

### tokenize_query()

- Разбивает по пробелам
- Оставляет только токены длиной > 1

Пример: `"Что-нибудь мрачное про космос"` → `["что", "мрачное", "про", "космос"]`

---

## 3. Enrichment

**Файл:** `app/search/enricher.py`

### Когда срабатывает

`should_enrich_results()` возвращает `True` если:
- `WEB_ENRICHMENT_ENABLED=true`
- Есть кандидаты (`candidate_count > 0`)
- Запрос содержит vibe-маркеры ИЛИ external_signals

### Vibe-маркеры

```python
VIBE_MARKERS = {"мрач", "атмосфер", "vibe", "moody", "sci-fi", "sci fi", "вайб"}
```

### External signal prefixes

```python
EXTERNAL_SIGNAL_PREFIXES = ("era:", "actor:", "vibe:")
```

### Как работает

1. Берёт top `WEB_ENRICHMENT_MAX_TITLES` (default 3) тайтлов
2. Для каждого ищет в web: `"{title} era:1980s actor:winona_ryder"`
3. Скорит snippets на совпадение с external_signals
4. Возвращает `confidence_boost` = число совпавших сигналов
5. `maybe_enrich_search_output()` в pipeline rerank'ит по confidence_boost

### Guardrails

- Не запускается до CSV retrieval
- Максимум 1 pass
- Максимум 2-3 тайтла
- При timeout/failure → graceful degradation (no enrichment)
- **Никогда не добавляет новые тайтлы**

---

## 4. Web Search

**Файл:** `app/search/web_search.py`

### search_web()

```python
snippets = search_web(
    query="Stranger Things era:1980s",
    timeout_seconds=5,
    max_results=5
)
```

Использует `duckduckgo_search.DDGS` для текстового поиска.

### enrich_titles()

Для каждого тайтла:
1. Строит запрос: `"{title} {external_signals}"`
2. Ищет в web
3. Скорит snippets через `_score_result()`

### _score_result()

Для каждого external_signal проверяет, есть ли он в snippet text:

| Signal | Как матчится |
|---|---|
| `actor:winona_ryder` | `"winona ryder"` в тексте |
| `era:1980s` | `"1980s"`, `"1980"`, `"80s"`, `"80's"` в тексте |
| `vibe:mysterious` | `"mysterious"` в тексте |

Возвращает:
```json
{
  "title": "Stranger Things",
  "matched_external_signals": ["era:1980s", "actor:winona_ryder"],
  "confidence_boost": 2,
  "evidence": ["https://wikipedia.org/...", "https://imdb.com/..."]
}
```

---

## 5. Image Search (Poster Lookup)

**Файл:** `app/search/image_search.py`

### search_poster()

```python
url = search_poster(
    title="Interstellar",
    content_type="Movie",
    release_year=2014,
    timeout_seconds=5
)
```

### Алгоритм

1. Строит запрос: `"Interstellar" film 2014`
2. Ищет через DuckDuckGo
3. Приоритизирует источники:
   - Wikipedia (infobox poster) — приоритет 0
   - IMDb / Rotten Tomatoes — приоритет 1
   - Britannica — приоритет 2
   - Остальные — приоритет 50
   - Официальные студии — приоритет 100 (деприоритизируются, часто только логотип)

4. Для Wikipedia:
   - Парсит infobox table
   - Находит `<img>` с wikimedia URL
   - Конвертирует thumbnail URL → full-size URL

5. Для остальных:
   - Fetch'ает страницу через curl_cffi (impersonate Chrome)
   - Извлекает `og:image` meta tag
   - Фильтрует логотипы по URL (logo, wordmark, brand, icon, favicon)

6. При ошибке → `null`

---

## Поток данных: полный путь поиска

```
User: "посоветуй сериал с вайбом 80-х и Вайноной Райдер"
    ↓
Analyst → external_signals: ["era:1980s", "actor:winona_ryder", "vibe:mysterious"]
    ↓
Searcher → NetflixSearch(mode="hybrid", text_query="...")
    ↓
CatalogSearchEngine → скорит 8807 строк → top 10 кандидатов
    ↓
maybe_enrich_search_output()
    ↓ should_enrich_results() = True (есть vibe-маркеры + external_signals)
    ↓
enrich_shortlisted_titles(top 3)
    ↓
enrich_titles() → search_web() → score snippets
    ↓
rerank по confidence_boost
    ↓
Finalizer → PosterLookup для верифицированных тайтлов
    ↓
search_poster() → web search → Wikipedia/og:image
    ↓
Ответ с рекомендациями + poster_url
```
