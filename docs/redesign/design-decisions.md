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
