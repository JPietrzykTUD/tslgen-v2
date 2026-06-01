# M191 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M190 as accepted plus the ADR-055 backend/output correction.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
M190: Typed Backend Language And Translation Metadata Catalog
ADR-055: Backend Output Uses Typed Render Models, Profile Layouts, And After-Write Verification
```

Selected milestone:

```text
Milestone 191: Profile-Aware Generated Project Skeleton And Smoke Verification Boundary
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/requirements.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `tslgen/src/tslgen/io/artifacts.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/rendering/supplementary.py`
- `tslgen/src/tslgen/domain/machine_profiles.py`
- `tslgen/src/tslgen/pipeline/machine_profiles.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m189_machine_feature_profiles.py`
- `supplementary/buildsystem/machine_profiles.json`
- `supplementary/buildsystem/cpp/templates/CMakeLists.txt.in`
- `supplementary/buildsystem/rust/templates/Cargo.toml.in`

## Goal

Implement the first ADR-055 backend/output slice before more backend semantic
translation work. The slice should produce a run-level generated project tree
with C++ and Rust backend subprojects, profile-specific skeleton files,
manifest-aware writing, and an after-write smoke build verification boundary.

This milestone proves that generated artifacts can be written and build-tested
from typed render models before primitive bodies, backend type spellings,
intrinsics, source operations, or dependency closure are rendered.

## Scope

- Add a small typed profile-subset selection boundary over the M189 machine
  profile catalog:
  - omitted profile selection resolves to `scalar`;
  - explicit profile names resolve to a deterministic generated subset;
  - reserved `all` resolves to all known machine profiles in catalog order;
  - unknown or ambiguous profile names are diagnostics.
- Add typed backend project/profile render models containing only
  already-decided presentation values:
  - backend id;
  - project paths;
  - selected profile names;
  - allowed profile choices;
  - public entry point paths;
  - smoke test paths;
  - already-prepared profile/build metadata.
- Render a run-level generated project tree with this layout:

  ```text
  generated/
    cpp/
      CMakeLists.txt
      include/
        tsl.hpp
        profiles/
          scalar.hpp
          ...
      tests/
        smoke.cpp
    rust/
      Cargo.toml
      src/
        lib.rs
        profiles/
          scalar.rs
          ...
      tests/
        smoke.rs
  ```

- Update supplementary templates/static assets only as needed for the
  profile-aware skeleton.
- C++ must expose `cpp/include/tsl.hpp`; Rust must expose `rust/src/lib.rs`.
  Generated profile files may contain only compileable skeleton marker code.
- CMake must use a profile cache string such as `TSL_PROFILE` with declared
  allowed values, not a boolean profile option.
- Rust must select exactly one generated profile through features or `cfg`
  wiring. Omitted profile selection should generate and default to `scalar`;
  if an explicit subset omits `scalar`, the default active generated profile
  may be the first selected profile.
- Add a manifest-based writer mode to the existing artifact writer so stale
  generator-owned files can be removed without deleting unknown user files.
- Add an after-write build verifier boundary with an injectable command
  runner and command records.
- The verifier must verify each generated profile in the selected subset for
  each generated backend project. Tests may use the real scalar smoke path and
  injected command execution for multi-profile behavior.
- Preserve deterministic artifact ordering, manifest ordering, diagnostics,
  and verifier command ordering.

## Out Of Scope

- Primitive body rendering.
- Backend type, backend value, intrinsic, control, mask, source-operation, or
  primitive-call translation.
- Dependency closure and non-empty primitive topological rendering.
- Evaluating backend translation templates.
- Translating normalized machine features into final compiler-specific
  target-feature option spellings.
- Full CMake/Cargo production packaging beyond the smoke skeleton.
- C17.
- CLI integration.
- Broad generated test framework parity.
- Lowering changes.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- Do not execute the previous M191 type-spelling plan. Backend type spelling
  translation is deliberately deferred until the output skeleton and verifier
  boundary exist.
- Do not put semantic decisions into supplementary templates. Templates may
  format selected profile names, allowed profile lists, already-prepared build
  presentation fields, and skeleton code only.
- Do not pass catalog objects, lowering requests, raw TSIL, raw
  `type<backend>(...)`, or raw `value<backend>(...)` into render models.
- Do not make the artifact writer sort primitives, resolve profiles, evaluate
  templates, infer compiler options, or repair output content.
- Do not make the verifier repair generated files, select alternative
  profiles, infer host CPU support, or feed results back into rendering.
- Keep the implementation as a skeleton/output boundary. If target-feature
  compiler option spelling becomes necessary to keep the slice coherent, stop
  and create a focused follow-up prompt rather than broadening M191.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m191_generated_project_smoke_boundary.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify the slice follows ADR-055, keeps
   render models already-decided, keeps templates presentation-only, keeps
   writing and verification separate, and does not implement backend semantic
   translation.
2. Evidence auditor: verify profile behavior is grounded in
   `supplementary/buildsystem/machine_profiles.json` and M189 typed profile
   catalog behavior, and no `frozen/` or `tslgenold` runtime dependency is
   introduced.
3. Documentation auditor: verify roadmap, state, and redesign docs describe
   the accepted skeleton/output/verifier boundary and any diagnostic codes.
4. Validation auditor: verify exact validation results and workspace hygiene.

If review returns `Needs Revision`, make only focused fixes and re-run focused
review. If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next prompt instead of continuing implementation.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M191 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M191 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
