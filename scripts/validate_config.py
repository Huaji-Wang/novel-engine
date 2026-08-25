"""Validate llm.agents keys cover all LLMClient(...) usages.

Run from the repository root: python -m scripts.validate_config
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.agents import LLM_AGENT_KEYS
from backend.config import load_config

ROOT = Path(__file__).resolve().parents[1] / "backend" / "agents"
PATTERN = re.compile(r'LLMClient\("([^"]+)"\)')


def main() -> None:
    used: set[str] = set()
    for path in ROOT.rglob("*.py"):
        used.update(PATTERN.findall(path.read_text(encoding="utf-8")))
    configured = set((load_config().get("llm", {}).get("agents") or {}).keys())
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    import yaml

    ex_agents = set((yaml.safe_load(example.read_text(encoding="utf-8")).get("llm", {}).get("agents") or {}).keys())
    missing_cfg = used - configured
    missing_ex = used - ex_agents
    extra_keys = set(LLM_AGENT_KEYS) - used
    print("LLMClient keys in code:", sorted(used))
    print("config.yaml agents:", sorted(configured))
    print("config.example agents:", sorted(ex_agents))
    if missing_ex:
        raise SystemExit(f"config.example.yaml missing: {sorted(missing_ex)}")
    if extra_keys:
        print("note: LLM_AGENT_KEYS unused in code:", sorted(extra_keys))
    if missing_cfg:
        print("warn: config.yaml missing (will use provider default):", sorted(missing_cfg))
    print("ok")


if __name__ == "__main__":
    main()
