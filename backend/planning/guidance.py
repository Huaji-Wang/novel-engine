"""全局写作指导三块 + 开放规模（总章数软估计）。"""

from __future__ import annotations

from typing import Any

EMPTY_SLOT = "无（作者跳过或未设置）"
OPEN_CHAPTER_CAP = 10**9


def is_scale_open(num_chapters: int | None) -> bool:
    return int(num_chapters or 0) <= 0


def chapter_cap(num_chapters: int | None) -> int:
    """细纲/规划用硬上限：0=开放，视为极大。"""
    n = int(num_chapters or 0)
    return OPEN_CHAPTER_CAP if n <= 0 else n


def scale_label(num_chapters: int | None) -> str:
    n = int(num_chapters or 0)
    if n <= 0:
        return "未锁定（开放滚动）"
    return f"软估计约{n}章"


def budget_scale(num_chapters: int | None, chapter_no: int = 1) -> int:
    """上下文预算用的体量感：开放时按当前进度推一档，避免永远走 full。"""
    n = int(num_chapters or 0)
    if n > 0:
        return n
    return max(int(chapter_no) + 40, 60)


def slot_text(value: str | None) -> str:
    v = (value or "").strip()
    return v if v else EMPTY_SLOT


def format_guides_block(
    *,
    guide_style: str = "",
    guide_pov: str = "",
    guide_taboos: str = "",
    cocreate_context: str = "",
    chapter_extra: str = "",
) -> str:
    parts = [
        f"【开书共创指令】\n{slot_text(cocreate_context)}",
        f"【全局写作指导·文风语气】\n{slot_text(guide_style)}",
        f"【全局写作指导·视角人称】\n{slot_text(guide_pov)}",
        f"【全局写作指导·禁忌与硬要求】\n{slot_text(guide_taboos)}",
    ]
    extra = (chapter_extra or "").strip()
    if extra:
        parts.append(f"【本章额外要求】\n{extra}")
    return "\n\n".join(parts)


def prompt_guide_fields(
    *,
    guide_style: str = "",
    guide_pov: str = "",
    guide_taboos: str = "",
    cocreate_context: str = "",
    chapter_extra: str = "",
) -> dict[str, str]:
    """供 prompt.format(**prompt_guide_fields(...))。"""
    block = format_guides_block(
        guide_style=guide_style,
        guide_pov=guide_pov,
        guide_taboos=guide_taboos,
        cocreate_context=cocreate_context,
        chapter_extra=chapter_extra,
    )
    return {
        "guide_style": slot_text(guide_style),
        "guide_pov": slot_text(guide_pov),
        "guide_taboos": slot_text(guide_taboos),
        "cocreate_context": slot_text(cocreate_context),
        "chapter_extra": slot_text(chapter_extra) if (chapter_extra or "").strip() else "无",
        "user_guidance": block,  # 兼容尚未改完的模板
    }


def guides_from_novel(novel: dict[str, Any] | Any) -> dict[str, str]:
    """从 novel dict / ORM 取三块指导。"""
    def _get(key: str) -> str:
        if isinstance(novel, dict):
            return str(novel.get(key) or "")
        return str(getattr(novel, key, "") or "")

    return {
        "guide_style": _get("guide_style"),
        "guide_pov": _get("guide_pov"),
        "guide_taboos": _get("guide_taboos"),
    }
