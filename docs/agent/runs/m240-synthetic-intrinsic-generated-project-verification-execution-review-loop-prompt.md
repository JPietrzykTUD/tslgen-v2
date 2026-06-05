# M240 Synthetic Intrinsic Generated-Project Verification Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M239 as accepted.

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
Milestone 239: Backend Intrinsic Body-Token Render Bridge
```

M239 proved that synthetic already-lowered typed backend intrinsic handoff
values can render C++ and Rust primitive profile artifacts through accepted
intrinsic invocation/call rendering, body-token substitution, exact
`v:=(v,v)` function-shape templates, and primitive profile templates.

Do not reopen lowering in M240. The point is to verify that the M239 primitive
profile artifacts fit into the accepted generated-project/write/verify path.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/agent/runs/m239-backend-intrinsic-body-token-render-bridge-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/rendering/intrinsic_body_token_bridge.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`
- `tslgen/tests/test_m238_generated_project_source_template_boundary.py`
- `tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py`
- `supplementary/buildsystem/machine_profiles.json`
- `supplementary/buildsystem/cpp/templates/`
- `supplementary/buildsystem/rust/templates/`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Implement the smallest verification slice proving this path works end to end:

```text
synthetic already-lowered typed intrinsic handoff
-> M239 primitive profile artifacts
-> generated-project skeleton artifacts
-> selected-profile primitive replacement
-> ArtifactWriter
-> BuildVerifier
```

This is still not the real corpus path. It is a build-verification bridge over
explicit typed fixture values.

## Scope

Add focused tests, and only minimal production helper code if existing
boundaries cannot express the slice cleanly, that prove:

- a synthetic C++ intrinsic primitive profile artifact for an explicit selected
  profile can be composed into the generated C++ project;
- the Rust parity artifact can be composed into the generated Rust project;
- the composed artifacts are written through `ArtifactWriter` to a temporary
  output directory;
- the existing build verifier runs every selected profile for both backends;
- the selected profile uses existing machine-profile build flags;
- artifact output and verification command ordering are deterministic.

Use an explicit profile whose existing build flags make the synthetic
intrinsic compile. A narrow x86 `sse2` fixture using `_mm_add_epi32` is the
preferred candidate because it exercises real intrinsic compilation without
real `tsldata` primitive selection.

If the real toolchain in this environment cannot compile the selected
synthetic intrinsic, treat that as a verifier/environment diagnostic and
record the exact failure. Do not add compiler capability modeling, host CPU
autodetection, or fallback selection.

## Guardrails

- Do not change lowering, recursive TSIL keyword handling, primitive-call
  semantics, parser/catalog/selector code, or source-body scanning.
- Do not implement full `fundamental.tsl`/`add`/`avx2` corpus selection.
- Do not implement dependency closure or topological primitive planning.
- Do not add new intrinsic, type, value, source-operation, or feature
  semantics.
- Do not add C++/Rust source skeleton strings to Python.
- Do not hide intrinsic/type/feature semantics in templates.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not grow `tslgen.rendering.intrinsic_body_token_bridge` into a broad
  backend/output orchestrator. If a helper is needed for write/verify
  composition, keep it in a focused pipeline/output boundary or test fixture.
- Do not add runtime dependencies on `frozen/` or `tslgenold`.
- Keep C++ and Rust in parity.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py
```

Cover:

- M239 C++ and Rust synthetic intrinsic profile artifacts compose into the
  generated project for the selected profile.
- Written generated output verifies for both C++ and Rust with the existing
  build verifier.
- The selected profile's existing C++ target options and Rust target features
  are present in the generated buildsystem artifacts or verifier commands.
- Repeated render/compose/write/verify planning produces deterministic
  artifact manifests and command ordering.
- The test constructs typed handoff fixtures directly and does not parse
  `.tsl`, call `Lowerer`, run selection over real primitives, or inspect
  `frozen/`/`tslgenold`.
- Existing M225/M238/M239 tests continue to pass.

## Out Of Scope

- Full source/corpus path from `tsldata/primitives/arithmetic/fundamental.tsl`.
- Wildcard type expansion or selected primitive context construction.
- Dependency closure/topological primitive planning.
- Vector/register type spelling expansion beyond already-provided render
  values.
- Rust architecture module selection beyond existing renderer inputs.
- New supplementary generated-project templates.
- New CLI/API generation command.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m238_generated_project_source_template_boundary.py tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: M240 uses typed M239 artifacts and accepted
   generated-project/write/verify boundaries; it does not reopen lowering,
   parser/catalog/selection, or template-side semantics.
2. Evidence reviewer: M240 stays synthetic and does not implement the full
   real x86 corpus fixture; existing M225/M238/M239 behavior remains
   compatible.
3. Test reviewer: C++/Rust parity, selected-profile build flags, write/verify
   coverage, deterministic artifacts/commands, and no source/lowering access
   are covered.
4. Documentation reviewer: roadmap/state/design-doc consistency and follow-ups
   are accurate.
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
- do not start the next milestone inside M240.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
