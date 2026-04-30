# Design Decisions

This file records major redesign decisions in an ADR-like format.

## ADR-001: Clean Redesign, Not Legacy Rewrite

Status: Accepted

Context:

The repository includes a brittle legacy implementation under `frozen/` and an exploratory sketch under `tslgen/`. The user explicitly requested a first-principles redesign, not a refactor or module-by-module rewrite.

Considered alternatives:

- Refactor legacy modules incrementally.
- Port legacy modules into the new package.
- Design around observed domain requirements.

Decision:

Design around domain requirements and observable behavior. Use `frozen/` only as evidence.

Rationale:

The legacy implementation mixes parsing, compatibility projections, selection, rendering, and side effects. Preserving that structure would preserve technical debt.

Consequences:

- Future agents must cite behavior evidence rather than old module names.
- No central migration map from old modules to new modules will be maintained.
- Compatibility must be proven through behavioral and golden tests.

## ADR-002: Target Python 3.14 Or Newer

Status: Accepted

Context:

The exploratory package at `tslgen/pyproject.toml` declares `requires-python = ">=3.14"`. The dev container has Python 3.14.4 installed, so the repository runtime currently matches that baseline.

Considered alternatives:

- Keep Python `>=3.14`.
- Lower the target to Python `>=3.12` for broader compatibility.
- Defer the version decision until packaging work begins.

Decision:

Target Python `>=3.14` for the redesign.

Rationale:

The active development environment already provides Python 3.14.4, and matching the existing package metadata avoids adding an artificial compatibility constraint during the clean redesign.

Consequences:

- New implementation work may rely on Python 3.14 as the minimum supported runtime.
- `tslgen/pyproject.toml` can keep `requires-python = ">=3.14"`.
- Agents should still write plain, maintainable typed Python and avoid version-specific features unless they materially improve the implementation.

## ADR-003: Typed Domain Catalog After Parsing

Status: Accepted

Context:

TSL source contains structured concepts: primitives, attributes, tests, implementations, extensions, type groups, lane sets, templates, language maps, translations, and flags. Legacy evidence uses dictionaries far into the pipeline.

Considered alternatives:

- Keep dictionaries as primary objects.
- Use typed dataclasses immediately after parsing.
- Use a schema library as the only domain representation.

Decision:

Use typed immutable domain objects after the parser boundary. Boundary schemas may help validate raw input, but core logic consumes domain objects.

Rationale:

Typed objects make invariants testable and reduce accidental key/string coupling.

Consequences:

- Catalog construction is an explicit stage.
- Existing TSL flexibility needs a constrained `CatalogValue` escape hatch for extra fields.
- Repeated nested field keys may be preserved structurally in `CatalogValue` data;
  semantic merge or ambiguity policy belongs to validation and selection stages.
- Tests should assert object-level invariants, not raw dict keys.

## ADR-004: Diagnostics Are Structured Values

Status: Accepted

Context:

Legacy validators often raise `SystemExit`. The repository also contains early diagnostic dataclasses in `frozen/tsl-gen/tsl_gen/core/diagnostics.py`.

Considered alternatives:

- Continue raising `SystemExit`.
- Raise arbitrary exceptions from all validation logic.
- Accumulate structured diagnostics and let CLI convert them to exit codes.

Decision:

Use structured diagnostics with severity, stable code, message, source location, and notes.

Rationale:

Diagnostics improve testability, API usability, and multi-error reporting.

Consequences:

- CLI adapters own process exits.
- Tests can assert diagnostic codes and locations.
- Stage APIs should return result objects that include diagnostics.

## ADR-005: Source Loading And Artifact Writing Own Filesystem Side Effects

Status: Accepted

Context:

Generation involves many file types and generated outputs. Hidden I/O makes deterministic testing difficult.

Considered alternatives:

- Let each stage read/write files as needed.
- Centralize all I/O in a repository object.
- Use explicit loader and writer boundaries.

Decision:

Only source loading, manifest loading, hardware detection adapters, CLI, and artifact writing own side effects.

Rationale:

Pure stages are easier to test and can be reused through API calls.

Consequences:

- Renderers return `ArtifactSet` instead of writing.
- Selection receives CPU flags as data.
- Pipeline tests can run fully in memory until the writer stage.

## ADR-006: Backend Abstraction Is Capability-Based

Status: Accepted

Context:

The current redesign plan supports C++ and Rust as first-class backends. Legacy evidence also contains C17 manifests and templates, but C17 is no longer a planned implementation target for the current roadmap. Backend abstractions still need to be extensible enough for future backends.

Considered alternatives:

- Make Jinja file names the backend interface.
- Hard-code backend conditionals in shared planning code.
- Define backend protocols with capabilities, planners, and renderers.

Decision:

Use backend protocols and typed manifests/capabilities. Template engines are private renderer details.

Rationale:

Future backends and rendering strategies should not require changing core selection and validation.

Consequences:

- Backend support can be tested independently.
- Backend manifests need schema validation.
- Shared code should operate on templates as domain operation names, not file paths.

## ADR-007: Determinism Is A Pipeline Invariant

Status: Accepted

Context:

Generated code and tests need golden-file validation. Filesystem traversal, maps, and parallelism can produce nondeterministic outputs.

Considered alternatives:

- Rely on Python insertion order.
- Sort only final artifacts.
- Define stable ordering at every pipeline boundary.

Decision:

Every stage that produces a collection must define stable ordering.

Rationale:

Determinism is required for reproducible generation, golden tests, and useful diffs.

Consequences:

- Candidate identities and artifact keys need explicit ordering.
- Parallel execution must merge by stable keys.
- Tests should include repeat-run determinism checks.

## ADR-008: Host Hardware Detection Is An Adapter

Status: Accepted

Context:

Legacy workflows infer extensions from `/proc/cpuinfo` and shell commands. API and tests need host-independent behavior.

Considered alternatives:

- Read `/proc/cpuinfo` in selection.
- Require users to always pass explicit flags.
- Make hardware detection an optional adapter feeding explicit config.

Decision:

Hardware detection belongs in CLI/config adapters. Core selection receives normalized feature flags and explicit extension policy.

Rationale:

This keeps tests stable and makes cross-target generation possible.

Consequences:

- CLI can offer autodetect mode.
- API callers can provide flags directly.
- Selection tests do not depend on host CPU.

## ADR-009: TSIL Needs A Semantic Boundary

Status: Accepted for the first lowering slice; full TSIL grammar remains open

Context:

TSIL bodies in `tsldata/primitives/**.tsl` include calls, loops, type expressions, generation-time conditions, and backend translations. Legacy code uses many string and regex rewrites.

Considered alternatives:

- Continue string rewrites.
- Fully implement TSIL parser first.
- Initially preserve TSIL text but design a parser/lowering boundary.

Decision:

Introduce a TSIL semantic boundary before implementing broad lowering. Early milestones may store TSIL as text, but dependency and lowering milestones should parse TSIL into a model.

Milestone 18 decision:

Use a typed-opaque lowering boundary before parsing TSIL broadly. The boundary
classifies selected implementation payloads and returns explicit unsupported
diagnostics for semantic lowering. It records generation-time branch markers so
future lowering slices, not renderers, own `if<generation>(...)` evaluation.

Rationale:

String rewrites are brittle, but a full TSIL compiler is too large for the first milestone.

Consequences:

- Early catalog milestones can defer TSIL parsing.
- Dependency extraction should be designed to migrate from conservative parser to full TSIL AST.
- Lowering tests need focused fixtures.
- Production-shaped renderers must not treat opaque TSIL payload text as
  lowered backend code.

## ADR-010: Variant Selection Policy Must Be Explicit

Status: Accepted

Context:

Some implementation entries may have list-backed variants. Legacy evidence selects the first dict in a list in some cases.

Considered alternatives:

- Preserve first-dict-wins.
- Reject all list variants.
- Define an explicit policy based on predicates, priority, or diagnostics.

Decision:

Do not preserve first-dict-wins as hidden behavior. Define explicit variant selection before supporting list-backed variants broadly.

Rationale:

Hidden selection makes output difficult to reason about and test.

Consequences:

- Milestone 20 diagnoses unsupported selected list-backed implementation
  variants at the implementation-spec boundary while deferring unselected
  branches.
- A future milestone may add an explicit list-variant policy, but it must not
  silently choose the first entry.

## ADR-011: Golden Compatibility Is Behavioral, Not Structural

Status: Accepted

Context:

Generated output compatibility matters, but legacy structure does not.

Considered alternatives:

- Match legacy output byte-for-byte immediately.
- Ignore legacy output entirely.
- Establish selected golden baselines for behaviorally important outputs.

Decision:

Use selected golden baselines for deterministic compatibility where output stability matters.

Rationale:

Byte-for-byte matching all legacy output would over-constrain architecture, while no baselines would risk regressions.

Consequences:

- Golden coverage starts with small representative primitives/backends.
- Formatting can change intentionally with updated golden files and documented decisions.

## ADR-012: C17 Is Deferred From The Current Roadmap

Status: Accepted

Context:

Legacy evidence includes C17 manifests and templates, but the current redesign effort should focus on C++ and Rust. Supporting fewer first-class backends reduces early architecture and testing load while the core pipeline is still being established.

Considered alternatives:

- Keep C17 as a first-class backend alongside C++ and Rust.
- Remove backend extensibility and specialize around C++ and Rust only.
- Defer C17 while keeping the backend protocol extensible.

Decision:

Defer C17 support from the current implementation roadmap. Treat C17 files under `frozen/` and `tsldata/` as legacy evidence only unless a future decision reintroduces C17 as a target.

Rationale:

The core redesign needs stable parsing, catalog modeling, validation, selection, lowering, rendering, and golden testing before additional backend breadth is valuable. C++ and Rust provide enough backend diversity to validate the architecture.

Consequences:

- Current milestones target C++ first and Rust second.
- C17 should not appear in package layout, required tests, or first-release backend requirements.
- Backend interfaces should remain general enough that C17 or another backend can be added later without changing core pipeline boundaries.

## ADR-013: Backend Manifests Are Typed Planning Inputs

Status: Accepted

Context:

Backend behavior is evidenced by YAML manifest files and by TSL language and
translation declarations. Artifact planning needs an authoritative backend set
without coupling later stages to YAML dictionaries or parser trees.

Considered alternatives:

- Treat YAML dictionaries as backend plans.
- Convert all backend manifest data into TSL before planning.
- Load backend manifests into typed Python value objects.

Decision:

Load backend manifests into typed immutable `BackendManifest` values. The
artifact planning stage uses a `BackendManifestSet` as the authoritative set of
known backend IDs. A minimal manifest set may be derived from catalog data only
when matching `language` and `translation` entries exist for the same backend ID
and the artifact descriptor is known.

Rationale:

Typed manifests keep YAML at the I/O boundary while preserving a data-driven
backend model for C++, Rust, and future backends.

Consequences:

- YAML remains a supported interchange format, not a core architecture shape.
- Unknown backend diagnostics are issued against the supplied manifest set.
- Artifact descriptors remain content-free until rendering and writing stages.

## ADR-014: First C++ Slice Renders Opaque Candidate Summaries

Status: Accepted

Context:

The roadmap calls for a first narrow C++ backend artifact before full lowering
and template rendering exist. Candidate selection currently provides typed
candidate metadata and opaque implementation payloads, while TSIL lowering is a
later boundary.

Considered alternatives:

- Implement broad C++ template rendering immediately.
- Treat opaque TSIL strings as final generated code.
- Render a deterministic C++ header-like summary artifact from selected
  candidate metadata.

Decision:

The first C++ backend slice renders a deterministic generated-header artifact
containing candidate metadata, required flags, and escaped opaque TSIL payload
text. It does not lower TSIL or claim the payload is executable backend code.

Rationale:

This proves the accepted selection, dependency, manifest, artifact-plan, and
backend-rendering boundaries can connect end to end without smuggling in a
template engine or TSIL compiler ahead of their milestones.

Consequences:

- Golden output covers the rendering contract for this narrow slice.
- Full C++ specialization/wrapper rendering remains deferred.
- Backend mismatch is diagnosed by the renderer before artifact content is
  produced.

## ADR-015: Post-Milestone-15 Work Establishes Boundaries Before Broad Generation

Status: Accepted

Context:

Milestones 1 through 15 establish parsing, catalog modeling, validation,
selection, dependency discovery, backend manifests, summary rendering, CLI/API
integration, Rust summary rendering, and coverage reporting. The remaining
risks are not one large code-generation task; they are boundary questions around
filesystem writing, production test planning, lowering, dependency precision,
implementation specification typing, validation scope, report artifacts, and
public API shape.

Considered alternatives:

- Start broad C++ or Rust code generation immediately.
- Combine artifact writing, lowering, generated tests, report files, and CLI
  compatibility into one milestone.
- Add small boundary milestones before broad backend rendering.

Decision:

The post-Milestone-15 roadmap establishes reviewable boundaries first:
artifact writing, production test-source planning, lowering/TSIL strategy,
candidate-specific dependency closure, implementation spec promotion, validation
baseline/quarantine, then one narrow production-shaped backend rendering slice.
Report files and public API polish follow those foundations.

Rationale:

Broad generation would otherwise force renderers to absorb filesystem safety,
TSIL semantics, dependency extraction, test planning, report writing, and API
decisions at once. Keeping these concerns separate preserves the clean-room
architecture and gives each future executor a thin vertical slice with clear
tests.

Consequences:

- Milestone 16 is the recommended next executor milestone.
- Full backend completeness remains deliberately deferred until the prerequisites
  are accepted.
- API and CLI expansion must expose only capabilities implemented by earlier
  milestones.
