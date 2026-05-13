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

- Future review packets can run
  `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`.
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

Support only TSIL shaped as `emit_return(<parameter> + <parameter>);`, where both
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
- The selected `_mm256_add_ps` output can still be golden-tested, but tests must
  also prove the value came from typed metadata and lowered helper IR rather
  than a renderer table.
- Broad modifier support, primitive calls, direct intrinsics, and Rust body
  rendering remain deferred until their own helper slices are selected.
- Future native rendering milestones must state which helper IR and translation
  data they consume before adding generated output.
