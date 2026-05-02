from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

ANALYST_PROMPT = (_PROMPTS_DIR / "analyst.md").read_text(encoding="utf-8")
SEARCHER_PROMPT = (_PROMPTS_DIR / "searcher.md").read_text(encoding="utf-8")
FINALIZER_PROMPT = (_PROMPTS_DIR / "finalizer.md").read_text(encoding="utf-8")

__all__ = ["ANALYST_PROMPT", "SEARCHER_PROMPT", "FINALIZER_PROMPT"]
