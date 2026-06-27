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

The quarantined exploratory package at `tslgenold/pyproject.toml` declares
`requires-python = ">=3.14"`. The dev container has Python 3.14.4 installed,
so the repository runtime currently matches that baseline.

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
- Future clean `tslgen/` packaging can keep `requires-python = ">=3.14"`.
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

Milestone 30 refinement: the active backend IDs for the current roadmap are
`cpp` and `rust`. Catalog-derived manifests are created only for active
backends; `c17` language and translation data remains deferred evidence and is
not derived into an active `BackendManifestSet`. Catalog `language` and
`translation` entries are promoted into typed boundary values for validation
only. Active manifests require a language map for `language_id` and a
translation map for `backend_id`, but renderers do not evaluate translation maps
in this slice.

Rationale:

Typed manifests keep YAML at the I/O boundary while preserving a data-driven
backend model for active C++/Rust and future backends.

Consequences:

- YAML remains a supported interchange format, not a core architecture shape.
- Unknown backend diagnostics are issued against the supplied manifest set.
- Inactive backend diagnostics are issued before rendering when a deferred
  manifest such as C17 is supplied for artifact planning.
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

## ADR-016: Validation Baseline Quarantines Exploratory Sketches

Status: Accepted

Context:

Milestones 1 through 20 have accepted a redesigned pipeline surface, but the
repository still contains pre-redesign sketches under `frontend`, `ir`,
`middle_end`, `utils`, and early core files. Broad package validation fails on
these sketches because some files are syntactically incomplete or import
unstable `tslgen.src.tslgen` paths. Future agents still need a reliable command
that catches regressions in accepted code.

Considered alternatives:

- Require every historical sketch to pass the same validation profile.
- Delete exploratory paths during the validation milestone.
- Define a production validation profile and quarantine unsupported sketches.

Decision:

Define a local redesigned-code validation profile in `tslgen.tooling.validation`.
The profile includes accepted redesigned modules and unit tests, current-corpus
probes, targeted compile/lint/type checks, and `git diff --check`. Exploratory
sketches are documented as quarantined until a future milestone promotes or
removes them.

Rationale:

Validation should be strict for accepted architecture without spending this
milestone refactoring or deleting unrelated sketches. Explicit quarantine keeps
unsupported code visible and prevents accidental broad-validation claims.

Consequences:

- Historical pre-restart review packets can run
  `PYTHONPATH=tslgenold/src python -m tslgen.tooling.validation`.
- Quarantined paths must not be imported by public API, CLI, or accepted
  pipeline tests.
- Quarantine cannot be used to exclude accepted redesigned modules merely
  because they fail validation.

## ADR-017: First Production-Shaped Rendering Slice Is C++ Scalar Declarations

Status: Accepted

Context:

The accepted C++ and Rust backend slices render deterministic summary artifacts
from typed candidate metadata and opaque implementation payloads. Milestone 18
keeps TSIL lowering typed-but-opaque, so rendering executable implementation
bodies would overclaim semantics that are not available yet. Milestone 22 still
needs a concrete step beyond summary metadata.

Considered alternatives:

- Render C++ implementation bodies by treating TSIL text as C++ code.
- Start broad template rendering for a full primitive family.
- Render one production-shaped declaration slice from typed candidate and
  signature metadata while leaving bodies opaque.

Decision:

Expand only the C++ `generated` artifact with declarations for selected scalar
`binary` candidates with signature `v:=(v,v)` and type tag `si32`. Candidates
outside this slice are diagnostics, not silent omissions.

Rationale:

Function declarations are production-shaped C++ output but do not require TSIL
semantic lowering, backend translation maps, or implementation-body rendering.
The slice validates renderer ownership, deterministic output, unsupported-case
diagnostics, and golden review without starting full generation.

Consequences:

- The C++ golden artifact now includes a declaration namespace and `<cstdint>`.
- Full wrappers, implementations, SIMD type mapping, translation-map evaluation,
  and Rust production-shaped rendering remain deferred.
- Future rendering slices should continue consuming typed candidate/spec/lowering
  objects rather than parser trees or raw catalog dictionaries.

## ADR-018: Report HTML Is A Pure Artifact Renderer

Status: Accepted for the Milestone 23 slice

Context:

Milestone 15 introduced deterministic coverage report values and JSON text.
Milestone 16 introduced artifact writing as the only filesystem mutation
boundary. The roadmap calls for a first legacy-style report/output slice without
reintroducing hidden writes or full legacy web UI parity.

Considered alternatives:

- Recreate the legacy HTML report structure.
- Add report writing directly to reporting helpers.
- Render a small deterministic HTML report from accepted coverage values and
  expose it as a normal in-memory artifact.

Decision:

Render the first HTML coverage report as pure text from
`PipelineCoverageReport`, then wrap it in an `Artifact` at
`reports/coverage.html` when callers need an artifact value.

Rationale:

This keeps reporting descriptive and side-effect-free while proving report
artifacts can flow through the same artifact and writer boundaries as backend
outputs.

Consequences:

- Dynamic report content must be HTML-escaped.
- HTML output has a narrow golden baseline and does not claim full legacy
  report parity.
- Any filesystem write for report artifacts must use the accepted artifact
  writer boundary.

## ADR-019: API And CLI Expose Accepted Capabilities Only

Status: Accepted for the Milestone 24 slice

Context:

The redesigned pipeline now has accepted public orchestration, reporting,
rendered artifact values, and a safe artifact writer. The final polish milestone
needs to make those capabilities usable without turning the CLI into a legacy
drop-in replacement or exposing unstable internals.

Considered alternatives:

- Keep reporting and writing available only through implementation modules.
- Add broad legacy-compatible CLI flags for all historical workflows.
- Expose small API helpers and narrow CLI flags for already-accepted behavior.

Decision:

Expose coverage/reporting helpers and writer delegation through `tslgen.api`.
Expose CLI report output through `--coverage-report json|html` and explicit
artifact writing through `--output-root`, with `--dry-run` and
`--no-skip-unchanged` applying only to that write request.

Rationale:

This gives API and CLI users a stable facade over the accepted pipeline while
preserving side-effect boundaries. Reporting remains pure, and every filesystem
write still goes through `io.artifact_writer`.

Consequences:

- Default CLI behavior remains non-writing.
- Report stdout is deterministic and does not imply report file generation.
- Full legacy CLI compatibility and broader output UX remain deferred.

## ADR-020: Post-Milestone-24 Phase Stabilizes Interfaces Before Broad Generation

Status: Accepted

Context:

Milestones 1 through 24 establish a clean pipeline, writer boundary, reporting
facade, test-source planning, typed-opaque lowering, candidate-specific
dependency closure, implementation-spec promotion, validation quarantine, and
one narrow C++ declaration slice. The remaining work includes real lowering,
body rendering, generated tests, Rust production-shaped output, backend metadata
completeness, and cleanup of exploratory sketches.

Considered alternatives:

- Start full C++ code generation immediately.
- Start full TSIL parsing before any further rendering work.
- Stabilize the accepted CLI/report/write contract, expand declarations and
  naming, then add one mini-lowering and one body-rendering slice.

Decision:

The next roadmap phase proceeds in small reviewable slices: first lock down
combined CLI report/write behavior, then expand C++ declarations and naming,
then introduce one TSIL mini-lowering form, then render one C++ scalar body from
lowered data. Production test rendering, backend manifest/language-map
completeness, Rust declaration rendering, dependency reporting, exploratory-code
retirement, and corpus/validation hygiene follow as separate milestones.

Rationale:

Broad generation would force unresolved naming, lowering, test rendering,
backend metadata, API/reporting, and cleanup questions into one change. The
chosen sequence protects accepted user-facing behavior first, then grows
semantic generation only where the data model is ready.

Consequences:

- Milestone 25 is the recommended next executor milestone.
- C++ body rendering is blocked on a documented naming contract and a
  mini-lowered TSIL form.
- Rust production-shaped rendering remains first-class but follows the backend
  metadata and naming lessons from C++.
- Legacy CLI compatibility and full report/documentation parity remain deferred
  until the narrower CLI and report contracts are stable.

## ADR-021: Combined Report/Write CLI Keeps Report Stdout Parseable

Status: Accepted for the Milestone 25 slice

Context:

Milestone 24 exposed both report printing and artifact writing through the CLI.
Coverage reports can be machine-readable stdout, while write reports are
human-readable summaries of filesystem effects.

Considered alternatives:

- Suppress write-report lines whenever a coverage report is requested.
- Put both report content and write-report lines on stdout.
- Keep report content on stdout and write-report lines on stderr in combined
  report/write mode.

Decision:

When `--coverage-report json|html` is combined with `--output-root`, stdout is
reserved for the requested report content and write-report lines are emitted to
stderr. Without `--coverage-report`, write-report lines continue to use stdout.

Rationale:

This preserves machine-readable report output for automation while still making
write behavior visible to users and keeping all filesystem mutation delegated to
the artifact writer.

Consequences:

- JSON report stdout remains parseable when artifacts are also written.
- HTML report stdout is not interleaved with write summaries.
- CLI stream behavior is now a regression-tested contract before broader CLI
  compatibility work.

## ADR-022: C++ Declaration Naming Is Narrow And Diagnostic-Only

Status: Accepted for the Milestone 26 slice

Context:

Milestone 22 introduced a production-shaped C++ declaration section for scalar
`binary` `si32` candidates. Milestone 26 expands that declaration slice to
`ui32` and needs the generated function and parameter names to be contractual
before future body rendering depends on them.

Considered alternatives:

- Sanitize unsupported characters into generated C++ identifiers.
- Introduce a broad ABI-level mangling policy before wrappers, overloads, and
  attributes are modeled.
- Keep the current declaration slice narrow and reject invalid names with
  diagnostics.

Decision:

For the current C++ declaration slice, derive function names as
`<emitted_primitive_name>_<type_tag>` and preserve TSL parameter names. The
derived function name and every parameter name must already be valid non-keyword
C++ identifiers. Invalid names produce structured diagnostics; the renderer does
not sanitize or mangle names.

Rationale:

The redesign does not yet model wrappers, overload sets, attribute-driven ABI
forms, or body rendering. A conservative diagnostic-only policy keeps current
golden output deterministic without freezing a broad future C++ ABI.

Consequences:

- The C++ golden declaration slice now covers `si32` and `ui32`.
- Future wrapper, overload, extension, and attribute naming must define their
  own backend-owned contract before generating output.
- Body rendering may reuse this naming contract only for the same supported
  scalar declaration slice.

## ADR-023: First TSIL Mini-Lowering Form Is Direct Parameter Addition Return

Status: Accepted for the Milestone 27 slice

Context:

Milestone 18 kept lowering typed-opaque because TSIL includes calls, loops,
generation-time expressions, intrinsic composition, casts, and backend
translation hooks. Milestone 27 needs one safe form before C++ body rendering
can consume lowered data without reading raw TSIL text.

Considered alternatives:

- Keep all TSIL typed-opaque and block body rendering again.
- Parse a general expression grammar.
- Lower one exact direct-return expression over declared parameters.

Decision:

Support only TSIL shaped as `complete(<parameter> + <parameter>);`, where both
operands name parameters declared by the selected primitive. Lowering produces
backend-neutral parameter-reference, binary-expression, and return-statement
values. Nearby return forms, unknown operands, generation-time branches, calls,
loops, intrinsics, casts, and backend-specific payloads remain diagnostics.

Rationale:

The form is evidenced by scalar arithmetic data and is small enough to review.
It gives the next C++ body-rendering milestone semantic input without treating
opaque TSIL text as backend code or committing to a full TSIL parser.

Consequences:

- `mini_tsil` becomes the default lowering strategy for selected candidates.
- `typed_opaque` remains available for the explicit unsupported Milestone 18
  behavior.
- Future lowering milestones must grow the lowering-owned TSIL model rather than
  letting renderers rescan raw payload text.

## ADR-024: First C++ Bodies Consume Mini-Lowered Return Statements Only

Status: Accepted for the Milestone 28 slice

Context:

Milestone 26 established the scalar C++ declaration and naming contract.
Milestone 27 introduced one backend-neutral lowered TSIL form: a direct
parameter-add return. The first body-rendering slice must prove rendering can
consume lowered data without reopening raw TSIL parsing in the backend.

Considered alternatives:

- Keep C++ output declaration-only until broad TSIL lowering exists.
- Render C++ bodies by reading candidate TSIL payload text.
- Render stubs when lowering is missing.
- Render one body form only from accepted lowered statements.

Decision:

Render C++ definitions only for the existing scalar `binary` `si32`/`ui32`
declaration slice when a `LoweringPlan` contains the mini-lowered direct
parameter-add return statement for the candidate. Missing lowered data,
unsupported lowered status, unsupported statement shape, or lowered parameter
references outside the declaration are diagnostics.

Rationale:

This keeps rendering backend-owned while preserving the lowering boundary. It
also gives the next production test and broader C++ rendering milestones a
concrete generated body without claiming general TSIL or SIMD semantics.

Consequences:

- The C++ golden artifact now contains inline function definitions for the
  supported scalar add slice.
- C++ rendering can still produce declaration-only output when no lowering plan
  is provided.
- Broader body rendering remains blocked on future TSIL, type, translation-map,
  and wrapper milestones.

## ADR-025: First Production Test Artifact Is Metadata-Style C++ Source

Status: Accepted for the Milestone 29 slice

Context:

Milestone 17 introduced typed production test-source planning, and Milestone 28
introduced one C++ scalar body-rendering slice. The first generated production
test artifact should prove that planned test metadata can become deterministic
source text without starting compile/run orchestration or a full generated-test
framework.

Considered alternatives:

- Render executable C++ assertions immediately.
- Render a backend-neutral manifest instead of C++ source.
- Defer generated test artifacts until full lane and mask policy exists.
- Render a narrow C++ metadata-style source artifact from `TestSourcePlan`.

Decision:

Render one deterministic C++ `production_tests` source artifact containing
metadata records for scalar `binary` `si32`/`ui32` planned tests. Each record
captures the test name, primitive, generated function name, candidate ID,
extension metadata, type tag, lane metadata, input vectors, and expected vector.
Unsupported artifact kinds, type tags, extra metadata, and case shapes are
diagnostics.

Rationale:

This makes the production-test rendering boundary concrete while avoiding
unstable lane resizing, mask handling, runtime execution, and compiler policy.
It also keeps generated production tests separate from repository unit tests.

Consequences:

- The first test artifact is inspectable C++ source, not an executable test
  harness.
- Full assertion rendering, lane policy, mask/test-manifest policy, compile/run
  orchestration, and Rust test rendering remain future milestones.
- Test rendering consumes `TestSourcePlan` and does not rescan raw TSL.

## ADR-026: First Rust Production Shape Is Body-Free Trait Signatures

Status: Accepted for the Milestone 31 slice

Context:

The accepted Rust backend renders deterministic summary metadata, while C++
already has a narrow scalar declaration and body slice. Rust needs a first
production-shaped output that validates backend-owned naming and signature
rendering without implying Rust body lowering or broad wrapper parity.

Considered alternatives:

- Render Rust free-function declarations without bodies.
- Render Rust function bodies from opaque TSIL payload text.
- Start with broad Rust trait/wrapper parity.
- Render one narrow trait signature slice.

Decision:

Render body-free Rust trait function signatures for scalar `binary`
`si32`/`ui32` candidates with normalized signature `v:=(v,v)`. The signatures
are emitted under `pub mod production` in a `ScalarBinaryDeclarations` trait.
Function names are derived as `<emitted_primitive_name>_<type_tag>` and
parameter names are preserved. Names must already be valid non-keyword Rust
identifiers. The slice uses a local explicit type mapping for `si32 -> i32` and
`ui32 -> u32`; it does not evaluate Rust language or translation maps.

Rationale:

Rust does not have ordinary body-free free-function declarations in modules.
Trait signatures provide a valid Rust-shaped declaration surface without
claiming lowered bodies, compiler integration, or final wrapper design. The
small scalar mapping is grounded in current Rust type evidence while keeping
translation-map evaluation deferred.

Consequences:

- The Rust golden artifact now preserves the summary metadata and adds body-free
  production signatures.
- Unsupported Rust declaration candidates and invalid names are structured
  diagnostics.
- Rust function bodies, intrinsics, Cargo integration, generated tests,
  translation-map evaluation, and broad trait/wrapper parity remain deferred.

## ADR-027: Candidate Dependency Reporting Uses Stable DTOs

Status: Accepted for the Milestone 32 slice

Context:

Milestone 19 accepted candidate-specific dependency closure, including
candidate edges, fallback primitive names, and warning diagnostics for
ambiguous, missing, or unsupported candidate-specific resolution. Coverage
reports and API helpers still exposed primarily primitive-level dependency
closure, leaving the accepted candidate-specific data hard to inspect.

Considered alternatives:

- Expose raw candidate dependency closure objects as the main public API.
- Recompute candidate dependency closure inside report generation.
- Replace primitive-level dependency fields with candidate-specific fields.
- Retain the closure in the pipeline and expose stable report DTOs.

Decision:

Retain candidate-specific dependency closure after primitive dependency
closure, derive it from the accepted primitive dependency graph, and expose it
through `CandidateDependencyReport` rows in coverage reports plus
`tslgen.api.candidate_dependency_report(...)`. JSON and HTML reports include
candidate edges, issues, fallback primitive names, ambiguous/missing/unsupported
groups, required candidate/primitive IDs, and candidate dependency diagnostic
counts.

Rationale:

The report should include candidate-specific dependency fallbacks because
Milestone 19 accepted fallback preservation as part of the dependency model.
Stable DTOs let API callers inspect the data without depending on raw analysis
internals, and deriving the closure before reporting keeps JSON/HTML rendering
pure and deterministic.

Consequences:

- Primitive-level dependency closure remains visible as the broad fallback
  model.
- Candidate-specific unresolved issues and fallback names are visible in both
  JSON and HTML reports.
- Reporting still does not parse TSIL, run dependency analysis, select
  dependency implementations, schedule backend jobs, or change lowering.

## ADR-028: Quarantined Code Is Retired By Evidence, Not Migration Shape

Status: Accepted for the Milestone 33 planning slice

Context:

Milestone 21 created a validation baseline that deliberately excludes
pre-redesign sketches under `frontend`, `ir`, `middle_end`, `utils`, early core
files, old sketch tests, `frozen`, and `tsldata`. Leaving those paths
unclassified makes future cleanup ambiguous, but deleting them without a plan
could lose evidence about dependency syntax, filtering, TSIL generation-time
expressions, or legacy workflows.

Considered alternatives:

- Promote quarantined modules into accepted packages because similar package
  names exist.
- Delete all quarantined paths immediately.
- Keep all quarantined paths indefinitely.
- Classify each path by evidence value and accepted-boundary fit.

Decision:

Use `docs/redesign/exploratory-code-retirement-plan.md` as the retirement
authority for Milestone 33. Delete candidates are paths whose useful concepts
are already covered by accepted architecture and tests. Evidence-only paths are
kept as requirement evidence, not runtime architecture. Keep-quarantined paths
need a future policy decision before deletion or migration. No path is approved
for direct code migration in this milestone.

Rationale:

The accepted architecture already covers behavior such as parsing, source-span
diagnostics, typed primitive/signature/extension models, selection filtering,
dependency closure, and lowering boundaries through accepted modules. The plan
therefore preserves evidence without treating historical module shape as a
target design.

Consequences:

- Future cleanup slices must update `tslgen.tooling.validation` only when they
  actually delete or promote a quarantined path.
- Future migrations must re-express behavior behind accepted boundaries with
  focused tests; they must not import quarantined modules.
- `frozen` remains evidence-only, and `tsldata` remains corpus data pending
  Milestone 34 hygiene policy.

## ADR-029: Corpus Hygiene Validates Data Without Treating It As Code

Status: Accepted for the Milestone 34 documentation slice

Context:

Milestone 21 established a validation profile for accepted redesigned Python
code and selected current-corpus probes. Milestone 33 classified `tsldata` as
keep-quarantined pending a corpus hygiene policy. The current workspace also
showed dirty `tsldata/**`, `.gitignore`, and `.devcontainer/**` entries that
were mode-only changes with zero content diff.

Considered alternatives:

- Add `tsldata` to Python compile, lint, or type-check targets.
- Normalize or reformat the entire corpus as cleanup.
- Expand the validation profile before deciding corpus ownership.
- Document a corpus review policy and keep the validation command surface
  unchanged for this slice.

Decision:

Classify `tsldata/` as accepted source corpus and read-only fixture corpus, not
as generated artifacts or Python implementation code. Validate it through
deterministic parser, catalog, validation, selection, backend metadata, and
rendering probes as those behaviors become accepted. Keep current mode-only
dirty state classified as accidental local dirty state unless executable-bit
intent is explicitly documented. Keep generated outputs behind the artifact
writer and committed golden fixtures under their own exact-diff policy.

Rationale:

The corpus should be validated through parser/catalog probes because `tsldata`
is accepted source data, not Python code. This protects behavior without
creating output churn, host dependencies, or broad cleanup pressure inside
implementation milestones.

Consequences:

- Milestone 34 does not change `tslgen.tooling.validation`, `.gitignore`, tests,
  generator behavior, generated outputs, or corpus contents.
- Future `tsldata` content edits must be reviewed as source-data changes with
  behavior evidence and focused tests.
- Future validation-profile expansion for corpus checks must be deterministic,
  host-independent, and paired with validation-profile tests plus the full
  Milestone 21 profile.
- Permission-bit churn and unrelated local artifacts are reported as dirty
  workspace state, not silently fixed in implementation slices.

## ADR-030: Pause Implementation For Stabilization After Milestone 34

Status: Accepted for the post-Milestone-34 closure review

Context:

Milestones 1 through 34 now cover the accepted clean-redesign foundation:
diagnostics, loading, parsing, catalog modeling, validation, selection,
dependency closure, backend manifests, artifact planning/writing, API/CLI
integration, reporting, typed-opaque lowering, a mini-lowering slice, narrow
C++ and Rust rendering, production test-source planning/rendering, validation
quarantine, and corpus hygiene. The remaining candidate work is broad and
directional rather than an immediate architectural prerequisite.

Considered alternatives:

- Start a new Milestone 35+ phase immediately for all remaining feature areas.
- Stop planning entirely and leave the stale "Recommended Next Milestone"
  pointer in place.
- Require planner resolution of every deferred open question before any
  stabilization work.
- Close the current phase and require a new planner pass only when a concrete
  future objective is chosen.

Decision:

Close the current roadmap phase and pause implementation for a
stabilization/release-readiness pass. Do not define a Milestone 35 in the
roadmap yet. Future implementation phases should begin only after a planner
chooses one primary objective, such as broader TSIL lowering, broader C++
rendering, Rust bodies, executable generated tests, legacy CLI compatibility,
or exploratory-code cleanup.

Rationale:

The accepted slices prove the major boundaries without overclaiming full
generator parity. Starting every deferred area at once would couple independent
concerns and encourage speculative abstractions. A stabilization pause gives
future agents a chance to verify the accepted surface, clarify release language,
and choose the next product goal deliberately.

Consequences:

- `docs/redesign/implementation-roadmap.md` records no new implementation
  milestone after Milestone 34.
- Open questions remain valid but are classified as future expansion blockers,
  not blockers for stabilization.
- Future agents should run the accepted validation and test surface before
  making release claims.
- A future roadmap phase must be scoped around one reviewable objective rather
  than bundling lowering, backend rendering, tests, CLI compatibility, and
  cleanup together.

## ADR-031: Functional Parity Proceeds From Selected Observable Behaviors

Status: Accepted for the post-stabilization parity roadmap

Context:

The architecture-foundation release does not claim to replace the legacy
generator. The next user goal is functional parity with `frozen/`, but the
project remains a clean-room redesign. The legacy implementation contains
useful evidence for CLI workflows, generated C++ output, backend manifests,
generated tests, documentation/reporting, and TSIL behavior, but its modules and
string-rewrite mechanisms are not target architecture.

Considered alternatives:

- Define one broad "reach parity" milestone.
- Port legacy emitters, TSIL passes, or CLI wrappers module by module.
- Start by implementing full TSIL grammar before selecting an output target.
- Select one observable behavior at a time and validate it through accepted
  redesign boundaries.

Decision:

Functional parity work must start with a frozen-output inventory and selected
golden baseline. The first implementation target is C++ `binary/add` parity,
because concrete generated output exists in `frozen/out/tsl`, accepted C++
scalar rendering already exists, and `tsldata/primitives/arithmetic/fundamental.tsl`
contains both simple scalar and native intrinsic TSIL evidence for the same
primitive family. Rust, executable tests, full generated docs, and broad CLI
compatibility remain later parity areas unless inventory evidence changes the
priority.

Rationale:

A selected C++ output slice is small enough to review and exercises real parity
concerns: output layout, support preamble, primary/specialization/wrapper
relationships, TSIL lowering, backend metadata, generated tests, and CLI
workflow compatibility. Starting with full TSIL or broad generation would make
it too easy to copy legacy architecture rather than reproduce required
behavior.

Consequences:

- `frozen/` remains a behavioral oracle and must not become a runtime
  dependency.
- Byte-for-byte compatibility is decided per output family or excerpt.
- Future parity milestones must name the legacy evidence path, accepted parity
  level, golden fixture policy, diagnostics, and deterministic validation.
- Production replacement claims remain blocked until selected parity criteria
  pass across the required behavior families.

## ADR-032: Backend Intrinsic Composition Belongs Behind Lowering/Translation

Status: Accepted for the backend-drift correction roadmap

Context:

The selected C++ native `binary/add` parity target requires a visible intrinsic
call such as `_mm256_add_ps(left, right)`. A narrow renderer-local mapping from
`("add", "avx2", "f32")` to that spelling can reproduce one fixture, but it
puts semantic lowering in the renderer and would scale into backend-specific
Python lookup tables. Repository evidence shows that `intrin_compose<...>`
includes base names, optional prefix/infix/suffix/post/immediate modifiers, and
generation-time type/value queries. The relevant data already lives in
`tsldata/detail/lang/types/types_cpp.tsl`,
`tsldata/detail/lang/translate_cpp.tsl`, `tsldata/extensions/extension.tsl`,
and primitive TSIL bodies.

Some modifier expressions combine backend-scoped requests with generation-time
queries, for example a backend suffix request whose input depends on
`type<generation>(...)`. Those generation-time forms must be resolved before
backend translation; otherwise translation becomes a raw TSIL evaluator.

Considered alternatives:

- Keep a small renderer-local intrinsic map for each native parity case.
- Implement full TSIL grammar and full translation-map evaluation before any
  native C++ output.
- Let backend templates evaluate generation-time conditions and compose
  intrinsic names.
- Let backend translation evaluate raw nested `if<generation>`,
  `type<generation>`, or `value<generation>` text.
- Add a typed translation/intrinsic-composition boundary that can grow one
  helper form at a time.

Decision:

Intrinsic composition must be represented as typed helper data and resolved by
a lowering/translation boundary before text rendering. Backend renderers may own
language-specific formatting, declarations, wrappers, and emitted text, but they
must consume already-resolved backend-call IR for semantic helper forms such as
`intrin_compose<add>`. Renderer-local intrinsic lookup tables are rejected as
the expansion strategy for native C++ or Rust rendering. The already-implemented
Milestone 39 native C++ `avx2/f32` slice does not need to be reverted solely
because it used a narrow local mapping, but it is classified as transitional:
Milestone 40 must preserve its observable output while relocating
intrinsic/type resolution behind typed lowering and data-driven translation.
Generation-time helpers such as `if<generation>(...)`,
`type<generation>(...)`, and `value<generation>(...)` resolve in semantic
lowering before backend translation. Backend translation receives typed semantic
values and backend-scoped requests; it does not parse or evaluate raw
generation-time TSIL text.

Rationale:

This preserves the generator architecture: TSIL helper semantics are modeled
once, data from `tsldata` remains authoritative, unsupported helper forms
produce diagnostics, and backend renderers stay focused on text emission. It
also avoids the false choice between a one-off hardcoded slice and a full TSIL
compiler.

Consequences:

- The accepted M39 native-rendering slice remains useful parity evidence, but
  it must not be expanded as-is.
- Milestone 40 becomes the required boundary-correction step before any broader
  native C++ or Rust rendering.
- Milestone 41 defines the generation-time semantic lowering contract before
  modifier support, suffix inference, or branch-dependent output expands.
- Milestone 41 selects boolean primitive-attribute branch pruning for
  `if<generation>(value<generation>(primitive::attribute(aligned)))` as the
  next implementable generation-time helper slice; broader generation-time
  type/value queries remain deferred.
- Milestone 42 implements that slice. The unselected branch is not recursively
  lowered or diagnosed, while unresolved generation-time helpers in the
  selected branch produce lowering diagnostics before backend translation.
- Milestone 43 implements the next generation-time helper/query slice:
  exact base scalar type queries for `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`, and
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`. Prose
  shorthand such as `base::signed_of(base::in)` is not accepted TSIL syntax.
  The slice produces typed semantic type references only; M45 and M46 consume
  those refs in backend translation for selected suffix and type-spelling
  slices, while native integer rendering remains separate M47 work.
- The post-M43 phase is numbered to keep translation and rendering separate:
  Milestone 44 selects the modifier boundary, Milestone 45 implements only
  intrinsic suffix translation over typed M43 values, Milestone 46 implements
  selected C++ type spelling over typed M43 values, and Milestone 47 renders
  native integer add only from those translated outputs.
- Milestone 45 produces typed suffix modifier values such as
  `BackendIntrinsicModifier(kind="suffix", backend_id="cpp",
  extension="avx2", intrinsic="add", value="epi32")`.
- Milestone 46 produces typed C++ scalar type-spelling values such as
  `BackendTypeSpelling(backend_id="cpp", type_tag="si32",
  spelling="int32_t")` and `BackendTypeSpelling(backend_id="cpp",
  type_tag="ui32", spelling="uint32_t")`.
- Milestone 47 consumes the M45/M46 values to render only the selected
  `add_binary<simd<int32_t, avx2>>` and
  `add_binary<simd<uint32_t, avx2>>` output returning
  `_mm256_add_epi32(left, right)`.
- Milestone 48 implements the selected post-M47 generation-time semantic
  lowering slice. It evaluates only
  `value<generation>(type::is_signed(type<generation>(base::in)))` over typed
  M43 `GenerationTypeRef(kind="base.in")` values and prunes exact
  `if<generation> ... else<generation>` branches with M42-style provenance.
  It does not reopen backend suffix/type-spelling translation or renderer
  semantics.
- Milestone 49 is accepted as the generated C++ test-source parity slice.
  It renders only one `add_i32_basic` source fixture from typed
  `TestSourcePlan` data and explicit typed C++ type-spelling input, preserves
  semantic evidence for wrapper-call and `TEST` registration intent, and does
  not compile, run, fetch `gtest`, read legacy templates at runtime, infer type
  spellings locally, or broaden generated-test parity.
- Milestone 50 is the selected post-M49 reporting adapter slice. It renders
  only one legacy-style coverage JSON row for `add` / `avx2` / `cpp` / `f32`
  from accepted typed report DTOs, keeps legacy string booleans at the adapter
  boundary, and does not rerun parser, selection, lowering, backend rendering,
  test rendering, CLI/writer, or compiler work.
- Milestone 51 is accepted as the exact plain-`else` syntax extension for the
  M48 signedness branch-pruning slice. It stays in generation-time semantic
  lowering over typed M43 `GenerationTypeRef(kind="base.in")` values and does
  not add conversion body lowering, backend translation, rendering, generated
  output, or broad TSIL parsing.
- Milestone 52 extends only the accepted concrete integer generation
  type/signedness semantics to the
  8/16/32/64-bit signed and unsigned integer tags. Backend suffix/type-spelling
  expansion,
  vector/register metadata, rendering, generated output, branch-body lowering,
  Rust, CLI/reporting, and compiler execution remain separate future
  decisions.
- Milestone 53 moves the accepted concrete integer semantic-rule source out of
  the lowering-private table and into typed domain/catalog rule values. This is
  a rule-ownership boundary change only; M52 behavior, selected tags,
  diagnostics, and backend/rendering deferrals remain stable.
- Milestone 54 wires those rule values through the normal catalog/lowering
  input path for pipeline-facing use without changing helper semantics or
  backend/rendering boundaries. The focused adapter builds a
  `LoweringRequest` with explicit catalog-derived concrete integer rules before
  lowering evaluates generation-time helpers.
- Milestone 55 introduces only the exact scalar
  size-byte generation value query
  `value<generation>(type::size_bytes(type<generation>(base::in)))`. It uses
  explicit scalar size-byte rules for selected integer and `f32`/`f64`
  singleton tags, returns a typed integer generation value, and keeps float
  support scoped to this query instead of broadening standalone `base.in` or
  signed/unsigned companion semantics.
- Milestone 56 introduces only the exact
  `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`
  arithmetic expression as another typed generation integer value. It keeps
  general expression parsing, comparisons, branch pruning, `else if<generation>`,
  surrounding body lowering, backend translation, rendering, and output
  deferred.
- Milestone 57 introduces only exact size-byte
  equality predicates over literals `2`, `4`, and `8`. It records typed
  boolean predicate values and keeps branch-chain pruning, broad
  `else if<generation>`, direct-intrinsic/body lowering, vector metadata,
  backend translation, rendering, and output deferred.
- Milestone 58 makes the value -> predicate -> control-flow lowering stage
  contract explicit through typed stage records on lowered implementations. It
  preserves accepted helper behavior while giving M59 branch-chain pruning a
  typed predicate output to consume without backend/rendering changes or raw
  helper reparsing.
- Milestone 59 uses those typed predicate stage outputs for exactly the
  documented SVE size-byte no-final-else branch chain. It keeps selected bodies
  opaque and defers selected-body handoff, direct-intrinsic/SVE body lowering,
  backend translation, rendering, and generated output.
- Milestone 60 makes selected-body handoff a distinct typed opaque boundary.
  It carries selected body text and provenance from M59 pruning without parsing
  or lowering body semantics and without stretching M59 pruning metadata into
  the reusable handoff contract.
- Milestone 61 keeps the next step as typed selected-body assignment-form
  recognition only. It consumes M60 handoff values and emits form metadata
  through a distinct `selected_body_form_recognition` stage, not assignment
  semantics, direct intrinsic/SVE IR, backend translation input, renderer-ready
  IR, or broad TSIL body parsing.
- Milestone 62 is the first body-specific typed IR step because M61 has
  already isolated the exact selected assignment form. M62 projects typed M61
  records into unresolved selected-body IR, not a raw-text dispatcher, backend
  intrinsic request, SVE predicate semantic evaluator, or renderer-ready
  representation.
- Milestone 63 adds a backend-neutral selected-body envelope/sequence boundary
  over M62 typed selected-body IR values before adding more body semantics. It
  is a composition point for future body slices, not a direct-intrinsic
  evaluator, SVE semantic layer, backend translation input, renderer input, or
  broad TSIL parser. SVE-looking `array.tsl` text is evidence for the need for
  the boundary, not an architectural dependency.
- Milestone 64 accepts exact structural array-body slot assembly before
  semantic slot lowering. It composes accepted M63 selected-body envelopes into
  a deterministic ordered whole-body slot envelope, while keeping surrounding
  slots opaque and non-semantic so later milestones can refine one slot at a
  time.
- Milestone 65 is accepted as pipeline integration for the accepted M64
  envelope before semantic slot lowering. It makes normal lowering produce
  `ExactArrayBodyEnvelopeIr` and the `array_body_envelope_slot_assembly` stage
  from typed/provenanced skeleton input, without turning `lower_candidates`
  into a raw-text dispatcher and without adding skeleton recognition or
  body-slot semantics.
- Milestone 66 uses exact array-initialization slot form IR as the first
  slot-specific refinement because M65 made the whole-body envelope reachable
  through normal lowering. M66 refines only the first
  `opaque_pre_branch_array_initialization` slot into typed form IR, leaving
  vector metadata evaluation, backend uninit semantics, skeleton production,
  store/return lowering, SVE/direct-intrinsic semantics, backend translation,
  rendering, and output for later milestones.
- Milestone 67 is accepted as a typed deferred helper-request/provenance IR
  boundary over M66 leaves. It classifies the exact base-type,
  vector-length, vector-alignment, and backend-uninit helper leaves without
  evaluating them, creating backend translation requests, parsing raw slot
  text, or adding declaration/array semantics.
- Milestone 68 is accepted as the first typed request-resolution boundary over
  M67 helper-request IR. It resolves exactly the M67 base-type request
  for `type<generation>(base::in)` using accepted M43/M52/M53/M54 typed
  semantics and request/context inputs, not by reparsing M67 leaf text or
  bypassing the M67 request IR. Vector length, vector alignment, backend
  uninit, declaration/array semantics, backend translation, rendering, and
  generated output remain deferred.
- Milestone 69 is accepted as the extraction of the accepted M64-M68
  array-initialization stage assembly before adding vector/backend sibling
  resolvers. This is behavior-preserving maintainability work: the extracted
  private helper/result preserves current lowered fields, stage names/order,
  diagnostics, deterministic behavior, and generated-output state, and does
  not become a semantic helper dispatcher or broad stage registry.
- Milestone 70 is accepted to resolve exactly the M67
  `value<generation>(vector::length)` request through the M69 extracted
  pipeline. The accepted design condition is that vector-length facts arrive as
  explicit typed metadata before lowering evaluation; M70 must not infer lanes
  from raw helper text, SVE tokens, extension names, vector-bit strings,
  selected type tags, host CPU state, catalog data, backend maps, or renderer
  names.
- Milestone 71 is accepted to resolve exactly the M67
  `value<generation>(vector::alignment)` request through the M69/M70 extracted
  pipeline. The accepted design condition is that vector-alignment facts arrive
  as explicit typed metadata before lowering evaluation; M71 must not infer
  alignment from vector length, vector bits, scalar byte size, selected type
  tags, SVE token text, extension names, host CPU state, catalog data, backend
  maps, backend vector-alignment spellings, or renderer names.
- Milestone 72 is accepted to complete the exact array-initialization helper
  set before declaration/array semantics. The accepted design condition is
  that M72 packages accepted M68/M70/M71 results and the remaining exact M67
  `value<backend>(uninit::array)` request into one typed aggregate, while
  preserving backend uninit only as a deferred backend-value request boundary.
  It must not query backend maps, create translation requests, render backend
  text, or lower `var`/`array_type` semantics.
- Milestone 73 is implemented to introduce exact first-slot
  declaration-shell structural IR before broad declaration/array semantics.
  M73 consumes the accepted M72 helper-set completion and records the exact
  `array.tsl:105` `var<typed>(array_type<...>, tmp, ...)` structure as typed
  lowering state only. It must not add generic `var`/`array_type` parsing,
  variable scope, allocation/lifetime, initializer semantics, backend uninit
  translation, renderer-ready IR, store/return semantics, or generated output.
- Milestone 74 introduces exact array-body structural sequence and
  structural/provenance slot-role classification before any remaining slot
  semantics. M74 consumes accepted M64/M65 envelope state and accepted M73
  declaration-shell IR, then records the exact
  `array.tsl:105-111` source-ordered slot sequence as typed lowering state.
  The role labels must not become executable statement kinds or imply generic
  body IR, variable scope, allocation/lifetime, predicate semantics, store/
  return semantics, SVE/direct-intrinsic semantics, backend translation,
  renderer-ready IR, or generated output.
- Milestone 75 introduces an exact predicate path structural/request IR before
  any store-call or SVE predicate semantics. M75 consumes accepted M74 sequence
  state and accepted M63/M62 selected-body evidence, then records the exact
  `pg` initialization/update/use path as typed lowering state. It does not
  make `svptrue_b*`, `svst1`, `tmp.data()`, or `a` into SVE/store/backend
  semantics, and it does not introduce variable scope, generic predicate IR,
  backend translation, renderer-ready IR, or generated output.
- Milestone 76 is accepted as an exact post-branch intrinsic call-site
  structural/request IR before any store-call, ARM/SVE intrinsic, memory,
  pointer, or backend semantics. M76 consumes accepted M75 predicate-path state
  and accepted M74/M73 provenance, then records only the exact
  `intrin<svst1>(pg, tmp.data(), a);` shape as typed lowering state.
  It must not make `svst1`, `tmp.data()`, or `a` into store/backend semantics,
  and it must not introduce generic call IR, variable scope, backend
  translation, renderer-ready IR, or generated output.
- Milestone 77 addresses the accepted Stage 8 maintainability pressure as
  architecture rather than semantics. Lowering is treated as a composable typed
  pipeline: the exact M69-M76 tail now records private typed facts and
  dependencies in `tslgen.lowering._pipeline`, and exact recognizer tokens live
  in `tslgen.lowering._exact_shapes` as slice-local structural evidence.
  Future backfeeds must be explicit typed facts, typed requests, dependencies,
  and deterministic coordinator decisions; stages must not depend on hidden
  recursion, broad registries, raw-helper dispatch, or central semantic
  branching. M77 preserves accepted M57-M76 behavior and does not add semantic
  rules for `pg`, `svptrue_b*`, `intrin`, `svst1`, `tmp.data()`, or `a`.
- Post-M77 planning selects Milestone 78 because a module boundary without
  moving the package did not solve the `boundary.py` size problem. M78 is a
  behavior-preserving package decomposition decision: move the accepted exact
  array-body / array-initialization lowering package into private modules,
  keep public imports stable, and require a measurable `boundary.py` reduction
  of at least 1,000 physical lines. This is not a decision to create a generic
  lowering framework, a broad OO hierarchy, a stage registry, a semantic
  dispatcher, or new body/call/store/return semantics.
- M78 execution chooses the first concrete decomposition boundary as exact
  array-body shapes and diagnostics, not the whole package at once:
  `_array_body_shapes.py` owns exact array-initialization helper/slot
  structural rule values, `_array_body_diagnostics.py` owns exact array-body
  diagnostics, and `_exact_shapes.py` owns the remaining exact predicate-init
  recognizer tokens. `boundary.py` remains the public facade and is reduced to
  11,109 physical lines without adding semantics or circular imports.
- Post-M78 planning selects M79 as exact array-body typed model ownership
  extraction. This deliberately bundles only the follow-ups that share one
  ownership problem: duplicated exact helper `Literal` aliases and
  `_array_body_diagnostics.py` `Any` inputs both exist because the exact
  array-body / array-initialization models remain owned by `boundary.py` while
  related shapes and diagnostics now live in private modules. M79 is not a
  general cleanup bundle; it must preserve behavior, keep `boundary.py` as the
  public facade, prevent private modules from importing `boundary.py`, and
  avoid registries, dispatchers, plugin systems, broad TSIL parsing, backend
  hooks, renderer hooks, and new body/call/store/return semantics.
- M79 execution chooses `tslgen.lowering._array_body_models` as the private
  typed model owner. Exact helper aliases/rules, exact array-body envelope and
  array-initialization request/resolution models, declaration-shell and
  structural-sequence values, predicate-path request values, post-branch
  call-site request values, and local diagnostic protocols move there.
  `boundary.py` remains the facade/coordinator at 8,915 physical lines, and
  `_array_body_shapes.py` plus `_array_body_diagnostics.py` consume the model
  boundary without importing the facade. This is a behavior-preserving
  ownership decision, not a new lowering semantic layer.
- Post-M79 planning selects M80 as exact array-body validation boundary
  extraction rather than return-emission IR or full coordinator extraction.
  The validation/request-record helpers are the largest next coherent package
  that can depend on accepted private models, shapes, diagnostics, exact shape
  evidence, and pipeline facts without importing `boundary.py`. Source adapters
  and stage construction remain deferred because they still touch facade-owned
  `GenerationLoweringStage` and `LoweredImplementation`. This is a
  maintainability decision, not a registry, dispatcher, fixpoint, or new
  semantic lowering decision.
- M80 executes that decision by moving exact validation/request-record helper
  ownership into `tslgen.lowering._array_body_validation`. The module uses
  accepted private models, shape rules, diagnostics, exact structural evidence,
  and narrow protocols where facade-owned context-like values are still
  required. `boundary.py` remains the facade/coordinator, now at 7,208 physical
  lines, and private modules still do not import `boundary.py`.
- Post-M80 planning selected M81 as generation-time lowering core ownership
  extraction rather than return emission, broad TSIL lowering, or a generic
  evaluator/dispatcher. M81 executed that decision by moving accepted
  generation helper models, exact generation query helpers, control-flow
  pruning helpers, and diagnostics behind private typed modules while
  preserving facade imports and M42-M80 behavior. Source adapters, stage
  construction, backend/rendering/output behavior, broad helper families, and
  extension-specific semantic shortcuts remain out of scope.
- Post-M81 planning selects M82 as selected-body envelope ownership
  extraction rather than return-emission IR, stage-contract extraction, or
  exact-array readability cleanup. The selected-body envelope seam is the
  narrowest current lowering ownership problem: M60-M63 concrete body/envelope
  models still live in the facade while private exact array-body modules
  consume broad protocols and casts. M82 should move the minimal cohesive
  selected-body value-model cluster into a private typed module, preserve
  public facade imports and accepted behavior, and avoid new selected-body
  semantics, broad body parsing, registries, dispatchers, backend hooks,
  renderer hooks, and extension-specific shortcuts.
- M82 executes that decision by creating
  `tslgen.lowering._selected_body_models` as the private selected-body
  value-model owner. The selected-body handoff/form/body-IR/envelope dataclass
  cluster and selected-body union aliases move out of `boundary.py`, while
  selected-body lowering functions, source adapters, stage construction, and
  the public facade stay in `boundary.py`. Exact array-body modules now use
  concrete private selected-body envelope model checks instead of broad
  structural seams. This remains behavior-preserving ownership work, not new
  selected-body semantics or an extension-specific dispatch layer.
- M83 is accepted as the `GenerationLoweringStage` output-contract ownership
  decision. Stage/output compatibility, `GenerationLoweringStage`, and the
  minimal accepted mini-TSIL value-model dependency move to
  `tslgen.lowering._stage_contracts`; `boundary.py` remains the public
  facade/coordinator for source adapters, stage construction, and
  lower-candidate orchestration. The result removes the growing facade-owned
  stage/output validation ladder before adding another semantic stage while
  keeping M83 as private typed contract validation only: no new stage names, no
  output behavior changes, no source-adapter move, no registry/dispatcher/
  fixpoint engine, no exact return-emission/store/body semantics, and no
  backend or renderer hooks.
- M84 implements exact array-body pipeline and source-adapter ownership
  extraction before exact return-emission IR. The decision shrank
  `boundary.py` by moving one cohesive accepted M64-M76 ownership cluster
  behind private typed lowering modules, not by adding new lowering semantics
  or moving arbitrary code for line count. `boundary.py` remains the public
  facade for request/result models, selected-body public lowerers,
  `lower_candidates`, payload classification, and mini-TSIL lowering. Private
  exact array-body modules do not import the facade, preserve public imports,
  diagnostics, source locations, stage ordering, keys, output identities, and
  pipeline snapshots, and must not become raw-helper dispatchers, registries,
  callback maps, plugin systems, or fixpoint/backfeed engines.
- Post-M84 planning selects M85 as selected-body lowering ownership extraction
  before exact return-emission IR. The decision is to close the ownership gap
  left by M82 and M84 by moving the accepted M60-M63 selected-body lowerer
  implementation and direct source-helper ownership into a focused private
  typed module, not by adding new selected-body semantics. `boundary.py`
  remains the public facade for request/result models, `_lower_input`,
  `lower_candidates`, payload classification, mini-TSIL lowering, generation
  control-flow pruning, and exact array-body pipeline orchestration. The new
  module must not be `_selected_body_models.py`, must not import the facade or
  exact array-body source/lowering modules as convenience dispatchers, and
  must not become a selected-body framework, raw-helper dispatcher, registry,
  callback map, plugin system, or fixpoint/backfeed engine.
- M85 is accepted as that extraction in
  `tslgen.lowering._selected_body_lowering`. The public facade aliases remain
  stable through `boundary.py` and `tslgen.lowering`; the private module owns
  the accepted lowerer implementation and direct helper cluster without
  importing `boundary.py`, the package facade, `_array_body_sources.py`, or
  `_array_body_lowering.py`.
- M86 is accepted as candidate payload-intake and mini-TSIL leaf return
  lowering extraction before exact return-emission IR. The decision removes
  the remaining payload classifier and mini-TSIL parser/lowerer island from
  `boundary.py` while keeping central `_lower_input` orchestration,
  request/result models, generation query/control-flow staging, selected-body
  lowering, and exact array-body pipeline orchestration in the facade. The new
  private modules do not import `boundary.py` or the package facade, do not
  become a broad TSIL parser, registry, callback map, plugin system, raw text
  rewrite engine, or fixpoint/backfeed engine, and do not add new return
  semantics or generated-output behavior.
  Exact return-emission structural/request IR was identified as the next
  high-value semantic frontier, but M86 deliberately chose a broader
  maintainability slice first because payload classification and mini-TSIL leaf
  lowering were still facade-owned after M85 and could move behind typed
  private boundaries without changing behavior. M87 later addressed the exact
  return-emission frontier.
- M87 is accepted as exact return-emission structural/request IR. This is the
  first semantic step after the M77-M86 cleanup, but it is deliberately still
  structural/request-only: recognize the exact trailing `complete(tmp);`
  slot from the accepted array-body path, link the returned token to accepted
  declaration-shell provenance, and emit diagnostics for nearby or malformed
  forms. The implementation keeps source intake narrow in
  `tslgen.lowering._return_emission`, and the focused revision removed the M87
  output from the shared runtime lowered-implementation source protocol. The
  decision explicitly rejects source-body repair, broad `complete(...)`
  support, return-value semantics, variable lifetime/scope semantics,
  renderer-ready IR, backend translation, generated output, and generic TSIL
  statement dispatch.
- M88 is accepted as exact array-body structural package assembly before
  backend-uninit refinement, store semantics, or renderer-ready body IR. The
  decision turns the accepted M64-M87 exact array-body facts into one typed,
  source-ordered package that later stages can consume without reaching across
  many pipeline outputs. M88 uses focused private package ownership, preserves
  member fact identity/provenance, appends the
  `array_body_structural_package_assembly` stage after M87, and rejects
  missing, duplicate, malformed, mismatched, or provenance-inconsistent inputs
  with diagnostics. It deliberately remains typed aggregation only, not body
  semantics, source repair, backend translation, rendering, generated output,
  a broad source protocol, or a generic TSIL/body package framework.
- M89 is accepted as exact array backend-deferred request inventory before any
  backend-uninit translation or renderer-ready body IR. The decision consumes
  the accepted M88 structural package and exposes the accepted M72/M67
  `value<backend>(uninit::array)` deferred backend-value boundary as one typed
  inventory member for later backend planning. M89 preserves object
  identity/provenance and validates typed request fields and
  `deferred_backend_value` policy. It deliberately rejects backend map lookup,
  backend translation, Stage 9 planning, rendering, generated output, generic
  backend-value evaluation, broad protocols, and source-body repair.
- M90 is accepted as exact array lowering completion package before backend
  planning or renderer-ready body IR. The decision packages accepted M88
  structural facts and accepted M89 backend-deferred inventory facts into one
  typed Stage 8 handoff with explicit unresolved dependencies. "Completion" is
  deliberately limited to lowering-side handoff assembly; it rejects semantic
  body completion, backend-uninit resolution, backend map lookup, Stage 9
  planning, renderer-ready IR, rendering, generated output, generic
  backend-value evaluation, broad protocols, raw helper dispatch, hidden
  backfeeds, fixpoint machinery, and source-body repair.
- M91 is accepted as a behavior-preserving exact array pipeline ownership
  consolidation before adding more lowering semantics. The decision reduces
  future Stage 8 friction by giving exact array pipeline result aggregation
  focused `_array_body_pipeline_results.py` ownership and stage/snapshot
  assembly focused `_array_body_stage_assembly.py` ownership instead of adding
  another stage or aggregate field to `boundary.py` or
  `_array_body_pipeline.py`. M91 preserves accepted M64-M90 behavior and does
  not become a semantic lowering slice, backend planning boundary, renderer
  hook, broad protocol, registry, hidden backfeed engine, fixpoint
  coordinator, or source-body repair mechanism.
- M92 is accepted as exact array lowering backend-handoff request before
  backend planning. The decision creates one concrete typed request/provenance
  output from the accepted M90 completion package so later backend planning can
  consume stable lowering facts without reaching across pipeline internals.
  M92 is not a wrapper-only abstraction, and it does not resolve backend
  values, read backend maps, create Stage 9 plans, render output, introduce
  broad protocols, or repair source bodies.
- M93 is accepted as a dual-source lowering operation package boundary before
  backend planning. The decision proves the lowering package shape is not
  array-only by packaging exactly the accepted M86 mini-TSIL leaf return source
  family and accepted M92 exact array backend-handoff source family as
  distinct typed Stage 8 entries. M93 must not create a broad operation
  framework, semantic dispatcher, operation registry, dependency solver, Stage
  9 backend plan, renderer-ready IR, or source-body repair path.
- M94 is accepted as behavior-preserving operation-package diagnostics/
  provenance ownership split before adding more package families. The decision
  keeps the accepted M93 package contract stable while preventing
  `_operation_package.py` from becoming a replacement monolith. M94 moves
  diagnostics, accepted-source narrowing, mini-TSIL package-contract,
  exact-array provenance validation, and package models into focused private
  modules with one-way imports; it adds no new semantics, package registry,
  semantic dispatcher, backend-planning hook, renderer-ready IR, or source-body
  repair path.
- M95 is accepted as the first post-split package-family expansion because
  accepted M63/M62 selected-body direct-intrinsic facts are already typed and
  diagnostic-covered. The decision deliberately packages those facts as
  provenance only: `svptrue_b*`, `pg`, selected literals, type tags, branch
  ids, and source locations must not become semantic dispatch keys. The
  implementation owns selected-body package validation and entry construction
  in `_operation_package_selected_body.py`, while `_operation_package_sources.py`
  remains a narrow explicit source/stage/container bridge rather than a
  generic source protocol, package registry, callback map, or dispatcher.
- M96 is accepted as a Stage 8 lowering completion manifest boundary. The
  implementation creates a deterministic per-candidate
  `Stage8LoweringCompletionManifestIr` over accepted
  `LoweringOperationPackageIr` facts and explicit unresolved dependency
  references, not backend planning. "Completion" and "readiness" mean
  accepted Stage 8 package/provenance assembly status only; they do not mean
  semantic body completion, backend readiness, renderer readiness, executable
  readiness, or generated-output readiness. M96 preserves accepted package
  and unresolved dependency references by object identity, keeps manifest
  ownership in `_lowering_completion_manifest.py`, avoids growing
  `boundary.py` or `_operation_package_sources.py`, and does not introduce a
  backend plan, operation schedule, dependency closure, renderer IR, wrapper
  plan, artifact plan, package registry, source-family dispatcher, hidden
  backfeed, fixpoint mechanism, source repair path, or semantic unifier.
- M97 is accepted as a Stage 8 lowering completion gap inventory boundary.
  The decision makes unresolved lowering-side gaps explicit from accepted M96
  manifest facts before attempting backend planning or output work. The first
  supported gap category is accepted unresolved backend-handoff dependency
  records; manifests without those records produce a deterministic no-known-gap
  inventory. M97 preserves M96 object identity, keeps ownership in a focused
  private gap-inventory module, keeps `_operation_package_sources.py`
  unchanged, integrates one stage after `lowering_completion_manifest`, and
  does not infer backend readiness, semantic body completion, operation
  schedules, dependency closure, renderer readiness, or source repairs.
- M98 is accepted as behavior-preserving Stage 8 stage-assembly ownership
  extraction before adding more lowering semantics. The decision keeps this
  architecture work narrower than a broad coordinator: M98 extracts accepted
  `GenerationLoweringStage` construction and accepted per-candidate
  operation-package -> completion-manifest -> completion-gap-inventory result
  assembly into focused private `_lowering_stage_assembly.py` ownership, while
  keeping `boundary.py` as public facade and model owner. M98 preserves
  M57-M97 behavior, diagnostics, stage order, keys, and object identities and
  does not create a registry, dispatcher, callback map, hidden backfeed,
  fixpoint engine, backend-planning surface, renderer hook, source parser, or
  source-repair path.
- M99 is accepted as a Stage 8 backend-translation request
  inventory/provenance boundary before backend planning. The decision makes
  accepted backend-scoped request facts visible across operation packages,
  completion manifests, and gap inventories without resolving or translating
  them. M99 consumes accepted typed M93-M98 facts only, keeps ownership split
  across focused inventory, source-adapter, and diagnostics modules, updates
  `docs/redesign/missing-lowering-inventory.md`, and does not evaluate backend
  maps, start Stage 9 planning, infer direct-intrinsic/SVE semantics, scan raw
  source bodies, schedule operations, solve dependencies, render output, or
  turn inventories into readiness/completion claims.
- M100 is accepted as the first request-to-translation-result boundary after
  M99. The decision deliberately resolves only accepted M99 exact-array
  `exact_array_backend_value_uninit_array` records to typed C++ backend-uninit
  translation-result state from explicit typed rule input. This is the first
  small proof that request inventories can feed backend translation results
  without pushing semantics into renderers. M100 must not read backend
  maps/catalogs/manifests or `tsldata/detail/lang` during lowering, must not
  render C++ or Rust output, must not create Stage 9 backend plans, and must
  not generalize to Rust, generic backend helper evaluation, or selected-body
  direct-intrinsic/SVE semantics.
- M101 is accepted as a behavior-preserving lowering IR taxonomy and
  provenance consolidation before adding more lowering features. The decision
  recognizes that the accepted M57-M100 path made semantics explicit but also
  accumulated many narrow request/result/inventory/provenance object families.
  Future IR additions must fit a small vocabulary of semantic facts, requests,
  results, inventories, provenance values, rule inputs, and stage envelopes.
  M101 applies that contract only to the M99/M100 backend-translation
  request/result path through a small private helper for contract attachment,
  key comparison, and provenance identity mismatch checks. It does not use
  consolidation as a vehicle for new backend semantics, rendering, Stage 9
  planning, source repair, broad inheritance, registries, dispatchers, hidden
  backfeeds, or fixpoint machinery.
- M102 is accepted as the next architecture-stabilization slice because M101's
  category labels were useful but not yet the stable typed IR surface needed by
  future lowering milestones. M102 adds private category/protocol contracts for
  facts, requests, translation requests, translation results, inventories,
  provenance, rule inputs, stage outputs, and diagnostic boundaries, applies
  them first to the M99/M100 path, and keeps the existing public
  `LoweringRequest` input bundle distinct from taxonomy-level request IR.
- M103 accepts a Stage 8 backend-translation boundary worklist inventory before
  adding another backend-result or direct-intrinsic semantic family. The
  decision makes the backend-facing frontier visible as a static typed
  inventory/provenance view over accepted concrete M99/M100 facts, not a queue,
  scheduler, readiness oracle, Stage 9 planner, renderer-ready IR, backend-map
  evaluator, registry, dispatcher, hidden backfeed, or fixpoint mechanism.
- M104 accepts a broadened but single-boundary backend translation result
  expansion. The decision resolves more of the M103 worklist frontier through
  typed resolved/deferred/unsupported result records, while keeping semantics
  tied to explicit typed rule inputs and concrete typed request/result facts.
  It is not a generic backend dispatcher and does not infer
  direct-intrinsic/SVE semantics from tokens, extension ids, type tags, byte
  sizes, primitive names, raw source text, or hardware-looking strings.
- M105 records the KISS generator restart charter instead of extending another
  lowering micro-layer. The decision treats the accepted M57-M104 lowering/
  request/result/worklist path as evidence for requirements, diagnostics, and
  regression concerns, not as the architecture to keep extending by default.
  The restart product path is `.tsl` source data to a validated catalog,
  selected implementations, and deterministic C++ and Rust library artifacts.
  New abstractions must earn their place by simplifying that path or by
  serving at least two concrete accepted stages. The restart also requires a
  package-layout reset: the pre-restart top-level `tslgen/` tree is old-state
  evidence that M106 moved to `tslgenold/`, while the clean restart
  implementation owns the top-level `tslgen/` path. The standing contract is
  `docs/redesign/kiss-generator-restart.md`.
- The selected `_mm256_add_ps` output can still be golden-tested, but tests must
  also prove the value came from typed metadata and lowered helper IR rather
  than a renderer table.
- Broad modifier support, primitive calls, direct-intrinsic semantics beyond
  the accepted M62 unresolved body-IR shape, and broad C++/Rust body rendering
  beyond the accepted M63/M64/M65 envelope path, M66 first-slot form-IR
  boundary, accepted M67 helper-request/provenance boundary, and accepted M68
  base-type request-resolution boundary remain
  deferred until their own helper slices are selected.
- Future native rendering milestones must state which helper IR and translation
  data they consume before adding generated output.

## ADR-034: Tiny Scalar Operation Tables Are Bootstrap Core Lowering Semantics

Status: Accepted for post-M122 planning

Context:

The clean restart M111-M122 slices intentionally used small lowering-owned
tables for scalar operation descriptors and operation/type compatibility rules.
Those operation names are visible in `tsldata/*`, but the accepted clean
implementation currently does not parse broad `tsldata/` operation metadata or
load backend manifests to derive them. A product-owner review called out the
risk that corpus facts might appear to have silently leaked into generator
code.

Considered alternatives:

- Treat the current operation tables as test-only fixtures.
- Read `tsldata/*` or backend manifests at runtime to populate operation
  semantics now.
- Declare the current scalar operation set as explicit bootstrap core lowering
  semantics until a future typed rule-loading milestone is selected.

Decision:

The accepted M111-M122 scalar operation descriptors and compatibility rules are
bootstrap core lowering semantics for the clean restart, not accidental
runtime imports from `tsldata/*`. Milestone 123 will make that contract explicit
in typed lowering-owned records.

Rationale:

The clean restart is still proving a tiny source-to-artifact path. Loading
operation semantics from the broad corpus now would pull backend manifests,
translation maps, and catalog-wide policy into a slice that is only ready to
handle exact scalar source forms. At the same time, leaving the current tables
undocumented makes it unclear whether they are product semantics or fixture
leakage.

Consequences:

- `tsldata/` remains source corpus and fixture evidence, not a runtime source
  for the accepted scalar operation descriptor tables.
- Backend spellings remain backend-owned; lowering operation descriptors and
  compatibility rules must not carry C++ or Rust operator text.
- Future data-driven operation semantics require an explicit typed rule-loading
  milestone with diagnostics and tests; they must not be introduced through
  renderer inference, backend manifest shortcuts, or ad hoc dictionary maps.
## ADR-036: Implementation Bodies Are Source-Owned Token Streams

Status: Accepted

Context:

Clean restart body-lowering planning briefly drifted toward exact typed values
for specific indexed-assignment and loop-envelope TSIL forms. A product-owner
review clarified that this is drifting toward a validator/compiler for TSIL
instead of a generator that should primarily preserve `.tsl` implementation
body text and lower only the pseudo-language islands that require generator or
backend ownership. TSIL bodies can contain text where raw target-like text and
lowerable pseudo-language fragments are mixed, such as helper calls embedded in
assignments.

Considered alternatives:

- Continue adding one typed body class for each exact multiline source shape.
- Parse TSIL as a complete statement and expression language.
- Treat each implementation body as raw text with no typed lowerable fragments.
- Model implementation bodies as an ordered source-authored token stream where
  raw text and lowerable islands are peers.

Decision:

Implementation bodies are source-owned ordered token streams. Raw source text
and documented lowerable islands are peers in the stream. The working model is:

```text
ImplementationBody
  tokens: tuple[BodyToken, ...]

BodyToken =
  RawStringToken
  LowerableOperationFragment
  LowerableDirective
```

Raw text is the default and may contain newlines, indentation, braces,
assignments, semicolons, and target-like text. The generator recognizes and
lowers only documented pseudo-language islands that need generator/backend
ownership, such as helper operation fragments, generation/backend directives,
or exact return/loop directives selected by future milestones. Recognition of
an island must not imply parsing the surrounding assignment, array access,
expression, scope, or statement list unless a separate milestone explicitly
selects that behavior.

Rationale:

The research prototype needs to generate code from `.tsl` files that will
continue to change. Treating every nearby body shape as a new semantic object
creates noise and makes the generator look like a TSIL compiler. Treating the
entire body as raw text hides the parts that backends must own. A token stream
keeps source order and source-authored text intact while giving the generator
precise hooks for the few constructs it actually lowers, including future
islands that may span source lines.

Consequences:

- Future body-lowering milestones should prefer the ordered body-token stream
  instead of adding another exact whole-body wrapper class or line-primary
  container.
- Backends may render raw text segments as source-authored text only within an
  explicit backend rendering policy; backend-owned spellings and directives
  must still come from typed lowerable segments or backend translation rules.
- Unknown or unsupported source text should be preserved or diagnosed at the
  documented boundary; it must not be silently repaired, normalized, reordered,
  or guessed.
- Nested lowerable islands must be handled by recursive token-stream
  composition, not by adding pairwise context-combination handlers. For
  example, `intrin_compose` inside `complete`, `call`, or a control body is
  still just an `intrin_compose` island found inside another source-owned span.
  Future keyword semantics should consume matching keyword tokens wherever they
  appear in the recursive stream.
- Earlier exact whole-body prototypes remain evidence, but future work should
  avoid extending that shape-proliferation pattern without a clear product
  reason.
- The generator still does not parse TSIL as a complete language: no general
  precedence, associativity, statement-list, scope, loop, or expression model
  is implied by recognizing lowerable islands inside the token stream.

## ADR-037: Extension Register And Mask Type Facts Live In Source Data

Status: Accepted

Context:

The clean restart type-lowering work reached `vector::register`,
`vector::mask`, `vector::imask`, `vector::as_extension(...)`, and related type
queries while the generator still treated extension names as strings. Product
review clarified that `tsldata/extensions/extension.tsl` is the ground truth
for supported extensions and must also carry extension-specific register and
mask type facts. C++ and Rust both expose native SIMD register types for x86
and ARM, while generic vectors should be fixed-size compile-time arrays rather
than runtime-growing containers.

Decision:

Extension metadata owns vector register facts and mask policies as typed
catalog data. Native fixed-width x86 extensions use backend-aware register
spellings grouped by integer/f32/f64 selectors. NEON and SVE use concrete
per-type register entries because the native spelling depends on signedness
and scalar width. `sse_vl` and `avx2_vl` inherit register maps from `sse` and
`avx2`.

`generic` is modeled as a lane-count-parametric fixed-array policy. Rust
generic registers are fixed arrays such as `[T; LANES]`, not `Vec<T>`, and the
model avoids unstable generic const expressions that compute array length from
bit width and element size.

`mask_type_policy` and `integral_mask_type_policy` are separate facts.
`lane_bitmask` has exactly one valid bit per lane, even when a backend stores
the bits in the smallest wider unsigned type. Native predicate extensions use
backend-specific predicate types, and integral mask may intentionally be the
same native predicate type.

Consequences:

- Later selector/type lowering can consume extension facts from the catalog
  instead of hardwiring extension tables.
- Backend-specific register spellings are catalog facts, but backend rendering
  remains a later boundary.
- SVE Rust register facts are not introduced while SVE remains marked
  unsupported for Rust in extension metadata.
- Future changes to extension register or mask behavior should update
  `tsldata/extensions/extension.tsl` first, then catalog validation/tests.

## ADR-038: Current Vector Is A Domain-Typed Extension/Type Value

Status: Accepted

Context:

Primitive-call selector payload lowering needs to understand source forms such
as `@self[Vec]`, aliases bound to `Vec`, and selector entries that name
extensions. Earlier type lowering used the milestone-shaped name
`LoweredCurrentVectorType` with raw string fields. Product review clarified
that the important semantic value is the current implementation's extension
plus type tag, with the extension resolved against the extension catalog.

Decision:

`Vec` lowers to one small domain value named `CurrentVector`, with
`extension: ExtensionName` and `type_tag: TypeTag`. Source-defined aliases
preserve that same value. M144 refines the earlier
`LoweredCurrentVectorType` concept instead of adding a second selector-local
vector class.

Selector payload lowering may also produce typed extension operands, selector
symbols, selector literals, and selector attributes. These values describe the
selector payload only; they do not match primitive-call targets, select
dependency implementations, or render backend text.

Consequences:

- There is one semantic representation for the current `extension + type_tag`
  pair.
- Backend type spellings remain a later backend boundary.
- Unknown extension operands in type-valued selector expressions are
  diagnostics, not raw string fallbacks.
- Future naming cleanup should preserve the single-value rule rather than
  adding aliases that behave like parallel domain concepts.

## ADR-039: Backend Support Helper Calls Are Raw By Default

Status: Accepted

Context:

The TSIL surface inventory found `details::arith_add`,
`details::arith_mul`, and `details::arith_rem` in implementation bodies. It
was tempting to treat those helper-looking calls as semantic arithmetic
lowering islands and rewrite them to `+`, `*`, or `%`. Product review
clarified that these names are source-authored calls to predefined
backend/language support helpers, just like `details::popcount`,
`details::clz`, `details::clz_recursive`, `details::ctz`, and
`details::mask_test`.

Decision:

Lowering preserves backend support helper calls as raw source-authored text by
default. The generator must not lower `details::arith_add`,
`details::arith_mul`, or `details::arith_rem` to typed arithmetic operations
or backend operator spellings. Any future support-helper work must be selected
explicitly as backend support-library or rendering policy, not smuggled into
semantic operation lowering.

Consequences:

- `complete(details::arith_*(...));` remains an opaque unsupported return
  payload until a future milestone selects a backend support-helper rendering
  boundary.
- Helper calls inside assignments, loops, declarations, or mixed expressions
  do not force the generator to parse the surrounding target-language text.
- The missing-lowering backlog should focus on TSIL keyword families such as
  generation values, generation/backend control, backend queries, intrinsics,
  primitive calls, and body-token rendering.

## ADR-040: Generation Arithmetic Uses Explicit TSIL Functions

Status: Accepted

Context:

Generation-control conditions and loop/declaration bounds need integer
arithmetic over generation values. Raw target-language spellings such as `* 8`
or `value<generation>(vector::length) - 1` appear near TSIL islands, but
parsing those spellings would pull the generator toward a broad C/C++/Rust
expression parser. Product review also clarified that backend support helpers
such as `details::arith_mul(...)` remain raw source-authored helper calls, not
semantic generation arithmetic.

Decision:

Generation-time arithmetic must be explicit TSIL. The accepted source shape is
function-like and phase-marked:

```text
arith<generation>::add(ARG, ARG)
arith<generation>::sub(ARG, ARG)
arith<generation>::mul(ARG, ARG)
arith<generation>::div(ARG, ARG)
arith<generation>::rem(ARG, ARG)
```

These functions are lowered only inside generation-value lowering, such as
`value<generation>(arith<generation>::mul(type::size_bytes(...), 8))`. Their
arguments are recursively lowered generation values. Raw `+`, `-`, `*`, `/`,
and `%` remain source text unless a future milestone explicitly accepts a
narrow source form with tests.

Consequences:

- M158 can broaden from equality to typed integer comparisons without adding
  raw arithmetic parsing.
- M159 can add generation arithmetic as a compact generation-value function
  family rather than as operator precedence machinery.
- Backend helper calls named `details::arith_*` continue to be governed by
  ADR-039 and are not rewritten to operators or generation arithmetic facts.

## ADR-041: Shared TSIL Lexical Helpers Are Not A Parser

Status: Accepted

Context:

By M162, several accepted TSIL keyword boundaries used local copies of the
same lexical mechanics: matching balanced parentheses, brackets, braces, and
angle brackets; splitting payloads on top-level commas; finding selector
terminators outside nested brackets; and tracking raw brace depth while
discovering top-level loop regions. Duplicating this low-level scanning made
future keyword slices more fragile, but replacing it with a broad TSIL parser
would reintroduce the overengineering risk called out in the lowering
guardrails.

Decision:

M162.5 introduces one small syntax-owned helper for lexical delimiter facts
only. The helper returns character indexes, balanced-delimiter results,
top-level payload parts with offsets, and raw brace-depth updates. It does not
know TSIL keyword names, selectors, arity, source validity, diagnostics,
lowering semantics, backend rendering, or catalog state.

Keyword-specific classifiers and lowerers keep ownership of accepted source
forms. They may use the shared helper only after they have selected a narrow
lexical island such as a directive payload, primitive-call selector, type
query, generation-value argument list, or top-level loop discovery scan.

Consequences:

- New TSIL keywords are not accepted by adding the helper; each keyword still
  needs an explicit milestone, diagnostics, and tests.
- Existing source forms keep their current behavior while duplicated scanner
  code can be removed from accepted keyword modules.
- Token-region scans with domain-specific diagnostics may keep local control
  flow and use the helper only for the lexical subproblem that directly fits.
- The helper must remain dependency-light and below pipeline/lowering semantics
  in the package dependency direction.

## ADR-042: Return-Type Binding Names Are Primitive-Local Source Declarations

Status: Accepted

Context:

Current `.tsl` conversion and load/store primitives can declare a
`return_type` block with a user-defined identifier, for example
`base: ToBase` or `extension: ToExtension`. That identifier is later used in
specialization branches and TSIL type queries. Treating spellings such as
`ToBase` or `ToExtension` as generator keywords would move source-owned
meaning into hidden generator convention.

Decision:

The primitive declaration owns an optional return-type binding declaration.
The declaration records only the binding kind (`base` or `extension`), the
exact source-defined identifier, and source location. Absence of
`return_type` is normal. Concrete selected values for the declared identifier
belong to later selected-context binding work.

Consequences:

- `ToBase`, `ToExtension`, and similar names are corpus examples, not magic
  global names.
- M168.5 stores declarations only; it does not lower identifiers or bind
  selected type/extension values.
- M169 and later selection/lowering work must resolve such identifiers through
  explicit selected context supplied for the primitive declaration, not through
  raw-name guessing.

## ADR-043: Selected Specialization Values Are Explicit Target Facts

Status: Accepted

Context:

After M168.5, the generator knows that a primitive may declare an arbitrary
return-type binding name such as `base: ToBase` or
`extension: ToExtension`, but it still must not infer concrete values from
those spellings. The current corpus also uses related names such as `ToType`
inside type queries. Those values come from selected implementation facts,
not from generic source-name conventions.

Decision:

M169 models selected specialization values as explicit target facts. A target
may carry a primitive-local return-type base binding to a concrete `TypeTag`,
a primitive-local return-type extension binding to a concrete
`ExtensionName`, or an explicit vector/type binding to a concrete
`ExtensionName + TypeTag` pair. Return-type base/extension bindings validate
against the primitive-local M168.5 declaration before type lowering consumes
them.

Consequences:

- `ToBase`, `ToExtension`, and `ToType` remain source examples. Tests use
  arbitrary names such as `ResultBase` and `TargetExtension` to prevent
  spelling-based behavior.
- Type lowering can make aliases such as `OutVec` concrete when selected
  facts are supplied, enabling accepted `generic::length(...)` lowering.
- Missing, duplicate, malformed, mismatched, or wrong-kind selected bindings
  are diagnostics, not raw fallback or source repair.
- M169 does not parse implementation selector trees, expand wildcards, derive
  `ToType`, or select all possible manifestations from `.tsl` source data.

## ADR-044: Primitive-Call Selectors Consume Existing Selected Facts

Status: Accepted

Context:

M169 made selected specialization facts available to type/generation
lowering, but primitive-call selector payload lowering still classified bare
selector entries only as current keywords, aliases, catalog extensions,
literals, type-valued expressions, or raw selector symbols. That meant the
same selected fact could be visible in `type<generation>(...)` while remaining
invisible in `call<primitive=NAME[...]>(...)`.

Decision:

M170 reuses the explicit M169 selected specialization binding boundary in the
M144 selector-payload lowerer. Exact bare selector entries that name selected
bindings lower to existing selector/type values: base bindings become scalar
type identities, extension bindings become `ExtensionOperand`, and vector/type
bindings become `CurrentVector`. The selected-binding validation and
resolution helpers live in one focused lowering module shared by type-query
and selector-payload lowering.

Consequences:

- Selector payloads can consume explicit selected facts without parsing the
  full implementation selector tree or deriving values from spellings such as
  `ToBase`, `ToExtension`, or `ToType`.
- Unbound arbitrary selector names remain raw `SelectorSymbol` values.
- A primitive-declared extension binding name without a supplied selected fact
  is diagnostic, so it cannot accidentally fall through to a raw catalog
  extension or raw symbol.
- The shared helper is not a registry, dispatcher, worklist, selector engine,
  dependency scheduler, or backend rendering surface.

## ADR-045: Primitive-Call Target Matching May Decorate Matched Return Bindings

Status: Accepted

Context:

M170 made explicit selected return-type facts visible in primitive-call
selector payloads, but target matching still consumed only no selector entries
or one concrete vector entry. Current conversion data uses selector shapes
such as `call<primitive=cast[Vec, ToBase]>(...)`, where the second value must
be available to the matched target primitive under that target primitive's
own declaration name.

Decision:

M171 keeps selector parsing and selector-payload lowering unchanged, then
extends primitive-call target matching for one exact value shape: a concrete
vector selector followed by an already lowered selected return-type value.
Selector payload lowering carries minimal per-entry selected-return-binding
provenance so target matching can distinguish selected return bindings from
raw scalar type expressions or catalog extension operands that lower to the
same value classes.
After normal target selection succeeds, the resolver validates the matched
target primitive's `return_type` declaration and decorates the selected
target with either `TargetReturnTypeBaseBinding` or
`TargetReturnTypeExtensionBinding` using the matched target declaration name.

Consequences:

- Caller-local selector names do not become target-local names.
- Existing no-specialization and single-vector selector matching remains
  unchanged.
- Missing target declarations, wrong declaration kinds, raw symbols, literals,
  raw scalar type expressions, raw catalog extension operands, non-concrete
  vector entries, and broader selector dimensions remain diagnostics.
- This is not a selector engine, wildcard expander, dependency scheduler,
  renderer, source repair pass, or raw-name inference mechanism.

## ADR-046: Concrete Vector Alias Matching Consumes Typed Values Only

Status: Accepted

Context:

Current corpus bodies use `let<type>` aliases such as `StepVec`, `UVec`,
`IndexVec`, and `SignedVec` inside primitive-call selector payloads. M144 can
lower those aliases to typed vector transform values, but primitive-call target
matching previously recognized only direct `CurrentVector`, backend-wrapped
vectors, and selected `vector::as_extension(...)` values as concrete vectors.

Decision:

M172 extends the existing concrete-vector extraction helper to accept
`LoweredVectorTransformType` values only when the lowered value itself proves a
concrete extension and a concrete scalar `TypeTag`. Backend type references
wrapping scalar identities may be unwrapped. Alias names are not semantic and
are not inspected by target matching.

Consequences:

- Corpus shapes such as `cast[StepVec, ToBase]`, `reinterpret[Vec, UVec]`, and
  `load[UVec] attrs[...]` can move forward when their aliases already lower to
  concrete vector facts.
- Raw selector symbols, literals, known extension operands in vector position,
  unresolved specialization symbols, and mask/member aliases that do not expose
  a concrete scalar type tag remain diagnostics.
- M171 selected-return-binding provenance is preserved for two-entry selector
  shapes.
- This is not a selector parser, alias-name interpreter, mask/register solver,
  wildcard expander, renderer, dependency scheduler, or source repair pass.

## ADR-047: Vector Member Types Resolve Only From Explicit Fixed Metadata

Status: Accepted

Context:

Current `.tsl` bodies use vector member type queries such as
`vector::mask_underlying_t`, `vector::mask_underlying`, `vector::imask`, and
`vector::mask` in type aliases. These aliases may appear inside primitive-call
selectors, for example a `MaskVec`-style alias over
`vector::transform(type<generation>(vector::mask_underlying_t))`. M172 could
match vector-transform aliases only when their base already reduced to a
concrete scalar type tag.

Decision:

M173 resolves `LoweredVectorMemberType` values to scalar type facts only from
accepted extension catalog metadata. `vector::mask` uses `mask_type_policy`;
`vector::imask`, `vector::mask_underlying_t`, and
`vector::mask_underlying` use `integral_mask_type_policy`. Fixed
`lane_bitmask` policies resolve by deriving the selected vector lane count
from `vector_bits` and an accepted scalar descriptor for the selected scalar
type tag, then mapping that count to an exact unsigned scalar `TypeTag` that
also has an accepted scalar descriptor.

Consequences:

- `MaskVec`-style aliases can participate in primitive-call selector matching
  only when the member query resolves to a concrete scalar tag through typed
  metadata.
- Native predicate, lane-keyed native predicate, generic size-parameter,
  runtime/scalable lane, missing metadata, `unsigned_scalar` spelling-only,
  and register/member cases remain unsupported or backend-owned.
- M174 completes scalar descriptor coverage for current concrete scalar tags,
  so real fixed lane-bitmask member outputs such as `ui8`, `ui16`, and `ui64`
  can resolve through descriptor facts.
- Alias spellings such as `MaskVec`, `MaskWord`, and `MaskT` remain
  source-local and are not semantic.
- This is not backend type rendering, register spelling resolution, a
  selector engine, source parser, source repair pass, or runtime corpus lookup.

## ADR-048: Current Scalar Tags Are Explicit Descriptor Facts

Status: Accepted

Context:

M173 requires accepted scalar descriptors before vector member type queries
can produce concrete scalar facts. Current TSL type data includes concrete
integer and floating tags beyond the original clean-restart representative set:
`si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, `ui64`, `f32`, and
`f64`.

Decision:

M174 accepts those current arithmetic scalar tags as explicit lowering-owned
`ScalarTypeDescriptor` facts. Each descriptor records scalar kind, integer or
floating family, bit width, and signedness. Descriptor consumers use these
facts directly; they do not infer semantic properties from `TypeTag` spelling.

Consequences:

- Type-size, type-signedness, signed/unsigned transforms, generic length, and
  M173 fixed lane-bitmask member resolution can use the full current scalar
  descriptor set.
- Integer operation compatibility broadens to all accepted integer
  descriptors. `neg` broadens to accepted signed integer and floating
  descriptors while unsigned descriptors remain unsupported for `neg`.
- Pointer-like tags such as `ptr` remain outside scalar descriptor coverage.
- Backend C++ and Rust scalar type spellings are still backend-owned and are
  not broadened merely because lowering accepts a scalar descriptor.

## ADR-049: Generation Type Values May Consume Resolved Vector Members

Status: Accepted

Context:

M155 `type::*` generation value queries accept scalar type arguments after the
argument lowers through the type-expression path. M173 can resolve exact
`LoweredVectorMemberType` values such as `vector::imask` and
`vector::mask_underlying_t` to concrete scalar type facts from catalog
extension metadata. M174 completed the scalar descriptors needed by real
fixed lane-bitmask results such as `ui8`.

Decision:

M175 connects these existing facts without adding a new semantic layer. When a
generation value `TYPE_EXPR` argument lowers to `LoweredVectorMemberType` and
an explicit `Catalog` is available, the generation value lowerer invokes
`resolve_vector_member_scalar_type(...)`. A successful
`LoweredScalarTypeIdentity` result then feeds the same scalar descriptor lookup
used by `base::in` and `scalar::...` arguments.

Consequences:

- `type::size_bytes(...)`, `type::is_signed(...)`, and `type::is_same(...)`
  can consume fixed descriptor-backed vector mask/member type facts.
- Missing catalog metadata preserves the previous unsupported generation-value
  type diagnostic rather than inventing runtime corpus access.
- M173 missing-metadata and unsupported-policy diagnostics propagate unchanged.
- Backend type spelling, native predicate/register spelling, new vector member
  policies, new query families, renderer behavior, and broad expression
  parsing remain out of scope.

## ADR-050: Vector Member Byte Sizes Come From Fixed Metadata

Status: Accepted

Context:

M175 let `type::*` generation values consume vector member types only when the
member first reduced to a scalar descriptor. That was enough for fixed
lane-bitmask members such as AVX2 `vector::imask`, but not for
`vector::register` or lane-keyed native predicate masks such as AVX-512
`__mmask*` families. The current extension catalog already records fixed
`vector_bits` and native predicate lane-capacity metadata.

Decision:

M175.5 keeps the broad `type::*` scalar bridge unchanged and adds a focused
fixed-size resolver used only by `type::size_bytes(TYPE_EXPR)`. The resolver
accepts already lowered `LoweredVectorMemberType` values. Register size is
computed from fixed positive integer `extension.vector_bits`. `lane_bitmask`
mask size is `ceil(lanes / 8)`. `native_predicate_by_lanes` chooses an exact
or smallest sufficient lane capacity from typed extension metadata and returns
`ceil(capacity / 8)`. `same_as_mask_type` delegates to the mask policy.

Consequences:

- Size lowering uses typed extension and scalar descriptor facts, not C++ or
  Rust spelling strings.
- SVE/scalable vectors, generic symbolic `LANES`, missing catalog metadata,
  and unsupported policies remain diagnostics.
- `type::is_signed(...)` and `type::is_same(...)` still use the M175 scalar
  descriptor bridge; they do not infer register or native predicate semantics.
- This is not backend rendering, register spelling resolution, a new query
  family, source repair, or a general type-system redesign.

## ADR-051: Mask Lane Constants Are Backend Support-Helper Requests

Status: Accepted

Context:

Current `.tsl` spells mask lane constants as generation values:
`value<generation>(mask::lane::all_true)` and
`value<generation>(mask::lane::all_false)`. Corpus evidence shows 42 current
occurrences: 30 `all_true` and 12 `all_false`. They appear inside nested
primitive-call arguments, direct assignment text, and `var<const_infer>`
initializers.

Legacy behavior maps these forms to backend/support helper expressions rather
than backend-neutral booleans. C++ uses a `details::mask_true_lane_value`
style helper for `all_true` and a default constructed base type for
`all_false`; Rust uses corresponding helper/default expressions.

Decision:

The clean restart will model these exact forms as typed backend/support-helper
requests. The request records only the semantic polarity, source text, and
source location. It does not carry C++ or Rust helper text. It is not a
`LoweredGenerationValue[int|bool]` and must not be consumed as a branch
condition, loop bound, arithmetic operand, or Python boolean.

Consequences:

- The existing source mismatch remains explicit: the source uses
  `value<generation>(...)`, but the clean generator treats the two accepted
  mask lane constants as deferred backend/support-helper requests.
- Backend helper text belongs to a later backend translation/rendering rule,
  not generation lowering.
- A future executor may discover exact request islands in source-owned text and
  preserve surrounding raw text/tokens, similar in spirit to backend value
  query discovery, without parsing every surrounding call, declaration, or
  assignment form.
- Malformed, unknown, or nearby `mask::lane::*` forms remain diagnostics or
  unsupported generation-value families until explicitly selected.

## ADR-052: Supplementary Assets Are Formatting And Packaging Boundaries

Status: Accepted

Context:

After the post-M187 lowering completion gate, backend/output work needs a
clean place for generated-project scaffolding, helper source files, and render
templates. Moving hardcoded backend text out of Python is useful only if it
does not hide backend semantics inside templates.

Decision:

The clean generator will use `supplementary/` for copied or rendered output
assets:

```text
supplementary/
  buildsystem/
    cpp/
      static/
      templates/
    rust/
      static/
      templates/
  helpers/
    cpp/
    rust/
  templates/
    cpp/
    rust/
```

Static assets are byte-for-byte inputs to generated artifact sets. Template
assets format typed render contexts produced by Python backend/output stages.
Templates may use presentation logic such as loops, indentation, optional
sections, and list joining, but they must not perform backend semantic
decisions, type or intrinsic selection, feature gating, primitive selection,
TSIL parsing, dependency closure, fallback selection, or source repair.

Consequences:

- Backend semantics remain in typed rule/evaluator stages before rendering.
- Template files are output formatting infrastructure, not semantic rule
  tables.
- Helper source files under `supplementary/helpers/**` are source-authored
  backend support assets; their availability can be planned and copied, but
  their existence does not resolve TSIL semantics by itself.
- Future milestones that introduce a template engine must define typed render
  contexts and tests proving deterministic output.

## ADR-053: Machine Feature Profiles Are Build Metadata, Not Compiler Capability Policy

Status: Accepted

Context:

Generated C++ and Rust projects need an explicit way to select a target
machine/profile such as `sse2`, `avx2`, `skylake`, `zen4`, or `neon`.
Product-provided profile data groups profiles by architecture family and lists
requested feature flags plus occasional alternative spellings. The existing
`tsldata/detail/flags.tsl` data already defines the normalized feature
vocabulary used by the TSL corpus.

Decision:

The clean generator will model machine profiles as typed build metadata:
architecture family, profile name, normalized requested feature set, and
optional alternative feature spellings. Profile flags are normalized through
typed flag-normalization data from `tsldata/detail/flags.tsl`. The scalar
profile's `NOSIMD-INVALID` spelling is treated as a sentinel for no SIMD
feature flags, not as a real feature.

The generator does not decide whether a user's compiler supports the requested
feature set, nor does it choose compiler-specific command-line spellings in
the profile catalog. Host CPU autodetection, compiler capability checks, and
compile/run validation belong to explicit outer tooling or later backend build
integration, not to the pure profile catalog.

Consequences:

- Machine profile selection can feed deterministic buildsystem option/render
  contexts without making compiler-support claims.
- Alternative spellings are preserved as typed alias metadata for later
  buildsystem presentation, not treated as automatic fallbacks.
- Feature vocabulary stays grounded in `.tsl` data instead of a hardcoded
  Python list.
- Future CMake, Cargo, or compiler integration must consume these typed
  profile facts and make any compiler-specific policy explicit in a separate
  boundary.

## ADR-054: Backend Metadata Is Cataloged Before Translation

Status: Accepted

Context:

Backend/output work needs C++ and Rust type spellings and translation
templates from `tsldata/detail/lang/**`. Those files are source data, but
using them directly from renderers or as raw dictionaries would hide semantic
decisions behind string lookups.

Decision:

The clean generator will first promote active C++ and Rust backend language
maps and translation maps into typed catalog facts:
`BackendLanguageTypeSpelling` and `BackendTranslationTemplate`. Translation
template text remains inert in the metadata catalog. The catalog may provide
typed lookup helpers and missing-entry diagnostics, but it does not evaluate
placeholders, render code, translate TSIL requests, or replace existing
backend emitters by itself.

C17 language and translation files remain deferred evidence. They are not
loaded by the active backend metadata catalog until a future milestone
explicitly selects C17 as an active backend.

Consequences:

- Later backend translation stages can consume typed metadata instead of raw
  file strings.
- Missing backend type/translation entries become source-aware diagnostics.
- Template evaluation and rendering remain separate backend/output
  responsibilities with their own typed rule boundaries.
- The metadata catalog does not reopen lowering, dependency closure, machine
  profile handling, compiler support policy, or generated-project rendering.

## ADR-055: Backend Output Uses Typed Render Models, Profile Layouts, And After-Write Verification

Status: Accepted

Context:

M188 introduced the supplementary layout and in-memory skeleton artifact
rendering. M189 introduced typed machine profile metadata. M190 introduced
typed backend language and translation metadata. Before adding more backend
translation pieces, the output architecture needs a clear boundary so the
research prototype can generate code that is build-verified and so templates
do not become hidden semantic engines.

Decision:

Backend/output work follows this boundary order:

```text
catalog and selection
  -> dependency planning
  -> backend translation
  -> typed render model
  -> renderer/templates
  -> ArtifactSet
  -> ArtifactWriter
  -> BuildVerifier
```

Dependency planning owns topological primitive ordering. A backend render plan
may contain profile-specific primitive plans such as:

```text
PrimitiveRenderPlan(
    backend=BackendId("cpp"),
    profile=ProfileName("avx2"),
    primitives=(OrderedPrimitive(...), ...)
)
```

The `primitives` sequence is already dependency ordered. Renderers and
templates may iterate it, but they must not sort it or rediscover primitive
dependencies.

The typed render model is the last structured boundary before text rendering.
It contains only already-decided values: selected profile names, selected
includes/imports, already spelled types, already translated primitive bodies or
body fragments, ordered primitive records, and fixed artifact paths. It must
not contain unresolved lowering requests, raw `type<backend>(...)` text,
raw `value<backend>(...)` text, TSIL snippets needing interpretation, or
catalog objects that would let templates select semantics.

Templates are presentation-only. They may use loops, optional sections,
joining, indentation, and other formatting logic over typed render-model
fields. They must not perform backend semantic decisions, type or intrinsic
selection, feature gating, primitive selection, overload resolution,
dependency closure, TSIL parsing, fallback selection, source repair, or
compiler capability policy.

Python backend/output logic owns semantic translation and render-model
construction. Supplementary static files own fixed build scaffolding and
hand-written helper source that is copied as-is. Supplementary templates own
presentation of already-decided render-model fields. Buildsystem templates may
receive selected profile names, allowed profile choices, normalized feature
metadata, and already-prepared build option text from typed profile/build
contexts, but they must not map raw feature names, select fallback features,
test compiler support, or infer host capabilities.

A generation run writes one run-level project tree:

```text
generated/
  cpp/
    CMakeLists.txt
    include/
      tsl.hpp
      profiles/
        scalar.hpp
        avx2.hpp
        ...
    tests/
      smoke.cpp
  rust/
    Cargo.toml
    src/
      lib.rs
      profiles/
        scalar.rs
        avx2.rs
        ...
    tests/
      smoke.rs
```

C++ exposes `include/tsl.hpp` as the stable public entry point. That header
selects exactly one generated profile header according to build configuration.
The CMake project uses a modern cache string such as `TSL_PROFILE` with
declared allowed values rather than a boolean option, because profile selection
is not true/false.

Rust exposes `src/lib.rs` as the stable public entry point. It selects exactly
one generated profile module through Cargo feature or `cfg` configuration.
Rust target-feature flags are build/verifier configuration, not semantic
decisions inside `lib.rs`.

M225 realizes this by deriving target-feature spellings from the M189 feature
flag catalog and explicit profile alternatives, rendering Rust profile
target-feature values as presentation metadata in `Cargo.toml`, and having the
after-write verifier apply the same already-decided values as profile-specific
`RUSTFLAGS`. This keeps Cargo features responsible only for profile-module
selection and keeps target-feature decisions out of Rust source templates.

A generation run includes only an explicit selected profile subset. If no
profile is requested, the subset defaults to `scalar`. The reserved profile
selection value `all` means all known machine profiles from the machine profile
catalog and cannot be used as a real profile name. Build configuration selects
exactly one active profile from the generated subset.

`ArtifactSet` is a deterministic in-memory collection of files to write. It
does not know primitive dependencies, backend semantics, profile selection, or
compiler policy. The `ArtifactWriter` is the only filesystem-writing boundary.
It resolves paths under the configured output root, rejects absolute paths and
path traversal, writes deterministic bytes, and supports manifest-based
cleanup of stale generated files. Cleanup removes files previously written by
the generator according to the manifest; it does not delete unknown user files.

Build verification runs after artifact writing and verifies every generated
profile in the selected subset for each generated backend project. The project
may assume the maintained development container supplies modern C++ compilers,
Rust tooling, and QEMU support for cross-machine execution. The generator still
does not model host CPU autodetection or compiler capability as semantic input;
verification failures are reported as build/environment failures rather than
being used to repair generation semantics.

Consequences:

- Backend type, value, intrinsic, primitive-call, and source-operation
  translation can continue, but translation results must feed typed render
  models rather than renderer-local tables or template-side decisions.
- The current type-spelling translation milestone should be revisited against
  this output architecture before execution so that it contributes to a
  build-verifiable render path.
- Single-profile smoke output is no longer the target shape. The prototype
  should support an explicit generated profile subset, with `scalar` as the
  default and `all` as reserved shorthand for all known profiles.
- Future writer milestones should implement manifest-based cleanup before
  broad generated-output workflows rely on stale-file removal.

## ADR-056: Rust Intrinsic Calls Use Explicit Architecture Paths

Status: Accepted.

Context:

Rust SIMD intrinsics live under architecture modules such as
`core::arch::x86_64` and `core::arch::aarch64`. Intrinsic compose modifier
translation also produces name fragments such as `_mm256_`, but those
fragments are not complete Rust call paths.

Decision:

Rust backend rendering should emit intrinsic calls with explicit fully
qualified architecture module paths, for example:

```rust
core::arch::x86_64::_mm256_add_epi32(...)
core::arch::aarch64::vaddq_u32(...)
```

Modifier translation remains responsible only for typed intrinsic-name
fragments. It must not prepend `core::arch::*` paths, introduce imports, or
assemble final Rust call expressions. The Rust intrinsic-call renderer or
backend call-translation layer owns architecture module qualification from
typed extension/backend facts.

Current corpus evidence uses `intrin::prefix` for selected x86-family forms.
ARM/NEON/SVE intrinsic names are currently source-authored as direct names
such as `vld1q`, `vst1q`, `svld1`, and `svst1`; do not invent ARM
`intrin::prefix` mappings unless the `.tsl` corpus starts using that modifier.

Consequences:

- M198 may translate Rust prefix metadata for intrinsic-name fragments such as
  `_mm_`, `_mm256_`, and `_mm512_`, but those fragments must not contain
  `core::arch::*`.
- Import-based Rust intrinsic rendering is intentionally avoided for generated
  intrinsic calls.
- M219 realizes the first typed Rust architecture-module renderer boundary:
  Rust intrinsic-call rendering consumes an explicit `RustArchitectureModule`
  value and never string-rewrites or infers the module from rendered intrinsic
  names.

## ADR-057: No-Argument Intrinsic Suffix Uses The Current Selected Type

Status: Accepted.

Context:

After M198, the largest remaining simple intrinsic modifier family is
`value<backend>(intrin::suffix)` with no argument. The current corpus uses
this form as a source/current-type suffix in `suffix` fields and, in a few
conversion intrinsics, as an `infix` fragment. Nearby forms such as
`intrin::suffix(ToBase)` and `infix=to_type_suffix` need destination or return
type bindings and should not be guessed from raw source text.

Decision:

`intrin::suffix` with no argument means the suffix for the current selected
implementation type tag. Backend modifier translation must obtain that type
tag from typed selection/backend translation context, not by parsing the
surrounding source expression or inferring from intrinsic names. The selected
extension's intrinsic style and backend metadata continue to determine the
actual suffix fragment text.

The same current-type suffix value may be translated for both `suffix` and
`infix` modifier fields because the field name controls placement later; the
modifier translator only produces a typed literal fragment for the already
identified field.

Consequences:

- The backend intrinsic modifier context needs an explicit selected/current
  `TypeTag` for no-argument suffix translation.
- M200 translates `suffix=value<backend>(intrin::suffix)` and
  `infix=value<backend>(intrin::suffix)` through the existing metadata-backed
  suffix rule path.
- M200 must not translate `intrin::suffix(ToBase)`, `intrin::suffix("stream")`,
  `intrin::suffix(si?)`, `infix=to_type_suffix`, or symbol immediates.
- Intrinsic-name assembly and Rust `core::arch::*` qualification remain later
  backend rendering or call-translation concerns.

## ADR-058: Quoted Intrinsic Suffix Names Are Explicit Named Policies

Status: Accepted.

Context:

After M200, the only quoted intrinsic suffix argument in the accepted balanced
`intrin_compose` handoff corpus is `"stream"`, observed as
`suffix=value<backend>(intrin::suffix("stream"))`. Legacy evidence maps this
name to x86 register-width suffix fragments such as `si128`, `si256`, and
`si512`, but quoted strings in source must not become arbitrary literal
passthrough.

The raw `.tsl` corpus also contains escaped `"stream"` spellings inside quoted
TSIL strings in `conversion/cast.tsl`. The accepted M195-M200
discovery/lowering path does not currently classify those escaped spellings as
balanced modifier fields. They are evidence for a future source-island/lowering
check, not a reason for M202 to change discovery while implementing a backend
modifier rule.

Decision:

`intrin::suffix("stream")` is a named backend suffix policy only when an
execution milestone explicitly selects it. It is not a request to emit the raw
string `stream`, and it does not generalize to arbitrary quoted suffix names.

The named policy must consume typed backend modifier handoff values plus typed
backend/extension context. Python may contain typed rule records that map the
accepted policy name and selected extension to backend metadata keys, but the
suffix fragment text must live in active C++ and Rust backend metadata.

M202 may implement only the exact accepted handoff form:

```text
suffix=value<backend>(intrin::suffix("stream"))
```

Destination-bound suffixes such as `intrin::suffix(ToBase)`, semantic
`infix=to_type_suffix`, symbol immediates, intrinsic-name assembly, escaped
quoted-TSIL discovery changes, and Rust `core::arch::*` qualification remain
separate future work.

Consequences:

- Unsupported quoted suffix names must continue to produce diagnostics.
- The `infix` field must not gain quoted-string suffix behavior unless a
  future milestone explicitly selects and justifies it from typed handoff
  evidence.
- Stream suffix support should be metadata-backed for C++ and Rust, preserving
  ADR-056: Rust architecture module paths are still renderer/call-translation
  work, not modifier translation work.

## ADR-059: Return-Type Intrinsic Suffix Symbols Resolve Through Selected Bindings

Status: Accepted.

Context:

After M202, the largest remaining intrinsic modifier family uses source-owned
symbols such as `ToBase` in forms like:

```text
suffix=value<backend>(intrin::suffix(ToBase))
infix=value<backend>(intrin::suffix(ToBase))
```

`ToBase` is not a generator keyword. It is the current corpus spelling for an
arbitrary primitive-local `return_type: base: ...` binding name. Existing
selected-specialization lowering can resolve such names to a typed scalar
identity when the selected target supplies a matching return-type base binding.

Decision:

Destination or return-type intrinsic suffix translation may proceed only when
the source symbol has already lowered through typed selected binding context to
`BackendValueTypeOperand(LoweredScalarTypeIdentity(...))`.

Backend modifier translation must not interpret
`BackendValueSymbolOperand("ToBase")`, or any other raw symbol spelling, as a
destination type. Unbound or mismatched symbols remain diagnostics. Tests should
use arbitrary fixture names such as `ResultBase` to prove the rule is not
spelling-specific.

The same metadata-backed type-suffix rule may translate typed operands for
both `suffix` and `infix` fields; the field name controls later intrinsic-name
placement. This does not make `infix=to_type_suffix` a supported literal
fragment and does not add intrinsic-name assembly.

Consequences:

- M204 can implement the destination/return-type suffix slice by using the
  accepted lowering context and a narrow typed `infix` suffix rule.
- No `.tsl` implementation selector tree inference, wildcard expansion, source
  repair, or raw-name special casing is allowed.
- Symbol immediates such as `index` and `Index` remain a separate selected
  generic/immediate-parameter value problem.
- FTF-002 `intrin::suffix(si?)` remains source-data debt and must stay
  unsupported until a focused source-data cleanup milestone changes the input.

## ADR-060: `infix=to_type_suffix` Is A Selected Destination-Type Marker

Status: Accepted.

Context:

After M204, destination/return-type suffix operands are supported when the
source explicitly spells a backend suffix query, for example:

```text
infix=value<backend>(intrin::suffix(ToBase))
```

The remaining corpus also contains the exact marker:

```text
infix=to_type_suffix
```

This marker appears only in `tsldata/primitives/conversion/cast.tsl` for
NEON/SVE reinterpret intrinsic names. It is not a literal infix fragment, and
it is not a request for backend modifier translation to treat the raw string
`to_type_suffix` as magic. FTF-003 records the source-convention flaw: this is
legacy shorthand for the explicit destination suffix query, not preferred new
TSIL syntax.

Decision:

`infix=to_type_suffix` may be lowered only as an exact source marker meaning
"the suffix for the selected destination/return base type." It requires a
primitive-local `return_type: base: ...` declaration and a matching selected
return-type base binding. The arbitrary declaration name remains source-owned;
`ToBase` is an observed spelling, not a generator keyword.

Lowering must turn the marker into typed destination-type suffix information
before backend modifier translation consumes it. Backend translation must not
infer the destination type from `BackendIntrinsicModifierSymbolOperand(
"to_type_suffix")` or any raw symbol.

Consequences:

- M206 implements only the exact `infix=to_type_suffix` selected-context slice
  and reuses the existing metadata-backed suffix translation path once
  lowering has produced a typed scalar destination type.
- M206 introduces a small semantic modifier operand for the marker so
  provenance stays honest; it does not fake a `value<backend>(...)` island or
  add a broad request/result family.
- Symbol immediates such as `index` and `Index` remain a separate selected
  immediate/generic-parameter value problem.
- FTF-002 `intrin::suffix(si?)` remains source-data debt and must stay
  unsupported until a focused source-data cleanup milestone changes the input.

## ADR-061: Indexed Generic Immediates Resolve Through Primitive-Local Generic Parameters

Status: Accepted.

Context:

After M208, source-owned symbol immediates are supported when the symbol is a
selected primitive parameter whose signature term is `sImm`. The remaining
observed non-literal immediate is:

```text
immediate(1)=Index
```

in the NEON implementation of `extract_value`, whose primitive declares:

```text
prim<s:=v[idx]> extract_value(a):
  generic_params:
    Index {kind int, default 0}
```

`Index` is not a primitive parameter and must not be treated as a generator
keyword. The spelling `idx` inside `v[idx]` is a signature-term marker, not a
source-owned identifier.

Decision:

Indexed generic immediates may be lowered only through typed primitive-local
generic parameter facts. The catalog must first represent observed
`generic_params` declarations as typed facts with source provenance, including
the observed kinds `int`, `bool`, and `simd_type` and typed defaults where
present. Selected lowering context then carries the selected primitive's
generic parameters.

For the current indexed immediate slice, lowering may resolve
`immediate(N)=SYMBOL` only when `SYMBOL` matches exactly one selected
primitive-local generic parameter of kind `int` and the selected primitive
signature includes an indexed-vector term such as `v[idx]`. The backend
modifier translator must consume the resulting lowered generic-immediate
value; it must not inspect raw symbol names, generic parameter declarations,
or selected context to decide immediacy.

Consequences:

- `Index` is source-owned local data, not a global magic name.
- M208's signature-parameter `sImm` path remains separate and unchanged.
- Other observed generic parameters such as `PreserveSign`, `IndicesType`, and
  `N` become catalog facts, but M210 does not lower their uses in compile-time
  branches, primitive-call selectors, casts, array subscripts, or generic
  template systems.
- Rendering C++ non-type template parameters and Rust const generics remains a
  later backend/rendering concern.

## ADR-062: Intrinsic Invocation Assembly Precedes Language Rendering

Status: Accepted.

Context:

After M211, lowering is complete by current contract. Backend intrinsic work
has accepted request islands for direct and composed intrinsics and accepted
typed modifier translation results, but no stage yet turns those pieces into
an invocation-shaped backend/output value.

The generator needs a boundary between backend semantic translation and
language rendering. Without that boundary, C++ and Rust templates would need
to decide intrinsic name construction, immediate placement, unresolved direct
name placeholders, or argument policy.

Decision:

Backend intrinsic invocation assembly is a backend/output translation stage
before rendering. It consumes accepted intrinsic handoff requests and typed
modifier translation results, and produces typed invocation values whose
semantic pieces are already decided:

- direct or composed intrinsic kind;
- backend id;
- intrinsic name text or name parts assembled from source/metadata-derived
  typed fragments;
- opaque argument payload text and source provenance;
- typed immediate metadata for later language-specific rendering.

Argument payloads remain opaque in this stage. Assembly must not parse
target-language expressions, split intrinsic arguments, resolve primitive
dependencies, repair source, or rescan raw TSIL for lowering facts. Direct
intrinsic names that contain unresolved placeholder/template-like payloads are
diagnostic boundaries until a focused direct-name placeholder milestone is
selected.

Language renderers remain responsible for formatting an already assembled
invocation into C++ or Rust syntax. Rust `core::arch::*` module qualification,
C++ non-type template argument rendering, and Rust const generic rendering are
language rendering policies over typed invocation values, not modifier
translation or lowering behavior.

Consequences:

- M213 can implement a narrow invocation assembly boundary without turning it
  into a renderer or expression parser.
- Templates stay presentation-only because they receive already-decided
  invocation values rather than raw modifier fields.
- The same assembled invocation shape can feed later C++ and Rust renderers,
  while backend-specific metadata and typed modifier translations remain
  explicit inputs.

## ADR-063: Primitive Templates Move Before More Backend Rendering

Status: Accepted.

Context:

After M215, the backend/output path has enough C++ rendering pieces to show a
real risk: continuing with more backend-specific render snippets in Python
would gradually move C++ and Rust source structure into Python strings. The
accepted supplementary layout already reserves `supplementary/templates/cpp/`
and `supplementary/templates/rust/`, but those primitive-template directories
are currently empty except for `.gitkeep`. Existing generated-project
skeleton rendering is intentionally small and already build-verified; real
primitive rendering now needs a stronger template boundary before broadening.

Decision:

Primitive templates should be established before adding more real primitive
wrapper/body artifact rendering. Backend-facing rendering milestones should
move C++ and Rust in parity unless a prompt records a concrete temporary
exception and a nearby catch-up milestone.

Primitive template files live under:

```text
supplementary/templates/cpp/
supplementary/templates/rust/
```

They may contain language presentation structure such as includes/imports,
module or namespace layout, declaration/definition layout, indentation,
optional sections, and loops over already-decided primitive records. They must
not perform backend semantic decisions, type or intrinsic selection, feature
gating, primitive selection, overload resolution, TSIL parsing, dependency
closure, fallback selection, source repair, or compiler capability policy.

Python backend/output code owns semantic translation and typed render-model
construction. Templates format only already-decided typed render values such
as artifact paths, profile names, includes/imports, rendered signatures,
rendered body text, ordered primitive records, and translated operation text.
Fields that carry unresolved lowering requests, raw TSIL needing
interpretation, catalog objects, primitive selectors, dependency rules, or
backend metadata lookups must be rejected before rendering.

M217 establishes the primitive-template boundary and minimal C++/Rust template
files. It should not reuse the M188 `ProjectSkeletonRenderContext`, because
that context and its semantic-field guard are skeleton-specific. M218 owns the
fuller typed primitive render context needed by real selected primitive
rendering. M219 restores Rust intrinsic-call parity. M220 accepts the shared
intrinsic body-token replacement/provenance contract because it has exactly
two concrete consumers: the accepted C++ intrinsic body-token substitution
boundary and the Rust intrinsic body-token substitution boundary added in the
same focused parity slice.

The template engine is a renderer detail, not the architecture. The accepted
M188 boundary uses Python standard-library formatting. A later milestone may
introduce Jinja2 or another template engine only when a selected template
requires presentation features that the current engine cannot express, and
the same presentation-only restrictions still apply.

Consequences:

- The next executable milestone after M216 is M217 primitive template
  boundary, not another C++-only token substitution slice.
- Real primitive artifact language structure should move into supplementary
  templates before broad primitive rendering.
- M227 applies this decision to exact `v:=(v,v)` function presentation:
  catalog/lowering carries the typed signature shape, Python builds
  already-decided render values, and C++/Rust supplementary shape templates
  format the function definition before later real intrinsic fixtures consume
  that boundary.
- M238 applies the same presentation-only rule to generated-project public
  entry files, profile source files, and smoke tests. Python may compute typed
  values and join already-rendered supplementary partials, but it must not
  assemble whole generated C++/Rust source skeletons from language-line lists.
- Small Python strings remain acceptable for typed already-decided render
  values and focused tests, but they must not become hidden C++/Rust
  templates or semantic engines.
- Shared token replacement work must name concrete consumers before adding a
  shared contract, avoiding another broad dispatcher/worklist abstraction.

## ADR-064: M228 Restart Uses A Declaration Parser Boundary Before Real Fixture Expansion

Status: Accepted.

Context:

The first M228 attempt was moved to the `m228-spike` branch as evidence. It
proved that the observed `add`/`avx2` fixture is reachable, but it also
recreated the same risk the restart is meant to avoid: parser, catalog,
lowerer, and generated-project bridge changes grew together, with exact
regular-expression additions and raw-body fallbacks scattered through already
large modules.

Outer `.tsl` declaration syntax is not TSIL. Primitive declarations,
attributes, optional `return_type`, optional `generic_params`, nested `impls`
extension/type selectors, `requires`, and `implementation` body envelopes
should be parsed as source declarations with spans. The body payload inside
`tsil "..."` or `tsil """..."""` remains source-owned body text that is later
segmented into raw spans and accepted lowerable token islands.

Decision:

M228 restarts from the accepted M227 baseline. Before implementing the real
x86 intrinsic fixture, it must establish or select a focused outer TSL
declaration parser boundary. A grammar parser such as Lark is the preferred
candidate because the redesign docs already identify `tsl_data.lark` and the
legacy grammar is usable evidence; however, the executor may choose another
parser only if it gives simpler typed declarations, source spans, diagnostics,
and maintainability for the current corpus.

The parser boundary must not become a broad TSIL parser. It parses declaration
structure and preserves TSIL bodies as raw payload spans. Lowering may then use
a separate body/token boundary to identify exact lowerable islands needed by
the selected fixture. Because multiple TSIL keywords may carry single-line or
multiline balanced payloads and body regions, that boundary should reuse or
extend the accepted lexical-only helper pattern from M162.5 instead of making
a `complete(...)`-only extractor. Keyword-specific lowerers still own the
meaning, diagnostics, and accepted source forms for each recognized region.

Consequences:

- The `m228-spike` branch is evidence only; do not cherry-pick or copy it
  wholesale.
- The active M228 prompt must require a parser-choice preflight and a
  module-size pressure check before implementation.
- If outer declaration parser work is too large to fit beside the exact x86
  fixture, the executor must stop and create a parser-boundary milestone before
  rendering the fixture.
- New support for multiline TSIL keyword islands belongs in a focused
  source-body/token lexical boundary that can be shared by keyword lowerers,
  not as a general raw-string repair path or a `complete(...)` special
  case hidden inside `Lowerer`.
- Existing TSIL lowerable token semantics, backend translation, templates, and
  generated-project rendering remain separate boundaries.

## ADR-065: Defer The First Real X86 Fixture Until Parser And Body Foundations Are Explicit

Status: Accepted.

Context:

After ADR-064, a sideways M228.5 parser/body attempt was preserved on the
`m2285-sideways-parser-body-attempt.patch` branch and removed from the active
worktree. That attempt did not become accepted implementation. It confirmed
that the first real `fundamental.tsl` `add`/`avx2` fixture is not just a small
rendering slice. It pulls outer `.tsl` declaration parsing, nested `impls`,
wildcard type selectors, concrete selection context, multiline TSIL body
tokenization, lowerable token extraction, backend translation, function
rendering, generated project writing, and build verification into one path.

Decision:

Do not continue directly from M227/M228 into real x86 fixture lowering or
rendering. Before the fixture path resumes, run a planning/foundation
milestone that decides the outer TSL declaration parser strategy and the
source-body tokenization boundary.

The foundation milestone must use `tsldata/**/*.tsl` as evidence for observed
outer declaration forms, but it must not implement broad parser code. It must
decide whether the next executable parser slice should use a grammar parser
such as Lark, a smaller typed declaration parser for a selected subset, or
another explicit inventory/foundation step.

Consequences:

- The `m228-spike` and `m2285-sideways-parser-body-attempt.patch` branches are
  evidence only, not implementation to copy.
- The active next prompt is a planning prompt, not a fixture implementation
  prompt.
- Future parser work must avoid regex accretion in `parser.py` and must keep
  outer TSL declaration parsing separate from TSIL body-token lowering.
- Real fixture rendering may resume only after the parser/catalog and
  source-body boundaries are explicit enough to avoid bundling the fixture
  with foundational parser work.

## ADR-066: Outer TSL Declarations Get A Lark-Backed Parser Boundary Before Body Lowering Resumes

Status: Accepted.

Context:

M228.5 planning audited the real `tsldata/**/*.tsl` corpus after the M228 and
sideways M228.5 attempts were preserved as evidence. The observed primitive
fixture path does not only need a TSIL body token. It first needs outer TSL
source structure: `prim<...>` declarations with signatures and attrs,
primitive child fields, nested `impls` selector trees, `requires` forms,
`implementation:` entries, and inline or multiline `tsil` payload envelopes.
Catalog/detail files also contain `types`, `flags`, `template`, `extension`,
`lane_set`, `language`, and `translation` blocks.

Primitive declaration shape is anchored by the top-level
`prim<...> name(...):` header, but the declaration fields below that header
are semantically order-insensitive. Fields such as `brief_description`,
`operation`, `tests`, `generic_params`, `return_type`, `sImm_type`, and
`impls` may occur in any order. The parser may preserve source order for
diagnostics and provenance, but it must not require a fixed field sequence.

The current clean `parser.py` is already a large regular-expression parser
for tiny fixture shapes, and `lowerer.py` is also large. Adding another
selected-fixture parser bridge would repeat the same accretion pattern that
caused the M228/M228.5 resets.

Decision:

The next executable parser slice is a Lark-backed outer TSL declaration parser
boundary. The target architecture already reserves
`syntax/grammar/tsl_data.lark`, and the legacy grammar is useful compact syntax
evidence, but the clean implementation must own its grammar, dependency, typed
transform, spans, and diagnostics. M229 must not use a regex parser,
hand-written parser, or alternative parser for this boundary. If using Lark
would require an undeclared runtime dependency or grammar package-data behavior
that cannot be made explicit in the clean package, the executor must stop and
create a dependency/package-boundary prompt rather than adding hidden
dependency behavior.

Parsed outer TSL values exposed past parser internals must be typed
dataclasses. They should use `@dataclass(frozen=True, slots=True)` following
the repository convention unless a concrete local exception is documented in
the milestone result. Parser-private dictionaries may exist inside a transform
if useful, but raw dictionaries must not be the public parsed field model.

The outer parser ends at the implementation body envelope. It may parse the
`tsil` envelope, quote form, source location, and raw payload span, but it must
not parse or interpret `complete`, `intrin_compose`, TSIL control keywords,
expressions, operators, backend intrinsic semantics, or source-operation
semantics. Those belong to a later shared lexical body-region layer and
keyword-specific lowerers.

Consequences:

- M229 implements only the outer declaration parser/catalog boundary.
- The first real x86 fixture remains deferred until after M229 and a focused
  source-body lexical-region milestone.
- Existing tiny pipeline code may continue using the old narrow parser until a
  later integration milestone deliberately replaces it.
- New parser work should live in focused syntax modules and grammar assets,
  with only narrow public-surface edits to existing modules.
- `parser.py`, `lowerer.py`, and `generated_primitive_pipeline.py` must not
  receive new fixture-specific regex fallback logic in M229.
- TSIL payload text remains source-owned raw text until accepted body/token
  lowerers consume exact lexical regions.

## ADR-067: Primitive Profile Artifact Wrappers Are Template-Backed Presentation

Status: Accepted.

Context:

M240 proved that synthetic already-lowered intrinsic handoff values can render
primitive profile artifacts, compose into the generated project skeleton, write
through the artifact writer, and verify through C++/Rust build commands. That
path exposed one remaining presentation leak: primitive replacement artifacts
must carry the profile-file wrapper expected by generated smoke tests, but
accepted tests and the tiny generated pipeline still supplied pieces of that
wrapper as C++/Rust strings in Python.

The wrapper is broader than the active-profile constants. It includes C++
include lines, namespace/profile metadata, root active-profile constants,
Rust imports, Rust profile constants, and the placement of already-rendered
primitive declarations/definitions inside the profile file.

Decision:

Primitive profile artifact wrappers are a backend/output presentation boundary.
They live under:

```text
supplementary/templates/cpp/primitive_profile/
supplementary/templates/rust/primitive_profile/
```

Python supplies typed generated-profile render values and already-rendered
primitive presentation values. The primitive-profile templates format wrapper
presentation only. They do not select primitives, compute dependencies,
evaluate TSIL, choose intrinsic/type spellings, inspect catalog objects, or
repair source. Template fields that look like unresolved semantic/source data
must be rejected before rendering.

The existing primitive-template renderer remains the final file formatter for
profile artifacts where useful; the new primitive-profile boundary prepares
the wrapper values that feed it. Existing renderer bridges may delegate to the
primitive-profile boundary when they have a selected typed profile model, but
they must not grow into selection, parsing, dependency planning, or generated
project orchestration.

Consequences:

- M241 moves active-profile constants and profile-file wrapper text out of the
  tiny generated pipeline and focused intrinsic verification fixtures.
- Future primitive profile artifacts should be built from typed profile facts
  plus already-rendered primitive declarations/definitions, not ad hoc
  namespace/module/include/import strings in Python.
- C++ and Rust profile wrapper behavior stays in parity.
- The first real x86 fixture can now reuse the profile artifact wrapper
  boundary instead of rediscovering profile scaffolding in a fixture-specific
  pipeline.

## ADR-068: Fixture Names Must Not Become Pipeline Architecture

Status: Accepted.

Context:

M243 and M244 proved an important end-to-end backend/rendering behavior from
real `tsldata` evidence: a selected real primitive implementation can be
parsed, accepted through a narrow exact body boundary, rendered through C++
and Rust templates, written through `ArtifactWriter`, and build verified.
However, the implementation named that bridge
`tslgen.pipeline.real_scalar_pipeline`. The selected `scalar` profile is
source data from TSL files, not a durable pipeline owner.

The same problem exists from the other direction with
`generated_primitive_pipeline.py`: its name sounds generic, but it is the M224
tiny regression/demo path built around `TslParser`, tiny fixtures, local
scalar/operator spelling tables, and `LoweredBinaryOperationExpression`.

If selected fixture details become module or public API ownership, future work
will naturally grow sibling paths such as `real_avx2_pipeline.py`,
`real_neon_pipeline.py`, or `real_add_pipeline.py`. That repeats the
unmaintainable special-case architecture the redesign is meant to avoid.

Decision:

Fixture details may appear in tests, selected-entry defaults, exact body
adapters, and documentation of supported slices, but not as production
pipeline ownership. Primitive names, extension/profile names, type tags,
signature spellings, and exact implementation-body shapes must flow as typed
selected data through generic generator boundaries.

Production pipeline modules and public APIs should be named after stable
responsibilities such as selected primitive project generation, catalog
building, backend translation, render planning, artifact writing, and build
verification. A module whose name is derived from a selected primitive,
extension/profile, type tag, signature, or exact body form requires a
fixture-name pressure check. If another similar feature would imply a sibling
module with the same shape, the next milestone must consolidate or rename the
boundary before adding feature work.

Regression/demo paths must be labelled honestly and isolated from real
generator architecture. They must carry an explicit deletion or replacement
follow-up once the generic real path covers their regression value.

Consequences:

- M244.5 is inserted before M245 to replace `real_scalar_pipeline.py` with a
  generic real selected primitive project bridge.
- `generated_primitive_pipeline.py` remains M224 tiny/regression-only and must
  be labelled as such until it is deleted.
- M245 vector register type spelling remains useful, but is deferred until the
  generic real primitive project bridge exists.
- Future milestones must not add sibling fixture pipelines for specific
  extensions, primitives, type tags, signatures, or exact body forms.

## ADR-069: Extension-Owned Default Intrin Compose Naming Policy

Status: Accepted.

Context:

`intrin_compose<BASE>(...)` is intended to express backend intrinsic names
that follow regular extension-specific patterns such as backend prefix plus
base operation plus type suffix. Explicit modifier fields such as
`prefix=...`, `infix=...`, and `suffix=...` are already typed source facts,
but unqualified forms such as `intrin_compose<add>(left, right)` need a
default naming policy.

That default policy is extension metadata. It must not be inferred in the
renderer, hardcoded in Python lookup tables, or recovered from legacy code.

Decision:

`tsldata/extensions/extension.tsl` owns default `intrin_compose` naming policy
using this source shape:

```tsl
intrinsic_compose:
  prefix:
    cpp "_mm256_"
    rust "core::arch::x86_64::_mm256_"
  suffix:
    by_type:
      f32 "ps"
      f64 "pd"
      si8 "epi8"
      si16 "epi16"
      si32 "epi32"
      si64 "epi64"
      ui8 "epu8"
      ui16 "epu16"
      ui32 "epu32"
      ui64 "epu64"
```

Suffix entries are concrete per `TypeTag`, not wildcard or type-group rules.
Rust module qualification remains in the backend-specific `prefix` metadata,
for example `core::arch::x86_64::_mm256_`.

Source-provided modifiers always override defaults. If a source
`intrin_compose` request provides `prefix`, `infix`, or `suffix`, the backend
uses the translated source modifier for that name part and does not apply the
extension default for the same part.

Missing default policy, missing backend prefix, missing type suffix, unknown
extension, unsupported backend, and malformed policy source are diagnostic
boundaries. The generator must not guess backend intrinsic names.

Consequences:

- M246 implements typed parsing/promotion of extension-owned default compose
  policy and backend invocation assembly support for missing default
  prefix/suffix parts.
- Explicit modifier translation from earlier milestones remains authoritative
  and override-capable.
- Real vector/intrinsic generated-project rendering can consume this policy in
  a later milestone without embedding intrinsic naming rules in templates or
  fixture-specific pipelines.

## ADR-070: Selected Implementation Context At Body-Token Render Boundary

Status: Accepted.

Context:

M246 made default `intrin_compose` naming policy extension-owned, but body-token
rendering still needed selected backend, extension, type tag, and extension
catalog context to consume that policy. That context already exists at selected
implementation/project-pipeline boundaries; rendering must receive it as typed
data instead of rediscovering it from TSIL source text, fixture names, or
template conditionals.

Rust adds one extra boundary concern: extension metadata may provide a full
`core::arch::*` prefix, while older direct Rust intrinsic rendering prepends a
typed architecture module. The renderer needs an explicit typed mode for
already-qualified intrinsic names so policy-owned Rust prefixes are not
double-qualified.

Decision:

Selected implementation context at body-token rendering is represented as a
direct typed value carrying backend id, selected `ExtensionName`, selected
`TypeTag`, and `ExtensionCatalog`. The existing intrinsic body-token bridge
consumes that context and resolves default compose policy only when a composed
request is missing a source-provided prefix or suffix.

Default policy resolution is part-specific. If only the prefix is needed, the
bridge requests only the prefix; if only the suffix is needed, it requests only
the suffix. Explicit source modifiers remain authoritative and do not force
diagnostics for default parts they already replace.

Rust intrinsic call rendering uses a typed `RustIntrinsicNameQualification`
value. `ARCHITECTURE_MODULE` preserves the existing unqualified-name path, and
`ALREADY_QUALIFIED` renders the assembled name without adding a module. This
mode is chosen by the typed render context/default-policy path, not by
inspecting intrinsic-name strings.

Consequences:

- M247 propagates selected implementation context through the existing
  intrinsic body-token bridge; it does not add a sibling fixture bridge.
- M246 extension-owned policy can now drive C++ and Rust body-token rendering
  without Python intrinsic spelling tables or template-side semantic logic.
- M248 connects real selected primitive rendering to this bridge through the
  generic selected primitive project pipeline, using the same selected context
  and M245 type spelling boundaries.

## ADR-071: Rust Intrinsic Unsafe Body Boundary Is Typed Render Context

Status: Accepted.

Context:

M249 proved the real selected `add` `avx2/f32` generated project through
after-write C++ and Rust build verification. The generated Rust profile uses
the correct extension-owned `core::arch::x86_64::__m256` type spelling and
fully-qualified `core::arch::x86_64::_mm256_add_ps(left, right)` intrinsic
call. Rust still requires target-feature intrinsic calls to occur inside an
unsafe call boundary even when build verification supplies target-feature
flags through `RUSTFLAGS`.

That safety presentation is a backend render concern over already-lowered
intrinsic body-token output. It must not be inferred by inspecting intrinsic
name strings such as `_mm256`, by looking for `core::arch::*` text, by
repairing source bodies, or by pushing safety decisions into templates.

Decision:

Rust intrinsic body safety is represented by a typed render-context value. The
intrinsic body-token bridge can render an accepted Rust body token stream as
plain body text or wrap it in an unsafe block when the caller supplies the
typed unsafe policy. The generic selected primitive project pipeline requests
the unsafe policy for Rust already-lowered intrinsic body-token output in the
selected real project path.

Templates may format the already-decided body text they receive, but they do
not decide whether an intrinsic call is unsafe. The policy does not change
lowering, intrinsic name assembly, Rust module qualification, target-feature
build flag selection, or host/compiler capability modeling.

Consequences:

- M249 keeps Rust AVX2 intrinsic build verification in parity with C++ without
  introducing intrinsic-name heuristics or template-side semantics.
- Future Rust backend slices can reuse the same typed safety boundary for
  already-lowered intrinsic body-token output.
- Broader Rust safety policy, target-feature attributes, or function-level
  unsafe presentation remain future explicitly selected backend/render work if
  real generated shapes require them.

## ADR-072: Source-Provided Intrin Compose Modifiers Translate Before Rendering

Status: Accepted.

Context:

Real selected primitive bodies can provide explicit `intrin_compose` modifiers
whose values are themselves typed backend/generation queries. The real AVX2
integer `add` implementation provides a `suffix=value<backend>(...)` modifier
whose suffix argument lowers through generation type queries, including
`base::signed_of(base::in)`.

By M249, selected primitive project rendering carried selected backend,
extension, type tag, backend metadata, and extension catalog context to
intrinsic body-token rendering for default compose policy. However,
source-provided modifier facts also need to be translated before invocation
assembly. The renderer must not rediscover them from raw source text, infer
them from wildcard selectors, or embed suffix tables.

Decision:

The generic selected primitive project pipeline translates already-lowered
`BackendIntrinsicComposeHandoffRequest` modifier fields before calling the
intrinsic body-token bridge. Translation uses the accepted backend intrinsic
modifier boundary with selected backend id, selected `ExtensionName`, selected
concrete `TypeTag`, `BackendMetadataCatalog`, `ExtensionCatalog`, and the
typed lowered modifier operands already present in the handoff.

Only `intrin_compose` request segments with modifier fields are translated.
Direct intrinsic requests and compose requests without explicit modifiers
continue through the existing body-token/default-policy path.

Selector wildcard text such as `?i?` is source selection evidence only. It is
not rendered or translated as the selected current type. If a source-provided
modifier asks for a transformed type such as `base::signed_of(base::in)`, the
lowered typed operand determines the suffix translation. This is why an
unsigned selected type such as `ui8` may render the signed intrinsic suffix
`epi8` when the source modifier explicitly requested it.

Consequences:

- M250 proves the boundary with the real `add` `avx2/?i?` integer matrix for
  C++ and Rust generated-project build verification.
- Explicit source modifiers and extension-owned defaults now compose through
  the same generic selected-project path.
- Future selected primitive matrices can broaden coverage without adding
  pairwise keyword handlers, fixture-specific pipelines, raw source-string
  matchers, template-side semantic logic, or Python-owned suffix tables.

## ADR-073: Source Body Fragments Supersede ImplementationBody Token Scanning

Status: Accepted.

Context:

M254 proved that the recursive source-body fragment boundary can recognize the
real generic unmasked `add`/`sub` body shape, including nested TSIL keyword
regions inside loop bodies and primitive-call selectors. The codebase still has
an older `ImplementationBody.tokens` layer whose lowerers independently scan
body tokens for variables, loops, type/value queries, masks, intrinsics, output
requests, source operations, and backend control.

Keeping both layers as production source-discovery mechanisms is high risk. It
invites pairwise keyword-combination handling, duplicate keyword spelling
ownership, and repeated drift back toward source-string scanners. However, the
older layer also contains accepted typed semantic evaluator behavior that must
not be lost casually.

Decision:

`SourceBodyFragmentSequence` or a pure source-body successor is the canonical
owner of TSIL implementation-body structure. TSIL keyword regions are discovered
once through the shared recursive fragment boundary. Semantic lowerers consume
typed facts derived from those fragments; they must not independently rediscover
source regions by scanning `ImplementationBody.tokens` or raw source strings.

`ImplementationBody` is now explicit removal debt. The workflow inserts an
M254.x consolidation series before M255. M254.1 starts by making the
fragment-first boundary the production body-lowering entry point and by
quarantining or deleting old token-scanning paths. Follow-up M254.x milestones
must continue reducing references until production code and tests no longer
depend on `ImplementationBody`.

Temporary compatibility adapters are allowed only when they reduce the remaining
dependency and record the next removal step. They must be named and documented
as compatibility/deprecation paths, not as new architecture.

Consequences:

- M255 real generic self-call selector specialization lowering is deferred
  until the source-body ownership correction has started.
- Future TSIL keyword work must add one fragment-based semantic consumer, not
  one handler per surrounding keyword combination.
- Existing typed semantic behavior may be reused, but source discovery moves to
  the fragment-first model.
- Lexical region heads may recognize selector families broadly when needed to
  route accepted diagnostics, but semantic lowerers still own supported
  selector sets and must not treat lexical recognition as new semantics.
- Primitive-call reference inventory consumes recursive fragments first, but
  primitive-call argument payloads remain opaque until a future milestone
  explicitly changes dependency semantics.
- Selected-implementation discovery APIs should consume the typed selected
  lowering context directly. Passing a separate `ImplementationBody` through
  already migrated discovery families is compatibility debt, not production
  architecture.
- Direct lowerer and primitive-call diagnostic APIs should consume
  fragment-derived token/source views or explicit token tuples. Constructing or
  passing `ImplementationBody` inside lowering is compatibility debt and should
  not reappear.
- Once a selected implementation carries `source_body_fragments`, compatibility
  `ImplementationBody.tokens` must not override fragment-derived direct-body
  tokens. Token-only fallback is allowed only for selected implementations that
  do not yet carry fragments.
- Backend rendering, dependency closure, source repair, assignment/index
  parsing, and target-language expression parsing remain outside the M254.x
  cleanup series unless a later prompt explicitly selects them.

## ADR-074: Vector Type Query Names Expose Changed Axes Explicitly

Status: Accepted and implemented in `tslc`/`tsldata`.

Context:

The TSL source vocabulary previously had vector type queries whose names did
not make the transformed axes obvious. In the observed corpus, one-argument
`vector::as_extension(ext)` meant "same base, named extension". The old
two-argument `vector::as_extension(ext, base)` meant "named extension, named
base". The old `vector::transform_extension(base)` meant "same current
extension, named base" despite the name mentioning extension transformation.

This ambiguity matters because primitive bodies use these queries to express
selected vector aliases such as output vectors, chunk vectors, and scalar or
generic fallback call targets. The source language should make the changed
axis explicit before lowering, dependency planning, or backend rendering
consume the query.

Decision:

`vector::as_extension(ext)` remains the spelling for "same base, named
extension".

The same-extension base-change operation is named `vector::as_base(base)`.
This is the semantic replacement for the current
`vector::transform_extension(base)` spelling.

The two-axis operation is named `vector::as(ext, base)`. This is the semantic
replacement for the current two-argument `vector::as_extension(ext, base)`
spelling.

The two-argument `vector::as_extension(ext, base)` form must not be collapsed
to `vector::as_base(base)`, because that would discard the explicit extension
argument. Any compatibility support for the old spellings is migration debt and
must remain in the source/query boundary. It must not leak into backend
rendering or intrinsic-specific lowering.

Consequences:

- The vector query vocabulary exposes the changed axes directly:
  extension-only, base-only, and extension-plus-base.
- The lowerer can map all supported spellings to the same typed vector-query
  value without embedding intrinsic names or backend details.
- The `tsldata` source spellings are migrated to the new vocabulary, and
  focused query tests cover accepted forms plus rejected old arities.
- Backend translation and rendering remain consumers of typed vector values;
  they do not decide which vector axis changed.

## ADR-075: Diagnostics Carry Domain Provenance Past Parsing

Status: Accepted and implemented in `tslc`.

Context:

The parser already records source spans for outer TSL declarations and body
payloads, but selector, catalog, and lowerer diagnostics historically lost that
provenance after promotion. Later stages often constructed diagnostics from
semantic objects or selected implementation state without a file/line/column,
making errors and coverage skips difficult for `.tsl` authors to act on.

At the same time, downstream stages should not depend on parser-private AST
span types. The source-body scanner also needs to identify exact TSIL keyword
islands inside a quoted implementation payload, but that must remain lexical
provenance, not a broad TSIL parser or source repair mechanism.

Decision:

Introduce a stable domain provenance value, `SourceSpan`, separate from
parser-boundary span objects. Parser/catalog promotion converts parser spans
into optional `SourceSpan` fields on source-authored domain objects such as
primitives, implementations, signatures, selectors, bodies, immediate
parameters, and generic parameters. Hand-built fixtures may omit these fields.

Keep `Diagnostic.location` as the public point-location contract for now.
Diagnostic helpers derive that point from `SourceSpan.start`; this records
actionable source locations without introducing diagnostic notes, secondary
locations, or a new reporting framework.

The TSIL body scanner may accept an optional body `SourceSpan` and attach
optional spans to lexical `RawText` and `Region` segments. Nested payloads,
blocks, and switch arms compute spans relative to the original body payload.
Lowering handlers use `Region.source` for handler diagnostics, so diagnostics
for unsupported or unresolved TSIL islands point at the exact island when
known. The scanner still owns only lexical region discovery; keyword handlers
own semantic support and diagnostics.

Consequences:

- Source-authored catalog, selector, and lowerer diagnostics can report
  actionable file/line/column locations after parsing.
- Parser-private AST span types do not leak into catalog, selector, lowering,
  or handler APIs.
- Exact TSIL island locations are available for handler diagnostics without
  parsing TSIL as a complete expression or statement language.
- Generated text, selection, dependency closure, lowering semantics, rendering,
  and source bodies remain unchanged by provenance threading.
- Diagnostic notes, secondary locations, CLI request provenance, build
  verifier/output writer locations, source repair, and broad diagnostic
  framework replacement remain future explicitly selected work.

## ADR-076: Lowered Bodies Carry Typed Render Values

Status: Accepted and implemented in `tslc`.

Context:

The active `tslc` lowerer had already moved many semantic decisions into typed
selection, query, and lowering objects, but the final body handoff still used a
raw `body_text` string. Rust overloaded rendering then rewrote that string to
reinterpret `Self` as the concrete SIMD vector, and backend template rendering
performed unchecked placeholder replacement. Those paths made semantic
decisions easy to hide inside renderer string operations.

Decision:

Lowering produces a typed lowered-body value. Literal text is explicit terminal
text, while semantic rebinding points such as current vector, current register,
current base, current mask, and current imask type are represented as typed
render placeholders. Backend renderers may supply a render context for cases
where presentation context changes, such as Rust argument-dispatch impls, but
they must not rediscover or rewrite semantic spellings from body strings.

Nested TSIL region rendering must preserve typed render fragments. A handler may
render a fragment to a concrete string only when it is intentionally consuming a
generation-time key, selector, count, intrinsic suffix, or diagnostic value.
Expression bodies, declaration initializers, casts, calls, memory/mask template
fields, templates, and control-flow bodies pass typed render values across
handler boundaries.

`let<type>` aliases that resolve to backend spellings are stored in lowering
scope as typed render values. Raw source chunks are tokenized at the source-body
boundary so alias occurrences become typed render fragments instead of a final
whole-body string substitution. Query evaluation also resolves those aliases for
type positions such as `cast<static>(CountT, ...)`.

Backend translation templates render through a validated template application:
all declared placeholders must be supplied and unresolved placeholders must not
survive formatting. Template rendering remains a formatting boundary over typed
fields; it must not choose types, intrinsics, mask policies, dependency
closure, source repair, or backend fallback behavior.

Rust unsafe wrapping and accepted bitwise-not presentation are lowered into the
typed body value before backend project rendering. Source bodies use the
explicit `bit_negate(expr)` TSIL keyword for bitwise complement; the backend
syntax dialect renders that semantic operation as `~` in C++ and `!` in Rust.
Generic raw-text lowering does not inspect `~` and does not branch on backend
ids. Existing `body_text` access stays as a compatibility property that renders
the default lowered body.

Consequences:

- Renderer-side semantic rewrites such as concretizing Rust `Self` in body text
  are disallowed.
- Raw source/body fragments may survive only as explicit literal render text
  after TSIL regions have either lowered or produced diagnostics; source-boundary
  alias tokenization is the only accepted text-to-typed-fragment conversion.
- Existing generated C++ and Rust behavior remains stable; text differences are
  limited to the intentional `bit_negate(expr)` presentation cleanup.
- Broader expression/statement IR is still not introduced by default; future
  body semantics should add typed render values only where they remove real
  string-side semantic decisions.

## ADR-077: TSLc Catalog And Profile Validation Gates Generation

Status: Accepted and implemented in `tslc`.

Context:

The active `tslc` parser and catalog builder preserve enough structure to build
typed domain objects, but malformed source data could still reach selection,
lowering, or backend creation. Duplicate source keys were especially dangerous
because later promotion naturally keeps only one value, and unsupported backend
requests could fail as plain Python exceptions instead of structured user
diagnostics. Machine profile loading had similar risks around duplicate JSON
keys, unknown fields, and malformed shapes.

Decision:

Add an explicit catalog/profile validation boundary after parsing and catalog
promotion, before selection, lowering, or backend construction. The catalog pass
uses typed catalog data for coherence checks such as required backend type
spellings and extension inheritance, and uses the parsed tree where source shape
is needed for duplicate keys, unknown fields, enum-like strings, and malformed
`requires` maps. `requires` validation is structural; it does not try to become
feature selection or profile matching.

Keep `tslc.catalog.validation` as a package with a narrow public
`validate_catalog(...)` facade. Split catalog invariants, parsed-source schema
checks, structural `requires` checks, and parsed-span helpers into focused
private implementation modules so future validation rules do not accumulate in a
single catch-all file.

Machine profile loading returns a typed load result with profiles plus
diagnostics. It validates JSON shape, duplicate object keys, duplicate profile
names, allowed profile families, allowed profile fields, flag string shape, and
alternative spelling shape. The pipeline accumulates these diagnostics and stops
on errors before creating backend dialects or selecting implementations.

Consequences:

- Malformed catalog/profile data fails at a deterministic admission boundary
  with stable diagnostic codes.
- Duplicate source and JSON keys no longer silently overwrite without a
  diagnostic.
- Selection, lowering, and rendering continue to consume typed catalog/profile
  objects rather than raw parser dictionaries.
- Exact legacy diagnostic wording is not preserved; actionable code, severity,
  and location are the contract.
- Profile JSON structural diagnostics currently use root file locations except
  for JSON parse errors; finer JSON key locations remain a future diagnostic
  enhancement.

## ADR-078: TSLc Support Policy Uses Catalog Capabilities, Not Extension Identities

Status: Accepted and implemented in `tslc`.

Context:

The active `tslc` selector, lowering, query evaluation, render naming, and
backend renderers had accumulated small local support decisions: supported
backend ids, supported extension families, signature kinds, mask-policy split
forms, immediate split forms, variadic skips, representation-change target
rules, and sized-vector behavior. Several of those decisions were expressed by
checking the source extension spelling `generic`, which made compiler behavior
depend on one corpus extension identity instead of on typed extension
capabilities.

Decision:

Introduce `tslc.support_policy.SupportPolicy` as the single small capability
object for the current prototype support surface. It owns supported backend
ids, emitted extension families, supported signature kinds, maskable signature
forms, mask suffixes, immediate and variadic kinds, pointer/index kinds,
target-marker values, and explicitly deferred cases.

Keep catalog-derived scans outside that object. `tslc.support_policy_views`
owns deterministic views that need catalog traversal, including selectable
primitive variants, mask/immediate split-name discovery, and representation
target candidate filtering. This keeps `SupportPolicy` as facts and predicates
over typed values rather than turning it into a catalog query facade.

Promote the minimal extension capability facts needed at the catalog boundary:
`vector_bits_kind`, `size_parameter_name`, `vector_register_type_policy`, and
`intrinsic_style`. Selection, lowering, query evaluation, and renderers ask the
policy or its catalog views capability questions such as whether an extension
uses a sized-vector substrate, whether a variadic signature should be skipped
for that extension, whether a register is represented by the base type, and
which representation-change target dimensions are currently supported for sized
vectors.

Backend renderers may still spell the generated static sized-vector substrate
required by the current C++/Rust support assets, but they receive that need as
lowered capability data (`uses_sized_vector`, lane parameter, target facts)
rather than inferring it from a source extension name.

Backend-specific syntax limits remain backend dialect capabilities. For example,
lowering asks whether the backend can spell symbolic sized-vector lane
expressions instead of branching on a backend id.

Consequences:

- Adding or renaming source extensions should not require new behavior checks
  against extension identities in selection, lowering, query evaluation, or
  backend renderers.
- `SupportPolicy` stays small and import-light; catalog scans live in the
  adjacent view module and can grow or split independently when catalog
  selection rules become richer.
- Lowering should not branch on backend ids for behavior; it should ask the
  selected backend dialect for explicit capabilities.
- Current deferred cases remain explicit: sized-vector variadic fallback loops,
  sized-vector extension-dimension representation changes, masked
  gather/scatter forms, masked scalar reductions, unsupported extension
  families, and different-width reinterpret targets.
- The catalog still admits source names such as `generic` and `scalar`; those
  are source data, not compiler policy branches.
- The current generated C++/Rust substrate names remain a backend presentation
  detail. A future runtime/support-library rename should be handled in backend
  rendering/static assets, not by changing selection or lowering behavior.

## ADR-079: Lane-List Parameters Replace Variadic `set` Source Shape

Status: Accepted and implemented in `tslc`/`tsldata`.

Implementation status:

- Completed: structured `lanes<s>` signature terms, parameter-position
  validation, typed lowered lane-list parameter facts, literal and
  generation-bound `lanes<at>` indexes, `loop<generation>` integer expansion,
  C++/Rust array-like parameter rendering, full `set` source migration, value
  tests for `v:=(lanes<s>)`, and removal/quarantine of transition-only
  variadic/pack behavior.

Context:

The active `set` primitive is currently authored as:

```tsl
prim<v:=s...>[arg_count(args)=return_vector_length] set(args...):
```

This models "one scalar argument per result lane" as a variadic source
signature. That shape is convenient for C++ and x86 `_mm_set*` intrinsics, but
it leaks backend calling conventions into the source language. It is awkward
for Rust, forces special handling in generated wrappers and smoke tests, skips
sized-vector generic fallback loops, and keeps value-test planning from treating
`set` as an ordinary typed shape.

The source intent is not "a C++ parameter pack"; it is a named lane-list
argument whose length is the selected vector lane count.

Decision:

Introduce a first-class lane-list parameter term and migrate `set` to it:

```tsl
prim<v:=(lanes<s>)> set(values):
```

`lanes<s>` is a single named parameter. Its element kind is scalar `s`, and its
length is exactly the selected return vector lane count. The first accepted
surface supports only parameter-position `lanes<s>`; result-position lane
lists, nested lane lists, empty lane-list element kinds, and non-scalar element
kinds are rejected until deliberately selected.

Add one lane-list accessor:

```tsl
lanes<at>(values, N)
```

The selector `at` is the only accepted lane-list operation for the first slice.
`N` must be generation-time known: a literal integer, or a symbol bound by a
generation-time loop. Runtime/emitted loop variables are rejected. The accessor
returns the scalar value at the logical lane-list index `N`.

Add generation-time range expansion:

```tsl
loop<generation>(i, start, end, step) { ... }
```

It has the same four-argument shape as `loop<backend>`, but it is executed by the
generator. `start`, `end`, and `step` must evaluate to generation-time integer
values. The body is expanded once for each iteration with `i` bound as a
generation-time integer. The emitted target-language counterpart is now
`loop<backend>`.

Do not add `lanes<expand>` or `lanes<expand_reverse>` in the first design. When
x86 set intrinsics require reversed argument order, the source body should spell
that fact explicitly with `lanes<at>(values, value<generation>(vector::length)
- 1 - i)` or equivalent generation-time arithmetic instead of hiding reversal in
the signature or renderer.

Consequences:

- `set` stops exposing a C++ variadic/public parameter-pack API as the source
  semantic model.
- C++ and Rust can receive the same logical lane-list argument. Backends may
  still render native x86 set intrinsics, array construction, scalar fallback,
  or lane-insert workarounds from typed lowered facts.
- Neon/ARM-style workarounds can name the lane-list parameter and access
  generation-known lanes without manufacturing fake top-level parameters.
- Value-test generation can add a normal `v:=(lanes<s>)` pattern: test inputs
  become the lane-list argument, and expected values remain vector lanes.
- `s...`, `arg_count(args)=return_vector_length`, `pack<expand>`, and
  `pack<first>` become transition-only mechanisms. They should be removed or
  quarantined once no source data needs them.

Implementation plan:

1. Document accepted/rejected `lanes<s>`, `lanes<at>`, and
   `loop<generation>` syntax and diagnostics.
2. Extend the signature model to represent `lanes<s>` as structured typed data
   rather than a raw signature string convention.
3. Validate only parameter-position `lanes<s>` for the first slice.
4. Lower lane-list parameters as named typed facts carrying element kind and
   selected lane count.
5. Implement `lanes<at>` for literal generation-time indexes, then for
   generation-loop-bound symbols.
6. Implement `loop<generation>` by expanding the body with a generation-time
   integer binding.
7. Migrate `set` from `v:=s...` to `v:=(lanes<s>)`, spelling the current
   reverse construction explicitly where preserving existing tests requires it.
8. Add a value-test pattern for `v:=(lanes<s>)`.
9. Remove or quarantine the old variadic and pack mechanisms after migration.

## ADR-080: Value-Test Backend Capability Is Renderer-Owned

Status: Accepted and implemented in `tslc`.

Context:

The value-test planner originally matched typed primitive/test shapes and also
carried backend IDs such as `cpp` and `rust` on those semantic patterns. That
kept behavior correct, but it coupled generic test-shape planning to the
currently implemented renderer set. It also made future backend addition look
like a semantic pattern edit even when the shape itself was already generic.

Decision:

Separate semantic value-test planning from backend renderer capability.

`ValueTestPattern` objects match typed lowered facts and authored test-case
metadata only. They do not name concrete backends. Backend renderers declare
`ValueTestBackendSupport` values containing the `ValueTestCasePlan.kind`
variants they can render and whether they support differential cases. The
planner receives generic `ValueTestBackendProfileInput` values and filters
planned cases through the supplied backend capability.

Concrete C++/Rust wiring remains in project assembly, where generated project
layout and renderer selection already live.

Consequences:

- Adding a backend requires a renderer plus a capability declaration, not edits
  to semantic value-test patterns.
- The same pattern can plan `v:=(lanes<s>)` or other typed shapes for any
  backend that advertises support for the resulting case kind.
- Differential tests are modeled as backend capability, not as a language-name
  branch inside the generic golden pattern.
- `ValueTestProjectPlan` stores backend profile plans generically and callers
  select plans by backend ID when assembling artifacts.

## ADR-081: TSIL Source Semicolons Are Statement Terminators

Status: Accepted and implemented in `tslc`.

Context:

TSIL bodies mix target-like raw text with recognized keyword regions. Before
this decision, a source semicolon after a recognized region leaked through as
raw text. That accidentally worked for `complete(...)` because the backend
`complete` template does not include `;`, but it produced duplicate
terminators for forms whose templates already own their target statement
syntax, such as `var<infer>(...)`.

Expression regions such as `call(...)`, `intrin(...)`, `cast(...)`,
`type(...)`, `value(...)`, and `lanes<at>(...)` can also appear as complete
statements. In that position the source `;` belongs to the surrounding TSIL
statement, not to the expression atom itself.

Decision:

The shared TSIL scanner treats top-level body streams and brace-block bodies as
statement streams. If a recognized region in a statement stream is followed by
a source `;` (allowing whitespace), the scanner consumes that terminator and
records it on the `Region`. Nested keyword payloads are scanned as expression
streams, so punctuation inside argument lists remains owned by the surrounding
expression.

Lowering renders a consumed statement terminator exactly once. The expression
renderer owns the default rule for ordinary non-block regions: append one target
`;`. A keyword lowerer may override finalization when the keyword owns a
different target statement shape:

- `var<...>` does not get an extra terminator because current backend
  declaration templates already include one; `VarLowerer` returns its rendered
  declaration unchanged when the source terminator was consumed.
- `let<type>(...)` consumes the source terminator but still renders no target
  statement because type aliases are currently substituted; `LetLowerer`
  returns its rendered alias binding unchanged.
- Other terminated non-block regions append a target `;` after their lowered
  expression or statement text.
- Block constructs such as `if`, `loop<backend>`, and `switch<compile>` do not
  gain a target semicolon.

Consequences:

- Authored source semicolons no longer leak as raw text after recognized TSIL
  regions.
- `complete(expr);`, expression statements like `intrin<...>(...);`, and
  side-effect helpers like `mem<copy>(...);` still render one target statement
  terminator.
- `var<...>(...);` no longer renders `;;`.
- Primitive TSIL source under `tsldata/primitives` should spell statement
  regions with source semicolons. A corpus guard test enforces this for the
  accepted statement keyword families.
- This remains a lexical source-body boundary, not a full TSIL statement or
  expression parser. Raw target-like statements keep their raw semicolons, and
  expression-region punctuation inside nested payloads is not reinterpreted.

## ADR-082: `intrin` Owns Direct And Built Intrinsic Calls

Status: Accepted and implemented in `tslc`.

Context:

TSIL had two intrinsic-call keywords with the same broad purpose:
`intrin<NAME>(...)` for direct backend intrinsic calls and
`intrin_compose<BASE, ...>(...)` for backend-built intrinsic names. That split
made the source surface larger than the semantic distinction. The real
distinction is not two keywords; it is whether the intrinsic name is used
directly or built from a base plus backend/extension naming policy and optional
modifiers.

Decision:

Use one keyword:

```tsl
intrin<NAME>(...)
intrin<BASE, build>(...)
intrin<BASE, build[prefix=..., infix=..., suffix=..., post=..., immediate(N)=...]>(...)
```

Without `build`, the selector is direct. The backend may qualify the name for
presentation, such as Rust's `core::arch` path, but lowering does not compose a
new intrinsic name.

With `build`, lowering composes an intrinsic name from the selected backend and
extension. Omitted build fields use backend/extension defaults. Explicit fields
override those defaults; an explicit empty text value suppresses the field.
`suffix=` and `infix=` accept either backend text or a typed generation value;
typed values are mapped through the selected extension's intrinsic suffix
metadata. `prefix=` remains text-only because a type value has no prefix
meaning. Existing build metadata such as `post=mask`, `infix_sep`, and
`immediate(N)=...` remains part of the same intrinsic invocation builder.

Consequences:

- The scanner and region registry no longer need an `intrin_compose` keyword.
- `IntrinLowerer` owns both direct and built intrinsic calls through one parsed
  selector object.
- The primitive corpus now spells built intrinsic calls as
  `intrin<..., build...>(...)`; a corpus guard rejects `intrin_compose<` in
  primitive TSIL bodies.
- `intrin::prefix` remains a first-class query function for the cases that need
  an explicit backend prefix value. Calls that want the selected extension's
  default prefix should omit `prefix=`.
- The primitive corpus uses direct typed modifier slots such as
  `suffix=base::signed_of(base::in)`, `suffix=ToBase`, and `infix=base::in`
  instead of wrapping type values in `value<backend>(intrin::suffix(...))`.
  Named suffix policies still use query form, for example
  `suffix=intrin::suffix("stream")`.
- Historical redesign notes may still mention `intrin_compose` as prior
  evidence, but current `tslc` source data should not use it.

## ADR-083: `call` Selector Clauses Use Commas

Status: Accepted and implemented in `tslc`.

Context:

TSIL selector surfaces should be visually consistent where they contain
multiple clauses. After ADR-082, `intrin<BASE, build[...]>(...)` uses a comma
between selector clauses, while `call<primitive=NAME attrs[...]>(...)` still
used whitespace between the primitive reference and the optional attribute
clause. That made two similar selector surfaces use different top-level
separators.

Decision:

Use comma-separated top-level `call` selector clauses:

```tsl
call<primitive=NAME>(...)
call<primitive=NAME[TypeArgs...]>(...)
call<primitive=NAME, attrs[key=value]>(...)
call<primitive=NAME[TypeArgs...], attrs[key=value]>(...)
```

The bracketed type-argument list remains attached to the primitive reference,
because it specializes that reference rather than forming a separate selector
clause. Attribute entries inside `attrs[...]` remain comma-separated.

Consequences:

- `parse_call_selector(...)` rejects the old whitespace-separated
  `call<primitive=NAME attrs[...]>(...)` spelling.
- The primitive corpus now uses `call<primitive=..., attrs[...]>(...)`.
- This is a source-syntax cleanup only; dependency extraction, call rendering,
  attribute evaluation, and primitive selection behavior are unchanged.

## ADR-084: Backend Loops Own Optional Unroll Hints

Status: Accepted and implemented in `tslc`.

Context:

TSIL previously used `loop<range>(var, start, end, step) { ... }` for emitted
target-language loops and a separate preceding `loop<unroll>(count)` directive
for loop-unroll hints. That split made unroll intent live beside, rather than
on, the loop it modified. It also left the source surface with a `range` name
that described the loop shape less directly than the current backend-emission
role.

Decision:

Use one emitted-loop keyword surface:

```tsl
loop<backend>(var, start, end, step) { ... }
loop<backend, unroll>(var, start, end, step) { ... }
```

`loop<generation>(var, start, end, step) { ... }` remains the generation-time
expansion loop.

`loop<backend, unroll>` is an explicit hint attached to the emitted loop. If the
selected backend declares a `loop_backend_unroll` translation template and the
trip count can be evaluated from generation-time integer bounds, lowering emits
the backend's unroll hint before the normal loop. If the backend has no unroll
template, or the count is symbolic such as a sized-vector `LANES` parameter,
lowering emits the normal backend loop. A known zero step remains an error.

Backend translation metadata uses `loop_backend` for the emitted loop and may
provide `loop_backend_unroll` for the optional hint. Rust currently omits the
unroll template and therefore renders normal loops for `loop<backend, unroll>`.

Consequences:

- Standalone source `loop<unroll>(...)` is removed from current primitive TSIL.
- The primitive corpus now uses `loop<backend>` and `loop<backend, unroll>`.
- `loop<range>` is no longer a supported production loop selector.
- Known-count C++ fallback loops still emit `TSL_UNROLL(count)` through the
  backend template, while symbolic generic loops remain valid normal loops.

## ADR-085: Primitive Value Tests Derive Names And Lane Counts

Status: Accepted and implemented in `tslc`.

Context:

Primitive value tests previously carried renderer-facing `test_name` plus both
`lane_set` and `lanes`. That duplicated facts already present in the primitive,
type, target axes, input vectors, expected values, and test intent. It also made
source tests easier to make internally inconsistent: `type`, `lane_set`, and
`lanes` could disagree even though downstream planning only needs one typed lane
count.

Decision:

Author value tests around semantic intent:

```tsl
tests:
  - {tags [basic], type "si32",
     case {inputs [[1, 2, 3, 4], [5, 6, 7, 8]], expected [6, 8, 10, 12]}}
```

`tags` is required and describes why the test exists, such as `basic`, `edge`,
`nan`, `overflow`, `mask`, `repeat`, or `reverse`. Source tests no longer carry
`test_name`, `lane_set`, or authored `lanes`. Catalog promotion derives the
stable case name from the primitive name, type tag, typed axes (`extension`,
`to_type`, `to_extension`, `index`, and `attrs`), plus either an optional `id`
or the tag list. Duplicate derived case names are catalog errors.

Lane count is inferred during catalog promotion. The common vector case uses the
expected vector length; representation-change cases use the source vector input
length; reductions and stores use vector input lengths. Source `lane_count` is
an explicit escape hatch for cases where no vector-shaped list exists or the
lane count is otherwise ambiguous, such as mask-only scalar bitset tests.

Consequences:

- The primitive corpus under `tsldata/primitives` has been migrated to `tags`,
  inferred lanes, and `lane_count` only where inference is not available.
- `TestCase.name` and `TestCase.lanes` remain typed promoted facts consumed by
  value-test planning and renderers; inference does not leak into renderers.
- Renderer function names use the derived case name directly instead of hiding
  duplicates behind numeric source-order suffixes.
- Test coverage audits can reason over semantic tags rather than parsing
  renderer-facing names.

## ADR-086: Value-Test Completeness Is A Typed Coverage Contract

Status: Accepted and implemented in `tslc`.

Context:

The value-test planner previously emitted the cases it recognized and separate
tests inferred coverage gaps by scanning generated source text. That made
coverage dependent on renderer output shape and allowed selected primitives,
authored test cases, and backend-unsupported plan kinds to disappear without a
single typed accounting boundary.

Decision:

Value-test planning now produces explicit coverage entries for every selected
backend/profile/primitive test responsibility. A coverage entry is one of:

- `emitted`: at least one backend-supported value-test plan was emitted;
- `compile_only_emitted`: an authored compile-only smoke case was emitted;
- `missing_authored_tests`: a selected primitive has no authored tests;
- `authored_unplanned`: an authored applicable test case was not accepted by
  any planner pattern;
- `backend_unsupported`: the planner produced a case kind the backend renderer
  does not support.

The full C++ AVX2 value-test gate asserts zero `missing_authored_tests`, zero
`authored_unplanned`, and zero `backend_unsupported` entries. Profile-specific
authored cases are admitted only when the selected specialization set contains
the matching typed extension, type tag, and representation axis facts.

Authored source tests also carry a typed role. `role "value"` is the default.
`role "compile"` is the current explicit smoke-test role for deterministic
compile-only cases such as undefined-value constructors. Source test arguments
are promoted to typed `vector`, `mask`, or `scalar` values according to their
signature position before value-test planning runs.

Consequences:

- C++ and Rust AVX2 are the current full-corpus completeness gates: every
  applicable selected primitive test case is emitted as a value test or
  compile-only smoke case, and the two backends must have no parity gaps for
  the current authored inventory.
- Unsupported planned kinds remain represented as `backend_unsupported` for
  future backend bring-up work; the current C++/Rust AVX2 gate requires that
  status to be absent.
- Renderers consume `ValueTestCasePlan` objects and coverage lives on
  `ValueTestProjectPlan`; tests no longer regex generated source to infer
  planning behavior.
- Planner support remains typed and signature-driven. New primitive tests
  should normally be added in `tsldata`, with new planner patterns added only
  for genuinely new typed shapes.
- The C++ renderer and case planner are split into helper modules before they
  become catch-all files: shared case-planning helpers live in
  `value_tests.case_helpers`, and pure C++ formatting helpers live in
  `value_tests.render_cpp_helpers`.
- `store_mask_repr` tests cover both compact `packed=true` storage and representative
  unpacked `packed=false` storage. The unpacked storage type is a typed
  planning fact (`target_base_spelling` and `expected_type_tag`), so the C++
  renderer formats an already-decided unsigned lane-word layout instead of
  inferring mask storage from primitive names or backend families.
- The mask representation source primitives are named `load_mask_repr` and
  `store_mask_repr` so they do not collide with emitted masked overload names
  such as `load_mask`, `load_maskz`, and `store_mask`.

## ADR-087: TSLc Scalar Facts And Dependency Closure Stay Semantic

Status: Accepted and implemented in `tslc`.

Context:

A design-principles review found that primitive-call dependency extraction
constructed a concrete C++ backend dialect even though dependency closure only
needs source-level vector identities. The same review found scalar width and
signedness facts duplicated through local digit parsing in validation, support
policy, lowering, and value-test helpers. A related residual risk remained in
`load_mask_repr`, whose unpacked layout still relied on the older
`vector::mask_underlying_t` source spelling after `store_mask_repr` had moved
to explicit unsigned lane-word storage.

Decision:

Scalar TSL type tags are catalog/domain facts. `tslc.catalog.scalar_types` owns
the explicit scalar table (`si8`/`ui8`/`f32`, widths, signedness, floatingness,
and backend type-map keys). Validation, support policy, query evaluation,
immediate-range lowering, and value-test scalar-tag helpers consume that table
instead of rediscovering scalar facts from raw strings.

Primitive-call dependency extraction uses a narrow semantic query resolver for
dependency identity. It recognizes the source forms needed for call closure:
`type`/`value` wrappers, `base::in`, signed/unsigned base transforms,
`vector::as_extension`, `vector::as_base`, `vector::window_base`, `vector::as`,
`base::generic`, target aliases, source-local `let<type>` aliases, concrete
scalar type tags, and extension names. It does not construct a backend dialect
or render backend spellings.

`load_mask_repr` and `store_mask_repr` now share the same unpacked layout
contract: `packed=false` uses unsigned lane-word storage derived from
`base::unsigned_of(base::in)`. Source bodies convert those typed lane-word
vectors to masks before returning. Dependency worklist expansion sorts
discovered primitive names before adding them to the queue.

Consequences:

- Call closure remains backend-neutral and deterministic.
- Scalar source semantics have one typed owner; presentation-only helpers may
  still parse emitted spellings when they are formatting backend substrate
  names rather than interpreting TSL type tags.
- `vector::mask_underlying_t` remains a supported backend/member query where
  documented, but it is no longer the unpacked mask representation source
  contract for `load_mask_repr` / `store_mask_repr`.

## ADR-088: TSIL Completion Uses `complete(...)`

Status: Accepted and implemented in `tslc`.

Context:

The TSIL directive for value-returning implementation bodies is semantic: it
marks the implementation result and lets the selected backend frame that value
as target-language return syntax. The source spelling must therefore describe
source intent rather than backend emission mechanics.

Decision:

`complete(expr)` is the canonical TSIL directive for completing a
value-returning implementation with `expr`. The directive lowers to the
backend's typed return framing through the backend translation key `complete`.
There is no compatibility alias for the former spelling in `tslc`, and source
bodies that use another directive name are unsupported.

Consequences:

- TSL source data describes semantic completion instead of target-language
  return emission.
- Backend translation metadata still owns the C++/Rust/C17 return spelling via
  the `complete` template.
- Lowering diagnostics use `TSL-LOWER-NO-COMPLETE` when a value-returning body
  has no supported completion directive.

## ADR-089: `param_types` Is A Typed Value-Test Layout Contract

Status: Accepted and implemented in `tslc`.

Context:

Mask representation primitives use an abstract `ptr` signature, but their
pointed-to storage layout depends on source attributes such as `packed`.
Leaving `param_types` as a parsed-but-unused annotation would duplicate the
same layout rule in value-test planning and make the source field decorative.

Decision:

Promote `param_types:` entries into typed catalog `ParamTypeRule` values on
`Primitive`. A rule records the parameter name, the controlling primitive
attribute, the concrete attribute value, the source type expression, and source
provenance.

Catalog validation checks the supported first-slice shape:

- the parameter exists on the primitive;
- the condition is shaped as `if attribute=value`;
- the controlling attribute exists on the primitive;
- the condition value is a valid concrete value for that attribute;
- duplicate `(parameter, attribute, value)` rules are diagnostics;
- the rule has a non-empty type expression.

Value-test planning consumes these rules through a small pointer-layout
resolver. The resolver currently supports scalar lane-word expressions needed
by authored tests: `base::in`, `base::signed_of(base::in)`, and
`base::unsigned_of(base::in)`, with optional `type<generation>(...)` wrapping
and pointer/const decoration. Resolved storage facts are carried on
`ValueTestCasePlan` as `target_base_spelling` and `expected_type_tag`; C++
renderers continue to format already-decided plan data.

Consequences:

- `param_types` is no longer sugar: changing a supported source type rule can
  change value-test buffer/storage typing.
- Generated wrapper signatures remain unchanged in this slice. `ptr` still
  lowers through the existing abstract pointer ABI; `param_types` does not yet
  drive public API or overload rendering.
- Unsupported type expressions remain outside this first resolver and produce
  unplanned value-test coverage rather than renderer-side guessing.

## ADR-090: CLI `--test` Reuses The Value-Test Pipeline

Status: Accepted and implemented in `tslc`.

Context:

The API already exposes the two facts needed to run generated value tests:
generation can include value-test harness dependencies through `test_harness`,
and after-write verification can run backend value-test targets through
`run_value_tests`. The CLI only exposed `--verify`, so users had to know the
Python API or pytest entry points to run the generated value-test gate.

Decision:

Add a CLI `--test` flag as a thin convenience over those existing contracts.
The flag:

- requires `--output-root`, because value tests are built and run from written
  generated artifacts;
- enables `test_harness` during generation;
- enables value-test planning warnings;
- runs the existing verifier even when `--verify` is not also present;
- passes `run_value_tests=True` to the verifier.
- prints an explicit progress line before invoking value-test verification, so
  users can see that tests are being built and run rather than only compiled.
- prints captured stdout/stderr for verifier commands whose step is `test`,
  which surfaces C++ `ctest` and Rust `cargo test` output without dumping every
  configure/build command.
- treats verifier diagnostics as a failed `--test` run, even when the verifier
  reports a value-test command failure with warning severity for API callers.

Omitting `--primitives` means the request starts from every primitive in the
loaded catalog. An explicit `--primitives ...` list is the narrowing mechanism
for focused smoke runs. This all-corpus default is resolved after catalog
building in the pipeline, not by a CLI-side source scan.

Consequences:

- No new pipeline stage, generation mode, verifier path, or API wrapper is
  introduced.
- `--verify` keeps its existing compile-only behavior; `--test` means
  compile plus generated value-test execution.
- The verifier still owns subprocess execution and capture. The CLI formats
  already-recorded `BuildCommandResult` test output for user feedback.
- A CLI `--test` run must not print `build/test-verified` or exit 0 after a
  failed generated test command.
- CLI tests assert only the option-to-existing-contract mapping, while the
  generated value-test build/run behavior remains covered by the existing
  value-test integration tests.
- The CLI no longer defaults to a tiny `add,hadd` smoke set. A command such as
  `--backends rust --test` without `--primitives` exercises every selected
  primitive root for the requested profiles/types.

## ADR-091: Rust Warning Hygiene Follows Source And Backend Ownership

Status: Accepted and implemented in `tslc`.

Context:

Running generated Rust value tests surfaced a large number of compiler warnings
from two different ownership layers:

- backend syntax warnings, such as Rust `if (...)` conditions and casts wrapped
  as whole parenthesized expressions;
- source-body constness warnings, where non-mutated TSIL variables were emitted
  as mutable Rust bindings.

Decision:

Keep the cleanup split by ownership.

Runtime `if` rendering now uses backend translation templates. C++ keeps
`if ({cond})`, while Rust uses `if {cond}`. Rust cast templates wrap only the
cast operand, `({expr}) as {type}`, preserving precedence without adding a
parenthesized return/assignment/function-argument expression. Rust pointer
casts likewise avoid wrapping the whole cast in an extra pair of parentheses.

Source bodies under `tsldata/primitives` were audited for non-mutated
`var<infer>` and `var<typed>` declarations. Read-only temporaries now use
`var<const_infer>` or `var<const_typed>`. Declarations that are mutated through
assignment, indexed writes, mask setters, pointer writes, or `mem<copy>`
destinations stay mutable. Source bodies also parenthesize the result of casts
that are intentionally shifted, so Rust sees `(cast_result) << i` rather than a
generic-argument ambiguity.

`s[]` parameters are rendered as immutable Rust bindings by default. Source
bodies that need a mutable array pointer introduce a mutable local copy
explicitly before calling `.data()`. A narrow `var<const_init_register>` form
covers zero-initialized register locals that are returned without mutation.

Consequences:

- Renderers format target-language syntax but do not guess source mutability.
- Source constness remains explicit and benefits both Rust and C++ output.
- The warning-focused Rust value-test run no longer reports any
  `unnecessary parentheses around ...` or `unused_mut` warnings.
- Remaining Rust warnings are a separate follow-up: unnecessary `unsafe`
  wrappers around calls that are already safe in the selected context.

## ADR-092: Implementation Safety Is A Typed Contract

Status: Accepted and implemented in `tslc`.

Context:

Generated Rust code previously treated unsafety as a body-rendering detail:
lowering marked a body as needing `unsafe { ... }`, and renderers still exposed
safe public functions. That hid two different facts behind one boolean:

- the implementation body performs an unsafe operation internally;
- the generated API requires the caller to uphold a safety contract.

Decision:

Add a typed `ImplementationSafety` value to catalog implementations and lowered
specializations. Source may declare selector-level safety metadata beside the
implementation body:

```tsl
impls:
  scalar:
    safety:
      internal_unsafe true
      caller_unsafe false
      reasons [intrinsic]
    anyint:
      implementation:
        tsil "complete(data);"
```

The safety block inherits down nested implementation selectors like `requires`
and `unroll_variants`. Validation checks only the supported structural shape:
boolean fields are `true`/`false`, and `reasons` is a scalar label list.
Reason labels remain open data.

The active primitive corpus uses this as explicit source metadata rather than
implicit compiler inference alone: every primitive implementation body carries
a local `safety:` block. A corpus guard checks that all current primitive bodies
remain annotated and that direct unsafe facts (`intrin<`, `mem<`, and pointer
parameters) are reflected by the authored safety metadata. Schema validation
also rejects unsupported children under an `implementation:` body field so a
misplaced `safety:` block cannot be silently ignored.

Lowering combines source-authored safety with inferred body effects. Intrinsics
and memory regions mark `internal_unsafe`; raw pointer parameters mark both
`internal_unsafe` and `caller_unsafe` because callers must uphold pointer
validity. Selection also preserves the concrete feature flags selected from
extension/type-scoped `requires` clauses and lowering carries them as
`LoweredSpecialization.required_features`.

After unresolved callees are pruned, the pipeline propagates live call-graph
facts bottom-up to a fixpoint. Unsafe callee metadata propagates as an internal
unsafe dependency plus `unsafe_callee` reason on callers. The public
`caller_unsafe` contract does not automatically propagate, because higher-level
wrappers can safely discharge a raw-pointer callee by passing locally-owned
storage. Required feature flags propagate through the same lowered call graph,
so if `prim1 -> prim2 -> primX` and `primX` requires `avx512f`, the lowered
`prim1` specialization carries `avx512f` too. The generated profile's effective
feature set is the machine profile features plus every propagated required
feature from live lowered specializations.

Call-fact propagation uses a lowered-body key that includes signature and
immediate shape, so runtime and immediate overloads can share the pruning key
without overwriting each other's internal unsafe or required-feature facts.

Transitive `unsafe_callee` is rendered with local unsafe call-site blocks for
Rust rather than by forcing a whole-body unsafe frame. This keeps wrappers such
as `to_array` public-safe and avoids nesting expression-local unsafe templates
like `MaybeUninit::assume_init()` inside a broader generated `unsafe { ... }`.
The render model carries an unsafe block as typed render text that suppresses
itself when the surrounding lowered body already renders inside an unsafe
frame.

Rust rendering consumes the lowered safety facts. Caller-unsafe primitives emit
`unsafe fn` trait methods, impl methods, free functions, and wrappers, while
internal unsafe still controls the lowered body frame.

Consequences:

- Safety is represented at a typed catalog/lowering boundary, not inferred by
  string inspection in renderers.
- Architecture feature requirements selected from `requires` are represented as
  typed lowered facts and propagate through primitive calls before rendering or
  verification.
- Safe abstractions can encapsulate internal unsafe blocks without forcing their
  public API to become unsafe.
- Transitive unsafe callees are not silent: callers get an internal unsafe
  frame and retain `unsafe_callee` in their safety reasons.
- Future source-owned safety documentation can be attached to `reasons` without
  changing renderer behavior.

## ADR-093: Metadata Audit Tool Suggests Source Contract Updates

Context:

The active corpus now carries source-owned implementation metadata for
`safety:` and `requires`. Keeping those fields synchronized by hand is tedious,
but automatically "fixing" semantic source contracts inside the compiler would
violate the source-body integrity boundary.

Decision:

Add `python -m tslc.maintenance.metadata_audit` as a maintenance script outside
the normal generation CLI. Maintenance commands live under the importable
`tslc.maintenance` package rather than split between package modules and
repo-local scripts. The tool loads TSL sources through the existing
source/parser/catalog boundary and returns typed `MetadataSuggestion` records.
It supports check-only reporting, an interactive prompt, and automatic
application of suggestions that carry a narrow source edit.

Safety suggestions are high-confidence only for direct facts that the compiler
already infers:

- `intrin<...>` body regions imply `internal_unsafe true` plus reason
  `intrinsic`;
- `mem<...>` body regions imply `internal_unsafe true` plus reason
  `raw_memory`;
- pointer-taking signatures imply `internal_unsafe true`,
  `caller_unsafe true`, and reason `raw_pointer`.

Requirement suggestions use the lowered, post-prune call graph introduced by
ADR-092. Selection preserves direct `requires` flags on selected
implementations, lowering carries them on `LoweredSpecialization`, and the
pipeline propagates live callees' required features bottom-up. The audit tool
compares direct source requirements with propagated requirements and suggests
local updates for callers.

Automatic `requires` edits are deliberately conservative. The tool applies them
only when the target selector has a simple local `requires [..]` list, or when a
leaf implementation selector can receive a new simple local `requires [..]`
line. Scoped `requires:` maps and broad nested selector shapes remain visible
manual suggestions.

Consequences:

- Normal generation still compiles source truth; it does not rewrite source
  metadata or guess source intent.
- The maintenance tool can keep direct `safety:` metadata current without
  forcing developers to hand-edit repetitive blocks.
- Requirement drift is surfaced from typed selected/lowered facts instead of
  intrinsic-name string guessing.
- The tool's source edits are intentionally small and span-based; it is not a
  general TSL formatter.

## ADR-094: Value-Test Parity Uses Typed Coverage Inventory

Context:

The C++ AVX2 value-test gate was the first strict full-corpus runtime gate.
Rust initially supported fewer case kinds, so the completeness campaign needed
to expose every Rust gap explicitly before closing case families. Otherwise
missing Rust tests could look like absent planning data instead of a tracked
backend parity problem.

Decision:

Keep value-test coverage accounting inside the value-test planning boundary.
`ValueTestCoverageEntry` now uses a typed status set and carries the planned
case kind when one exists. `ValueTestParityEntry` groups per-backend outcomes
for one authored value-test identity. The coverage helper exposes deterministic
parity inventories and parity gaps for requested backend sets.

The final current AVX2 parity gate requests C++ and Rust together. It requires
zero `missing_authored_tests`, zero `authored_unplanned`, zero
`backend_unsupported`, matching emitted value-test counts, and no parity gaps.
Both backends keep compile-only smoke cases in the same typed inventory.

Rust value-test rendering now covers every planned full-corpus AVX2 case kind:
masked/vector/scalar/mask cases, immediates, reductions, broadcasts, lane-list
and scalar-vector constructors, array/vector round trips, contiguous and
indexed memory operations, mask loads/stores, load-convert, memory copy,
pointer lifetime/free, stream output, representation-change cases, and
extension insert/extract. The Rust renderer is split into focused formatting
modules for shared helpers, memory cases, and conversion/extension cases while
the main renderer remains a dispatch boundary over already-planned
`ValueTestCasePlan` objects.

Source bodies that intentionally ignore or branch over values made visible by
Rust tests should make that fact explicit in TSIL source. Examples in this
slice include scalar `custom_sequence`, scalar `conflict`, `memory_cp`, scalar
scatter pointer locals, and unsigned comparison sign-bit selection. The
renderer does not carry primitive-specific warning suppression.

Consequences:

- Renderers still format `ValueTestCasePlan` objects and do not compute
  semantic coverage.
- Unsupported value-test families remain visible as structured planning records
  and warnings when future backends request value-test warnings.
- The current C++/Rust AVX2 full-corpus gate is hard parity by typed inventory:
  Rust reports 1 `compile_only_emitted` case and 1,107 emitted value cases, with
  no backend-unsupported or parity-gap records.
- Full-corpus Rust AVX2 value tests build and run warning-clean, so warning
  hygiene remains a source/backend ownership contract rather than a renderer
  suppression mechanism.

## ADR-095: SDE Runs Profile Value Tests After Artifact Generation

Context:

The AVX2 parity gate proves C++ and Rust value-test parity for one profile, but
it does not prove every x86 machine profile can build and run its generated
value tests on a host without native support for that ISA. Intel SDE is
available in the development environment and can emulate the relevant x86
profiles after generated artifacts exist.

Decision:

Keep emulator execution in the after-write build verifier. Machine profiles may
declare an optional `sde` chip alias in
`supplementary/buildsystem/machine_profiles.json`. The profile loader validates
that alias as typed profile metadata, and renderers pass it through to
`VerifyProfile`.

`tslc.cli --test --sde [PATH]` supplies an optional SDE executable to the
verifier. C++ value-test execution wraps the generated profile's `ctest`
command with `sde -chip -- ...` when the profile declares an SDE chip. Rust
cannot run `cargo test` itself under SDE as a precise profile test runner, so
the verifier builds Rust tests with `cargo test --no-run --message-format=json`,
extracts the compiler-artifact test executables, and runs each executable
through the same SDE prefix.

When SDE value-test mode is enabled and the caller did not explicitly choose a
C++ compiler, the verifier pins the C++ compiler command to `c++` instead of
inheriting ambient `CXX`. This avoids accidentally building low-ISA SDE test
binaries with toolchain runtime helpers such as Zig compiler-rt routines that
use newer instructions than the selected SDE chip. Explicit `--cpp-compiler`
configuration still wins. SDE-mode C++ verification also removes profile build
directories before configure so an existing CMake cache cannot preserve a
previous incompatible compiler.

SDE remains explicit. Generation does not autodetect host hardware, and normal
verification does not require an emulator. If `--sde` names a missing
executable, the verifier reports `TSL-BUILD-VERIFY-EMULATOR-MISSING`. If Rust
test build output does not expose runnable test binaries for an SDE profile,
the verifier reports `TSL-BUILD-VERIFY-NO-RUST-TEST-BINARIES`.

The SDE sweep also corrected source profile/requirement facts rather than
adding verifier exceptions. KNL/KML machine profile flags now exclude legacy
AVX-512 subsets that the current compiler toolchains do not accept and that
the current corpus does not use. A few `.tsl` implementation selectors now
carry the feature requirements needed by the actual intrinsics they select,
including AVX-512 floating bitwise operations, byte/word convert-up paths,
and the AVX2 floating load family.

Omitting `--profiles` on the CLI now means every loaded machine profile. The
API represents that as `profiles=None`; explicit `--profiles` remains the
narrowing mechanism. When SDE value-test mode is active, non-generic profiles
without an SDE chip alias are skipped by the verifier with a visible
`verify-skip` note instead of being built with an incompatible host toolchain.
This allows default generation to include non-x86 artifacts such as `neon`
while keeping x86 SDE runtime testing scoped to profiles SDE can actually
emulate.

Consequences:

- SDE execution is a verifier-side side effect, not a rendering or planning
  concern.
- C++ and Rust use the same profile metadata and the same explicit CLI opt-in.
- Omitting `--profiles` is the way to request all loaded profiles; there is no
  magic `--profiles all` selector.
- Value-test runtime feedback can cover all SDE-annotated x86 profiles without
  requiring the host CPU to support those instruction sets.
- Source feature requirements stay source-owned and typed; verifier failures
  exposed metadata drift instead of becoming hard-coded profile exceptions.

## ADR-096: Pointer Mutability And Array Parameters Are Typed

Context:

The `set` and `from_array` families exposed a parameter-passing mismatch:
array-like values are read-only inputs, but C++ previously passed lane arrays
by value and Rust owned array arguments. Memory loads also used the same `ptr`
kind as stores, which hid whether a primitive reads through a pointer or
writes through it.

Decision:

Encode pointer mutability in the signature vocabulary. `ptr` and `ptr+` remain
mutable pointer kinds for stores and other output/input-output operations.
`cptr` and `cptr+` are read-only pointer kinds for loads, gathers,
load-convert, scalar loads, mask loads, and memory-copy sources.

Keep array/lane-list constness as backend parameter policy derived from typed
signature terms. `s[]` and `lanes<s>` parameters are read-only inputs: C++
renders them through `array_param<Vec>` (`const array_for<Vec>::type &`) and
Rust renders them as `&S::Array`/`&Self::Array`. Owned array results such as
`s[]:=v` still return `array_for<Vec>::type` / `S::Array` by value.

Rust primitive-call lowering uses catalog-derived borrowed argument positions
to borrow `s[]` and `lanes<s>` call arguments at call sites. TSIL source stays
semantic (`call<primitive=from_array>(result)`); it does not spell backend
borrow syntax. Read-only array buffers use `as_ptr()`, while mutable output
buffers keep `data()`/`as_mut_ptr()`.

Consequences:

- Source signatures now say whether a pointer parameter is read-only or
  mutable.
- `from_array` no longer needs a local copy workaround before loading from its
  input array.
- Generic C++ vector register parameters use `reg_param` by const reference;
  real SIMD registers keep the existing value-passing behavior.
- The design avoids body mutation inference. If a future primitive genuinely
  needs caller-visible mutable array input, that should become an explicit
  typed signature role rather than a renderer heuristic.

## ADR-097: Generated Build Verification Uses Isolated Toolchain Scratch

Context:

The generated value/build tests can invoke ambient compilers such as
`CXX="zig c++"`. Under the workspace mount, Zig can fail during CMake compiler
checks even when the generated source is valid. Running value-test build/run
checks in parallel with the rest of the suite can also oversubscribe the host
and turn toolchain scratch failures into misleading compile diagnostics.

Decision:

Keep build verification as the side-effect boundary, but isolate its toolchain
scratch deliberately. `verify.sh` runs ordinary non-build tests in shards,
runs value-test build/run checks serially, and runs generated-build shards
with basetemps under `/tmp/tslc-verify` by default. The verifier subprocess
runner supplies per-command-root Zig caches under `/tmp/tslc-zig-cache`.
`TSLC_VERIFY_TMPROOT` can override the generated-build pytest temp root.

Consequences:

- Generated project verification remains deterministic with ambient Zig
  compilers in this workspace.
- Regular non-build tests can keep the repo-local pytest temp policy.
- Toolchain scratch placement stays in the verifier/wrapper boundary, not in
  parsing, selection, lowering, rendering, or artifact writing.

## ADR-098: Value-Test Emulators Are Typed Verifier Metadata

Context:

The SDE value-test runner solved x86 execution, but it encoded profile runtime
support as an SDE-only field. ARM profile testing needs QEMU user-mode
execution, and QEMU cannot be modeled as “SDE but with another executable”:
SDE can wrap `ctest`, while QEMU must run the target test binary, or be wired
through CMake's cross-compiling emulator support.

Decision:

Machine profiles now declare optional emulator metadata as:

```json
"emulator": {"kind": "sde", "profile": "hsw"}
```

or:

```json
"emulator": {"kind": "qemu-aarch64", "profile": "cortex-a76"}
```

The metadata records only emulator kind, profile/CPU, and optional extra
arguments. Executable paths remain verifier configuration supplied by the CLI
or API (`--sde`, `--qemu-aarch64`), not profile data.

The verifier carries the same `VerifyEmulator` value for C++ and Rust
profiles. SDE preserves the existing behavior: C++ wraps `ctest` with
`sde -chip --`, and Rust builds tests with `cargo test --no-run
--message-format=json` before running each test binary through SDE.
QEMU uses the same Rust no-run path, but C++ configures CMake with
`CMAKE_CROSSCOMPILING_EMULATOR` so host `ctest` remains native and CMake wraps
only the generated aarch64 test executable.

Aarch64 verifier profiles now carry target metadata derived from the machine
profile family. C++ profiles use `aarch64-linux-gnu` and ARM `-march=...`
flags; the verifier defaults targeted C++ profiles to `clang++` unless the
caller explicitly chooses a compiler. Rust profiles use
`aarch64-unknown-linux-musl` with `rust-lld`, which is enough to build static
test binaries runnable by `qemu-aarch64` on the current development machine.

Consequences:

- Emulator execution remains an after-write verifier side effect.
- Profile data names emulator capabilities, not local executable paths.
- SDE and QEMU share typed metadata, but their command shapes stay honest.
- Rust NEON-profile value tests can cross-build and run through QEMU today.
- C++ QEMU verification is wired, but it still needs an installed aarch64 C++
  sysroot/standard library for clang to compile generated C++ artifacts.
- Native ARM extension emission remains a separate support-policy/rendering
  slice; the current proof exercises the NEON machine profile and QEMU runner,
  while ARM-specific register substrate support is still deferred.

## ADR-099: Fixed Native Extension Register Substrates Come From Catalog Data

Context:

The NEON machine profile could be cross-built and run through QEMU, but it was
only exercising scalar/generic fallback coverage. The `neon` extension already
declared concrete C++ and Rust vector register spellings in
`vector_register_types`, plus the C++ header needed for those types, but that
metadata stopped at the source schema boundary.

Decision:

Promote extension-owned native register spellings and backend headers into the
typed `Extension` catalog model. Lowering records the selected specialization's
concrete register spelling as a lowered fact. C++ and Rust project renderers
register any selected non-x86 fixed-width extension that declares backend
register spellings; renderers do not infer register types from extension names.

Enable the `arm` extension family only for fixed-width extension substrates in
this slice. `neon` now emits native `tsl::simd<T, tsl::neon>` and
`Simd<T, Neon>` registrations from typed metadata. Scalable-vector extensions
such as SVE stay source-visible but unsupported for emission until a separate
scalable-vector design pass.

NEON source bodies that were previously hidden by fallback-only emission were
repaired using existing typed TSIL forms: `blend` uses unified
`intrin<..., build[suffix=...]>`, `reinterpret` uses semantic bitcast rather
than backend-divergent reinterpret intrinsic names, and `set_undef` uses a
backend-rendered typed uninitialized register declaration.

Consequences:

- Native fixed-width extension registration is data-driven by `tsldata`, not
  hard-coded to `neon`.
- Rust NEON value tests for the `add` slice and its dependency closure now
  cross-build for `aarch64-unknown-linux-musl` and run through QEMU.
- C++ NEON artifacts render native tags and include `<arm_neon.h>`; runtime
  C++ QEMU verification is covered by the follow-up toolchain decision in
  ADR-100.
- SVE remains intentionally deferred; enabling `arm` does not mean scalable
  vector semantics are modeled.

## ADR-100: C++ Aarch64 Runtime Verification Uses Existing Toolchain Knobs

Context:

C++ NEON profile artifacts can render native `<arm_neon.h>` code, and the
verifier already carries a typed C++ compiler, target triple, and QEMU
emulator path. The open question was whether the CLI/API needed more sysroot
plumbing before C++ NEON value tests could run under QEMU.

Decision:

Do not add a new sysroot flag for this slice. The current development image has
no clang-compatible aarch64 GNU C++ sysroot: `clang++ --target=aarch64-linux-gnu`
cannot find standard library headers such as `<array>`, and `<arm_neon.h>`
transitively needs target libc headers. However, the installed Zig frontend can
cross-build aarch64 musl C++ binaries with its bundled libc when invoked through
the existing verifier knobs:

```text
--cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
```

Keep local Zig cache paths outside the workspace mount when running this gate.
The verifier remains responsible for after-write build/test execution, and
machine profile metadata remains free of local compiler/sysroot paths.
Full C++ compiler flags that are profile-specific, such as future
`-march=...` arguments, belong to typed machine profile data (`cpp_flags`), not
to C++ rendering code. The renderer may derive the current x86 `-m...` flags
from feature tokens, but it forwards full profile-owned C++ flags verbatim.

The C++ verifier now performs a target-specific preflight for profiles that
declare a C++ target triple. If the local compiler cannot compile a tiny
standard-library/NEON probe for that target, only that profile is skipped with a
structured verifier note instead of failing the whole host-buildable C++ gate.

Consequences:

- C++ NEON runtime verification can run today through
  `qemu-aarch64 -cpu cortex-a76` without adding local-machine-specific profile
  metadata.
- Plain clang remains usable only when the environment provides a matching
  aarch64 C++ sysroot; otherwise the C++ NEON profile is skipped by target
  preflight in broad host-build verification.
- AArch64 NEON C++ profiles declare an empty `cpp_flags` list because the
  target triple selects the baseline AArch64 NEON substrate. Future SVE-style
  `-march=...` flags should be declared in machine profile data.
- The ISA-neutral `lane_bitmask_int` helper lives in `tsl_core.hpp`, so ARM
  profile headers do not depend on x86 traits merely to name integral masks.

## ADR-101: Rust Integer Generic Parameters Are Immediate/Index Values

Context:

Native NEON lane extraction exposed a Rust const-generic typing mismatch.
`extract_value` models its lane as `generic_params: Index {kind int}`, and the
NEON implementation forwards that value through an intrinsic
`immediate(1)=Index` modifier. Rust `core::arch::aarch64::vgetq_lane_*`
intrinsics require the lane const generic to be `i32`, while `tslc` had been
rendering all Rust `kind int` generic parameters as `usize`.

Decision:

Render Rust `generic_params {kind int}` as `i32`. In the current corpus these
integer generic parameters are immediate/index values (`Index` for lane
extraction and `N` in gather/scatter metadata), not array extents. Source bodies
that need a Rust array index already cast explicitly through
`type<backend>(scalar::size)`, keeping the size/index conversion source-visible.

Do not add primitive-name or NEON-specific compiler branches. The source still
owns which intrinsic receives the immediate, the Rust backend owns the const
parameter spelling, and renderers consume lowered facts.

Consequences:

- Native Rust NEON `extract_value` compiles and passes value tests through QEMU.
- C++ remains unchanged: C++ `kind int` parameters continue to render as
  `std::size_t`.
- If a future source generic is truly an array extent rather than an immediate
  or lane/index value, the source language should add a distinct typed kind
  instead of overloading `kind int`.

## ADR-102: NEON Conversion Intrinsic Spelling Stays Source-Owned

Context:

Broad native NEON Rust value-test generation exposed conversion intrinsic names
such as `vcvtqf32_s32`. Those names are not valid Rust `core::arch::aarch64`
spellings; the expected form is `vcvtq_f32_s32`. The same source bodies also
need to preserve C++ behavior and avoid a Python-side table of NEON primitive
or intrinsic spelling exceptions.

Decision:

Keep this spelling in source-owned TSIL intrinsic composition metadata. The
NEON `cast` implementations use the existing
`intrin<..., build[infix=..., infix_sep="_", suffix=...]>` form so the
generated intrinsic name is built as `vcvtq_<to>_<from>`.

Do not add primitive-name, extension-name, or backend intrinsic-name classifier
branches in renderers. The source body owns the intrinsic spelling pieces; the
lowerer evaluates typed generation-time selectors; renderers format the
already-decided call.

Consequences:

- Native NEON `cast` now compiles and passes C++/Rust value tests through QEMU.
- The broad fixed-width NEON C++/Rust gate now builds and runs the current
  selected corpus through QEMU.
- Future spelling mismatches should first be treated as source-data
  composition issues or typed intrinsic-build capability gaps, not renderer
  tables.

## ADR-103: SVE Needs A Scalable-Vector Substrate Before Primitive Coverage

Context:

Fixed-width NEON now has broad C++/Rust QEMU value-test coverage, so the next
ARM-native target is SVE. The source corpus already declares an `sve` extension
with `vector_bits "scalable"`, C++ register spellings such as `svint32_t`,
`svbool_t` mask metadata, and SVE primitive bodies. The generator still
explicitly excludes scalable extensions in `SupportPolicy.supports_extension`.

Evidence from the maintenance helpers:

- `./dev.sh explain --primitive add --profile neon --type si32 --backend cpp
  --extension sve` reports that the NEON profile emits only `generic`, `neon`,
  and `scalar`; `sve` is not emitted for that profile.
- `./dev.sh explain --primitive add --profile sve --type si32 --backend cpp`
  reports there is no `sve` machine profile.
- `./dev.sh dump --stage catalog --primitive add` confirms SVE source bodies
  already exist for `add`.
- `./dev.sh ratchet` passes the current baseline with `67152 emitted / 67152`
  slot-variants across `36616` keys.

Toolchain probes show C++ SVE is viable in this environment with the existing
compiler/emulator surface: Zig can compile `<arm_sve.h>` probes for SVE-capable
AArch64 CPUs such as `a64fx` or `neoverse_v1`, and QEMU can execute a tiny SVE
binary. Stable Rust in this environment exposes an `+sve` target feature but
does not expose SVE stdarch vector types/functions such as `svbool_t`,
`svint32_t`, or `svadd_s32_x`; the source extension currently declares
`rust supported false`.

Decision:

Do not enable SVE by adding it to the fixed-width native-extension path.
Scalable vectors need a typed substrate first because current renderers and
helpers assume a concrete `extension.vector_bits` value when registering
native `simd`/`SimdVector` types, mask/imask types, array types, alignment, and
value-test lane counts.

The first implementation slice should be C++-only and should introduce the
minimal typed scalable-vector facts needed to compile one primitive family,
starting with `add<sve, si32>`:

- add a machine profile for SVE with profile-owned C++ flags and QEMU metadata;
- introduce an explicit support-policy capability for C++ scalable extensions
  instead of reusing the fixed-width or sized-vector paths;
- render C++ `simd<T, sve>` registrations from source-owned SVE register and
  mask metadata without computing fixed lane counts;
- define how `vector::length`, `vector::alignment`, arrays, and value tests are
  represented for a concrete SVE test vector length before running value tests;
- keep Rust SVE unsupported until a supported Rust backend API is available or
  a separate typed backend strategy is designed.

Consequences:

- Primitive-by-primitive SVE work should start only after the scalable C++
  substrate exists; otherwise every primitive fix would fight the same missing
  lane/mask/register model.
- SVE profile flags belong in `machine_profiles.json`, not in C++ render code.
- Rust parity for SVE is explicitly out of scope for the first SVE slice.
- The new `dev.sh explain`, `dump`, and `ratchet` helpers are the preferred
  evidence tools for checking each next ARM coverage step.

## ADR-104: C++ SVE Starts With Build-Verified Scalable Native Registration

Context:

The first SVE implementation slice needed to prove that a scalable native ARM
extension can be selected, lowered, rendered, built, and executed without being
modeled as a fixed-width vector. The existing C++ native-registration path was
close, but it still assumed non-x86 native masks were represented by the vector
register and that all emitted vector signatures could instantiate
`array_for<Vec>` via `sizeof(register_type)`. SVE register types are sizeless,
so `sizeof(svint32_t)` is invalid.

Decision:

Add a narrow C++ SVE substrate rather than a broad scalable-vector model:

- add an `sve` machine profile with profile-owned `-mcpu=a64fx` flags and
  `qemu-aarch64 -cpu a64fx` metadata;
- allow scalable extension selection through an explicit support-policy
  capability;
- keep `vector::length` unresolved for scalable vectors and defer `s[]` /
  lane-list signatures for scalable extensions, preventing accidental
  `array_for<simd<T, sve>>` instantiation;
- promote direct native-predicate mask spellings such as `svbool_t` from
  `mask_type_policy`;
- register C++ `simd<T, sve>` from source-owned `sv*` register metadata and
  `svbool_t` mask/imask metadata;
- keep SVE intrinsic spelling source-owned through `intrin<..., build>`:
  suffix fragments live in `tsldata/extensions/extension.tsl`, and literal
  `post=x/z/m` fragments append generically in the intrinsic lowerer;
- normalize the SVE `mask_true` source body to ordinary typed implementation
  entries so `add<sve, T>` closes its dependency graph.

Consequences:

- `./dev.sh explain --primitive add --profile sve --type si32 --backend cpp
  --extension sve` shows selected/lowered/emitted SVE `add`, including the
  `mask_true<sve, si32>` dependency.
- `dev.sh build/test` can cross-build the C++ SVE profile with Zig and execute
  the generated CTest target through QEMU.
- The generated values executable currently does not contain true SVE lane
  value cases; it exercises generic/scalar cases while the SVE profile smoke
  target address-takes and compiles many SVE specializations. Real SVE
  value-test lane strategy remains the next slice.
- Rust SVE remains unsupported because stable Rust stdarch still lacks the
  required SVE symbols in this environment.

## ADR-105: C++ SVE Value Tests Use Extension-Owned Runtime Lane Counts

Context:

The C++ SVE substrate could build and run through QEMU, but generated
`values_sve.cpp` still contained no true `tsl::simd<..., tsl::sve>` lane value
cases. Existing value-test renderers initialize fixed-width/generic registers
through `array_for<Vec>` or direct lane indexing, both of which are invalid for
sizeless SVE registers.

Decision:

Add a narrow C++ scalable value-test path for authored all-vector value cases:

- source extension metadata owns the runtime lane-count expression through
  `test_runtime_lanes`, with SVE declaring
  `cpp "svcntb() / sizeof({base_type})"`;
- value-test harness discovery now also finds pointer load/store helpers by
  unique signatures `v:=cptr` and `void:=(ptr,v)`;
- test-mode dependency closure includes those load/store helpers, so a
  generated scalable value case can use the public TSL load/store surface;
- the planner emits a render-ready `scalable_golden` case only for backends
  that declare support for that case kind, scalable extensions, value-result
  all-vector shapes, runtime-lane metadata, and available load/store helpers;
- the C++ renderer formats the already-decided plan by filling runtime-sized
  buffers, loading SVE registers via `tsl::load<Vec, false>`, calling the
  primitive under test, storing via `tsl::store<Vec, false>`, and comparing the
  runtime buffer with the existing lane equality helper.

Consequences:

- No fixed `vector::length` or `array_for<simd<T, sve>>` fact is invented for
  SVE.
- Renderer code does not inspect the catalog or classify source primitive
  names; it consumes `source_extension`, load/store names, and the lane-count
  expression from the plan.
- The first supported SVE value shape is consumed by the C++ renderer and
  covers `add`-style all-vector value-result cases. Masked SVE cases, mask
  results, memory cases, reductions, scalar results, and Rust SVE remain
  separate follow-ups.
- `dev.sh test --profiles sve --primitives add --backends cpp` now emits true
  SVE value cases and runs them through QEMU.

## ADR-106: C++ SVE Masked Value Tests Use Extension-Owned Predicate Construction

Context:

SVE masked value-result primitives such as `add[mask=zero]` and
`add[mask=pass_through]` lowered and compiled, but generated value tests still
only exercised fixed-lane/generic mask representations. SVE masks are native
`svbool_t` predicates, so authored integer mask bits cannot be passed directly
as `typename Vec::mask_type`.

Decision:

Extend the scalable value-test boundary without making renderers classify SVE:

- source extension metadata owns a backend-specific `test_mask_from_bits`
  expression. SVE declares the C++ expression that invokes the generic
  `::tsl::test::mask_from_bits<{vec}>({mask_bits}, {authored_lanes}, {lanes})`
  test API;
- source extension metadata also declares any profile-specific C++ test support
  headers needed by that expression. SVE requests `tsl_test_sve.hpp`, which
  specializes the shared mask-bit adapter behind `__ARM_FEATURE_SVE`,
  constructing `svbool_t` predicates with lane-index vectors and
  `svcmpeq_n_u*` instead of converting predicates through an integral
  representation;
- the planner emits `scalable_masked` only when the backend supports that case
  kind, the selected extension is scalable, runtime-lane and mask-construction
  metadata are present, and typed load/store harness helpers are available;
- the renderer consumes `ValueTestCasePlan.mask_from_bits_expr` and formats
  runtime-sized load/call/store/compare code. It does not inspect the catalog
  or branch on extension/primitive names.

Consequences:

- `dev.sh test --profiles sve --primitives add --backends cpp` now emits and
  runs native scalable SVE value tests for masked `add` forms.
- `array_for<simd<T, sve>>`, fixed `vector::length`, and packed integral mask
  assumptions remain out of the scalable SVE value path.
- Mask-result SVE value tests remain a separate typed slice because comparing
  native predicates requires a source-owned extraction/comparison boundary.
- Rust SVE remains unsupported until a Rust backend strategy exists.

## ADR-107: C++ SVE Mask-Result Value Tests Use Extension-Owned Predicate Checks

Context:

Unmasked SVE comparison primitives such as `equal` lower to native predicate
results (`svbool_t`). The generic/fixed-lane value-test path can compare
integer mask bitsets, but it cannot inspect a native scalable predicate without
inventing a packed representation or asking the source/runtime boundary how to
check predicate activity.

Decision:

Add a narrow scalable mask-result test boundary:

- source extension metadata owns a backend-specific `test_mask_check`
  expression. SVE declares the C++ expression that invokes the generic
  `::tsl::test::check_mask_bits<{vec}>({case_name}, {mask}, {expected_bits}, {authored_lanes}, {lanes})`
  test API;
- SVE's profile-specific test support header specializes the shared mask-bit
  adapter with reusable all-lanes and single-lane predicate helpers, probing
  each lane with `svptest_any` rather than converting `svbool_t` through an
  integral mask;
- the planner emits `scalable_mask_result` only for backends that support that
  case kind, scalable extensions, result kind `m`, all-vector parameters,
  runtime-lane metadata, mask-check metadata, and available load helpers;
- the renderer consumes `ValueTestCasePlan.mask_check_expr` and formats
  runtime-sized load/call/check code. It does not inspect the catalog or branch
  on primitive/extension names.

Consequences:

- `dev.sh test --profiles sve --primitives equal --backends cpp` now emits and
  runs native scalable SVE value tests for unmasked comparison results.
- Scalable predicate comparison remains separate from packed integral mask
  representations.
- Masked mask-result comparisons (`m:=(m,v,v)`) remain a follow-up because
  they combine predicate construction and predicate-result checking in one
  typed case shape.
- Rust SVE remains unsupported.

## ADR-108: C++ SVE Masked Mask-Result Value Tests Combine Predicate Construction And Checks

Context:

Masked SVE comparison primitives such as `equal[mask=zero]` lower to native
predicate inputs and native predicate results (`m:=(m,v,v)`). Previous scalable
value-test slices covered predicate construction for masked value-result cases
and predicate checking for unmasked comparison results, but not the combined
shape.

Decision:

Add a narrow scalable masked mask-result test boundary:

- the planner emits `scalable_masked_mask_result` only for backends that support
  that case kind, scalable extensions, result kind `m`, exactly one mask
  parameter, vector parameters, runtime-lane metadata, mask-construction
  metadata, mask-check metadata, and available load helpers;
- the pattern layer keeps this shape separate from masked value-result
  planning so value-result semantics do not become a mixed procedural hub;
- the C++ renderer formats runtime-sized vector loads, uses the plan's native
  predicate-construction expression for the input mask, calls the selected
  primitive, and returns the plan's native predicate-check expression;
- the renderer does not inspect the catalog or branch on primitive/extension
  names.

Consequences:

- `dev.sh test --profiles sve --primitives equal --backends cpp` now emits and
  runs native scalable SVE value tests for masked comparison results such as
  `equal_maskz<Vec>(mask, v0, v1)`.
- Predicate construction and checking remain source/catalog-owned through
  extension test metadata.
- Scalable mask-logic cases (`m:=(m,m)`) remain a follow-up because they need
  predicate construction for multiple mask inputs and predicate-result checks
  without vector load helpers.
- Rust SVE remains unsupported.

## ADR-109: C++ SVE Mask-Logic Value Tests Use Multiple Render-Ready Predicate Inputs

Context:

SVE mask-logic primitives such as `mask_binary_and` lower to native predicate
operations (`m:=(m,m)`) and already compile for C++ SVE. The fixed/generic
value-test path compares packed integer masks, but scalable SVE needs to
construct multiple native `svbool_t` inputs and check a native predicate result
without fixed `array_for<Vec>` or packed-mask assumptions.

Decision:

Add a narrow scalable mask-logic value-test boundary:

- keep scalable C++ value-test rendering in a focused
  `tslc.value_tests._render_cpp_scalable` module rather than growing
  `_render_cpp_core.py`;
- the planner emits `scalable_mask_logic` only for backends that support that
  case kind, scalable extensions, result kind `m`, all-mask parameters,
  runtime-lane metadata, mask-construction metadata, and mask-check metadata;
- the plan carries one render-ready predicate-construction expression per mask
  input plus one render-ready predicate-check expression for the result;
- the C++ renderer formats those already-decided expressions and does not
  inspect the catalog or branch on primitive/extension names;
- SVE-authored mask-logic test cases live in `tsldata`, because existing
  mask-logic tests are explicitly `extension "avx512"` and must not be reused
  implicitly for SVE.

Consequences:

- `dev.sh test --profiles sve --primitives mask_binary_and --backends cpp` now
  emits and runs native scalable SVE value tests for mask logic.
- Predicate construction and checking remain source/catalog-owned through
  extension test metadata.
- Scalable mask constants (`m:=()`) remain a follow-up because they need
  predicate-result checks without input predicate construction.
- Rust SVE remains unsupported.

## ADR-110: C++ SVE Mask-Constant Value Tests Use Extension-Owned Predicate Checks

Context:

SVE mask-constant primitives such as `mask_false` and `mask_true` lower to
native predicate results (`m:=()`). They do not have vector or mask inputs, so
the previous scalable cases for value results, masked value results, comparison
results, masked comparison results, and mask-logic results did not cover them.
The fixed/generic path assumes a packed mask representation, which is not the
right contract for native SVE `svbool_t`.

Decision:

Add a narrow scalable mask-constant value-test boundary:

- SVE-authored mask-constant cases live in `tsldata` and provide expected
  predicate bits for a concrete authored lane count.
- The planner emits `scalable_mask_constant` only for backends that support
  that case kind, scalable extensions, result kind `m`, no parameters,
  runtime-lane metadata, and mask-check metadata.
- The plan carries the render-ready predicate-check expression through
  `ValueTestCasePlan.mask_check_expr`.
- The C++ renderer calls the selected primitive and formats the already-decided
  check expression. It does not inspect the catalog or branch on primitive or
  extension names.
- Scalable mask planning now lives in
  `tslc.value_tests._case_scalable_masks`, leaving the vector scalable planner
  and C++ scalable renderer below the module-size guardrail.

Consequences:

- `dev.sh test --profiles sve --primitives mask_true,mask_false --backends cpp`
  now emits and runs native scalable SVE value tests for mask constants.
- Predicate checking remains source/catalog-owned through extension test
  metadata.
- Packed integral-mask assumptions and fixed `vector::length` remain out of
  the scalable SVE value-test path.
- Rust SVE remains unsupported.

## ADR-111: C++ SVE Mask Conversion Uses Native-Predicate Identity

Context:

The SVE extension declares `integral_mask_type_policy kind "same_as_mask_type"`.
Therefore `typename Vec::imask_type` is the same native predicate type as
`typename Vec::mask_type` for `simd<T, sve>`. However `to_integral` had no SVE
implementation, and `to_mask` still used an older fixed-lane body that tried to
materialize an array through `vector::length`, `set_zero`, and `to_array`. That
body cannot be lowered for scalable vectors and also contradicts the extension
metadata that says no packed integral-mask conversion is needed.

Decision:

For scalable extensions whose integral-mask type is the same as the mask type:

- `to_integral` and `to_mask` are source-level identity conversions;
- SVE-authored value tests provide predicate bitsets for representative
  authored lanes;
- the planner emits `scalable_mask_conversion` only when the backend supports
  that case kind, the extension is scalable, `imask_policy.kind` is
  `same_as_mask_type`, and runtime-lane, predicate-construction, and
  predicate-check metadata are present;
- the C++ renderer formats the already-decided native predicate input, calls
  the selected conversion primitive, and checks the result through
  extension-owned predicate-check metadata;
- renderers do not inspect the catalog or branch on primitive/extension names.

Consequences:

- `dev.sh test --profiles sve --primitives to_integral,to_mask --backends cpp`
  now emits and runs native scalable SVE value tests for mask conversions.
- Packed integral-mask conversion remains out of scope for SVE until an
  extension declares a real scalar/packed `imask_type`.
- The next SVE mask gap is `to_vector` (`v:=m`), which currently has no SVE
  source implementation but can likely be composed from existing typed
  primitives such as masked `mov`, `set1`, and `mask::lane::all_true`.
- Rust SVE remains unsupported.

## ADR-112: C++ SVE Mask-To-Vector Uses Typed Primitive Composition

Context:

After SVE mask conversions, `to_vector` (`v:=m`) was the next mask-specific
gap. `./dev.sh explain --primitive to_vector --profile sve --type ui32
--backend cpp --extension sve` reported that the primitive had no SVE
implementation. Existing SVE primitives already provided the necessary typed
pieces: masked zeroing move (`mov[mask=zero]`), scalar broadcast (`set1`), and
the generation-time all-true mask lane value.

Decision:

Keep the implementation source-owned and planner-driven:

- add an SVE `to_vector` source implementation that composes
  `call<primitive=mov, attrs[mask=zero]>` with `call<primitive=set1>` of
  `value<generation>(mask::lane::all_true)`;
- add an SVE-authored `to_vector` value test for a representative predicate
  bitset and authored lane count;
- move mask-to-vector planning into a focused `_MaskToVectorPattern` in
  `tslc.value_tests._pattern_masks`;
- preserve the existing fixed/generic `mask_to_vector_case` path while adding
  scalable planning through the already-rendered `scalable_masked` case kind
  when runtime lanes, predicate-construction metadata, and load/store harness
  helpers are available;
- keep renderers as formatters of render-ready `ValueTestCasePlan` data.

Consequences:

- `dev.sh test --profiles sve --primitives to_vector --backends cpp` now emits
  and runs native scalable SVE value tests for mask-to-vector conversion.
- No compiler-side primitive or extension classifier branch was added for
  `to_vector` or `sve`.
- The next sampled SVE gap is mask representation memory, especially
  `store_mask_repr`, whose SVE body still depends on fixed `vector::length` and
  `mask<test>` over a native predicate.
- Rust SVE remains unsupported.

## ADR-113: C++ SVE Unpacked Mask Store Uses Vector Store Composition

Context:

After mask-to-vector coverage, `store_mask_repr` (`void:=(ptr,m)`) was the
next sampled SVE mask-memory gap. `dev.sh explain --primitive store_mask_repr
--profile sve --type ui32 --backend cpp --extension sve` selected the SVE body
but failed to lower all attribute slots because the source used fixed
`value<generation>(vector::length)` and `mask<test>` on native SVE predicates.
The existing `load_mask_repr` unpacked path already showed the viable typed
shape: use the lane-word storage layout and compose through vector/mask
primitives instead of treating the predicate as a fixed packed integer.

Decision:

For SVE `store_mask_repr` with `packed=false`:

- the source body composes `to_vector[MaskVec]` with `store[MaskVec]`, using
  `MaskWord = base::unsigned_of(base::in)` and the source-owned `param_types`
  storage contract;
- the unpacked path no longer uses fixed `vector::length` or `mask<test>` over
  a native predicate;
- the packed path remains deliberately unresolved because SVE declares
  `integral_mask_type_policy kind "same_as_mask_type"`, so a packed
  representation of native predicates needs an explicit typed contract rather
  than guessed byte storage;
- the value-test planner emits `scalable_mask_store` only for `packed=false`
  scalable cases with runtime-lane metadata, predicate construction metadata,
  and resolved pointer storage layout;
- the C++ renderer formats the render-ready plan and does not inspect the
  catalog or branch on primitive/extension names.

Consequences:

- `dev.sh test --profiles sve --primitives store_mask_repr --backends cpp` now
  emits and runs native scalable SVE value tests for unpacked mask storage.
- Existing compatible unpacked authored tests can also plan scalable SVE cases
  when the selected SVE specialization and storage layout match, so the planner
  is not tied to one SVE-only test name.
- `store_mask_repr packed=true` and `load_mask_repr packed=true` remain the
  next mask-representation design target.
- Rust SVE remains unsupported.
