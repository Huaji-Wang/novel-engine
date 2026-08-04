"""骨架弧策略：仅展开首弧，其余按需 expand。"""

from __future__ import annotations

EXPANDED_STATUSES = frozenset({"expanded", "active", "finished"})


def apply_skeleton_policy(
    volumes: list[dict],
    *,
    expand_volume_no: int | None = None,
) -> list[dict]:
    """分卷后处理：指定卷的第 1 弧分配章范围并 expanded，同卷其余及他卷弧为 skeleton。"""
    if expand_volume_no is None and volumes:
        expand_volume_no = int(volumes[0]["volume_no"])
    for vol in volumes:
        arcs = vol.get("arcs") or []
        if not arcs:
            continue
        cursor = int(vol["start_chapter"])
        vol_end = int(vol["end_chapter"])
        for i, arc in enumerate(arcs):
            est = int(arc.get("estimated_chapters") or 0)
            if not est and arc.get("end_chapter") and arc.get("start_chapter"):
                est = int(arc["end_chapter"]) - int(arc["start_chapter"]) + 1
            if expand_volume_no is not None and vol["volume_no"] == expand_volume_no and i == 0:
                if arc.get("start_chapter") and arc.get("end_chapter"):
                    cursor = int(arc["end_chapter"]) + 1
                else:
                    est = est or max(3, (vol_end - cursor + 1) // max(len(arcs), 1))
                    arc["start_chapter"] = cursor
                    arc["end_chapter"] = min(cursor + est - 1, vol_end)
                    cursor = int(arc["end_chapter"]) + 1
                arc["estimated_chapters"] = (
                    int(arc["end_chapter"]) - int(arc["start_chapter"]) + 1
                )
                arc["status"] = "expanded"
            else:
                remaining = max(0, vol_end - cursor + 1)
                if not est:
                    est = max(3, remaining // max(1, len(arcs) - i))
                arc["start_chapter"] = 0
                arc["end_chapter"] = 0
                arc["estimated_chapters"] = est
                arc["status"] = "skeleton"
    return volumes


def _prev_expanded_end(vol: dict, arc_no: int) -> int:
    end = int(vol["start_chapter"]) - 1
    for arc in sorted(vol.get("arcs") or [], key=lambda a: a["arc_no"]):
        if arc["arc_no"] >= arc_no:
            break
        if arc.get("status") in EXPANDED_STATUSES and arc.get("end_chapter"):
            end = max(end, int(arc["end_chapter"]))
    return end


def allocate_skeleton_arc(vol: dict, arc: dict) -> tuple[int, int]:
    """为 skeleton 弧分配章范围。"""
    start = _prev_expanded_end(vol, int(arc["arc_no"])) + 1
    est = int(arc.get("estimated_chapters") or 5)
    end = min(start + est - 1, int(vol["end_chapter"]))
    arcs = sorted(vol.get("arcs") or [], key=lambda a: a["arc_no"])
    idx = next(i for i, a in enumerate(arcs) if a["arc_no"] == arc["arc_no"])
    for later in arcs[idx + 1:]:
        if later.get("status") in EXPANDED_STATUSES and later.get("start_chapter"):
            end = min(end, int(later["start_chapter"]) - 1)
            break
    if end < start:
        end = start
    return start, end


def find_skeleton_arc(volumes: list[dict], volume_no: int, arc_no: int) -> tuple[dict, dict] | None:
    for vol in volumes:
        if vol["volume_no"] != volume_no:
            continue
        for arc in vol.get("arcs") or []:
            if arc["arc_no"] == arc_no and arc.get("status") == "skeleton":
                return vol, arc
    return None


def next_skeleton_to_expand(volumes: list[dict], next_chapter: int) -> dict | None:
    """若 next_chapter 落在未展开区域，返回应 expand 的 skeleton 弧信息。"""
    for vol in volumes:
        if not (vol["start_chapter"] <= next_chapter <= vol["end_chapter"]):
            continue
        for arc in sorted(vol.get("arcs") or [], key=lambda a: a["arc_no"]):
            if arc.get("status") in EXPANDED_STATUSES:
                if arc.get("start_chapter") and arc["start_chapter"] <= next_chapter <= arc["end_chapter"]:
                    return None
                continue
            if arc.get("status") == "skeleton":
                prev_end = _prev_expanded_end(vol, arc["arc_no"])
                if next_chapter <= prev_end:
                    continue
                return {
                    "volume_no": vol["volume_no"],
                    "volume_title": vol["title"],
                    "arc_no": arc["arc_no"],
                    "arc_id": arc.get("id"),
                    "title": arc["title"],
                    "goal": arc["goal"],
                    "estimated_chapters": arc.get("estimated_chapters"),
                }
    return None
