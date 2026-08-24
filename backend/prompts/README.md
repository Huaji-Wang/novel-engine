# prompts 内容地图

| 目录 | 装什么 | 谁消费 |
|------|--------|--------|
| `tasks/` | 任务 user prompt（从 novel-engine `definitions.py` **原样**迁出） | 各 Agent 的 `method` |
| `prompts/assets/` | anti-ai-tone、default-rules、writer-anti-ai-extra | `anti_ai.py` → Writer/Editor/Reviewer |
| `references/` | 写作知识材料（**追加**在 task 末尾，不改 task 正文）；来源见 `references/README.md` | `context/assembler.py` |
| `references/writing-quality.md` | Writer 写作质量总纲（task 内 `{writing_quality}` + 参考资料包） | `WriterAgent` / `assembler.writer_references` |
| `definitions.py` | 薄加载层，常量名与旧版兼容 | 全项目 |

## 新内容归属

1. 流程必须保证 → LangGraph / Python（`chapter_graph.py`、`chapter_health.py`）
2. 任务怎么说 → `tasks/<role>/*.md`
3. 可机械检查 → `rules` + `chapter_health.py`
4. 写作知识材料 → `references/`（由 assembler 追加，不嵌入 task 文件）

## 提取/更新 task 模板

```bash
python scripts/extract_prompts.py
```

仅在 novel-engine 原版 `definitions.py` 仍含字符串常量时使用；当前仓库以 `tasks/` 为准。
