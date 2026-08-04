"""Load task prompts from tasks/**/*.md (verbatim from original definitions.py)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=128)
def load_task(relative_path: str) -> str:
    """Load a task template by path relative to backend/prompts/, e.g. planner/expand-story."""
    path = _PROMPTS_ROOT / "tasks" / relative_path
    if not path.suffix:
        path = path.with_suffix(".md")
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=64)
def load_reference(name: str) -> str:
    """Load optional reference material from references/."""
    path = _PROMPTS_ROOT / "references" / name
    if not path.suffix:
        path = path.with_suffix(".md")
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=32)
def load_system(role: str) -> str:
    """Load role system prompt from prompts/<role>.md if present."""
    path = _PROMPTS_ROOT / "prompts" / f"{role}.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def format_reference_pack(refs: dict[str, str]) -> str:
    if not refs:
        return "（无额外参考资料）"
    parts: list[str] = []
    for key, text in refs.items():
        if text.strip():
            parts.append(f"### {key}\n{text.strip()}")
    return "\n\n".join(parts) if parts else "（无额外参考资料）"
