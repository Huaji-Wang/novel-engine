# novel-engine

**Community Edition** — long-form AI novel workbench (self-hosted).  
中文网文向的多智能体写作引擎：蓝图 → 滚动分卷/弧 → 写章 → 定稿记忆。

- **Author:** [Huaji-Wang](https://github.com/Huaji-Wang)  
- **License:** [AGPL-3.0](./LICENSE)  
- **Strategy:** [STRATEGY.md](./STRATEGY.md)  
- **Cloud / Pro:** coming soon — [Waitlist / 云端内测报名](#waitlist)（链接占位，稍后替换）

> Official hosted SaaS (stricter quality gate, advanced context compression, export, quotas) will be separate. This repo is the open funnel.

---

## Features / 功能

| Area | Community |
|------|-----------|
| Blueprint + rolling volumes/arcs | ✅ |
| Chapter write pipeline (retrieve → write → review → quality) | ✅ |
| Jobs + checkpoint resume | ✅ |
| Pending proposals + ledgers | ✅ |
| Shallow context budgeter | ✅ |
| Quality Gate | **L2** (reports + humanize; no finalize block / no auto-rewrite) |
| Advanced ainovel-style compression pipeline | ❌ (Cloud / private lab) |
| Account / billing / export | ❌ Cloud |

---

## Quick start / 快速开始

```bash
cd novel-engine
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml   # 填入 LLM API Key
python run.py
```

Open http://127.0.0.1:8000

**Do not commit `config.yaml`** (gitignored) — it contains secrets.

---

## Write pipeline / 写章流水线

```
retrieve_memory → Writer → Reviewer → [Revision] → QualityGate → [humanize]
```

Details: see comments in `backend/graph/chapter_graph.py`.

Finalize updates summary/state/ledgers and Pending proposals (confirm before canon).

---

## Config notes / 配置

Community defaults (`quality_gate` in `config.example.yaml` / `DEFAULT_QUALITY_GATE`):

- `block_finalize: false`
- `auto_rewrite_on_critical: false`
- `auto_humanize_on_fix: true`

You may tighten locally; Cloud product defaults will be stricter.

---

## Waitlist

云端托管（严格质量门、长篇上下文压缩、导出、配额）内测报名：

**[Waitlist / 云端内测报名](#)** ← replace with Google Form / 腾讯问卷 URL

Signal to build SaaS: ~6 weeks after public launch **or** waitlist ≥ 50 / clear purchase intent.

---

## Privacy / 隐私

Public GitHub identity for this project: **Huaji-Wang**.  
Please prefer the GitHub noreply email for commits if you contribute.

---

## Acknowledgements

Inspired by long-form patterns in ainovel-cli and related open engines; Community ships a simpler budgeter only.
