FROM python:3.11-slim

WORKDIR /app

RUN useradd -m appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model so first container run is instant
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

RUN mkdir -p logs chroma_db data kb \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "app.main"]
