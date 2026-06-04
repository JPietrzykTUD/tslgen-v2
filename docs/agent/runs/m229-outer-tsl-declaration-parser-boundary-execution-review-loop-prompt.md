# M229 Outer TSL Declaration Parser Boundary Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M228.5 planning as accepted.

This prompt selects an implementation milestone. Use the executor-review loop
specified below. Keep the implementation focused on the outer TSL declaration
parser boundary that enables later lowering; do not resume the real x86
fixture in this milestone.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
Milestone 228.5: Outer TSL Declaration Foundation Planning
```

M228 remains stopped before implementation. The `m228-spike` branch and
`m2285-sideways-parser-body-attempt.patch` branch are evidence only. Do not
copy or cherry-pick them wholesale.

M228.5 selected a Lark-backed outer TSL declaration parser boundary as the
next executable foundation before TSIL body lowering and real x86 fixture work
resume.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/requirements.md`
- `frozen/tsl-gen/tsl_gen/tsl_data.lark`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/load_store/array.tsl`
- `tsldata/extensions/extension.tsl`
- `tsldata/detail/templates.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`

## Goal

Implement a focused parser/catalog-boundary foundation for outer TSL
declarations. The parser must understand source envelopes well enough to reach
real primitive implementation bodies later, while preserving each `tsil`
implementation payload as raw source text for a later body-token lowering
milestone.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Adds a focused Lark-backed outer TSL declaration parser boundary in new
   syntax modules and `syntax/grammar` assets rather than by growing
   `tslgen/src/tslgen/syntax/parser.py`.
2. Uses Lark for this parser. Do not implement a regex parser, hand-written
   parser, or alternative parser for M229. The executor must make the Lark
   runtime dependency and grammar package-data boundary explicit in the clean
   implementation. If that cannot be done in the same focused slice, stop and
   create the next prompt for the dependency/package boundary instead of
   adding hidden dependency behavior.
3. Produces typed parser-boundary values with source spans. Keep any parser
   dictionaries private to parser internals.
4. Represents parsed documents, top-level declarations, primitive headers,
   primitive attributes, known primitive child fields, generic preserved
   fields, nested `impls` selector entries, `requires` values, and
   implementation body envelopes as typed dataclasses. Use
   `@dataclass(frozen=True, slots=True)` following repo convention unless a
   concrete local exception is documented in the M229 result. Do not use raw
   dictionaries as the public parsed field model.
5. Treats the top-level `prim<...> name(...):` header as the primitive anchor,
   but accepts all primitive child fields below that header in any order.
   Preserve original source order only as provenance/diagnostic data; do not
   make `brief_description`, `operation`, `tests`, `generic_params`,
   `return_type`, `sImm_type`, or `impls` depend on a fixed sequence.
6. Recognizes top-level outer declarations observed in current data:
   `description`, `prim<...>`, `types:`, `flags:`, `template NAME:`,
   `extension NAME:`, `lane_set NAME:`, `language NAME:`, and
   `translation NAME:`.
7. Recognizes primitive body envelopes:
   inline `tsil "..."` and multiline `tsil """..."""`.
   Preserve quote form, payload text, payload span, and envelope source span.
8. Parses all current `tsldata/**/*.tsl` outer declarations in tests without
   misclassifying declaration-like text inside multiline metadata strings as
   real top-level declarations.
9. Adds an order-insensitivity parser test or fixture for primitive child
   fields below a `prim<...>` header.
10. Keeps existing M224/M225/M227 tests passing.

## Out Of Scope

- TSIL body-token lowering.
- `emit_return`, `intrin_compose`, `call<...>`, `if<...>`, `loop<...>`,
  `switch<...>`, `value<...>`, `type<...>`, `cast<...>`, `mem<...>`, or
  `io<...>` semantic parsing.
- Expression/operator parsing or target-language parsing.
- Source repair, normalization, fallback guessing, or auto-completion.
- Wildcard expansion, implementation selection, catalog semantic validation,
  dependency closure, backend translation, primitive rendering, generated
  project writing, build verification, all-profile generation, ARM/qemu, host
  detection, or compiler capability modeling.
- Runtime dependency on `frozen/`, `tslgenold`, `m228-spike`, or
  `m2285-sideways-parser-body-attempt.patch`.
- New fixture-specific regex fallback logic in `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py`.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Parser architecture reviewer: checks typed boundary, grammar/package-data
   ownership, spans, diagnostics, and no dictionary leakage past parser
   internals.
2. Corpus evidence auditor: checks `tsldata/**/*.tsl` coverage, top-level
   declaration counts, selected primitive examples, and multiline string
   handling.
3. Lowering-boundary reviewer: checks that TSIL payloads remain raw source
   envelopes and no body semantics slipped into the parser.
4. Complexity reviewer: checks module-size guardrails and no accretion in
   `parser.py`, `lowerer.py`, or `generated_primitive_pipeline.py`.

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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py
find tslgen -type d -name __pycache__ -print
```

If the expected M229 test file has a different final name, the executor may use
that path, but the final report must state the exact command actually run and
why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M229 result.
- Update `docs/redesign/design-decisions.md` only if implementation revises
  ADR-066.
- Update `docs/redesign/open-questions.md` if a dependency/package or parser
  boundary issue cannot be resolved from evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The likely next milestone is a shared source-body lexical-region boundary over
accepted raw `tsil` payload envelopes. Do not start it in M229.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
