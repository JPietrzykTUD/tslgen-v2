# M254 Real Generic Unmasked Binary Arithmetic Body Lowering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M253 as accepted.

This is an implementation task. Use the executor-review loop:

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
Milestone 253: AVX512 Feature Option Spelling And Unmasked Binary Arithmetic Matrix Build Verification
```

M249-M253 proved real scalar, AVX2, SSE/SSE2, and AVX512 generated-project
paths through the generic selected primitive project pipeline. The next task
returns to lowering, per workflow direction. It should target a distinct real
TSIL source shape rather than another profile matrix.

## Goal

Prove or implement lowering for the real generic unmasked binary arithmetic
body shape used by `add` and `sub` in
`tsldata/primitives/arithmetic/fundamental.tsl`.

The relevant real body shape is:

```tsil
var<init_register>(result)
loop<unroll>(value<generation>(vector::length))
loop<range>(i, 0, value<generation>(vector::length), 1) {
  result[i] = call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left[i], right[i]);
}
emit_return(result);
```

## Scope

Implement the smallest coherent lowering slice:

- Load the real unmasked `add` and `sub` generic implementation bodies from
  `fundamental.tsl`.
- Use the accepted recursive TSIL lexical/token lowering boundary, not a
  parent-child special case such as `loop + call`, `loop + emit_return`,
  `assignment + call`, or `emit_return + call`.
- Recognize/lower lowerable islands in the real generic body:
  - `var<init_register>(result)`;
  - `loop<unroll>(value<generation>(vector::length))`;
  - `loop<range>(i, 0, value<generation>(vector::length), 1) { ... }`;
  - nested `call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(...)`;
  - nested `type<backend>(vector::as_extension(scalar))`;
  - `emit_return(result);`.
- Preserve concrete source spans and deterministic token order.
- Preserve non-lowerable assignment/indexing punctuation such as
  `result[i] = `, `left[i]`, and `right[i]` as source-owned raw tokens unless
  an accepted existing lowerer already owns an exact typed fragment for them.
- Produce typed lowering facts, typed unresolved requests, or explicit
  diagnostics from existing lowering contracts.
- If the existing lowering stack already supports this real body shape, add
  tests/docs only. If implementation is needed, keep it in the shared recursive
  token/lowering path.

## Non-Negotiable Guardrails

- No backend rendering or generated-project build verification in M254.
- No primitive-call dependency closure.
- No semantic resolution of `@self`.
- No broad assignment or array expression parser.
- No target-language operator parser.
- No source repair, normalization, or guessing.
- No pairwise surrounding-keyword special cases.
- No fixture sibling pipeline or primitive-specific module.
- No template-side semantic decisions.
- No runtime dependency on `frozen` or `tslgenold`.
- Do not solve masks, SVE/NEON, backend source-operation rendering, or generic
  loop code generation in this milestone.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m254_real_generic_unmasked_binary_arithmetic_body_lowering.py
```

Cover:

- Real `add` and `sub` generic unmasked bodies are loaded from
  `tsldata/primitives/arithmetic/fundamental.tsl`, not inline fixtures.
- Lowering uses the recursive token/region path and not pairwise combination
  adapters.
- The lowerer recognizes the real `var<init_register>`, `loop<unroll>`,
  `loop<range>`, nested `value<generation>(vector::length)`, nested
  `call<primitive=...>`, nested `type<backend>(...)`, and
  `emit_return(result);` islands.
- Raw source text around lowerable islands is preserved for non-lowerable
  assignment/indexing punctuation.
- Diagnostics remain explicit for unsupported semantic resolution such as
  dependency closure or unresolved `@self`, rather than silently rendering or
  repairing the body.
- Guardrails reject fixture-shaped modules, pairwise keyword-combination paths,
  exact raw source-string matchers, and runtime `frozen`/`tslgenold`
  dependencies.

## Out Of Scope

Backend rendering/build verification; primitive-call expansion; dependency
closure; semantic `@self` target resolution; full generic loop code
generation; broad body expression parsing; broad assignment/indexed expression
parsing; source repair; masks; SVE/NEON; target-language operator parsing;
template rendering; CLI workflow; runtime dependencies on `frozen` or
`tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m231_emit_return_lexical_region_lowering.py tslgen/tests/test_m232_return_payload_region_rescan_adapter.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py tslgen/tests/test_m235_primitive_call_fragment_adapter_consolidation.py tslgen/tests/test_m236_recursive_payload_fragment_diagnostic_propagation.py tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py tslgen/tests/test_m254_real_generic_unmasked_binary_arithmetic_body_lowering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: lowering-only scope; recursive token path;
   no pairwise keyword special case, backend rendering, dependency closure,
   source repair, or fixture pipeline.
2. Evidence reviewer: selected generic bodies are real `tsldata`; lowerable
   islands and raw spans match the corpus; no hidden reliance on `frozen` or
   `tslgenold`.
3. Test reviewer: real corpus coverage, recursive/nested lowering behavior,
   raw-span preservation, diagnostics, regressions, and guardrails.
4. Documentation reviewer: roadmap/state/spec/decision consistency and next
   prompt accuracy.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M255 inside M254.

## Final Report

Report:

1. Implementation summary.
2. Whether the real generic body needed production lowering changes.
3. Which lowerable islands are recognized and which text remains raw.
4. How recursive lowering avoids pairwise keyword-combination paths.
5. Review/audit verdicts.
6. Validation commands and exact results.
7. Any follow-ups.
8. Next active prompt path.
