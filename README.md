# novel-engine

**[中文说明](./README.zh-CN.md)**

**A local-first multi-agent writing engine for long-form fiction.**

`novel-engine` is an open-source, locally runnable writing system designed for **long-form novels, serialized fiction, and web novels**.

It does not try to generate an entire book with a single prompt.

Instead, it uses a **multi-stage, multi-agent workflow** to turn an initial idea into a living story structure, then develops that structure **one arc, one outline, and one chapter at a time**.

You remain the author and the final decision-maker.
The AI handles planning, drafting, revision, continuity, and state tracking.

> **Plan locally. Write incrementally. Keep the story under your control.**

- **Author:** [Huaji-Wang](https://github.com/Huaji-Wang)
- **License:** [AGPL-3.0](./LICENSE)
- **Cloud version:** Planned

> **Before you clone:** the web interface and the built-in prompts are currently
> **Chinese only**, and the engine is tuned for writing Chinese prose. An English
> interface and English prompt set are on the roadmap, but they do not exist yet.

---

## Why novel-engine?

Long-form fiction is not simply a matter of asking an LLM to "write a novel."

A model can produce a convincing paragraph. It is much harder to make it:

- remember what happened 50 chapters ago;
- maintain consistent character states;
- preserve world-building rules;
- manage long-running story arcs;
- maintain pacing across chapters;
- plant and resolve foreshadowing;
- adapt when the author changes an earlier decision;
- avoid turning the entire novel into a single, rigid outline.

`novel-engine` treats long-form generation as a **continuous planning and state-management problem**, rather than a single generation task.

The system therefore separates the writing process into multiple stages:

```text
Idea
  │
  ▼
Co-Creation
  │
  ▼
Story Blueprint
  │
  ├── Core Seed
  ├── Characters
  ├── World
  ├── Arc Structure
  └── Long-term Direction
  │
  ▼
Chapter Outline
  │
  ▼
Chapter Draft
  │
  ├── Revision
  ├── Polishing
  └── AI-assisted Rewriting
  │
  ▼
Author Approval
  │
  ▼
Story State Update
  │
  ├── Summary
  ├── Character State
  ├── World State
  ├── Foreshadowing
  └── Continuity Records
  │
  ▼
Next Chapter
```

The important part is the loop:

**write → revise → approve → update state → continue**

The story is not treated as a static prompt.

---

## Core Philosophy

### 1. Don't generate the whole novel at once

A long novel is inherently uncertain.

Instead of forcing the model to determine the entire plot before writing chapter one, `novel-engine` uses **progressive planning**.

The system plans what is needed now, while keeping a softer direction for what comes later.

For example:

```text
Whole Novel
    │
    └── Long-term direction
            │
            └── Current Arc
                    │
                    ├── Chapter 1
                    ├── Chapter 2
                    ├── Chapter 3
                    └── ...
```

The current arc receives detailed planning.

The rest of the novel remains intentionally flexible.

This makes it possible to change direction without immediately invalidating the entire story.

---

### 2. The author stays in the loop

`novel-engine` is not intended to replace the author.

You can intervene at almost every important stage:

- change the initial concept;
- discuss the story with the AI before planning;
- edit the blueprint;
- modify chapter outlines;
- provide additional chapter instructions;
- rewrite selected passages;
- revise generated chapters;
- approve or reject newly discovered characters and settings;
- change global writing instructions;
- regenerate planning when you intentionally want to restart.

AI generates suggestions and drafts.

**The author decides what becomes canon.**

---

### 3. Memory is a structured state, not just a giant context window

Long-form fiction quickly exceeds what is practical to keep inside a single conversation.

Instead of continuously stuffing the entire manuscript into every prompt, `novel-engine` maintains structured story state.

Examples include:

- chapter summaries;
- character states;
- world-building information;
- unresolved elements;
- foreshadowing;
- story progression;
- confirmed and unconfirmed entities.

This allows later chapters to retrieve **the information they actually need**, rather than blindly replaying the entire history of the novel.

---

## Multi-Agent Workflow

The system is built around the idea that different parts of long-form writing should be handled by different specialized roles.

Rather than asking one agent to simultaneously act as:

> novelist + planner + editor + continuity checker + memory manager

the workflow separates these responsibilities into different stages and agents.

A typical generation cycle looks like:

```text
                  ┌─────────────────┐
                  │   Author Idea   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Co-Creation    │
                  │     Agent       │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Blueprint /     │
                  │ Planning Agents │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Outline Agent   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Writing Agent   │
                  └────────┬────────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
          ┌──────────────┐   ┌──────────────┐
          │ Revision /   │   │ Continuity / │
          │ Polish Agent │   │ Quality Check│
          └──────┬───────┘   └──────┬───────┘
                 │                  │
                 └────────┬─────────┘
                          ▼
                 ┌─────────────────┐
                 │  Author Review  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Story State     │
                 │ Update          │
                 └────────┬────────┘
                          │
                          └──────► Next Chapter
```

The exact agent composition may evolve as the project develops.

The important principle is **specialization and controlled information flow**, rather than simply adding more agents.

---

## From Idea to Chapter One

After starting the local application, create a new book and provide:

- title;
- story concept;
- optional genre/type information;
- optional fan-fiction mode.

You can then enter the **Co-Creation** stage.

### Co-Creation

Instead of immediately turning a one-line idea into a complete outline, you can discuss the premise with the AI.

The conversation is gradually converted into a structured **Creative Instruction Draft**.

This document becomes the foundation for later planning.

You can iterate on it as many times as necessary before confirming it.

---

### Blueprint

Once the creative direction is confirmed, the system generates a blueprint containing information such as:

- core story seed;
- characters and relationships;
- world-building;
- current arc structure;
- long-term story direction;
- initial chapter outlines.

The key distinction is that the system does **not** attempt to completely lock down the entire novel.

The first arc receives relatively detailed planning.

The eventual ending is treated as a **soft compass**, not a contract.

---

### Chapter Outline

Each chapter receives a more detailed outline describing the intended narrative beats.

The author can:

- edit the outline manually;
- ask the AI to revise it;
- regenerate it when necessary.

The outline is the bridge between high-level planning and actual prose generation.

---

### Chapter Generation

Once the outline is ready, the writing agent generates the chapter.

You can provide additional instructions for that particular chapter, while global writing instructions can be maintained separately.

Generated chapters can then be:

- revised;
- polished;
- "de-AI-ified";
- partially rewritten;
- reviewed for quality and consistency.

Nothing becomes part of the official story state until the author **finalizes** the chapter.

---

## Finalization & Story State

Finalization is an important concept in `novel-engine`.

A generated chapter is not automatically treated as canon.

When you approve a chapter, the system updates the persistent story state.

For example:

```text
Chapter 12
    │
    ▼
Author Approval
    │
    ├── Chapter Summary
    ├── Character Changes
    ├── New Characters
    ├── World Changes
    ├── Foreshadowing
    └── Other Story State
            │
            ▼
       Global Memory
            │
            ▼
       Chapter 13
```

This creates a clear boundary between:

**what the AI suggested**

and

**what actually happened in the novel.**

New characters or settings discovered during writing can also remain in a **pending** state until the author confirms them.

---

## Long-form Continuity

Long-form fiction inevitably accumulates information.

`novel-engine` therefore maintains several forms of structured state, including:

### Character State

Tracks information that can change during the story, rather than treating a character card as a permanently static description.

### World State

Stores important world-building information that later chapters may need to respect.

### Foreshadowing

Tracks unresolved narrative elements so that they are less likely to disappear after dozens of chapters.

### Chapter Summaries

Provides compact representations of previous chapters instead of repeatedly injecting the complete manuscript into every generation request.

### Pending State

New entities and facts can be marked as **pending** until the author confirms whether they should become part of the canonical story.

---

## Designed for Serialized Fiction

`novel-engine` is particularly interested in the workflow of **serialized / web fiction**.

That means the system explicitly considers:

- chapter-level pacing;
- chapter-end hooks;
- story arcs;
- progression;
- long-term foreshadowing;
- recurring characters;
- continuity;
- incremental planning.

A chapter should not only answer:

> "What happens next?"

It should also consider:

> "Why should the reader continue to the next chapter?"

---

## Fan Fiction Mode

`novel-engine` also supports a dedicated **fan-fiction mode**.

After co-creation is confirmed, relevant fields can be locked more strictly so that generated content is less likely to casually violate established source-material constraints.

The goal is not to perfectly reproduce the original author's writing style.

Instead, the focus is on maintaining:

- character identity;
- established relationships;
- world rules;
- canon constraints;
- user-defined restrictions.

---

## What It Is — and Isn't

### It is

- A **local-first** long-form fiction writing environment.
- A **multi-agent** writing workflow.
- A structured planning and generation system.
- A tool for human-AI co-creation.
- Designed around incremental chapter generation.
- Designed with story-state and continuity management in mind.
- Suitable for experimentation with different LLM providers.

### It isn't

- A one-click "generate an entire novel" button.
- A cloud-only SaaS.
- A system that requires the entire ending to be decided before chapter one.
- A replacement for the author.
- A guarantee of publishable-quality prose.
- A magical solution to long-context problems.

---

## Interface

The application runs locally and is accessed through your browser.

The main workflow is organized around the following stages:

| Stage | Purpose |
| ----- | ------- |
| **① Blueprint**（蓝图） | Co-creation, writing instructions, story seed, current arc and long-term direction |
| **② Characters**（角色） | Character cards, relationships and per-character voice rules |
| **③ Outline**（细纲） | Detailed chapter planning |
| **④ Chapters**（章节） | Actual manuscript generation and revision |
| **⑤ Knowledge Base**（设定库） | Structured story/world information |
| **⑥ Global State**（全局状态） | Summaries, character states and pending information |
| **Jobs** | Background generation tasks and resumable workflows |

Tab labels are shown here with the Chinese text you will actually see in the
application.

The interface deliberately separates **planning** from **writing**.

---

## Background Jobs & Resume

Long-form generation can take a significant amount of time.

Generation tasks therefore run as background jobs rather than blocking the entire application.

If a process fails or the application is restarted, completed steps can be reused rather than regenerating everything from scratch.

This is especially important when using paid or rate-limited LLM APIs.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Huaji-Wang/novel-engine.git
cd novel-engine
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the configuration file

Linux / macOS:

```bash
cp config.example.yaml config.yaml
```

Windows:

```powershell
copy config.example.yaml config.yaml
```

Edit `config.yaml` and configure an **OpenAI-compatible LLM provider**:

```yaml
llm:
  providers:
    your_provider:
      api_key: "YOUR_API_KEY"
      enabled: true
```

Use the provider configuration supported by your installation.

### 5. Start the application

```bash
python run.py
```

Then open:

**http://127.0.0.1:8000**

> **Never commit `config.yaml`.**
> It may contain your API credentials and is already included in `.gitignore`.

---

## Recommended Workflow

For a new novel, the recommended workflow is:

```text
Create Book
    ↓
Co-Creation
    ↓
Confirm Creative Instructions
    ↓
Generate Blueprint
    ↓
Review / Edit Blueprint
    ↓
Generate Chapter Outline
    ↓
Review / Revise Outline
    ↓
Generate Chapter
    ↓
Revise / Polish
    ↓
Author Approval
    ↓
Update Story State
    ↓
Next Chapter
```

You can skip co-creation and directly generate a blueprint, but the resulting story direction is usually less constrained because the model has less information about your intent.

---

## Quality Gates

The open-source version intentionally uses relatively permissive quality settings.

Default configuration:

```yaml
block_finalize: false
auto_rewrite_on_critical: false
auto_humanize_on_fix: true
```

The quality system is designed primarily as an **assistant**, not an authoritarian gatekeeper.

A quality warning does not automatically prevent the author from finalizing a chapter.

You can configure stricter behavior for your own deployment.

---

## LLM Providers

`novel-engine` is designed around **OpenAI-compatible APIs**, allowing different model providers to be configured without fundamentally changing the writing workflow.

This makes it possible to experiment with different models for different roles.

For example, a future configuration could use:

```text
Planning Agent     → Model A
Writing Agent      → Model B
Revision Agent     → Model C
Quality Agent      → Model D
```

The exact model strategy is intentionally left configurable.

---

## Project Status

`novel-engine` is an **experimental open-source project**.

The current focus is on:

- multi-agent orchestration;
- long-form story planning;
- incremental generation;
- structured story memory;
- human-in-the-loop writing;
- continuity management;
- serialized-fiction workflows.

The architecture and UI are still evolving.

Expect rough edges.

Expect things to change.

And please open an Issue before relying on undocumented behavior.

---

## Roadmap

Potential future directions include:

- an English interface and an English prompt set;
- stronger long-context retrieval;
- more sophisticated story-state management;
- improved agent collaboration;
- better continuity checking;
- stronger narrative quality evaluation;
- more flexible model routing;
- richer knowledge-base tooling;
- cloud deployment;
- export formats;
- collaboration features.

The exact roadmap will depend on how the open-source project evolves.

---

## What This Project Is Really Exploring

At a deeper level, `novel-engine` is an experiment in:

> **Can long-form creative writing be treated as a persistent multi-agent planning problem rather than a single LLM generation problem?**

A novel is not merely a sequence of independently generated chapters.

It is a changing system of:

```text
Characters
    +
World
    +
Events
    +
Goals
    +
Conflicts
    +
Foreshadowing
    +
Author Decisions
    +
Narrative Direction
```

The challenge is therefore not simply generating better prose.

It is maintaining a coherent **stateful narrative process** over a long period of time.

That is the problem this project is trying to explore.

---

## Contributing

Issues, discussions, experiments, and forks are welcome.

If you want to make a substantial change, please open an Issue first so that the scope can be discussed before submitting a Pull Request.

Fork it, modify it, experiment with different models, and build your own workflow.

By submitting a Pull Request you agree that your contribution is licensed under
**AGPL-3.0**, and that the maintainer may also use it in this project and in
derived versions of it, including versions distributed or hosted under other
terms.

If you distribute modified versions of the project, please follow the terms of the **AGPL-3.0** license.

---

## License

[AGPL-3.0](./LICENSE)

Part of the writing-reference and prompt-asset material is derived from third-party
work licensed under Apache-2.0. See [NOTICE](./NOTICE) and
[LICENSE-APACHE-2.0](./LICENSE-APACHE-2.0).

---

## Acknowledgements

The project was inspired in part by community experiments around long-form AI fiction, rolling story arcs, and CLI-based novel-generation workflows.

The open-source version intentionally keeps the context-management layer relatively lightweight.

More sophisticated long-context and hosted infrastructure may be explored in future versions.
