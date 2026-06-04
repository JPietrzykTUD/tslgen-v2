# M228 Restarted First Real X86 Intrinsic Fixture Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M225, M226.5, and M227 as accepted.

This is an implementation task with a mandatory preflight gate. Use the
executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if `Needs Revision`
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
```

The first M228 attempt was moved to the `m228-spike` branch as evidence. Do
not copy or cherry-pick it wholesale. Use it only to understand the failure
mode: parser/catalog/lowering/rendering changes were bundled, and already
large modules grew through exact regex additions and raw-body fallbacks.

ADR-064 is accepted: outer `.tsl` declaration structure belongs behind a
focused parser boundary, while TSIL implementation payloads remain source-owned
raw spans plus accepted lowerable token islands.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/flaws-to-fix.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/agent/runs/m226-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `docs/agent/runs/m2265-signature-shape-template-render-model-cleanup-planning-prompt.md`
- `docs/agent/runs/m227-vv-function-shape-template-render-boundary-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/tsl-gen/tsl_gen/tsl_data.lark`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/primitive_function_shapes.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/backends/*intrinsic*`
- `tslgen/src/tslgen/backends/*body_tokens*`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`
- `tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py`

You may inspect `m228-spike` only as negative/evidence material. Do not make it
a runtime dependency and do not copy broad code from it.

## Goal

Implement the smallest maintainable first real observed x86 non-scalar
intrinsic fixture for both C++ and Rust, without repeating the M228 spike.

The preferred fixture is:

```text
tsldata/primitives/arithmetic/fundamental.tsl
prim<v:=(v,v)> add(left, right)
impls -> avx2 -> ?i?
tsil multiline emit_return(intrin_compose<add, suffix=...>(left, right));
```

The selected implementation must use the concrete selected target type in the
lowering/render context. Wildcard selectors such as `?i?` are selection
patterns, not backend suffix/type text.

## Mandatory Preflight Gate

Before editing implementation code, write down the selected strategy in the
work notes and then follow it.

1. Inspect the current line counts and responsibilities of:

```text
tslgen/src/tslgen/syntax/parser.py
tslgen/src/tslgen/lowering/lowerer.py
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
```

2. Decide the outer `.tsl` declaration parser strategy.

Prefer a grammar parser such as Lark if it can parse the required outer TSL
declaration structure with spans and clearer module ownership. The legacy
`frozen/tsl-gen/tsl_gen/tsl_data.lark` is evidence, not architecture. Another
parser or a very small existing-parser extension is acceptable only if the
decision is simpler, tested, and does not continue regex accretion in a large
module.

The parser strategy must cover only outer declaration structure needed for the
fixture:

- primitive header and attributes;
- optional `return_type`;
- optional `generic_params`;
- nested `impls` extension/type selector blocks;
- `requires` in inline and block forms;
- `implementation:` with `tsil "..."` and `tsil """..."""` body payloads.

The parser strategy must not parse TSIL semantics inside the payload.

3. Decide the body-token strategy.

Multiline keyword support belongs in a focused source-body lexical boundary,
not in one `emit_return(...)` special case. Multiple TSIL keywords can carry
balanced single-line or multiline payloads/body regions, so the strategy should
reuse or extend the existing lexical-only helper pattern in
`tslgen/src/tslgen/syntax/tsil_lexical.py` where it fits.

The shared body boundary may know about raw spans, source locations, balanced
parentheses, angle brackets, square brackets, braces, and top-level separators.
It must not know TSIL keyword semantics, generation evaluation, backend
translation, or source repair. Keyword-specific lowerers consume the lexical
regions and decide whether their exact accepted source forms apply.

For M228, this shared lexical boundary only needs enough coverage to expose
the selected multiline `emit_return(PAYLOAD);` region and the nested
`intrin_compose<...>(...)` island needed by the fixture. It should be designed
so later `if<...>`, `switch<...>`, `loop<...>`, `var<...>`, `let<...>`,
`call<...>`, `mem<...>`, `io<...>`, and `cast<...>` lowerers can use the same
lexical region mechanics when their semantics are selected. Do not bury this
as an ad hoc raw-text fallback in `Lowerer`.

4. Decide the render bridge strategy.

Any exact intrinsic fixture adapter in
`tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py` must stay small.
If the bridge needs substantial backend-specific intrinsic rendering logic,
factor it into a focused backend/output module that consumes already-decided
typed lowering and translation values.

If the preflight shows that parser replacement, body segmentation, or render
bridge factoring is too large to implement safely together with the exact
fixture, stop implementation and create the next prompt as a parser/body
boundary milestone. Do not force the fixture through by growing
`parser.py`, `lowerer.py`, or `generated_primitive_pipeline.py`.

## Scope

Implement only the exact support required by the selected fixture after the
preflight gate passes.

Expected areas, depending on the preflight decision:

```text
tslgen/src/tslgen/syntax/...
tslgen/src/tslgen/pipeline/catalog_builder.py
tslgen/src/tslgen/lowering/...
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
tslgen/tests/test_m228_first_real_x86_intrinsic_fixture.py
```

The implementation should:

- preserve M224/M225 scalar behavior;
- keep C++ and Rust in parity;
- parse enough real outer `.tsl` declaration structure to select the observed
  `add`/`avx2`/concrete integer implementation from source evidence;
- preserve implementation payloads as source-owned body text until the focused
  shared lexical body-token boundary identifies accepted lowerable islands;
- lower the selected multiline `emit_return(...)` region through the shared
  lexical boundary without parsing general target-language statements;
- lower the selected `intrin_compose<add, suffix=...>(left, right)` island
  through existing typed intrinsic handoff/modifier/invocation boundaries where
  possible;
- render function shape through the M227 supplementary templates;
- write selected `scalar,avx2` profile artifacts through the selected-profile
  replacement policy;
- compile/test generated C++ and Rust `scalar,avx2` projects;
- keep raw accepted lowerable token text such as `intrin_compose<...>` and
  `value<backend>(...)` out of generated bodies.

## Guardrails

- Do not implement broad TSIL parsing.
- Do not add a general expression parser, statement parser, source repair path,
  or target-language parser.
- Do not broaden to all `intrin_compose`, `intrin`, `call`, `if`, `loop`,
  `mem`, `io`, `cast`, or all primitive bodies.
- Do not hardcode C++/Rust backend source snippets in Python.
- Do not put semantic decisions into templates.
- Do not add dependency closure, all-profile generation, ARM/NEON/SVE/qemu,
  host autodetection, or compiler capability modeling.
- Do not treat selector wildcard text such as `?i?` as a concrete type.
- Do not grow already-large modules with unrelated responsibilities; split
  focused parser/body/render helpers when the module-size guardrail applies.
- Do not use `frozen/`, `tslgenold/`, `new_chat_test`, or `m228-spike` as
  runtime dependencies.

## Expected Tests

Add focused tests for:

- parser preflight behavior, including the chosen parser strategy and source
  spans for the observed `impls -> avx2 -> ?i? -> implementation` shape;
- evidence that the selected observed fixture still exists in
  `tsldata/primitives/arithmetic/fundamental.tsl`;
- concrete selection from wildcard implementation selector to a concrete
  target type, proving the context carries the selected concrete type;
- shared lexical body-region behavior for balanced single-line and multiline
  TSIL keyword islands, with raw spans preserved and keyword semantics kept in
  keyword-specific lowerers;
- selected multiline `emit_return(PAYLOAD);` extraction through that lexical
  boundary, with only the accepted payload island lowered;
- C++ and Rust rendered `avx2` profile artifacts containing the real intrinsic
  call and no raw accepted lowerable token text;
- unsupported nearby forms producing diagnostics instead of source repair;
- deterministic artifact digests across repeated runs;
- generated `scalar,avx2` projects written through manifest-clean mode and
  build-verified;
- M224/M225/M227 tests still passing.

If implementation stops at the preflight gate, create a parser/body-boundary
prompt and run only the validation appropriate for the docs-only transition.

## Required Validation

For an implementation result, run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m228_first_real_x86_intrinsic_fixture.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

For a preflight stop with docs/prompt updates only, run:

```bash
git diff --check
```

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: verifies declaration parsing, shared
   lexical body-region segmentation, keyword-specific lowering, backend
   translation, rendering, writing, and verification stay separate.
2. Parser reviewer: verifies the chosen parser strategy is maintainable,
   source-spanned, and not TSIL parsing in disguise.
3. Evidence reviewer: verifies the selected fixture is real observed `tsldata`
   input and no runtime dependency on `frozen/`, `tslgenold`, `new_chat_test`,
   or `m228-spike` exists.
4. Test reviewer: exact fixture coverage, unsupported-form diagnostics,
   C++/Rust parity, deterministic output, manifest-clean writing, and build
   verification are covered.
5. Documentation reviewer: roadmap/state/design-doc consistency.
6. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution or
  preflight-stop result;
- update redesign docs if behavior, architecture, or parser choice changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M229.

## Final Report

Report:

1. Preflight parser/body/render strategy.
2. Implementation summary or preflight stop reason.
3. Review/audit verdicts if implementation ran.
4. Validation commands and exact results.
5. Any follow-ups.
6. Next active prompt path.
