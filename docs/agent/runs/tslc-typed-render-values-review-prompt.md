# TSLc Typed Render Values Review Prompt

## Accepted State

This is an ad hoc `tslc/` worktree review prompt, not a numbered `tslgen/`
redesign milestone. The previously selected numbered redesign action remains
paused while this `tslc` work is reviewed.

The implemented slice replaces renderer-side semantic body rewrites and
unchecked template substitution with typed render values for the current
lowering/rendering path. Lowered specializations now carry `LoweredBody` values,
Rust overload rendering supplies an explicit `RenderContext`, backend syntax
facets no longer frame or rewrite body text, backend templates render through
validated typed fields, and nested lowerer handlers preserve typed render
fragments instead of forcing them through default-context strings.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/design-decisions.md`
- `tslc/src/tslc/render/model.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/backend/translation_common.py`
- `tslc/src/tslc/backend/translation.py`
- `tslc/src/tslc/backend/cpp_translation.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/src/tslc/ir/scan.py`
- `tslc/src/tslc/lower/context.py`
- `tslc/src/tslc/lower/queries.py`
- `tslc/src/tslc/lower/region_handlers/bitwise.py`
- `tslc/src/tslc/lower/region_handlers/declarations.py`
- `tslc/tests/test_render_model.py`
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/mask/bitwise.tsl`

## Scope

Review the strict typed render rewrite and confirm that:

- `LoweredSpecialization` stores `body: LoweredBody` and keeps `body_text` only
  as a compatibility render property;
- successful lowered bodies are rendered through typed render values and
  explicit `RenderContext` values where presentation context changes;
- Rust overloaded rendering no longer uses `_concretize_simd_assoc` or body-text
  semantic replacement;
- nested handler rendering passes `RenderText` values through expression bodies,
  declaration initializers, casts, calls, memory/mask template fields,
  templates, and control-flow bodies;
- `let<type>` aliases that resolve to backend spellings are represented as
  typed render values both in raw source chunks and type-position queries such
  as `cast<static>(CountT, ...)`;
- backend syntax facets no longer expose `frame_body(...)` semantic rewrites;
- unsafe wrapping and accepted `bit_negate(expr)` presentation happen before
  backend project rendering, with backend syntax facets rendering C++ `~` and
  Rust `!` rather than a `backend_id` branch or raw `~` interpretation in
  lowering;
- template rendering validates supplied placeholders and rejects unresolved
  placeholders while preserving accepted Rust const-generic brace forms;
- raw body text survives only as explicit literal render text after unsupported
  TSIL regions have diagnosed and skipped the specialization;
- generated C++ and Rust artifacts remain behaviorally stable for accepted
  covered behavior; presentation changes are limited to the intentional
  `bit_negate(expr)` cleanup.

## Out Of Scope

- Do not write a C++ or Rust parser.
- Do not add new backend semantics, selector behavior, fallback policy, or source
  repair.
- Do not intentionally change generated C++ or Rust text outside the
  `bit_negate(expr)` presentation cleanup.
- Do not migrate the paused old `tslgen/` milestone line.
- Do not require every existing region handler implementation to construct
  dedicated render classes when the current typed lowered-body boundary already
  preserves accepted behavior.

## Required Validation

Run or confirm:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_render_model.py
python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py
python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_coverage.py
python -m pytest -q tslc/tests/test_build_verify.py::test_elementwise_bitwise_builds tslc/tests/test_build_verify.py::test_mask_boolean_algebra_builds
./verify.sh
git diff --check
grep -RInE 'backend_id ==|backend_id !=' tslc/src/tslc/lower --include='*.py'
```

If `./verify.sh` fails because a host compiler, Zig cache, or Cargo cache is not
available or writable, record that as environmental only after the targeted
Python tests above pass.

The `grep` command is expected to return no matches and exit with status 1.

## Expected Output

Return a review verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with any blocking findings and cite file/line references. If accepted,
update `docs/agent/current-redesign-state.md` and create the next concrete
prompt required by `docs/agent/next-run-prompt-protocol.md`.

## Stop Rule

Do not implement revisions during review unless a focused revision task is
explicitly created. Do not start the paused old `tslgen/` milestone line in this
run.
