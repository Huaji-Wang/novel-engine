"""MemoryService：章节向量化入库与相关旧情节检索（非 LLM Agent）。"""

from __future__ import annotations

import logging

import numpy as np
from openai import OpenAI

from backend.config import embedding_config
from backend.db.models import MemoryChunk
from backend.db.session import db_session

logger = logging.getLogger(__name__)


def _split_chunks(text: str, chunk_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 > chunk_chars and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
        while len(current) > chunk_chars * 2:
            chunks.append(current[:chunk_chars])
            current = current[chunk_chars:]
    if current:
        chunks.append(current)
    return chunks


class MemoryService:
    def __init__(self):
        cfg = embedding_config()
        self.enabled = bool(cfg.get("api_key"))
        self.model = cfg.get("model", "text-embedding-3-small")
        self.retrieval_k = int(cfg.get("retrieval_k", 4))
        self.chunk_chars = int(cfg.get("chunk_chars", 600))
        self._client = (
            OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url") or None)
            if self.enabled else None
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def index_chapter(self, novel_id: int, chapter_no: int, text: str) -> int:
        if not self.enabled:
            return -1
        chunks = _split_chunks(text, self.chunk_chars)
        if not chunks:
            return 0
        embeddings = self._embed(chunks)
        with db_session() as session:
            session.query(MemoryChunk).filter_by(
                novel_id=novel_id, chapter_no=chapter_no).delete()
            for seq, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                session.add(MemoryChunk(
                    novel_id=novel_id, chapter_no=chapter_no,
                    seq=seq, text=chunk, embedding=emb,
                ))
        return len(chunks)

    def retrieve(self, novel_id: int, query: str,
                 exclude_chapters: set[int] | None = None) -> list[dict]:
        if not self.enabled or not query.strip():
            return []
        with db_session() as session:
            rows = session.query(MemoryChunk).filter_by(novel_id=novel_id).all()
            candidates = [
                {"chapter_no": r.chapter_no, "text": r.text, "embedding": r.embedding}
                for r in rows
                if not (exclude_chapters and r.chapter_no in exclude_chapters)
            ]
        if not candidates:
            return []
        try:
            query_vec = np.array(self._embed([query[:4000]])[0])
        except Exception as e:  # noqa: BLE001
            logger.warning("记忆检索 embedding 失败，跳过: %s", e)
            return []
        matrix = np.array([c["embedding"] for c in candidates])
        scores = matrix @ query_vec / (
            np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec) + 1e-9)
        top = np.argsort(scores)[::-1][: self.retrieval_k]
        return [
            {"chapter_no": candidates[i]["chapter_no"],
             "text": candidates[i]["text"], "score": float(scores[i])}
            for i in top
        ]


def format_retrieved(snippets: list[dict]) -> str:
    if not snippets:
        return "（无）"
    return "\n\n".join(
        f"（出自第{s['chapter_no']}章）{s['text']}" for s in snippets)


# 兼容旧名
MemoryAgent = MemoryService
