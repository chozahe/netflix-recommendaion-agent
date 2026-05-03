import json as json_module
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class InspectCandidateInput(BaseModel):
    candidate: dict[str, Any] = Field(..., description="Single candidate row to inspect.")


class InspectCandidateTool(BaseTool):
    name: str = "InspectCandidate"
    description: str = "Return a compact explanation for why a candidate matched."
    args_schema: Type[BaseModel] = InspectCandidateInput

    def _run(self, candidate: dict[str, Any]) -> str:
        features = candidate.get("match_features", {})
        explanation = {
            "title": candidate.get("title", ""),
            "type": candidate.get("type", ""),
            "release_year": candidate.get("release_year"),
            "match_features": features,
            "summary": self._build_summary(candidate, features),
        }
        return json_module.dumps(explanation, ensure_ascii=False)

    @staticmethod
    def _build_summary(candidate: dict[str, Any], features: dict[str, Any]) -> str:
        parts: list[str] = []
        if features.get("title_exact"):
            parts.append("exact title match")
        if features.get("description_overlap"):
            parts.append(f"description overlap={features['description_overlap']}")
        if features.get("listed_in_overlap"):
            parts.append(f"genre overlap={features['listed_in_overlap']}")
        if not parts:
            parts.append("matched by search route")
        return f"{candidate.get('title', 'Candidate')} — " + ", ".join(parts)
