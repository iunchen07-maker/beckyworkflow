# Spec-driven Agent Workflow

**English** · [繁體中文](README.zh-TW.md)

> A spec-driven workflow for product managers who design systems from scratch with Claude Code.
> **Humans decide; AI drafts, writes and audits.** Each step runs on the model tier that fits the job.

This folder (`agent-workflow/`) holds the **method itself**: the workflow rulebooks (`workflow/`) and 12 Claude Code subagent definitions (`agents-setup/`), plus one slash command (`commands/`), three skills (`skills/`) and one recipe (`recipes/`: SPEC version branches, with its sync scripts and tests). All rulebooks, agents, the command, the skills and the recipe are written in Traditional Chinese; only the READMEs are bilingual. Start with the rulebook index: [`workflow/README.md`](workflow/README.md).
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
- **Vendoring.** A new project gets its own copy of `workflow/` and `agents-setup/` under `.claude/`. Anyone else's Claude can then run the same process without installing this folder.

## Three axes

```
Axis A  Foundation track (once per project)  L0 Vision → L1 Scope → L2 Entities → L3 Permission → [seam] → L4 Process → L5 UI → L6 Tech
                                                    │ each layer's gate calls Axis B
Axis B  Phase 0 decision-write engine        discuss → impact-scan → PM sign-off → write → verify → drift → commit (Path A/B)
                                                    │ per-feature callbacks
Axis C  Phases 1–8                           mockup → tech spec → test scripts → build → autotest → manual check → user guide
                                             only the subset whose upstream changed
```

- **Axis A, foundation track**: decide Vision, Scope, Entities (including the Glossary, the single source of terms), Permission, Process, UI and Tech layer by layer. Passing each layer's gate means one Phase 0 run. See [`workflow/foundation-track.md`](workflow/foundation-track.md).
- **Axis B, Phase 0 decision-write engine**: every spec change goes through here. See [`workflow/phase-0-spec-update.md`](workflow/phase-0-spec-update.md).
- **Axis C, artifact pipeline**: assembled on demand; only the parts whose upstream changed are re-run.
- **Entry routing**: which track a new request takes. See [`workflow/entry-routing.md`](workflow/entry-routing.md).
- **Two-pass drafting.** Sonnet first fills in every clear-cut answer and marks each fork with `⏳`. Opus then resolves only the `⏳` items. Opus does most of its work while the foundation is laid and much less once it is locked.

## Phase 0: how one spec change gets into the SPEC

| Step | What happens | Who |
|---|---|---|
| Pre-discussion digest | Turn the prepared material into an agenda | 🟢 |
| Decide the draft | Decide item by item, resolve forks | 🔵 + 👤 |
| impact-scan | Expand keywords to at least 30 terms, scan the whole SPEC for strong, weak or no impact, and check eight dimensions: terminology, API, permissions, state machine, cross-spec consistency, summary-layer sync, re-reading every row of the same table, dead ends | 🔵 |
| PM sign-off | Decide after reading the scan result | 👤 |
| spec-writer writes | Transcribe the decided draft into the feature document; **refuses to write without a scan result**; emits a JSON self-report | 🟢 |
| (if postponed) spec-deferrer moves it | A feature the PM postpones moves verbatim to `Spec/Deferred/`; the body keeps a reserved-number placeholder and a restore list, so it can be put back later by anchor | 🔵 |
| spec-verifier audits | Cross-checks three sources: the issue, the strong links, and what the diff implies; re-verifies the self-report by machine; auto-fixes mechanical deviations; term lint; checks the decision record and restore anchors | 🔵 |
| Release | Path A: one commit; Path B: feature branch with two commits | 👤 |

- **Phase 0 checks.** The writer refuses to write without a scan result and emits a JSON self-report; the verifier never trusts that self-report without re-checking it.
- **Spec lifecycle.** The spec body describes only current behavior. Every change adds a decision record (why, rejected options, what it overturned) linked to a work item. A feature that gets postponed moves verbatim to `Spec/Deferred/`, with a restore list that lets it be put back later. Existing section numbers are never renumbered; retired or deferred numbers stay reserved. See [`workflow/phase-0-spec-update.md`](workflow/phase-0-spec-update.md) §SPEC lifecycle.
- **SPEC version branches.** The spec is always written on `main`, which often holds several releases' worth of behavior at once. Projects that opt in get one `spec/vX.Y.Z` branch per in-progress milestone; CI cherry-picks each `main` commit into the branches its work item's milestone belongs to, so engineers and QA read exactly one release's full behavior, frozen by a release tag. See [`recipes/spec-version-branches.md`](recipes/spec-version-branches.md) (the `recipes/` folder holds how-to-install guides; the sync scripts, tests and CI snippet are in [`recipes/spec-version-branches/`](recipes/spec-version-branches/)).
- **Verification.** Any code change follows [`workflow/verification.md`](workflow/verification.md): acceptance scripts are written first by someone other than the implementer, the implementer cannot edit them, and escaped bugs become new rules.

## The 12 agents

| Agent | Phase | Role | Model |
|---|---|---|---|
| [`phase0-impact-scanner`](agents-setup/phase0-impact-scanner.md) | 0 | Scan the whole spec for strong, weak or no impact before sign-off | opus |
| [`phase0-spec-writer`](agents-setup/phase0-spec-writer.md) | 0 | Write decisions into the spec and emit a JSON self-report | sonnet |
| [`phase0-spec-verifier`](agents-setup/phase0-spec-verifier.md) | 0 | Independent audit; auto-fix mechanical deviations | opus |
| [`phase0-mockup-drift-scanner`](agents-setup/phase0-mockup-drift-scanner.md) | 0 | Detect drift between mockups or flowcharts and the spec | sonnet |
| [`phase0-spec-deferrer`](agents-setup/phase0-spec-deferrer.md) | 0 | Move a postponed feature out of the spec verbatim, and restore it later by anchor | opus |
| [`phase1-product-designer`](agents-setup/phase1-product-designer.md) | 1 | Annotated mockup HTML and user stories | sonnet |
| [`phase2-tech-spec`](agents-setup/phase2-tech-spec.md) | 2 | Derive DB, API and state machine | sonnet |
| [`phase25-pending-manager`](agents-setup/phase25-pending-manager.md) | 2.5 | Track open questions and mock values | haiku |
| [`phase4-test-writer`](agents-setup/phase4-test-writer.md) | 4 | AC → coverage matrix → YAML test cases | sonnet |
| [`phase5-dev-builder`](agents-setup/phase5-dev-builder.md) | 5 | Implement, keeping `data-action` hooks for tests | sonnet |
| [`phase6-test-runner`](agents-setup/phase6-test-runner.md) | 6 | Run automated tests, take screenshots, write the report | sonnet |
| [`phase8-guide-writer`](agents-setup/phase8-guide-writer.md) | 8 | Produce the user guide | sonnet |

Phase 7 is a manual spot-check that the PM runs. Phase 3 (Mockup) was merged into Phase 1.

## Rulebook index

All rulebooks are in Traditional Chinese. A grouped index with a reading order is in [`workflow/README.md`](workflow/README.md).

| File | Contents |
|---|---|
| [`entry-routing.md`](workflow/entry-routing.md) | Which track a new request takes |
| [`foundation-track.md`](workflow/foundation-track.md) | Axis A, foundation track L0–L6 |
| [`phase-0-spec-update.md`](workflow/phase-0-spec-update.md) · [`phase-0-impact-scan.md`](workflow/phase-0-impact-scan.md) | Axis B, decision-write engine |
| [`phase-1-product-design.md`](workflow/phase-1-product-design.md) to [`phase-8-userguide.md`](workflow/phase-8-userguide.md) | Axis C, one file per phase |
| [`CONTRACTS.md`](workflow/CONTRACTS.md) · [`SPEC_NUMBERING_RULES.md`](workflow/SPEC_NUMBERING_RULES.md) · [`CROSSLINK_REGEN.md`](workflow/CROSSLINK_REGEN.md) · [`GUIDE_SECTIONS.md`](workflow/GUIDE_SECTIONS.md) | Hand-off contracts, numbering, cross-links, guide sections |
| [`file-discipline.md`](workflow/file-discipline.md) · [`discussion-docs.md`](workflow/discussion-docs.md) | Preventing file sprawl, discussion-document discipline |
| [`verification.md`](workflow/verification.md) | Verification for code changes: scripts written first by a non-implementer, the implementer cannot edit the checks, escaped bugs become rules |
| [`recipes/spec-version-branches.md`](recipes/spec-version-branches.md) | Recipe: SPEC version branches with CI auto-sync |

## Try it (manual)

```bash
# in your project root
mkdir -p .claude/agents .claude/workflow
cp <this-repo>/agent-workflow/agents-setup/*.md .claude/agents/
cp <this-repo>/agent-workflow/workflow/*.md     .claude/workflow/
```

Open Claude Code, run `/agents` to confirm the agents loaded, then say "start Phase 0".

## Slash command and skills

| File | What it does |
|---|---|
| [`commands/spec-change.md`](commands/spec-change.md) | `/spec-change`: a 12-step no-skip Phase 0 checklist (open MRs → work item and draft → impact scan → proposal → PM sign-off → worktree → write or defer → verify → drift → diff review → legacy-cleanup audit → summary), one evidence line per step |
| [`skills/verify/SKILL.md`](skills/verify/SKILL.md) | Runs the code-change verification flow from `workflow/verification.md` |
| [`skills/scenario-expansion/SKILL.md`](skills/scenario-expansion/SKILL.md) | Expands a requirement into a scenario matrix (HP/EC/ER, domain blind spots, the 12 Phase 0 boundary questions) that feeds Phase 1 and Phase 4 |
| [`skills/task-breakdown/SKILL.md`](skills/task-breakdown/SKILL.md) | Breaks a scoped feature into vertical to-dos, each with a DoD, priority and dependencies |

```bash
mkdir -p .claude/commands .claude/skills
cp <this-repo>/agent-workflow/commands/*.md .claude/commands/
cp -R <this-repo>/agent-workflow/skills/*   .claude/skills/
```

> `$CLAUDE_WORKSPACE` in the rulebooks, command and skills means the location of this folder (`agent-workflow/`). Helper scripts they mention under `scripts/` are not included yet (see Roadmap); the version-branch scripts under `recipes/` are included.

## Glossary

| Term | Meaning in this folder |
|---|---|
| Subagent | A Claude Code agent defined in `agents-setup/`; the main session calls it for one job, with its own model and tools |
| Rulebook | One file in `workflow/`; the authority for how a phase or cross-cutting rule works |
| SPEC | The project's spec `.md` files under `Spec/`; the source of truth for current behavior (`.docx` is only rendered output) |
| US-ID | A user-story number such as `US-T1.1`; the stable anchor scanners and mockups (`data-spec`) use to find what a change touches |
| HP / EC / ER | Happy Path / Edge Case / Error: the three columns every action is expanded into by scenario-expansion |
| P0 / P1 / P2 | Priority tiers; for open questions, P0 blocks building the DB or backend, P1 stops one feature from fully working, P2 is nice-to-have |
| AC | Acceptance criteria: sub-sections of a user story in the SPEC; Phase 4 test cases point to them with `ac:` |
| DoD | Definition of Done: how a to-do counts as finished (task-breakdown) |
| Path A / B | The two Phase 0 release routes: A is a text-only change in one commit; B also changes mockups, on a feature branch with two commits |
| Drift | Mockups or flowcharts that no longer match the SPEC after a write; listed by the mockup-drift-scanner for the PM |
| Vendoring | Copying `workflow/` and `agents-setup/` into a project's `.claude/` so the project carries its own process |
| MR | A GitLab merge request |
| Milestone | The release version (e.g. `v1.10.0`) a work item belongs to; drives SPEC version branches and when Phase 4 tests run |
| Worktree | A separate git worktree; Phase 0 writes happen there, never in the main tree (`/spec-change` Step 6 is a hard gate) |
| L0–L6 | Foundation layers: Vision, Scope, Entities, Permission, Process, UI, Tech; each layer passes its gate with one Phase 0 run |
| Seam | The layer where the foundation track hands over to per-feature Phases 0–8; before it, no mockups or tests are produced |

## Roadmap

- [ ] Project template and one-command bootstrap
- [ ] The helper check scripts referenced by the rulebooks
- [ ] A worked example in a fictional domain (`examples/`)
- [ ] English rulebooks
