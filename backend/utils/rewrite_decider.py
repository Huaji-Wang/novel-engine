"""综合 health + publish_readiness，决定整章重写 / humanize / 通过。"""

from __future__ import annotations

from enum import Enum
from typing import Any


class QualityDecision(str, Enum):
    REWRITE = "rewrite"
    HUMANIZE = "humanize"
    PASS = "pass"
    WARNING = "warning"


def decide_quality_action(
    *,
    health: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    h_status = health.get("status", "ok")
    r_status = readiness.get("status", "ok")
    h_metrics = health.get("metrics") or {}
    r_metrics = readiness.get("metrics") or {}

    quote_pairs = int(h_metrics.get("chinese_quotes") or h_metrics.get("quote_pairs") or 0)
    template_count = int(h_metrics.get("template_words_total") or 0)
    critical_count = len(health.get("critical") or [])
    scene_count = int(r_metrics.get("scene_count") or 0)

    if scene_count > 2:
        return _result(QualityDecision.REWRITE, f"场景过多: {scene_count} 场 > 2")

    if r_status == "critical":
        structural = 0
        if r_metrics.get("bookkeeping", 0) >= 6:
            structural += 1
        if r_metrics.get("summary", 0) >= 5:
            structural += 1
        if r_metrics.get("telling", 0) >= 5:
            structural += 1
        if structural >= 2 or readiness.get("blockers"):
            return _result(
                QualityDecision.REWRITE,
                f"发布结构阻断（账本{r_metrics.get('bookkeeping')}/"
                f"总结{r_metrics.get('summary')}/讲述{r_metrics.get('telling')}）",
            )

    if h_status == "critical":
        if quote_pairs < 6 and critical_count >= 2:
            return _result(
                QualityDecision.REWRITE,
                f"引号仅 {quote_pairs} 对且 CRITICAL ≥ {critical_count}",
            )
        return _result(
            QualityDecision.HUMANIZE,
            f"健康检查 CRITICAL（引号{quote_pairs}/模板词{template_count}）",
        )

    if template_count > 8 or quote_pairs < 6 or critical_count > 0:
        return _result(
            QualityDecision.HUMANIZE,
            f"模板词 {template_count} 或引号 {quote_pairs} 对不足",
        )

    if h_status == "warning" or r_status == "warning":
        return _result(QualityDecision.WARNING, "存在 WARNING，可交付但建议润色")

    return _result(QualityDecision.PASS, "质量检查通过")


def _result(decision: QualityDecision, reason: str) -> dict[str, Any]:
    return {
        "decision": decision.value,
        "reason": reason,
        "rewrite": decision == QualityDecision.REWRITE,
        "humanize": decision == QualityDecision.HUMANIZE,
    }


def quality_issues_for_revision(
    health: dict[str, Any], readiness: dict[str, Any], decision: dict[str, Any],
) -> list[dict]:
    issues: list[dict] = []
    for item in health.get("critical") or []:
        issues.append({
            "severity": "high",
            "category": "health",
            "message": str(item) if isinstance(item, str) else item.get("message", str(item)),
        })
    for blocker in readiness.get("blockers") or []:
        issues.append({"severity": "high", "category": "publish", "message": blocker})
    if not issues and decision.get("humanize"):
        issues.append({
            "severity": "medium",
            "category": "style",
            "message": decision.get("reason", "去 AI 味与人味润色"),
        })
    return issues
