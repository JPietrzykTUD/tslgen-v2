# Stabilization And Release-Readiness Checklist

This checklist is the post-Milestone-34 release-readiness gate for the
redesigned `tslgen` package. It is documentation for stabilization; it is not a
new implementation milestone.

## Recommendation

Pause feature implementation and run a stabilization pass.

A release candidate can be cut without another implementation phase only as a
narrow `0.1.0a1` alpha / architecture-foundation release candidate after every
blocker below is resolved. That release may advertise the accepted pipeline,
API/CLI, validation, reporting, writer, lowering-boundary, and narrow
production-shaped rendering slices.

Do not cut a production replacement release for the legacy generator yet. Do
not claim full TSIL lowering, full C++ or Rust generation, executable generated
tests, generated documentation parity, broad corpus normalization, or drop-in
legacy CLI compatibility.

## Accepted Stable Surface

The following areas are accepted enough to stabilize for a narrow alpha release:

- Python packaging baseline: `tslgen/pyproject.toml` declares package name
  `tslgen`, version `0.1.0a1`, console script `tslgen`, `requires-python =
  ">=3.14"`, and package data for the TSL grammar.
- Core foundation: diagnostics, result containers, frozen maps, deterministic
  ordering, and explicit configuration values.
- Source and syntax boundary: source loading from explicit paths, parser
  boundary, syntax nodes, source locations, and parser diagnostics.
- Domain and validation: typed catalog construction, signature/template
  validation, attribute validation, reference validation, extension fallback,
  type/lane metadata, backend metadata validation, and implementation-spec
  promotion for accepted fields.
- Analysis: variant expansion, selection planning, candidate selection,
  primitive dependency closure, and candidate-specific dependency reporting
  with primitive-level fallbacks preserved.
- Lowering: typed-opaque lowering boundary plus the mini-TSIL direct
  parameter-add return form accepted by Milestone 27.
- Backend planning and artifacts: backend manifests, artifact descriptors,
  artifact sets, deterministic digests, duplicate/path-safety checks, and the
  filesystem writer with dry-run and skip-unchanged behavior.
- Rendering: C++ summary output, narrow C++ scalar declaration/body rendering,
  Rust summary output, and narrow Rust scalar body-free trait signatures.
- Test generation: production test-source planning from TSL `tests`
  declarations and one metadata-style C++ test-source rendering slice.
- Reporting: deterministic JSON coverage reports, deterministic HTML coverage
  reports, and candidate dependency report DTOs exposed through accepted API
  helpers.
- API/CLI: public API facade for accepted pipeline/reporting/writer helpers and
  CLI behavior for explicit source/backend/selection options, `--output-root`,
  `--dry-run`, `--no-skip-unchanged`, and `--coverage-report json|html`.
- Validation policy: Milestone 21 production validation profile, Milestone 33
  exploratory-code retirement plan, and Milestone 34 corpus hygiene policy.

## Deferred And Not Promised

These areas are intentionally out of scope for the release candidate:

- Full TSIL grammar, semantic lowering, calls, loops, type expressions, and
  generation-time branches such as `if<generation>(...)`.
- Translation-map evaluation and backend-owned intrinsic/type lowering beyond
  accepted validation of language and translation maps.
- Broad C++ generation, wrappers, overload policy, ABI naming policy, CMake
  parity, and template-family coverage beyond the accepted scalar slices.
- Rust function bodies, wrappers, trait parity, generated tests, Cargo
  integration, and broad Rust type/intrinsic mapping.
- C17 as an active backend.
- Executable generated tests, compiler invocation, runtime harnesses,
  runtime-lane behavior such as SVE, and sized-extension policy for generic
  targets.
- Full legacy CLI flag parity, legacy shell workflow replacement, and
  compatibility aliases.
- Generated documentation site parity or full legacy HTML report parity beyond
  the accepted coverage report artifact.
- Direct migration of quarantined exploratory code into production modules.
- Corpus-wide formatting, sorting, permission-bit normalization, or generated
  artifact regeneration.
- Performance instrumentation or timing utilities as accepted production
  behavior.

## Release Blockers

All blockers must be resolved before cutting any release candidate.

| Blocker | Required outcome | Evidence to record |
| --- | --- | --- |
| Release target | Use `0.1.0a1` as the public alpha / architecture-foundation release candidate label, not a production replacement label. | Release notes or project documentation state the scope and exclusions. |
| Validation profile | The accepted validation profile passes in the dev container. | Command output for `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`. |
| Unit/golden/API/CLI tests | Accepted Milestone 1-34 tests pass without relying on host CPU features, compilers, network, or quarantined modules. | Command output for the agreed test command, normally `PYTHONPATH=tslgen/src pytest tslgen/tests/unit`. |
| Determinism | Repeated rendering/reporting/writing checks produce identical artifacts, digests, write reports, and report output. | Test output or a short release-readiness note naming the deterministic checks. |
| Combined CLI report/write behavior | `--coverage-report json|html` combined with `--output-root` keeps report output on stdout and write-report lines on stderr. | CLI integration test output or release-readiness note. |
| Packaging metadata | Package metadata matches the accepted baseline: Python `>=3.14`, console script `tslgen`, runtime dependencies, and grammar package data. | Package build or metadata inspection output. |
| Package artifact boundary | Wheel and sdist contain accepted production modules and required package data only; quarantined exploratory modules remain in the repository as evidence but are not shipped. | Wheel/sdist content inspection showing `frontend`, `ir`, `middle_end`, `utils`, early core sketches, and sketch tests are absent. |
| User-facing scope docs | User docs explain supported commands/API helpers and make the alpha scope explicit. | Release notes, README, or equivalent docs. |
| Contributor docs | Contributor docs point to the clean-redesign policy, validation profile, quarantine policy, corpus hygiene policy, and review checklist. | Documentation review note. |
| Dirty worktree | Release candidate is cut from a clean worktree, or every intentional diff is documented and included in the release commit. | `git status --short` output. |
| Corpus mode churn | Current `.devcontainer/**`, `.gitignore`, and `tsldata/**` mode-only dirty state is either resolved before release or explicitly documented as not part of the release commit. | `git diff --name-status -- tsldata .devcontainer .gitignore`, `git diff --numstat -- tsldata .devcontainer .gitignore`, and `git diff --summary -- tsldata .devcontainer .gitignore`. |
| Quarantine boundary | Production API, CLI, pipeline, and accepted tests do not import quarantined exploratory modules. | Validation-profile output and import-boundary test output. |
| No overclaims | Release notes do not imply full legacy replacement, full TSIL lowering, broad backend generation, executable tests, generated docs parity, or drop-in CLI compatibility. | Release note review. |

If validation exposes defects inside the accepted Milestone 1-34 surface, fix
them as stabilization patches. If a fix requires a new feature boundary or
answers a deferred open question, stop and plan a new implementation phase.

## Non-Blocking Follow-Ups

These items should remain documented but should not block the narrow alpha
release candidate:

- OQ-003 list-backed implementation variant policy.
- OQ-004 broad byte-for-byte output compatibility policy.
- OQ-005 full TSIL grammar and semantics.
- OQ-006 generic/sized extension representation.
- OQ-007 runtime-lane extension policy.
- OQ-008 legacy CLI compatibility.
- OQ-009 generated documentation/report parity.
- OQ-011 structured type/template shape parsing.
- OQ-012 broad unknown-field strictness policy.
- Broader C++ naming, wrappers, body rendering, and template-family support.
- Translation-map evaluation and backend lowering services.
- Rust bodies, wrappers, generated tests, and Cargo integration.
- Executable production test assertions and compile/run orchestration.
- Focused deletion or migration of quarantined exploratory code.
- Broader corpus probes, corpus normalization, and permission-bit cleanup.
- Performance instrumentation policy.

## User Documentation Checklist

Before release, user-facing docs should state:

- `tslgen` requires Python `>=3.14`.
- `frozen/` is not a runtime dependency and remains behavior evidence only.
- `tsldata/` is source corpus and fixture data, not generated output.
- The package supports the accepted API/CLI slices, coverage report helpers,
  artifact writing, and narrow C++/Rust rendering slices listed above.
- Generated artifacts are deterministic within accepted slices and should be
  written only through the artifact writer boundary.
- Diagnostics include stable codes and source locations where available.
- C++/Rust output is intentionally narrow and does not replace the full legacy
  generator.
- Generated tests are metadata-style source artifacts only; they are not an
  executable test framework.
- Hardware autodetection is a CLI adapter concern; core logic expects explicit
  normalized flags.

## Contributor Documentation Checklist

Before release, contributor-facing docs should state:

- The project remains a clean-room redesign, not a legacy module rewrite.
- Future work must select one roadmap objective or milestone at a time.
- `docs/redesign/` is the design source of truth.
- `docs/agent/review-checklist.md` is the review gate for implementation work.
- Quarantined exploratory paths are evidence or cleanup candidates, not
  production dependencies or shipped package content.
- `tsldata/` edits are source-data changes requiring behavioral evidence and
  focused tests.
- Generated outputs and golden fixtures must be deterministic and reviewed as
  exact artifacts.
- Validation must use the Milestone 21 profile unless a focused milestone
  changes that profile.

## Dirty Workspace And Corpus Notes

The current observed dirty workspace includes mode-only changes under
`.devcontainer/**`, `.gitignore`, and many `tsldata/**` files. The observed
`git diff --numstat -- tsldata .devcontainer .gitignore` output reports zero
insertions and zero deletions for those files, and `git diff --summary` reports
`100644 => 100755` mode changes.

Those mode-only changes are not accepted release content by default. Before a
release candidate:

- resolve them outside an implementation milestone, or
- explicitly document why any executable-bit change is intentional, or
- ensure they are absent from the release commit.

Do not bundle permission-bit cleanup with feature work.

## Package Artifact Boundary

The package artifact boundary follows the accepted production validation
boundary. A release artifact should include accepted production modules and
required package data, including `tslgen/syntax/grammar/tsl_data.lark`, but
should not ship quarantined exploratory modules merely because they still exist
in the repository.

The following paths are repository evidence or cleanup candidates and are not
release artifact content for the narrow alpha:

- `tslgen.frontend`
- `tslgen.ir`
- `tslgen.middle_end`
- `tslgen.utils`
- early core sketches: `tslgen.core.context`, `tslgen.core.passes`, and
  `tslgen.core.types`; these delete-candidate files may also be retired in a
  focused packaging-boundary stabilization pass when artifact inspection proves
  they would otherwise ship inside the accepted `tslgen.core` package.
- sketch tests such as `tests/test_timing.py`

This exclusion does not delete or migrate the quarantined code. It only keeps
wheel and sdist artifacts aligned with the accepted production package surface.

## Release Candidate Verdict

Recommended action:

Pause feature implementation, run the stabilization checklist, resolve release
blockers, and cut a narrow alpha or architecture-foundation release candidate
only after the checks pass.

Another implementation phase is not required before that alpha release
candidate. Another implementation phase is required before any release claims
full legacy workflow replacement, broad code generation, full TSIL lowering, or
executable generated tests.
