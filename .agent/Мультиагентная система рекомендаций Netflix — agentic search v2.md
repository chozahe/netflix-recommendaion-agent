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

1.4. Область применения

* Персональные рекомендации контента  
* Демонстрация agentic architecture  
* Учебный проект по архитектуре AI-агентов и retrieval systems

2. ТРЕБОВАНИЯ К АРХИТЕКТУРЕ  
2.1. Общая схема системы

Пайплайн остаётся линейным:

**Analyst → Searcher → Finalizer**

Но теперь Searcher является реальным центром поиска, а не форматировщиком уже готового результата.

2.2. Обоснование выбора 3 агентов

3 агента по-прежнему дают хороший баланс между качеством и сложностью:

* **Analyst** отвечает за extraction и intent contract  
* **Searcher** отвечает за search strategy и tool loop  
* **Finalizer** отвечает за финальный UX-ответ

Это позволяет отдельно улучшать:

* intent extraction  
* retrieval/search quality  
* user-facing wording

2.3. Технологический стек

| Компонент | Технология | Обоснование выбора |
| :---- | :---- | :---- |
| Оркестрация агентов | CrewAI | Простая интеграция tools и линейного пайплайна |
| LLM client layer | LangChain + кастомный provider adapter | Единый интерфейс для OpenAI-compatible и Anthropic-style endpoints |
| Векторная БД | ChromaDB | Локальная knowledges cache без отдельного сервера |
| Работа с данными | Pandas | Быстрая фильтрация и преобразование CSV |
| Мониторинг | Prometheus Client | Простые локальные метрики |
| Логирование | Structlog | Структурированные event logs |

3. ЛОКАЛЬНАЯ СРЕДА И ЗАПУСК  
3.1. Подход к изоляции

В этой версии проекта Docker больше не является целевым способом запуска.

Выбран **local-first workflow**:

* `python -m venv .venv`  
* `source .venv/bin/activate`  
* `pip install -r requirements.txt`  
* `python -m app.main "..."`

Преимущества:

* быстрее iteration loop  
* проще отладка tools и orchestration  
* меньше инфраструктурного шума  
* проще локально гонять evals и pytest

4. ВЫБОР МОДЕЛЕЙ И ПРОВАЙДЕРА  
4.1. OpenCode Go как основной провайдер

Используется OpenCode Go через `https://opencode.ai/zen/go/v1`.

Ключевая идея новой архитектуры — не использовать одну модель для всех ролей, а распределять модели по агентам.

4.2. Базовый модельный профиль

Рекомендуемый baseline:

* **Analyst** → `openai/qwen3.5-plus`  
* **Searcher** → `openai/deepseek-v4-pro`  
* **Finalizer** → `openai/deepseek-v4-flash`

Причины выбора:

* Analyst должен дешево и стабильно выдавать structured intent  
* Searcher — самый “мыслящий” агент, ему выгодна более сильная модель  
* Finalizer не обязан быть дорогим, ему нужен приятный стиль и аккуратность

4.3. Универсальный клиент

Проект поддерживает:

* OpenAI-compatible `/chat/completions`  
* Anthropic-style `/messages`

Для этого используется единый provider layer, который:

* нормализует имена моделей  
* классифицирует backend  
* скрывает transport details от бизнес-логики

5. СИСТЕМНЫЕ ПРОМПТЫ  
5.1. Analyst

Analyst теперь должен возвращать контракт вида:

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

Searcher получает structured intent и запускает tool-driven search loop. Он может:

* выбрать route поиска  
* повторить поиск через другой route  
* ослабить soft-предпочтения  
* отобрать лучшие кандидаты  
* вернуть strict JSON с selected/discarded/explanation

5.3. Finalizer

Finalizer пишет дружелюбный ответ человеку, используя только верифицированный Searcher output.

6. СКИЛЛЫ / TOOLS АГЕНТОВ  
6.1. NetflixSearch

Теперь это не просто грубый фильтр по DataFrame, а прозрачный retrieval tool с режимами:

* `title`  
* `description`  
* `listed_in`  
* `cast`  
* `hybrid`

6.2. FilterCandidates

Применяет hard filters к уже полученному candidate pool.

6.3. InspectCandidate

Возвращает компактное объяснение, почему title вообще был найден.

6.4. PreferenceExtractor

Детерминированно извлекает базовые сигналы из пользовательского запроса и используется как safety net для Analyst fallback.

6.5. KnowledgeSearch

Даёт доступ к knowledges из `kb/*.md` для genre/rating/country/mood interpretation.

7. KNOWLEDGES И БАЗА ЗНАНИЙ  
Папка `kb/` по-прежнему содержит:

* `genre_mapping.md`  
* `rating_guide.md`  
* `mood_keywords.md`  
* `country_codes.md`  
* `recommendation_rules.md`

Но теперь knowledges используются не как абстрактный RAG-модуль, а как явный semantic helper для Analyst и Searcher.

8. CHROMADB И КЭШ ЗНАНИЙ  
ChromaDB в новой версии рассматривается как **локальный rebuildable cache**.

Особенности:

* нет hot reload  
* при битом persisted state кэш может быть восстановлен  
* параллельные debug-запуски против одного `chroma_db/` нежелательны

9. ПОИСК И RETRIEVAL  
9.1. Новый принцип поиска

Searcher не должен "помнить фильмы". Вместо этого система использует:

* text normalization  
* title exact/prefix/token overlap  
* description overlap  
* listed_in / genre route  
* candidate ranking через match features

9.2. Agentic search loop

Searcher может:

1. получить intent  
2. запустить retrieval  
3. оценить candidate pool  
4. попробовать альтернативный route  
5. выбрать 3–5 лучших кандидатов  
6. вернуть SearchResult

10. ЗАЩИТА ОТ ХРУПКОСТИ И ДОЛГИХ ЦИКЛОВ  
10.1. Guardrails

Добавлены runtime guardrails:

* `LLM_TIMEOUT_SECONDS`  
* `ANALYST_MAX_ITER`  
* `SEARCHER_MAX_ITER`  
* `FINALIZER_MAX_ITER`

Это уменьшает риск бесконечного tool loop и слишком долгих ответов.

10.2. Fallback-механизмы

Если агентный этап работает нестабильно:

* Analyst может упасть обратно на deterministic intent из `PreferenceExtractor`  
* Searcher может упасть обратно на deterministic search result через `NetflixSearch`

11. МОНИТОРИНГ И EVALS  
11.1. Логирование

Используется `structlog` для событий вроде:

* `analyst_started`  
* `searcher_started`  
* `finalizer_finished`  
* `request_completed`

11.2. Метрики

Prometheus endpoint остаётся на порту `8001`.

11.3. Evals

Есть локальный `app.evals.run_evals`, который предназначен для ручной проверки качества и latency на наборе запросов.

12. ИТОГОВОЕ СОСТОЯНИЕ ПРОЕКТА  
В этой версии проект больше не является скелетом.

Реализованы:

* contracts  
* local-first runtime  
* search primitives  
* transparent tools  
* universal model routing  
* orchestration layer  
* deterministic fallbacks  
* guardrails against slow loops  
* local eval scaffolding

13. ЗАКЛЮЧЕНИЕ  
Новая версия проекта делает архитектуру честнее и понятнее:

* поиск больше не спрятан в `main.py`  
* Searcher реально использует tools  
* система лучше подходит для бюджетных моделей OpenCode Go  
* локальная разработка и отладка стали проще  
* появились fallback-механизмы и bounded execution

Предыдущий документ можно сохранить как исторический пример исходного проектного замысла, а этот документ считать актуальным описанием второй версии архитектуры.
