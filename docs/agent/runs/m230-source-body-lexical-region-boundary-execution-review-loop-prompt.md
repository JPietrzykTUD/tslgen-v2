# M230 Source Body Lexical Region Boundary Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M229 as accepted.

This prompt selects a lowering-enabling implementation milestone. Use the
executor-review loop specified below. Keep the implementation focused on shared
lexical body-region discovery over M229 raw `tsil` payload envelopes. Do not
resume the real x86 fixture in this milestone.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
Milestone 228.5: Outer TSL Declaration Foundation Planning
Milestone 229: Outer TSL Declaration Parser Boundary
```

M229 added a Lark-backed outer TSL declaration parser boundary. It preserves
inline and multiline implementation bodies as raw `ParsedImplementationBodyEnvelope`
payloads with quote form and source spans. It deliberately does not parse or
lower TSIL body semantics.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/syntax/outer_ast.py`
- `tslgen/src/tslgen/syntax/outer_parser.py`
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/lowering/_source_islands.py`
- `tslgen/tests/test_m1625_tsil_lexical.py`
- `tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py`
- Representative source evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/primitives/conversion/cast.tsl`
  - `tsldata/primitives/bitwise/shifts.tsl`
  - `tsldata/primitives/load_store/load.tsl`

## Goal

Add a shared lexical source-body region boundary that consumes M229 raw `tsil`
payload envelopes and produces source-mapped raw spans plus balanced lexical
region candidates for later keyword-specific lowerers.

This is a lexical boundary, not a TSIL semantic parser.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Adds a focused module for source-body lexical regions. Do not grow
   `outer_parser.py`, the old narrow `parser.py`, `lowerer.py`, or
   `generated_primitive_pipeline.py`.
2. Consumes `ParsedImplementationBodyEnvelope` values or a narrow equivalent
   raw payload/span input from M229.
3. Produces typed frozen slotted dataclasses for:
   - raw body segments;
   - balanced region candidates;
   - source spans and source-order provenance;
   - diagnostics for malformed or unbalanced regions.
4. Preserves raw payload text exactly, including escaped inline source text and
   multiline indentation/newlines.
5. Supports source-mapped lookup across inline and multiline payloads.
6. Reuses or consolidates existing delimiter helpers from `tsil_lexical.py`
   and source span/island mechanics where practical.
7. Identifies balanced lexical regions for configured TSIL keyword heads
   without assigning semantics. Region data may include:
   - head span;
   - optional angle/selector span;
   - optional parenthesized payload span;
   - optional braced body span;
   - surrounding raw prefix/suffix spans.
8. Handles representative balanced single-line and multiline forms:
   - `emit_return(...)`;
   - `intrin_compose<...>(...)`;
   - `call<...>(...)`;
   - `if<generation>(...) { ... }`;
   - `else<generation> { ... }`;
   - `loop<range>(...) { ... }`;
   - `switch<compile>(...) { ... }`.
9. Preserves deterministic source order for multiple regions in one payload.
10. Emits diagnostics for malformed/unbalanced configured regions without
    guessing or repairing source.

## Out Of Scope

- TSIL semantic lowering.
- Interpreting `emit_return`, `intrin_compose`, `call`, `if`, `else`, `loop`,
  `switch`, `value`, `type`, `cast`, `mem`, `io`, operators, assignments, or
  expressions.
- Branch evaluation, primitive-call resolution, intrinsic translation, backend
  translation, rendering, generated project writing, or fixture resumption.
- Outer TSL declaration parsing changes.
- Source repair, normalization, fallback guessing, or auto-completion.
- Runtime dependency on `frozen/`, `tslgenold`, `m228-spike`, or
  `m2285-sideways-parser-body-attempt.patch`.
- Growing `outer_parser.py`, `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py` with keyword-local regex scanners.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Boundary reviewer: checks that the implementation remains lexical-only and
   does not assign TSIL semantics.
2. Evidence auditor: checks representative `tsldata` payloads, including
   multiline bodies and escaped inline bodies.
3. Complexity reviewer: checks module-size guardrails and no accretion in
   parser/lowerer/generated pipeline modules.
4. Diagnostics reviewer: checks malformed/unbalanced-region diagnostics and
   source locations.

Use `docs/agent/review-checklist.md`. If review returns `Needs Revision`, run
one focused revision executor and re-review only the blocking findings. If
review returns `Return To Planner` or `Reject`, stop implementation and create
a planner/rollback prompt instead of continuing.

The orchestrator owns final verdict consolidation, state update, and next
prompt creation.

## Required Validation

Run exactly:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py
find tslgen -type d -name __pycache__ -print
```

If the expected M230 test file has a different final name, the executor may use
that path, but the final report must state the exact command actually run and
why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M230 result.
- Update `docs/redesign/design-decisions.md` only if implementation revises
  the accepted parser/body boundary.
- Update `docs/redesign/open-questions.md` if a body-region issue cannot be
  resolved from evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The likely next milestone after M230 is a narrow keyword-specific lowerer that
consumes lexical regions, not another parser foundation step. Do not start it
in M230.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
