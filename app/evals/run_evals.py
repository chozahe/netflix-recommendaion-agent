from __future__ import annotations

import time

from app.orchestration import run_pipeline

EVAL_QUERIES = [
    "что-нибудь мрачное про космос",
    "хочу что-нибудь мрачное",
    "interstellar",
    "легкий сериал на вечер",
    "посоветуй сериал с вайбом 80-х и Вайноной Райдер",
]


def run_evals() -> list[dict]:
    results: list[dict] = []
    for query in EVAL_QUERIES:
        started = time.perf_counter()
        try:
            output = run_pipeline(query)
            status = "ok"
        except Exception as exc:  # pragma: no cover - runtime path
            output = str(exc)
            status = "error"
        results.append(
            {
                "query": query,
                "status": status,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "output_preview": output[:300],
            }
        )
    return results


if __name__ == "__main__":
    for item in run_evals():
        print(f"[{item['status']}] {item['query']} ({item['latency_seconds']}s)")
        print(item["output_preview"])
        print("-" * 60)
