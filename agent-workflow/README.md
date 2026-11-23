# Spec-driven Agent Workflow

**English** · [繁體中文](README.zh-TW.md)

> A spec-driven workflow for product managers who design systems from scratch with Claude Code.
> **Humans decide; AI drafts, writes and audits.** Each step runs on the model tier that fits the job.

This repo holds the **method itself**: the workflow rulebooks (`workflow/`, in Traditional Chinese) and 12 Claude Code subagent definitions (`agents-setup/`).
This is a showcase release (v0.1). The project template, bootstrap script and helper check scripts are not included yet. Where the rulebooks mention those scripts, read them as design notes.

## Core ideas

| Cognitive work | Who |
|---|---|
| Decide the spec, reason, resolve forks; scan impact and audit independently | 🔵 **Opus + PM** |
| Prepare options, **write** decided content, detect drift, run tests | 🟢 Sonnet |
| Light tidying (open questions, mock values) | 🟡 Haiku |
| Sign off, release, spot-check | 👤 PM |

- **The writer never decides.** The spec-writer agent only transcribes what was already decided. Every decision goes through Opus and the PM.
- **🚦 Token gate.** Before an expensive step (implementation, test generation, test runs, batch expansion), the agent reports its scope and size and waits for the PM to approve. By default it runs one feature at a time.
- **Vendoring.** A new project gets its own copy of `workflow/` and `agents-setup/` under `.claude/`. Anyone else's Claude can then run the same process without installing this repo.

## Three axes

```
Axis A  Foundation track (once per project)  L0 Vision → L1 Scope → L2 Entities → L3 Permission → [seam] → L4 Process → L5 UI → L6 Tech
                                                    │ each layer's gate calls Axis B
Axis B  Phase 0 decision-write engine        discuss → impact-scan → PM sign-off → write → verify → drift → commit (Path A/B)
                                                    │ per-feature callbacks
Axis C  Phases 1–8                           mockup → tech spec → test scripts → build → autotest → manual check → user guide
                                             only the subset whose upstream changed
```

- **Two-pass drafting.** Sonnet first fills in every clear-cut answer and marks each fork with `⏳`. Opus then resolves only the `⏳` items. Opus does most of its work while the foundation is laid and much less once it is locked.
- **Phase 0 checks.** The impact scan expands keywords to at least 30 terms and checks eight dimensions. The writer refuses to write without a scan result and emits a JSON self-report. The verifier then cross-checks three independent sources: the issue file, the strong links, and what the diff implies.
- **Spec lifecycle.** The spec body describes only current behavior. Every change adds a decision record (why, rejected options, what it overturned) linked to a work item. A feature that gets postponed moves verbatim to `Spec/Deferred/`, with a restore list that lets it be put back later. Existing section numbers are never renumbered; retired or deferred numbers stay reserved.

## The 12 agents

| Agent | Phase | Role | Model |
|---|---|---|---|
| `phase0-impact-scanner` | 0 | Scan the whole spec for strong, weak or no impact before sign-off | opus |
| `phase0-spec-writer` | 0 | Write decisions into the spec and emit a JSON self-report | sonnet |
| `phase0-spec-verifier` | 0 | Independent audit; auto-fix mechanical deviations | opus |
| `phase0-mockup-drift-scanner` | 0 | Detect drift between mockups or flowcharts and the spec | sonnet |
| `phase0-spec-deferrer` | 0 | Move a postponed feature out of the spec verbatim, and restore it later by anchor | opus |
| `phase1-product-designer` | 1 | Annotated mockup HTML and user stories | sonnet |
| `phase2-tech-spec` | 2 | Derive DB, API and state machine | sonnet |
| `phase25-pending-manager` | 2.5 | Track open questions and mock values | haiku |
| `phase4-test-writer` | 4 | AC → coverage matrix → YAML test cases | sonnet |
| `phase5-dev-builder` | 5 | Implement, keeping `data-action` hooks for tests | sonnet |
| `phase6-test-runner` | 6 | Run automated tests, take screenshots, write the report | sonnet |
| `phase8-guide-writer` | 8 | Produce the user guide | sonnet |

## Try it (manual)

```bash
mkdir -p .claude/agents .claude/workflow
cp <this-repo>/agents-setup/*.md .claude/agents/
cp <this-repo>/workflow/*.md     .claude/workflow/
```

Open Claude Code, run `/agents` to confirm the agents loaded, then say "start Phase 0".

## Roadmap

- [ ] Project template and one-command bootstrap
- [ ] The helper check scripts referenced by the rulebooks
- [ ] A worked example in a fictional domain (`examples/`)
- [ ] English rulebooks
