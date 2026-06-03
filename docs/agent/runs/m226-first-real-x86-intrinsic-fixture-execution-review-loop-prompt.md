# M226 First Real X86 Intrinsic Fixture Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M225 as accepted.

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
Milestone 225: Generated Profile Build Flags
```

M224 proved the parsed tiny scalar `.tsl` to generated-project path. M225 made
selected profile target-feature flags reach generated C++ and Rust build
verification as already-decided presentation values. The next useful slice is
one real non-scalar intrinsic fixture, with C++ and Rust kept in parity, so the
project starts exercising the lowered body-token to backend-rendered output
path under a real generated profile.

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
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/backends/body_token_contract.py`
- `tslgen/src/tslgen/backends/intrinsic_body_tokens.py`
- `tslgen/src/tslgen/backends/type_value_body_tokens.py`
- `tsldata/primitives/**/*.tsl`

## Goal

Implement the smallest real x86 intrinsic fixture that proves:

- one observed `.tsl` primitive implementation can be selected for a
  non-scalar x86 generated profile, preferably `avx2`;
- its implementation body is represented as raw source tokens plus already
  lowered typed body-token values;
- lowered intrinsic/intrinsic-compose tokens are translated and rendered for
  both C++ and Rust without renderer-side parsing or semantic inference;
- generated `scalar,avx2` C++ and Rust projects write through manifest-clean
  mode and compile/test, with the `avx2` build using M225 target-feature
  flags;
- no raw `intrin<...>`, `intrin_compose<...>`, `value<backend>(...)`, or other
  accepted lowerable token text leaks into the generated intrinsic body.

This milestone is about the lowered body-token handoff into real generated
intrinsic output, not about building a complete TSIL parser or full corpus
generator.

## Preflight Evidence Step

Before editing implementation code, inspect `tsldata/primitives/**/*.tsl` and
select one exact observed x86 non-scalar implementation shape that is safe for
this milestone:

- no dependency closure beyond the selected primitive;
- no unresolved control-flow lowering requirement;
- no source-data flaw already recorded in `docs/redesign/flaws-to-fix.md`;
- no need for all-profile, ARM, NEON, SVE, qemu, or host autodetection;
- C++ and Rust can both render an actual intrinsic call from already accepted
  lowering/body-token facts or one narrowly added exact lowering shape.

If no such observed fixture exists without broad TSIL/source parsing, stop and
create a planner prompt instead of implementing.

Record the selected primitive, profile, type, backend body form, and why it is
safe in `docs/redesign/implementation-roadmap.md`.

## Scope

Add focused implementation and tests, likely touching:

```text
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
tslgen/src/tslgen/backends/*body_tokens*.py
tslgen/src/tslgen/rendering/primitive_render_model.py
tslgen/src/tslgen/rendering/generated_primitive_project.py
tslgen/tests/test_m226_first_real_x86_intrinsic_fixture.py
```

The implementation should:

- preserve the M224 parsed-source entry path where practical;
- add only the exact parser/lowering/body-token support needed for the chosen
  observed fixture;
- keep the implementation body as a sequence of raw source text and typed
  lowerable token results;
- let backend rendering consume typed lowered token results only;
- keep C++ and Rust behavior in parity for the chosen fixture;
- use M225 generated profile build flags for the `avx2` verification path;
- keep deterministic artifact ordering and manifest-clean writing.

## Guardrails

- Do not implement a general TSIL expression/statement parser.
- Do not add broad support for every `intrin_compose`, `intrin`, `call`,
  `if`, `loop`, `mem`, `io`, or `cast` shape.
- Do not parse or infer semantics inside templates, renderers, or the artifact
  writer.
- Do not introduce raw C++/Rust intrinsic source strings in Python when a
  typed lowered token or presentation model should carry the decision.
- Do not use `frozen/` or `tslgenold/` as runtime dependencies.
- Do not broaden to all machine profiles, NEON/SVE/qemu, compiler capability
  detection, host autodetection, or generated benchmark/test matrices.
- Do not repair source-data mistakes; malformed or unsupported nearby forms
  remain diagnostics or follow-ups.

## Expected Tests

Add focused tests for:

- the selected real `.tsl` fixture/evidence still contains the exact observed
  implementation form chosen for M226;
- the selected non-scalar implementation lowers to typed body-token values and
  raw source tokens, not raw lowerable token passthrough;
- rendered C++ and Rust `avx2` profile artifacts contain an actual intrinsic
  call and no raw accepted lowerable token text;
- generated `scalar,avx2` projects write via manifest-clean mode and
  configure/build/test for C++ and Rust;
- deterministic artifact digests across two runs;
- diagnostics when the exact selected form is malformed or unsupported.

Do not add all-profile matrices, ARM/qemu tests, broad corpus-generation tests,
or hardware autodetection tests in M226.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m226_first_real_x86_intrinsic_fixture.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: lowered body-token values feed backend
   rendering; templates/renderers do not parse TSIL or decide semantics.
2. Evidence reviewer: selected fixture is real observed `tsldata` input and
   does not rely on `frozen/`, `tslgenold/`, or host autodetection.
3. Test reviewer: C++/Rust parity, no raw lowerable token leakage, deterministic
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
  or `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M227.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
