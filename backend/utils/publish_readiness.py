"""发布结构审稿（零 LLM）：场景数、裸对话、账本句、总结句、讲述句。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

SCENE_MARKERS_RE = re.compile(
    r"^[一二三四五六七八九十]+、\s*\S*|^#{1,3}\s+(?!第\d+章)[^\n]+", re.MULTILINE)

SUMMARY_MARKERS = [
    "这意味着", "这不只是", "说到底", "不过他知道", "他现在不着急",
    "接下来要", "以后是不是", "到时候", "算了一笔账", "盘算着接下来的计划",
    "脑子里盘算着",
]

BOOKKEEPING_MARKERS = [
    "平均", "一共", "加起来", "每个", "一斤", "半斤", "一两",
    "块钱", "毛钱", "目标", "计划", "品相", "品质", "价格", "供货",
    "规模做大", "扩大规模", "稳定供货",
]

GENERIC_REACTION_MARKERS = [
    "心里头一", "心里一", "嘴角动了动", "深吸了口气", "摸了摸鼻子",
    "没说话", "整个人僵住了", "眼睛刷的一下就亮了",
]

TELLING_PATTERNS = [
    "他心里头", "他心里", "她心里", "他知道", "她知道",
    "他明白", "她明白", "这意味着", "说明", "证明", "意味着",
]


@dataclass
class LineHit:
    line_no: int
    text: str


def _clean_text(raw: str) -> str:
    text = re.sub(r"^【第\d+章[^】]*】\n", "", raw)
    return re.sub(r"（本章完）\s*$", "", text).strip()


def _collect_naked_dialogue(lines: list[str]) -> list[LineHit]:
    hits: list[LineHit] = []
    narration_verbs = "走看站坐想转回头抬头低头伸手拿放蹲挠扶推"
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or "“" in stripped or '"' in stripped:
            continue
        if len(stripped) > 30 or not re.search(r"[？?！!]$", stripped):
            continue
        if re.search(rf"(他|她).{{0,6}}[{narration_verbs}]", stripped):
            continue
        hits.append(LineHit(idx, stripped))
    return hits


def _collect_marker_hits(lines: list[str], markers: list[str]) -> list[LineHit]:
    hits: list[LineHit] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(m in stripped for m in markers):
            hits.append(LineHit(idx, stripped))
    return hits


def _collect_bookkeeping_hits(lines: list[str]) -> list[LineHit]:
    hits: list[LineHit] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or len(stripped) < 28:
            continue
        marker_count = sum(1 for m in BOOKKEEPING_MARKERS if m in stripped)
        digit_count = len(re.findall(r"\d+", stripped))
        if marker_count >= 2 or (marker_count >= 1 and digit_count >= 2):
            hits.append(LineHit(idx, stripped))
    return hits


def _collect_telling_hits(lines: list[str]) -> list[LineHit]:
    hits: list[LineHit] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or "“" in stripped or '"' in stripped:
            continue
        if sum(1 for p in TELLING_PATTERNS if p in stripped) >= 2:
            hits.append(LineHit(idx, stripped))
    return hits


def _score_blockers(
    scene_count: int, naked: int, bookkeeping: int, summary: int, telling: int,
) -> list[str]:
    blockers: list[str] = []
    if scene_count > 2:
        blockers.append(f"场景过多: {scene_count} 场戏挤在一章")
    if naked >= 3:
        blockers.append(f"裸对话过多: {naked} 行")
    if bookkeeping >= 6:
        blockers.append(f"账本式说明过多: {bookkeeping} 行")
    if summary >= 5:
        blockers.append(f"总结/计划句过多: {summary} 行")
    if telling >= 5:
        blockers.append(f"讲述句过多: {telling} 行")
    return blockers


def check_publish_readiness(
    chapter_text: str, *, strict: bool = True,
) -> dict[str, Any]:
    text = _clean_text(chapter_text)
    lines = text.splitlines()
    scenes = SCENE_MARKERS_RE.findall(text)
    naked_hits = _collect_naked_dialogue(lines)
    bookkeeping_hits = _collect_bookkeeping_hits(lines)
    summary_hits = _collect_marker_hits(lines, SUMMARY_MARKERS)
    telling_hits = _collect_telling_hits(lines)
    reaction_hits = _collect_marker_hits(lines, GENERIC_REACTION_MARKERS)

    metrics = {
        "scene_count": len(scenes),
        "naked_dialogue": len(naked_hits),
        "bookkeeping": len(bookkeeping_hits),
        "summary": len(summary_hits),
        "telling": len(telling_hits),
        "generic_reaction": len(reaction_hits),
    }
    blockers = _score_blockers(
        metrics["scene_count"], metrics["naked_dialogue"],
        metrics["bookkeeping"], metrics["summary"], metrics["telling"],
    )
    status = "critical" if blockers else "ok"
    if not strict and blockers and metrics["scene_count"] <= 2:
        status = "warning"

    def _sample(hits: list[LineHit], n: int = 3) -> list[dict]:
        return [asdict(h) for h in hits[:n]]

    summary_text = "；".join(blockers) if blockers else "发布结构检查通过"
    return {
        "status": status,
        "summary": summary_text,
        "metrics": metrics,
        "blockers": blockers,
        "samples": {
            "naked_dialogue": _sample(naked_hits),
            "bookkeeping": _sample(bookkeeping_hits),
            "summary": _sample(summary_hits),
            "telling": _sample(telling_hits),
        },
    }
