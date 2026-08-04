# novel-engine-next 增强说明

基于 `novel-engine-new`（备份于 `novel-engine-new-backup/`），完整接入三项借鉴优化（非渐进试水，默认 strict）。

## 1. 写法特征池（Style Engine）

| 项 | 说明 |
|----|------|
| 表 | `writing_style_profiles`；`novels.style_profile_id` |
| API | `GET/PATCH /api/novels/{id}/style-profile` |
| 学习 | `POST /api/novels/{id}/style-profile/learn` → JSON features + 绑定 |
| 编译 | `backend/style/compiler.py`：profile + style_guide + writing_style_rules |
| Prompt | `tasks/oneshot/style-learn.md` 输出结构化 JSON |

Writer/Editor 使用 `_compiled_style_for_novel()` 注入，弧末 `style_rules` 优先级最高。

## 2. 质量门（Quality Gate）

| 项 | 说明 |
|----|------|
| 配置 | `config.yaml` → `quality_gate`；`novel.quality_gate` 可覆盖 |
| 写章 | LangGraph：`quality_gate` → `quality_fix`（rewrite / humanize） |
| 工具 | `utils/publish_readiness.py`、`utils/rewrite_decider.py` |
| 定稿 | `health` + `readiness` 任一为 critical 且 `block_finalize=true` → **阻断** |
| 字段 | `chapters.readiness_report`、`chapters.quality_decision` |

默认：

```yaml
quality_gate:
  block_finalize: true
  auto_rewrite_on_critical: true
  auto_humanize_on_fix: true
  max_quality_rewrite_rounds: 1
  strict_publish_audit: true
```

## 3. 上下文优先级 + 待确认提案

| 项 | 说明 |
|----|------|
| 分层 | `context/priority.py`：L0 事实 → L1 规划 → L2 写法 → L3 外部 |
| 检索 | Memory query 含细纲 + 角色名 + compass |
| 表 | `pending_proposals`（character/cast/lore/faction/…） |
| 定稿 | 新角色/配角/设定/阵营 → pending；摘要/状态仍直接更新 |
| API | `GET /pending`、`POST /pending/confirm`、`confirm-all/{chapter}` |
| Lore | `_load_lore` 仅已确认条目 |
| 准入策略 | `pending/policy.py`：正文证据、重要性阈值、正式库/待办去重、每章分类配额 |
| 核心/轻量 | `character` 是核心角色；`cast` 是轻量名册，确认升格为核心角色时移除同名 cast |

Pending 仍严格遵守：**章节定稿成功后才产生候选，人工确认后才进入正式库**。
前端不提供“确认本章全部”，避免确认疲劳导致设定库无脑膨胀；可以逐条查看重要性、
后续复用度、入账理由与正文原句证据。

## 4. 后台任务队列 + 断点恢复（Jobs）

| 项 | 说明 |
|----|------|
| 表 | `jobs`：kind / status / progress / checkpoint / result |
| Worker | 单线程轮询；启动时 `recover_interrupted` 把崩溃遗留的 running 重新排队 |
| 写章 | `POST .../write_job`；节点级 checkpoint（phase + state），失败重试不重跑已完成节点 |
| 定稿 | `POST .../finalize_job`；步骤级 checkpoint（done + pending_items） |
| API | `GET /api/jobs/{id}`、`POST .../cancel`、`POST .../retry`、`GET .../jobs/active` |
| 前端 | 写章/定稿改为入队 + 轮询；刷新页面自动续接；可取消 / 从断点重试 |

同步 SSE 版（`/write`、`/finalize`）仍保留，步骤实现与 job 版复用同一套 service。

## 5. 上下文预算器 + 自适应压缩

| 项 | 说明 |
|----|------|
| 模块 | `context/budget.py`：CJK 感知 token 估算 + 按层级优先裁剪 |
| 策略 | ≤50 章 `full` / 51–150 `sliding` / >150 `layered`（预算与前章节选长度不同） |
| 裁剪次序 | L3 外部参考 → L2 写法 → L1 规划 → L0 事实（摘要/角色状态最后裁，有高地板） |
| 覆盖 | `app.context_budget_tokens`（可选）；写章进度日志会打印裁剪报告 |

## 运行

```bash
cd novel-engine-next
copy config.example.yaml config.yaml   # 或沿用原 config，建议改 database.url
python -m backend.main
```

数据库默认：`./data/novel_engine_next.db`（与备份版分离）。

## 文件地图

```
backend/style/compiler.py
backend/utils/publish_readiness.py
backend/utils/rewrite_decider.py
backend/context/priority.py
backend/pending/service.py
backend/api/style_profiles.py
backend/api/pending_proposals.py
backend/graph/chapter_graph.py   # 扩展质量门节点
```

原版 README 见同目录 `README.md`。
