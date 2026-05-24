# M105 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 105.

Milestones 1 through 104 are accepted. Post-M104 planning is accepted and
selected:

```text
Milestone 105: Clean KISS Generator Restart Charter Slice
```

Use the orchestrated executor-review loop in this prompt. M105 is a
documentation/architecture milestone only. Do not implement product code, do
not move directories, and do not start the first restart implementation slice.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`

## Goal

Create a clean restart charter for a simple, object-oriented generator
architecture that keeps the project focused on the real product path:

```text
.tsl source data -> validated catalog -> selected implementations -> C++ and Rust library artifacts
```

M105 must turn the accepted post-M104 direction into a durable documentation
contract. The current M57-M104 lowering/request/result/worklist path is
evidence for requirements, diagnostics, and pitfalls. It is not the
architecture to keep extending by default.

M105 must also make the repository layout rule explicit:

```text
old accepted/exploratory state: tslgen/ -> tslgenold/
new clean implementation: fresh tslgen/
```

No new restart product code may be added under `tslgen/` until the old tree is
quarantined under `tslgenold/` or an explicitly accepted equivalent layout
with the same clean separation is recorded.

## Scope

- Create `docs/redesign/kiss-generator-restart.md`.
- Define the restart principles as standing architecture rules, not a
  one-milestone exception.
- Define the small stable concept set and ownership boundaries:
  - `TslProject`
  - source documents / source loader
  - parse result
  - catalog
  - primitive
  - implementation
  - target
  - generator service
  - backend protocol
  - C++ emitter
  - Rust emitter
  - diagnostic reporter
  - artifact set
  - artifact writer
- Define the minimal end-to-end restart slice that should follow the layout
  reset: consume a tiny `.tsl` fixture, build a validated catalog, select one
  implementation for explicit C++ and Rust targets, and emit deterministic C++
  and Rust library artifacts through an explicit writer boundary.
- Define how `docs/redesign/`, `tslgen/`, `tslgenold/`, `tsldata/`, and
  `frozen/` may be used as evidence after the restart.
- State that the current top-level `tslgen/` tree must move to `tslgenold/`
  before new clean product code is added under `tslgen/`.
- Record anti-complexity rules for future milestones:
  - no new IR category, request/result family, inventory, worklist,
    provenance wrapper, registry, dispatcher, hidden backfeed, fixpoint
    machinery, or pipeline stage unless at least two concrete accepted stages
    need it;
  - prefer small OO objects/protocols with clear ownership over chains of
    request/result wrappers;
  - prove value through end-to-end source-to-artifact slices;
  - keep old evidence quarantined and out of runtime imports.
- Update `docs/redesign/implementation-roadmap.md`,
  `docs/redesign/design-decisions.md`, `docs/redesign/pipeline-design.md`,
  `docs/redesign/target-architecture.md`,
  `docs/redesign/testing-strategy.md`,
  `docs/redesign/open-questions.md`, and
  `docs/redesign/missing-lowering-inventory.md` only as needed for coherence.
- Update `docs/agent/current-redesign-state.md` after review acceptance.
- Create the next concrete run prompt under `docs/agent/runs/`.

## Out Of Scope

- Product-code implementation.
- Physically moving `tslgen/` to `tslgenold/`.
- Creating a fresh `tslgen/` package tree.
- Parser, catalog, generator, renderer, backend, writer, CLI, or test
  implementation.
- Adding fixtures, generated output, golden files, compiler execution, or
  runtime workflows.
- Extending `boundary.py`, M57-M104 lowering modules,
  `_lowering_ir_contracts.py`, M99-M104 backend request/result/worklist/
  expansion modules, or the accepted micro-IR taxonomy.
- Porting legacy modules from `frozen/` or preserving old `tslgen/` internals
  for convenience.
- Adding registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  machinery, scheduler/readiness behavior, source repair, renderer-side
  semantic inference, or raw source rewriting.

## Required Executor Task

Run exactly one write-capable documentation executor for M105. The executor
should:

1. Create `docs/redesign/kiss-generator-restart.md` with a concise charter.
2. Keep the charter practical and enforceable: simple OO ownership, direct
   product path, explicit layout reset, and no ceremony without demonstrated
   need.
3. Update only the docs needed to keep the roadmap/state/design contracts
   coherent.
4. Make the next structural milestone explicit. The expected next milestone is
   a layout quarantine slice that moves current `tslgen/` to `tslgenold/` and
   creates or reserves a fresh `tslgen/` for the clean implementation. Do not
   schedule new product-code implementation before that move.
5. Run the required validation.
6. Return a concise review packet with files changed, scope confirmation,
   follow-ups, and validation results.

If the executor discovers that the layout reset is unsafe without additional
inventory or dependency mapping, it may document that as the next structural
milestone, but it must still preserve the rule that no clean product code goes
under `tslgen/` before old state is quarantined.

## Required Review/Audit Subagents

After the documentation executor finishes, use read-only subagents:

1. Architecture reviewer: verify the charter is simple, product-path oriented,
   and avoids reintroducing the M57-M104 micro-IR chain as the default
   architecture.
2. Layout/boundary auditor: verify the `tslgen/` -> `tslgenold/` quarantine
   requirement is explicit and that `tslgenold/` is evidence-only, not runtime
   input for the clean generator.
3. Documentation auditor: verify roadmap, state, design, testing, open
   questions, and missing-lowering inventory remain coherent.
4. Simplicity auditor: verify the charter uses OO for ownership and
   maintainability without creating broad class hierarchies, registries,
   dispatchers, or speculative IR.

Reviewer/auditor subagents are read-only. They must not edit files.

## Review Verdict

Consolidate the executor and subagent results into one verdict:

```text
Accept
Accept With Follow-Ups
Needs Revision
Return To Planner
Reject
```

If the verdict is `Needs Revision`, run one focused documentation revision and
then a focused re-review. If the verdict is `Return To Planner` or `Reject`,
stop and create the appropriate planning/rollback prompt.

## Required Validation

Run:

```bash
git diff --check
```

If touched docs need additional lightweight validation, run it and report it,
but do not run product-code tests unless M105 unexpectedly touches code. M105
should not touch product code.

## Completion Rules

If M105 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M105 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

The next prompt should be for the structural layout-quarantine step unless M105
records a justified stop/return-to-planner condition. The expected next
milestone is:

```text
Milestone 106: Old Implementation Quarantine Layout Reset Slice
```

That milestone should move the current top-level `tslgen/` tree to
`tslgenold/`, create or reserve a fresh `tslgen/` path for the clean
implementation, update validation/import paths as needed, and still avoid
new product-code implementation.

Do not start Milestone 106 in this prompt.

## Final Report

Report:

1. Files changed.
2. Charter created.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command and exact result.
