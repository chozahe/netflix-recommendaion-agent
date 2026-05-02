import json as json_module
import re
from pathlib import Path
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings

_MOOD_FIELDS = ["mood", "moods", "mood_genre_weights"]
_CONTEXT_FIELDS = [
    "content_type",
    "genre",
    "genres",
    "year_from",
    "year_to",
    "country",
    "country_aliases_matched",
    "rating_filter",
    "reasoning",
]


class PreferenceExtractorInput(BaseModel):
    query: str = Field(
        ...,
        description="The user's natural language query in Russian or English.",
    )


class PreferenceExtractorTool(BaseTool):
    name: str = "PreferenceExtractor"
    description: str = (
        "Extract content preferences (type, genre, mood, year, country, rating) "
        "from a user's natural language query. Uses keyword matching against "
        "the knowledge base (kb/*.md files). Returns structured JSON for the "
        "Searcher agent to use."
    )
    args_schema: Type[BaseModel] = PreferenceExtractorInput

    _mood_keywords: dict[str, str]
    _mood_genre_weights: dict[str, dict[str, float]]
    _theme_to_genre: dict[str, str]
    _country_alias_to_name: dict[str, str]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        kb = Path(settings.kb_path)
        self._mood_keywords, self._mood_genre_weights = self._parse_mood_keywords(
            kb / "mood_keywords.md"
        )
        self._theme_to_genre = self._parse_genre_mapping(kb / "genre_mapping.md")
        self._country_alias_to_name = self._parse_country_codes(
            kb / "country_codes.md"
        )

    # ------------------------------------------------------------------
    # Mood keywords parser
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_mood_keywords(filepath: Path) -> tuple[dict[str, str], dict[str, dict[str, float]]]:
        mood_map: dict[str, str] = {}
        weight_map: dict[str, dict[str, float]] = {}

        if not filepath.exists():
            return mood_map, weight_map

        text = filepath.read_text(encoding="utf-8")
        # Split into sections by ### headers
        sections = re.split(r"\n###\s+", text)
        current_mood: Optional[str] = None

        for section in sections:
            lines = section.strip().split("\n")
            if not lines:
                continue

            header = lines[0].strip()
            # Skip pre-section material (no ### prefix for first chunk)
            if not any(line.startswith("###") for line in text.split("\n")):
                if "Mood" in header or "mood" in header.lower():
                    continue

            for line in lines[1:]:
                line = line.strip()
                if line.startswith("### "):
                    current_mood = line[4:].strip()
                    continue

                # Detect mood name from header
                header_mood = header.split("/")[0].strip().lower()

                if line.startswith("**Keywords EN**:"):
                    kw_en = line.split(":", 1)[1].strip()
                    for kw in kw_en.split(","):
                        kw = kw.strip().lower()
                        if kw:
                            mood_map[kw] = header_mood
                elif line.startswith("**Keywords RU**:"):
                    kw_ru = line.split(":", 1)[1].strip()
                    for kw in kw_ru.split(","):
                        kw = kw.strip().lower()
                        if kw:
                            mood_map[kw] = header_mood
                elif line.startswith("**Genre weight**:"):
                    weights_raw = line.split(":", 1)[1].strip()
                    weights: dict[str, float] = {}
                    for part in weights_raw.split(","):
                        part = part.strip()
                        match = re.match(r"(.+?)\s+([+-]?[\d.]+)", part)
                        if match:
                            genre_name = match.group(1).strip()
                            score = float(match.group(2))
                            weights[genre_name] = score
                    if weights:
                        weight_map[header_mood] = weights

        return mood_map, weight_map

    # ------------------------------------------------------------------
    # Genre mapping parser (Markdown table)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_genre_mapping(filepath: Path) -> dict[str, str]:
        mapping: dict[str, str] = {}
        if not filepath.exists():
            return mapping

        rows = _parse_markdown_table(filepath)
        for row in rows:
            if len(row) < 2:
                continue
            themes_raw = row[0].strip()
            genre_raw = row[1].strip()
            if not themes_raw or not genre_raw:
                continue
            for theme in themes_raw.split(","):
                theme = theme.strip().lower()
                if theme:
                    mapping[theme] = genre_raw
        return mapping

    # ------------------------------------------------------------------
    # Country codes parser (Markdown table)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_country_codes(filepath: Path) -> dict[str, str]:
        mapping: dict[str, str] = {}
        if not filepath.exists():
            return mapping

        rows = _parse_markdown_table(filepath)
        for row in rows:
            if len(row) < 3:
                continue
            country = row[0].strip()
            aliases_raw = row[2].strip()
            if not country or not aliases_raw:
                continue
            # Add the canonical name itself
            mapping[country.lower()] = country
            for alias in aliases_raw.split(","):
                alias = alias.strip().lower()
                if alias:
                    mapping[alias] = country
        return mapping

    # ------------------------------------------------------------------
    # Main extraction logic
    # ------------------------------------------------------------------
    def _run(self, query: str) -> str:
        query_lower = query.lower()
        query_words = query_lower.split()
        reasons: list[str] = []

        # --- Mood detection ---
        moods: dict[str, float] = {}
        for keyword, mood_name in self._mood_keywords.items():
            for word in query_words:
                if keyword in word:
                    moods[mood_name] = moods.get(mood_name, 0.0) + 1.0
                    break

        total = sum(moods.values())
        if total > 0:
            moods = {k: round(v / total, 2) for k, v in moods.items()}
            reasons.append(f"mood keywords matched: {list(moods.keys())}")

        # --- Content type detection ---
        content_type: Optional[str] = None
        movie_kw = {"фильм", "movie", "film", "кино", "полнометраж", "полнометражный"}
        tv_kw = {"сериал", "show", "series", "сезон", "эпизод"}

        for kw in movie_kw:
            if any(kw in w for w in query_words):
                content_type = "Movie"
                reasons.append(f"content_type=Movie (keyword: '{kw}')")
                break
        if content_type is None:
            for kw in tv_kw:
                if any(kw in w for w in query_words):
                    content_type = "TV Show"
                    reasons.append(f"content_type=TV Show (keyword: '{kw}')")
                    break

        # --- Year detection ---
        year_from: Optional[int] = None
        year_to: Optional[int] = None

        # Decades: "90-е", "90s", "80s"
        decade_match = re.search(r"\b(\d{2})\s*[-–]\s*[еe]\b", query_lower)
        if decade_match:
            decade = int(decade_match.group(1))
            year_from = 1900 + decade
            year_to = year_from + 9
            reasons.append(f"year range={year_from}-{year_to} (decade '{decade_match.group(0)}')")

        # "после YYYY", "after YYYY"
        after_match = re.search(r"(?:после|after|с)\s+(\d{4})", query_lower)
        if after_match:
            year_from = int(after_match.group(1))
            year_to = 2021
            reasons.append(f"year from={year_from} (keyword 'after/после')")

        # "до YYYY", "before YYYY"
        before_match = re.search(r"(?:до|before)\s+(\d{4})", query_lower)
        if before_match:
            year_to = int(before_match.group(1))
            if year_from is None:
                year_from = 1925
            reasons.append(f"year to={year_to} (keyword 'before/до')")

        # Single year: "2020", "год 2019"
        if year_from is None and year_to is None:
            year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", query)
            if year_match:
                year_from = year_to = int(year_match.group(1))
                reasons.append(f"year={year_from} (exact year match)")

        # --- Country detection ---
        country: Optional[str] = None
        aliases_matched: list[str] = []
        # Match longer aliases first to avoid partial matches
        sorted_aliases = sorted(
            self._country_alias_to_name.items(),
            key=lambda x: -len(x[0]),
        )
        for alias, canonical in sorted_aliases:
            if len(alias) <= 2:
                # Short codes (US, UK, IN etc.) — must match a whole word
                if any(alias == w for w in query_words):
                    country = canonical
                    aliases_matched.append(alias)
                    break
            elif any(alias in w for w in query_words):
                country = canonical
                aliases_matched.append(alias)
                break
        if country:
            reasons.append(f"country={country} (alias matched: '{aliases_matched[0]}')")

        # --- Genre/Themes detection ---
        genres: list[str] = []
        sorted_themes = sorted(
            self._theme_to_genre.items(),
            key=lambda x: -len(x[0]),
        )
        for theme, netflix_genre in sorted_themes:
            if any(theme in w for w in query_words) or theme in query_lower:
                # netflix_genre may contain multiple genres like "Comedies, TV Comedies"
                for g in netflix_genre.split(","):
                    g = g.strip()
                    if g and g not in genres:
                        genres.append(g)
                reasons.append(f"theme '{theme}' → genre '{netflix_genre}'")

        primary_genre = genres[0] if genres else None

        # --- Rating filter (inferred from age context) ---
        rating_filter: Optional[list[str]] = None
        child_kw = {
            "дети", "ребён", "ребен", "ребёно", "child", "kids", "kid",
            "семья", "семей", "family", "малыш", "toddler", "дошколь",
        }
        teen_kw = {"подрост", "teen", "тинейдж", "школь", "school"}
        adult_kw = {"взросл", "adult", "жёстк", "жестк", "mature", "18+"}

        if any(any(kw in w for w in query_words) for kw in child_kw):
            rating_filter = [
                "G", "TV-Y", "TV-Y7", "TV-Y7-FV",
                "TV-G", "PG", "TV-PG",
            ]
            reasons.append("rating filter: family/kids safe ratings")
        elif any(any(kw in w for w in query_words) for kw in teen_kw):
            rating_filter = [
                "G", "TV-Y", "TV-Y7", "TV-Y7-FV",
                "TV-G", "PG", "TV-PG", "PG-13", "TV-14",
            ]
            reasons.append("rating filter: teen-safe ratings")
        elif any(any(kw in w for w in query_words) for kw in adult_kw):
            rating_filter = ["R", "TV-MA", "NC-17"]
            reasons.append("rating filter: adult-only ratings")

        # Build output
        output = {
            "content_type": content_type,
            "genre": primary_genre,
            "genres": genres,
            "mood": max(moods, key=moods.get) if moods else None,
            "moods": moods,
            "mood_genre_weights": (
                self._mood_genre_weights.get(max(moods, key=moods.get), {})
                if moods
                else {}
            ),
            "year_from": year_from,
            "year_to": year_to,
            "country": country,
            "country_aliases_matched": aliases_matched,
            "rating_filter": rating_filter,
            "reasoning": "; ".join(reasons) if reasons else "No preferences detected",
        }

        return json_module.dumps(output, ensure_ascii=False)


# ------------------------------------------------------------------
# Generic Markdown table parser
# ------------------------------------------------------------------
def _parse_markdown_table(filepath: Path) -> list[list[str]]:
    """Parse a simple Markdown table, returning rows of cell values."""
    rows: list[list[str]] = []
    if not filepath.exists():
        return rows

    lines = filepath.read_text(encoding="utf-8").split("\n")
    in_table = False
    header_sep_seen = False

    for line in lines:
        stripped = line.strip()
        # Detect table row: starts and ends with |
        if stripped.startswith("|") and stripped.endswith("|"):
            # Skip separator lines like | :---- | :---- |
            if re.match(r"^\|[\s\-:]+\|", stripped):
                header_sep_seen = True
                continue
            if not header_sep_seen:
                # This is the header row — skip it
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if any(cells):
                rows.append(cells)

    return rows
