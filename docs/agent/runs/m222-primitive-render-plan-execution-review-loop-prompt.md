# M222 Primitive Render Plan Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M221 as accepted.

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
Milestone 221: C++/Rust Backend Type/Value Body Token Substitution Parity
```

M217 established primitive templates. M218 established typed primitive render
model values and adapters into those templates. M220 and M221 added body-token
substitution for already-rendered intrinsic and backend type/value islands.

M222 connects these pieces with a typed primitive render plan boundary. It
should collect already-decided render facts into ordered primitive records for
C++ and Rust, but it must not render/write/build a full generated project.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `tslgen/src/tslgen/rendering/primitive_render_model.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/tests/test_m218_typed_primitive_render_context.py`
- `tslgen/src/tslgen/backends/cpp/body_tokens.py`
- `tslgen/src/tslgen/backends/rust/body_tokens.py`

## Goal

Build a typed primitive render plan boundary for C++ and Rust that carries:

```text
backend/profile context
+ ordered selected primitive render records
+ already-rendered declaration/definition/body text
+ provenance
-> M218 primitive render model contexts
```

The render plan is an assembly boundary over already-decided values. It must
not decide primitive semantics, parse body text, execute dependency closure,
or render missing body-token islands.

## Scope

Add focused implementation and tests, likely:

```text
tslgen/src/tslgen/rendering/primitive_render_plan.py
tslgen/tests/test_m222_primitive_render_plan.py
```

The implementation should:

- define typed primitive render plan values for one backend/profile and an
  ordered tuple of primitive render records;
- keep C++ and Rust in parity;
- preserve the supplied primitive order as dependency/planning order, not as
  `PrimitiveRenderSortKey` presentation sorting;
- consume already-rendered declaration, definition, and body text values;
- consume backend id, profile name, artifact logical path, includes/imports,
  namespace/module text, and source/provenance values;
- adapt the plan into the M218 primitive render model and then into M217
  primitive template contexts;
- diagnose unsupported backend ids, wrong-backend records, duplicate plan
  identities if the chosen model has stable identities, unsupported raw
  TSIL/source sentinels, and unresolved semantic sentinel values;
- keep deterministic ordering in all returned tuples and diagnostics.

## Guardrails

- Do not reopen lowering or rescan raw TSIL.
- Do not run body-token substitution in M222.
- Do not translate source operations, intrinsics, type queries, value queries,
  signatures, or declarations in M222.
- Do not implement primitive dependency closure if no typed ordered input is
  supplied; preserve the order given to the plan boundary.
- Do not render a full generated project, write files, run CMake/Cargo, or
  compile generated output.
- Do not put semantic decisions into templates.
- Do not make `frozen/` or `tslgenold` runtime dependencies.

## Expected Tests

Add focused tests for:

- C++ and Rust primitive render plans adapting into M218 render contexts;
- preserving supplied primitive order independently from presentation sort key;
- preserving already-rendered declaration, definition, and body text;
- deterministic artifact/context order for multiple plans;
- diagnostics for unsupported backend ids;
- diagnostics for wrong-backend records or context fields;
- diagnostics for raw TSIL/source or unresolved semantic sentinel values;
- no skeleton-context reuse and no template-side semantics;
- public imports if new API is exposed.

Do not add generated project rendering, artifact writing, build verification,
compile tests, broad dependency closure, or new lowering in M222.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m222_primitive_render_plan.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: plan assembly consumes only already-decided
   values, preserves supplied order, and does not render/write/build.
2. Evidence reviewer: M217/M218 contracts are used correctly and M220/M221
   body-token output remains an input, not recomputed.
3. Test reviewer: coverage of C++/Rust parity, ordering, diagnostics,
   unresolved/raw sentinel rejection, and public imports.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md`, `docs/redesign/domain-model.md`,
  or `docs/redesign/design-decisions.md` if the accepted implementation adds
  or clarifies primitive render plan values or policy;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M223.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
