"""配置加载：读取 config.yaml（缺失时从 config.example.yaml 复制）。

同时兼容两种 LLM 配置格式：
1. 扁平格式：llm.api_key / llm.model / llm.base_url
2. 多 Provider 格式：llm.default_provider + llm.providers.<别名>.{type, base_url,
   api_key, default_model, enabled, ...}，按 default_provider（或第一个 enabled）解析
3. Agent 级可设 provider: <别名>，为该 LLM 调用单独指定模型/温度。
   llm.agents 键名与 LLMClient("...") 一致，见 config.example.yaml 与 backend.agents.LLM_AGENT_KEYS。
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
CONFIG_EXAMPLE_FILE = PROJECT_ROOT / "config.example.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists() and CONFIG_EXAMPLE_FILE.exists():
        shutil.copyfile(CONFIG_EXAMPLE_FILE, CONFIG_FILE)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _provider_flat(providers: dict[str, Any], name: str) -> dict[str, Any] | None:
    chosen = providers.get(name)
    if not isinstance(chosen, dict) or not chosen.get("enabled", True):
        return None
    flat = dict(chosen)
    flat.setdefault("model", flat.pop("default_model", ""))
    return flat


def _resolve_provider(llm_raw: dict[str, Any], provider_name: str = "") -> dict[str, Any]:
    """把多 Provider 格式解析为扁平的 {base_url, api_key, model, ...}。"""
    providers: dict[str, dict] = llm_raw.get("providers") or {}
    name = provider_name or llm_raw.get("default_provider", "")
    chosen = _provider_flat(providers, name) if name else None
    if not chosen:
        chosen = next(
            (_provider_flat(providers, k) for k, p in providers.items()
             if isinstance(p, dict) and p.get("enabled", True)),
            None,
        )
    return chosen or {}


def llm_config() -> dict[str, Any]:
    raw = load_config().get("llm", {}) or {}
    if "providers" in raw:
        flat = _resolve_provider(raw)
        flat["agents"] = raw.get("agents") or {}
        return flat
    return raw


def app_config() -> dict[str, Any]:
    cfg = load_config()
    app = dict(cfg.get("app", {}) or {})
    # 兼容顶层 database.url 写法
    db = cfg.get("database", {}) or {}
    if "database_url" not in app and db.get("url"):
        app["database_url"] = db["url"]
    return app


def embedding_config() -> dict[str, Any]:
    """向量检索用的 embedding 配置；api_key 为空表示功能关闭。"""
    return load_config().get("embedding", {}) or {}


DEFAULT_PENDING_POLICY = {
    "require_evidence": True,
    "per_chapter": {
        "character": 1,
        "cast": 2,
        "faction": 1,
        "faction_relation": 1,
        "lore": 2,
    },
    "min_importance": {
        "character": 0.75,
        "cast": 0.60,
        "faction": 0.75,
        "faction_relation": 0.75,
        "lore": 0.70,
    },
}


def pending_policy_config() -> dict[str, Any]:
    """Pending 准入策略；嵌套字典逐层合并，避免局部配置覆盖全部默认值。"""
    raw = load_config().get("pending") or {}
    merged = dict(DEFAULT_PENDING_POLICY)
    merged["per_chapter"] = {
        **DEFAULT_PENDING_POLICY["per_chapter"],
        **dict(raw.get("per_chapter") or {}),
    }
    merged["min_importance"] = {
        **DEFAULT_PENDING_POLICY["min_importance"],
        **dict(raw.get("min_importance") or {}),
    }
    if "require_evidence" in raw:
        merged["require_evidence"] = bool(raw["require_evidence"])
    return merged


# Community / 开源默认 = L2：有检查与 humanize；不阻断定稿、不自动 rewrite。
# 云端 / lab 可在 config.yaml 打开严格门。
DEFAULT_QUALITY_GATE = {
    "block_finalize": False,
    "auto_rewrite_on_critical": False,
    "auto_humanize_on_fix": True,
    "max_quality_rewrite_rounds": 1,
    "strict_publish_audit": True,
    # 仅文档位：提案仍只在「定稿」时产生；确认入账由人工完成，默认不阻断写下一章
    "require_pending_confirm": False,
}


def quality_gate_config(novel_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """全局 quality_gate + 可选书籍级覆盖。"""
    merged = dict(DEFAULT_QUALITY_GATE)
    merged.update(load_config().get("quality_gate") or {})
    if novel_overrides:
        merged.update({k: v for k, v in novel_overrides.items() if v is not None})
    return merged


def agent_llm_config(agent_name: str) -> dict[str, Any]:
    """合并 Provider 默认参数与 Agent 级覆盖（含 provider / model / temperature）。"""
    raw = load_config().get("llm", {}) or {}
    if "providers" in raw:
        overrides = (raw.get("agents") or {}).get(agent_name) or {}
        provider_name = overrides.get("provider") or raw.get("default_provider", "")
        base = _resolve_provider(raw, provider_name)
        agent_overrides = {k: v for k, v in overrides.items() if k != "provider"}
        base.update(agent_overrides)
        return base
    overrides = (raw.get("agents") or {}).get(agent_name) or {}
    base = {k: v for k, v in raw.items() if k != "agents"}
    base.update(overrides)
    return base
