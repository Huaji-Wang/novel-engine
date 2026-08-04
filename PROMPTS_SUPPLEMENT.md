# 提示词补充说明（ainovel-cli → novel-engine-new）

## 原则

- **原有 task 模板**（`backend/prompts/tasks/**`）正文与 novel-engine 一致，未改字。
- **补充内容**来自 `_ref_ainovel_cli/assets/references/`，通过 `backend/context/assembler.py` 在调用 LLM **前追加**到 prompt 末尾，不写入 task 文件。

## 已引入的 reference 文件

| 文件 | 来源 | 注入给谁 | 原因 |
|------|------|----------|------|
| `character-building.md` | ainovel-cli | Planner（expand/plot 等） | 原 novel-engine 无独立角色构建参考，规划阶段易缺方法论文本 |
| `character-template.md` | ainovel-cli | Planner | 大纲/角色卡结构模板，与蓝图流水线对齐 |
| `outline-template.md` | ainovel-cli | Planner | 长篇大纲格式参考 |
| `longform-planning.md` | ainovel-cli | Planner | 滚动规划、卷弧等长篇方法论 |
| `hook-techniques.md` | ainovel-cli | Writer（按章裁剪） | 章节钩子写法，Writer task 未单独展开 |
| `chapter-guide.md` | ainovel-cli | Writer（前 3 章） | 开篇章节写作指南，避免首章信息过载 |
| `dialogue-writing.md` | ainovel-cli | Writer（前 3 章） | 对话潜台词与区分度 |
| `consistency.md` | ainovel-cli | Reviewer | 一致性审校量表，补强 Consistency 任务 |
| `quality-checklist.md` | ainovel-cli | Reviewer | 质量评审维度，补强 Critic 任务 |

## 未引入（及原因）

| ainovel-cli 文件 | 原因 |
|------------------|------|
| `anti-ai-tone.md` | novel-engine 已有 `prompts/assets/anti-ai-tone.md`，并在 task 内通过 `{anti_ai_tone}` 注入 |
| `default-rules.md` / rules | 已有 `default-rules.md` + `chapter_health.py` 机械检查 |
| `styles/*.md` | novel-engine 用 Meta 的 `writing_style` 字段 + `style_guide`，暂不重复 |
| `references/genres/*` | 需与 `genre` 配置联动，留待后续按题材接线 |
| coordinator/architect/writer/editor **prompts** | 架构不同（LangGraph vs Coordinator），不直接照搬 system prompt |

## 注入方式

```python
from backend.context.assembler import append_reference_block, writer_references

prompt = append_reference_block(task_template.format(...), writer_references(chapter_no=n))
```

追加块标题：`【补充参考资料（ainovel-cli 引入，供对照，勿逐字复述）】`

## Agent 合并（代码层，与 prompt 无关）

| 新类 | 合并自 |
|------|--------|
| `PlannerAgent` | Planner + Meta + VolumePlanner |
| `ReviewerAgent` | Consistency + Critic |
| `WorldKeeperAgent` | Faction + LoreKeeper |
| `NarrativeLedgerAgent` | Foreshadow + Payoff + Toxin |
| `MemoryService` | MemoryAgent（非 LLM，改名） |

保留独立：`ChapterPlannerAgent`、`CharacterAgent`、`WriterAgent`、`EditorAgent`、`RevisionAgent`、`ImpactAgent`、`StyleLearnerAgent`。

LLM 配置仍使用原 `config.yaml` 中的 agent 名（如 `meta`、`faction`），合并类内按 method 选用对应 client。
