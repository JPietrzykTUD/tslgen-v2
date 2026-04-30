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

The repository supports C++, C17, and Rust, each with distinct templates and behavior. Legacy manifests map templates to Jinja filenames.

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

Status: Proposed

Context:

TSIL bodies in `tsldata/primitives/**.tsl` include calls, loops, type expressions, generation-time conditions, and backend translations. Legacy code uses many string and regex rewrites.

Considered alternatives:

- Continue string rewrites.
- Fully implement TSIL parser first.
- Initially preserve TSIL text but design a parser/lowering boundary.

Decision:

Introduce a TSIL semantic boundary before implementing broad lowering. Early milestones may store TSIL as text, but dependency and lowering milestones should parse TSIL into a model.

Rationale:

String rewrites are brittle, but a full TSIL compiler is too large for the first milestone.

Consequences:

- Early catalog milestones can defer TSIL parsing.
- Dependency extraction should be designed to migrate from conservative parser to full TSIL AST.
- Lowering tests need focused fixtures.

## ADR-010: Variant Selection Policy Must Be Explicit

Status: Proposed

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

- Initial implementation may diagnose unsupported ambiguous variants.
- An open question tracks the exact policy.

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
