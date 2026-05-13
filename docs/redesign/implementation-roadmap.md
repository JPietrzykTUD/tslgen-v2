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

Roadmap correction for TSIL/backend drift:

The native C++ parity path must not grow backend-local type or intrinsic lookup
tables. Evidence from `tsldata/primitives/**.tsl` shows that
`intrin_compose<...>` is only one helper among many TSIL forms that require
semantic lowering.

Current-state policy:

- Do not revert Milestone 39 solely because it used a narrow renderer-local
  intrinsic mapping for the selected `avx2/f32` output.
- Treat Milestone 39 as a transitional parity spike that proves the observable
  native C++ output, not as the architecture for future native rendering.
- Do not expand the Milestone 39 hardcoded pattern to additional intrinsics,
  types, extensions, backends, or helper forms.
- Milestone 40 must preserve the selected M39 output while relocating
  intrinsic/type resolution behind the lowering/translation boundary.
- Generated-test, CLI workflow, coverage-adapter, Rust-body, and broader C++
  parity work remain deferred until the M40 boundary correction is accepted.

Staged lowering/translation contract:

1. TSIL parsing/lowering produces typed helper IR.
2. Generation-time semantic lowering resolves `if<generation>(...)`,
   `type<generation>(...)`, and `value<generation>(...)` against an explicit
   generation context before backend translation runs.
3. Backend translation receives typed semantic values such as resolved type
   tags, selected extension metadata, primitive attributes, and ordered helper
   arguments. It does not evaluate raw generation-time TSIL text.
4. Backend-scoped forms such as `type<backend>(...)` and
   `value<backend>(...)` are translation requests whose inputs must already be
   typed semantic values.
5. Backend renderers receive backend-call IR or equivalent translated values
   and format text only.

### TSIL/Lowering Helper Inventory Matrix

| Observed helper/form | Evidence path | Apparent semantics | Required context | Lowered IR concept | Backend/data dependency | Parity priority | Proposed milestone | Validation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct scalar return `emit_return(left + right);` | `tsldata/primitives/arithmetic/fundamental.tsl` | Return a binary expression over declared primitive parameters. | Primitive parameter names and selected candidate. | `TsilReturnStatement(TsilBinaryExpression("+", ...))` | None beyond backend expression rendering. | `required-now`, already accepted for scalar parity | M27/M28/M37 retained | Lowering unit tests and C++ scalar golden output. |
| Simple `intrin_compose<add>(left, right)` | `tsldata/primitives/arithmetic/fundamental.tsl` | Compose a target intrinsic from operation name plus default backend prefix/suffix for selected extension and type. | Backend ID, extension, type tag, language type map, intrinsic style, primitive parameters. | `TsilIntrinsicComposeExpression` plus backend-call IR after translation. | `tsldata/detail/lang/types/types_cpp.tsl`, `tsldata/detail/lang/translate_cpp.tsl`, `tsldata/extensions/extension.tsl` | `required-for-selected-parity-slice` | M38/M39 transitional, M40 correction | Data-driven `add + avx2 + f32 -> _mm256_add_ps` fixture with no renderer-owned lookup table after M40. |
| `intrin_compose` modifiers: `prefix=...`, `suffix=...`, `infix=...`, `post=...`, `immediate(n)=...` | `tsldata/primitives/arithmetic/fundamental.tsl`, `tsldata/primitives/bitwise/shifts.tsl`, `tsldata/primitives/conversion/repr_change.tsl`, `tsldata/primitives/load_store/rnd_access.tsl`, `frozen/tsl-gen/tsl_gen/resolver/render_support.py` | Compose backend intrinsic names and immediate metadata from explicit and default modifier fields. | Modifier parser, already-resolved generation-time type/value inputs, backend intrinsic naming policy. | `IntrinsicComposeModifier`, `BackendIntrinsicName`, optional immediate metadata. | Translation/type maps, extension intrinsic style, type suffix rules. | `required-later`; default prefix/suffix is `required-for-selected-parity-slice` | M40 for selected generation-free default form; later helper slices after generation-time semantic lowering for full modifier semantics | Unit tests for modifier parsing, deterministic composition, unsupported modifier diagnostics, and proof that generation-time expressions are resolved before backend translation. |
| `if<generation>(...)` / `else<generation>` | `tsldata/primitives/load_store/load.tsl`, `tsldata/primitives/load_store/store.tsl`, `tsldata/primitives/bitwise/shifts.tsl`, `frozen/tsl-gen/tsl_gen/tsil_engine/passes/generation_ifs.py` | Select a TSIL branch at generation time based on attributes, type predicates, or vector metadata. | Generation context: selected type, extension, primitive attributes, vector metadata, type predicates. | `TsilGenerationIf` or already-pruned statement list with branch provenance. | Translation values such as type predicates and primitive attributes. | `required-later`, `required-for-selected-parity-slice` only when a selected output uses a generation branch | M41 selection or later numbered helper slice | Branch selection fixtures, unsupported condition diagnostics, renderer non-evaluation tests. |
| `type<generation>(...)`, `value<generation>(...)`, `type<backend>(...)`, `value<backend>(...)` | `tsldata/primitives/**.tsl`, `tsldata/detail/lang/translate_cpp.tsl`, `frozen/tsl-gen/tsl_gen/tsil_engine/passes/types.py`, `frozen/tsl-gen/tsl_gen/tsil_engine/passes/values.py` | Resolve semantic types/values first, then translate backend spellings or suffixes from typed values. | Type tag, extension, vector/register metadata, primitive attributes, backend language map, translation map. | `TsilGenerationTypeQuery`, `TsilGenerationValueQuery`, `ResolvedGenerationValue`, `BackendTypeRequest`, `BackendValueRequest`. | Typed language maps and translation snippets. | `required-later`; selected C++ type spelling is `required-for-selected-parity-slice` | M40 for selected generation-free C++ type spelling; M41 defines generation-time-before-backend contract; later numbered slice implements selected query forms | Type/value query fixtures, missing map diagnostics, no renderer-owned resolution, and tests that backend translation never receives unresolved `type<generation>`/`value<generation>` nodes. |
| `call<primitive=...>` and `call<primitive=@self[...] ...>` | `tsldata/primitives/arithmetic/fundamental.tsl`, `tsldata/primitives/misc/conflict.tsl`, `tsldata/primitives/load_store/load.tsl` | Call selected primitive implementations or wrappers; may also define dependency edges. | Catalog, selected candidates, type/extension arguments, attributes, dependency closure. | `TsilPrimitiveCall` plus dependency/render-call metadata. | Selection and dependency closure; backend call translation. | `required-later` | Future TSIL call/dependency milestone after M41 chooses the next helper family | Candidate-specific call fixtures, fallback diagnostics, no string-only dependency semantics. |
| `loop<range>`, `loop<unroll>`, `var<...>`, `let<type>`, assignment, indexing | `tsldata/primitives/arithmetic/fundamental.tsl`, `tsldata/primitives/io/out.tsl`, `tsldata/primitives/misc/conflict.tsl` | Structured statements for generic fallback implementations and helper code. | Statement parser, scoped symbols, type/value evaluation, backend statement translation. | `TsilLoop`, `TsilVariable`, `TsilLetType`, assignment/index expressions. | Translation entries for loops, vars, arrays, and type aliases. | `required-later` | Future generic-body lowering phase | Statement-level AST fixtures and unsupported-scope diagnostics. |
| `cast<...>`, `io<...>`, `mem<...>`, `pack<...>`, `seq<...>`, `algo<...>` | `tsldata/primitives/io/out.tsl`, `tsldata/primitives/bitwise/bit_counts.tsl`, `tsldata/detail/lang/translate_cpp.tsl` | Backend-language helper operations for casts, IO, memory, tuples, sequences, and algorithms. | Backend translation map and typed argument semantics. | Helper-call IR keyed by semantic helper family. | Translation snippets such as `cast_static`, `io_write`, `mem_copy`, `seq_make`. | `required-later` | Future helper-family milestones | Translation helper fixtures and missing-entry diagnostics. |
| Direct `intrin<...>` calls and placeholder tokens such as `{{ ?i? }}` | `tsldata/primitives/arithmetic/horizontal.tsl`, `tsldata/primitives/bitwise/shifts.tsl`, `frozen/tsl-gen/tsl_gen/tsil.lark` | Call an explicitly named backend intrinsic, sometimes with type suffix placeholders. | Backend, type tag, extension, placeholder resolver, argument expression lowering. | `BackendIntrinsicCall` with literal or resolved name. | Intrinsic suffix/type rules and backend expression rendering. | `required-later` | Future direct-intrinsic milestone | Exact-name and placeholder diagnostics; no raw string splice into renderer. |

### Backend Drift Risk Matrix

| Current behavior | File/evidence path | Why it is risky | Correct boundary | Proposed fix milestone | Validation |
| --- | --- | --- | --- | --- | --- |
| Native C++ intrinsic selected by local tuple table, e.g. `("add", "avx2", "f32") -> "_mm256_add_ps"`. | `tslgen/src/tslgen/backends/cpp/scalar_binary.py` | Encodes backend translation in renderer-owned Python data and will grow into an x86 intrinsic registry. | Lowering/translation service composes backend calls from typed TSIL IR plus `tsldata` metadata; renderer renders a backend call IR. | M40 | Test that selected native add is produced through translation metadata, and add a regression preventing new renderer-owned intrinsic lookup tables for the slice. |
| C++ scalar and native type spellings are local renderer maps. | `tslgen/src/tslgen/backends/cpp/scalar_binary.py`, `tsldata/detail/lang/types/types_cpp.tsl` | Type spellings are part of language-map data, not renderer policy. Local maps make future backends and type groups inconsistent. | Backend language-map access through typed metadata passed into lowering/render planning. | M40 | Type-map fixture uses `types_cpp.tsl`; missing/unknown type diagnostics occur before rendering. |
| A file named `scalar_binary.py` now owns native SIMD specializations. | `tslgen/src/tslgen/backends/cpp/scalar_binary.py` | Naming and ownership encourage mixing scalar body rendering, native translation, and wrapper rendering. | Separate scalar rendering from backend-call rendering or rename around the supported binary parity slice once boundary is corrected. | M40 or focused follow-up | Review confirms native renderer consumes backend-call IR and does not use scalar-only planning assumptions. |
| Mini TSIL parser recognizes only a regex-shaped `intrin_compose<add>` without modifier metadata. | `tslgen/src/tslgen/lowering/boundary.py`, `tsldata/primitives/arithmetic/fundamental.tsl`, `tsldata/primitives/load_store/load.tsl` | It cannot represent the modifiers that make TSIL helper lowering general enough for real parity. | Lowering-owned helper parser/model with explicit modifier fields and diagnostics. | M38 and M40, with broader modifier slices selected later | Modifier inventory, unsupported-modifier diagnostics, and typed model tests. |
| Golden tests may lock in hardcoded renderer output as if it were the intended architecture. | `tslgen/tests/unit/test_cpp_backend_vertical_slice.py`, native parity fixtures | Tests could protect the wrong boundary by asserting `_mm256_add_ps` without asserting data-driven translation. | Golden tests assert output plus unit tests assert the translation source and renderer non-ownership. | M40 | Golden parity remains, but a lower-level test proves `tsldata` metadata drove composition. |

### Roadmap Change Matrix

| Current/proposed milestone | Current intent | Issue discovered | Action | Revised milestone/deferred target | Reason |
| --- | --- | --- | --- | --- | --- |
| M35 Frozen Output Inventory And Golden Baseline Selection | Select first parity target. | No boundary issue; selected baseline remains useful. | Kept. | M35 unchanged. | Parity work still needs measured behavior before implementation. |
| M36 C++ Output Layout And Support Preamble Parity Slice | Render selected path and preamble. | Does not require intrinsic translation. | Kept. | M36 unchanged. | Layout/preamble can remain renderer-owned support output. |
| M37 C++ Scalar Binary Primary/Specialization/Wrapper Parity Slice | Render scalar add primary/specialization/wrapper from lowered scalar add. | Does not require native translation. | Kept. | M37 unchanged. | Scalar slice validates wrapper/body shape before native translation. |
| M38 TSIL Intrinsic Compose Lowering Slice | Lower `intrin_compose<add>(left, right)` into typed helper IR. | Narrow but useful; not enough by itself to authorize renderer-owned intrinsic naming. | Kept as predecessor. | M38 remains accepted if already reviewed. | It provides the input M40 needs. |
| M39 C++ Native Intrinsic Binary Parity Slice | Render native `avx2/f32` output. | Used a local renderer mapping for intrinsic/type resolution. | Keep as transitional; do not revert by default; do not expand. | M40 boundary correction follows immediately. | Reverting would lose useful parity evidence; correction can preserve output while fixing architecture. |
| Old M40 Generated C++ Test Parity Slice | Render a legacy-style generated C++ test. | Depends on stable generated function/wrapper output; not urgent before native translation correction. | Deferred. | Future generated-test parity milestone after M40. | Test parity should validate accepted generated APIs, not a drifting backend. |
| Old M41 CLI Workflow Compatibility Slice | Add one legacy-compatible generation workflow. | Depends on corrected rendering/output behavior. | Deferred. | Future CLI workflow milestone after M40 or later selected output slice. | CLI compatibility should not expose unstable native rendering. |
| Old M42 Legacy Coverage JSON Adapter Slice | Add legacy-style coverage JSON adapter. | Independent but lower priority than correcting generation semantics. | Deferred. | Future report parity milestone after generation boundary correction. | Reporting adapter should not distract from backend/lowering boundary repair. |

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

Milestone 35 selected baseline:

- The inventory and baseline decision are recorded in
  `docs/redesign/frozen-parity-baselines.md`.
- The first parity target is C++ `binary/add` output in logical path
  `tsl/tsl_native.hpp`.
- The selected scalar baseline is `add_binary` for `si32` and `ui32`, grounded
  in `frozen/out/tsl/tsl_native.hpp` excerpts and
  `tsldata/primitives/arithmetic/fundamental.tsl`.
- The selected native baseline is `avx2/f32` `add_binary`, grounded in the
  `_mm256_add_ps(left, right)` excerpt and the current `intrin_compose<add>`
  source data.
- No fixture files are copied by Milestone 35; future parity milestones create
  fixtures from the recorded provenance when they consume the baseline.

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
- Milestone 36 selected `tsl/tsl_native.hpp` only. `tsl/CMakeLists.txt` and
  `tsl/tsl_flags.cmake` remain deferred evidence until a later slice can derive
  required native-extension flags from accepted rendering behavior.

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
- M36 adds
  `tslgen/tests/fixtures/golden/parity/cpp/native_layout_excerpt.hpp` with a
  companion provenance file; no sidecar fixture is selected in this slice.

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
- Milestone 37 selects the redesign-owned exact golden fixture
  `tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.hpp` and records
  provenance in the companion `.provenance.md` file.

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
- M37 adds
  `tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.hpp` with
  fixture provenance; native intrinsic and sidecar fixtures remain deferred.

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

Status:

Retained as the accepted predecessor for the native C++ parity slice.

Goal:

Lower exactly the selected TSIL form
`emit_return(intrin_compose<add>(left, right));` into typed helper IR without
rendering backend text.

Scope:

- Parse and lower the no-modifier `intrin_compose<add>` return shape for the
  selected `binary/add` parity target.
- Validate declared parameter references, arity, unsupported intrinsic names,
  malformed nearby syntax, and unknown operands.
- Represent the result as typed helper data, not C++ source.
- Keep modifier metadata, generation-time suffixes, primitive calls, loops,
  variables, direct `intrin<...>` calls, and generation-time branches
  diagnostic-producing.

Out of scope:

- Backend intrinsic name composition.
- Full TSIL grammar.
- Full modifier expression evaluation.
- Primitive-call semantic lowering.
- Rust lowering.

Evidence paths:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/out/tsl/tsl_native.hpp`

Accepted redesign inputs:

- Typed implementation specs from Milestone 20.
- Typed-opaque lowering boundary from Milestone 18.
- Direct scalar return lowering from Milestone 27.
- Selected C++ parity baseline from Milestone 35.

Expected outputs:

- Lowered helper IR for the selected no-modifier `intrin_compose<add>` return.
- Deterministic unsupported-form diagnostics for adjacent helper shapes.
- No backend intrinsic name, backend type spelling, or rendered C++ text.

Parity criterion:

The selected TSIL source form is represented as typed helper data with the same
operation name and argument order as the legacy-observed `avx2/f32` add body.
It does not yet claim backend intrinsic-name parity.

Tests required:

- Lowering tests for the selected helper form.
- Unsupported-form diagnostics for nearby syntax.
- Deterministic lowered IR.
- No backend text emitted from lowering.

Golden fixtures required:

- Minimal TSIL/lowering fixtures only; no generated C++ golden is owned by this
  milestone.

Documentation updates:

- Record that this milestone enables M39/M40 but does not authorize
  renderer-local intrinsic composition.

Review risks:

- Treating the bare helper parser as a general TSIL parser.
- Emitting `_mm256_add_ps` or any backend text from lowering.
- Silently accepting modifier syntax that is not modeled yet.

Dependencies:

- Milestones 18, 27, 35, and 37.

## Milestone 39: Transitional C++ Native Intrinsic Binary Parity Slice

Status:

Accepted only as a transitional parity slice if already implemented/reviewed.
Do not revert solely because this slice used a narrow renderer-local mapping.
Do not expand this pattern.

Goal:

Render the selected native C++ `binary/add` `avx2/f32` specialization and
preserve the observable parity output selected by Milestone 35.

Scope:

- Render one selected native extension/type pair: `avx2/f32`.
- Consume the Milestone 38 lowered `intrin_compose<add>` helper result.
- Preserve the primary/specialization/wrapper relationship accepted by
  Milestone 37.
- Produce the selected `_mm256_add_ps(left, right)` observable output.
- Record that any renderer-local intrinsic/type mapping in this slice is a
  correction target for Milestone 40.

Out of scope:

- Additional native intrinsics, extensions, or type tags.
- Integer suffix generation.
- Masked add.
- Generic loop-backed add.
- Rust native rendering.
- Compiler execution.
- Treating renderer-local intrinsic maps as architecture.

Evidence paths:

- `frozen/out/tsl/tsl_native.hpp`
- `frozen/jinja/cpp/spec_binary.j2`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/types/types_cpp.tsl`

Accepted redesign inputs:

- Output layout and scalar wrapper/body shape from Milestones 36 and 37.
- Selected intrinsic-compose helper lowering from Milestone 38.
- Selected native C++ parity baseline from Milestone 35.

Expected outputs:

- Deterministic selected native C++ specialization for `simd<float, avx2>`.
- Selected native golden fixture and provenance.
- Structured diagnostics for unsupported native rendering cases.
- Explicit documentation that local intrinsic/type mapping is temporary debt.

Parity criterion:

The selected generated output exposes the expected `detail::add_binary`
specialization and public wrapper behavior and emits
`_mm256_add_ps(left, right)` for `avx2/f32`. This criterion is transitional:
it proves observable output only, not the final translation boundary.

Tests required:

- Golden test for the selected native specialization.
- Diagnostics for unsupported native type, extension, intrinsic, missing
  lowering, and unsupported lowered-expression inputs.
- Deterministic output.

Golden fixtures required:

- `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_f32_excerpt.hpp`
  with companion provenance.

Documentation updates:

- Mark this milestone transitional in the roadmap, behavioral spec, parity
  baseline, testing strategy, and open questions.

Dependencies:

- Milestones 35, 36, 37, and 38.

Review risks:

- Mistaking this transitional slice for permission to add more renderer-local
  intrinsic mappings.
- Hiding the need for data-driven translation behind a passing golden test.

## Milestone 40: Backend Translation Boundary Correction

Goal:

Preserve the Milestone 39 observable C++ native output while moving selected
intrinsic/type resolution out of the renderer and behind a typed
lowering/translation boundary.

Scope:

- Introduce the smallest typed translation/composition service needed for the
  selected `intrin_compose<add>` `avx2/f32` fixture.
- Treat the selected M40 fixture as generation-free: any nested
  `if<generation>(...)`, `type<generation>(...)`, or
  `value<generation>(...)` expression remains unsupported until a generation
  semantic-lowering slice resolves it before translation.
- Model intrinsic composition as data: base name, ordered arguments, selected
  backend, selected extension, selected type tag, and optional modifier fields.
- Load or promote the selected C++ type spelling from
  `tsldata/detail/lang/types/types_cpp.tsl` instead of relying on a native-only
  renderer map.
- Resolve the selected backend intrinsic call from typed `tsldata` metadata and
  selected context, producing backend-call IR or an equivalent typed translated
  call value.
- Require backend translation inputs to be typed semantic values; do not allow
  backend translation to parse or evaluate raw generation-time TSIL helpers.
- Adapt the current C++ native renderer path so the selected native
  specialization renders that already-resolved backend call.
- Remove, bypass, or quarantine the selected renderer-local intrinsic lookup so
  future cases cannot be added there accidentally.
- Keep the M39 golden output stable unless the corrected architecture reveals a
  documented parity mistake.

Out of scope:

- Adding new generated output beyond the M39 `avx2/f32` slice.
- Full translation-map evaluation.
- Full TSIL grammar.
- Full modifier expression evaluation for `suffix=value<backend>(...)`,
  `post=...`, `infix=...`, `prefix=...`, or `immediate(n)=...`.
- Generation-time branch evaluation.
- Generation-time type/value query evaluation, including nested
  `type<generation>(...)` or `value<generation>(...)` inside backend modifier
  expressions.
- Primitive-call semantic lowering.
- Rust native rendering.
- Generated-test, CLI workflow, or report parity.

Evidence paths:

- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/tsl-gen/tsl_gen/resolver/render_support.py`
- `frozen/out/tsl/tsl_native.hpp`
- `tslgen/src/tslgen/backends/cpp/scalar_binary.py`

Accepted redesign inputs:

- Backend metadata boundary from Milestone 30.
- Selected parity baseline from Milestone 35.
- Scalar wrapper/body output from Milestones 36 and 37.
- Lowered intrinsic-compose helper output from Milestone 38.
- Transitional native output from Milestone 39.

Expected outputs:

- Typed translation/composition model for the selected helper form.
- Backend-call IR or equivalent typed value for `_mm256_add_ps(left, right)`.
- A stated translation input contract that rejects unresolved generation-time
  helper IR before backend translation.
- C++ renderer consumption of the translated value rather than renderer-owned
  intrinsic lookup.
- Diagnostics for missing language map, missing translation metadata,
  unsupported extension/type/intrinsic, and missing translated call IR.
- Stable M39 native golden output.

Parity criterion:

The selected native specialization still emits the same observable
`_mm256_add_ps(left, right)` call, but the renderer no longer decides that
`add + avx2 + f32` means `_mm256_add_ps`.

Tests required:

- Unit tests for selected translation/composition input and output.
- Unit tests proving `f32` type spelling is read through typed backend metadata.
- Unit tests or diagnostics proving backend translation rejects unresolved
  `if<generation>`, `type<generation>`, or `value<generation>` helper nodes.
- Unit tests or integration tests proving the C++ renderer consumes translated
  backend-call IR and does not rescan raw TSIL.
- Regression coverage preventing future selected native intrinsic resolution
  from being added by extending renderer-local lookup tables.
- Golden regression for the existing native `avx2/f32` specialization.
- Diagnostic tests for missing translated call IR and unsupported
  type/extension/intrinsic combinations.
- Determinism tests for translation output and rendered artifacts.

Golden fixtures required:

- Reuse the Milestone 39 native C++ golden fixture.
- Add a small translation fixture derived from `tsldata` only if it clarifies
  provenance; do not copy broad legacy output.

Documentation updates:

- Update `behavioral-spec.md`, `pipeline-design.md`,
  `target-architecture.md`, `testing-strategy.md`, and `open-questions.md` with
  the corrected boundary.
- Close or narrow OQ-035 for the selected fixture.

Review risks:

- Moving the hardcoded table without actually making translation data-driven.
- Making all translation maps executable in one milestone.
- Letting backend translation become a second TSIL evaluator for
  generation-time helpers.
- Emitting backend text from lowering instead of a typed translated value.
- Leaving a duplicate renderer-local intrinsic path that future slices might
  expand.

Dependencies:

- Milestones 30, 35, 36, 37, 38, and 39.

## Milestone 41: Generation-Time Semantic Lowering Contract

Goal:

After the M40 boundary correction, define the generation-time semantic lowering
contract that must run before backend translation. This prevents helpers such as
`if<generation>(...)`, `type<generation>(...)`, and
`value<generation>(...)` from leaking into backend translation or renderers as
raw TSIL text.

Scope:

- Refresh the TSIL helper inventory against the actual post-M40 code.
- Define the ordered lowering phases:
  TSIL helper parse, generation-time semantic lowering, backend translation,
  then backend rendering.
- Define the typed `GenerationContext` fields required by the first query
  forms, such as selected primitive, selected candidate, type tag, extension,
  vector/register metadata, primitive attributes, signature, and template.
- Classify `type<generation>(...)`, `value<generation>(...)`, and
  `if<generation>(...)` forms found in `tsldata` by priority and required
  context.
- Pick one next implementable generation-time semantic slice or explicitly
  defer implementation if evidence is insufficient.
- Record that backend translation may consume `type<backend>(...)` and
  `value<backend>(...)` only after their generation-time arguments have been
  resolved to typed semantic values.
- Keep generated-test, CLI, report, Rust-body, and broad backend expansion
  deferred unless they directly depend on the selected helper slice.

Out of scope:

- Production implementation unless the planner explicitly converts this into a
  small implementation milestone.
- Full TSIL grammar.
- Evaluating broad generation-time expression language.
- Backend translation for unresolved generation-time helper expressions.
- Broad C++ or Rust rendering.

Evidence paths:

- `tsldata/primitives/**.tsl`
- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/*.py`
- `frozen/tsl-gen/tsl_gen/resolver/render_support.py`

Accepted redesign inputs:

- Corrected translation/backend boundary from Milestone 40.
- Updated helper inventory and drift matrices from this roadmap phase.
- Open questions OQ-032 and OQ-035.

Expected outputs:

- A documented generation-time-before-backend translation contract.
- A helper inventory and typed `GenerationContext` contract in
  `docs/redesign/generation-time-semantic-lowering.md`.
- The selected next generation-time helper slice:
  `if<generation>(value<generation>(primitive::attribute(aligned)))` branch
  pruning over primitive attributes.
- Updated milestone plan for the chosen helper and deferred-target list.
- Updated open questions for blocked helper semantics.

Parity criterion:

The next implementation target must be justified by observed `tsldata` and
`frozen` behavior and must ensure generation-time helper semantics are resolved
before backend translation receives inputs.

Tests required:

- Documentation-only milestone: `git diff --check`.
- Matrix checks for every observed `type<generation>`, `value<generation>`, and
  `if<generation>` form selected by the contract.
- If a fixture inventory is added, provenance tests must not import from
  `frozen/`.

Golden fixtures required:

- None unless the selected next helper needs a minimal TSIL fixture.

Documentation updates:

- Update the roadmap, open questions, behavioral spec, and testing strategy
  with the generation-time lowering contract and selected next helper family.

Review risks:

- Reopening broad TSIL grammar work without a selected parity need.
- Letting backend translation parse or evaluate raw `type<generation>` or
  `if<generation>` text.
- Picking generated-test or CLI work before the required helper semantics are
  stable.
- Letting another backend renderer absorb helper-specific translation.

Dependencies:

- Milestone 40.

## Milestone 42: Primitive-Attribute Generation Branch Pruning Slice

Goal:

Implement the boolean primitive-attribute generation branch slice selected by
Milestone 41:
`if<generation>(value<generation>(primitive::attribute(aligned)))`. This keeps
aligned load/store branch selection in semantic lowering, so future helper
forms do not migrate into backend translation or renderers as raw TSIL text.

Scope:

- Recognize the selected primitive-attribute condition shape.
- Resolve `value<generation>(primitive::attribute(aligned))` to a typed boolean
  generation value using explicit primitive attributes from
  `GenerationContext`.
- Lower the selected branch form to a pruned statement list with deterministic
  provenance.
- Diagnose unsupported condition expressions, malformed branch forms, missing
  context, missing/non-boolean/unknown attributes, and unresolved helper forms
  only in the selected branch.
- Do not recursively lower or diagnose helper forms in the unselected branch.

Out of scope:

- Full generation-time expression language.
- Generic loops, arrays, and variable scoping.
- Backend rendering changes.
- Backend translation of unresolved generation-time helper IR.
- Compile/run orchestration.
- Rust body generation.

Legacy evidence paths:

- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/generation_ifs.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`

Accepted redesign inputs:

- Generation context placeholder from Milestone 18.
- Helper inventory from Milestone 38.
- Translation/type metadata boundary from Milestone 40.

Expected outputs:

- A documented and tested first generation-time condition evaluator for the
  selected primitive-attribute branch shape.
- Diagnostics for unsupported condition functions, unknown attributes,
  missing `aligned`, non-boolean `aligned`, missing generation context,
  malformed generation-time branches, and unresolved helpers in the selected
  branch.
- Clear guidance for which future backend parity slices may depend on this
  condition support.

Parity criterion:

Selected generation-time branch behavior is evaluated in semantic lowering
before backend translation receives inputs, never in backend renderers or
template text. The unselected branch must not poison a valid branch choice.

Tests required:

- Unit tests for the selected condition shape.
- Branch-selection and typed-value determinism tests.
- Diagnostic tests for unknown attributes, missing/non-boolean `aligned`,
  missing generation context, malformed branches, unsupported conditions, and
  unresolved helpers in the selected branch.
- Regression tests proving backend translation rejects unresolved
  generation-time helper IR.
- Renderer non-evaluation regression test when a rendering fixture consumes a
  lowered branch result later.

Golden fixtures required:

- Minimal TSIL condition fixtures derived from `tsldata`, not large legacy
  output files.

Documentation updates:

- Update lowering behavior, pipeline design, and open questions for generation
  expressions.
- Add or revise an ADR if implementation reveals a branch-pruning policy change.

Review risks:

- Implementing a broad expression evaluator too early.
- Evaluating type or attribute predicates in backend templates.
- Choosing a branch fixture unrelated to the next parity target.

Dependencies:

- Milestones 18, 30, 40, and 41.

Implementation note:

Milestone 42 implements this selected branch-pruning scope and does not add
backend rendering behavior.

## Milestone 43: Base Type Generation Query Slice

Goal:

Implement the next narrow generation-time query family after Milestone 42:
selected base scalar type references and their signed/unsigned integer
companions. This gives later backend modifier translation typed semantic input
for forms such as integer intrinsic suffix selection without letting backend
translation parse raw `type<generation>(...)` text.

Scope:

- Recognize only the selected base-type generation query forms listed below.
- Resolve the selected candidate type tag to an immutable typed semantic type
  value during semantic lowering.
- Resolve signed and unsigned integer companions for the selected base type.
- Preserve deterministic provenance tying the resolved type value to the
  candidate id and implementation source location.
- Keep the resolved generation type as semantic IR for later backend
  translation; do not render a backend type spelling in this milestone.
- Continue rejecting unresolved generation-time helpers before backend
  translation.

Out of scope:

- Full TSIL grammar or expression parsing.
- Backend suffix, prefix, infix, post, or `immediate(n)` modifier evaluation.
- Backend rendering changes or new C++/Rust output.
- Vector/register type queries such as `vector::register`,
  `vector::as_extension(...)`, `vector::transform_extension(...)`, and
  `vector::mask_underlying_t`.
- Generation-time value queries such as `vector::length`,
  `vector::alignment`, and `generic::length(...)`.
- Signedness branch pruning for
  `if<generation>(value<generation>(type::is_signed(...)))`.
- Primitive calls, loops, variables, aliases, casts, arrays, compile-time
  switches, and direct intrinsic parsing.

Exact supported helper/query forms:

```text
type<generation>(base::in)
type<generation>(base::signed_of(type<generation>(base::in)))
type<generation>(base::unsigned_of(type<generation>(base::in)))
```

No shorthand, alias, vector, generic, nested non-base, or backend-scoped type
form is accepted by this milestone.

Required `GenerationContext` fields:

- selected primitive name
- emitted primitive name
- selected candidate id
- normalized signature
- parameter list
- selected type tag, defaulting to the selected candidate type tag when no
  explicit generation-context override is supplied
- `GenerationContext.type_tag_override`, which is the explicit request-local
  override and wins over the context-selected type tag and candidate default
- implementation source location

Typed semantic value model:

- `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`
- `GenerationTypeRef(kind="base.signed_of", type_tag=<signed companion>,
  source_type_tag=<selected type tag>)`
- `GenerationTypeRef(kind="base.unsigned_of", type_tag=<unsigned companion>,
  source_type_tag=<selected type tag>)`

The selected companion conversion supports only integer tags with explicit
signed/unsigned prefixes such as `si32` and `ui32`. Signedness-preserving input
returns the corresponding same-width tag. Floating, pointer, mask, wildcard,
generic, and unknown tags are diagnostics until a later milestone selects their
semantics.

Diagnostics:

- Missing selected type context.
- Unknown or malformed selected type tag.
- Unsupported generation type query shape.
- Unsupported companion conversion for non-integer, generic, wildcard, pointer,
  or mask-like tags.
- Unresolved nested generation helper reaching backend translation.
- `TSL-LOWER-GEN-TYPE-CONTEXT-MISSING` triggers when no
  `GenerationContext.type_tag_override`, no `selected_type_tag`, and no
  selected candidate type tag is available.

Implemented outputs:

- A documented and tested base-generation-type value model.
- Deterministic lowering output that can be consumed by a later backend
  modifier translation milestone.
- Backend-neutral `GenerationTypeRef` values only; backend type spelling and
  suffix/prefix/post/infix/immediate evaluation remain deferred.
- Translation rejection of unresolved raw generation helper text remains in
  force.
- Renderer behavior remains unchanged.
- No generated C++, Rust, or other output changes.

Parity criterion:

Integer native `binary/add` variants and shift/conversion parity paths require
generation-time base type references before backend suffix or signedness
translation can be implemented. This milestone resolves those generation-time
type references before backend translation, preserving the Milestone 40 rule
that translation receives typed semantic values only.

Evidence paths:

- `tsldata/primitives/arithmetic/fundamental.tsl:47-90` for integer
  `intrin_compose<add>` suffix inputs using
  `type<generation>(base::signed_of(type<generation>(base::in)))`.
- `tsldata/primitives/bitwise/shifts.tsl:38-40`,
  `shifts.tsl:63-82`, `shifts.tsl:625-648`, and
  `shifts.tsl:842-886` for signed/unsigned companion and signedness-branch
  pressure.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1225` for conversion
  paths that combine signedness predicates and companion type references.
- `tsldata/detail/lang/translate_cpp.tsl:5-8` for backend type-trait and
  signed/unsigned translation metadata that later consumes resolved type
  values.
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:319-354`,
  `expansion_support.py:375-412`, and
  `expansion_support.py:4578-4596` as behavior evidence for canonical base
  type, signed/unsigned companion, and signedness classification forms.
- `frozen/tsl-gen/tsl_gen/resolver/render_support.py:565-699` as evidence
  that suffix modifiers consume type-derived values, not as architecture to
  port.

Tests implemented:

- Unit tests cover each exact supported query form over selected `si32` and
  `ui32` candidates.
- Tests prove selected candidate type tag is the default generation context
  source unless an explicit generation context supplies a type tag.
- Diagnostic tests cover missing type context, unknown tags, malformed helper
  text, unsupported helper families, and unsupported companion conversions.
- Determinism tests cover repeated lowering of the same query input.
- Regression tests prove backend translation still rejects unresolved raw
  `type<generation>(...)` text, while resolved `GenerationTypeRef` values
  remain backend-neutral and unsupported by current suffix/type-spelling
  translation.
- Existing Milestone 42 branch-pruning tests continue to pass unchanged.

Documentation updates:

- `generation-time-semantic-lowering.md` records the implemented M43 helper
  family, decision table, context fields, typed semantic result, and deferrals.
- `behavioral-spec.md`, `pipeline-design.md`, `testing-strategy.md`,
  `open-questions.md`, and the ADR-032 notes in `design-decisions.md` record
  the implemented base generation type query behavior.
- No new ADR was required because implementation did not change the M40/M41
  boundary or signed/unsigned companion semantics.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
  for lowering behavior and diagnostics.
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_cpp_backend_vertical_slice.py`
  for C++ translation-boundary and renderer non-evaluation regressions.
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_backend_metadata_boundary.py`
  for unchanged backend metadata boundary behavior.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation` for the full
  accepted validation profile.
- Targeted `python -m compileall -q`, `ruff check`, and
  `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` over
  the changed Python files and tests.
- `git diff --check`.

Review risks:

- Accidentally implementing backend suffix translation in the same slice.
- Rendering C++ or Rust type spellings from generation lowering.
- Treating wildcard type-group selectors such as `?i?` as concrete selected
  type tags.
- Extending companion conversion to floats, masks, pointer-like tags, or
  generic aliases without evidence-backed semantics.
- Letting backend translation evaluate raw nested `type<generation>(...)`
  expressions.

Dependencies:

- Milestones 18, 30, 40, 41, and 42.

Implementation note:

Milestone 43 is complete as a lowering/model slice only. It did not combine
query support with C++ or Rust output changes.

## Post-Milestone-43 Native Integer Modifier Phase

Milestones 1 through 43 are accepted. The next phase advances from typed M43
`GenerationTypeRef` values toward the next useful native integer C++ parity
slice without repeating the Milestone 39 renderer-local intrinsic drift.

Pipeline order remains:

```text
generation-time semantic lowering
-> backend translation
-> backend rendering
```

Generation-time helpers still resolve before backend translation. Backend
translation consumes typed semantic values, not raw
`type<generation>(...)` or `value<generation>(...)` helper text. Renderers never
parse generation-time helpers or derive suffix/type semantics locally.

### Phase Decision Table

| Candidate slice | Evidence path and exact form | Required inputs from previous milestones | Expected output/model | Pipeline owner | Risk and test strategy | Recommended position |
| --- | --- | --- | --- | --- | --- | --- |
| Backend modifier value family boundary selection and inventory | `tsldata/primitives/arithmetic/fundamental.tsl:47-90` uses `suffix=value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))`; `tsldata/primitives/load_store/load.tsl:55-70` and `tsldata/primitives/load_store/store.tsl:54-64` show prefix/suffix plus aligned branches; `tsldata/primitives/conversion/repr_change.tsl:358-370` and `:908-918` show literal and backend `immediate(n)` modifiers; grammar evidence in `frozen/tsl-gen/tsl_gen/tsil.lark:75-78`; canonical value-backend evidence in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:416-433`; modifier behavior evidence in `frozen/tsl-gen/tsl_gen/resolver/render_support.py:500-524`, `:632-674`, and `:680-699`; signed/unsigned output evidence in `frozen/out/tsl/tsl_native.hpp:24460-24477` and `:24712-24729`. | M40 backend-call translation boundary, M41/M42 generation-time-before-backend rule, M43 `GenerationTypeRef` values, and backend metadata inventory from M30. | A documented typed request/result model for backend intrinsic modifier values plus a selected first family. No runtime model changes in the planning milestone. | Planning for backend translation boundary. | Low for docs; validation is `git diff --check`. Future tests are defined here so implementation can cover raw-helper rejection, missing metadata, unsupported modifiers, and renderer non-evaluation. | Milestone 44. |
| Intrinsic suffix modifier translation over typed `GenerationTypeRef` | `tsldata/primitives/arithmetic/fundamental.tsl:65-75` shows native integer `avx2` add suffix input; `frozen/tsl-gen/tsl_gen/resolver/render_support.py:500-524`, `:632-657`, and `:680-692` show suffix-derived intrinsic-name behavior as evidence only; `frozen/out/tsl/tsl_native.hpp:24460-24477` and `:24712-24729` show `_mm256_add_epi32` for signed and unsigned 32-bit add. Exact supported form: `suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))`, where the type ref was produced by M43 from `type<generation>(base::signed_of(type<generation>(base::in)))`. | M43 typed `GenerationTypeRef(kind="base.signed_of", type_tag="si32")` with `source_type_tag` in `{si32, ui32}`, M44 modifier request/result contract, M40 intrinsic-compose expression model, selected backend id `cpp`, selected extension `avx2`, selected primitive/type, implementation source location, and typed backend metadata. | Typed backend modifier value such as `BackendIntrinsicModifier(kind="suffix", backend_id="cpp", extension="avx2", intrinsic="add", value="epi32", source_type_tag="si32")`, or an equivalent immutable modifier result consumed by later backend-call translation. | Backend translation. | Medium because suffix semantics cross type, extension, and translation metadata. Tests cover `si32` and `ui32` selected candidates resolving through `base.signed_of` to `epi32`, deterministic output, unsupported type/extension/map diagnostics, missing typed input diagnostics, and rejection of raw `type<generation>(...)` text. | Milestone 45. |
| Backend type spelling request over typed `GenerationTypeRef` | `tsldata/detail/lang/types/types_cpp.tsl:1-12` maps C++ scalar spellings such as `s32 {type "int32_t"}` and `u32 {type "uint32_t"}`; `translate_cpp.tsl:4-8` records backend type trait forms; frozen output uses `simd<int32_t, avx2>` at `tsl_native.hpp:24460-24477` and `simd<uint32_t, avx2>` at `:24712-24729`. Exact form: selected C++ backend type spelling request over typed M43 `GenerationTypeRef` values for `base.in`, `base.signed_of`, and `base.unsigned_of` when they resolve to selected `si32`/`ui32` scalar integer tags. | M43 `GenerationTypeRef`, typed language map metadata, backend id `cpp`, selected candidate type tag, and a documented tag-key normalization rule when source tags use `si32`/`ui32` but language keys use `s32`/`u32`. | Typed backend type spelling result such as `BackendTypeSpelling(backend_id="cpp", type_tag="si32", spelling="int32_t", source_ref_kind="base.in")`. | Backend translation. | Medium because tag normalization must be explicit and cannot live in renderers. Tests cover `si32 -> int32_t`, `ui32 -> uint32_t`, companion ref spellings, missing map diagnostics, unsupported/raw helper diagnostics, and deterministic results. | Milestone 46. |
| Native integer add parity rendering using resolved suffix/type data | `fundamental.tsl:65-75` is the active `avx2/?i?` add source; frozen output evidence is `tsl_native.hpp:24460-24477` for `simd<int32_t, avx2>` and `:24712-24729` for `simd<uint32_t, avx2>`, both returning `_mm256_add_epi32(left, right)`. | M45 resolved suffix modifier, M46 resolved C++ type spelling, M40 backend-call IR, existing C++ native specialization/wrapper rendering from M36-M40, selected candidate metadata and provenance. | Deterministic C++ golden fixture for selected native integer `add_binary` specializations, consuming already-translated suffix/type data. | Rendering, but only after translation outputs are explicit inputs. | Medium because it touches output. Tests are golden/provenance/determinism tests plus regressions proving the renderer has no suffix/type lookup and rejects missing translated data. No compiler execution. | Milestone 47. |
| Signedness branch pruning | `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`, `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518` use the exact `if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }` form. `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is predicate evidence but uses plain `else`, so it is not an exact M48 branch-shape input. | M42 branch-pruning model and M43 `GenerationTypeRef(kind="base.in")`. | Boolean generation value and pruned branch result for signed/unsigned selected types. | Generation-time semantic lowering. | Medium. Tests cover true/false pruning, selected-branch-only diagnostics, unsupported type predicates, unsupported/non-integer tags, and raw-helper rejection. | Implemented as Milestone 48 after the native integer add phase was accepted. |
| Prefix/post/infix/immediate modifiers | `load.tsl:55-70` and `store.tsl:54-64` show `prefix=value<backend>(intrin::prefix)` and suffix literals; `repr_change.tsl:358-370` and `:908-918` show `immediate(n)`; `render_support.py:610-623` and `:675-699` show modifier assembly behavior as evidence. Exact forms include `prefix=value<backend>(intrin::prefix)`, `post=...`, `infix=...`, and `immediate(n)=...`. | M44 request/result model, selected backend metadata, argument ordering, extension/type context, and for dynamic forms M43/M45-style typed values. | Typed modifier results for non-suffix families. | Backend translation. | Medium to high because forms have different syntax and naming effects. Tests must be family-specific and fixture-driven. | Defer until suffix proves the modifier boundary. |
| Vector/register metadata queries | `load.tsl:55-70`, `store.tsl:177-205`, and `translate_cpp.tsl:16-23`, `:63-65` show `type<generation>(vector::register)`, `type<generation>(vector::mask_underlying_t)`, `value<generation>(vector::alignment)`, and `value<generation>(vector::length)`. | Selected extension, vector width/lane/alignment metadata, backend id only for later spelling, and existing M42/M43 lowering context fields. | `GenerationTypeRef` or typed generation integer/symbol values for vector metadata. | Generation-time semantic lowering. | High for this phase because selected bodies also contain casts, loops, calls, masks, and attributes. Tests need metadata fixtures and no host CPU dependency. | Defer until load/store or mask parity is selected. |

The selected sequence is four milestones. Milestone 44 stays planning-only so
reviewers can confirm the backend modifier value boundary before implementation.
Milestones 45 and 46 build the translation prerequisites independently.
Milestone 47 is the first output expansion and is allowed to render only after
it consumes the explicit typed suffix and type-spelling results.

## Milestone 44: Backend Modifier Value Family Boundary Selection

Goal:

Select the first backend modifier value family to implement and define the
typed request/result model that backend translation will own.

Scope:

- Documentation/planning only.
- Select intrinsic suffix as the first backend modifier family because it is
  required by native integer `binary/add` and directly consumes M43 typed type
  refs.
- Define M45 as suffix translation over typed M43 `GenerationTypeRef` inputs,
  not as parsing of raw nested generation helper text.
- Prove the selected `si32` and `ui32` native integer add candidates both need
  the x86 suffix `epi32` after the M43 `base.signed_of` query resolves.
- Inventory exact evidence paths for suffix, prefix, post, infix, immediate,
  signedness predicates, type spelling, and vector/register metadata.
- Define implementation-slice diagnostics and tests for suffix translation.
- State the renderer non-evaluation regression that future implementation must
  keep.

Out of scope:

- Implementing modifier evaluation.
- Backend type spelling.
- Renderer changes or output changes.
- Full translation-map evaluation.
- Prefix, post, infix, or `immediate(n)` implementation.

Required inputs:

- Accepted M40 backend translation boundary.
- Accepted M41/M42 generation-time semantic-lowering contract.
- Accepted M43 `GenerationTypeRef` model.
- Backend metadata/language-map evidence from M30 and `tsldata/detail/lang`.
- Source/evidence paths listed in the phase decision table.

M44 selection result:

- First backend modifier value family: intrinsic suffix.
- First implementation milestone for that family: Milestone 45.
- M45 accepted conceptual form:

  ```text
  suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))
  ```

  where `<GenerationTypeRef>` is already the typed M43 lowering result for:

  ```text
  type<generation>(base::signed_of(type<generation>(base::in)))
  ```

- M45 must not consume or parse raw nested text such as:

  ```text
  suffix=value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))
  ```

  until the `type<generation>(...)` portion has been resolved by semantic
  lowering into `GenerationTypeRef`.

Accepted typed M45 inputs:

- `GenerationTypeRef(kind="base.signed_of", type_tag="si32",
  source_type_tag="si32")` for the selected signed 32-bit add candidate.
- `GenerationTypeRef(kind="base.signed_of", type_tag="si32",
  source_type_tag="ui32")` for the selected unsigned 32-bit add candidate.
- Backend id `cpp`.
- Selected extension `avx2`.
- Intrinsic base name `add`.
- The typed intrinsic-compose boundary from M40.
- The typed backend translation metadata boundary needed to prove the selected
  suffix table is present.
- Implementation source location for diagnostics.
- Source extension only when the selected implementation carries one; it must
  be request-local metadata, not renderer state.

Expected typed M45 output:

```text
BackendIntrinsicModifier(
  kind="suffix",
  backend_id="cpp",
  extension="avx2",
  value="epi32",
  source_type_tag="si32",
  source_ref_kind="base.signed_of",
)
```

An equivalent immutable value is acceptable if it preserves the same typed
data and provenance. The value is backend translation output for later
intrinsic-call translation/rendering; it is not a rendered intrinsic name.

Supported M45 suffix behavior:

| Selected candidate type tag | M43 typed input | M45 suffix output |
| --- | --- | --- |
| `si32` | `GenerationTypeRef(kind="base.signed_of", type_tag="si32", source_type_tag="si32")` | `epi32` |
| `ui32` | `GenerationTypeRef(kind="base.signed_of", type_tag="si32", source_type_tag="ui32")` | `epi32` |

M45 diagnostics:

- Raw unresolved generation helper text:
  `TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED`.
- Missing `GenerationTypeRef` for a suffix request:
  `TSL-CPP-TRANSLATE-MODIFIER-TYPE-MISSING`.
- Unsupported modifier family:
  `TSL-CPP-TRANSLATE-MODIFIER-UNSUPPORTED`.
- Unsupported suffix type tag:
  `TSL-CPP-TRANSLATE-MODIFIER-TYPE-UNSUPPORTED`.
- Unsupported backend:
  `TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND`.
- Unsupported extension:
  `TSL-CPP-TRANSLATE-UNSUPPORTED-EXTENSION`.
- Missing translation metadata:
  `TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP`.
- Missing modifier metadata inside an otherwise present map:
  `TSL-CPP-TRANSLATE-MODIFIER-METADATA-MISSING`.
- Malformed modifier request:
  `TSL-CPP-TRANSLATE-MODIFIER-MALFORMED`.

Each diagnostic should include the invalid helper, type tag, backend,
extension, or metadata key in the message and source location when available.

Expected outputs:

- Roadmap decision that intrinsic suffix is Milestone 45.
- A typed backend modifier request/result contract to be implemented later.
- Documentation that raw `type<generation>(...)` and
  `value<generation>(...)` helper text must not reach backend modifier
  translation.
- Documentation that prefix, post, infix, `immediate(n)`, backend type
  spelling, vector/register metadata, signedness branch pruning, renderer
  changes, C++ output changes, Rust output changes, and full translation-map
  evaluation remain separate milestones.

Validation criteria:

- Roadmap and supporting docs agree that M43 is complete and that M44-M47 are
  the post-M43 phase.
- No implementation files are changed.
- `git diff --check` succeeds.

Tests required:

- No runtime tests in the planning milestone.
- Future M45 tests must cover selected suffix success, diagnostics, determinism,
  raw-helper rejection, and renderer non-evaluation.
- Future M45 tests must also prove M42 branch-pruning and M43 base-type query
  regressions remain stable while suffix translation is added.

Documentation updates:

- Update this roadmap with the phase decision table and numbered milestones.
- Align generation-time lowering, behavioral, pipeline, architecture, testing,
  open-question, ADR, and parity-baseline notes if they reference the stale
  unnumbered next target.

Review risks:

- Accidentally turning the planning milestone into broad modifier
  implementation.
- Selecting a modifier family that is useful only for load/store before the
  integer add parity path is unblocked.
- Letting suffix semantics drift into renderer-local lookup again.

Dependencies on prior milestones:

- Milestones 30, 40, 41, 42, and 43.

## Milestone 45: Intrinsic Suffix Modifier Translation Slice

Status:

Implemented in the M45 slice. Milestone 45 adds typed backend intrinsic
modifier request/result values and translates only the selected C++ AVX2
integer `add` suffix request over M43 `GenerationTypeRef` inputs. It does not
render native integer output and does not provide backend type spelling.

Goal:

Translate one selected intrinsic suffix modifier over typed M43
`GenerationTypeRef` inputs.

Scope:

- Implement typed backend modifier request/result values for the selected
  suffix family.
- Support exactly the native integer C++ `binary/add` suffix input:

  ```text
  suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))
  ```

  where `<GenerationTypeRef>` is the M43 result for:

  ```text
  type<generation>(base::signed_of(type<generation>(base::in)))
  ```

- Support the selected `avx2` `si32` and `ui32` add candidates through the same
  signed companion suffix result, `epi32`.
- Reject raw `type<generation>(...)` or `value<generation>(...)` text at the
  backend translation boundary.
- Preserve deterministic provenance for the modifier source and resolved value.

Out of scope:

- Prefix, post, infix, and `immediate(n)`.
- Backend type spelling.
- Renderer changes and output changes.
- Full translation-map evaluation.
- Vector/register metadata queries and signedness branch pruning.

Required inputs:

- M43 `GenerationTypeRef` values.
- M44 typed modifier request/result contract.
- M40 intrinsic-compose translation boundary.
- Selected backend id `cpp`.
- Selected extension `avx2`.
- Selected candidate type tags `si32` and `ui32`.
- Intrinsic base name `add`.
- Implementation source location.
- Typed backend translation metadata needed to map signed 32-bit integer type
  to `epi32`.

Expected outputs:

- Immutable suffix modifier translation result, for example:

  ```text
  BackendIntrinsicModifier(
    kind="suffix",
    backend_id="cpp",
    extension="avx2",
    intrinsic="add",
    value="epi32",
    source_type_tag="si32",
    source_ref_kind="base.signed_of",
  )
  ```

- Structured diagnostics for unsupported modifier shape, unsupported or
  missing type/extension metadata, missing typed `GenerationTypeRef`, missing
  translation metadata, missing modifier metadata, unsupported backend,
  unsupported extension, unsupported intrinsic base, unsupported source ref
  kind, unsupported type tag, malformed modifier requests, and raw
  generation-helper text reaching backend translation.

Validation criteria:

- Backend translation accepts only typed M43 inputs for the selected suffix
  request.
- `si32` and `ui32` selected add candidates resolve the suffix needed for
  `_mm256_add_epi32`.
- No renderer output changes occur in this milestone.

Tests required:

- Unit tests for suffix translation over `si32` and `ui32`.
- Unit tests proving both selected tags resolve through the M43
  `base.signed_of` input to `epi32`.
- Diagnostic tests for missing metadata, unsupported type tag, unsupported
  extension, unsupported backend, unsupported modifier family, missing
  `GenerationTypeRef`, unsupported intrinsic base, unsupported source ref kind,
  malformed modifier request, and raw helper text.
- Determinism tests for repeated suffix translation.
- Regression tests proving renderers do not evaluate suffix helpers.

Documentation updates:

- Record the implemented suffix slice and remaining modifier deferrals in the
  roadmap, generation-time semantic-lowering doc, behavioral spec, pipeline
  design, testing strategy, open questions, and ADR notes.

Review risks:

- Implementing prefix/post/infix/immediate while adding suffix.
- Inferring backend type spelling from suffix translation.
- Keeping a renderer-local fallback for `_mm256_add_epi32`.
- Treating legacy `render_support.py` parsing as the new architecture.

Dependencies on prior milestones:

- Milestones 30, 40, 41, 42, 43, and 44.

## Milestone 46: Backend Type Spelling Request Slice

Goal:

Implement one selected backend C++ type spelling request over typed M43
`GenerationTypeRef` inputs.

Scope:

- Implement a typed backend type-spelling request/result boundary for selected
  scalar C++ base types.
- Support selected `si32` and `ui32` type refs for the native integer add path:

  ```text
  GenerationTypeRef(kind="base.in", type_tag="si32") -> int32_t
  GenerationTypeRef(kind="base.in", type_tag="ui32") -> uint32_t
  GenerationTypeRef(kind="base.signed_of", type_tag="si32",
                    source_type_tag="si32" | "ui32") -> int32_t
  GenerationTypeRef(kind="base.unsigned_of", type_tag="ui32",
                    source_type_tag="si32" | "ui32") -> uint32_t
  ```

- Read through typed language-map metadata; document or implement the
  `si32`/`ui32` to `s32`/`u32` key normalization needed by
  `types_cpp.tsl`.
- Reject raw generation helper text.
- Preserve deterministic provenance tying spelling to backend metadata.

Out of scope:

- Vector/register type spellings.
- Generic, wildcard, pointer, mask, or extension-transform type spellings.
- Rust type spelling.
- Changing M45 suffix behavior or adding prefix, post, infix, or immediate
  evaluation.
- Renderer/output changes except metadata-level consumption tests if needed.

Required inputs:

- M43 `GenerationTypeRef` values for selected `base.in`, `base.signed_of`, and
  `base.unsigned_of` scalar integer refs.
- Typed C++ language-map metadata from `types_cpp.tsl`.
- Backend id `cpp`.
- Selected candidate type tags `si32` and `ui32`.
- The M40 translation boundary and M44/M45 no-raw-helper rule.

Expected outputs:

- Immutable backend type spelling results, for example:

  ```text
  BackendTypeSpelling(backend_id="cpp", type_tag="si32",
                      spelling="int32_t", source_ref_kind="base.in")
  BackendTypeSpelling(backend_id="cpp", type_tag="ui32",
                      spelling="uint32_t", source_ref_kind="base.in")
  ```

- Structured diagnostics for raw unresolved generation helper text, missing
  `GenerationTypeRef`, unsupported backend, unsupported type tag, unsupported
  source ref kind, missing language/type map metadata, missing type-spelling
  metadata, malformed request, and unsupported vector/register/generic/pointer
  or mask requests.

Validation criteria:

- Backend type spelling is translated before rendering and never inside a
  renderer-local scalar type map.
- The selected `si32` and `ui32` spellings match the frozen native integer add
  evidence.
- No output expansion occurs in this milestone.

Tests required:

- Unit tests for selected `base.in`, `base.signed_of`, and `base.unsigned_of`
  refs resolving to `int32_t` or `uint32_t`.
- Tests for language-map key normalization or equivalent typed metadata.
- Diagnostic tests for missing/unsupported type-map entries and raw helper text.
- Determinism tests and renderer non-evaluation regressions.

Documentation updates:

- Record the implemented backend type-spelling boundary, supported tags,
  language-map normalization rule, diagnostics, and remaining deferrals.

Review risks:

- Placing type spelling in generation-time semantic lowering.
- Reintroducing local C++ renderer type maps.
- Accidentally selecting vector/register or generic type spelling.
- Hiding tag normalization in ad hoc string logic.

Dependencies on prior milestones:

- Milestones 30, 40, 41, 42, 43, 44, and usually 45 for the selected native add
  path, though the type-spelling translator is independently testable.

## Milestone 47: Native Integer Add Parity Slice

Status:

Accepted. Milestone 47 renders only the selected native integer C++
`binary/add` output after consuming explicit M45 suffix and M46 type-spelling
translation values.

Goal:

Render the selected native integer C++ `add` output slice using typed suffix
and type-spelling translation outputs.

Scope:

- One backend: C++.
- One primitive/template path: `fundamental/add` with `binary`.
- One native extension: `avx2`.
- Selected integer types: `si32` and `ui32`.
- Consume the M45 suffix value and M46 C++ type spelling values as explicit
  renderer inputs.
- Produce deterministic golden output for:

  ```text
  add_binary<simd<int32_t, avx2>>
  add_binary<simd<uint32_t, avx2>>
  return _mm256_add_epi32(left, right);
  ```

- Record fixture provenance against active source and frozen behavioral
  evidence.

Out of scope:

- Broad native rendering.
- SSE, AVX512, NEON, SVE, scalar, generic, mask, or conversion expansion.
- Shifts, load/store, reinterpret, or immediate-heavy primitives.
- Compiler execution, generated-test execution, CLI workflows, and report
  parity.
- Renderer-local suffix or type lookup.

Required inputs:

- M40 backend-call IR boundary.
- M45 resolved intrinsic suffix modifier.
- M46 resolved C++ type spelling.
- Existing C++ native layout/specialization/wrapper rendering slices from
  M36-M40.
- Selected candidate metadata and deterministic provenance.

Expected outputs:

- A redesign-owned golden fixture for the selected native integer C++ add
  specializations:
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_i32_u32_excerpt.hpp`
  with provenance in the adjacent `.provenance.md` file.
- Artifact metadata and provenance showing the output consumed translated
  suffix/type values.
- Structured diagnostics when the translated suffix, translated type spelling,
  or native integer translation plan is missing, unsupported, or ambiguous.

Validation criteria:

- Golden output matches the selected semantic evidence for `int32_t` and
  `uint32_t` AVX2 add.
- Repeated rendering is deterministic.
- Renderer tests prove no raw generation helper text, suffix lookup, or type-map
  lookup is evaluated locally.
- No compiler or legacy workflow is run.

Tests required:

- Golden output fixture and provenance test.
- Unit tests for renderer consumption of translated suffix/type values.
- Diagnostic tests for missing, unsupported, and ambiguous translated suffix
  and type-spelling values, plus missing translated native integer plan.
- Determinism test for repeated artifact rendering.
- Regression tests keeping M39/M40 `avx2/f32` behavior intact.

Documentation updates:

- Update roadmap status, parity baselines, behavioral spec, testing strategy,
  and open questions for the implemented native integer add parity slice.

Review risks:

- Expanding beyond selected `si32`/`ui32` AVX2 add.
- Combining rendering with new translation semantics.
- Allowing fallback renderer maps for `_mm256_add_epi32`, `int32_t`, or
  `uint32_t`.
- Treating frozen output as a byte-for-byte whole-header target.

Dependencies on prior milestones:

- Milestones 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, and 46.

## Milestone 48: Signedness Type-Predicate Branch Pruning Slice

Status:

Accepted.

Goal:

Implement the next narrow generation-time semantic lowering slice:
`if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
branch pruning over typed M43 `GenerationTypeRef(kind="base.in")` inputs.
This unlocks a prerequisite for later shift and conversion parity without
combining branch pruning with backend modifier translation or rendering.

Scope:

- Recognize only the exact signedness condition shape:

  ```text
  value<generation>(type::is_signed(type<generation>(base::in)))
  ```

- Reuse the M42 generation branch pruning model, including selected-branch
  provenance and selected-branch-only unresolved-helper diagnostics.
- Resolve the inner `type<generation>(base::in)` through the M43 typed
  `GenerationTypeRef` model. Do not parse raw type text downstream.
- Evaluate signedness as a typed boolean generation value for selected
  concrete integer tags already supported by M43:
  `si32 -> true` and `ui32 -> false`.
- Prune the selected `if<generation> ... else<generation>` branch
  deterministically.
- Keep unresolved generation-time helpers diagnostic-producing only in the
  selected branch.

Out of scope:

- Plain `else` branch syntax, including the conversion evidence in
  `repr_change.tsl`.
- Shift or conversion output parity, direct intrinsic rendering, backend
  rendering changes, generated output, compiler execution, and generated-test
  execution.
- Backend suffix/type translation, prefix/post/infix/immediate modifiers, and
  broad translation-map evaluation.
- Vector/register metadata, vector transforms, masks, casts, loops,
  `if<compile>`, primitive calls, variables, aliases, and direct
  `intrin<...>` parsing.
- Signedness predicates over floats, masks, pointers, wildcard/generic tags,
  vector types, or backend-scoped type requests.

Required inputs:

- M42 branch-pruning model and provenance behavior.
- M43 `GenerationTypeRef(kind="base.in", type_tag="si32" | "ui32")` values.
- Existing request-local `GenerationContext` type-tag override, selected type
  tag, and selected candidate default behavior.
- M40/M41/OQ-036 ordering: generation-time semantic lowering before backend
  translation before rendering.

Expected outputs:

- A typed boolean generation predicate result for the selected
  `type::is_signed(base.in)` condition.
- A pruned generation branch result, or equivalent lowered statement list with
  deterministic branch provenance, for signed and unsigned selected candidates.
- Structured diagnostics for malformed branches, unsupported condition
  expressions, missing generation/type context, unsupported type tags,
  non-integer signedness predicates, unsupported nested type query shapes, and
  unresolved helpers in the selected branch.
- Continued backend-translation rejection of raw unresolved generation helper
  text.

Parity criterion:

The selected signedness branch condition is evaluated in semantic lowering from
typed M43 values, never in backend translation, backend templates, or
renderers. The unselected branch does not poison a valid selected branch.

Evidence paths:

- `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`,
  `:842-887`, `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and
  `:1507-1518` for exact `if<generation>(...type::is_signed...)` plus
  `else<generation>` branch forms.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` for the same
  signedness predicate in conversion code, but with plain `else`; this is
  predicate evidence only and not an accepted M48 branch syntax.
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:319-339`,
  `:403-404`, `:4586-4596`, and `:5011-5097` as behavior evidence for base
  type canonicalization, `type::is_signed` canonicalization, signedness
  classification, and generation-branch selection. `frozen/` remains evidence
  only.

Tests required:

- Unit tests where selected `si32` prunes to the true branch and selected
  `ui32` prunes to the false branch.
- Determinism tests for repeated signedness branch pruning and diagnostic
  ordering.
- Diagnostic tests for malformed branches, unsupported predicates,
  unsupported nested type query shapes, missing type context, unknown tags,
  unsupported/non-integer tags such as `f32`, pointer/mask-like tags, wildcard
  or generic tags, and unresolved helpers in the selected branch.
- Regression tests proving unselected branch helpers are not diagnosed.
- Regression tests proving backend translation still rejects unresolved raw
  `if<generation>`, `type<generation>`, and `value<generation>` text and that
  renderers remain non-evaluating.

Golden fixtures required:

- None. M48 is a lowering slice and must not change generated C++ or Rust
  output.

Documentation updates:

- Update lowering behavior, pipeline design, behavioral spec, testing
  strategy, open questions, ADR notes, parity baselines, and
  `docs/agent/current-redesign-state.md` for the implemented M48 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Re-parsing raw `type<generation>(...)` text instead of consuming typed M43
  values.
- Expanding the slice into shift/conversion body lowering or plain `else`
  syntax support.
- Letting backend translation, backend templates, or renderers evaluate
  signedness.
- Treating legacy `expansion_support.py` as architecture rather than evidence.

Dependencies on prior milestones:

- Milestones 18, 30, 40, 41, 42, 43, 44, 45, 46, and 47.

Implementation note:

Milestone 48 should remain generation-time semantic lowering only. It should
not change generated output or broaden backend translation.

## Deferred Parity Targets After Boundary Correction

The following previously planned targets remain valid but are deliberately
deferred until explicitly reintroduced as separate milestones:

- Generated C++ test parity slice from old M40.
- CLI workflow compatibility slice from old M41.
- Legacy coverage JSON adapter slice from old M42.
- Broader C++ or Rust backend rendering beyond the corrected M40 call IR.
- Executable generated tests and compile/run orchestration.

When one of these targets is reintroduced, give it a fresh milestone number and
reuse the same milestone contract fields: goal, scope, out of scope, evidence
paths, accepted redesign inputs, expected outputs, parity criterion, tests,
golden fixtures, documentation updates, review risks, dependencies, and whether
it replaces or adapts a deferred target.

## Post-M48 Planning Needed

Milestones 1 through 48 are accepted. No Milestone 49 is selected yet.

The next action is a docs-only post-M48 planning pass that reviews the deferred
targets below and selects at most one narrow next milestone.

M48 is constrained to generation-time semantic lowering over typed M43
`GenerationTypeRef(kind="base.in")` inputs. Broader native rendering,
prefix/post/infix/immediate modifiers, vector/register metadata, Rust output,
generated tests, compiler execution, and branch body semantics beyond the
selected pruning result remain deferred.
