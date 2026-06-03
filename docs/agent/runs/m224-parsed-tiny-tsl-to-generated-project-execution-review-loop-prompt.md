# M224 Parsed Tiny TSL To Generated Project Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M223 as accepted.

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
Milestone 223: First Real Generated Primitive
```

M223 proved that one already-decided C++ and Rust scalar primitive profile
artifact can be rendered through accepted primitive templates, composed with
the generated-project skeleton, written through the manifest-clean writer, and
verified by compiling/testing the generated scalar projects.

M224 should now prove that a tiny parsed `.tsl` source can feed that accepted
backend/output path. This answers the parsing concern without broadening into
full `tsldata` corpus generation.

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
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/tests/test_m223_first_real_generated_primitive.py`

## Goal

Add one tiny parser-to-generated-project vertical slice:

```text
SourceDocument
  -> TslParser
  -> CatalogBuilder
  -> Selector
  -> accepted lowering/render facts for one scalar primitive
  -> M222 PrimitiveRenderPlan
  -> M217 primitive templates
  -> M223 generated primitive project composition
  -> manifest-clean ArtifactWriter
  -> BuildVerifier
```

The fixture should be intentionally tiny, for example one scalar `add_one` or
identity-style primitive source that the current clean parser can parse. The
important contract is that the primitive/profile artifacts are no longer
hand-authored directly by the test; they are derived from a parsed source
fixture through accepted typed stages before reaching M222/M223.

## Scope

Add focused implementation and tests, likely:

```text
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py
```

The implementation should:

- use `SourceDocument`, `TslParser`, `CatalogBuilder`, and `Selector` for the
  tiny fixture;
- select explicit scalar C++ and Rust targets only;
- use the existing lowering result only for accepted exact source forms already
  supported by the clean parser/lowerer;
- adapt the accepted lowered/rendered facts into M222 `PrimitiveRenderPlan`
  values for C++ and Rust;
- keep C++ and Rust in parity for the same parsed primitive and selected scalar
  profile;
- route rendering through M217 primitive templates;
- route generated-project composition through M223;
- write artifacts through the manifest-clean writer in a temporary output
  root;
- verify scalar generated C++ and Rust projects through the existing
  after-write build verifier;
- preserve deterministic artifact ordering and digest manifests.

If the existing clean lowering/backend facts are not yet sufficient to derive
the tiny primitive body into already-rendered C++ and Rust declaration or
definition text, add the smallest typed bridge needed for this one accepted
source form. Keep the bridge explicit and typed. Do not use raw text matching
or direct backend emitters as a shortcut.

## Guardrails

- Do not use `tslgen.pipeline.generator.Generator` if it bypasses the accepted
  M217-M223 render/project path through older direct backend emitters.
- Do not generate from the full `tsldata` corpus.
- Do not broaden the parser beyond the exact tiny fixture source form selected
  for M224.
- Do not add new TSIL syntax, operator parsing, source repair, dependency
  closure, profile matrices, wrapper generation, generated test planning, or
  broad primitive selection.
- Do not hand-author final primitive profile artifacts in the test the way
  M223 did; the profile artifacts must come from the parsed source path.
- Do not hide type, body, intrinsic, helper, feature, or primitive-selection
  decisions in templates, renderers, the artifact writer, or the verifier.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.

## Expected Tests

Add focused tests for:

- parsing the tiny source fixture and building a catalog without diagnostics;
- selecting explicit scalar C++ and Rust targets from that catalog;
- proving the rendered primitive profile artifacts are derived from parsed
  source/catalog/selection/lowering facts, not hand-authored artifact text;
- composing those profile artifacts with the generated-project skeleton through
  M223;
- manifest-clean writing and real scalar C++/Rust build verification;
- deterministic artifact digest manifests across two identical runs;
- diagnostics if the tiny fixture cannot be parsed, selected, lowered, or
  adapted into render plans;
- public imports if a new pipeline API is exposed.

Do not add broad corpus tests, dependency-closure tests, all-profile tests, or
legacy parity golden files in M224.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: parser/catalog/selection/lowering feed the
   accepted render-plan/project path; direct backend emitters and template-side
   semantics are not used as shortcuts.
2. Evidence reviewer: the tiny source fixture uses only source forms already
   accepted by the clean parser/catalog/lowerer, and M217-M223 contracts are
   preserved.
3. Test reviewer: coverage proves the parsed source path, C++/Rust parity,
   deterministic artifacts, manifest-clean writing, and build verification.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md`, `docs/redesign/domain-model.md`,
  or `docs/redesign/design-decisions.md` if the accepted implementation adds
  or clarifies the parsed-source-to-render-plan bridge;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M225.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
