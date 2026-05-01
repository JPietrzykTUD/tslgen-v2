# Implementation Roadmap

Each milestone should produce a usable architectural slice. Do not define milestones as porting legacy modules.

## Milestone 1: Project And Diagnostic Foundation

Goal:

Establish the basic package foundation, diagnostic model, result types, stable ordering helpers, and test fixture conventions.

Scope:

- `tslgen/src/tslgen/core/diagnostics.py`
- `tslgen/src/tslgen/core/result.py`
- `tslgen/src/tslgen/core/frozen_map.py`
- `tslgen/src/tslgen/core/ordering.py`
- Test utilities for fixture paths and diagnostics.

Required tests:

- Diagnostic construction and ordering.
- Result success/error behavior.
- Frozen map immutability and deterministic iteration.

Validation criteria:

- Pure unit tests pass.
- No runtime dependency on `frozen/`.
- Public diagnostic fields include code, severity, message, and optional location.

Out of scope:

- TSL parsing.
- Backend rendering.
- CLI behavior.

## Milestone 2: Source Loading Boundary

Goal:

Load source documents from explicit paths and standard data directories without parsing them.

Scope:

- `io/sources.py`
- `config/model.py`
- Source kind classification.
- Deterministic path resolution.

Required tests:

- Explicit source loading.
- Standard `tsldata/` loading order.
- Missing file diagnostic.
- Duplicate path handling.

Validation criteria:

- Source loading returns immutable `SourceDocument` objects with path, text, digest, and kind.
- Filesystem reads are isolated to this layer.

Out of scope:

- Syntax validation.
- Catalog construction.

## Milestone 3: TSL Parser Boundary

Goal:

Parse the current TSL corpus into syntax nodes with spans.

Scope:

- `syntax/grammar/tsl_data.lark`
- `syntax/parser.py`
- `syntax/ast.py`
- Parser diagnostics.

Required tests:

- Parse representative files from `tsldata/detail`.
- Parse primitive declarations with attributes and multiline TSIL strings.
- Parse inline maps and multiline maps.
- Syntax error diagnostics with file, line, column.
- Snapshot or structural tests for representative AST nodes.

Validation criteria:

- All files under `tsldata/` parse.
- Parser output preserves source spans.

Out of scope:

- Domain validation.
- Signature-to-template resolution.
- TSIL parsing.

## Milestone 4: Catalog Domain Model

Goal:

Convert parsed TSL syntax into typed catalog objects for core block types.

Scope:

- `domain/catalog.py`
- `domain/primitives.py`
- `domain/types.py`
- `domain/extensions.py`
- `domain/templates.py`
- `domain/tests.py`
- Catalog builder.

Required tests:

- Build catalog from `tsldata/detail/types.tsl`.
- Build catalog from `tsldata/detail/lane_sets.tsl`.
- Build catalog from `tsldata/extensions/extension.tsl`.
- Build representative primitive specs from `tsldata/primitives/arithmetic/fundamental.tsl`.
- Preserve extra fields in a constrained value type.

Validation criteria:

- Catalog contains typed objects, not raw parser dictionaries.
- Parser-private keys do not appear in domain fields.

Out of scope:

- Full semantic validation.
- Implementation selection.
- Rendering.

## Milestone 5: Signature And Attribute Validation

Goal:

Validate signatures, attributes, template required fields, and signature-to-template resolution.

Scope:

- `domain/signatures.py`
- `validation/signature_rules.py`
- `validation/attribute_rules.py`
- `validation/catalog_validator.py`
- Typed representation of signature rules from `frozen/generator_specs/signatures.yaml` or a new manifest format.

Required tests:

- Resolve representative signatures to templates.
- Reject invalid `mask`, `aligned`, `packed`, `op`, `cast`, `direction`, and `value` attributes.
- Enforce required template fields from `tsldata/detail/templates.tsl`.
- Normalize signatures with whitespace.
- Diagnostic codes and locations.

Validation criteria:

- Current `tsldata/` passes validation for implemented rule coverage.
- Invalid fixtures produce multiple structured diagnostics where practical.

Out of scope:

- Implementation selection.
- Backend rendering.

## Milestone 6: Reference Validation

Goal:

Validate cross-references between primitives, implementations, type groups, lane sets, extensions, flags, language maps, and templates.

Scope:

- `validation/reference_rules.py`
- `validation/extension_rules.py`
- Type group expansion helpers.
- Extension inheritance graph.

Required tests:

- Unknown extension in implementation block.
- Unknown type group in implementation category.
- Unknown lane set or test type.
- Extension inheritance unknown parent, self-parent, and cycle.
- Flag alias normalization collisions or unknown policy.

Validation criteria:

- Validation does not call `SystemExit`.
- Diagnostics include source locations when available.

Out of scope:

- TSIL primitive call validation unless dependency parsing is already available.

## Milestone 7: Variant Expansion And Selection Planning

Goal:

Expand wildcard primitive variants and build explicit selection plans from requests.

Scope:

- `analysis/expansion.py`
- `analysis/requirements.py`
- `analysis/selection.py`
- `SelectionRequest` and `SelectionPlan`.

Required tests:

- `aligned=*` expands to true/false in stable order.
- `aligned=*, packed=*` expands to four stable variants.
- CPU flags normalize through `tsldata/detail/flags.tsl`.
- Explicit extensions and autodetected flags produce expected allowed extension sets.
- Forced support extensions policy is explicit.

Validation criteria:

- Selection planning is pure and host-independent.
- Unknown requested names are diagnostics or documented warnings.

Out of scope:

- Selecting concrete implementation bodies.
- Dependency closure.

## Milestone 8: Implementation Candidate Selection

Goal:

Select supported implementation candidates by primitive variant, extension fallback, type group, backend, and feature requirements.

Scope:

- `analysis/selection.py`
- Requirement expression normalization.
- Extension fallback chains.
- Candidate identity and deterministic ordering.

Required tests:

- Select scalar/generic candidates for a small primitive fixture.
- Select AVX/SSE candidates based on normalized flags.
- Fallback from `avx2_vl` to `avx2` where applicable.
- Filter unsupported backend entries.
- Determinism across repeated runs.

Validation criteria:

- Candidate set is stable and inspectable.
- Ambiguous list-backed variants produce diagnostics until policy is defined.

Out of scope:

- TSIL lowering.
- Artifact rendering.

## Milestone 9: Dependency Discovery And Closure

Goal:

Include primitive dependencies required by selected implementations.

Scope:

- `analysis/dependencies.py`
- Conservative call parser or initial TSIL parser slice.
- Dependency graph and closure algorithm.

Required tests:

- Discover `call<primitive=mov attrs[mask=zero]>`.
- Resolve `@self` references.
- Include support primitives for targeted selection.
- Diagnose unknown dependency.
- Stable closure ordering.

Validation criteria:

- Targeted primitive generation plans include required dependencies.
- The design can migrate to full TSIL parsing.

Out of scope:

- Full TSIL lowering.

## Milestone 10: Backend Manifest And Artifact Model

Goal:

Load backend manifests into typed models and produce artifact sets without rendering real primitive bodies.

Scope:

- `domain/backends.py`
- `io/manifests.py`
- `io/artifacts.py`
- `rendering/render_plan.py`

Required tests:

- Load C++ and Rust manifest fixtures.
- Reject bad manifest versions and missing fields.
- Detect duplicate artifact targets.
- Skip unchanged writes in temp output directories.
- Digest map determinism.

Validation criteria:

- Artifact writing is the only file-writing stage.
- Backend manifest validation is typed and deterministic.

Out of scope:

- Real code generation.

## Milestone 11: First Backend Vertical Slice

Goal:

Generate a minimal deterministic C++ artifact for a narrow primitive subset.

Scope:

- `backends/base.py`
- `backends/cpp/backend.py`
- `backends/cpp/planner.py`
- `backends/cpp/renderer.py`
- Minimal template/render strategy.

Required tests:

- Golden output for one simple primitive and one extension/type.
- Required flags metadata.
- Stable render job ordering.
- API pipeline test from source fixture to artifact set.

Validation criteria:

- The artifact is generated without reading from `frozen/`.
- Rendering receives a backend plan and does not perform selection.

Out of scope:

- Full wrapper parity.
- All templates.
- Rust.

## Milestone 12: Test Planning And Golden Harness

Goal:

Plan and render representative tests from TSL test cases.

Milestone 12 initial slice:

- Reusable golden-file harness.
- Rendered-artifact comparison helpers.
- Artifact digest determinism helpers.
- Regression coverage for accepted C++ backend-slice diagnostics.

Full production test-source planning from TSL `tests` declarations is deferred
to a later test-generation slice.

Scope:

- `domain/tests.py`
- Test planning policy.
- Golden-file harness.
- Backend test renderer slice.

Required tests:

- Plan tests for a selected primitive.
- Filter unsupported extensions/types.
- Lane-set validation and resizing policy tests.
- Golden test source fixture.

Validation criteria:

- Test generation is deterministic.
- Test planning is based on selected implementations.

Out of scope:

- Running generated C++/Rust tests in CI unless toolchain is documented.

## Milestone 13: CLI/API Integration

Goal:

Expose the implemented pipeline through a CLI and stable API.

Milestone 13 initial slice:

- Stable public API that returns structured stage outputs and diagnostics.
- Minimal diagnostic CLI over the public API.
- In-memory artifact rendering only for the accepted C++ summary artifact when
  manifests and `render_backend` are provided.
- No artifact writing, skip-unchanged behavior, full production CLI compatibility,
  or production test-source generation.

Scope:

- `api.py`
- `cli.py`
- `config/cli_adapter.py`
- `config/hardware.py`
- Diagnostic rendering for humans.

Required tests:

- CLI parse success and invalid option behavior.
- API run with explicit config.
- Hardware autodetection adapter mocked in tests.
- Nonzero exit on diagnostics with errors.

Validation criteria:

- CLI reads host hardware only in autodetect mode.
- API is host-independent by default.

Out of scope:

- Full `run_all.sh` replacement.

## Milestone 14: Rust Backend Slice

Goal:

Add the Rust backend using the established backend protocol.

Milestone 14 initial slice:

- Minimal Rust summary renderer for the `generated` artifact kind.
- Golden-file coverage for one representative Rust summary artifact.
- Backend renderer registry used by the public API for C++ and Rust dispatch.
- No Rust SIMD lowering, template rendering engine, Cargo integration, artifact
  writing, or production Rust code generation.

Scope:

- `backends/rust/*`
- Backend-specific tests and golden files.

Required tests:

- Golden output for representative primitives.
- Manifest validation for backend-specific fields.
- Backend support filtering.
- Determinism tests.

Validation criteria:

- No backend-specific conditionals leak into generic selection.

Out of scope:

- Full coverage of every template until prioritized.
- C17 or other additional backend implementation.

## Milestone 15: Coverage And Reporting

Goal:

Produce implementation coverage reports from the typed catalog and selection logic.

Milestone 15 initial slice:

- In-memory coverage report model over existing pipeline/stage outputs.
- Deterministic JSON serialization for report values.
- Primitive, candidate, dependency-closure, backend artifact, and diagnostic
  count summaries.
- Public reporting helper that accepts the existing pipeline result shape.
- No report file writing, HTML report generation, CI integration, or CLI report
  flag.

Scope:

- Reporting models.
- JSON and optional HTML artifact generation.
- CLI command or API entry point.

Required tests:

- Coverage rows for a fixture catalog.
- Missing implementation reporting by extension/type/backend.
- Deterministic JSON output.

Validation criteria:

- Report generation does not parse raw TSL after catalog construction.

Out of scope:

- Full legacy HTML parity unless requested.

## Milestone 16: Artifact Writer Boundary

Goal:

Introduce a filesystem boundary that writes already-rendered artifacts without
changing rendering, selection, lowering, or backend behavior.

Scope:

- Output-root configuration for artifact writes.
- A write plan separate from rendered artifact content.
- Artifact path safety checks for absolute paths, parent traversal, duplicate
  paths, and paths outside the output root.
- Skip-unchanged behavior based on stable content digests.
- Dry-run behavior that reports intended writes, skips, and conflicts without
  mutating the filesystem.
- Deterministic write reports with per-artifact status, digest, path, and
  diagnostics.
- All filesystem mutation kept inside the writer boundary.

Out of scope:

- Rendering new artifact kinds.
- Changing backend manifests.
- CLI compatibility with legacy generator commands.
- Report or HTML generation.
- Compiler invocation.

Required inputs:

- `ArtifactSet` or equivalent rendered artifact collection from Milestones 10,
  11, and 14.
- Output root configuration.
- Writer options such as dry-run and skip-unchanged.

Expected outputs:

- A write plan or write report that records `would_write`, `written`,
  `skipped_unchanged`, and `failed` statuses.
- Files written under the configured output root when not in dry-run mode.
- Deterministic diagnostics for unsafe paths and write conflicts.

Validation criteria:

- No artifact can escape the output root.
- Re-running the writer with unchanged content produces skip-unchanged results.
- Dry-run produces the same planned statuses without creating or modifying
  files.
- Write reports are stable across repeated runs.
- Pure pipeline stages remain free of hidden file I/O.

Tests required:

- Unit tests for path normalization, unsafe path rejection, duplicate artifact
  detection, digest comparison, dry-run behavior, and write status ordering.
- Filesystem tests using temporary directories for first write, skip unchanged,
  changed content rewrite, and parent-directory creation.
- Diagnostic tests that assert code, severity, path, and actionable message
  text.
- Determinism test that runs the same write plan twice and compares reports.

Documentation updates:

- Update artifact-writing behavior in `docs/redesign/behavioral-spec.md` if any
  status names or diagnostics become contractual.
- Update `docs/redesign/target-architecture.md` if the writer module boundary
  changes.
- Update `docs/redesign/open-questions.md` if output compatibility questions
  become narrower.

Review risks:

- Hidden coupling between renderers and filesystem paths.
- Incomplete path safety checks.
- Nondeterministic write ordering.
- Treating skip-unchanged as rendering behavior instead of writer behavior.

Dependencies on prior milestones:

- Milestone 10 artifact model.
- Milestone 11 and Milestone 14 rendered artifact slices.
- Milestone 13 API/CLI integration if the writer is optionally exposed through
  public entry points.

## Milestone 17: Production Test-Source Planning

Goal:

Model production test-source artifacts from TSL `tests` declarations without
invoking compilers or building a full generated test framework.

Scope:

- Typed models for supported `tests` declaration shapes.
- Validation of test declarations against known primitives, types, extensions,
  and supported backend capabilities.
- Deterministic test artifact descriptors for selected primitives and candidate
  implementations.
- Connection to the existing golden harness only as a planning output.
- A clear boundary between repository unit/golden tests and generated production
  test sources.

Out of scope:

- Compiling or running generated tests.
- Full legacy test framework parity.
- Backend-specific test rendering beyond descriptors or one minimal textual
  fixture if needed to validate planning.
- Hardware autodetection.

Required inputs:

- Catalog test declarations parsed from TSL data.
- Validated catalog and selection or candidate-selection result.
- Backend manifest capabilities and artifact naming conventions.

Expected outputs:

- Typed test declaration objects or normalized test-plan records.
- Deterministic test artifact descriptors with target path, backend, primitive,
  candidate, and test intent metadata.
- Diagnostics for malformed, unsupported, or dangling test declarations.

Validation criteria:

- Test plans are deterministic for identical input.
- Unsupported test declarations produce diagnostics rather than silent drops.
- Test planning can be exercised without rendering production code or invoking a
  compiler.
- Existing golden harness remains a test infrastructure boundary, not a domain
  model.

Tests required:

- Unit tests for typed test declaration normalization and validation.
- Planning tests for primitive, type, extension, and backend filtering.
- Diagnostic tests for missing primitive references and unsupported declaration
  shapes.
- Golden or snapshot tests for stable test artifact descriptor output.

Documentation updates:

- Update `docs/redesign/domain-model.md` if the test declaration model is
  finalized.
- Update `docs/redesign/behavioral-spec.md` with supported production
  test-source planning behavior.
- Update `docs/redesign/open-questions.md` for any unsupported declaration
  shapes.

Review risks:

- Confusing tests of the generator with tests generated by the generator.
- Overfitting to legacy test planner structure.
- Generating executable tests before the planning model is stable.

Dependencies on prior milestones:

- Milestones 3 through 6 catalog parsing and validation.
- Milestones 7 and 8 selection and candidate selection.
- Milestone 10 backend manifest and artifact model.
- Milestone 12 golden harness.

## Milestone 18: Lowering Boundary And TSIL Strategy

Goal:

Establish the boundary where opaque implementation payloads become typed
lowering inputs, and decide the first safe TSIL parsing/lowering strategy.

Scope:

- Typed lowering request and lowering result models.
- Selected implementation candidates as lowering inputs without requiring
  renderers to inspect raw catalog dictionaries.
- A documented place for generation-time conditions such as
  `if<generation>(...)` to be represented and evaluated.
- One of the following TSIL strategies for the first slice:
  - Keep payloads opaque but wrap them in typed lowering candidates with
    explicit unsupported diagnostics.
  - Parse a minimal TSIL subset needed for one tiny fixture.
- A semantic or backend-neutral intermediate representation only for the
  selected strategy.
- Unsupported TSIL forms reported as diagnostics with source context when
  available.

Out of scope:

- Full TSIL grammar parity.
- Full expression evaluation.
- Full C++ or Rust code generation from TSIL.
- Optimization passes.
- Backend-specific instruction selection beyond a minimal fixture.

Required inputs:

- Candidate-selection result.
- Implementation body payloads and metadata.
- Backend or generation context needed for generation-time condition evaluation.
- Existing TSIL examples from `tsldata/` and legacy evidence.

Expected outputs:

- Lowering models that can be consumed by later backend rendering milestones.
- A documented TSIL parse/defer decision.
- Diagnostics for unsupported lowering inputs.
- Optional tiny lowered fixture if the safe subset is clear.

Validation criteria:

- Lowering has no hidden file I/O and does not mutate the catalog.
- Unsupported bodies fail predictably with diagnostics.
- Generation-time condition handling is located in lowering, not in template
  rendering.
- Renderers can depend on typed lowering results for the supported slice.

Tests required:

- Unit tests for lowering request construction, unsupported-body diagnostics,
  and deterministic result ordering.
- Tests for `if<generation>(...)` handling if any evaluation is implemented.
- Fixture tests for the minimal TSIL subset if parsing begins.
- Regression tests proving unsupported TSIL is explicit rather than silently
  ignored.

Documentation updates:

- Update `docs/redesign/pipeline-design.md` if lowering stage inputs or outputs
  change.
- Update `docs/redesign/domain-model.md` with lowering entities.
- Update `docs/redesign/design-decisions.md` with the TSIL strategy decision.
- Update `docs/redesign/open-questions.md` to close or narrow TSIL parsing
  questions.

Review risks:

- Accidentally embedding backend rendering logic in lowering.
- Treating raw implementation dictionaries as the lowering API.
- Parsing too much TSIL before the required semantics are known.

Dependencies on prior milestones:

- Milestone 8 candidate selection.
- Milestone 9 dependency discovery.
- Milestones 11 and 14 renderer slices, as evidence of what renderers currently
  lack.

## Milestone 19: Candidate-Specific Dependency Closure

Goal:

Decide and implement the next dependency-closure model if primitive-name closure
is too coarse for real generation.

Scope:

- Evaluate whether dependency edges should attach to primitive names, selected
  implementation candidates, lowered bodies, or backend-specific render jobs.
- Add a candidate-specific dependency representation if evidence shows
  primitive-name closure is insufficient.
- Preserve deterministic ordering and diagnostics for missing or cyclic
  dependencies.
- Keep dependency discovery pure and independent of filesystem writing.

Out of scope:

- Full TSIL call graph parsing unless Milestone 18 already established a safe
  subset.
- Backend code rendering changes.
- Runtime dependency management.

Required inputs:

- Existing primitive-name closure behavior from Milestone 9.
- Candidate-selection result from Milestone 8.
- Lowering model or unsupported-lowering diagnostics from Milestone 18.
- Observed dependency forms in TSL implementation payloads.

Expected outputs:

- A documented decision on primitive-name versus candidate-specific closure.
- Updated dependency closure result shape if candidate-specific closure is
  adopted.
- Diagnostics for ambiguous or unsupported dependency edges.

Validation criteria:

- Existing primitive-name closure behavior remains covered by regression tests
  or is intentionally changed with documented rationale.
- Candidate-specific closure, if adopted, does not require renderers to rescan
  raw payloads.
- Dependency cycles and missing references are reported deterministically.

Tests required:

- Unit tests for candidate-specific edge creation, closure expansion, ordering,
  and cycle diagnostics.
- Regression tests for Milestone 9 primitive-name examples.
- Determinism tests over repeated closure calculation.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the chosen dependency
  semantics.
- Update `docs/redesign/domain-model.md` if dependency entities change.
- Update `docs/redesign/open-questions.md` to close or narrow the closure
  question.

Review risks:

- Adding closure precision without enough evidence.
- Creating a second dependency model that conflicts with selection planning.
- Making dependency behavior backend-specific too early.

Dependencies on prior milestones:

- Milestone 9 dependency discovery and closure.
- Milestone 18 lowering boundary, if dependency extraction depends on lowered
  calls.

## Milestone 20: Implementation Specification Promotion

Goal:

Promote implementation metadata that is still stored as raw catalog values into
typed implementation specification objects where the generator needs stable
semantics.

Scope:

- Identify the smallest set of implementation fields needed by selection,
  lowering, dependency discovery, and backend rendering.
- Typed implementation spec models for that set.
- Validation for supported implementation forms, including list-backed variants
  if they are required by real `tsldata/`.
- Unknown or unsupported fields kept available for diagnostics and future
  extension without treating dictionaries as domain objects.

Out of scope:

- Full template rendering.
- Full TSIL parsing.
- Broad normalization of every raw TSL field.
- Compatibility wrappers around legacy shapes that are not externally required.

Required inputs:

- Validated catalog records.
- Candidate-selection implementation metadata.
- Lowering and dependency needs identified in Milestones 18 and 19.
- Open question evidence about list-backed variants and unknown fields.

Expected outputs:

- Typed implementation spec objects for supported forms.
- Deterministic diagnostics for unsupported implementation forms.
- Reduced renderer and analysis dependence on raw catalog values.

Validation criteria:

- Selection, lowering, and dependency code no longer need to interpret untyped
  implementation dictionaries for the supported slice.
- Unsupported fields are either preserved as raw extension data at the boundary
  or diagnosed consistently.
- Existing candidate-selection behavior remains compatible unless explicitly
  revised.

Tests required:

- Unit tests for implementation spec normalization and validation.
- Regression tests for existing scalar payload examples.
- Fixture tests for list-backed variants if accepted.
- Diagnostic tests for unknown, malformed, or unsupported implementation fields.

Documentation updates:

- Update `docs/redesign/domain-model.md` with implementation spec entities.
- Update `docs/redesign/requirements.md` if new supported forms become
  requirements.
- Update `docs/redesign/open-questions.md` for list-backed variants and unknown
  extra fields.

Review risks:

- Over-modeling fields before they are used.
- Losing raw evidence needed for future diagnostics.
- Introducing implicit behavior through catch-all dictionaries.

Dependencies on prior milestones:

- Milestone 4 catalog domain model.
- Milestone 8 candidate selection.
- Milestone 18 lowering boundary.
- Milestone 19 dependency closure decision.

## Milestone 21: Validation Baseline And Exploratory-Code Quarantine

Goal:

Make repository-wide validation reliable by defining what is supported
production code, what is exploratory, and which checks must pass for each area.

Scope:

- A documented validation command surface for formatting, typing, linting where
  adopted, unit tests, and golden tests.
- Quarantine rules for exploratory or incomplete code paths so broad validation
  does not fail on intentionally unsupported sketches.
- Package ownership boundaries for production implementation, exploratory
  sketches, tests, and frozen evidence.
- Validation that can run without network access, host CPU feature dependence,
  or generated output churn.

Out of scope:

- Refactoring exploratory code into production architecture.
- Fixing all historical sketches.
- Changing generator behavior.
- Requiring heavyweight tooling that is not already part of the project
  contract.

Required inputs:

- Existing package layout under `tslgen/`.
- Current unit test surface from Milestones 1 through 15.
- Redesign architecture boundaries.

Expected outputs:

- A documented validation baseline that future agents can run before review.
- Explicit quarantine rules for exploratory modules or directories.
- Stable validation expectations for implementation milestones.

Validation criteria:

- The documented validation command succeeds in the dev container.
- Quarantined code is not imported accidentally by production package entry
  points.
- Validation failures distinguish production regressions from unsupported
  exploratory sketches.

Tests required:

- Smoke test or script test for the validation command if a script is added.
- Import-boundary tests where feasible.
- Existing unit and golden tests remain runnable under the documented baseline.

Documentation updates:

- Update `AGENTS.md` and `PLANS.md` if the validation workflow changes.
- Update `docs/redesign/target-architecture.md` with quarantine boundaries if
  needed.
- Update `docs/redesign/testing-strategy.md` with the validation command
  surface.

Review risks:

- Hiding real production failures behind quarantine labels.
- Making validation depend on local environment quirks.
- Treating exploratory code as accepted architecture.

Dependencies on prior milestones:

- Milestones 1 through 15 accepted implementation and tests.

## Milestone 22: Backend Rendering Expansion

Goal:

Expand one backend beyond summary artifacts for one narrow, reviewable class of
generated output.

Scope:

- Select exactly one backend, preferably C++ unless Rust evidence makes a
  narrower slice safer.
- Select one primitive/template class whose lowering, dependencies,
  implementation specs, and artifact paths are understood.
- Render production-shaped text for that class using typed inputs, not raw
  catalog dictionaries.
- Produce golden outputs and artifact descriptors for the selected slice.
- Keep backend-specific behavior behind the backend interface.

Out of scope:

- Full C++ backend.
- Full Rust backend.
- Multiple primitive families.
- Full legacy layout compatibility.
- Production test-source rendering unless Milestone 17 has already made that
  slice explicit.

Required inputs:

- Artifact writer boundary from Milestone 16, if generated files are written
  during integration tests.
- Lowering boundary from Milestone 18.
- Dependency closure decision from Milestone 19.
- Implementation spec promotion from Milestone 20 for fields needed by the
  selected output class.
- Backend manifest and renderer interfaces.

Expected outputs:

- One backend renderer path that emits production-shaped source for a small
  supported slice.
- Golden files for the selected generated output.
- Diagnostics for selected candidates that cannot be rendered by the slice.

Validation criteria:

- The generated output is deterministic.
- Unsupported primitives or templates are excluded or diagnosed explicitly.
- The renderer does not own parsing, selection, lowering, dependency closure, or
  writing.
- Golden output changes are intentional and reviewable.

Tests required:

- Unit tests for backend rendering helpers.
- Golden-file tests for generated text.
- Integration test from source loading through rendering, and optionally writing
  if Milestone 16 is wired into the slice.
- Diagnostic tests for unsupported backend rendering inputs.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the supported backend output
  slice.
- Update `docs/redesign/target-architecture.md` if renderer interfaces evolve.
- Update `docs/redesign/open-questions.md` for remaining backend completeness
  gaps.

Review risks:

- Starting broad code generation before prerequisites are stable.
- Letting backend rendering consume raw TSL payloads directly.
- Baking legacy output layout into architecture without evidence.

Dependencies on prior milestones:

- Milestones 10, 11, and 14 backend manifest and summary rendering.
- Milestones 16, 18, 19, and 20.

## Milestone 23: Legacy-Style Reporting And HTML Output

Goal:

Decide and implement the first report/output slice beyond pure in-memory
coverage summaries.

Scope:

- Report artifact descriptors for JSON, text, or HTML output as selected by
  evidence and user need.
- Report generation that remains pure, with artifact writing delegated to the
  writer boundary.
- Coverage and generation summaries from existing pipeline results.
- A decision on whether legacy-style HTML is required for compatibility or only
  a future optional backend.

Out of scope:

- Full legacy web UI parity.
- Runtime server behavior.
- Report-driven code generation.
- Writing reports outside the artifact writer boundary.

Required inputs:

- Coverage/reporting model from Milestone 15.
- Artifact writer from Milestone 16.
- Artifact model and optional report artifact descriptors.

Expected outputs:

- One deterministic report artifact format.
- Clear API or pipeline hook for requesting report artifacts.
- Documentation of remaining report/HTML parity gaps.

Validation criteria:

- Reports are deterministic for identical pipeline results.
- Report rendering performs no filesystem writes.
- Writer behavior for report artifacts matches regular artifact behavior.
- Unsupported legacy report expectations are documented.

Tests required:

- Unit tests for report rendering.
- Golden tests for the selected report artifact format.
- Integration test that writes the report through the artifact writer.
- Diagnostic or compatibility tests for unsupported report options if exposed.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` for report artifacts.
- Update `docs/redesign/target-architecture.md` if report renderer modules are
  added.
- Update `docs/redesign/open-questions.md` for legacy-style HTML parity.

Review risks:

- Reintroducing hidden output writing inside reporting.
- Treating legacy HTML structure as architecture.
- Expanding report scope into a dashboard before generator behavior needs it.

Dependencies on prior milestones:

- Milestone 15 coverage and reporting.
- Milestone 16 artifact writer.

## Milestone 24: API And CLI Polish

Goal:

Make the public API and CLI expose the accepted post-15 capabilities coherently,
including the decision on reporting exposure through `tslgen.api`.

Scope:

- Public API decisions for writer, test planning, lowering, and reporting
  slices.
- Output-root, dry-run, skip-unchanged, report, and test-plan options only for
  capabilities implemented in earlier milestones.
- Stable result objects so API callers can inspect diagnostics, artifacts, write
  reports, coverage reports, and test plans without parsing stdout.
- Deterministic CLI output, preferably with machine-readable forms where
  practical.

Out of scope:

- Legacy CLI flag parity unless explicitly required.
- Options for unimplemented future capabilities.
- Broad backend generation.

Required inputs:

- Writer result from Milestone 16.
- Test planning result from Milestone 17.
- Lowering result from Milestone 18 if exposed.
- Reporting artifacts from Milestone 23 if implemented.
- Current `tslgen.api` and CLI integration from Milestone 13.

Expected outputs:

- Documented public API surface for post-15 features.
- CLI options and outputs for implemented writer/report/test-plan behavior.
- Clear decision on whether coverage/reporting helpers are exposed through
  `tslgen.api`.

Validation criteria:

- API callers can run the accepted vertical slices without relying on
  implementation modules.
- CLI behavior is deterministic and covered by tests.
- Public API does not expose exploratory or unstable internals.
- Unsupported combinations produce diagnostics or clear errors.

Tests required:

- API unit tests for new public functions and result fields.
- CLI integration tests for output root, dry-run, skip-unchanged, and report or
  test-plan options that are in scope.
- Backward-compatible smoke tests for existing Milestone 13 behavior where still
  supported.
- Documentation examples verified by tests where practical.

Documentation updates:

- Update `docs/redesign/target-architecture.md` public interface section.
- Update `AGENTS.md` or `PLANS.md` if executor workflow changes.
- Update `docs/redesign/open-questions.md` to close the API reporting exposure
  question.

Review risks:

- Exposing unstable internal models as public API.
- Adding CLI flags ahead of implemented behavior.
- Turning stdout into the only integration contract.

Dependencies on prior milestones:

- Milestone 13 CLI/API integration.
- Milestones 16, 17, 18, and 23 as applicable.

## Milestone 25: CLI Report/Write Interaction Regression

Goal:

Lock down the accepted Milestone 24 CLI behavior when coverage-report output and
artifact writing are requested together.

Scope:

- Add regression coverage for `--coverage-report json|html` combined with
  `--output-root`.
- Include `--no-skip-unchanged` and existing skip-unchanged behavior in the
  covered matrix.
- Document stdout/stderr behavior when both report printing and artifact writing
  occur.
- Verify that report printing remains pure and artifact writing still uses the
  writer boundary.

Out of scope:

- New CLI flags.
- Legacy CLI compatibility aliases.
- Writing coverage report artifacts automatically.
- Changing backend rendering output.

Inputs:

- Milestone 24 CLI/API facade.
- Artifact writer from Milestone 16.
- HTML/JSON report renderers from Milestones 15 and 23.
- Existing C++ scalar declaration artifact from Milestone 22.

Outputs:

- Tests and documentation that define the combined report/write CLI contract.
- Clear behavior for whether stdout contains report content, write-report lines,
  or both.
- Regression coverage for `--no-skip-unchanged` causing a rewrite instead of a
  skip when output content already exists.

Validation criteria:

- Combined report/write CLI runs are deterministic.
- Report output is not interleaved with human diagnostics.
- Files are written only under `--output-root`.
- `--dry-run` and `--no-skip-unchanged` remain invalid without `--output-root`.

Tests required:

- CLI integration test for `--coverage-report json --output-root`.
- CLI integration test for `--coverage-report html --output-root`.
- CLI integration test for repeated writes with and without
  `--no-skip-unchanged`.
- Assertion that write diagnostics still go to stderr and report output remains
  parseable on stdout.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the combined CLI contract.
- Update `docs/redesign/open-questions.md` to close or narrow the Milestone 24
  follow-up.

Review risks:

- Accidentally making stdout both machine-readable report data and write-report
  text in the same mode.
- Bypassing `io.artifact_writer` for report/write combinations.
- Expanding CLI scope into legacy compatibility too early.

Dependencies on prior milestones:

- Milestones 16, 23, and 24.

## Milestone 26: C++ Declaration Slice Expansion And Naming Contract

Goal:

Expand the accepted C++ declaration renderer by one small signature/type slice
and make the function and parameter naming contract explicit.

Scope:

- Document the C++ function naming rule for production declarations.
- Document the parameter naming rule and invalid-identifier diagnostics.
- Add one additional supported declaration slice, such as another scalar type
  for `binary` or one similarly simple scalar signature.
- Keep declarations body-free; emitted declarations must not imply TSIL lowering.

Out of scope:

- Function body rendering.
- SIMD vector type mapping.
- Wrapper generation.
- Broad template coverage.
- Rust production-shaped output.

Inputs:

- C++ declaration planner/renderer from Milestone 22.
- Typed candidate and implementation spec metadata from Milestone 20.
- Golden harness from Milestone 12.

Outputs:

- Updated C++ declaration planning policy.
- Golden C++ artifact showing the added declaration slice.
- Diagnostics for unsupported or invalid declaration names.

Validation criteria:

- Declaration output is deterministic and golden-tested.
- Unsupported candidates remain diagnostics, not silent omissions.
- Naming rules are documented before more generated signatures rely on them.
- Renderer still consumes typed candidates, not parser trees or raw catalog
  dictionaries.

Tests required:

- Unit tests for C++ function-name and parameter-name generation.
- Invalid identifier diagnostic tests.
- Golden output for the expanded declaration slice.
- Regression test proving the original scalar `binary si32` slice remains
  stable.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the naming contract.
- Update `docs/redesign/open-questions.md` for C++ naming/output compatibility.
- Update `docs/redesign/testing-strategy.md` for C++ naming golden coverage.

Review risks:

- Freezing a naming rule without enough evidence.
- Treating declaration expansion as permission to render implementation bodies.
- Introducing backend-specific naming into generic pipeline code.

Dependencies on prior milestones:

- Milestones 20, 22, and 24.

## Milestone 27: TSIL Mini-Lowering Strategy Slice

Goal:

Move from typed-opaque lowering to one tiny, safe TSIL lowering form, or record a
blocking TSIL grammar decision if no safe subset can be justified.

Scope:

- Select one minimal TSIL form from repository evidence.
- Add a small TSIL AST or parsed-operation model only for that form.
- Preserve typed-opaque diagnostics for unsupported TSIL.
- Keep generation-time condition markers represented but do not broaden
  expression evaluation beyond the selected subset.
- Document how the mini-lowering slice will grow or why it remains blocked.

Out of scope:

- Full TSIL grammar.
- Loop lowering.
- Full expression/type system.
- Backend translation-map evaluation beyond the chosen tiny form.
- C++ or Rust body rendering.

Inputs:

- Typed-opaque lowering boundary from Milestone 18.
- Implementation specs from Milestone 20.
- Current TSIL payload examples from `tsldata/`.
- Legacy TSIL grammar only as evidence.

Outputs:

- A minimal lowered representation for the selected TSIL form, or a documented
  blocker with diagnostics.
- Tests proving unsupported TSIL remains explicit.
- Updated TSIL/lowering decision notes.

Validation criteria:

- Lowering remains pure and deterministic.
- Lowered values are typed and do not expose parser-private structures.
- Unsupported TSIL cannot be rendered as production code accidentally.
- The selected subset is small enough to review independently.

Tests required:

- Unit tests for parsing/lowering the selected TSIL form.
- Diagnostic tests for malformed and unsupported nearby forms.
- Determinism tests for lowering order.
- Regression tests for existing typed-opaque unsupported diagnostics.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md`, `pipeline-design.md`, and
  `domain-model.md` with the mini-lowering shape.
- Update `docs/redesign/design-decisions.md` with the TSIL strategy refinement.
- Update `docs/redesign/open-questions.md` to narrow the long-term TSIL
  question.

Review risks:

- Letting a mini-parser become an ad hoc string-rewrite system.
- Overfitting to one fixture in a way that blocks real TSIL later.
- Evaluating generation-time conditions in renderers instead of lowering.

Dependencies on prior milestones:

- Milestones 18 and 20.

## Milestone 28: C++ Scalar Body Rendering Slice

Goal:

Render one tiny C++ function body from the accepted mini-lowered TSIL form.

Scope:

- Consume the lowered result from Milestone 27 for one scalar declaration slice.
- Emit a production-shaped inline function body for the selected C++ primitive
  class.
- Keep unsupported candidates as diagnostics.
- Keep summary metadata if it is still useful, but do not let it drive body
  semantics.

Out of scope:

- SIMD intrinsic rendering.
- Wrapper generation.
- Full translation-map support.
- Rust body rendering.
- Production test execution.

Inputs:

- C++ naming/declaration contract from Milestone 26.
- Mini-lowered TSIL result from Milestone 27.
- Backend manifest and artifact model.

Outputs:

- One deterministic C++ artifact with a real body for the supported slice.
- Golden output for the body-rendering slice.
- Diagnostics for candidates whose lowered form is unavailable or unsupported.

Validation criteria:

- Body rendering depends on lowered data, not raw TSIL text.
- Function declarations and definitions follow the documented naming contract.
- Unsupported candidates do not produce misleading stub bodies.
- Generated text is deterministic.

Tests required:

- Unit tests for C++ body rendering helpers.
- Golden test for the body-rendered artifact.
- Diagnostic tests for missing lowered body and unsupported lowered operation.
- Integration test from source fixture through lowering and rendering.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the supported C++ body slice.
- Update `docs/redesign/pipeline-design.md` if Stage 8 to Stage 10 data changes.
- Update `docs/redesign/open-questions.md` for remaining body-rendering gaps.

Review risks:

- Rendering bodies by string-splicing raw TSIL.
- Expanding from one scalar case into broad code generation.
- Hiding lowering failures behind empty or placeholder implementations.

Dependencies on prior milestones:

- Milestones 22, 26, and 27.

## Milestone 29: Production Test Rendering Slice

Goal:

Render one narrow production test source artifact from the accepted
test-source planning metadata without compiling or running it.

Scope:

- Choose one backend, preferably matching the current C++ scalar rendering
  slice.
- Render one deterministic test source artifact from planned test cases.
- Include enough metadata to trace test cases to primitive, candidate, type, and
  expected value.
- Route any file writes through the artifact writer only in integration tests.

Out of scope:

- Compiler invocation.
- Runtime test execution.
- Full generated test framework parity.
- Lane resizing, runtime-lane, or mask-manifest policy beyond the selected
  fixture.
- Rust test rendering.

Inputs:

- Production test-source planning from Milestone 17.
- Golden harness from Milestone 12.
- Artifact writer from Milestone 16.
- C++ rendering/naming context from Milestones 26 and 28, if the test references
  generated functions.

Outputs:

- A deterministic in-memory test artifact for one supported planned-test slice.
- Golden test source output.
- Diagnostics for planned test cases that cannot be rendered.

Validation criteria:

- Test rendering consumes `TestSourcePlan` or equivalent typed planning values.
- Test rendering does not invoke compilers or inspect host hardware.
- Unsupported test declarations are reported explicitly.
- Golden output is small and reviewable.

Tests required:

- Unit tests for test rendering helpers.
- Golden test for the produced test artifact.
- Diagnostic tests for unsupported planned test cases.
- Optional integration test that writes the test artifact through the writer.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` and `testing-strategy.md` with the
  supported test rendering slice.
- Update `docs/redesign/open-questions.md` for remaining generated-test policy
  gaps.

Review risks:

- Confusing generated tests with repository unit tests.
- Starting compile/run orchestration too early.
- Recreating legacy test framework structure instead of supporting observable
  test-source behavior.

Dependencies on prior milestones:

- Milestones 12, 16, 17, and 26.

## Milestone 30: Backend Manifest, Language Map, And Translation Boundary Pass

Goal:

Tighten backend manifest completeness and clarify how language type maps and
translation maps enter lowering and rendering.

Scope:

- Validate known backend IDs against supplied manifests and catalog language /
  translation declarations.
- Decide how much of `language` and `translation` catalog data is promoted into
  typed backend planning models now.
- Remove or quarantine accidental default-backend behavior that conflicts with
  the active C++/Rust first-class policy.
- Add diagnostics for missing language maps, translation maps, artifact specs,
  or unsupported backend IDs.

Out of scope:

- Full translation-map evaluation.
- New backend support.
- C17 implementation.
- Broad template rendering.

Inputs:

- Backend manifest models from Milestone 10.
- Catalog language and translation entries from current TSL data.
- Lowering strategy from Milestone 27.
- C++/Rust first-class backend decision.

Outputs:

- Clear backend manifest and language/translation-map validation policy.
- Typed models or documented deferral for language/translation data consumed by
  later lowering/rendering slices.
- Regression tests for missing or inconsistent backend metadata.

Validation criteria:

- C++ and Rust remain the active first-class backends.
- C17 evidence does not become a current implementation target accidentally.
- Backend completeness diagnostics are deterministic and actionable.
- Generic pipeline code does not grow backend-specific conditional sprawl.

Tests required:

- Manifest/catalog consistency tests.
- Missing language-map and missing translation-map diagnostic tests.
- Known-backend-ID tests for C++ and Rust.
- Regression test proving unsupported backend IDs fail before rendering.

Documentation updates:

- Update `docs/redesign/target-architecture.md` and `pipeline-design.md` for the
  backend metadata boundary.
- Update `docs/redesign/open-questions.md` around backend completeness and C17
  deferral.
- Update `docs/redesign/design-decisions.md` if default manifest derivation
  policy changes.

Review risks:

- Reintroducing C17 as an active backend by accident.
- Turning YAML or raw TSL maps into downstream architecture.
- Blocking useful C++/Rust slices on full backend completeness.

Dependencies on prior milestones:

- Milestones 10, 18, 22, and 27.

## Milestone 31: Rust Declaration Rendering Slice

Goal:

Add the first production-shaped Rust declaration/signature slice without Rust
body lowering.

Scope:

- Select a Rust declaration or trait-function signature slice equivalent in
  scale to the accepted C++ declaration slice.
- Define Rust naming and parameter rules for that slice.
- Keep TSIL payloads opaque and reject unsupported candidates with diagnostics.
- Produce deterministic Rust golden output.

Out of scope:

- Rust function bodies.
- Cargo integration.
- Rust generated tests.
- Full Rust wrapper/trait parity.
- C++ renderer changes except shared naming lessons if already documented.

Inputs:

- Rust summary backend from Milestone 14.
- Backend manifest/language boundary from Milestone 30, if accepted.
- C++ naming-contract lessons from Milestone 26.
- Implementation specs from Milestone 20.

Outputs:

- One Rust production-shaped declaration/signature slice.
- Golden Rust output.
- Diagnostics for unsupported Rust rendering inputs.

Validation criteria:

- Rust renderer remains behind the backend protocol.
- Rust output does not claim lowered bodies exist.
- The C++ renderer is not changed except for shared infrastructure that is
  justified and tested.
- Output is deterministic and golden-tested.

Tests required:

- Unit tests for Rust naming/signature helpers.
- Golden test for the Rust declaration artifact.
- Backend mismatch and unsupported-slice diagnostic tests.
- Regression test for the original Rust summary output if it remains present.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md` with the Rust declaration slice.
- Update `docs/redesign/open-questions.md` for remaining Rust rendering gaps.
- Update `docs/redesign/testing-strategy.md` for Rust golden expectations.

Review risks:

- Copying C++ assumptions into Rust where language semantics differ.
- Starting Rust body rendering before lowering supports it.
- Introducing shared renderer abstractions too early.

Dependencies on prior milestones:

- Milestones 14, 20, 26, and 30.

## Milestone 32: Candidate Dependency Reporting And API Integration

Goal:

Expose candidate-specific dependency closure through reports and stable API
inspection without changing dependency semantics.

Scope:

- Add report fields for candidate-specific dependency edges, fallbacks, and
  unresolved issues where accepted data already exists.
- Expose candidate dependency data through `PipelineResult` or public helpers if
  the current result shape hides it.
- Keep primitive-name dependency closure visible as the stable broad model.
- Preserve deterministic JSON/HTML report ordering.

Out of scope:

- New dependency extraction semantics.
- TSIL call-graph parsing.
- Backend render-job dependency scheduling.
- Changing selection behavior.

Inputs:

- Candidate-specific dependency closure from Milestone 19.
- Reporting model from Milestones 15 and 23.
- Public API facade from Milestone 24.

Outputs:

- Reports and/or API helpers that make candidate-specific dependency state
  inspectable.
- Golden or snapshot coverage for report serialization changes.
- Documentation of remaining dependency integration gaps.

Validation criteria:

- Reports remain descriptive and do not re-run dependency analysis.
- Candidate-specific unresolved issues remain visible instead of disappearing
  behind primitive-level fallbacks.
- JSON and HTML output remain deterministic.
- Public API exposes stable values, not internal mutable structures.

Tests required:

- Unit tests for dependency report rows or summary fields.
- JSON and HTML serialization tests for candidate-specific dependency data.
- API tests for accessing the accepted dependency result.
- Regression tests for primitive-level dependency coverage fields.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md`, `domain-model.md`, and
  `target-architecture.md` if result/report models change.
- Update `docs/redesign/open-questions.md` to close or narrow dependency
  reporting questions.

Review risks:

- Making report generation perform analysis.
- Freezing unstable internal dependency classes as public API.
- Hiding fallback primitive dependencies once candidate-specific data exists.

Dependencies on prior milestones:

- Milestones 19, 23, and 24.

## Milestone 33: Exploratory-Code Retirement Plan

Goal:

Decide which quarantined exploratory code should be deleted, migrated into the
accepted architecture, or kept quarantined with a specific future purpose.

Scope:

- Inventory quarantined paths from the validation profile.
- Classify each path as delete, migrate, keep-quarantined, or convert to
  evidence-only documentation.
- For migrate candidates, name the architectural boundary they would enter and
  the tests required.
- Do not perform large deletions or migrations unless a tiny, separately
  reviewable cleanup is explicitly in scope.

Out of scope:

- Broad refactoring of quarantined sketches.
- Silent deletion of behavior evidence.
- Changing production pipeline behavior.
- Replacing the validation profile wholesale.

Inputs:

- Quarantine list from Milestone 21.
- Current validation profile.
- Accepted target architecture.

Outputs:

- A documented retirement plan for quarantined paths.
- Updated open questions for any path that cannot be classified.
- Optional tiny cleanup only if it is clearly documentation-only or test-only.

Validation criteria:

- Production code still does not import quarantined paths.
- Classification is evidence-based, not a legacy migration map.
- Future executors can pick one cleanup or migration slice without guessing.

Tests required:

- Import-boundary regression tests if quarantine markers change.
- Validation-profile smoke test if the accepted surface changes.
- No tests are required for a documentation-only retirement plan beyond
  standard doc review.

Documentation updates:

- Update `docs/redesign/target-architecture.md` exploratory-code quarantine
  section.
- Update `docs/redesign/open-questions.md` with any unresolved migration
  blockers.
- Update `docs/redesign/design-decisions.md` if deletion or migration policy is
  accepted.

Review risks:

- Turning the plan into a legacy-to-new module map.
- Deleting useful evidence before replacement behavior is specified.
- Keeping broken sketches forever without an explicit reason.

Dependencies on prior milestones:

- Milestone 21.

## Milestone 34: Validation Profile Expansion And Corpus Hygiene

Goal:

Expand validation policy around accepted code, generated artifacts, and the
current `tsldata/` corpus without treating corpus churn as implementation code.

Scope:

- Decide how dirty `tsldata/` changes are reviewed, normalized, and protected by
  tests.
- Add or document a validation mode that can include selected corpus checks
  without linting TSL data as Python.
- Decide whether generated cache files, local pycache files, and generated
  artifacts need stronger ignore or cleanup policy.
- Keep validation host-independent and deterministic.

Out of scope:

- Reformatting the entire TSL corpus.
- Editing generated outputs without a generator milestone.
- Broad repository cleanup unrelated to accepted validation.
- Network-dependent CI setup.

Inputs:

- Milestone 21 validation profile.
- Current dirty-worktree observations around `tsldata/`.
- Parser/current-corpus tests from earlier milestones.
- Artifact writer behavior from Milestone 16.

Outputs:

- Documented corpus hygiene policy for future milestones.
- Optional validation-profile expansion for selected corpus checks.
- Clear guidance on generated/cache file handling.

Validation criteria:

- Validation remains reproducible in the dev container.
- Corpus checks detect parser/semantic regressions without producing output
  churn.
- Future agents know whether `tsldata/` edits are fixtures, source data, or
  generated artifacts for review purposes.

Tests required:

- Validation-profile smoke test if the command surface changes.
- Corpus regression tests for any newly protected TSL behavior.
- No host hardware, compiler, or network dependence.

Documentation updates:

- Update `docs/redesign/testing-strategy.md` and
  `docs/redesign/target-architecture.md` with corpus/validation policy.
- Update `docs/redesign/open-questions.md` for remaining dirty-worktree or data
  ownership questions.

Review risks:

- Treating broad dirty-worktree cleanup as part of a generator behavior slice.
- Letting generated artifacts churn nondeterministically.
- Making validation too broad to run reliably.

Dependencies on prior milestones:

- Milestone 21 and any accepted cleanup decisions from Milestone 33.

## Post-Milestone-34 Closure Review

Status:

Milestones 1 through 34 close the current implementation roadmap phase. Do not
define or execute a Milestone 35 until a planner selects a concrete product
goal for the next phase.

Decision:

Pause implementation and prepare stabilization/release readiness work instead
of starting another broad feature phase immediately.

Rationale:

- The accepted architecture now has explicit boundaries for source loading,
  parsing, catalog construction, validation, selection, candidate dependency
  closure, implementation-spec promotion, backend manifests, artifact planning,
  artifact writing, reporting, API/CLI integration, typed-opaque lowering,
  mini-TSIL lowering, narrow C++ rendering, narrow Rust rendering, production
  test-source planning/rendering, validation quarantine, and corpus hygiene.
- Remaining work is important but product-directional: broader TSIL semantics,
  translation-map evaluation, wider C++/Rust output, executable generated tests,
  legacy CLI compatibility, documentation/report parity, corpus normalization,
  and exploratory-code deletion.
- Those remaining areas should be planned as future phases only after a clear
  objective is chosen. Starting all of them now would couple independent
  concerns and weaken the clean redesign boundary.

Stabilization checklist:

- Run the accepted validation profile in the dev container.
- Run the unit, golden, and CLI/API tests that cover accepted Milestones 1
  through 34.
- Confirm `--coverage-report` plus `--output-root` stream behavior still matches
  the Milestone 25 contract.
- Confirm generated artifacts and golden fixtures are deterministic across two
  equivalent runs.
- Review public `tslgen.api` and CLI help for terminology that overclaims full
  backend generation, full TSIL lowering, or legacy compatibility.
- Audit dirty workspace state, especially `tsldata/**`, `.devcontainer/**`, and
  `.gitignore`, using the Milestone 34 corpus hygiene policy.
- Confirm quarantined exploratory paths remain outside accepted imports and
  validation targets.
- Update release notes or project-facing docs to describe the current state as
  an architectural foundation with narrow production-shaped slices, not a full
  legacy-generator replacement.

Deferred future phase candidates:

- Broader TSIL grammar and semantic lowering, including generation-time
  conditions such as `if<generation>(...)`.
- Translation-map evaluation and backend-owned type/intrinsic lowering.
- C++ rendering beyond the accepted scalar declaration/body slices.
- Rust body rendering and broader Rust wrapper/trait policy.
- Executable production test assertions, compile/run orchestration, and
  runtime-lane test policy.
- Legacy CLI compatibility or migration wrapper design.
- Generated documentation/report parity beyond accepted coverage artifacts.
- Focused deletion or migration of quarantined exploratory code.
- Validation-profile expansion and corpus normalization beyond current hygiene
  policy.

Recommended next action:

Use the stabilization checklist above and the release-readiness gate in
`docs/redesign/stabilization-release-checklist.md`. If a future implementation
phase is needed, start with a planner pass that chooses exactly one objective,
such as broader C++ rendering, broader TSIL lowering, executable test
generation, or legacy CLI compatibility, and then defines a small reviewable
milestone sequence for that objective.

## Functional Parity Phase: Behavior-First Frozen Parity

Status:

Planned after the accepted architecture-foundation release. This phase moves
toward functional parity with `frozen/` by selecting observable legacy behavior,
measuring it, and reproducing it through the accepted redesign architecture.

Phase principle:

`frozen/` is a behavioral oracle only. Future executors must not port legacy
modules, mirror legacy package structure, or make runtime imports from
`frozen/`. Each milestone below chooses one observable behavior and validates it
with golden, semantic, deterministic, diagnostic, and no-hidden-I/O checks as
appropriate.

Primary parity target for this phase:

C++ output parity for a small `binary/add` slice, because `frozen/out/tsl` has
concrete generated C++ output, the accepted redesign already has scalar C++
declaration/body slices, and `tsldata/primitives/arithmetic/fundamental.tsl`
contains both simple scalar TSIL and richer native TSIL for the same primitive
family. Rust, executable tests, generated docs, and broad CLI compatibility
remain planned later unless the inventory milestone changes the priority with
evidence.

## Milestone 35: Frozen Output Inventory And Golden Baseline Selection

Goal:

Inventory observable `frozen/` workflows and outputs, then choose a minimal
golden baseline for the first functional-parity implementation slices.

Scope:

- Inspect `frozen/run_all.sh`, `frozen/run_tests.py`, legacy CLI options,
  generator specs, generated `frozen/out/**` files, docs/report outputs, test
  templates, and TSIL grammar evidence.
- Classify generated output families by backend, artifact kind, template
  family, primitive family, extension, type, and required toolchain.
- Choose a small C++ parity baseline, recommended as the `binary/add` family
  with scalar `si32`/`ui32` and one native floating-point SIMD extension/type
  such as `avx2/f32`.
- Decide per selected file whether parity means byte-for-byte output, semantic
  output equivalence, or a new redesign-owned golden baseline.
- Record provenance for every selected golden fixture.

Out of scope:

- Production code changes.
- New rendering behavior.
- Full output inventory for every template family.
- Running legacy build/test workflows as part of normal validation.
- Treating C17 as an active backend.

Legacy evidence paths:

- `frozen/run_all.sh`
- `frozen/run_tests.py`
- `frozen/tsl-gen/tsl_gen/app/cli.py`
- `frozen/generator_specs/backend_cpp.yaml`
- `frozen/generator_specs/backend_rust.yaml`
- `frozen/generator_specs/tests.yaml`
- `frozen/generator_specs/wrapper_shapes.yaml`
- `frozen/out/tsl/tsl_native.hpp`
- `frozen/out/tsl/tsl_generic.hpp`
- `frozen/out/tsl/CMakeLists.txt`
- `frozen/out/tsl/tsl_flags.cmake`
- `frozen/out/reports/primitive_coverage.json`
- `frozen/out/reports/primitive_coverage.html`
- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/jinja/cpp/test_file.j2`
- `frozen/jinja/cpp/test_case.j2`

Accepted redesign inputs:

- Current `PipelineResult`, `ArtifactSet`, writer, report, lowering, backend,
  testgen, and validation boundaries.
- Functional parity gap matrix in `docs/redesign/behavioral-spec.md`.
- Parity test rules in `docs/redesign/testing-strategy.md`.

Expected outputs:

- A documented frozen-output inventory and selected-golden baseline.
- Golden fixture plan, including exact source provenance and intended parity
  level.
- Updates to open questions if any selected target cannot be judged from
  evidence.

Parity criterion:

Future executors can name one exact output slice, its legacy evidence file, its
accepted parity level, and the validation method without inspecting legacy
implementation modules.

Tests required:

- Documentation-only milestone: `git diff --check`.
- If fixture files are copied or summarized, add fixture integrity tests that
  assert provenance metadata and do not import from `frozen/`.

Golden fixtures required:

- Selected C++ excerpt or whole-file fixture for the first parity target.
- Optional manifest/report fixture excerpts if they are selected as parity
  targets.

Documentation updates:

- Update `docs/redesign/behavioral-spec.md`, `testing-strategy.md`, and
  `open-questions.md` with selected baseline decisions.

Review risks:

- Accidentally creating a legacy-module migration map.
- Choosing an output slice too large to reproduce in one milestone.
- Treating all `frozen/out` whitespace as globally required.
- Forgetting that `frozen` cannot become a runtime dependency.

Dependencies:

- Milestones 1 through 34.

## Milestone 36: C++ Output Layout And Support Preamble Parity Slice

Goal:

Reproduce the selected legacy C++ output layout and support preamble needed by
the first golden C++ parity slice.

Scope:

- Plan and render selected C++ output paths such as `tsl/tsl_native.hpp`,
  `tsl/tsl_generic.hpp`, `tsl/tsl_flags.cmake`, and `tsl/CMakeLists.txt` only
  when selected by Milestone 35.
- Render the minimum C++ support preamble required by the selected
  `binary/add` slice, such as includes, `TSL_FORCE_INLINE`, `TSL_UNROLL`,
  `VectorProcessingStyle`, basic `tsl::simd` declarations, and helper type
  aliases if selected.
- Keep support/preamble rendering backend-owned and deterministic.
- Preserve artifact writing through the accepted writer boundary.

Out of scope:

- Full `tsl_native.hpp` or `tsl_generic.hpp` parity.
- Every helper function in the legacy preamble.
- Primitive specializations beyond placeholders needed for the next slice.
- Rust output.
- CMake build execution.

Legacy evidence paths:

- `frozen/out/tsl/tsl_native.hpp`
- `frozen/out/tsl/tsl_generic.hpp`
- `frozen/out/tsl/CMakeLists.txt`
- `frozen/out/tsl/tsl_flags.cmake`
- `frozen/jinja/cpp/primary.j2`

Accepted redesign inputs:

- `BackendPlan`, `ArtifactDescriptor`, `ArtifactSet`, `ArtifactWriter`.
- C++ backend protocol and accepted renderer slices.
- Backend manifest and language-map metadata.

Expected outputs:

- Deterministic in-memory C++ artifacts with selected legacy-compatible logical
  names.
- Optional sidecar CMake metadata artifacts if selected by Milestone 35.
- Diagnostics for unsupported output-layout requests.

Parity criterion:

Selected output paths and support preamble match the Milestone 35 baseline
exactly where marked byte-for-byte, or match the documented semantic baseline
where exact compatibility was rejected.

Tests required:

- Golden tests for selected path names and preamble text.
- Artifact descriptor/order/digest determinism tests.
- Writer dry-run and skip-unchanged tests for selected paths.
- Diagnostic tests for unsupported C++ layout requests.

Golden fixtures required:

- C++ preamble fixture or excerpts selected in Milestone 35.
- Optional sidecar CMake fixtures for `tsl_flags.cmake` and `CMakeLists.txt`.

Documentation updates:

- Update behavioral output-layout expectations and any CMake sidecar parity
  decision.

Review risks:

- Recreating a template-file abstraction as the central backend model.
- Emitting support code that is not needed by the selected slice.
- Hiding file writes inside the renderer.

Dependencies:

- Milestones 16, 22, 26, 28, 30, and 35.

## Milestone 37: C++ Scalar Binary Primary/Specialization/Wrapper Parity Slice

Goal:

Reproduce one legacy-observed C++ `binary/add` scalar output slice through the
redesigned renderer.

Scope:

- Render the selected primary declaration shape for `add_binary`.
- Render scalar `simd<T, scalar>` specializations for the selected type subset,
  recommended `si32` and `ui32`.
- Render the minimal public wrapper relationship selected in Milestone 35, such
  as a `tsl::add<Vec>(...)` wrapper delegating to `tsl::detail::add_binary`.
- Consume the accepted `LoweringPlan` for `emit_return(left + right);`; do not
  inspect raw TSIL inside the renderer.

Out of scope:

- Native SIMD intrinsics.
- Masked add variants.
- Generic loop-backed add.
- Combined binary specialization templates.
- Broad wrapper-shape coverage.
- Rust rendering.

Legacy evidence paths:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/out/tsl/tsl_native.hpp`
- `frozen/jinja/cpp/primary.j2`
- `frozen/jinja/cpp/spec_binary.j2`
- `frozen/jinja/cpp/wrappers.j2`
- `frozen/generator_specs/wrapper_shapes.yaml`

Accepted redesign inputs:

- Typed catalog and implementation specs.
- Candidate selection and dependency closure.
- Lowering mini-form from Milestone 27.
- C++ naming contract from Milestones 26 and 28.
- Output layout from Milestone 36.

Expected outputs:

- Deterministic C++ primary declaration, scalar specialization, and wrapper
  artifact content for the selected `add` slice.
- Structured diagnostics for unsupported template/type/extension combinations.

Parity criterion:

For the selected scalar slice, generated C++ must match the Milestone 35
baseline exactly where exact parity is selected. If Milestone 35 selects a
semantic baseline, the generated code must expose the same public function,
detail functor, parameter order, return type, and lowered `return left + right;`
behavior.

Tests required:

- Golden tests for primary declaration, specialization, and wrapper content.
- Unit tests for wrapper naming and parameter mapping.
- Lowering-to-rendering integration test proving the renderer consumes the
  lowered model.
- Determinism test for repeated artifact generation.
- Diagnostic tests for unsupported wrapper/template/type requests.

Golden fixtures required:

- Selected `add_binary` primary/specialization/wrapper fixture or excerpt.

Documentation updates:

- Update C++ rendering behavior with the selected parity contract.
- Narrow any C++ naming/wrapper open questions with accepted decisions.

Review risks:

- Copying legacy templates instead of modeling primary/specialization/wrapper
  concepts.
- Treating `wrapper_shapes.yaml` as downstream architecture instead of evidence.
- Letting raw TSIL leak into renderer code.

Dependencies:

- Milestones 27, 28, 35, and 36.

## Milestone 38: TSIL Intrinsic Compose Lowering Slice

Goal:

Add the next minimal TSIL lowering form required for a native C++ `binary/add`
parity target.

Scope:

- Parse and lower `emit_return(intrin_compose<add>(left, right));` for one
  backend-neutral intrinsic-call return form.
- Resolve the backend, extension, and type context only as needed for the
  selected C++ floating-point `binary/add` native slice.
- Model the lowered result as a typed intrinsic-call return, not backend text.
- Keep unsupported `intrin_compose` metadata, generation-time suffixes,
  primitive calls, loops, variables, and type expressions diagnostic-producing
  unless explicitly selected.

Out of scope:

- Full TSIL grammar.
- Integer intrinsic suffix inference.
- `value<generation>(...)`, `type<generation>(...)`, `type<backend>(...)`.
- `call<primitive=...>` semantic lowering.
- Loops, variables, arrays, masks, casts, and generation-time `if`.
- Rust lowering.

Legacy evidence paths:

- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/tsl-gen/tsl_gen/tsil_engine/compiler.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/calls.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/generation_ifs.py`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`

Accepted redesign inputs:

- Lowering boundary and mini-TSIL model.
- Backend metadata boundary with typed language/translation maps.
- Selected candidate implementation specs.

Expected outputs:

- Typed lowered intrinsic-call return statements for the selected form.
- Unsupported diagnostics for nearby but unsupported TSIL forms.

Parity criterion:

The selected TSIL source lowers to a stable, backend-neutral intrinsic-call
model that contains enough information for the C++ backend to render the native
`add` specialization selected by Milestone 39, without copying legacy string
rewrite passes.

Tests required:

- Unit tests for accepted intrinsic-compose lowering.
- Negative tests for unsupported metadata, generation-time suffix, calls, loops,
  and variables.
- Source-location diagnostic tests when malformed TSIL is tied to source spans.
- Determinism tests for lowering results.

Golden fixtures required:

- Minimal TSIL fixtures derived from `fundamental.tsl`, not large legacy output
  files.

Documentation updates:

- Update lowering behavior, domain model if new lowered IR nodes are added, and
  open questions around TSIL scope.

Review risks:

- Recreating the legacy pass pipeline.
- Emitting C++ text from lowering.
- Accidentally accepting more TSIL syntax than tested.

Dependencies:

- Milestones 18, 20, 27, 30, and 35.

## Milestone 39: C++ Native Intrinsic Binary Parity Slice

Goal:

Render one native C++ SIMD `binary/add` specialization from the typed intrinsic
lowering model.

Scope:

- Render one selected native extension/type pair, recommended `avx2/f32` or
  `avx2/f64`, using the Milestone 38 lowered intrinsic-call return.
- Use typed backend metadata to map selected language types and intrinsic naming
  only for the selected form.
- Preserve the primary/specialization/wrapper relationship accepted in
  Milestone 37.

Out of scope:

- Integer intrinsic suffix generation.
- All AVX/SSE/AVX512 add variants.
- Masked add.
- Generic loop-backed add.
- Rust native rendering.
- Compiler execution.

Legacy evidence paths:

- `frozen/out/tsl/tsl_native.hpp`
- `frozen/jinja/cpp/spec_binary.j2`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/types/types_cpp.tsl`

Accepted redesign inputs:

- C++ output layout and wrapper parity from Milestones 36 and 37.
- TSIL intrinsic-compose lowering from Milestone 38.
- Backend metadata boundary from Milestone 30.

Expected outputs:

- Deterministic C++ native `add_binary<simd<float, avx2>>` or equivalent
  selected specialization.
- Diagnostics for unsupported native type/extension/intrinsic combinations.

Parity criterion:

Generated native specialization matches the Milestone 35 selected C++ baseline
for function shape, return type, parameter order, native-supported metadata,
and intrinsic call semantics. Byte-for-byte whitespace parity is required only
if Milestone 35 selected exact output parity for this excerpt.

Tests required:

- Golden test for selected native specialization.
- Unit tests for selected intrinsic name resolution.
- Determinism test for repeated rendering.
- Diagnostic tests for unsupported intrinsic compose forms.

Golden fixtures required:

- Selected native `add_binary` specialization excerpt.

Documentation updates:

- Update C++ rendering and lowering behavior with the selected native parity
  contract.

Review risks:

- Making translation maps executable globally before their semantics are
  modeled.
- Hard-coding `avx2`/`f32` in generic rendering paths.
- Expanding into integer suffix handling without a separate milestone.

Dependencies:

- Milestones 30, 35, 36, 37, and 38.

## Milestone 40: Generated C++ Test Parity Slice

Goal:

Render one legacy-style C++ generated test source for the selected `binary/add`
parity target.

Scope:

- Render one C++ test source fixture for a selected `add` test case, recommended
  `add_i32_basic`.
- Use typed `TestSourcePlan` data and backend-owned test rendering.
- Include the minimum legacy-observed structure needed for the selected test:
  support header include, generated output header include, `gtest` include,
  deterministic test function, and `TEST(...)` registration.
- Keep compile/run orchestration out of scope unless a later milestone accepts
  toolchain requirements.

Out of scope:

- Full generated C++ test framework parity.
- Rust generated tests.
- SVE/runtime-lane tests.
- Generic/oneAPIfpga size expansion beyond selected fixtures.
- Downloading or vendoring googletest.
- Executing generated tests.

Legacy evidence paths:

- `frozen/generator_specs/tests.yaml`
- `frozen/jinja/cpp/test_file.j2`
- `frozen/jinja/cpp/test_case.j2`
- `frozen/tsl-gen/tsl_gen/backend/tests/planner.py`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/run_tests.py`

Accepted redesign inputs:

- `TestSourcePlan` from Milestone 17.
- Metadata-style production test rendering from Milestone 29.
- C++ output/header naming from Milestones 36 and 37.

Expected outputs:

- Deterministic C++ test artifact for one selected generated test.
- Diagnostics for unsupported test kinds or missing planned metadata.

Parity criterion:

The selected test artifact either matches the Milestone 35 legacy fixture
exactly, or preserves the same observable test behavior: same declared test
name, selected primitive, inputs, expected values, wrapper call, and assertion
semantics.

Tests required:

- Golden test for selected C++ generated test source.
- Unit tests for planned-case to test-rendering metadata conversion.
- Diagnostic tests for unsupported test kinds and missing metadata.
- Determinism test for repeated test rendering.

Golden fixtures required:

- Selected legacy-style C++ test source fixture or excerpt.

Documentation updates:

- Update test generation behavior and testing strategy with the selected parity
  contract.

Review risks:

- Turning repository unit-test helpers into production generator logic.
- Starting compile/run orchestration too early.
- Reintroducing host toolchain or network dependencies into default tests.

Dependencies:

- Milestones 17, 29, 35, 36, and 37.

## Milestone 41: CLI Workflow Compatibility Slice

Goal:

Implement one documented legacy-compatible workflow through the redesigned CLI
without cloning the legacy CLI wholesale.

Scope:

- Select one workflow from Milestone 35, recommended:
  `python -m tsl_gen --emit-lang cpp --input <file> --templates binary
  --primitives add --output <path>`.
- Provide a redesigned CLI compatibility command, alias, or adapter that maps
  the selected workflow onto `PipelineConfig`, accepted selection inputs,
  rendering, and artifact writing.
- Preserve the accepted report/write stdout/stderr contract for all existing
  options.
- Emit structured diagnostics for unsupported legacy flags or workflows.

Out of scope:

- Full `run_all.sh` replacement.
- Build/test/run orchestration.
- All legacy flags.
- Hidden host CPU reads except through explicit accepted autodetection options.
- Import compatibility with `tsl_gen` internals.

Legacy evidence paths:

- `frozen/tsl-gen/tsl_gen/app/cli.py`
- `frozen/tsl-gen/tsl_gen/cli.py`
- `frozen/run_all.sh`
- `frozen/run_tests.py`

Accepted redesign inputs:

- Public API and CLI facade.
- Artifact writer boundary.
- Selected C++ parity artifact from Milestones 36 through 39.

Expected outputs:

- One documented compatibility workflow.
- CLI diagnostics for unsupported compatibility requests.
- No runtime dependency on `frozen`.

Parity criterion:

For the selected command shape, users can request the same observable outcome:
selected backend, input, primitive/template filter, and output file generation.
Argument spelling may differ only if the compatibility decision says the exact
legacy spelling is not required for this slice.

Tests required:

- CLI integration test for the selected compatibility workflow.
- stdout/stderr regression tests for combined reporting/writing behavior.
- Diagnostic tests for unsupported legacy flags.
- No-hidden-I/O test using a temporary output root.

Golden fixtures required:

- CLI output or generated artifact fixture selected by Milestone 35.

Documentation updates:

- Update CLI behavior with supported and unsupported compatibility claims.
- Update open questions for remaining legacy workflow gaps.

Review risks:

- Creating a broad compatibility wrapper around bad legacy abstractions.
- Breaking accepted modern CLI behavior.
- Implied support for `run_all.sh` build/test/run flows.

Dependencies:

- Milestones 24, 25, 35, and at least one accepted C++ parity rendering slice.

## Milestone 42: Legacy Coverage JSON Adapter Slice

Goal:

Provide one deterministic report-adapter slice for legacy-style primitive
coverage JSON when selected as a parity target.

Scope:

- Render a legacy-style row-oriented coverage JSON artifact from accepted report
  data for a selected subset.
- Include fields evidenced by `frozen/out/reports/primitive_coverage.json`,
  such as primitive, primitive class, template, type, extension, language,
  `has_tsil`, `has_intrinsic`, `has_lang_block`, and `effective_present`.
- Route report files through the artifact model and writer boundary.

Out of scope:

- Full HTML documentation site parity.
- Exact legacy HTML parity.
- Re-running analysis during report rendering.
- Changing coverage semantics to hide accepted diagnostic data.

Legacy evidence paths:

- `frozen/out/reports/primitive_coverage.json`
- `frozen/out/reports/primitive_coverage.html`
- `frozen/tools/report_primitive_coverage.py`
- `frozen/tools/primitive_coverage_html.py`

Accepted redesign inputs:

- `PipelineCoverageReport` and candidate dependency report DTOs.
- HTML and JSON report renderers from Milestones 15, 23, and 32.
- Artifact writer boundary.

Expected outputs:

- Deterministic legacy-style JSON report artifact for a selected subset.
- Documentation of fields intentionally absent or semantically different.

Parity criterion:

Selected legacy-style JSON rows match the documented field names and stable
ordering from the Milestone 35 baseline. Full row count parity is required only
after a future milestone broadens backend/template coverage.

Tests required:

- Golden JSON adapter test for selected rows.
- Determinism test for row/key ordering.
- Diagnostic or unavailable-section tests when required source data is missing.

Golden fixtures required:

- Selected row excerpt from `frozen/out/reports/primitive_coverage.json`.

Documentation updates:

- Update coverage/reporting behavior and open questions around documentation
  parity.

Review risks:

- Freezing legacy report semantics that conflict with accepted report DTOs.
- Making report rendering re-run pipeline stages.
- Claiming full report parity before backend coverage exists.

Dependencies:

- Milestones 15, 23, 32, and 35.

## Recommended Next Milestone

Start with Milestone 35. The smallest useful step toward `frozen/` parity is to
select measured golden baselines and parity levels before implementing more
generation. Without that inventory, executors would either overfit to legacy
files wholesale or choose output slices whose compatibility cannot be reviewed.
