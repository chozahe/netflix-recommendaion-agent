from __future__ import annotations

from typing import Any

import pandas as pd

from app.search.text import normalize_text, tokenize_query


class CatalogSearchEngine:
    def __init__(self, df: pd.DataFrame):
        self._df = df.copy()
        for column in ["title", "country", "rating", "duration", "listed_in", "description", "cast"]:
            if column not in self._df:
                self._df[column] = ""
            self._df[column] = self._df[column].fillna("")

    def search(self, query: str, mode: str, hard_filters: dict, limit: int = 10) -> list[dict[str, Any]]:
        df = self._apply_hard_filters(self._df.copy(), hard_filters)
        if df.empty:
            return []

        query_normalized = normalize_text(query)
        query_tokens = tokenize_query(query)
        results: list[dict[str, Any]] = []

        for row in df.to_dict(orient="records"):
            candidate = dict(row)
            features = self._score_candidate(candidate, query_normalized, query_tokens, mode)
            score = features.pop("_score", 0.0)
            if score <= 0:
                continue
            candidate["match_features"] = features
            candidate["_score"] = score
            results.append(candidate)

        results.sort(key=lambda item: item["_score"], reverse=True)
        for item in results:
            item.pop("_score", None)
        return results[: min(limit, 20)]

    def _apply_hard_filters(self, df: pd.DataFrame, hard_filters: dict) -> pd.DataFrame:
        content_type = hard_filters.get("content_type")
        if content_type in {"Movie", "TV Show"}:
            df = df[df["type"] == content_type]

        year_from = hard_filters.get("year_from")
        year_to = hard_filters.get("year_to")
        if year_from is not None:
            df = df[df["release_year"] >= year_from]
        if year_to is not None:
            df = df[df["release_year"] <= year_to]

        country = hard_filters.get("country")
        if country:
            df = df[df["country"].str.contains(country, case=False, na=False)]

        rating = hard_filters.get("rating")
        if rating:
            df = df[df["rating"] == rating]

        genre = hard_filters.get("genre")
        if genre:
            df = df[df["listed_in"].str.contains(genre, case=False, na=False)]

        return df

    def _score_candidate(self, candidate: dict[str, Any], query_normalized: str, query_tokens: list[str], mode: str) -> dict[str, Any]:
        title_normalized = normalize_text(str(candidate.get("title", "")))
        description_normalized = normalize_text(str(candidate.get("description", "")))
        listed_in_normalized = normalize_text(str(candidate.get("listed_in", "")))
        cast_normalized = normalize_text(str(candidate.get("cast", "")))

        title_tokens = set(tokenize_query(title_normalized))
        description_tokens = set(tokenize_query(description_normalized))
        listed_in_tokens = set(tokenize_query(listed_in_normalized))
        cast_tokens = set(tokenize_query(cast_normalized))
        query_set = set(query_tokens)

        title_exact = query_normalized == title_normalized and bool(query_normalized)
        title_prefix = bool(query_normalized) and title_normalized.startswith(query_normalized)
        title_overlap = len(query_set & title_tokens)
        description_overlap = len(query_set & description_tokens)
        listed_in_overlap = len(query_set & listed_in_tokens)
        cast_overlap = len(query_set & cast_tokens)

        score = 0.0
        if mode == "title":
            score = (100.0 if title_exact else 0.0) + (25.0 if title_prefix else 0.0) + (10.0 * title_overlap)
        elif mode == "description":
            score = float(description_overlap * 10)
        elif mode == "listed_in":
            score = float(listed_in_overlap * 10)
        elif mode == "cast":
            score = float(cast_overlap * 10)
        else:  # hybrid
            score = (
                (100.0 if title_exact else 0.0)
                + (20.0 if title_prefix else 0.0)
                + (8.0 * title_overlap)
                + (10.0 * description_overlap)
                + (6.0 * listed_in_overlap)
                + (4.0 * cast_overlap)
            )

        return {
            "title_exact": title_exact,
            "title_prefix": title_prefix,
            "title_overlap": title_overlap,
            "description_overlap": description_overlap,
            "listed_in_overlap": listed_in_overlap,
            "cast_overlap": cast_overlap,
            "mode": mode,
            "_score": score,
        }
