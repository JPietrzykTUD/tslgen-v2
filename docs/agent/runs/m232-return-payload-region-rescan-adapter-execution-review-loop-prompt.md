# M232 Return Payload Region Rescan Adapter Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M231 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. Keep the implementation focused on a
thin adapter over the already-accepted M230 source-body lexical scanner for
already-lowered `emit_return(...)` payload spans. Do not lower payload
semantics in this milestone.

## Accepted State

Accepted through:

```text
Milestone 229: Outer TSL Declaration Parser Boundary
Milestone 230: Source Body Lexical Region Boundary
Milestone 231: Emit Return Lexical Region Lowering
```

M229 parses outer `.tsl` declarations and preserves raw `tsil` body payload
envelopes. M230 discovers balanced lexical source-body regions for configured
keyword heads and exposes symbolic keyword identities plus spelling-owned
descriptors. M231 consumes M230 scan results and lowers only symbolic
`emit_return` regions into typed return directives with raw source-mapped
payload spans.

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
- `tslgen/src/tslgen/lowering/emit_return_regions.py`
- `tslgen/tests/test_m230_source_body_lexical_region_boundary.py`
- `tslgen/tests/test_m231_emit_return_lexical_region_lowering.py`
- Representative source evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/primitives/conversion/cast.tsl`
  - `tsldata/primitives/load_store/load.tsl`

## Goal

Add a narrow return-payload region rescan adapter that consumes M231
`LoweredEmitReturnDirective` payload spans, runs the already-accepted M230
scanner over that span, and wraps the resulting M230 raw segments and lexical
region candidates with return-directive provenance.

This is not a new payload parser, token language, expression model, or TSIL
AST. It proves only that future payload-specific lowerers can share one
source-mapped rescan result instead of each lowerer rescanning raw strings in
its own way.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Adds a focused lowering module or a focused extension to the M231 module
   for return-payload region rescanning. Do not grow `outer_parser.py`, the
   old narrow `parser.py`, `lowerer.py`, or
   `generated_primitive_pipeline.py`.
2. Consumes accepted M231 `LoweredEmitReturnDirective` values and their
   `payload_span`.
3. Reuses the M230 `SourceBodyLexicalRegionScanner` or
   `scan_source_body_text(SourceBodyText.from_span(...))` boundary for nested
   lexical discovery. Do not duplicate delimiter matching or keyword spelling
   checks.
4. Produces only thin typed frozen slotted adapter dataclasses for:
   - the return-payload rescan result;
   - M230 raw segment wrappers with return-directive provenance;
   - M230 lexical-region wrappers with return-directive provenance;
   - diagnostics propagated from the M230 rescan.
   Do not introduce a broader payload-token taxonomy.
5. Preserves payload raw text exactly. Raw text between nested region islands
   must remain raw and source-mapped.
6. Keeps nested region candidates lexical only. `intrin_compose<...>(...)`,
   `call<...>(...)`, `cast<...>(...)`, `value<...>(...)`, `type<...>(...)`,
   operators, helper calls, and assignments must not be semantically lowered
   here.
7. Handles payloads with no nested configured regions by returning the M230
   raw segment wrapper(s) and no diagnostics.
8. If nested payload scanning reports diagnostics, propagate those diagnostics
   and do not emit semantic payload-region facts from the malformed nested
   scan. Do not repair, normalize, or guess source intent.
9. Covers representative real `.tsl` payloads from M231:
   - `left + right` remains M230 raw text wrapped with return provenance;
   - multiline `intrin_compose<...>(...)` remains an M230 lexical-region
     candidate wrapped with return provenance, with surrounding whitespace as
     M230 raw segments;
   - `call<primitive=...>(...)` remains an M230 lexical-region candidate
     wrapped with return provenance;
   - `*ptr` remains M230 raw text wrapped with return provenance.
10. Adds focused negative tests for malformed nested regions and no source
    repair.

## Out Of Scope

- Payload semantic lowering.
- `intrin_compose`, `intrin`, `call`, `if`, `else`, `loop`, `switch`,
  `value`, `type`, `cast`, `mem`, `io`, operators, assignments, or expression
  semantics.
- Primitive-call resolution, intrinsic translation, branch evaluation, loop
  execution, backend translation, rendering, generated project writing, or
  real x86 fixture resumption.
- Outer TSL declaration parsing changes.
- Source repair, normalization, fallback guessing, or auto-completion.
- A new payload parser, generic payload token language, expression tree,
  precedence model, or recursive semantic lowering dispatcher.
- Runtime dependency on `frozen/`, `tslgenold`, `m228-spike`, or
  `m2285-sideways-parser-body-attempt.patch`.
- Growing `outer_parser.py`, `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py`.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks that M232 only wraps an M230 rescan of
   return payload spans and does not lower nested payload semantics.
2. Evidence auditor: checks real `tsldata` coverage for raw-only, call, and
   multiline intrinsic-compose payloads.
3. Complexity reviewer: checks module-size guardrails, scanner reuse, no new
   payload-token taxonomy, and no parser/lowerer/generated-pipeline accretion.
4. Diagnostics reviewer: checks malformed nested-scan handling, source
   locations, and no source repair.

Use `docs/agent/review-checklist.md`. If review returns `Needs Revision`, run
one focused revision executor and re-review only the blocking findings. If
review returns `Return To Planner` or `Reject`, stop implementation and create
the appropriate planner/rollback prompt instead of continuing.

The orchestrator owns final verdict consolidation, state update, and next
prompt creation.

## Required Validation

Run exactly:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m231_emit_return_lexical_region_lowering.py tslgen/tests/test_m232_return_payload_region_rescan_adapter.py
find tslgen -type d -name __pycache__ -print
```

If the expected M232 test file has a different final name, the executor may
use that path, but the final report must state the exact command actually run
and why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M232 result.
- Update `docs/redesign/design-decisions.md` only if implementation revises
  the accepted parser/body/lowering boundary.
- Update `docs/redesign/open-questions.md` if a lowering issue cannot be
  resolved from evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The likely next milestone after M232 is a semantic lowerer for one already
recognized nested region family, selected from the wrapped M230 rescan result.
Do not start it in M232.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
