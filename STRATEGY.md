# 产品策略共识（Grill 锁定）

> 最后确认：2026-08-04。开源改造 / SaaS / lab 优化以本文为准。

## 关系

- **GitHub = 漏斗**；**只有 SaaS 收钱**
- 开源宜厚；云端卖：托管省心、**严格 Quality Gate**、**ainovel 级上下文压缩**、导出、配额

## 开源（仓名 `novel-engine`，账号 [Huaji-Wang](https://github.com/Huaji-Wang)）

| 项 | 决定 |
|----|------|
| 许可证 | **AGPL-3.0** |
| 版权 | `Copyright 2026 Huaji-Wang`（唯一版权人；自用可跑 SaaS；慎收无 CLA 的外人 PR） |
| 含 | 写章、分卷弧、Pending/台账、Jobs 断点、**浅层 context budgeter** |
| Quality Gate | **L2 默认**：检查 + 可 humanize；`block_finalize=false`；`auto_rewrite_on_critical=false` |
| 不含（产品叙事） | 导出/批量、账号/支付；**不含 ainovel 级压缩管线** |
| Harness 三 Pack | 暂不进开源主叙事；在 harness/lab 验证 |
| 品牌 | 技术名 `novel-engine`；商业名 90 天内再定 |
| 文档 | 中英；Waitlist **先占位**后补问卷链接 |
| 发布 | 先 **Private** 短验收 → 再 Public |

## SaaS（后做）

| 项 | 决定 |
|----|------|
| 客群 | 个人作者（团队以后） |
| 定价 | 月费含额度 + 超出可加点 |
| 免费云 | 无永久免费档；仅试用 |
| 模型 | 平台统一提供 + 严配额 |
| 独有 | 完整严格 QG、**ainovel-cli 风格自适应压缩管线**、导出、账号/配额 |

## 节奏

1. 完成本地开源可发版 → Private 验收 → Public  
2. **满 6 周或 waitlist≥50 / 付费意向** → SaaS MVP  
3. **开源发布之后**：在 `novel-engine-lab` 内化 ainovel-cli 压缩能力（见下）

## 代码仓

| 仓 | 用途 |
|----|------|
| `novel-engine` | 开源发布线（从 next 复制改造；若仍存在 `novel-engine-next` 为锁文件残留，可稍后手动删除） |
| `novel-engine-legacy` | 更旧的历史目录（原 `novel-engine`） |
| `novel-engine-lab` | 私有优化 + 未来 SaaS；**压缩管线在此做** |
| `novel-engine-harness` | 定稿 Pack 实验 |

## lab backlog：上下文压缩（开源发完再做）

参考本地 `_ref_ainovel_cli` / [voocel/ainovel-cli](https://github.com/voocel/ainovel-cli)：

- 自适应 `full / sliding / layered`
- 管线：`ToolResultMicrocompact → LightTrim → StoreSummaryCompact → FullSummary`
- **StoreSummaryCompact**：用已有章/弧/卷摘要与角色快照替换原文（零 LLM）
- 压缩后 **恢复包**、上下文健康度、CJK token 估算校准

现有 `backend/context/budget.py` 仅为浅层优先级截断，可保留在开源；**深度管线只合入 lab/SaaS**。

## 明确不做（当前）

- 把 ainovel 级压缩管线放进开源主仓
- 云端永久免费厚额度
- 冷启动就上多团队工作台
