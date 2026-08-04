"""Pending 提案准入策略：只让有证据、值得成为 canon 的候选进入待确认区。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


VALID_KINDS = {
    "character", "cast", "lore", "faction", "faction_relation",
}

META_KEYS = {
    "importance", "future_relevance", "evidence", "reason",
}

DEFAULT_LIMITS = {
    "character": 1,
    "cast": 2,
    "lore": 2,
    "faction": 1,
    "faction_relation": 1,
}

DEFAULT_MIN_IMPORTANCE = {
    "character": 0.75,
    "cast": 0.60,
    "lore": 0.70,
    "faction": 0.75,
    "faction_relation": 0.75,
}


def proposal_key(kind: str, payload: Mapping[str, Any]) -> str:
    """生成去重键；同名核心角色与配角共享名字，但保留不同层级。"""
    if kind == "faction_relation":
        source = _norm_name(payload.get("source"))
        target = _norm_name(payload.get("target"))
        relation = _norm_name(payload.get("relation_type"))
        return f"{kind}:{source}>{target}:{relation}"
    return f"{kind}:{_norm_name(payload.get('name'))}"


def strip_proposal_meta(payload: Mapping[str, Any]) -> dict[str, Any]:
    """正式入账前移除仅供审批使用的元数据。"""
    return {k: v for k, v in payload.items() if k not in META_KEYS}


def select_proposals(
    items: list[dict],
    *,
    chapter_text: str,
    existing_keys: set[str] | None = None,
    limits: Mapping[str, int] | None = None,
    min_importance: Mapping[str, float] | None = None,
    require_evidence: bool = True,
) -> tuple[list[dict], dict[str, int]]:
    """过滤、去重并按重要性选取每章提案。

    返回 ``(保留项, 统计)``。保留项仍按原提取顺序展示，但配额竞争时高分优先。
    """
    caps = {**DEFAULT_LIMITS, **dict(limits or {})}
    thresholds = {**DEFAULT_MIN_IMPORTANCE, **dict(min_importance or {})}
    known = set(existing_keys or set())
    stats = {
        "input": len(items),
        "added": 0,
        "invalid": 0,
        "duplicate": 0,
        "low_value": 0,
        "over_limit": 0,
    }
    candidates: list[tuple[int, float, str, dict]] = []

    for index, item in enumerate(items):
        kind = str(item.get("kind", "")).strip()
        payload = item.get("payload")
        if kind not in VALID_KINDS or not isinstance(payload, dict):
            stats["invalid"] += 1
            continue

        key = proposal_key(kind, payload)
        if not _key_is_complete(key, kind) or key in known:
            stats["duplicate"] += 1
            continue

        importance = _importance(payload.get("importance"))
        relevance = str(payload.get("future_relevance", "")).strip().lower()
        evidence = str(payload.get("evidence", "")).strip()
        threshold = float(thresholds.get(kind, 0.7))
        if importance < threshold or relevance == "low":
            stats["low_value"] += 1
            continue
        if require_evidence and (
            not evidence or not _evidence_exists(evidence, chapter_text)
        ):
            stats["low_value"] += 1
            continue

        normalized = {
            "kind": kind,
            "payload": {
                **payload,
                "importance": round(importance, 2),
                "future_relevance": relevance or "medium",
                "evidence": evidence[:160],
                "reason": str(payload.get("reason", "")).strip()[:240],
            },
        }
        candidates.append((index, importance, key, normalized))

    # 同一批内重复时保留重要性最高者。
    best_by_key: dict[str, tuple[int, float, str, dict]] = {}
    for candidate in candidates:
        old = best_by_key.get(candidate[2])
        if old is None or candidate[1] > old[1]:
            if old is not None:
                stats["duplicate"] += 1
            best_by_key[candidate[2]] = candidate
        else:
            stats["duplicate"] += 1

    selected: list[tuple[int, float, str, dict]] = []
    counts: dict[str, int] = {}
    for candidate in sorted(
        best_by_key.values(), key=lambda x: (-x[1], x[0]),
    ):
        kind = candidate[3]["kind"]
        cap = max(0, int(caps.get(kind, 0)))
        if counts.get(kind, 0) >= cap:
            stats["over_limit"] += 1
            continue
        counts[kind] = counts.get(kind, 0) + 1
        selected.append(candidate)

    selected.sort(key=lambda x: x[0])
    result = [candidate[3] for candidate in selected]
    stats["added"] = len(result)
    return result, stats


def _norm_name(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).casefold()


def _key_is_complete(key: str, kind: str) -> bool:
    suffix = key.split(":", 1)[-1]
    if kind == "faction_relation":
        source_target = suffix.split(":", 1)[0]
        source, _, target = source_target.partition(">")
        return bool(source and target)
    return bool(suffix)


def _importance(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 5 if score <= 5 else score / 100
    return max(0.0, min(1.0, score))


def _evidence_exists(evidence: str, chapter_text: str) -> bool:
    evidence_norm = re.sub(r"\s+", "", evidence)
    chapter_norm = re.sub(r"\s+", "", chapter_text or "")
    return bool(evidence_norm and evidence_norm in chapter_norm)
