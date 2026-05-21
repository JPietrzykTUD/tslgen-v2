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
  structural/request-only: recognize the exact trailing `emit_return(tmp);`
  slot from the accepted array-body path, link the returned token to accepted
  declaration-shell provenance, and emit diagnostics for nearby or malformed
  forms. The implementation keeps source intake narrow in
  `tslgen.lowering._return_emission`, and the focused revision removed the M87
  output from the shared runtime lowered-implementation source protocol. The
  decision explicitly rejects source-body repair, broad `emit_return(...)`
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
