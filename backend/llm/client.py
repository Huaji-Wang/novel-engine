"""OpenAI 兼容 LLM 客户端封装：按 Agent 取配置、带重试与输出清洗。"""

from __future__ import annotations

import json
import logging
import re
import time

from openai import OpenAI

from backend.config import agent_llm_config

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```[\w-]*\s*\n|\n```\s*$", re.MULTILINE)


def _clean(text: str) -> str:
    """去掉模型偶尔包裹的 markdown 代码围栏与首尾空白。"""
    return _CODE_FENCE_RE.sub("", text).strip()


class LLMClient:
    def __init__(self, agent_name: str):
        cfg = agent_llm_config(agent_name)
        if not cfg.get("api_key"):
            raise RuntimeError(
                "尚未配置 LLM API Key：请编辑项目根目录的 config.yaml，填入 llm.api_key"
            )
        self.agent_name = agent_name
        self.model = cfg.get("model", "deepseek-chat")
        self.temperature = float(cfg.get("temperature", 0.7))
        self.max_tokens = int(cfg.get("max_tokens", 8192))
        self.max_retries = int(cfg.get("max_retries", 2))
        extra_headers = cfg.get("extra_headers") or None
        self._client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url") or None,
            timeout=float(cfg.get("timeout_seconds", 300)),
            default_headers=extra_headers if isinstance(extra_headers, dict) else None,
        )

    def invoke(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                text = _clean(resp.choices[0].message.content or "")
                if text:
                    return text
                last_err = RuntimeError("模型返回了空内容")
            except Exception as e:  # noqa: BLE001 - 重试所有调用错误
                last_err = e
                logger.warning("[%s] LLM 调用失败(第%d次): %s", self.agent_name, attempt + 1, e)
            time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"LLM 调用失败（Agent: {self.agent_name}）: {last_err}")

    def invoke_json(self, prompt: str, system: str | None = None) -> dict | list:
        """要求模型输出 JSON 并解析；解析失败时尝试提取最外层 JSON 块。"""
        text = self.invoke(prompt, system=system)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise RuntimeError(f"模型未返回合法 JSON（Agent: {self.agent_name}）：{text[:200]}")
