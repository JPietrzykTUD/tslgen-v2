# M100 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 100.

Milestones 1 through 99 are accepted. Post-M99 planning is accepted and
selected:

```text
Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice
```

Use the orchestrated executor-review loop in this prompt. M100 is an
implementation milestone; one write-capable executor may implement the selected
slice. Do not start post-M100 planning until M100 review returns `Accept` or
`Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Resolve the accepted M99 exact-array
`exact_array_backend_value_uninit_array` request into typed C++ backend
translation-result state without rendering code or starting Stage 9 backend
planning.

For M100, "translation result" means a typed value record produced from
accepted request/provenance facts and explicit typed C++ translation
rule/metadata input. It does not mean C++ or Rust source rendering, declaration
or body IR completion, artifact planning, backend support decisions,
scheduling, dependency closure, or generic backend helper evaluation.

## Scope

- Add focused private lowering ownership for typed backend translation-result
  models, C++ exact-array uninit rule values, diagnostics, validation,
  deterministic keys, source/request narrowing, and stage assembly.
- Prefer a split private ownership shape if needed:
  - `_lowering_backend_translation_result.py` for models, rules, validation,
    keys, and public lowering functions;
  - `_lowering_backend_translation_result_sources.py` for M99 inventory/request
    narrowing;
  - `_lowering_backend_translation_result_diagnostics.py` for diagnostics.
- Consume only accepted M99 `Stage8BackendTranslationRequestInventoryIr`
  records and their preserved accepted M97/M96/M92/M72/M67 object references.
- Select only request records with kind
  `exact_array_backend_value_uninit_array`.
- Support only the exact C++ array-uninit backend value rule represented as
  typed `value_array_uninit` rule/metadata input. The lowering stage must not
  read `tsldata/detail/lang/translate_cpp.tsl` at runtime.
- Produce one typed translation-result value per accepted exact-array request,
  preserving request record, unresolved dependency, dependency request,
  completion manifest, gap inventory, and source package identity where those
  references exist.
- Add a deterministic result/no-result state after
  `lowering_backend_translation_request_inventory`, with stage name:

```text
exact_array_backend_uninit_translation_result
```

- Keep `boundary.py` as a narrow public facade only.
- Prefer a new focused M100 test file instead of adding large M100 coverage to
  `test_lowering_boundary.py`.
- Keep `docs/redesign/missing-lowering-inventory.md` accurate if execution
  narrows, resolves, or newly discovers a lowering gap.

## Out Of Scope

- Rust translation. Rust `value_array_uninit` requires typed `{type}` context
  that is not accepted for this exact M99 request yet.
- Generic `value<backend>(...)` or `type<backend>(...)` evaluation, broad
  backend translation maps, language-map evaluation, backend manifest reads,
  backend support decisions, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, operation DAGs, wrapper
  planning, artifact planning, renderer-ready IR, rendering, generated C++ or
  Rust output, generated tests, CLI/report/writer behavior, compiler execution,
  or host hardware dependency.
- Selected-body direct-intrinsic handoff resolution, direct-intrinsic/SVE
  semantics, byte-size-to-token inference, intrinsic suffix/prefix/post/infix/
  immediate resolution, vector/register metadata expansion, or broad body
  semantics.
- Raw `.tsl` source text parsing, source-body reparsing, source repair, source
  normalization, broad TSIL/body parsing, best-effort correction, registries,
  semantic dispatchers, hidden recursive backfeeds, fixpoint machinery, or
  lookup tables keyed by raw helper text, source location, backend id,
  extension id, primitive name, type tag, or direct-intrinsic token text.
- Reading `tsldata/detail/lang`, backend maps/catalogs/manifests, or `frozen`
  during lowering. The repository data files are evidence for the plan and
  fixtures only; M100 runtime behavior consumes explicit typed rule values.

## Required Inputs

- Accepted M99 backend-translation request inventory behavior and request
  record identity/provenance.
- Accepted M97 gap-inventory and M96 completion-manifest unresolved dependency
  identity behavior.
- Accepted M92 exact array backend-handoff request behavior.
- Accepted M72/M67 exact array deferred backend-uninit request behavior.
- Explicit typed C++ translation rule/metadata input for exact
  `value_array_uninit`, supplied by the caller/test fixture rather than read
  from `tsldata` during lowering.
- Current pressure points after M99:
  - `boundary.py`: 1,254 physical lines.
  - `_lowering_backend_translation_request_inventory.py`: 770 physical lines.
  - `_lowering_stage_assembly.py`: 223 physical lines.
  - `cpp/translation.py` is near the module-size guardrail and should not
    receive M100 ownership.
  - `test_lowering_boundary.py` is already too large for major new coverage.

## Expected Outputs

- One typed C++ exact-array backend-uninit translation-result value for each
  accepted exact-array M99 request record.
- Deterministic result keys and ordering.
- Result records that preserve accepted M99 request record identity and the
  relevant M97/M96/M92/M72/M67 provenance/object identities.
- Explicit unsupported/no-result diagnostics for non-exact-array request kinds,
  unsupported backend ids including Rust, missing/duplicate/conflicting typed
  C++ uninit rules, malformed request records, provenance mismatches, and
  copied/equal-but-not-identical records.
- Stage integration after `lowering_backend_translation_request_inventory` that
  preserves accepted M57-M99 diagnostics, stage names, stage ordering, stage
  keys, deterministic ordering, output identities, source locations, object
  identities, selected-branch-only diagnostics, public imports, and
  no-external-input boundaries.
- Import-boundary and line-count guardrails proving M100 does not grow
  `boundary.py`, M99 inventory modules, `cpp/translation.py`, or a new private
  module into a replacement monolith.

## Required Executor Task

Run exactly one write-capable executor for M100. The executor should:

1. Implement the exact-array C++ backend-uninit translation-result boundary
   described above.
2. Add focused private lowering ownership for result models, typed rule input,
   validation, diagnostics, source/request narrowing, and deterministic
   assembly.
3. Add the deterministic stage after
   `lowering_backend_translation_request_inventory`.
4. Consume only accepted typed M99 request records and preserved object
   references plus explicit typed C++ rule values.
5. Preserve accepted diagnostics, stage names, ordering, keys, deterministic
   ordering, output identities, source locations, object identities,
   selected-branch-only diagnostics, public imports, and no-external-input
   boundaries.
6. Add focused tests for C++ exact-array uninit results, object identity,
   determinism, diagnostics, import boundaries, line-count guardrails, and
   forbidden behaviors.
7. Avoid all out-of-scope backend, rendering, output, source-repair, raw-body
   parsing, broad-body-semantics, broad-protocol, registry/dispatcher,
   scheduler, dependency-solver, hidden-backfeed, fixpoint, and hardwiring
   behavior.
8. Run the required validation commands below.
9. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Tests

- Positive C++ exact-array uninit translation-result tests from accepted M99
  inventory records and explicit typed C++ `value_array_uninit` rule input.
- Tests proving object identity is preserved from the M100 result back through
  M99 request inventory, M97 gap inventory, M96 completion manifest, M92
  backend handoff, M72 deferred backend-uninit boundary, and M67 request record
  where those values are present.
- Determinism tests for result keys, ordering, repeated lowering, and reordered
  accepted inputs.
- Stage tests proving the new result stage follows
  `lowering_backend_translation_request_inventory` without changing accepted
  M57-M99 stage names, ordering, keys, diagnostics, output identities, object
  identities, selected-branch-only behavior, public imports, or
  no-external-input boundaries.
- Negative diagnostics for missing typed C++ rule, duplicate/conflicting typed
  rules, unsupported backend/Rust, wrong request kind, selected-body
  direct-intrinsic handoff, malformed request record, copied/equal-but-not-
  identical provenance, candidate/source-location mismatch, and unsupported
  source/container inputs.
- Import-boundary tests proving M100 modules do not import `boundary.py`, the
  `tslgen.lowering` package facade, backend modules, renderers, backend
  planners, `tsldata`, or `frozen`.
- Forbidden-behavior tests proving M100 does not read `tsldata`, backend
  maps/catalogs/manifests, or `frozen`; does not introduce Stage 9 planning,
  renderer-ready IR, rendering/output, source repair, raw body parsing,
  registries, dispatchers, schedulers, dependency closure, hidden backfeeds,
  fixpoint behavior, or hardwired `{}` fallback outside typed rule input.
- Line-count tests or source assertions keeping `boundary.py`, M99
  request-inventory modules, `_lowering_stage_assembly.py`,
  `cpp/translation.py`, and new M100 modules within module-size guardrails.

Prefer a focused new test file for M100 unit coverage. Use
`test_lowering_boundary.py` only for minimal public/stage integration coverage
if needed.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/backends/cpp/translation.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/backends/cpp/translation.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or exact_array_backend_uninit_translation_result or m100"
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/src/tslgen/backends/cpp
git diff --check
```

If implementation chooses different focused private module names or does not
touch `tslgen/src/tslgen/backends/cpp/translation.py`, include the actual
touched files consistently in line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final reporting.

Run broader validation if the implementation touches shared lowering/backend
surfaces:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
```

## Required Subagents

After the executor completes, use read-only subagents:

1. Reviewer: review the implementation against this prompt, `AGENTS.md`,
   `PLANS.md`, `docs/agent/review-checklist.md`, and the roadmap. Return
   `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`,
   or `Reject`.
2. Boundary auditor: verify no backend map/catalog/manifest reads during
   lowering, no raw helper parsing, no source repair, no renderer inference,
   no Stage 9 planning, no rendering/output, no Rust, no generic backend helper
   evaluation, and no direct-intrinsic/SVE semantics.
3. Extensibility auditor: verify focused module ownership, import direction,
   line-count guardrails, no replacement monoliths, and composable pipeline
   fit.
4. Validation auditor: verify tests and validation results, including
   diagnostics, determinism, object identity, forbidden behaviors, and mypy.
5. Documentation auditor: verify roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` reflect M100 accurately.

## Review Loop

The main thread is the orchestrator.

- If all reviews return `Accept`, mark M100 accepted, update
  `docs/agent/current-redesign-state.md`, update any needed redesign docs, and
  create `docs/agent/runs/post-m100-planning-plus-review-prompt.md`.
- If reviews return `Accept With Follow-Ups`, record non-blocking follow-ups,
  mark M100 accepted, update state/docs, and create the post-M100 planning
  prompt.
- If any review returns `Needs Revision`, run one focused write-capable
  revision executor limited to the blocking issues, then run focused re-review.
- If any review returns `Return To Planner`, stop implementation, update state,
  and create an appropriate post-M100 planning-revision prompt.
- If any review returns `Reject`, stop implementation, update state, and create
  an appropriate rollback/redesign prompt.

Only one write-capable executor or revision executor may modify the worktree at
a time. Review and audit subagents are read-only unless the orchestrator later
creates a focused revision task.

## Finalization Rules

On `Accept` or `Accept With Follow-Ups`, before finishing:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record accepted M100 behavior and validation;
- update `docs/redesign/missing-lowering-inventory.md` because M100 narrows one
  backend-value/type request gap;
- create the next concrete run prompt under `docs/agent/runs/`;
- run the final `git diff --check`.

Do not start Milestone 101 or post-M100 implementation work.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
