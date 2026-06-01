# M207 Selected Symbol Immediate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M206.5 as accepted.

This is a planning milestone, not an implementation milestone. Use the
subagent workflow with read-only evidence and architecture reviewers. The main
thread is the orchestrator and owns the final roadmap/state updates. Do not
modify implementation code.

## Accepted State

Accepted through:

```text
M206.5: Complete Observed Signature Term Model
```

Selected milestone:

```text
Milestone 207: Selected Symbol Immediate Planning
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/flaws-to-fix.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m206_to_type_suffix_infix_translation.py`
- `tslgen/tests/test_m2065_signature_term_model.py`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/load_store/array.tsl`

## Goal

Plan the smallest correct lowering path for source-owned symbol immediate
modifier operands such as:

```text
immediate(1)=index
immediate(1)=Index
```

The goal is to decide what typed selected context is needed before any
implementation translates these operands. Do not treat `index` or `Index` as
backend magic strings.

Important source-of-truth rule: compile-time immediate-ness comes from the
primitive signature/template parameter kinds, not from the parameter name. For
example, in:

```text
prim<v:=(v,sImm)>[cast=convert, direction=up] convert_up(data, index)
```

the second source parameter is compile-time/immediate because its signature
term is `sImm`. The name `index` is user/source-owned and arbitrary. M206.5
must already have made that parameter-to-signature-term mapping available as
typed catalog/lowering context.

## Planning Scope

- Inventory all observed non-literal `immediate(N)=SYMBOL` intrinsic compose
  modifier operands across `tsldata/primitives/**/*.tsl`.
- Record source locations, intrinsic compose bases, argument positions, and
  nearby `.tsl` ownership context for each observed symbol.
- Determine the symbol's owning primitive parameter and its corresponding
  signature/template term. Treat `sImm` as compile-time immediate evidence and
  verify whether any other immediate-like signature terms exist in the corpus.
- Distinguish signature-owned compile-time parameters from compile-time switch
  variables, test/catalog values, or other source constructs; do not infer
  immediacy from names such as `index` or `Index`.
- Decide whether the next executable slice can introduce a minimal typed
  signature-parameter/immediate value context, or whether a prior
  catalog/signature evidence milestone is required.
- Define exact positive and negative tests for the next executable milestone:
  arbitrary source-owned names should be supported only when their primitive
  parameter maps to an `sImm`-style compile-time signature term; unresolved raw
  symbols and runtime parameters must remain unsupported.
- Keep M204/M206 behavior intact: destination suffix names and
  `to_type_suffix` stay selected-context gated, not raw-name matched.

## Out Of Scope

- Implementation code.
- Translating raw `index` or `Index` by spelling.
- Broad TSIL parsing.
- Intrinsic-name assembly.
- Rendering, generated output, artifact writing, or build verification.
- Dependency closure.
- Source repair.
- FTF-002 `intrin::suffix(si?)` cleanup.
- Runtime dependency on `frozen/` or `tslgenold`.

## Subagent Workflow

Use read-only subagents for:

- evidence audit: inventory all observed symbol immediate operands and their
  source ownership context;
- architecture/boundary audit: check that the proposed next slice does not
  turn source-owned names into magic strings and does not add broad IR
  machinery prematurely.

The orchestrator must consolidate findings into one verdict:

- `Accept`: update the roadmap and state, and create the next concrete prompt.
- `Needs Revision`: revise only docs/planning and rerun the focused review.
- `Return To Planner`: record the blocking design issue and create a planner
  prompt instead of selecting an executor.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M207 planning result, and
create the next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Planning/review verdict.
2. Selected next milestone or stop condition.
3. Why that next milestone is useful.
4. Files changed.
5. Validation commands with exact results.
