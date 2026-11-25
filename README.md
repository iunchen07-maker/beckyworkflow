# Internal Systems Portfolio

**English** · [繁體中文](README.zh-TW.md)

This repo collects the **architecture notes and design decisions** behind two internal systems I built with Claude through vibe coding while working as a PM at a tech company, plus the **spec-driven workflow (the method)** I use to work with Claude.
- Learning Platform: the company's HR acted as PM and owned the UI design and spec decisions. Claude and I built the site together and connected it to internal company services; Claude handled the technical structure.
- Internal Request Hub: I described the pain points and the spec I wanted; Claude handled the technical structure and the UI design.
- Agent Workflow: the way of working behind both systems. It covers spec discussion, sign-off, writing, auditing, testing and the user guide, and says which agent and which model handles each step. It also ships ready-to-install SPEC CI checks, version-branch sync scripts, and a verification flow for code changes.

Because of confidentiality obligations, there is no source code or internal information here. All system names and integrations have been replaced with neutral names, and numbers have been blurred. Examples in the workflow are rewritten around a fictional to-do list app. The focus is on **how the systems are designed, why they are designed that way, and how engineering quality is kept**.

## Where to start

1. **This page**: what the two systems are and what my role was.
2. **System design**: [`learning-platform/ARCHITECTURE.md`](learning-platform/ARCHITECTURE.md) and [`internal-request-hub/ARCHITECTURE.md`](internal-request-hub/ARCHITECTURE.md).
3. **The method**: [`agent-workflow/README.md`](agent-workflow/README.md).

## Projects

| Project | In one line | Stack | My role |
|---|---|---|---|
| [Learning Platform](learning-platform/) | Internal training platform (LMS) for a mid-to-large company | Laravel + Nuxt/Vue 3 + PostgreSQL + K8s | Built it with Claude from HR's spec: integrated internal services, CI/CD, E2E test suite; Claude owned the technical structure |
| [Internal Request Hub](internal-request-hub/) | Tracks cross-team requests through their whole lifecycle, from wish to closure | FastAPI + htmx + SQLite | PM: pain points, spec and acceptance; drove Claude through implementation, CI/CD and release; Claude owned the technical structure and UI design |
| [Agent Workflow](agent-workflow/) | A spec-driven workflow for PMs designing systems from scratch with Claude Code: humans decide, AI drafts, writes and audits | Claude Code subagents (12) + rulebooks + Python CI checks (GitLab CI) | Method design, agent definitions, process upkeep |

Each system project folder has two documents (written in Traditional Chinese):

- **README.md**: what the system is for, the stack, and engineering highlights
- **ARCHITECTURE.md**: architecture diagrams (Mermaid), data flow, and for each design decision, the problem and how it was solved

`agent-workflow/` contains:

| Folder | Contents | Count | Language |
|---|---|---|---|
| [`workflow/`](agent-workflow/workflow/) | Workflow rulebooks (entry routing, foundation track, Phases 0–8, cross-cutting rules) | 20 rulebooks + an index README | Traditional Chinese (index is bilingual) |
| [`agents-setup/`](agent-workflow/agents-setup/) | Claude Code subagent definitions | 12 | Traditional Chinese |
| [`commands/`](agent-workflow/commands/) | The `/spec-change` slash command | 1 | Traditional Chinese |
| [`skills/`](agent-workflow/skills/) | Skills (verify, scenario-expansion, task-breakdown) | 3 | Traditional Chinese |
| [`recipes/`](agent-workflow/recipes/) | [SPEC CI checks](agent-workflow/recipes/spec-ci-gates.md) (9) and [SPEC version branches](agent-workflow/recipes/spec-version-branches.md), each with scripts, a CI snippet and tests | 2 recipes | Traditional Chinese |

All documents, agents, commands and skills are written in **Traditional Chinese**; only the READMEs are bilingual (English and Chinese).

## Engineering principles shared by both systems

- **Tests are gatekeepers, not decoration.** The full suite must pass before merge. A custom impact map works out from the git diff which tests to run; if nothing matches, it fails safe and runs the full suite.
- **Single source of truth.** Anything that can be derived is not stored twice, to avoid inconsistent double writes.
- **Degrade on failure, don't spread it.** Notifications, AI and external integrations are best-effort; when they fail, the main flow keeps working.
- **Ops surfaces itself.** Sync health and errors show up directly in the admin UI, with no log digging needed.
