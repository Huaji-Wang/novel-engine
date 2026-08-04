"""滚动分卷：首卷 / append / 边界检测。"""

from __future__ import annotations

from backend.planning.skeleton import EXPANDED_STATUSES, apply_skeleton_policy


def last_volume(volumes: list[dict]) -> dict | None:
    if not volumes:
        return None
    return max(volumes, key=lambda v: v["volume_no"])


def is_book_complete(compass: dict | None) -> bool:
    return bool((compass or {}).get("book_complete"))


def chapter_beyond_planned(volumes: list[dict], chapter_no: int) -> dict | None:
    """若 chapter_no 超出已 append 的最后一卷，返回拦截信息。"""
    last = last_volume(volumes)
    if not last:
        return {"code": "no_volumes", "message": "请先生成首卷规划"}
    if chapter_no > int(last["end_chapter"]):
        return {
            "code": "need_append_volume",
            "message": (
                f"第{chapter_no}章超出当前规划（最后一卷到第{last['end_chapter']}章）。"
                f"请卷末选定下一卷方向并「追加卷」，或标记全书完结。"
            ),
            "last_volume_no": last["volume_no"],
        }
    return None


def volume_at_chapter(volumes: list[dict], chapter_no: int) -> dict | None:
    for v in volumes:
        if v["start_chapter"] <= chapter_no <= v["end_chapter"]:
            return v
    return None


def is_last_chapter_of_volume(volumes: list[dict], chapter_no: int) -> bool:
    last = last_volume(volumes)
    return bool(last and last["end_chapter"] == chapter_no)


def has_next_volume(volumes: list[dict], volume_no: int) -> bool:
    return any(v["volume_no"] > volume_no for v in volumes)


def format_arc_summaries_for_propose(volumes: list[dict]) -> str:
    lines: list[str] = []
    for vol in volumes:
        for arc in vol.get("arcs") or []:
            if arc.get("summary"):
                lines.append(
                    f"第{vol['volume_no']}卷·第{arc['arc_no']}弧《{arc['title']}》：{arc['summary']}"
                )
    return "\n".join(lines) if lines else "（尚无弧摘要）"


def format_volume_summaries(volumes: list[dict]) -> str:
    lines: list[str] = []
    for v in volumes:
        lines.append(
            f"第{v['volume_no']}卷《{v['title']}》（{v['start_chapter']}-{v['end_chapter']}）"
            f" 主题：{v.get('theme', '')}；{v.get('summary', '')}"
        )
    return "\n".join(lines) if lines else "（尚无分卷）"


def normalize_volume_dict(raw: dict, *, volume_no: int, start_chapter: int, end_chapter: int) -> dict:
    arcs_raw = raw.get("arcs") or []
    arcs = []
    for j, a in enumerate(arcs_raw, start=1):
        if not isinstance(a, dict):
            continue
        arcs.append({
            "arc_no": int(a.get("arc_no") or j),
            "title": str(a.get("title", "")),
            "goal": str(a.get("goal", "")),
            "start_chapter": int(a.get("start_chapter") or 0),
            "end_chapter": int(a.get("end_chapter") or 0),
            "estimated_chapters": int(
                a.get("estimated_chapters")
                or max(0, int(a.get("end_chapter") or 0) - int(a.get("start_chapter") or 0) + 1)
                or 5
            ),
        })
    return {
        "volume_no": volume_no,
        "title": str(raw.get("title", "")),
        "start_chapter": start_chapter,
        "end_chapter": end_chapter,
        "theme": str(raw.get("theme", "")),
        "summary": str(raw.get("summary", "")),
        "arcs": arcs,
    }


def prepare_volume_for_persist(vol: dict, *, expand_volume_no: int) -> dict:
    """对单卷应用 skeleton 策略（指定卷的首弧 expanded）。"""
    processed = apply_skeleton_policy([vol], expand_volume_no=expand_volume_no)
    return processed[0]


def option_to_volume_dict(
    option: dict,
    *,
    volume_no: int,
    start_chapter: int,
) -> dict:
    est = int(option.get("estimated_chapters") or 15)
    end_chapter = start_chapter + max(est, 3) - 1
    arcs = []
    for j, a in enumerate(option.get("arcs") or [], start=1):
        if not isinstance(a, dict):
            continue
        arcs.append({
            "arc_no": j,
            "title": str(a.get("title", f"第{j}弧")),
            "goal": str(a.get("goal", "")),
            "start_chapter": 0,
            "end_chapter": 0,
            "estimated_chapters": int(a.get("estimated_chapters") or 5),
        })
    if not arcs:
        arcs = [{
            "arc_no": 1,
            "title": "开篇弧",
            "goal": str(option.get("theme", "")),
            "start_chapter": 0,
            "end_chapter": 0,
            "estimated_chapters": min(8, est),
        }]
    return normalize_volume_dict(
        {
            "title": option.get("title", ""),
            "theme": option.get("theme", ""),
            "summary": option.get("summary", ""),
            "arcs": arcs,
        },
        volume_no=volume_no,
        start_chapter=start_chapter,
        end_chapter=end_chapter,
    )


def locked_arcs_text(vol: dict) -> str:
    lines: list[str] = []
    for arc in vol.get("arcs") or []:
        if arc.get("status") in EXPANDED_STATUSES | {"finished"}:
            lines.append(
                f"第{arc['arc_no']}弧《{arc['title']}》"
                f"（{arc.get('start_chapter')}-{arc.get('end_chapter')}）"
                f" status={arc.get('status')} — {arc.get('goal', '')}"
            )
    return "\n".join(lines) if lines else "（无）"


def skeleton_arcs_text(vol: dict) -> str:
    lines: list[str] = []
    for arc in vol.get("arcs") or []:
        if arc.get("status") == "skeleton":
            lines.append(
                f"第{arc['arc_no']}弧《{arc['title']}》"
                f" 预估{arc.get('estimated_chapters')}章 — {arc.get('goal', '')}"
            )
    return "\n".join(lines) if lines else "（无 skeleton 弧）"

