# references/ — provenance and change notes

Writing-knowledge material appended to task prompts by `backend/context/assembler.py`.
Task templates themselves are never modified.

Part of this directory is derived from [ainovel-cli](https://github.com/voocel/ainovel-cli)
(Apache License 2.0). The license text is in `LICENSE-APACHE-2.0` at the repository
root; the summary of third-party material is in `NOTICE`.

| File | Origin | Changed by novel-engine |
| ---- | ------ | ----------------------- |
| `arc-planning.md` | novel-engine (original) | — |
| `writing-quality.md` | novel-engine (original) | — |
| `character-building.md` | ainovel-cli `assets/references/character-building.md` | No |
| `character-template.md` | ainovel-cli `assets/references/character-template.md` | No |
| `dialogue-writing.md` | ainovel-cli `assets/references/dialogue-writing.md` | No |
| `longform-planning.md` | ainovel-cli `assets/references/longform-planning.md` | No |
| `chapter-guide.md` | ainovel-cli `assets/references/chapter-guide.md` | Yes |
| `consistency.md` | ainovel-cli `assets/references/consistency.md` | Yes |
| `hook-techniques.md` | ainovel-cli `assets/references/hook-techniques.md` | Yes |
| `outline-template.md` | ainovel-cli `assets/references/outline-template.md` | Yes |
| `quality-checklist.md` | ainovel-cli `assets/references/quality-checklist.md` | Yes |

Sibling assets under `backend/prompts/assets/` share the same lineage; see `NOTICE`.

Which reference is appended for which agent, and for which chapters, is decided
in `backend/context/assembler.py`.
