# M154 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M153:

```text
Milestone 154: Generation Value Query Corpus Inventory Boundary
```

Milestones 1 through 153 are accepted. M153 locked down
`details::arith_add`, `details::arith_mul`, and `details::arith_rem` as raw
backend/language support helper calls and recorded the post-M152 lowering
backlog.

M154 selects the first backlog lane: `value<generation>(...)`. This milestone
is an inventory and planning boundary only. It must not implement generation
value evaluators, branch pruning, loop execution, backend rendering, or broad
expression parsing.

The planning output must identify the biggest cohesive subset of
generation-value queries that can be implemented safely in one follow-up
executor milestone. "Biggest" means the largest set that shares one typed
context/evaluator boundary and can be tested together without parsing
surrounding target-language expressions or mixing unrelated TSIL keyword
families.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/requirements.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`

## Goal

Create a corpus-grounded inventory of every generation-value query family used
by current `tsldata/**/*.tsl` sources:

- identify each observed `value<generation>(...)` family and representative
  source locations;
- classify whether each family depends on type facts, vector/extension facts,
  primitive attributes, generic-vector aliases, mask/lane constants, or nested
  TSIL queries;
- separate standalone query families from surrounding raw syntax such as
  loops, assignments, casts, calls, array indexes, `if<generation>`, and
  `if<compile>`;
- recommend the largest safe cohesive subset of generation-value query
  families to implement in one next executable lowering slice, with explicit
  justification for included and excluded families.

## Required Executor Task

Run exactly one write-capable executor for M154. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Survey all current `tsldata/**/*.tsl` files, not a single primitive file.
3. Create `docs/redesign/generation-value-query-inventory.md` or an
   equivalently focused section if that file already exists.
4. Update `docs/redesign/missing-lowering-inventory.md` and
   `docs/redesign/implementation-roadmap.md` to point to the inventory and the
   selected largest-safe next slice.
5. Keep `docs/agent/current-redesign-state.md` ready for M154 finalization
   only after review acceptance.
6. Do not modify production code or tests unless the executor discovers that a
   docs-only validation fixture is required to make the inventory reproducible.

## Required Inventory Shape

The inventory must at least classify these likely families if present in the
current corpus:

- `value<generation>(vector::length)`
- `value<generation>(vector::alignment)`
- `value<generation>(type::size_bytes(...))`
- `value<generation>(type::is_signed(...))`
- `value<generation>(type::is_same(...))`
- `value<generation>(primitive::attribute(...))`
- `value<generation>(mask::lane::all_true)`
- `value<generation>(generic::length(...))`
- `value<generation>(generic::runtime_length(...))`

If additional families are observed, record them explicitly. If any listed
family is absent, say so with the evidence command result.

## Largest-Safe Subset Selection Criteria

The inventory must rank candidate subsets and choose one follow-up executor
scope. The chosen subset should be as broad as possible while satisfying all
of these constraints:

- all included families share the same explicit typed inputs, such as selected
  scalar/type facts, selected vector/extension facts, primitive attributes, or
  alias facts already available from accepted lowering;
- every included family can lower an isolated `value<generation>(...)` query
  island without requiring branch pruning, loop expansion, assignment parsing,
  operator precedence, raw expression evaluation, backend rendering, or source
  repair;
- the implementation can have one coherent owner/API and one coherent test
  fixture family;
- unsupported neighboring syntax remains raw or diagnostic at the documented
  boundary;
- excluded families are listed with the specific missing prerequisite, not
  just marked "later."

Prefer a larger cohesive subset over a single tiny query when the additional
families use the same facts and diagnostics. Reject a larger subset if it
would require a second independent semantic context or a general expression
parser.

## Must Preserve

- M107-M153 accepted behavior, diagnostics, source locations, and generated
  bytes.
- The M153 raw helper boundary: `details::*` support helpers are not
  generation-value lowering.
- The accepted type-query work for `type<generation>(...)` and
  `type<backend>(...)`; do not redesign it during this inventory.
- The source-body token model: raw text remains source truth, and lowerable
  islands must be selected by explicit future milestones.

## Out Of Scope

Implementing generation-value evaluators; resolving any new
`value<generation>(...)` form; pruning `if<generation>` branches; executing
`loop<unroll>` or `loop<range>`; lowering `var`, `let`, `cast`, `mem`, `io`,
`intrin`, `intrin_compose`, `call<primitive=...>`, helper calls, assignments,
array indexing, operators, or backend queries; backend rendering; source
repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies; registries,
dispatchers, fixpoint mechanisms, broad request/result/worklist families, or
source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Evidence auditor: verify the inventory covers all current
   `value<generation>(...)` occurrences in `tsldata/**/*.tsl` and cites
   representative source locations.
2. Architecture reviewer: verify the milestone stays docs/inventory-only and
   does not add a generation expression parser, evaluator, or new IR family.
3. Boundary auditor: verify M153 helper raw preservation and M107-M153
   behavior remain untouched.
4. Documentation auditor: verify roadmap, missing-inventory, behavioral/domain
   docs, and current state are coherent.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
rg -n "value<generation>\\(" tsldata -g "*.tsl"
rg --count-matches "value<generation>\\(" tsldata -g "*.tsl"
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of this docs-only
lowering inventory. The `rg` commands are evidence commands; report their
exit codes and summarize the output shape instead of pasting the full corpus
listing if it is large.

## Completion Rules

If M154 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M154 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M154 is accepted. Do not implement generation-value
evaluator code until M154 is accepted and the next prompt explicitly selects
that work. The next prompt should select the largest-safe subset identified by
the M154 inventory, unless review records a stop condition or a blocking
design issue.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 155 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
