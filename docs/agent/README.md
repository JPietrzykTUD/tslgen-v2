# docs/agent — orientation

This directory holds agent/handoff material. Most of it is **historical
`tslgen` process scaffolding**. This README exists so a reader can tell, at a
glance, what describes the **active `tslc` line** and what is archive.

## Active line: `tslc`

The active codebase is `tslc/`. Start here:

- **`../../tslc/CHARTER.md`** — the design rules `tslc` holds itself to. Read first.
- **`../../tslc/README.md`** — the pipeline overview and quick start.
- **`tslc-vector-query-handoff.md`** — the running handoff for recent `tslc`
  work (vector queries, lowering/render modularization, backend dialect facets,
  diagnostic provenance, performance). This is the authoritative `tslc` log.
- **`../redesign/design-decisions.md`** — the ADRs. Most recent that apply to
  `tslc`: ADR-074 (vector-query vocabulary) and ADR-075 (diagnostic provenance).

`frozen/`, `tslgen/`, and `tslgenold/` are read-only evidence only and are never
imported at runtime (see the charter).

## Active-but-mixed

- **`current-redesign-state.md`** — its top banner and `## Current Work State`
  section have been refreshed for `tslc`. **Everything between them is stale
  `tslgen` milestone history (M1–M254.x)**, kept only as the `tslgen` record.

## Historical `tslgen` process scaffolding (not active work)

These describe the codex milestone process that built the superseded `tslgen`
line. They are kept for orientation; do not run them as `tslc` tasks.

- `runs/` — ~358 milestone run prompts (`m100`…`m254.x`). Note: a few recent
  `tslc-*` prompts also live here.
- `m254.{6,7,8,9}-implementationbody-accounting.txt` — `tslgen`
  ImplementationBody-deletion accounting dumps.
- `codex-workflow.md`, `execution-template.md`, `next-run-prompt-protocol.md`,
  `review-checklist.md` — generic codex executor/reviewer process docs.
- `prompt-templates/`, `subagents/` — codex role/prompt definitions.
