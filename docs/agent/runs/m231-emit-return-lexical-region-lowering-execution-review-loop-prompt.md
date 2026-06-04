# M231 Emit Return Lexical Region Lowering Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M230 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. Keep the implementation focused on the
`emit_return(...)` keyword envelope already discovered by M230 lexical regions.
Do not lower the payload expression in this milestone.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
Milestone 228.5: Outer TSL Declaration Foundation Planning
Milestone 229: Outer TSL Declaration Parser Boundary
Milestone 230: Source Body Lexical Region Boundary
```

M229 added a Lark-backed outer TSL declaration parser boundary. M230 added a
shared lexical source-body region scanner over M229 raw `tsil` payload
envelopes. M230 produces source-mapped raw segments and balanced lexical
region candidates for configured keyword heads without assigning TSIL
semantics.

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
- `tslgen/src/tslgen/syntax/source_body_regions.py`
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/syntax/outer_ast.py`
- `tslgen/src/tslgen/syntax/outer_parser.py`
- `tslgen/tests/test_m230_source_body_lexical_region_boundary.py`
- Representative source evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/primitives/conversion/cast.tsl`
  - `tsldata/primitives/load_store/load.tsl`

## Goal

Add a narrow keyword-specific lowerer that consumes M230 lexical region
candidates and lowers only the symbolic `emit_return` keyword identity into
typed return facts/directives with source-mapped raw payload spans.

This is the first consumer of M230 lexical regions. It must prove the clean
model: body payloads are raw source text plus lowerable lexical islands, and
keyword-specific lowerers consume those islands without rescanning outer TSL
or inventing backend code.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Adds a focused lowering module for `emit_return(...)` lexical-region
   lowering. Do not grow `outer_parser.py`, the old narrow `parser.py`,
   `lowerer.py`, or `generated_primitive_pipeline.py`.
2. Consumes M230 `SourceBodyLexicalScanResult` values or exact
   `SourceBodyLexicalRegionCandidate` values.
   - M230 should expose or be adjusted to expose a stable symbolic keyword
     identity such as `SourceBodyKeyword.EMIT_RETURN`, alongside the lexical
     descriptor that owns the source spelling `emit_return`.
   - The M231 lowerer must branch on that symbolic identity, not by comparing
     the raw spelling string again.
3. Produces typed frozen slotted dataclasses for:
   - lowered `emit_return` facts/directives;
   - raw/opaque surrounding items;
   - preserved source spans, source order, and provenance;
   - diagnostics for unsupported or malformed lowering inputs.
4. Accepts only M230 regions whose keyword identity is the return keyword,
   with no selector and no braced body, and with a balanced parenthesized
   payload span supplied by M230. The source spelling remains owned by the
   M230 lexical descriptor, so a future spelling change is localized there.
5. Preserves the payload text exactly as a raw source span. Do not parse,
   evaluate, normalize, repair, or recursively lower that payload here.
6. Leaves nested payload text such as `intrin_compose<...>(...)`,
   `call<...>(...)`, `cast<...>(...)`, raw operators, assignments, or helper
   calls as raw payload text for future lowerers.
7. Preserves deterministic source order across raw segments, lowered return
   facts, and non-return lexical regions.
8. If the M230 scan result contains diagnostics, emits/propagates a diagnostic
   and returns no lowered `emit_return` facts from that malformed scan result.
9. Covers representative inline and multiline real `.tsl` bodies, including:
   - scalar inline `tsil "emit_return(left + right);"`;
   - multiline `emit_return(intrin_compose<...>(...));`;
   - `emit_return(call<primitive=...>(...));`;
   - raw target-language-looking payloads such as `emit_return(*ptr);`.
10. Adds focused negative tests for malformed M230 scan results, non-return
    regions, and no source repair.

## Out Of Scope

- Payload semantic lowering.
- Recursive lowering of nested payload regions.
- `intrin_compose`, `intrin`, `call`, `if`, `else`, `loop`, `switch`,
  `value`, `type`, `cast`, `mem`, `io`, operators, assignments, or expression
  semantics.
- Primitive-call resolution, intrinsic translation, branch evaluation, loop
  execution, backend translation, rendering, generated project writing, or
  real x86 fixture resumption.
- Outer TSL declaration parsing changes.
- Source repair, normalization, fallback guessing, or auto-completion.
- Runtime dependency on `frozen/`, `tslgenold`, `m228-spike`, or
  `m2285-sideways-parser-body-attempt.patch`.
- Growing `outer_parser.py`, `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py`.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks that only the `emit_return` envelope is
   lowered and payload semantics stay raw/deferred.
2. Evidence auditor: checks real `tsldata` inline and multiline return
   payload coverage and verifies keyword spelling is owned by the M230 lexical
   descriptor rather than duplicated in the lowerer.
3. Complexity reviewer: checks module-size guardrails and no accretion in
   parser/lowerer/generated pipeline modules.
4. Diagnostics reviewer: checks malformed M230 scan-result handling,
   unsupported-region diagnostics, source locations, and no source repair.

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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m231_emit_return_lexical_region_lowering.py
find tslgen -type d -name __pycache__ -print
```

If the expected M231 test file has a different final name, the executor may use
that path, but the final report must state the exact command actually run and
why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M231 result.
- Update `docs/redesign/design-decisions.md` only if implementation revises
  the accepted parser/body/lowering boundary.
- Update `docs/redesign/open-questions.md` if a lowering issue cannot be
  resolved from evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The likely next milestone after M231 is a payload-token lowerer that consumes
raw payload spans, not a backend/rendering or real-fixture milestone. Do not
start it in M231.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
