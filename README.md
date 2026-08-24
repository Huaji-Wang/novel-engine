# novel-engine

**[中文说明](./README.zh-CN.md)**

Self-hosted software for writing a **long novel with an AI**, without handing the whole book to a single “generate everything” button.

You talk through what you want, the app only **locks the first stretch of plot**, then you write **one chapter at a time**. You can always edit, reject, or regenerate. It is aimed at serial / web-novel pacing (hooks, arcs, not forgetting old setup).

- **Author:** [Huaji-Wang](https://github.com/Huaji-Wang)
- **License:** [AGPL-3.0](./LICENSE)
- **Hosted cloud:** later — [Waitlist](#waitlist)

---

## What this is (and is not)

**Is:** a local website (open it in the browser after `python run.py`). Left side = your books. Main area = tabs for this book. Right side = progress while the model is working.

**Is not:** a cloud account, an ebook exporter, or a tool that must know the ending and total chapter count on day one.

---

## First time: from empty page to chapter 1

Do this after [Quick start](#quick-start). Budget: one sitting, several model calls (blueprint is the slowest).

1. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Click **＋ 新建** (New).
2. Enter a **title** and a **premise** (the idea of the story). Per-chapter word count is optional. If this is fanfiction of an existing work, tick **同人模式** (fanfic mode). Click **创建** (Create).
3. You land on tab **① 蓝图** (Blueprint). You do **not** need a finished novel plan yet. In **开书共创** (opening co-create), type what you care about and click **发送** (Send). Chat as many turns as you want. The right-hand **创作指令草稿** (instruction draft) is the running spec—the model is supposed to obey this later.
4. When the draft looks right, click **确认共创** (Confirm co-create). Then click **🚀 生成蓝图** (Generate blueprint). Wait until the progress panel finishes. This fills seed, cast dynamics, world, **only the first arc**, a loose compass, and the **first few chapter outlines**.
5. Open tab **③ 细纲** (Outlines). Skim chapter 1. Edit or **AI 修订** if needed.
6. Open tab **④ 章节** (Chapters). On chapter 1 click **✍ 生成正文** (Generate prose). Optional extra instruction in the popup. Wait for the job.
7. Read the draft. Use **润色** / **去AI味** / select a span and rewrite, or **AI 修订**. When you accept it as canon, click **定稿** (Finalize). That updates summaries and ledgers for later chapters.

You can skip co-create and hit **生成蓝图** immediately; quality is usually worse because the model has only your one-line premise.

---

## Words on the screen

| You see | What it means |
|---------|----------------|
| **① 蓝图** | Planning tab: co-create, writing guides, first-arc plan, compass. Not the chapter text. |
| **开书共创** | Chat that turns your idea into a markdown **instruction draft**. Confirm it before blueprint if you used it. |
| **本轮思考** | Optional folded notes (understood / gaps / next question). Appears only if your LLM API **streams**. Not a hidden inner monologue fed back into the next turn. |
| **全局写作指导** | Three boxes: voice, POV, taboos. Each can be empty (“skipped”). Edit anytime; later chapters follow the new text. Does not by itself rebuild the whole blueprint. |
| **规模 / 类型** | Genre label; **软估计总章数** (soft chapter estimate). `0` = unlimited / unknown. Does not stop you writing past that number the way a hard “20 chapters” contract would. |
| **核心种子 / 世界观 / 第1弧架构** | Short planning docs. Arc 1 = the **near** plot, not the whole trilogy. |
| **故事倾向摘要 / 终局指南针** | A **weak compass**: likely ending *direction*, open threads, scale *feel*. Not a locked last chapter. You may change it. |
| **③ 细纲** | Per-chapter beat sheet the writer model should follow. Often includes short **必做 / 禁做** (must / must not). Fanfic mode asks for stricter must-nots. |
| **④ 章节** | The actual prose. **定稿** means “this chapter is official for memory/ledgers,” not “publish to the web.” |
| **⑥ 全局状态** | Running summary, character state table, **待确认** (pending) cards. New characters/lore from a chapter wait here until you **确认** or **拒绝**. |
| **Jobs / 断点** | Long tasks run in the background. If the process dies, you can retry from the last finished step. |

---

## After chapter 1

- **➕ 生成后续章节细纲** when you need the next outline window.
- Write, revise, finalize in order; skipping finalize makes later chapters forget what just happened.
- When the planned volume/arc runs out, use volume tools (append volume / next-arc direction)—the app will refuse to plan a chapter past the current volume until you extend the plan or mark the book complete.
- **重新生成蓝图** wipes planning (and related cards/outlines). Use it only if you meant to start the plan over.

---

## Also included

Fanfic field locks after you confirm co-create; setting bible (tab ⑤); foreshadowing / payoff ledgers; polish and health-check on a chapter; a **lenient** quality report (Community will not block finalize or auto-rewrite the whole chapter).

**Not in this repository** (possible later hosted product): login, billing, epub/batch export, heavy long-session compression.

---

## Quick start

```bash
cd novel-engine
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # Windows: copy config.example.yaml config.yaml
```

Edit `config.yaml`: set `llm.providers.<name>.api_key` (OpenAI-compatible) and `enabled: true` for that provider. Save, then:

```bash
python run.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

**Do not commit `config.yaml`.** It is gitignored and contains secrets.

Streaming “this turn’s thinking” in co-create is on only if that API really supports `stream=True`; otherwise you get a normal full reply and no thinking panel.

---

## Quality gate (Community)

Defaults are loose so you can keep serializing:

- `block_finalize: false`
- `auto_rewrite_on_critical: false`
- `auto_humanize_on_fix: true`

You may tighten these locally. A hosted cloud build is expected to be stricter.

---

## Waitlist

Hosted cloud (stricter quality, long-form context tools, export, quotas):

**[Waitlist / 云端内测报名](#)** ← replace with your form URL when you have one.

---

## Contributing

Issues and discussion are welcome. **Forks are welcome**—run it, change it, publish derivatives under AGPL-3.0.

Please **open an issue before a pull request** so we can agree on scope. Unsolicited PRs may remain unmerged.

---

## Acknowledgements

Rolling-arc long-form tools in the community (including ainovel-cli-style structures) informed this workbench. The open edition only includes a **shallow** context budgeter.
