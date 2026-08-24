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
# 进程内缓存：当前 Agent 所用 Provider 是否接受 chat.completions stream=True
_STREAM_CAP: dict[str, bool] = {}


def _clean(text: str) -> str:
    """去掉模型偶尔包裹的 markdown 代码围栏与首尾空白。"""
    return _CODE_FENCE_RE.sub("", text).strip()


class LLMClient:
    def __init__(self, agent_name: str):
        cfg = agent_llm_config(agent_name)
        if not str(cfg.get("api_key") or "").strip():
            raise RuntimeError(
                "尚未配置 LLM API Key：请编辑项目根目录的 config.yaml，"
                "填入 llm.providers.<default_provider>.api_key（或多 Provider 扁平写法 llm.api_key），"
                "保存后重启 python run.py"
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

    def invoke_stream(self, prompt: str, system: str | None = None):
        """逐块产出 assistant content。不支持流式时由 SDK/Provider 抛错。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        try:
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                piece = getattr(delta, "content", None) if delta is not None else None
                if piece:
                    yield piece
        finally:
            closer = getattr(stream, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass

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


def probe_chat_stream(agent_name: str = "cocreate") -> bool:
    """探测当前 Agent 所用 Provider 是否接受 OpenAI 兼容的 stream=True。结果进程内缓存。"""
    cached = _STREAM_CAP.get(agent_name)
    if cached is not None:
        return cached
    try:
        client = LLMClient(agent_name)
        orig_max = client.max_tokens
        client.max_tokens = 8
        try:
            for _ in client.invoke_stream("hi", system="Reply with one word."):
                break
        finally:
            client.max_tokens = orig_max
        _STREAM_CAP[agent_name] = True
        logger.info("[%s] chat stream 可用", agent_name)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("[%s] chat stream 不可用: %s", agent_name, e)
        _STREAM_CAP[agent_name] = False
        return False
