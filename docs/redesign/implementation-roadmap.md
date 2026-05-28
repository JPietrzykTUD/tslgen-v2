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
| Signedness branch pruning | `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`, `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518` use the exact `if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }` form. `tsldata/primitives/conversion/repr_change.tsl:1210-1217` uses the same predicate with plain `else` and is selected as branch-shape evidence for M51 only. | M42 branch-pruning model and M43 `GenerationTypeRef(kind="base.in")`. | Boolean generation value and pruned branch result for signed/unsigned selected types. | Generation-time semantic lowering. | Medium. Tests cover true/false pruning, selected-branch-only diagnostics, unsupported type predicates, unsupported/non-integer tags, raw-helper rejection, and no conversion-body lowering. | M48 implemented `else<generation>`; M51 implements the exact plain-`else` signedness form. |
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

## Post-M48 Candidate Decision Table

| Candidate slice | Evidence path and exact form | Required accepted inputs | Expected output/model | Pipeline owner | Risk and test strategy | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| Generated C++ `add_i32_basic` test-source parity | `tsldata/primitives/arithmetic/fundamental.tsl:6` records the selected `add_i32_basic` test data. `frozen/jinja/cpp/test_file.j2:1-56`, `frozen/jinja/cpp/partials/test_common.j2:1-13`, `frozen/jinja/cpp/test_case.j2:51-63`, and `frozen/generator_specs/tests.yaml` provide legacy test-file, boolean test-function, binary test-case, and test-policy evidence. | Existing `TestSourcePlan` / `PlannedTestCase` values, M46 `BackendTypeSpelling` for selected C++ `si32 -> int32_t`, accepted scalar C++ wrapper naming from M37, artifact/golden infrastructure, and M35 parity baseline `CPP-ADD-I32-TEST`. | One deterministic redesign-owned C++ test-source artifact and golden fixture for the selected scalar `add_i32_basic` case. | Test-source rendering. | Medium. Tests must prove the renderer consumes typed test-plan and typed type-spelling data, is deterministic, preserves semantic evidence for test name/inputs/expected/wrapper-call intent/`TEST` registration, and does not compile, run, fetch `gtest`, read `frozen/`, infer type spellings locally, or broaden generated-test support. | Select as Milestone 49. |
| Legacy coverage JSON adapter row | `frozen/out/reports/primitive_coverage.json:57762-57777` records the selected `add`, `avx2`, `cpp`, `f32` row. `frozen/tools/report_primitive_coverage.py:242-266` records the legacy field construction rules. | Accepted coverage/report DTOs and deterministic JSON rendering. | One selected-row JSON adapter fixture. | Reporting. | Low to medium. Tests must prove selected-row field mapping, stable string-valued legacy booleans at the adapter boundary, deterministic ordering, and no parser/selection/lowering/rendering rerun during serialization. | Select as Milestone 50. |
| CLI workflow compatibility | `frozen/run_all.sh`, `frozen/run_tests.py`, and legacy CLI evidence show broad workflows. | Accepted API/CLI, writer, selected output, and explicit workflow policy. | One generation-only workflow if selected later. | CLI/API boundary. | High if it tries to include build/test/run/docs/CPU detection. | Defer. |
| Prefix/post/infix/immediate modifiers | `tsldata/primitives/bitwise/shifts.tsl`, `tsldata/primitives/conversion/repr_change.tsl`, and `frozen/tsl-gen/tsl_gen/resolver/render_support.py` show broad modifier behavior. | M44-M46 typed modifier boundaries plus selected family-specific fixtures. | Typed backend modifier results. | Backend translation. | Medium to high; not needed for the selected generated-test parity slice. | Defer. |
| Vector/register metadata or shift/conversion output | Shift/conversion and load/store sources contain vector metadata, casts, loops, direct intrinsics, calls, and branch-body semantics. | Additional lowering/type/value metadata and backend translation slices. | Future semantic values or output slices. | Lowering plus later translation/rendering. | High if combined. | Defer. |
| Executable generated tests and compiler orchestration | `frozen/run_tests.py` and `frozen/generator_specs/tests.yaml` show compile/run behavior. | Toolchain policy, optional dependency policy, generated-test source parity, and runtime harnesses. | Optional toolchain execution workflow. | Toolchain/test execution boundary. | High; must not enter default validation. | Explicitly defer. |

## Milestone 49: Generated C++ Add I32 Test Source Parity Slice

Status:

Accepted in the Milestone 49 execution-review loop.

Goal:

Render one deterministic, legacy-style C++ test source for the selected
`add_i32_basic` case, consuming typed `TestSourcePlan` data rather than
rescanning raw TSL or copying legacy templates. This reintroduces the old
generated C++ test parity target as a narrow source-rendering slice, without
compiler execution.

Scope:

- Backend: C++ only.
- Primitive/test/type/extension: `add`, `add_i32_basic`, `si32`, scalar.
- Produce a redesign-owned golden fixture:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`.
- Add fixture provenance that cites active source data and legacy evidence.
- Render artifact kind `production_tests` at logical path
  `tests/add_i32_basic_test.cpp`.
- Preserve semantic parity for:
  - test name `add_i32_basic`;
  - two input vectors and one expected vector from `fundamental.tsl`;
  - wrapper-call intent for `tsl::add<Vec>(...)`;
  - `using Vec = tsl::simd<int32_t, scalar>` from an explicit typed C++
    type-spelling input;
  - legacy-style `TEST(...){ ASSERT_TRUE(...) }` registration intent.
- Consume `TestSourcePlan` / `PlannedTestCase` or an equivalent typed test-plan
  value. The renderer must not rescan raw TSL text.
- Consume an explicit M46-style
  `BackendTypeSpelling(backend_id="cpp", type_tag="si32", spelling="int32_t",
  source_ref_kind="base.in")` value, or an equivalent immutable typed
  type-spelling input. The renderer must not infer `int32_t` from `si32`.
- Keep the existing metadata-style C++ production-test artifact stable unless
  a local refactor is required to share typed rendering helpers.

Out of scope:

- Compiling or running generated tests.
- Fetching, vendoring, configuring, or requiring `gtest`.
- Full legacy support headers, runtime aligned buffers, lane resizing,
  runtime-lane policy, or mask/test-manifest policy.
- Broad generated-test parity beyond the selected scalar `add_i32_basic` case.
- `add_i32_edge`, `ui32`, floating, AVX2, vector, mask, load/store, shift, or
  conversion tests.
- CLI/report/Rust work, output writing beyond existing test artifact paths, and
  compiler/toolchain orchestration.
- Backend translation changes, generation-time lowering changes, rendering
  semantic inference, or broad C++ generated output expansion.
- Runtime dependency on `frozen/` or importing/executing legacy templates.

Required inputs:

- Existing `TestSourcePlan` and `PlannedTestCase` values.
- M46 typed C++ scalar type spelling for `GenerationTypeRef(kind="base.in",
  type_tag="si32")`, producing `int32_t`.
- Accepted scalar C++ `add<Vec>` wrapper contract from M37.
- M29 production-test rendering boundary, including the rule that test source
  rendering consumes typed test-plan data and does not compile or run tests.
- M35 parity baseline entry `CPP-ADD-I32-TEST`.

Expected outputs:

- One deterministic in-memory C++ test-source artifact for the selected
  `add_i32_basic` case with artifact kind `production_tests` and logical path
  `tests/add_i32_basic_test.cpp`.
- One golden fixture plus provenance file.
- Structured diagnostics for wrong backend, wrong artifact kind, non-scalar
  extension, unsupported type, unsupported case shape, extra metadata,
  missing/ambiguous C++ type-spelling input, missing/zero/multiple selected
  cases when the slice requires exactly one, malformed vectors, and attempts to
  render unsupported legacy-test features.

Parity criterion:

The generated test source must be semantically equivalent to the selected
legacy evidence for test name, input values, expected values, wrapper-call
intent, `Vec` alias using the typed C++ `int32_t` spelling, boolean test
function shape, and `TEST` registration intent. Exact byte-for-byte legacy
template output is not selected.

Evidence paths:

- `tsldata/primitives/arithmetic/fundamental.tsl:6` for `add_i32_basic` input
  and expected vectors.
- `frozen/jinja/cpp/test_file.j2:1-56` for includes and `TEST(...)`
  registration evidence.
- `frozen/jinja/cpp/partials/test_common.j2:1-13` for the boolean test
  function and `Vec` alias shape.
- `frozen/jinja/cpp/test_case.j2:51-63` for binary test-case shape evidence.
- `frozen/jinja/cpp/partials/test_vectors.j2:38-50` for store-vector
  expansion evidence.
- `frozen/generator_specs/tests.yaml:45-59` for test-generation policy
  evidence.
- `docs/redesign/frozen-parity-baselines.md` `CPP-ADD-I32-TEST` entry for the
  selected baseline. `frozen/` remains evidence only.

Tests required:

- Golden fixture and provenance tests for
  `add_i32_basic_test.cpp`.
- Determinism tests for repeated rendering.
- Unit tests proving rendering consumes `TestSourcePlan` / `PlannedTestCase`
  data and an explicit typed type-spelling value, and does not read raw TSL or
  `frozen/` templates.
- Diagnostic tests for unsupported backend, artifact kind, extension, type,
  case shape, extra metadata, malformed vector values, missing/ambiguous type
  spelling, and wrong selected-case cardinality.
- Regression test proving the existing metadata-style C++ production-test
  artifact remains stable.

Golden fixtures required:

- `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`
- `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.provenance.md`

Documentation updates:

- Update behavioral spec, testing strategy, pipeline design, target
  architecture, open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the accepted M49 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_test_source_planning.py tslgen/tests/unit/test_cpp_production_test_rendering.py`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally making generated tests executable by default.
- Pulling legacy Jinja templates into runtime logic.
- Rendering from raw TSL instead of typed `TestSourcePlan` data.
- Inferring `int32_t` or the `Vec` alias from local renderer maps instead of
  consuming an explicit typed type-spelling value.
- Depending on unsupported load/store helpers or support-header behavior as if
  they were accepted.
- Expanding from one selected `add_i32_basic` case into broad generated-test
  parity.

Dependencies on prior milestones:

- Milestones 12, 17, 29, 35, 36, 37, 40, and 48.

## Deferred Parity Targets After Boundary Correction

The following previously planned targets remain valid but are deliberately
deferred until explicitly reintroduced as separate milestones:

- CLI workflow compatibility slice from old M41.
- Legacy coverage JSON adapter breadth beyond the selected M50 row.
- Broader C++ or Rust backend rendering beyond the corrected M40 call IR.
- Executable generated tests and compile/run orchestration.

When one of these targets is reintroduced, give it a fresh milestone number and
reuse the same milestone contract fields: goal, scope, out of scope, evidence
paths, accepted redesign inputs, expected outputs, parity criterion, tests,
golden fixtures, documentation updates, review risks, dependencies, and whether
it replaces or adapts a deferred target.

## Milestone 50: Legacy Coverage JSON Adapter Row Slice

Status:

Accepted. The M50 execution-review loop returned `Accept With Follow-Ups` after
one focused revision. Non-blocking follow-ups are tracked in
`docs/agent/current-redesign-state.md`.

Goal:

Render one deterministic legacy-style coverage JSON adapter row for the
selected `add` / `avx2` / `cpp` / `f32` baseline from accepted typed reporting
data. This reintroduces only the selected row-level report parity target from
old M42, without whole-report parity, HTML/site parity, CLI workflow changes, or
pipeline reruns during serialization.

Scope:

- Reporting adapter only.
- Selected row only: primitive `add`, extension `avx2`, language `cpp`, type
  `f32`.
- Produce selected legacy row fields in stable order:
  - `effective_present`;
  - `extension`;
  - `has_intrinsic`;
  - `has_lang_block`;
  - `has_tsil`;
  - `language`;
  - `missing_effective`;
  - `missing_intrinsic`;
  - `missing_lang_block`;
  - `missing_tsil`;
  - `primitive`;
  - `primitive_class`;
  - `template`;
  - `type`.
- Emit legacy string-valued booleans only at the adapter/serialization boundary.
  Internal reporting values must remain typed.
- Add a redesign-owned golden fixture:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`.
- Add fixture provenance that cites active source/report data and legacy
  evidence.
- Keep the existing redesign coverage JSON and HTML report behavior stable.

Out of scope:

- Whole `primitive_coverage.json` parity, row-count parity, or broad coverage
  matrix parity.
- Coverage HTML, MkDocs/site output, or documentation-report parity.
- CLI workflow compatibility, new CLI flags, stdout/stderr behavior changes, or
  writer/report file writes.
- Backend rendering, generation-time lowering, backend translation, generated
  C++ implementation output, test-source rendering, Rust output, compiler
  execution, or generated-test execution.
- Runtime dependency on `frozen/`, legacy report tools, or raw legacy JSON.
- Rerunning parsing, selection, lowering, backend rendering, or test planning
  during adapter serialization.

Required inputs:

- Accepted `PipelineCoverageReport` / primitive coverage DTOs or equivalent
  typed report data.
- A new M50 typed adapter request and selected-row fact value, derived from
  accepted report data, that carries the exact selected legacy-row facts for
  `add` / `avx2` / `cpp` / `f32`, including template `v:=(v,v)`, primitive
  class `fundamental`, `has_tsil=true`, `has_intrinsic=false`,
  `has_lang_block=false`, and `effective_present=true`. Do not pass untyped
  dictionaries as the adapter model.
- Existing deterministic JSON rendering helpers.
- M35 parity baseline entry `COVERAGE-ADD-AVX2-F32-ROW`.

Expected outputs:

- One typed legacy coverage-row adapter value or equivalent immutable adapter
  result for the selected row.
- One deterministic JSON artifact/string for that row, with stable field order
  matching the selected legacy row field order.
- One golden fixture plus provenance file.
- Structured diagnostics for unsupported adapter request, missing selected row,
  ambiguous selected row, missing required typed report fields, unavailable
  primitive class/template metadata, and attempts to serialize from raw legacy
  evidence instead of accepted report DTOs.

Parity criterion:

The selected adapter row must be semantically equivalent to
`frozen/out/reports/primitive_coverage.json:57762-57777` for the listed fields
and ordering. Whole-report byte-for-byte parity and full legacy field expansion
are not selected.

Evidence paths:

- `frozen/out/reports/primitive_coverage.json:57762-57777` for the selected
  legacy row.
- `frozen/tools/report_primitive_coverage.py:242-266` for legacy field
  construction and string-valued boolean evidence.
- `docs/redesign/frozen-parity-baselines.md` `COVERAGE-ADD-AVX2-F32-ROW`
  entry for the selected baseline. `frozen/` remains evidence only.

Tests required:

- Golden fixture and provenance tests for
  `add_avx2_f32_coverage_row.json`.
- Determinism tests for repeated adapter serialization.
- Unit tests proving the adapter consumes accepted typed coverage/report DTOs
  rather than raw legacy JSON or fresh parser/selection/lowering/rendering
  runs.
- Field mapping tests for selected `add`, `avx2`, `cpp`, `f32`,
  `fundamental`, `v:=(v,v)`, `has_tsil=true`, `has_intrinsic=false`,
  `has_lang_block=false`, and derived missing/effective fields.
- Diagnostic tests for unsupported request, missing selected row, ambiguous
  selected row, missing metadata, and raw legacy evidence/runtime-read attempts.
- Regression tests proving existing redesign coverage JSON and HTML reports
  remain stable.

Golden fixtures required:

- `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`
- `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.provenance.md`

Documentation updates:

- Update behavioral spec, testing strategy, pipeline design, target
  architecture, open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the accepted M50 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_coverage_reporting.py`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally expanding into whole-report parity or broad report matrix
  coverage.
- Treating legacy string booleans as the internal report model instead of
  adapter output.
- Inferring report facts from raw TSIL text or raw source files instead of
  accepted typed report data.
- Rerunning pipeline stages during serialization.
- Changing CLI/report stdout, artifact writing, or HTML behavior.
- Reading `frozen/` or legacy report JSON at runtime.

Dependencies on prior milestones:

- Implementation input dependencies: Milestones 15, 23, 24, and 25 reporting
  DTO/JSON/API foundations.
- Parity and chronology context only: Milestones 35, 39, 40, and 49. M50 must
  not borrow backend-call, generated-output, or test-source rendering machinery
  as implementation inputs.

## Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice

Status:

Accepted. The M51 execution-review loop returned `Accept With Follow-Ups` after
one focused documentation revision.

Goal:

Extend the accepted M48 signedness generation branch pruning slice to accept
the documented plain `else` branch spelling for the same exact signedness
predicate. M51 remains generation-time semantic lowering only and does not
lower conversion or shift bodies.

Scope:

- Recognize only this branch shape:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else {
    ...
  }
  ```

- Reuse the M48 signedness predicate evaluation over typed M43
  `GenerationTypeRef(kind="base.in")` values.
- Reuse the M42/M48 branch pruning model, branch provenance, deterministic
  pruning, and selected-branch-only unresolved-helper diagnostics.
- Treat plain `else` as equivalent to `else<generation>` only for this selected
  signedness predicate branch form.
- Preserve existing `else<generation>` signedness branch behavior.

Out of scope:

- Broad plain-`else` support for arbitrary generation branches.
- Primitive-attribute plain `else` support.
- Conversion or shift body parity.
- `switch<compile>`, `if<compile>`, direct `intrin<...>`, `let`, `var`, calls,
  vector transforms, loops, aliases, casts, arrays, generic lengths,
  immediates, vector/register metadata, and branch-body semantics.
- Backend translation, backend rendering, generated C++ output, generated test
  sources, Rust output, CLI/reporting, writer behavior, compiler execution, or
  generated-test execution.
- Signedness predicates over floats, masks, pointers, wildcard/generic tags,
  vector types, `si64`/`ui64`, or backend-scoped type requests unless a future
  milestone explicitly broadens the accepted type set.

Required inputs:

- M42 generation branch pruning and provenance behavior.
- M43 `GenerationTypeRef(kind="base.in", type_tag="si32" | "ui32")` values.
- M48 typed signedness predicate evaluation and diagnostics.
- Existing request-local `GenerationContext` type-tag override, selected type
  tag, selected candidate default behavior, and implementation source location.

Expected outputs:

- A pruned generation branch result, or equivalent lowered statement list, for
  the selected plain-`else` signedness branch form.
- Deterministic branch provenance that distinguishes the accepted plain `else`
  syntax when the existing model has a natural field for that information.
- Structured diagnostics for malformed plain-`else` branch syntax, unsupported
  condition expressions, missing generation/type context, unsupported nested
  type query shapes, unknown type tags, unsupported or non-integer tags,
  aggregate/generalized plain-`else` attempts, and unresolved helpers in the
  selected branch.
- Continued backend-translation rejection of raw unresolved generation helper
  text and continued renderer non-evaluation.

Parity criterion:

The selected plain-`else` signedness branch form must behave semantically like
the accepted M48 `else<generation>` form: signed selected types keep the true
branch, unsigned selected types keep the false branch, and unselected branch
helpers do not produce diagnostics. The behavior is derived from typed M43
generation type values, never from renderer/backend text rewriting.

Evidence paths:

- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` for the selected
  representative plain-`else` signedness branch shape.
- Additional same-predicate plain-`else` evidence:
  `tsldata/primitives/conversion/repr_change.tsl:540-649`, `:1093-1100`, and
  `:1160-1167`.
- M48 exact `else<generation>` comparison evidence:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- Legacy grammar and behavior evidence:
  `frozen/tsl-gen/tsl_gen/tsil.lark:24` and
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:5039`.
  `frozen/` remains evidence only.

Tests required:

- Unit tests where selected `si32` prunes a plain-`else` branch to the true
  branch and selected `ui32` prunes to the false branch.
- Regression tests proving M48 `else<generation>` signedness branches still
  behave unchanged.
- Selected-branch-only diagnostics for unresolved helpers in the selected
  branch and no diagnostics for unresolved helpers in the unselected branch.
- Diagnostic tests for malformed plain-`else` branch syntax, unsupported
  predicates, unsupported nested type queries, missing type context, unknown
  type tags, unsupported/non-integer tags such as `f32`, and unsupported
  generalized plain-`else` forms.
- Determinism tests for repeated plain-`else` pruning and diagnostic ordering.
- Boundary regression tests proving backend translation still rejects
  unresolved raw generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M51 is a lowering slice and must not change generated C++ or Rust
  output.

Documentation updates:

- Update lowering behavior, pipeline design, behavioral spec, testing
  strategy, open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the accepted M51 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Generalizing plain `else` support beyond the exact selected signedness
  branch form.
- Lowering conversion or shift branch bodies because the evidence is inside
  conversion code.
- Parsing raw `type<generation>(...)` text downstream instead of consuming typed
  M43 values.
- Letting backend translation, backend templates, or renderers evaluate
  signedness or generation-time branch semantics.
- Broadening the supported type set beyond the selected M43 `si32`/`ui32`
  inputs.

Dependencies on prior milestones:

- Milestones 18, 30, 40, 41, 42, 43, and 48.

## Post-M51 Planning Context

Milestones 1 through 51 are accepted. Milestone 51:
Plain-Else Signedness Generation Branch Lowering Slice completed with
`Accept With Follow-Ups`.

M49 reintroduced only the generated C++ test parity target from old M40 as a
single-test source-rendering slice. M50 reintroduces only the selected legacy
coverage JSON row target from old M42 as a pure reporting-adapter slice. CLI
workflow compatibility, whole-report coverage parity, coverage HTML/site parity,
broader C++/Rust rendering, executable generated tests, compiler execution, and
broad generated-test framework parity remain deferred.

M48 is constrained to generation-time semantic lowering over typed M43
`GenerationTypeRef(kind="base.in")` inputs. Broader native rendering,
prefix/post/infix/immediate modifiers, vector/register metadata, Rust output,
generated tests, compiler execution, and branch body semantics beyond the
selected pruning result remain deferred.

The post-M51 planning pass prioritizes lowering, per current project direction.
The next slice should continue the typed generation-time semantic model without
opening backend translation, rendering, output, CLI/reporting, Rust, compiler
execution, generated-test execution, vector metadata, or broad TSIL parsing.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Concrete integer generation type/signedness expansion | Builds directly on M43 `GenerationTypeRef` values and M48/M51 signedness branch pruning. Corpus evidence covers concrete 8/16/32/64-bit integer tags and signedness branches. | Low if kept to typed lowering and diagnostics; high if it expands backend suffix/type-spelling translation. | Select as M52. |
| `value<generation>(type::size_bytes(type<generation>(base::in)))` value query | Lowering-focused evidence exists in IO, bit-count, and array bodies. | Medium because it introduces a new general generation-value result model and surrounding bodies include broader unsupported constructs. | Defer until a value-query result slice is selected. |
| Vector/register metadata queries | Needed for later load/store and conversion work. | High now because evidence is coupled to loops, casts, calls, language maps, vector/register metadata, and backend requests. | Defer. |
| `packed` primitive-attribute branch pruning | Mechanically close to M42. | Low mechanically but low parity value now; likely invites mask/vector metadata work. | Defer until mask-store parity is selected. |

## Milestone 52: Concrete Integer Generation Type Semantics Slice

Status:

Accepted with follow-ups. The execution-review loop accepted the lowering-only
behavior described here.

Goal:

Extend the accepted generation-time lowering semantics from the selected
`si32`/`ui32` pair to the concrete integer tag family:

```text
si8, ui8, si16, ui16, si32, ui32, si64, ui64
```

M52 remains generation-time semantic lowering only. It broadens the supported
type set for already accepted exact helper forms; it does not add a new TSIL
helper family, backend translation, rendering, or generated output.

Scope:

- Support the existing exact M43 generation type query forms for all selected
  concrete integer tags:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

- Support the existing exact M48/M51 signedness predicate branch forms for all
  selected concrete integer tags:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else<generation> {
    ...
  }
  ```

  and the M51 plain `else` spelling for the same exact predicate.

- Express the concrete integer signed/unsigned companion mapping as typed rule
  values or typed evaluator functions, not raw text rewriting:

  ```text
  si8  <-> ui8
  si16 <-> ui16
  si32 <-> ui32
  si64 <-> ui64
  ```

- Preserve M42/M48/M51 branch provenance, deterministic ordering, and
  selected-branch-only diagnostics.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Out of scope:

- Backend translation expansion, including suffix, type-spelling, prefix, post,
  infix, or immediate modifier support for non-32-bit integer tags.
- C++ or Rust rendering, generated C++ or Rust output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, or generated-test
  execution.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`, or
  `idqword` as selected concrete type tags during lowering.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, and branch-body semantics.
- Shift or conversion body parity. Evidence from shifts and conversions is
  type/signedness-helper evidence only.

Required inputs:

- M43 `GenerationTypeRef` model and context type-tag resolution.
- M48 signedness predicate evaluator.
- M51 plain-`else` branch syntax support.
- Existing request-local `GenerationContext` type-tag override, selected
  candidate default behavior, and implementation source location.

Expected outputs:

- `GenerationTypeRef(kind="base.in", type_tag=<selected concrete integer tag>)`.
- `GenerationTypeRef(kind="base.signed_of", type_tag=<signed companion>,
  source_type_tag=<selected concrete integer tag>)`.
- `GenerationTypeRef(kind="base.unsigned_of", type_tag=<unsigned companion>,
  source_type_tag=<selected concrete integer tag>)`.
- Pruned signedness branches for signed and unsigned selected concrete integer
  tags, for both `else<generation>` and M51 plain `else` forms.
- Existing structured diagnostics for unsupported float, pointer, mask,
  wildcard/group, unknown, malformed, shorthand, unsupported nested, and
  unresolved-selected-branch cases.

Parity criterion:

For each selected concrete integer tag, generation-time type queries and
signedness branches must produce the same typed semantic result as the accepted
`si32`/`ui32` slice. Signed tags select the true branch; unsigned tags select
the false branch. The behavior is derived from typed concrete-integer rules and
typed M43/M48/M51 lowering values, never from backend/render text rewriting.

Evidence paths:

- `tsldata/detail/types.tsl:2-16` for concrete integer tags and integer groups.
- `tsldata/primitives/arithmetic/fundamental.tsl:10-21` for accepted add tests
  over 8/16/64-bit signed and unsigned types.
- `tsldata/primitives/arithmetic/fundamental.tsl:47-90` for `?i?` intrinsic
  suffix helper evidence using base signed companion queries.
- `tsldata/primitives/bitwise/shifts.tsl:603-618` for shift tests over
  8/16/64-bit integer tags.
- `tsldata/primitives/bitwise/shifts.tsl:625-635` for exact signedness branch
  evidence over `?i?`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` for plain-`else`
  signedness evidence in a `?i64` context. Branch bodies remain out of scope.
- Legacy canonicalization and signedness evidence may be consulted in
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`, but `frozen/`
  remains evidence only.

Tests required:

- Parameterized unit tests for `base::in`, `base::signed_of`, and
  `base::unsigned_of` across all selected concrete integer tags.
- Parameterized signedness branch pruning tests proving signed tags choose the
  true branch and unsigned tags choose the false branch for both
  `else<generation>` and plain `else`.
- Regression tests proving accepted `si32`/`ui32` behavior is unchanged.
- Diagnostic tests for `f32`, `f64`, `ptr`, mask tags, wildcard/group tags,
  unknown tags, shorthand forms, unsupported nested queries, and unresolved
  helpers in selected branches.
- Determinism tests for repeated type-query and signedness branch lowering.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M52 is a lowering slice and must not change generated C++ or Rust
  output.

Documentation updates:

- Update lowering behavior, pipeline design, behavioral spec, testing strategy,
  open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the accepted M52 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally expanding backend suffix/type-spelling translation for
  non-32-bit tags.
- Treating type groups such as `?i?`, `?i64`, `si?`, or `ui?` as selected
  concrete type tags.
- Letting shift or conversion branch-body constructs enter scope because the
  evidence appears inside shift/conversion bodies.
- Moving signedness or companion-type inference into backend translation or
  renderers.
- Encoding concrete integer rules as raw string rewrites instead of typed
  semantic rules.

Dependencies on prior milestones:

- Milestones 18, 40, 41, 42, 43, 48, and 51.

## Post-M52 Planning Context

Milestones 1 through 52 are accepted. Milestone 52:
Concrete Integer Generation Type Semantics Slice completed with
`Accept With Follow-Ups`.

M52 intentionally kept concrete integer signed/unsigned semantics as typed
rules instead of raw text rewriting. Its first implementation placed those
typed rules in the lowering boundary. The post-M52 planning pass prioritizes
cleaning that ownership boundary before adding any new helper behavior.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Catalog-validated concrete integer generation rule source | Directly addresses the M52 rule ownership concern. `tsldata/detail/types.tsl` and typed catalog `TypeGroup` data already identify concrete integer singleton tags and wildcard/group selectors. | Low if it preserves M52 behavior exactly and passes immutable typed rules into lowering; medium if it infers broad type semantics from names or groups. | Select as M53. |
| `value<generation>(type::size_bytes(type<generation>(base::in)))` value query | Lowering-focused corpus evidence exists in IO, load/store array, and bit-count bodies. | Medium because it introduces a new generation value result model and evidence is embedded in broader loops/casts/conditions. | Defer until a value-query result model slice is selected. |
| Backend suffix/type-spelling expansion for 8/16/64-bit integers | Useful after M52 because generation-time semantics now know those tags. | High now because it reopens M45/M46 translation limits and would mix rule-source cleanup with backend behavior. | Defer until after the rule-source boundary is clean. |
| Vector/register metadata queries | Needed for later load/store and conversion work. | High because evidence is coupled to lane metadata, language maps, loops, casts, calls, and backend requests. | Defer. |
| M49-M52 follow-up cleanup | Several non-blocking quality follow-ups remain. | Low individually, but they do not advance one coherent product/domain milestone. | Keep recorded as follow-ups. |

## Milestone 53: Catalog-Validated Concrete Integer Generation Rule Source Slice

Status:

Accepted. The M53 execution-review loop returned `Accept With Follow-Ups` after
one focused documentation revision.

Goal:

Move the accepted M52 concrete integer generation type/signedness semantics out
of the lowering-local private table and into an explicit typed domain/catalog
rule source, while preserving M52 behavior exactly.

M53 is an architectural boundary slice, not a behavior expansion. Generation
lowering should consume immutable typed rule values prepared at a domain,
catalog, or lowering-input boundary. Lowering must not read files, parse raw
TSL, or infer arbitrary integer semantics from tag spelling.

Scope:

- Introduce a typed concrete integer generation rule model outside
  `tslgen.lowering.boundary` for exactly:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Validate or construct that rule source from typed catalog/type-group data
  such as `TypeGroup` entries from `tsldata/detail/types.tsl`, while preserving
  the exact accepted M52 rule set:

  ```text
  si8  <-> ui8
  si16 <-> ui16
  si32 <-> ui32
  si64 <-> ui64
  ```

- Make generation-time lowering consume the typed rule source instead of owning
  the private concrete-integer rule table.
- Preserve all accepted M52 outputs for:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

  and exact M48/M51 signedness predicate branch pruning.

- Preserve M52 diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless a more precise rule-source diagnostic
  is needed for missing or inconsistent rule data.
- Keep backend-translation rejection of raw unresolved generation helpers and
  renderer non-evaluation unchanged.

Out of scope:

- New generation-time helper forms such as `type::size_bytes`.
- Backend suffix/type-spelling expansion beyond accepted M45/M46 `si32`/`ui32`
  behavior.
- C++ or Rust rendering, generated C++ or Rust output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, or generated-test
  execution.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`, or
  `idqword` as selected concrete type tags during lowering.
- Regex-derived acceptance of new concrete-looking tags such as `si128`.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, and branch-body semantics.
- Runtime dependency on `frozen/`, raw legacy TSL, or legacy generator logic.

Required inputs:

- Typed catalog type-group data for the selected concrete integer singleton
  tags and wildcard/group selectors.
- Existing M43/M48/M51/M52 lowering behavior and tests.
- Existing request-local generation context and selected candidate type tag
  behavior.

Expected outputs:

- A deterministic typed concrete integer generation rule set with signed
  companion, unsigned companion, and signedness facts.
- Existing M52 `GenerationTypeRef` and pruned branch results unchanged.
- Structured diagnostics for missing, incomplete, or inconsistent rule-source
  data if selected lowering needs that rule data.

Parity criterion:

For all accepted M52 inputs, M53 must produce the same semantic lowering
results and preserve the same unsupported selected-tag boundary. The only
intended architectural change is rule ownership: concrete integer semantics
move from a lowering-private table to a typed domain/catalog rule source.

Evidence paths:

- `tsldata/detail/types.tsl:2-9` for concrete integer singleton tags.
- `tsldata/detail/types.tsl:10-16` and `:20-24` for wildcard/group selectors
  that must remain unsupported as selected concrete lowering tags.
- `tslgen/src/tslgen/domain/types.py` for typed `TypeGroup` values.
- `tslgen/src/tslgen/domain/catalog.py` for typed catalog lookup/indexing.
- Current M52 tests in `tslgen/tests/unit/test_lowering_boundary.py` for the
  accepted behavior contract.

Tests required:

- Focused unit tests for the new typed rule source, including deterministic
  rule ordering.
- Rule-source validation tests for missing singleton tags, missing companion
  pairs, inconsistent singleton/group data, wildcard/group selectors, floats,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128`.
- Regression tests proving all M52 type-query and signedness branch behavior
  remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M53 is a semantic rule-source boundary slice and must not change
  generated C++ or Rust output.

Documentation updates:

- Update lowering behavior, pipeline design, behavioral spec, testing strategy,
  open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the selected M53 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- New focused rule-source test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally making lowering read the catalog, filesystem, or raw TSL
  directly.
- Replacing explicit typed rules with broad regex/string inference.
- Treating wildcard/group selectors as selected concrete type tags.
- Changing accepted M52 diagnostics, provenance, or deterministic ordering
  unintentionally.
- Letting backend translation consume the broader rule source and expand
  suffix/type-spelling behavior.
- Creating a broad type-system abstraction beyond the selected rule-source
  boundary.

Dependencies on prior milestones:

- Milestones 4, 18, 40, 41, 42, 43, 48, 51, and 52.

## Post-M53 Planning Context

Milestones 1 through 53 are accepted. Milestone 53:
Catalog-Validated Concrete Integer Generation Rule Source Slice completed with
`Accept With Follow-Ups`.

M53 moved the accepted M52 concrete integer generation type/signedness
semantics from a lowering-private table into typed domain/catalog rule values.
The M53 review left a non-blocking follow-up: normal pipeline-facing lowering
usage should wire catalog-derived rule values through the lowering input path
instead of relying on the synthetic default rule source.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Catalog-derived concrete integer generation rule pipeline wiring | Directly completes the M53 rule-source ownership boundary by passing typed catalog-derived rules into normal lowering use. | Low if kept to catalog/lowering-input wiring; medium if it becomes a broad pipeline rewrite or generic rule registry. | Select as M54. |
| Backend suffix/type-spelling expansion for 8/16/64-bit integers | Useful after M52/M53 because generation-time semantics now know those tags. | Medium because it reopens M45/M46 backend translation limits. | Defer until catalog-derived rule wiring is normal. |
| `value<generation>(type::size_bytes(type<generation>(base::in)))` value query | Lowering-focused corpus evidence exists in IO, load/store array, and bit-count bodies. | Medium to high because it introduces a new generation value family and evidence is embedded in loops/casts/memory operations. | Defer until a value-query result model slice is selected. |
| Vector/register metadata queries | Needed for later load/store and conversion work. | High because evidence is coupled to lane metadata, language maps, loops, casts, calls, and backend requests. | Defer. |
| Direct `intrin<...>` / broader semantic TSIL helper slices | Important for later parity. | High because it touches placeholder semantics, modifier resolution, and broader TSIL parsing. | Defer. |
| Broader generated tests, CLI/reporting breadth, Rust output, and compiler/toolchain orchestration | All remain useful parity families. | Medium to high and orthogonal to the current lowering rule-source boundary. | Defer. |
| M49-M53 follow-up cleanup | Several non-blocking quality follow-ups remain. | Low individually, but they do not all form one coherent milestone. | Keep recorded as follow-ups unless one becomes a selected architectural slice. |

## Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice

Status:

Accepted. The M54 execution-review loop returned `Accept With Follow-Ups` with
no blocking implementation issues and no focused revision. The remaining
follow-up is to add explicit `dword` / `qword` negative selected-tag test
subcases for tighter evidence traceability.

Goal:

Wire the accepted M53 concrete integer generation rule source through the
normal catalog/lowering-input path so generation lowering consumes
catalog-derived `ConcreteIntegerGenerationRuleSet` values for normal
pipeline-facing use, rather than silently relying on the synthetic default rule
source.

M54 is a pipeline/lowering-input wiring slice, not a behavior expansion. It
must preserve M52/M53 lowering behavior exactly while proving the accepted rule
source can be built from typed catalog `TypeGroup` data and supplied to
lowering before evaluation.

Scope:

- Build or expose the concrete integer generation rule set from accepted typed
  catalog/type-group data for exactly:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Thread that immutable rule set through the normal lowering-input path, such
  as `GenerationContext` / `LoweringRequest` construction or a focused
  pipeline/API adapter.
- Preserve the useful request-local default for unit tests only if normal
  pipeline-facing use has an explicit catalog-derived rule path.
- Prove selected lowering consumes an explicitly supplied catalog-derived rule
  set and does not hide missing or inconsistent explicit rule data behind the
  synthetic default.
- Preserve all accepted M52/M53 outputs for:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

  and exact M48/M51 signedness predicate branch pruning.

- Preserve M52/M53 diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless an explicit catalog-derived
  rule-source diagnostic is required for missing or inconsistent rule data.
- Keep backend-translation rejection of raw unresolved generation helpers and
  renderer non-evaluation unchanged.

Out of scope:

- New generation-time helper forms such as `type::size_bytes`.
- Backend suffix/type-spelling expansion beyond accepted M45/M46 `si32`/`ui32`
  behavior.
- C++ or Rust rendering, generated C++ or Rust output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, or generated-test
  execution.
- Broad generic semantic-rule registries or plugin systems before a second rule
  family demonstrates the need.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`,
  `idqword`, `dword`, or `qword` as selected concrete type tags during
  lowering.
- Regex-derived acceptance of new concrete-looking tags such as `si128`.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, and branch-body semantics.
- Lowering reading files, parsing raw TSL, querying the catalog during
  evaluation, or importing/executing `frozen/`.

Required inputs:

- Typed catalog `TypeGroup` data from `tsldata/detail/types.tsl`.
- Existing M53 `ConcreteIntegerGenerationRuleSet` / rule values and diagnostics.
- Existing selection/lowering request data, `GenerationContext`, and
  `LoweringRequest` behavior.
- Existing M43/M48/M51/M52/M53 lowering behavior and tests.

Expected outputs:

- A catalog-derived concrete integer generation rule set passed into lowering
  through a normal pipeline-facing path.
- Existing M52/M53 `GenerationTypeRef` and pruned branch results unchanged.
- Structured diagnostics for missing, incomplete, unsupported, or inconsistent
  explicit rule-source data without hidden fallback to defaults.

Parity criterion:

For all accepted M52/M53 inputs, M54 must produce the same semantic lowering
results. The only intended architectural change is wiring: normal
pipeline-facing lowering receives the concrete integer generation rules derived
from typed catalog data before lowering evaluates helper forms.

Evidence paths:

- `tsldata/detail/types.tsl:2-9` for concrete integer singleton tags.
- `tsldata/detail/types.tsl:10-16`, `:20-24`, and `:25-26` for wildcard/group
  selectors that must remain unsupported as selected concrete lowering tags.
- `tslgen/src/tslgen/domain/generation_rules.py` for typed M53 rule-source
  values and builder behavior.
- `tslgen/src/tslgen/domain/types.py` for typed `TypeGroup` values.
- `tslgen/src/tslgen/domain/catalog.py` for typed catalog lookup/indexing.
- `tslgen/src/tslgen/lowering/boundary.py` for `GenerationContext`,
  `LoweringRequest`, and lowering consumption of typed rule values.
- Current M52/M53 tests in `tslgen/tests/unit/test_lowering_boundary.py` and
  `tslgen/tests/unit/test_concrete_integer_generation_rules.py`.

Tests required:

- Focused unit tests proving catalog/type-group data can build the rule set and
  that repeated construction is deterministic.
- A lowering or pipeline-facing adapter test proving an explicitly
  catalog-derived `ConcreteIntegerGenerationRuleSet` is consumed by lowering.
- Negative tests proving missing singleton tags, missing companion pairs,
  inconsistent singleton/group data, wildcard/group selected tags, floats,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128` produce structured diagnostics without hidden default fallback.
- Regression tests proving all M52/M53 type-query and signedness branch
  behavior remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M54 is a pipeline/lowering-input wiring slice and must not change
  generated C++ or Rust output.

Documentation updates:

- Update lowering behavior, pipeline design, behavioral spec, testing strategy,
  open questions, design decisions, frozen parity baselines, and
  `docs/agent/current-redesign-state.md` for the selected M54 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_concrete_integer_generation_rules.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- New focused pipeline/lowering-input wiring test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally adding a broad semantic-rule registry before a second rule
  family exists.
- Letting lowering read files, parse raw TSL, or query the catalog during
  evaluation instead of consuming typed input values.
- Silently falling back to synthetic defaults when explicit catalog-derived rule
  data is missing or inconsistent.
- Expanding backend suffix/type-spelling translation or generated output under
  the guise of wiring.
- Changing accepted M52/M53 diagnostics, provenance, or deterministic ordering
  unintentionally.

Dependencies on prior milestones:

- Milestones 4, 18, 40, 41, 42, 43, 48, 51, 52, and 53.

## Post-M54 Planning Context

Milestones 1 through 54 are accepted. Milestone 54:
Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice
completed with `Accept With Follow-Ups`.

M54 made the accepted M53 concrete-integer rule source available through the
normal catalog/lowering-input path. The next lowering step can now introduce a
small typed generation-value result without letting backend translation or
renderers evaluate generation-time helper text.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Base scalar size-bytes generation value query | Directly advances generation-time semantic lowering by adding the first typed scalar generation-value result. Evidence exists in IO, bit-count, array, and conflict bodies for the exact `value<generation>(type::size_bytes(type<generation>(base::in)))` helper. | Medium if it broadens into loops, arithmetic, branch comparisons, vector metadata, backend translation, or float companion semantics. Low to medium if kept to one exact query and explicit scalar size-byte rules. | Select as M55. |
| Backend suffix/type-spelling expansion for 8/16/64-bit integers | Useful now that integer generation semantics and rule wiring exist. | Medium because it reopens M45/M46 backend translation limits and moves away from the current lowering focus. | Defer. |
| Vector/register metadata queries | Needed for future load/store and conversion work. | High because evidence is coupled to lane metadata, language maps, loops, casts, calls, masks, and backend requests. | Defer. |
| Direct `intrin<...>` / broader semantic TSIL helper slices | Important for later parity. | High because it touches placeholder semantics, modifier resolution, direct backend calls, and broader TSIL parsing. | Defer. |
| Broader generated tests, CLI/reporting breadth, Rust output, and compiler/toolchain orchestration | Useful parity families, but orthogonal to the current lowering direction. | Medium to high depending on slice. | Defer. |
| M49-M54 follow-up cleanup | Several non-blocking quality follow-ups remain. | Low individually, but they do not form the next lowering milestone. | Keep recorded as follow-ups unless one becomes a selected architectural slice. |

## Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice

Status:

Accepted. The M55 execution-review loop returned `Accept With Follow-Ups`
after one focused revision for strict exact-query parsing.

Goal:

Introduce the first typed generation-time scalar value result in semantic
lowering by supporting exactly:

```text
value<generation>(type::size_bytes(type<generation>(base::in)))
```

M55 is a generation-time semantic lowering slice only. It must produce a typed
integer generation value for the selected base scalar tag and must not lower the
surrounding IO, memory, array, branch-comparison, cast, loop, call, or direct
intrinsic bodies where the helper appears.

Scope:

- Add an explicit typed scalar size-byte rule/value source for exactly:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64, f32, f64
  ```

- Produce deterministic byte values:

  ```text
  si8/ui8 -> 1
  si16/ui16 -> 2
  si32/ui32/f32 -> 4
  si64/ui64/f64 -> 8
  ```

- Resolve the exact nested helper through the existing selected type-tag
  context precedence: explicit override, context selected tag, then selected
  candidate tag when enabled.
- Carry the result as a typed generation value, such as
  `GenerationValue(kind="type.size_bytes", value=<int>, type_tag=<tag>)` or an
  equivalent immutable value object.
- Build or expose the scalar size-byte rule/value source from typed
  catalog/type-group data before lowering evaluation, following the M54
  lowering-input pattern.
- Preserve M52-M54 behavior exactly for concrete-integer type refs,
  signed/unsigned companion refs, and signedness branch pruning.
- Accept `f32` and `f64` only for this exact size-bytes value query. M55 must
  not make standalone `type<generation>(base::in)` or
  `base::signed_of` / `base::unsigned_of` accept floats unless a later
  milestone explicitly selects that behavior.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Out of scope:

- Reusing or mutating `ConcreteIntegerGenerationRuleSet` for float size
  semantics. M55 should use explicit scalar size-byte rule/value records.
- Inferring sizes from regex, tag spelling, wildcard/group selectors, or
  unselected concrete-looking tags such as `si128`.
- Treating `arith`, `f?`, `?i?`, `?i64`, `si?`, `ui?`, `dword`, `qword`,
  `idqword`, `dqword`, or other group selectors as selected scalar tags during
  lowering.
- `type::size_bytes(...)` over `base::signed_of`, `base::unsigned_of`,
  `vector::imask`, `vector::register`, backend types, aliases, casts, arrays,
  generics, pointers, masks, or vector metadata.
- Generation-value arithmetic or comparisons such as `* 8`, `== 2`,
  `else if<generation>`, or branch pruning based on size-byte values.
- Lowering enclosing IO, memory-copy, array, bit-count, conflict, conversion,
  load/store, loop, cast, call, direct `intrin<...>`, `switch<compile>`, or
  `if<compile>` bodies.
- Backend suffix/type-spelling expansion, backend type/value translation,
  C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, broad TSIL parsing, or runtime dependency on `frozen/`.
- Lowering reading files, parsing raw TSL, or querying the catalog during
  evaluation.

Required inputs:

- Typed catalog `TypeGroup` singleton data from `tsldata/detail/types.tsl`.
- Existing selection/lowering request data, `GenerationContext`, and
  `LoweringRequest` behavior.
- Existing M54 catalog/lowering-input wiring pattern.
- Existing M43/M48/M51/M52/M53/M54 lowering behavior and tests.

Expected outputs:

- A typed scalar size-byte rule/value source for selected scalar tags.
- A typed generation value result for the exact size-bytes query.
- Structured diagnostics for missing type context, malformed query syntax,
  wrong arity, unsupported operands, unsupported selected tags, unknown tags,
  and malformed or incomplete explicit scalar size rule data.
- Existing M52-M54 integer type/signedness lowering results unchanged.

Parity criterion:

For the exact selected helper, M55 resolves the scalar byte size before backend
translation or rendering. For surrounding corpus bodies, M55 may still report
unsupported-body or unresolved-helper diagnostics; it does not claim broad IO,
array, bit-count, memory-copy, loop, cast, call, or branch-body parity.

Evidence paths:

- `tsldata/detail/types.tsl:2-9` for integer singleton tags.
- `tsldata/detail/types.tsl:17-19` for `f32` and `f64` singleton tags plus
  the `f?` group that remains unsupported as a selected tag.
- `tsldata/detail/types.tsl:10-16`, `:20-26` for wildcard/group selectors that
  must remain unsupported as selected scalar tags.
- `tsldata/primitives/io/out.tsl:7`, `:22`, and `:43-52` for `arith` IO
  evidence with integer and float tests plus implementation use of the exact
  helper.
- `tsldata/primitives/bitwise/bit_counts.tsl:91-99` for float bit-count
  evidence using the exact helper.
- `tsldata/primitives/load_store/array.tsl:101-109` for array/SVE comparison
  evidence. M55 selects only the nested value query, not the comparisons or
  branch bodies.
- `tsldata/primitives/misc/conflict.tsl:59-79` for integer conflict evidence.
- `frozen/` remains evidence only and is not needed for the selected M55 slice.

Tests required:

- Unit tests proving the exact query returns `1`, `2`, `4`, or `8` for every
  selected scalar tag.
- Tests proving `f32` and `f64` are accepted only for the exact size-bytes
  query and do not broaden standalone `base.in` or signed/unsigned companion
  behavior.
- Context precedence tests for type-tag override, context-selected tag, and
  selected candidate default.
- Diagnostics for missing type context, malformed value query syntax, wrong
  arity, unsupported nested operands, unsupported wildcard/group tags,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128`.
- Tests proving malformed or incomplete explicit scalar size rule data is not
  hidden by a synthetic fallback.
- Regression tests proving all accepted M52-M54 type-query, signedness branch,
  rule-source, and catalog-wiring behavior remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.
- Determinism tests for repeated query and rule construction.

Golden fixtures required:

- None. M55 is a lowering/value-query slice and must not change generated C++
  or Rust output.

Documentation updates:

- Update lowering behavior, generation-time helper inventory, pipeline design,
  behavioral spec, testing strategy, open questions, design decisions, frozen
  parity baselines, and `docs/agent/current-redesign-state.md` for the
  selected M55 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused scalar size-byte rule/value test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally broadening standalone `type<generation>(base::in)` to floats or
  broadening signed/unsigned companion semantics to floats.
- Reusing integer companion rules for scalar size semantics instead of adding
  explicit typed scalar size-byte rules.
- Inferring sizes from tag spelling, wildcard/group selectors, or regex.
- Lowering arithmetic/comparison/body constructs around the selected helper.
- Expanding backend translation, rendering, generated output, CLI/reporting,
  Rust, or compiler/test execution under the guise of value-query support.

Dependencies on prior milestones:

- Milestones 4, 18, 40, 41, 42, 43, 48, 51, 52, 53, and 54.

## Post-M55 Planning Context

Milestones 1 through 55 are accepted. Milestone 55:
Base Scalar Size-Bytes Generation Value Query Slice completed with
`Accept With Follow-Ups` after one focused revision for strict exact-query
parsing.

M55 introduced a typed scalar size-byte generation value. The next lowering
step can build directly on that typed value, but should not combine value
arithmetic, value comparisons, branch-chain syntax, branch pruning, body
lowering, backend translation, rendering, output, or toolchain behavior in one
milestone.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Size-bytes times-eight generation value arithmetic | Directly extends M55 by deriving bit-width values from the typed `type.size_bytes` value. Evidence appears in IO and conflict bodies as `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`. | Low to medium if restricted to one exact expression and typed value output; high if it becomes broad expression parsing or body lowering. | Select as M56. |
| Size-byte equality branch pruning over `== 2`, `== 4`, and `== 8` | Evidence exists in the SVE array branch chain. It would advance toward branch pruning over typed generation values. | Medium to high because it combines comparison semantics, `else if<generation>` chain syntax, selected-branch provenance, direct intrinsics in branch bodies, and no-final-else policy questions. | Defer until after the exact arithmetic value slice or select separately with tight branch-chain scope. |
| Vector/register metadata queries | Needed for later load/store and conversion work. | High because evidence is coupled to lane metadata, language maps, loops, casts, calls, and backend requests. | Defer. |
| Backend suffix/type-spelling expansion for 8/16/64-bit integers | Useful after M52-M55 typed lowering semantics. | Medium because it reopens M45/M46 backend translation limits and moves away from the current lowering focus. | Defer. |
| Direct `intrin<...>` / broader semantic TSIL helper slices | Important for later parity. | High because it touches placeholder semantics, modifier resolution, direct backend calls, and broad TSIL parsing. | Defer. |
| Broader generated tests, CLI/reporting breadth, Rust output, and compiler/toolchain orchestration | Useful parity families, but orthogonal to the current lowering direction. | Medium to high depending on slice. | Defer. |
| M49-M55 follow-up cleanup | Several non-blocking quality follow-ups remain. | Low individually, but they do not form the next lowering milestone. | Keep recorded as follow-ups unless one becomes a selected architectural slice. |

## Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice

Status:

Accepted by the M56 execution-review loop with `Accept With Follow-Ups`.

Goal:

Extend M55's typed generation-time scalar value result with exactly one
arithmetic expression:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) * 8
```

M56 is a generation-time semantic lowering slice only. It should produce a
typed integer generation value representing the selected scalar base type's bit
width. It must not lower the surrounding IO, conflict, loop, cast, call,
direct-intrinsic, branch, array, or memory bodies where the expression appears.

Scope:

- Reuse the M55 exact nested size-byte query and scalar size-byte rule source.
- Support only the exact `size_bytes * 8` expression where the left operand is
  the M55 value query and the right operand is the integer literal `8`.
- Produce deterministic bit-width values:

  ```text
  si8/ui8 -> 8
  si16/ui16 -> 16
  si32/ui32/f32 -> 32
  si64/ui64/f64 -> 64
  ```

- Carry the result as a typed generation value, such as
  `GenerationValue(kind="type.size_bits", value=<int>, type_tag=<tag>)` or an
  equivalent immutable value object.
- Preserve M55 context precedence: explicit override, context selected tag,
  then selected candidate tag when enabled.
- Preserve all accepted M52-M55 type-query, signedness branch, rule-source,
  catalog-wiring, and size-byte query behavior.
- Accept `f32` and `f64` only through the M55 exact size-bytes operand. M56
  must not broaden standalone `type<generation>(base::in)` or
  `base::signed_of` / `base::unsigned_of` behavior to floats.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Out of scope:

- General arithmetic expression parsing.
- Operators other than this exact `*` expression.
- Literal values other than `8`.
- Reversed operands such as `8 * value<generation>(...)`.
- Parenthesized, nested, chained, divided, added, subtracted, modulo, unary, or
  mixed arithmetic expressions.
- Comparisons such as `== 2`, `== 4`, or `== 8`.
- Branch pruning based on size values, `else if<generation>`, branch-chain
  syntax, or no-final-else branch policy.
- Lowering enclosing IO, conflict, array, bit-count, horizontal, conversion,
  mask, load/store, loop, cast, call, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, or memory-copy bodies.
- Backend suffix/type-spelling expansion, backend type/value translation,
  C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- Lowering reading files, parsing raw TSL, or querying the catalog during
  evaluation.

Required inputs:

- M55 typed `GenerationValue(kind="type.size_bytes")` behavior.
- M55 scalar size-byte rules from typed catalog/type-group data.
- Existing `GenerationContext` and `LoweringRequest` behavior.
- Existing M43/M48/M51/M52/M53/M54/M55 lowering behavior and tests.

Expected outputs:

- A typed generation value result for the exact `size_bytes * 8` expression.
- Structured diagnostics for malformed arithmetic expression syntax,
  unsupported operators, unsupported literals, unsupported operands, missing
  type context, unsupported or unknown tags, and malformed or incomplete
  explicit scalar size rule data reused from M55.
- Existing M52-M55 lowering results unchanged.

Parity criterion:

For the exact selected expression, M56 resolves the scalar bit width before
backend translation or rendering. For surrounding corpus bodies, M56 may still
report unsupported-body or unresolved-helper diagnostics; it does not claim
broad IO, conflict, array, bit-count, memory-copy, loop, cast, call,
branch-chain, or direct-intrinsic parity.

Evidence paths:

- `tsldata/primitives/io/out.tsl:43`, `:46`, `:48`, `:50`, `:52`, `:70`,
  `:73`, `:75`, `:77`, and `:79` for IO uses of the exact size-byte query
  multiplied by `8`.
- `tsldata/primitives/misc/conflict.tsl:79` for conflict logic using the exact
  size-byte query multiplied by `8`.
- `tsldata/detail/types.tsl:2-9` for integer singleton tags.
- `tsldata/detail/types.tsl:17-19` for `f32` and `f64` singleton tags plus the
  `f?` group that remains unsupported as a selected tag.
- `tsldata/detail/types.tsl:10-16`, `:20-26` for wildcard/group selectors that
  must remain unsupported as selected scalar tags.
- `frozen/tsl-gen/tsl_gen/tsil.lark` may remain syntax evidence for arithmetic
  shape only; `frozen/` must not become runtime input.

Tests required:

- Unit tests proving the exact expression returns `8`, `16`, `32`, or `64` for
  every selected scalar tag.
- Tests proving `f32` and `f64` are accepted only through the exact M55
  size-byte operand and do not broaden standalone `base.in` or signed/unsigned
  companion behavior.
- Context precedence tests for type-tag override, context-selected tag, and
  selected candidate default.
- Diagnostics for malformed arithmetic expression syntax, unsupported
  operators, unsupported literals, reversed operands, unsupported nested
  operands, unsupported wildcard/group tags, pointers, masks, unknown tags, and
  concrete-looking unselected tags such as `si128`.
- Regression tests proving all accepted M52-M55 type-query, signedness branch,
  rule-source, catalog-wiring, and size-byte query behavior remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.
- Determinism tests for repeated expression lowering.

Golden fixtures required:

- None. M56 is a lowering/value-expression slice and must not change generated
  C++ or Rust output.

Documentation updates:

- Update lowering behavior, generation-time helper inventory, pipeline design,
  behavioral spec, testing strategy, open questions, design decisions, frozen
  parity baselines, and `docs/agent/current-redesign-state.md` for the selected
  M56 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused size-bytes times-eight generation value test command selected by
  the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally introducing broad expression parsing.
- Accepting reversed operands, arbitrary literals, or unrelated arithmetic
  operators.
- Pulling in size-value comparisons, branch pruning, or `else if<generation>`.
- Lowering enclosing IO/conflict bodies instead of only the selected
  generation-time value expression.
- Inferring sizes from tag spelling, wildcard/group selectors, or regex instead
  of consuming typed M55 rules and values.
- Expanding backend translation, rendering, generated output, CLI/reporting,
  Rust, or compiler/test execution under the guise of value-expression support.

Dependencies on prior milestones:

- Milestones 4, 18, 40, 41, 42, 43, 48, 51, 52, 53, 54, and 55.

## Post-M56 Planning Context

Milestones 1 through 56 are accepted. Milestone 56:
Size-Bytes Times-Eight Generation Value Arithmetic Slice completed with
`Accept With Follow-Ups` and no focused revision.

M56 introduced a typed scalar bit-width generation value while keeping
comparisons and branch pruning out of scope. The next requested planning
direction is still lowering-focused. User review of the first post-M56 plan
identified that size-byte comparison evaluation should be separated from
branch-chain pruning so lowering can proceed through smaller typed steps.

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Size-byte equality generation predicate lowering | Directly extends M55 by evaluating exact `type.size_bytes == 2`, `== 4`, and `== 8` predicates as typed boolean generation predicate results before any branch-chain policy. | Low to medium if restricted to exact predicates and typed results; high if it becomes general comparison parsing or branch pruning. | Select as revised M57. |
| Size-byte equality generation branch-chain pruning | Needed for the SVE array branch chain after predicate lowering exists. | Medium because it combines comparison consumption, `else if<generation>` chain syntax, selected/no-match provenance, and no-final-else policy. | Defer until after M57 predicate lowering. |
| Vector/register metadata queries | Needed for later load/store and conversion body parity. | High because evidence is coupled to vector length/alignment, language maps, loops, casts, calls, and backend requests. | Defer. |
| Backend suffix/type-spelling expansion for 8/16/64-bit integers | Useful after M52-M56 typed lowering semantics. | Medium because it reopens M45/M46 backend translation limits and moves away from the requested lowering focus. | Defer. |
| Direct `intrin<...>` / SVE body lowering | Appears inside the M57 evidence branches. | High because it touches direct backend calls, vector predicates, statement semantics, and rendering/output concerns. | Defer. |
| M49-M56 follow-up cleanup | Several non-blocking quality follow-ups remain. | Low individually, but they do not form the next lowering milestone. | Keep recorded as follow-ups unless one becomes a selected architectural slice. |

## Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice

Status:

Accepted with follow-ups.

Goal:

Extend generation-time semantic lowering with exact scalar size-byte equality
predicates over M55 scalar size-byte values:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) == 2
value<generation>(type::size_bytes(type<generation>(base::in))) == 4
value<generation>(type::size_bytes(type<generation>(base::in))) == 8
```

M57 should produce typed predicate results only. It must not prune branch
chains, introduce `else if<generation>` syntax, or lower any surrounding SVE
array body or direct intrinsic branch body.

Scope:

- Consume M55 typed `GenerationValue(kind="type.size_bytes")` behavior and
  explicit scalar size-byte rules.
- Support only the exact `==` predicates where the left operand is the M55
  size-byte value query and the right operand is one of the integer literals
  `2`, `4`, or `8`.
- Produce deterministic boolean predicate results for selected scalar tags:

  ```text
  si8/ui8 -> false for 2/4/8
  si16/ui16 -> true only for 2
  si32/ui32/f32 -> true only for 4
  si64/ui64/f64 -> true only for 8
  ```

- Carry the result as a typed generation predicate, such as
  `GenerationPredicate(kind="type.size_bytes.equals", literal=<int>,
  value=<bool>, type_tag=<tag>)` or an equivalent immutable value object.
- Preserve M55/M56 context precedence and scalar-size rule behavior.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Out of scope:

- Branch pruning, `if<generation>` parsing, `else if<generation>` syntax,
  branch-chain pruning, selected-arm/no-match provenance, final `else`, broad
  no-final-else policy, and branch-body semantics.
- Standalone comparison forms outside the exact selected predicates.
- General comparison expression evaluation.
- Operators other than the exact selected `==` predicates.
- Literals other than `2`, `4`, and `8`.
- Reversed comparisons such as `2 == value<generation>(...)`.
- Nested, chained, parenthesized, bit-width, arithmetic, or mixed comparisons.
- Lowering the SVE array body, assignments, variables, arrays, calls, casts,
  loops, `emit_return`, `intrin<svptrue_b*>`, `intrin<svst1>`, direct
  `intrin<...>`, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, or vector
  predicate semantics.
- Backend suffix/type-spelling expansion, backend type/value translation,
  C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- Lowering reading files, parsing raw TSL, or querying the catalog during
  evaluation.

Required inputs:

- M55 typed `GenerationValue(kind="type.size_bytes")` behavior.
- M55 scalar size-byte rules from typed catalog/type-group data.
- M54 catalog-to-lowering request wiring for size-byte rules.
- Existing `GenerationContext` and `LoweringRequest` behavior.
- Existing M52-M56 lowering behavior and tests.

Expected outputs:

- A typed boolean predicate result for each exact selected size-byte equality
  predicate.
- Structured diagnostics for malformed predicate syntax, unsupported
  operators, unsupported literals, reversed operands, unsupported nested or
  mixed operands, missing type context, unsupported or unknown tags, and
  malformed or incomplete explicit scalar size rule data reused from M55.
- Existing M42/M48/M51/M52/M53/M54/M55/M56 lowering results unchanged.

Parity criterion:

For the exact selected predicates, M57 resolves boolean predicate values before
any future branch pruning, backend translation, or rendering. It does not claim
broad SVE array, load/store, direct-intrinsic, vector metadata, branch-chain,
or generated-output parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the exact size-byte
  equality predicates with literals `2`, `4`, and `8` inside a future
  branch-chain context.
- `tsldata/detail/types.tsl:2-9` for integer singleton tags.
- `tsldata/detail/types.tsl:17-19` for `f32` and `f64` singleton tags plus the
  `f?` group that remains unsupported as a selected tag.
- `tsldata/detail/types.tsl:10-16`, `:20-26` for wildcard/group selectors that
  must remain unsupported as selected scalar tags.
- `frozen/tsl-gen/tsl_gen/tsil.lark` may remain syntax evidence for
  comparison shape only if needed; `frozen/` must not become runtime input.

Tests required:

- Unit tests proving each selected scalar tag produces the expected boolean
  value for `== 2`, `== 4`, and `== 8`.
- Unit tests proving `si8`/`ui8` return `false` for all selected predicates
  without involving branch-chain no-match policy.
- Diagnostics for malformed predicates, unsupported operators, unsupported
  literals, reversed comparisons, nested or mixed operands, unsupported
  wildcard/group tags, pointers, masks, unknown tags, and concrete-looking
  unselected tags such as `si128`.
- Regression tests proving accepted M42/M48/M51 branch pruning and M52-M56
  type/value lowering behavior remains unchanged.
- Boundary tests proving M57 does not parse or prune `if<generation>` /
  `else if<generation>` chains.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.
- Determinism tests for repeated predicate lowering.

Golden fixtures required:

- None. M57 is a lowering/predicate slice and must not change generated C++ or
  Rust output.

Documentation updates:

- Update lowering behavior, generation-time helper inventory, pipeline design,
  behavioral spec, testing strategy, open questions, design decisions, frozen
  parity baselines, and `docs/agent/current-redesign-state.md` for the revised
  M57 predicate boundary. Keep branch-chain pruning recorded as future work.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused size-byte equality predicate test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally introducing broad comparison parsing or branch-chain syntax.
- Pulling in `if<generation>`, `else if<generation>`, selected-arm/no-match
  provenance, direct intrinsics, assignments, or branch-body semantics.
- Treating `si8`/`ui8` false predicates as branch-chain no-match behavior.
- Pulling in vector/register metadata, SVE predicate semantics, backend
  translation, rendering, generated output, CLI/reporting, Rust, or
  compiler/test execution.
- Inferring sizes from tag spelling, wildcard/group selectors, or regex
  instead of consuming typed M55 rules and values.

Dependencies on prior milestones:

- Milestones 4, 18, 40, 41, 42, 43, 48, 51, 52, 53, 54, 55, and 56.

## Post-M57 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Generation-time lowering stage pipeline boundary | Makes the accepted M55 value, M56 arithmetic-value, and M57 predicate results explicit as staged typed outputs before any branch-chain pruning. This directly addresses the staged lowering architecture and lets later control-flow consume typed results instead of reparsing raw helper text. | Low to medium if behavior-preserving; high if it becomes a broad refactor or second evaluator. | Select as M58. |
| Size-byte equality generation branch-chain pruning | Evidence exists in the SVE array chain and it is the next behavioral consumer of M57 predicates. | Medium because it combines `else if<generation>` chain syntax, no-match provenance for byte size `1`, selected-arm policy, and opaque body handling. | Defer until after M58 stage boundary. |
| Opaque selected branch body handoff | Needed after branch-chain pruning so later body-lowering slices see only selected branch text. | Medium if kept opaque; high if it starts parsing direct intrinsics, assignments, arrays, loops, calls, vector metadata, or renderer/backend semantics. | Defer until after branch-chain pruning. |
| Direct `intrin<...>` / SVE body lowering | Present inside the same array evidence. | High because it touches direct backend calls, vector predicates, body semantics, and rendering/output concerns. | Defer. |
| M49-M57 follow-up cleanup | Several accepted follow-ups remain. | Low individually, but cleanup does not form the next lowering architecture milestone. | Keep recorded as follow-ups unless one is selected separately. |

## Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice

Status:

Accepted. The M58 execution-review loop returned `Accept With Follow-Ups`
after one focused documentation revision.

Goal:

Make the generation-time semantic lowering stage contract explicit around the
accepted helper/expression work:

```text
helper/expression recognition
-> typed generation values
-> typed generation predicates
-> generation control-flow pruning
-> selected body lowering
```

M58 should not add new helper semantics. It should organize the accepted M55
`type.size_bytes` value, M56 `type.size_bits` value, and M57
`type.size_bytes.equals` predicate results so future branch pruning consumes
typed results instead of reparsing raw generation helper text.
The goal is an extendable and maintainable stage contract, not a cosmetic
wrapper around existing functions and not a broad replacement evaluator.

Scope:

- Define or refine typed records for the generation-time lowering stage
  boundary, including expression recognition, resolved value results, and
  resolved predicate results where needed.
- Give each introduced or refined stage boundary explicit typed inputs and
  outputs so later lowering stages can be added locally.
- Show how M59 branch-chain pruning can consume typed predicate or staged
  results without backend/rendering changes.
- Preserve existing M55/M56/M57 observable lowered outputs exactly.
- Preserve existing M42/M48/M51 generation branch-pruning behavior exactly.
- Keep `LoweringPlan` / `LoweredImplementation` public behavior stable unless a
  narrow typed stage result must be exposed.
- Prove backend translation still rejects raw unresolved generation helpers and
  renderers remain non-evaluating.
- Keep catalog-derived rule construction before lowering evaluation; lowering
  evaluation must consume typed request/context values only.

Out of scope:

- New generation-time helper forms.
- New arithmetic, comparison, or predicate semantics.
- Size-byte equality branch-chain pruning.
- `else if<generation>` support.
- No-match provenance for size-byte branch chains.
- Final `else`, broad no-final-else policy, nested generation branches, or
  broad generation control-flow semantics.
- Opaque selected branch body handoff.
- Direct `intrin<...>` / SVE body lowering, assignments, variables, arrays,
  loops, calls, casts, vector/register metadata, vector length/alignment, or
  backend uninit values.
- Backend translation expansion, rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, Rust, compiler execution,
  generated-test execution, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

Required inputs:

- M53/M54 typed rule-source and catalog-derived lowering request wiring.
- M55 `GenerationValue(kind="type.size_bytes")` behavior.
- M56 `GenerationValue(kind="type.size_bits")` behavior.
- M57 `GenerationPredicate(kind="type.size_bytes.equals")` behavior.
- Existing M42/M48/M51 branch-pruning behavior and provenance.
- Existing backend raw-helper rejection and renderer non-evaluation tests.

Expected outputs:

- A typed staged-lowering contract or equivalent explicit stage records that
  make accepted generation values and predicates available to later
  control-flow pruning without backend/renderers evaluating helpers.
- The concrete M58 implementation exposes this contract as deterministic typed
  stage records on lowered implementations: helper/expression recognition,
  typed generation values, typed generation predicates, generation control-flow
  pruning, and selected-body lowering.
- A maintainable extension path for future lowering stages, especially M59
  branch-chain pruning, without concentrating future behavior in one broad
  central string-matching or `if`/`elif` evaluator.
- Unchanged accepted M42/M48/M51/M55/M56/M57 lowering behavior.
- No generated C++ or Rust artifacts.

Parity criterion:

M58 proves the value -> predicate -> control-flow path is represented by typed
lowering-stage values. It does not claim branch-chain, SVE array, direct
intrinsic, selected body, backend translation, rendering, generated output, or
compiler parity.

Evidence paths:

- Accepted M55/M56/M57 lowering tests and implementation for existing typed
  values and predicates.
- `tsldata/primitives/load_store/array.tsl:107-109` as future consumer
  evidence showing why predicates must be handed to control-flow as typed
  values before branch-chain pruning.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.
- `frozen/tsl-gen/tsl_gen/tsil.lark` may remain optional syntax evidence only;
  `frozen/` must not become runtime input.

Tests required:

- Regression tests proving M55, M56, and M57 lowered results are unchanged.
- Regression tests proving M42/M48/M51 branch-pruning results are unchanged.
- Tests proving accepted generation values and predicates are visible through
  the staged contract.
- Tests proving M57 array branch-chain input still does not prune in M58.
- Backend raw-helper rejection and renderer non-evaluation regressions.
- Determinism tests for the staged outputs.

Golden fixtures required:

- None. M58 is a lowering-stage contract slice and must not change generated
  C++ or Rust output.

Documentation updates:

- Update the roadmap, generation-time lowering contract, behavioral spec,
  pipeline design, target architecture, testing strategy, open questions,
  design decisions, frozen parity baselines, and `docs/agent/current-redesign-state.md`
  for the selected M58 boundary.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused stage-boundary lowering test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Turning M58 into a broad lowering refactor without a typed behavioral
  contract.
- Producing only a cosmetic wrapper that does not make future stages easier to
  add or review.
- Accidentally adding branch-chain pruning, `else if<generation>`, no-match
  policy, or selected body handoff.
- Adding general expression parsing or a second evaluator instead of typed
  records over accepted semantics.
- Letting backend translation/rendering evaluate generation helpers.
- Making lowering evaluation read files, parse raw TSL, query the catalog, or
  depend on `frozen/`.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 56, and 57.

## Post-M58 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Size-byte equality generation branch-chain pruning | M57 resolves exact `type.size_bytes == 2/4/8` predicates and M58 exposes them through typed stage records. The SVE array evidence has exactly this no-final-else branch chain. | Medium if it becomes broad `else if<generation>` parsing, selected-body handoff, or direct SVE/body lowering; low to medium if it consumes typed M57/M58 predicate outputs and keeps bodies opaque. | Select as M59. |
| Opaque selected branch body handoff | Needed after branch-chain pruning so later body-lowering slices see only selected branch text. | Medium if kept opaque; high if it starts parsing direct intrinsics, assignments, arrays, loops, calls, vector metadata, or renderer/backend semantics. | Select as M60 after M59 acceptance. |
| Small M58 staged-predicate reuse cleanup | M58 review noted that M59 should not duplicate private staged predicate assembly or consume raw recognition text. | Low if used only as a tiny enabling cleanup; medium if it becomes a standalone refactor milestone. | Fold only the minimal enabling cleanup into M59 if needed; do not select separately. |
| Direct `intrin<...>` / SVE body lowering | Present around and inside the same array evidence. | High because it touches direct backend calls, vector predicates, body semantics, and rendering/output concerns. | Defer. |
| M49-M59 follow-up cleanup | Several accepted follow-ups remain. | Low individually, but cleanup does not form the next lowering architecture milestone. | Keep recorded as follow-ups unless one is selected separately. |

## Staged Lowering Path After M59

This path is recorded now because the post-M56 planning discussion identified a
clear architectural direction: generation-time lowering should proceed through
small typed stages rather than repeatedly recognizing entire surrounding
strings. M59 and M60 are now accepted, and post-M60 planning selects M61 for
human acceptance as the next lowering-focused candidate. The following
milestones must still be reviewed and accepted one at a time before execution.

### Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice

Status:

Accepted. M59 returned `Accept With Follow-Ups` after one focused
documentation revision.

Goal:

Consume typed M57/M58 size-byte equality predicate stage results to prune
exactly the SVE array no-final-else branch chain:

```text
if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { ... }
else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { ... }
else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { ... }
```

M59 proves the accepted staged lowering contract is useful for control-flow
pruning without reparsing raw generation helper text in backend translation,
renderers, or a second broad branch-chain evaluator.

Scope:

- Consume typed predicate results and stage records from M57/M58 instead of
  evaluating comparisons inside the branch-chain parser.
- Recognize only the exact no-final-else chain shape from
  `tsldata/primitives/load_store/array.tsl:107-109`, with arms in the
  documented `== 2`, `== 4`, then `== 8` order.
- Select the matching arm for byte sizes `2`, `4`, or `8`.
- Record explicit no-match provenance for byte size `1` without synthesizing a
  final `else`.
- Keep all branch bodies opaque; M59 may preserve selected-arm text/provenance
  as part of the pruning result, but it must not introduce the M60 selected
  body handoff contract.
- If M59 needs access to staged predicate details outside `_lower_input`, make
  the smallest typed reuse cleanup needed to avoid duplicating private staged
  predicate assembly or re-evaluating raw helper text.
- Preserve M42/M48/M51 selected-branch-only diagnostic principles where they
  apply to the selected chain.

Out of scope:

- Standalone comparison evaluation.
- Broad `else if<generation>` syntax beyond the exact selected chain shape.
- Final `else`, reordered chains, missing arms, duplicate arms, nested
  branches, or broad no-final-else policy.
- Opaque selected branch body handoff as a reusable input to later body-lowering
  stages.
- Direct-intrinsic/body lowering, SVE array body lowering, assignments,
  variables, arrays, calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting, writer
  behavior, Rust, compiler execution, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

Required inputs:

- M55 `GenerationValue(kind="type.size_bytes")` behavior.
- M57 `GenerationPredicate(kind="type.size_bytes.equals")` behavior for
  literals `2`, `4`, and `8`.
- M58 typed `GenerationLoweringStage` records for helper/expression
  recognition, typed generation values, typed generation predicates, and
  generation control-flow pruning.
- Existing M42/M48/M51 branch-pruning provenance and selected-branch-only
  diagnostic principles.

Expected outputs:

- A typed branch-chain pruning result or equivalent typed stage record that
  identifies the selected arm for byte sizes `2`, `4`, and `8`.
- Explicit no-match provenance for byte size `1`.
- Opaque selected-arm body text/provenance retained only as pruning metadata,
  not as a general selected-body handoff contract.
- No backend translation, rendering, or generated artifact output.

Parity criterion:

M59 proves exactly the SVE size-byte branch-chain control-flow decision can be
made from typed lowering predicate/stage outputs. It does not claim SVE body,
direct intrinsic, vector metadata, backend translation, rendering, generated
output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the exact SVE
  no-final-else size-byte branch chain.
- Accepted M57 tests and implementation for `type.size_bytes == 2/4/8`
  predicates.
- Accepted M58 tests and implementation for typed generation stage records.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- `si16`/`ui16` select the `== 2` arm.
- `si32`/`ui32`/`f32` select the `== 4` arm.
- `si64`/`ui64`/`f64` select the `== 8` arm.
- `si8`/`ui8` produce explicit no-match provenance with no synthesized else.
- Unselected/no-match branch bodies do not emit nested helper diagnostics.
- Rejection tests for unsupported branch-chain shapes.
- Determinism tests for selected arm and no-match provenance.
- Regression tests proving M55/M57/M58 value, predicate, and stage outputs
  remain unchanged.
- Backend raw-helper rejection and renderer non-evaluation regressions.

Golden fixtures required:

- None. M59 is a lowering/control-flow pruning slice and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M59 branch-chain pruning test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Evaluating branch-chain comparisons through raw helper text instead of typed
  M57/M58 predicate/stage outputs.
- Turning exact branch-chain recognition into broad `else if<generation>` or
  general comparison parsing.
- Combining M59 with M60 selected-body handoff.
- Inspecting, parsing, or diagnosing unselected opaque branch bodies.
- Pulling in direct intrinsics, SVE statements, vector metadata, backend
  translation, rendering, output, generated tests, CLI/reporting, Rust,
  compiler execution, broad TSIL parsing, or runtime `frozen/` use.
- Making lowering evaluation read files, parse raw TSL, query the catalog, or
  construct catalog-derived rule data during evaluation.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, and 58.

### Milestone 60: Opaque Selected Branch Body Handoff Slice

Status:

Accepted. M60 returned `Accept With Follow-Ups` with no blocking
implementation issues and no focused revision.

Goal:

Create a distinct typed handoff for selected branch bodies so future
body-lowering slices can consume only the branch text chosen by accepted
generation-time control-flow pruning. M60 converts M59 selected-arm pruning
metadata into an inert, provenanced lowering input while keeping the body
opaque.

Scope:

- Consume only accepted M59 `GenerationSizeByteBranchChainPruning` or
  equivalent typed `generation_control_flow_pruning` stage output.
- Represent a selected generation branch body as a distinct explicit typed
  lowering input, preserving candidate id, selected type tag, selected literal,
  opaque body text, source/provenance, and originating branch-chain identity.
- Represent M59 byte-size `1` no-match cases explicitly without synthesizing a
  selected body.
- Prove unselected branch bodies are not inspected, parsed, or diagnosed by
  the handoff step.
- Define diagnostics only for invalid handoff state, such as missing selected
  body text, missing provenance, or unsupported source stage. These diagnostics
  must not parse deferred direct-intrinsic or SVE body semantics.

Out of scope:

- Direct `intrin<...>` lowering.
- Assignment, variable, array, loop, call, cast, `emit_return`, SVE predicate,
  `value<generation>(vector::length)`, `value<generation>(vector::alignment)`,
  vector/register metadata, backend uninit, backend translation, rendering,
  output, generated tests, CLI/reporting, writer behavior, Rust, compiler
  execution, broad TSIL parsing, or runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

Required inputs:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")` behavior.
- M58 typed `GenerationLoweringStage` records, especially
  `generation_control_flow_pruning` and the existing selected-body stage slot.
- M59 typed branch-chain pruning results for selected `== 2`, `== 4`, and
  `== 8` arms plus explicit no-match provenance for byte size `1`.
- Existing M42/M48/M51/M59 selected-branch-only diagnostic principles.

Expected outputs:

- A distinct typed opaque selected-body handoff value, or equivalent typed
  stage output, that records the selected branch body text and provenance
  without lowering body semantics.
- An explicit no-selected-body/no-match result for byte size `1`, or no handoff
  plus typed no-match provenance that remains inspectable.
- Boundary-level diagnostics for invalid handoff state only.
- No backend translation, rendering, or generated artifact output.

Parity criterion:

M60 proves selected branch bodies can be handed from generation-time
control-flow pruning into a later body-lowering boundary as typed opaque data.
It does not claim direct-intrinsic, SVE body, vector metadata, backend
translation, rendering, generated output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the selected branch
  bodies chosen by M59.
- Accepted M57 predicate behavior for `type.size_bytes == 2/4/8`.
- Accepted M58 stage records for generation-time lowering outputs.
- Accepted M59 typed branch-chain pruning and body-opacity tests.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- Selected body provenance and deterministic handoff tests for `== 2`,
  `== 4`, and `== 8` selected arms.
- Tests proving `si8` and `ui8` no-match cases do not synthesize a selected
  body.
- Tests proving unselected branch bodies are ignored, including bodies
  containing deferred helpers or unsupported body syntax.
- Boundary-level invalid handoff-state diagnostics, without body semantic
  parsing.
- Regression tests preserving M57 predicate behavior, M58 stage records, and
  M59 branch-chain pruning/no-match behavior.
- Backend raw-helper rejection and renderer non-evaluation regressions.

Golden fixtures required:

- None. M60 is a lowering/handoff slice and must not change generated C++ or
  Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M60 selected-body handoff test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating M59 pruning metadata itself as the reusable body-handoff contract
  instead of introducing a distinct typed handoff value.
- Accidentally invoking mini TSIL lowering or producing `TsilStatement` values
  for direct-intrinsic/SVE branch bodies.
- Parsing or diagnosing selected or unselected branch body semantics.
- Synthesizing a final `else` body for byte-size `1` no-match cases.
- Pulling in direct intrinsics, SVE statements, assignments, arrays, calls,
  casts, loops, vector metadata, backend translation, rendering, output,
  generated tests, CLI/reporting, Rust, compiler execution, broad TSIL parsing,
  or runtime `frozen/` use.
- Making lowering evaluation read files, parse raw TSL, query the catalog, or
  construct catalog-derived rule data during evaluation.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, 58, and 59.

Next concrete prompt:

- Completed by `docs/agent/runs/m60-execution-review-loop-prompt.md`; the
  workflow now continues through the post-M60 planning result below.

## Post-M60 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Selected branch body assignment form recognition | M60 now hands forward only the selected branch body as typed opaque data. Recognizing the exact selected assignment-form shape turns that inert text into a typed, reviewable input for later body-specific lowering. | Medium if it stays form recognition; high if it validates direct intrinsics, SVE predicate meaning, assignment semantics, or feeds backend/rendering. | Select as M61. |
| First direct `intrin<...>` / SVE body lowering | The selected M60 bodies contain `pg = intrin<svptrue_b16/b32/b64>();`. | High because it combines assignment semantics, direct intrinsic semantics, SVE predicate meaning, backend translation pressure, and likely renderer/output questions. | Defer until after typed form recognition. |
| Vector length/alignment generation values | Surrounding SVE array evidence contains vector length/alignment helpers. | Medium to high because it jumps away from the selected-body handoff path and pulls in metadata needed by surrounding non-branch statements. | Defer. |
| Broad SVE array body lowering | The same corpus block includes array construction, backend uninit, predicate initialization, stores, and `emit_return`. | Very high because it combines multiple TSIL body forms and backend/output concerns. | Defer. |
| M49-M60 follow-up cleanup | Several accepted follow-ups remain. | Low individually, but cleanup does not form the next lowering architecture milestone. | Keep recorded unless selected separately. |

### Milestone 61: Selected Branch Body Assignment Form Recognition Slice

Status:

Accepted. M61 returned `Accept With Follow-Ups` after one focused revision.

Goal:

Consume the accepted M60 typed selected-body handoff and recognize exactly the
selected branch-body assignment form:

```text
pg = intrin<svptrue_b16>();
pg = intrin<svptrue_b32>();
pg = intrin<svptrue_b64>();
```

M61 is a form-recognition boundary only. It makes the selected body
inspectable as typed, provenanced form metadata for future body-specific
lowering, while keeping assignment semantics, direct intrinsic semantics, SVE
predicate meaning, backend translation, rendering, and generated output
deferred.

Scope:

- Consume only accepted M60 `OpaqueSelectedBranchBodyHandoff` and
  `NoSelectedBranchBodyHandoff` values, or equivalent typed selected-body
  handoff stage output.
- Recognize only the exact single-statement assignment body form selected by
  M59/M60 from `tsldata/primitives/load_store/array.tsl:107-109`.
- Preserve candidate id, selected type tag, selected literal, originating
  branch-chain identity, original opaque body text, selected statement source
  span/provenance, assignment target text, and opaque RHS/source text.
- Record the direct-intrinsic token text only as form metadata needed by later
  slices; do not validate, translate, or semantically lower it.
- Represent `si8`/`ui8` byte-size `1` no-match handoffs explicitly without
  synthesizing a body or recognized form.
- Diagnose only invalid selected-body form-recognition state, such as an
  unsupported handoff source, extra statements, unsupported target shape,
  unsupported RHS shape, or malformed selected body text. Missing selected body
  text and missing source provenance remain M60 handoff-boundary invariants.

Out of scope:

- Assignment semantics, variable binding, declaration handling, target scope
  validation, or proving that `pg` is an SVE predicate.
- Direct `intrin<...>` lowering, intrinsic-name validation, SVE predicate
  semantics, mapping byte-size literals to SVE suffixes, backend intrinsic IR,
  backend translation input, rendering, generated output, generated tests,
  CLI/reporting, writer behavior, Rust, compiler execution, or generated-test
  execution.
- Surrounding SVE body forms such as `svbool_t pg = intrin<svptrue_b8>()`,
  `intrin<svst1>(...)`, array construction, backend uninit,
  `emit_return`, vector length/alignment, declarations, variables, arrays,
  calls, casts, loops, multi-statement bodies, or broad TSIL parsing.
- Inspecting or diagnosing unselected branch bodies.
- Lowering-time file reads, raw TSL parsing, catalog queries during
  evaluation, central raw-string dispatch tables, or runtime dependency on
  `frozen/`.

Required inputs:

- M58 typed `GenerationLoweringStage` records.
- M59 typed branch-chain pruning results for selected `== 2`, `== 4`, and
  `== 8` arms plus no-match provenance for byte size `1`.
- M60 `OpaqueSelectedBranchBodyHandoff` and
  `NoSelectedBranchBodyHandoff` values, including candidate id, selected type
  tag, selected literal, opaque body text, source/provenance, and originating
  branch-chain identity.
- Existing M42/M48/M51/M59/M60 selected-branch-only diagnostic principles.

Expected outputs:

- A distinct typed selected-body assignment-form recognition value, or
  equivalent typed stage output, carrying the preserved M60 handoff identity
  and selected-body provenance plus form-level metadata for the assignment
  target and opaque RHS/direct-intrinsic token text.
- The concrete M61 implementation exposes the recognized selected assignment
  forms, and explicit no-selected-body/no-form cases, through the distinct
  `selected_body_form_recognition` stage.
- A distinct no-selected-body/no-recognized-form result for byte-size `1`
  no-match cases.
- Boundary-level diagnostics for invalid recognition state only.
- No `TsilStatement`, backend intrinsic call, translation request, rendered
  code, or generated artifact output.

Parity criterion:

M61 proves the accepted M60 selected-body handoff can be classified into one
typed body-form record without implementing body semantics. It does not claim
assignment, direct-intrinsic, SVE body, vector metadata, backend translation,
rendering, generated output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the exact selected
  branch body assignment forms.
- `tsldata/primitives/load_store/array.tsl:105-106` and `:110-111` as
  surrounding out-of-scope SVE body evidence.
- Accepted M58 stage records for generation-time lowering outputs.
- Accepted M59 typed branch-chain pruning.
- Accepted M60 typed opaque selected-body handoff.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- Selected `== 2`, `== 4`, and `== 8` M60 handoffs recognize the exact
  assignment-form bodies for `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  while preserving original text/provenance.
- `si8` and `ui8` no-match handoffs produce explicit
  no-selected-body/no-form results.
- Unsupported selected-body forms, extra statements, malformed assignment
  text, and unsupported source-stage diagnostics remain boundary-level and do
  not classify direct intrinsic or SVE semantics.
- Unselected branch bodies remain uninspected and do not emit body-form
  diagnostics.
- Regression tests preserve M57 predicates, M58 stage records, M59
  branch-chain pruning/no-match behavior, M60 handoff behavior, backend
  raw-helper rejection, and renderer non-evaluation.
- Determinism tests for recognized form metadata and
  no-selected-body/no-form results.

Golden fixtures required:

- None. M61 is a lowering/form-recognition slice and must not change generated
  C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M61 selected-body assignment-form recognition test command
  selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting form recognition become assignment lowering, direct-intrinsic/SVE
  semantic lowering, backend translation input, or renderer-ready IR.
- Treating intrinsic names such as `svptrue_b16` as semantic values instead of
  opaque selected-form metadata.
- Inferring a size-to-intrinsic mapping rather than consuming M60 selected
  handoff text/provenance.
- Building a broad body parser, central raw-string dispatcher, or
  multi-statement TSIL evaluator.
- Inspecting or diagnosing unselected branch bodies.
- Pulling in surrounding vector length/alignment, backend uninit, stores,
  arrays, declarations, calls, casts, loops, `emit_return`, generated tests,
  CLI/reporting, Rust, compiler execution, or runtime `frozen/` use.
- Making lowering evaluation read files, parse raw TSL, query the catalog, or
  construct catalog-derived rule data during evaluation.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, 58, 59, and 60.

Next concrete prompt:

- Completed by `docs/agent/runs/m61-execution-review-loop-prompt.md`; the
  workflow now continues through post-M61 planning.

## Post-M61 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Selected assignment direct-intrinsic body IR | M61 now exposes the selected `pg = intrin<svptrue_b16/b32/b64>();` form as typed, provenanced metadata. Converting that exact recognized form into an unresolved typed selected-body IR value is the first useful body-specific lowering step after form recognition. | Medium if it remains a typed IR projection from M61 records; high if "direct intrinsic" becomes SVE/backend semantic validation, translation input, or renderer-ready text. | Select as M62. |
| Body-lowering request/result boundary only | A pure boundary could make future stages easier to attach, but M61 already provides a typed stage output that a very narrow IR slice can consume directly. | Low, but it risks being a cosmetic wrapper without advancing observable lowering capability. | Defer unless M62 implementation reveals the need. |
| Broad direct `intrin<...>` / SVE body lowering | The selected bodies contain zero-argument `svptrue_b*` calls, and the surrounding SVE block uses predicate initialization and `svst1`. | Very high because it would combine assignment semantics, intrinsic validation, SVE predicate meaning, vector metadata, backend translation, and rendering/output pressure. | Defer. |
| Vector length/alignment generation values | The same array evidence contains vector length and alignment helpers outside the selected generation branches. | Medium to high because it jumps away from the selected-body path and pulls in surrounding array/declaration semantics. | Defer. |
| M49-M61 follow-up cleanup | Several accepted follow-ups remain non-blocking. | Low individually, but cleanup does not form the next lowering architecture milestone. | Keep recorded unless selected separately. |

### Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice

Status:

Accepted. M62 returned `Accept With Follow-Ups` after one focused
documentation revision.

Goal:

Convert the accepted M61 selected assignment-form record into a typed
selected-body IR node for the exact zero-argument direct-intrinsic RHS already
recognized by M61:

```text
pg = intrin<svptrue_b16>();
pg = intrin<svptrue_b32>();
pg = intrin<svptrue_b64>();
```

M62 is the first body-specific lowering step after form recognition. Its IR is
an unresolved, backend-neutral lowering-stage value. It is not backend
intrinsic IR, not a backend translation request, not renderer-ready text, and
not SVE predicate semantics.

Scope:

- Consume only accepted typed `selected_body_form_recognition` outputs:
  `SelectedBranchBodyAssignmentFormRecognition` and
  `NoSelectedBranchBodyAssignmentFormRecognition`, or equivalent typed stage
  values.
- Produce a distinct typed selected assignment/direct-intrinsic body IR value
  for the exact M61-recognized single-statement form.
- Preserve candidate id, selected type tag, selected byte-size literal,
  originating branch-chain identity, original body text, source/provenance,
  assignment target text, opaque RHS text, direct-intrinsic token text, and
  explicit empty argument list.
- Represent `si8`/`ui8` byte-size `1` no-selected-body/no-form cases as an
  explicit no-selected-body/no-body-IR result without synthesizing a body.
- Expose the result through a distinct post-form-recognition stage, such as
  `selected_body_ir_lowering`, instead of stretching M60 handoff metadata or
  M61 form-recognition metadata into a mixed semantic dispatcher.
- Diagnose only invalid M62 boundary state, such as unsupported M61
  form-recognition boundary state, missing provenance, missing
  direct-intrinsic token metadata, or inconsistent selected form-to-IR input.

M62 must not read, parse, or match the preserved original body text to derive
semantics. It may carry original text as provenance, but it may consume only
typed fields already exposed by M61.

Out of scope:

- Assignment semantics, variable binding, declaration handling, target scope
  validation, proving that `pg` is an SVE predicate, or checking that `pg` was
  previously declared.
- Direct-intrinsic semantic validation, SVE predicate semantics, mapping
  byte-size literals to `svptrue_b*` intrinsic tokens, backend intrinsic IR,
  backend translation input, backend metadata lookup, or translation-map
  evaluation.
- General `intrin<...>` lowering, non-zero-argument direct intrinsics,
  primitive calls, casts, arrays, loops, declarations, stores, `emit_return`,
  multi-statement body lowering, surrounding `svbool_t pg =
  intrin<svptrue_b8>()`, `intrin<svst1>(...)`, backend uninit values,
  `value<generation>(vector::length)`, or
  `value<generation>(vector::alignment)`.
- Backend translation expansion, rendering, generated output, generated tests,
  CLI/reporting/writer behavior, Rust, compiler execution,
  generated-test execution, broad TSIL parsing, central raw-string body
  dispatch tables, lowering-time file reads, raw TSL parsing, catalog queries
  during evaluation, or runtime dependency on `frozen/`.

Required input:

- M61 `SelectedBranchBodyAssignmentFormRecognition` and
  `NoSelectedBranchBodyAssignmentFormRecognition` outputs from the distinct
  `selected_body_form_recognition` stage. These values may carry provenance,
  selected type/literal facts, and branch identity originating upstream, but
  M62 must not separately consume M58 stage records, M59 pruning results, or
  M60 handoff records.

Expected outputs:

- A distinct typed value such as
  `SelectedAssignmentDirectIntrinsicBodyIr`, carrying:
  - the selected candidate/type/literal/branch provenance from M60/M61,
  - an assignment target record preserving text `pg`,
  - an unresolved zero-argument direct-intrinsic expression record preserving
    the M61 token text `svptrue_b16`, `svptrue_b32`, or `svptrue_b64`,
  - the original RHS/body text only as provenance.
- A distinct no-selected-body/no-body-IR result for byte-size `1` no-match
  cases.
- Boundary-level diagnostics for invalid M62 input state only.
- No `TsilStatement`, `BackendIntrinsicCall`, backend translation request,
  renderer-ready expression, rendered code, or generated artifact.

Parity criterion:

M62 proves the selected M61 assignment/direct-intrinsic form can become typed
body-specific lowering IR without implementing assignment semantics, direct
intrinsic semantics, SVE predicate meaning, backend translation, rendering,
generated output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the exact selected
  `pg = intrin<svptrue_b16/b32/b64>();` branch bodies.
- `tsldata/primitives/load_store/array.tsl:105-106` and `:110-111` as
  surrounding out-of-scope evidence for declarations, vector metadata, backend
  uninit, stores, and `emit_return`.
- Accepted M57 size-byte equality predicate lowering.
- Accepted M58 staged lowering contract.
- Accepted M59 exact branch-chain pruning.
- Accepted M60 opaque selected-body handoff.
- Accepted M61 selected assignment-form recognition.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- Selected M61 records for `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  produce deterministic typed selected assignment/direct-intrinsic body IR
  preserving target text, token text, empty arguments, selected literal,
  selected type tag, original text, and provenance.
- `si8` and `ui8` M61 no-form results produce explicit no-selected-body/
  no-body-IR results without synthesizing a body or form.
- A synthetic mismatch between selected byte-size literal and
  direct-intrinsic token text preserves both values without diagnosing or
  correcting them, proving M62 does not infer a size-to-intrinsic mapping.
- Unsupported M61 form-recognition boundary state produces M62 boundary
  diagnostics without classifying SVE/backend semantics.
- M62 consumes M61 typed fields and does not parse preserved original body text
  to derive target or RHS semantics.
- Regression tests preserve M57 predicates, M58 stage records, M59 pruning,
  M60 handoff, M61 form recognition, backend raw-helper rejection, and
  renderer non-evaluation.
- Determinism tests cover selected body IR and no-body-IR results.

Golden fixtures required:

- None. M62 is a lowering/body-IR slice and must not change generated C++ or
  Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M62 selected assignment direct-intrinsic body IR test command
  selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting the selected body IR become backend intrinsic IR, translation input,
  renderer-ready text, generated output, or SVE predicate semantics.
- Re-reading or matching original body text instead of consuming typed M61
  fields.
- Inferring a byte-size-to-`svptrue_b*` mapping rather than preserving the M61
  token text.
- Adding assignment binding, declaration/scope checks, broad call lowering,
  or a central raw-string body dispatcher.
- Pulling in surrounding vector length/alignment, backend uninit, stores,
  arrays, declarations, calls, casts, loops, `emit_return`, generated tests,
  CLI/reporting, Rust, compiler execution, or runtime `frozen/` use.
- Making lowering evaluation read files, parse raw TSL, query the catalog, or
  construct catalog-derived rule data during evaluation.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, 58, 59, 60, and 61.

Next concrete prompt:

- The M62 execution-review loop owns acceptance for this milestone. If M62 is
  accepted, update workflow state and create the next concrete post-M62 prompt
  under `docs/agent/runs/`. Do not start M63.

## Post-M62 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Backend-neutral selected body envelope IR | M62 now exposes an unresolved typed selected-body IR/no-body-IR result, but future body-specific lowering needs a composable whole-body boundary before additional statement forms are added. | Low to medium if it only wraps typed M62 outputs in a stable sequence envelope; high if it reparses preserved text, recognizes surrounding array statements, or treats SVE tokens as architecture. | Select as M63. |
| Direct-intrinsic/SVE semantic lowering | The selected M62 body IR carries `svptrue_b16/b32/b64` token text. | High because it would combine intrinsic validation, SVE predicate meaning, byte-size-to-token inference, backend translation pressure, and rendering/output pressure. | Defer. |
| Vector length/alignment generation values | The surrounding array evidence includes `value<generation>(vector::length)` and `value<generation>(vector::alignment)`. | Medium to high because it leaves the selected-body pipeline and pulls in declaration/array semantics before a body envelope exists. | Defer. |
| Broad array-body or multi-statement TSIL lowering | `tsldata/primitives/load_store/array.tsl:105-111` contains a real ordered body shape around the accepted M57-M62 branch chain. | Very high because it would parse declarations, assignments, stores, returns, arrays, direct intrinsics, and backend values in one milestone. | Defer. |
| M62 diagnostic follow-up cleanup | M62 review recorded a non-blocking diagnostic-location/message test gap. | Low, but it does not move the lowering architecture forward. | Keep recorded unless selected separately. |

### Milestone 63: Backend-Neutral Selected Body Envelope IR Slice

Status:

Accepted. M63 returned `Accept With Follow-Ups`; no blocking implementation
issues were found.

Goal:

Wrap the accepted M62 selected-body IR or no-body-IR result in a deterministic
backend-neutral selected-body envelope containing an ordered sequence of typed
body IR entries. M63 makes the post-M62 body-lowering boundary extendable
without turning M62 into a central dispatcher or reparsing raw selected body
text.

For this slice, the only selected sequence entry is the existing M62
`SelectedAssignmentDirectIntrinsicBodyIr`; the sequence is exact and singleton.
Byte-size `1` no-selected-body cases produce an explicit no-body envelope.

Scope:

- Consume only M62 `selected_body_ir_lowering` outputs or equivalent typed
  M62 values: `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr`.
- Expose the result through a distinct post-M62 stage, such as
  `selected_body_envelope_lowering`.
- Produce typed envelope/sequence records with stable ordering, candidate
  identity, selected type/literal facts, branch-chain identity, source
  location, and provenance already carried by M62.
- Preserve M62 assignment target text, unresolved direct-intrinsic token text,
  explicit empty argument list, original RHS/body text, and source/provenance
  only as typed facts within the one selected entry.
- Represent byte-size `1` no-selected-body/no-body-IR cases as explicit
  no-body envelope values without synthesizing body text or statements.
- Diagnose only invalid M63 boundary state, such as unsupported M62 source
  stage/type or inconsistent selected/no-body envelope input.

M63 treats the SVE-looking tokens and surrounding array body in
`tsldata/primitives/load_store/array.tsl:105-111` as corpus evidence for a
needed body boundary only. `svptrue_b16/b32/b64`, `pg`, `svbool_t`, `svst1`,
vector metadata, backend uninit values, and `emit_return` must not become
architectural concepts or semantic lowering rules in M63.

Out of scope:

- Parsing or matching preserved original selected-body text to derive
  semantics.
- Direct-intrinsic semantic validation, SVE predicate/vector/register
  semantics, proving that `pg` has any particular type or scope, or inferring
  byte-size-to-`svptrue_b*` mappings.
- Backend intrinsic IR, backend translation requests, renderer-ready
  expression/body IR, rendering, generated C++/Rust output, generated tests,
  CLI/reporting/writer behavior, compiler execution, or Rust.
- Assignment binding, declaration handling, variable scope, array
  construction, stores, calls, casts, loops, returns, `emit_return`, backend
  uninit values, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, non-zero-argument direct intrinsics,
  or broad multi-statement TSIL body lowering.
- Broad TSIL parsing, lowering-time file reads, raw TSL parsing, catalog
  queries during evaluation, runtime dependency on `frozen/`, dictionaries or
  raw string keys as downstream semantic models, and backend-specific branches
  in the envelope stage.

Required input:

- M62 `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr` outputs from the distinct
  `selected_body_ir_lowering` stage. M63 may rely on provenance and selected
  facts already present on those values, but it must not separately consume
  M60 handoff text or M61 form-recognition records.

Expected outputs:

- A distinct typed selected-body envelope value, such as
  `SelectedBodyEnvelopeIr`, carrying a deterministic statement sequence.
- A typed one-entry sequence for selected cases, with that entry wrapping the
  M62 unresolved assignment/direct-intrinsic body IR facts.
- A distinct no-selected-body envelope value for no-body-IR cases.
- Boundary-level diagnostics for invalid M63 input state only.
- No `TsilStatement`, `BackendIntrinsicCall`, backend translation request,
  renderer-ready body, rendered code, generated artifact, SVE semantic object,
  or array/store/return statement IR.

Parity criterion:

M63 proves accepted M62 body IR can be carried through a maintainable,
backend-neutral whole-body envelope boundary without implementing SVE
semantics, direct intrinsic semantics, broad statement lowering, backend
translation, rendering, generated output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:107-109` for the exact selected
  M57-M62 branch bodies that become the singleton selected sequence entry.
- `tsldata/primitives/load_store/array.tsl:105-111` as evidence that the
  accepted selected body appears inside a larger ordered body, while the
  surrounding declaration, initialization, store, and return forms remain
  out of scope.
- Accepted M57 size-byte equality predicate lowering.
- Accepted M58 staged lowering contract.
- Accepted M59 exact branch-chain pruning.
- Accepted M60 opaque selected-body handoff.
- Accepted M61 selected assignment-form recognition.
- Accepted M62 unresolved selected assignment/direct-intrinsic body IR.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- Selected M62 records for `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  produce deterministic selected-body envelopes with exactly one typed
  sequence entry.
- The one selected entry preserves M62 target/token/text/provenance, selected
  type/literal facts, branch identity, source location, and explicit empty
  argument list without reparsing original body text.
- `si8` and `ui8` M62 no-body-IR results produce explicit no-body envelopes
  without synthesizing statements.
- A synthetic mismatch between selected byte-size literal and
  direct-intrinsic token text is preserved inside the envelope without
  diagnosis or correction, proving M63 still does not infer token semantics.
- Unsupported M62 source/type or inconsistent M62 boundary state produces
  structured M63 diagnostics without classifying SVE/backend semantics.
- Repeated envelope lowering is deterministic.
- Regression tests preserve M57 predicates, M58 stage records, M59 pruning,
  M60 handoff, M61 form recognition, M62 body IR, backend raw-helper
  rejection, renderer non-evaluation, and no generated output.

Golden fixtures required:

- None. M63 is a lowering/body-envelope IR slice and must not change generated
  C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M63 selected body envelope test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Re-reading preserved body text or consuming M60/M61 raw text instead of M62
  typed body IR values.
- Turning the envelope into a cosmetic wrapper without stable typed sequence
  contracts and future extension points.
- Letting SVE evidence hardwire architecture, class names, stage names,
  branch logic, or semantic rules.
- Adding direct-intrinsic semantics, byte-size-to-token inference,
  assignment/declaration/call/store/return semantics, vector metadata, backend
  translation, rendering, generated output, or broad TSIL parsing.
- Using dictionaries, raw string dispatch, backend-specific branches, file
  reads, raw TSL parsing, catalog queries, or runtime `frozen/` evidence during
  lowering evaluation.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, 58, 59, 60, 61, and 62.

Next concrete prompt:

- Completed by `docs/agent/runs/m63-execution-review-loop-prompt.md`; the
  workflow now continues through post-M63 planning.

## Post-M63 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array body envelope slot assembly | M63 now supplies a typed selected-body envelope, but the accepted corpus evidence places that branch inside a larger ordered array body. A structural slot envelope gives future body-lowering slices named attachment points without interpreting those slots yet. | Medium if framed as exact opaque slot assembly over M63; very high if it becomes broad TSIL parsing, SVE array lowering, store/return semantics, or backend/rendering input. | Accepted as M64. |
| Direct-intrinsic/SVE semantics | The selected branch and surrounding body contain `svptrue_b*`, `svptrue_b8`, and `svst1` tokens. | High because it would add SVE predicate/vector meaning, direct-intrinsic validation, byte-size-to-token inference, backend intrinsic pressure, and rendering pressure. | Defer. |
| Vector length/alignment value semantics | The declaration slot contains `value<generation>(vector::length)` and `value<generation>(vector::alignment)`. | Medium to high because it pulls in vector/register metadata and array declaration semantics before the full body has a typed structural envelope. | Defer. |
| Declaration/store/return lowering | The exact body includes array construction, a store call, and `emit_return`. | High because it would mix variable binding, array type/value semantics, call semantics, store semantics, return semantics, and eventual renderer concerns. | Defer. |
| M62 diagnostic follow-up cleanup | A non-blocking M62 diagnostic-location/message assertion follow-up remains recorded. | Low, but it does not move lowering architecture forward. | Keep recorded unless selected separately. |

### Milestone 64: Exact Array Body Envelope Slot Assembly Slice

Status:

Accepted.

Goal:

Assemble the exact ordered array-body shape evidenced by
`tsldata/primitives/load_store/array.tsl:105-111` into a deterministic typed
body-envelope slot sequence around the accepted M63 selected-body envelope.

M64 is a larger structural step than M63: it creates the whole-body composition
point future body-lowering milestones can refine one slot at a time. It is not
semantic array-body lowering.

Scope:

- Consume accepted typed M63 `selected_body_envelope_lowering` outputs or
  equivalent typed M63 envelope values:
  `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`.
- Consume only in-memory typed/provenanced implementation payload information
  already available to lowering for the exact array body shape. M64 must not
  read `tsldata`, `frozen/`, the catalog, or files during evaluation.
- Add the distinct post-M63 `array_body_envelope_slot_assembly` typed value
  boundary.
- Recognize only the exact ordered structural skeleton evidenced by
  `tsldata/primitives/load_store/array.tsl:105-111`:
  - one opaque pre-branch array-initialization slot for the line 105 shape,
  - one opaque pre-branch predicate-initialization slot for the line 106 shape,
  - one selected-body envelope slot carrying the M63 envelope for the lines
    107-109 branch-chain path,
  - one opaque post-branch store-call slot for the line 110 shape,
  - one opaque post-branch return-emission slot for the line 111 shape.
- Treat those slot labels as exact structural/provenance labels only. They must
  not imply declaration, assignment, predicate, store, return, array, vector,
  direct-intrinsic, or backend semantics.
- Preserve deterministic slot order, slot ordinal, opaque source text,
  source/provenance, candidate id, selected type tag, branch-chain identity,
  and a typed reference to the nested M63 envelope.
- For byte-size `1` no-selected-body cases, carry the M63 no-body envelope in
  the selected-body slot without synthesizing selected branch text.
- Diagnose only M64 boundary state: unsupported source/stage/type, missing M63
  envelope, duplicate selected-body slot, unsupported exact skeleton, missing
  or extra slot, reordered slot, or candidate/type/branch provenance mismatch.

M64 may use exact-shape structural recognition to assemble slots, but it must
not split the body into semantic statements or dispatch behavior from raw text.
Raw body text may be preserved as opaque provenance only.

Out of scope:

- SVE predicate/vector/register semantics, including meaning of `svbool_t`,
  `pg`, `svptrue_b8`, `svptrue_b16/b32/b64`, or `svst1`.
- Direct-intrinsic semantic validation, non-zero-argument intrinsic semantics,
  byte-size-to-intrinsic-token inference, backend intrinsic IR, backend
  translation requests, translation-map evaluation, renderer-ready IR,
  rendering, generated C++/Rust output, generated tests, CLI/reporting/writer
  behavior, compiler execution, or Rust.
- Declaration semantics, assignment binding, variable scope, array type/value
  semantics, `tmp.data()` semantics, store semantics, return semantics,
  primitive calls, casts, loops, broad body lowering, or broad TSIL parsing.
- Evaluation of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Consuming M60/M61/M62 raw text as a semantic shortcut; re-opening M63
  `original_opaque_body_text` to infer target/RHS/intrinsic semantics; using
  dictionaries, raw string keys, backend-specific branches, file reads, raw
  TSL parsing, catalog queries, or runtime `frozen/` evidence during lowering
  evaluation.

Required input:

- M63 `SelectedBodyEnvelopeIr` or `NoSelectedBodyEnvelopeIr` outputs from the
  distinct `selected_body_envelope_lowering` stage.
- Typed/provenanced exact array-body source information already supplied by
  the lowering pipeline for the selected implementation payload. This source
  information is structural/provenance input only, not semantic statement IR.

Expected outputs:

- A distinct typed value such as `ExactArrayBodyEnvelopeIr`, carrying five
  deterministic ordered slots.
- Opaque structural slot values for the four surrounding pre/post slots,
  preserving text and provenance only.
- A selected-body envelope slot referencing the M63 selected/no-body envelope.
- Boundary-level diagnostics for invalid M64 input state only.
- No `TsilStatement`, declaration/store/return statement IR, `BackendIntrinsicCall`,
  backend translation request, renderer-ready body, rendered code, generated
  artifact, SVE semantic object, vector metadata object, or backend-value
  semantic object.

Parity criterion:

M64 proves the exact `array.tsl:105-111` body can be represented as a typed,
ordered, backend-neutral structural envelope around the accepted M63 selected
body envelope without implementing semantic array-body lowering, SVE/direct
intrinsic semantics, backend translation, rendering, generated output, or
compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105-111` for the exact ordered
  array-body evidence.
- `tsldata/primitives/load_store/array.tsl:107-109` for the accepted selected
  branch-chain body evidence already covered through M57-M63.
- Accepted M57 size-byte equality predicate lowering.
- Accepted M58 staged lowering contract.
- Accepted M59 exact branch-chain pruning.
- Accepted M60 opaque selected-body handoff.
- Accepted M61 selected assignment-form recognition.
- Accepted M62 unresolved selected assignment/direct-intrinsic body IR.
- Accepted M63 backend-neutral selected-body envelope IR.
- `docs/redesign/generation-time-semantic-lowering.md` staged lowering
  direction.

Tests required:

- Selected M63 envelopes for `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  assemble deterministic five-slot exact array-body envelopes.
- `si8` and `ui8` M63 no-body envelopes assemble deterministic five-slot
  envelopes with an explicit no-body selected-body slot and no synthesized
  selected branch text.
- Slot order, slot ordinals, candidate id, selected type tag, branch-chain
  identity, opaque slot text, source locations, and nested M63 envelope
  references are preserved.
- Reordered, missing, duplicate, or extra slots produce structured M64
  boundary diagnostics.
- Mismatched candidate/type/branch provenance between the exact body skeleton
  and nested M63 envelope produces structured M64 diagnostics.
- Unsupported non-exact body skeletons, including final-else or additional
  statements, are rejected without semantic classification.
- Tests prove M64 does not reopen M63 selected-body text to infer
  byte-size-to-token relationships, direct-intrinsic meaning, or SVE semantics.
- Regression tests preserve M57 predicates, M58 stage records, M59 pruning,
  M60 handoff, M61 form recognition, M62 body IR, M63 envelopes, backend
  raw-helper rejection, renderer non-evaluation, and no generated output.
- Determinism tests cover selected and no-body array-body envelopes.

Golden fixtures required:

- None. M64 is a lowering/body-envelope slot assembly slice and must not
  change generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M64 exact array body envelope slot assembly test command selected
  by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting exact structural slot assembly become broad TSIL parsing or
  multi-statement body lowering.
- Naming slot records in a way that implies declaration, store, return, SVE,
  vector, or backend semantics rather than opaque provenance roles.
- Consuming M60/M61/M62 raw text, reparsing M63 selected-body text, or
  dispatching semantics from raw strings.
- Inferring byte-size-to-`svptrue_b*` mappings, validating direct intrinsics,
  or interpreting `svbool_t`, `svst1`, vector length/alignment, backend
  uninit, `tmp.data()`, or `emit_return`.
- Adding backend translation, rendering, generated output, generated tests,
  file/catalog reads, runtime `frozen/` use, dictionaries/raw string keys as
  semantic models, or backend-specific branches.

Dependencies on prior milestones:

- Milestones 41, 42, 43, 48, 51, 52, 53, 54, 55, 57, 58, 59, 60, 61, 62, and
  63.

Next concrete prompt:

- Completed by `docs/agent/runs/m64-execution-review-loop-prompt.md`; the
  orchestrator owns workflow-state updates and the next concrete prompt.

## Post-M64 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array body envelope pipeline integration | M64 defines `ExactArrayBodyEnvelopeIr`, `ExactArrayBodyEnvelopeSkeleton`, and the `array_body_envelope_slot_assembly` stage, but normal `lower_candidates` still stops at M63 unless callers invoke M64 assembly directly. Wiring typed skeleton input through normal lowering makes M64 usable by later body slices. | Medium if framed as typed pipeline wiring; high if it starts recognizing skeletons from raw body text or becomes a new raw-text dispatcher. | Accepted as M65 after the execution-review loop. |
| Exact skeleton-producing recognition | A future source/input adapter must eventually prove where exact skeletons come from. | High now because it invites broad TSIL parsing or exact-shape recognition from raw body text before the pipeline can consume typed skeletons cleanly. | Defer. |
| First slot-specific lowering | M64 gives future slot-specific lowering named attachment points. | High now because normal lowering does not yet produce M64 envelopes, and slot lowering could pull in declaration, array, store, return, vector, or SVE semantics too early. | Defer until M64 is pipeline-reachable. |
| Vector length/alignment helper semantics | The opaque array-initialization slot contains `value<generation>(vector::length)` and `value<generation>(vector::alignment)`. | Medium to high because it introduces vector metadata semantics before the whole-body envelope is produced by the normal pipeline. | Defer. |

### Milestone 65: Exact Array Body Envelope Pipeline Integration Slice

Status:

Accepted.

Goal:

Make the normal lowering pipeline populate accepted M64 exact array-body
envelopes when supplied with in-memory typed/provenanced exact skeleton input.

M65 is a pipeline-integration and maintainability slice. It turns M64 from a
direct assembly boundary into a normal staged lowering output, without adding
body semantics or skeleton recognition from raw TSIL text.

Scope:

- Consume accepted M63 `SelectedBodyEnvelopeIr` and
  `NoSelectedBodyEnvelopeIr` values produced by the
  `selected_body_envelope_lowering` stage inside the normal lowering path.
- Consume explicit in-memory typed/provenanced `ExactArrayBodyEnvelopeSkeleton`
  input supplied to lowering. Skeleton lookup must be keyed by typed
  candidate id, selected type tag, and branch-chain identity, not by raw body
  text.
- Call the accepted M64 `assemble_exact_array_body_envelope` boundary when a
  matching typed skeleton is supplied.
- Populate `LoweredImplementation.array_body_envelopes` with the resulting
  `ExactArrayBodyEnvelopeIr`.
- Append a deterministic
  `GenerationLoweringStage(stage="array_body_envelope_slot_assembly", ...)`
  immediately after the accepted M63 `selected_body_envelope_lowering` stage.
- Preserve existing M57-M64 values, diagnostics, ordering, selected/no-body
  behavior, and backend raw-helper/rendering regressions.
- Diagnose only M65 integration state: missing required skeletons, duplicate
  skeletons, conflicting skeletons, orphan skeletons supplied for candidates
  without an M63 envelope, and skeleton/envelope provenance mismatches.
  Unsupported skeleton shape should continue through existing M64 diagnostics.

Out of scope:

- Producing or recognizing `ExactArrayBodyEnvelopeSkeleton` from raw payload
  text.
- Broad TSIL parsing or exact skeleton recognition from `array.tsl` text.
- Slot-specific lowering or semantic interpretation of M64 slot labels.
- Declaration semantics, assignment binding, variables, arrays, stores,
  returns, primitive calls, casts, loops, `tmp.data()`, or `emit_return`.
- SVE predicate/vector/register semantics, including meaning of `svbool_t`,
  `pg`, `svptrue_b8`, `svptrue_b16/b32/b64`, or `svst1`.
- Byte-size-to-intrinsic-token validation or inference.
- Evaluation of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Backend intrinsic IR, backend translation requests, translation-map
  evaluation, renderer-ready IR, rendering, generated C++/Rust output,
  generated tests, CLI/reporting/writer behavior, compiler execution, or Rust.
- File reads, catalog queries, raw TSL parsing, or runtime `frozen/` evidence
  during lowering evaluation.

Required input:

- Accepted M63 selected/no-body envelope outputs from the normal lowering
  path.
- Accepted M64 `ExactArrayBodyEnvelopeSkeleton` values supplied in memory
  through the lowering request/input boundary.

Expected outputs:

- Existing M57-M64 stage outputs preserved in deterministic order.
- `ExactArrayBodyEnvelopeIr` values available in
  `LoweredImplementation.array_body_envelopes`.
- A final `array_body_envelope_slot_assembly` stage referencing the same
  `ExactArrayBodyEnvelopeIr`.
- Structured diagnostics for invalid M65 integration state.
- No backend translation request, renderer-ready body, generated artifact,
  SVE semantic object, vector metadata object, or semantic statement IR.

Parity criterion:

M65 proves the accepted M64 exact array-body envelope can be produced through
the normal lowering pipeline from typed/provenanced skeleton input, without
implementing skeleton recognition, semantic array-body lowering, SVE/direct
intrinsic semantics, backend translation, rendering, generated output, or
compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105-111` for the exact ordered
  array-body evidence. The SVE-looking text remains evidence only.
- `tslgen/src/tslgen/lowering/boundary.py` M64 models:
  `ExactArrayBodyEnvelopeSkeletonSlot`, `ExactArrayBodyEnvelopeSkeleton`,
  `ExactArrayBodyEnvelopeIr`, and `assemble_exact_array_body_envelope`.
- `tslgen/src/tslgen/lowering/boundary.py` normal branch-chain lowering path,
  which currently reaches M63 selected-body envelopes.
- M64 unit tests in `tslgen/tests/unit/test_lowering_boundary.py` for direct
  assembly, no-body handling, deterministic stage construction, mismatch
  preservation, and boundary diagnostics.
- Accepted M57-M64 staged lowering behavior.

Tests required:

- `lower_candidates` produces `ExactArrayBodyEnvelopeIr` in
  `array_body_envelopes` when matching typed skeleton input is supplied.
- The final `generation_stages` entry is
  `array_body_envelope_slot_assembly` and references the same envelope stored
  in `array_body_envelopes`.
- Selected `svptrue_b16`, `svptrue_b32`, and `svptrue_b64` M63 envelopes
  assemble through normal lowering.
- `si8` and `ui8` no-body envelopes assemble through normal lowering without
  synthesized selected branch text.
- No-skeleton input preserves existing M63-only behavior unless the accepted
  M65 input contract explicitly marks a skeleton as required for the
  candidate.
- The M65 diagnostic matrix covers missing required skeletons, duplicate
  skeletons, conflicting skeletons, orphan skeletons, and skeleton/envelope
  provenance mismatches with source locations and actionable messages.
- Unsupported or non-exact skeleton shape continues to report existing M64
  diagnostics.
- Existing M57/M58/M59/M60/M61/M62/M63/M64 behavior remains unchanged.
- Backend raw-helper rejection and renderer non-evaluation remain unchanged.
- Determinism tests compare two normal lowering runs with the same skeleton
  input.
- No generated output or golden fixtures change.

Golden fixtures required:

- None. M65 is a lowering pipeline-integration slice and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M65 pipeline-integration test command used by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting pipeline integration become skeleton recognition from raw body text.
- Turning `lower_candidates` into a broad raw-string dispatcher.
- Treating M64 slot labels or opaque source text as semantic statements.
- Combining integration with slot-specific lowering, vector metadata, SVE
  predicate/direct-intrinsic semantics, backend translation, or rendering.
- Silently skipping missing or mismatched skeleton input when the accepted
  integration contract requires it.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, and 64.

Completion note:

- M65 is accepted after the execution-review loop. Post-M65 planning selected
  M66 as the first exact slot-specific form-IR slice over the accepted M65
  array-body envelope.

## Post-M65 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array initialization slot form IR | M65 now makes the accepted M64 array-body envelope available through normal lowering. Refining exactly the first opaque array-initialization slot starts body-specific lowering at the narrowest available attachment point. | Medium if framed as exact form IR over one slot; high if it becomes broad declaration/array semantics, vector metadata evaluation, backend uninit evaluation, or a raw-text dispatcher. | Select as M66. |
| Exact skeleton-producing/source adapter | M65 still consumes typed skeletons supplied in memory, so a source adapter remains useful. | High now because it invites broad TSIL parsing or exact-shape recognition from raw body text before slot-specific consumers prove which skeleton data matters. | Defer. |
| Vector length/alignment helper semantics | The first array-initialization slot contains `value<generation>(vector::length)` and `value<generation>(vector::alignment)`. | Medium to high because evaluating them pulls in vector metadata before the exact slot form boundary exists. | Defer until after exact form IR. |
| Store or return slot lowering | The accepted envelope has post-branch store and return slots. | High because store/return lowering would combine variable binding, call semantics, `tmp.data()`, SVE/direct-intrinsic pressure, backend semantics, and output pressure. | Defer. |
| M65 determinism follow-up only | Review recorded a useful explicit test for skeleton-input ordering. | Low, but it is a hardening task rather than a large architectural step. | Keep recorded unless bundled as a regression in M66. |

### Milestone 66: Exact Array Initialization Slot Form IR Slice

Status:

Accepted after the M66 execution-review loop.

Goal:

Consume accepted M65 `ExactArrayBodyEnvelopeIr` values and refine exactly the
`opaque_pre_branch_array_initialization` slot into typed form IR for the exact
`array.tsl:105` shape, without evaluating helper semantics or lowering broad
array/declaration behavior.

M66 is the first body-specific lowering slice after M65. It uses the whole-body
slot envelope for its intended purpose: one named opaque slot becomes a typed
form boundary while all other slots remain opaque.

Scope:

- Consume `LoweredImplementation.array_body_envelopes`,
  `ExactArrayBodyEnvelopeIr`, or the typed
  `array_body_envelope_slot_assembly` stage produced by accepted M65.
- Select only the slot with label `opaque_pre_branch_array_initialization` and
  ordinal `0`.
- Recognize only the exact slot form evidenced by
  `tsldata/primitives/load_store/array.tsl:105`:
  `var<typed>(array_type<type<generation>(base::in), value<generation>(vector::length), value<generation>(vector::alignment)>, tmp, value<backend>(uninit::array))`.
- Produce an immutable typed form IR value, for example
  `ExactArrayInitializationSlotFormIr`, preserving candidate id, selected type
  tag, branch-chain identity, envelope identity, slot ordinal, source
  location, original slot text, variable token `tmp`, and exact nested helper
  positions.
- Represent `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, and
  `value<backend>(uninit::array)` as unresolved typed/provenance leaves only.
- Append a distinct deterministic lowering stage, for example
  `array_initialization_slot_form_lowering`, after
  `array_body_envelope_slot_assembly`.
- Preserve the accepted M65 envelope and the other four M64/M65 slots as
  opaque, unchanged provenance.
- Diagnose only M66 boundary/form state, such as unsupported source
  stage/type, missing array-body envelope, missing slot, wrong label or
  ordinal, malformed exact slot text, unsupported nested helper shape, or
  provenance mismatch.

Out of scope:

- Evaluation of `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Generic `var` parsing, generic `array_type` parsing, broad helper-expression
  parsing, broad declaration semantics, array allocation/lifetime semantics,
  variable binding/scope, array type/value semantics, or statement IR.
- Predicate initialization slot lowering, selected-body slot changes, store
  slot lowering, return slot lowering, `tmp.data()` semantics, or
  `emit_return` semantics.
- SVE predicate/vector/register semantics, direct-intrinsic semantics,
  byte-size-to-`svptrue_b*` token inference, backend intrinsic IR, backend
  translation requests, translation-map evaluation, renderer-ready IR,
  rendering, generated C++/Rust output, generated tests, CLI/reporting/writer
  behavior, compiler execution, or Rust.
- Producing or recognizing `ExactArrayBodyEnvelopeSkeleton` from raw payload
  text, broad TSIL parsing, lowering-time file reads, catalog queries, raw TSL
  parsing, or runtime `frozen/` evidence.

Required input:

- Accepted M65 `LoweredImplementation.array_body_envelopes` /
  `ExactArrayBodyEnvelopeIr` values, or equivalent typed
  `array_body_envelope_slot_assembly` stage output.
- The exact M65 opaque slot text/provenance for
  `opaque_pre_branch_array_initialization`.

Expected outputs:

- A typed exact array-initialization slot form IR value keyed to the M65
  envelope and slot `0`.
- A distinct deterministic stage after `array_body_envelope_slot_assembly`
  carrying the same typed form IR value.
- Unresolved typed/provenance leaves for the base type, vector length, vector
  alignment, and backend uninit helpers.
- Existing `ExactArrayBodyEnvelopeIr` values and all non-selected slots
  preserved unchanged.
- Structured diagnostics for invalid M66 source, slot, form, helper-shape, or
  provenance state.
- No semantic array declaration IR, backend value request, renderer-ready body,
  generated artifact, SVE semantic object, vector metadata value, store IR, or
  return IR.

Parity criterion:

M66 proves the accepted M65 array-body envelope can be refined one slot at a
time by turning the exact array-initialization slot into typed form IR, while
leaving vector metadata, backend uninit, array/declaration semantics,
store/return semantics, backend translation, rendering, generated output, and
compiler parity deferred.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105` for the exact
  array-initialization slot form.
- `tsldata/primitives/load_store/array.tsl:105-111` only as context that this
  slot is part of the accepted M64/M65 five-slot envelope.
- Accepted M64 `ExactArrayBodyEnvelopeIr` structural slot model.
- Accepted M65 normal lowering pipeline integration for
  `LoweredImplementation.array_body_envelopes`.
- Accepted M57-M63 staged selected-body behavior for preserving the rest of
  the envelope.

Tests required:

- Normal `lower_candidates` with typed M65 skeleton input produces M66
  array-initialization slot form IR for selected `svptrue_b16`, `svptrue_b32`,
  and `svptrue_b64` paths.
- `si8` and `ui8` no-body M65 envelopes still lower the first slot form
  without synthesizing selected branch text or changing the no-body envelope.
- The output preserves envelope identity, slot ordinal, candidate id, selected
  type tag, branch-chain identity, source location, original slot text, the
  variable token `tmp`, and unresolved helper leaves.
- Slots `1` through `4` remain opaque and unchanged.
- Malformed slot text, missing slot, wrong label/ordinal, unsupported helper
  shape, unsupported source stage/type, and provenance mismatch produce
  structured diagnostics with source location and actionable messages.
- Determinism tests cover repeated M66 lowering, and may include the recorded
  M65 skeleton-input-ordering follow-up as supporting regression coverage.
- Regression tests preserve M57-M65 behavior, backend raw-helper rejection,
  renderer non-evaluation, and no generated output or golden-file changes.

Golden fixtures required:

- None. M66 is a lowering/form-IR slice and must not change generated C++ or
  Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M66 exact array-initialization slot form test command selected by
  the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting exact slot-form recognition become broad TSIL parsing or a central
  raw-text dispatcher.
- Accidentally evaluating vector length, vector alignment, base type, or
  backend uninit helpers.
- Treating `var<typed>`, `array_type`, or `tmp` as broad declaration, array,
  variable-binding, allocation, or lifetime semantics.
- Mutating the M65 envelope or lowering slots `1` through `4` instead of
  appending one typed refinement stage.
- Adding SVE/direct-intrinsic semantics, store/return semantics, backend
  translation, renderer-ready IR, generated output, file/catalog reads,
  runtime `frozen/` use, dictionaries/raw string keys as downstream semantic
  models, or backend-specific branches.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, and 65.

Execution-review result:

- M66 is accepted. The next workflow action is post-M66 planning; this section
  does not select the follow-on milestone.

## Post-M66 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array initialization helper request IR | M66 now records the exact first-slot helper leaves as typed unresolved provenance. Classifying those leaves into typed deferred request records creates the next useful lowering handoff without evaluating helper semantics. | Medium if "request" becomes helper evaluation, backend translation input, or a generic raw helper dispatcher. | Select as M67. |
| Vector length/alignment semantic values | The M66 form includes `value<generation>(vector::length)` and `value<generation>(vector::alignment)`. | High now because evaluating them requires vector metadata rules, extension/type metadata policy, missing-metadata diagnostics, and could become broad vector semantics. | Defer until a request IR boundary exists and a value-resolution slice is selected. |
| Backend uninit semantics | The M66 form includes `value<backend>(uninit::array)`. | High because it invites backend value semantics, backend translation requests, renderer-ready values, and generated output pressure. | Defer. |
| Generic array/declaration IR | The M66 form is syntactically a `var<typed>(array_type<...>, tmp, ...)` declaration-like shape. | High because it combines generic `var`, `array_type`, allocation/lifetime, variable binding, and statement semantics. | Defer. |
| Next slot-specific form IR | The accepted M64/M65 envelope also has predicate, selected-body, store, and return slots. | Medium to high because the nearby slots pull in SVE predicates, direct intrinsics, store semantics, `tmp.data()`, `emit_return`, and backend/rendering pressure. | Defer until helper-request/provenance boundaries are stable. |
| Determinism-only hardening | M65 recorded a useful explicit skeleton-input-ordering test follow-up. | Low risk, but lower architectural value than the next typed lowering boundary. | Keep recorded; include only if it naturally fits a nearby implementation. |

### Milestone 67: Exact Array Initialization Helper Request IR Slice

Status:

Accepted with follow-ups after one focused documentation revision.

Goal:

Consume accepted M66 `ExactArrayInitializationSlotFormIr` values, their stage
output, or a typed `LoweredImplementation` carrying exactly one accepted M66
form as a container/source, and classify the four exact unresolved helper
leaves into typed deferred helper-request IR, without evaluating, resolving,
translating, normalizing, or rendering any helper.

M67 is a request/provenance boundary only. It is intended to make the next
array-initialization lowering steps explicit and composable before any helper
family is semantically resolved.

Scope:

- Consume accepted M66 `ExactArrayInitializationSlotFormIr` values, the typed
  `array_initialization_slot_form_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M66
  `array_initialization_slot_forms` entry as a container/source.
- Produce an immutable typed helper-request IR value, for example
  `ExactArrayInitializationHelperRequestIr`, keyed to the M66 slot form.
- Classify exactly the four M66 helper leaves into deterministic request
  records:
  - generation type request for `type<generation>(base::in)`;
  - generation value request for `value<generation>(vector::length)`;
  - generation value request for `value<generation>(vector::alignment)`;
  - backend value request for `value<backend>(uninit::array)`.
- Preserve source leaf text, leaf kind, source locations, candidate id,
  selected type tag, branch-chain identity, envelope identity, slot ordinal,
  variable token `tmp`, and deterministic request ordering.
- Append a distinct deterministic lowering stage, for example
  `array_initialization_helper_request_lowering`, after
  `array_initialization_slot_form_lowering`.
- Preserve the accepted M65 envelope, accepted M66 form IR, and all non-M66
  body slots unchanged.
- Produce structured diagnostics for invalid M67 boundary/request state, such
  as unsupported source stage/type, missing M66 form in a source container,
  multiple M66 forms in a `LoweredImplementation`, missing request leaf,
  duplicate/mismatched leaf kind, unsupported leaf text, or provenance
  mismatch.

Out of scope:

- Calling existing generation helper evaluators, including M43 base type
  resolution, from the M67 request boundary.
- Producing `GenerationTypeRef`, `GenerationValue`, vector metadata values,
  backend uninit values, backend translation requests, renderer-ready values,
  generated output, or resolved helper results.
- Evaluating `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Generic `type<generation>(...)`, `value<generation>(...)`,
  `type<backend>(...)`, or `value<backend>(...)` parsing or dispatch.
- Generic `var` parsing, generic `array_type` parsing, declaration semantics,
  array allocation/lifetime semantics, variable binding/scope, store/return
  lowering, `tmp.data()`, `emit_return`, direct-intrinsic/SVE semantics,
  vector/register metadata lookup, backend semantics, backend translation,
  rendering, generated tests, CLI/reporting/writer behavior, Rust, compiler
  execution, broad TSIL parsing, lowering-time file/catalog reads, raw TSL
  parsing, raw-text dispatch tables, or runtime `frozen/` use.

Required input:

- Accepted M66 `ExactArrayInitializationSlotFormIr` values, equivalent typed
  `array_initialization_slot_form_lowering` stage output, or a typed
  `LoweredImplementation` container with exactly one accepted M66
  `array_initialization_slot_forms` entry.
- The exact M66 unresolved helper leaf records and provenance for
  `tsldata/primitives/load_store/array.tsl:105`.

Expected outputs:

- A typed deferred helper-request IR value keyed to the accepted M66 form.
- Exactly four typed request records in deterministic order, preserving the
  accepted M66 leaf text and source locations.
- A distinct deterministic lowering stage after
  `array_initialization_slot_form_lowering`.
- Existing M65 array-body envelopes, M66 slot forms, M57-M66 lowering outputs,
  backend raw-helper rejection, renderer non-evaluation, generated outputs, and
  golden fixtures unchanged.

Parity criterion:

M67 proves the accepted M66 first-slot helper leaves can become explicit typed
request/provenance records for future helper-resolution milestones without
evaluating vector metadata, backend uninit semantics, declaration semantics, or
backend/rendering behavior.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105` for the exact helper leaves in
  the M66 first-slot form.
- Accepted M66 `ExactArrayInitializationSlotFormIr` and unresolved leaf
  records.
- Accepted M65 `LoweredImplementation.array_body_envelopes` /
  `ExactArrayBodyEnvelopeIr` integration.
- Accepted M57-M64 staged lowering and provenance boundaries.

Tests required:

- Direct M67 lowering from an accepted M66 `ExactArrayInitializationSlotFormIr`
  produces exactly four typed deferred request records.
- Normal `lower_candidates` with typed M65 skeleton input carries M67 request
  IR and appends `array_initialization_helper_request_lowering` after
  `array_initialization_slot_form_lowering`.
- Request records preserve leaf kind, source text, source location, candidate
  id, selected type tag, branch-chain identity, envelope identity, slot
  ordinal, variable token `tmp`, and deterministic ordering.
- Selected `svptrue_b16`, `svptrue_b32`, and `svptrue_b64` paths and `si8` /
  `ui8` no-body paths continue to preserve M65/M66 behavior.
- Unsupported source stage/type, missing form, missing leaf, duplicate or
  multiple forms in a `LoweredImplementation`, duplicate or mismatched leaf
  kind/text, and provenance mismatch produce structured diagnostics with
  source locations and actionable messages.
- Tests prove the request IR contains no resolved values and does not call
  generation helper evaluators, backend translation, renderers, file/catalog
  reads, or runtime `frozen/`.
- Regression tests preserve M57-M66 behavior, backend raw-helper rejection,
  renderer non-evaluation, determinism, and no generated output or golden-file
  changes.

Golden fixtures required:

- None. M67 is a lowering/request-IR slice and must not change generated C++ or
  Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M67 exact array-initialization helper-request test command
  selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting request IR become helper evaluation, especially for M43
  `base::in`, vector length/alignment metadata, or backend uninit semantics.
- Treating backend value requests as backend translation requests.
- Re-parsing `original_slot_text`, scanning raw payloads, or adding a generic
  helper dispatcher instead of consuming M66 leaf records.
- Treating `var<typed>`, `array_type`, or `tmp` as declaration, array,
  allocation, or variable-binding semantics.
- Adding store/return lowering, direct-intrinsic/SVE semantics, rendering,
  generated output, file/catalog reads, or runtime `frozen/` behavior.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, and 66.

Execution-review result:

- M67 is accepted with non-blocking follow-ups. The next workflow action is
  post-M67 planning; this section does not select the follow-on milestone.

## Post-M67 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array initialization base-type helper request resolution | M67 now exposes a typed `generation_type` request for `type<generation>(base::in)`, and M43/M52/M53/M54 already define the accepted typed base-type semantics. Resolving exactly this request proves the request IR can feed a later lowering pass. | Medium if it calls raw query-string helper evaluators, expands to the full M43 helper family, or starts resolving all four M67 requests. | Select as M68. |
| Vector length/alignment request resolution | M67 also records `value<generation>(vector::length)` and `value<generation>(vector::alignment)` requests. | High because these require vector/extension/lane metadata policy and missing-metadata diagnostics. | Defer until a vector metadata policy slice is selected. |
| Backend uninit request resolution | M67 records `value<backend>(uninit::array)` as a backend-value request. | High because it crosses into backend value semantics, backend translation requests, renderer-ready IR, and generated-output pressure. | Defer. |
| Generic helper request dispatcher | A shared resolver might seem useful after M67. | High because it would become a central helper evaluator and invite raw-string dispatch. | Reject for now; future helpers should add typed, family-specific slices. |
| Next exact slot-specific form IR | The M64/M65 envelope still has predicate, selected-body, store, and return slots. | Medium to high because nearby slots pull in SVE predicates, direct intrinsics, store semantics, `tmp.data()`, `emit_return`, and backend/rendering pressure. | Defer until first-slot helper-resolution staging is proven. |
| Determinism or diagnostic hardening | M67 and M65 recorded useful non-blocking hardening follow-ups. | Low risk, but lower architectural value than turning M67 request IR into a typed resolution pass. | Keep recorded; include only if it naturally fits M68. |

### Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice

Status:

Implemented and accepted with non-blocking follow-ups after the M68
execution-review loop.

Goal:

Consume accepted M67 `ExactArrayInitializationHelperRequestIr` values and
resolve exactly the base-type helper request record for
`type<generation>(base::in)` into a typed base-type resolution result, using
accepted M43/M52/M53/M54 base-type semantics without reparsing raw helper text.

M68 is a request-resolution boundary only. It proves that M67 request/
provenance IR can feed a later lowering pass while leaving vector metadata,
backend uninit semantics, declaration semantics, backend translation, and
rendering unresolved.

Scope:

- Consume accepted M67 `ExactArrayInitializationHelperRequestIr` values, the
  typed `array_initialization_helper_request_lowering` stage output, or a
  typed `LoweredImplementation` carrying exactly one accepted M67
  `array_initialization_helper_requests` entry as a container/source.
- Select only the M67 request record with request ordinal `0`, request kind
  `generation_type`, helper leaf kind `type_generation_base_in`, and source
  text `type<generation>(base::in)` as provenance/invariant evidence.
- Produce an immutable typed result value, for example
  `ExactArrayInitializationBaseTypeResolutionIr`, keyed to the M67 request IR
  and source base-type request record.
- Carry the resolved `GenerationTypeRef(kind="base.in",
  type_tag=<selected type tag>)` or an equivalent M68-specific wrapper around
  that accepted value.
- Use accepted M43/M52/M53/M54 selected type context and concrete integer
  generation rule semantics through typed lowering request/context inputs.
- Preserve source M67 request IR, source request record, leaf source text,
  source locations, candidate id, selected type tag, branch-chain identity,
  envelope identity, slot ordinal, variable token `tmp`, and deterministic
  result ordering.
- Preserve the remaining M67 requests for vector length, vector alignment, and
  backend uninit as unresolved request/provenance records.
- Append a distinct deterministic lowering stage, for example
  `array_initialization_base_type_request_resolution`, after
  `array_initialization_helper_request_lowering`.
- Produce structured diagnostics for invalid M68 boundary/request state, such
  as unsupported source stage/type, missing or multiple M67 request IR values,
  missing base-type request, duplicate base-type request, mismatched request
  ordinal/kind/leaf kind, unsupported base-type request text, unsupported
  selected type, or provenance mismatch.

Out of scope:

- Calling raw query-string helper evaluators such as
  `resolve_generation_type_query(...)` on M67 leaf text unless the evaluator is
  refactored behind a typed, non-text entry point and tests prove no raw helper
  text is parsed.
- Parsing, regex-matching, normalizing, or dispatching on `leaf_source_text`,
  `original_slot_text`, raw TSIL, raw TSL, or helper strings. Source text is
  provenance/invariant evidence only.
- Resolving `base.signed_of`, `base.unsigned_of`, or any other M43 type query
  family.
- Resolving `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Producing `GenerationValue`, vector metadata values, backend uninit values,
  backend translation requests, renderer-ready values, generated output, or
  resolved array declaration semantics.
- Generic `type<generation>(...)`, `value<generation>(...)`,
  `type<backend>(...)`, or `value<backend>(...)` parsing or dispatch.
- Generic `var` parsing, generic `array_type` parsing, declaration semantics,
  array allocation/lifetime semantics, variable binding/scope, store/return
  lowering, `tmp.data()`, `emit_return`, direct-intrinsic/SVE semantics,
  vector/register metadata lookup, backend semantics, backend translation,
  rendering, generated tests, CLI/reporting/writer behavior, Rust, compiler
  execution, broad TSIL parsing, lowering-time file/catalog reads, raw TSL
  parsing, raw-text dispatch tables, or runtime `frozen/` use.

Required input:

- Accepted M67 `ExactArrayInitializationHelperRequestIr` values, equivalent
  typed `array_initialization_helper_request_lowering` stage output, or a
  typed `LoweredImplementation` container with exactly one accepted M67
  `array_initialization_helper_requests` entry.
- The exact M67 base-type request record and provenance for
  `tsldata/primitives/load_store/array.tsl:105`.
- Accepted M43/M52/M53/M54 typed base-type semantics and concrete integer
  generation rule inputs already available before lowering evaluation.

Expected outputs:

- A typed base-type request-resolution IR value keyed to the accepted M67
  request IR and source base-type request record.
- A typed base-type result equivalent to
  `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`.
- A distinct deterministic lowering stage after
  `array_initialization_helper_request_lowering`.
- Remaining vector length, vector alignment, and backend uninit M67 request
  records preserved as unresolved provenance.
- Existing M57-M67 lowering outputs, backend raw-helper rejection, renderer
  non-evaluation, generated outputs, and golden fixtures unchanged.

Parity criterion:

M68 proves the accepted M67 request/provenance IR can drive a typed helper
resolution pass for the already accepted base-type semantics without raw
helper reparsing, vector metadata policy, backend uninit semantics,
declaration semantics, backend translation, or renderer behavior.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105` for the exact first-slot
  `type<generation>(base::in)` helper request evidence.
- Accepted M67 `ExactArrayInitializationHelperRequestIr` and request records.
- Accepted M43 `GenerationTypeRef(kind="base.in")` behavior.
- Accepted M52 concrete integer type/signedness expansion.
- Accepted M53 typed concrete integer generation rule source.
- Accepted M54 catalog-derived rule wiring into lowering inputs.

Tests required:

- Direct M68 lowering from an accepted M67
  `ExactArrayInitializationHelperRequestIr` resolves exactly the base-type
  request for selected supported concrete integer tags.
- Normal `lower_candidates` with typed M65/M66/M67 input carries M68
  base-type resolution IR and appends
  `array_initialization_base_type_request_resolution` after
  `array_initialization_helper_request_lowering`.
- The resolved type result matches accepted M43/M52/M53/M54 selected type
  context and concrete integer rule semantics.
- Vector length, vector alignment, and backend uninit requests remain
  unresolved and unchanged.
- Unsupported source stage/type, missing or multiple request IR values,
  missing base-type request, duplicate base-type request, mismatched
  ordinal/kind/leaf kind, unsupported base-type request text, unsupported
  selected type, and provenance mismatch produce structured diagnostics with
  source locations and actionable messages.
- Tests prove M68 consumes typed M67 records and does not call raw query-string
  helper evaluators on M67 leaf text, parse raw helper strings, read files,
  query the catalog during evaluation, invoke backend translation, feed
  renderers, or use runtime `frozen/`.
- Regression tests preserve M57-M67 behavior, backend raw-helper rejection,
  renderer non-evaluation, determinism, and no generated output or golden-file
  changes.

Golden fixtures required:

- None. M68 is a lowering/request-resolution slice and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M68 exact array-initialization base-type request-resolution test
  command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Calling raw query-string helper evaluators on M67 leaf text or adding a
  generic helper dispatcher.
- Expanding from `base.in` to the whole M43 type-query family.
- Resolving all four M67 requests rather than only the base-type request.
- Making vector metadata, backend uninit, declaration, array, store, return,
  direct-intrinsic, backend translation, rendering, or output decisions under
  the cover of request resolution.
- Rebuilding rule sources, querying catalogs, reading `tsldata`, or inspecting
  `frozen/` during lowering evaluation.
- Mutating M67 request IR instead of appending one typed resolution stage.

Dependencies on prior milestones:

- Milestones 43, 52, 53, 54, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, and 67.

Next concrete prompt:

- M68 execution is complete and accepted. Post-M68 planning is the next
  workflow step.

## Post-M68 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array-initialization stage pipeline extraction | M68 review identified the growing M64-M68 array-initialization tail in `_lower_input` as the next maintainability pressure point. Extracting it into a typed helper/pipeline extension point lets future vector/backend request-resolution stages attach locally without changing behavior now. | Medium if it becomes a cosmetic wrapper, a broad stage registry, or a semantic helper dispatcher. Low if it preserves current outputs, diagnostics, and stage order exactly. | Select as M69. |
| Vector length request resolution | M67 records `value<generation>(vector::length)` as a typed request, and resolving it would move functionality forward. | High now because it requires selected extension/type lane metadata policy and could extend the current `_lower_input` tail before the stage assembly point is maintainable. | Defer until after M69 extraction. |
| Vector alignment request resolution | M67 records `value<generation>(vector::alignment)` as a typed request, and aligned load/store bodies need this later. | High now because it requires alignment metadata policy and aligned branch context; it should use the extracted stage point rather than expand `_lower_input` further. | Defer until after M69 extraction and metadata policy selection. |
| Backend uninit request boundary | M67 records `value<backend>(uninit::array)` as a backend-value request. | High because it crosses into backend value semantics, backend translation requests, renderer-ready IR, and generated-output pressure. | Defer. |
| Generic helper resolver family | A shared resolver abstraction could prepare future helper families. | High because it could become a central raw-string dispatcher or stage registry before multiple typed resolver families justify it. | Reject for now. |
| Next exact slot-specific form IR | The M64/M65 envelope still has predicate, selected-body, store, and return slots. | Medium to high because nearby slots pull in SVE predicates, direct intrinsics, store semantics, `tmp.data()`, `emit_return`, and backend/rendering pressure. | Defer. |
| Stage-contract table cleanup | `GenerationLoweringStage.__post_init__` is a growing stage-name-to-output-type table. | Medium if mixed with extraction; it is type validation rather than semantic dispatch, but broadening it could distract from the immediate array-initialization tail. | Keep as follow-up. |

### Milestone 69: Exact Array Initialization Stage Pipeline Extraction Slice

Status:

Accepted after the M69 execution-review loop.

Goal:

Extract the accepted M64-M68 exact array-initialization stage assembly tail from
`_lower_input` into a small typed helper or private pipeline result while
preserving observable behavior exactly.

M69 is behavior-preserving maintainability work only. It creates a clearer
typed attachment point for later vector length, vector alignment, backend
uninit, or array/declaration slices, but it does not implement any of those
semantics.

Scope:

- Extract only the existing exact array-initialization sequence currently
  assembled inline after selected-body envelope lowering:
  - accepted M64 array-body envelope assembly;
  - accepted M66 exact array-initialization slot form lowering;
  - accepted M67 exact helper-request IR lowering;
  - accepted M68 exact base-type request resolution.
- Introduce a small private typed helper/result, for example
  `ExactArrayInitializationStagePipelineResult`, carrying the same existing
  output tuples and `GenerationLoweringStage` records currently assembled in
  `_lower_input`.
- Preserve the same public `LoweredImplementation` fields, stage names, stage
  order, typed outputs, diagnostics, source locations, deterministic ordering,
  and no-skeleton/no-body behavior as accepted M68.
- Keep the accepted calls to M64/M66/M67/M68 lowering functions in the same
  order and with the same typed inputs.
- Keep M66 slot text and M67 leaf text as provenance/invariant evidence only.
- Leave `GenerationLoweringStage.__post_init__` table cleanup and
  `_ExactArrayInitializationBaseTypeRequestRule.result_kind` cleanup as
  follow-ups unless they are touched only mechanically and without semantic
  scope expansion.

Out of scope:

- New semantic helper resolution.
- Resolution of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Generic helper resolver families, broad stage registries, raw helper-string
  dispatch, or semantic tables keyed by source text, request ordinals, selected
  type tags, SVE tokens, backend ids, or renderer names.
- New public IR, new `LoweredImplementation` fields, new stage names, or
  renderer-facing values.
- New slot-specific lowering beyond the existing exact ordinal-0
  array-initialization slot; predicate initialization, selected-body, store,
  and return slots remain untouched and opaque.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable,
  store, return, SVE/direct-intrinsic, backend translation, rendering,
  generated output, generated tests, CLI/reporting/writer behavior, Rust,
  compiler execution, broad TSIL parsing, lowering-time file/catalog reads,
  raw TSL parsing, `tsldata` reads during lowering evaluation, or runtime
  `frozen/` use.

Required input:

- Accepted M63 selected/no-body envelope outputs and accepted M64 skeleton
  inputs/lookup behavior.
- Accepted M64 `ExactArrayBodyEnvelopeIr` behavior.
- Accepted M66 `ExactArrayInitializationSlotFormIr` behavior.
- Accepted M67 `ExactArrayInitializationHelperRequestIr` behavior.
- Accepted M68 `ExactArrayInitializationBaseTypeResolutionIr` behavior.
- Existing typed `LoweringInput`, `LoweringRequest`, and generation context
  inputs, including M43/M52/M53/M54 rule/context inputs used by M68.

Expected outputs:

- A private typed helper/pipeline result carrying the same existing tuples for:
  - `array_body_envelopes`;
  - `array_initialization_slot_forms`;
  - `array_initialization_helper_requests`;
  - `array_initialization_base_type_resolutions`;
  - corresponding `GenerationLoweringStage` records.
- `lower_candidates` output identical to accepted M68 for the covered selected
  and no-body paths.
- No generated artifact, golden output, backend translation, renderer,
  CLI/report/writer, Rust, or compiler behavior changes.

Parity criterion:

M69 proves the accepted M64-M68 array-initialization lowering sequence can be
owned by a typed sub-pipeline boundary without changing behavior or creating a
semantic dispatcher.

Evidence paths:

- M68 review follow-up in `docs/agent/current-redesign-state.md` identifying
  the growing M64-M68 `_lower_input` tail as the next maintainability pressure.
- `tslgen/src/tslgen/lowering/boundary.py` around `_lower_input`, where the
  accepted M64/M66/M67/M68 outputs and stages are assembled inline.
- Accepted M64, M65, M66, M67, and M68 lowering tests for stage order,
  diagnostics, deterministic output, and unresolved helper preservation.
- `tsldata/primitives/load_store/array.tsl:105-111` only as existing corpus
  context for the accepted exact array-body envelope; no new corpus evidence
  is required.

Tests required:

- Direct helper/pipeline tests for selected `svptrue_b16`, `svptrue_b32`, and
  `svptrue_b64` paths, plus no-body paths such as `si8`/`ui8`, proving the
  helper returns the same tuples and stage records that `_lower_input`
  previously assembled inline.
- Normal `lower_candidates` tests proving identical `LoweredImplementation`
  fields and the same stage sequence:
  `array_body_envelope_slot_assembly`,
  `array_initialization_slot_form_lowering`,
  `array_initialization_helper_request_lowering`, and
  `array_initialization_base_type_request_resolution`.
- Failure-propagation tests for representative M64/M66/M67/M68 diagnostics,
  preserving diagnostic codes, severity, source locations, and actionable
  message intent.
- Determinism tests comparing repeated runs and, where nearby skeleton inputs
  are touched, reversed skeleton ordering.
- Regression tests proving no raw helper parsing, no raw query-string helper
  evaluation on M67 leaf text, no vector/backend request resolution, no
  backend translation/rendering, and no generated output or golden-file
  changes.

Golden fixtures required:

- None. M69 is a behavior-preserving lowering-pipeline extraction and must not
  change generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M69 behavior-preservation test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Cosmetic extraction that leaves `_lower_input` as the real orchestration
  point.
- Broad stage registry or semantic dispatcher introduced under a
  maintainability label.
- Any changed `LoweredImplementation` fields, stage names/order, diagnostics,
  deterministic ordering, no-body/no-skeleton behavior, or generated outputs.
- Pulling in vector length/alignment, backend uninit, declaration/array,
  store/return, SVE/direct-intrinsic, backend translation, rendering, output,
  file/catalog reads, raw helper dispatch, or runtime `frozen/` use.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, and 68.

Next concrete prompt:

- M69 execution is complete and accepted. Post-M69 lowering planning is the
  next workflow step.

## Post-M69 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array-initialization vector-length request resolution | M67 records `value<generation>(vector::length)` as a typed request, M68 proved the sibling request-resolution pattern for `type<generation>(base::in)`, and M69 provides the extracted typed stage-pipeline attachment point. Resolving one remaining request moves the array-initialization lowering chain materially forward. | High if it infers lanes from SVE tokens, vector bits, type tags, host CPU, catalog data, backend maps, or raw helper text. Low to medium if it consumes explicit typed vector-length metadata supplied before lowering evaluation and preserves scalable/runtime-lane uncertainty as typed value policy or diagnostics. | Select as M70, with explicit typed metadata input as a blocking boundary. |
| Typed vector metadata input boundary only | A metadata-only milestone could be needed if vector-length facts cannot be stated without speculative policy. | Medium because it may be too abstract if it does not resolve a selected request. | Defer unless M70 execution discovers the metadata input cannot be made explicit and narrow. |
| Vector alignment request resolution | M67 records `value<generation>(vector::alignment)`, and aligned load/store bodies need it later. | Higher than vector length because alignment is tied to aligned branches, backend/language maps, and `assume_aligned` behavior. | Defer until after vector-length resolution and selected alignment policy. |
| Backend uninit request boundary | M67 records `value<backend>(uninit::array)` as a backend-value request. | High because it crosses into backend value semantics, backend translation requests, renderer-ready values, and generated-output pressure. | Defer. |
| Exact array declaration/array-type IR | The first slot cannot become renderer-useful until base type, vector length, vector alignment, and backend uninit have typed values. | High if it broadens into `var`, `array_type`, allocation/lifetime, store, or return semantics before helper values are resolved. | Defer until the selected helper requests are resolved or explicitly modeled. |
| Stage-contract table cleanup | `GenerationLoweringStage.__post_init__` is a growing stage-name-to-output-type table. | Medium if mixed with new semantics; it is type validation rather than semantic dispatch. | Keep as follow-up. |

### Milestone 70: Exact Array Initialization Vector-Length Request Resolution Slice

Status:

Accepted. The M70 execution-review loop returned `Accept With Follow-Ups`
after one focused documentation revision.

Goal:

Resolve exactly the accepted M67 array-initialization helper request for
`value<generation>(vector::length)` into a typed vector-length request
resolution result, using the extracted M69 array-initialization stage pipeline
and explicit typed vector-length metadata supplied before lowering evaluation.

M70 is generation-time lowering request resolution only. It consumes lane facts
as typed inputs; it does not compute them from raw helper text, SVE token text,
extension names, vector-bit strings, selected type tags, host CPU features,
backend maps, renderers, or catalog/file reads during lowering evaluation.

Scope:

- Consume accepted M67 `ExactArrayInitializationHelperRequestIr` request
  records through the accepted M68/M69 array-initialization pipeline after
  `array_initialization_base_type_request_resolution`.
- Select only the request record whose kind/leaf identify the exact
  `value<generation>(vector::length)` helper.
- Introduce or consume explicit typed vector-length metadata input, supplied
  before lowering evaluation through `LoweringRequest`, `GenerationContext`,
  or an equivalent typed request/context value.
- Use typed candidate context such as candidate id, target extension, source
  extension, and selected type tag as structured fields, not by parsing
  `candidate_id` or source text.
- Produce a typed result such as
  `ExactArrayInitializationVectorLengthResolutionIr`, carrying:
  - the source M68 base-type resolution;
  - the source M67 vector-length request record;
  - a typed vector-length value or policy value;
  - remaining unresolved requests for vector alignment and backend uninit;
  - deterministic provenance including candidate, type, envelope/slot, and
    source location facts.
- Append one deterministic stage after
  `array_initialization_base_type_request_resolution`, for example
  `array_initialization_vector_length_request_resolution`.
- Preserve accepted M68 base-type resolution behavior and accepted M69
  pipeline behavior.
- Preserve the M69 review follow-up by adding explicit pipeline-level M67
  diagnostic propagation coverage, since M70 extends the extracted pipeline.

Out of scope:

- Resolution of `value<generation>(vector::alignment)` or
  `value<backend>(uninit::array)`.
- Broad vector/register metadata semantics, SVE predicate semantics, register
  type lowering, byte-size-to-`svptrue_b*` inference, or lane-count inference
  from `vector_bits`, scalar byte size, selected type tag, extension name, SVE
  token text, backend id, renderer name, catalog data, `tsldata`, or host CPU
  state during lowering.
- Backend translation or backend rendering of vector length, including C++
  spellings such as `Vec::vector_element_count()`.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable
  scope, store, return, `tmp.data()`, `emit_return`, direct-intrinsic
  semantics, loops, calls, casts, or broad TSIL parsing.
- Generic `value<generation>(...)` evaluator families, broad stage registries,
  raw helper-string dispatch, or semantic tables keyed by raw helper text,
  request ordinals, selected type tags, SVE tokens, backend ids, or renderer
  names.
- Generated C++ or Rust output, generated tests, golden output, CLI/reporting/
  writer behavior, compiler execution, lowering-time file/catalog reads, raw
  TSL parsing, `tsldata` reads during lowering evaluation, or runtime
  `frozen/` use.

Required input:

- Accepted M67 helper request IR for the exact first-slot helper leaves.
- Accepted M68 base-type request resolution output, including preserved
  unresolved vector-length, vector-alignment, and backend-uninit requests.
- Accepted M69 extracted array-initialization stage pipeline boundary.
- Typed selected-candidate context already available to lowering, including
  candidate id, target/source extension, and selected type tag.
- Explicit in-memory typed vector-length metadata/rules supplied before
  lowering evaluation. Runtime/scalable metadata must be represented as an
  explicit typed policy/value or rejected with diagnostics; M70 must not fake a
  fixed integer lane count for runtime-lane extensions.

Expected outputs:

- One typed vector-length request-resolution IR value for the exact selected
  request when metadata is sufficient.
- A typed vector-length value or policy value suitable for later typed lowering
  consumers, but not renderer-ready text.
- One deterministic generation-lowering stage after
  `array_initialization_base_type_request_resolution`.
- Remaining unresolved request records for vector alignment and backend uninit.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, or compiler behavior change.

Parity criterion:

M70 proves one sibling helper request can be resolved through the M69 extracted
typed pipeline from explicit metadata without hardwiring vector semantics or
crossing into backend rendering.

Evidence paths:

- Accepted M67 helper request IR and M68 unresolved-request preservation in
  `tslgen/src/tslgen/lowering/boundary.py`.
- Accepted M69 private array-initialization stage pipeline helper in
  `tslgen/src/tslgen/lowering/boundary.py`.
- `tsldata/primitives/load_store/array.tsl:105` for the exact selected
  `value<generation>(vector::length)` request in the accepted first-slot form.
- `tsldata/extensions/extension.tsl:212-219` and
  `docs/redesign/open-questions.md` OQ-007 as evidence that SVE scalable/
  runtime-lane behavior must not be converted into a fake fixed lane count.
- `tsldata/detail/lang/translate_cpp.tsl:63` only as evidence that backend
  vector-length spelling exists later; it must not be emitted or consumed by
  M70.

Tests required:

- Direct resolver tests for the M67/M68 vector-length request using explicit
  typed vector-length metadata.
- Normal `lower_candidates` pipeline tests proving the M70 stage appears after
  `array_initialization_base_type_request_resolution` and preserves M69 output
  ordering.
- Tests for static metadata and, if selected by implementation policy, runtime/
  scalable metadata as a typed policy value rather than a fixed lane count.
- Diagnostics for missing metadata, duplicate/conflicting metadata,
  unsupported runtime/scalable numeric resolution, mismatched selected
  candidate context, malformed/missing/multiple vector-length request records,
  unsupported source stage, and provenance mismatch.
- Determinism tests for repeated runs and reversed metadata input order.
- Regression tests proving vector alignment and backend uninit remain
  unresolved; M68 base-type behavior remains unchanged; raw helper evaluators
  are not called on M67 leaf text; raw helper text is not parsed; no catalog,
  `tsldata`, host CPU, backend translation, rendering, generated output, or
  golden-file behavior is introduced.
- Pipeline-level M67 diagnostic propagation coverage, since M70 extends the
  extracted M69 stage pipeline.

Golden fixtures required:

- None. M70 is lowering-only request resolution and must not change generated
  C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M70 vector-length request-resolution test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Hidden hardwiring from `(extension, type_tag)` or SVE token text directly to
  a semantic value instead of consuming explicit typed vector-length metadata.
- Treating SVE scalable/runtime-lane metadata as a fixed integer lane count.
- Reusing backend C++ vector-length spelling as a lowering value.
- Adding a broad vector metadata resolver, generic helper dispatcher, raw
  helper parser, broad stage registry, declaration/array lowering, or
  backend/rendering/output behavior under the vector-length label.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, and 69.

Next concrete prompt:

- M70 execution is complete and accepted. Post-M70 lowering planning is the
  next workflow step.

## Post-M70 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Exact array-initialization vector-alignment request resolution | M67 records `value<generation>(vector::alignment)` as a typed request, M70 preserves it unresolved after resolving the sibling vector-length request, and the M69/M70 stage pipeline now provides the typed attachment point. Resolving it completes the generation-side vector metadata pair for the exact first array-initialization slot. | High if it infers alignment from vector length, vector bits, scalar byte size, selected type tags, SVE spelling, extension names, backend maps, host CPU state, catalog data, or raw helper text. Low to medium if it consumes explicit typed alignment metadata supplied before lowering evaluation and preserves backend uninit unresolved. | Select as M71, with explicit typed alignment metadata input as a blocking boundary. |
| Backend uninit request boundary | M67 records `value<backend>(uninit::array)` as the remaining backend-value request. | High because it crosses into backend-scoped value semantics, backend translation requests, renderer-ready values, and generated-output pressure. | Defer until generation-side helper requests are resolved. |
| Typed vector metadata input boundary only | A metadata-only milestone could generalize length/alignment inputs. | Medium because it risks becoming a broad registry without resolving a selected request. M70 already proved a narrow explicit metadata pattern. | Defer unless M71 execution discovers alignment metadata cannot be stated narrowly. |
| Exact array declaration/array-type IR | The first slot moves toward declaration/array IR once base type, vector length, vector alignment, and backend uninit are resolved or modeled. | High before alignment and backend uninit are handled because it invites `var`, `array_type`, allocation/lifetime, store, return, and rendering semantics. | Defer. |
| Diagnostic/no-runtime-dependency hardening only | M70 left a non-blocking follow-up for explicit no catalog/`tsldata`/host CPU read coverage. | Low risk but lower value than resolving the next exact request. | Fold into M71 validation criteria. |

### Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice

Status:

Accepted after the M71 execution-review loop.

Goal:

Resolve exactly the accepted M67 array-initialization helper request for
`value<generation>(vector::alignment)` into a typed vector-alignment request
resolution result, using the accepted M69/M70 array-initialization stage
pipeline and explicit typed vector-alignment metadata supplied before lowering
evaluation.

M71 is generation-time lowering request resolution only. It consumes alignment
facts as typed inputs; it does not compute them from vector length, vector
bits, scalar byte size, selected type tags, SVE token text, extension names,
backend ids, renderer names, host CPU features, backend maps, catalog/file
reads, `tsldata`, raw helper text, or `candidate_id` parsing.

Scope:

- Consume accepted M70 vector-length request-resolution output, the accepted
  M68 base-type resolution, the accepted M67 helper-request IR, and the
  extracted M69 array-initialization stage pipeline.
- Select only the remaining request record whose typed kind/leaf/ordinal
  identify the exact `value<generation>(vector::alignment)` helper from the
  first array-initialization slot.
- Introduce or consume explicit typed vector-alignment metadata input,
  supplied before lowering evaluation through `LoweringRequest`,
  `GenerationContext`, or an equivalent typed request/context value.
- Use typed candidate context such as candidate id, target extension, source
  extension, and selected type tag as structured fields, not by parsing
  `candidate_id` or source text.
- Produce a typed result such as
  `ExactArrayInitializationVectorAlignmentResolutionIr`, carrying:
  - the source M70 vector-length resolution;
  - the source M67 vector-alignment request record;
  - a typed alignment value or explicit unsupported-policy diagnostic;
  - the remaining unresolved backend-uninit request;
  - deterministic provenance including candidate, type, envelope/slot, and
    source location facts.
- Append one deterministic stage after
  `array_initialization_vector_length_request_resolution`, for example
  `array_initialization_vector_alignment_request_resolution`.
- Preserve accepted M68 base-type behavior, accepted M69 stage-pipeline
  behavior, and accepted M70 vector-length behavior.
- Address the M70 validation hardening follow-up by requiring explicit tests
  that no catalog reads, `tsldata` reads, or host CPU queries are used during
  request resolution.

Out of scope:

- Resolution of `value<backend>(uninit::array)`.
- Broad vector/register metadata semantics, vector register type lowering, SVE
  predicate semantics, aligned load/store semantics, `assume_aligned`
  rendering, byte-size-to-`svptrue_b*` inference, or alignment inference from
  vector length, vector bits, scalar byte size, selected type tag, extension
  name, SVE token text, backend id, renderer name, catalog data, `tsldata`, or
  host CPU state during lowering.
- Backend translation or backend rendering of vector alignment, including C++
  spellings such as `Vec::vector_alignment()`.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable
  scope, store, return, `tmp.data()`, `emit_return`, direct-intrinsic
  semantics, loops, calls, casts, or broad TSIL parsing.
- Generic `value<generation>(...)` or `value<backend>(...)` evaluator
  families, broad stage registries, raw helper-string dispatch, or semantic
  tables keyed by raw helper text, request ordinals alone, selected type tags,
  SVE tokens, backend ids, or renderer names.
- Generated C++ or Rust output, generated tests, golden output, CLI/reporting/
  writer behavior, compiler execution, lowering-time file/catalog reads, raw
  TSL parsing, `tsldata` reads during lowering evaluation, or runtime
  `frozen/` use.

Required input:

- Accepted M67 helper request IR for the exact first-slot helper leaves.
- Accepted M68 base-type request resolution output.
- Accepted M69 extracted array-initialization stage pipeline boundary.
- Accepted M70 vector-length request-resolution output preserving the
  vector-alignment and backend-uninit requests.
- Typed selected-candidate context already available to lowering, including
  candidate id, target/source extension, and selected type tag.
- Explicit in-memory typed vector-alignment metadata/rules supplied before
  lowering evaluation. Unsupported policy must be explicit typed diagnostics;
  M71 must not fake or infer alignment values.

Expected outputs:

- One typed vector-alignment request-resolution IR value for the exact selected
  request when metadata is sufficient.
- A typed vector-alignment value or policy value suitable for later typed
  lowering consumers, but not renderer-ready text.
- One deterministic generation-lowering stage after
  `array_initialization_vector_length_request_resolution`.
- Remaining unresolved request record for backend uninit.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, or compiler behavior change.

Parity criterion:

M71 proves a second sibling helper request can be resolved through the M69/M70
typed pipeline from explicit metadata without hardwiring vector semantics,
borrowing aligned load/store behavior, or crossing into backend rendering.

Evidence paths:

- Accepted M67 helper request IR and M68/M70 unresolved-request preservation in
  `tslgen/src/tslgen/lowering/boundary.py`.
- Accepted M70 vector-length request-resolution pattern and tests in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- `tsldata/primitives/load_store/array.tsl:105` for the exact selected
  `value<generation>(vector::alignment)` request in the accepted first-slot
  form.
- `tsldata/primitives/load_store/load.tsl:55-70` and
  `tsldata/primitives/load_store/store.tsl:54-64` only as evidence that vector
  alignment semantics exist later for aligned load/store bodies; M71 must not
  consume aligned branch/body semantics.
- `tsldata/detail/lang/translate_cpp.tsl:65` only as evidence that backend
  vector-alignment spelling exists later; it must not be emitted or consumed
  by M71.

Tests required:

- Direct resolver tests for the M67/M70 vector-alignment request using explicit
  typed vector-alignment metadata.
- Normal `lower_candidates` pipeline tests proving the M71 stage appears after
  `array_initialization_vector_length_request_resolution` and preserves M69/M70
  output ordering.
- Tests for static alignment metadata and unsupported-policy diagnostics.
- Diagnostics for missing metadata, duplicate/conflicting metadata,
  mismatched selected candidate context, malformed/missing/multiple
  vector-alignment request records, unsupported source stage, and provenance
  mismatch.
- Determinism tests for repeated runs and reversed metadata input order.
- Regression tests proving backend uninit remains unresolved; M68 base-type
  behavior and M70 vector-length behavior remain unchanged; raw helper
  evaluators are not called on M67 leaf text; raw helper text is not parsed; no
  catalog, `tsldata`, host CPU, backend translation, rendering, generated
  output, or golden-file behavior is introduced.

Golden fixtures required:

- None. M71 is lowering-only request resolution and must not change generated
  C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M71 vector-alignment request-resolution test command selected by
  the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Hidden hardwiring from `(extension, type_tag)`, vector length, vector bits,
  scalar byte size, or SVE token text directly to a semantic value instead of
  consuming explicit typed vector-alignment metadata.
- Reusing backend C++ vector-alignment spelling as a lowering value.
- Treating aligned load/store `assume_aligned` evidence as runtime dependency
  or selected body semantics.
- Adding a broad vector metadata resolver, generic helper dispatcher, raw
  helper parser, broad stage registry, declaration/array lowering, backend
  uninit resolution, or backend/rendering/output behavior under the alignment
  label.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, and 70.

Next concrete prompt:

- M71 execution is complete and accepted. Post-M71 lowering planning is the
  next workflow step.

## Post-M71 Planning Result

Candidate comparison:

| Candidate | Why considered | Boundary risk | Decision |
| --- | --- | --- | --- |
| Narrow backend-uninit request boundary | M71 leaves only the exact M67 `value<backend>(uninit::array)` request unresolved in the accepted first-slot helper family. | High if it resolves to backend text or queries backend maps; lower if it is only a typed deferred boundary. | Safe but slightly too small because later declaration/array slices would still need to stitch together M68/M70/M71 and the remaining request. |
| Exact array-initialization helper-set completion IR | Completes the exact M66/M67 first-slot helper set as typed lowering state: accepted M68 base type, accepted M70 vector length, accepted M71 vector alignment, and the remaining backend-uninit request as a typed deferred boundary. | Medium if the aggregate remains exact, typed, and non-rendering; high if it turns into backend uninit translation, broad helper dispatch, or declaration/array lowering. | Select as M72, with strict wording that backend uninit remains a typed unresolved backend-value request boundary and no backend/rendering/output behavior is introduced. |
| Exact array declaration/array-type IR | Once the helper set is complete, later slices can start lowering the surrounding `var<typed>(array_type<...>, tmp, ...)` structure. | High now because it invites `var`, `array_type`, allocation/lifetime, initializer, store, return, `tmp.data()`, and rendering semantics before the helper set has a single typed handoff. | Defer until M72 provides a complete typed helper-set input. |
| Private exact-array resolver cleanup | M68/M70/M71 repeat request/provenance/metadata validation shapes. | Medium if it becomes a broad registry or central raw-helper dispatcher. | Defer as a standalone milestone; permit only the smallest private typed helper extraction needed by M72. |
| Diagnostic/no-runtime-dependency hardening only | M69/M70/M71 left non-blocking follow-ups around pipeline-level diagnostic propagation and broader no-runtime-dependency guards. | Low risk, but lower value than completing the helper-set handoff. | Fold relevant hardening into M72 validation criteria. |

### Milestone 72: Exact Array Initialization Helper-Set Completion IR Slice

Status:

Accepted after M72 execution review.

Goal:

Consume the accepted M71 vector-alignment resolution for the exact first
array-initialization slot and package the complete helper set into one typed
aggregate IR: the accepted M68 base-type resolution, accepted M70
vector-length resolution, accepted M71 vector-alignment resolution, and the
remaining exact M67 `value<backend>(uninit::array)` request as a typed
unresolved backend-value request boundary.

M72 is generation-time lowering helper-set completion only. It must not
resolve backend uninit into backend text, backend translation requests,
renderer-ready values, generated output, or declaration/array semantics.

Scope:

- Consume only accepted M71
  `ExactArrayInitializationVectorAlignmentResolutionIr` values, the
  `array_initialization_vector_alignment_request_resolution` stage output, or
  a typed `LoweredImplementation` carrying exactly one accepted M71
  vector-alignment resolution.
- Select only the remaining M67 request record whose typed fields identify the
  exact backend-uninit helper from the first array-initialization slot:
  request ordinal `3`, request kind `backend_value`, and helper leaf kind
  `value_backend_uninit_array`.
- Model that backend-uninit request only as a typed deferred backend-value
  request boundary or policy value. Source text may be preserved only as
  provenance/invariant evidence.
- Produce one typed aggregate such as
  `ExactArrayInitializationHelperSetCompletionIr`, carrying:
  - the source M71 vector-alignment resolution;
  - the accepted M70 vector-length resolution;
  - the accepted M68 base-type resolution;
  - the source M67 backend-uninit request record;
  - the typed unresolved backend-uninit boundary/policy;
  - deterministic provenance including candidate id, target/source extension,
    selected type tag, branch-chain id, envelope/slot identity, variable token,
    and source locations.
- Append one deterministic stage after
  `array_initialization_vector_alignment_request_resolution`, for example
  `array_initialization_helper_set_completion`.
- Preserve accepted M68 base-type behavior, accepted M69 stage-pipeline
  behavior, accepted M70 vector-length behavior, and accepted M71
  vector-alignment behavior.
- Include M69/M71 hardening follow-ups where practical: pipeline-level M67
  diagnostic propagation coverage for the extracted array-initialization stage
  pipeline and guards that M72 lowering does not read catalog data, `tsldata`,
  host CPU state, backend maps, or `frozen/` at evaluation time.

Out of scope:

- Translating, resolving, or rendering `value<backend>(uninit::array)` to C++,
  Rust, backend text, initializer syntax, `{}`, `MaybeUninit`, backend
  translation requests, renderer-ready values, or generated output.
- Backend manifests, backend maps, language maps, translation maps,
  renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- Broad `var`, `array_type`, declaration, array allocation/lifetime,
  variable binding/scope, initializer semantics, store, return, `tmp.data()`,
  `emit_return`, `assume_aligned`, direct-intrinsic/SVE semantics, loops,
  calls, casts, or multi-statement lowering.
- Generic `value<backend>(...)`, `type<backend>(...)`,
  `value<generation>(...)`, or `type<generation>(...)` evaluator families;
  broad helper registries; raw helper-string dispatch; broad stage registries;
  broad TSIL parsing; lowering-time file/catalog reads; raw TSL parsing;
  `tsldata` reads during lowering evaluation; host CPU queries; or runtime
  dependency on `frozen/`.

Required input:

- Accepted M67 helper request IR for the exact first-slot helper leaves.
- Accepted M68 base-type request-resolution output.
- Accepted M69 extracted array-initialization stage pipeline boundary.
- Accepted M70 vector-length request-resolution output.
- Accepted M71 vector-alignment request-resolution output preserving only the
  backend-uninit request as unresolved.
- Typed selected-candidate context already available to lowering, including
  candidate id, target/source extension, and selected type tag. Backend id may
  be preserved as typed provenance/policy input only if already supplied; it
  must not drive backend map lookup or emitted text.

Expected outputs:

- One typed unresolved backend-uninit boundary/policy value for the exact M67
  backend-uninit request.
- One typed helper-set completion aggregate with no remaining unresolved
  helper-request records for the exact first array-initialization slot.
- One deterministic generation-lowering stage after
  `array_initialization_vector_alignment_request_resolution`.
- Structured diagnostics for unsupported source/container shapes,
  missing/duplicate/mismatched/malformed backend-uninit request records,
  context mismatch, and provenance mismatch.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, or compiler behavior change.

Parity criterion:

M72 proves the accepted M66/M67 first-slot helper family can be completed as a
single typed lowering handoff after M68/M70/M71, while keeping backend uninit
deferred and preventing declaration/rendering semantics from leaking into
lowering.

Evidence paths:

- Accepted M67 helper request IR and M68/M70/M71 unresolved-request
  preservation in `tslgen/src/tslgen/lowering/boundary.py`.
- Accepted M70/M71 request-resolution pattern and tests in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- `tsldata/primitives/load_store/array.tsl:105` for the exact selected
  `value<backend>(uninit::array)` request in the accepted first-slot form.
- Other same-shape `array.tsl` forms at lines 37, 45, 54, 62, 71, 79, 88,
  and 96 are supporting corpus repetition only, not expanded M72 scope.
- `tsldata/detail/lang/translate_cpp.tsl` backend-uninit entries are evidence
  that output behavior exists later; M72 must not read or consume those maps.
- `frozen/` remains legacy evidence only and must not become runtime input.

Tests required:

- Direct resolver tests from M71 vector-alignment resolution to the M72
  helper-set completion aggregate.
- Normal `lower_candidates` pipeline tests proving the M72 stage appears after
  `array_initialization_vector_alignment_request_resolution` and preserves
  M68/M69/M70/M71 ordering and outputs.
- Tests proving the backend-uninit request is identified by typed M67 fields
  and source text is provenance/invariant evidence only.
- Diagnostics for missing, duplicate, wrong-kind, wrong-ordinal, unsupported
  leaf text, unsupported source/container, context mismatch, and provenance
  mismatch.
- Determinism tests for repeated runs and reordered inputs.
- Regression tests proving M68 base-type behavior, M70 vector-length behavior,
  and M71 vector-alignment behavior are unchanged.
- Regression tests proving no backend translation, rendering, generated
  output, golden-file churn, declaration/array lowering, raw helper evaluator
  calls, raw helper parsing, catalog reads, `tsldata` reads, host CPU queries,
  backend map reads, or runtime `frozen/` use is introduced.
- Pipeline-level M67 diagnostic propagation coverage if M72 touches the
  extracted array-initialization stage pipeline in a way that can exercise it.

Golden fixtures required:

- None. M72 is lowering-only helper-set completion and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M72 helper-set completion test command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating backend uninit as a backend translation or rendering problem under
  a lowering label.
- Hardwiring uninit behavior from request ordinal, helper text, backend id,
  selected type tag, extension name, renderer name, or backend map directly to
  emitted text or a fake backend-neutral initializer.
- Letting the aggregate IR become declaration/array IR for `var`, `array_type`,
  allocation/lifetime, initializer, store, return, `tmp.data()`, or
  `emit_return`.
- Creating a broad helper-set registry, generic backend-value evaluator,
  central stage dispatcher, or raw-helper parser instead of one exact typed
  continuation after M71.
- Expanding public exports beyond genuinely consumed typed boundary values.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, and 71.

Next concrete prompt:

- `docs/agent/runs/post-m72-planning-plus-review-prompt.md` is created for the
  next lowering-focused planning pass. Do not start Milestone 73 until a
  post-M72 plan is accepted.

### Post-M72 Planning Result

Status:

Milestone 73 was selected by post-M72 planning and is now implemented as the
exact first-slot declaration-shell structural IR slice.

Implemented milestone:

```text
Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Exact first-slot declaration-shell structural IR | High. Consumes the completed M72 helper-set aggregate and makes the exact `array.tsl:105` first slot structurally usable as typed lowering state. | Medium-high if it is mistaken for broad declaration/array semantics. | Implemented as M73 with strict wording that the output is structural IR only. |
| Narrow helper-set-to-envelope handoff | Low. Mostly rewraps M72 without exposing the first-slot statement structure. | Low, but too little functional movement. | Defer. |
| Backend-uninit handling | Medium later. Eventually needed for output, but M72 intentionally keeps it deferred. | High now because translation/rendering would cross the lowering boundary. | Defer until backend translation/rendering slices are selected. |
| Generic `var` / `array_type` parsing | Broadly useful later. | Too broad now; would add generic declaration/array semantics and broad TSIL parsing. | Reject for M73. |
| Store/return/`tmp.data()`/`emit_return` lowering | High later. | Too early; pulls in allocation/lifetime, store, return, and SVE semantics. | Defer. |
| Private resolver cleanup | Useful maintainability work. | Lower value than a structural IR step unless driven by implementation pressure. | Keep as non-blocking follow-up. |

### Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice

Status:

Implemented as the exact first-slot declaration-shell structural IR slice.

Goal:

Consume the accepted M72 `ExactArrayInitializationHelperSetCompletionIr` for
the exact first array-initialization slot and produce one typed structural
declaration-shell IR for the exact `array.tsl:105` shape:

```text
var<typed>(
  array_type<base type, vector length, vector alignment>,
  tmp,
  deferred backend uninit
)
```

M73 is generation-time lowering structural IR only. It turns the completed
helper facts into typed first-slot statement structure, but it must not define
generic declaration semantics, generic array semantics, variable scope,
allocation/lifetime, initializer behavior, backend uninit translation,
renderer-ready IR, or generated output.

Scope:

- Consume only accepted M72 `ExactArrayInitializationHelperSetCompletionIr`
  values, the `array_initialization_helper_set_completion` stage output, or a
  typed `LoweredImplementation` carrying exactly one accepted M72 helper-set
  completion.
- Produce one typed IR such as
  `ExactArrayInitializationDeclarationShellIr`, carrying:
  - the source M72 helper-set completion;
  - the source M66 slot-form / M65 envelope provenance reachable through the
    accepted M72 chain;
  - the exact structural declaration kind `var<typed>`;
  - the exact structural array-type shape using the accepted M68 base type,
    accepted M70 vector length, and accepted M71 vector alignment facts;
  - variable token `tmp` as preserved M66/M67/M72 provenance;
  - the accepted M72 deferred backend-uninit boundary/policy;
  - deterministic provenance including candidate id, target/source extension,
    selected type tag, branch-chain id, envelope/slot identity, variable
    token, and source locations.
- Append one deterministic stage after
  `array_initialization_helper_set_completion`, for example
  `array_initialization_declaration_shell_lowering`.
- Preserve accepted M66/M67/M68/M69/M70/M71/M72 behavior and outputs.
- Use source text only as provenance/invariant evidence. M73 must consume the
  typed M72 helper-set facts rather than reparsing M66 slot text or M67 leaf
  text as semantics.

Out of scope:

- Translating, resolving, or rendering `value<backend>(uninit::array)` to C++,
  Rust, backend text, initializer syntax, `{}`, `MaybeUninit`, backend
  translation requests, renderer-ready values, or generated output.
- Backend manifests, backend maps, language maps, translation maps, renderer
  calls, generated artifacts, golden files, CLI/report/writer behavior, Rust
  behavior, compiler execution, or generated-test execution.
- Generic `var`, generic `array_type`, generic declaration semantics, generic
  array semantics, array allocation/lifetime, variable binding/scope,
  initializer semantics, store, return, `tmp.data()`, `emit_return`,
  `assume_aligned`, aligned-store semantics, direct-intrinsic/SVE semantics,
  loops, calls, casts, multi-statement lowering, or broad TSIL parsing.
- Broad helper registries, raw helper-string dispatch, broad stage registries,
  lowering-time file/catalog reads, raw TSL parsing, `tsldata` reads during
  lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.

Required input:

- Accepted M72 helper-set completion IR for the exact first-slot helper family.
- Accepted M66 slot-form and M65 envelope provenance reachable through the M72
  source chain.
- Accepted M68 base-type request-resolution output.
- Accepted M70 vector-length request-resolution output.
- Accepted M71 vector-alignment request-resolution output.
- Accepted M72 deferred backend-uninit boundary/policy.

Expected outputs:

- One typed exact first-slot declaration-shell structural IR value.
- One deterministic generation-lowering stage after
  `array_initialization_helper_set_completion`.
- Structured diagnostics for unsupported source/container shapes,
  missing/duplicate M72 completions, context mismatch, provenance mismatch,
  malformed or unsupported exact shell invariants, and backend-uninit policy
  mismatch.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, or compiler behavior change.

Parity criterion:

M73 proves the accepted M66-M72 exact first-slot helper facts can become a
single typed structural declaration-shell handoff while keeping backend uninit
deferred and preventing generic declaration/array, allocation, store, return,
and rendering semantics from leaking into lowering.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105` for the exact selected
  `var<typed>(array_type<...>, tmp, value<backend>(uninit::array))` first-slot
  form.
- Same-text `array.tsl` repetitions at lines 37, 45, 54, 62, 71, 79, 88, and
  96 are supporting corpus repetition only, not expanded M73 scope.
- Structurally similar `construct.tsl` forms with different variable names are
  future evidence only; M73 remains anchored to the accepted M66 `tmp`
  first-slot path.
- Accepted M66/M67/M68/M70/M71/M72 IR and tests in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- `tsldata/detail/lang/translate_cpp.tsl` and
  `tsldata/detail/lang/translate_rust.tsl` backend array/uninit entries are
  evidence that output behavior exists later; M73 must not read or consume
  those maps.
- `frozen/` remains legacy evidence only and must not become runtime input.

Tests required:

- Direct resolver tests from M72 helper-set completion to the M73 structural
  declaration-shell IR.
- Normal `lower_candidates` pipeline tests proving the M73 stage appears after
  `array_initialization_helper_set_completion` and preserves M66-M72 ordering
  and outputs.
- Tests proving the structural shell consumes typed M72 facts and preserves
  the deferred backend-uninit policy without translating it.
- Diagnostics for missing, duplicate, unsupported source/container, context
  mismatch, provenance mismatch, malformed exact shell invariants, and
  backend-uninit policy mismatch.
- Determinism tests for repeated runs and reordered inputs.
- Regression tests proving M66/M67/M68/M70/M71/M72 behavior is unchanged.
- Regression tests proving no backend translation, rendering, generated
  output, golden-file churn, broad declaration/array lowering, generic
  `var`/`array_type` parsing, raw helper evaluator calls, raw helper parsing,
  catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M73 is lowering-only structural IR and must not change generated C++
  or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M73 declaration-shell structural IR test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting "declaration" become generic declaration semantics, variable scope,
  allocation/lifetime, initializer semantics, renderer-ready IR, or generated
  output.
- Reparsing M66 slot text or M67 helper leaf text as semantic input instead
  of consuming typed M72 helper-set facts.
- Treating backend uninit as backend translation/rendering under a structural
  lowering label.
- Expanding scope to non-`tmp` corpus forms, generic `var`/`array_type`, store
  or return slots, `tmp.data()`, `emit_return`, `assume_aligned`,
  direct-intrinsic/SVE semantics, loops, calls, casts, or broad TSIL parsing.
- Adding a broad `VarIr`, `ArrayTypeIr`, declaration registry, helper-set
  registry, central stage dispatcher, or public IR family instead of one exact
  typed boundary value.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, and
  72.

Next concrete prompt:

- `docs/agent/runs/post-m73-planning-plus-review-prompt.md` completed the
  post-M73 lowering-focused planning pass. The
  `docs/agent/runs/post-m73-acceptance-finalization-prompt.md` prompt recorded
  human acceptance and created the M74 execution-review loop prompt.

### Post-M73 Planning Result

Status:

Accepted after post-M73 planning and implemented by the M74 execution-review
loop.

Selected milestone:

```text
Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Exact array-body structural sequence and slot-role classification | High. Rejoins the accepted M64/M65 exact body envelope with the accepted M73 declaration-shell IR, giving future lowering slices one source-ordered typed body structure instead of isolated slot fragments. | Medium-high if role names become store/return/predicate/body semantics. | Select as M74 with strict wording that roles are structural/provenance labels only. |
| Narrow M73-to-envelope handoff | Medium. Links M73 back to the envelope but mostly rewraps existing facts without making all body roles explicit. | Low, but less forward movement than a five-role structural sequence. | Defer. |
| Predicate-init slot lowering | Useful later for SVE body parity. | High now because it pulls in `svbool_t`, `pg`, `svptrue_b8`, direct-intrinsic, and SVE predicate semantics. | Defer. |
| Store-call or return-emission lowering | High later. | Too early; would interpret `tmp.data()`, `svst1`, `emit_return`, store/return semantics, variable scope, and backend/rendering pressure. | Defer. |
| Private resolver/stage-table cleanup | Useful maintainability work. | Lower value than making the exact body sequence explicit, unless implementation pressure forces it. | Keep as non-blocking follow-up. |

### Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice

Status:

Accepted after the M74 execution-review loop.

Goal:

Consume accepted M64/M65 exact array-body envelope state and the accepted M73
first-slot declaration-shell IR, then produce one typed source-ordered
structural sequence for the exact `array.tsl:105-111` body:

```text
slot 0: first-slot declaration shell from M73
slot 1: opaque predicate-init-shaped structural role
slot 2: selected-body envelope structural role
slot 3: opaque post-branch store-call-shaped structural role
slot 4: opaque return-emission-shaped structural role
```

M74 is structural/provenance lowering only. Slot-role classification names the
accepted exact body positions; it must not define executable statement kinds,
generic body IR, declaration/array semantics, variable scope,
allocation/lifetime, initializer behavior, predicate semantics, store/return
semantics, direct-intrinsic/SVE semantics, backend translation, renderer-ready
IR, or generated output.

Scope:

- Consume accepted typed M64/M65 `ExactArrayBodyEnvelopeIr` values, the
  `array_body_envelope_slot_assembly` stage output, accepted typed M73
  `ExactArrayInitializationDeclarationShellIr` values, the
  `array_initialization_declaration_shell_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one matching M64/M65 envelope and
  one matching M73 declaration shell.
- Produce one typed IR such as `ExactArrayBodyStructuralSequenceIr`, carrying:
  - the source M64/M65 exact array-body envelope;
  - the accepted M73 declaration-shell IR attached only to slot ordinal `0`;
  - the accepted M63 selected/no-body envelope through the M64 selected-body
    envelope slot;
  - one source-ordered five-entry structural/provenance role sequence;
  - role labels for declaration-shell, opaque predicate-init-shaped slot,
    selected-body envelope slot, opaque post-branch store-call-shaped slot,
    and opaque return-emission-shaped slot;
  - opaque source/provenance for the non-first slots without interpreting
    their text;
  - deterministic provenance including candidate id, selected type tag,
    target/source extension where available, branch-chain id, envelope/slot
    identity, role ordinal, and source locations.
- Append one deterministic stage after
  `array_initialization_declaration_shell_lowering`, for example
  `array_body_structural_sequence_classification`.
- Preserve accepted M63/M64/M65/M66/M67/M68/M69/M70/M71/M72/M73 behavior and
  outputs.
- Use source text only as provenance/invariant evidence. M74 must derive roles
  from accepted typed envelope slot identity and provenance, not from raw body
  text, corpus line numbers, SVE tokens, backend ids, or helper strings.

Out of scope:

- Interpreting `svbool_t`, `pg`, `intrin<svptrue_b8>`, selected
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `a`,
  `emit_return(tmp)`, `assume_aligned`, stores, returns, direct intrinsics,
  SVE predicate/vector/register semantics, byte-size-to-token inference, or
  branch-body semantics beyond accepted M57-M63.
- Generic body IR, broad TSIL parsing, generic declaration semantics, generic
  array semantics, generic variable semantics, allocation/lifetime, variable
  binding/scope, initializer semantics, statement execution order semantics,
  store semantics, return semantics, or multi-statement lowering.
- Backend manifests, backend maps, language maps, translation maps, backend
  uninit translation, backend translation requests, renderer-ready values,
  renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- Broad helper registries, raw helper-string dispatch, broad body/slot
  registries, lowering-time file/catalog reads, raw TSL parsing, `tsldata`
  reads during lowering evaluation, host CPU queries, backend map reads, or
  runtime dependency on `frozen/`.

Required input:

- Accepted M64/M65 exact array-body envelope state for the selected body.
- Accepted M73 exact first-slot declaration-shell structural IR.
- Accepted M63 selected/no-body envelope reachable through the M64/M65
  selected-body slot.
- Accepted M66-M72 first-slot provenance reachable through the M73 source
  chain.

Expected outputs:

- One typed exact array-body structural sequence IR value.
- One deterministic generation-lowering stage after
  `array_initialization_declaration_shell_lowering`.
- Structured diagnostics for unsupported source/container shapes, missing or
  duplicate envelope/declaration-shell values, context mismatch, provenance
  mismatch, role/order mismatch, malformed exact five-slot sequence
  invariants, and unsupported non-exact body shapes.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, compiler, generic body/declaration/
  array semantics, store, return, `tmp.data()`, `emit_return`, or SVE/direct-
  intrinsic behavior change.

Parity criterion:

M74 proves the accepted `array.tsl:105-111` body can be carried as one typed,
source-ordered structural/provenance sequence around the accepted M73
declaration-shell IR and accepted M63/M64 selected-body envelope without
implementing body-slot semantics, backend translation, rendering, generated
output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105` for the exact first-slot
  declaration shell already refined by M73.
- `tsldata/primitives/load_store/array.tsl:106` for the exact predicate-init
  shaped slot as opaque structural evidence only.
- `tsldata/primitives/load_store/array.tsl:107-109` for the accepted selected
  branch-chain body evidence already covered through M57-M63.
- `tsldata/primitives/load_store/array.tsl:110` for the exact post-branch
  store-call shaped slot as opaque structural evidence only.
- `tsldata/primitives/load_store/array.tsl:111` for the exact return-emission
  shaped slot as opaque structural evidence only.
- Accepted M63 selected-body envelope, M64 exact array-body envelope slot
  assembly, M65 pipeline integration, and M66-M73 first-slot chain in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- Same-text `array.tsl` repetitions are supporting corpus repetition only,
  not expanded M74 scope.
- `construct.tsl`, backend translation maps, and `frozen/` remain future
  evidence only and must not become runtime input.

Tests required:

- Direct resolver tests from accepted M64/M65 envelope plus accepted M73
  declaration shell to the M74 structural sequence IR.
- Normal `lower_candidates` pipeline tests proving the M74 stage appears after
  `array_initialization_declaration_shell_lowering` and preserves M63-M73
  ordering and outputs.
- Tests proving exact five-entry role order, M73 shell linkage only to slot
  `0`, M63 selected/no-body envelope linkage only to the selected-body slot,
  and opaque preservation of predicate-init, store-call, and return-emission
  slot text/provenance without interpreting it.
- Diagnostics for missing, duplicate, unsupported source/container, context
  mismatch, provenance mismatch, role/order mismatch, and malformed exact
  sequence invariants.
- Determinism tests for repeated runs and reordered inputs.
- Regression tests proving M63/M64/M65/M66/M67/M68/M70/M71/M72/M73 behavior is
  unchanged.
- Regression tests proving no backend translation, rendering, generated
  output, golden-file churn, broad body/declaration/array lowering, generic
  parser, raw helper evaluator calls, raw helper parsing, catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`
  use is introduced.

Golden fixtures required:

- None. M74 is lowering-only structural IR and must not change generated C++
  or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M74 structural sequence / slot-role test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting role labels become executable statement kinds or generic body IR.
- Inferring roles from raw text, SVE tokens, backend ids, corpus line numbers,
  or helper strings instead of accepted typed slot identity and provenance.
- Treating the store-call-shaped or return-emission-shaped roles as store or
  return lowering.
- Treating the predicate-init-shaped role or selected-body role as SVE/direct-
  intrinsic semantics.
- Reconnecting M73 to the envelope in a way that implies variable scope,
  allocation/lifetime, initializer semantics, or backend-uninit translation.
- Adding broad `BodyIr`, slot-role registries, central semantic dispatchers,
  backend shortcuts, rendering, generated output, or raw TSIL parsing.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
  and 73.

Next concrete prompt:

- `docs/agent/runs/m74-execution-review-loop-prompt.md` completed the M74
  implementation and review loop. Post-M74 planning was accepted, M75
  execution is accepted, and the active concrete prompt is
  `docs/agent/runs/post-m75-planning-plus-review-prompt.md`.

### Post-M74 Planning Result

Status:

Accepted for execution after post-M74 planning and human acceptance.

Selected milestone:

```text
Milestone 75: Exact Predicate Path Structural Request IR Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Exact predicate path structural request IR | High. Broadens beyond only slot 1 by connecting the accepted M74 predicate-init slot, accepted selected-body predicate update evidence, and post-branch store-call predicate-token use into one typed path needed before any store lowering. | Medium-high if it starts interpreting SVE predicate semantics, `svptrue_b*`, `svst1`, or variable scope. | Select as M75 with strict structural/request-only wording. |
| Predicate-init slot only | Medium. Refines the next opaque slot but leaves the selected update and store-call predicate token disconnected. | Lower risk, but less forward movement after M74 made the whole sequence available. | Defer in favor of the broader exact predicate path. |
| Store-call slot lowering | High later. | Too broad now because it would pull in `tmp.data()`, `a`, store semantics, backend maps, alignment behavior, renderer pressure, and generated output. | Defer. |
| Return-emission slot lowering | High later. | Too broad now because it pulls in return semantics, `emit_return`, variable lifetime, renderer pressure, and output behavior. | Defer. |
| Private resolver/stage-table cleanup | Useful maintainability work. | Lower forward movement than consuming M74 for the next semantic-bearing path. | Keep as non-blocking follow-up. |

### Milestone 75: Exact Predicate Path Structural Request IR Slice

Status:

Accepted after M75 execution-review loop.

Goal:

Consume accepted M74 exact array-body structural sequence state and produce one
typed predicate-path structural/request IR for the exact `array.tsl:106-110`
predicate path:

```text
slot 1: svbool_t pg = intrin<svptrue_b8>();
slot 2: accepted selected-body assignment envelope for pg = intrin<svptrue_b*>();
slot 3: intrin<svst1>(pg, tmp.data(), a);
```

M75 connects the exact predicate initialization, accepted selected
predicate update evidence, and post-branch predicate-token use as typed
lowering state only. It must not define SVE predicate semantics, variable
scope, store semantics, backend translation, renderer-ready IR, or generated
output.

Scope:

- Consume accepted typed M74 `ExactArrayBodyStructuralSequenceIr` values, the
  `array_body_structural_sequence_classification` stage output, or a typed
  `LoweredImplementation` carrying exactly one M74 structural sequence.
- Consume the accepted M63/M64 selected/no-body envelope reachable through the
  M74 selected-body role and the accepted M61/M62 selected assignment/direct-
  intrinsic body IR when present.
- Produce one typed IR such as `ExactPredicatePathStructuralRequestIr`,
  carrying:
  - the source M74 structural sequence;
  - slot ordinal `1` as the exact predicate-init-shaped structural request
    source;
  - structural tokens `svbool_t`, `pg`, and unresolved direct-intrinsic request
    token `svptrue_b8` from the exact predicate-init shape;
  - the accepted selected-body predicate update request from the M63 selected
    body envelope when a selected body exists, preserving the already accepted
    unresolved token such as `svptrue_b16`, `svptrue_b32`, or `svptrue_b64`;
  - an explicit no-update state for accepted `NoSelectedBodyEnvelopeIr` cases;
  - slot ordinal `3` as the exact post-branch store-call-shaped structural
    source, recording only that the predicate argument token is the same `pg`;
  - deterministic provenance including candidate id, target/source extension
    where available, selected type tag, branch-chain id, M74 role identity,
    envelope/slot identity, and source locations.
- Append one deterministic stage after
  `array_body_structural_sequence_classification`, for example
  `predicate_path_structural_request_lowering`.
- Preserve accepted M57-M74 behavior and outputs.
- Use source text only as exact structural shape/provenance evidence. M75 must
  derive path membership from accepted M74 role identity and accepted M63/M62
  selected-body state, not from raw corpus line numbers, SVE token semantics,
  backend ids, renderer names, catalog data, or helper-string dispatch.

Out of scope:

- Interpreting `svbool_t`, `pg`, `intrin<svptrue_b8>`, selected
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `a`, `emit_return`,
  `assume_aligned`, stores, returns, direct intrinsics, SVE predicate/vector/
  register semantics, byte-size-to-token inference, lane masks, backend uninit,
  backend maps, rendering, generated output, generic body/declaration/array
  semantics, allocation/lifetime, initializer behavior, variable scope, broad
  TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, or runtime `frozen/` use.
- Generic predicate IR, broad variable/use-def analysis, generic call
  semantics, generic store-call IR, generic direct-intrinsic semantics,
  backend translation requests, renderer-ready values, generated artifacts,
  golden files, CLI/report/writer behavior, Rust behavior, compiler
  execution, or generated-test execution.
- Broad helper registries, raw helper-string dispatch, broad slot-role
  registries, broad stage registries, central semantic dispatchers, or public
  IR families beyond one exact predicate-path structural/request boundary.

Required input:

- Accepted M74 exact array-body structural sequence.
- Accepted M64/M65 exact array-body envelope and M63 selected/no-body envelope
  reachable through M74.
- Accepted M61/M62 selected assignment/direct-intrinsic body IR when present.
- Exact M74 predicate-init-shaped slot and post-branch store-call-shaped slot
  provenance.

Expected outputs:

- One typed exact predicate-path structural/request IR value.
- One deterministic generation-lowering stage after
  `array_body_structural_sequence_classification`.
- Structured diagnostics for unsupported source/container shapes, missing or
  duplicate M74 values, context mismatch, provenance mismatch, malformed exact
  predicate-init shape, malformed exact store-call predicate-token shape,
  selected-body target-token mismatch, selected-body provenance mismatch, and
  unsupported non-exact predicate-path shapes.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, compiler, generic predicate/store/
  return semantics, `tmp.data()`, `emit_return`, SVE semantics, or direct-
  intrinsic behavior change.

Parity criterion:

M75 proves the accepted `array.tsl:106-110` predicate path can be carried as
typed structural/request lowering state around the accepted M74 sequence and
accepted M63/M62 selected-body evidence, without implementing SVE predicate
semantics, store semantics, backend translation, rendering, generated output,
or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:106` for the exact predicate-init
  shaped slot as structural/request evidence only.
- `tsldata/primitives/load_store/array.tsl:107-109` for the accepted selected
  branch-chain predicate update evidence already covered through M57-M63.
- `tsldata/primitives/load_store/array.tsl:110` for the exact post-branch
  store-call-shaped predicate-token use as structural evidence only.
- Accepted M74 exact structural sequence in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- Same-text `array.tsl` repetitions are supporting corpus repetition only,
  not expanded M75 scope.
- Backend translation maps, `construct.tsl`, generated outputs, and `frozen/`
  remain future evidence only and must not become runtime input.

Tests required:

- Direct resolver tests from accepted M74 structural sequence to the M75
  predicate-path structural/request IR.
- Normal `lower_candidates` pipeline tests proving the M75 stage appears after
  `array_body_structural_sequence_classification` and preserves M57-M74
  ordering and outputs.
- Tests proving slot-1 predicate init, slot-2 accepted selected/no-body
  predicate update, and slot-3 predicate-token use all reference the same
  structural `pg` token without variable-scope or store semantics.
- Tests proving selected-body update request preservation for selected
  `svptrue_b16/b32/b64` tokens and explicit no-update preservation for
  `NoSelectedBodyEnvelopeIr` cases.
- Diagnostics for missing, duplicate, unsupported source/container, context
  mismatch, provenance mismatch, malformed predicate-init shape, malformed
  store-call predicate-token shape, selected-body target-token mismatch, and
  unsupported non-exact predicate-path shape.
- Determinism tests for repeated runs and reordered inputs.
- Regression tests proving M57-M74 behavior is unchanged.
- Regression tests proving no backend translation, rendering, generated
  output, golden-file churn, broad body/declaration/array/predicate/store
  lowering, generic parser, raw helper evaluator calls, raw helper parsing,
  catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M75 is lowering-only structural/request IR and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M75 predicate-path structural/request test command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Letting `svptrue_b8`, `svptrue_b16`, `svptrue_b32`, or `svptrue_b64` become
  SVE predicate semantics instead of unresolved direct-intrinsic request
  tokens.
- Inferring byte-size-to-token relationships beyond accepted M57-M63 branch
  selection evidence.
- Treating slot 3 as store lowering or interpreting `svst1`, `tmp.data()`,
  `a`, alignment, or memory behavior.
- Introducing variable scope, lifetime, store semantics, return semantics,
  backend maps, renderer-ready IR, generated output, or raw helper dispatch.
- Growing the M74 private role detail into a slot-role registry, generic body
  IR, broad stage registry, or central semantic dispatcher.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
  73, and 74.

Next concrete prompt:

- `docs/agent/runs/m75-execution-review-loop-prompt.md` ran after explicit
  human acceptance. The M75 execution-review loop returned
  `Accept With Follow-Ups` after one focused validation-coverage revision.
  The next concrete prompt is
  `docs/agent/runs/post-m75-planning-plus-review-prompt.md`. Do not start M76
  until post-M75 planning is accepted.

### Post-M75 Planning Result

Status:

Accepted for execution after post-M75 planning and human acceptance.

Selected milestone:

```text
Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Exact post-branch intrinsic call-site structural request IR | High. Consumes accepted M75 predicate-path state and records the exact post-branch call-shaped slot as typed lowering state, moving the array-body pipeline forward without assigning store, SVE, or backend meaning. | Medium if the plan treats `svst1`, `tmp.data()`, or `a` as semantic store/memory facts instead of structural tokens and provenance. | Select as M76 with strict structural/request-only wording and no hardwired ARM/store semantics. |
| Store-call semantic lowering | High later. | Too broad now because it would combine call semantics, memory behavior, alignment, `tmp.data()`, source operand semantics, backend intrinsic behavior, renderer pressure, and generated output. | Defer. |
| Return-emission structural/request IR | High later. | Lower immediate value for the M75 predicate-path handoff and risks pulling in return semantics and renderer-ready body shape too early. | Defer. |
| Backend-uninit deferred-value refinement | Useful for the first-slot helper set. | Lower forward movement for the post-branch body path, and backend uninit still belongs at a backend-value boundary rather than this call-site slice. | Defer. |
| Private resolver/stage-table cleanup | Useful maintainability work. | Does not advance the typed lowering frontier as much as consuming M75 into the next exact post-branch structural value. | Keep as non-blocking follow-up unless a focused cleanup is required by M76. |

### Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice

Status:

Accepted after M76 execution-review loop.

Goal:

Consume accepted M75 exact predicate-path structural/request IR and produce one
typed structural/request IR value for the exact post-branch call-site shape at
`array.tsl:110`:

```text
intrin<svst1>(pg, tmp.data(), a);
```

M76 records only that the accepted post-branch slot is an exact
`intrin<...>(...)` call-shaped site with structural argument tokens and
provenance. It must not define store semantics, ARM/SVE intrinsic semantics,
memory behavior, `tmp.data()` semantics, operand semantics, backend
translation, renderer-ready IR, or generated output.

Scope:

- Consume accepted typed M75 `ExactPredicatePathStructuralRequestIr` values,
  the `predicate_path_structural_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M75 value.
- Consume accepted M74 exact array-body structural sequence state and accepted
  M73 declaration-shell state only through the accepted M75/M74 provenance
  chain; do not reparse raw body text as semantics.
- Produce one typed IR value such as
  `ExactPostBranchIntrinsicCallSiteStructuralRequestIr`, carrying:
  - the source M75 predicate-path value;
  - the source M74 structural sequence identity and exact post-branch slot
    identity for slot ordinal `3`;
  - the structural call-head token `intrin`;
  - the unresolved intrinsic token `svst1` as source evidence only;
  - argument ordinal `0` as structural token `pg`, linked to the accepted M75
    slot-3 predicate-token use;
  - argument ordinal `1` as exact member-access-shaped structural token/path
    `tmp.data()`, linked only to accepted structural provenance for `tmp`
    where that provenance is already carried through M73/M74/M75;
  - argument ordinal `2` as structural source operand token `a`;
  - deterministic provenance including candidate id, target/source extension
    where available, selected type tag, branch-chain id, M74/M75 identity, and
    source locations.
- Append one deterministic generation-lowering stage after
  `predicate_path_structural_request_lowering`, for example
  `post_branch_intrinsic_call_site_structural_request_lowering`.
- Preserve accepted M57-M75 behavior and outputs, including selected-branch
  diagnostics from the earlier branch-pruning/lowering slices.
- Use source text only as exact shape/provenance evidence. M76 may enforce the
  selected exact corpus shape as an invariant for this slice, but it must not
  dispatch semantic behavior from raw helper text, SVE token text, backend ids,
  renderer names, catalog data, corpus line numbers, or request ordinals.
- Keep public IR additions narrow: at most one exact public call-site
  structural/request IR value and one exact stage/output pairing.

Out of scope:

- Store semantics, memory writes, alignment behavior, pointer semantics,
  operand semantics, variable scope/use-def/lifetime, declaration/array
  semantics, initializer behavior, return semantics, `emit_return`, or
  `assume_aligned`.
- Interpreting `svst1`, `pg`, `tmp.data()`, `a`, `svbool_t`, `svptrue_b*`, or
  any ARM/SVE predicate/vector/register/intrinsic behavior.
- Generic call IR, broad direct-intrinsic semantics, generic store-call IR,
  generic body IR, broad slot-role registries, broad helper registries, broad
  stage registries, central semantic dispatchers, or raw helper-string
  dispatch.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready values, generated artifacts, golden
  files, generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, broad TSIL parsing, lowering-time
  file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
  queries, backend map reads, or runtime dependency on `frozen/`.

Required input:

- Accepted M75 exact predicate-path structural/request IR.
- Accepted M74 exact array-body structural sequence reachable through M75.
- Accepted M73 first-slot declaration-shell structural IR reachable through
  M74/M75 when `tmp` provenance is already available.
- Exact `array.tsl:110` post-branch call-site source evidence as provenance
  only.

Expected outputs:

- One typed exact post-branch intrinsic call-site structural/request IR value.
- One deterministic generation-lowering stage after
  `predicate_path_structural_request_lowering`.
- Structured diagnostics for unsupported source/container shapes, missing or
  duplicate M75 values, context mismatch, provenance mismatch, missing M74
  sequence provenance, malformed exact post-branch call shape, call-head token
  mismatch, unresolved intrinsic-token mismatch, argument-count mismatch,
  predicate-argument mismatch against M75, unsupported `tmp.data()` structural
  shape, unsupported source-operand token shape, and unsupported non-exact
  call-site shapes.
- No backend translation request, renderer-ready value, generated artifact,
  golden output, CLI/report/writer, Rust, compiler, generic call/store/body
  semantics, ARM/SVE intrinsic behavior, memory behavior, or `tmp.data()`
  semantic behavior change.

Parity criterion:

M76 proves the accepted `array.tsl:110` post-branch `intrin<svst1>(pg,
tmp.data(), a);` call site can be carried as typed structural/request lowering
state after accepted M75 predicate-path lowering, without implementing
store semantics, ARM/SVE semantics, backend translation, rendering, generated
output, or compiler parity.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:110` for the exact post-branch
  call-site shape as structural/request evidence only.
- Accepted M75 exact predicate-path structural/request IR in
  `tslgen/src/tslgen/lowering/boundary.py` and
  `tslgen/tests/unit/test_lowering_boundary.py`.
- Accepted M74 exact structural sequence and accepted M73 declaration-shell
  provenance in the same implementation/test files.
- Same-text `array.tsl` repetitions are supporting corpus repetition only,
  not expanded M76 scope.
- Backend translation maps, generated outputs, and `frozen/` remain future
  evidence only and must not become runtime input.

Tests required:

- Direct resolver tests from accepted M75 predicate-path state to the M76
  exact post-branch intrinsic call-site structural/request IR.
- Normal `lower_candidates` pipeline tests proving the M76 stage appears after
  `predicate_path_structural_request_lowering` and preserves M57-M75 stage
  ordering and outputs.
- Tests proving argument `0` `pg` links to the accepted M75 slot-3 predicate
  token without predicate, SVE, or store semantics.
- Tests proving `svst1`, `tmp.data()`, and `a` are recorded only as structural
  tokens/provenance, with no ARM/SVE, memory, pointer, operand, variable-scope,
  or backend meaning.
- Diagnostics for missing, duplicate, unsupported source/container, context
  mismatch, provenance mismatch, malformed exact call shape, call-head token
  mismatch, unresolved intrinsic-token mismatch, argument-count mismatch,
  predicate-argument mismatch, unsupported `tmp.data()` structural shape,
  unsupported source-operand token shape, and unsupported non-exact call-site
  shape.
- Determinism tests for repeated runs and reordered inputs.
- Regression tests proving M57-M75 behavior is unchanged, including
  selected-branch-only diagnostics.
- Regression tests proving no backend translation, rendering, generated
  output, golden-file churn, broad body/declaration/array/call/store
  lowering, generic parser, raw helper evaluator calls, raw helper parsing,
  catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M76 is lowering-only structural/request IR and must not change
  generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M76 exact post-branch intrinsic call-site structural/request test
  command selected by the executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating `intrin<svst1>(...)` as store lowering, ARM/SVE intrinsic
  semantics, memory behavior, or backend translation.
- Letting `tmp.data()` become pointer, member-access, variable-lifetime, or
  renderer-ready semantics rather than structural provenance.
- Treating `a` as an evaluated operand instead of an exact source token.
- Dispatching semantic behavior from raw helper text, intrinsic token text,
  backend ids, renderer names, corpus line numbers, request ordinals, or
  catalog data.
- Growing the exact call-site value into generic call IR, generic store IR,
  broad body IR, broad slot-role registries, broad helper registries, broad
  stage registries, or central semantic dispatchers.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
  73, 74, and 75.

Next concrete prompt:

- `docs/agent/runs/post-m75-acceptance-finalization-prompt.md` ran after
  explicit human acceptance. The M76 execution-review loop returned
  `Accept With Follow-Ups` after one focused documentation revision. The next
  concrete prompt is
  `docs/agent/runs/post-m76-planning-plus-review-prompt.md`. Do not start M77
  until post-M76 planning is accepted.

### Post-M76 Planning Result

Status:

Selected for human acceptance after post-M76 planning. Do not start M77
execution until the post-M76 acceptance finalization prompt has run.

Selected milestone:

```text
Milestone 77: Composable Lowering Pipeline Module Boundary Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Composable lowering pipeline module boundary | High. Addresses the concrete M58-M76 maintainability pressure in `tslgen/src/tslgen/lowering/boundary.py` while preserving accepted lowering behavior and making future lowering/backfeed stages explicit and typed. | Medium if treated as a broad rewrite, generic registry, semantic dispatcher, or behavior change. | Select as M77 with strict behavior-preserving, private-boundary wording. |
| Exact return-emission structural/request IR | High later. | It would continue the exact array-body frontier, but the current 12k-line lowering boundary and growing stage table make the next semantic slice harder to review safely. | Defer until the pipeline/module boundary is easier to extend. |
| Whole-file lowering rewrite/split | Potentially high. | Too broad for one milestone and likely to mix mechanical movement, behavior changes, and new abstractions. | Reject for M77; use one coherent extraction slice instead. |
| Generic lowering pipeline framework with backfeed execution | Useful later. | Too speculative before one behavior-preserving module-boundary slice proves the shape. | Defer. M77 may define private typed contracts for future backfeeds, but must not implement broad fixpoint semantics. |
| Generic call/body/parser cleanup | Tempting because M76 exposed call-shaped evidence. | Violates the exact-slice boundary and risks raw-helper parsing or broad body semantics. | Reject for M77. |

### Milestone 77: Composable Lowering Pipeline Module Boundary Slice

Status:

Accepted after the M77 execution-review loop returned `Accept With Follow-Ups`
following one focused documentation revision. It remains behavior-preserving
lowering architecture work and does not add new lowering semantics.

Goal:

Make Stage 8 lowering more maintainable and extensible by introducing a
behavior-preserving, private composable pipeline/module boundary under
`tslgen/src/tslgen/lowering/`. M77 starts breaking the large lowering boundary
apart around accepted M58-M76 stage contracts without adding new lowering
semantics, backend behavior, rendering, generated output, or broad parsing.

M77 must model lowering as a staged typed pipeline. Future backfeeds should be
represented as typed facts, typed requests, or deterministic coordinator
decisions rather than as hidden recursion, direct stage-to-stage callbacks, raw
helper dispatch, or central semantic `if`/`elif` chains.

Scope:

- Keep the public lowering API stable through `tslgen.lowering` and any
  existing `boundary.py` facade imports used by tests or downstream code.
- Introduce private typed pipeline/module contracts only where needed for the
  accepted M58-M76 pattern. Acceptable private names include concepts such as
  stage input, stage output, artifact/fact store, stage dependency, or deferred
  request, provided they are typed values and not a broad runtime plugin
  system.
- Move one coherent cluster of Stage 8 lowering implementation out of the
  monolithic `boundary.py` into one or more modules under
  `tslgen/src/tslgen/lowering/`, chosen to minimize behavior risk. The
  preferred cluster is the accepted exact array-body / array-initialization
  stage assembly and exact structural/request helpers that are already a
  private lowering pipeline pressure point after M69-M76.
- Preserve all accepted M57-M76 stage names, outputs, diagnostics,
  deterministic ordering, and public typed boundary values.
- Keep exact-shape recognizer constants slice-local. Tokens such as `pg`,
  `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `intrin`, `svst1`,
  `tmp.data()`, and `a` may remain exact structural evidence for accepted
  slices, but they must not become extension semantics, SVE semantics, store
  semantics, or backend dispatch keys.
- Reduce or isolate the growing `GenerationLoweringStage.__post_init__`
  validation-table pressure only if it can be done by preserving typed
  stage-specific attachment points. M77 must not replace it with an untyped
  registry, raw dispatcher, or semantic lookup keyed by strings.
- Document the private pipeline boundary and future backfeed rule in the
  redesign docs so later lowering milestones can extend it without guessing.

Out of scope:

- New lowering semantics or new generated behavior.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics, initializer
  behavior, `tmp.data()` semantics, `emit_return`, `assume_aligned`, ARM/SVE
  predicate/vector/register/intrinsic semantics, or byte-size-to-token
  inference.
- Generic call IR, generic store IR, generic return IR, broad body IR, broad
  slot-role registries, broad helper registries, broad stage registries,
  central semantic dispatchers, runtime plugin systems, raw helper-string
  dispatch, raw TSIL expression evaluation, or broad TSIL parsing.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- A whole-file rewrite of `boundary.py` or a migration map organized around
  legacy modules.

Required input:

- Accepted M58 typed `GenerationLoweringStage` contract and accepted M59-M76
  Stage 8 lowering behavior.
- The existing `tslgen/src/tslgen/lowering/boundary.py` implementation as the
  current module-boundary pressure point.
- Existing unit tests in `tslgen/tests/unit/test_lowering_boundary.py` as
  behavior-preservation evidence.
- Redesign docs that require typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch, deterministic diagnostics, and
  side-effect-free lowering.

Expected outputs:

- A stable public facade in `tslgen/src/tslgen/lowering/boundary.py` that
  preserves current callers.
- New private modules under `tslgen/src/tslgen/lowering/`:
  - `_pipeline.py`, carrying the exact array-body pipeline snapshot, typed
    facts, dependencies, and an empty typed backfeed-request boundary for the
    accepted M69-M76 stage tail;
  - `_exact_shapes.py`, carrying exact selected-body/post-branch recognizer
    shapes and tokens as slice-local structural evidence.
- No public behavior changes to accepted M57-M76 lowering.
- No new backend translation, rendering, generated output, CLI/report/writer,
  Rust, compiler, generated-test, file/catalog-read, `tsldata`-read,
  host-CPU-query, backend-map-read, or runtime `frozen/` behavior.
- Redesign documentation describing the composable lowering pipeline boundary,
  future typed backfeed rule, and exact-token evidence boundary.

Parity criterion:

M77 proves the accepted M57-M76 lowering behavior can be preserved while the
lowering implementation begins moving behind composable typed module/stage
boundaries. The milestone is successful when future exact lowering slices can
attach to a clearer private pipeline boundary without relying on a 12k-line
central file, raw helper dispatch, or hardwired extension semantics.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the current Stage 8 facade and
  M77 integration points.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for exact selected-body and
  post-branch recognizer shapes/tokens as slice-local structural evidence.
- `tslgen/src/tslgen/lowering/_pipeline.py` for the exact array-body pipeline
  snapshot, typed facts, dependencies, and empty typed backfeed boundary.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M57-M76 behavior
  and diagnostics.
- `docs/redesign/pipeline-design.md`,
  `docs/redesign/generation-time-semantic-lowering.md`,
  `docs/redesign/target-architecture.md`, and
  `docs/redesign/design-decisions.md` for typed Stage 8 boundaries and
  no-hardwiring rules.
- `tsldata/primitives/load_store/array.tsl` remains source-shape evidence
  only. It must not become runtime input to lowering evaluation.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M77 tests proving `_pipeline.py` records the exact M69-M76 stage
  facts/dependencies without pending backfeeds and `_exact_shapes.py` keeps the
  exact recognizer tokens slice-local as structural evidence.
- Import/API stability tests or existing public import tests proving
  `tslgen.lowering` exports remain stable.
- Diagnostics preservation for representative M57-M76 failures across the
  extracted boundary, including exact code, severity, deterministic ordering,
  and source location where already asserted.
- Determinism tests for repeated lowering runs and reordered inputs where the
  moved cluster participates.
- Regression tests proving no backend translation, rendering, generated
  output, broad body/call/store/return parsing, raw helper evaluator calls,
  raw helper dispatch, catalog reads, `tsldata` reads, host CPU queries,
  backend map reads, or runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M77 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M77 module-boundary/import-preservation command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating M77 as permission for a whole-file rewrite or broad OO redesign.
- Creating a generic stage registry, helper registry, call parser, body parser,
  central semantic dispatcher, runtime plugin system, or raw-helper evaluator.
- Moving exact tokens such as `pg`, `svptrue_b*`, `intrin`, `svst1`,
  `tmp.data()`, or `a` into global extension/backend semantics instead of
  keeping them slice-local structural evidence.
- Hiding file/catalog reads, `tsldata` reads, host CPU queries, backend map
  reads, renderer calls, generated-output writes, or runtime `frozen/` access
  inside the new modules.
- Changing accepted M57-M76 diagnostics, stage ordering, output identities, or
  public imports while moving code.
- Implementing backfeed/fixpoint execution before a later milestone consumes a
  concrete need.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
  73, 74, 75, and 76.

Next concrete prompt:

- `docs/agent/runs/post-m76-acceptance-finalization-prompt.md` ran after
  explicit human acceptance and created
  `docs/agent/runs/m77-execution-review-loop-prompt.md`. The M77
  execution-review loop returned `Accept With Follow-Ups` after one focused
  documentation revision. The next concrete prompt is
  `docs/agent/runs/post-m77-planning-plus-review-prompt.md`. Do not start M78
  until post-M77 planning is accepted.

### Post-M77 Planning Result

Status:

Selected for human acceptance after post-M77 planning. Do not start M78
execution until the post-M77 acceptance finalization prompt has run.

Selected milestone:

```text
Milestone 78: Lowering Boundary Package Decomposition Slice
```

Candidate comparison:

| Candidate | Value | Risk | Decision |
| --- | --- | --- | --- |
| Lowering boundary package decomposition | Highest. Directly addresses the M77 shortfall: `boundary.py` still contains the accepted exact array-body / array-initialization implementation and remains about 12.3k lines. | Medium-high if treated as a whole-file rewrite, broad OO redesign, generic registry, or behavior change. | Select as M78 with a single coherent extraction target, strict behavior preservation, and a measurable line-count reduction. |
| Narrow exact array-initialization pipeline extraction | Useful and safer. | Risks repeating M77 by adding boundaries without materially shrinking `boundary.py`. | Fold into the selected M78 scope as the core extraction target. |
| Exact return-emission structural/request IR | High later. | Would add the next semantic lowering slice before the current lowering boundary is maintainable, likely growing `boundary.py` further. | Defer until the exact array-body package has a smaller home. |
| Focused `_pipeline.py` payload/backfeed identity tightening | Useful follow-up. | Too narrow for the current maintainability problem and would not reduce `boundary.py` meaningfully. | Defer unless needed by M78 extraction. |
| Generic lowering framework / registry cleanup | Too abstract. | Would risk broad registries, semantic dispatchers, hidden backfeeds, or speculative architecture. | Reject for M78. |

### Milestone 78: Lowering Boundary Package Decomposition Slice

Status:

Accepted after the M78 execution-review loop returned `Accept With Follow-Ups`.

Goal:

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization lowering package behind
private, typed modules under `tslgen/src/tslgen/lowering/`, while preserving
all accepted M57-M77 behavior.

M78 is a behavior-preserving package decomposition. It must not add new
lowering semantics. Its success is measured partly by maintainability: the
pre-M78 `boundary.py` baseline is 12,371 physical lines, and M78 must reduce
that file by at least 1,000 net physical lines without leaving duplicate moved
code behind. A larger reduction is welcome only if it stays within the exact
package boundary and keeps imports/test behavior stable.

M78 execution reduced `boundary.py` to 11,109 physical lines, a net reduction
of 1,262 lines from the pre-M78 baseline. The extraction moved the exact
array-initialization shape/request-rule constants into
`tslgen.lowering._array_body_shapes`, the extracted exact array-body /
array-initialization diagnostics into
`tslgen.lowering._array_body_diagnostics`, and the remaining M75
predicate-init tokens and recognizer regex into
`tslgen.lowering._exact_shapes` as structural evidence only.

Scope:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from their accepted public paths.
- Extract one coherent private package area: the accepted exact array-body /
  array-initialization lowering tail from M63-M77. The extraction target may
  include private modules such as `_array_body_pipeline.py`,
  `_array_body_models.py`, `_array_body_sources.py`, or
  `_array_body_diagnostics.py` if those names fit the implementation, but it
  must not become a broad framework.
- M78 execution selected `_array_body_shapes.py` and
  `_array_body_diagnostics.py` as the first concrete extraction modules
  because they are exact-package-owned, do not import `boundary.py`, and keep
  public facade imports stable.
- Move only code exclusively owned by that exact package boundary, such as:
  - exact array-body envelope slot/skeleton assembly and lookup support;
  - exact array-initialization slot form, helper request, base-type,
    vector-length, vector-alignment, helper-set, and declaration-shell
    lowering orchestration;
  - exact array-body structural sequence, predicate-path, and post-branch
    call-site structural/request lowering orchestration;
  - `_ExactArrayInitializationStagePipelineResult` and the M77 pipeline
    snapshot integration;
  - known accepted exact stage-construction helpers for this package;
  - source adapters, validation helpers, and diagnostic helpers that are used
    only by the exact array-body / array-initialization path.
- Move remaining M75 exact predicate-init recognizer tokens such as
  `svbool_t`, `pg`, and `svptrue_b8` into `_exact_shapes.py` as slice-local
  structural evidence, not SVE or extension semantics.
- Leave shared models/helpers in `boundary.py` unless moving them is necessary
  for the coherent extraction and the public facade continues to re-export
  them.
- Avoid circular imports. New private modules should depend on explicit typed
  inputs and moved shared values, not on broad `boundary.py` internals that
  would recreate the monolith through imports.
- Preserve accepted M57-M77 diagnostics, stage names, stage ordering, output
  identities, keys, deterministic ordering, and selected-branch-only
  diagnostics.
- Preserve M77's private `_pipeline.py` fact/dependency snapshot behavior with
  no pending backfeeds. M78 may tighten `_pipeline.py` typing or backfeed
  identity only if doing so is directly needed by the decomposition.

Out of scope:

- New lowering semantics or generated behavior.
- Whole-file rewrite of `boundary.py`, broad OO class hierarchy, migration map
  from legacy modules, runtime plugin system, broad stage/helper/slot registry,
  generic semantic dispatcher, hidden recursive backfeeds, or generic
  fixpoint/backfeed execution.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics beyond accepted
  exact structural IR, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic
  semantics, byte-size-to-token inference, or source-operand semantics.
- Generic call IR, generic store IR, generic return IR, broad body IR, broad
  declaration/array/body/call/store/return parsing, raw helper-string
  dispatch, raw TSIL expression evaluation, or broad TSIL parsing.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M79.

Required input:

- Accepted M57-M77 lowering behavior and tests.
- The M77 private `_exact_shapes.py` and `_pipeline.py` boundaries.
- The current `tslgen/src/tslgen/lowering/boundary.py` implementation as the
  decomposition target.
- The current `boundary.py` line-count baseline of 12,371 physical lines.
- Redesign docs requiring typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch, deterministic diagnostics, and
  side-effect-free lowering.

Expected outputs:

- One or more private modules under `tslgen/src/tslgen/lowering/` containing
  the exact array-body / array-initialization lowering package previously
  concentrated in `boundary.py`.
- `tslgen/src/tslgen/lowering/_array_body_shapes.py` for exact
  array-initialization helper text, helper-leaf specs, request-rule values,
  and slot-form regexes.
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py` for extracted exact
  array-body / array-initialization diagnostics.
- M75 predicate-init structural tokens and recognizer regex in
  `tslgen/src/tslgen/lowering/_exact_shapes.py`.
- A `boundary.py` facade measured at 11,109 physical lines, at least 1,000
  physical lines smaller than the pre-M78 12,371-line baseline, with no
  duplicate moved code left behind.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- No public behavior changes to accepted M57-M77 lowering.
- No new backend translation, rendering, generated output, CLI/report/writer,
  Rust, compiler, generated-test, file/catalog-read, `tsldata`-read,
  host-CPU-query, backend-map-read, or runtime `frozen/` behavior.
- Redesign documentation describing the decomposition boundary and the measured
  `boundary.py` reduction.

Parity criterion:

M78 proves the accepted exact array-body / array-initialization lowering
package can live outside the central `boundary.py` file while preserving all
accepted behavior. The milestone is successful when the public facade remains
stable, tests prove behavior preservation, and `boundary.py` is materially
smaller.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the current 12,371-line facade,
  exact array-body models, resolver functions, and normal lowering integration
  points. After M78 execution it is 11,109 physical lines.
- `tslgen/src/tslgen/lowering/_array_body_shapes.py` for exact
  array-initialization helper/slot structural shapes and typed request-rule
  values.
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py` for exact
  array-body / array-initialization diagnostics.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for existing exact structural
  shape evidence and the destination for remaining M75 exact predicate-init
  tokens.
- `tslgen/src/tslgen/lowering/_pipeline.py` for M77 typed pipeline facts,
  dependencies, and empty pending-backfeed boundary.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M57-M77 behavior,
  diagnostics, determinism, and public import coverage.
- `tsldata/primitives/load_store/array.tsl` remains source-shape evidence only
  and must not become runtime input to lowering evaluation.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M78 module-decomposition tests proving public imports remain stable
  and the moved exact array-body / array-initialization pipeline produces the
  same stage names, outputs, keys, diagnostics, and deterministic ordering.
- Focused M78 tests assert the `boundary.py` public facade still exposes the
  accepted exact lowering types/functions while exact shape/rule constants and
  diagnostics resolve through the new private modules.
- A `boundary.py` line-count validation that records the new physical line
  count and proves it is at least 1,000 lines below the 12,371-line pre-M78
  baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad body/call/store/return/declaration/array
  semantics, raw helper evaluator calls, raw helper dispatch, catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`
  use is introduced.
- Import-cycle/import-stability checks selected by the executor.

Golden fixtures required:

- None. M78 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M78 module-decomposition/import-stability command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Reducing line count by moving code but leaving duplicate behavior or
  compatibility wrappers behind.
- Creating circular private imports that make the decomposition only cosmetic.
- Moving helpers that are still shared by unrelated lowering paths and thereby
  coupling unrelated slices to the exact array-body package.
- Treating exact tokens such as `svbool_t`, `pg`, `svptrue_b8`,
  `svptrue_b*`, `intrin`, `svst1`, `tmp.data()`, or `a` as SVE/ARM/store/
  backend semantics rather than structural evidence.
- Introducing generic stage factories, broad registries, semantic dispatchers,
  raw helper evaluators, runtime plugins, or fixpoint/backfeed execution.
- Changing accepted M57-M77 diagnostics, stage ordering, output identities,
  public imports, or deterministic behavior while moving code.
- Adding backend translation, rendering, generated output, broad TSIL parsing,
  lowering-time file/catalog reads, `tsldata` reads, host CPU queries, backend
  map reads, or runtime `frozen/` access.

Dependencies on prior milestones:

- Milestones 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
  73, 74, 75, 76, and 77.

Next concrete prompt:

- `docs/agent/runs/post-m77-acceptance-finalization-prompt.md` must run after
  explicit human acceptance. It will update the workflow state for M78
  execution and create `docs/agent/runs/m78-execution-review-loop-prompt.md`.

### Milestone 79: Exact Array-Body Typed Model Ownership Extraction Slice

Status:

Accepted. The M79 execution-review loop returned `Accept With Follow-Ups`.

Goal:

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization typed model ownership into
private lowering modules while preserving all accepted M57-M78 behavior.

M79 is a behavior-preserving model ownership extraction, not a new lowering
semantic milestone. It may combine the M78 follow-ups only because they have
the same root cause: exact array-body typed model ownership is still split
between `boundary.py`, `_array_body_shapes.py`, and
`_array_body_diagnostics.py`. The post-M78 `boundary.py` baseline is 11,109
physical lines, and M79 should reduce that facade by at least 1,500 net
physical lines unless the executor documents that an import-boundary risk
requires a narrower accepted reduction.

M79 execution creates `tslgen.lowering._array_body_models` as the private
exact array-body / array-initialization model owner. It moves exact-package
typed aliases, helper rule/spec values, vector metadata values, envelope
models, helper request/resolution models, declaration shell, structural
sequence, predicate-path request, and post-branch call-site request values out
of `boundary.py` while keeping `boundary.py` as the public facade. It also
updates `_array_body_shapes.py` to consume the model-owned helper aliases and
rule values, and updates `_array_body_diagnostics.py` to use small local
protocols from the model boundary instead of unconstrained `Any` inputs for
the targeted helper diagnostics. `boundary.py` now measures 8,915 physical
lines, which is 2,194 lines below the post-M78 11,109-line baseline and
satisfies the M79 reduction target.

Scope:

- Create a private exact array-body model module such as
  `tslgen.lowering._array_body_models` to own exact-package typed aliases,
  dataclasses, and tiny protocols that are exclusively consumed by the exact
  M63-M78 array-body / array-initialization path.
- Preserve public imports through `tslgen.lowering` and
  `tslgen.lowering.boundary`. Accepted public classes/functions must remain
  importable from their existing public paths.
- Consolidate duplicated exact helper `Literal` aliases currently split
  between `boundary.py` and `_array_body_shapes.py` into one private typed
  ownership location consumed by both modules.
- Move exact array-body / array-initialization typed IR/value models when they
  can move without making a private module import `boundary.py`. Candidate
  model ownership includes exact envelope slots, unresolved helper leaves,
  helper request records, base/vector/backend request-resolution values,
  declaration-shell values, structural sequence values, predicate-path request
  values, and post-branch call-site request values.
- Replace `_array_body_diagnostics.py` `Any` helper inputs only where the new
  model/protocol boundary provides a local typed replacement. Diagnostics may
  use small private protocols for source-location, field-name, kind, and
  source-text access instead of importing `boundary.py`.
- Keep `boundary.py` as a facade/coordinator around the accepted lowering
  functions and normal pipeline integration. It may import private model
  values and re-export accepted public names, but private modules must not
  import `boundary.py`.
- Preserve accepted M57-M78 diagnostics, stage names, stage ordering, output
  identities, keys, deterministic ordering, selected-branch-only diagnostics,
  public facade imports, and the M78 private-module import direction.

Out of scope:

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, or generated output.
- Whole-file rewrite of `boundary.py`, moving unrelated shared generation
  models, broad OO hierarchy, broad model hierarchy, generic body model,
  stage/helper/slot registry, semantic dispatcher, runtime plugin system,
  hidden recursive backfeeds, or fixpoint execution.
- Moving the full exact array-body stage coordinator, source-adapter cluster,
  validator cluster, or `_pipeline.py` payload/backfeed model unless a small
  dependency move is necessary for the model boundary and remains private.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics beyond accepted
  exact structural IR, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic
  semantics, byte-size-to-token inference, source-operand semantics, generic
  call/store/return/body/declaration/array parsing, broad TSIL parsing, or raw
  helper-string dispatch.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M80.

Required input:

- Accepted M57-M78 lowering behavior and tests.
- The post-M78 private modules:
  `tslgen.lowering._array_body_shapes`,
  `tslgen.lowering._array_body_diagnostics`,
  `tslgen.lowering._exact_shapes`, and `tslgen.lowering._pipeline`.
- The post-M78 `boundary.py` baseline of 11,109 physical lines.
- Redesign rules requiring typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch, deterministic diagnostics, no circular
  private imports, and side-effect-free lowering.

Expected outputs:

- A private exact array-body model module, or equivalent coherent private
  module split, that owns the exact package typed model boundary.
- M79 execution adds `tslgen/src/tslgen/lowering/_array_body_models.py` for
  this private model boundary.
- `_array_body_shapes.py` consuming shared exact helper aliases/spec types from
  the new private model boundary instead of duplicating them with `boundary.py`.
- `_array_body_diagnostics.py` using local typed protocols or moved typed
  models for targeted helper inputs instead of unconstrained `Any` where the
  M79 boundary owns the needed attributes.
- `boundary.py` acting as public facade/coordinator and measuring 8,915
  physical lines, at least 1,500 physical lines below the post-M78 11,109-line
  baseline, without a documented narrower reduction exception.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- No public behavior changes to accepted M57-M78 lowering.

Parity criterion:

M79 proves the accepted exact array-body / array-initialization typed model
ownership can live outside the central `boundary.py` file while preserving all
accepted behavior. The milestone succeeds when model ownership is no longer
split, the public facade remains stable, diagnostics stay stable, and
`boundary.py` is materially smaller without duplicate moved code.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the post-M79 facade and the
  former pre-M79 exact array-body typed model ownership site.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for the M79 private exact
  array-body / array-initialization typed model boundary.
- `tslgen/src/tslgen/lowering/_array_body_shapes.py` for the former
  duplicated exact helper aliases and current shared helper shape consumers.
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py` for the former M78
  `Any` diagnostic helper inputs and current protocol-typed diagnostic
  consumers.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for exact structural tokens
  that must remain shape evidence only.
- `tslgen/src/tslgen/lowering/_pipeline.py` for the accepted private pipeline
  boundary that M79 must not broaden into a registry.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M57-M78 behavior,
  diagnostics, determinism, private-module boundaries, and public facade
  coverage.
- `tsldata/primitives/load_store/array.tsl` remains source-shape evidence only
  and must not become runtime input to lowering evaluation.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M79 import-stability tests proving accepted public exact model names
  still resolve through `tslgen.lowering` and `tslgen.lowering.boundary`.
- M79 execution adds focused tests proving the `boundary.py` facade re-exports
  model-owned exact classes, `_array_body_shapes.py` shares helper aliases and
  rule values from `_array_body_models.py`, and `_array_body_diagnostics.py`
  consumes typed protocols instead of importing `Any`.
- Focused private-boundary tests proving `_array_body_models` or equivalent
  private modules import without importing `boundary.py`, and that
  `_array_body_shapes.py` consumes the shared exact helper aliases/specs.
- Focused tests proving representative moved model constructors, keys,
  source-location handling, and deterministic ordering remain unchanged.
- Focused diagnostic-preservation tests for any `_array_body_diagnostics.py`
  helper whose `Any` input is replaced by a typed protocol or moved model.
- A `boundary.py` line-count validation measured against the 11,109-line
  post-M78 baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad body/call/store/return/declaration/array
  semantics, raw helper evaluator calls, raw helper dispatch, catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, import cycles,
  duplicate moved code, or runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M79 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M79 model-ownership/import-stability command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating a line-count target as permission to move unrelated shared lowering
  models or recreate `boundary.py` as a second monolith.
- Creating circular private imports, especially by making `_array_body_models`,
  `_array_body_shapes.py`, or `_array_body_diagnostics.py` import
  `boundary.py`.
- Leaving duplicated exact helper aliases in place, making the extraction
  cosmetic.
- Replacing diagnostic `Any` with over-broad protocols or changing diagnostic
  codes, messages, severity, paths, lines, or columns.
- Turning exact helper text, request ordinals, SVE-looking tokens, backend ids,
  or corpus paths into semantic dispatch keys.
- Changing accepted M57-M78 diagnostics, stage ordering, output identities,
  public imports, deterministic behavior, or selected-branch-only diagnostics.

Dependencies on prior milestones:

- Milestones 57 through 78.

Next concrete prompt:

- `docs/agent/runs/post-m79-planning-plus-review-prompt.md` completed the
  post-M79 planning pass that selected M80.

### Milestone 80: Exact Array-Body Validation Boundary Extraction Slice

Status:

Accepted. M80 execution-review returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, extensibility, documentation,
or evidence issues after workflow documentation finalization.

Goal:

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization validation and request-record
helper ownership into a private lowering module while preserving all accepted
M57-M79 behavior.

M80 is a behavior-preserving lowering architecture slice, not a new semantic
lowering milestone. The post-M79 `boundary.py` baseline is 8,915 physical
lines. M80 should remove at least 1,500 net physical lines from that facade,
so the post-M80 count should be 7,415 physical lines or lower, unless the
executor documents that import-boundary risk requires a narrower accepted
reduction. The line-count target must not justify moving unrelated shared
generation models, changing diagnostics, broadening semantics, or recreating a
second monolith.

Scope:

- Create a private exact array-body validation module such as
  `tslgen.lowering._array_body_validation` to own accepted exact-package
  validation, request-record selection, metadata lookup validation, and small
  construction helpers that can move without importing `boundary.py`.
- Move the pure exact array-body / array-initialization helper cluster around:
  `_validate_array_initialization_*`,
  `_array_initialization_*_request_record`,
  `_array_initialization_*_metadata_for_context` where narrow local protocols
  avoid facade imports, `_validate_array_body_structural_sequence_inputs`,
  `_validate_predicate_path_structural_request_input`,
  `_validate_post_branch_intrinsic_call_site_input`,
  `_exact_array_body_envelope_shape_is_supported`,
  `_structural_role_from_slot`, and `_array_initialization_leaf`.
- Use narrow private protocols only where the moved helpers need facade-owned
  context-like values such as generation context metadata. Prefer leaving a
  helper in `boundary.py` over making a private module import `boundary.py` or
  duplicating ownership.
- Add a committed private-import-boundary regression test covering
  `_array_body_models.py`, `_array_body_shapes.py`,
  `_array_body_diagnostics.py`, `_array_body_validation.py`,
  `_exact_shapes.py`, and `_pipeline.py`.
- Keep public imports stable through `tslgen.lowering` and
  `tslgen.lowering.boundary`; `boundary.py` remains the public facade and may
  delegate to private validation helpers.
- Preserve accepted M57-M79 diagnostics, diagnostic codes, severities,
  messages, source locations, stage names, stage ordering, output identities,
  keys, deterministic ordering, selected-branch-only diagnostics, public facade
  imports, and no-external-input boundaries.
- Preserve the M79 private-module import direction. Private modules must not
  import `boundary.py`.

Out of scope:

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, exact return-emission IR, store semantics,
  return semantics, memory behavior, pointer semantics, variable
  scope/use-def/lifetime, declaration/array semantics beyond accepted exact
  structural IR, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic
  semantics, byte-size-to-token inference, source-operand semantics, or
  generated output.
- Moving source adapters that consume `GenerationLoweringStage` or
  `LoweredImplementation`, moving the full exact stage coordinator,
  moving `GenerationLoweringStage.__post_init__`, or changing public stage
  construction unless a tiny dependency move is required and remains
  behavior-preserving.
- Broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering; broad direct `intrin<...>`
  semantics; broad vector metadata semantics; generic body/call/store/return/
  declaration/array IR; broad TSIL parsing; raw helper dispatch; registry,
  dispatcher, plugin, or fixpoint/backfeed engine work.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M81.

Required input:

- Accepted M57-M79 lowering behavior and tests.
- M79 private model ownership in `tslgen.lowering._array_body_models`.
- M78/M79 private exact shape, diagnostic, structural-token, and pipeline
  modules:
  `tslgen.lowering._array_body_shapes`,
  `tslgen.lowering._array_body_diagnostics`,
  `tslgen.lowering._exact_shapes`, and `tslgen.lowering._pipeline`.
- The post-M79 `boundary.py` baseline of 8,915 physical lines.
- Redesign rules requiring typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch, deterministic diagnostics, no circular
  private imports, and side-effect-free lowering.

Expected outputs:

- A private exact array-body validation module, or an equivalent coherent
  private module split, owning the accepted exact validation/request-record
  helper boundary.
- `boundary.py` delegates to the private validation helpers while remaining the
  public facade/coordinator.
- `boundary.py` measures 7,415 physical lines or lower, unless a documented
  import-boundary exception justifies a narrower accepted reduction.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- A focused private-import-boundary regression test that protects M79/M80
  module direction.
- No public behavior changes to accepted M57-M79 lowering.

Parity criterion:

M80 proves the accepted exact array-body validation/request-record helper
boundary can live outside the central `boundary.py` file while preserving all
accepted behavior. The milestone succeeds when validation ownership is no
longer mixed into the facade, the public import surface remains stable,
diagnostics remain stable, private modules do not import `boundary.py`, and
`boundary.py` is materially smaller without duplicate moved code.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the post-M79 facade and the
  remaining exact validation/request-record helper cluster.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for accepted exact
  array-body / array-initialization typed model ownership.
- `tslgen/src/tslgen/lowering/_array_body_shapes.py` for accepted exact helper
  aliases/rules and exact shape consumers.
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py` for accepted exact
  diagnostics.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for exact structural tokens
  that must remain shape evidence only.
- `tslgen/src/tslgen/lowering/_pipeline.py` for accepted private pipeline
  facts that M80 must not broaden into a registry or fixpoint engine.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M57-M79 behavior,
  diagnostics, determinism, private-module boundaries, and public facade
  coverage.
- `tsldata/primitives/load_store/array.tsl` remains source-shape evidence only
  and must not become runtime input to lowering evaluation.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M80 tests proving public exact lowering functions still resolve
  through `tslgen.lowering` and `tslgen.lowering.boundary`.
- Focused private-import-boundary regression proving accepted private lowering
  modules, including the new validation module, do not import `boundary.py`.
- Focused validation/request-record equivalence tests for representative moved
  helpers, including diagnostic code/severity/message/source-location
  preservation.
- Focused tests preserving exact array-body pipeline stage names/order/output
  keys where moved validation helpers are consumed.
- A `boundary.py` line-count validation measured against the 8,915-line
  post-M79 baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad body/call/store/return/declaration/array
  semantics, raw helper evaluator calls, raw helper dispatch, catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, import cycles,
  duplicate moved code, or runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M80 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M80 validation-boundary/import-stability command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Moving source adapters or stage construction that still depend on
  facade-owned `GenerationLoweringStage` or `LoweredImplementation`, causing
  circular imports or over-broad protocols.
- Turning the private validation module into a general validator registry,
  semantic dispatcher, or stage framework.
- Changing accepted diagnostic text, code, severity, path, line, or column
  while moving validators.
- Broadening structural protocols to hide missing ownership boundaries.
- Treating exact tokens such as `svst1`, `tmp.data()`, `emit_return(tmp)`,
  `pg`, `svptrue_b*`, or `a` as semantics rather than structural provenance.
- Reducing line count by moving unrelated shared lowering/generation code,
  duplicating moved helpers, or leaving compatibility wrappers around poor
  abstractions.

Dependencies on prior milestones:

- Milestones 57 through 79.

Next concrete prompt:

- `docs/agent/runs/post-m80-planning-plus-review-prompt.md` selects the next
  lowering-focused milestone after M80.

Execution result:

- M80 preserves accepted M57-M79 behavior while creating
  `tslgen.lowering._array_body_validation` as the private exact array-body /
  array-initialization validation and request-record helper owner.
- `boundary.py` delegates exact validation/request-record helper work to the
  private module while remaining the public facade/coordinator.
- Public `tslgen.lowering` and `tslgen.lowering.boundary` imports remain
  stable.
- Private lowering modules, including `_array_body_validation.py`, do not
  import `boundary.py`.
- `boundary.py` now measures 7,208 physical lines, which is below the M80
  threshold of 7,415 lines and 1,707 lines below the post-M79 baseline.
- No new lowering semantics, helper evaluation, source-adapter behavior,
  backend translation, rendering, generated output, broad parsing,
  extension hardwiring, file/catalog reads, `tsldata` reads, host CPU queries,
  backend map reads, or runtime `frozen/` use were added.

### Milestone 81: Generation-Time Lowering Core Ownership Extraction Slice

Status:

Accepted. M81 execution-review returned `Accept With Follow-Ups` after one
focused maintainability revision.

Goal:

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted generation-time lowering core into private typed lowering modules
while preserving all accepted M42-M80 behavior.

M81 is a behavior-preserving lowering architecture slice, not a new semantic
lowering milestone. The post-M80 `boundary.py` baseline was 7,208 physical
lines. M81 reduced that facade to 5,438 physical lines, below the 5,808-line
target, without moving unrelated exact array-body source adapters, changing
diagnostics, broadening semantics, or recreating a second monolith.

Scope:

- Create private generation-time lowering modules such as
  `tslgen.lowering._generation_models`,
  `tslgen.lowering._generation_queries`,
  `tslgen.lowering._generation_control_flow`, and
  `tslgen.lowering._generation_diagnostics`, or an equivalent coherent
  private module split.
- Move accepted generation-time model ownership where it can remain
  import-stable, including `GenerationTypeRef`, `GenerationValue`,
  `GenerationPredicate`, `GenerationExpressionRecognition`,
  `PrunedGenerationBranch`, `GenerationSizeByteBranchChainArm`,
  `GenerationSizeByteBranchChainPruning`,
  `TsilPrimitiveAttributeCondition`, and `TsilTypeSignednessCondition`.
- Move accepted generation helper parsing/resolution support where it can move
  without importing `boundary.py`, including exact generation type/value/
  predicate query parsing, `base.in`, signed/unsigned companion, scalar
  `type.size_bytes` / `type.size_bits`, exact size-byte equality predicate,
  primitive-attribute condition, signedness condition, generation `if` /
  plain-else / size-byte branch-chain parsing, and related diagnostics.
- Keep public imports stable through `tslgen.lowering` and
  `tslgen.lowering.boundary`; `boundary.py` remains the public facade and may
  delegate to private generation helpers.
- Keep source adapters and orchestration that still depend on
  `LoweringInput`, `LoweringRequest`, `LoweredImplementation`,
  `GenerationLoweringStage`, candidate selection, or the exact array-body
  pipeline in `boundary.py` unless a tiny delegation move is required and
  remains behavior-preserving.
- Preserve accepted M42-M80 diagnostics, diagnostic codes, severities,
  messages, source locations, selected-branch-only diagnostics, stage names,
  stage ordering, output identities, keys, deterministic ordering, public
  facade imports, and no-external-input boundaries.
- Preserve private-module import direction. New generation-time private
  modules and existing private lowering modules must not import `boundary.py`.

Out of scope:

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, new generation helper families, broad
  `type<generation>` / `value<generation>` / `type<backend>` /
  `value<backend>` evaluation, exact return-emission IR, store semantics,
  return semantics, memory behavior, pointer semantics, variable
  scope/use-def/lifetime, declaration/array semantics, initializer behavior,
  `tmp.data()` semantics, `emit_return`, `assume_aligned`, ARM/SVE predicate/
  vector/register/intrinsic semantics, byte-size-to-token inference,
  source-operand semantics, or generated output.
- Moving `LoweredImplementation`, `GenerationLoweringStage`,
  `GenerationContext`, `LoweringRequest`, `lower_candidates`, the full
  exact array-body stage coordinator, or source adapters that consume
  `GenerationLoweringStage` / `LoweredImplementation`, unless a tiny dependency
  move is required and remains behavior-preserving.
- Moving mini-TSIL return lowering, broad assignment, variable, declaration,
  array, call, cast, loop, store, return, or multi-statement body lowering;
  broad direct `intrin<...>` semantics; broad vector metadata semantics;
  generic body/call/store/return/declaration/array IR; broad TSIL parsing;
  raw helper dispatch; registry, dispatcher, plugin, or fixpoint/backfeed
  engine work.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M82.

Required input:

- Accepted M42-M59 generation-time helper and branch-pruning behavior.
- Accepted M57-M80 lowering behavior and tests.
- The post-M80 `boundary.py` baseline of 7,208 physical lines.
- Existing generation rule-set ownership in `tslgen.domain.generation_rules`.
- Redesign rules requiring typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch to semantic outputs, deterministic
  diagnostics, no circular private imports, and side-effect-free lowering.

Expected outputs:

- Private generation-time lowering modules owning accepted generation model,
  query, control-flow, and diagnostic helpers that can move without importing
  `boundary.py`: `tslgen.lowering._generation_models`,
  `tslgen.lowering._generation_queries`,
  `tslgen.lowering._generation_control_flow`, and
  `tslgen.lowering._generation_diagnostics`.
- `boundary.py` delegates accepted generation-time helper resolution and
  branch pruning to the private generation modules while remaining the public
  facade/coordinator.
- `boundary.py` measures 5,438 physical lines, below the 5,808-line M81
  threshold.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- Focused private-import-boundary regression coverage for the new generation
  modules.
- No public behavior changes to accepted M42-M80 lowering.

Parity criterion:

M81 proves the accepted generation-time lowering core can live outside the
central `boundary.py` file while preserving accepted behavior. The milestone
succeeds when generation model/query/control-flow/diagnostic ownership is no
longer mixed into the facade, the public import surface remains stable,
diagnostics remain stable, private modules do not import `boundary.py`, and
`boundary.py` is materially smaller without duplicate moved code.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the post-M80 facade and the
  remaining generation-time model/query/control-flow/diagnostic cluster.
- `tslgen/src/tslgen/lowering/_array_body_models.py`,
  `_array_body_shapes.py`, `_array_body_diagnostics.py`,
  `_array_body_validation.py`, `_exact_shapes.py`, and `_pipeline.py` for
  accepted private lowering-module import direction and facade delegation
  style.
- `tslgen/src/tslgen/domain/generation_rules.py` for accepted typed
  generation rule-set ownership.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M42-M80
  generation-time helper, branch-pruning, determinism, diagnostics, private
  module boundary, and public facade coverage.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M81 tests proving public generation-time imports still resolve
  through `tslgen.lowering` and `tslgen.lowering.boundary`.
- Focused private-import-boundary regression proving new generation private
  modules and accepted private lowering modules do not import `boundary.py`.
- Focused generation query/control-flow equivalence tests for representative
  moved helpers, including diagnostic code/severity/message/source-location
  preservation for type queries, value queries, size-byte predicates,
  primitive-attribute branches, signedness branches, plain `else`, and
  size-byte branch chains.
- A `boundary.py` line-count validation measured against the 7,208-line
  post-M80 baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad TSIL/body/call/store/return/declaration/
  array semantics, raw helper evaluator calls, raw helper dispatch, catalog
  reads, `tsldata` reads, host CPU queries, backend map reads, import cycles,
  duplicate moved code, or runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M81 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M81 generation-core/import-stability command selected by the
  executor.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Moving source adapters or orchestration that still depend on facade-owned
  `GenerationLoweringStage`, `LoweredImplementation`, `LoweringInput`, or
  `LoweringRequest`, causing circular imports or over-broad protocols.
- Turning the generation modules into a general helper evaluator, registry,
  semantic dispatcher, plugin system, or fixpoint/backfeed engine.
- Changing accepted diagnostic text, code, severity, path, line, or column
  while moving helpers.
- Broadening structural protocols to hide missing ownership boundaries.
- Treating source text, selected type tags, SVE tokens, backend ids, renderer
  names, or corpus line numbers as semantic dispatch keys rather than
  provenance/invariant evidence.
- Reducing line count by moving unrelated exact array-body pipeline code,
  duplicating moved helpers, or leaving compatibility wrappers around poor
  abstractions.

Dependencies on prior milestones:

- Milestones 42 through 80.

Next concrete prompt:

- `docs/agent/runs/post-m81-planning-plus-review-prompt.md` runs the
  post-M81 lowering-focused planning and review workflow.

Accepted result:

- M81 preserves accepted M42-M80 behavior while moving generation-time model,
  query, control-flow, and diagnostic helper ownership into private typed
  generation modules.
- Public `tslgen.lowering` and `tslgen.lowering.boundary` imports remain
  stable, and private lowering modules do not import `boundary.py`.
- The initial maintainability review found an over-broad private
  `GenerationControlContext` / candidate-context copy in
  `_generation_control_flow.py`; the focused revision narrowed the protocol,
  removed the duplicate private context construction, and kept concrete
  `GenerationContext` construction in the facade.
- `boundary.py` now measures 5,438 physical lines, which is below the M81
  threshold of 5,808 lines and 1,770 lines below the post-M80 7,208-line
  baseline.
- Validation completed with the required line-count, py-compile, focused M81
  generation-core/import-stability command, full lowering-boundary suite, full
  tooling validation profile, and diff-check.
- Non-blocking follow-ups remain for broadening focused M81 diagnostic
  location coverage and hoisting repeated facade-local context/type-tag
  expressions in the exact-array pipeline call sequence.

### Milestone 82: Selected-Body Envelope Ownership Extraction Slice

Status:

Accepted. M82 execution-review returned `Accept`.

Goal:

Move accepted selected-body envelope concrete model ownership out of
`tslgen/src/tslgen/lowering/boundary.py` into a private typed lowering module
while preserving all accepted M42-M81 behavior and public import paths.

M82 is a behavior-preserving lowering architecture slice, not a new semantic
lowering milestone. It addresses the M80/M81 follow-up that the concrete M63
selected/no-selected body envelope models still live in the facade, forcing
`_array_body_models.py` and `_array_body_validation.py` to consume broad
structural protocols, `hasattr` checks, and casts. The slice should remove
that seam through concrete private model ownership rather than broader
protocols.

Scope:

- Create a private selected-body model module such as
  `tslgen.lowering._selected_body_models`, or an equivalent coherent private
  module.
- Move the minimal cohesive selected-body value-model cluster needed to avoid
  circular private imports while preserving public facade imports. The expected
  ownership set includes:
  - `OpaqueSelectedBranchBodyHandoff`
  - `NoSelectedBranchBodyHandoff`
  - `SelectedBranchBodyAssignmentFormRecognition`
  - `NoSelectedBranchBodyAssignmentFormRecognition`
  - `SelectedAssignmentDirectIntrinsicBodyIr`
  - `NoSelectedAssignmentDirectIntrinsicBodyIr`
  - `SelectedBodyEnvelopeEntry`
  - `SelectedBodyEnvelopeIr`
  - `NoSelectedBodyEnvelopeIr`
  - the selected-body union aliases that can move without importing
    `boundary.py`
- Keep `boundary.py` as the public facade/coordinator and re-export the moved
  public names through existing public paths.
- Keep selected-body lowering functions in `boundary.py` unless a tiny helper
  move is required and remains behavior-preserving:
  `handoff_opaque_selected_branch_body`,
  `recognize_selected_branch_body_assignment_form`,
  `lower_selected_branch_body_ir`, and `lower_selected_body_envelope`.
- Tighten `_array_body_models.py` and `_array_body_validation.py` to consume
  the concrete private selected-body envelope model types where possible,
  removing or narrowing the M63 selected/no-selected `hasattr`/cast seam.
- Preserve accepted M42-M81 diagnostics, diagnostic codes, severities,
  messages, source locations, selected-branch-only diagnostics, stage names,
  stage ordering, output identities, keys, deterministic ordering, public
  facade imports, and no-external-input boundaries.
- Preserve private-module import direction. New selected-body private modules
  and existing private lowering modules must not import `boundary.py` or the
  `tslgen.lowering` package facade.

Out of scope:

- New lowering semantics, new selected-body semantics, new generation helper
  semantics, helper evaluation, broad direct-intrinsic semantics, broad TSIL
  parsing, exact return-emission IR, store semantics, return semantics,
  memory behavior, pointer semantics, variable scope/use-def/lifetime,
  declaration/array semantics, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/
  intrinsic semantics, byte-size-to-token inference, source-operand semantics,
  or generated output.
- Moving `GenerationLoweringStage`, `GenerationContext`,
  `LoweredImplementation`, `LoweringRequest`, `lower_candidates`, source
  adapters, the exact array-body stage coordinator, or the M81 generation
  query/control-flow modules' ownership.
- Moving selected-body lowering functions beyond tiny behavior-preserving
  helper delegation.
- Moving mini-TSIL return lowering, broad assignment, variable, declaration,
  array, call, cast, loop, store, return, or multi-statement body lowering;
  broad vector metadata semantics; generic body/call/store/return/
  declaration/array IR; raw helper dispatch; registry, dispatcher, plugin, or
  fixpoint/backfeed engine work.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M83.

Required input:

- Accepted M60 opaque selected-body handoff behavior.
- Accepted M61 selected assignment-form recognition behavior.
- Accepted M62 selected/no-body assignment/direct-intrinsic body IR behavior.
- Accepted M63 selected/no-selected body envelope behavior.
- Accepted M64-M81 exact array-body consumers, validation, pipeline, stage,
  public import, and private import-direction behavior.
- The post-M81 `boundary.py` baseline of 5,438 physical lines.
- Redesign rules requiring typed semantic lowering, no renderer-side helper
  evaluation, no raw helper dispatch to semantic outputs, deterministic
  diagnostics, no circular private imports, and side-effect-free lowering.

Expected outputs:

- A private selected-body model module owning the moved selected-body handoff,
  form-recognition, body-IR, and envelope model values that can move without
  importing `boundary.py`.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- The same `selected_body_envelope_lowering` stage output identity and
  `LoweredImplementation.selected_body_envelopes` behavior.
- `_array_body_models.py` and `_array_body_validation.py` consume concrete
  selected-body envelope model types where possible rather than broad M63
  selected/no-selected structural checks.
- `boundary.py` remains the public facade/coordinator and is materially
  smaller, with no duplicate moved model code.
- No public behavior changes to accepted M42-M81 lowering.

Parity criterion:

M82 succeeds when selected-body envelope concrete ownership is no longer mixed
into the facade, the M63 selected/no-selected envelope seam in private
array-body modules is concrete or deliberately narrow, public imports remain
stable, diagnostics remain stable, private modules do not import `boundary.py`,
and no new semantics or output behavior are introduced.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the post-M81 facade,
  selected-body value-model cluster, selected-body lowering functions,
  `GenerationLoweringStage`, `LoweredImplementation`, and exact array-body
  orchestration that must remain facade-owned.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for the existing
  selected/no-selected envelope structural checks and concrete model consumer
  pressure.
- `tslgen/src/tslgen/lowering/_array_body_validation.py` for existing
  selected/no-selected envelope protocols/casts.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M60-M63
  selected-body handoff/form/body-IR/envelope behavior, diagnostics,
  determinism, no-reparse guarantees, nested envelope identity, and stage
  order/output coverage.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M82 tests proving public selected-body model imports still resolve
  through `tslgen.lowering` and `tslgen.lowering.boundary`.
- Focused private-import-boundary regression proving the new selected-body
  private module and accepted private lowering modules do not import
  `boundary.py` or the `tslgen.lowering` package facade.
- Focused selected/no-selected envelope behavior and diagnostic preservation
  tests, including source locations, keys, deterministic output, and no
  selected-body reparsing.
- Regression coverage through M64-M76 consumers proving nested envelope
  identity and stage order remain stable.
- A `boundary.py` line-count validation measured against the 5,438-line
  post-M81 baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad TSIL/body/call/store/return/declaration/
  array semantics, raw helper evaluator calls, raw helper dispatch, catalog
  reads, `tsldata` reads, host CPU queries, backend map reads, import cycles,
  duplicate moved code, or runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M82 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- A focused M82 selected-body ownership/import-stability command selected by
  the executor.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Moving only envelope classes and creating circular imports because M63
  envelopes depend on M62 body IR classes still in `boundary.py`.
- Moving too much selected-body lowering behavior under an ownership label.
- Replacing the old structural seam with broader protocols instead of concrete
  private model ownership.
- Changing accepted diagnostic text, code, severity, path, line, or column
  while moving models.
- Moving source adapters or orchestration that still depend on facade-owned
  `GenerationLoweringStage`, `LoweredImplementation`, `LoweringInput`, or
  `LoweringRequest`.
- Treating SVE-looking tokens, selected type tags, source text, backend ids,
  renderer names, or corpus line numbers as semantic dispatch keys rather
  than provenance/invariant evidence.
- Reducing line count by moving unrelated exact array-body pipeline code,
  duplicating moved helpers, or leaving compatibility wrappers around poor
  abstractions.

Dependencies on prior milestones:

- Milestones 60 through 81.

Execution result:

- M82 preserves accepted M42-M81 behavior while moving selected-body
  handoff/form/body-IR/envelope model ownership into
  `tslgen.lowering._selected_body_models`.
- The moved private model module owns:
  `OpaqueSelectedBranchBodyHandoff`, `NoSelectedBranchBodyHandoff`,
  `SelectedBranchBodyAssignmentFormRecognition`,
  `NoSelectedBranchBodyAssignmentFormRecognition`,
  `SelectedAssignmentDirectIntrinsicBodyIr`,
  `NoSelectedAssignmentDirectIntrinsicBodyIr`,
  `SelectedBodyEnvelopeEntry`, `SelectedBodyEnvelopeIr`,
  `NoSelectedBodyEnvelopeIr`, and the selected-body union aliases.
- `boundary.py` remains the public facade/coordinator and re-exports the
  moved public names through existing public paths.
- `_array_body_models.py` and `_array_body_validation.py` now consume concrete
  private selected-body envelope model types through the private module rather
  than broad selected/no-selected structural `hasattr` or cast seams.
- Private lowering modules, including `_selected_body_models.py`, do not
  import `boundary.py` or the `tslgen.lowering` package facade.
- `boundary.py` now measures 4,965 physical lines, which is 473 lines below
  the post-M81 5,438-line baseline.
- No new lowering semantics, selected-body semantics, helper evaluation,
  source-adapter behavior, backend translation, rendering, generated output,
  broad parsing, extension hardwiring, file/catalog reads, `tsldata` reads,
  host CPU queries, backend map reads, or runtime `frozen/` use were added.
- Review and audit found no blocking implementation, validation, boundary,
  extensibility, documentation, or evidence issues.

Next concrete prompt:

- `docs/agent/runs/post-m82-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 83: GenerationLoweringStage Output Contract Extraction Slice

Status:

Accepted. M83 execution-review returned `Accept With Follow-Ups`.

Goal:

Move the accepted generation lowering stage-name/output validation contract out
of `tslgen/src/tslgen/lowering/boundary.py` into a private typed lowering
module while preserving all accepted M42-M82 behavior, public import paths,
stage names, stage ordering, output identities, deterministic keys,
diagnostics, and no-external-input boundaries.

M83 is behavior-preserving lowering architecture work. It prepares the staged
lowering pipeline for later semantic slices by taking the growing
`GenerationLoweringStage` output contract out of the facade-owned validation
ladder. M87 later used that foundation for exact return-emission
structural/request IR. M83 is contract validation, not stage execution
dispatch, a registry, a plugin system, a fixpoint engine, or a new semantic
lowering slice.

Scope:

- Create a private typed stage-contract module such as
  `tslgen.lowering._stage_contracts`, or an equivalent coherent private
  lowering module.
- Move or own the stage contract data currently encoded by
  `GenerationLoweringStage.__post_init__`, including the accepted mapping from
  each `GenerationLoweringStageName` to the allowed output model type or types.
- Preserve the existing public `GenerationLoweringStage` behavior and import
  paths through `tslgen.lowering` and `tslgen.lowering.boundary`.
- Keep stage names, stage ordering, output object identity, `key` behavior,
  error class/message shape for invalid stage/output pairings, and deterministic
  pipeline snapshots unchanged.
- Keep `boundary.py` as the public facade/coordinator for lowering requests,
  candidate/source adapters, `LoweredImplementation`, lower-candidate
  orchestration, and existing stage construction unless a tiny dependency move
  is required to avoid an import cycle.
- If import safety requires it, move only the minimal mini-TSIL value-model
  cluster needed by the stage-output union into a private model module. Do not
  move mini-TSIL parsing or broad TSIL semantics under this milestone.
- Preserve one-way private imports. The new stage-contract module and existing
  private lowering modules must not import `boundary.py` or the
  `tslgen.lowering` package facade.
- Reduce `boundary.py` line count from the accepted M82 baseline of 4,965
  physical lines without duplicating moved contract code.

Out of scope:

- New stage names, new stage ordering, new stage outputs, new diagnostics, new
  lowering semantics, exact return-emission IR, store/call/body/return
  semantics, broad TSIL parsing, generic body/call/store/return/declaration/
  array IR, generic source adapters, source skeleton recognition, helper
  evaluation, broad generation helper families, raw helper dispatch, semantic
  dispatchers, registries, runtime plugins, fixpoint/backfeed execution, or
  broad pipeline payload rewrites.
- Moving `LoweredImplementation`, `LoweringInput`, `LoweringRequest`,
  `lower_candidates`, source adapters, exact array-body pipeline
  coordination, or backend/rendering/output-facing behavior.
- Interpreting `emit_return`, `tmp`, `tmp.data()`, `svst1`, `pg`, SVE-looking
  tokens, selected type tags, backend ids, renderer names, or corpus line
  numbers as semantic dispatch keys.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M84.

Required input:

- Accepted M42-M82 lowering behavior.
- The accepted M58 `GenerationLoweringStage` record contract.
- The accepted M59-M76 stage names, ordering, output identities, keys, and
  exact structural/request stage outputs.
- The accepted M77 pipeline snapshot behavior.
- The private module ownership boundaries accepted in M78-M82:
  `_array_body_models`, `_array_body_shapes`, `_array_body_diagnostics`,
  `_array_body_validation`, `_generation_models`, `_generation_queries`,
  `_generation_control_flow`, `_generation_diagnostics`, `_exact_shapes`,
  `_pipeline`, and `_selected_body_models`.
- The accepted M82 `boundary.py` line-count baseline of 4,965 physical lines.

Expected outputs:

- A private typed stage-contract module, or equivalent private ownership
  boundary, containing the accepted stage-to-output compatibility contract.
- The same public `GenerationLoweringStage` values, keys, output identities,
  invalid-stage errors, and invalid-output-type errors as before M83.
- Stable public imports from `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- Stable stage snapshots and `LoweredImplementation` stage tuples.
- `boundary.py` remains the public facade/coordinator and becomes smaller.
- No new semantic IR output.

Parity criterion:

M83 succeeds when stage/output compatibility is owned by a private typed
lowering boundary, public stage imports and accepted stage behavior remain
unchanged, private modules still do not import the facade, `boundary.py` is
smaller than the accepted M82 baseline, and no new lowering semantics or output
behavior are introduced.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for
  `GenerationLoweringStageName`, `GenerationLoweringStageOutput`,
  `GenerationLoweringStage.__post_init__`, stage helper construction, public
  facade exports, `LoweredImplementation`, source adapters, and lower-candidate
  orchestration that must remain behavior-preserving.
- `tslgen/src/tslgen/lowering/_pipeline.py` for accepted stage snapshot and
  dependency behavior that must remain unchanged.
- `tslgen/src/tslgen/lowering/_array_body_models.py`,
  `_selected_body_models.py`, and `_generation_models.py` for private model
  owner patterns and existing output types consumed by the stage contract.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted stage ordering,
  output identity, public import, diagnostic, and deterministic behavior.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M83 tests for every accepted stage/output pairing, including
  representative M42-M76 stage outputs.
- Focused rejection tests for unknown stage names and wrong output object
  types, preserving the same exception classes and message shape.
- Focused public import stability tests for `GenerationLoweringStage`,
  `GenerationLoweringStageName`, and accepted stage output aliases through
  `tslgen.lowering` and `tslgen.lowering.boundary`.
- Focused private-import-boundary tests proving the new private stage-contract
  module and existing private lowering modules do not import `boundary.py` or
  the `tslgen.lowering` package facade.
- Pipeline snapshot/stage identity regression tests proving stage ordering,
  keys, and output object identity remain unchanged.
- A `boundary.py` line-count validation measured against the accepted 4,965
  line M82 baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad TSIL/body/call/store/return/declaration/
  array semantics, raw helper dispatch, catalog reads, `tsldata` reads, host
  CPU queries, backend map reads, import cycles, duplicate moved code, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M83 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m83 or stage_contract or generation_lowering_stage"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Creating a circular import by moving the stage contract into a private module
  that imports `boundary.py` or the package facade.
- Moving too much orchestration, source-adapter behavior, or pipeline execution
  under a "contract extraction" label.
- Accidentally changing stage names, stage ordering, output identities, keys,
  exception classes, or error message shape for invalid stage/output pairings.
- Turning stage contract validation into a broad registry, plugin system,
  semantic dispatcher, or fixpoint/backfeed engine.
- Treating exact return-emission, store-call, selected-body, SVE-looking token,
  backend, renderer, or corpus-line evidence as semantic behavior.
- Reducing line count by moving unrelated exact array-body, generation-helper,
  selected-body, source-adapter, or lower-candidate coordination code.

Dependencies on prior milestones:

- Milestones 42 through 82.

Execution result:

- M83 preserves accepted M42-M82 behavior while moving stage-name/output
  contract ownership into `tslgen.lowering._stage_contracts`.
- The new private module owns `GenerationLoweringStageName`,
  `GenerationLoweringStageOutput`, typed `GenerationLoweringStageOutputContract`
  records, the contract validator, `GenerationLoweringStage`, and the minimal
  accepted mini-TSIL statement value-model dependency needed by the
  stage-output union.
- `boundary.py` remains the public facade/coordinator and re-exports the moved
  public names through existing public paths. Source adapters,
  `LoweredImplementation`, `LoweringInput`, `LoweringRequest`, lower-candidate
  orchestration, and stage construction remain facade-owned.
- Private lowering modules, including `_stage_contracts.py`, do not import
  `boundary.py` or the `tslgen.lowering` package facade.
- Invalid-stage `ValueError`, invalid-output `TypeError`, error message shape,
  stage names/order, output identities, deterministic keys, pipeline snapshots,
  diagnostics, and public imports remain stable.
- `boundary.py` now measures 4,807 physical lines, which is 158 lines below
  the accepted M82 4,965-line baseline.
- No new stage behavior, new lowering semantics, exact return-emission IR,
  return/store/body semantics, helper evaluation, source-adapter behavior,
  backend translation, rendering, generated output, broad parsing, extension
  hardwiring, file/catalog reads, `tsldata` reads, host CPU queries, backend
  map reads, or runtime `frozen/` use were added.
- Review and audit found no blocking implementation, validation, boundary,
  extensibility, documentation, or evidence issues after documentation
  finalization.
- Non-blocking follow-up: package-level alias coverage is intentionally
  unchanged. `tslgen.lowering.boundary` exposes `GenerationLoweringStageName`
  and `GenerationLoweringStageOutput`, while `tslgen.lowering` does not expose
  those aliases. A future public-surface cleanup may either document those
  aliases as boundary-only or explicitly export/test them from
  `tslgen.lowering`.

Next concrete prompt:

- `docs/agent/runs/post-m83-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 84: Exact Array-Body Pipeline And Source Adapter Ownership Extraction Slice

Status:

Accepted. M84 execution-review returned `Accept With Follow-Ups` after one
focused revision.

Goal:

Move the accepted exact array-body staged-lowering pipeline and source-adapter
ownership out of `tslgen/src/tslgen/lowering/boundary.py` into one or more
private typed lowering modules while preserving all accepted M42-M83 behavior,
public imports, diagnostics, stage names/order, output identities, deterministic
keys, and no-external-input boundaries.

M84 is behavior-preserving lowering architecture work. It is the next large
step toward making `boundary.py` a small facade, with a campaign target of
eventually bringing the facade toward roughly 1,000 physical lines. M84 should
make a material reduction from the accepted M83 4,807-line baseline by moving
one cohesive ownership cluster, not by scattering unrelated helpers or adding
compatibility wrappers around poor boundaries.

Scope:

- Create a private exact array-body pipeline/source-adapter ownership module
  such as `tslgen.lowering._array_body_pipeline`,
  `tslgen.lowering._array_body_sources`, or an equivalent small set of
  cohesive private lowering modules.
- Move the accepted exact array-body stage-pipeline result/coordinator and its
  direct helper ownership out of `boundary.py`, including the M64-M76 exact
  array-body pipeline call sequence, stage construction helpers for the exact
  array-body stages, deterministic stage-output/source-location helpers, and
  exact pipeline skeleton lookup/assembly helpers.
- Move the accepted exact array-body source-adapter helpers out of
  `boundary.py`, including adapters for selected-body handoff, selected-body
  IR recognition, selected-body envelope, M63 envelope skeletons, M66-M76
  exact array-initialization outputs, predicate-path structural requests, and
  post-branch intrinsic-call-site structural requests.
- Move exact array-body skeleton validation helpers only when they belong to
  the same private exact array-body source/pipeline ownership boundary and can
  preserve diagnostics exactly.
- Keep `boundary.py` as the public facade for `GenerationContext`,
  `LoweringRequest`, `LoweringInput`, `LoweringInputSet`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, payload classification, mini-TSIL lowering, and public
  import compatibility unless a tiny delegate is required for public lowering
  functions.
- Preserve public API behavior by re-exporting or delegating from
  `tslgen.lowering.boundary` and `tslgen.lowering` where names are already
  public.
- Use only narrow typed protocols for facade-owned values, if needed. Private
  exact array-body modules must not import `boundary.py` or the
  `tslgen.lowering` package facade.
- Preserve accepted source locations, diagnostic codes/messages, stage names,
  stage ordering, stage keys, output object identities, pipeline snapshots,
  selected-branch-only behavior, and deterministic ordering.
- Record the post-M84 `boundary.py` line count. The expected target is a
  substantial reduction from 4,807 physical lines, with review pressure toward
  a facade below roughly 2,000 lines if the exact array-body ownership cluster
  can move without broad protocols or semantic expansion.

Out of scope:

- New semantic lowering behavior, new stage names, new stage outputs, exact
  return-emission IR, `emit_return(tmp)` interpretation, `tmp.data()`
  semantics, store/call/body/return/declaration/array semantics beyond the
  accepted exact structural/request records, broad TSIL parsing, broad source
  skeleton recognition, broad source-adapter support, or helper-family
  expansion.
- Moving `LoweredImplementation`, `LoweringRequest`, `LoweringInput`,
  `LoweringInputSet`, `LoweringPlan`, `lower_candidates`, payload
  classification, or mini-TSIL parsing out of the facade.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  fixpoint/backfeed engines, raw helper dispatch, token-keyed semantic maps,
  or a second monolithic private module.
- Treating SVE-looking tokens, selected type tags, backend ids, renderer
  names, corpus line numbers, request ordinals, or raw source text as semantic
  dispatch keys. Existing exact tokens may move only as structural provenance
  or invariant evidence.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M85 or selecting exact return-emission structural/request IR.

Required input:

- Accepted M42-M83 lowering behavior.
- The accepted M57-M59 generation predicate/control-flow pruning path.
- The accepted M60-M63 selected-body handoff/form/body-IR/envelope values.
- The accepted M64-M76 exact array-body envelope, helper request/resolution,
  declaration shell, predicate-path, and post-branch intrinsic-call-site
  structural/request path.
- The accepted M77 pipeline snapshot behavior and M78-M83 private lowering
  ownership boundaries.
- Private lowering modules `_array_body_models`, `_array_body_shapes`,
  `_array_body_diagnostics`, `_array_body_validation`, `_selected_body_models`,
  `_generation_models`, `_generation_queries`, `_generation_control_flow`,
  `_generation_diagnostics`, `_exact_shapes`, `_pipeline`, and
  `_stage_contracts`.
- The accepted M83 `boundary.py` line-count baseline of 4,807 physical lines.

Expected outputs:

- A private typed exact array-body pipeline/source-adapter ownership boundary
  that does not import `boundary.py` or the `tslgen.lowering` package facade.
- Stable public imports and stable public facade behavior for all accepted
  lowering names.
- The same lowered values, diagnostics, source locations, stage snapshots,
  stage keys, output identities, and deterministic ordering as before M84.
- `boundary.py` remains the public facade/coordinator and becomes materially
  smaller.
- No new semantic IR output and no generated artifact changes.

Parity criterion:

M84 succeeds when exact array-body pipeline/source-adapter ownership is private
and typed, `boundary.py` remains only the public facade/coordinator for this
slice, accepted behavior and public imports are unchanged, private lowering
modules still have one-way imports away from the facade, and the line-count
reduction is achieved by moving the cohesive exact array-body ownership
cluster rather than by duplicating code or adding broad protocols.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the accepted exact array-body
  pipeline implementation, source adapters, stage builders, skeleton lookup,
  validation helpers, public facade imports, and lower-candidate orchestration
  that must remain behavior-preserving.
- `tslgen/src/tslgen/lowering/_stage_contracts.py` for accepted stage/output
  contracts and import-boundary patterns.
- `tslgen/src/tslgen/lowering/_array_body_models.py`,
  `_array_body_shapes.py`, `_array_body_diagnostics.py`,
  `_array_body_validation.py`, `_selected_body_models.py`, `_exact_shapes.py`,
  and `_pipeline.py` for accepted private exact array-body model, validation,
  shape, and pipeline dependencies.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted stage ordering,
  output identity, diagnostic, source-location, no-reparse, import-boundary,
  and deterministic behavior.
- `tsldata/primitives/load_store/array.tsl:105-111` as shape/provenance
  evidence only, not a runtime input or semantic dispatch source.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M84 tests proving the new private exact array-body pipeline/source
  module or modules do not import `boundary.py` or the package facade.
- Focused M84 tests proving public imports and public facade calls still
  return the accepted exact array-body values and stage outputs.
- Focused M84 tests for representative direct typed values, stage output
  values, and `LoweredImplementation`-like stage tuples consumed by moved
  source adapters.
- Focused M84 diagnostic preservation tests for representative unsupported,
  missing, duplicate, conflict, orphan, and provenance-mismatch source cases.
- Focused M84 pipeline snapshot tests proving stage ordering, keys, output
  object identity, selected-branch-only behavior, and deterministic source
  locations remain unchanged.
- A `boundary.py` line-count validation measured against the accepted M83
  4,807-line baseline.
- Regression tests or existing tests proving no backend translation, rendering,
  generated output, broad TSIL/body/call/store/return/declaration/array
  semantics, raw helper dispatch, catalog reads, `tsldata` reads, host CPU
  queries, backend map reads, import cycles, duplicate moved code, or runtime
  `frozen/` use is introduced.

Golden fixtures required:

- None. M84 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m84 or array_body_pipeline or array_body_sources or array_body_lowering or source_adapter or exact_array"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Creating a circular import by moving exact array-body helpers into a private
  module that imports `boundary.py` or the package facade.
- Moving too much facade state, such as `LoweredImplementation`,
  `LoweringRequest`, `lower_candidates`, payload classification, or mini-TSIL
  parsing, under an exact array-body ownership label.
- Turning moved source adapters into a raw-helper dispatcher, registry,
  callback map, plugin system, or token-keyed semantic table.
- Broadening protocols so much that they hide public facade ownership problems
  or reintroduce structural `hasattr` seams.
- Accidentally changing diagnostics, source locations, stage names, stage
  ordering, output identities, keys, selected-branch-only behavior, or
  pipeline snapshots while moving code.
- Treating exact return-emission, store-call, selected-body, SVE-looking token,
  backend, renderer, or corpus-line evidence as semantic behavior.
- Reducing line count by duplicating moved code, creating a second monolith, or
  mixing unrelated generation, selected-body, mini-TSIL, backend, or renderer
  work into M84.

Dependencies on prior milestones:

- Milestones 42 through 83.

Execution result:

- M84 preserves accepted M42-M83 behavior while moving exact array-body
  pipeline/source-adapter ownership into private typed lowering modules:
  `tslgen.lowering._array_body_pipeline`,
  `tslgen.lowering._array_body_sources`, and
  `tslgen.lowering._array_body_lowering`.
- `boundary.py` remains the public facade/coordinator for request/result
  models, selected-body public lowerers, `lower_candidates`, payload
  classification, and mini-TSIL lowering.
- Private exact array-body modules do not import `boundary.py` or the
  `tslgen.lowering` package facade.
- Public imports, diagnostics, source locations, stage names/order, output
  identities, deterministic keys, selected-branch-only behavior, and pipeline
  snapshots remain stable.
- `boundary.py` now measures 1,898 physical lines, which is 2,909 lines below
  the accepted M83 4,807-line baseline. The new private module counts are
  `_array_body_pipeline.py` 835 lines, `_array_body_sources.py` 1,022 lines,
  and `_array_body_lowering.py` 1,378 lines.
- No new lowering semantics, exact return-emission IR, backend translation,
  rendering, generated output, extension-specific shortcuts, lowering-time
  file/catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
  runtime `frozen/` use were added.
- Review and audit found no blocking implementation, validation, boundary,
  extensibility, documentation, or evidence issues after one focused revision.
- Non-blocking follow-ups: continue the longer campaign toward a roughly
  1,000-line facade through cohesive ownership slices, and prevent
  `_array_body_sources.py` or `_array_body_lowering.py` from becoming new
  catch-all modules.

Next concrete prompt:

- `docs/agent/runs/post-m84-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 85: Selected-Body Lowering Ownership Extraction Slice

Status:

Accepted. M85 execution-review returned `Accept` after one focused revision.

Goal:

Move accepted M60-M63 selected-body lowering function/source-helper ownership
out of `tslgen/src/tslgen/lowering/boundary.py` into a focused private typed
lowering module, likely `tslgen.lowering._selected_body_lowering`, while
preserving all accepted M42-M84 behavior, public imports, diagnostics, source
locations, stage names/order, output identities, deterministic keys,
selected-branch-only behavior, pipeline snapshots, and no-external-input
boundaries.

M85 is behavior-preserving lowering architecture work. It closes the ownership
gap left intentionally by M82 and M84: M82 moved selected-body value models
into `_selected_body_models.py`, and M84 left the selected-body public
lowerers in `boundary.py` while extracting exact array-body pipeline/source
ownership. M85 moves one cohesive selected-body lowering ownership cluster
without adding new selected-body semantics or broad body parsing.

Scope:

- Create a focused private selected-body lowering module such as
  `tslgen.lowering._selected_body_lowering`.
- Move the accepted public selected-body lowerer implementations out of
  `boundary.py`:
  - `handoff_opaque_selected_branch_body`
  - `recognize_selected_branch_body_assignment_form`
  - `lower_selected_branch_body_ir`
  - `lower_selected_body_envelope`
- Move only the private helpers directly owned by those lowerers: selected-body
  source coercion helpers, originating branch-chain id construction, selected
  body envelope consistency validation, selected-body assignment-form parsing
  delegation, and selected-body diagnostic helpers.
- Preserve public facade imports and calls through `tslgen.lowering.boundary`
  and `tslgen.lowering` by re-exporting or tiny delegating from the facade.
- Preserve accepted diagnostics, messages, source locations, stage names/order,
  stage keys, output object identities, selected-branch-only behavior,
  deterministic ordering, and pipeline snapshots.
- Keep private-module imports one-way. The new selected-body lowering module
  must not import `boundary.py` or the `tslgen.lowering` package facade.
- Record the post-M85 `boundary.py` line count. The M85 executor measured
  `boundary.py` at 1,417 physical lines and
  `_selected_body_lowering.py` at 538 physical lines. Line-count reduction is
  useful, but the success criterion is cohesive ownership extraction and
  behavior preservation.

Out of scope:

- New lowering semantics, new selected-body semantics, new stage names, new
  stage outputs, exact return-emission IR, `emit_return(tmp)` interpretation,
  `tmp.data()` semantics, store/call/body/return/declaration/array semantics
  beyond accepted exact structural/request records, broad TSIL parsing, broad
  selected-body parsing, broad source-adapter support, or helper-family
  expansion.
- Moving selected-body behavior into `_selected_body_models.py`; that module
  remains the value-model owner.
- Moving `LoweredImplementation`, `LoweringRequest`, `LoweringInput`,
  `LoweringInputSet`, `LoweringPlan`, `_lower_input`, `lower_candidates`,
  payload classification, generation control-flow pruning, exact array-body
  pipeline/source modules, exact array-body lowerers, stage construction for
  mini-TSIL output, or mini-TSIL parsing/lowering out of the facade.
- Importing `_array_body_sources.py` or `_array_body_lowering.py` from the new
  selected-body lowering module as a convenience dispatcher. Use a
  selected-body-local source-location helper or another narrow private helper
  if needed.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  fixpoint/backfeed engines, raw helper dispatch, token-keyed semantic maps,
  or a selected-body framework.
- Treating selected literals, SVE-looking tokens, selected type tags, backend
  ids, renderer names, corpus line numbers, request ordinals, or raw source
  text as semantic dispatch keys. Existing exact tokens may remain structural
  provenance or invariant evidence only.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M86.

Required input:

- Accepted M42-M84 lowering behavior.
- The accepted M57-M59 generation predicate/control-flow pruning path.
- The accepted M60-M63 selected-body handoff/form/body-IR/envelope values and
  diagnostics.
- The accepted M82 private selected-body value-model ownership in
  `_selected_body_models.py`.
- The accepted M83 stage contract boundary in `_stage_contracts.py`.
- The accepted M84 exact array-body pipeline/source/lowering modules and the
  accepted post-M84 `boundary.py` baseline of 1,898 physical lines.

Expected outputs:

- A focused private selected-body lowering ownership module that owns the
  accepted selected-body lowerer implementations and direct private helpers.
- Stable public imports and stable public facade behavior for all accepted
  selected-body lowering names.
- The same typed outputs as before M85:
  `GenerationSelectedBranchBodyHandoff`,
  `GenerationSelectedBranchBodyAssignmentRecognition`,
  `GenerationSelectedBranchBodyIr`,
  `GenerationSelectedBodyEnvelopeIr`, and their existing
  `GenerationLoweringStage` outputs.
- The same lowered values, diagnostics, source locations, stage snapshots,
  stage keys, output identities, selected-branch-only behavior, and
  deterministic ordering as before M85.
- `boundary.py` remains the public facade/coordinator and becomes smaller.
- No new semantic IR output and no generated artifact changes.

Parity criterion:

M85 succeeds when selected-body lowering ownership is private and typed,
`boundary.py` remains the public facade/coordinator for this slice, accepted
behavior and public imports are unchanged, private lowering modules still have
one-way imports away from the facade, and the line-count reduction is achieved
by moving the cohesive selected-body lowering ownership cluster rather than by
duplicating code or adding broad protocols.

Evidence paths:

- `tslgen/src/tslgen/lowering/_selected_body_lowering.py` for the accepted
  selected-body lowerer implementations, selected-body source adapters,
  validation helpers, and selected-body diagnostics.
- `tslgen/src/tslgen/lowering/boundary.py` for public facade imports,
  `_lower_input`, stage construction, and lower-candidate orchestration that
  must remain behavior-preserving.
- `tslgen/src/tslgen/lowering/_selected_body_models.py` for accepted
  selected-body value-model ownership that must remain model-only.
- `tslgen/src/tslgen/lowering/_stage_contracts.py` for accepted stage/output
  contracts and import-boundary patterns.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for the accepted exact
  selected-body assignment-form shape parser used as structural evidence, not
  semantic dispatch.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted selected-body
  behavior, diagnostics, source-location, no-reparse, public import,
  import-boundary, pipeline snapshot, and deterministic behavior.
- `tsldata/primitives/load_store/array.tsl:105-111` as shape/provenance
  evidence only, not a runtime input or semantic dispatch source.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M85 tests proving selected-body public imports and public facade
  calls still return the accepted typed values and diagnostics.
- Focused M85 tests proving the new private selected-body lowering module does
  not import `boundary.py`, the package facade, `_array_body_sources.py`, or
  `_array_body_lowering.py`.
- Update the M84 ownership guard that asserted selected-body lowerers were
  boundary-owned so it now proves stable public facade imports plus private
  selected-body lowering ownership.
- Focused M85 diagnostic preservation tests for selected-body source
  unsupported, provenance missing, body missing, malformed assignment,
  unsupported target/RHS, extra-statement, direct-intrinsic unsupported, and
  selected-body envelope inconsistency cases.
- Pipeline snapshot/stage identity regression tests proving stage ordering,
  keys, output object identity, selected-branch-only behavior, and
  deterministic source locations remain unchanged.
- A `boundary.py` line-count validation measured against the accepted M84
  1,898-line baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad TSIL/body/call/store/return/declaration/
  array semantics, raw helper dispatch, catalog reads, `tsldata` reads, host
  CPU queries, backend map reads, import cycles, duplicate moved code, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M85 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m85 or selected_body_lowering or selected_body_handoff or selected_body_envelope"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Creating a circular import by placing selected-body lowering behavior in
  `_selected_body_models.py` or importing `boundary.py` / the package facade
  from a private module.
- Moving too much facade state, such as `LoweredImplementation`,
  `LoweringRequest`, `_lower_input`, `lower_candidates`, payload
  classification, stage construction for mini-TSIL output, or mini-TSIL
  parsing, under a selected-body ownership label.
- Importing exact array-body source/lowering modules as convenience
  dispatchers from the selected-body lowerer module.
- Turning selected-body lowering into a raw-helper dispatcher, registry,
  callback map, plugin system, token-keyed semantic table, broad source
  adapter, or fixpoint/backfeed engine.
- Accidentally changing diagnostics, source locations, stage names, stage
  ordering, output identities, keys, selected-branch-only behavior, or
  pipeline snapshots while moving code.
- Treating exact return-emission, store-call, selected-body SVE-looking token,
  backend, renderer, or corpus-line evidence as semantic behavior.
- Reducing line count by duplicating moved code, creating another catch-all
  module, or mixing unrelated generation, exact array-body, mini-TSIL,
  backend, or renderer work into M85.

Dependencies on prior milestones:

- Milestones 42 through 84.

Execution result:

- M85 preserves accepted M42-M84 behavior while moving selected-body
  lowerer/source-helper ownership into
  `tslgen.lowering._selected_body_lowering`.
- The new private module owns `handoff_opaque_selected_branch_body`,
  `recognize_selected_branch_body_assignment_form`,
  `lower_selected_branch_body_ir`, `lower_selected_body_envelope`, selected-
  body source coercion helpers, originating branch-chain id construction,
  selected-body envelope consistency validation, selected-body assignment-form
  parsing delegation, selected-body diagnostics, and selected-body-local stage
  output source-location lookup.
- `boundary.py` remains the public facade/coordinator and re-exports the moved
  public names through existing public paths. `LoweredImplementation`,
  `LoweringRequest`, `LoweringInput`, `LoweringInputSet`, `LoweringPlan`,
  `_lower_input`, `lower_candidates`, payload classification, generation
  control-flow pruning, exact array-body pipeline/source modules, exact
  array-body lowerers, and mini-TSIL parsing/lowering remain facade-owned.
- Private lowering modules, including `_selected_body_lowering.py`, do not
  import `boundary.py`, `tslgen.lowering`, `_array_body_sources.py`, or
  `_array_body_lowering.py` as convenience dispatchers.
- Public imports, diagnostics, source locations, stage names/order, output
  identities, deterministic keys, selected-branch-only behavior, and pipeline
  snapshots remain stable.
- The focused revision restored source-location preservation for unsupported
  selected-body handoff diagnostics over `PrunedGenerationBranch` stage
  outputs and added focused regression coverage.
- `boundary.py` now measures 1,417 physical lines, which is 481 lines below
  the accepted M84 1,898-line baseline. `_selected_body_lowering.py` measures
  538 physical lines.
- No new selected-body semantics, broad TSIL/body/call/store/return semantics,
  exact return-emission IR, backend translation, rendering, generated output,
  extension-specific shortcuts, lowering-time file/catalog reads, `tsldata`
  reads, host CPU queries, backend map reads, or runtime `frozen/` use were
  added.
- Review and audit found no blocking implementation, validation, boundary,
  extensibility, documentation, or evidence issues after one focused revision.
- Non-blocking follow-ups: none recorded.

Next concrete prompt:

- `docs/agent/runs/post-m85-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 86: Candidate Payload Intake And Mini-TSIL Leaf Lowering Extraction Slice

Status:

Accepted. M86 execution-review returned `Accept` with no focused revision.

Goal:

Move the accepted candidate payload-intake helpers and accepted mini-TSIL leaf
return lowering implementation out of `tslgen/src/tslgen/lowering/boundary.py`
into focused private typed lowering modules while preserving all accepted
M42-M85 behavior, public imports, diagnostics, source locations, stage
names/order, output identities, deterministic keys, selected-branch-only
behavior, pipeline snapshots, and no-external-input boundaries.

M86 is behavior-preserving lowering architecture work. It broadens the next
`boundary.py` refactor beyond only mini-TSIL regex movement, but it remains one
cohesive ownership slice: candidate payload intake plus the leaf mini-TSIL
return lowerer that consumes that intake. It should make `boundary.py` closer
to a true facade/coordinator without moving the central `_lower_input`
orchestration or adding new semantic lowering.

Scope:

- Create a focused private payload-intake module such as
  `tslgen.lowering._lowering_inputs`.
- Move the accepted payload-intake value/helper cluster out of `boundary.py`:
  `LoweringStrategy`, `PayloadClassification`, `ClassifiedPayload`,
  `LoweringInput`, `_classify_payload`, and
  `_unsupported_payload_diagnostic`.
- Preserve public facade imports and calls through `tslgen.lowering.boundary`
  and `tslgen.lowering` by re-exporting or tiny delegating from the facade.
- Keep `LoweringInputSet`, `LoweringRequest`, `GenerationContext`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, and `_lower_input` facade-owned.
- Create a focused private mini-TSIL leaf-lowering module such as
  `tslgen.lowering._mini_tsil_lowering`.
- Move the accepted mini-TSIL leaf return-lowering cluster out of
  `boundary.py`: the direct parameter-add return regex/helper, the
  `intrin_compose<add>` return regex/helper, mini-TSIL identifier validation,
  argument splitting, declared-parameter validation, and the accepted
  mini-TSIL diagnostics.
- Preserve accepted mini-TSIL behavior exactly:
  `emit_return(<parameter> + <parameter>);` and
  `emit_return(intrin_compose<add>(<parameter>, <parameter>));` remain the only
  semantically lowered mini-TSIL statement shapes.
- Keep private-module imports one-way. The new private modules must not import
  `boundary.py` or the `tslgen.lowering` package facade.
- Preserve the intended import direction:
  `boundary.py -> _lowering_inputs`,
  `boundary.py -> _mini_tsil_lowering`,
  `_mini_tsil_lowering -> _lowering_inputs and _stage_contracts`, and
  `_lowering_inputs -> candidates, diagnostics, result, values` only.
- `_lower_input` may only delegate the accepted payload-classification and
  mini-TSIL leaf return-lowering calls to focused private helpers while
  preserving the existing call order, diagnostics, and stage construction.
- Record the post-M86 `boundary.py` line count against the accepted M85
  1,417-line baseline. Line-count reduction is useful, but the success
  criterion is cohesive ownership extraction and behavior preservation.

Out of scope:

- Moving `LoweringInputSet`, `LoweringRequest`, `GenerationContext`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, `_lower_input`, stage construction, `_context_for_candidate`,
  generation query payload lowering, generation control-flow pruning,
  selected-body lowering, exact array-body lowering, exact array-body pipeline
  orchestration, request/result model ownership, or package-level public
  surface policy beyond stable facade aliases.
- New lowering semantics, new mini-TSIL syntax, broad TSIL parsing, broad
  statement/body/call/store/return/declaration/array semantics,
  exact return-emission IR, `emit_return(tmp)` interpretation, `tmp.data()`
  semantics, variable scope/lifetime semantics, renderer-ready IR, broad
  direct-intrinsic semantics, helper-family expansion, or stage output changes.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  ordered lowerer tables, generic TSIL statement dispatchers,
  fixpoint/backfeed engines, raw text rewrite engines, raw helper dispatch,
  token-keyed semantic maps, broad source-adapter protocols, or a mini-TSIL
  framework.
- Treating selected literals, SVE-looking tokens, selected type tags, backend
  ids, renderer names, corpus line numbers, request ordinals, or raw source
  text as semantic dispatch keys. Existing exact tokens may remain structural
  provenance or invariant evidence only.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M87.

Required input:

- Accepted M42-M85 lowering behavior.
- The accepted M2/M4 catalog payload shapes already consumed by
  `ImplementationCandidate.implementation.body`.
- The accepted M12/M13/M32-M39 mini-TSIL direct parameter-add and
  intrinsic-compose add return behavior.
- The accepted M58/M83 stage contract boundary in `_stage_contracts.py`.
- The accepted post-M85 `boundary.py` baseline of 1,417 physical lines.

Expected outputs:

- A focused private payload-intake module owning the accepted payload
  classification models/helpers and unsupported-payload diagnostics.
- A focused private mini-TSIL leaf-lowering module owning the accepted
  mini-TSIL regexes, return-shape lowerers, parameter validation, and
  mini-TSIL diagnostics.
- Stable public imports and stable public facade behavior for accepted payload
  classification and mini-TSIL lowering paths.
- The same typed `TsilReturnStatement`, `TsilBinaryExpression`,
  `TsilIntrinsicComposeExpression`, and `TsilParameterReference` outputs as
  before M86.
- The same lowered values, diagnostics, source locations, stage snapshots,
  stage keys, output identities, selected-branch-only behavior, and
  deterministic ordering as before M86.
- `boundary.py` remains the public facade/coordinator and becomes smaller.
- No new semantic IR output and no generated artifact changes.

Parity criterion:

M86 succeeds when candidate payload intake and mini-TSIL leaf return lowering
are privately owned behind typed modules, `boundary.py` remains the
facade/coordinator for request/result models and `_lower_input` orchestration,
accepted behavior and public imports are unchanged, private lowering modules
still have one-way imports away from the facade, and the line-count reduction
is achieved by moving cohesive ownership clusters rather than duplicating code
or adding broad protocols.

Evidence paths:

- `tslgen/src/tslgen/lowering/boundary.py` for the accepted payload-intake
  models/helpers, mini-TSIL leaf lowerer, public facade imports,
  `prepare_lowering_inputs`, `_lower_input`, `lower_candidates`, stage
  construction, and lower-candidate orchestration that must remain
  behavior-preserving.
- `tslgen/src/tslgen/lowering/_stage_contracts.py` for accepted
  `TsilReturnStatement`, `TsilBinaryExpression`,
  `TsilIntrinsicComposeExpression`, `TsilParameterReference`, and stage/output
  contracts.
- `tslgen/src/tslgen/lowering/_selected_body_lowering.py` and
  `tslgen/src/tslgen/lowering/_array_body_lowering.py` as import-boundary
  comparators, not as dependencies for the new private modules.
- `tslgen/src/tslgen/lowering/__init__.py` for public lowering imports.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted payload
  classification, typed-opaque strategy, mini-TSIL return lowering,
  diagnostics, public import, import-boundary, pipeline snapshot, and
  deterministic behavior.

Tests required:

- Full `tslgen/tests/unit/test_lowering_boundary.py` preservation.
- Focused M86 tests proving public facade imports and calls for payload intake
  and mini-TSIL lowering still return the accepted values and diagnostics.
- Focused M86 tests proving the new private payload-intake and mini-TSIL
  modules do not import `boundary.py`, the package facade, selected-body
  lowering modules, exact array-body lowering modules, backend modules, or
  renderers.
- Focused M86 tests preserving diagnostics for non-text TSIL payloads,
  typed-opaque TSIL payloads, unsupported payload kinds, unsupported
  `emit_return` shapes, malformed `intrin_compose`, unsupported intrinsic
  names, invalid intrinsic arguments, invalid intrinsic arity, and unknown
  parameter names.
- Pipeline snapshot/stage identity regression tests proving stage ordering,
  keys, output object identity, selected-branch-only behavior, and
  deterministic source locations remain unchanged.
- A `boundary.py` line-count validation measured against the accepted M85
  1,417-line baseline.
- Regression tests or existing tests proving no backend translation,
  rendering, generated output, broad TSIL/body/call/store/return/declaration/
  array semantics, raw helper dispatch, catalog reads, `tsldata` reads, host
  CPU queries, backend map reads, import cycles, duplicate moved code, or
  runtime `frozen/` use is introduced.

Golden fixtures required:

- None. M86 is behavior-preserving lowering architecture work and must not
  change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m86 or lowering_input or payload_classification or mini_tsil or typed_opaque"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally moving `_lower_input`, `lower_candidates`, request/result model
  ownership, generation query payload lowering, stage construction,
  selected-body lowering, or exact array-body orchestration under a payload or
  mini-TSIL ownership label.
- Creating a circular import by importing `boundary.py` or `tslgen.lowering`
  from the new private modules.
- Turning mini-TSIL lowering into a broad TSIL parser, statement dispatcher,
  raw text rewrite engine, registry, callback map, plugin system, token-keyed
  semantic table, or fixpoint/backfeed engine.
- Accidentally changing diagnostics, source locations, stage names, stage
  ordering, output identities, keys, selected-branch-only behavior, typed
  opaque behavior, payload classification keys, or pipeline snapshots while
  moving code.
- Treating exact return-emission, store-call, selected-body SVE-looking token,
  backend, renderer, or corpus-line evidence as semantic behavior.
- Reducing line count by duplicating moved code, creating another catch-all
  module, or mixing unrelated generation, selected-body, exact array-body,
  backend, or renderer work into M86.

Dependencies on prior milestones:

- Milestones 42 through 85.

Execution result:

- M86 preserves accepted M42-M85 behavior while moving candidate
  payload-intake ownership into `tslgen.lowering._lowering_inputs` and
  mini-TSIL leaf return-lowering ownership into
  `tslgen.lowering._mini_tsil_lowering`.
- `_lowering_inputs.py` owns `LoweringStrategy`, `PayloadClassification`,
  `ClassifiedPayload`, `LoweringInput`, `_classify_payload`, and
  `_unsupported_payload_diagnostic`.
- `_mini_tsil_lowering.py` owns the accepted direct parameter-add and
  `intrin_compose<add>` mini-TSIL leaf return lowerers, including the
  accepted regexes, argument splitting, declared-parameter validation, and
  mini-TSIL diagnostics.
- `boundary.py` remains the public facade/coordinator for request/result
  models, `LoweringInputSet`, `prepare_lowering_inputs`, `_lower_input`,
  `lower_candidates`, stage construction, generation query/control-flow
  staging, selected-body lowering, and exact array-body pipeline
  orchestration.
- Private lowering modules keep the planned one-way import direction:
  `boundary.py -> _lowering_inputs`,
  `boundary.py -> _mini_tsil_lowering`,
  `_mini_tsil_lowering -> _lowering_inputs and _stage_contracts`, and
  `_lowering_inputs -> candidates, diagnostics, result, values`.
- Public imports, diagnostics, source locations, stage names/order, output
  identities, deterministic keys, selected-branch-only behavior, typed-opaque
  behavior, payload classification keys, and pipeline snapshots remain stable.
- `boundary.py` now measures 1,145 physical lines, which is 272 lines below
  the accepted M85 1,417-line baseline. `_lowering_inputs.py` measures
  128 physical lines and `_mini_tsil_lowering.py` measures 188 physical lines.
- No new TSIL syntax, broad return/body/call/store semantics, exact
  return-emission IR, backend translation, rendering, generated output,
  extension-specific shortcuts, lowering-time file/catalog reads, `tsldata`
  reads, host CPU queries, backend map reads, or runtime `frozen/` use were
  added.
- Review and audit found no blocking implementation, validation, boundary,
  extensibility, documentation, or evidence issues after finalization.
- Non-blocking follow-ups: exact return-emission structural/request IR was
  identified as the next high-value semantic frontier after the facade cleanup;
  M87 addressed that follow-up.

### Milestone 87: Exact Return-Emission Structural Request IR Slice

Status:

Accepted. M87 execution-review returned `Accept With Follow-Ups` after one
focused maintainability revision.

Goal:

Add the next lowering semantic frontier after the M77-M86 facade/module cleanup:
record the exact trailing return-emission-shaped slot from the accepted exact
array-body path as typed structural/request IR. M87 recognizes only the exact
source form shaped as `emit_return(tmp);` with insignificant whitespace, links
the returned token to the accepted M73 declaration-shell variable token, and
keeps the result structural/request-only.

This is not a `.tsl` body repair milestone. If the source body is wrong,
nearby, malformed, or merely resembles the selected form, M87 must emit a
structured diagnostic instead of correcting or broadening the accepted shape.

Scope:

- Add a typed exact return-emission structural/request IR value, such as
  `ExactReturnEmissionStructuralRequestIr`, behind the private exact array-body
  lowering boundary.
- Consume accepted M74 `ExactArrayBodyStructuralSequenceIr` provenance and the
  accepted M76 post-branch intrinsic call-site structural request as typed
  inputs so the return-emission request is ordered after the accepted
  post-branch call-site path without interpreting store semantics.
- Recognize only the M74 role ordinal `4` /
  `opaque_return_emission_shaped_slot` source text with the exact
  `emit_return(<token>);` shape, allowing insignificant whitespace.
- Require the returned token text to match the accepted M73 declaration-shell
  variable token carried by the M74 sequence. This is provenance linkage only,
  not variable lifetime, allocation, or return-value semantics.
- Add a deterministic `return_emission_structural_request_lowering` stage after
  the accepted post-branch call-site stage in the exact array-body pipeline.
- Preserve public facade imports through `tslgen.lowering.boundary` and
  `tslgen.lowering` if new public aliases are exposed; otherwise keep new
  model/lowering helpers private and test the public pipeline result.
- Keep implementation cohesive. If existing exact array-body modules would grow
  into catch-all files, create a focused private return-emission module with
  one-way imports rather than adding a large new cluster to an already
  substantial file.

Out of scope:

- Correcting, normalizing, rewriting, completing, reordering, or guessing the
  intended meaning of malformed `.tsl` implementation bodies.
- Supporting broad `emit_return(...)`, expressions inside `emit_return`,
  multiple return statements, missing semicolons, alternate variables,
  `tmp.data()`, stores, calls, direct `intrin<...>` semantics, variable
  lifetime/scope, allocation semantics, array value semantics, or return-value
  semantics.
- Backend translation, renderer-ready return IR, rendering, generated C++ or
  Rust output, generated tests, golden files, CLI/report/writer behavior,
  compiler execution, or generated-test execution.
- Broad TSIL parsing, source-file reads during lowering, catalog reads,
  `tsldata` reads, backend map reads, host CPU queries, runtime dependency on
  `frozen/`, registries, dispatchers, plugin systems, raw text rewrite
  engines, raw helper dispatch, or fixpoint/backfeed machinery.
- Moving unrelated request/result models, `LoweringInputSet`,
  `prepare_lowering_inputs`, `_lower_input`, `lower_candidates`, selected-body
  lowering, generation query/control-flow staging, or broad exact array-body
  orchestration out of `boundary.py`.

Required input:

- Accepted M64-M65 exact array-body envelope and pipeline integration.
- Accepted M73 declaration-shell structural IR and declaration variable token.
- Accepted M74 source-ordered array-body structural sequence with role ordinal
  `4` / `opaque_return_emission_shaped_slot` provenance.
- Accepted M75 predicate-path and M76 post-branch call-site structural request
  values as typed ordering/provenance inputs.
- Accepted M84 exact array-body pipeline/source/lowering module boundaries and
  M86 public facade behavior.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:104-112`, especially the trailing
  `emit_return(tmp) ;` shape at line 111.

Expected outputs:

- A typed exact return-emission structural/request IR value carrying:
  source sequence identity, post-branch call-site identity, return role label,
  slot ordinal `4`, source location, original source text, `emit_return` token,
  returned token text, declaration-shell variable-token link, candidate id,
  target extension, source extension, selected type tag, and branch-chain id.
- Deterministic key/provenance behavior matching accepted M74-M86 conventions.
- A pipeline stage snapshot entry for the exact return-emission structural
  request when the exact shape is present.
- Structured diagnostics for unsupported source, missing return slot, malformed
  return-emission shape, returned-token mismatch, context mismatch, and
  provenance mismatch.
- No backend/rendering/output artifacts and no semantic correction of source
  bodies.

Parity criterion:

M87 succeeds when the accepted exact array-body lowering path can carry a typed
return-emission structural/request value for the selected corpus shape, while
unsupported or malformed nearby forms produce diagnostics. The new IR must be
proof that lowering can identify the exact return-emission slot as data; it
must not be proof that return semantics or generated output are implemented.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:104-112` for the selected exact
  source shape.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for M73-M76 typed exact
  array-body model ownership and the new request model location or import
  boundary.
- `tslgen/src/tslgen/lowering/_array_body_lowering.py` and, if created, a
  focused private return-emission module for the exact recognizer/lowerer.
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py` for deterministic
  stage wiring and pipeline snapshot identity.
- `tslgen/src/tslgen/lowering/_exact_shapes.py` for exact structural token
  constants/regexes, if the implementation adds a focused exact return shape.
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py` and
  `_array_body_validation.py` for diagnostic and input-boundary ownership.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted M64-M86
  lowering behavior, exact array-body pipeline snapshots, diagnostics, and
  import-boundary tests.

Tests required:

- Focused M87 positive tests for the exact `emit_return(tmp);` shape with
  whitespace matching the selected corpus style.
- Tests proving the returned token links to the accepted declaration-shell
  variable token and does not infer a different variable or repair source
  text.
- Negative tests for malformed `emit_return`, wrong returned token, missing
  semicolon, extra arguments/expression forms, missing return slot, wrong slot
  ordinal/source role, context mismatch, and provenance mismatch.
- Pipeline tests proving the new stage appears after the M76 post-branch
  call-site stage, preserves stage order, keys, output object identity,
  source locations, deterministic ordering, and selected-branch-only behavior.
- Import-boundary tests if a new private return-emission module is created:
  it must not import `boundary.py`, `tslgen.lowering`, backend modules,
  renderers, or unrelated exact array-body modules as convenience dispatchers.
- Full lowering-boundary preservation plus focused mypy and tooling
  validation.

Golden fixtures required:

- None. M87 must not change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_return_emission.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_return_emission.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m87 or return_emission or exact_array_body_pipeline"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally implementing return semantics, variable lifetime/scope,
  `tmp.data()`, store-call semantics, backend translation, or renderer-ready
  return IR instead of structural/request IR.
- Treating malformed source as something to correct rather than diagnose.
- Generalizing to broad `emit_return(...)` parsing or a TSIL statement
  dispatcher.
- Using raw helper text, extension names, SVE tokens, corpus line numbers,
  backend ids, renderer names, or request ordinals as direct semantic dispatch
  shortcuts.
- Adding another catch-all lowering module or growing an existing exact
  array-body module without a focused ownership boundary.
- Changing accepted diagnostics, source locations, stage names/order, output
  identities, keys, selected-branch-only behavior, public imports, or pipeline
  snapshots from M64-M86.

Dependencies on prior milestones:

- Milestones 64 through 86.

Execution result:

- M87 implements exact return-emission structural/request IR as
  `ExactReturnEmissionStructuralRequestIr`.
- The focused private module `tslgen.lowering._return_emission` owns the M87
  lowerer. It consumes direct M76 post-branch call-site values, the M76 stage
  output, or a private M76-only source protocol; the focused revision removed
  M87 output from the shared runtime `ExactArrayBodyLoweredImplementationSource`
  protocol so the central source adapter does not grow with downstream stages.
- The exact recognizer accepts only `emit_return(<token>);` with insignificant
  whitespace, and M87 requires that token to match the accepted M73
  declaration-shell variable token. The selected corpus shape
  `emit_return(tmp) ;` is accepted through this structural rule.
- The exact array-body pipeline now appends
  `return_emission_structural_request_lowering` after the accepted M76
  post-branch call-site stage. Pipeline snapshots record the produced
  `return_emission_structural_request` fact and preserve identity, keys, and
  deterministic ordering.
- Public facade exports expose `ExactReturnEmissionStructuralRequestIr` and
  `lower_exact_return_emission_structural_request` through
  `tslgen.lowering.boundary` and `tslgen.lowering`.
- M87 added diagnostics for unsupported sources, missing or multiple source IR
  when lowering from a lowered implementation, context mismatch, missing return
  slot, malformed return-emission shape, returned-token mismatch, and
  provenance mismatch.
- M87 added focused tests for exact accepted whitespace, M76 source forms,
  returned-token/declaration linkage, unsupported source and context
  diagnostics, malformed nearby forms, wrong token, missing slot, provenance
  mismatch, selected-candidate-only behavior, pipeline stage ordering,
  snapshot identity, and import boundaries.
- M87 did not repair source bodies, broaden `emit_return(...)`, implement
  return-value semantics, variable lifetime/scope, `tmp.data()`, store/call
  semantics, backend translation, renderer-ready IR, rendering, generated
  output, generated tests, CLI/report/writer behavior, Rust, compiler
  execution, broad TSIL parsing, raw helper dispatch, file/catalog reads,
  `tsldata` reads during lowering evaluation, backend map reads, host CPU
  queries, or runtime `frozen/` use.
- Line counts after M87 are `boundary.py` 1,163,
  `_array_body_models.py` 2,629, `_array_body_lowering.py` 1,378,
  `_array_body_pipeline.py` 890, and `_return_emission.py` 112.
- Validation completed with focused M87 tests returning
  `6 passed, 286 deselected in 2.18s`, the full lowering-boundary suite
  returning `292 passed in 39.25s`, focused lowering mypy returning
  `Success: no issues found in 22 source files`, and full tooling validation
  returning exit 0 with corpus probes `3 passed`, unit discovery `626` tests
  OK, compileall OK, ruff OK, mypy `Success: no issues found in 126 source
  files`, and diff-check OK.
- Non-blocking follow-ups: improve the returned-token mismatch diagnostic to
  include the actual and expected token text; future exact array-body stages
  should continue splitting stage-specific source/validation/diagnostic
  ownership instead of growing central exact array-body modules; future import
  boundary tests may prefix-match backend/rendering submodules and include
  `frozen` / `tsldata`.

Next concrete prompt:

- `docs/agent/runs/post-m87-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 88: Exact Array Body Structural Package Assembly Slice

Status:

Accepted. The M88 execution-review loop returned `Accept With Follow-Ups`
after one focused extensibility revision for malformed protocol-shaped M87
source entries.

Goal:

Assemble the accepted exact array-body structural/request facts into one typed,
source-ordered structural package for the selected `array.tsl:105-111` body
shape. M88 is a lowering package assembly step: it makes the M64-M87 typed
facts consumable as one coherent Stage 8 handoff while preserving their
structural-only meaning.

M88 must not claim that the array body is semantically lowered. It proves only
that the exact accepted body structure has been assembled as typed lowering
state from already accepted facts.

Scope:

- Add a typed exact array-body structural package value, such as
  `ExactArrayBodyStructuralPackageIr`, behind a focused private lowering
  ownership boundary.
- Prefer a focused private module such as
  `tslgen.lowering._array_body_package` for package assembly, source
  selection, and package-specific diagnostics rather than growing central exact
  array-body modules into catch-all files.
- Consume accepted typed facts only:
  M64/M65 exact array-body envelope state, M72 helper-set completion, M73
  declaration-shell structural IR, M74 source-ordered structural sequence,
  M75 predicate-path structural request, M76 post-branch intrinsic call-site
  structural request, and M87 return-emission structural request.
- Validate that the package members belong to the same candidate, source
  envelope/sequence, branch path, target extension, source extension, selected
  type tag, and source-ordered exact body.
- Preserve object identity/provenance for the packaged member facts instead of
  copying or normalizing them into semantic body nodes.
- Add one deterministic package-assembly stage after
  `return_emission_structural_request_lowering`, such as
  `array_body_structural_package_assembly`.
- Preserve public facade imports through `tslgen.lowering.boundary` and
  `tslgen.lowering` if a new public alias is exposed; otherwise keep the new
  helper private and test the public pipeline result.

Out of scope:

- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, generic body IR, generic statement packages, source-body
  repair, raw helper dispatch, registries, callback maps, plugin systems,
  dispatch tables keyed by raw text, or fixpoint/backfeed machinery.
- Declaration semantics, array semantics, variable lifetime/scope, allocation
  semantics, initializer behavior, store semantics, return-value semantics,
  `tmp.data()` pointer semantics, `emit_return` semantics, `assume_aligned`
  semantics, `intrin<svst1>` semantics, SVE predicate/vector/register
  semantics, memory behavior, or broad direct-intrinsic semantics.
- Backend uninit translation, backend map reads, backend translation, renderer-
  ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, catalog reads during
  lowering, `tsldata` reads during lowering evaluation, host CPU queries, or
  runtime dependency on `frozen/`.
- Moving unrelated request/result models, `LoweringInputSet`,
  `prepare_lowering_inputs`, `_lower_input`, `lower_candidates`, selected-body
  lowering, generation query/control-flow staging, or broad exact array-body
  orchestration out of `boundary.py`.

Required input:

- Accepted M64/M65 exact array-body envelope and pipeline integration.
- Accepted M72 array-initialization helper-set completion, including the
  deferred `value<backend>(uninit::array)` backend-value boundary as data only.
- Accepted M73 declaration-shell structural IR and declaration variable token.
- Accepted M74 source-ordered array-body structural sequence.
- Accepted M75 predicate-path structural request.
- Accepted M76 post-branch intrinsic call-site structural request.
- Accepted M87 return-emission structural request.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

Expected outputs:

- A typed exact array-body structural package value carrying stable package
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, source sequence identity, and
  references to the accepted member facts.
- A source-ordered package member sequence that preserves the accepted exact
  declaration, predicate path, selected-body/predicate update evidence,
  post-branch call-site, and return-emission structural/request facts.
- Deterministic key/provenance behavior matching accepted M64-M87
  conventions.
- A pipeline stage snapshot entry for the package-assembly stage.
- Structured diagnostics for unsupported source, missing member facts,
  duplicate member facts, source/order mismatch, context mismatch, and
  provenance mismatch.

Parity criterion:

M88 succeeds when the accepted exact array-body lowering path produces one
typed structural package over the accepted M64-M87 facts and rejects missing,
duplicate, mismatched, or provenance-inconsistent inputs with diagnostics. It
must not produce backend/rendering/output artifacts or semantic body nodes.

Execution result:

- Added focused `tslgen.lowering._array_body_package` ownership for
  `ExactArrayBodyStructuralPackageIr`, package members, source selection, and
  package diagnostics.
- Added the deterministic `array_body_structural_package_assembly` stage after
  `return_emission_structural_request_lowering`.
- The package consumes accepted typed M64-M87 facts, preserves member object
  identity/provenance, validates candidate/source-extension/target-extension/
  selected-type/source-order consistency, and returns diagnostics for missing,
  duplicate, malformed, mismatched, or provenance-inconsistent facts.
- The focused revision treats protocol-shaped
  `return_emission_structural_requests` entries as untrusted runtime data and
  diagnoses malformed entries instead of raising attribute errors.
- M88 remains structural aggregation/provenance validation only; it did not
  add source-body repair, semantic body lowering, declaration/store/return/
  SVE/backend semantics, renderer-ready IR, rendering, generated output, broad
  TSIL parsing, broad dispatch, hidden backfeeds, or runtime `frozen/` use.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105-111` for the exact source
  body shape.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for accepted M72-M87
  typed fact ownership and the new package model location or import boundary.
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py` for deterministic
  stage wiring and pipeline snapshot identity.
- `tslgen/src/tslgen/lowering/_return_emission.py` for the focused M87 stage
  ownership pattern that M88 followed.
- `tslgen/src/tslgen/lowering/_pipeline.py` and
  `_stage_contracts.py` for stage/output contract updates.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted exact array-body
  pipeline behavior, diagnostics, and import-boundary tests.

Tests required:

- Focused positive M88 tests for package assembly from accepted M64-M87 facts.
- Tests proving source-ordered member identity/provenance is preserved and the
  package does not clone facts into semantic body nodes.
- Negative tests for missing, duplicate, mismatched, out-of-order, and
  provenance-inconsistent member facts.
- Pipeline tests proving the new package stage appears after
  `return_emission_structural_request_lowering`, preserves stage order, keys,
  output object identity, source locations, deterministic ordering, selected-
  branch-only behavior, and pipeline snapshots.
- Import-boundary tests proving any focused package module does not import
  `boundary.py`, `tslgen.lowering`, backend modules, renderers, `tsldata`,
  `frozen`, or unrelated private modules as convenience dispatchers.
- Full lowering-boundary preservation plus focused mypy and tooling
  validation.

Golden fixtures required:

- None. M88 must not change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m88 or structural_package or exact_array_body_pipeline"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally treating package assembly as semantic array-body lowering.
- Re-parsing raw source text or repairing malformed body shapes instead of
  consuming accepted typed facts.
- Inferring declaration, store, return, pointer, memory, SVE, backend, or
  renderer semantics from structural tokens.
- Adding a broad body package, generic TSIL parser, raw-helper dispatcher,
  registry, callback map, plugin system, broad protocol, or fixpoint/backfeed
  engine.
- Growing `_array_body_models.py`, `_array_body_sources.py`,
  `_array_body_validation.py`, `_array_body_diagnostics.py`, or
  `_array_body_pipeline.py` into catch-all modules instead of adding focused
  package ownership.
- Changing accepted diagnostics, source locations, stage names/order, output
  identities, keys, selected-branch-only behavior, public imports, or pipeline
  snapshots from M64-M87.

Dependencies on prior milestones:

- Milestones 64 through 87.

Next concrete prompt:

- Post-M88 planning selected Milestone 89. The next concrete prompt is
  `docs/agent/runs/post-m88-acceptance-finalization-prompt.md`, which records
  human acceptance before creating an M89 execution-review loop prompt.

### Milestone 89: Exact Array Backend-Deferred Request Inventory Slice

Status:

Accepted. The M89 execution-review loop returned `Accept With Follow-Ups` with
no blocking implementation, validation, boundary, documentation, or evidence
issues and no focused revision.

Goal:

Consume the accepted M88 exact array-body structural package and produce one
typed, source-ordered inventory of backend-deferred requests for the exact
selected `array.tsl:105-111` body. The first and only supported inventory
member is the accepted M72/M67 `value<backend>(uninit::array)` deferred
backend-value boundary.

M89 gives later backend-planning work one stable typed handoff for deferred
backend-value facts without resolving those facts. It is still Stage 8
lowering inventory/provenance validation, not backend translation or semantic
array-body lowering.

Scope:

- Add focused private ownership, such as
  `tslgen.lowering._array_body_backend_deferred_requests`, for exact array
  backend-deferred request inventory assembly, source selection, and
  inventory-specific diagnostics.
- Consume accepted M88 `ExactArrayBodyStructuralPackageIr` values, the
  `array_body_structural_package_assembly` stage output, or one narrowly
  validated package-only source carrying exactly one accepted M88 package.
- Produce a typed inventory value, such as
  `ExactArrayBackendDeferredRequestInventoryIr`, containing exactly one typed
  member for the accepted `value_backend_uninit_array` deferred backend-value
  fact.
- Preserve object identity/provenance from M88 package to M73 declaration
  shell, M72 `ExactArrayInitializationDeferredBackendUninitValue`, and the M67
  `ExactArrayInitializationHelperRequestRecord`.
- Validate candidate id, target extension, source extension, selected type
  tag, branch-chain id, variable token, slot identity, source location, request
  ordinal, request kind, helper leaf kind, source text provenance, and
  `deferred_backend_value` policy.
- Add one deterministic stage after `array_body_structural_package_assembly`,
  such as `array_backend_deferred_request_inventory`.
- Treat any protocol-shaped/runtime source entries as untrusted until concrete
  typed M88 package payloads are validated.
- Preserve accepted M64-M88 diagnostics, source locations, stage names/order,
  output identities, deterministic keys, selected-branch-only behavior, public
  imports, and pipeline snapshots.

Out of scope:

- Resolving, translating, normalizing, rendering, or otherwise interpreting
  `value<backend>(uninit::array)` beyond preserving the accepted deferred
  backend-value policy and typed provenance.
- Backend map reads, backend catalog reads, `tsldata/detail/lang` reads,
  backend translation, Stage 9 backend planning, renderer-ready IR, rendering,
  generated C++ or Rust output, generated tests, CLI/report/writer behavior,
  compiler execution, or Rust.
- Generic `value<backend>(...)`, `type<backend>(...)`, backend modifier, or
  backend helper evaluation.
- Declaration semantics, array semantics, allocation/lifetime, initializer
  behavior, variable scope, store semantics, return semantics, `tmp.data()`
  pointer semantics, SVE predicate/vector/register semantics, memory behavior,
  direct-intrinsic semantics, or broad body semantics.
- Inventorying generic backend-ish unresolved tokens such as `svst1`,
  `tmp.data()`, `svptrue_b*`, `emit_return`, or unrelated selected-body facts.
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, raw helper dispatch, registries, callback maps, plugin
  systems, dispatch tables keyed by raw helper text/backend id/extension/type
  tag/corpus line number, reflection over package members, hidden backfeeds, or
  fixpoint execution.
- Growing `_array_body_models.py`, `_array_body_package.py`,
  `_array_body_pipeline.py`, or central facade modules into catch-all
  ownership.

Required input:

- Accepted M88 `ExactArrayBodyStructuralPackageIr`.
- Accepted M72 `ExactArrayInitializationHelperSetCompletionIr`, including
  accepted `ExactArrayInitializationDeferredBackendUninitValue` with policy
  `deferred_backend_value`.
- Accepted M67 backend-value request record for
  `value<backend>(uninit::array)`.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

Expected outputs:

- A typed exact array backend-deferred request inventory value carrying stable
  inventory identity, source location/provenance, candidate id, target
  extension, source extension, selected type tag, branch-chain id, source
  package identity, and the accepted M88 package reference.
- A typed inventory member carrying kind `value_backend_uninit_array`, request
  kind `backend_value`, policy `deferred_backend_value`, source location, and
  references to the accepted M72 deferred backend-uninit value and M67 request
  record.
- Deterministic key/provenance behavior matching accepted M64-M88 conventions.
- A pipeline stage snapshot entry for the inventory stage.
- Structured diagnostics for unsupported source, missing package, duplicate
  package, malformed package entry, context mismatch, missing/wrong
  backend-uninit boundary, wrong policy, source/provenance mismatch, and
  attempted non-exact backend-deferred member inventory.

Parity criterion:

M89 succeeds when the accepted exact array-body lowering path produces one
typed backend-deferred request inventory over the accepted M88 package and M72
backend-uninit boundary, while rejecting missing, duplicate, malformed,
mismatched, or provenance-inconsistent inputs with diagnostics. It must not
resolve backend values, create renderer-ready IR, or produce generated output.

Execution result:

- Added focused `tslgen.lowering._array_body_backend_deferred_requests`
  ownership for exact array backend-deferred request inventory assembly,
  source selection, validation, and inventory diagnostics.
- Added `ExactArrayBackendDeferredRequestInventoryIr` and
  `ExactArrayBackendDeferredRequestInventoryMemberIr` for the single accepted
  `value_backend_uninit_array` inventory member.
- Added deterministic `array_backend_deferred_request_inventory` stage wiring
  after `array_body_structural_package_assembly`.
- Preserved object identity/provenance for the accepted M88 package, M73
  declaration shell, M72 deferred backend-uninit value, and M67 backend-value
  request record.
- Added diagnostics and tests for unsupported, missing, duplicate, malformed,
  context-mismatched, wrong-policy, wrong-request, wrong-source-text,
  source-location, slot/variable, and provenance-mismatched inputs.
- M89 remained Stage 8 inventory/provenance validation only; it did not add
  backend map reads, backend-uninit resolution, backend translation, Stage 9
  backend planning, renderer-ready IR, rendering, generated output, or generic
  backend-value evaluation.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105-111` for the exact selected
  array body and its `value<backend>(uninit::array)` leaf.
- `tslgen/src/tslgen/lowering/_array_body_models.py` for accepted M67 request
  records, M72 deferred backend-uninit values, and helper-set completion
  models.
- `tslgen/src/tslgen/lowering/_array_body_package.py` for accepted M88 package
  input ownership and provenance.
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py` for deterministic stage
  wiring and pipeline snapshot identity.
- `tslgen/src/tslgen/lowering/_pipeline.py` and
  `tslgen/src/tslgen/lowering/_stage_contracts.py` for stage/output contract
  updates.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted exact array-body
  pipeline behavior, diagnostics, import-boundary tests, and new M89 coverage.

Tests required:

- Focused positive M89 tests for direct M88 package input, M88 stage-output
  input, and narrowly validated one-package source input.
- Tests proving the inventory contains exactly one `value_backend_uninit_array`
  member and preserves object identity for the M88 package, M72 deferred value,
  and M67 backend-value request record.
- Negative tests for unsupported source, missing package, duplicate package,
  malformed protocol-shaped package entries, context mismatch, missing or wrong
  backend-uninit boundary, wrong request ordinal/kind/leaf/source text, wrong
  `deferred_backend_value` policy, and provenance mismatch.
- Pipeline tests proving the new inventory stage appears after
  `array_body_structural_package_assembly`, preserves stage order, keys,
  output object identity, source locations, deterministic ordering, selected-
  branch-only behavior, and pipeline snapshots.
- Import-boundary tests proving the focused inventory module does not import
  `boundary.py`, `tslgen.lowering`, backend modules, renderers, `tsldata`,
  `frozen`, or unrelated private modules as convenience dispatchers.
- Tests or assertions proving M89 does not read backend maps, translate
  `uninit::array`, produce renderer-ready values, render output, or widen to
  generic backend-value evaluation.
- Full lowering-boundary preservation plus focused mypy and tooling
  validation.

Golden fixtures required:

- None. M89 must not change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m89 or backend_deferred or structural_package or exact_array_body_pipeline"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Accidentally turning inventory into backend-uninit resolution, backend
  translation, Stage 9 backend planning, renderer-ready values, rendering, or
  generated output.
- Branching on raw helper text, backend ids, extension names, type tags,
  request ordinals, SVE tokens, or corpus line numbers directly to semantic
  outputs rather than validating accepted typed M67/M72/M88 values.
- Broadening to generic `value<backend>(...)` evaluation or generic backend
  request registries.
- Duplicating the M72 deferred backend-uninit value into a semantic node rather
  than referencing the accepted object identity/provenance.
- Adding broad runtime protocols or putting later-stage package outputs back
  into shared protocol-shaped intake.
- Growing `_array_body_models.py`, `_array_body_package.py`,
  `_array_body_pipeline.py`, or the lowering facade into catch-all modules.

Dependencies on prior milestones:

- Milestones 67, 72, and 88, plus the accepted exact array-body chain from
  Milestones 64 through 87.

Next concrete prompt:

- `docs/agent/runs/post-m89-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 90: Exact Array Lowering Completion Package Slice

Status:

Accepted. The M90 execution-review loop returned `Accept With Follow-Ups`
after one focused diagnostic-boundary revision. Review and audit found no
blocking implementation, validation, boundary, extensibility, documentation,
or evidence issues after that revision.

Goal:

Consume the accepted M89 exact array backend-deferred request inventory and
its accepted M88 structural package, then produce one typed Stage 8 exact
array lowering completion package for the selected `array.tsl:105-111` body.

"Completion" means completion of the current lowering-side handoff: all
accepted exact array lowering facts are packaged with explicit unresolved
dependencies for later backend planning. It does not mean semantic completion
of declaration, array, store, return, SVE, backend, renderer, generated-output,
or broad TSIL body behavior.

Scope:

- Add focused private ownership, such as
  `tslgen.lowering._array_body_completion_package`, for exact array lowering
  completion-package assembly, source selection, validation, and diagnostics.
- Consume accepted `ExactArrayBackendDeferredRequestInventoryIr` values, the
  `array_backend_deferred_request_inventory` stage output, or one narrowly
  validated source carrying exactly one accepted M88 package and one matching
  accepted M89 inventory.
- Reach accepted M64-M87 structural facts through the M88 package and accepted
  M89 inventory references, not by re-collecting broad pipeline outputs.
- Produce a typed value, such as `ExactArrayLoweringCompletionPackageIr`,
  carrying stable identity, source location/provenance, candidate id, target
  extension, source extension, selected type tag, branch-chain id, the accepted
  M88 package reference, the accepted M89 inventory reference, and explicit
  unresolved dependency records.
- Represent the accepted M89 `value_backend_uninit_array` inventory member as
  an unresolved dependency by typed reference only. Preserve object identity to
  the accepted M72 deferred backend-uninit value and M67 backend-value request
  record.
- Add one deterministic Stage 8 stage after
  `array_backend_deferred_request_inventory`, such as
  `array_lowering_completion_package`.
- Treat protocol-shaped/runtime sources as untrusted until concrete typed M88
  package and M89 inventory payloads are validated.
- Keep `boundary.py`, `_array_body_pipeline.py`, `_array_body_models.py`, and
  `_array_body_backend_deferred_requests.py` changes minimal. The new focused
  module should own the completion-package logic.

Out of scope:

- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Generic `value<backend>(...)`, `type<backend>(...)`, backend modifier, or
  backend helper evaluation.
- Declaration semantics, array semantics, allocation/lifetime, initializer
  behavior, variable scope, store semantics, return semantics, `tmp.data()`
  pointer semantics, SVE predicate/vector/register semantics, memory behavior,
  direct-intrinsic semantics, or broad body semantics.
- Re-interpreting `svst1`, `tmp.data()`, `svptrue_b*`, `emit_return(tmp)`, or
  the accepted structural slots as semantic body facts.
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, raw helper dispatch, registries, callback maps, plugin
  systems, dispatch tables keyed by raw helper text/backend id/extension/type
  tag/corpus line number, reflection over package members, hidden backfeeds,
  fixpoint execution, or broad source protocols.

Required input:

- Accepted M89 `ExactArrayBackendDeferredRequestInventoryIr`.
- Accepted M88 `ExactArrayBodyStructuralPackageIr`, reached through the M89
  inventory and validated by identity/provenance.
- Accepted M73 declaration shell, M72 deferred backend-uninit value, and M67
  backend-value request record as references through M88/M89.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

Expected outputs:

- A typed exact array lowering completion package carrying stable completion
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, accepted M88 package
  reference, accepted M89 inventory reference, package member references, and
  explicit unresolved dependency records.
- One unresolved dependency record for the accepted M89
  `value_backend_uninit_array` inventory member, preserving typed
  `deferred_backend_value` policy and M72/M67 object identity.
- A deterministic pipeline stage snapshot entry for the completion-package
  stage after `array_backend_deferred_request_inventory`.
- Structured diagnostics for unsupported source, missing/duplicate package,
  missing/duplicate inventory, malformed entries, package/inventory mismatch,
  context mismatch, source-location mismatch, wrong inventory member set,
  wrong policy, and provenance mismatch.

Parity criterion:

M90 succeeds when the accepted exact array-body lowering path produces one
typed completion package that proves the Stage 8 exact array handoff is
assembled and dependency-inventoried, while leaving backend-uninit translation,
renderer-ready IR, generated output, and semantic body lowering unresolved.

Execution result:

- Added focused `tslgen.lowering._array_body_completion_package` ownership for
  exact array lowering completion-package assembly, source selection,
  validation, and diagnostics.
- Added `ExactArrayLoweringCompletionPackageIr` and
  `ExactArrayLoweringUnresolvedDependencyIr`.
- Consumes accepted M89 inventory values, the accepted M89 stage output, or a
  narrowly validated source carrying exactly one accepted M88 package and one
  matching accepted M89 inventory.
- Preserves object identity/provenance for the accepted M88 package, accepted
  M89 inventory, M73 declaration shell, M72 deferred backend-uninit value, and
  M67 backend-value request record.
- Records the accepted M89 `value_backend_uninit_array` inventory member as a
  typed unresolved dependency, preserving `deferred_backend_value` policy by
  reference only.
- Added deterministic `array_lowering_completion_package` stage wiring after
  `array_backend_deferred_request_inventory`.
- Added diagnostics and tests for unsupported, missing, duplicate, malformed,
  package/inventory-mismatched, context-mismatched, source-location-mismatched,
  wrong-member-set, wrong-policy, and provenance-mismatched inputs.
- A focused diagnostic-boundary revision added a guard for malformed
  `source_request_record` values before reading request-record source-location
  data, preserving structured diagnostics instead of raising `AttributeError`.
- M90 remained Stage 8 lowering-side handoff packaging only; it did not add
  backend map reads, backend-uninit resolution, backend translation, Stage 9
  backend planning, renderer-ready IR, rendering, generated output, generic
  backend-value evaluation, semantic body completion, or source-body repair.

Evidence paths:

- `tsldata/primitives/load_store/array.tsl:105-111` for the exact selected
  array body.
- `tslgen/src/tslgen/lowering/_array_body_package.py` for accepted M88 package
  input ownership and provenance.
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py` for
  accepted M89 inventory input and unresolved backend-deferred member
  provenance.
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py` for deterministic stage
  wiring and pipeline snapshot identity.
- `tslgen/src/tslgen/lowering/_pipeline.py` and
  `tslgen/src/tslgen/lowering/_stage_contracts.py` for stage/output contract
  updates.
- `tslgen/tests/unit/test_lowering_boundary.py` for accepted exact array-body
  pipeline behavior, diagnostics, import-boundary tests, and M90 coverage.

Tests required:

- Positive M90 tests for direct M89 inventory input, M89 stage-output input,
  and narrowly validated one-source package-plus-inventory input.
- Identity/provenance tests proving the completion package references accepted
  M88/M89/M73/M72/M67 objects rather than duplicating or re-collecting them.
- Negative tests for unsupported source, missing package, duplicate package,
  missing inventory, duplicate inventory, malformed runtime entries,
  package/inventory mismatch, target/source extension mismatch, selected-type
  mismatch, branch-chain mismatch, source-location mismatch, wrong inventory
  member set, wrong policy, and provenance mismatch.
- Pipeline tests proving `array_lowering_completion_package` appears after
  `array_backend_deferred_request_inventory`, preserves stage order, keys,
  output object identity, source locations, deterministic ordering, selected-
  branch-only behavior, and pipeline snapshots.
- Import-boundary tests proving the focused completion module does not import
  `boundary.py`, `tslgen.lowering`, `_array_body_pipeline.py`, backend modules,
  renderers, `tsldata`, `frozen`, or unrelated private modules as convenience
  dispatchers.
- Tests or assertions proving M90 does not read backend maps, resolve
  `uninit::array`, produce renderer-ready values, render output, infer
  declaration/store/return/SVE semantics, repair source text, or widen to
  generic backend-value evaluation.

Golden fixtures required:

- None. M90 must not change generated C++ or Rust output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m90 or lowering_completion or backend_deferred or structural_package or exact_array_body_pipeline"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line counts after the focused revision: `1226 boundary.py`,
  `1043 _array_body_pipeline.py`, `708 _array_body_package.py`,
  `735 _array_body_backend_deferred_requests.py`,
  `829 _array_body_completion_package.py`, `4541 total`.
- Py-compile returned exit 0 with no output.
- Focused M90 pytest returned `22 passed, 291 deselected in 9.98s`.
- Full lowering-boundary pytest returned `313 passed in 65.72s`.
- Focused lowering mypy returned `Success: no issues found in 25 source files`.
- Full tooling validation returned exit 0 with corpus probes
  `3 passed in 6.78s`, unit discovery `647` tests OK in `139.463s`,
  compileall OK, ruff `All checks passed!`, mypy
  `Success: no issues found in 129 source files`, and diff-check OK.
- Standalone final `git diff --check` returned exit 0 with no output.

Review risks:

- Overclaiming the word "completion" as semantic body completion, backend
  readiness, renderer readiness, or generated output.
- Building a wrapper-only abstraction that does not add a stable typed stage
  output, diagnostics, deterministic key, and pipeline snapshot.
- Reaching across all M64-M87 outputs from `LoweredImplementation` instead of
  consuming the accepted M89 inventory and validating its accepted M88 package
  identity.
- Turning unresolved dependency records into Stage 9 backend planning,
  backend map keys, resolved backend text, renderer slots, artifact paths, or
  scheduling decisions.
- Adding broad protocols, registries, callback dispatch, raw-helper dispatch,
  hidden backfeeds, fixpoint machinery, or generic backend-value evaluation.
- Growing `boundary.py`, `_array_body_pipeline.py`, `_array_body_models.py`,
  or `_array_body_backend_deferred_requests.py` into catch-all modules instead
  of adding focused completion-package ownership.

Dependencies on prior milestones:

- Milestones 67, 72, 73, 88, and 89, plus the accepted exact array-body chain
  from Milestones 64 through 87.

Next concrete prompt:

- `docs/agent/runs/post-m90-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice

Status:

Accepted. The M91 execution-review loop returned `Accept With Follow-Ups` with
no blocking implementation, validation, boundary, documentation, evidence, or
review issues.

Goal:

Perform a behavior-preserving Stage 8 exact array pipeline ownership
consolidation after M90. Move exact array pipeline result aggregation,
stage/snapshot assembly, and public handoff aggregation out of catch-all
facade/orchestration ownership so later lowering milestones can build on the
accepted M64-M90 handoff without growing `boundary.py` or
`_array_body_pipeline.py`.

Scope:

- Add focused private ownership for exact array pipeline result/aggregate DTOs,
  including behavior currently concentrated around the M90-era exact array
  pipeline aggregate result.
- Add focused private ownership for exact array stage construction and
  snapshot-step assembly over accepted M64-M90 outputs.
- Keep `boundary.py` as a public facade/projection surface and
  `_array_body_pipeline.py` as orchestration over focused helpers.
- Preserve accepted M64-M90 diagnostics, source locations, public imports,
  stage names/order, artifact kinds, deterministic keys, output identities,
  selected-branch-only behavior, no-external-input boundaries, and pipeline
  snapshots.
- Add or preserve import-boundary, line-count, behavior-preservation, and
  snapshot-stability tests for the public handoff.

Out of scope:

- New lowering semantics.
- Backend-uninit resolution, backend maps/catalog reads, backend translation,
  Stage 9 backend planning, renderer-ready IR, rendering, generated output,
  CLI/report/writer behavior, Rust, or compiler execution.
- Broad TSIL parsing, broad body/declaration/array/store/return/call/SVE
  semantics, `tmp.data()` semantics, `emit_return` semantics, or
  source-body repair.
- Broad protocols, registries, raw-helper dispatch, callback maps, plugin
  systems, hidden backfeeds, fixpoint machinery, or extension-specific
  hardwiring.
- Changing public behavior, diagnostic codes, accepted keys, or snapshot
  ordering.

Required input:

- Accepted M64-M90 exact array pipeline stage outputs and public facade
  expectations.
- Existing exact array pipeline aggregate/result behavior.
- M90 line-count pressure: `boundary.py` measured 1,226 physical lines and
  `_array_body_pipeline.py` measured 1,043 physical lines after M90.

Expected outputs:

- New focused private module ownership for exact array pipeline result
  aggregation and stage/snapshot assembly.
- Stable public `tslgen.lowering` and `tslgen.lowering.boundary` imports.
- Stable deterministic Stage 8 pipeline snapshots and accepted exact array
  handoff keys.
- Reduced or stabilized responsibilities in `boundary.py` and
  `_array_body_pipeline.py`.

Execution result:

- Added focused `tslgen.lowering._array_body_pipeline_results` ownership for
  the exact array pipeline result DTO/key behavior previously concentrated in
  `_array_body_pipeline.py`.
- Added focused `tslgen.lowering._array_body_stage_assembly` ownership for
  exact Stage 8 stage construction, result assembly, and pipeline snapshot
  assembly over accepted M64-M90 outputs.
- Kept `tslgen.lowering._array_body_pipeline` as orchestration over accepted
  lowerers and the focused assembly helpers.
- Preserved accepted M64-M90 diagnostics, source locations, public imports,
  stage names/order, artifact kinds, deterministic keys, output identities,
  selected-branch-only behavior, no-external-input boundaries, and pipeline
  snapshots.
- Added M91 tests for result DTO ownership, stage/snapshot stability,
  import-boundary preservation, and line-count guardrails.
- Reduced `_array_body_pipeline.py` from the M90 1,043-line pressure point to
  591 physical lines without changing behavior. `boundary.py` remained
  unchanged at 1,226 lines.

Tests required:

- Behavior-preservation tests proving accepted M64-M90 stage names/order,
  diagnostics, output identities, deterministic keys, selected-branch-only
  behavior, and pipeline snapshots remain unchanged.
- Import-boundary tests proving new private modules do not import
  `boundary.py`, the `tslgen.lowering` package facade, backend modules,
  renderers, `tsldata`, or `frozen`.
- Line-count reporting for `boundary.py`, `_array_body_pipeline.py`, and the
  new private ownership modules.
- Negative tests or existing assertions proving M91 does not add backend map
  reads, backend translation, Stage 9 planning, rendering, generated output,
  broad TSIL parsing, source-body repair, broad protocols, or fixpoint
  behavior.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py <new-private-modules>`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py <new-private-modules>`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m91 or pipeline_ownership or exact_array_body_pipeline or lowering_completion"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line counts: `1226 boundary.py`, `591 _array_body_pipeline.py`,
  `829 _array_body_completion_package.py`,
  `225 _array_body_pipeline_results.py`,
  `465 _array_body_stage_assembly.py`, `3336 total`.
- Py-compile returned exit 0 with no output.
- Focused M91 pytest returned `13 passed, 303 deselected in 5.67s`; read-only
  smoke re-runs returned `13 passed, 303 deselected in 5.58s` and
  `13 passed, 303 deselected in 5.34s`.
- Full lowering-boundary pytest returned `316 passed in 55.88s`.
- Focused lowering mypy returned `Success: no issues found in 27 source files`.
- Full tooling validation returned exit 0 with corpus probes `3 passed`, unit
  discovery `650` tests OK, compileall OK, ruff `All checks passed!`, mypy
  `Success: no issues found in 131 source files`, and diff-check OK.
- Standalone `git diff --check` returned exit 0 with no output.

Review risks:

- Moving code without creating a clearer ownership boundary.
- Creating a replacement private monolith.
- Changing stage names/order, keys, public imports, diagnostics, snapshots, or
  selected-branch-only behavior while claiming no behavior change.
- Turning exact array handoff aggregation into a broad source protocol,
  registry, callback dispatcher, hidden backfeed, or fixpoint coordinator.
- Letting backend planning, backend maps, renderer-ready IR, rendering, or
  generated output enter Stage 8 lowering ownership.

Next concrete prompt:

- `docs/agent/runs/post-m91-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 92: Exact Array Lowering Backend-Handoff Request Slice

Status:

Accepted. Selected by accepted post-M91 planning and implemented through
`docs/agent/runs/m92-execution-review-loop-prompt.md`. The M92
execution-review loop returned `Accept With Follow-Ups`; review and audit
found no blocking implementation, validation, boundary, extensibility, or
evidence issues after a focused documentation update recorded the M92
diagnostics and final roadmap/status wording.

Goal:

Create the typed lowering-side handoff request that lets future backend
planning consume the accepted M90 exact array lowering completion package
without reaching back through pipeline internals. M92 bridges Stage 8
lowering completion to a future Stage 9 backend-planning boundary while
remaining request/provenance data only.

Scope:

- Add focused private ownership, such as
  `tslgen.lowering._array_body_backend_handoff`, for one exact array backend
  handoff request type and assembly function.
- Consume accepted typed `ExactArrayLoweringCompletionPackageIr` values,
  `array_lowering_completion_package` stage outputs, or narrowly validated
  sources carrying exactly one accepted completion package.
- Produce one typed exact array backend-handoff request carrying stable
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, accepted completion-package
  reference, accepted M88/M89 package/inventory references, and explicit
  unresolved dependency request records.
- Preserve object identity/provenance for the accepted M90 completion package,
  accepted M89 inventory member, accepted M72 deferred backend-uninit value,
  and accepted M67 backend-value request record.
- Add one deterministic Stage 8 handoff stage after
  `array_lowering_completion_package`, such as
  `array_backend_handoff_request`.
- Preserve accepted M64-M91 diagnostics, source locations, public imports,
  stage names/order before the new stage, deterministic keys, selected-branch-
  only behavior, no-external-input boundaries, and pipeline snapshots.

Out of scope:

- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Generic `value<backend>(...)`, `type<backend>(...)`, backend modifier, or
  backend helper evaluation.
- Declaration semantics, array semantics, allocation/lifetime, initializer
  behavior, variable scope, store semantics, return semantics, `tmp.data()`
  pointer semantics, SVE predicate/vector/register semantics, memory behavior,
  direct-intrinsic semantics, or broad body semantics.
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad protocols, registries, callback maps, plugin systems, hidden
  backfeeds, fixpoint execution, raw-helper dispatch, or dispatch tables keyed
  by raw helper text/backend id/extension/type tag/corpus line number.

Required input:

- Accepted M90 `ExactArrayLoweringCompletionPackageIr`.
- Accepted M89 inventory and M88 structural package, reached by reference
  through the accepted M90 completion package.
- Accepted M72 deferred backend-uninit value and M67 backend-value request
  record, reached by reference through the accepted M90 unresolved dependency.
- Accepted M91 stable pipeline result/stage/snapshot ownership.
- Corpus evidence: `tsldata/primitives/load_store/array.tsl:105-111`.

Expected outputs:

- A typed exact array backend-handoff request with stable identity,
  provenance, completion-package reference, unresolved dependency request
  records, and deterministic key behavior.
- A deterministic pipeline stage snapshot entry for the handoff-request stage
  after `array_lowering_completion_package`.
- Structured diagnostics for unsupported source, missing/duplicate completion
  package, malformed entries, context mismatch, source-location mismatch,
  wrong dependency set, wrong policy, and provenance mismatch.

Tests required:

- Positive M92 tests for direct M90 completion package input, M90 stage-output
  input, and narrowly validated one-completion-package source input.
- Identity/provenance tests proving the handoff request references accepted
  M90/M89/M88/M72/M67 objects rather than duplicating or re-collecting them.
- Negative diagnostics for unsupported source, missing completion package,
  duplicate completion package, malformed runtime entries, context mismatch,
  source-location mismatch, wrong dependency set, wrong policy, and provenance
  mismatch.
- Pipeline tests proving the new handoff-request stage follows
  `array_lowering_completion_package` and preserves prior stage order, keys,
  output identity, selected-branch-only behavior, and pipeline snapshots.
- Import-boundary tests proving the focused handoff module does not import
  `boundary.py`, `tslgen.lowering`, `_array_body_pipeline.py`, backend
  modules, renderers, `tsldata`, or `frozen`.
- Negative assertions proving M92 does not read backend maps, resolve
  `uninit::array`, create Stage 9 plans, produce renderer-ready values, render
  output, infer declaration/store/return/SVE semantics, repair source text, or
  widen to generic backend-value evaluation.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m92 or backend_handoff or lowering_completion or exact_array_body_pipeline"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line counts were `1245 tslgen/src/tslgen/lowering/boundary.py`,
  `616 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
  `667 tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`, and
  `2528 total`.
- The py-compile command returned exit 0 with no output.
- The focused M92 command returned `17 passed, 306 deselected in 12.13s`.
- The full lowering-boundary suite returned `323 passed in 107.02s`.
- The focused lowering mypy check returned
  `Success: no issues found in 28 source files`.
- The validation profile returned exit 0 with corpus probes
  `3 passed in 10.44s`, unit discovery `657` tests OK in `239.885s`,
  compileall OK, ruff `All checks passed!`, mypy
  `Success: no issues found in 132 source files`, and diff-check OK.
- The standalone final `git diff --check` returned exit 0 with no output.

Review risks:

- Creating a wrapper-only abstraction that does not add a concrete typed
  request, deterministic key, diagnostics, and pipeline snapshot.
- Starting Stage 9 backend planning under a handoff label.
- Turning unresolved dependencies into backend map keys, resolved backend text,
  renderer slots, artifact paths, scheduling decisions, broad protocols,
  hidden backfeeds, or fixpoint machinery.
- Reaching across all exact array pipeline outputs instead of consuming the
  accepted M90 completion package and validating identity/provenance.
- Growing `boundary.py`, `_array_body_pipeline.py`,
  `_array_body_completion_package.py`, `_array_body_pipeline_results.py`, or
  `_array_body_stage_assembly.py` into catch-all modules instead of adding
  focused handoff ownership.

Next concrete prompt:

- `docs/agent/runs/post-m92-planning-plus-review-prompt.md` runs the next
  lowering-focused planning pass.

### Milestone 93: Dual-Source Lowering Operation Package Boundary Slice

Status:

Accepted. The M93 execution-review loop returned `Accept With Follow-Ups`
after a focused revision for container-context validation and M86 mini-TSIL
source-shape narrowing. M93 implemented a Stage 8 lowering operation package
boundary seed over exactly two accepted typed source families: accepted M86
mini-TSIL leaf return statements and accepted M92 exact array backend-handoff
requests. The slice proves that lowering packaging is not array-only without
creating a broad operation framework, dispatcher, backend plan, renderer
input, or semantic body normalizer.

Goal:

Create a backend-neutral typed lowering operation package boundary that can
carry either an accepted mini-TSIL leaf return operation or an accepted exact
array backend-handoff operation as immutable typed/provenance data. M93 should
give later lowering/backend-planning work one common package surface while
preserving source-family identity and without pretending that the two source
families share broad body semantics.

Scope:

- Add focused private ownership, such as
  `tslgen.lowering._operation_package`, for one lowering operation package
  type, two exact package entry variants, deterministic keys, source narrowing,
  provenance validation, and diagnostics.
- Consume only accepted M86 `TsilReturnStatement` / `selected_body_lowering`
  values with explicit candidate context, accepted M92
  `ExactArrayBackendHandoffRequestIr` / `array_backend_handoff_request`
  values, or narrowly validated sources carrying exactly one packageable
  accepted value.
- Produce a deterministic typed package for `mini_tsil_leaf_return` entries
  that preserves the accepted M86 return statement object and candidate
  context.
- Produce a deterministic typed package for `exact_array_backend_handoff`
  entries that preserves the accepted M92 request object and its M90/M89/M88/
  M72/M67 identity/provenance chain.
- Expose the packages on `LoweredImplementation` and stage snapshots as a
  Stage 8 `lowering_operation_package` fact, without changing accepted M86 or
  M92 output identity or earlier stage order.
- Preserve accepted M57-M92 diagnostics, source locations, public imports,
  deterministic keys, selected-branch-only behavior, no-external-input
  boundaries, and pipeline snapshots.

Out of scope:

- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Primitive dependency closure, primitive-call discovery, operation
  scheduling, backend support filtering, wrapper-shape planning, artifact path
  planning, or backend operation DAG construction.
- Generic operation registries, plugin systems, callback maps, semantic
  dispatchers, hidden backfeeds, fixpoint execution, or dispatch tables keyed
  by primitive name, raw helper text, backend id, extension id, selected type
  tag, SVE token, renderer name, corpus line number, or request ordinal.
- Hardwiring semantic outputs from primitive names, selected type tags,
  extension names, backend ids, helper text, SVE tokens, corpus line numbers,
  or request ordinals.
- Generic TSIL parsing, broad expression/body/return/call/store/declaration/
  array/variable/cast/loop/SVE semantics, broad `emit_return(...)`, broad
  direct-intrinsic semantics, generic `value<backend>(...)` or
  `type<backend>(...)` evaluation, or source-body repair.
- Placeholder operation package kinds for unimplemented primitive families.
  Future primitive families must be added by later milestones with their own
  accepted typed source facts, evidence, diagnostics, and tests.

Required input:

- Accepted M86 `TsilReturnStatement` values and the selected-candidate context
  that produced them.
- Accepted M92 `ExactArrayBackendHandoffRequestIr` values.
- Accepted M92 source-chain references to M90/M89/M88/M72/M67 values.
- Corpus evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl:31`
  - `tsldata/primitives/arithmetic/fundamental.tsl:64`
  - `tsldata/primitives/load_store/array.tsl:105-111`

Expected outputs:

- A typed lowering operation package with stable identity, source-family tag,
  candidate id, source location/provenance, source typed value reference, and
  deterministic key behavior.
- A mini-TSIL leaf-return operation package entry preserving the accepted M86
  `TsilReturnStatement` object and candidate context.
- An exact-array backend-handoff operation package entry preserving the
  accepted M92 request object and its unresolved dependency request/provenance
  records.
- Structured diagnostics for unsupported source, missing packageable value,
  duplicate packageable values, malformed runtime entries, source-family
  mismatch, context mismatch, source-location mismatch, dependency/provenance
  mismatch, and package-source ambiguity.

Accepted result:

- Added focused private `tslgen.lowering._operation_package` ownership for
  `LoweringOperationPackageIr`, the two exact package entry variants, package
  keys, source narrowing, provenance validation, and M93 diagnostics.
- Added `LoweredImplementation.operation_packages` and the typed
  `lowering_operation_package` stage/snapshot fact after accepted M86
  `selected_body_lowering` outputs or accepted M92
  `array_backend_handoff_request` outputs.
- Preserved accepted M86 `TsilReturnStatement` object identity and accepted
  M92/M90/M89/M88/M72/M67 provenance identity. Mini-TSIL package inputs are
  narrowed to the accepted M86 leaf-return shapes rather than all possible
  manually constructed `TsilReturnStatement` values.
- Review recorded non-blocking follow-ups to keep `_operation_package.py` from
  becoming a replacement monolith, avoid future facade growth in
  `boundary.py`, and prevent package source narrowing from evolving into a
  central semantic dispatcher.

Tests required:

- Positive M93 tests for direct M86 statement plus explicit candidate context,
  M86 stage-output/container input, direct M92 handoff request input, M92
  stage-output/container input, and normal `LoweredImplementation` /
  `LoweringPlan` integration.
- Identity/provenance tests proving package entries reference accepted M86 and
  M92 objects rather than duplicating, reparsing, or re-collecting facts.
- Negative diagnostics for unsupported source, missing packageable value,
  duplicate packageable values, malformed runtime entries, source-family
  mismatch, context mismatch, source-location mismatch, and M92 dependency/
  provenance mismatch.
- Determinism tests for package keys, reordered lowered implementations, and
  pipeline snapshots.
- Import-boundary tests proving the focused package module does not import
  `boundary.py`, `tslgen.lowering`, exact-array orchestration modules as
  dispatchers, backend modules, renderers, `tsldata`, or `frozen`.
- Negative assertions proving M93 does not read backend maps/catalogs, resolve
  `uninit::array`, create Stage 9 plans, produce renderer-ready values, render
  output, infer broad body semantics, repair source text, or widen to generic
  TSIL/backend-helper evaluation.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m93 or operation_package or mini_tsil or backend_handoff"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Turning the package boundary into Stage 9 backend planning, renderer-ready
  IR, dependency closure, scheduling, or artifact planning.
- Hiding array-specific assumptions behind a generic name or, conversely,
  claiming broad cross-primitive support beyond the accepted M86/M92 source
  families.
- Creating a broad source protocol, registry, callback map, plugin system,
  semantic dispatcher, hidden backfeed, or fixpoint coordinator.
- Hardwiring semantic outputs from primitive names, selected type tags,
  extension names, backend ids, helper text, SVE tokens, corpus line numbers,
  or request ordinals.
- Normalizing M86 and M92 into a fake common body semantics model instead of
  preserving distinct typed source-family identity.
- Adding placeholder operation kinds for unsupported future primitive
  families.
- Growing `boundary.py` or `_stage_contracts.py` into catch-all ownership
  instead of adding focused package ownership with one-way imports.

Next concrete prompt:

- `docs/agent/runs/post-m93-planning-plus-review-prompt.md` runs post-M93
  planning and review with a lowering focus.

### Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice

Status:

Accepted. The M94 execution-review loop returned `Accept With Follow-Ups`
after one focused validation-coverage revision.

Goal:

Keep the accepted M93 lowering operation package boundary maintainable before
any future package-family expansion. M94 is behavior-preserving Stage 8
lowering architecture work: it splits M93 diagnostics, source narrowing, and
exact-array provenance validation into focused private ownership so
`_operation_package.py` remains a small package/coordinator surface instead of
becoming a replacement monolith.

Scope:

- Preserve accepted M93 behavior for exactly the two packageable source
  families: accepted M86 mini-TSIL leaf return statements and accepted M92
  exact array backend-handoff requests.
- Keep the public `tslgen.lowering` and `tslgen.lowering.boundary` import
  surfaces stable, including `lower_lowering_operation_package`,
  `LoweringOperationPackageIr`, package entry types, and source-family values.
- Split focused private ownership out of `_operation_package.py`, such as:
  - `_operation_package_models.py` for package/entry value models,
    source-family literal ownership, and deterministic keys.
  - `_operation_package_diagnostics.py` for M93 diagnostic constructors and
    source-location helper behavior.
  - `_operation_package_sources.py` for accepted source/stage/container
    narrowing and exactly-one-packageable-value checks.
  - `_operation_package_mini_tsil.py` for the accepted M86 leaf-return
    package contract and exact accepted-shape predicate.
  - `_operation_package_exact_array.py` for M92/M90/M89/M88/M72/M67
    identity/provenance contract validation.
- Keep `_operation_package.py` as the narrow coordinator/facade over those
  focused modules, not as the owner of diagnostics, provenance, and source
  narrowing.
- Preserve accepted M93 diagnostics, diagnostic codes, diagnostic locations,
  package keys, stage name `lowering_operation_package`, stage ordering,
  snapshots, object identity, deterministic ordering, and selected-branch-only
  behavior.
- Add or update import-boundary and contract tests for the new modules, proving
  one-way private imports and public-surface stability.
- Include line-count validation proving `_operation_package.py` drops
  materially below the roughly 1,000-line guardrail and that no replacement
  operation-package module approaches the guardrail.

Out of scope:

- New operation package source families or placeholder package kinds.
- New semantic lowering behavior, broad package-family dispatch, generic
  operation registries, callback maps, plugin systems, semantic dispatchers,
  hidden backfeeds, fixpoint machinery, or token-keyed semantic maps.
- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Primitive dependency closure, primitive-call discovery, operation
  scheduling, backend support filtering, wrapper-shape planning, artifact path
  planning, or backend operation DAG construction.
- Generic TSIL parsing, broad expression/body/return/call/store/declaration/
  array/variable/cast/loop/SVE semantics, generic backend-helper evaluation,
  broad direct-intrinsic semantics, or source-body repair.
- Changing accepted M86/M92 source-family narrowing, reparsing accepted values,
  normalizing M86 and M92 into shared body semantics, or hardwiring semantic
  outputs from primitive names, selected type tags, extension names, backend
  ids, helper text, SVE tokens, corpus line numbers, or request ordinals.
- Growing `boundary.py`, exact-array pipeline modules, `_stage_contracts.py`,
  or any new private operation-package module into a catch-all owner.

Required input:

- Accepted M93 `LoweringOperationPackageIr` behavior and tests.
- Accepted M86 mini-TSIL leaf return statements and selected-candidate context.
- Accepted M92 exact array backend-handoff requests and their accepted
  M90/M89/M88/M72/M67 provenance chain.
- Current line-count evidence:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,280 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package.py`: 1,044 physical lines.

Expected outputs:

- Focused private operation-package modules with one-way imports and explicit
  ownership.
- `_operation_package.py` reduced to a small coordinator/re-export surface
  while preserving accepted public imports and behavior.
- The same accepted M93 package outputs, diagnostics, keys, identities, stage
  outputs, and snapshots as before the split.
- Focused tests proving behavior preservation, diagnostic preservation,
  public-surface stability, import-boundary discipline, and line-count
  guardrails.

Accepted result:

- Kept `tslgen.lowering._operation_package` as a 19-line facade/re-export
  surface for the accepted M93 public operation-package API.
- Added focused private operation-package ownership:
  - `_operation_package_models.py` owns package/entry value models,
    source-family literal ownership, and deterministic keys.
  - `_operation_package_diagnostics.py` owns M93 diagnostic constructors and
    source-location helper behavior.
  - `_operation_package_sources.py` owns accepted source/stage/container
    narrowing and exactly-one-packageable-value checks for the two accepted
    M93 source families.
  - `_operation_package_mini_tsil.py` owns the accepted M86 leaf-return shape
    predicate.
  - `_operation_package_exact_array.py` owns accepted
    M92/M90/M89/M88/M72/M67 identity/provenance contract validation.
- Preserved accepted M93 behavior, public imports, diagnostic codes and source
  locations, package keys, stage name/order, snapshots, object identity,
  deterministic ordering, selected-branch-only behavior, and no-external-input
  boundaries.
- Added focused validation coverage proving operation-package public facade
  stability, one-way import boundaries for every split module, line-count
  guardrails, and representative diagnostic source-location preservation.

Files changed:

- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

Final line counts:

- `tslgen/src/tslgen/lowering/boundary.py`: 1,280
- `tslgen/src/tslgen/lowering/_operation_package.py`: 19
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`: 136
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`: 174
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`: 36
- `tslgen/src/tslgen/lowering/_operation_package_models.py`: 153
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 604

Tests required:

- Existing M93 positive, diagnostic, identity/provenance, determinism,
  integration, and snapshot tests must continue to pass unchanged or with only
  behavior-preserving test ownership updates.
- New or updated M94 import-boundary tests must cover each new private module,
  proving they do not import `boundary.py`, the `tslgen.lowering` package
  facade, backend modules, renderers, `tsldata`, or `frozen`.
- Contract tests must prove the public facade exports still point at the same
  operation-package API and that stage name/order/key behavior remains stable.
- Negative assertions must prove no backend map/catalog reads, backend-uninit
  resolution, Stage 9 planning, renderer-ready IR, rendering, generated
  output, source repair, operation registry, semantic dispatcher, generic TSIL
  parsing, or generic backend-helper evaluation is introduced.

Final validation results:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py`:
  `boundary.py` 1,280, `_operation_package.py` 19,
  `_operation_package_diagnostics.py` 136,
  `_operation_package_exact_array.py` 174,
  `_operation_package_mini_tsil.py` 36,
  `_operation_package_models.py` 153,
  `_operation_package_sources.py` 604, total 2,402.
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py`:
  exit 0, no output.
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m94 or operation_package or provenance or diagnostics"`:
  38 passed, 293 deselected.
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`:
  331 passed.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`:
  `Success: no issues found in 34 source files`.
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`: corpus probes
  3 passed, unittest discovery ran 665 tests OK, compileall OK, ruff all
  checks passed, mypy success across 138 source files, and diff-check OK.
- `git diff --check`: exit 0, no output.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m94 or operation_package or provenance or diagnostics"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Review risks:

- Treating M94 as cleanup without preserving observable M93 contracts.
- Creating several new files but leaving `_operation_package.py` responsible
  for diagnostics, provenance validation, and source narrowing.
- Creating a second monolith in one of the new private modules.
- Converting package source narrowing into a generic dispatcher or broad
  structural protocol for future body families.
- Allowing exact-array provenance validation to reach into backend planning,
  backend maps, renderer-ready IR, or source-body semantics.
- Adding new package families before the M93 maintainability follow-up is
  resolved.

Review follow-ups:

- `_operation_package_sources.py` remains focused at 604 lines but necessarily
  uses duck-typed accepted containers through `hasattr`/`getattr` for the M93
  surface. Future package-family work must not grow this into a generic source
  protocol or dispatcher.
- The current line-count test asserts each operation-package module remains
  below 1,000 lines. A future maintainability pass may choose a tighter
  threshold for operation-package private modules so a near-guardrail
  replacement monolith cannot technically pass.

Next concrete prompt:

- `docs/agent/runs/post-m94-planning-plus-review-prompt.md` runs post-M94
  planning and review with a lowering focus.

### Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice

Status:

Accepted. The M95 execution-review loop returned `Accept With Follow-Ups`
after focused revision.

Goal:

Add one focused Stage 8 lowering operation-package family for already accepted
selected-body direct-intrinsic facts. M95 proves the post-M94 package design
can grow by family-specific typed ownership without turning
`_operation_package_sources.py` into a generic source protocol or dispatcher.

Accepted result:

- Added the `selected_body_direct_intrinsic` operation-package source family
  over accepted M63 `SelectedBodyEnvelopeIr` values and their enclosed
  accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr` provenance.
- Moved selected-body package validation and entry ownership into
  `_operation_package_selected_body.py`; `_operation_package.py` remains a
  narrow facade and `_operation_package_sources.py` only performs explicit
  source/stage/container integration.
- Appended selected-body operation-package facts immediately after
  `selected_body_envelope_lowering` for selected envelopes. No selected-body
  package is produced for `NoSelectedBodyEnvelopeIr`; explicit selected-body
  package requests diagnose the no-selected envelope at its source location.
- Preserved accepted M86 mini-TSIL leaf-return and accepted M92 exact-array
  backend-handoff package behavior, keys, object identity, stage ordering,
  snapshots, diagnostics, deterministic ordering, public imports, and
  selected-branch-only behavior.
- Added focused coverage for direct/stage/container package creation,
  malformed/non-singleton selected envelopes, wrong stage, no-selected body,
  candidate/source-location/provenance mismatch, deterministic package keys,
  pipeline integration, public facade stability, import boundaries, forbidden
  semantic/boundary terms, and line-count guardrails.

Files changed:

- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_selected_body.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

Final line counts:

- `tslgen/src/tslgen/lowering/boundary.py`: 1,300
- `tslgen/src/tslgen/lowering/_operation_package.py`: 23
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`: 136
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`: 174
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`: 36
- `tslgen/src/tslgen/lowering/_operation_package_models.py`: 171
- `tslgen/src/tslgen/lowering/_operation_package_selected_body.py`: 186
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 819

Scope:

- Consume only accepted M63 `SelectedBodyEnvelopeIr` values from the
  `selected_body_envelope_lowering` stage or equivalent narrow typed
  container input.
- Preserve the enclosed accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr`
  as the source of typed selected-body direct-intrinsic provenance.
- Add exactly one package source family, such as
  `selected_body_direct_intrinsic`, with one focused package entry for the
  exact singleton selected-body assignment/direct-intrinsic envelope already
  accepted by M62/M63.
- Preserve candidate id, selected type tag, selected literal, originating
  branch-chain id, assignment target text, direct-intrinsic token text,
  original selected body text, source location, and deterministic keys as
  typed provenance.
- Produce no selected-body direct-intrinsic package for
  `NoSelectedBodyEnvelopeIr`, except a clear diagnostic when that source family
  is explicitly requested.
- Keep existing M86 mini-TSIL leaf-return and M92 exact-array backend-handoff
  package behavior, public imports, package keys, diagnostics, stage ordering,
  snapshots, object identity, deterministic ordering, and
  selected-branch-only behavior stable.
- Put selected-body package validation and entry ownership in a focused module
  such as `_operation_package_selected_body.py`; `_operation_package_sources.py`
  may receive only narrow explicit integration and must not become a generic
  source dispatcher or protocol.

Out of scope:

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  Stage 9 backend planning, renderer-ready IR, rendering, generated C++ or
  Rust output, generated tests, CLI/report/writer behavior, compiler
  execution, or Rust.
- Direct-intrinsic/SVE predicate semantics, `pg` type/scope proof, byte-size
  to `svptrue_b*` inference, vector metadata, store/return semantics, primitive
  dependency closure, operation scheduling, wrapper planning, or artifact
  planning.
- Raw selected-body text parsing, source-body repair, nearby malformed body
  acceptance, broad TSIL/body parsing, generic operation registries, callback
  maps, package-family registries, semantic dispatchers, hidden backfeeds,
  fixpoint machinery, or placeholder package kinds for future families.
- Treating `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `pg`, selected
  literals, selected type tags, extension ids, primitive names, backend ids, or
  corpus line numbers as semantic dispatch keys.

Required input:

- Accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr` behavior and diagnostics.
- Accepted M63 `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`
  behavior, source locations, deterministic keys, and stage output contracts.
- Accepted M93/M94 `LoweringOperationPackageIr` behavior, package source-family
  distinction, facade imports, diagnostics, and module-size/import guardrails.

Expected outputs:

- A focused selected-body direct-intrinsic operation-package entry/family over
  accepted M63/M62 typed values.
- Stable public operation-package facade imports for the new family, if a
  public import is added.
- Deterministic package keys and stage/snapshot integration that preserve
  source-family identity and object provenance.
- Diagnostics for unsupported source, wrong stage/source family, no selected
  body, malformed/non-singleton envelope state, context/source-location
  mismatch, and provenance mismatch.
- Tests proving no raw text parsing, SVE/direct-intrinsic interpretation,
  backend planning, renderer-ready IR, source repair, registry/dispatcher, or
  second operation-package monolith is introduced.

Tests required:

- Positive tests for direct accepted M63 envelope input, stage input, and
  narrow lowered-implementation/container input where applicable.
- Negative tests for `NoSelectedBodyEnvelopeIr`, unsupported stages, malformed
  envelopes, source-family mismatch, candidate/source-location mismatch, and
  M62/M63 provenance mismatch.
- Determinism tests for package keys and reordered typed inputs.
- Pipeline/stage tests proving selected-body packages append after
  `selected_body_envelope_lowering` without changing existing M86/M92 package
  behavior.
- Import-boundary and line-count tests proving focused operation-package
  modules keep one-way imports and stay comfortably below the 1,000-line
  guardrail.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m95 or operation_package or selected_body"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Final validation results:

- Focused M95 pytest returned `26 passed, 308 deselected`.
- Full lowering-boundary pytest returned `334 passed`.
- Focused lowering mypy returned `Success: no issues found in 35 source files`.
- Full tooling validation returned exit 0 with corpus probes `3 passed`, unit
  discovery `668` tests OK, compileall OK, ruff OK, mypy
  `Success: no issues found in 139 source files`, and diff-check OK.

Review risks:

- Growing `_operation_package_sources.py` from a narrow accepted-source bridge
  into a generic source protocol, dispatcher, callback map, or package-family
  registry.
- Interpreting `svptrue_b*`, `pg`, selected literals, type tags, primitive
  names, extension ids, backend ids, or source locations as semantic dispatch
  keys instead of preserving them as typed provenance.
- Treating selected-body package creation as SVE/direct-intrinsic semantics,
  backend planning, renderer-ready IR, broad body parsing, or source-body
  repair.
- Creating a new private operation-package module that becomes a replacement
  monolith despite the M94 split.

Execution follow-ups:

- `_operation_package_sources.py` remains below the guardrail at 819 lines,
  but it is now the operation-package pressure point. Before adding another
  operation-package source family, split more source narrowing/package
  construction out of it rather than letting it grow into a central package
  router.
- `boundary.py` is exactly at the current 1,300-line guardrail. Future
  lowering work should avoid adding ownership there and should keep new
  behavior in focused private modules.

Next concrete prompt:

- `docs/agent/runs/post-m95-planning-plus-review-prompt.md` runs post-M95
  planning and review with a lowering focus.

### Milestone 96: Stage-8 Lowering Completion Manifest Slice

Status:

Accepted. The M96 execution-review loop returned `Accept With Follow-Ups`
after one focused identity/provenance revision. Review found no remaining
blocking implementation, validation, boundary, extensibility, or documentation
issues after that revision.

Goal:

Create one typed, deterministic Stage 8 lowering completion manifest over the
currently accepted lowering operation-package families. M96 should give later
backend-planning work a single lowering-owned readiness/provenance contract
without starting backend planning, translating backend values, or turning the
operation-package bridge into a package router.

For M96, "completion" and "readiness" mean only that the accepted Stage 8
package/provenance facts present on the candidate have been assembled and
validated. They do not mean semantic body completion, backend readiness,
renderer readiness, executable readiness, or generated-output readiness.

Scope:

- Added focused private lowering ownership in
  `_lowering_completion_manifest.py` for manifest models, diagnostics,
  validation, and assembly.
- Consumes accepted `LoweringOperationPackageIr` values as the primary input.
  Family-specific M86 mini-TSIL leaf-return values, accepted M92 exact array
  backend-handoff values, and accepted M95 selected-body direct-intrinsic
  values are reached only through those accepted package entries and
  already-preserved object references.
- Preserves accepted M92/M90 unresolved backend-handoff dependency provenance
  as unresolved lowering-side manifest records. It does not resolve those
  dependencies.
- Produces one deterministic per-candidate typed manifest value,
  `Stage8LoweringCompletionManifestIr`, with candidate identity, package keys,
  source-family identities, package-entry identities, source locations,
  unresolved-dependency summaries, and readiness/provenance status.
- Adds one deterministic Stage 8 stage, `lowering_completion_manifest`, after
  accepted `lowering_operation_package`
  facts without changing accepted M86/M92/M95 package behavior, object
  identity, diagnostics, selected-branch-only behavior, stage ordering, or
  pipeline snapshots.
- Keeps `boundary.py` and `_operation_package_sources.py` from absorbing new
  ownership. `boundary.py` coordinates the stage only, and
  `_operation_package_sources.py` is unchanged.

Out of scope:

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  Stage 9 backend planning, operation scheduling, primitive dependency
  closure, renderer-ready IR, rendering, generated C++ or Rust output,
  generated tests, CLI/report/writer behavior, compiler execution, or Rust.
- New operation-package source families, placeholder package kinds, generic
  operation registries, semantic dispatchers, callback maps, plugin systems,
  hidden recursive backfeeds, fixpoint machinery, or broad source protocols.
- Re-entering raw M86 statements, M92 handoff assembly, M63 envelopes, or the
  M90/M89/M72/M67 provenance chain except to validate object references already
  preserved by accepted operation-package entries.
- Direct-intrinsic/SVE semantics, byte-size-to-token inference, vector
  metadata inference, declaration/array/store/return/body semantics,
  `value<backend>(...)` evaluation, raw body text parsing, source-body repair,
  or generic TSIL/body parsing.
- Treating `svptrue_b*`, `pg`, selected literals, type tags, primitive names,
  extension ids, backend ids, source locations, or package-family tags as
  semantic dispatch keys.

Required input:

- Accepted M86 mini-TSIL leaf-return package behavior and diagnostics.
- Accepted M92 exact array backend-handoff request package behavior and
  unresolved dependency provenance through M90/M89/M72/M67.
- Accepted M95 selected-body direct-intrinsic package behavior and provenance.
- Accepted M93/M94 operation-package facade, source-family distinction,
  deterministic package keys, diagnostics, and import/module-size guardrails.

Expected outputs:

- A typed Stage 8 lowering completion manifest/readiness value per selected
  candidate with deterministic keys and package ordering.
- Manifest records that distinguish complete lowering facts from unresolved
  backend-handoff dependencies without converting either into backend plans.
- Diagnostics for unsupported sources, missing packages, duplicate package
  keys, malformed package entries, mixed candidate context,
  source-location/provenance mismatches, wrong stage/order, ambiguous
  containers, and dependency provenance mismatches.
- A narrow private module boundary with tests that prove imports remain
  one-way. The manifest is not exported as public API in M96.

Tests required:

- Positive tests for manifests over accepted M86 mini-TSIL packages, accepted
  M92 exact-array backend-handoff packages, accepted M95 selected-body
  direct-intrinsic packages, and a mixed per-candidate package set.
- Determinism tests for package ordering, manifest keys, stage output keys,
  and repeated pipeline runs.
- Pipeline/stage tests proving the manifest stage appears after accepted
  operation-package facts and preserves existing M86/M92/M95 package facts,
  object identities, selected-branch-only behavior, and snapshots.
- Negative tests for unsupported sources, no packages, duplicate package keys,
  malformed package entries, candidate/source-location/provenance mismatch,
  wrong stage inputs, ambiguous containers, and unresolved dependency
  provenance mismatch, including equal-but-copied unresolved dependency
  requests.
- Import-boundary, line-count, and forbidden-behavior tests proving no growth
  in `boundary.py`, no new `_operation_package_sources.py` package router, no
  backend maps/catalog reads, no backend planning, no renderer-ready IR, no
  source repair, no generic registry/dispatcher, and no fixpoint/backfeed
  machinery.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package*.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m96 or completion_manifest or operation_package"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line-count validation returned `boundary.py` 1,300,
  `_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
  and `2,895 total`.
- Py-compile returned exit 0 with no output.
- Focused M96/manifest/operation-package pytest returned
  `17 passed, 326 deselected in 18.10s`.
- Full lowering-boundary pytest returned `343 passed in 148.42s`.
- Lowering mypy returned `Success: no issues found in 36 source files`.
- Full tooling validation returned corpus probes `3 passed`, unittest
  discovery `Ran 677 tests ... OK`, compileall OK, ruff
  `All checks passed!`, mypy `Success: no issues found in 140 source files`,
  and diff-check OK.
- Standalone `git diff --check` returned exit 0 with no output.

Review risks:

- Letting "completion" mean semantic body completion, backend planning,
  backend-value resolution, renderer-ready IR, or generated output instead of
  Stage 8 lowering-readiness/provenance.
- Creating a second monolith in a manifest module or growing
  `_operation_package_sources.py` into a central package-family router.
- Converting package-family tags or hardware-looking tokens into semantic
  dispatch keys.
- Introducing operation scheduling, dependency solving, registries,
  dispatchers, hidden backfeeds, or fixpoint behavior under the name
  "manifest graph". Any graph-like structure is only an identity/provenance
  graph of accepted operation-package records and explicit unresolved
  dependency references; it is not an operation DAG, dependency closure,
  backend plan, renderer IR, wrapper plan, artifact plan, registry,
  dispatcher, backfeed, or fixpoint mechanism.

Planning follow-ups:

- Stage 9 backend planning remains deferred after M96. The next planning pass
  should focus on lowering unless it explicitly selects a narrow,
  boundary-reviewed handoff.
- `boundary.py` remains exactly at the 1,300-line guardrail and
  `_operation_package_sources.py` remains exactly at 819 lines. The next
  lowering slice should extract before adding ownership to either pressure
  point.
- If the Stage 8 manifest becomes public API later, add explicit
  facade/export stability tests. It is currently a private lowering module
  with stage-contract integration.

Next concrete prompt:

- `docs/agent/runs/post-m96-planning-plus-review-prompt.md` runs post-M96
  planning and review with a lowering focus.

### Milestone 97: Lowering Completion Gap Inventory Slice

Status:

Accepted. The M97 execution-review loop returned `Accept With Follow-Ups`
after focused test-only revisions. It implemented the selected Stage 8
lowering completion gap inventory and integrated the
`lowering_completion_gap_inventory` stage after
`lowering_completion_manifest` while preserving the line-count guardrails.

Goal:

Create one typed Stage 8 lowering-owned gap inventory over accepted M96
completion manifests. M97 should turn "what is still unresolved for lowering?"
into an explicit typed artifact without starting backend planning, resolving
backend values, repairing source bodies, or inferring broad body semantics.

For M97, a "gap" means only a lowering-observed deferred or unsupported fact
visible from accepted M96 manifest facts. The initial supported gap is the
accepted unresolved backend-handoff dependency record preserved by M96. A
manifest without such records produces a deterministic no-known-gap inventory.

Scope:

- Add focused private lowering ownership in
  `_lowering_completion_gap_inventory.py` for gap-inventory models,
  diagnostics, validation, and assembly.
- Consume accepted `Stage8LoweringCompletionManifestIr` values,
  `lowering_completion_manifest` stages, or a narrow one-manifest container.
- Preserve source manifest, package record, package object, unresolved
  dependency record, and source dependency request object identity.
- Produce a deterministic typed inventory value, such as
  `Stage8LoweringCompletionGapInventoryIr`, with candidate identity,
  source-location provenance, inventory state, stable keys, and explicit
  gap records.
- Add one deterministic Stage 8 stage,
  `lowering_completion_gap_inventory`, after accepted
  `lowering_completion_manifest` facts while preserving `boundary.py` at or
  below the 1,300-line guardrail.
- Keep `_operation_package_sources.py` unchanged. M97 consumes M96 manifests;
  it must not add another operation-package source family or source router
  branch.

Out of scope:

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  backend support decisions, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, renderer-ready IR,
  rendering, generated output, generated tests, CLI/report/writer behavior,
  compiler execution, or Rust.
- New operation-package source families, package-family registries, semantic
  dispatchers, callback maps, plugin systems, hidden recursive backfeeds,
  fixpoint machinery, dependency-closure graphs, or operation DAGs.
- Re-entering raw M86 statements, M92 handoff assembly, M63 envelopes, M90/M89/
  M72/M67 provenance chains, raw body text, source-body repair, broad TSIL/body
  parsing, direct-intrinsic/SVE semantics, byte-size-to-token inference,
  declaration/array/store/return/body semantics, or broad
  `value<backend>(...)` evaluation.

Required input:

- Accepted M96 `Stage8LoweringCompletionManifestIr` behavior, diagnostics,
  object-identity preservation, deterministic keys, and private-module import
  boundary.
- Accepted M96 unresolved dependency manifest records for M92/M90 backend
  handoff provenance.
- Current line-count pressure points before M97: `boundary.py` at 1,300 lines
  and `_operation_package_sources.py` at 819 lines.

Expected outputs:

- A typed Stage 8 lowering completion gap inventory per accepted manifest.
- A no-known-gap inventory state for manifests without explicit unresolved
  dependency records.
- Gap records for accepted unresolved backend-handoff dependencies that
  preserve M96 object references without resolving them.
- Diagnostics for unsupported sources, missing manifests, multiple manifests,
  wrong stage/order, malformed manifests, candidate/source-location mismatch,
  and copied/equal-but-not-identical manifest/package/dependency records.
- Import-boundary and line-count guardrails proving the new private module does
  not become a replacement monolith and the pressure-point modules do not grow.

Tests required:

- Positive tests for gap inventories over accepted M96 manifests produced from
  mini-TSIL, selected-body direct-intrinsic, exact-array backend-handoff, and
  mixed package sets.
- Tests proving exact-array inventory records preserve unresolved dependency
  record and dependency request object identity from M96.
- Tests for no-known-gap inventories where a manifest has no unresolved
  dependencies.
- Determinism tests for repeated inventory construction, inventory keys, and
  reordered inputs.
- Pipeline/stage tests proving `lowering_completion_gap_inventory` follows
  `lowering_completion_manifest` when stage integration is implemented.
- Negative diagnostics for unsupported source, empty/missing manifests,
  multiple manifests, wrong stage, malformed manifest, candidate/source-location
  mismatch, and copied/equal-but-not-identical records.
- Import-boundary and forbidden-behavior tests proving no imports of
  `boundary.py`, the `tslgen.lowering` package facade, backend modules,
  renderers, `tsldata`, or `frozen`, and no backend maps/catalog reads,
  rendering/output, source repair, raw body parsing, registries, dispatchers,
  schedulers, hidden backfeeds, or fixpoint behavior.
- Line-count tests requiring `boundary.py <= 1300`,
  `_operation_package_sources.py <= 819`, and the new gap-inventory module
  below the module-size guardrail.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m97 or completion_gap_inventory or completion_manifest"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line counts: `boundary.py` 1,285, `_operation_package_sources.py` 819,
  `_lowering_completion_manifest.py` 776, and
  `_lowering_completion_gap_inventory.py` 564.
- Required py-compile returned exit 0 with no output.
- Focused M97/manifest/gap-inventory pytest returned
  `14 passed, 334 deselected`.
- Full lowering-boundary pytest returned `348 passed`.
- Focused lowering mypy returned
  `Success: no issues found in 37 source files`.
- Full tooling validation returned exit 0 with corpus probes `3 passed`,
  unit discovery `682` tests OK, compileall OK, ruff OK, mypy
  `Success: no issues found in 141 source files`, and diff-check OK.
- Standalone final `git diff --check` returned exit 0 with no output.

Review risks:

- Treating a gap inventory as backend readiness, renderer readiness,
  dependency closure, operation scheduling, or semantic body completion.
- Letting "other accepted lowering facts" become a broad source protocol
  instead of an explicit allowlist reachable through M96 manifest object
  references.
- Growing `boundary.py`, `_operation_package_sources.py`, or
  `_lowering_completion_manifest.py` instead of using focused gap-inventory
  ownership.
- Introducing backend maps/catalog reads, source repair, raw body parsing,
  registries, dispatchers, backfeeds, fixpoint behavior, or hardwiring under
  the name "inventory".

Execution follow-ups:

- `boundary.py` remains near the 1,300-line guardrail and stayed below it
  partly through compressed stage-helper coordination. The next lowering slice
  should extract coordination/stage helper ownership before adding more state
  there.

Next concrete prompt:

- `docs/agent/runs/post-m97-planning-plus-review-prompt.md` runs post-M97
  planning and review with a lowering focus.

### Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice

Status:

Accepted. The M98 execution-review loop returned `Accept With Follow-Ups`
after one focused public-facade import correction and documentation
finalization. It implemented the selected behavior-preserving Stage 8
stage-assembly ownership extraction and kept the extracted module narrow.

Goal:

Keep the Stage 8 lowering pipeline maintainable before adding more lowering
semantics. M98 is behavior-preserving architecture work: it extracts accepted
stage construction and per-candidate Stage 8 result assembly from `boundary.py`
into a focused private stage-assembly module while preserving all accepted
M57-M97 behavior.

The extraction reduces `boundary.py` pressure without creating a replacement
monolith. The new module owns accepted stage construction and the accepted
operation-package -> completion-manifest -> completion-gap-inventory tail
assembly only.

Scope:

- Added focused private ownership in
  `tslgen.lowering._lowering_stage_assembly` for accepted
  `GenerationLoweringStage` construction helpers and per-candidate Stage 8
  result assembly.
- Moved accepted stage helper construction out of `boundary.py` for existing
  stages such as recognition, typed generation values/predicates,
  generation-control-flow pruning, selected-body lowering, selected-body form/
  IR/envelope lowering, lowering operation packages, completion manifests, and
  completion gap inventories.
- Extracted the repeated accepted operation-package -> completion-manifest ->
  completion-gap-inventory tail assembly into a narrow typed helper/result.
- Preserved `LoweringRequest`, `LoweredImplementation`, `LoweringPlan`, public
  imports, accepted diagnostics, accepted stage names, stage ordering, stage
  keys, deterministic ordering, output identities, source locations, and
  object identity behavior.
- Kept `boundary.py` as the public facade and owner for request/result models,
  `lower_candidates`, and `_lower_input` unless a tiny helper move is
  explicitly necessary for the stage-assembly extraction.
- Kept `_operation_package_sources.py` unchanged.

Out of scope:

- New lowering semantics, new generation-time helper forms, new
  operation-package families, broad TSIL/body parsing, raw body parsing,
  source-body repair, or best-effort source correction.
- Backend translation, backend map/catalog reads, backend-uninit resolution,
  backend support decisions, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, renderer-ready IR,
  rendering, generated output, generated tests, Rust, CLI/report/writer
  behavior, or compiler execution.
- Registries, dispatchers, callback maps, plugin systems, broad source
  protocols, hidden backfeeds, fixpoint machinery, operation DAGs, or
  dependency-closure graphs.
- Moving public request/result model ownership, changing public facade exports,
  or making the new module import `boundary.py`, the `tslgen.lowering` facade,
  backend modules, renderers, `tsldata`, or `frozen`.

Required input:

- Accepted M57-M97 lowering stage behavior, diagnostics, stage names, stage
  ordering, deterministic keys, output identities, selected-branch-only
  diagnostics, public imports, and no-external-input boundaries.
- Accepted M96 completion manifest and M97 completion gap inventory behavior
  and object-identity contracts.
- Current line-count pressure points after M97: `boundary.py` 1,285 physical
  lines and `_operation_package_sources.py` 819 physical lines.

Expected outputs:

- A focused private stage-assembly module,
  `_lowering_stage_assembly.py`, below the module-size guardrail.
- `boundary.py` reduced to 1,241 physical lines while continuing to act as the
  public facade.
- `_operation_package_sources.py` unchanged at 819 physical lines.
- Behavior-preserving stage construction for all accepted M57-M97 stage facts.
- Behavior-preserving per-candidate completion-tail assembly for accepted
  operation packages, completion manifests, and completion gap inventories.
- Import-boundary and line-count guardrails proving the new module is not a
  replacement monolith.

Tests required:

- Stage-construction parity tests proving stage names, outputs, output
  identities, stage keys, and ordering match the accepted pre-M98 behavior.
- Mini-TSIL and exact-array path parity tests proving the operation-package ->
  completion-manifest -> completion-gap-inventory tail remains unchanged.
- Tests proving M96 package/manifest and M97 gap-inventory object identities
  are preserved across the extracted assembly helper.
- Determinism tests for repeated lowering, stage keys, lowered implementation
  keys, and reordered accepted inputs where applicable.
- Public import stability tests for the accepted `tslgen.lowering` and
  `tslgen.lowering.boundary` surfaces.
- Import-boundary tests proving the new module does not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Line-count tests requiring `boundary.py <= 1285`,
  `_operation_package_sources.py <= 819`, and the new stage-assembly module
  below the module-size guardrail.
- Forbidden-behavior tests or source assertions proving M98 introduces no
  backend maps/catalog reads, backend-uninit resolution, Stage 9 planning,
  renderer-ready IR, rendering/output, source repair, raw body parsing,
  registries, dispatchers, schedulers, hidden backfeeds, fixpoint behavior, or
  hardwiring.

Validation commands:

- `wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m98 or stage_assembly or completion_manifest or completion_gap_inventory or operation_package"`
- `PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py`
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering`
- `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`
- `git diff --check`

Validation result:

- Line counts: `boundary.py` 1,241, `_lowering_stage_assembly.py` 189,
  `_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
  and `_lowering_completion_gap_inventory.py` 564.
- Required py-compile returned exit 0 with no output.
- Focused M98/stage-assembly/package/manifest/gap-inventory pytest returned
  `27 passed, 325 deselected`.
- Full lowering-boundary pytest returned `352 passed`.
- Focused lowering mypy returned
  `Success: no issues found in 38 source files`.
- Full tooling validation returned exit 0 with corpus probes `3 passed`,
  unit discovery `686` tests OK, compileall OK, ruff OK, mypy
  `Success: no issues found in 142 source files`, and diff-check OK.
- Standalone final `git diff --check` returned exit 0 with no output.

Review risks:

- Letting the extracted module become a generic coordinator, registry,
  dispatcher, callback map, broad source protocol, hidden backfeed, or fixpoint
  mechanism.
- Moving request/result model ownership or public facade behavior when the
  selected slice only needs stage construction and result assembly.
- Accidentally changing accepted M57-M97 stage ordering, keys, diagnostics,
  output identities, object identities, or selected-branch-only diagnostics.
- Routing more ownership through `_operation_package_sources.py`.
- Adding backend translation, backend map/catalog reads, Stage 9 planning,
  renderer-ready IR, rendering/output, source repair, raw body parsing, or new
  semantics under the name "coordinator".

Execution follow-ups:

- Future lowering additions may reuse `_lowering_stage_assembly.py` for
  accepted stage construction/result assembly, but must not broaden it into a
  generic coordinator, registry, dispatcher, callback map, hidden backfeed,
  fixpoint mechanism, or semantic lowering milestone.

Next concrete prompt:

- `docs/agent/runs/post-m98-planning-plus-review-prompt.md` runs post-M98
  planning and review with a lowering focus.

### Milestone 99: Operation Package Backend-Translation Request Inventory Slice

Status:

Accepted. The M99 execution-review loop returned `Accept` after focused
extensibility and validation revisions.

Goal:

Create one typed, deterministic Stage 8 lowering-owned inventory of accepted
backend-scoped request facts visible from current operation packages,
completion manifests, and gap inventories. M99 should make the next backend
translation/planning handoff explicit without starting backend translation or
Stage 9 planning.

For M99, "backend-translation request inventory" means inventory/provenance
over already accepted deferred/backend-scoped request facts. It does not mean
translation, backend value resolution, backend support decisions, operation
scheduling, dependency closure, renderer-ready IR, or generated output.

M99 also creates and maintains
`docs/redesign/missing-lowering-inventory.md` as the redesign-owned list of
known missing lowering work. That document is a planning aid only, not a
runtime input, generated artifact, source scanner, dependency-closure plan, or
completion oracle.

Scope:

- Add focused private lowering ownership for typed inventory models,
  diagnostics, validation, deterministic keys, source adaptation, and assembly.
  The accepted implementation splits this ownership across
  `_lowering_backend_translation_request_inventory.py`,
  `_lowering_backend_translation_request_sources.py`, and
  `_lowering_backend_translation_request_diagnostics.py`.
- Add one deterministic Stage 8 stage after accepted
  `lowering_completion_gap_inventory`, such as
  `lowering_backend_translation_request_inventory`.
- Consume only accepted typed Stage 8 facts: accepted M93-M95 operation
  packages, accepted M96 completion manifests, accepted M97 gap inventories,
  accepted M98 stage assembly outputs, and their preserved object references.
- Preserve source manifest, package record, package object, gap record,
  unresolved dependency record, and dependency request object identity.
- Produce typed deterministic inventory records for currently visible
  lowering-owned backend-scoped request states:
  - exact-array `value<backend>(uninit::array)` deferred backend-value request
    from accepted M92/M96/M97 facts;
  - selected-body direct-intrinsic package handoff as a later backend-owned
    body/direct-intrinsic request state, preserving accepted M62/M63/M95
    provenance without interpreting direct-intrinsic or SVE semantics;
  - explicit no-accepted-request / no-known-request inventory state for
    package families with no accepted backend-scoped request facts.
- Keep `boundary.py` as the public facade and request/result model owner.
- Keep `_operation_package_sources.py`, `_lowering_completion_manifest.py`,
  and `_lowering_completion_gap_inventory.py` from receiving request-inventory
  ownership.
- Use `_lowering_stage_assembly.py` only for narrow stage construction/result
  assembly integration if needed; do not broaden it into a coordinator.

Out of scope:

- Backend translation, backend map/catalog/lang reads, backend manifest reads,
  `tsldata/detail/lang` reads, backend-uninit resolution, backend support
  decisions, Stage 9 backend planning, operation scheduling, primitive
  dependency closure, dependency solving, operation DAGs, wrapper planning,
  artifact planning, renderer-ready IR, rendering, generated C++ or Rust
  output, generated tests, CLI/report/writer behavior, compiler execution, or
  host hardware dependency.
- Generic `value<backend>(...)` or `type<backend>(...)` evaluation, intrinsic
  suffix/prefix/post/infix/immediate resolution, type spelling, vector/register
  metadata resolution, direct-intrinsic/SVE semantics, or byte-size-to-token
  inference.
- Raw `.tsl` source text parsing, source-body reparsing, source repair,
  source normalization, broad TSIL/body parsing, or best-effort correction.
- New operation-package source families, broad source protocols, registries,
  dispatchers, callback maps, plugin systems, hidden recursive backfeeds,
  fixpoint machinery, dependency-closure graphs, or lookup tables keyed by raw
  helper text, backend id, extension id, type tag, primitive name, source
  location, or direct-intrinsic token text.
- Treating the new missing-lowering inventory document as evidence by itself,
  a runtime dependency, or a broad TODO dump disconnected from accepted docs
  and repository evidence.

Required input:

- Accepted M92 exact-array backend-handoff request behavior and unresolved
  backend-handoff dependency provenance.
- Accepted M93/M94 operation-package behavior and source-family distinction.
- Accepted M95 selected-body direct-intrinsic package behavior and provenance.
- Accepted M96 completion manifest and M97 gap inventory behavior, diagnostics,
  deterministic ordering, keys, and object-identity preservation.
- Accepted M98 stage-assembly behavior, public facade stability, and
  no-coordinator guardrails.
- Current pressure points after M98: `boundary.py` 1,241 lines,
  `_operation_package_sources.py` 819 lines,
  `_lowering_completion_manifest.py` 776 lines,
  `_lowering_completion_gap_inventory.py` 564 lines, and
  `_lowering_stage_assembly.py` 189 lines.

Accepted outputs:

- One typed Stage 8 backend-translation request inventory value per selected
  candidate, with deterministic keys and record ordering. The accepted stage
  name is `lowering_backend_translation_request_inventory`.
- Inventory records that distinguish accepted backend-scoped request facts
  from explicit no-accepted-request states without inferring missing requests.
  The accepted inventory states are `has_accepted_backend_scoped_requests` and
  `no_accepted_backend_scoped_requests`.
- Exact-array request records that preserve accepted M96/M97 unresolved
  dependency and dependency request object identity with kind
  `exact_array_backend_value_uninit_array`.
- Selected-body direct-intrinsic request/handoff records that preserve accepted
  M62/M63/M95 provenance without interpreting intrinsic token text, with kind
  `selected_body_direct_intrinsic_handoff`.
- No-request records for packages without accepted backend-scoped request facts,
  with reason `no_accepted_backend_scoped_request`.
- A new living planning document,
  `docs/redesign/missing-lowering-inventory.md`, recording known missing
  lowering work, accepted coverage, selected next gap, and guardrails.
- Import-boundary and line-count guardrails proving the new module is focused
  and pressure-point modules do not become replacement monoliths.

Tests required:

- Positive tests for exact-array backend-value request inventory records,
  selected-body direct-intrinsic handoff/request records, mini-TSIL or other
  no-accepted-request states, and mixed per-candidate inventories.
- Tests proving request records preserve accepted source manifest, package
  record, package object, gap record, unresolved dependency record, and
  dependency request object identity where those references exist.
- Determinism tests for inventory keys, record ordering, repeated lowering,
  and reordered accepted inputs.
- Stage tests proving the new stage follows `lowering_completion_gap_inventory`
  without changing accepted M57-M98 stage names, ordering, keys, diagnostics,
  output identities, object identities, selected-branch-only behavior, public
  imports, or no-external-input boundaries.
- Negative diagnostics for unsupported source, missing manifest, missing gap
  inventory, multiple manifests/inventories, manifest/inventory mismatch,
  wrong stage/order, malformed entries, copied/equal-but-not-identical
  records, candidate/source-location mismatch, and provenance mismatch.
- Import-boundary and forbidden-behavior tests proving the new module does not
  import `boundary.py`, the `tslgen.lowering` package facade, backend modules,
  renderers, `tsldata`, or `frozen`, and introduces no backend maps/catalog
  reads, backend translation, Stage 9 planning, renderer-ready IR, rendering,
  output, source repair, raw body parsing, registries, dispatchers, schedulers,
  hidden backfeeds, fixpoint behavior, dependency closure, or hardwiring.
- Line-count tests or source assertions keeping `boundary.py`,
  `_operation_package_sources.py`, `_lowering_completion_manifest.py`,
  `_lowering_completion_gap_inventory.py`, `_lowering_stage_assembly.py`, and
  the new request-inventory module within the module-size guardrails. Prefer a
  new focused test file if adding all M99 coverage to
  `test_lowering_boundary.py` would make that file harder to maintain.

Validation results:

- Line counts: `boundary.py` 1,254,
  `_operation_package_sources.py` 819,
  `_lowering_completion_manifest.py` 776,
  `_lowering_completion_gap_inventory.py` 564,
  `_lowering_stage_assembly.py` 223,
  `_lowering_backend_translation_request_inventory.py` 770,
  `_lowering_backend_translation_request_sources.py` 207, and
  `_lowering_backend_translation_request_diagnostics.py` 64.
- Required py-compile returned exit 0 with no output.
- Focused M99/package/manifest/gap-inventory pytest returned
  `27 passed, 330 deselected in 87.81s`.
- Full lowering-boundary pytest returned
  `357 passed in 741.11s (0:12:21)`.
- Focused lowering mypy returned
  `Success: no issues found in 41 source files`.
- Full tooling validation returned exit 0 with corpus probes `3 passed`,
  unittest discovery `691` tests OK, compileall OK, ruff OK, mypy
  `Success: no issues found in 145 source files`, and diff-check OK.
- Standalone `git diff --check` returned exit 0 with no output.

Execution review notes:

- Boundary review accepted M99 as Stage 8 inventory/provenance only, with no
  backend translation, Stage 9 planning, renderer-ready IR, rendering/output,
  source repair, raw body parsing, dependency closure, scheduling, backfeeds,
  fixpoint behavior, or hardwiring.
- Extensibility review initially found the near-guardrail inventory module too
  broad. The accepted revision split diagnostics and source/container
  adaptation into focused private modules.
- Validation review initially found missing manifest-container diagnostic cases
  and a full-suite mypy annotation issue. The accepted revision added the
  diagnostic cases and type annotation.

Accepted follow-ups:

- Future lowering milestones should update
  `docs/redesign/missing-lowering-inventory.md` when they accept, resolve,
  narrow, or discover lowering gaps.

Next concrete prompt:

- `docs/agent/runs/post-m99-planning-plus-review-prompt.md` runs post-M99
  planning and review with a lowering focus.

### Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice

Status:

Accepted. Post-M99 planning selected this milestone and internal planning
review returned `Accept With Follow-Ups`. Human acceptance was recorded. The
M100 execution-review loop returned `Accept With Follow-Ups` after focused
rule-validation, source/container diagnostic, determinism, and documentation
revisions.

Goal:

Resolve the accepted M99 exact-array
`exact_array_backend_value_uninit_array` request into typed C++ backend
translation-result state without rendering code or starting Stage 9 backend
planning. M100 proves the first concrete handoff from accepted Stage 8 request
inventory facts to a backend translation-result boundary.

For M100, "translation result" means a typed value record produced from
accepted request/provenance facts and explicit typed C++ translation
rule/metadata input. It does not mean C++ or Rust source rendering, declaration
or body IR completion, artifact planning, backend support decisions, scheduling,
dependency closure, or generic backend helper evaluation.

Scope:

- Added focused private lowering ownership for typed backend translation-result
  models, C++ exact-array uninit rule values, diagnostics, validation,
  deterministic keys, source/request narrowing, and optional stage assembly in
  `_lowering_backend_translation_result.py`,
  `_lowering_backend_translation_result_sources.py`, and
  `_lowering_backend_translation_result_diagnostics.py`.
- Consumes only accepted M99 `Stage8BackendTranslationRequestInventoryIr`
  records and their preserved accepted M97/M96/M92/M72/M67 object references.
- Selects only request records with kind
  `exact_array_backend_value_uninit_array`.
- Supports only the exact C++ array-uninit backend value rule evidenced by the
  `value_array_uninit` metadata shape; the stage receives typed rule values and
  does not read `tsldata/detail/lang/translate_cpp.tsl` at runtime.
- Produces one typed translation-result value per accepted exact-array request,
  preserving request record, unresolved dependency, dependency request,
  completion manifest, gap inventory, and source package identity where those
  references exist.
- Adds a deterministic result/no-result state after
  `lowering_backend_translation_request_inventory`, with stage name
  `exact_array_backend_uninit_translation_result`.
- Keeps `boundary.py` as a narrow facade and keeps focused M100 coverage in
  `tslgen/tests/unit/test_lowering_backend_translation_result.py`.

Out of scope:

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

Required input:

- Accepted M99 backend-translation request inventory behavior and request
  record identity/provenance.
- Accepted M97 gap-inventory and M96 completion-manifest unresolved dependency
  identity behavior.
- Accepted M92 exact array backend-handoff request behavior.
- Accepted M72/M67 exact array deferred backend-uninit request behavior.
- Explicit typed C++ translation rule/metadata input for exact
  `value_array_uninit`, supplied by the caller/test fixture rather than read
  from `tsldata` during lowering.
- Execution-time pressure points at planning start: `boundary.py` 1,254 lines,
  `_lowering_backend_translation_request_inventory.py` 770 lines,
  `_lowering_stage_assembly.py` 223 lines, `cpp/translation.py` near the
  module-size guardrail, and `test_lowering_boundary.py` already too large for
  major new coverage.

Expected outputs:

- One typed C++ exact-array backend-uninit translation-result value for each
  accepted exact-array M99 request record.
- Deterministic result keys and ordering.
- Result records that preserve accepted M99 request record identity and the
  relevant M97/M96/M92/M72/M67 provenance/object identities.
- Explicit unsupported/no-result diagnostics for non-exact-array request kinds,
  unsupported backend ids including Rust, missing/duplicate/conflicting typed
  C++ uninit rules, malformed request records, provenance mismatches, and
  copied/equal-but-not-identical records.
- Import-boundary and line-count guardrails proving M100 does not grow
  `boundary.py`, M99 inventory modules, `cpp/translation.py`, or a new private
  module into a replacement monolith.

Tests required:

- Positive C++ exact-array uninit translation-result tests from accepted M99
  inventory records.
- Tests proving object identity is preserved from the M100 result back through
  M99 request inventory, M97 gap inventory, M96 completion manifest, M92
  backend handoff, M72 deferred backend-uninit boundary, and M67 request
  record where those values are present.
- Determinism tests for result keys, ordering, repeated lowering, and reordered
  accepted inputs.
- Stage tests proving the new result stage follows
  `lowering_backend_translation_request_inventory` without changing accepted
  M57-M99 stage names, ordering, keys, diagnostics, output identities, object
  identities, selected-branch-only behavior, public imports, or no-external-
  input boundaries.
- Negative diagnostics for missing typed C++ rule, duplicate/conflicting typed
  rules, unsupported backend/Rust, wrong request kind, selected-body
  direct-intrinsic handoff, malformed request record, copied/equal-but-not-
  identical provenance, candidate/source-location mismatch, and unsupported
  source/container inputs.
- Forbidden-behavior tests proving M100 does not read `tsldata`, backend
  maps/catalogs/manifests, or `frozen`; does not import renderers or backend
  planners; and does not introduce Stage 9 planning, renderer-ready IR,
  rendering/output, source repair, raw body parsing, registries, dispatchers,
  schedulers, dependency closure, hidden backfeeds, fixpoint behavior, or
  hardwiring.
- Prefer a focused new test file for M100 unit coverage, with only minimal
  public facade/stage integration tests in existing broad lowering tests if
  needed.

Validation required:

- `wc -l` for `boundary.py`, M99 request-inventory modules, the new M100
  module or modules, `_lowering_stage_assembly.py`, and any touched backend
  module.
- `PYTHONPATH=tslgen/src python -m py_compile` for touched lowering/backend
  modules and the new M100 test module.
- Focused pytest for M100 backend-uninit translation-result behavior.
- Focused pytest covering M99 request inventory plus M100 result integration.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` for
  touched packages or modules.
- `git diff --check`.

Planning review notes:

- Planner selected M100 as more valuable than another Stage 8 inventory-only
  slice because M99 already exposes a concrete request that should prove the
  typed request-to-translation-result handoff.
- Boundary review accepted the plan with follow-ups requiring typed metadata
  input, no backend map/catalog/manifest reads, no renderer-ready IR, no Stage
  9 planning, and explicit rejection/deferment of selected-body direct-
  intrinsic handoffs.
- Extensibility review accepted the plan with follow-ups to keep ownership in
  new focused modules, avoid near-guardrail backend translation modules, keep
  `boundary.py` narrow, and put most tests in a focused new test file.
- Documentation review required roadmap/state/design docs and
  `docs/redesign/missing-lowering-inventory.md` to record that M100 narrows
  only exact C++ backend-uninit translation-result work.

Satisfied planning constraints:

- M100 keeps translation metadata as explicit typed input and does not read
  backend maps/catalogs/manifests or `tsldata/detail/lang` during lowering.
- M100 keeps the result as typed backend value state only, not
  renderer-ready IR, declaration/body IR, Stage 9 planning, generated output,
  Rust, or generic backend helper evaluation.
- M100 uses focused private modules and avoids growing pressure-point modules
  into replacement monoliths.

Next concrete prompt:

- `docs/agent/runs/post-m100-planning-plus-review-prompt.md` runs post-M100
  planning and review with a lowering focus.

Execution review notes:

- Review found and the focused revision fixed a rule-validation gap where an
  unsupported Rust `value_array_uninit` rule could be ignored when a valid C++
  rule was also present.
- Validation review found and the focused revision added unsupported
  source/container diagnostics plus reordered-input determinism coverage.
- Documentation review required final accepted-state wording in roadmap/state
  and missing-lowering inventory docs.
- Extensibility review accepted the module split with a non-blocking follow-up
  that `boundary.py` remains close to the size guardrail and should not receive
  more orchestration without extraction.

Accepted follow-ups:

- Future milestones should avoid adding more orchestration to `boundary.py`
  without extracting boundary request/result assembly, because it remains close
  to the module-size guardrail after M100.

### Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice

Status:

Accepted. M101 added a small private lowering IR contract/provenance module
and applied it only to the accepted M99/M100 backend-translation request/result
path. The slice preserved accepted M99/M100 behavior, keys, diagnostics,
object identities, source locations, stage names, ordering, and public imports.

Goal:

Define and enforce a smaller lowering IR taxonomy contract, then apply it only
to the accepted M99/M100 backend-translation request/result path. M101 should
reduce repeated provenance and one-off request/result layering without changing
observable lowering behavior or adding new backend semantics.

For M101, "IR taxonomy contract" means a narrow set of stable categories:
semantic facts, requests, results, inventories, provenance values, rule inputs,
and stage envelopes. It does not mean a broad inheritance hierarchy, a generic
semantic dispatcher, a registry, a callback system, a plugin mechanism, or a
rewrite of every existing lowering IR class.

Scope:

- Add or update redesign documentation that states the lowering IR taxonomy
  contract and the rules for adding future IR types.
- Add focused private lowering ownership if implementation needs a small shared
  contract module, such as a provenance/reference helper or protocol module,
  but keep it behavior-neutral and narrowly applied.
- Apply the contract only to the accepted M99/M100 backend-translation
  request/result path, especially repeated candidate/source-location/provenance
  and object-identity validation patterns.
- Preserve all accepted M99/M100 public imports, stage names, stage ordering,
  keys, diagnostics, source locations, object identities where required, and
  deterministic ordering.
- Keep `boundary.py` as a narrow facade; do not add more orchestration there.
- Prefer focused tests in a new or existing M99/M100-specific test module
  rather than adding large coverage to `test_lowering_boundary.py`.

Out of scope:

- New lowering semantics, new request families, new translation result
  families, C++ declaration/body assembly, Rust translation, generic
  `value<backend>(...)` or `type<backend>(...)` evaluation, backend
  map/catalog/manifest reads during lowering, backend support decisions,
  Stage 9 backend planning, rendering, generated output, operation scheduling,
  dependency closure, wrapper planning, artifact planning, CLI/report/writer
  behavior, compiler execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair,
  source normalization, best-effort correction, broad TSIL/body parsing,
  selected-body direct-intrinsic resolution, SVE/direct-intrinsic semantics,
  byte-size-to-token inference, or vector/register metadata expansion.
- A broad base-class hierarchy imposed across M57-M100 IR, a new registry,
  dispatcher, callback map, plugin mechanism, hidden backfeed, or fixpoint
  machinery.

Expected outputs:

- The documented lowering IR taxonomy contract now has a narrow private code
  contract in `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`.
- M99/M100 request, no-request, inventory, rule-input, record, and result
  classes expose explicit `ir_contract` values for the stable categories
  `request`, `provenance`, `inventory`, `rule_input`, and `result`.
- Repeated key-comparison and provenance identity mismatch checks in the
  M99/M100 path now use the shared contract helpers without changing keys or
  diagnostic messages.
- Focused tests prove accepted M99/M100 behavior, diagnostics, deterministic
  keys, object identity, source locations, import boundaries, and line-count
  guardrails are preserved.

Tests required:

- Focused regression tests for M99 backend-translation request inventory and
  M100 exact-array C++ backend-uninit translation-result behavior.
- Determinism tests proving result keys and ordering remain stable before and
  after the consolidation.
- Diagnostic tests proving source/container, provenance mismatch, context
  mismatch, missing/duplicate/conflicting rule, unsupported backend, and wrong
  request-kind diagnostics remain stable.
- Import-boundary tests proving any new contract module does not import
  `boundary.py`, the `tslgen.lowering` facade, backend modules, renderers,
  backend planners, `tsldata`, or `frozen`.
- Line-count tests or source assertions proving the consolidation does not grow
  `boundary.py`, M99/M100 modules, or `_lowering_stage_assembly.py` into a new
  monolith.

Validation required:

- `wc -l` for `boundary.py`, `_lowering_stage_assembly.py`, M99/M100
  backend-translation modules, and any new contract module.
- `PYTHONPATH=tslgen/src python -m py_compile` for touched lowering modules
  and touched tests.
- Focused pytest for M99/M100 backend-translation request/result behavior.
- Focused pytest for any new IR-taxonomy/provenance contract tests.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` for
  touched lowering modules and tests where practical.
- `git diff --check`.

Review notes:

- The selected milestone deliberately pauses feature expansion after M100
  because the exact-array path now has many narrow package/request/inventory/
  result layers. The next highest-value work is to prevent that shape from
  becoming the default pattern for all remaining lowering work.
- M101 should be behavior-preserving and should make future C++ declaration,
  direct-intrinsic, Rust, or Stage 9 milestones easier by giving them a smaller
  vocabulary for facts, requests, results, provenance, and rule inputs.
- M101 did not add backend semantics, new request families, new result
  families, rendering/output, Stage 9 planning, Rust translation, generic
  backend helper evaluation, backend map/catalog/manifest reads during
  lowering, raw source parsing, source repair, selected-body direct-intrinsic
  resolution, SVE semantics, scheduling, dependency closure, a broad hierarchy,
  registry, dispatcher, hidden backfeed, or fixpoint mechanism.

Accepted follow-ups:

- Future diagnostic-sensitive slices should tighten diagnostic matrix tests to
  assert exact locations and important message snippets in addition to
  code/severity.
- Future milestones should continue extracting orchestration instead of adding
  to `boundary.py`, which remains close to the module-size guardrail.

Next concrete prompt:

- `docs/agent/runs/post-m101-planning-plus-review-prompt.md` selects the next
  lowering milestone after accepted M101.

### Milestone 102: Lowering IR Category Protocol Surface Slice

Status:

Accepted. M102 added the first private typed lowering IR category/protocol
surface over the accepted M101 taxonomy and applied it only to the accepted
M99/M100 backend-translation request/result path. The slice preserved accepted
M99/M100 behavior, keys, diagnostics, source locations, object identities,
stage names, stage ordering, public imports, and deterministic behavior.

Goal:

Turn the M101 taxonomy from string/category labels into a small, explicit,
private lowering IR category surface that future milestones can target before
adding more feature-specific request/result/inventory families. M102 should
make the architecture easier to extend without introducing new lowering
semantics.

For M102, "IR category protocol surface" means typed, maintainable contracts
such as:

- `LoweringFact`: an accepted domain/semantic fact produced by lowering;
- `LoweringRequestIr`: a typed unresolved need for a later lowering/backend
  stage;
- `TranslationRequestIr`: a backend-translation-specific request category;
- `TranslationResultIr`: a typed fulfillment of a translation request from
  explicit facts/rules;
- `LoweringInventory`: a deterministic collection of accepted facts, not a
  readiness claim;
- `LoweringProvenance`: source/object identity needed for diagnostics,
  determinism, and traceability;
- `LoweringRuleInput`: explicit typed metadata supplied before evaluation;
- `LoweringStageOutput`: the typed output carried by a named stage envelope;
- `DiagnosticBoundary`: a typed boundary for malformed, unsupported, context,
  source-location, and provenance diagnostics.

The existing public `LoweringRequest` input/configuration bundle is not the
same concept as the taxonomy category "request". M102 must avoid renaming or
breaking that public API unless a focused compatibility plan is separately
accepted.

Scope:

- Add or refine private lowering contracts/protocols in the M101-owned
  contract area, likely `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
  or a focused sibling module.
- Keep the surface structural and typed, using small protocols, value objects,
  or helper predicates where useful. Do not impose a broad inheritance
  hierarchy on M57-M101 classes.
- Apply the protocol surface only to the accepted M99/M100 backend-translation
  request/result path as the first proof point.
- Preserve accepted M99/M100 keys, diagnostics, source locations, object
  identities, stage names, stage ordering, public imports, and deterministic
  behavior.
- Clarify in docs and tests that future feature-specific IR additions must
  first choose one of the stable category protocols.
- Keep `boundary.py` as a facade; do not add orchestration there.

Out of scope:

- New lowering semantics, new request families, new translation result
  families, C++ declaration/body assembly, Rust translation, generic
  `value<backend>(...)` or `type<backend>(...)` evaluation, backend
  map/catalog/manifest reads during lowering, backend support decisions,
  Stage 9 backend planning, rendering, generated output, operation scheduling,
  dependency closure, wrapper planning, artifact planning, CLI/report/writer
  behavior, compiler execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair,
  source normalization, best-effort correction, broad TSIL/body parsing,
  selected-body direct-intrinsic resolution, SVE/direct-intrinsic semantics,
  byte-size-to-token inference, or vector/register metadata expansion.
- Renaming the existing public `LoweringRequest`, rewriting all accepted
  M57-M101 IR to inherit from new base classes, introducing registries,
  dispatchers, callback maps, plugin mechanisms, hidden backfeeds, fixpoint
  machinery, or turning protocols into renderer/backend-planning APIs.

Expected outputs:

- A small private lowering IR protocol/category surface now directly answers
  the M101 taxonomy categories with stable typed names in
  `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`.
- M99/M100 request/result/rule/provenance/inventory classes classify against
  that surface without changing observable behavior.
- Focused helpers may validate or assert category/protocol shape, but they must
  not choose semantic behavior, route requests, translate backend values, or
  act as a registry/dispatcher.
- Focused tests prove category classification, import boundaries, line-count
  guardrails, deterministic keys, object identity, diagnostics, source
  locations, and public imports remain stable.
- Documentation clarifying the distinction between the existing public
  `LoweringRequest` input bundle and taxonomy-level request protocols.

Tests required:

- Focused contract/protocol tests for the new category surface.
- Negative tests proving wrong, missing, or mismatched category/protocol
  conformance is caught as a structural contract failure.
- Regression tests proving M99 backend-translation request inventory and M100
  exact-array backend-uninit translation result behavior remain unchanged.
- Diagnostic tests covering the existing malformed/source/container,
  provenance mismatch, context mismatch, source-location mismatch,
  missing/duplicate/conflicting rule, unsupported backend, and wrong
  request-kind cases.
- Import-boundary tests proving the category/protocol module does not import
  `boundary.py`, the `tslgen.lowering` facade, backend modules, renderers,
  backend planners, `tsldata`, or `frozen`.
- Line-count tests or source assertions proving the protocol surface does not
  grow `boundary.py`, `_lowering_stage_assembly.py`, M99/M100 modules, or the
  contract module into a new monolith.

Validation required:

- `wc -l` for `boundary.py`, `_lowering_stage_assembly.py`, M99/M100
  backend-translation modules, `_lowering_ir_contracts.py`, and any new
  category/protocol module.
- `PYTHONPATH=tslgen/src python -m py_compile` for touched lowering modules
  and touched tests.
- Focused pytest for the new IR category/protocol tests.
- Focused pytest for M99/M100 backend-translation request/result behavior.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` for
  touched lowering modules and tests where practical.
- `git diff --check`.

Review notes:

- M102 deliberately pauses feature expansion again because adding the next
  direct-intrinsic or backend-result family before a real category surface
  would likely recreate the one-off layering M101 was meant to contain.
- The milestone should produce a category surface, not a semantic dispatcher.
  Future milestones still own concrete request/result semantics in focused
  modules.
- M102 makes a later selected-body direct-intrinsic translation-result
  slice safer by forcing it to fit `TranslationRequestIr`,
  `TranslationResultIr`, `LoweringProvenance`, `LoweringRuleInput`, and
  `DiagnosticBoundary` contracts first.
- M102 review initially found that the type guards were checking category
  labels without validating keyed structural conformance. A focused revision
  made guards require typed contracts plus non-empty tuple keys, tightened
  backend-translation owner namespace matching, and narrowed stage-output
  recognition to explicit `stage_envelope` contracts.

Accepted follow-ups:

- None recorded for the accepted M102 implementation.

Next concrete prompt:

- `docs/agent/runs/post-m102-planning-plus-review-prompt.md` selects the next
  lowering milestone after accepted M102.

### Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice

Status:

Accepted. Post-M102 planning selected M103 as the next lowering milestone.
Internal planning review returned `Accept With Follow-Ups` after narrowing the
initial broad "worklist" idea into a static typed inventory/provenance view.
Human acceptance was recorded. The M103 execution-review loop returned
`Accept With Follow-Ups` after a focused fake-object validation revision and
focused re-review.

Goal:

Create a typed, deterministic Stage 8 backend-translation boundary worklist
inventory over already accepted backend-boundary facts. For M103, "worklist"
means a static lowering-owned inventory/provenance view, not an executable
queue, scheduler, dependency-closure plan, readiness oracle, Stage 9 backend
plan, renderer-ready IR, completeness oracle, source scanner, backend-map
evaluator, registry, dispatcher, hidden backfeed, or fixpoint mechanism.

The milestone should make the Stage 8-to-backend frontier visible in one
maintainable typed shape before adding another feature-specific backend-result
or direct-intrinsic semantic slice.

M102 taxonomy fit:

- the aggregate worklist is a lowering inventory;
- entries preserve provenance and object identity for accepted concrete M99
  `TranslationRequestIr` records and accepted concrete M100
  `TranslationResultIr` records;
- M103 must not introduce a new `work_item` taxonomy category;
- M102 protocol conformance may validate shape, but must not route semantics
  or accept arbitrary fake objects that merely satisfy a protocol.

Scope:

- Add a focused private lowering module such as
  `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`, with
  optional focused source/diagnostic siblings only if the implementation
  justifies the split.
- Consume only accepted typed M99
  `Stage8BackendTranslationRequestInventoryIr` values and optional accepted
  typed M100 `ExactArrayBackendUninitTranslationResultIr` values.
- Produce a deterministic per-candidate backend-boundary worklist inventory
  that preserves object identity to M99 request/no-request records and M100
  result/deferred records.
- Classify only accepted concrete states, such as accepted exact-array
  backend-uninit translation results, accepted exact-array translation
  requests that are still unresolved, accepted selected-body direct-intrinsic
  handoff requests that remain deferred, and explicit no-accepted-backend-
  boundary-fact records.
- Validate candidate id, source location, source inventory identity, M100
  result/inventory consistency, duplicate/conflicting entries, deterministic
  ordering, and malformed source containers with explicit diagnostics.
- Keep new worklist-specific contracts local to the new focused module unless
  a separate consolidation milestone later accepts shared ownership.
- Add focused tests in a new test file rather than expanding the already-large
  `test_lowering_boundary.py`.

Out of scope:

- Calling existing translation/result lowerers to complete missing work.
- Inferring new requests, duplicating request records by key, or resolving
  direct-intrinsic/SVE meaning.
- Pipeline integration through `LoweredImplementation`, public facade exports,
  `_lower_input` orchestration, new `GenerationLoweringStageName` /
  `_stage_contracts.py` integration, or `boundary.py` growth.
- Growing `_lowering_ir_contracts.py` into a registry of feature-specific
  contracts.
- New lowering semantics, new request/result families, backend translation
  semantics, Rust translation, generic backend helper evaluation, backend
  map/catalog/manifest reads during lowering, `tsldata/detail/lang` reads,
  runtime `frozen/` use, Stage 9 backend planning, renderer-ready IR,
  rendering, generated output, operation scheduling, dependency closure,
  wrapper planning, artifact planning, CLI/report/writer behavior, compiler
  execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair, source
  normalization, best-effort correction, broad TSIL/body parsing, token-to-
  intrinsic inference, byte-size-to-token inference, vector/register metadata
  expansion, category-based semantic dispatch, registries, dispatchers,
  callback maps, plugin mechanisms, hidden backfeeds, or fixpoint machinery.

Accepted outputs:

- New private typed Stage 8 backend-boundary worklist inventory modules:
  `_lowering_backend_boundary_worklist.py`,
  `_lowering_backend_boundary_worklist_models.py`,
  `_lowering_backend_boundary_worklist_entries.py`,
  `_lowering_backend_boundary_worklist_sources.py`,
  `_lowering_backend_boundary_worklist_validation.py`, and
  `_lowering_backend_boundary_worklist_diagnostics.py`.
- Worklist records preserve accepted M99/M100 object identity and expose
  stable keys, source locations, candidate ids, source inventory/result keys,
  and classification states.
- Diagnostics for mismatched context/source/provenance, malformed containers,
  mismatched optional M100 result, duplicate/conflicting entries, and
  unsupported source shapes.
- Tests prove deterministic ordering, protocol/category fit, object-identity
  preservation, import boundaries, line-count guardrails, and the absence of
  backend planning/rendering/source-repair/category-dispatch behavior.

Accepted tests:

- Positive tests over M99 request inventories with exact-array request,
  selected-body direct-intrinsic request, and no-request records.
- Positive tests over an M99 inventory plus matching M100 exact-array
  translation result, preserving source object identities.
- Negative tests for arbitrary M102-conformant fake objects, mismatched M100
  result inventory/candidate/source location, duplicate/conflicting worklist
  entries, missing source inventory, unsupported source containers, and
  malformed keys.
- Import-boundary/source assertions proving no `boundary.py`, public
  `tslgen.lowering` facade, backend modules, renderers, backend planners,
  `tsldata`, `frozen`, backend maps/catalogs/manifests, raw parsing helpers,
  source repair, registry/dispatcher/callback/plugin/backfeed/fixpoint, or
  category-based semantic dispatch.
- Line-count tests or source assertions proving M103 does not grow
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, or the new
  worklist module into a replacement monolith. The tests should prove
  `boundary.py` remains unchanged and below its current guardrail,
  `_lowering_ir_contracts.py` remains below its current guardrail, and the new
  worklist module stays below a focused ceiling such as 400 lines unless a
  reviewed split justifies a different limit.

Validation completed:

- `wc -l` for `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 backend-
  translation modules, the new worklist module, and any new focused
  source/diagnostic/test modules.
- `PYTHONPATH=tslgen/src python -m py_compile` for touched lowering modules
  and touched tests.
- Focused pytest for the new backend-boundary worklist tests.
- Focused pytest for M99/M100 backend-translation request/result regression
  behavior.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` for
  touched lowering modules and tests where practical.
- `git diff --check`.

Results: line count total `5248`; py-compile returned exit 0 with no output;
focused worklist pytest returned `7 passed in 13.79s`; focused M100
backend-translation result pytest returned `12 passed in 18.57s`; focused
lowering mypy returned `Success: no issues found in 53 source files`; final
`git diff --check` returned exit 0 with no output.

Review notes:

- M103 is intentionally broad at the boundary level, but narrow in semantics:
  it inventories accepted Stage 8 backend-boundary facts instead of translating
  or planning backend work.
- The worklist name must not invite scheduler/readiness behavior. Reviewers
  should reject any queue, Stage 9 planner, dependency closure, resolver
  choice, renderer-ready IR, or category-based semantic dispatcher.
- Because `boundary.py` and `_lowering_ir_contracts.py` are near line-count
  pressure points, M103 must keep ownership in a focused private module and
  avoid facade/pipeline integration unless a separate extraction milestone
  accepts that ownership first.
- After M103 is accepted, a future planning pass should select exactly one
  row/classification from the worklist or one documented lowering gap as the
  next implementation milestone.
- M103 must not add `GenerationLoweringStageName` values or `_stage_contracts.py`
  integration; it should expose a direct private lowering function over
  accepted M99/M100 values first.

Accepted follow-ups:

- Post-M102 execution follow-ups were addressed during M103: the worklist
  remained a static inventory/provenance view, worklist-specific contract
  constants stayed in the focused module set, line-count ceilings/source
  assertions were added, and arbitrary protocol-shaped fake-object negative
  tests were tightened after focused review.
- Future diagnostic-sensitive slices should keep tightening exact location and
  message-snippet assertions around malformed source/container diagnostics.
- After accepted M103, select one worklist row/classification or documented
  lowering gap as a focused implementation milestone. Addressed by post-M103
  planning, which selected M104 as one documented gap: M103 worklist entry to
  typed translation expansion result.

Next concrete prompt:

- `docs/agent/runs/post-m103-planning-plus-review-prompt.md` selects the next
  lowering milestone after accepted M103.

### Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice

Status:

Accepted. Post-M103 planning selected M104 as the next lowering milestone after
user-requested broadening. Internal planning review returned
`Accept With Follow-Ups` after local planning-doc revisions clarified that the
scope is one documented lowering gap: expanding M103 worklist entries into
typed backend translation expansion results. Human acceptance was recorded,
and the M104 execution-review loop returned `Accept With Follow-Ups`.

Goal:

Create a typed, deterministic Stage 8 lowering result boundary that consumes
accepted M103 backend-boundary worklist entries and produces typed
resolved/deferred/unsupported backend translation expansion result records.

M104 is intentionally broader than a single literal worklist classification,
but it is one coherent boundary: M103 worklist entry to typed translation
expansion result. It may cover the accepted
`exact_array_backend_uninit_unresolved` and
`selected_body_direct_intrinsic_deferred` classifications only when explicit
typed rule inputs are supplied. The worklist remains static inventory and
provenance input, not a scheduler, readiness oracle, Stage 9 plan, renderer
surface, completeness oracle, backend-map evaluator, source scanner,
dispatcher, hidden backfeed, or fixpoint mechanism.

M101/M102/M103 taxonomy fit:

- consumes a lowering inventory, specifically accepted concrete M103
  `Stage8BackendBoundaryWorklistInventoryIr` values;
- preserves provenance and object identity to accepted M103 worklist entries,
  M99 request/no-request records, optional M100 result/deferred records, and
  earlier source facts;
- adds typed translation result records, explicit typed rule input records,
  and local provenance values as needed;
- must not introduce a new `work_item` taxonomy category;
- M103 worklist classifications may filter candidate entries, but semantic
  behavior must come from concrete typed request/result objects plus explicit
  typed rule inputs, not from category dispatch.

Scope:

- Add focused private lowering modules for backend translation expansion, such
  as `_lowering_backend_translation_expansion.py` with focused model, source,
  validation, and diagnostic siblings if the split is needed.
- Consume only accepted concrete M103
  `Stage8BackendBoundaryWorklistInventoryIr` values.
- Accept only M103 entries classified as
  `exact_array_backend_uninit_unresolved` or
  `selected_body_direct_intrinsic_deferred`.
- Produce deterministic typed resolved/deferred/unsupported translation
  expansion result records.
- Resolve exact-array backend-uninit unresolved entries only from explicit
  typed rule inputs. This may extend beyond M100 only when the rule carries
  typed context M100 did not accept, such as the backend/type context required
  for a Rust or additional exact value result.
- Resolve selected-body direct-intrinsic deferred entries only from explicit
  typed rule inputs identity-bound to accepted typed request/worklist facts.
- Emit typed deferred/unsupported records with diagnostics when no explicit
  rule applies, when a rule is malformed, or when provenance/context does not
  match the accepted worklist entry.
- Preserve deterministic ordering, stable keys, source locations, candidate
  ids, source inventory/result keys, and object identities.
- Keep new M104-specific contracts local to focused M104 modules unless a
  later consolidation milestone accepts shared ownership.
- Add focused tests in a new test file rather than expanding the already-large
  `test_lowering_boundary.py`.

Out of scope:

- Rendering, renderer-ready IR, generated output, Stage 9 backend planning,
  artifact planning, wrapper planning, output/report/writer behavior, compiler
  execution, and host hardware dependency.
- Backend map/catalog/manifest reads during lowering, `tsldata/detail/lang`
  reads, generic backend helper evaluation, or raw helper text parsing.
- Calling existing translation lowerers to complete missing work.
- Source-body reparsing, source repair, source normalization, best-effort
  correction, TSIL/body broad parsing, or guessing the intended meaning of a
  malformed `.tsl` body.
- Dispatching by `svptrue_b*`, extension id, type tag, byte size, primitive
  name, raw direct-intrinsic token text, source location, or hardware-looking
  tokens.
- Direct-intrinsic/SVE semantic inference beyond explicit typed rule input.
- Rust rendering or broad Rust support; Rust exact-array uninit is allowed only
  if the typed rule input supplies the required typed backend/type context and
  the output remains a typed translation result.
- Operation scheduling, dependency closure, queues, scheduler/readiness
  behavior, registries, dispatchers, callbacks, plugins, hidden backfeeds,
  fixpoint mechanisms, or category-based semantic dispatch.
- Pipeline integration through `LoweredImplementation`, public facade exports,
  `_lower_input` orchestration, new `GenerationLoweringStageName` /
  `_stage_contracts.py` integration, or `boundary.py` growth.
- Growing `_lowering_ir_contracts.py`, M99/M100 modules, or M103 worklist
  modules for M104 ownership.

Accepted outputs:

- New private typed backend translation expansion modules:
  `_lowering_backend_translation_expansion.py`,
  `_lowering_backend_translation_expansion_models.py`,
  `_lowering_backend_translation_expansion_sources.py`,
  `_lowering_backend_translation_expansion_validation.py`, and
  `_lowering_backend_translation_expansion_diagnostics.py`.
- Typed expansion result values with resolved, deferred, and
  unsupported records.
- Explicit typed rule input values for the accepted exact-array and
  selected-body direct-intrinsic result families.
- Diagnostics for missing rules, unsupported entries, malformed/fake objects,
  duplicate/conflicting rules, mismatched worklist/provenance/source context,
  and forbidden hardwired-token behavior.
- Tests proving deterministic ordering, object-identity preservation,
  concrete-type rejection of fake protocol-shaped objects, import boundaries,
  line-count guardrails, and absence of scheduler/readiness/backend-rendering/
  hardwired-token/category-dispatch behavior.
- Malformed fake inputs and malformed containers fail at the boundary; accepted
  entries with missing rules become deferred records, and accepted entries with
  mismatched, duplicate, or conflicting explicit rules become unsupported
  records.

Accepted tests:

- Positive exact-array unresolved entry resolved by explicit typed rule input.
- Positive selected-body direct-intrinsic deferred entry resolved by explicit
  typed rule input.
- Missing rule produces typed deferred or unsupported state, not guessed
  behavior.
- Negative tests for rule mismatch, duplicate/conflicting rules, fake
  protocol-shaped worklist/rule/result objects, malformed source containers,
  malformed keys, and provenance mismatch.
- Direct-intrinsic negative tests proving no dispatch by `svptrue_b*`,
  extension id, type tag, byte size, primitive name, raw token text,
  source-location text, or hardware-looking tokens.
- Determinism tests for ordering and repeat-run equality.
- Import-boundary/source assertions proving no `boundary.py`, public facade,
  backend modules, renderers, backend planners, `tsldata`, `frozen`, backend
  maps/catalogs/manifests, raw parsing helpers, source repair, registry/
  dispatcher/callback/plugin/backfeed/fixpoint behavior, or category-based
  semantic dispatch.
- Line-count tests or source assertions proving M104 does not grow
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, M103 worklist
  modules, or new M104 modules into replacement monoliths.

Validation completed:

- `wc -l` for `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 backend-
  translation modules, M103 worklist modules, new M104 modules, and the new
  focused M104 test file.
- `PYTHONPATH=tslgen/src python -m py_compile` for touched/new lowering
  modules and touched/new tests.
- Focused pytest for the new backend translation expansion tests.
- Focused pytest for M103 backend-boundary worklist regression behavior.
- Focused pytest for M100 backend-translation result regression behavior.
- `MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases` for
  touched/new lowering modules and tests where practical.
- `git diff --check`.

Results: line count total `6689`; py-compile returned exit 0 with no output;
focused backend translation expansion pytest returned `10 passed in 27.10s`;
focused M103 backend-boundary worklist pytest returned `7 passed in 18.04s`;
focused M100 backend-translation result pytest returned
`12 passed in 23.65s`; focused lowering mypy returned
`Success: no issues found in 59 source files`; final `git diff --check`
returned exit 0 with no output.

Review notes:

- M104 is accepted as a broadened planning target only because it shares one
  boundary: M103 worklist entry to typed translation expansion result.
- Reviewers should reject any generic backend dispatcher, registry, source
  scanner, scheduler/readiness oracle, hidden backfeed, fixpoint loop, Stage 9
  planner, renderer-ready IR, or renderer-side inference.
- Reviewers should verify that direct-intrinsic behavior is driven by explicit
  typed rule input and not by SVE tokens, extension ids, type tags, byte sizes,
  primitive names, or raw intrinsic text.
- Exact-array expansion must not duplicate M100; it must either add explicitly
  typed context not accepted by M100, produce deferred/unsupported result state,
  or bridge unresolved M103 worklist entries to a typed result boundary.

Accepted follow-ups:

- M104 execution follow-ups were addressed during M104: the prompt stated the
  single-boundary justification, and tests cover explicit typed rule inputs,
  no-hardwiring, fake-object negatives, line counts, and import boundaries.
- Consider tightening `Stage8BackendTranslationExpansionRule.rule_kind` from
  `str` to the existing `Stage8BackendTranslationExpansionRuleKind` alias in a
  later cleanup.
- Consider trimming M103 worklist contract constant re-exports from the
  private M104 facade module if ownership clarity becomes important.
- Future diagnostic-sensitive slices should assert exact source path, line,
  column, and message snippets in addition to code/severity.
- Future Rust/type-context work should introduce explicit typed context instead
  of relying on M104's already-translated rule value.
- Future post-M104 planning should choose between renderer-ready body IR,
  additional backend value/type result families, direct-intrinsic result
  broadening, primitive calls/dependencies, or output integration based on the
  accepted M104 result surface.

Next concrete prompt:

- `docs/agent/runs/post-m104-planning-plus-review-prompt.md` selects the next
  lowering milestone after accepted M104.

### Milestone 105: Clean KISS Generator Restart Charter Slice

Status:

Accepted. Post-M104 planning selected M105 after the project owner and
orchestrator agreed that the accepted M57-M104 lowering path captured useful
requirements but had become too complex for the intended research prototype.
Human acceptance of the plan was recorded, and the M105 execution-review loop
returned `Accept With Follow-Ups`.

Planning verdict:

`Accept With Follow-Ups`. The plan is accepted for handoff, with the explicit
follow-up that M105 execution must remain documentation/architecture work and
must not begin product-code implementation.

Goal:

Create a clean restart charter for a KISS, object-oriented generator
architecture that keeps the project focused on the real product path:

```text
.tsl source data -> validated catalog -> selected implementations -> C++ and Rust library artifacts
```

M105 does not discard accepted evidence. It freezes the M57-M104
lowering/request/result/worklist path as requirement and regression evidence,
then defines the simpler architecture the next implementation slice should
follow.

Scope:

- Create a restart charter under `docs/redesign/`, such as
  `docs/redesign/kiss-generator-restart.md`.
- Name the small stable concepts and ownership boundaries for the restart:
  `TslProject`, source documents, parse result, catalog, primitive,
  implementation, target, generator, backend, diagnostic reporter, artifact
  set, and artifact writer.
- Define the minimal end-to-end vertical slice that should follow M105:
  consume a tiny `.tsl` fixture, build a validated catalog, select one
  implementation for explicit C++ and Rust targets, and emit deterministic
  C++ and Rust library artifacts through an explicit writer boundary.
- State how existing `docs/redesign/`, `tslgen/`, `tsldata/`, and `frozen/`
  material may be used as evidence without shaping the restart around the
  micro-IR chain or legacy module layout.
- Define the repository layout reset: the current top-level `tslgen/` tree is
  old-state evidence and must be moved wholesale to `tslgenold/` before new
  restart product code is added; the new clean implementation owns the
  top-level `tslgen/` path.
- Add anti-complexity rules for future milestones: no new IR category,
  request/result family, inventory, worklist, registry, dispatcher, or
  provenance wrapper unless at least two concrete accepted stages need it.
- Record which accepted lowering capabilities remain useful as requirements
  and which existing implementation modules should be treated as quarantined
  evidence for the restart path.
- Update roadmap/state/design docs so the next concrete prompt is an M105
  documentation/architecture execution-review loop or, after accepted M105
  review, the M106 layout-quarantine prompt.

Out of scope:

- Product-code implementation, parser rewrites, catalog implementation,
  generator implementation, renderer implementation, artifact writing, tests,
  fixture changes, generated output, or CLI behavior.
- Physically moving `tslgen/` to `tslgenold/`; M105 must plan and require that
  as the first structural restart milestone unless it records a better
  accepted layout with the same clean separation.
- Extending `boundary.py`, M57-M104 lowering modules, M99-M104 backend
  request/result/worklist/expansion modules, or `_lowering_ir_contracts.py`.
- Creating another micro-IR taxonomy, scheduler/readiness oracle, Stage 9
  plan, backend dispatcher, plugin registry, hidden backfeed, fixpoint
  mechanism, source repair layer, or renderer-side semantic inference path.
- Porting legacy modules or preserving the current exploratory `tslgen/`
  object graph for convenience.

Accepted outputs:

- A KISS restart charter document with explicit design rules and first-slice
  acceptance criteria.
- A repository-layout rule that quarantines the old state under `tslgenold/`
  and reserves `tslgen/` for the clean restart implementation.
- Roadmap/state/design-doc updates that mark M57-M104 as evidence for the
  restart, not the implementation path to keep extending.
- A concrete next-run prompt for the structural M106 layout quarantine after
  accepted M105 review.

Validation:

```bash
git diff --check
```

Review notes:

- Reviewers should reject any M105 execution that starts product code or
  creates another lowering micro-layer instead of clarifying the restart
  architecture.
- Reviewers should require the first restart implementation slice to generate
  both C++ and Rust artifacts from a tiny fixture before adding broad
  lowering/backend machinery.
- Reviewers should treat object orientation as a simplicity tool, not as a
  license for broad class hierarchies.

Accepted follow-ups:

- M105 execution addressed the layout-order follow-up: M106 is the dedicated
  `tslgen/` -> `tslgenold/` quarantine move before clean product code starts.
- M105 execution addressed the test-evidence follow-up: accepted M57-M104 tests
  are regression evidence for diagnostics, determinism, source-body integrity,
  and semantic-boundary risks, not constraints on restart internals.
- Before the first clean product-code slice, reconcile older target-architecture
  references to `backends/registry.py` and "register manifest/capabilities"
  with the M105 no-registry-default charter.
- When drafting the first clean product-code slice, keep backend selection as
  explicit configuration/simple ownership rather than a revived renderer
  registry or dispatcher.

Next concrete prompt:

- `docs/agent/runs/m106-execution-review-loop-prompt.md` executes the
  structural layout quarantine after accepted M105.

### Milestone 106: Old Implementation Quarantine Layout Reset Slice

Status:

Accepted. M106 completed the structural restart layout reset after accepted
M105.

Goal:

Separate old accepted/exploratory implementation state from the clean restart
package path before any new product code is added:

```text
old state: tslgen/ -> tslgenold/
clean restart path: fresh tslgen/
```

Scope:

- Move the current top-level `tslgen/` tree wholesale to `tslgenold/`.
- Reserve or create a fresh top-level `tslgen/` path for the clean generator
  without adding parser, catalog, generator, backend, renderer, CLI, fixture,
  test, or generated-output implementation.
- Update documentation and workflow state so `tslgenold/` is evidence-only,
  like `frozen/`, and is not a runtime dependency for the clean generator.
- Update validation/import-path documentation or lightweight checks needed to
  keep the repository coherent after the move.
- Preserve dirty-worktree safety: do not revert edits made by others, and
  inspect overlapping changes before moving files.

Out of scope:

- New product-code implementation under the fresh `tslgen/` path.
- Porting, adapting, or compatibility-wrapping old `tslgen/` modules.
- Changing `frozen/` or treating `tslgenold/` as a runtime package for the new
  generator.
- Parser, catalog, selection, backend, rendering, artifact writer, CLI, test
  fixture, generated output, or broad validation-profile implementation.

Accepted outputs:

- The old top-level implementation tree exists under `tslgenold/`.
- The clean top-level `tslgen/` path is available for later restart product
  slices and does not contain new product implementation code.
- Docs and workflow state record the evidence-only status of `tslgenold/`.
- No clean runtime import path depends on `frozen/` or `tslgenold/`.

Validation:

```bash
git diff --check
```

If the move changes lightweight repository checks or import-path docs, run the
smallest additional validation that proves the layout reset is coherent.

Accepted result:

- The pre-restart top-level implementation tree exists under `tslgenold/`.
- The fresh top-level `tslgen/` path contains only a README placeholder and is
  reserved for later clean restart product code.
- `frozen/` remained unchanged.
- No parser, catalog, generator, backend, renderer, writer, CLI, fixture,
  test, or generated-output product code was added.
- Layout/workflow docs record `tslgenold/` as evidence-only.

Review notes:

- Reviewers should reject any M106 execution that starts the first product
  implementation slice or mixes old and clean code under the same package path.
- Reviewers should require the move to be explicit and reviewable, not an
  opportunistic cleanup or compatibility migration.

### Milestone 107: Tiny Clean Restart Source-To-Artifact Vertical Slice

Status:

Accepted. M107 completed the first clean restart product-code vertical slice
after focused architecture, documentation, and validation revisions. It added
a tiny source-loading, parsing, catalog, selection, backend-emission, artifact
value, test, and fixture surface under the fresh `tslgen/` path. It also added
a repo-root import shim and pytest path configuration for uninstalled
validation. It did not import from `tslgenold/` or `frozen/`, did not add broad
TSL/TSIL parsing, and did not add lowering IR taxonomies, worklists,
registries, dispatchers, hidden backfeeds, or fixpoint mechanisms.

Goal:

Prove the clean restart path on a tiny fixture:

```text
.tsl source document -> parse result -> minimal catalog -> selected implementation -> deterministic C++ and Rust artifact values
```

Scope:

- Add the minimal clean package/test structure under fresh `tslgen/`.
- Load one explicit tiny `.tsl` source fixture through an explicit source
  loading boundary.
- Parse only the documented source form needed by the fixture.
- Build and validate a minimal typed catalog with one primitive and one
  implementation.
- Select one implementation for explicit C++ and Rust target requests.
- Emit one deterministic C++ artifact value and one deterministic Rust artifact
  value through typed backend emitters.
- Exercise the artifact writer only as the explicit filesystem-write boundary,
  if the slice writes files at all.
- Prove repeated runs produce stable diagnostics and artifacts.

Out of scope:

- Broad `tsldata/` corpus parsing.
- Broad TSIL/body semantics, dependency closure, backend manifests, hardware
  autodetection, CLI compatibility, generated tests, and generated-output
  parity.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old `tslgenold/`
  modules.
- New lowering IR taxonomies, worklists, registries, dispatchers, hidden
  backfeeds, or fixpoint mechanisms.

Accepted outputs:

- A tiny clean product path exists under `tslgen/` without importing
  `tslgenold/` or `frozen/`.
- Tests prove the tiny C++ and Rust artifact outputs are deterministic.
- Diagnostics remain structured and source-aware for the supported invalid
  fixture boundary.
- Documentation records any narrowed source form, validation decision, or open
  question discovered by the slice.

Validation:

```bash
git diff --check
```

Run the targeted clean-package tests added by M107 and any smallest supporting
compile/import checks needed for the new package surface. Do not run the old
`tslgenold` validation profile as proof of the clean product slice.

Review notes:

- Reviewers should reject runtime imports from `tslgenold/` or `frozen/`.
- Reviewers should reject broad parser/catalog/backend work beyond the tiny
  end-to-end fixture.
- Reviewers should require the C++ and Rust artifact outputs to come from typed
  clean restart values, not renderer-side inference over raw source text.

### Milestone 108: Minimal Clean Body Lowering Boundary Slice

Status:

Accepted. M108 completed the first deliberately small clean lowering boundary
after accepted M107. It added a tiny `tslgen/src/tslgen/lowering/` module for
the exact M107 `add(left, right)` / `scalar` / `si32` selected body, lowered
selected implementations into backend-neutral `LoweredFunction` values, and
made C++ and Rust emitters consume those lowered values. It preserved M107
artifact content, logical paths, digests, diagnostics, and deterministic
ordering. It did not import from `tslgenold/` or `frozen/`, port old lowering
modules, add broad TSIL/body semantics, expression parsing beyond the exact
fixture, branch pruning, dependency closure, backend manifests, type maps
beyond `si32`, CLI compatibility, artifact writing, generated-output parity,
lowering IR taxonomies, worklists, inventories, registries, dispatchers,
plugin systems, hidden backfeeds, or fixpoint mechanisms.

Goal:

Introduce the first deliberately small lowering boundary in the clean restart
path:

```text
selected typed implementation -> backend-neutral lowered function -> C++ and Rust artifact values
```

Scope:

- Add a focused `tslgen/src/tslgen/lowering/` module for the exact M107
  `add(left, right)` / `scalar` / `si32` body only.
- Lower the selected M107 implementation into a small backend-neutral typed
  function value with deterministic name, parameters, scalar type tag, and
  binary-add expression.
- Make C++ and Rust emitters consume the lowered function value rather than
  reading the catalog body directly.
- Preserve M107 generated C++ and Rust artifact content, logical paths,
  diagnostics, and deterministic ordering.
- Add tests for the lowering value, pipeline determinism, backend consumption
  of lowered values, and at least one unsupported-lowering diagnostic
  boundary.

Out of scope:

- Broad TSIL/body semantics, expression parsing, branch pruning, dependency
  closure, backend manifests, type maps beyond `si32`, hardware autodetection,
  CLI compatibility, generated tests, artifact writing, or corpus-wide
  `tsldata/` parsing.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old `tslgenold/`
  lowering modules.
- Lowering IR taxonomies, worklists, inventories, registries, dispatchers,
  plugin systems, hidden backfeeds, or fixpoint mechanisms.

Accepted outputs:

- A tiny clean lowering boundary exists and has obvious ownership.
- Backends receive already-lowered typed values for the accepted fixture.
- Existing M107 outputs remain byte-stable.
- Unsupported lowering inputs produce structured diagnostics instead of source
  repair or renderer-side inference.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject any broad lowering framework, scheduler, registry,
  or compatibility port.
- Reviewers should require the lowering boundary to make backend ownership
  simpler, not add milestone-shaped wrappers for their own sake.
- Reviewers should require diagnostics for unsupported lowering inputs and
  byte-stable artifact outputs for the accepted fixture.

### Milestone 109: Tiny Clean Artifact Writer Boundary Slice

Status:

Accepted. M109 added the first explicit filesystem-write boundary for clean
restart artifact values. The writer consumes existing in-memory `ArtifactSet`
values plus a caller-provided output root, validates paths before writing,
rejects unsafe logical paths with structured `TSL-WRITE-*` diagnostics,
returns deterministic typed write reports, and keeps the existing
`generate_from_paths(...)` path in-memory only. M109 did not add CLI
integration, generated test execution, CMake/Cargo scaffolding, broad output
tree parity, output-root cleaning, formatting/compiling generated C++/Rust,
runtime imports from `frozen/` or `tslgenold/`, old writer migration, new
lowering semantics, backend manifests, dependency closure, registries,
dispatchers, plugin systems, hidden backfeeds, or fixpoint mechanisms.

Goal:

Add the first explicit filesystem-write boundary for the clean restart path:

```text
artifact values -> deterministic checked write report
```

Scope:

- Add a focused clean artifact writer under `tslgen/src/tslgen/io/`.
- Write only existing in-memory `ArtifactSet` values to an explicit output
  root supplied by the caller.
- Keep path handling deterministic and safe: reject absolute logical paths,
  parent-directory escapes, duplicate logical paths, and directory/file
  collisions with structured diagnostics.
- Return a typed write report with stable written-path and digest data.
- Add tests that generate the M108 artifact set, write it to a temporary
  output root, assert file contents/digests/report ordering, and cover at
  least one unsafe-path diagnostic boundary.
- Keep the existing pure source-to-artifact API usable without writing files.

Out of scope:

- CLI integration.
- Generated test execution.
- CMake/Cargo/project scaffolding.
- Broad output tree parity.
- Cleaning output roots.
- Watch/incremental behavior.
- Formatting or compiling generated C++/Rust.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old writer modules.
- New lowering semantics, backend manifests, dependency closure, registries,
  dispatchers, plugin systems, hidden backfeeds, or fixpoint mechanisms.

Accepted outputs:

- A small writer boundary exists and is the only filesystem-write owner for
  generated artifact values in the clean package.
- Existing M108 in-memory artifacts remain byte-stable.
- Writer tests prove deterministic writes and structured diagnostics for unsafe
  paths.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject hidden writes in parsing, catalog construction,
  selection, lowering, or backend emission.
- Reviewers should require path-safety diagnostics and deterministic report
  ordering.
- Reviewers should reject broad CLI/output-layout parity work in M109.

### Milestone 110: Tiny Clean Scalar Type Lowering Table Slice

Status:

Accepted. M110 broadened the tiny clean lowering path from a one-off `si32`
check into a small lowering-owned scalar type descriptor table for `si32`,
`ui32`, `f32`, and `f64`. `LoweredFunction` now carries a backend-neutral
descriptor with tag, scalar kind, integer/floating family, bit width, and
signedness. C++ and Rust spellings remain backend-owned in their emitters. The
parser/catalog still preserve the exact tiny scalar `add(left, right)` source
shape while allowing identifier-like type tags, and syntactically valid but
unsupported tags fail in lowering with `TSL-LOWER-UNSUPPORTED-TYPE`. Existing
`si32` artifact bytes, logical paths, and digests remain stable. M110 did not
add CLI work, writer changes, vector/SIMD semantics, broad TSIL parsing,
backend-manifest/type-map reads, old imports, old type/lowering migration,
dependency closure, registries, dispatchers, plugin systems, hidden backfeeds,
fixpoint mechanisms, or a broad type-system framework.

Goal:

Broaden the tiny clean lowering path from one hard-coded scalar type to a small
typed scalar-type lowering table:

```text
selected scalar add implementation -> lowered function with typed scalar type descriptor
```

Scope:

- Add a small lowering-owned scalar type descriptor model and typed descriptor
  table for the clean restart scalar types selected for this slice.
- Keep the descriptor backend-neutral: tags, kind/family, bit width, and
  signedness/floating classification are lowering facts; C++ and Rust spelling
  remain backend-owned.
- Replace the M108 lowerer's single `si32` type constant with lookup through
  this typed descriptor table.
- Allow the exact existing `scalar` / `add(left, right)` clean source form to
  use the supported scalar type tags, while malformed or unsupported tags
  remain diagnostic boundaries.
- Update C++ and Rust backends only as consumers of the lowered scalar type
  descriptor, with small backend-owned spelling maps, so supported scalar tags
  can be emitted deterministically.
- Preserve the existing M107/M108 `si32` artifact bytes and logical paths.
- Add focused tests for descriptor lookup, successful lowering for the
  supported tags, unsupported-type diagnostics, byte-stable `si32` output, and
  at least one non-`si32` end-to-end clean fixture or generated temporary
  source.

Out of scope:

- CLI integration or legacy CLI compatibility.
- Writer changes beyond preserving M109 behavior.
- New primitive names, templates, arities, extensions, vector/SIMD shapes,
  hardware feature selection, branch pruning, generation-time helper
  evaluation, or broad TSIL parsing.
- Type metadata loaded from `tsldata`, backend manifests, or old generator
  maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old type/lowering
  modules.
- Dependency closure, registries, dispatchers, plugin systems, hidden
  backfeeds, fixpoint mechanisms, or a broad type-system framework.

Accepted outputs:

- The clean lowerer has an obvious typed scalar type descriptor boundary
  instead of a one-off `si32` check.
- Supported scalar type tags lower deterministically into backend-neutral
  descriptor values.
- C++ and Rust emitters consume the descriptor through backend-owned spelling
  maps and keep existing `si32` output byte-stable.
- Unsupported scalar tags produce structured diagnostics rather than silent
  fallback, source repair, or renderer-side inference.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject hard-coded backend or extension-specific lowering
  behavior outside the typed descriptor table.
- Reviewers should reject moving backend spelling policy into lowering.
- Reviewers should reject broad parser/type-system/framework growth beyond the
  exact scalar-add source form.
- Reviewers should require deterministic descriptor ordering, diagnostics, and
  byte-stable existing artifacts.

### Milestone 111: Tiny Clean Binary Operation Lowering Table Slice

Status:

Accepted. M111 broadened the tiny clean lowering path from a one-off `add`
operation check into a small lowering-owned binary operation descriptor table
for `add`, `sub`, and `mul`. `LoweredFunction` now carries a backend-neutral
binary operation expression with an operation descriptor alongside the M110
scalar type descriptor. C++ and Rust operator spellings remain backend-owned
in their emitters. The parser/catalog still preserve the exact tiny scalar
binary source shape while allowing identifier-like primitive/body operation
names, and syntactically valid but unsupported operation ids fail in lowering
with `TSL-LOWER-UNSUPPORTED-OPERATION`. A supported primitive whose body uses a
different operation fails with `TSL-LOWER-OPERATION-MISMATCH`. Existing
`add`/`si32` artifact bytes, logical paths, and digests remain stable. M111
did not add CLI work, writer changes, vector/SIMD semantics, broad
TSIL/expression parsing, backend-manifest/operation-map reads, old imports,
old operation/lowering migration, dependency closure, registries, dispatchers,
plugin systems, hidden backfeeds, fixpoint mechanisms, division/modulo
semantics, or a broad expression/type framework.

Goal:

Broaden the tiny clean lowering path from one hard-coded binary operation to a
small typed binary-operation descriptor table:

```text
selected scalar binary implementation -> lowered function with scalar type and binary operation descriptors
```

Scope:

- Add a small lowering-owned binary operation descriptor model and typed
  descriptor table for the clean restart operation set selected for this
  slice: `add`, `sub`, and `mul`.
- Keep operation descriptors backend-neutral: operation id, arity/category,
  expected source body operation name, and stable semantic name are lowering
  facts; C++ and Rust operator spellings remain backend-owned.
- Replace the lowerer's one-off `add` primitive/body check with lookup through
  this typed operation descriptor table, while preserving exact binary
  `left, right` parameter handling.
- Allow the exact tiny scalar source form to use the supported operation names
  as primitive name and body operation, for example `sub(left, right)` in a
  `sub` primitive. Nearby shapes remain diagnostic boundaries.
- Update C++ and Rust backends only as consumers of the lowered operation
  descriptor, with small backend-owned operator spelling maps.
- Preserve existing `add`/`si32` artifact bytes, logical paths, and digests.
- Add focused tests for operation descriptor lookup, successful lowering for
  supported operations across at least one non-`add` source, unsupported
  operation diagnostics, operation/body mismatch diagnostics, backend-owned
  operator spelling, and byte-stable existing `add` output.

Out of scope:

- CLI integration or legacy CLI compatibility.
- Writer changes beyond preserving M109 behavior.
- New arities, parameter names, templates beyond the exact binary scalar form,
  extensions beyond `scalar`, vector/SIMD shapes, hardware feature selection,
  branch pruning, generation-time helper evaluation, broad TSIL parsing, or
  division/modulo semantics.
- Type metadata or operation metadata loaded from `tsldata`, backend manifests,
  or old generator maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old operation,
  parser, backend, or lowering modules.
- Dependency closure, registries, dispatchers, plugin systems, hidden
  backfeeds, fixpoint mechanisms, or a broad expression/type framework.

Accepted outputs:

- The clean lowerer has an obvious typed binary-operation descriptor boundary
  instead of a one-off `add` check.
- Supported operation ids lower deterministically into backend-neutral
  operation descriptor values alongside the M110 scalar type descriptor.
- C++ and Rust emitters consume the operation descriptor through backend-owned
  operator spelling maps and keep existing `add`/`si32` output byte-stable.
- Unsupported operations and primitive/body mismatches produce structured
  diagnostics rather than source repair, fallback, or renderer-side inference.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject moving backend operator spelling into lowering.
- Reviewers should reject broad expression parsing or a general operation
  registry/dispatcher.
- Reviewers should require source-body integrity: mismatched or malformed
  bodies are diagnostics, never corrected.
- Reviewers should require deterministic operation ordering, diagnostics, and
  byte-stable existing artifacts.

### Milestone 112: Tiny Clean Return Statement Body Lowering Slice

Status:

Accepted. M112 made the lowered function body explicit for the tiny clean
lowering path. `LoweredFunction` now carries a backend-neutral
`LoweredFunctionBody` containing exactly one `LoweredReturnStatement` over the
accepted M111 binary operation expression. The return statement preserves the
source body location, contains no C++/Rust text or backend operator spelling,
and does not broaden parser/catalog body forms. C++ and Rust emitters render
from the explicit return statement while keeping language syntax and operator
spelling backend-owned. Existing artifact bytes, logical paths, ordering,
descriptor tables, operation/type diagnostics, and digests remain stable. M112
did not add source syntax, `emit_return(...)` recognition, broad TSIL parsing,
multiple statements, locals, assignments, loops, control flow, source repair,
old body-lowering migration, CLI work, writer changes, generated test
execution, CMake/Cargo scaffolding, vector/SIMD semantics, backend manifests,
old generator maps, registries, dispatchers, plugin systems, hidden backfeeds,
fixpoint mechanisms, or a broad statement/expression framework.

Goal:

Make the lowered function body explicit without adding new source syntax:

```text
lowered binary expression -> lowered function body with one typed return statement
```

Scope:

- Add a small lowering-owned function-body model for the current tiny clean
  slice, such as a `LoweredFunctionBody` containing exactly one
  `LoweredReturnStatement` over the accepted M111 binary operation expression.
- Keep the body model backend-neutral. It may reference lowered expressions
  and source locations; it must not contain C++/Rust text, backend operator
  spelling, or source-body repair policy.
- Change `LoweredFunction` to carry the explicit body rather than exposing the
  binary expression directly as the whole function body.
- Update C++ and Rust backends to consume the explicit return-statement body
  and preserve the current generated bytes for all accepted tiny outputs.
- Preserve existing M110/M111 descriptor tables, operation/type diagnostics,
  logical paths, artifact ordering, and digests.
- Add focused tests for the new function body/return statement values,
  backend rendering from the explicit return statement, byte-stable existing
  `add` output, and at least one non-`add`/non-`si32` output still passing
  through the new body model.

Out of scope:

- New `.tsl` source syntax, `emit_return(...)` source recognition, broad TSIL
  parsing, parser/catalog body-form changes, source-body repair, or accepting
  additional body shapes.
- Multiple statements, local variables, assignments, loops, control flow,
  dependency closure, expression trees beyond the accepted binary operation
  expression, or a general statement/expression framework.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, vector/SIMD shapes, hardware feature selection, branch pruning,
  generation-time helper evaluation, backend manifests, or old generator maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old return/body
  lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, or fixpoint
  mechanisms.

Accepted outputs:

- The clean lowerer has an explicit backend-neutral function-body/return
  statement boundary for the accepted tiny binary expression slice.
- C++ and Rust emitters render from the body/return statement model while
  keeping backend spellings backend-owned.
- Existing generated artifacts stay byte-stable.
- The change creates a simple extension point for future body lowering without
  broadening source syntax or adding a general statement framework.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject parser/source syntax broadening in M112.
- Reviewers should reject old `emit_return(...)` compatibility, source repair,
  or hidden semantic inference.
- Reviewers should reject broad statement/expression frameworks, registries, or
  dispatchers.
- Reviewers should require current output bytes, diagnostics, and descriptor
  behavior to remain stable.

### Milestone 113: Tiny Clean Function Signature Lowering Slice

Status:

Accepted. M113 made the lowered function signature explicit for the tiny clean
lowering path. `LoweredFunction` now carries a backend-neutral
`LoweredFunctionSignature` paired with the accepted M112
`LoweredFunctionBody`. The signature contains only the deterministic function
name, source primitive name, ordered parameters, and scalar type descriptor.
C++ and Rust emitters render from the explicit signature/body pair while
keeping language syntax, type spelling, operator spelling, logical paths, and
metadata backend-owned. Existing artifact bytes, logical paths, ordering,
descriptor tables, body values, lowering diagnostics, and digests remain
stable. M113 did not add parser/source syntax changes, source repair,
`emit_return(...)` recognition, extra arities/parameter names, function
overloading policy, namespaces/modules/packages, include planning, artifact
layout changes, CLI work, writer changes, generated test execution,
CMake/Cargo scaffolding, vector/SIMD semantics, backend manifests, old
signature/body migration, registries, dispatchers, plugin systems, hidden
backfeeds, fixpoint mechanisms, or a broad signature/type framework.

Goal:

Make the lowered function signature explicit without changing source syntax or
generated bytes:

```text
lowered function fields -> lowered signature plus explicit body
```

Scope:

- Add a small lowering-owned `LoweredFunctionSignature` value for the current
  tiny clean slice, carrying the deterministic function name, primitive name,
  ordered parameters, and return/scalar type descriptor.
- Keep the signature model backend-neutral. It must not contain C++/Rust
  spelling, backend operator spelling, include policy, artifact paths, or
  source-body repair policy.
- Change `LoweredFunction` to carry the explicit signature plus the accepted
  M112 function body.
- Update C++ and Rust backends to consume the explicit signature and body while
  preserving current generated bytes for all accepted tiny outputs.
- Preserve M110 scalar descriptors, M111 operation descriptors, M112 body
  values, diagnostics, logical paths, artifact ordering, and digests.
- Add focused tests for the new signature value, backend rendering from the
  explicit signature/body pair, byte-stable existing `add` output, and at
  least one non-`add`/non-`si32` output still passing through the signature
  model.

Out of scope:

- New `.tsl` source syntax, parser/catalog source-form changes, source-body
  repair, broad TSIL parsing, `emit_return(...)` recognition, additional body
  shapes, or additional arities/parameter names.
- Function overloading policy, namespaces/modules/packages, include planning,
  artifact layout changes, language-specific type names in lowering, or broad
  signature/type frameworks.
- Multiple statements, local variables, assignments, loops, control flow,
  dependency closure, expression trees beyond the accepted binary operation
  expression, or a general statement/expression framework.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, vector/SIMD shapes, hardware feature selection, branch pruning,
  generation-time helper evaluation, backend manifests, or old generator maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old signature,
  declaration, or body lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, or fixpoint
  mechanisms.

Accepted outputs:

- The clean lowerer has an explicit backend-neutral function-signature boundary
  paired with the M112 body boundary.
- C++ and Rust emitters render from the signature/body pair while keeping
  language spellings backend-owned.
- Existing generated artifacts stay byte-stable.
- The change creates a simple extension point for future declaration, module,
  or overload work without adding broad frameworks.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject backend type spellings, artifact paths, includes, or
  declaration/module planning in the lowering signature.
- Reviewers should reject parser/source syntax broadening and old signature
  compatibility work.
- Reviewers should reject broad signature/type frameworks, registries, or
  dispatchers.
- Reviewers should require current output bytes, diagnostics, descriptor
  behavior, and the M112 body boundary to remain stable.

### Milestone 114: Tiny Clean Lowering Stage Output Boundary Slice

Status:

Accepted. M114 made the lowering stage output explicit for the tiny clean
lowering path. The clean lowerer now exposes a backend-neutral
`LoweredFunctionSet` plus `LoweringStageResult` for batch lowering selected
implementations into an ordered lowered-function set with accumulated
diagnostics. The existing single-selected `lower(...)` behavior remains
available and unchanged as the unit used by the batch boundary. The generator
consumes `lower_all(...)` stage output before backend emission and emits every
returned lowered function while still accumulating diagnostics, preserving the
previous per-selected behavior for mixed valid/invalid lowering results.
Existing artifact bytes, logical paths, metadata, ordering, M110 scalar
descriptors, M111 operation descriptors, M112 body values, M113 signature
values, lowering diagnostics, and digests remain stable. M114 did not add
parser/source syntax changes, source repair, `emit_return(...)` recognition,
new scalar types, new operations, vector/SIMD semantics, hardware feature
selection, branch pruning, generation-time helper evaluation, backend
manifests, dependency closure, module/package planning, include planning,
artifact-plan values, renderer-ready IR, backend emission inside lowering,
cross-target coordination, schedulers, queues, registries, dispatchers,
plugin systems, hidden backfeeds, fixpoint mechanisms, or a broad IR/stage
framework.

Goal:

Make the lowering stage output explicit before backend emission:

```text
selected implementations -> ordered lowered function set plus diagnostics
```

Scope:

- Add a small lowering-owned stage-output value for the current tiny clean
  slice, such as a `LoweredFunctionSet`, carrying an ordered tuple of accepted
  `LoweredFunction` values.
- Add a small lowering-stage result for batch lowering of selected
  implementations, carrying the lowered function set plus accumulated lowering
  diagnostics.
- Keep the existing single-selected lowering semantics intact; M114 may
  factor that path into the batch output but must not change the accepted
  M110/M111/M112/M113 descriptor, expression, body, or signature values.
- Update the generator to lower the selected implementations for a target into
  the explicit lowering stage output before backend emission, then emit only
  from the output's ordered lowered functions.
- Preserve current C++ and Rust artifact bytes, logical paths, metadata,
  ordering, diagnostics, and digests.
- Add focused tests for ordered stage-output functions, diagnostic
  accumulation for unsupported selected implementations, generator use of the
  stage output, byte-stable existing `add` output, and at least one
  non-`add`/non-`si32` path still passing through the stage output.

Out of scope:

- New `.tsl` source syntax, parser/catalog source-form changes, source-body
  repair, broad TSIL parsing, `emit_return(...)` recognition, additional body
  shapes, or additional arities/parameter names.
- New scalar types, new operations, vector/SIMD shapes, hardware feature
  selection, branch pruning, generation-time helper evaluation, backend
  manifests, dependency closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- Cross-target coordination, schedulers, readiness oracles, queues, registries,
  dispatchers, plugin systems, hidden backfeeds, fixpoint mechanisms, or a
  broad IR/stage framework.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  lowering-stage modules.

Accepted outputs:

- The clean lowerer has an explicit lowering stage-output boundary for ordered
  lowered function sets and diagnostics.
- The generator consumes the stage output before backend emission without
  changing backend ownership of rendering, spelling, logical paths, or
  metadata.
- Existing generated artifacts stay byte-stable.
- The change creates a simple extension point for future multi-function
  lowering without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject backend emission, artifact planning, module/package
  planning, or renderer-ready IR inside lowering.
- Reviewers should reject schedulers, queues, readiness oracles, registries,
  dispatchers, hidden backfeeds, fixpoint behavior, or broad stage frameworks.
- Reviewers should require current output bytes, diagnostics, descriptor
  behavior, M112 body values, and M113 signature values to remain stable.

### Milestone 115: Tiny Clean Binary Division Operation Lowering Slice

Status:

Accepted. M115 added `div` to the tiny clean lowering-owned binary operation
descriptor table and backend-owned C++/Rust operator spelling tables. It
preserved M110 scalar descriptors, M112 body values, M113 signatures, M114
lowering stage-output behavior, diagnostics, logical paths, artifact ordering,
and existing `add`/`sub`/`mul` artifact bytes and digests. M115 did not add
parser/source syntax changes, source repair, modulo/remainder semantics,
division-by-zero diagnostics, integer overflow policy, floating special-value
policy, constant folding, algebraic simplification, vector/SIMD semantics,
backend manifests, old operation migration, registries, dispatchers, plugin
systems, hidden backfeeds, fixpoint mechanisms, or a broad operation/type
framework.

Goal:

Add binary division to the existing tiny clean binary-operation lowering path:

```text
div(left, right) -> LoweredBinaryOperationExpression(operation="div")
```

Scope:

- Add `div` to the existing lowering-owned binary operation descriptor table,
  preserving deterministic descriptor ordering.
- Keep the descriptor backend-neutral. It must not contain C++ or Rust
  spelling, divide-by-zero policy, overflow policy, or source repair policy.
- Update C++ and Rust backends to spell only the accepted `div` descriptor via
  backend-owned operator spelling tables, preserving backend ownership of text.
- Preserve M110 scalar descriptors, M112 body values, M113 signatures, M114
  lowering stage-output behavior, diagnostics, logical paths, artifact
  ordering, and existing `add`/`sub`/`mul` artifact bytes and digests.
- Add focused tests for descriptor lookup/order, lowerer acceptance, backend
  spelling ownership, generator output for at least one `div` source, M114
  stage-output pass-through for `div`, and the updated unsupported-operation
  diagnostic boundary.

Out of scope:

- New `.tsl` source syntax, parser/catalog source-form changes, source-body
  repair, broad TSIL parsing, additional arities/parameter names, or additional
  body shapes.
- Modulo/remainder semantics, division-by-zero diagnostics, integer overflow
  policy, floating special-value policy, constant folding, algebraic
  simplification, or broad arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad operation/type framework.

Accepted outputs:

- `div(left, right)` lowers into the existing backend-neutral binary operation
  expression shape.
- C++ and Rust emitters render `div` through backend-owned operator spelling
  maps while existing operations remain byte-stable.
- Unsupported operations still produce structured lowering diagnostics rather
  than source repair, fallback, or renderer-side inference.
- The M114 lowering stage-output boundary continues to carry the new operation
  without adding scheduler, package, artifact-plan, or broad IR machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject parser/source syntax broadening or source repair.
- Reviewers should reject putting C++/Rust spelling or arithmetic runtime
  policy into lowering descriptors.
- Reviewers should reject modulo/remainder semantics, broad arithmetic
  frameworks, registries, or dispatchers.
- Reviewers should require current `add`/`sub`/`mul` output bytes,
  diagnostics, M112 body values, M113 signature values, and M114 stage-output
  behavior to remain stable.

### Milestone 116: Tiny Clean Integer Remainder Operation Type-Gated Lowering Slice

Status:

Accepted. M116 added integer-only `mod` to the tiny clean lowering-owned
binary operation descriptor table, added a focused lowering-owned
operation/type compatibility rule boundary, and added backend-owned C++/Rust
`%` spellings for accepted lowered `mod` functions. Floating `mod` over
accepted `f32`/`f64` scalar descriptors fails in lowering with
`TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`. M116 preserved accepted
`add`/`sub`/`mul`/`div` behavior, M110 scalar descriptors, M112 body values,
M113 signatures, M114 lowering stage-output behavior, diagnostics, logical
paths, artifact ordering, and existing artifact bytes and digests. M116 did
not add parser/source syntax changes, source repair, floating modulo
semantics, runtime remainder policy, divide-by-zero diagnostics, integer
overflow policy, constant folding, algebraic simplification, vector/SIMD
semantics, backend manifests, old operation migration, registries,
dispatchers, plugin systems, hidden backfeeds, fixpoint mechanisms, or a broad
operation/type framework.

Goal:

Add integer-only remainder to the existing tiny clean binary-operation
lowering path:

```text
mod(left, right) over integer scalar descriptors
-> LoweredBinaryOperationExpression(operation="mod")
```

Scope:

- Add `mod` to the existing lowering-owned binary operation descriptor table,
  preserving deterministic descriptor ordering.
- Introduce a small lowering-owned operation/type compatibility boundary over
  the existing M110 scalar descriptors and M111/M115 operation descriptors.
- Accept `mod` only for the currently supported integer scalar descriptors and
  reject floating scalar descriptors with a structured lowering diagnostic,
  such as `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`.
- Keep descriptors backend-neutral. They must not contain C++ or Rust
  spelling, divide-by-zero policy, signed-remainder policy, overflow policy,
  floating special-value policy, or source repair policy.
- Update C++ and Rust backends to spell only the accepted `mod` descriptor via
  backend-owned operator spelling tables.
- Preserve accepted `add`/`sub`/`mul`/`div` behavior, M110 scalar descriptors,
  M112 body values, M113 signatures, M114 lowering stage-output behavior,
  diagnostics, logical paths, artifact ordering, and existing artifact bytes
  and digests.
- Add focused tests for descriptor lookup/order, integer lowerer acceptance,
  floating-type rejection with the new diagnostic, backend spelling ownership,
  generator output for at least one integer `mod` source, M114 stage-output
  pass-through for `mod`, and the updated unsupported-operation diagnostic
  boundary.

Out of scope:

- New `.tsl` source syntax, parser/catalog source-form changes, source-body
  repair, broad TSIL parsing, additional arities/parameter names, or additional
  body shapes.
- Floating modulo semantics, division-by-zero diagnostics, signed-remainder
  runtime policy, integer overflow policy, constant folding, algebraic
  simplification, or broad arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad operation/type framework.

Accepted outputs:

- `mod(left, right)` lowers only for accepted integer scalar descriptors.
- Floating `mod(left, right)` reaches lowering and fails with a structured
  operation/type compatibility diagnostic rather than source repair, fallback,
  or renderer-side inference.
- C++ and Rust emitters render accepted `mod` through backend-owned operator
  spelling maps while existing operations remain byte-stable.
- The M114 lowering stage-output boundary continues to carry the accepted
  operation without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject parser/source syntax broadening or source repair.
- Reviewers should reject putting C++/Rust spelling or runtime arithmetic
  policy into lowering descriptors.
- Reviewers should reject floating modulo semantics, broad arithmetic
  frameworks, registries, or dispatchers.
- Reviewers should require current `add`/`sub`/`mul`/`div` output bytes,
  diagnostics, M112 body values, M113 signature values, and M114 stage-output
  behavior to remain stable.

### Milestone 117: Tiny Clean Integer Bitwise Binary Operations Type-Gated Lowering Slice

Status:

Accepted. M117 added integer-only `bit_and`, `bit_or`, and `bit_xor` to the
tiny clean lowering-owned binary operation descriptor table, reused the M116
operation/type compatibility rule boundary for integer-only gating, and added
backend-owned C++/Rust `&`, `|`, and `^` spellings for accepted lowered
bitwise functions. Floating bitwise operations over accepted `f32`/`f64`
scalar descriptors fail in lowering with
`TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`. M117 preserved accepted
`add`/`sub`/`mul`/`div`/`mod` behavior, M110 scalar descriptors, M112 body
values, M113 signatures, M114 lowering stage-output behavior, M116
compatibility behavior, diagnostics, logical paths, artifact ordering, and
existing artifact bytes and digests. M117 did not add parser/source syntax
changes, source repair, logical boolean semantics, boolean scalar types,
masks, shifts, rotates, bit-width promotion, signedness runtime policy,
constant folding, algebraic simplification, vector/SIMD semantics, backend
manifests, old operation migration, registries, dispatchers, plugin systems,
hidden backfeeds, fixpoint mechanisms, or a broad operation/type framework.

Goal:

Add integer-only bitwise binary operations to the existing tiny clean
binary-operation lowering path:

```text
bit_and(left, right) / bit_or(left, right) / bit_xor(left, right)
over integer scalar descriptors
-> LoweredBinaryOperationExpression(operation="bit_*")
```

Scope:

- Add `bit_and`, `bit_or`, and `bit_xor` to the existing lowering-owned binary
  operation descriptor table, preserving deterministic descriptor ordering
  after `mod`.
- Reuse and minimally extend the M116 lowering-owned operation/type
  compatibility boundary so the bitwise operations lower only for the
  currently supported integer scalar descriptors.
- Reject floating scalar descriptors for these operations with the accepted
  M116 `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE` diagnostic shape.
- Keep descriptors backend-neutral. They must not contain C++ or Rust
  spelling, logical-boolean policy, mask policy, signedness runtime policy,
  overflow policy, or source repair policy.
- Update C++ and Rust backends to spell only the accepted bitwise descriptors
  via backend-owned operator spelling tables.
- Preserve accepted `add`/`sub`/`mul`/`div`/`mod` behavior, M110 scalar
  descriptors, M112 body values, M113 signatures, M114 lowering stage-output
  behavior, M116 compatibility behavior, diagnostics, logical paths, artifact
  ordering, and existing artifact bytes and digests.
- Add focused tests for descriptor lookup/order, integer lowerer acceptance,
  floating-type rejection with the M116 diagnostic, backend spelling ownership,
  generator output for at least one integer bitwise source, M114 stage-output
  pass-through, and the unsupported-operation diagnostic boundary.

Out of scope:

- New `.tsl` source syntax, parser/catalog source-form changes, source-body
  repair, broad TSIL parsing, additional arities/parameter names, or additional
  body shapes.
- Logical boolean semantics, boolean scalar types, masks, shifts, rotates,
  bit-width promotion, signedness runtime policy, constant folding, algebraic
  simplification, or broad bitwise/arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad operation/type framework.

Accepted outputs:

- `bit_and(left, right)`, `bit_or(left, right)`, and `bit_xor(left, right)`
  lower only for accepted integer scalar descriptors.
- Floating bitwise operation inputs reach lowering and fail with the accepted
  operation/type compatibility diagnostic rather than source repair, fallback,
  or renderer-side inference.
- C++ and Rust emitters render accepted bitwise operations through
  backend-owned operator spelling maps while existing operations remain
  byte-stable.
- The M114 lowering stage-output boundary continues to carry the accepted
  operations without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject parser/source syntax broadening or source repair.
- Reviewers should reject putting C++/Rust spelling or runtime bitwise policy
  into lowering descriptors.
- Reviewers should reject logical boolean semantics, shifts/rotates, broad
  arithmetic frameworks, registries, or dispatchers.
- Reviewers should require current `add`/`sub`/`mul`/`div`/`mod` output bytes,
  diagnostics, M112 body values, M113 signature values, M114 stage-output
  behavior, and M116 compatibility behavior to remain stable.

### Milestone 118: Tiny Clean Unary Bitwise Not Lowering Shape Slice

Status:

Accepted. M118 added the exact unary `bit_not(value)` source/lowering shape,
modeled accepted unary source bodies as typed `UnaryOperationBody` catalog
values, added a backend-neutral unary operation descriptor and lowered unary
expression, and kept C++/Rust unary spellings backend-owned (`~value` for C++
and `!value` for Rust). `bit_not` lowers only for accepted integer scalar
descriptors, while accepted floating scalar descriptors fail in lowering with
`TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`. M118 preserved accepted binary
`add`/`sub`/`mul`/`div`/`mod`/`bit_*` behavior, M110 scalar descriptors, M112
body values, M113 signatures, M114 lowering stage-output behavior, M116/M117
compatibility behavior, diagnostics, logical paths, artifact ordering, and
existing artifact bytes and digests. M118 did not add broad TSIL parsing,
arbitrary arity, multiple statements, nested expressions, calls, variables,
source repair, logical boolean semantics, masks, shifts, rotates, bit-width
promotion, signedness runtime policy, constant folding, algebraic
simplification, vector/SIMD semantics, backend manifests, dependency closure,
old operation/lowering migration, registries, dispatchers, plugin systems,
hidden backfeeds, fixpoint mechanisms, or a broad expression/type framework.

Goal:

Add integer-only unary bitwise-not lowering for the exact one-parameter clean
source form:

```text
prim<v:=(v)> bit_not(value):
  implementation scalar si32:
    body bit_not(value)
```

Scope:

- Add the exact one-parameter source shape needed for `bit_not(value)`:
  signature `v:=(v)`, parameter tuple `("value",)`, and body argument tuple
  `("value",)`.
- Model the accepted unary source body as typed catalog data rather than
  forcing it through the binary body model.
- Add a small backend-neutral unary operation descriptor for `bit_not`.
- Add a small lowered unary operation expression/body path paired with the
  existing lowered function signature/return statement structure.
- Gate `bit_not` to the currently supported integer scalar descriptors and
  reject floating scalar descriptors with a structured lowering diagnostic.
- Keep unary descriptors backend-neutral. They must not contain C++ or Rust
  spelling, logical-boolean policy, mask policy, signedness runtime policy,
  overflow policy, or source repair policy.
- Update C++ and Rust backends to render accepted unary lowered expressions
  through backend-owned spellings. C++ and Rust may spell this differently, but
  spelling must stay in the backend layer.
- Preserve accepted binary `add`/`sub`/`mul`/`div`/`mod`/`bit_*` behavior,
  M110 scalar descriptors, M112 body values, M113 signatures, M114
  stage-output behavior, M116/M117 compatibility behavior, diagnostics,
  logical paths, artifact ordering, and existing artifact bytes and digests.
- Add focused tests for parsing/cataloging the exact unary form, rejecting
  nearby malformed unary forms, unary descriptor lookup/order, integer lowerer
  acceptance, floating-type rejection, backend spelling ownership, generator
  output for one integer `bit_not` source, M114 stage-output pass-through, and
  preservation of existing binary behavior.

Out of scope:

- Broad TSIL parsing, arbitrary arity support, multiple statements, nested
  expressions, calls, variables, source repair, or generalized expression
  trees beyond the accepted binary and exact unary shapes.
- Logical boolean semantics, boolean scalar types, masks, shifts, rotates,
  bit-width promotion, signedness runtime policy, constant folding, algebraic
  simplification, or broad bitwise/arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

Accepted outputs:

- The clean source-to-lowering path accepts the exact unary `bit_not(value)`
  shape and rejects unsupported nearby unary forms with structured diagnostics.
- `bit_not(value)` lowers only for accepted integer scalar descriptors.
- Floating `bit_not(value)` reaches lowering and fails with a structured
  operation/type compatibility diagnostic rather than source repair, fallback,
  or renderer-side inference.
- C++ and Rust emitters render accepted unary bitwise-not through
  backend-owned spelling rules while existing binary operations remain
  byte-stable.
- The M114 lowering stage-output boundary carries the accepted unary lowered
  function without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject broad parser/source syntax broadening or source
  repair.
- Reviewers should reject putting C++/Rust spelling or runtime unary bitwise
  policy into lowering descriptors.
- Reviewers should reject logical boolean semantics, shifts/rotates, broad
  expression frameworks, registries, or dispatchers.
- Reviewers should require current binary output bytes, diagnostics, M112 body
  values, M113 signature values, M114 stage-output behavior, and M116/M117
  compatibility behavior to remain stable.

### Milestone 119: Tiny Clean Unary Arithmetic Negation Type-Gated Lowering Slice

Status:

Accepted. M119 added backend-neutral unary `neg` after `bit_not` in the clean
unary operation descriptor table, reused the accepted exact unary
`v:=(v)`/`value` source and lowering path, and added a lowering-owned
operation/type compatibility gate that accepts `si32`, `f32`, and `f64` while
rejecting `ui32` with `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`. C++ and Rust own
the accepted `-` spelling in their backend layers. M119 preserved accepted
binary operations, M118 `bit_not` behavior, M110 scalar descriptors, M112 body
values, M113 signatures, M114 stage-output behavior, M116/M117/M118
compatibility behavior, diagnostics, logical paths, artifact ordering, and
existing artifact bytes/digests. M119 did not add source syntax beyond the
accepted unary form, source repair, runtime overflow/wrapping policy, unsigned
negation semantics, floating special-value policy, constant folding, broad
arithmetic semantics, vector/SIMD semantics, backend manifests, old imports,
registries, dispatchers, hidden backfeeds, fixpoint behavior, or a broad
expression/type framework.

Goal:

Add unary arithmetic negation for the accepted one-parameter clean source
shape:

```text
prim<v:=(v)> neg(value):
  implementation scalar si32:
    body neg(value)
```

Scope:

- Add `neg` to the existing lowering-owned unary operation descriptor table,
  preserving deterministic descriptor ordering after `bit_not`.
- Reuse the M118 exact unary source/catalog/lowering shape:
  signature `v:=(v)`, parameter tuple `("value",)`, typed unary operation
  body, and lowered unary expression.
- Extend the lowering-owned unary operation/type compatibility boundary so
  `neg` accepts currently supported signed integer and floating scalar
  descriptors (`si32`, `f32`, `f64`) and rejects unsigned scalar descriptors
  such as `ui32` with `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`.
- Keep unary descriptors backend-neutral. They must not contain C++ or Rust
  spelling, overflow/wrapping policy, unsigned-negation policy, floating
  special-value policy, constant-folding policy, or source repair policy.
- Update C++ and Rust backends to render accepted `neg` lowered expressions
  through backend-owned unary spellings.
- Preserve accepted binary operations, M118 `bit_not` behavior, M110 scalar
  descriptors, M112 body values, M113 signatures, M114 stage-output behavior,
  M116/M117/M118 compatibility behavior, diagnostics, logical paths, artifact
  ordering, and existing artifact bytes and digests.
- Add focused tests for unary descriptor lookup/order, signed/floating lowerer
  acceptance, unsigned rejection with the existing operation/type diagnostic,
  backend spelling ownership, generator output for at least one `neg` source,
  M114 stage-output pass-through, and preservation of existing binary and
  `bit_not` behavior.

Out of scope:

- New source syntax beyond the accepted M118 one-parameter unary form, broad
  TSIL parsing, arbitrary arity support, multiple statements, nested
  expressions, calls, variables, source repair, or generalized expression
  trees beyond the accepted binary and exact unary shapes.
- Runtime overflow/wrapping policy, unsigned negation semantics, floating
  special-value policy, constant folding, algebraic simplification, or broad
  arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

Accepted outputs:

- `neg(value)` lowers for accepted signed integer and floating scalar
  descriptors.
- Unsigned `neg(value)` reaches lowering and fails with the existing
  operation/type compatibility diagnostic rather than source repair, fallback,
  runtime policy, or renderer-side inference.
- C++ and Rust emitters render accepted unary negation through backend-owned
  spelling rules while existing binary operations and `bit_not` remain
  byte-stable.
- The M114 lowering stage-output boundary carries the accepted `neg` lowered
  function without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject source syntax broadening beyond the accepted unary
  form or source repair.
- Reviewers should reject putting C++/Rust spelling or runtime negation policy
  into lowering descriptors.
- Reviewers should reject broad arithmetic semantics, broad expression
  frameworks, registries, or dispatchers.
- Reviewers should require current binary output bytes, `bit_not` output
  bytes, diagnostics, M112 body values, M113 signature values, M114
  stage-output behavior, and M116/M117/M118 compatibility behavior to remain
  stable.

### Milestone 120: Tiny Clean Shift Binary Operations Type-Gated Lowering Slice

Status:

Accepted. M120 added backend-neutral `shift_left` and `shift_right` after
`bit_xor` in the clean binary operation descriptor table, reused the accepted
exact binary source/catalog/lowering shape, and reused the lowering-owned
operation/type compatibility boundary so shifts lower only for `si32` and
`ui32` while floating descriptors fail with
`TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`. C++ and Rust own the accepted `<<` and
`>>` spellings in their backend layers. M120 preserved accepted
`add`/`sub`/`mul`/`div`/`mod`/`bit_*` binary behavior, M118/M119 unary
behavior, M110 scalar descriptors, M112 body values, M113 signatures, M114
stage-output behavior, M116-M119 compatibility behavior, diagnostics, logical
paths, artifact ordering, and existing artifact bytes/digests. M120 did not
add source syntax beyond the accepted binary form, shift-count range/width
policy, arithmetic-vs-logical right-shift runtime policy, undefined-behavior
modeling, source repair, rotates, masks, vector/SIMD semantics, backend
manifests, old imports, registries, dispatchers, hidden backfeeds, fixpoint
behavior, or a broad expression/type framework.

Goal:

Add exact integer shift operations for the accepted scalar binary source form:

```text
prim<v:=(v,v)> shift_left(left, right):
  implementation scalar si32:
    body shift_left(left, right)
```

and:

```text
prim<v:=(v,v)> shift_right(left, right):
  implementation scalar si32:
    body shift_right(left, right)
```

Scope:

- Add `shift_left` and `shift_right` to the existing lowering-owned binary
  operation descriptor table, preserving deterministic descriptor ordering
  after `bit_xor`.
- Reuse the accepted exact binary source/catalog/lowering shape:
  signature `v:=(v,v)`, parameter tuple `("left", "right")`, typed binary
  operation body, lowered binary expression, and M114 stage-output boundary.
- Extend the lowering-owned operation/type compatibility boundary so
  `shift_left` and `shift_right` accept the currently supported integer scalar
  descriptors (`si32`, `ui32`) and reject floating scalar descriptors with
  `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`.
- Keep binary descriptors backend-neutral. They must not contain C++ or Rust
  spelling, shift-count range/width policy, arithmetic-vs-logical right-shift
  policy, signedness runtime policy, overflow/wrapping policy, constant-folding
  policy, or source repair policy.
- Update C++ and Rust backends to render accepted shift lowered expressions
  through backend-owned spellings.
- Preserve accepted `add`/`sub`/`mul`/`div`/`mod`/`bit_*` binary behavior,
  M118/M119 unary behavior, M110 scalar descriptors, M112 body values, M113
  signatures, M114 stage-output behavior, M116-M119 compatibility behavior,
  diagnostics, logical paths, artifact ordering, and existing artifact bytes
  and digests.
- Add focused tests for binary descriptor lookup/order, integer lowerer
  acceptance, floating rejection with the existing operation/type diagnostic,
  backend spelling ownership, generator output for at least one shift source,
  M114 stage-output pass-through, and preservation of existing binary and
  unary behavior.

Out of scope:

- New source syntax beyond the accepted binary form, broad TSIL parsing,
  arbitrary arity support, shift-immediate forms such as `sImm`, multiple
  statements, nested expressions, calls, variables, source repair, or
  generalized expression trees beyond the accepted binary and exact unary
  shapes.
- Shift-count range validation, shift-count width policy,
  arithmetic-vs-logical signed right-shift runtime policy, undefined-behavior
  modeling, overflow/wrapping policy, constant folding, algebraic
  simplification, rotates, masks, or broad bitwise/arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

Accepted outputs:

- `shift_left(left, right)` and `shift_right(left, right)` lower for accepted
  integer scalar descriptors.
- Floating shift inputs reach lowering and fail with the existing
  operation/type compatibility diagnostic rather than source repair, fallback,
  runtime policy, or renderer-side inference.
- C++ and Rust emitters render accepted shifts through backend-owned spelling
  rules while existing binary and unary operations remain byte-stable.
- The M114 lowering stage-output boundary carries accepted shift lowered
  functions without adding scheduler, package, artifact-plan, or broad IR
  machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject source syntax broadening beyond the accepted binary
  form or source repair.
- Reviewers should reject putting C++/Rust spelling or shift runtime policy
  into lowering descriptors.
- Reviewers should reject broad arithmetic semantics, broad expression
  frameworks, registries, or dispatchers.
- Reviewers should require current binary and unary output bytes, diagnostics,
  M112 body values, M113 signature values, M114 stage-output behavior, and
  M116-M119 compatibility behavior to remain stable.

### Milestone 121: Tiny Clean Scalar Compare Result Lowering Shape Slice

Status:

Accepted. M121 added the first exact scalar comparison result lowering shape
for `equal(left, right)` over the documented `m:=(v,v)` source form. It models
comparison bodies as typed catalog data, lowers accepted `si32`, `ui32`, `f32`,
and `f64` equality comparisons into a backend-neutral comparison expression
with an explicit scalar-comparison result boundary, and keeps C++/Rust `bool`
result spelling plus `==` operator spelling owned by the backend layers. M121
preserved accepted binary and unary behavior, M110 scalar descriptors, M112
body values, M113 signatures, M114 stage-output behavior, M116-M120
compatibility behavior, diagnostics, logical paths, artifact ordering, and
existing artifact bytes. It did not add broad mask modeling, vector/SIMD
comparison results, comparison families beyond equality, floating
NaN/special-value policy, signed ordering policy, source repair, backend
manifests, old imports, registries, dispatchers, hidden backfeeds, fixpoint
behavior, or a broad expression/type framework.

Goal:

Add exact scalar equality comparison lowering for the documented compare source
shape:

```text
prim<m:=(v,v)> equal(left, right):
  implementation scalar si32:
    body equal(left, right)
```

Scope:

- Add parser/catalog support only for the exact compare source shape:
  signature `m:=(v,v)`, parameter tuple `("left", "right")`, one scalar
  implementation, and body argument tuple `("left", "right")`.
- Model the accepted compare source body as typed catalog data rather than
  forcing it through arithmetic/bitwise binary operation semantics.
- Add a small backend-neutral comparison operation descriptor for `equal` and
  a lowered comparison expression paired with the existing lowered
  return-statement/function structure.
- Introduce the smallest explicit lowered result-type boundary needed for a
  scalar comparison result. The accepted backend result spelling is `bool` in
  C++ and Rust, owned by the backend layer, not by lowering descriptors.
- Allow currently supported scalar descriptors (`si32`, `ui32`, `f32`, `f64`)
  as the left/right input scalar type for `equal(left, right)`.
- Update C++ and Rust backends to render accepted `equal` lowered expressions
  through backend-owned result-type and operator spelling rules.
- Preserve accepted binary and unary operation behavior, M110 scalar
  descriptors, M112 body values, M113 signatures, M114 stage-output behavior,
  M116-M120 compatibility behavior, diagnostics, logical paths, artifact
  ordering, and existing artifact bytes and digests.
- Add focused tests for parsing/cataloging the exact compare form, rejecting
  nearby malformed compare forms, descriptor lookup/order, lowerer acceptance
  for representative integer and floating scalar descriptors, backend result
  and operator spelling ownership, generator output for one `equal` source,
  M114 stage-output pass-through, and preservation of existing binary/unary
  behavior.

Out of scope:

- Compare operations beyond `equal`, broad mask modeling, vector/SIMD compare
  results, mask lane types, boolean scalar inputs, mask composition, predicate
  paths, or backend mask ABI decisions.
- New source syntax beyond the exact compare form, broad TSIL parsing,
  arbitrary arity support, multiple statements, nested expressions, calls,
  variables, source repair, or generalized expression trees beyond the
  accepted binary, unary, and exact comparison shapes.
- Floating NaN/special-value policy, signed ordering policy, runtime comparison
  semantics beyond emitting the backend-owned equality operator for accepted
  lowered values, constant folding, algebraic simplification, or broad
  comparison semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

Accepted outputs:

- The clean source-to-lowering path accepts the exact scalar
  `equal(left, right)` compare shape and rejects unsupported nearby forms with
  structured diagnostics.
- Accepted scalar inputs lower into a backend-neutral comparison expression
  with an explicit scalar comparison result boundary.
- C++ and Rust emitters render accepted equality comparison functions with
  backend-owned `bool` result type spelling and `==` operator spelling while
  existing binary and unary operations remain byte-stable.
- The M114 lowering stage-output boundary carries accepted comparison lowered
  functions without adding scheduler, package, artifact-plan, broad mask IR, or
  broad expression machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject source syntax broadening beyond the exact compare
  form or source repair.
- Reviewers should reject putting C++/Rust result-type spelling or comparison
  operator spelling into lowering descriptors.
- Reviewers should reject broad mask modeling, vector/SIMD comparison
  semantics, broad expression frameworks, registries, or dispatchers.
- Reviewers should require current binary and unary output bytes, diagnostics,
  M112 body values, M113 signature values, M114 stage-output behavior, and
  M116-M120 compatibility behavior to remain stable.

### Milestone 122: Tiny Clean Scalar Comparison Operator Family Lowering Slice

Status:

Accepted. M122 broadened the accepted M121 same-shape scalar comparison path
from `equal` to `nequal`, `less_than`, `greater_than`,
`less_than_or_equal`, and `greater_than_or_equal`. It reused the exact
`m:=(v,v)` / `left, right` source/catalog/lowering shape, kept comparison
descriptors backend-neutral, kept C++/Rust result and operator spellings
backend-owned, and preserved accepted binary, unary, and `equal` behavior.
M122 also addressed the M121 malformed compare-body follow-up with an explicit
`equal(value, right)` negative test. It did not add new compare source syntax,
broad mask modeling, vector/SIMD comparison results, runtime floating or
signed-ordering policy, source repair, backend manifests, old imports,
registries, dispatchers, hidden backfeeds, fixpoint behavior, or a broad
expression/type framework.

Goal:

Add exact scalar comparison lowering for the documented compare source shape:

```text
prim<m:=(v,v)> nequal(left, right):
  implementation scalar si32:
    body nequal(left, right)
```

and the same exact source/catalog/lowering shape for `less_than`,
`greater_than`, `less_than_or_equal`, and `greater_than_or_equal`.

Scope:

- Add `nequal`, `less_than`, `greater_than`, `less_than_or_equal`, and
  `greater_than_or_equal` to the existing lowering-owned comparison operation
  descriptor table, preserving deterministic descriptor ordering after
  `equal`.
- Reuse the accepted M121 exact compare source/catalog/lowering shape:
  signature `m:=(v,v)`, parameter tuple `("left", "right")`, one scalar
  implementation, typed comparison operation body, lowered comparison
  expression, explicit scalar-comparison result boundary, and M114
  stage-output boundary.
- Allow the currently supported scalar descriptors (`si32`, `ui32`, `f32`,
  `f64`) as the left/right input scalar type for each accepted comparison
  operation.
- Keep comparison descriptors backend-neutral. They must not contain C++ or
  Rust result-type spelling, backend operator spelling, runtime
  NaN/special-value policy, signed ordering policy, mask ABI policy,
  constant-folding policy, or source repair policy.
- Update C++ and Rust backends to render accepted comparison lowered
  expressions through backend-owned result-type spellings and backend-owned
  operator spellings: `!=`, `<`, `>`, `<=`, and `>=`.
- Preserve accepted `equal` behavior, binary and unary operation behavior,
  M110 scalar descriptors, M112 body values, M113 signatures, M114
  stage-output behavior, M116-M121 compatibility behavior, diagnostics,
  logical paths, artifact ordering, and existing artifact bytes and digests.
- Add focused tests for comparison descriptor lookup/order, parser/catalog
  acceptance for the exact compare family form, the M121 malformed
  body-argument follow-up case such as `equal(value, right)`, lowerer
  acceptance for representative integer and floating scalar descriptors,
  backend result/operator spelling ownership, generator output for at least
  one new comparison source, M114 stage-output pass-through, and preservation
  of existing binary, unary, and `equal` behavior.

Out of scope:

- New compare source syntax beyond the accepted M121 same-shape compare form,
  broad TSIL parsing, arbitrary arity support, compare-zero forms, range
  comparisons, special predicates, multiple statements, nested expressions,
  calls, variables, source repair, or generalized expression trees beyond the
  accepted binary, unary, and exact comparison shapes.
- Broad mask modeling, vector/SIMD compare results, mask lane types, boolean
  scalar inputs, mask composition, predicate paths, or backend mask ABI
  decisions.
- Floating NaN/special-value policy, signed ordering policy beyond emitting
  backend-owned operators for accepted lowered values, constant folding,
  algebraic simplification, or broad comparison semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

Accepted outputs:

- The clean source-to-lowering path accepts exact scalar comparison family
  forms for the currently supported scalar descriptors and rejects unsupported
  nearby forms with structured diagnostics.
- Accepted scalar inputs lower into backend-neutral comparison expressions
  with the accepted scalar-comparison result boundary.
- C++ and Rust emitters render accepted comparison functions with backend-owned
  `bool` result type spelling and backend-owned operator spelling while
  existing binary, unary, and `equal` operations remain byte-stable.
- The M114 lowering stage-output boundary carries accepted comparison-family
  lowered functions without adding scheduler, package, artifact-plan, broad
  mask IR, or broad expression machinery.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject source syntax broadening beyond the exact compare
  form or source repair.
- Reviewers should reject putting C++/Rust result-type spelling, comparison
  operator spelling, runtime floating policy, or signed-ordering policy into
  lowering descriptors.
- Reviewers should reject broad mask modeling, vector/SIMD comparison
  semantics, broad expression frameworks, registries, or dispatchers.
- Reviewers should require current binary, unary, and `equal` output bytes,
  diagnostics, M112 body values, M113 signature values, M114 stage-output
  behavior, and M116-M121 compatibility behavior to remain stable.

### Milestone 123: Tiny Clean Bootstrap Operation Semantics Contract Slice

Status:

Accepted after one write-capable executor plus read-only architecture,
boundary, documentation, and validation audits. M123 kept the next task
focused on lowering by making the accepted M111-M122 scalar operation facts an
explicit bootstrap-core lowering contract rather than implicit corpus-derived
knowledge in product code.

Goal:

Make the existing lowering-owned scalar operation descriptor and
operation/type compatibility facts explicitly identify their semantic origin as
accepted clean-restart bootstrap core semantics:

```text
add/sub/mul/div/mod/bit_*/shift_* -> binary bootstrap core operations
bit_not/neg -> unary bootstrap core operations
equal/nequal/less_than/... -> comparison bootstrap core operations
integer-only and tag-specific compatibility gates -> bootstrap core rules
```

Scope:

- Add the smallest typed lowering-owned semantic-origin contract needed for
  the accepted operation descriptor and operation/type compatibility rule
  records. The origin should identify the accepted bootstrap-core source of
  the rule; it must not be a path into `tsldata/`, `frozen/`, or
  `tslgenold/`.
- Attach that origin to existing binary, unary, and comparison operation
  descriptor records without changing their operation ids, arity, category,
  source body operation, semantic name, deterministic order, lookup behavior,
  or public import surface except where tests deliberately assert the new
  typed origin field.
- Attach the same origin contract to the existing lowering-owned
  operation/type compatibility rules for integer-only binary operations,
  `bit_not`, and `neg`.
- Keep backend result/type/operator spellings in the C++ and Rust backend
  layers. Lowering descriptors and compatibility rules must not contain
  backend text, backend capability state, backend manifest keys, or renderer
  policy.
- Add focused tests proving every accepted operation descriptor and
  compatibility rule declares the bootstrap-core origin, no descriptor/rule
  records corpus paths or backend spelling, descriptor/rule ordering is
  stable, existing lowering diagnostics remain clear, and existing generated
  artifact bytes for representative binary, unary, and comparison operations
  remain stable.
- Add a focused no-runtime-corpus-read regression for operation descriptor and
  compatibility-rule lookup/lowering if it can be done without broad monkey
  patching or hidden environment dependencies.
- Update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` only to record the accepted
  bootstrap-core semantic contract and the fact that `tsldata/` remains source
  corpus/fixture evidence, not runtime input to these lowering tables.

Out of scope:

- Adding new operation ids, scalar types, source syntax, templates, body
  shapes, broad TSIL parsing, arbitrary arity support, multiple statements,
  nested expressions, variables, calls, source repair, or generalized
  expression trees.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen/`, `tslgenold/`, plugins, or
  environment configuration at runtime.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Defining runtime floating NaN/special-value policy, signed ordering policy,
  shift-count policy, overflow/wrapping policy, vector/SIMD semantics, mask
  ABI policy, dependency closure, backend planning, artifact writing, CLI
  behavior, or generated-test execution.

Accepted outputs:

- The accepted scalar operation descriptor and compatibility-rule records have
  explicit typed bootstrap-core semantic origin.
- Existing binary, unary, and comparison lowering behavior, diagnostics,
  descriptor ordering, stage-output behavior, public API imports, generated
  logical paths, artifact ordering, and representative artifact bytes remain
  stable.
- Tests make it clear that accepted operation semantics are deliberate
  clean-restart core semantics, not accidental leakage from `tsldata/*`.
- `tsldata/`, `frozen/`, and `tslgenold/` remain evidence/source inputs only
  and are not read by lowering operation lookup or compatibility evaluation.

Validation:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/lowering/binary_operations.py tslgen/src/tslgen/lowering/unary_operations.py tslgen/src/tslgen/lowering/comparison_operations.py tslgen/src/tslgen/lowering/operation_type_compatibility.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
```

Run the smallest additional import check needed for the new semantic-origin
contract. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

Review notes:

- Reviewers should reject treating `tsldata/*` operation names as hidden
  runtime input to the lowering tables.
- Reviewers should reject backend spellings, backend manifests, or renderer
  policy in lowering descriptors or compatibility rules.
- Reviewers should reject broad operation registries, dispatchers, plugin
  systems, or wrapper-only provenance abstractions.
- Reviewers should require current binary, unary, and comparison behavior,
  diagnostics, output bytes, and stage-output behavior to remain stable.

### Milestone 124: Tiny Clean Multi-Primitive Source-Set Lowering Slice

Status:

Accepted after one write-capable executor plus read-only architecture,
boundary, documentation, and validation audits. M124 kept the next task
focused on lowering while moving the research prototype closer to the intended
product loop: changing explicit `.tsl` source files affects selected lowered
functions and generated artifacts, or produces clear diagnostics.

Goal:

Allow one generator run to consume a small explicit source set containing
multiple exact supported primitive `.tsl` files, select explicit targets from
that catalog, lower the selected implementations through the accepted M108-M123
lowering path, and emit deterministic C++/Rust artifacts.

Scope:

- Broaden catalog construction from exactly one parsed primitive per run to a
  deterministic catalog of multiple parsed primitives across explicit source
  documents. Preserve the current exact parser shape of one primitive,
  one scalar implementation, and one body line per `.tsl` file.
- Preserve the accepted M107-M123 body forms, scalar type descriptors,
  operation descriptors, compatibility rules, and
  `clean_restart_bootstrap_core` semantic-origin contract. M124 must not add
  operations, scalar types, or source body syntax.
- Add a focused duplicate primitive-name diagnostic before selection/lowering
  so multiple source files cannot silently choose whichever duplicate appears
  first.
- Keep target requests explicit. Selection should choose requested primitive,
  backend, extension, and type from the multi-primitive catalog; M124 must not
  add automatic target discovery or "generate everything" behavior.
- Prove that a source-set change flows through lowering by adding fixtures or
  test-built source documents for at least representative binary, unary, and
  comparison primitives and by asserting selected lowered functions/artifacts
  reflect the `.tsl` primitive/body/type data.
- Add negative tests showing unsupported or mismatched `.tsl` operation bodies
  still produce structured lowering diagnostics rather than source repair,
  renderer inference, or silent fallback.
- Add determinism tests that run the same explicit source set in different
  input orders and compare diagnostics, artifact logical paths, contents, and
  digests.

Out of scope:

- Parsing multiple primitive blocks inside one `.tsl` document, loading the
  broad `tsldata/` corpus, parsing broad TSL syntax, parsing TSIL strings, or
  accepting body shapes beyond the exact M107-M123 forms.
- Adding new operation ids, scalar types, templates, implementation variants,
  extension fallback, dependency closure, backend manifests, target discovery,
  generated-test execution, CLI behavior, writer behavior, or output tree
  parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen/`, `tslgenold/`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

Accepted outputs:

- A `Catalog` may contain multiple exact supported primitives from explicit
  source documents, ordered deterministically.
- Duplicate primitive names in the explicit source set fail with a structured
  diagnostic before selection/lowering.
- Existing one-primitive generation behavior and representative artifact bytes
  remain stable.
- Multiple explicit targets can select and lower different primitives from the
  same source set and produce deterministic C++/Rust artifacts.
- Tests demonstrate that future `.tsl` edits to accepted primitive/body/type
  data are the product input to lowering, while unsupported edits remain
  diagnostic boundaries.

Validation:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/pipeline/generator.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

Review notes:

- Reviewers should require M124 to remain a source-set-to-lowering product
  slice, not a broad parser/corpus-loading milestone.
- Reviewers should reject multi-block `.tsl` parsing, broad `tsldata/`
  ingestion, automatic target discovery, operation semantics loaded from
  corpus/manifest data, or renderer-side semantic inference.
- Reviewers should require explicit diagnostics for duplicate primitive names
  and unsupported/mismatched body operations.
- Reviewers should require existing one-primitive behavior, backend-owned
  spellings, accepted semantic-origin fields, deterministic target ordering,
  and artifact bytes to remain stable.

### Milestone 125: Tiny Clean Multi-Implementation Primitive Lowering Slice

Status:

Accepted. The M125 execution-review loop returned `Accept With Follow-Ups`
after one write-capable executor and read-only architecture, boundary,
documentation, and validation audits. The follow-ups were finalization-only:
mark M125 accepted, update workflow state, and create the integrated M126
execution prompt.

Goal:

Allow one exact supported primitive `.tsl` document to contain multiple scalar
implementation blocks for distinct type tags. Selection must choose the
implementation requested by the explicit target, and lowering/backend emission
must consume only that selected implementation while preserving accepted
M108-M124 behavior.

Scope:

- Broaden the narrow parser/catalog source shape from one scalar
  implementation block per primitive document to two or more exact scalar
  implementation blocks under one primitive header. Each implementation block
  remains exactly an implementation header immediately followed by one body
  line.
- Preserve the accepted primitive header shapes, body argument shapes,
  operation descriptors, scalar type descriptors, compatibility rules, and
  `clean_restart_bootstrap_core` semantic-origin contract.
- Add duplicate implementation-key diagnostics for repeated
  `(extension, type_tag)` entries within the same primitive before selection
  and lowering.
- Keep target requests explicit. Selection should pick only the implementation
  matching the target extension and type tag; M125 must not add target
  discovery, generate-all behavior, extension fallback, type groups, or
  implementation ranking.
- Prove that selected implementation bodies drive lowering by testing a source
  document with multiple type-specific implementations for at least one
  representative binary primitive, and by asserting generated C++/Rust
  artifacts reflect the selected implementation's type/body.
- Prove that unselected implementation bodies are not lowered by adding a
  focused test where an unselected exact-shape implementation would be
  semantically unsupported if selected, while the selected implementation still
  generates successfully.
- Add negative tests showing duplicate implementation keys and selected
  mismatched bodies produce structured diagnostics, not source repair,
  renderer inference, or silent fallback.
- Preserve M124 multi-document source-set behavior and deterministic artifact
  ordering.

Out of scope:

- Parsing multiple primitive blocks inside one `.tsl` document, loading broad
  `tsldata/`, parsing broad TSL syntax, parsing TSIL strings, or accepting
  body shapes beyond the exact M107-M124 forms.
- Adding new operation ids, scalar types, templates, type groups, extension
  fallback, dependency closure, backend manifests, target discovery,
  generated-test execution, CLI behavior, writer behavior, or output tree
  parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

Accepted outputs:

- A parsed primitive may contain multiple exact scalar implementation blocks
  with distinct type tags.
- A catalog primitive may expose multiple typed `Implementation` values for
  explicit target selection.
- Duplicate implementation keys fail with a structured diagnostic before
  selection/lowering.
- Selection and lowering consume only the explicit target's implementation;
  unselected exact-shape implementation bodies do not create lowering
  diagnostics.
- Existing one-implementation, M124 multi-source, and representative artifact
  bytes remain stable.

Validation:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

Review notes:

- Reviewers should require M125 to remain a selected-implementation lowering
  slice, not broad TSL parsing or corpus ingestion.
- Reviewers should reject automatic target discovery, type-group expansion,
  extension fallback, implementation ranking, backend manifest loading,
  renderer-side semantic inference, or source repair.
- Reviewers should require duplicate implementation-key diagnostics to remain
  narrow and deterministic.
- Reviewers should require existing one-implementation behavior, M124
  multi-source behavior, backend-owned spellings, accepted semantic-origin
  fields, and artifact bytes to remain stable.

Review result:

- Parser support was broadened from one scalar implementation block to one or
  more exact scalar implementation/body pairs under the same primitive header.
- Catalog construction now rejects duplicate `(extension, type_tag)`
  implementation keys within one primitive with
  `TSL-CATALOG-DUPLICATE-IMPLEMENTATION-KEY` before selection/lowering.
- Explicit target selection and lowering consume only the matching
  implementation; unselected exact-shape implementation bodies do not create
  lowering diagnostics.
- Existing one-implementation behavior, M124 multi-source behavior,
  `clean_restart_bootstrap_core` semantic-origin records, backend-owned
  spellings, source-body integrity, deterministic artifact ordering, and
  representative artifact bytes remained stable.

Validation result:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

`git diff --check` returned exit 0 with no output. The public API import
command returned exit 0 with no output. The py-compile command returned exit 0
with no output. The targeted clean-package pytest command returned exit 0 with
`112 passed in 7.38s`. Validation-created `__pycache__` directories were
removed, and the final `find tslgen -type d -name __pycache__ -print` returned
exit 0 with no output.

### Milestone 126: Tiny Clean Ordered Implementation Body Line Boundary Slice

Status:

Accepted. This milestone applied ADR-036 before adding more TSIL source forms.
It consolidated implementation bodies toward ordered source-owned body lines
with optional lowerable segments. The first slice preserved the current exact
synthetic `body ...` fixture behavior by representing it as a one-line body
containing one lowerable operation fragment.

Goal:

Represent the existing accepted selected scalar implementation body line:

```text
    body add(left, right)
```

as an ordered implementation body:

```text
ImplementationBody
  lines:
    SegmentedBodyLine
      segments:
        LowerableOperationFragment(operation="add", arguments=("left", "right"))
```

The selected implementation must still lower through the existing typed
selected-implementation path and preserve M107-M125 generated artifacts.

Scope:

- Introduce small typed parser/domain values for implementation bodies as
  ordered body lines with lowerable segments, aligned with ADR-036.
- Represent the existing exact `body <operation>(...)` line as a body with one
  `LowerableOperationFragment`; do not add new accepted source syntax.
- Keep lowering focused: consume only the accepted one-line / one-fragment body
  forms for the already supported binary, unary, and comparison templates.
- Preserve all accepted primitive header shapes, selected-implementation
  behavior, body argument shape rules, operation descriptors, scalar type
  descriptors, compatibility rules, and the `clean_restart_bootstrap_core`
  semantic-origin contract.
- Keep target requests explicit. Selection should pick only the implementation
  matching the target extension and type tag; do not add target discovery,
  generate-all behavior, extension fallback, type groups, or implementation
  ranking.
- Prove existing selected bodies still drive lowering and generated C++/Rust
  artifacts for representative binary, unary, and comparison primitives.
- Add negative tests showing malformed body-line/segment containers produce
  structured diagnostics rather than source repair, renderer inference, raw
  passthrough, or silent fallback.
- Preserve M125 multi-implementation behavior, M124 multi-source behavior, and
  deterministic artifact ordering.

Out of scope:

- Parsing or accepting TSIL strings, `emit_return(...)`, helper calls,
  primitive calls, intrinsics, casts, variables, immediates, multiple
  statements, multiline bodies, raw body passthrough, helper evaluation, branch
  pruning, source repair, or TSIL compiler behavior.
- Segmenting mixed raw/lowerable TSIL lines. M126 creates the body-line
  boundary but does not yet recognize raw text tokens or lowerable islands
  inside a raw source line.
- Parsing multiple primitive blocks inside one `.tsl` document, loading broad
  `tsldata/`, parsing broad TSL syntax, adding new operation ids, scalar
  types, templates, type groups, extension fallback, dependency closure,
  backend manifests, target discovery, generated-test execution, CLI behavior,
  writer behavior, or output tree parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

Accepted outputs:

- Implementation bodies have an explicit ordered body-line model.
- Existing exact `body <operation>(...)` source lines are promoted into typed
  lowerable operation fragments before lowering.
- Lowering consumes typed body-line/segment values and does not emit from raw
  source text or rescan source text in backends.
- Malformed or unsupported body-line/segment shapes are rejected with
  structured diagnostics and are not repaired, normalized, or passed through.
- Existing M107-M125 behavior and representative artifact bytes remain stable.

Validation:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/model.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

Review notes:

- Reviewers should require M126 to remain a body-model consolidation slice,
  not a broad TSIL parser, compiler milestone, raw passthrough renderer, or
  exact new TSIL source-form milestone.
- Reviewers should reject `emit_return(...)` parsing, helper parsing,
  primitive-call lowering, intrinsics, casts, generation-time helpers, branch
  pruning, backend manifest loading, renderer-side semantic inference, target
  discovery, or source repair.
- Reviewers should require existing body behavior to flow through typed
  body-token values before lowering/backend emission.

Review result:

- Parser-owned body values now represent the existing exact
  `body <operation>(...)` line as `ParsedImplementationBody` containing one
  `ParsedSegmentedLine` with one `ParsedLowerableOperationFragment`.
- Domain `Implementation` values initially carried `ImplementationBody` with
  ordered body-line/segment values; M131 superseded this as the canonical
  domain shape with ordered body tokens.
- Catalog construction promotes accepted exact body lines into typed
  lowerable operation fragments and rejects malformed body-line/segment
  containers with `TSL-CATALOG-UNSUPPORTED-BODY`.
- Lowering consumes typed `ImplementationBody` values and, after M131, accepts
  only the one-token operation-fragment shape for the already supported binary,
  unary, and comparison templates. It rejects raw-only or malformed containers
  with `TSL-LOWER-UNSUPPORTED-BODY`.
- M107-M125 source syntax, selected-implementation behavior, unselected-body
  behavior, bootstrap operation descriptors, backend-owned spellings,
  deterministic ordering, and representative artifact bytes remained stable.

Internal review verdict:

`Accept With Follow-Ups`. Architecture returned `Accept With Follow-Ups` with
documentation coherence as the only follow-up. Boundary and validation audits
returned `Accept`. Documentation audit initially returned `Needs Revision`
because `behavioral-spec.md` still named the old per-operation body classes;
a focused docs revision updated `behavioral-spec.md` and `domain-model.md`,
and focused documentation re-review returned `Accept`.

Validation result:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/model.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

`git diff --check` returned exit 0 with no output. The public API import
command returned exit 0 with no output. The py-compile command returned exit 0
with no output. The targeted clean-package pytest command returned exit 0 with
`116 passed in 12.79s`. Validation-created `__pycache__` directories were
removed, and the final `find tslgen -type d -name __pycache__ -print` returned
exit 0 with no output.

### Milestone 127: TSIL Corpus Surface Inventory And Lowering Classification Slice

Status:

Accepted. This milestone corrected the next-step direction after the
body-model boundary: before adding more lowerable body fragments, it
inventoried the actual TSIL surface used by the current `tsldata/**/*.tsl`
corpus and classified which construct families are raw text, generator
directives, backend-control directives, primitive-call semantics,
backend-owned operations, helper calls, or deferred language forms.

Goal:

Create a corpus-grounded inventory from all current `tsldata/**/*.tsl` files,
not from one representative source file and not from synthetic clean-restart
fixture syntax. The inventory should make clear that primitive-looking calls
such as `sub(...)` are not a real accepted TSIL surface form unless they occur
through documented TSIL constructs such as:

```text
emit_return(left + right);
emit_return(call<primitive=sub>(left, right));
result[i] = details::arith_mul(data[i], factor);
if<generation>(...) { ... } else<generation> { ... }
if<compile>(...) { ... } else<compile> { ... }
if<runtime>(...) { ... } else<runtime> { ... }
```

The result should recommend the next implementation milestone as one real,
documented TSIL construct family rather than another synthetic
`body <operation>(...)` refinement.

Scope:

- Inspect all current `tsldata/**/*.tsl` files as the ground-truth corpus for
  source-body surface evidence. `frozen/` may be cited only as grammar or
  historical evidence, not as the corpus being inventoried.
- Create or update a focused redesign document, preferably
  `docs/redesign/tsil-surface-inventory.md`, that records the observed TSIL
  construct families with representative current `tsldata/` file references.
- Classify at least these buckets:
  - TSIL payload envelope forms: inline and multiline `tsil` payloads.
  - Return/directive forms such as `emit_return(...)`.
  - Primitive-call forms such as `call<primitive=...>(...)` and
    `call<primitive=@self[...]>(...)`.
  - Generation-time control forms such as `if<generation>`,
    `else<generation>`, generation loops, and generation `type<...>` /
    `value<...>` queries.
  - Backend-control forms, explicitly checking `if<compile>`,
    `else<compile>`, `if<runtime>`, and `else<runtime>` even if the current
    corpus count is zero.
  - Backend/generation query forms such as `type<backend>(...)`,
    `value<backend>(...)`, `type<generation>(...)`, and
    `value<generation>(...)`.
  - Backend intrinsic forms such as `intrin_compose<...>(...)` and
    `intrin<...>(...)`.
  - Helper-call forms such as `details::arith_add`, `details::arith_mul`,
    `details::arith_rem`, `details::popcount`, `details::clz`,
    `details::ctz`, and `details::mask_test`.
  - Raw target-language-like syntax around TSIL islands, including
    assignments, declarations, array indexing, operators, loops, and braces.
- For each bucket, state whether the likely generator treatment is `raw`,
  `lowerable directive`, `lowerable semantic operation`, `backend-owned`,
  `helper substitution candidate`, or `defer/diagnose`.
- Recommend exactly one next M128 implementation milestone grounded in the
  inventory. Prefer a small construct family that moves the source-to-artifact
  path toward real `.tsl` bodies without requiring a complete TSIL compiler.
- Preserve M126 as a body-line/segment container boundary, but do not treat
  the synthetic `body <operation>(...)` fixture form as evidence that
  `sub(...)`, `add(...)`, or similar primitive-looking calls are real TSIL
  constructs.

Out of scope:

- Implementing production parser, catalog, selection, lowering, backend, CLI,
  writer, or generated-output code.
- Accepting new source syntax in the clean generator.
- Lowering `emit_return(...)`, `call<primitive=...>`, helpers, intrinsics,
  assignments, array access, loops, declarations, backend-control forms, or
  raw target-language text in this milestone.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Treating current `tsldata/` corpus inspection as a runtime dependency.
- Building a complete TSIL grammar/parser, semantic validator, source repair
  mechanism, broad expression parser, or target-language compiler.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result/worklist family.

Accepted outputs:

- A reviewed TSIL surface inventory document grounded in all current
  `tsldata/**/*.tsl` files.
- The inventory explicitly records generation-control and backend-control
  buckets, including `if<compile>`, `else<compile>`, `if<runtime>`, and
  `else<runtime>`.
- The inventory distinguishes real TSIL constructs from the clean-restart
  synthetic `body <operation>(...)` fixture syntax.
- The next concrete M128 prompt is an implementation milestone selected from
  one real, documented TSIL construct family.
- No production generator behavior changes in this milestone.

Validation:

```bash
git diff --check
rg --files tsldata | rg "\\.tsl$" | sort
rg -n "tsil|emit_return|call<primitive=|intrin|intrin_compose|details::|if<generation>|else<generation>|if<compile>|else<compile>|if<runtime>|else<runtime>|loop<|var<|let<|type<generation>|type<backend>|value<generation>|value<backend>" tsldata -g "*.tsl"
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. This is a documentation/evidence milestone; if no Python code
is executed, the final cache check should normally return no output.

Review notes:

- Reviewers should require M127 to remain a corpus inventory and lowering
  classification milestone, not a product-code parser/lowering milestone.
- Reviewers should reject any inventory based on a single file or synthetic
  fixture forms instead of all current `tsldata/**/*.tsl` files.
- Reviewers should require backend-control forms `if<compile>`,
  `else<compile>`, `if<runtime>`, and `else<runtime>` to be explicitly checked
  and recorded even if absent from the current corpus.
- Reviewers should reject any recommendation that treats `sub(...)`,
  `add(...)`, or similar primitive-looking calls as real TSIL constructs
  unless the inventory shows that exact surface form in `tsldata/`.

Review result:

- Created `docs/redesign/tsil-surface-inventory.md` as the M127 inventory
  document grounded in all 41 current `tsldata/**/*.tsl` files.
- The inventory records `tsil` payload envelopes, `emit_return(...)`,
  primitive-call forms, generation-control forms, backend-control forms,
  backend/generation queries, intrinsic forms, helper calls, raw surrounding
  target-language-like text, and backend translation metadata.
- The backend-control bucket explicitly records present `if<compile>` and
  `else<compile>` forms and explicitly records that `if<runtime>` and
  `else<runtime>` are absent from the current corpus.
- The inventory distinguishes real TSIL constructs from the clean-restart
  synthetic `body <operation>(...)` fixture syntax and records that bare
  primitive-looking calls such as `sub(left, right)` are not real TSIL
  primitive-call syntax in the current corpus.
- The inventory recommends M128 as a lowering-enabling real `tsil`
  payload-envelope intake slice.
- No production parser, catalog, lowering, backend, renderer, writer, or
  generated-output code changed in M127.

Internal review verdict:

`Accept With Follow-Ups`. Architecture returned `Accept With Follow-Ups` with
one nonblocking note to keep M128 framed as a lowering-enabling payload intake
slice rather than semantic lowering. Boundary returned `Accept`. Documentation
returned `Accept With Follow-Ups` with nonblocking notes to explicitly record
`else if<generation>` before any generation-control lowering milestone and to
record TSIL-style `cast<...>`, `mem<...>`, and `io<...>` forms before any
related lowering milestone. Validation returned `Accept`.

Validation result:

```bash
git diff --check
rg --files tsldata | rg "\\.tsl$" | sort
rg -n "tsil|emit_return|call<primitive=|intrin|intrin_compose|details::|if<generation>|else<generation>|if<compile>|else<compile>|if<runtime>|else<runtime>|loop<|var<|let<|type<generation>|type<backend>|value<generation>|value<backend>" tsldata -g "*.tsl"
find tslgen -type d -name __pycache__ -print
```

`git diff --check` returned exit 0 with no output.
`rg --files tsldata | rg "\\.tsl$" | sort` returned exit 0 and printed the 41
current `.tsl` corpus paths. The required corpus `rg -n` command returned exit
0 and printed 5827 matching lines. The final
`find tslgen -type d -name __pycache__ -print` returned exit 0 with no output.

### Milestone 128: Real TSIL Payload Envelope Body Intake Slice

Status:

Accepted after the M128 execution-review loop. This is a lowering-enabling
slice, not semantic TSIL lowering: it admits real source-authored quoted
`tsil` payload envelopes as source-owned raw body content so future lowering
milestones can select exact TSIL islands from real payloads. M128 originally
used the then-current M126 line model; M131 superseded the canonical domain
shape with body tokens.

Goal:

Extend the clean restart parser/catalog body intake to recognize quoted
`tsil` payload envelopes in the existing narrow clean source shape. Preserve
the existing synthetic `body <operation>(...)` fixture behavior, but allow a
selected implementation body to carry raw TSIL payload lines such as:

```text
tsil "emit_return(left + right);"
```

and multiline quoted TSIL payloads such as:

```text
tsil """
  var<init_register>(result)
  emit_return(result);
"""
```

The payload content originally became ordered raw body-line values inside
`ImplementationBody`; after M131, the canonical domain form is ordered
`RawStringToken` values. It is not parsed into `emit_return`, primitive-call,
helper, intrinsic, assignment, loop, generation-control, backend-control, or
operator semantics in this slice.

Scope:

- Keep the existing exact `body <operation>(...)` path and accepted artifact
  behavior stable.
- Add parser-owned raw body-line intake and domain-owned raw body tokens for
  exact quoted `tsil` payload envelopes inside the current clean restart outer
  fixture shape.
- Preserve payload line order, source locations, and raw text. Do not repair
  indentation, punctuation, missing delimiters, or unsupported nearby source
  forms.
- Catalog construction may accept raw TSIL payload bodies as typed
  `ImplementationBody` values, but selected raw TSIL bodies must lower to an
  explicit unsupported-body diagnostic until later milestones select exact
  lowerable islands.
- Add focused tests for inline quoted `tsil`, multiline quoted `tsil`,
  malformed/unterminated quoted `tsil`, existing synthetic `body ...`
  stability, and selected raw TSIL unsupported-lowering behavior.
- Update docs if the implementation clarifies raw body-line behavior or
  diagnostic boundaries.

Out of scope:

- Parsing full current `tsldata/` primitive nesting under `impls:`.
- Supporting `tsil:` block entries; record as a follow-up unless selected by a
  later milestone.
- Lowering or parsing `emit_return(...)`, `call<primitive=...>`,
  `call<primitive=@self[...]>(...)`, helpers, intrinsics, assignments, array
  access, declarations, operators, loops, `if<generation>`,
  `else if<generation>`, `else<generation>`, `if<compile>`,
  `else<compile>`, `if<runtime>`, `else<runtime>`, `switch<compile>`, casts,
  memory helpers, or I/O helpers.
- Rendering raw TSIL payload text as C++ or Rust code.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Building a complete TSIL grammar/parser, semantic validator, source repair
  mechanism, broad expression parser, or target-language compiler.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result/worklist family.

Accepted outputs:

- Exact quoted `tsil` payload envelopes can be represented as ordered raw
  body content. After M131, parser line values are adapter details and domain
  `ImplementationBody` values carry ordered `RawStringToken` values.
- Existing synthetic `body <operation>(...)` fixture behavior and generated
  artifact bytes remain stable.
- Selected raw TSIL bodies produce structured unsupported-lowering diagnostics
  instead of generated backend code.
- No semantic TSIL lowerable islands are accepted in this milestone.

Validation:

```bash
git diff --check
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Review notes:

- Reviewers should require M128 to remain payload-envelope intake only. It is
  useful because future lowering must see real `tsil` payloads in the body
  model, but it must not overclaim semantic lowering.
- Reviewers should reject raw TSIL backend rendering, `emit_return(...)`
  parsing, helper substitution, primitive-call dependency lowering, or
  generation/backend-control lowering in this slice.
- Reviewers should require the M127 follow-ups about `else if<generation>` and
  `cast<...>` / `mem<...>` / `io<...>` buckets to remain recorded for future
  milestones rather than being accidentally implemented here.

Accepted result:

- Parser/catalog intake accepts exact inline and multiline quoted `tsil`
  payload envelopes as ordered raw body content. M131 superseded the original
  domain line representation with ordered `RawStringToken` values.
- Catalog admission for raw bodies is gated by the parser-owned quoted-TSIL
  envelope marker; arbitrary raw parsed body containers remain malformed
  catalog input.
- Lowering still rejects selected raw TSIL bodies with
  `TSL-LOWER-UNSUPPORTED-BODY`; no raw TSIL rendering or semantic TSIL lowering
  was added.
- Existing exact synthetic `body <operation>(...)` fixture behavior and
  representative generated artifact bytes remain stable.
- Review returned `Accept With Follow-Ups`: architecture and documentation
  returned `Accept With Follow-Ups`; boundary and validation returned
  `Accept`; no blocking findings were reported. The recorded follow-up is to
  keep `ParsedImplementationBody.envelope` as a parser/catalog admission marker
  only unless a later milestone explicitly documents or narrows additional
  envelope forms.

Validation result:

```bash
git diff --check
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

`git diff --check` returned exit 0 with no output. The py-compile command
returned exit 0 with no output. The pytest command returned exit 0 with
`122 passed in 8.23s`. The first cache check printed validation-created cache
directories; after removal, the final cache check returned exit 0 with no
output.

### Milestone 129: Exact TSIL Emit-Return Directive Boundary Slice

Status:

Accepted after the M129 execution-review loop. This is the first keyword-level
lowering slice over real quoted TSIL payload content. It recognizes the
`emit_return` TSIL directive envelope and preserves its argument as opaque
source text. It does not interpret the return expression, operators, operands,
helper calls, primitive calls, casts, intrinsics, array access, assignments, or
target-language-looking syntax.

Corpus grounding:

- `tsldata/primitives/arithmetic/fundamental.tsl:31` uses
  `tsil "emit_return(left + right);"`.
- `tsldata/primitives/arithmetic/fundamental.tsl:328` uses
  `tsil "emit_return(left - right);"`.
- `tsldata/primitives/comparison/fundamental.tsl:33`,
  `:192`, `:344`, `:539`, `:734`, and `:900` use exact scalar comparison
  returns for `==`, `!=`, `<`, `>`, `<=`, and `>=`.
- Many multiline payloads use indented `emit_return(...)` statements with
  nontrivial payloads such as `result`, `call<primitive=...>(...)`,
  `details::...`, `intrin_compose<...>(...)`, casts, array access, and
  generation/backend queries. These are evidence that `emit_return` is a TSIL
  directive boundary whose argument must remain opaque until separate
  expression/call/helper/query milestones are selected.

Goal:

When an M128 raw TSIL body line contains an exact `emit_return` statement
envelope:

```text
emit_return(<opaque-source-payload>);
emit_return(<opaque-source-payload>) ;
```

classify it as the existing typed directive concept
`LowerableDirective(name="emit_return", arguments=(<opaque-source-payload>,))`
or an equally narrow typed directive value if implementation evidence shows the
existing domain value is insufficient. The payload text is source-owned and
opaque. Do not split it into operands, parse operators, resolve helper calls,
or map it to a backend expression in this milestone.

Scope:

- Preserve the accepted synthetic `body <operation>(...)` lowering path and
  existing generated artifact bytes.
- Recognize only the `emit_return` keyword/directive envelope from M128 raw
  TSIL payload lines. Matching may ignore leading/trailing payload-line
  indentation introduced by quoted multiline TSIL, but the directive payload
  itself must remain unchanged source text.
- Preserve the raw directive argument exactly as source text between the outer
  `emit_return(` and its matching close parenthesis.
- Handle nested parentheses while finding the matching close parenthesis for
  the outer directive call; this is delimiter matching for the keyword
  envelope, not expression parsing.
- Promote exact `emit_return` directive lines into typed body/directive values
  that later expression/call/helper/query milestones can consume.
- Selected bodies containing only an `emit_return` directive with opaque
  payload must still stop before backend rendering with an explicit unsupported
  return-expression diagnostic unless the existing synthetic `body ...` path is
  in use.
- Diagnose malformed directive envelopes, missing semicolons, extra statements
  on the same line, unsupported directives, and non-directive raw lines as
  unsupported body/directive lowering. Do not repair source.
- Keep the parser/catalog M128 quoted-TSIL intake unchanged except for the
  exact directive classification needed by this milestone.

Out of scope:

- Full TSIL parsing, expression precedence, operator/operand parsing,
  expression semantic lowering, literals, constants, member access, array
  access, assignments, declarations, loops, block structure, comments inside
  expressions, semicolon repair, or whitespace normalization beyond exact
  directive-envelope matching.
- Lowering `details::arith_mul`, `details::arith_rem`,
  `details::arith_add`, operators such as `+`, `-`, `==`, `<`, `>`, `<=`,
  `>=`, `!=`, `call<primitive=...>`, `intrin`, `intrin_compose`,
  `cast<...>`, `type<generation>`, `type<backend>`, `value<generation>`,
  `value<backend>`, `if<generation>`, `else if<generation>`,
  `else<generation>`, `if<compile>`, `else<compile>`, `if<runtime>`,
  `else<runtime>`, `mem<...>`, or `io<...>`.
- Adding operation semantics from `tsldata/`, backend manifests, YAML,
  `frozen`, `tslgenold`, plugins, or environment configuration at runtime.
- Adding a complete TSIL grammar, semantic validator, target-language parser,
  renderer-side fallback, registry, dispatcher, callback map, hidden backfeed,
  fixpoint mechanism, or new lowering IR category/request/result/worklist
  family.

Accepted outputs:

- Exact raw TSIL `emit_return(...)` statement envelopes become typed
  `emit_return` directive/body values carrying opaque payload text.
- `emit_return(left + right);`, `emit_return(result);`,
  `emit_return(call<primitive=add>(left, right));`, and
  `emit_return(details::arith_mul(left, right));` all classify the same outer
  keyword/directive boundary while preserving different opaque payload text.
- Selected `emit_return` directive bodies do not render backend code until a
  later milestone lowers the opaque payload into a typed expression.
- Existing synthetic `body <operation>(...)` fixture behavior and generated
  artifacts remain stable.
- Nearby malformed or unsupported raw TSIL payloads remain diagnostics rather
  than raw backend output or guessed semantic lowering.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Review notes:

- Reviewers should require M129 to remain exact TSIL `emit_return` directive
  boundary lowering only. It should not become expression/operator/helper/call
  lowering.
- Reviewers should require the directive payload to remain source-owned opaque
  text and backend rendering to remain blocked until typed expression lowering
  exists.
- Reviewers should require helper substitution, primitive-call lowering,
  operator lowering, and generic/vector body lowering to remain future
  milestones.

Accepted result:

- Parser output for quoted TSIL payloads remains raw as established by M128.
- Catalog promotion classifies exact `emit_return(...)` payload lines from
  parser-recognized TSIL envelopes into `LowerableDirective` segments carrying
  opaque payload text.
- The directive matcher performs only outer keyword-envelope delimiter
  matching and preserves nested payloads such as
  `call<primitive=add>(left, right)` without parsing them.
- Lowering reports `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` for selected
  bodies containing only an `emit_return` directive with opaque payload; no
  raw TSIL payload text is rendered.
- Malformed directive envelopes, unsupported directive keywords, and
  non-directive raw lines remain unsupported body diagnostics.
- Existing synthetic `body <operation>(...)` behavior and representative
  artifact-byte tests remain stable.
- Review returned `Accept With Follow-Ups`: architecture, documentation, and
  validation returned `Accept With Follow-Ups`; boundary returned `Accept`; no
  blocking findings were reported. Follow-ups are to keep the TSIL envelope
  marker as an admission guard only, to consider extracting the small directive
  matcher before adding more directive recognition, and to add explicit
  coverage for the `emit_return(payload) ;` space-before-semicolon variant.

Validation result:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

`git diff --check` returned exit 0 with no output. The compileall command
returned exit 0 with no output. The pytest command returned exit 0 with
`127 passed in 9.94s`. The first cache check printed validation-created cache
directories; after removal, the final cache check returned exit 0 with no
output.

### Milestone 130: Exact TSIL Directive Envelope Boundary Slice

Status:

Accepted. The M130 execution-review loop returned `Accept With Follow-Ups`.
This is a keyword/directive boundary slice over M128 raw TSIL payload lines and
the M129 directive-classification path. It recognizes a small, explicit set of
exact TSIL directive envelopes and preserves their selectors, payloads, and raw
surrounding text as source-owned opaque text. It does not interpret
initializer expressions, helper calls, primitive calls, operators, type
queries, target-language-looking text, branch conditions, loop semantics,
block bodies, or storage semantics.

Corpus grounding:

- `tsldata/primitives/arithmetic/fundamental.tsl:36` uses
  `var<init_register>(result)`.
- `tsldata/primitives/bitwise/bit_ops.tsl:37-38` use
  `var<const_infer>(ua, call<primitive=reinterpret[...]>(left));` and
  `var<const_infer>(ub, call<primitive=reinterpret[...]>(right));`.
- `tsldata/primitives/bitwise/shifts.tsl:625-633` shows nested
  `if<generation>(...) {`, `if<compile>(...) {`, and
  `} else<compile> {` directive headers.
- `tsldata/primitives/load_store/rnd_access.tsl:33` uses
  `switch<compile>(scale) {`.
- `tsldata/primitives/arithmetic/fundamental.tsl:41-42` uses adjacent
  `loop<unroll>(...)` and `loop<range>(...) {` directive headers.
- `tsldata/primitives/bitwise/shifts.tsl:626` and nearby lines show
  `let<type>(...)` and `var<const_infer>(...)` inside directive blocks.

Goal:

When an M128 raw TSIL body line contains one exact selected directive
envelope, classify only the directive span and preserve surrounding source
text as raw tokens when present.

Accepted call-shaped directive envelopes:

```text
var<selector>(opaque-payload)
var<selector>(opaque-payload);
let<selector>(opaque-payload)
let<selector>(opaque-payload);
loop<selector>(opaque-payload)
loop<selector>(opaque-payload) {
if<selector>(opaque-payload)
if<selector>(opaque-payload) {
switch<selector>(opaque-payload)
switch<selector>(opaque-payload) {
```

Accepted selector-only directive envelopes:

```text
else<selector>
else<selector> {
```

The existing M129 `emit_return(opaque-payload)` directive remains accepted.
Classify with the existing source-body model, for example:

```text
LowerableDirective(name="var", arguments=(<selector>, <opaque-payload>))
LowerableDirective(name="loop", arguments=(<selector>, <opaque-payload>))
LowerableDirective(name="else", arguments=(<selector>,))
```

or an equally narrow typed directive value if implementation evidence shows the
existing domain value is insufficient. Selector and payload text are
source-owned opaque text. Preserve raw source before or after the matched
directive as `RawStringToken` segments. Do not split initializer arguments,
parse operators, resolve helper calls, resolve primitive calls, infer storage
semantics, evaluate conditions, pair `else` with `if`, match block bodies, or
map directives to backend code in this milestone.

Scope:

- Preserve M128 quoted-TSIL intake, M129 `emit_return` directive
  classification, and existing synthetic `body <operation>(...)` generated
  artifacts.
- Recognize only the selected directive envelopes from parser-recognized TSIL
  payload bodies: `var<...>(...)`, `let<...>(...)`, `loop<...>(...)`,
  `if<...>(...)`, `switch<...>(...)`, and `else<...>`.
- Preserve the selector text between `<` and the matching `>` and, for
  call-shaped directives, the payload text between the outer `(` and its
  matching `)`.
- Use delimiter matching for the directive envelope only. Nested parentheses
  and bracket/angle-like source text inside the payload remain opaque.
- Treat trailing `{`, trailing semicolons where accepted above, a leading `}`
  before `else<...>`, indentation, and other accepted surrounding target-like
  text as raw source tokens. Do not match or validate whole block bodies
  across lines.
- Classify indented multiline payload lines by ignoring indentation only to
  find the directive keyword; do not normalize selector, payload, or preserved
  raw text.
- Keep selected bodies containing these directives unsupported for backend
  rendering unless a later milestone defines complete statement/body lowering.
- Add tests for `var<init_register>(result)`,
  `var<const_infer>(ua, call<primitive=...>(left));`,
  `let<type>(UnsignedT, type<generation>(...))`, `loop<unroll>(...)`,
  `loop<range>(...) {`, `if<generation>(...) {`, `if<compile>(...) {`,
  `switch<compile>(...) {`, `} else<compile> {`, malformed envelopes,
  unsupported nearby directives, and coexistence with an already classified
  `emit_return` line in a multiline body.

Out of scope:

- Variable declaration semantics, storage initialization, type inference,
  expression parsing, helper/call/operator lowering, assignment lowering,
  loop execution semantics, branch/control evaluation, block-body matching,
  generation/backend query evaluation, backend rendering, source repair,
  complete TSIL grammar, runtime `tsldata` semantic lookup, `frozen` or
  `tslgenold` runtime dependency, registries, dispatchers, hidden backfeeds,
  fixpoint mechanisms, or new lowering IR category/request/result/worklist
  families.
- Supporting `call<...>`, `intrin`, `intrin_compose`, `cast<...>`, `mem<...>`,
  `io<...>`, `type<...>`, `value<...>`, helper calls, assignments, array
  access, or any keyword/directive not explicitly selected here.
- Pairing `if`/`else`, validating `else if<...>` chains, matching braces
  across multiple lines, or interpreting any raw prefix/suffix around a
  directive envelope.

Accepted outputs:

- Exact selected directive envelopes become typed directive/body values
  carrying opaque selector and payload text, with any raw prefix/suffix kept as
  raw source tokens.
- New directive classification coexists with M129 `emit_return`
  classification in ordered multiline bodies.
- Selected bodies containing recognized directives do not render backend code,
  infer semantics, evaluate conditions, or match blocks.
- Existing M128/M129 behavior remains stable.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Review notes:

- Reviewers should require M130 to remain exact directive-envelope
  classification only.
- Reviewers should reject initializer expression parsing, helper/call/operator
  lowering, variable lifetime/type inference, condition evaluation, block/body
  matching, assignment lowering, and backend rendering.
- Reviewers should consider whether adding these directives should extract
  the small directive-envelope matcher from `catalog_builder.py` into a focused
  syntax/catalog helper module without introducing a broad TSIL parser.

Execution notes:

- M130 added the focused private classifier
  `tslgen/src/tslgen/pipeline/_tsil_directives.py` and kept catalog promotion
  gated to parser-recognized quoted `tsil` payload envelopes.
- Exact selected directive envelopes become `LowerableDirective` segments;
  accepted raw prefix/suffix text such as `} ` before `else<...>`, ` {`, and
  `;` becomes `RawStringToken` data.
- Selected bodies containing M130 directives remain unsupported for backend
  rendering unless a later milestone defines complete body lowering.
- Review follow-ups were either addressed in the execution loop or recorded
  for later. The remaining follow-up is that M130 directive selector matching
  supports the current simple selector corpus only; future nested selector
  syntax must be explicitly selected and tested.
- Required validation returned exit 0 for `git diff --check`, compileall, and
  pytest; the final cache check returned exit 0 with no output after removing
  validation-created `__pycache__` directories.

### Milestone 131: Source-Owned Body Token Stream Consolidation Slice

Status:

Accepted. This is a behavior-preserving body-model consolidation slice. It
replaces line-as-primary domain body structure with a source-owned token stream
so later lowerable islands can cross source lines without forcing a TSIL
statement or expression parser. It preserves accepted M126-M130 behavior while
making the canonical domain body shape a sequence of raw text tokens and
lowerable tokens.

Design grounding:

- ADR-036 already records that implementation bodies are source-owned and
  lowerable islands should not imply parsing surrounding assignment,
  expression, scope, or statement-list syntax.
- M128-M130 show that `RawStringLine | SegmentedLine` is too line-centered for
  future lowerable islands that may span multiple lines.
- Current `.tsl` source contains multiline TSIL payloads and future island
  candidates such as `call<primitive=...>(...)`; those candidates should not
  force single-line-only lowering or a full TSIL parser.

Goal:

Make the domain `ImplementationBody` canonical shape a token stream:

```text
ImplementationBody
  tokens: tuple[BodyToken, ...]

BodyToken =
  RawStringToken
  LowerableOperationFragment
  LowerableDirective
```

Raw string tokens may contain newlines, indentation, braces, assignments,
semicolons, and any target-like text. Lowerable tokens keep the existing
opaque arguments/source locations accepted by M126-M130.

Parser output may remain line-oriented as an adapter detail if that keeps the
slice small, but catalog/domain/lowering code should consume the token stream
as the accepted body model. Existing line container values such as
`RawStringLine`, `SegmentedLine`, and `BodyLine` should be removed from the
canonical domain model or reduced to private/parser-side compatibility only if
removal would make the slice unnecessarily risky.

Scope:

- Preserve M126 synthetic `body <operation>(...)` lowering behavior and
  generated artifact bytes.
- Preserve M128 quoted-TSIL intake semantics: inline and multiline payloads
  become source-owned raw text in deterministic order.
- Preserve M129 `emit_return(...)` directive classification and unsupported
  opaque-return diagnostics.
- Preserve M130 directive-envelope classification, raw prefix/suffix
  preservation, and unsupported selected-body behavior.
- Preserve source locations for diagnostics. If raw text spans multiple lines,
  keep enough source identity for diagnostics and future cross-line lowerable
  islands.
- Update production code and tests to use the token-stream model as the domain
  and lowering boundary.
- Add tests proving:
  - `body add(left, right)` becomes one `LowerableOperationFragment` token;
  - inline quoted `tsil` becomes raw token data;
  - multiline quoted `tsil` preserves order and newline/text boundaries;
  - M129 `emit_return(...)` becomes one directive token;
  - M130 `} else<compile> {` becomes raw/directive/raw tokens in order;
  - selected unsupported TSIL bodies still diagnose without rendering raw text;
  - existing accepted artifact bytes remain stable.

Out of scope:

- New TSIL syntax recognition; `call<primitive=...>` island matching;
  primitive resolution; dependency closure; `@self` resolution; type-argument
  parsing; argument splitting; expression parsing; helper/operator lowering;
  assignment lowering; array access lowering; directive-payload segmentation;
  multiline call matching; generation/backend query evaluation; backend
  rendering; source repair; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

Accepted outputs:

- `ImplementationBody` exposes a deterministic token sequence as its canonical
  domain shape.
- `RawStringToken`, `LowerableOperationFragment`, and `LowerableDirective`
  values are the body-token vocabulary.
- Accepted M126-M130 behavior, diagnostics, source locations, and artifact
  bytes remain stable.
- No new lowerable island is recognized in M131.

Execution notes:

- Domain `ImplementationBody` now carries `tokens: tuple[BodyToken, ...]`.
  The old canonical `RawStringLine`, `SegmentedLine`, and `BodyLine` domain
  containers were removed.
- Parser-owned `ParsedRawStringLine` and `ParsedSegmentedLine` values remain
  parser/catalog adapter details only.
- Catalog promotion flattens parser body lines into the canonical body-token
  stream. M126 synthetic operation bodies become one
  `LowerableOperationFragment` token. M128 raw TSIL payload lines become
  ordered `RawStringToken` values. M129-M130 directive recognition produces
  `LowerableDirective` tokens plus preserved raw prefix/suffix tokens.
- Lowering consumes only the body-token stream and still accepts only the
  current one-token operation-fragment body shape for generated artifacts, or
  one opaque `emit_return` directive token for the existing unsupported-return
  diagnostic.
- M131 added no primitive-call matching, expression parsing, directive-payload
  segmentation, helper/operator lowering, backend rendering, source repair,
  runtime `tsldata` lookup, or `frozen`/`tslgenold` runtime dependency.
- Required validation returned exit 0 for `git diff --check`, compileall, and
  pytest; the final cache check returned exit 0 with no output after removing
  validation-created `__pycache__` directories.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

### Milestone 132: Exact TSIL Primitive-Call Body-Token Island Boundary Slice

Status:

Accepted. This is a lowering-boundary slice over the canonical
`ImplementationBody.tokens` stream. It recognizes exact TSIL
`call<primitive=...>(...)` keyword islands only inside raw body-token text from
parser-recognized quoted `tsil` payloads. It preserves raw source text around
the island and captures selector/payload text as opaque source-owned data.

Goal:

When raw body-token text contains an exact TSIL primitive-call island:

```text
call<primitive=selector>(opaque-payload)
```

classify only the call span as a lowerable token and preserve any raw
prefix/suffix as `RawStringToken` values. Selector and payload text remain
opaque. The matcher may use delimiter matching for the outer `call<...>(...)`
envelope, including current corpus selectors such as
`@self[type<backend>(vector::as_extension(scalar))]`, but it must not parse the
selector or payload semantics.

Scope:

- Consume the M131 body-token stream as the canonical body model.
- Recognize only exact `call<primitive=...>(...)` islands in raw tokens that
  are not already inside `LowerableDirective` payloads.
- Preserve raw prefix/suffix text around the call island, including assignment,
  array access, braces, semicolons, whitespace, and target-like text.
- Support delimiter matching over contiguous raw token text so the outer
  selector `>` and payload `)` may be found even when the current parser emits
  one raw token per source line.
- Keep selector and payload source text opaque; a zero-argument payload is
  accepted.
- Keep selected bodies containing primitive-call islands unsupported for
  backend rendering until later milestones define semantic call lowering.
- Add tests for raw prefix/suffix preservation, current-corpus nested selector
  spelling, zero-argument calls, cross-line raw-token matching, malformed call
  envelopes remaining unsupported, direct primitive-looking names remaining
  unsupported, no classification inside existing directive payload tokens, and
  artifact-byte stability for already accepted bodies.

Out of scope:

- Primitive resolution; dependency closure; `@self` resolution; type-argument
  parsing; call argument splitting; expression parsing; helper/operator
  lowering; assignment lowering; array access lowering; directive-payload
  segmentation; generation/backend query evaluation; backend rendering; source
  repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

Accepted outputs:

- Exact TSIL primitive-call islands in raw body-token text become typed
  lowerable body tokens carrying opaque selector and payload text.
- Raw source text before and after the island remains source-owned
  `RawStringToken` data.
- Existing M126-M131 behavior, diagnostics, source locations, and artifact
  bytes remain stable.
- No primitive-call semantic lowering, dependency closure, or backend rendering
  is introduced.

Execution notes:

- M132 adds a focused private primitive-call classifier over contiguous raw
  body-token runs after M130 directive classification.
- Exact primitive-call islands become existing `LowerableDirective` tokens
  named `call` with arguments `(primitive, selector, payload)`.
- The classifier preserves raw prefix/suffix text as `RawStringToken` data and
  requires a keyword boundary so nearby names such as `recall<primitive=...>`
  remain raw.
- Calls inside existing directive payloads remain opaque because only raw token
  runs are classified.
- Selected bodies containing primitive-call tokens still stop at unsupported
  body diagnostics; no primitive resolution, dependency closure, argument
  splitting, expression parsing, backend rendering, runtime `tsldata` lookup,
  or legacy runtime dependency was introduced.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

### Milestone 133: Exact TSIL Primitive-Call Lowering Boundary Slice

Status:

Accepted. This is a lowering-boundary slice over recognized M132
primitive-call body tokens. It adds the first tiny self-contained
primitive-call lowering case and a precise unsupported diagnostic for all
other recognized primitive-call tokens.

Goal:

When the selected implementation body is exactly the self-contained M132 call
token:

```text
LowerableDirective(name="call", arguments=("primitive", "add", "left, right"))
```

and the selected primitive is the already supported scalar `add(left, right)`
shape, lowering resolves it through the existing accepted add-operation path.
When a selected implementation body contains any other M132 primitive-call
token, lowering reports an explicit unsupported primitive-call diagnostic at
the call token source. The diagnostic may mention the opaque selector and
payload text, but it must not interpret them.

Scope:

- Consume the existing M132 body-token representation; do not change the parser
  or primitive-call classifier except for defects found by tests.
- Detect primitive-call tokens by the exact existing token shape:
  `LowerableDirective(name="call", arguments=("primitive", selector, payload))`.
- Lower only the exact self-contained selected `add` case:
  `call<primitive=add>(left, right)` with no raw prefix/suffix tokens, no
  `@self`, no catalog dependency walk, and no argument parsing beyond matching
  the exact payload text.
- Emit a stable diagnostic such as `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`
  before backend rendering for recognized primitive-call tokens outside that
  exact self-contained case.
- Preserve existing generic unsupported-body diagnostics for raw-only bodies,
  malformed nearby call-like source, direct primitive-looking names such as
  `sub(left, right)`, and non-call directives.
- Preserve the existing `emit_return(...)` opaque return diagnostic for
  `emit_return(call<primitive=...>(...));`; do not segment directive payloads
  in this milestone.
- Add tests for exact `call<primitive=add>(left, right)` lowering to the same
  generated artifact bytes as the accepted synthetic `body add(left, right)`
  path, selected assignment-like primitive-call diagnostics, exact
  zero-argument call diagnostics, multiple call-token diagnostics if already
  classified by M132, malformed/nearby raw calls remaining generic unsupported
  bodies, direct primitive-looking names remaining generic unsupported bodies,
  directive payload calls remaining opaque, and existing artifact-byte
  stability.

Out of scope:

- General primitive resolution beyond the exact `add(left, right)` case;
  dependency closure; `@self` resolution; type-argument parsing; call argument
  splitting; expression parsing; helper/operator lowering; assignment
  lowering; array access lowering; directive-payload segmentation;
  generation/backend query evaluation; new backend call rendering; source
  repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

Accepted outputs:

- A selected exact `call<primitive=add>(left, right)` body for the accepted
  scalar add shape lowers through the same typed operation path as
  `body add(left, right)`.
- Other selected bodies containing M132 primitive-call tokens produce a precise
  unsupported primitive-call lowering diagnostic at the call token source.
- Existing M126-M132 behavior, diagnostics, source locations, and artifact
  bytes remain stable except for the deliberately added exact add-call lowering
  and narrowed diagnostic for unresolved primitive-call tokens.
- No general primitive-call semantic lowering, dependency closure, argument
  splitting, directive-payload segmentation, or new backend call rendering is
  introduced.

Execution notes:

- Lowering now recognizes a single-token M132 primitive-call body only when the
  selected primitive is `add`, the selected template is `binary`, and the call
  token arguments are exactly `("primitive", "add", "left, right")`.
- The accepted exact call is converted into the same typed add operation path
  used by the synthetic `body add(left, right)` source form; backend emitters
  did not gain any call rendering behavior.
- Other selected M132 primitive-call tokens produce
  `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` at the call token source. Selector and
  payload text appear only as opaque diagnostic context.
- Raw-only bodies, malformed nearby call-like source, direct primitive-looking
  names such as `sub(left, right)`, non-call directives, and
  `emit_return(call<primitive=...>(...));` payloads preserve their existing
  unsupported-body or unsupported-return boundaries.
- Review returned `Accept` from architecture, boundary, documentation, and
  validation auditors. A nonblocking follow-up notes that explicit selected
  `@self` primitive-call diagnostic coverage would make the boundary even more
  visible, although the implementation already rejects it by construction.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `144 passed in 8.39s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 134: Exact Lowerable Directive Payload Token Boundary Slice

Status:

Accepted. This is a narrow body-token composition slice. It gives selected
lowerable directives a source-owned payload-token boundary so lowerable islands
inside directive payloads can be represented as tokens instead of forcing later
milestones to hardcode combined source strings.

Goal:

When an M129 `emit_return(...)` directive payload contains an exact M132
primitive-call island:

```text
emit_return(call<primitive=add>(left, right));
```

the `emit_return` directive should retain the original opaque payload text for
diagnostics and also expose a payload-token stream containing the already
recognized primitive-call token. Lowering may then compose existing boundaries:
`emit_return` supplies the return context, and the payload token lowers only if
it is already accepted by the M133 exact self-contained add-call boundary.

This is not a milestone for matching the combined source string
`emit_return(call<primitive=add>(left, right));`. It is a milestone for making
directive payloads capable of carrying raw text plus lowerable islands in the
same spirit as `ImplementationBody.tokens`.

Scope:

- Consume the existing M129 `emit_return` directive representation and M132
  primitive-call island classifier; do not change parser syntax, source
  envelope intake, or standalone M132 call-token behavior except for defects
  found by tests.
- Introduce the smallest durable payload-token representation needed for
  lowerable directive payloads. The first accepted producer is
  `emit_return(...)`; other directive payloads such as `var`, `let`, `loop`,
  `if`, and `switch` remain opaque unless explicitly selected later.
- Preserve the original opaque payload text for diagnostics while exposing
  ordered payload tokens for exact lowerable islands. Raw prefix/suffix payload
  text remains raw payload-token data.
- Classify only exact `call<primitive=...>(...)` islands inside the
  `emit_return` payload using the M132 call-envelope rules. Selector and
  payload text inside the call remain opaque.
- Lower an `emit_return` directive only when its payload-token stream contains
  exactly one payload token that can already lower through the M133 exact
  `call<primitive=add>(left, right)` boundary for the accepted scalar add
  shape.
- Emit `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` at the call token source when an
  `emit_return` payload contains a recognized primitive-call token that cannot
  lower through the M133 boundary.
- Preserve `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` for raw-only,
  raw-plus-call, malformed nearby call-like, helper/operator/identifier, and
  other unsupported `emit_return` payloads.
- Add tests for payload-token representation of
  `emit_return(call<primitive=add>(left, right));`, exact artifact parity with
  `body add(left, right)` and M133 self-contained
  `call<primitive=add>(left, right)`, unsupported primitive-call diagnostics
  for `emit_return(call<primitive=sub>(left, right));` and
  `emit_return(call<primitive=@self[...]>(...));`, direct selected M133 `@self`
  primitive-call diagnostic coverage, raw-plus-call payload diagnostics,
  malformed/nearby emit-return payloads preserving existing diagnostics, and
  existing M126-M133 artifact-byte stability.

Out of scope:

General directive-payload segmentation; recursive payload parsing; broad
`emit_return` expression lowering; general primitive resolution; dependency
closure; `@self` interpretation; type-argument parsing; call argument
splitting; expression parsing; helper/operator lowering; assignment lowering;
array access lowering; generation/backend query evaluation; new backend call
rendering; source repair; complete TSIL grammar; runtime `tsldata` semantic
lookup; `frozen` or `tslgenold` runtime dependency; registries; dispatchers;
hidden backfeeds; fixpoint mechanisms; or new lowering IR
category/request/result/worklist families.

Expected outputs:

- `emit_return(...)` can retain opaque payload text and expose ordered payload
  tokens for exact lowerable islands, first for M132 primitive-call islands.
- A selected `emit_return(...)` body whose payload-token stream consists only
  of the M133 exact `call<primitive=add>(left, right)` token lowers through the
  same typed operation path as `body add(left, right)` and M133's exact
  self-contained add call.
- Recognized but unsupported primitive-call payload tokens produce the same
  precise primitive-call diagnostic boundary as M133 instead of disappearing
  inside an opaque return-expression string.
- Raw-only or mixed raw payloads preserve the existing opaque return-expression
  diagnostic boundary unless a later milestone explicitly selects their
  payload form.
- Existing M126-M133 behavior, diagnostics, source locations, and artifact
  bytes remain stable except for the deliberately added directive payload-token
  boundary, exact composed add-call return lowering, and narrowed diagnostics
  for recognized unsupported primitive-call payload tokens.
- No general `emit_return` expression parser, recursive directive-payload
  parser, primitive dependency closure, or backend call rendering is
  introduced.

Execution notes:

- `LowerableDirective` now preserves the existing opaque `arguments` tuple and
  adds `payload_tokens` for source-owned directive payload tokens.
- Catalog promotion currently populates payload tokens only for
  `emit_return(...)` directives from parser-recognized quoted TSIL payloads.
  Other directive payloads remain opaque.
- M134 reuses the M132 primitive-call island classifier over the
  `emit_return` payload text. Selector and call payload strings remain opaque.
- Lowering composes with M133 only when the selected `emit_return` payload
  stream contains exactly one exact add-call token. It does not match the
  combined source string directly.
- Unsupported recognized primitive-call payload tokens produce
  `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`; raw-only or mixed raw payloads keep
  `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION`.
- Review returned `Accept` from architecture, boundary, documentation, and
  validation auditors. There were no blocking findings or recorded follow-ups.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `149 passed in 7.78s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 135: Structured Primitive Call Representation Boundary Slice

Status:

Accepted. This superseded the previously planned raw
`emit_return(<selected-parameter>)` idea, because resolving raw payload
identifiers would push the generator back toward target-language expression
interpretation. M135 instead strengthens the representation of the explicit
TSIL `call<primitive=...>` keyword.

Goal:

Recognized TSIL primitive-call islands should expose a typed source-owned
representation of the `primitive=` selector. The selector target may be the
`@self` keyword, meaning the currently selected primitive, or an arbitrary
named primitive reference such as `add`, `binary_and`, `reinterpret`, or
`set_zero`.

```text
call<primitive=@self>(...)
call<primitive=@self[...]>(...)
call<primitive=@self attrs[...]>(...)
call<primitive=@self[...] attrs[...]>(...)
call<primitive=<primitive-name>>(...)
call<primitive=<primitive-name>[...]>(...)
call<primitive=<primitive-name> attrs[...]>(...)
call<primitive=<primitive-name>[...] attrs[...]>(...)
```

`<primitive-name>` is documentation notation for an arbitrary primitive name
token, not a literal source spelling. Bracket specialization payloads,
`attrs[...]` payloads, and call argument payloads remain opaque source text.
This milestone represents the selector; it does not resolve or execute the
call.

Scope:

- Keep parser syntax, M129/M130 directive classification, M132 call-island
  recognition, M133 exact add-call lowering, and M134 emit-return payload-token
  behavior stable unless a focused test exposes a defect.
- Add the smallest typed representation for a recognized primitive-call
  selector, distinguishing self target, named target, optional specialization
  payload, optional attrs payload, original selector source text, and source
  location.
- Preserve the existing opaque call argument payload exactly. Do not split
  arguments, parse nested calls, parse expressions, or evaluate attributes.
- Populate the structured selector for both standalone M132 call tokens and
  M134 `emit_return(...)` payload call tokens.
- Preserve M133/M134 exact add-call lowering behavior. If the existing exact
  add lowering consumes the old opaque selector arguments, adapt it to use or
  coexist with the typed selector without broadening semantics.
- Preserve unsupported-call diagnostics for all recognized calls that are not
  the accepted exact add-call lowering case. Diagnostics may include the
  structured target kind/name as context, but must not resolve the call.
- Add tests for structured representation of `@self`, `@self[...]`,
  named primitive references, named references with specialization brackets,
  named references with `attrs[...]`, named references with both
  specialization and attrs, and the same representation inside an
  `emit_return(call<primitive=...>(...));` payload token.
- Add negative tests for malformed selector brackets or malformed
  `attrs[...]` forms proving they remain unsupported/malformed boundaries
  rather than source repair.

Out of scope:

Raw `emit_return(left)` or `emit_return(result)` name resolution; primitive
dependency closure; resolving named primitive references against the catalog;
expanding `@self`; interpreting specialization payloads; interpreting
`attrs[...]`; splitting call arguments; recursive primitive-call trees;
expression parsing; helper/operator lowering; assignment lowering; array
access lowering; generation/backend query evaluation; backend call rendering;
source repair; complete TSIL grammar; runtime `tsldata` semantic lookup;
`frozen` or `tslgenold` runtime dependency; registries; dispatchers; hidden
backfeeds; fixpoint mechanisms; or new request/result/worklist families.

Expected outputs:

- Recognized primitive-call tokens carry typed selector structure for self
  references, named primitive references, specialization payloads, and attrs
  payloads while preserving original source text.
- Call arguments remain opaque source text.
- Existing M133/M134 exact add-call lowering and unsupported-call diagnostics
  remain stable.
- Existing M126-M134 behavior, diagnostics, source locations, and artifact
  bytes remain stable except for the deliberately added selector
  representation.
- No raw return-payload identifier resolution, primitive dependency closure,
  `@self` expansion, argument splitting, expression parser, or backend call
  rendering is introduced.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Execution notes:

- `LowerableDirective` call tokens now preserve the existing opaque
  `(primitive, selector, payload)` arguments and also carry a structured
  `PrimitiveCall` value for recognized TSIL primitive calls.
- The structured selector distinguishes `@self` from named primitive
  references and preserves optional specialization and `attrs[...]` payloads
  as opaque source text. The call argument payload remains opaque.
- Structured selector values are populated for standalone M132 call tokens and
  for M134 `emit_return(...)` payload call tokens.
- M133/M134 exact `call<primitive=add>(left, right)` lowering now uses or
  coexists with the structured selector while preserving the accepted exact
  add-call boundary.
- Malformed selector brackets and malformed `attrs[...]` forms remain raw
  unsupported source text rather than being repaired.
- Architecture review initially returned `Accept With Follow-Ups` requesting
  explicit tests for `@self attrs[...]` and `@self[...] attrs[...]`; that
  follow-up was addressed during execution. Boundary and documentation audits
  returned `Accept`. Validation initially requested cache cleanup and then
  returned `Accept` on focused re-review.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `152 passed in 8.79s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 136: Structured Primitive Call Argument List Boundary Slice

Status:

Accepted. This is still representation-first lowering work over explicit TSIL
`call<primitive=...>(...)` constructs, not primitive resolution or expression
interpretation.

Goal:

Recognized primitive-call tokens should expose an ordered source-owned call
argument list in addition to the opaque payload string accepted by M132-M135.
Each argument remains raw source text with a source location; the argument list
only records the top-level comma structure of the TSIL call payload.

Scope:

- Preserve the existing opaque `PrimitiveCall.payload` string and add the
  smallest structured argument-list representation needed for later lowering.
- Split only the top-level comma-separated payload of recognized
  `call<primitive=...>(...)` tokens, respecting nested parentheses and square
  brackets so nested TSIL calls or helper forms are not split internally.
- Represent zero-argument calls as an empty argument tuple.
- Populate argument lists for standalone M132 call tokens and M134
  `emit_return(...)` payload call tokens.
- Preserve M133/M134 exact add-call lowering and adapt its exact check to use
  or coexist with the structured argument list without broadening semantics.
- Add focused tests for zero arguments, two raw parameter-like arguments,
  nested call arguments, helper/cast-like nested parentheses, source
  locations, malformed argument delimiters, preserved unsupported-call
  diagnostics, and existing M126-M135 artifact-byte stability.

Out of scope:

Primitive dependency closure; resolving named primitive references against the
catalog; expanding `@self`; interpreting selector specialization or
`attrs[...]`; resolving argument identifiers; parsing array access,
assignment, operators, helpers, casts, or nested call semantics; recursively
lowering argument expressions; backend call rendering; source repair; complete
TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or `tslgenold`
runtime dependency; registries; dispatchers; hidden backfeeds; fixpoint
mechanisms; or new request/result/worklist families.

Expected outputs:

- Recognized primitive-call tokens preserve the original opaque payload and
  also expose deterministic source-owned argument payload values.
- Existing exact add-call lowering, unsupported-call diagnostics, source
  locations, and artifact bytes remain stable.
- No primitive resolution, argument expression parsing, dependency closure, or
  backend call rendering is introduced.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Execution notes:

- `PrimitiveCall` now preserves the accepted opaque `payload` string and also
  carries ordered `PrimitiveCallArgument` values with raw text and source
  locations.
- The argument splitter recognizes only top-level commas in recognized
  primitive-call payloads and respects nested parentheses and square brackets.
- Zero-argument calls produce an empty argument tuple.
- Argument lists are populated for standalone M132 call tokens and for M134
  `emit_return(...)` payload call tokens.
- M133/M134 exact `call<primitive=add>(left, right)` lowering now checks both
  the exact opaque payload and exact structured argument texts, preserving the
  strict exact boundary.
- Malformed argument delimiters remain raw unsupported source text rather than
  being repaired.
- Architecture, boundary, documentation, and validation audits all returned
  `Accept`; there were no blocking findings or recorded follow-ups.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `157 passed in 8.47s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 137: Exact Primitive Call Dependency Diagnostic Boundary Slice

Status:

Accepted. M137 was implemented after accepted M136. This is a lowering
diagnostic boundary over the M135/M136 structured primitive-call
representation. It still does not resolve or render primitive calls.

Goal:

Selected implementation bodies containing recognized primitive-call tokens
that are not the accepted exact add-call case should report why the call is
unresolved in terms of the structured call data. The diagnostic should name
the target kind (`@self` or named primitive), selector source text, optional
specialization and attrs payloads, and raw argument count. It should make the
next required semantic capability explicit: primitive-call dependency
resolution is not implemented yet.

Scope:

- Preserve M133/M134 exact `call<primitive=add>(left, right)` lowering and all
  M132-M136 body-token representation behavior.
- Replace or refine the generic unsupported primitive-call message with a
  stable structured diagnostic message for unresolved primitive calls.
- Keep the diagnostic code `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` unless a
  focused test demonstrates a need for a narrower code.
- Report structured context for standalone call tokens and for M134
  `emit_return(...)` payload call tokens.
- Add focused tests for named primitive calls, `@self`, specialization,
  `attrs[...]`, zero arguments, nested raw arguments, and exact source
  locations.
- Add tests proving raw `emit_return(left)`, malformed call selectors,
  malformed call arguments, and raw-plus-call payloads preserve existing
  diagnostics.

Out of scope:

Primitive dependency closure; resolving named primitive references against the
catalog; expanding `@self`; interpreting selector specialization or
`attrs[...]`; resolving argument identifiers; recursively lowering argument
expressions; backend call rendering; source repair; complete TSIL grammar;
runtime `tsldata` semantic lookup; `frozen` or `tslgenold` runtime dependency;
registries; dispatchers; hidden backfeeds; fixpoint mechanisms; or new
request/result/worklist families.

Expected outputs:

- Unsupported recognized primitive calls fail with a more actionable
  structured diagnostic grounded in the M135/M136 call representation.
- Accepted exact add-call lowering, source locations, and artifact bytes remain
  stable.
- The next semantic step, dependency resolution, is visible as an explicit
  unsupported boundary rather than an implicit opaque-string failure.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Execution notes:

- Unsupported recognized primitive calls now report structured diagnostic
  context from the existing `PrimitiveCall` value when available.
- The diagnostic context names named primitive versus `@self` target kind,
  named target where applicable, selector source text, optional opaque
  specialization and attrs payloads, raw argument count, raw argument payload
  texts, the opaque original payload, and the explicit missing capability:
  primitive-call dependency resolution is not implemented yet.
- The same context is used for standalone primitive-call body tokens and for
  `emit_return(...)` payload primitive-call tokens.
- Hand-constructed directive values that lack structured `PrimitiveCall` data
  keep the legacy opaque selector/payload fallback context, now with the same
  missing-capability statement.
- M133/M134 exact `call<primitive=add>(left, right)` lowering and generated
  artifact bytes remain stable.
- Raw `emit_return(left)`, raw-plus-call payloads, malformed call selectors,
  malformed call arguments, non-call raw bodies, and non-call directives remain
  at their existing diagnostic boundaries.
- Architecture, boundary, and validation audits returned `Accept`.
  Documentation audit returned `Accept With Follow-Ups`; the recorded
  follow-up is to update the older simplified implementation-body domain-model
  sketch so it shows the accepted M134-M136 `primitive_call` and
  `payload_tokens` fields.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `164 passed in 12.06s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 138: Primitive Call Target Reference Diagnostic Boundary Slice

Status:

Accepted. The M138 execution-review loop returned `Accept With Follow-Ups`,
and a focused follow-up audit returned `Accept` after adding the missing
separate specialization-only and attrs-only tests. This is a lowering
diagnostic boundary over recognized TSIL
`call<primitive=...>(...)` tokens. It should identify the source-declared base
call target against the current catalog when possible and classify
specialization / `attrs[...]` as unresolved target-reference dimensions, but
it still must not select or lower dependency implementations.

Goal:

Move one step beyond M137's generic "dependency resolution is not implemented"
diagnostic by checking only the primitive-call target reference boundary:

- `call<primitive=@self>(...)` identifies the currently selected primitive as
  the base dependency target;
- `call<primitive=NAME>(...)` checks whether `NAME` exists as a primitive in
  the catalog;
- `call<primitive=@self[...]>(...)`, `call<primitive=NAME[...]>(...)`,
  `call<primitive=@self attrs[...]>(...)`,
  `call<primitive=NAME attrs[...]>(...)`, and combined
  specialization-plus-attrs forms classify the base target and report that
  specialization-specific and/or attribute-specific target reference
  resolution is not implemented yet;
- missing named base targets receive a precise diagnostic at the call source
  while preserving specialization and attrs as opaque diagnostic context;
- known base targets still stop at a diagnostic boundary that distinguishes
  known base-target identity from unresolved specialization, unresolved attrs,
  and missing dependency implementation selection/lowering.

Scope:

- Preserve M133/M134 exact `call<primitive=add>(left, right)` lowering and all
  M135-M137 structured selector, argument, payload, and diagnostic behavior
  outside the deliberately refined target-reference diagnostic text.
- Use only the already built clean restart catalog and selected implementation
  context. Keep base-target lookup exact by primitive name; do not interpret
  specialization or attrs as successful specialization/attribute resolution.
- Keep selector specialization, attrs payloads, argument payloads, nested call
  payloads, and original payload text opaque, while reporting specialization
  and attrs presence as unresolved target-reference dimensions.
- Add focused tests for known named targets, unknown named targets, `@self`
  base target identity, known named targets with specialization, known named
  targets with `attrs[...]`, known named targets with both specialization and
  `attrs[...]`, unknown named base targets with specialization and/or attrs,
  `@self` with specialization and/or attrs, zero-argument calls, nested raw
  argument payloads, `emit_return(...)` payload calls, source locations, and
  exact add-call artifact stability.
- Preserve raw `emit_return(...)`, malformed call selectors, malformed call
  arguments, raw-plus-call payloads, non-call raw bodies, and non-call
  directives as diagnostic boundaries.
- Resolve the M137 documentation follow-up by updating the older
  implementation-body domain-model sketch to show the accepted
  `primitive_call` and `payload_tokens` fields if the milestone touches that
  area of the docs.

Out of scope:

Primitive dependency closure; selecting dependency implementations; lowering
dependency bodies; rendering backend call text; expanding `@self` beyond base
target identity; interpreting specialization, attrs, arguments, or nested call
semantics; expression parsing; assignment or array-access lowering; source
repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
`tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
fixpoint mechanisms; or new request/result/worklist families.

Expected outputs:

- Unknown named primitive-call base targets fail with a precise
  target-reference diagnostic grounded in source locations.
- Known named primitive-call base targets and `@self` calls remain unsupported
  until a later dependency-selection/lowering slice, but their diagnostics
  clearly distinguish base target identity from unresolved specialization,
  unresolved attrs, and the missing dependency implementation capability.
- Existing exact add-call lowering and artifact bytes remain stable.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Accepted result:

- The normal generator pipeline now passes the already built clean restart
  catalog into lowering so recognized primitive-call diagnostics can classify
  target references against selected implementation context.
- Named call targets use exact primitive-name membership only. Unknown named
  base targets produce `TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET` at the call
  source and include the known primitive names.
- Known named base targets and `@self` targets still stop at
  `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`. Diagnostics distinguish known base
  target identity from unresolved specialization, unresolved attrs, and the
  missing dependency implementation selection/lowering capability.
- Specialization payloads, attrs payloads, raw arguments, nested calls, and
  original payload text remain opaque diagnostic context. No dependency
  implementation is selected, no dependency body is lowered, no dependency
  closure is expanded, and no backend call text is rendered.
- Direct lowerer calls without catalog context preserve the M137 diagnostic
  fallback.
- The older implementation-body domain-model sketch now shows the accepted
  `PrimitiveCall`, `primitive_call`, and `payload_tokens` fields, resolving
  the M137 documentation follow-up.

Review verdicts:

- Architecture reviewer: `Accept`.
- Boundary auditor: `Accept With Follow-Ups`; the noted missing separate
  specialization-only and attrs-only tests were added during the loop.
- Documentation auditor: `Accept With Follow-Ups`; the only noted items were
  the orchestrator-owned roadmap, state, and next-prompt updates.
- Validation auditor: `Accept`.
- Focused follow-up audit after the test additions: `Accept`.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `171 passed in 13.46s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 139: Primitive Declaration Attribute Variant Catalog Slice

Status:

Accepted. The M139 execution-review loop returned `Accept With Follow-Ups`
after one write-capable executor and read-only architecture, boundary,
documentation, and validation audits. This is a catalog-first prerequisite for
correct future primitive-call selector matching. Real `.tsl` primitive
declarations carry semantic selector dimensions in their declaration headers,
including attributes and wildcard attributes such as `aligned=*` and
`packed=*`. The catalog now represents source declarations and deterministic
concrete variants before lowering tries to match `call<primitive=...>`
selectors against candidates.

Goal:

Store primitive definitions as source-authored declarations and deterministic
concrete variants:

- parse/store primitive declaration attributes from headers such as
  `prim<v:=(m,v,v)>[mask=zero] add(mask, left, right):`;
- represent primitive declaration attributes as typed source-owned metadata,
  not as ad hoc raw strings hidden in primitive names;
- expand boolean wildcard declaration attributes before downstream catalog
  matching, so `aligned=*` materializes concrete `aligned=true` and
  `aligned=false` variants;
- expand independent wildcard attributes deterministically, so
  `aligned=*, packed=*` materializes every concrete combination in stable
  order;
- preserve source provenance from every concrete variant back to the original
  source declaration and wildcard source span for diagnostics;
- keep implementation body text irrelevant for this milestone. Implementation
  bodies may still be parsed/preserved as existing body tokens, but body
  contents must not influence declaration-attribute expansion.

Scope:

- Extend the clean restart parser/catalog boundary just enough to admit
  primitive declaration attribute lists in the supported primitive header
  forms.
- Add typed catalog values for primitive declaration attributes and concrete
  primitive variants. Prefer simple, obvious objects over request/result,
  worklist, registry, dispatcher, or fixpoint machinery.
- Treat wildcard attributes as source shorthand only. Wildcards must not
  survive on concrete catalog variants after expansion.
- For this slice, resolve boolean wildcard values for the observed boolean
  attribute dimensions `aligned` and `packed` into `true` and `false`
  variants.
- Preserve non-wildcard declaration attributes such as `mask=zero`,
  `mask=pass_through`, `cast=reinterpret`, `cast=convert`, `direction=up`,
  `direction=down`, `value=zero`, `value=all`, `value=undef`, `op=keep`,
  `op=pack`, `op=expand`, and `arg_count(args)=return_vector_length` as
  concrete source-owned attribute facts where the narrow parser admits them.
- Preserve existing no-attribute fixtures, selected implementation/lowering
  behavior, and M133/M134 exact add-call artifact bytes.
- Add focused tests for no-attribute declarations, literal attributes,
  `aligned=*`, `aligned=*, packed=*`, multiple same-name declarations with
  distinct concrete attributes, variant source provenance, and body-content
  irrelevance.

Out of scope:

Primitive-call candidate lookup; dependency closure; lowering dependency
bodies; rendering backend call text; resolving `call<primitive=...>`
selectors; interpreting selector specialization or selector `attrs[...]`;
resolving argument identifiers; recursively lowering argument expressions;
expression parsing; assignment or array-access lowering; source repair;
complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
`tslgenold` runtime dependency; broad template/signature validation; full
attribute validity checking; extension/type-group expansion; hardware/feature
requirements; registries; dispatchers; hidden backfeeds; fixpoint mechanisms;
or new request/result/worklist families.

Expected outputs:

- Catalog consumers can inspect concrete primitive variants with concrete
  attributes.
- Boolean wildcard declaration attributes no longer survive past catalog
  variant expansion.
- Variant provenance remains tied to the original source declaration.
- Implementation body text has no effect on declaration-attribute expansion.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Accepted result:

- The clean restart parser admits primitive declaration attribute lists for the
  supported tiny source header shapes.
- `ParsedPrimitive` and `Primitive` carry typed source-owned attribute facts.
- Catalog construction materializes concrete primitive variants from
  declaration attributes. Literal attributes remain concrete facts.
- Boolean wildcard declaration attributes are source shorthand only:
  `aligned=*` and `packed=*` expand to deterministic `true` / `false`
  concrete variants. Wildcard values do not survive in `Primitive.attributes`.
- `Primitive.declared_attributes` and `PrimitiveAttribute.declared_value`
  preserve provenance back to the source declaration and wildcard value.
- Same-name primitive declarations with different concrete attributes are
  represented as distinct concrete variants.
- Implementation body text does not participate in declaration-attribute
  expansion.
- No primitive-call candidate lookup, dependency closure, dependency body
  lowering, backend rendering, selector specialization resolution, selector
  `attrs[...]` resolution, runtime `tsldata` shortcut, `frozen` runtime
  dependency, or `tslgenold` runtime dependency was added.

Review verdicts:

- Architecture reviewer: `Accept`.
- Boundary auditor: `Accept With Follow-Ups`; recorded follow-up is that the
  next selector-matching milestone must match only `Primitive.attributes` and
  ignore provenance fields such as `declared_attributes` and
  `declared_value`.
- Documentation auditor: `Accept With Follow-Ups`; the only noted items were
  the orchestrator-owned roadmap, state, and next-prompt updates.
- Validation auditor: `Accept`.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `177 passed in 13.39s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 140: Explicit Target Attribute Variant Selection Boundary Slice

Status:

Accepted. The M140 execution-review loop returned `Accept` after one
write-capable executor, read-only architecture, boundary, documentation, and
validation audits, and one focused documentation revision/re-review. This is a
selection prerequisite for correct lowering and future primitive-call selector
matching. Now that the catalog can contain multiple same-name concrete
primitive variants distinguished by attributes, explicit target selection no
longer treats primitive name alone as sufficient.

Goal:

Select primitive variants by explicit concrete target attributes:

- extend the explicit `Target` selection request with concrete primitive
  attributes while preserving existing no-attribute target construction;
- make empty target attributes match only catalog variants whose
  `Primitive.attributes` are empty;
- make nonempty target attributes match catalog variants by primitive name,
  signature where applicable, and concrete `Primitive.attributes`;
- ignore provenance-only fields such as `Primitive.declared_attributes` and
  `PrimitiveAttribute.declared_value` during matching;
- report precise diagnostics when a primitive name exists but no concrete
  attribute variant matches;
- preserve deterministic selection ordering and existing no-attribute
  generation behavior.

Scope:

- Add small typed selection/target attribute values or reuse the existing
  catalog attribute value type where that remains simple.
- Update `Selector` to match concrete catalog variants by name plus concrete
  attributes before implementation extension/type selection.
- Preserve existing no-attribute targets and generated artifact bytes.
- Add focused tests for no-attribute selection, explicit literal attribute
  selection, wildcard-expanded concrete variants selected by concrete
  attributes, empty-attribute target not matching attr-bearing variants,
  missing-attribute variant diagnostics, and provenance fields being ignored
  for matching.

Out of scope:

Primitive-call candidate lookup; dependency closure; lowering dependency
bodies; rendering backend call text; resolving `call<primitive=...>`
selectors; interpreting selector specialization or selector `attrs[...]`;
resolving argument identifiers; expression parsing; assignment or array-access
lowering; source repair; complete TSIL grammar; runtime `tsldata` semantic
lookup; `frozen` or `tslgenold` runtime dependency; broad template/signature
validation; full attribute validity checking; extension/type-group expansion;
hardware/feature requirements; registries; dispatchers; hidden backfeeds;
fixpoint mechanisms; or new request/result/worklist families.

Expected outputs:

- Target selection is explicit about concrete primitive attributes.
- Same-name catalog variants are not accidentally selected by name alone.
- The selected current primitive identity is ready for a later lowering slice
  to match recognized `call<primitive=... attrs[...]>(...)` selectors against
  concrete catalog variants.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Accepted result:

- `Target` now accepts concrete `TargetAttribute` values while existing
  no-attribute target construction remains valid.
- Empty target attributes match only catalog primitive variants whose concrete
  `Primitive.attributes` are empty.
- Nonempty target attributes match only concrete `Primitive.attributes` by
  key, optional key argument, and value.
- Attribute-variant matching ignores provenance-only fields such as source
  spans, `Primitive.declared_attributes`, and
  `PrimitiveAttribute.declared_value`.
- When a requested primitive name exists but no concrete attribute variant
  matches, selection emits `TSL-SELECT-NO-ATTRIBUTE-VARIANT` with the
  requested attributes and available concrete variants.
- Existing unsupported-backend, unknown-primitive, no-implementation,
  no-attribute generation, and M126-M139 lowering/body-token behavior remain
  stable.
- No primitive-call candidate lookup, dependency closure, dependency body
  lowering, backend call rendering, selector specialization or attrs
  interpretation, expression parsing, runtime `tsldata` shortcut, `frozen`
  runtime dependency, or `tslgenold` runtime dependency was added.

Review verdicts:

- Architecture reviewer: `Accept`.
- Boundary auditor: `Accept`.
- Documentation auditor: initial `Needs Revision` for a domain-model wording
  mismatch; focused documentation re-review returned `Accept`.
- Validation auditor: `Accept`.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `184 passed in 10.09s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 141: Selected Implementation Lowering Context Slice

Status:

Accepted. The M141 execution-review loop returned `Accept` after one
write-capable executor and read-only architecture, boundary, documentation,
and validation audits. This is the context boundary needed before
primitive-call selector matching starts interpreting type-related selector
payloads.

Goal:

Create the small typed lowering context for one selected implementation:

- carry the selected primitive identity, including concrete catalog attributes
  chosen by M140;
- carry selected backend, extension, datatype/base type, signature, parameter
  names, and implementation source provenance;
- represent `Vec` as the current implementation vector keyword derived from
  selected extension plus datatype, not as a primitive specialization or
  catalog attribute;
- keep implementation-body type aliases out of selected-context facts so later
  lowering resolves aliases from source-defined `let<type>(...)` bindings;
- expose enough context for later lowering of `type<backend>(...)` and
  `vector::as_extension(scalar)` without letting renderers or primitive-call
  matching evaluate raw source text.

Scope:

- Add or extend one small context object owned by the lowering/selection
  boundary, using existing selected primitive and target data where possible.
- Preserve existing M126-M140 body-token classification and generated bytes.
- Add tests proving the context distinguishes catalog attributes from
  implementation type aliases and preserves selected extension/datatype facts.

Out of scope:

Primitive-call candidate matching; dependency closure; lowering dependency
bodies; backend call rendering; interpreting call selector attrs; resolving
  source-defined type aliases, `type<backend>(...)`, or
  `vector::as_extension(scalar)` into backend text; expression parsing;
assignment/indexing; source repair; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad IR/worklist machinery.

Expected outputs:

- Later lowering can ask for the current selected implementation context
  without guessing from raw TSIL text.
- Future type-query and call-selector milestones have an explicit source of
  M141 context facts such as current primitive attributes, extension, and
  datatype, plus the M142 selected-body type environment for aliases.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Accepted result:

- Added `SelectedImplementationLoweringContext`, built only from an already
  selected `SelectedImplementation`.
- Preserved selected `Target`, `Primitive`, and `Implementation` object
  identity for diagnostics and traceability.
- Carried selected primitive name, concrete M140 `Primitive.attributes`,
  backend, extension, type tag, signature, template, parameter names,
  primitive source, and implementation source.
- Exposed context construction through `Lowerer.context_for(...)` and threaded
  context into current lowering output creation without changing generated
  C++/Rust bytes.
- Recorded `Vec` as the current selected-context vector keyword.
- Left implementation-body aliases for a later source-defined
  `let<type>(...)` alias binding slice rather than treating alias spellings as
  context facts.
- Kept declaration provenance such as `Primitive.declared_attributes` and
  `PrimitiveAttribute.declared_value` out of the context as separate semantic
  selectors.
- No `Vec`, source-defined type aliases, `type<backend>(...)`, or
  `vector::as_extension(scalar)` backend-text resolution, primitive-call
  selector matching, dependency closure, dependency body lowering, backend
  call rendering, expression parsing, runtime `tsldata` shortcut, `frozen`
  runtime dependency, or `tslgenold` runtime dependency was added.

Review verdicts:

- Architecture reviewer: `Accept`.
- Boundary auditor: `Accept`.
- Documentation auditor: `Accept`.
- Validation auditor: `Accept`.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `189 passed in 8.35s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 142: Exact Type Alias And Backend-Type Query Lowering Slice

Status:

Accepted. The M142 execution-review loop returned `Accept` after one
write-capable executor, one focused revision executor, and read-only
architecture, boundary, documentation, and validation audits plus focused
re-review. This is the narrow type/query lowering prerequisite for
attribute-aware primitive-call selector matching with specializations such as
`[Vec]` or `[type<backend>(vector::as_extension(scalar))]`.

Goal:

Lower exact type-related TSIL islands against the M141 selected implementation
context:

- resolve the `Vec` keyword to the current selected vector type from extension
  plus datatype;
- seed a tiny selected-body type environment with exact context symbols such
  as `Vec` and the current scalar/base type symbol;
- lower exact `let<type>(AliasName, TypeExpr)` directives in body order and
  bind arbitrary alias names to lowered typed type expressions;
- resolve implementation-body aliases such as `MaskVec` and `GenericVec` only
  through prior `let<type>(...)` bindings, never as hardcoded names;
- represent `vector::as_extension(scalar)` as a typed vector-type transform
  request over the current scalar/base type and selected extension context;
- represent `type<backend>(...)` as a backend type-spelling request over an
  already lowered typed semantic type value or prior alias binding;
- emit diagnostics for unsupported or malformed exact type/query islands
  rather than passing raw query text to renderers.

Scope:

- Recognize only exact documented type/query islands already isolated by the
  selected TSIL token boundaries, such as call selector specializations or
  directive payload tokens.
- Treat `MaskVec`, `GenericVec`, and any other alias name as source-defined
  aliases that must come from an earlier exact `let<type>(...)` directive in
  the selected body.
- If the M141 context's recorded unresolved alias names would imply hardcoded
  alias semantics, M142 may narrow or revise that field so alias resolution is
  driven by source-defined `let<type>(...)` bindings instead.
- Keep backend spelling as a typed request/result boundary; do not let backend
  rendering evaluate unresolved source text.
- Add focused positive and negative tests for `Vec`, arbitrary
  `let<type>(...)` alias binding and reference, `type<backend>(...)`, and
  `vector::as_extension(scalar)` in selected contexts.

Out of scope:

Primitive-call candidate matching; dependency closure; lowering dependency
bodies; rendering backend call text; hardcoded `MaskVec` / `GenericVec`
semantics; interpreting selector attrs; broad generation/backend query
grammar; expression parsing; arbitrary raw-line rewriting;
assignment/indexing; general block scoping, alias shadowing, or cross-body
alias lookup; source repair; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; broad IR/worklist machinery.

Expected outputs:

- The lowerer has typed current-context type facts and backend type requests
  for the exact source forms needed by selected primitive-call selectors.
- `Vec` is no longer confused with primitive catalog specialization keys, and
  source alias names such as `MaskVec` or `GenericVec` resolve only through
  `let<type>(...)` bindings.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Accepted result:

- Added typed selected-context type facts for `Vec` and `scalar`.
- Added an ordered selected-body type environment that binds arbitrary source
  alias names from exact `let<type>(AliasName, TypeExpr)` directives.
- Lowered exact `vector::as_extension(scalar)` to a typed vector transform
  fact over the current scalar/base type and selected extension.
- Lowered exact `type<backend>(TypeExpr)` to a typed
  `BackendTypeSpellingRequest` over an already lowered type value.
- Kept alias names source-defined only: `MaskVec`, `GenericVec`, and any
  other alias spelling are not hardcoded semantic aliases.
- Fixed alias visibility so backend type queries resolve only aliases whose
  `let<type>(...)` binding precedes the query in the same selected body.
- Preserved primitive-call selector target resolution, dependency closure,
  dependency body lowering, backend type/call rendering, arbitrary expression
  parsing, runtime `tsldata`, `frozen`, and `tslgenold` as out of scope.

Review verdicts:

- Initial architecture reviewer: `Needs Revision` for alias visibility.
- Initial boundary auditor: `Needs Revision` for alias visibility.
- Initial documentation auditor: `Needs Revision` for stale alias wording.
- Initial validation auditor: `Accept`.
- Focused architecture re-review: `Accept`.
- Focused boundary re-review: `Accept`.
- Focused documentation re-review: `Accept`.
- Focused validation re-review: `Accept`.

Validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `197 passed in 8.48s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed validation
  cache directories; after removing those directories, the final required
  `find tslgen -type d -name __pycache__ -print` returned exit 0 with no
  output.

### Milestone 143: Complete Observed TSIL Type Lowering Model

Status:

Accepted. The M143 execution-review loop returned `Accept With Follow-Ups`
after one write-capable executor, read-only architecture, boundary, evidence,
documentation, and validation audits, one focused documentation/evidence
revision executor, and focused re-review. M143 is the type-system foundation
milestone before primitive-call selector target resolution continues. It
completed observed TSIL type lowering for the current `tsldata/**/*.tsl`
corpus rather than selecting another tiny synthetic type slice.

Goal:

Realize the observed TSIL type language as typed semantic type values and
typed backend type-spelling requests:

- inventory every unique observed `let<type>(...)`,
  `type<generation>(...)`, and `type<backend>(...)` form across
  `tsldata/**/*.tsl` and record its category;
- lower context-given generation types such as `base::in`,
  `vector::register`, `vector::mask`, `vector::imask`,
  `vector::mask_underlying_t`, and `vector::offset_base`;
- lower type transforms such as `base::signed_of(...)`,
  `base::unsigned_of(...)`, `base::generic(...)`,
  `register::generic(...)`, `vector::transform(...)`,
  `vector::transform_extension(...)`, and `vector::as_extension(...)`;
- lower independent backend/scalar type identities such as `size_t`,
  `intrin::vector::imask`, and `scalar::ui8` / `scalar::ui16` /
  `scalar::ui32` / `scalar::ui64` / signed counterparts observed in the
  corpus;
- lower ordered source-defined aliases from `let<type>(AliasName, TypeExpr)`
  through the same semantic type model;
- keep `type<generation>(...)` as semantic type identity lowering and
  `type<backend>(...)` as backend type-spelling requests over already lowered
  semantic type values;
- use `frozen/` only as evidence for unclear observed forms such as
  `register::generic(...)`, never as a runtime dependency.

Scope:

- Treat the current `tsldata/**/*.tsl` type-query corpus as ground truth for
  supported type forms.
- Preserve source text as provenance/diagnostic context only; downstream
  matching/rendering must consume typed semantic type values or typed backend
  type requests.
- Preserve M142 alias ordering: aliases are visible only after their
  `let<type>(...)` binding in the same selected body.
- Add or update a documented type-query inventory under `docs/redesign/` with
  counts, unique forms, categories, and any open questions.
- Add tests for each observed type category, including nested forms such as
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`,
  `type<generation>(register::generic(OutVec))`,
  `type<generation>(vector::transform_extension(ToBase))`,
  `type<backend>(vector::as_extension(generic))`, and source aliases that
  compose those values.

Out of scope:

Primitive-call selector target resolution; dependency closure; selecting or
lowering dependency implementation bodies; recursive call argument lowering;
backend call rendering; backend type text rendering; general value query
lowering beyond the exact observed type predicate
`select(value<generation>(type::is_same(...)), ...)` supported as part of type
lowering; non-type expression parsing; assignment/indexing; source repair;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; registries,
dispatchers, fixpoint mechanisms, or broad request/result/worklist families.

Expected outputs:

- The lowerer has a coherent semantic type model for all observed TSIL type
  forms needed by current `.tsl` data.
- Later primitive-call selector resolution can compare fully lowered semantic
  type identities instead of reparsing raw specialization strings.
- Backend rendering still happens later from typed backend type-spelling
  requests, not from raw `type<backend>(...)` text.

Executor pass result:

- Added `docs/redesign/tsil-type-query-inventory.md` with counts, unique
  forms, categories, and representative source locations for every observed
  `let<type>(...)`, `type<generation>(...)`, and `type<backend>(...)` form in
  the current corpus.
- Extended the type model with typed semantic values for current context
  vector/scalar facts, independent scalar/size/intrinsic identities,
  specialization type symbols, context vector-member projections, base
  transforms, generic-register projections, vector transforms,
  `vector::as_extension(...)`, nested backend type references, and the
  observed type `select(...)` form.
- Added `lower_generation_type_query(...)` and broadened
  `lower_type_expression(...)` / `lower_backend_type_query(...)` so
  `type<generation>(...)` produces semantic type identity values and
  `type<backend>(...)` produces `BackendTypeSpellingRequest` values over
  semantic type values.
- Preserved M142 ordered alias behavior: aliases are arbitrary source names
  and are visible only after their `let<type>(...)` binding in the same
  selected body.
- Preserved backend type rendering, primitive-call selector target
  resolution, dependency closure, dependency body lowering, recursive call
  argument lowering, broad non-type expression parsing, runtime `tsldata`,
  runtime `frozen`, and runtime `tslgenold` as out of scope.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Review verdicts:

- Architecture reviewer: `Accept With Follow-Ups`.
- Boundary auditor: `Accept With Follow-Ups`.
- Evidence auditor: initially `Needs Revision` for nested
  `type<generation>(...)` count underreporting.
- Documentation auditor: initially `Needs Revision` for stale value-query
  out-of-scope wording.
- Validation auditor: `Accept With Follow-Ups`.
- Focused re-review after documentation/evidence revision: `Accept`.

Validation result:

- Executor `git diff --check`: exit 0, no output.
- Executor `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, no output.
- Executor `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py`:
  exit 0, `203 passed in 21.21s`.
- Executor initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final cache check returned exit 0 with no output.
- Focused documentation/evidence revision `git diff --check`: exit 0, no
  output.
- Focused re-review `git diff --check`: exit 0, no output.

Recorded follow-ups:

- Before primitive-call selector matching depends on `vector::as_extension`
  values, split extension operands into typed selector/type operands or
  explicitly document the string contract.
- Add focused negative coverage for malformed `type<generation>(...)`, wrong
  type-transform arity, unsupported type-call names, and bad nested predicate
  forms.
- Document or narrow the intentionally broader scalar/extension recognizers
  before treating them as a stable contract beyond the observed corpus.

### Milestone 143.1: Extension Catalog And Register/Mask Type Facts Boundary

Status:

Accepted. The M143.1 execution-review loop returned `Accept` after one
write-capable executor, read-only architecture, boundary, evidence,
documentation, and validation audits, one focused evidence revision, and
focused re-review. M143.1 made `tsldata/extensions/extension.tsl` a typed
source of extension facts before later lowering or selector matching relies on
extension/type values.

Goal:

Parse and promote extension metadata into a typed extension catalog, including
backend-aware vector register facts and separate mask/integral-mask policies:

- existing extension metadata such as identity, inheritance, vector size,
  backend support, flags, runtime-lane behavior, test metadata, signature
  support, and filters;
- x86 native register families for `sse`, `avx2`, and `avx512`, keyed by
  integer/f32/f64 type selectors and backend spellings;
- inherited register facts for `sse_vl` and `avx2_vl`;
- NEON concrete per-type register facts;
- SVE scalable concrete C++ register facts and native predicate mask facts;
- scalar base-type register policy;
- generic fixed-array register policy with a compile-time lane-count
  parameter, not runtime Rust vectors;
- lane-bitmask and native-predicate mask policies, with integral-mask policy
  represented separately from vector mask policy.

Scope:

- Update `tsldata/extensions/extension.tsl` with the accepted register and mask
  policy source-data shape.
- Add typed domain/catalog ownership for extension facts.
- Resolve type-tag or type-group keyed register entries deterministically where
  the necessary type-group facts are available.
- Preserve source locations and diagnostics for malformed policy data.
- Keep backend-specific register spellings as catalog facts only; do not render
  operation bodies or backend type text in this slice.

Out of scope:

Primitive-call selector payload lowering; primitive-call target matching;
dependency closure; backend operation rendering; backend type rendering from
the new facts; generated C++/Rust library layout changes; host CPU probing;
automatic target discovery; broad TSIL parsing; runtime dependency on
`frozen` or `tslgenold`; registries, dispatchers, fixpoint machinery, or broad
worklist families.

Expected outputs:

- The clean catalog contains typed extension metadata and typed register/mask
  type facts sourced from `tsldata/extensions/extension.tsl`.
- Generic register policy is represented as compile-time fixed arrays with a
  lane-count parameter, keeping Rust away from runtime-growing `Vec<T>` for
  generic registers.
- M144 can later consume extension/type facts without hardwiring extension
  tables in selector or lowering code.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py
find tslgen -type d -name __pycache__ -print
```

The accepted validation result was:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py`:
  exit 0, `214 passed in 10.83s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.

### Milestone 144: Typed Primitive-Call Selector Payload Lowering Boundary

Status:

Accepted. The M144 execution-review loop returned `Accept` after one
write-capable executor, read-only architecture, boundary, evidence,
documentation, and validation audits, one focused selector-attrs revision, and
focused architecture, boundary, and evidence re-reviews. M144 uses the M143
type model and the M143.1 extension catalog boundary to stop treating
recognized primitive-call selector specializations and `attrs[...]` payloads
as opaque strings, while still stopping before primitive-call target
selection, dependency closure, dependency-body lowering, or backend call
rendering.

Goal:

Lower the already recognized M135/M136 `call<primitive=...>(...)` selector
payload data into typed selector payload values:

- preserve the existing structured base target distinction between `@self`
  and named primitive references;
- split optional specialization payloads such as `[Vec]`,
  `[type<backend>(vector::as_extension(scalar))]`, `[ChunkVec, avx2, index]`,
  and `[type<backend>(vector::as_extension(scalar)), PreserveSign]` by
  top-level commas while respecting nested parentheses and brackets;
- lower type-valued specialization entries through the M143 selected type
  environment, including source-defined aliases visible before the call;
- treat `Vec` as the current selected vector value: exactly the selected
  implementation extension plus current type tag, with the extension identity
  resolved from the M143.1 extension catalog. Prefer refining/renaming the
  existing `LoweredCurrentVectorType` concept into one `CurrentVector` value
  with domain-typed `ExtensionName` and `TypeTag` fields. Do not add a
  parallel selector-vector class for the same `extension + type_tag` concept;
  source-defined aliases preserve that same value;
- preserve explicitly non-type selector entries as typed selector symbols or
  literals with source/provenance, not as semantic matches;
- parse `attrs[...]` payloads into typed concrete selector attributes using
  the same key, optional key-argument, and value semantics as catalog/target
  attributes;
- add diagnostics for malformed specialization or attrs payloads and for
  failed type-valued selector lowering.

Scope:

- Use only already selected implementations and already recognized
  `PrimitiveCall` tokens.
- Keep raw selector text only as provenance/diagnostic context.
- Keep M143 type values backend-neutral; backend type text remains unrendered.
- Keep the implementation deliberately small: no general type system, backend
  spelling renderer, expression AST, resolver registry, dispatcher, worklist,
  dependency solver, or vector-type hierarchy.
- Address the M143 extension-operand follow-up by introducing a typed
  extension/specialization operand for `Vec`, source-defined vector value
  aliases, `vector::as_extension(...)`, and selector entries. Unknown
  extension operands in type-valued selector expressions must be diagnostics.
- Add focused negative tests for the M143 malformed/wrong-arity type-query
  paths that selector lowering now relies on.

Out of scope:

Primitive-call target candidate matching; selecting dependency
implementations; dependency closure; dependency-body lowering; recursive call
argument lowering; backend call rendering; backend type text rendering;
semantic interpretation of non-type selector symbols such as `shift`,
`PreserveSign`, `sse`, or `index`; broad TSIL expression parsing;
assignment/indexing lowering; source repair; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, fixpoint mechanisms, or
broad worklist machinery.

Expected outputs:

- The lowerer can expose typed selector payload values for recognized
  primitive calls without resolving the target.
- Later primitive-call selector matching can consume typed specialization
  type values and typed selector attributes instead of reparsing selector
  strings.
- Existing M126-M143 generated artifacts and unsupported-call diagnostics
  remain stable unless deliberately narrowed by the typed selector diagnostics.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py
find tslgen -type d -name __pycache__ -print
```

The accepted validation result after the focused revision was:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py`:
  exit 0, `227 passed in 11.52s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

### Milestone 145: Primitive-Call Target Candidate Matching Boundary

Status:

Accepted. The M145 execution-review loop returned `Accept` after one
write-capable executor and read-only architecture, boundary, evidence,
documentation, and validation audits. M145 consumes typed
`PrimitiveCallSelectorPayload` values and selected implementation context to
identify the exact candidate primitive implementation for supported
primitive-call selectors. It remains a matching boundary only; it does not
lower call arguments, recursively lower nested calls, lower dependency bodies,
select dependency closure, or render backend call text.

Goal:

Produce a typed primitive-call target candidate match from the M144 selector
payload:

- preserve `@self` as the current primitive name and named selectors as the
  referenced primitive name;
- treat absent specialization as the current selected vector
  `(extension, type_tag)` for observed current-context calls such as
  `call<primitive=add>(left, right)`;
- accept exact vector-valued specializations that already lower to a concrete
  extension and type tag without backend rendering, including `CurrentVector`,
  aliases that preserve that value, and backend-type references only by
  inspecting their already-lowered underlying type value;
- match concrete selector attrs against catalog primitive attribute variants
  using key, optional key-argument, and value semantics;
- return explicit diagnostics for unknown primitive names, missing attribute
  variants, missing implementation for the requested extension/type, and
  unsupported selector dimensions or non-concrete vector specializations.

Scope:

- Use only selected context, the catalog, and an M144
  `PrimitiveCallSelectorPayload`.
- Reuse the existing catalog/selection attribute matching semantics where
  practical instead of creating a second ad hoc attribute matcher.
- Keep raw selector text as provenance only.
- Add focused tests for `@self[Vec]`, named `sub[Vec]`, naked named
  current-context calls such as `sub`, attrs-only calls such as
  `sub attrs[mask=zero]`, specialization-plus-attrs calls such as
  `load[Vec] attrs[aligned=false]`, and negative diagnostics.

Out of scope:

Dependency closure; dependency-body lowering; recursive call argument
lowering; matching nested calls by payload arguments; backend call rendering;
backend type text rendering; interpretation of non-type selector symbols such
as `shift`, `PreserveSign`, `index`, or numeric selector dimensions; broad
TSIL expression parsing; assignment/indexing lowering; source repair; runtime
`tsldata`, `frozen`, or `tslgenold` dependencies; registries, dispatchers,
fixpoint mechanisms, or broad worklist machinery.

Expected outputs:

- A typed match/result value can represent the target primitive, selected
  primitive variant, selected implementation, source/provenance, and
  diagnostics for unsupported or missing matches.
- Later primitive-call lowering can consume a matched candidate without
  reparsing selector strings or reimplementing catalog attribute matching.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py`:
  exit 0, `239 passed in 9.81s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

### Milestone 146: Primitive-Call Argument Binding Boundary

Status:

Accepted. The M146 execution-review loop returned `Accept With Follow-Ups`
after one write-capable executor and read-only architecture, boundary,
evidence, documentation, and validation audits. M146 consumes an already
recognized primitive-call token, the M144 typed selector payload, and the M145
target match to bind ordered raw source arguments positionally to the matched
primitive implementation's formal parameters.

Goal:

Produce a small typed primitive-call reference/binding result that records:

- the M145 target match;
- the matched primitive's formal parameters in deterministic order;
- the corresponding raw source argument text and source provenance from the
  recognized `PrimitiveCall` token;
- explicit diagnostics when the source argument count does not match the
  matched primitive's formal parameter count.

Scope:

- Use only the recognized primitive-call token, M144 selector payload, M145
  target match, selected implementation context, and catalog facts already
  needed by the M145 matcher.
- Preserve raw argument text as source truth.
- Bind arguments positionally; do not infer names or semantics.
- Prove nested call-looking argument text stays raw when the arity is valid.
- Add focused positives for matched `@self[Vec]`, named `sub[Vec]`, naked
  current-context named calls, and attrs/specialization cases already matched
  by M145.
- Add focused negatives for too few and too many arguments.

Out of scope:

Argument expression parsing; recursive nested-call lowering; identifier
resolution; array/index/operator/helper/cast semantics; dependency closure;
dependency-body lowering; backend call rendering; backend type text rendering;
source repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
registries, dispatchers, fixpoint mechanisms, or broad worklist machinery.

Expected outputs:

- A typed argument-binding result can be consumed later by dependency-call
  planning without reparsing selector strings or argument text.
- Arity diagnostics point at the primitive-call source and name the expected
  and actual argument counts.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py`:
  exit 0, `248 passed in 9.82s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

Follow-up:

- Before broader primitive-call lowering depends on
  `Lowerer.lower_primitive_call_argument_bindings`, either remove the
  redundant public `selected`, `selector_payload`, and `catalog` parameters or
  validate their relationship to the supplied target match.

### Milestone 147: Primitive-Call Reference Inventory Boundary

Status:

Accepted. The M147 execution-review loop returned `Accept` after one
write-capable executor and read-only architecture, boundary, evidence,
documentation, and validation audits. M147 walks a selected implementation
body in source order and composes the accepted M144 selector-payload, M145
target-match, and M146 argument-binding boundaries into a typed inventory of
already recognized primitive-call references.

Goal:

Produce a small typed primitive-call reference inventory for one selected
implementation:

- collect recognized `PrimitiveCall` tokens in deterministic source order from
  selected body tokens and already recognized directive payload tokens;
- lower each call through M144 selector-payload lowering, M145 target
  matching, and M146 argument binding;
- accumulate successful `PrimitiveCallReference` values;
- accumulate explicit diagnostics from the composed boundaries without
  silently dropping later recognized calls.

Scope:

- Use only selected implementation context, the selected implementation body,
  catalog facts, M144 selector-payload lowering, M145 target matching, and
  M146 argument binding.
- Preserve raw argument text and call provenance from the existing
  `PrimitiveCall` objects.
- Keep inventory ordering deterministic by source/body-token order.
- Add focused tests for one standalone primitive-call token, one
  `emit_return(...)` payload primitive-call token, multiple calls in source
  order, and mixed success/diagnostic cases.

Out of scope:

Dependency closure; dependency scheduling; selecting transitive dependency
sets; lowering dependency bodies; recursively lowering nested calls inside
arguments; parsing raw argument expressions; rendering backend call text;
rendering backend type text; replacing existing scalar operation lowering;
source repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
registries, dispatchers, dependency graphs, fixpoint mechanisms, or broad
worklist machinery.

Expected outputs:

- Later dependency planning can consume a source-ordered inventory of typed
  primitive-call references without scanning raw body text again.
- Unsupported selectors, missing targets, and arity mismatches remain
  diagnostics at the call sites that produced them.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py`:
  exit 0, `257 passed in 11.45s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

### Milestone 148: Primitive-Call Dependency Closure Boundary

Status:

Accepted. The M148 execution-review loop returned `Accept` after one
write-capable executor and read-only architecture, boundary, evidence,
documentation, and validation audits. M148 computes the small dependency
closure over selected implementations by repeatedly applying the accepted M147
primitive-call reference inventory to a root selected implementation and any
newly discovered target implementations.

Goal:

Produce a deterministic primitive-call dependency closure for one root
selected implementation:

- include the root selected implementation;
- discover direct dependencies from M147 `PrimitiveCallReference` values;
- recursively inspect newly discovered selected implementations with M147;
- de-duplicate already seen selected implementation identities;
- preserve first-discovery order for selected implementations and references;
- accumulate diagnostics from each M147 inventory.

Scope:

- Use only selected implementation facts, catalog facts, and M147 reference
  inventories.
- Treat `PrimitiveCallReference.target_match.selected` as the dependency
  target selected implementation.
- Handle self-recursion and cycles by deterministic de-duplication, not by a
  public graph or scheduler abstraction.
- Continue collecting successful references and later dependencies when one
  selected implementation inventory reports diagnostics.
- Add focused tests for one-hop dependency closure, transitive closure, shared
  dependency de-duplication, self/cycle no-infinite-recursion behavior, and
  diagnostic accumulation.

Out of scope:

Dependency scheduling; topological sorting for rendering; lowering dependency
bodies into renderable code; recursively lowering nested call-looking argument
text; parsing raw argument expressions; rendering backend call text; rendering
backend type text; replacing existing scalar operation lowering; source
repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies; public
dependency graphs, schedulers, registries, dispatchers, fixpoint mechanisms,
or broad worklist machinery.

Expected outputs:

- Later generation planning can ask which selected implementations and
  primitive-call references are required by a root selected implementation.
- The closure remains a compact typed result, not a scheduler or renderer.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py`:
  exit 0, `264 passed in 11.89s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

### Milestone 149: Primitive-Call Closure Function Lowering Package Boundary

Status:

Accepted. The M149 execution-review loop returned `Accept With Follow-Ups`
after one write-capable executor and read-only architecture, boundary,
evidence, documentation, and validation audits. M149 composes the accepted
M148 dependency closure with the existing selected-function lowering for the
selected implementations in that closure. It produces one compact typed
package containing the closure, lowered functions that the existing tiny
lowerer can already produce, and accumulated diagnostics from both closure
discovery and selected-function lowering.

Goal:

Produce a deterministic primitive-call closure lowering package for one root
selected implementation:

- compute the M148 dependency closure;
- lower the selected implementations in closure selected order with the
  existing selected-function lowerer;
- include successfully lowered functions in deterministic closure order;
- accumulate closure diagnostics and function-lowering diagnostics;
- preserve the closure references and selected implementation set for later
  planning.

Scope:

- Use only M148 closure facts, the existing `Lowerer.lower(...)` /
  `lower_all(...)` selected-function lowering behavior, and catalog facts
  already accepted by those boundaries.
- Keep the result a compact package/stage-envelope value, not a graph,
  scheduler, renderer, dispatcher, registry, or worklist family.
- Add focused tests for a root plus one lowerable dependency, unsupported
  dependency body diagnostics, combined closure and function-lowering
  diagnostics, and deterministic function order matching closure selected
  order.

Out of scope:

Dependency scheduling; topological sorting for rendering; backend call
rendering; lowering primitive-call references into invocation text; recursive
nested-call lowering; parsing raw argument expressions; rendering backend type
text; source repair; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; public dependency graphs, schedulers, registries, dispatchers,
fixpoint mechanisms, or broad worklist machinery.

Expected outputs:

- Later generation planning can inspect one package to see the dependency
  closure, references, lowerable functions, and diagnostics for a selected
  root.
- The package makes current body-lowering gaps visible without inventing
  scheduling or renderer semantics.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py`:
  exit 0, `268 passed in 28.15s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

Follow-up:

- Documentation audit follow-up addressed during finalization by mirroring the
  backend-rendering deferral in the domain-model invariant.

### Milestone 150: Primitive-Call Expression Lowering Boundary With Exact Emit-Return Consumer

Status:

Accepted. M150 lowered an already recognized `PrimitiveCall` token into a
reusable typed primitive-call expression value, then proved that expression
through the first exact selected body consumer:
`emit_return(call<primitive=...>(...));`.

Goal:

Produce one reusable typed primitive-call expression value and consume it only
through the exact return form:

- accept only a selected implementation body with exactly one `emit_return`
  directive token;
- accept only an `emit_return` payload token stream containing exactly one
  recognized `PrimitiveCall` token;
- preserve the accepted `PrimitiveCallReference`, including target match, raw
  source arguments, bindings, and source provenance;
- allow `Lowerer.lower(...)` and the M149 package to include a function whose
  return expression is that typed primitive-call expression.

Scope:

- Compose existing M144-M147 primitive-call reference behavior; do not
  duplicate selector parsing, target matching, argument binding, or inventory
  walking.
- Keep primitive-call expression lowering reusable; do not implement separate
  per-context call lowering for `emit_return`, `var`, `let`, assignments,
  loops, or conditions.
- Preserve raw argument text as source truth; do not parse, validate,
  normalize, or repair argument expressions.
- Keep standalone `call<...>(...)` bodies, raw `emit_return(left)`, mixed
  raw-plus-call payloads, malformed calls, multi-token payloads, and primitive
  calls embedded in unselected surrounding contexts as explicit unsupported
  diagnostics.

Out of scope:

Standalone primitive-call statement semantics; primitive-call consumers other
than the exact `emit_return(...)` form selected above; dependency scheduling;
topological sorting for rendering; backend call rendering; backend type
rendering; resolving call arguments into backend expressions; recursively
lowering nested calls inside arguments; parsing raw argument expressions;
array/index/operator/helper/cast semantics; lowering arbitrary
`emit_return(...)` expressions; lowering var/let/loop/if payload semantics;
source repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
public dependency graphs, schedulers, registries, dispatchers, fixpoint
mechanisms, or broad worklist machinery.

Expected outputs:

- Primitive-call expression lowering has one reusable typed representation
  instead of separate per-context call lowering.
- The first exact primitive-call return body can become backend-neutral
  lowered function state.
- The M149 package becomes more useful because root functions with exact
  return-call bodies can join the lowered-function set without renderer
  semantics.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py`:
  exit 0, `281 passed in 11.39s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-cleanup `git diff --check`: exit 0, no output.

Follow-up:

- Architecture and evidence follow-ups about explicit unselected-context and
  argument-count boundary coverage were addressed during finalization.
- Documentation follow-up about inventory reusing expression lowering was
  addressed during finalization.

### Milestone 151: Primitive-Call Lowering Consolidation Boundary

Status:

Accepted. M151 stopped primitive-call feature growth and consolidated the
accepted M144-M150 lowering path before adding recursive call scanning,
additional consumers, backend call rendering, or dependency scheduling.

Goal:

Reduce primitive-call lowering complexity while preserving accepted behavior:

- collapse milestone-shaped pass-through layers around selector payloads,
  target matching, argument binding, expression creation, inventory, closure,
  package assembly, and diagnostics where they do not carry independent
  ownership;
- keep a small cohesive resolver/collector concept for the real domain facts:
  source `PrimitiveCall`, matched selected implementation, raw argument
  bindings, source/provenance, diagnostics, deterministic reference order, and
  lowered primitive-call expression values;
- preserve public clean-restart behavior and accepted tests;
- update docs so primitive-call lowering is described as one cohesive concept,
  not as a durable mini-pipeline.

Scope:

- Refactor and simplify the current primitive-call lowering modules.
- Remove or collapse private modules whose only purpose is forwarding between
  adjacent primitive-call layers.
- Preserve `tslgen.lowering` public imports and `Lowerer` methods where
  accepted tests rely on them, unless the exposed surface is clearly internal
  milestone scaffolding and tests/docs are updated accordingly.
- Add consolidation-focused tests only where existing M144-M150 tests do not
  make the preserved behavior obvious.

Out of scope:

New primitive-call semantics; recursive primitive-call scanning; primitive-call
discovery in additional surrounding contexts; `var`, `let`, assignment, loop,
`if`, `switch`, cast, intrinsic, operator, helper, array/index, or
name-reference lowering; expression trees; replacing raw argument text with
lowered argument expressions; backend call rendering; backend type rendering;
dependency scheduling or topological output sorting; source repair; runtime
`tsldata`, `frozen`, or `tslgenold` dependencies; public dependency graphs,
schedulers, registries, dispatchers, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

Expected outputs:

- Primitive-call lowering has fewer moving parts and clearer ownership.
- Accepted M144-M150 behavior, diagnostics, deterministic order, and raw
  argument preservation remain stable.
- The next feature milestone can build on a simpler call boundary instead of
  carrying accumulated middleware.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
find tslgen -type d -name __pycache__ -print
```

Accepted validation result:

- `git diff --check`: exit 0, no output.
- `python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py`:
  exit 0, no output.
- `python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py`:
  exit 0, `273 passed in 11.34s`.
- Initial `find tslgen -type d -name __pycache__ -print` listed
  validation-created cache directories; after removing those directories, the
  final required `find tslgen -type d -name __pycache__ -print` returned exit
  0 with no output.
- Final post-review `git diff --check`: exit 0, no output.

Follow-ups:

- Future primitive-call work should not keep appending semantics to the
  consolidated `primitive_calls.py` file; split only for cohesive ownership if
  the file grows again.
- M152 is selected to shrink the remaining `Lowerer` primitive-call facade
  methods that were preserved for accepted tests during M151.

### Milestone 152: Lowerer Primitive-Call Facade Reduction Boundary

Status:

Planned after M151. This milestone should remove the remaining visible
primitive-call milestone scaffolding from `Lowerer` where it is only a facade
over the M151 resolver/collector ownership.

Goal:

Shrink `Lowerer` back toward selected-function/type lowering:

- update primitive-call substep tests to call `PrimitiveCallResolver`,
  `PrimitiveCallDependencyCollector`, or selector-payload helpers directly;
- remove `Lowerer.lower_primitive_call_*` helper methods that only delegate to
  the consolidated resolver/collector surface;
- keep selected-function lowering, exact return-call consumption, diagnostics,
  raw argument preservation, deterministic order, and generator behavior
  stable;
- keep closure-package composition on `Lowerer` only if it remains the
  smallest place to compose closure collection with `lower_all(...)`.

Out of scope:

New primitive-call semantics; recursive primitive-call scanning; primitive-call
discovery in additional surrounding contexts; `var`, `let`, assignment, loop,
`if`, `switch`, cast, intrinsic, operator, helper, array/index, or
name-reference lowering; expression trees; replacing raw argument text with
lowered argument expressions; backend call rendering; backend type rendering;
dependency scheduling or topological output sorting; source repair; runtime
`tsldata`, `frozen`, or `tslgenold` dependencies; public dependency graphs,
schedulers, registries, dispatchers, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

Expected outputs:

- The accepted primitive-call internals are exercised through their cohesive
  resolver/collector owner instead of old milestone entry points on `Lowerer`.
- `Lowerer` exposes fewer primitive-call substep facades while preserving its
  selected-function lowering role.

Validation:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
find tslgen -type d -name __pycache__ -print
```
