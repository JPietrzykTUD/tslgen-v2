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

## Recommended First Milestone

Start with Milestone 1, then Milestone 2 and Milestone 3. These establish the foundations needed to keep later work honest: diagnostics, source boundaries, and parser behavior.
