"""卷 / 弧结构辅助：上下文格式化与边界检测。"""

from __future__ import annotations


def format_arc_context(
    volumes: list[dict],
    start_no: int,
    end_no: int,
) -> str:
    """格式化与本批细纲相关的弧上下文。"""
    if not volumes:
        return ""
    lines: list[str] = []
    for vol in volumes:
        for arc in vol.get("arcs") or []:
            overlaps = (
                arc.get("status") in ("expanded", "active", "finished")
                and arc.get("start_chapter")
                and arc["start_chapter"] <= end_no
                and arc["end_chapter"] >= start_no
            )
            if overlaps:
                status_note = ""
                if arc.get("status") == "finished" and arc.get("summary"):
                    status_note = f"\n  弧摘要：{arc['summary']}"
                lines.append(
                    f"第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》"
                    f"（第{arc['start_chapter']}-{arc['end_chapter']}章）\n"
                    f"  弧目标：{arc['goal']}{status_note}"
                )
            elif (
                arc.get("status") == "skeleton"
                and arc.get("start_chapter") == 0
                and end_no >= vol["start_chapter"]
            ):
                lines.append(
                    f"（待展开骨架弧）第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》"
                    f" 预估{arc.get('estimated_chapters', '?')}章 — {arc.get('goal', '')}"
                )
            elif arc.get("start_chapter") == end_no + 1:
                lines.append(
                    f"（下一弧预告）第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》：{arc['goal']}"
                )
    if not lines and volumes:
        lines.append("（当前章号暂无已展开弧上下文；请先展开弧或追加新卷）")
    return "\n".join(lines)


def format_prev_arcs_context(
    volumes: list[dict],
    *,
    volume_no: int,
    before_arc_no: int,
) -> str:
    """已完成弧摘要，供 expand_arc 衔接前一弧节奏与伏笔。"""
    lines: list[str] = []
    for vol in sorted(volumes, key=lambda v: v["volume_no"]):
        for arc in vol.get("arcs") or []:
            if vol["volume_no"] > volume_no:
                break
            if vol["volume_no"] == volume_no and arc["arc_no"] >= before_arc_no:
                continue
            if arc.get("status") not in ("finished", "expanded", "active"):
                continue
            if arc.get("summary"):
                lines.append(
                    f"第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》：{arc['summary']}"
                )
            elif arc.get("goal"):
                lines.append(
                    f"第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》目标：{arc['goal']}"
                )
    return "\n".join(lines) if lines else "（无已完成弧摘要，为首弧或前序弧尚未沉淀摘要）"


def find_arc_for_chapter(volumes: list[dict], chapter_no: int) -> dict | None:
    for vol in volumes:
        for arc in vol.get("arcs") or []:
            if arc.get("status") not in ("expanded", "active", "finished"):
                continue
            if not arc.get("start_chapter"):
                continue
            if arc["start_chapter"] <= chapter_no <= arc["end_chapter"]:
                return {
                    **arc,
                    "volume_no": vol["volume_no"],
                    "volume_title": vol["title"],
                }
    return None


def is_volume_end(volumes: list[dict], chapter_no: int) -> bool:
    return any(vol["end_chapter"] == chapter_no for vol in volumes)
