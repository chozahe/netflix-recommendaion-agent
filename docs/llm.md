# LLM — провайдеры, маршрутизация, конфигурация

## Обзор

Проект работает через **OpenCode Go** — единый endpoint, который поддерживает как OpenAI-compatible, так и Anthropic-style API.

**Файлы:** `app/llm/`

---

## Конфигурация моделей

**Файл:** `app/config.py`

Модели настраиваются через `.env`:

```env
ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-pro
FINALIZER_MODEL=openai/deepseek-v4-flash
```

Формат: `provider/model_name`. Префикс провайдера (`openai/`, `anthropic/`, `opencode-go/`) нормализуется.

### Температуры

| Агент | Температура | Зачем |
|---|---|---|
| Analyst | 0.1 | Минимальная креативность, точный анализ |
| Searcher | 0.0 | Детерминированный поиск |
| Finalizer | 0.4 | Больше вариативности в формулировках |

### Таймауты и итерации

| Параметр | По умолчанию | Описание |
|---|---|---|
| `LLM_TIMEOUT_SECONDS` | 45 | Таймаут на вызов LLM |
| `ANALYST_MAX_ITER` | 2 | Максимум итераций Analyst |
| `SEARCHER_MAX_ITER` | 3 | Максимум итераций Searcher |
| `FINALIZER_MAX_ITER` | 2 | Максимум итераций Finalizer |

---

## Маршрутизация провайдеров

**Файл:** `app/llm/providers.py`

### Как определяется бэкенд

```python
ANTHROPIC_STYLE_MODELS = {"minimax-m2.5", "minimax-m2.7"}

def classify_model_backend(model: str) -> str:
    clean = normalize_model_name(model)
    return "anthropic" if clean in ANTHROPIC_STYLE_MODELS else "openai"
```

| Модель | Бэкенд |
|---|---|
| `qwen3.5-plus` | OpenAI-compatible |
| `deepseek-v4-pro` | OpenAI-compatible |
| `deepseek-v4-flash` | OpenAI-compatible |
| `minimax-m2.5` | Anthropic-style |
| `minimax-m2.7` | Anthropic-style |

### OpenAI-compatible

Используется `langchain_openai.ChatOpenAI`:

```python
ChatOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,  # https://opencode.ai/zen/go/v1
    model=model,
    temperature=temperature,
    timeout=settings.llm_timeout_seconds,
)
```

### Anthropic-style

Кастомный адаптер `AnthropicMessagesLLM` (наследует `langchain_core.language_models.llms.LLM`):

```python
class AnthropicMessagesLLM(LLM):
    model: str
    temperature: float

    def _call(self, prompt: str, stop=None, **kwargs) -> str:
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.openai_api_key,
            "anthropic-version": "2023-06-01",
        }
        response = httpx.post(
            "https://opencode.ai/zen/go/v1/messages",
            json=body, headers=headers, timeout=...
        )
        # Парсит response.content[].text
```

Отправляет запросы на `/messages` endpoint вместо `/chat/completions`.

---

## Фабрика LLM

**Файл:** `app/llm/factory.py`

```python
def create_analyst_llm():
    return create_llm(
        model=settings.analyst_model,
        temperature=settings.analyst_temperature
    )

def create_search_llm():
    return create_llm(
        model=settings.search_model,
        temperature=settings.search_temperature
    )

def create_finalizer_llm():
    return create_llm(
        model=settings.finalizer_model,
        temperature=settings.finalizer_temperature
    )
```

Каждый агент получает свой экземпляр LLM с уникальной моделью и температурой.

---

## Рекомендуемые профили

### Baseline (качество)

```env
ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-pro
FINALIZER_MODEL=openai/deepseek-v4-flash
```

### Fast (скорость)

```env
ANALYST_MODEL=openai/qwen3.5-plus
SEARCH_MODEL=openai/deepseek-v4-flash
FINALIZER_MODEL=openai/deepseek-v4-flash
```

---

## Поток вызова LLM

```
build_analyst_agent()
    → create_analyst_llm()
        → create_provider_llm(model="qwen3.5-plus", temperature=0.1)
            → classify_model_backend() → "openai"
            → ChatOpenAI(...)

CrewAI.kickoff()
    → Agent.llm.invoke(prompt)
        → provider._call(prompt)
            → HTTP POST → opencode.ai
            ← JSON response
```
