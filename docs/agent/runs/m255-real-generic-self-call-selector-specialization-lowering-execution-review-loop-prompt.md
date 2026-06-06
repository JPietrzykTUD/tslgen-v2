# M255 Real Generic Self-Call Selector Specialization Lowering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M254 as accepted.

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
Milestone 254: Real Generic Unmasked Binary Arithmetic Body Lowering
```

M254 proved the real generic unmasked `add`/`sub` body shape through the
shared recursive source-body keyword boundary. It recognizes exact
`var<init_register>`, `loop<unroll>`, `loop<range>`, nested
`value<generation>`, nested `call<primitive=...>`, nested `type<backend>`,
and `emit_return` islands while preserving assignment/index text as raw
source-owned fragments.

## Goal

Lower the real generic body's nested
`call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left[i], right[i])`
selector payload into accepted typed primitive-call selector facts. The
`@self` target remains unresolved; dependency closure and backend rendering
remain out of scope.

## Scope

Implement the smallest coherent lowering slice:

- Load the real unmasked `add` and `sub` generic implementation bodies from
  `tsldata/primitives/arithmetic/fundamental.tsl`.
- Reuse the M254 recursive fragment path to extract the nested primitive-call
  directive. Do not add an exact raw source-string matcher for the call.
- For representative concrete selected contexts, lower the selector
  specialization `type<backend>(vector::as_extension(scalar))` through the
  accepted primitive-call selector/type lowering boundary.
- Assert the lowered selector target remains an unresolved typed
  `SelfPrimitiveReference`.
- Assert the lowered specialization is typed and concrete relative to the
  selected context; it must not remain only raw selector text at the point this
  milestone accepts it.
- Preserve indexed argument text as raw argument facts: `left[i]` and
  `right[i]` are not parsed as index expressions.
- If existing lowering already supports this path, add tests/docs only. If
  implementation is needed, keep changes in the shared selector/type lowering
  path.

## Non-Negotiable Guardrails

- No semantic `@self` resolution.
- No primitive-call dependency closure.
- No backend rendering or generated-project build verification.
- No generic loop code generation.
- No assignment/index expression parser.
- No target-language operator parser.
- No source repair, normalization, or guessing.
- No pairwise surrounding-keyword special cases such as `loop + call`.
- No fixture sibling pipeline or primitive-specific module.
- No template-side semantic decisions.
- No runtime dependency on `frozen` or `tslgenold`.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m255_real_generic_self_call_selector_specialization_lowering.py
```

Cover:

- Real `add` and `sub` generic unmasked bodies are loaded from
  `fundamental.tsl`, not inline fixtures.
- The call directive is obtained from the accepted recursive fragment path and
  shared primitive-call adapter.
- The selector target is `@self` as a typed unresolved reference.
- The selector specialization
  `type<backend>(vector::as_extension(scalar))` lowers through existing
  selector/type lowering into typed facts for representative concrete selected
  contexts.
- Indexed arguments remain raw argument text.
- Diagnostics remain explicit for unsupported semantic resolution such as
  dependency closure or unresolved `@self`; no backend rendering or source
  repair is attempted.
- Guardrails reject pairwise keyword-combination paths, exact source-string
  matchers, fixture-shaped modules, template-side semantic decisions, and
  runtime `frozen`/`tslgenold` dependencies.

## Out Of Scope

Backend rendering/build verification; primitive-call dependency closure;
semantic `@self` target resolution; generic loop code generation; assignment
or indexed-expression parsing; source repair; masks; SVE/NEON; target-language
operator parsing; template rendering; CLI workflow; runtime dependencies on
`frozen` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m179_backend_type_queries.py tslgen/tests/test_m180_backend_type_query_handoff.py tslgen/tests/test_m235_primitive_call_fragment_adapter_consolidation.py tslgen/tests/test_m254_real_generic_unmasked_binary_arithmetic_body_lowering.py tslgen/tests/test_m255_real_generic_self_call_selector_specialization_lowering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: lowering-only scope; shared
   selector/type path; no dependency closure, backend rendering, pairwise
   keyword special case, source repair, assignment/index parser, or fixture
   pipeline.
2. Evidence reviewer: selected call comes from real `tsldata`; typed selector
   facts match the real generic body and selected concrete contexts; no hidden
   reliance on `frozen` or `tslgenold`.
3. Test reviewer: real corpus coverage, typed selector-specialization
   assertions, raw indexed-argument preservation, diagnostics, and guardrails.
4. Documentation reviewer: roadmap/state/spec/decision consistency and next
   prompt accuracy.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M256 inside M255.

## Final Report

Report:

1. Implementation summary.
2. Whether the real generic self-call selector path needed production lowering
   changes.
3. Which typed selector/specialization facts are produced and which argument
   text remains raw.
4. How the milestone avoids dependency closure, backend rendering, and
   pairwise keyword paths.
5. Review/audit verdicts.
6. Validation commands and exact results.
7. Any follow-ups.
8. Next active prompt path.
