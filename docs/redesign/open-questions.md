# Open Questions

This file tracks unresolved questions. Do not guess answers that materially affect architecture.

## OQ-001: What Exact Python Version Should The Redesign Target?

Status: Answered

Why it matters:

`tslgen/pyproject.toml` currently requires Python `>=3.14`, which is restrictive and may not match deployment expectations.

Decision:

Target Python `>=3.14` for the redesign. The dev container has Python 3.14.4 installed, and the existing `tslgen/pyproject.toml` already declares `requires-python = ">=3.14"`.

Considered answers:

- Keep `>=3.14`.
- Use a stable lower baseline such as `>=3.12`.
- Match the repository/devcontainer runtime.

Required evidence:

- Dev-container runtime: Python 3.14.4 is installed.
- Existing packaging sketch: `tslgen/pyproject.toml` declares `>=3.14`.
- Language features actually required should still be kept conservative and documented as implementation proceeds.

Implementation blocked:

No. Packaging and syntax choices may use Python 3.14 as the baseline. Implementations should still avoid unnecessary version-specific cleverness.

## OQ-002: Should Backend Manifests Remain YAML?

Status: Answered

Why it matters:

Legacy evidence stores backend behavior in YAML under `frozen/generator_specs`. The redesign can preserve YAML as a data format or move manifests into TSL/Python.

Decision:

Keep YAML as a supported manifest interchange format at the I/O boundary, but
do not make YAML structures part of downstream architecture. Backend planning
consumes typed `BackendManifest` and `BackendManifestSet` values.

Possible answers:

- Keep YAML with typed schemas.
- Convert manifests into TSL data.
- Define backend manifests in Python plugin modules.

Required evidence:

- Current C++ and Rust backend manifest fixtures exist at
  `frozen/generator_specs/backend_cpp.yaml` and
  `frozen/generator_specs/backend_rust.yaml`.
- C17 manifest fixtures also exist as legacy evidence, but C17 is no longer
  first-class in the current implementation roadmap.
- Current TSL language and translation declarations expose backend IDs under
  `tsldata/detail/lang/*.tsl`.

Implementation blocked:

No. Milestone 10 supports YAML loading into typed manifests and can also derive
a minimal manifest set from matching catalog `language` and `translation`
entries when artifact specs are known.

## OQ-003: What Is The Explicit Policy For List-Backed Implementation Variants?

Status: Open - scheduled for Milestone 20

Why it matters:

Some legacy selection paths accept list-backed implementation entries and select the first dict. This is likely accidental or underspecified.

Possible answers:

- Reject list variants until a selector field exists.
- Add priority fields.
- Add predicate-based variant matching.
- Preserve first-match only where golden evidence requires it.

Required evidence:

- Search current `tsldata/` for list-backed implementation variants.
- Identify whether generated outputs depend on ordering.
- Ask domain owners for intended semantics.

Implementation blocked:

Selection of ambiguous variants is blocked. Basic selection for simple map variants is not blocked. Milestone 20 is the next decision point because implementation spec promotion must decide whether list-backed variants are supported, rejected, or diagnosed.

## OQ-004: How Much Byte-For-Byte Output Compatibility Is Required?

Status: Open - required before broad backend rendering

Why it matters:

Strict generated output compatibility can constrain rendering and formatting decisions.

Possible answers:

- Byte-for-byte compatibility for selected public headers only.
- Semantic compatibility with new formatting.
- Golden compatibility only for representative fixtures.

Required evidence:

- Consumers of generated headers/source.
- Existing release expectations.
- Selected golden baseline outputs.

Implementation blocked:

Milestone 22 backend rendering expansion is blocked until this is narrowed for
the selected slice. Earlier boundary milestones are not blocked.

## OQ-005: What Is The Long-Term TSIL Grammar And Semantics?

Status: Open - scoped by Milestone 18

Why it matters:

TSIL includes calls, loops, type expressions, generation-time values, attributes, and backend translations. String rewriting will not scale.

Possible answers:

- Formalize TSIL grammar before backend work.
- Implement a minimal parser for dependency extraction first.
- Defer full TSIL semantics until after first backend slice.

Required evidence:

- `frozen/tsl-gen/tsl_gen/tsil.lark`
- TSIL bodies in `tsldata/primitives/**.tsl`
- Existing lowering behavior that must be preserved.

Implementation blocked:

Dependency and lowering milestones are partially blocked. Catalog milestones are not blocked. Milestone 18 is the next decision point and must either choose a minimal TSIL subset or document an explicit typed-opaque lowering boundary with unsupported diagnostics.

## OQ-006: How Should Generic/Sized Extensions Be Represented?

Why it matters:

Extensions such as `generic` and `oneAPIfpga` have `vector_bits "sized"` and tests use `test_sizes_bits`. Rendering may require type parameters such as `Bits`.

Possible answers:

- Model sized extensions as extension plus size parameter.
- Expand sized extensions into concrete target variants during selection/test planning.
- Treat sized bits as backend-specific generic parameters.

Required evidence:

- `tsldata/extensions/extension.tsl`
- Backend templates for generic and oneAPIfpga.
- Existing generated outputs for `frozen/out/tsl/tsl_generic.hpp`.

Implementation blocked:

Full generic backend planning is blocked. Basic fixed-width selection is not blocked.

## OQ-007: What Is The Correct Policy For Runtime-Lane Extensions Such As SVE?

Why it matters:

SVE has scalable vector length and runtime lane behavior. Test planning and generated code cannot assume fixed lanes.

Possible answers:

- Treat runtime-lane extensions as a separate test/generation mode.
- Skip specific templates according to manifest until full support exists.
- Generate runtime-lane-aware tests for all supported templates.

Required evidence:

- `tsldata/extensions/extension.tsl`
- `frozen/generator_specs/tests.yaml`
- `frozen/run_all.sh` SVE behavior.

Implementation blocked:

SVE test planning and backend slices are blocked. Fixed-lane backends are not blocked.

## OQ-008: Which CLI Compatibility Is Required?

Status: Partially answered

Why it matters:

Legacy workflows expose `run_all.sh`, `run_tests.py`, and `python -m tsl_gen` options. The new CLI can be cleaner, but users may rely on existing flags.

Possible answers:

- New CLI with no compatibility promises.
- Compatibility subcommands or aliases for common legacy workflows.
- Keep shell workflow as wrapper around new CLI.

Required evidence:

- Current users and automation.
- CI scripts.
- Documentation or release expectations.

Implementation blocked:

No for the Milestone 13 public API and minimal diagnostic CLI. Yes for any
claim that the redesigned CLI is a drop-in replacement for legacy shell or
module workflows.

Current resolution:

- Milestone 13 implements a clean public API plus a narrow CLI adapter over it.
- The CLI does not promise compatibility with legacy flags or shell workflows.
- A future CLI/writer milestone must decide output-writing behavior and any
  compatibility aliases before replacing legacy workflows.

## OQ-009: Should Generated Documentation Be In Scope?

Why it matters:

Legacy workflows generate TSL/TSIL documentation with MkDocs and coverage reports.

Possible answers:

- Include documentation generation as a later backend/reporting feature.
- Keep documentation tooling separate from the generator.
- Defer until code generation stabilizes.

Required evidence:

- Required docs outputs.
- Consumers of `frozen/docs` and generated site.

Implementation blocked:

Documentation generation is blocked. Core generation is not blocked.

Current status:

- Milestone 15 implements lightweight in-memory coverage summaries and
  deterministic JSON report text.
- Legacy-style generated documentation, report files, and HTML report parity
  remain deferred under this question and are scheduled for Milestone 23.

## OQ-010: What Backends Are First-Class For The First Release?

Status: Answered

Why it matters:

Evidence supports C++, Rust, and legacy C17, but implementation priority affects architecture and test coverage.

Decision:

C++ and Rust are first-class for the current redesign roadmap. C17 support is
deferred and should not appear in current implementation milestones. Backend
interfaces should remain extensible enough to add C17 later if it becomes a
priority again.

Considered answers:

- C++ only first, with backend protocol ready for others.
- C++ and Rust.
- C++, C17, and Rust from the start.

Required evidence:

- User direction: eliminate C17 support from the plan now.
- Existing consumer workflows.
- Golden baseline needs.

Implementation blocked:

No. Milestones should target C++ first and Rust after the backend protocol is
established. C17 is out of scope unless a new decision reintroduces it.

## OQ-011: Should Type And Template Shapes Be Parsed Or Kept As Strings Initially?

Why it matters:

`tsldata/detail/templates.tsl` has shape strings like `(vector, vector) -> vector`. They are useful for validation and docs but not yet formalized.

Possible answers:

- Parse shapes in the catalog milestone.
- Keep as strings and parse when needed.
- Replace with structured fields in TSL data.

Required evidence:

- How shapes are used by generators and tests.
- Whether shape strings are authoritative or descriptive.

Implementation blocked:

Not for early catalog construction. Stronger validation is blocked.

## OQ-012: What Is The Error Policy For Unknown Extra Fields?

Status: Open - scheduled for Milestone 20

Why it matters:

TSL data may include backend- or future-specific fields. Strict rejection improves safety but may block extensibility.

Possible answers:

- Preserve unknown fields with warnings.
- Reject unknown fields outside documented extension maps.
- Allow unknown fields by namespace/prefix.

Required evidence:

- Current extra fields in `tsldata/`.
- Expected authoring workflow.

Implementation blocked:

Validation strictness is partially blocked. Catalog can preserve extra fields now.

## OQ-013: Should Artifact Writing Be A Separate Boundary From Rendering?

Status: Answered

Why it matters:

The accepted backend slices render in-memory artifacts only. Writing files introduces path safety, skip-unchanged behavior, dry-run behavior, and filesystem errors. Mixing those concerns into renderers would make backend behavior harder to test and review.

Decision:

Artifact writing is a dedicated I/O boundary scheduled for Milestone 16. Renderers produce artifacts; the writer validates paths, compares digests, creates directories, writes files, and returns deterministic write reports.

Possible answers:

- Keep writing inside renderers.
- Write artifacts through a separate filesystem writer.
- Delay writing until full backend generation.

Required evidence:

- Milestones 10, 11, and 14 already produce artifact descriptors and in-memory rendered artifacts.
- Milestone 13 CLI/API integration intentionally does not write output files.
- Milestone 15 reporting is pure and does not write report files.

Implementation blocked:

No. Milestone 16 can proceed using already-rendered artifacts and temporary-directory tests.

Current status:

- Milestone 16 adds the dedicated writer boundary with dry-run,
  skip-unchanged, path-safety, and deterministic write-report behavior.
- CLI compatibility and output-mode UX remain deferred to the later API/CLI
  hardening milestone.

## OQ-014: Should Reporting Be Exposed Through `tslgen.api`?

Status: Open - scheduled for Milestone 24

Why it matters:

Milestone 15 added reporting helpers, but the current public API pipeline result does not expose reporting as a first-class API capability. Exposing it too early could freeze unstable report models; hiding it too long encourages callers to import internal modules.

Possible answers:

- Expose a stable `coverage_report(...)` helper through `tslgen.api`.
- Keep reporting under `tslgen.reporting` until report artifacts are implemented.
- Expose reporting only through a higher-level pipeline option.

Required evidence:

- API caller needs after Milestones 16 through 23.
- Whether report artifacts become part of normal generation output.
- Stability of coverage/report fields after backend rendering expands.

Implementation blocked:

No for Milestones 16 through 23. Public API polish is blocked until Milestone 24.

## OQ-015: Should Dependency Closure Remain Primitive-Name Based?

Status: Open - scheduled for Milestone 19

Why it matters:

The accepted dependency closure is intentionally conservative and primitive-name based. Real backend generation may need dependency edges between selected implementation candidates, lowered calls, or backend-specific render jobs.

Possible answers:

- Keep primitive-name closure and document it as the stable behavior.
- Add candidate-specific dependency closure after lowering exposes call targets.
- Add backend render-job dependencies only when backend artifacts require it.

Required evidence:

- Dependency markers and call forms in implementation payloads.
- Lowering results from Milestone 18.
- Backend rendering needs from Milestone 22.

Implementation blocked:

Milestone 19 is blocked on enough lowering evidence to avoid guessing. Milestone 16 and Milestone 17 are not blocked.

## OQ-016: How Far Should Implementation Specs Be Promoted From Raw Catalog Values?

Status: Open - scheduled for Milestone 20

Why it matters:

Milestones through 15 still allow some implementation metadata to travel as raw catalog values. Selection, lowering, dependency discovery, and backend rendering need stable typed semantics, but over-modeling unused fields would create premature architecture.

Possible answers:

- Promote only fields required by selection, lowering, dependency discovery, and the next backend slice.
- Fully model all implementation fields now.
- Keep raw values and add access helpers.

Required evidence:

- Fields consumed by candidate selection.
- Lowering and dependency needs from Milestones 18 and 19.
- Real `tsldata/` examples, especially list-backed variants and unknown extra fields.

Implementation blocked:

Milestone 20 is blocked on Milestones 18 and 19. Broad backend rendering is blocked until the needed implementation spec subset is typed.

## OQ-017: What Belongs In The Production Validation Baseline Versus Exploratory Quarantine?

Status: Open - scheduled for Milestone 21

Why it matters:

The repository contains accepted redesign code, exploratory sketches, legacy evidence, generated data, and tests. Future agents need a validation command that catches production regressions without being derailed by intentionally incomplete sketches.

Possible answers:

- Treat only documented production packages and tests as validation targets.
- Bring all exploratory code under the same validation baseline.
- Move or mark exploratory code so production imports cannot depend on it accidentally.

Required evidence:

- Current package layout under `tslgen/`.
- Import graph of accepted implementation modules.
- Existing test and tool configuration in the dev container.

Implementation blocked:

No for Milestones 16 through 20. Broad validation claims are blocked until Milestone 21.

## OQ-018: Which Backend Rendering Slice Should Follow Summary Artifacts?

Status: Open - scheduled for Milestone 22

Why it matters:

Milestones 11 and 14 render deterministic summary artifacts, not production C++ or Rust code. The first production-shaped rendering slice must be small enough to review and must not bypass lowering, dependency, or implementation-spec boundaries.

Possible answers:

- C++ first for one simple primitive/template class.
- Rust first for one simple primitive/template class.
- Defer production-shaped rendering until TSIL and implementation specs are more complete.

Required evidence:

- Lowering boundary result from Milestone 18.
- Dependency decision from Milestone 19.
- Typed implementation spec subset from Milestone 20.
- Output compatibility policy from OQ-004.

Implementation blocked:

Milestone 22 is blocked until Milestones 18 through 20 are accepted and OQ-004 is narrowed enough for the chosen slice.

## Follow-ups from Milestone 2 review

- Add focused tests for invalid UTF-8 and read failure diagnostics where practical.
- Standardize whether file-level diagnostics use synthetic locations such as `line=1, column=1` or `location=None` before CLI diagnostic rendering.
- Clarify whether source digests are computed over normalized text or raw bytes before digest behavior becomes externally visible.

## Follow-ups from Milestone 3 review

- Clarify parser public API exports and keep Lark construction private. 
- In Milestone 4, verify SyntaxNode structure is sufficient for typed catalog construction without parser-private leakage. 
- Consider changing the corpus test to assert “all discovered files parse” without hard-coding the count, or document the count as an intentional current-corpus check.

## Follow-ups from Milestone 4 review

- Replace generic `CatalogEntry` with typed models for flags, language type maps, translation maps, primitive tests, and implementation specs when later milestones require semantic access to those concepts.
- Revisit whether catalog construction should remain in `domain` or move to a boundary/conversion module if the strict target-architecture dependency rule becomes important.
- Add focused tests for duplicate fields inside extension, template, and primitive bodies if duplicate fields are intended to remain structural errors.
- Watch repeated nested field representation: tuple-grouped repeated fields may need a richer representation if occurrence identity matters during later validation.

## Follow-ups from Milestone 5 review

- Add focused tests for invalid signature syntax with source locations.
- Add direct tests for `v:=sequence` parameter-count behavior.
- Clarify whether repeated declaration parameters must include `...`.
- Treat the signature rule table as typed behavioral data; consider moving it to a typed manifest once rule churn slows.

## Follow-ups from Milestone 6 review

- Add typed flag models and flag-alias normalization before or during Milestone 7.
- Promote primitive tests and implementation specs out of generic `CatalogValue` structures when later stages depend on them.
- Add a focused test for all-unknown selectors in unambiguously extension-keyed `requires` maps.
- Revisit conservative `requires` validation once flags and implementation specs are typed.
- Decide whether `ReferenceValidatedCatalog` should remain a marker-only pipeline gate or gain stronger typed invariants in later stages.

## Follow-up from Milestone 7 review

- During Milestone 8, promote implementation metadata out of generic catalog values only as concrete selection needs become clear.

## Follow-ups from Milestone 8 review

- Addressed in Milestone 10: backend artifact planning treats
  `BackendManifestSet` as the authoritative backend-ID source, with optional
  minimal manifest derivation from matching catalog `language` and `translation`
  entries.
- Addressed in Milestone 10: artifact planning has focused unknown-backend
  diagnostic tests.
- Add focused tests for malformed or missing implementation body diagnostics.
- Continue promoting implementation specs out of raw catalog values only as later stages require them.

## Follow-ups from Milestone 9 review

- Add focused tests for malformed or incomplete dependency marker diagnostics.
- Addressed in Milestone 10: artifact descriptors preserve the current
  primitive-name closure and do not choose dependency implementations.
- Addressed in Milestone 10: `behavioral-spec.md` documents the conservative
  primitive-level closure boundary for artifact descriptors.

## Follow-ups from Milestone 10 review

- Clarify that skip-unchanged artifact writer behavior belongs to a later writer stage, not Milestone 10.
- Add a later writer milestone/test for skip-unchanged behavior and real artifact digests.
- Keep the actual writer boundary explicit when `io.artifacts` starts performing file writes.
- Addressed in Milestone 11: backend mismatch is a renderer diagnostic. The
  C++ renderer rejects non-`cpp` artifact plans/descriptors and candidates
  selected explicitly for a different backend.

## Follow-ups from Milestone 11 review

- Addressed in Milestone 12: added a regression test proving generic
  `backend=None` candidates are accepted by the C++ renderer.
- Addressed in Milestone 12: added focused tests for non-`cpp` artifact plan
  and descriptor rejection.
- Keep the future artifact writer as a separate I/O boundary, not an expansion of the renderer.

## Follow-ups from Milestone 12 review

- Create or rename a future milestone for production test-source planning from TSL `tests` declarations.
- Move the older broad Milestone 12 test-planning bullets into that future test-generation milestone so future agents do not treat them as already satisfied.
- Keep artifact writing and skip-unchanged behavior out of the golden harness and in a future writer boundary.

## Follow-ups from Milestone 13 review

- Addressed in Milestone 14: added a focused public API test that loads a Rust
  backend manifest from a path and renders the in-memory Rust summary artifact.
- Addressed in Milestone 14: introduced a small backend renderer registry used
  by the public API for C++ and Rust rendering dispatch.
- Keep output writing and skip-unchanged behavior in a later writer boundary.

## Follow-ups from Milestone 14 review

- Keep output writing and skip-unchanged behavior in a later writer boundary.
- Avoid expanding the backend registry into lifecycle/plugin mechanics until a real extension need appears.

## Follow-ups from Milestone 15 review

- Addressed by the post-Milestone-15 roadmap in `docs/redesign/implementation-roadmap.md`.
- Reporting exposure through `tslgen.api` remains open and is scheduled for Milestone 24.
- Artifact writing and skip-unchanged behavior are scheduled for Milestone 16.
- Production test-source planning from TSL `tests` declarations is scheduled for Milestone 17.
- Full lowering and TSIL strategy are scheduled for Milestone 18.
- Candidate-specific dependency closure is scheduled for Milestone 19.
- Implementation spec promotion is scheduled for Milestone 20.
- Broad validation cleanup and exploratory-code quarantine are scheduled for Milestone 21.
- Backend rendering expansion is scheduled for Milestone 22.
- Legacy-style report and HTML output are scheduled for Milestone 23.

## Follow-up from Milestone 16 review

- Keep API/CLI exposure of artifact writing deferred until its own milestone, preserving the dedicated writer boundary.