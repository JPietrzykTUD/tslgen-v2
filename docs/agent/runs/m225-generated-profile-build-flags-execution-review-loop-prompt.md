# M225 Generated Profile Build Flags Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M224 as accepted.

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
Milestone 224: Parsed Tiny TSL To Generated Project
```

M224 proved that one tiny parsed scalar `.tsl` fixture can flow through parser,
catalog, selector, lowering, M222 primitive render plans, M217 templates, M223
composition, manifest-clean writing, and scalar C++/Rust build verification.

Before introducing real SIMD intrinsics, generated non-scalar profiles need
already-decided build feature presentation values. M189 already loads machine
profile flags and alternatives. M191 already renders profile-aware generated
projects, but the current CMake/Cargo skeleton does not yet apply target
feature flags to generated builds.

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
- `supplementary/buildsystem/machine_profiles.json`
- `supplementary/buildsystem/cpp/templates/generated_project_CMakeLists.txt.in`
- `supplementary/buildsystem/rust/templates/generated_project_Cargo.toml.in`
- `tslgen/src/tslgen/domain/generated_project.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/pipeline/generated_profiles.py`
- `tslgen/tests/test_m191_generated_project_smoke_boundary.py`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`

## Goal

Add the smallest typed build-flag presentation slice needed before real
intrinsic generation:

- selected generated profiles expose already-decided C++ target-feature flag
  presentation values;
- selected generated profiles expose already-decided Rust target-feature flag
  presentation values;
- generated CMake/Cargo artifacts consume those values without deciding
  feature semantics in templates;
- scalar remains a no-feature build;
- at least one non-scalar x86 profile, preferably `avx2`, is rendered and
  compile-verified with a tiny scalar/no-intrinsic generated project.

This milestone prepares M226 to add the first real intrinsic fixture by proving
that profile feature flags can reach the compiler cleanly.

## Scope

Add focused implementation and tests, likely touching:

```text
tslgen/src/tslgen/domain/generated_project.py
tslgen/src/tslgen/rendering/generated_project.py
supplementary/buildsystem/cpp/templates/generated_project_CMakeLists.txt.in
supplementary/buildsystem/rust/templates/generated_project_Cargo.toml.in
tslgen/tests/test_m225_generated_profile_build_flags.py
```

The implementation should:

- derive typed C++ and Rust build-feature presentation values from selected
  `BackendProfileRenderModel`/machine profile data before template rendering;
- keep alternative flag spelling handling explicit and deterministic;
- render scalar with no feature flags;
- render x86 profiles into C++ compile options in the generated CMake project;
- render x86 profiles into Rust `target-feature` cfg/flag plumbing only as an
  already-decided build presentation value;
- keep C++ and Rust behavior in parity where each backend has a documented
  way to pass target features;
- verify a tiny generated `scalar,avx2` profile set can configure/build/test
  for C++ and run Rust tests in the current dev container;
- leave ARM/NEON/SVE/qemu execution for later explicit cross-arch milestones.

If Rust target-feature plumbing requires a different build artifact, such as
`.cargo/config.toml`, add it as an explicit generated artifact with typed
render values. Do not hide the decision inside source templates.

## Guardrails

- Do not generate real SIMD intrinsic calls in M225.
- Do not parse or lower new `.tsl` forms.
- Do not broaden primitive rendering beyond the M224 tiny scalar/no-intrinsic
  fixture.
- Do not model compiler capability detection or host autodetection.
- Do not infer feature support from the current CPU; selected profile flags are
  user/generator input, and build failures are environment failures.
- Do not put feature semantics, profile selection, fallback decisions, or flag
  normalization into templates.
- Do not add qemu/aarch64/NEON/SVE verification yet.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.

## Expected Tests

Add focused tests for:

- scalar profile renders no target-feature build flags;
- `avx2` profile renders deterministic C++ and Rust target-feature build
  values, including accepted alternative spellings if relevant;
- generated CMake/Cargo artifacts contain only already-decided presentation
  values;
- a tiny generated `scalar,avx2` project writes through manifest-clean mode and
  verifies C++/Rust builds/tests;
- duplicate/unknown profile behavior from M191 remains unchanged;
- public imports if new typed render values are exposed.

Do not add all-profile matrices, real intrinsic source, ARM/qemu tests, or
hardware autodetection tests in M225.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m225_generated_profile_build_flags.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: target-feature presentation is decided
   before templates; templates do formatting only; verifier remains after-write.
2. Evidence reviewer: build flag values derive from M189 machine profile data
   and accepted alternatives, not host autodetection or `frozen/`.
3. Test reviewer: scalar/no-feature and `avx2` feature rendering, deterministic
   artifacts, manifest-clean writing, and build verification are covered.
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
  or clarifies build-flag presentation behavior;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M226.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
