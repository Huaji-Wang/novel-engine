"""NarrativeLedger Agent：伏笔(Foreshadow) + 爽点(Payoff) + 毒点(Toxin)。"""

from __future__ import annotations

import json

from backend.llm.client import LLMClient
from backend.prompts import definitions as P

STATUS_LABELS = {"planted": "已埋设", "reinforced": "已强化", "resolved": "已回收"}
INTENSITY_STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}


def format_ledger(items: list[dict], include_resolved: bool = False) -> str:
    lines = []
    for it in items:
        if not include_resolved and it["status"] == "resolved":
            continue
        due = f"，建议第{it['resolve_by_chapter']}章前回收" if it.get("resolve_by_chapter") else ""
        lines.append(
            f"- [{STATUS_LABELS.get(it['status'], it['status'])}] {it['name']}"
            f"（第{it['planted_chapter']}章埋设{due}）：{it['description']}"
        )
    return "\n".join(lines) if lines else "（暂无伏笔记录）"


def format_payoff_ledger(items: list[dict], *, up_to_chapter: int, gap_warn: int = 3) -> str:
    if not items:
        return (
            f"（尚无爽点记录；建议在接下来 {gap_warn} 章内安排至少 1 个打脸/升级/收获类爽点）"
        )
    recent = sorted(items, key=lambda x: x["chapter_no"])
    lines = []
    last_ch = 0
    for it in recent:
        stars = INTENSITY_STARS.get(int(it.get("intensity") or 3), "★★★")
        lines.append(
            f"- 第{it['chapter_no']}章 [{it.get('payoff_type', '')}] "
            f"{it.get('name', '')}{stars}：{it.get('description', '')}"
        )
        last_ch = it["chapter_no"]
    gap = up_to_chapter - last_ch if last_ch else up_to_chapter
    if gap >= gap_warn:
        lines.append(
            f"⚠ 距上次爽点已 {gap} 章（建议每 {gap_warn} 章内至少 1 个爽点）；"
            f"请在下一批细纲中安排打脸/升级/收获等情节。"
        )
    else:
        lines.append(f"（距上次爽点 {gap} 章，节奏正常）")
    return "\n".join(lines)


class NarrativeLedgerAgent:
    def __init__(self):
        self._foreshadow_llm = LLMClient("foreshadow")
        self._payoff_llm = LLMClient("foreshadow")
        self._toxin_llm = LLMClient("critic")

    def analyze_foreshadow(self, *, chapter_no: int, chapter_text: str,
                           ledger: list[dict], num_chapters: int) -> dict:
        slim = [
            {"name": it["name"], "description": it["description"],
             "status": it["status"], "planted_chapter": it["planted_chapter"]}
            for it in ledger if it["status"] != "resolved"
        ]
        result = self._foreshadow_llm.invoke_json(P.FORESHADOW_EXTRACT_PROMPT.format(
            ledger_json=json.dumps(slim, ensure_ascii=False),
            chapter_no=chapter_no,
            chapter_text=chapter_text,
            num_chapters=num_chapters,
        ))
        if not isinstance(result, dict):
            return {"new": [], "reinforced": [], "resolved": []}
        for key in ("new", "reinforced", "resolved"):
            value = result.get(key)
            result[key] = value if isinstance(value, list) else []
        return result

    def extract_payoff(self, *, chapter_text: str, chapter_outline: str = "") -> list[dict]:
        result = self._payoff_llm.invoke_json(P.PAYOFF_EXTRACT_PROMPT.format(
            chapter_text=chapter_text,
            chapter_outline=chapter_outline or "（无）",
        ))
        if not isinstance(result, dict):
            return []
        payoffs = result.get("payoffs")
        if not isinstance(payoffs, list):
            return []
        out = []
        for p in payoffs:
            if not isinstance(p, dict):
                continue
            ptype = str(p.get("type", "")).strip()
            if not ptype:
                continue
            out.append({
                "payoff_type": ptype,
                "name": str(p.get("name", "")).strip() or ptype,
                "description": str(p.get("description", "")).strip(),
                "intensity": max(1, min(5, int(p.get("intensity") or 3))),
            })
        return out

    def scan_toxin(self, *, chapter_text: str, chapter_outline: str = "") -> dict:
        result = self._toxin_llm.invoke_json(P.TOXIN_SCAN_PROMPT.format(
            chapter_text=chapter_text,
            chapter_outline=chapter_outline or "（无）",
        ))
        if not isinstance(result, dict):
            return {"issues": [], "summary": ""}
        issues = result.get("issues")
        result["issues"] = issues if isinstance(issues, list) else []
        return result
