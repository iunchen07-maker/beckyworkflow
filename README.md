# Internal Systems Portfolio

**English** · [繁體中文](README.zh-TW.md)

This repo collects the **architecture notes and design decisions** behind two internal systems I built with Claude through vibe coding while working as a PM at a tech company, plus the **spec-driven workflow (the method)** I use to work with Claude.
- Internal Request Hub: I described the pain points and the spec I wanted; Claude handled the technical structure and the UI design.
- Learning Platform: the company's HR acted as PM and owned the UI design and spec decisions. Claude and I built the site together and connected it to internal company services; Claude handled the technical structure.
- Agent Workflow: the way of working behind both systems. It covers spec discussion, sign-off, writing, auditing, testing and the user guide, and says which agent and which model handles each step.

Because of confidentiality obligations, there is no source code or internal information here. All system names and integrations have been replaced with neutral names, and numbers have been blurred. Examples in the workflow are rewritten around a fictional to-do list app. The focus is on **how the systems are designed, why they are designed that way, and how engineering quality is kept**.

## Projects

| Project | In one line | Stack | My role |
|---|---|---|---|
| [Learning Platform](learning-platform/) | Internal training platform (LMS) for a mid-to-large company | Laravel + Nuxt/Vue 3 + PostgreSQL + K8s | Backend lead, architecture, CI/CD, E2E test suite |
| [Internal Request Hub](internal-request-hub/) | Tracks cross-team requests through their whole lifecycle, from wish to closure | FastAPI + htmx + SQLite | Sole owner of full stack, architecture, CI/CD and test strategy |
| [Agent Workflow](agent-workflow/) | A spec-driven workflow for PMs designing systems from scratch with Claude Code: humans decide, AI drafts, writes and audits | Claude Code subagents (12) + rulebooks | Method design, agent definitions, process upkeep |

Each system project folder has two documents (written in Traditional Chinese):

- **README.md**: what the system is for, the stack, and engineering highlights
- **ARCHITECTURE.md**: architecture diagrams (Mermaid), data flow, and for each design decision, the problem and how it was solved

`agent-workflow/` contains the workflow rulebooks (`workflow/`, in Traditional Chinese), 12 subagent definitions (`agents-setup/`), and a README in English and Chinese.

## Engineering principles shared by both systems

- **Tests are gatekeepers, not decoration.** The full suite must pass before merge. A custom impact map works out from the git diff which tests to run; if nothing matches, it fails safe and runs the full suite.
- **Single source of truth.** Anything that can be derived is not stored twice, to avoid inconsistent double writes.
- **Degrade on failure, don't spread it.** Notifications, AI and external integrations are best-effort; when they fail, the main flow keeps working.
- **Ops surfaces itself.** Sync health and errors show up directly in the admin UI, with no log digging needed.
