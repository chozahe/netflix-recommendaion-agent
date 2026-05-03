Мультиагентная система рекомендаций Netflix — agentic search v2

1. ОБЩИЕ ПОЛОЖЕНИЯ  
1.1. Наименование проекта

Netflix Recommendation Agent — локальная мультиагентная система рекомендаций контента Netflix с agentic search loop и детерминированными search primitives.

1.2. Назначение системы  
Создание интеллектуальной системы, которая:

* Анализирует пользовательский запрос на естественном языке  
* Преобразует его в структурированный search intent  
* Ищет релевантные фильмы/сериалы в реальном каталоге Netflix (CSV) через прозрачные tools  
* Формирует персонализированные рекомендации только из верифицированных данных  
* Ограничивает долгие agent loops через guardrails и fallback-механизмы

1.3. Цели проекта

| № | Цель | Критерий достижения |
| :---- | :---- | :---- |
| 1 | Реализовать честную 3-агентную архитектуру | Analyst, Searcher, Finalizer реально разделены по ответственности |
| 2 | Упростить среду разработки | Полностью local-first запуск без Docker |
| 3 | Интегрировать бюджетные модели OpenCode Go | Ролевой подбор моделей + универсальный клиент |
| 4 | Улучшить качество поиска | Описательные запросы ищутся через agentic loop и прозрачные retrieval routes |
| 5 | Снизить хрупкость системы | Fallback для Analyst/Searcher + bounded iterations + timeout |
| 6 | Подготовить почву для evals | Локальный eval runner и тесты по слоям |
| 7 | Минимализировать архитектуру | Убраны ChromaDB, kb-файлы, детерминированные экстракторы — Analyst думает сам |

1.4. Область применения

* Персональные рекомендации контента  
* Демонстрация agentic architecture  
* Учебный проект по архитектуре AI-агентов и retrieval systems

2. ТРЕБОВАНИЯ К АРХИТЕКТУРЕ  
2.1. Общая схема системы

Пайплайн линеен: **Analyst → Searcher → Finalizer**

Searcher является центром поиска, а не форматировщиком готового результата.

2.2. Обоснование выбора 3 агентов

3 агента дают хороший баланс между качеством и сложностью:

* **Analyst** — extraction и intent contract (LLM-only, без tools)  
* **Searcher** — search strategy и tool loop  
* **Finalizer** — финальный UX-ответ

Это позволяет отдельно улучшать intent extraction, retrieval quality и user-facing wording.

2.3. Технологический стек

| Компонент | Технология | Обоснование выбора |
| :---- | :---- | :---- |
| Оркестрация агентов | CrewAI | Простая интеграция tools и линейного пайплайна |
| LLM client layer | LangChain + кастомный provider adapter | Единый интерфейс для OpenAI-compatible и Anthropic-style endpoints |
| Работа с данными | Pandas | Быстрая фильтрация и преобразование CSV |
| Мониторинг | Prometheus Client | Простые локальные метрики |
| Логирование | Structlog | Структурированные event logs |

3. ЛОКАЛЬНАЯ СРЕДА И ЗАПУСК  
3.1. Подход к изоляции

Docker не используется. Выбран **local-first workflow**:

* `python -m venv .venv`  
* `source .venv/bin/activate`  
* `pip install -r requirements.txt`  
* `python -m app.main "..."`

Преимущества: быстрее iteration loop, проще отладка, меньше инфраструктурного шума.

4. ВЫБОР МОДЕЛЕЙ И ПРОВАЙДЕРА  
4.1. OpenCode Go как основной провайдер

Используется OpenCode Go через `https://opencode.ai/zen/go/v1`.

4.2. Базовый модельный профиль

* **Analyst** → `openai/qwen3.5-plus` — дёшево и стабильно выдаёт structured intent  
* **Searcher** → `openai/deepseek-v4-pro` — самый "мыслящий" агент  
* **Finalizer** → `openai/deepseek-v4-flash` — приятный стиль, аккуратность

4.3. Универсальный клиент

Поддерживает OpenAI-compatible `/chat/completions` и Anthropic-style `/messages` через единый provider layer.

5. СИСТЕМНЫЕ ПРОМПТЫ  
5.1. Analyst

Analyst — LLM-only агент без инструментов. Анализирует запрос самостоятельно и возвращает контракт:

* `query`  
* `content_type`  
* `hard_constraints`  
* `soft_preferences`  
* `topic_hypotheses`  
* `genre_hypotheses`  
* `mood_hypotheses`  
* `language`  
* `explanation`

5.2. Searcher

Получает structured intent, запускает tool-driven search loop. Может: выбрать route, повторить поиск, ослабить soft-предпочтения, отобрать лучших кандидатов. Возвращает strict JSON с selected/discarded/explanation.

5.3. Finalizer

Пишет дружелюбный ответ, используя только верифицированный Searcher output.

6. TOOLS АГЕНТОВ  

6.1. NetflixSearch

Прозрачный retrieval tool с режимами: `title`, `description`, `listed_in`, `cast`, `hybrid`. Hard-фильтры: content_type, year_from/to, country, rating, genre.

6.2. FilterCandidates

Применяет hard filters к candidate pool.

6.3. InspectCandidate

Компактное объяснение, почему title попал в выдачу: match_features (title_exact, description_overlap, listed_in_overlap).

7. ПОИСК И RETRIEVAL  
7.1. Новый принцип поиска

Searcher не "помнит фильмы". Система использует:

* text normalization  
* title exact/prefix/token overlap  
* description overlap  
* listed_in / genre route  
* candidate ranking через match features

7.2. Agentic search loop

Searcher: получает intent → запускает retrieval → оценивает candidate pool → пробует альтернативный route → выбирает 3–5 лучших → возвращает SearchResult.

8. ЗАЩИТА ОТ ХРУПКОСТИ И ДОЛГИХ ЦИКЛОВ  
8.1. Guardrails

* `LLM_TIMEOUT_SECONDS`  
* `ANALYST_MAX_ITER`  
* `SEARCHER_MAX_ITER`  
* `FINALIZER_MAX_ITER`

8.2. Fallback-механизмы

* **Analyst fallback** — минимальный intent (пустые constraints, raw query → Searcher)
* **Searcher fallback** — прямой вызов NetflixSearchTool

9. МОНИТОРИНГ И EVALS  
9.1. Логирование

`structlog` для событий: `analyst_started`, `searcher_started`, `finalizer_finished`, `request_completed`.

9.2. Метрики

Prometheus endpoint на порту `8001`.

9.3. Evals

`app.evals.run_evals` — ручная проверка качества и latency на наборе запросов.

10. ИТОГОВОЕ СОСТОЯНИЕ ПРОЕКТА  

Реализованы:

* contracts  
* local-first runtime  
* search primitives  
* transparent tools (3 шт.)  
* universal model routing  
* orchestration layer с fallback'ами  
* guardrails против slow loops  
* local eval scaffolding  
* минималистичная архитектура без ChromaDB/kb/детерминированных экстракторов

11. ЗАКЛЮЧЕНИЕ  

Архитектура упрощена до сути: Analyst думает сам (LLM-only), Searcher работает через tools против реального CSV, Finalizer оформляет. Никакой ChromaDB, никаких md-файлов знаний, никаких детерминированных экстракторов — только то, что реально нужно для работы.

Предыдущий документ сохранён как исторический пример исходного проектного замысла.
