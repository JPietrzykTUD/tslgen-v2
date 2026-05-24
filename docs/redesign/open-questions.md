# Open Questions

This file tracks unresolved questions. Do not guess answers that materially affect architecture.

## OQ-POST-M99: How Broad Should Backend-Value Translation Become After M100?

Status: Narrowed by post-M99 and post-M102 planning; broad support remains
open.

Why it matters:

M100 is accepted for resolving only the accepted exact-array C++
`value<backend>(uninit::array)` request into typed translation-result state.
The broader backend-value/type surface still includes Rust uninit values,
scalar and vector backend type spellings, modifier values, direct-intrinsic
requests, and body-level renderer-ready IR.

Current decision:

Do not broaden M100. M100 consumes explicit typed C++ rule input for the exact
array-uninit request and produces typed backend value state only. It must not
read backend maps/catalogs/manifests or `tsldata/detail/lang` during lowering,
render generated output, create Stage 9 backend plans, or infer Rust/type
context/direct-intrinsic semantics.

Current follow-up:

M103 created a static Stage 8 backend-translation boundary worklist inventory
over accepted concrete M99/M100 facts. M104 accepts a broadened
worklist-driven backend translation result expansion, covering the single
documented lowering gap from M103 worklist entry to typed translation
expansion result. M104 narrows exact-array backend-uninit unresolved and
selected-body direct-intrinsic deferred entries only through explicit typed
rule inputs. Broad backend-value/type translation, Rust rendering,
scalar/vector type spelling, backend modifier values, direct-intrinsic
broadening beyond accepted typed rules, renderer-ready exact-array body IR,
primitive calls/dependencies, and output integration remain open.

Implementation blocked:

No for M100, the accepted M103 inventory/provenance slice, or the accepted M104
explicit-rule translation expansion boundary. Yes for broad backend-value/type
translation, broad direct-intrinsic resolution, renderer-ready IR, and Rust
uninit rendering until typed context, rule, resolver, and rendering boundaries
are selected.

## OQ-001: What Exact Python Version Should The Redesign Target?

Status: Answered

Why it matters:

`tslgen/pyproject.toml` currently requires Python `>=3.14`, which is restrictive and may not match deployment expectations.

Decision:

Target Python `>=3.14` for the redesign. The dev container has Python 3.14.4 installed, and the existing `tslgen/pyproject.toml` already declares `requires-python = ">=3.14"`.

Considered answers:

- Keep `>=3.14`.
- Use a stable lower baseline such as `>=3.12`.
- Match the repository/devcontainer runtime.

Required evidence:

- Dev-container runtime: Python 3.14.4 is installed.
- Existing packaging sketch: `tslgen/pyproject.toml` declares `>=3.14`.
- Language features actually required should still be kept conservative and documented as implementation proceeds.

Implementation blocked:

No. Packaging and syntax choices may use Python 3.14 as the baseline. Implementations should still avoid unnecessary version-specific cleverness.

## OQ-002: Should Backend Manifests Remain YAML?

Status: Answered

Why it matters:

Legacy evidence stores backend behavior in YAML under `frozen/generator_specs`. The redesign can preserve YAML as a data format or move manifests into TSL/Python.

Decision:

Keep YAML as a supported manifest interchange format at the I/O boundary, but
do not make YAML structures part of downstream architecture. Backend planning
consumes typed `BackendManifest` and `BackendManifestSet` values.

Possible answers:

- Keep YAML with typed schemas.
- Convert manifests into TSL data.
- Define backend manifests in Python plugin modules.

Required evidence:

- Current C++ and Rust backend manifest fixtures exist at
  `frozen/generator_specs/backend_cpp.yaml` and
  `frozen/generator_specs/backend_rust.yaml`.
- C17 manifest fixtures also exist as legacy evidence, but C17 is no longer
  first-class in the current implementation roadmap.
- Current TSL language and translation declarations expose backend IDs under
  `tsldata/detail/lang/*.tsl`.

Implementation blocked:

No. Milestone 10 supports YAML loading into typed manifests and can also derive
a minimal manifest set from matching catalog `language` and `translation`
entries when artifact specs are known.

## OQ-003: What Is The Explicit Policy For List-Backed Implementation Variants?

Status: Narrowed in Milestone 20; broad support remains open.

Why it matters:

Some legacy selection paths accept list-backed implementation entries and select the first dict. This is likely accidental or underspecified.

Possible answers:

- Reject list variants until a selector field exists.
- Add priority fields.
- Add predicate-based variant matching.
- Preserve first-match only where golden evidence requires it.

Required evidence:

- Search current `tsldata/` for list-backed implementation variants.
- Identify whether generated outputs depend on ordering.
- Ask domain owners for intended semantics.

Resolution notes:

Milestone 20 rejects selected list-backed implementation variants with
structured implementation-spec diagnostics and does not preserve hidden
first-dict-wins behavior. Selector-aware promotion defers unsupported
list-backed branches that are irrelevant to the current request, so they do not
block valid selected branches. Broad support for list-backed variants remains
open until a predicate or priority policy is designed.

## OQ-004: How Much Byte-For-Byte Output Compatibility Is Required?

Status: Narrowed by Milestones 22, 26, 28, and 35; open for broad backend
rendering.

Why it matters:

Strict generated output compatibility can constrain rendering and formatting decisions.

Possible answers:

- Byte-for-byte compatibility for selected public headers only.
- Semantic compatibility with new formatting.
- Golden compatibility only for representative fixtures.

Required evidence:

- Consumers of generated headers/source.
- Existing release expectations.
- Selected golden baseline outputs.

Implementation blocked:

Not for the accepted scalar declaration/body slices or the Milestone 35
baseline-selection slice. Milestone 35 selects semantic equivalence plus
redesign-owned exact goldens for C++ `binary/add` scalar and `avx2/f32` parity
rather than whole-file byte-for-byte legacy output. Broad backend rendering
remains blocked until compatibility expectations are narrowed for each
production-shaped output family.

Resolution notes:

Milestone 22 establishes a new narrow C++ golden baseline for scalar `binary`
`si32` declarations. This baseline is behavioral and intentionally does not
claim byte-for-byte compatibility with legacy generated headers.

## OQ-005: What Is The Long-Term TSIL Grammar And Semantics?

Status: Narrowed through Milestone 27; broad TSIL grammar remains open

Why it matters:

TSIL includes calls, loops, type expressions, generation-time values, attributes, and backend translations. String rewriting will not scale.

Possible answers:

- Formalize TSIL grammar before backend work.
- Implement a minimal parser for dependency extraction first.
- Defer full TSIL semantics behind a typed-opaque lowering boundary.

Required evidence:

- `frozen/tsl-gen/tsl_gen/tsil.lark`
- TSIL bodies in `tsldata/primitives/**.tsl`
- Existing lowering behavior that must be preserved.

Implementation blocked:

Milestone 18 selected an explicit typed-opaque lowering boundary with
unsupported diagnostics. Milestone 27 adds a mini-lowered direct parameter-add
return form. Full TSIL grammar and semantic lowering remain open for later
lowering and production-rendering milestones; broad backend rendering must not
claim TSIL has been lowered until that future parser/model exists.

## OQ-006: How Should Generic/Sized Extensions Be Represented?

Why it matters:

Extensions such as `generic` and `oneAPIfpga` have `vector_bits "sized"` and tests use `test_sizes_bits`. Rendering may require type parameters such as `Bits`.

Possible answers:

- Model sized extensions as extension plus size parameter.
- Expand sized extensions into concrete target variants during selection/test planning.
- Treat sized bits as backend-specific generic parameters.

Required evidence:

- `tsldata/extensions/extension.tsl`
- Backend templates for generic and oneAPIfpga.
- Existing generated outputs for `frozen/out/tsl/tsl_generic.hpp`.

Implementation blocked:

Full generic backend planning is blocked. Basic fixed-width selection is not blocked.

## OQ-007: What Is The Correct Policy For Runtime-Lane Extensions Such As SVE?

Why it matters:

SVE has scalable vector length and runtime lane behavior. Test planning and generated code cannot assume fixed lanes.

Possible answers:

- Treat runtime-lane extensions as a separate test/generation mode.
- Skip specific templates according to manifest until full support exists.
- Generate runtime-lane-aware tests for all supported templates.

Required evidence:

- `tsldata/extensions/extension.tsl`
- `frozen/generator_specs/tests.yaml`
- `frozen/run_all.sh` SVE behavior.

Implementation blocked:

SVE test planning and backend slices are blocked. Fixed-lane backends are not blocked.
The accepted M70 lowering slice may represent explicit runtime/scalable
vector-length metadata as a typed value/policy or diagnose unsupported numeric
resolution, but it must not assume a fixed SVE lane count or decide SVE
backend/test generation policy. The accepted M71 vector-alignment slice is
similarly limited to explicit typed alignment metadata for the exact
array-initialization request. The accepted M72 helper-set completion slice
preserves backend uninit as a typed deferred boundary for that exact request,
but it does not decide broad SVE alignment, register, backend-uninit
translation, rendering, or test-generation policy.

## OQ-008: Which CLI Compatibility Is Required?

Status: Partially answered

Why it matters:

Legacy workflows expose `run_all.sh`, `run_tests.py`, and `python -m tsl_gen` options. The new CLI can be cleaner, but users may rely on existing flags.

Possible answers:

- New CLI with no compatibility promises.
- Compatibility subcommands or aliases for common legacy workflows.
- Keep shell workflow as wrapper around new CLI.

Required evidence:

- Current users and automation.
- CI scripts.
- Documentation or release expectations.

Implementation blocked:

No for the Milestone 13 public API and minimal diagnostic CLI. Yes for any
claim that the redesigned CLI is a drop-in replacement for legacy shell or
module workflows.

Current resolution:

- Milestone 13 implements a clean public API plus a narrow CLI adapter over it.
- The CLI does not promise compatibility with legacy flags or shell workflows.
- Milestone 24 adds explicit `--output-root`, `--dry-run`,
  `--no-skip-unchanged`, and `--coverage-report json|html` options for accepted
  writer and reporting capabilities.
- Milestone 25 will lock down the combined report/write CLI contract before
  broader output-mode UX or compatibility aliases are considered.
- Full legacy CLI drop-in compatibility, compatibility aliases, and broader
  output-mode UX remain unresolved before replacing legacy workflows.

## OQ-009: Should Generated Documentation Be In Scope?

Why it matters:

Legacy workflows generate TSL/TSIL documentation with MkDocs and coverage reports.

Possible answers:

- Include documentation generation as a later backend/reporting feature.
- Keep documentation tooling separate from the generator.
- Defer until code generation stabilizes.

Required evidence:

- Required docs outputs.
- Consumers of `frozen/docs` and generated site.

Implementation blocked:

Documentation generation remains blocked. Core generation is not blocked, and
the Milestone 23 HTML report artifact slice is not blocked.

Current status:

- Milestone 15 implements lightweight in-memory coverage summaries and
  deterministic JSON report text.
- Milestone 23 implements a deterministic legacy-style HTML coverage report
  artifact over accepted `PipelineCoverageReport` values.
- Full legacy HTML parity, generated documentation sites, report-writing UX, and
  documentation generation remain deferred under this question.

## OQ-010: What Backends Are First-Class For The First Release?

Status: Answered

Why it matters:

Evidence supports C++, Rust, and legacy C17, but implementation priority affects architecture and test coverage.

Decision:

C++ and Rust are first-class for the current redesign roadmap. C17 support is
deferred and should not appear in current implementation milestones. Backend
interfaces should remain extensible enough to add C17 later if it becomes a
priority again.

Considered answers:

- C++ only first, with backend protocol ready for others.
- C++ and Rust.
- C++, C17, and Rust from the start.

Required evidence:

- User direction: eliminate C17 support from the plan now.
- Existing consumer workflows.
- Golden baseline needs.

Implementation blocked:

No. Milestones should target C++ first and Rust after the backend protocol is
established. C17 is out of scope unless a new decision reintroduces it.

## OQ-011: Should Type And Template Shapes Be Parsed Or Kept As Strings Initially?

Why it matters:

`tsldata/detail/templates.tsl` has shape strings like `(vector, vector) -> vector`. They are useful for validation and docs but not yet formalized.

Possible answers:

- Parse shapes in the catalog milestone.
- Keep as strings and parse when needed.
- Replace with structured fields in TSL data.

Required evidence:

- How shapes are used by generators and tests.
- Whether shape strings are authoritative or descriptive.

Implementation blocked:

Not for early catalog construction. Stronger validation is blocked.

## OQ-012: What Is The Error Policy For Unknown Extra Fields?

Status: Narrowed in Milestone 20; broad strictness policy remains open

Why it matters:

TSL data may include backend- or future-specific fields. Strict rejection improves safety but may block extensibility.

Possible answers:

- Preserve unknown fields with warnings.
- Reject unknown fields outside documented extension maps.
- Allow unknown fields by namespace/prefix.

Required evidence:

- Current extra fields in `tsldata/`.
- Expected authoring workflow.

Implementation blocked:

Validation strictness is partially blocked. Catalog and implementation specs can
preserve extra fields now; future milestones should type only fields needed by
selection, lowering, rendering, test generation, or reporting.

## OQ-013: Should Artifact Writing Be A Separate Boundary From Rendering?

Status: Answered

Why it matters:

The accepted backend slices render in-memory artifacts only. Writing files introduces path safety, skip-unchanged behavior, dry-run behavior, and filesystem errors. Mixing those concerns into renderers would make backend behavior harder to test and review.

Decision:

Artifact writing is a dedicated I/O boundary scheduled for Milestone 16. Renderers produce artifacts; the writer validates paths, compares digests, creates directories, writes files, and returns deterministic write reports.

Possible answers:

- Keep writing inside renderers.
- Write artifacts through a separate filesystem writer.
- Delay writing until full backend generation.

Required evidence:

- Milestones 10, 11, and 14 already produce artifact descriptors and in-memory rendered artifacts.
- Milestone 13 CLI/API integration intentionally does not write output files.
- Milestone 15 reporting is pure and does not write report files.

Implementation blocked:

No. Milestone 16 can proceed using already-rendered artifacts and temporary-directory tests.

Current status:

- Milestone 16 adds the dedicated writer boundary with dry-run,
  skip-unchanged, path-safety, and deterministic write-report behavior.
- Milestone 24 exposes the writer through the API and CLI.
- Combined report/write CLI UX is scheduled for regression lock-down in
  Milestone 25.

## OQ-014: Should Reporting Be Exposed Through `tslgen.api`?

Status: Answered

Why it matters:

Milestone 15 added reporting helpers, but the current public API pipeline result does not expose reporting as a first-class API capability. Exposing it too early could freeze unstable report models; hiding it too long encourages callers to import internal modules.

Possible answers:

- Expose a stable `coverage_report(...)` helper through `tslgen.api`.
- Keep reporting under `tslgen.reporting` until report artifacts are implemented.
- Expose reporting only through a higher-level pipeline option.

Required evidence:

- API caller needs after Milestones 16 through 23.
- Whether report artifacts become part of normal generation output.
- Stability of coverage/report fields after backend rendering expands.

Implementation blocked:

No.

Decision:

Milestone 24 exposes a small stable reporting facade through `tslgen.api`.
`coverage_report(...)` derives a report from a `PipelineResult`, and dedicated
helpers serialize the report as deterministic JSON or HTML or wrap the HTML
report as an in-memory `ArtifactSet`. File writes are not part of the reporting
helpers; callers that want report or generated artifacts on disk must route the
artifact values through the accepted writer boundary.

## OQ-015: Should Dependency Closure Remain Primitive-Name Based?

Status: Resolved in Milestone 19 for the current typed-opaque lowering slice.

Why it matters:

The accepted dependency closure is intentionally conservative and primitive-name based. Real backend generation may need dependency edges between selected implementation candidates, lowered calls, or backend-specific render jobs.

Decision:

- Keep the Milestone 9 primitive-name closure as the stable broad dependency
  model.
- Add a candidate-specific closure layer for references that resolve to exactly
  one selected implementation candidate from already accepted metadata.
- Preserve primitive-name fallback entries, with warning diagnostics, for
  ambiguous, missing, or lowering-dependent references.
- Defer backend render-job dependencies until backend artifacts require them.

Required evidence:

- Dependency markers and call forms in implementation payloads.
- Lowering results from Milestone 18.
- Backend rendering needs from Milestone 22.

Resolution notes:

Milestone 18 established a typed-opaque lowering boundary, so Milestone 19 does
not treat conservative `call<primitive=...>` text extraction as final TSIL
semantics. Exact selected type tags may narrow candidate edges; generic
arguments such as `[Vec]` and `type<backend>(...)` remain unsupported for
candidate-specific resolution until semantic lowering exists.

## OQ-016: How Far Should Implementation Specs Be Promoted From Raw Catalog Values?

Status: Resolved in Milestone 20 for the currently consumed implementation
metadata.

Why it matters:

Milestones through 15 still allow some implementation metadata to travel as raw catalog values. Selection, lowering, dependency discovery, and backend rendering need stable typed semantics, but over-modeling unused fields would create premature architecture.

Decision:

- Promote only selected fields required by accepted selection planning,
  candidate selection, dependency discovery, lowering input preparation,
  coverage reporting, and summary backend rendering.
- Preserve unknown extra implementation fields as typed `extra_fields` on the
  implementation spec rather than discarding them or interpreting them early.
- Diagnose selected list-backed implementation variants until an explicit
  variant policy is accepted; do not preserve hidden first-dict-wins behavior.

Required evidence:

- Fields consumed by candidate selection.
- Lowering and dependency needs from Milestones 18 and 19.
- Real `tsldata/` examples, especially list-backed variants and unknown extra fields.

Resolution notes:

Milestone 20 introduced selector-aware `ImplementationSelector`,
`ImplementationBody`, and `ImplementationSpec` promotion. Broad backend
rendering remains blocked on future lowering and implementation semantics, but
accepted downstream stages now consume typed implementation specs for selected
fields they already use.

## OQ-017: What Belongs In The Production Validation Baseline Versus Exploratory Quarantine?

Status: Resolved for the Milestone 21 baseline.

Why it matters:

The repository contains accepted redesign code, exploratory sketches, legacy evidence, generated data, and tests. Future agents need a validation command that catches production regressions without being derailed by intentionally incomplete sketches.

Considered answers:

- Treat only documented production packages and tests as validation targets.
- Bring all exploratory code under the same validation baseline.
- Move or mark exploratory code so production imports cannot depend on it accidentally.

Decision:

Treat documented accepted redesigned modules and unit tests as the production
validation target. Quarantine exploratory sketches until a future milestone
promotes or removes them. The validation profile is implemented by
`tslgen.tooling.validation`.

Required evidence:

- Current package layout under `tslgen/`.
- Import graph of accepted implementation modules.
- Existing test and tool configuration in the dev container.

Implementation blocked:

No for the accepted baseline. Broad repository validation remains unsupported
until quarantined paths are cleaned up or promoted.

Resolution notes:

Milestone 21 quarantines pre-redesign `frontend`, `ir`, `middle_end`, `utils`,
and early core sketch files such as `core/passes.py`. The accepted baseline
includes current-corpus probes, unit discovery, targeted `compileall`, `ruff`,
targeted `mypy --explicit-package-bases`, and `git diff --check`.

## OQ-018: Which Backend Rendering Slice Should Follow Summary Artifacts?

Status: Resolved for Milestone 22.

Why it matters:

Milestones 11 and 14 render deterministic summary artifacts, not production C++ or Rust code. The first production-shaped rendering slice must be small enough to review and must not bypass lowering, dependency, or implementation-spec boundaries.

Considered answers:

- C++ first for one simple primitive/template class.
- Rust first for one simple primitive/template class.
- Defer production-shaped rendering until TSIL and implementation specs are more complete.

Decision:

Use C++ first for one scalar `binary` `si32` declaration slice inside the
existing `generated` artifact. Keep implementation bodies opaque and diagnose
selected candidates outside the supported declaration slice.

Required evidence:

- Lowering boundary result from Milestone 18.
- Dependency decision from Milestone 19.
- Typed implementation spec subset from Milestone 20.
- Output compatibility policy from OQ-004.

Implementation blocked:

No for the selected Milestone 22 slice. Further production-shaped rendering is
still blocked on TSIL lowering, broader type mapping, and output compatibility
decisions.

## OQ-019: What Is The CLI Contract When Reports And Writes Are Requested Together?

Status: Answered

Why it matters:

Milestone 24 added both `--coverage-report` and `--output-root`. Report output
can be machine-readable stdout, while write reports are also currently printed
to stdout when no report is requested. Combining both modes needs a stable
contract before users rely on CLI output.

Possible answers:

- Reserve stdout for the requested report and suppress write-report lines.
- Emit report to stdout and write-report lines to stderr.
- Add an explicit machine-readable combined envelope.

Required evidence:

- Current Milestone 24 CLI behavior.
- API/write-report structures from Milestone 16.
- User and automation needs for report parsing.

Implementation blocked:

No.

Decision:

Milestone 25 reserves stdout for the requested coverage report when
`--coverage-report` is combined with `--output-root`. Human-readable write-report
lines are emitted to stderr in combined report/write mode. When no report is
requested, write-report lines remain on stdout. Artifact files are written only
under an explicit `--output-root`, and all writes still go through
`io.artifact_writer`.

## OQ-020: What Is The C++ Function And Parameter Naming Contract?

Status: Answered for the Milestone 26 declaration slice; broader C++ ABI naming
remains open.

Why it matters:

Milestone 22 emits C++ scalar declarations. As declaration coverage expands,
function names and parameter names become observable generated output and golden
compatibility points.

Decision:

For the current C++ production declaration slice, function names are
`<emitted_primitive_name>_<type_tag>`. Parameter names are preserved from the TSL
primitive declaration. The renderer accepts only names that are already valid
non-keyword C++ identifiers and emits structured diagnostics for invalid
function or parameter names; it does not sanitize or mangle names.

Possible future answers:

- Introduce a backend-specific name mangling policy for attributes, extensions,
  overloads, wrappers, and public ABI forms.
- Add overload-safe names once overload and wrapper generation are in scope.
- Preserve the narrow diagnostic-only policy for all production-shaped output.

Required evidence:

- Existing C++ declaration slice.
- TSL primitive parameter names and overloaded primitive variants.
- Expected wrapper/public API naming behavior.

Implementation blocked:

Not for Milestone 26. Milestone 28 body rendering can proceed for the same
supported declaration slice. Broader generated C++ ABI naming remains blocked
until the corresponding output form is selected and documented.

## OQ-021: What Is The First Safe TSIL Mini-Lowering Subset?

Status: Answered for the Milestone 27 mini-lowering slice

Why it matters:

The accepted lowering boundary is typed-opaque and intentionally returns
unsupported diagnostics for semantic lowering. Real body rendering requires at
least one lowered TSIL form, but broad TSIL parsing is too large for one
milestone.

Decision:

Parse and lower only direct parameter-add returns shaped as
`emit_return(<parameter> + <parameter>);`. Both operands must resolve to
declared primitive parameter names. The lowered result is a backend-neutral
return statement with a binary `+` expression over parameter references.

Deferred answers:

- Full expression parsing.
- Dependency/call expression lowering.
- Generation-time branch evaluation.
- Translation-map and backend-specific lowering.

Required evidence:

- TSIL payloads in current `tsldata/`.
- Legacy TSIL grammar as behavior evidence.
- Needs of the planned C++ scalar body slice.

Implementation blocked:

Not for Milestone 27. Milestone 28 may render a C++ scalar body only from this
mini-lowered form. Broader body rendering remains blocked on future TSIL grammar
and semantic lowering work.

## OQ-022: What Is The First C++ Body Rendering Contract?

Status: Answered for the Milestone 28 scalar body slice

Why it matters:

Declarations prove naming and artifact structure, but production code needs
bodies. Rendering bodies before lowering exists would revive string-rewrite
behavior that the redesign rejects.

Decision:

Render one scalar C++ body from the Milestone 27 mini-lowered direct
parameter-add return form. The supported output remains limited to scalar
`binary` `si32`/`ui32` functions already covered by the declaration/naming
contract. Body rendering consumes `LoweringPlan` data and emits `return left +
right;`-style bodies from lowered parameter references.

Deferred answers:

- Broader expression rendering.
- SIMD/vector type mapping.
- Intrinsics and translation-map rendering.
- Wrapper and overload body generation.
- Rust production body rendering.

Required evidence:

- Mini-lowering output from Milestone 27.
- C++ declaration/naming contract from Milestone 26.
- Golden output expectations for the selected scalar fixture.

Implementation blocked:

Not for Milestone 28. Broader body rendering remains blocked on future TSIL
grammar, type mapping, backend translation, and wrapper policy milestones.

## OQ-023: What Should The First Production Test Rendering Artifact Look Like?

Status: Answered for the Milestone 29 metadata-style production-test rendering
slice and the accepted M49 generated C++ `add_i32_basic` test-source parity
slice.

Why it matters:

Milestone 17 plans production test sources as metadata, but no generated test
source text exists. The first rendering slice should prove the boundary without
starting compiler or runtime orchestration.

Decision:

Render a C++ metadata-heavy test source for the current scalar declaration/body
slice. The artifact consumes `TestSourcePlan` and emits deterministic
`scalar_binary_case` records for scalar `binary` `si32`/`ui32` planned tests.
The records include test name, primitive, generated function name, candidate ID,
extension metadata, type tag, lane metadata, input vectors, and expected vector.

Milestone 49 reintroduces a legacy-style generated C++ test-source parity slice
for only `add_i32_basic`. It must still consume typed `TestSourcePlan` /
`PlannedTestCase` data plus explicit typed C++ type-spelling input, but the
rendered source must preserve semantic evidence for wrapper-call intent, `Vec`
alias shape, boolean test function shape, and `TEST(...){ ASSERT_TRUE(...) }`
registration. It does not compile or run the test, infer type spellings
locally, or broaden support-header, runtime-lane, mask, Rust, or full legacy
framework policy.

Deferred answers:

- Executable generated assertions beyond the selected M49 semantic source
  shape.
- Lane resizing and runtime-lane policy.
- Mask/test-manifest policy.
- Compile/run orchestration.
- Rust test rendering.
- Full legacy test framework parity.

Required evidence:

- Test-source planning metadata.
- Selected backend rendering slice.
- Legacy test behavior only as evidence for expected inputs/outputs.

Implementation blocked:

Not for Milestone 29 and not for the selected M49 source-rendering parity
slice. Broader generated-test behavior remains blocked on future lane policy,
assertion rendering breadth, backend test harness, and execution milestones.

## OQ-024: How Complete Must Backend Manifests, Language Maps, And Translation Maps Be Before Broader Rendering?

Status: Answered for the Milestone 30 backend metadata boundary

Why it matters:

Backend manifests are typed, but language and translation catalog entries are
still only partially connected to lowering and rendering. Current default
manifest derivation also has to avoid accidentally reintroducing C17 as an
active backend.

Decision:

Validate active manifest/backend IDs against catalog language and translation
maps before broader rendering depends on those values. Promote TSL `language`
and `translation` declarations into typed boundary data for validation:
language maps expose source type keys and target type names, and translation
maps expose raw snippet templates. Do not evaluate translation maps or make
renderers consume them in Milestone 30.

`BackendManifestSet` remains the authoritative manifest source for artifact
planning. Catalog-derived manifest creation is limited to active backends with
matching language and translation data. The active backend IDs are `cpp` and
`rust`; `c17` remains deferred evidence and is not derived into active manifests
or planned for rendering.

Required evidence:

- `tsldata/detail/lang/types/types_cpp.tsl`,
  `tsldata/detail/lang/types/types_rust.tsl`,
  `tsldata/detail/lang/translate_cpp.tsl`, and
  `tsldata/detail/lang/translate_rust.tsl`.
- C++/Rust renderer needs after Milestones 27 and 28.
- C17 deferral decision.

Deferred answers:

- Full translation-map evaluation.
- Backend-specific lowering services over typed translation maps.
- Rust production-shaped declaration rendering.
- Reintroducing C17 as an active backend.

Implementation blocked:

Broader backend rendering and translation-map evaluation remain blocked until a
future lowering/rendering milestone consumes the typed boundary. Narrow C++ and
Rust declaration or summary slices are not blocked.

## OQ-025: What Is The First Rust Production-Shaped Rendering Slice?

Status: Answered for the Milestone 31 Rust signature slice

Why it matters:

Rust is first-class, but the accepted Rust backend still emits summary artifacts
only. The first Rust production-shaped slice should validate the backend
interface without duplicating C++ assumptions.

Decision:

Render body-free Rust trait function signatures for the same scalar primitive
class used by the accepted C++ declaration slice: scalar `binary` candidates
with normalized signature `v:=(v,v)` and type tags `si32` and `ui32`. The
signatures live in a small `pub mod production` section under a
`ScalarBinaryDeclarations` trait. This is a Rust-specific signature form, not a
copy of C++ free-function declaration syntax.

Rust function names are derived as `<emitted_primitive_name>_<type_tag>`.
Parameter names are preserved from the TSL declaration. Function and parameter
names must already be valid non-keyword Rust identifiers; the renderer does not
sanitize, mangle, or convert names to raw identifiers. The slice uses only a
local explicit type mapping: `si32 -> i32` and `ui32 -> u32`.

Required evidence:

- Rust summary renderer.
- Rust language/type map data.
- C++ naming/declaration lessons.

Implementation blocked:

No for this selected signature slice. Rust bodies, wrappers, trait parity,
intrinsic lowering, translation-map evaluation, generated tests, Cargo
integration, and broad Rust type mapping remain deferred.

## OQ-026: How Should Candidate-Specific Dependency Closure Appear In API And Reports?

Status: Answered for the Milestone 32 reporting/API slice

Why it matters:

Milestone 19 added candidate-specific dependency closure, but coverage reports
and public API consumers still primarily see primitive-level dependency
coverage. The extra precision should be inspectable without changing dependency
semantics.

Decision:

Milestone 32 retains candidate-specific dependency closure in the pipeline after
primitive-level dependency closure and exposes it through stable coverage-report
DTOs. `PipelineCoverageReport.candidate_dependencies` contains deterministic
edge rows, issue rows, fallback primitive names, ambiguous/missing/unsupported
groups, required candidate/primitive IDs, and candidate dependency diagnostic
counts. `tslgen.api.candidate_dependency_report(...)` returns that DTO from a
`PipelineResult` or an existing coverage report.

Evidence:

- The report should include candidate-specific dependency fallbacks because
  Milestone 19 accepted fallback preservation as part of the dependency model.
- Reports already preserve primitive-level dependency closure from Milestone 15,
  so candidate-specific rows are additive and do not replace the broad fallback
  model.
- The Milestone 24 API facade already exposes stable report helpers, so the
  candidate-specific helper returns a report DTO rather than making callers
  inspect raw dependency internals.

Implementation blocked:

No for the reporting/API slice. New dependency extraction semantics, TSIL call
graph parsing, dependency implementation selection, backend render scheduling,
and richer visualization remain deferred.

## OQ-027: What Should Happen To Quarantined Exploratory Code?

Status: Answered for the Milestone 33 retirement-planning slice

Why it matters:

The validation profile deliberately quarantines pre-redesign sketches. Leaving
them indefinitely increases confusion, but deleting them without a plan can
remove useful evidence or disrupt future work.

Decision:

Milestone 33 records the path-by-path plan in
`docs/redesign/exploratory-code-retirement-plan.md`. The accepted architecture
already covers frontend parsing, primitive/signature/extension modeling,
configuration context, pass orchestration needs, and hard-coded type helpers
through `io`, `syntax`, `domain`, `validation`, `analysis`, `lowering`,
`config`, and `api`, so those quarantined sketches are delete candidates after
focused cleanup tests. The middle-end sketch is evidence-only because it
documents dependency syntax, filtering concerns, and generation-time/type
rewrite motifs, but its implementation must not be promoted. `frozen` remains
evidence-only. Timing utilities and `tsldata` remain quarantined until future
performance/tooling and corpus-hygiene milestones decide their policy.

Evidence:

- Milestone 21 quarantine list.
- Current import boundaries.
- Any unique behavior evidence not already captured in docs or tests.

Implementation blocked:

No for semantic milestones. Direct code migration is not approved by Milestone
33. Future cleanup slices must update `tslgen.tooling.validation` and run
import-boundary or full validation checks according to the retirement plan.

## OQ-028: What Is The Policy For `tsldata/` Changes And Dirty Corpus State?

Status: Resolved for the Milestone 34 current slice; future corpus hygiene
expansion remains deferred.

Why it matters:

`tsldata/` is accepted source corpus and read-only fixture corpus. It is not
Python implementation code and not generated output. Future agents need to
classify TSL data changes without treating corpus churn as incidental
implementation cleanup.

Policy outcome:

- `tsldata/` content changes are source-data changes requiring focused
  behavioral evidence and relevant parser, catalog, validation, selection,
  backend metadata, lowering, or rendering tests.
- `tsldata/` may be used as read-only fixture corpus by deterministic
  current-corpus probes.
- Generated artifacts are separate from `tsldata/` and remain behind artifact
  writer and golden-fixture policies.
- Mode-only dirty state, such as `100644 => 100755`, is accidental local dirty
  state unless executable-bit intent is explicitly documented.

Deferred:

- Broader corpus probes.
- Corpus normalization.
- Permission-bit cleanup.
- Generated output regeneration.
- Validation-profile command changes.

Required evidence:

- Milestone 34 corpus policy in
  `docs/redesign/corpus-hygiene-policy.md`.
- Current dirty-worktree observations around `tsldata/**`, `.gitignore`, and
  `.devcontainer/**` showing mode-only zero-line diffs.
- Parser/current-corpus tests and existing catalog/validation probes that
  consume selected `tsldata` files.

Implementation blocked:

No current Milestone 34 implementation is blocked by this question. Future
corpus validation expansion or cleanup must be handled by focused milestones
and must not imply that all corpus hygiene work was completed by Milestone 34.

## Post-Milestone-34 Closure Review

Status:

Current roadmap phase closed. No remaining open question blocks a stabilization
pause.

Planner conclusion:

Milestones 25 through 34 answered or narrowed the immediate questions around
CLI report/write interaction, C++ naming, mini-TSIL lowering, scalar C++ body
rendering, metadata-style production test rendering, backend metadata
boundaries, Rust signatures, candidate-dependency reporting, exploratory-code
retirement, and corpus hygiene.

Questions that still require future planning are expansion questions, not
current blockers:

- OQ-003 list-backed implementation variant policy.
- OQ-004 broad generated-output compatibility policy.
- OQ-005 full TSIL grammar and semantics.
- OQ-006 generic/sized extension representation.
- OQ-007 runtime-lane extension policy.
- OQ-008 legacy CLI compatibility.
- OQ-009 generated documentation/report parity.
- OQ-011 structured type/template shape parsing.
- OQ-012 broad unknown-field strictness policy.
- Broader forms deferred inside OQ-020 through OQ-025, including C++ ABI/wrapper
  naming, broader C++ bodies, executable tests, translation-map evaluation, and
  Rust bodies.
- Cleanup execution deferred by OQ-027 and broader corpus normalization deferred
  by OQ-028.

Implementation blocked:

No for stabilization/release-readiness review. Yes for any future claim of full
legacy-generator replacement, broad backend rendering, full TSIL lowering,
executable production tests, or drop-in CLI compatibility.

## OQ-029: What Is The Stabilization Or Release Target After Milestone 34?

Status: Resolved for the current release-label slice by
`docs/redesign/stabilization-release-checklist.md`; not an implementation
blocker.

Why it matters:

The roadmap now has an accepted architectural foundation plus narrow
production-shaped slices. A stabilization pass needs to know whether the next
external milestone is an internal architecture checkpoint, an alpha package, a
replacement preview, or a production release.

Possible answers:

- Internal architecture checkpoint with validation and documentation only.
- Alpha release of the redesigned API/CLI for narrow supported slices.
- Preview release that explicitly excludes full code generation and legacy CLI
  compatibility.
- Production replacement release after a future feature phase expands lowering,
  rendering, tests, and compatibility.

Current recommendation:

Pause feature implementation and run the release-readiness checklist. The
chosen public alpha / pre-release label is `0.1.0a1`; a release candidate can be
cut without another implementation phase only under that narrow
architecture-foundation scope after all checklist blockers pass. A production
replacement release remains blocked until a future implementation phase expands
TSIL lowering, backend rendering, generated tests, and compatibility.

Required evidence:

- Intended users of the redesigned package.
- Required generated artifacts for the next external consumer.
- Required CLI/API compatibility commitments.
- Expected validation and packaging surface for the release.

Implementation blocked:

No for pausing implementation and running the stabilization checklist. Yes for
release packaging, compatibility promises, and any public claim that the
redesigned generator replaces the legacy workflow.

## OQ-030: Which Frozen Outputs Are The First Parity Golden Baselines?

Status: Answered for the first parity phase by Milestone 35.

Why it matters:

The legacy generator emits very large outputs. Treating every byte of
`frozen/out/**` as required would force a broad rewrite and make review
impossible. The next parity phase needs selected, representative golden
baselines with explicit parity levels.

Possible answers:

- Start with C++ `binary/add` excerpts from `frozen/out/tsl/tsl_native.hpp`.
- Start with C++ output layout and sidecars from `frozen/out/tsl`.
- Start with legacy coverage JSON rows.
- Start with generated C++ tests for one `add` case.
- Regenerate a new redesign-owned golden baseline when legacy output is too
  unstable or too broad.

Required evidence:

- `frozen/out/tsl/tsl_native.hpp`
- `frozen/out/tsl/tsl_generic.hpp`
- `frozen/out/tsl/CMakeLists.txt`
- `frozen/out/tsl/tsl_flags.cmake`
- `frozen/out/reports/primitive_coverage.json`
- `frozen/out/reports/primitive_coverage.html`
- `frozen/run_all.sh`

Decision:

Start with C++ `binary/add` excerpts from `frozen/out/tsl/tsl_native.hpp`,
recorded in `docs/redesign/frozen-parity-baselines.md`. The selected baseline
covers the `tsl/tsl_native.hpp` logical path, scalar `si32`/`ui32`
`add_binary`, native `avx2/f32` `add_binary`, the accepted M49
`add_i32_basic` generated test source, and the selected M50 legacy-style
coverage JSON row. Whole-file header/report parity is not selected.

Implementation blocked:

No for Milestone 36. Future output-parity renderers must consume the selected
baseline rather than choosing new frozen excerpts silently.

## OQ-031: Should Selected C++ Parity Targets Be Byte-For-Byte Or Semantic?

Status: Answered for the Milestone 35 selected C++ `binary/add` baseline; open
for broader output families.

Why it matters:

Some legacy C++ output contains broad preamble text and formatting that may be
incidental, while function names, wrapper shape, parameter order, return types,
and intrinsic/body semantics are externally observable. The redesign should not
make byte-for-byte compatibility the default for all output.

Possible answers:

- Byte-for-byte for selected excerpts only.
- Semantic parity for generated declarations/bodies/wrappers with
  redesign-owned formatting.
- Byte-for-byte for output path names and sidecars, semantic for C++ body text.
- New golden baseline for narrow slices where legacy text is unsuitable.

Required evidence:

- Selected excerpts from `frozen/out/tsl/tsl_native.hpp`.
- `frozen/jinja/cpp/primary.j2`
- `frozen/jinja/cpp/spec_binary.j2`
- `frozen/jinja/cpp/wrappers.j2`
- Known downstream consumers of generated headers, if any.

Decision:

- Output logical paths use exact parity for the selected artifact names.
- Milestone 36 selects exact logical-path parity for `tsl/tsl_native.hpp` and
  semantic parity for the support preamble, captured in a redesign-owned exact
  golden fixture.
- Tiny sidecar files may use byte-for-byte parity when a future milestone
  selects them. M36 explicitly defers `tsl/CMakeLists.txt` and
  `tsl/tsl_flags.cmake` because required native-extension flag coverage has not
  landed yet.
- C++ scalar `add_binary` and native `avx2/f32` code use semantic equivalence
  against frozen evidence plus redesign-owned exact golden output for the new
  renderer, but native parity must be reached through data-driven translation
  rather than renderer-local intrinsic lookup.
- Milestone 37 resolves the selected scalar portion by rendering
  `detail::add_binary`, scalar `simd<int32_t, scalar>` and
  `simd<uint32_t, scalar>` specializations, and the public `add<Vec>` wrapper
  delegation from typed candidates plus a `LoweringPlan`. Native `avx2/f32`
  parity may be represented by the accepted Milestone 39 transitional slice.
  Milestone 40 corrects intrinsic/type resolution for that selected output by
  translating the lowered helper data into backend-call IR before rendering.
  It does not authorize broader native intrinsic rendering.
- Whole-file legacy whitespace, full header ordering, and full report byte
  parity are not selected.

Implementation blocked:

No for Milestones 36 and 37 when they stay within the selected baseline. No
revert is required solely because Milestone 39 rendered the selected
`avx2/f32` output through a narrow local mapping, provided that mapping is not
expanded. Yes for any native expansion beyond the accepted M39/M40 slice until
a future milestone selects the next helper, type, extension, and translation
behavior. Yes for any broader output family until that family records its
parity level.

## OQ-032: Which TSIL Helper Boundary Should Follow The Mini Return Lowering?

Status: Answered for the Milestone 41 contract, Milestone 42 aligned-branch
slice, accepted/implemented Milestone 43 base type query slice, and
implemented Milestone 48 signedness branch-pruning slice. Narrowed, but not
closed, by the M44-M47 post-M43 native integer sequence and subsequent
M51-M57 lowering slices. M57 narrows only exact size-byte equality predicates
over `== 2`, `== 4`, and `== 8`; broader helper families remain open until
selected by future milestones.

Why it matters:

Functional parity requires far more TSIL than the accepted direct
parameter-add return. The previous next step selected only
`emit_return(intrin_compose<add>(left, right));`, but repository evidence shows
that `intrin_compose` belongs to a larger helper ecosystem with modifier
fields, generation-time type/value queries, generation-time branches, primitive
calls, loops, variables, casts, direct intrinsics, and translation-map helpers.
If the next slice ignores that context, backend renderers can drift into
hardcoded intrinsic and type lookup tables.

Current decision:

Do not treat a bare `intrin_compose<add>` parser or the Milestone 39
transitional renderer mapping as sufficient to unblock native backend
expansion. Milestone 38 lowers exactly
`emit_return(intrin_compose<add>(left, right));` into typed helper data.
Milestone 39 may preserve the selected observable native C++ output, but it is
not the architecture. Milestone 40 defines the first backend
translation/intrinsic-composition boundary and resolves the selected native
C++ call through typed data. Broader rendering still requires its own selected
helper and translation slices.

Milestone 41 defines the generation-time-before-backend-translation contract in
`generation-time-semantic-lowering.md` and selects boolean primitive-attribute
branch pruning for
`if<generation>(value<generation>(primitive::attribute(aligned)))` as the next
implementable helper slice. That selection does not implement type/value query
families, modifier evaluation, primitive calls, loops, or branch-dependent
backend rendering.

Milestone 42 implements that selected branch-pruning slice for `aligned`.
Diagnostics for unresolved nested generation-time helpers apply only to the
selected branch after pruning; helper forms in the unselected branch do not
poison a valid branch choice.

Milestone 43 implements the next helper/query family:
`type<generation>(base::in)`,
`type<generation>(base::signed_of(type<generation>(base::in)))`, and
`type<generation>(base::unsigned_of(type<generation>(base::in)))`. This
advances native integer `binary/add` suffix parity and later shift/conversion
work by creating typed generation type references before backend modifier
translation. It does not implement suffix/prefix/post/infix/immediate modifier
evaluation, backend type spelling, vector/register queries, or signedness
branch pruning. M43 uses request-local `GenerationContext.type_tag_override`
as the explicit override; missing override, missing context-selected type tag,
and missing selected candidate type tag produces
`TSL-LOWER-GEN-TYPE-CONTEXT-MISSING`.

The post-M43 roadmap narrows the next helper path without closing broad TSIL
semantics. Milestone 44 is documentation/planning only: it selects the backend
modifier value boundary and chooses intrinsic suffix first. Milestone 45
implements only the selected suffix request
`suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))`, with the input
constrained to the M43 `base.signed_of` result for selected `si32` and `ui32`
native integer add candidates; both resolve to typed suffix value `epi32`.
Milestone 46 provides selected C++ scalar backend type spelling over typed M43
inputs and language maps: `si32 -> int32_t` and `ui32 -> uint32_t`. Milestone
47 renders the selected native integer add output slice after consuming the M45
and M46 translated values.

Milestone 48 implements signedness type-predicate branch pruning for exact
`if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
plus `else<generation>` forms. M48 consumes typed M43
`GenerationTypeRef(kind="base.in")` values, produces a typed boolean
generation result, and prunes with M42-style selected-branch provenance. It does
not implement plain `else` conversion forms, backend translation, rendering,
shift/conversion body parity, or broader TSIL expression semantics.

Milestone 49 is accepted as generated C++ `add_i32_basic` test-source parity
from typed `TestSourcePlan` data and explicit typed C++ type-spelling input. It
does not add TSIL semantics, backend translation, generated C++ implementation
output, compiler execution, CLI/report parity, or broad generated-test
framework support.

The selected post-M49 plan is Milestone 50: one legacy coverage JSON adapter row
for `add`, `avx2`, `cpp`, `f32`. It stays in reporting, consumes accepted typed
coverage/report DTOs, and must not rerun parser, selection, lowering, backend
rendering, test rendering, CLI/writer, or compiler work during serialization.

Milestone 51 is accepted as the exact M48 signedness predicate branch form with
plain `else`. It stays in generation-time semantic lowering, consumes typed M43
`GenerationTypeRef(kind="base.in")` values, and does not add conversion body
lowering, backend translation, rendering, broad TSIL parsing, or generalized
plain-`else` support.

Milestone 52 extends the accepted concrete integer generation type and
signedness semantics to
`si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`. It remains
lowering-only and does not add backend suffix/type-spelling expansion,
vector/register metadata, branch-body lowering, generated output, or broad TSIL
parsing.
Milestone 53 moves those concrete integer rules into typed domain/catalog rule
values, and Milestone 54 wires the catalog-derived rule source through the
normal lowering-input path. Milestone 55 adds only
the exact scalar size-byte value query
`value<generation>(type::size_bytes(type<generation>(base::in)))` for explicit
selected scalar singleton tags. It produces a typed integer generation value
and does not lower surrounding IO, memory, array, bit-count, conflict, loop,
cast, call, direct-intrinsic, arithmetic, comparison, or branch bodies.
Milestone 56 adds only the exact
`value<generation>(type::size_bytes(type<generation>(base::in))) * 8`
arithmetic expression as a typed generation value; it does not lower
surrounding bodies or branch chains.
M57 adds only exact size-byte equality predicate lowering for
`type.size_bytes == 2/4/8`. It records typed boolean predicate values, but
still does not prune branch chains, lower SVE array bodies, direct intrinsics,
vector metadata, backend translation, or rendering.
Milestone 58 adds the accepted typed staged lowering contract so later
control-flow can consume typed predicate stage outputs instead of raw helper
text. Milestone 59 accepts the exact SVE size-byte branch-chain pruning slice.
Milestone 60 accepts only opaque selected-body handoff as a typed/provenanced
boundary. M61 accepts exact selected-body assignment-form recognition. M62
accepts only unresolved typed selected assignment/direct-intrinsic body IR
from the M61 records; direct-intrinsic semantics, SVE body semantics, vector
metadata, backend translation, rendering, and generated output remain deferred
until separate accepted milestones.
M63 accepts a backend-neutral selected-body envelope over M62 typed body IR
values. It adds a deterministic singleton sequence for the accepted M62
selected body and an explicit no-body envelope for no-body cases, but still
treats the surrounding SVE-looking array corpus text as evidence only.
Milestone 64 is accepted as exact structural array-body slot assembly around
M63 envelopes. It adds deterministic opaque pre/post slots for the exact
`array.tsl:105-111` body evidence and a branch slot referencing the M63
selected/no-body envelope, but it still leaves semantic questions about
declarations, arrays, direct intrinsics, SVE predicates, stores, returns,
vector metadata, backend values, translation, and rendering open.
Milestone 65 is accepted as exact array-body envelope pipeline integration. It
makes normal lowering produce M64 envelopes from typed/provenanced skeleton
input, but it still does not produce skeletons from raw body text or answer
semantic questions about the surrounding body.
Milestone 66 implements only the first surrounding-body question at form-IR
level: the exact `array.tsl:105` array-initialization slot becomes typed form
IR over accepted M65 envelopes. It still leaves vector metadata, backend
uninit evaluation, broad declaration/array semantics, store/return semantics,
SVE/direct-intrinsic semantics, translation, and rendering open.
Milestone 67 is accepted to classify exactly the four M66 helper leaves into
typed deferred helper-request/provenance IR. Milestone 68 is accepted to
resolve only the exact M67 base-type request for
`type<generation>(base::in)` through typed request IR and accepted
M43/M52/M53/M54 base-type semantics. It still does not evaluate vector
length/alignment or backend uninit helpers, and it does not answer semantic
questions about declarations, arrays, direct intrinsics, stores, returns,
translation, or rendering.
Milestone 69 is accepted as the answer to the immediate maintainability
question created by that accepted chain: extract the M64-M68
array-initialization stage assembly tail into a private typed helper/result
while preserving behavior. Milestone 70 is accepted to resolve only the exact
`value<generation>(vector::length)` request from explicit typed metadata
through that extracted pipeline. Milestone 71 is accepted to resolve only the
exact `value<generation>(vector::alignment)` request from explicit typed
metadata through the same staged pipeline. Milestone 72 is accepted to package
the exact helper set and preserve the remaining
`value<backend>(uninit::array)` request as a typed deferred backend-value
boundary. It still leaves backend uninit translation, declaration/array
semantics, aligned load/store semantics, rendering, output, and broad
vector/register metadata policy open.
Milestone 73 implements the next exact structural lowering step: typed
first-slot declaration-shell IR for the accepted `array.tsl:105`
`var<typed>(array_type<...>, tmp, ...)` shape. M73 narrows one structural
question but still leaves generic declaration/array semantics, allocation/
lifetime, initializer behavior, variable scope, store/return semantics,
`tmp.data()`, `emit_return`, backend uninit translation, rendering, output,
and broad vector/register metadata policy open.
Milestone 74 implements the exact source-ordered array-body structural
sequence and structural/provenance slot-role classification for the accepted
`array.tsl:105-111` shape. M87 later records the exact trailing
`emit_return(tmp);` slot as structural/request IR only. These milestones narrow
whole-body structure and one exact return-emission-shaped slot, but still leave
predicate semantics, SVE/direct-intrinsic semantics, generic body/declaration/
array semantics, variable scope, allocation/lifetime, initializer behavior,
`tmp.data()`, store semantics, broad return semantics, backend uninit
translation, rendering, output, and broad vector/register metadata policy open.
M88 narrows one more structural question by assembling the accepted M64-M87
exact array-body facts into a single typed, source-ordered package. That
accepted package remains structural/provenance state only; it still leaves
declaration semantics, array semantics, store semantics, `tmp.data()` pointer
semantics, SVE meaning, return semantics, backend uninit translation,
renderer-ready IR, generated output, and broad TSIL/body semantics open.
M89 narrows the backend-uninit handoff question by inventorying the accepted
M72/M67 `value<backend>(uninit::array)` deferred backend-value boundary from
the M88 package. That accepted inventory is still Stage 8
lowering/provenance state only; it leaves actual backend-uninit translation,
backend maps, renderer-ready IR, generated output, declaration/array
semantics, store semantics, and broad `value<backend>(...)` evaluation open.
M90 narrows the lowering handoff organization question by packaging accepted
M88/M89 exact facts into one Stage 8 completion package with explicit
unresolved dependencies. That accepted package still leaves actual backend-
uninit translation, backend maps, Stage 9 backend planning, renderer-ready IR,
generated output, declaration/array/store/return/SVE semantics, and broad
`value<backend>(...)` evaluation open.
M91 narrows the maintainability side of the same handoff path before adding
more semantics. It consolidates exact array pipeline result aggregation,
stage/snapshot assembly, and public handoff aggregation into focused private
ownership. It does not answer backend-uninit resolution, renderer-ready body
IR, broad body semantics, broad TSIL parsing, generic source protocols, or
fixpoint/backfeed policy.
M92 narrows the Stage 8-to-Stage 9 handoff shape by producing a typed exact
array backend-handoff request from the accepted M90 completion package, while
still leaving actual backend-uninit resolution, backend maps, Stage 9 backend
planning, renderer-ready body IR, generated output,
declaration/array/store/return/SVE semantics, and broad
`value<backend>(...)` evaluation open.
M93 is accepted and narrows the package organization side without staying
array-only. It packages exactly the accepted M86 mini-TSIL leaf return source
family and the accepted M92 exact array backend-handoff source family as
distinct Stage 8 typed entries, while still leaving semantic primitive calls,
dependency closure, backend-uninit resolution, backend maps, Stage 9 backend
planning, renderer-ready body IR, generated output, broad body semantics, and
broad `value<backend>(...)` evaluation open.
M94 is accepted and reduces operation-package maintainability risk before any
of those semantic gaps are tackled. It splits M93 diagnostics, source
narrowing, accepted M86 mini-TSIL package checks, exact-array provenance
validation, and package models into focused private modules, but it
intentionally leaves new package families, semantic primitive calls, dependency
closure, backend-uninit resolution, Stage 9 planning, renderer-ready body IR,
generated output, broad body semantics, and broad `value<backend>(...)`
evaluation open.
M95 is accepted as one new package family, but only over accepted M63/M62
selected-body direct-intrinsic facts. This does not resolve
SVE/direct-intrinsic semantics, byte-size-to-token inference, backend support,
primitive dependencies, Stage 9 planning, renderer-ready body IR, generated
output, broad body semantics, or broad `value<backend>(...)` evaluation.
M96 narrows the cross-family Stage 8 organization question by creating a
deterministic lowering completion manifest over accepted operation-package
facts and explicit unresolved dependency references. The accepted manifest
preserves package and unresolved dependency references by object identity, but
still leaves semantic body completion, backend-uninit resolution, backend
maps, backend support decisions, operation scheduling, dependency closure,
Stage 9 backend planning, renderer-ready body IR, generated output, broad body
semantics, and broad `value<backend>(...)` evaluation open.
M97 makes the remaining lowering-observed gap surface explicit without
resolving those open questions. The accepted inventory records accepted
unresolved backend-handoff dependency records from M96 and no-known-gap states,
but it still leaves backend-uninit resolution, backend maps, backend support
decisions, operation scheduling, dependency closure, Stage 9 backend planning,
renderer-ready body IR, generated output, broad body semantics, and broad
`value<backend>(...)` evaluation open.
M98 is accepted as behavior-preserving Stage 8 stage-assembly ownership
extraction. It addresses the local maintainability pressure around
`boundary.py` by moving accepted stage construction and accepted per-candidate
completion-tail assembly into focused private `_lowering_stage_assembly.py`
ownership. It does not resolve backend-uninit, backend maps, backend support
decisions, operation scheduling, dependency closure, Stage 9 planning,
renderer-ready body IR, generated output, broad body semantics, or broad
`value<backend>(...)` evaluation.
M99 is accepted as the inventory of accepted backend-scoped request facts
visible from package/manifest/gap state. M99 narrows what later backend
translation/planning must consume, but it does not resolve backend values,
evaluate maps, schedule operations, solve dependencies, create Stage 9 plans,
render output, or prove whole-lowering completeness. The broader known missing
lowering surface is tracked in
`docs/redesign/missing-lowering-inventory.md`.

Remaining deferred work includes broad TSIL grammar, full translation-map
evaluation, prefix/post/infix/immediate modifiers beyond the selected suffix,
vector/register metadata, signedness branch forms beyond the exact M48/M51/M52
predicate/branch syntax and selected concrete integer type set, primitive
calls, loops, variables, generation-time branches beyond the selected aligned
primitive-attribute and signedness predicate conditions, type/value metadata
beyond the selected base type query family, M55 size-byte value query,
accepted M56 exact size-bytes-times-eight expression, accepted M57 exact
size-byte equality predicates, branch-chain pruning beyond the accepted narrow
M59 slice over those predicates, selected body handling beyond the accepted
opaque M60 handoff, M61 assignment-form recognition slice, accepted M62
unresolved body-IR shape, accepted M63 singleton envelope shape, accepted M64
narrow structural slot envelope, accepted M65 pipeline integration, accepted
M67 helper-request/provenance IR over the M66 first-slot leaves, accepted M68
base-type request resolution, accepted M69 behavior-preserving extraction,
accepted M70 exact vector-length request resolution, accepted M71 exact
vector-alignment request resolution, accepted M72 exact helper-set completion,
implemented M73 exact first-slot declaration-shell structural IR, implemented
M74 exact array-body structural sequence and structural/provenance slot-role
classification, accepted M75 exact predicate-path structural/request IR,
accepted M76 exact post-branch intrinsic call-site structural/request IR,
accepted M77 behavior-preserving lowering pipeline/module-boundary cleanup,
accepted M78 behavior-preserving lowering boundary package decomposition, and
accepted M79 exact array-body typed model ownership extraction, accepted M80
exact array-body validation boundary extraction, accepted M81 generation-time
lowering core ownership extraction, accepted M82 selected-body envelope
ownership extraction, accepted M83 stage-contract ownership extraction,
accepted M84 exact array-body pipeline and source-adapter ownership
extraction, accepted M85 selected-body lowering ownership extraction, and
accepted M86 candidate payload-intake and mini-TSIL leaf return lowering
ownership extraction, accepted M87 exact return-emission structural/request IR,
accepted M88 exact array-body structural package assembly, accepted M89 exact
array backend-deferred request inventory, and accepted M90 exact array
lowering completion-package handoff, plus accepted M91 exact array pipeline
ownership consolidation, accepted M92 exact array backend-handoff request,
accepted M93 lowering operation-package boundary, accepted M94
operation-package ownership split, accepted M95 selected-body
direct-intrinsic operation package, accepted M96 lowering completion manifest,
and accepted M97 lowering completion gap inventory, while body-slot semantics
beyond those exact structural/request/inventory/package/manifest/gap
boundaries, including nested expressions, direct
`intrin<...>` calls, helper families such as `io`, `mem`, `seq`, `pack`, and
`algo`, Rust output, generated tests beyond the selected M49 source fixture,
CLI/report parity, compiler execution, and broad native rendering.

Required evidence:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/load_store/rnd_access.tsl`
- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/*.py`
- `frozen/tsl-gen/tsl_gen/resolver/render_support.py`
- `frozen/out/tsl/tsl_native.hpp`

Implementation blocked:

No for Milestone 38 and no need to revert Milestone 39 solely on boundary
grounds. No for the Milestone 41 documentation contract, the Milestone 42
aligned-branch pruning slice, the accepted/implemented Milestone 43 base type
query slice, or the Milestone 44 documentation/planning milestone.

No for the selected `avx2` `si32`/`ui32` native integer `binary/add` output:
Milestone 47 renders that slice from explicit M45 suffix and M46 type-spelling
values. Yes for native integer rendering expansion beyond that selected slice.
Backend translation must not parse raw
`type<generation>(...)` text, and renderers must not evaluate generation-time
helpers, suffixes, or type spelling locally. No for the M48
signedness-pruning slice because it stays inside generation-time semantic
lowering. No for the selected M49 generated C++ `add_i32_basic` test-source
parity plan because it consumes typed test-plan data and stays out of lowering,
translation, generated implementation rendering semantics, and compiler
execution; any type spelling used by its `Vec` alias must arrive as explicit
typed input. Yes for broader TSIL constructs, broad native rendering, Rust
output, generated-test breadth, CLI/report parity, and compiler execution until
their fixtures, expected models, and validation boundaries are selected.

## OQ-033: Which Legacy CLI Workflow Should Be Supported First?

Status: Narrowed by Milestone 35; blocks broad CLI compatibility claims, not
C++ rendering parity.

Why it matters:

Legacy scripts expose many workflows: generation, build, test, run, docs,
clean, examples, extension autodetection, cross-run ARM/SVE/NEON handling, and
Rust/C++ language selection. A broad clone would pull toolchain orchestration
into the CLI before behavior is selected.

Current recommendation:

Start with one generation-only workflow equivalent to selecting C++,
input/primitives/templates, and an output file. Defer `run_all.sh` build/test
orchestration, docs generation, clean mode, and test execution.

Milestone 35 selection, now deferred by the backend-drift correction roadmap:

Use one future CLI compatibility workflow equivalent to:
`python -m tsl_gen --emit-lang cpp --input tsldata/primitives/arithmetic/fundamental.tsl --templates binary --primitives add --extensions scalar,avx2 --output <path>`.
The redesigned command may map this behavior through accepted `PipelineConfig`,
selection, rendering, and artifact writing; it must not import legacy CLI
modules or claim full `run_all.sh` compatibility. This workflow should not be
scheduled until Milestone 40 corrects the native translation boundary or until
the CLI slice explicitly limits itself to scalar output.

Required evidence:

- `frozen/tsl-gen/tsl_gen/app/cli.py`
- `frozen/run_all.sh`
- `frozen/run_tests.py`

Implementation blocked:

No for C++ parity rendering. Yes for the deferred CLI workflow milestone and for
any user-facing claim of legacy CLI compatibility.

## OQ-034: What Is The First Executable Test Parity Boundary?

Status: Open; not part of the first parity implementation slice.

Why it matters:

The legacy test workflow can fetch googletest, configure CMake/Cargo, run
host-specific or cross-target tests, and summarize results. Default redesign
validation must remain host-independent, so execution parity needs its own
toolchain policy.

Possible answers:

- Render generated tests only and keep execution manual.
- Add optional `toolchain` tests for selected C++ generated fixtures.
- Add a dedicated compile/run orchestration layer with explicit compilers,
  qemu, rustup targets, and network-free dependencies.

Required evidence:

- `frozen/run_all.sh`
- `frozen/run_tests.py`
- `frozen/jinja/cpp/test_file.j2`
- `frozen/jinja/cpp/test_case.j2`

Implementation blocked:

No for the selected M49 generated-test source rendering milestone because it
does not compile or run generated tests. Yes for any milestone that compiles or
runs generated tests.

## OQ-035: How Should Backend Intrinsic Composition Be Data-Driven?

Status: Answered for the selected Milestone 40 slice and narrowed for the
post-M43 suffix/type-spelling phase; broader native intrinsic composition
remains open.

Why it matters:

The current C++ native parity work exposed a renderer-local mapping from
`("add", "avx2", "f32")` to `_mm256_add_ps`. That can reproduce one observable
output, but it is not the generator architecture: intrinsic names should be
composed from TSIL helper IR and typed `tsldata` translation/type/extension
metadata. If this boundary is not explicit, each backend renderer will grow its
own semantic translation table.

Possible answers:

- Add a lowering-owned backend translation service that resolves
  `IntrinsicCompose` helper IR into backend-call IR before rendering.
- Add a backend-owned translation service that is called from lowering but kept
  outside text renderers.
- Keep literal intrinsic names only for direct `intrin<...>` forms and use
  data-driven composition for `intrin_compose<...>`.
- Temporarily allow a one-case map only in a translation fixture, never in a
  renderer, until richer modifier semantics are implemented.

Required evidence:

- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- modifier-heavy examples in `tsldata/primitives/bitwise/shifts.tsl`,
  `tsldata/primitives/conversion/repr_change.tsl`, and
  `tsldata/primitives/load_store/rnd_access.tsl`
- legacy evidence in `frozen/tsl-gen/tsl_gen/resolver/render_support.py`

Implementation blocked:

No for Milestone 38 and no automatic revert for the accepted Milestone 39
transitional parity slice. No for the selected Milestone 40 correction that
preserves the M39 output through backend-call IR. Yes for any native C++ or
Rust intrinsic rendering expansion beyond the selected M39/M40 output until a
future milestone selects and tests the next data-driven composition path.

Current roadmap direction:

- Milestone 39 is a transitional selected-output spike, not an expansion
  pattern.
- Milestone 40 owns the first typed translation/composition boundary and
  preserves the M39 output through backend-call IR.
- Milestone 40 rejects unresolved generation-time helpers at the translation
  boundary; it does not evaluate `if<generation>`, `type<generation>`, or
  `value<generation>` itself.
- Milestone 41 defines the generation-time semantic lowering contract that runs
  before backend translation.
- Milestone 43 supplies typed `GenerationTypeRef` inputs for exact base scalar
  type queries.
- Milestone 44 selects intrinsic suffix as the first backend modifier family.
- Milestone 45 provides only suffix translation over typed M43 inputs.
- Milestone 46 provides selected C++ scalar type spelling over typed M43 inputs.
- Milestone 47 expands only the selected native integer add output after M45 and
  M46 translation results exist.
- Milestone 48 implements the selected return to generation-time semantic lowering for
  signedness branch pruning over typed M43 `base.in` values; it does not add
  native rendering expansion.
- M99 inventories accepted backend-scoped request facts before backend
  planning. It does not answer the broader data-driven intrinsic composition
  question and does not evaluate translation maps.
- Renderer-local intrinsic lookup tables are rejected as an implementation
  strategy for future native expansion.

## OQ-036: Where Do Generation-Time Helpers Resolve Relative To Backend Translation?

Status: Answered for Milestone 41, implemented for the first Milestone 42
helper slice, narrowed for the Milestone 43 base type query slice, preserved by
the numbered M44-M47 post-M43 phase, implemented for the M48 signedness
branch-pruning slice, implemented for the M51 exact plain-`else` signedness
branch extension, implemented for the M52 concrete integer type/signedness
expansion, moved to typed M53 rule-source values, and wired through the normal
catalog/lowering-input path by M54. M55 adds only
the exact scalar
`value<generation>(type::size_bytes(type<generation>(base::in)))`
generation-value query before backend translation. Milestone 56 adds only the
exact size-bytes-times-eight generation-value arithmetic expression before
backend translation. M57 adds only exact
size-byte equality predicates over `== 2`, `== 4`, and `== 8`; it keeps branch
chains, body lowering, backend translation, and rendering deferred.

Why it matters:

TSIL expressions such as `if<generation>(...)`, `type<generation>(...)`, and
`value<generation>(...)` affect which code exists and which semantic type/value
is passed into backend translation. If backend translation evaluates those
forms from raw text, it becomes a second TSIL interpreter and backend renderers
can again accumulate semantic rules.

Decision:

Generation-time helpers resolve before backend translation. The ordered model
is TSIL helper parse, generation-time semantic lowering, backend translation,
then backend rendering. Backend translation may consume `type<backend>(...)`
and `value<backend>(...)` only as typed requests whose inputs are already
resolved semantic values.

Milestone 41 selects and Milestone 42 implements the first slice: evaluate
`if<generation>(value<generation>(primitive::attribute(aligned)))` from explicit
primitive attributes and prune the selected branch with deterministic
provenance. The selected branch is checked for unresolved nested
generation-time helpers; the unselected branch is discarded without recursive
helper diagnostics. Milestone 43 resolves only exact base
scalar type queries:
`type<generation>(base::in)`,
`type<generation>(base::signed_of(type<generation>(base::in)))`, and
`type<generation>(base::unsigned_of(type<generation>(base::in)))`. These
resolve to typed semantic type values before backend translation. Milestone 48
evaluates only
`value<generation>(type::is_signed(type<generation>(base::in)))` over M43
`GenerationTypeRef(kind="base.in")` values and prunes exact
`if<generation> ... else<generation>` branches before backend translation.
Milestone 51 adds only the same signedness predicate branch with plain `else`.
M52 extends only the accepted concrete integer type/signedness rules to
selected 8/16/32/64-bit signed and unsigned tags.
Milestone 53 moves the accepted concrete integer semantic rule source to typed
domain/catalog rule values consumed by lowering. It does not add new generation
helper forms or backend translation behavior. Milestone 54 wires those rule
values through the normal catalog/lowering-input path for pipeline-facing use
by constructing lowering requests with explicit catalog-derived rules.
M55 resolves only
`value<generation>(type::size_bytes(type<generation>(base::in)))` to a typed
integer generation value for explicit selected scalar singleton tags; it does
not broaden standalone float `base.in` type refs, signed/unsigned companion
semantics, or backend translation.
Vector type/value queries, backend prefix/post/infix modifiers, `immediate(n)`,
primitive calls, loops, direct intrinsics, generalized plain `else` branch
syntax, backend suffix/type-spelling expansion for non-32-bit tags, and broader
branch body semantics remain deferred.
The known deferred lowering surface is tracked in
`docs/redesign/missing-lowering-inventory.md`; M99 inventories accepted
backend-scoped request facts only and does not change the generation-before-
backend ordering decision.

Milestones 44 through 47 preserve this decision. M45 and M46 are backend
translation slices that consume typed M43 values; they do not parse raw
generation helper text. M47 is a rendering slice that consumes translated
suffix/type-spelling values and must not evaluate helper or backend metadata
semantics locally. M48 returns to generation-time semantic lowering and does
not reopen the M45/M46 translation or M47 rendering boundaries. The M49
generated-test source slice stays in test-source rendering and likewise does
not reopen generation-time lowering, backend translation, or generated C++
implementation rendering; C++ type spelling must arrive as typed input rather
than renderer-local inference.
The selected M50 coverage JSON adapter row stays in reporting and likewise does
not reopen generation-time lowering, backend translation, backend rendering, or
renderer-local semantic inference.
The accepted M51 lowering slice reopens only generation-time branch syntax for
the exact signedness predicate with plain `else`; it does not reopen backend
translation, backend rendering, or renderer-local semantic inference.
M52 reopens only the concrete integer type set for accepted generation-time
type and signedness rules; it does not reopen backend translation, backend
rendering, or renderer-local semantic inference.
Milestone 53 reopens only the ownership boundary for those accepted concrete
integer rules; it does not reopen helper syntax, selected tag sets, backend
translation, backend rendering, or renderer-local semantic inference. The
M54 wiring slice reopens only catalog-to-lowering wiring for that rule source.
M55 reopens only one scalar generation-value helper; it does
not reopen backend translation, rendering, output, broad TSIL parsing,
generation-value arithmetic/comparisons, or surrounding body lowering.
Milestone 56 reopens only the exact scalar
`value<generation>(type::size_bytes(type<generation>(base::in))) * 8`
arithmetic expression. It does not reopen general arithmetic, comparisons,
branch pruning, `else if<generation>`, surrounding body lowering, backend
translation, rendering, output, broad TSIL parsing, or runtime dependency on
`frozen/`.
M57 reopens only exact
`type.size_bytes == 2/4/8` predicates. It does not reopen branch pruning,
broad `else if<generation>`, final-else policy, direct-intrinsic/body
lowering, backend translation, rendering, output, broad TSIL parsing, or
runtime dependency on `frozen/`.

Required evidence:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/generation_ifs.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/types.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/values.py`

Implementation blocked:

No for M40 because the selected `avx2/f32` default intrinsic-composition case
can remain generation-free and must reject unresolved generation-time inputs.
No for the Milestone 41 documentation contract, the Milestone 42
primitive-attribute branch pruning slice, or the Milestone 43 base type query
slice. No for the M48 signedness branch-pruning slice because the
implementation remains lowering-only. Yes for
modifier support beyond accepted suffix/type spelling, branch-dependent output
beyond selected branch pruning, vector/generic metadata queries, and broad
translation-map evaluation until later numbered slices implement the selected
generation-time semantic lowering behavior.

## OQ-037: Where Should Clean Restart Code Live?

Status: Answered by M105 charter; execution is assigned to M106.

Why it matters:

The current top-level `tslgen/` tree contains old accepted/exploratory state.
Adding clean restart code beside it would blur runtime imports, tests, and
review expectations.

Decision:

Before new clean restart product code is added, move the current top-level
`tslgen/` tree wholesale to `tslgenold/` as quarantined old-state evidence.
Reserve a fresh top-level `tslgen/` path for the clean implementation.
`tslgenold/` has the same evidence-only status as `frozen/` and must not
become a runtime dependency of the clean generator.

Implementation blocked:

Yes for clean restart product-code milestones until M106 or an explicitly
accepted equivalent layout reset creates the same separation. No for M105
documentation work.

## Follow-ups from Milestone 2 review

- Add focused tests for invalid UTF-8 and read failure diagnostics where practical.
- Standardize whether file-level diagnostics use synthetic locations such as `line=1, column=1` or `location=None` before CLI diagnostic rendering.
- Clarify whether source digests are computed over normalized text or raw bytes before digest behavior becomes externally visible.

## Follow-ups from Milestone 3 review

- Clarify parser public API exports and keep Lark construction private. 
- In Milestone 4, verify SyntaxNode structure is sufficient for typed catalog construction without parser-private leakage. 
- Consider changing the corpus test to assert “all discovered files parse” without hard-coding the count, or document the count as an intentional current-corpus check.

## Follow-ups from Milestone 4 review

- Replace generic `CatalogEntry` with typed models for flags, language type maps, translation maps, primitive tests, and implementation specs when later milestones require semantic access to those concepts.
- Revisit whether catalog construction should remain in `domain` or move to a boundary/conversion module if the strict target-architecture dependency rule becomes important.
- Add focused tests for duplicate fields inside extension, template, and primitive bodies if duplicate fields are intended to remain structural errors.
- Watch repeated nested field representation: tuple-grouped repeated fields may need a richer representation if occurrence identity matters during later validation.

## Follow-ups from Milestone 5 review

- Add focused tests for invalid signature syntax with source locations.
- Add direct tests for `v:=sequence` parameter-count behavior.
- Clarify whether repeated declaration parameters must include `...`.
- Treat the signature rule table as typed behavioral data; consider moving it to a typed manifest once rule churn slows.

## Follow-ups from Milestone 6 review

- Add typed flag models and flag-alias normalization before or during Milestone 7.
- Promote primitive tests and implementation specs out of generic `CatalogValue` structures when later stages depend on them.
- Add a focused test for all-unknown selectors in unambiguously extension-keyed `requires` maps.
- Revisit conservative `requires` validation once flags and implementation specs are typed.
- Decide whether `ReferenceValidatedCatalog` should remain a marker-only pipeline gate or gain stronger typed invariants in later stages.

## Follow-up from Milestone 7 review

- During Milestone 8, promote implementation metadata out of generic catalog values only as concrete selection needs become clear.

## Follow-ups from Milestone 8 review

- Addressed in Milestone 10: backend artifact planning treats
  `BackendManifestSet` as the authoritative backend-ID source, with optional
  minimal manifest derivation from matching catalog `language` and `translation`
  entries.
- Addressed in Milestone 10: artifact planning has focused unknown-backend
  diagnostic tests.
- Add focused tests for malformed or missing implementation body diagnostics.
- Continue promoting implementation specs out of raw catalog values only as later stages require them.

## Follow-ups from Milestone 9 review

- Add focused tests for malformed or incomplete dependency marker diagnostics.
- Addressed in Milestone 10: artifact descriptors preserve the current
  primitive-name closure and do not choose dependency implementations.
- Addressed in Milestone 10: `behavioral-spec.md` documents the conservative
  primitive-level closure boundary for artifact descriptors.

## Follow-ups from Milestone 10 review

- Clarify that skip-unchanged artifact writer behavior belongs to a later writer stage, not Milestone 10.
- Add a later writer milestone/test for skip-unchanged behavior and real artifact digests.
- Keep the actual writer boundary explicit when `io.artifacts` starts performing file writes.
- Addressed in Milestone 11: backend mismatch is a renderer diagnostic. The
  C++ renderer rejects non-`cpp` artifact plans/descriptors and candidates
  selected explicitly for a different backend.

## Follow-ups from Milestone 11 review

- Addressed in Milestone 12: added a regression test proving generic
  `backend=None` candidates are accepted by the C++ renderer.
- Addressed in Milestone 12: added focused tests for non-`cpp` artifact plan
  and descriptor rejection.
- Keep the future artifact writer as a separate I/O boundary, not an expansion of the renderer.

## Follow-ups from Milestone 12 review

- Create or rename a future milestone for production test-source planning from TSL `tests` declarations.
- Move the older broad Milestone 12 test-planning bullets into that future test-generation milestone so future agents do not treat them as already satisfied.
- Keep artifact writing and skip-unchanged behavior out of the golden harness and in a future writer boundary.

## Follow-ups from Milestone 13 review

- Addressed in Milestone 14: added a focused public API test that loads a Rust
  backend manifest from a path and renders the in-memory Rust summary artifact.
- Addressed in Milestone 14: introduced a small backend renderer registry used
  by the public API for C++ and Rust rendering dispatch.
- Keep output writing and skip-unchanged behavior in a later writer boundary.

## Follow-ups from Milestone 14 review

- Keep output writing and skip-unchanged behavior in a later writer boundary.
- Avoid expanding the backend registry into lifecycle/plugin mechanics until a real extension need appears.

## Follow-ups from Milestone 15 review

- Addressed by the post-Milestone-15 roadmap in `docs/redesign/implementation-roadmap.md`.
- Addressed in Milestones 16 through 24: artifact writing, production
  test-source planning, lowering boundary, candidate-specific dependency
  closure, implementation spec promotion, validation quarantine, C++ declaration
  rendering, HTML coverage artifacts, and API/CLI polish.

## Follow-up from Milestone 16 review

- Addressed in Milestone 24: API/CLI exposure of artifact writing preserves the
  dedicated writer boundary.

## Follow-up from Milestone 17 review

- Add broader tests for `to_type` / `to_extension` planning metadata when the next testgen slice starts using those fields semantically.

## Follow-up from Milestone 18 review

- Addressed in Milestone 19: aligned the `domain-model.md` lowering snippet
  with the implementation field name `LoweringPlan.input_set`.
- Addressed in Milestone 19: candidate-specific dependency closure preserves
  primitive-level fallbacks for generic or lowering-dependent TSIL references
  instead of treating conservative text extraction as final semantics.

## Follow-up from Milestone 19 review

- Addressed in Milestone 20: dependency reference attributes and body payload
  access are routed through typed implementation spec objects for accepted
  downstream uses.

## Follow-up from Milestone 20 review

- Addressed in Milestone 21: the selector-aware current-corpus probe is part of
  the validation baseline.

## Follow-up from Milestone 22 review

- Scheduled for Milestone 26: document the C++ function naming and parameter
  naming contract as the declaration slice expands.

## Follow-up from Milestone 23 review

- Addressed in Milestone 24: API/CLI reporting keeps HTML generation pure and
  routes writes through `io.artifact_writer`.

## Follow-up from Milestone 24 review

- Scheduled for Milestone 25: add CLI regression coverage for combining
  `--coverage-report` with `--output-root`, including
  `--no-skip-unchanged`, to lock down stdout and write-report expectations.

## Follow-up from Milestone 25 review

- Keep future CLI output changes under the accepted stream contract:
  - report-only: report on stdout
  - write-only: write report on stdout
  - report + write: report on stdout, write report on stderr

## Follow-up from Milestone 26 review

- Keep broader C++ ABI naming, wrappers, overloads, and attribute-sensitive names explicitly deferred until their own reviewed slice.

## Follow-up from Milestone 27 review

- Keep Milestone 28 constrained to consuming the lowered model; C++ body rendering must not rescan raw TSIL payload text.

## Follow-up from Milestone 28 review

- Add a focused future test for `TSL-CPP-RENDER-LOWERING-PARAMETER` to make the defensive diagnostic contract explicit.

## Follow-ups from Milestone 29 review

- Add a focused conversion-shaped test-rendering diagnostic test for `to_type` / `to_extension`.
- Before executable generated tests, promote enough planned-case metadata to distinguish primitive/template/signature shape explicitly rather than relying on vector-count shape alone.

## Follow-up from Milestone 30 review

- Use `BackendMetadataBoundary` as the input contract for future translation-aware lowering/rendering milestones, and keep translation snippets unevaluated until that slice is explicitly selected.

## Follow-up from Milestone 31 review

- Keep future Rust body rendering behind a lowering-backed slice.
- Define any broader Rust trait/wrapper API as its own reviewed contract.

## Follow-up from Milestone 32 review

- Keep future dependency visualization/API additions DTO-based.
- Preserve primitive-level fallback visibility alongside candidate-specific dependency precision.

## Follow-up from Milestone 33 review

- Addressed in Milestone 34: `docs/redesign/corpus-hygiene-policy.md` defines
  `tsldata` corpus hygiene, dirty-worktree classification, generated/cache file
  policy, and the rule that corpus validation uses deterministic data probes
  rather than Python lint/type checks.

## Follow-up from Milestone 34 review

- Keep broader corpus probes, normalization, permission-bit cleanup, generated-output regeneration, and validation-profile command changes as separate focused milestones.

## Follow-ups from package-boundary release re-review

- Release version label decided: use `0.1.0a1` for the public
  alpha/pre-release under PEP 440.
- Before publishing any artifact, rebuild from a clean worktree.
- Archive the wheel/sdist leak scan and validation output with the release notes or release-readiness record.

## Follow-ups from Milestone 41 review

- In M42, add focused fixtures/tests for:
  - `aligned=true` branch pruning.
  - `aligned=false` branch pruning.
  - selected-branch-only nested-helper diagnostics.
  - missing `aligned` attribute diagnostics.
  - non-boolean `aligned` attribute diagnostics.
  - renderer non-evaluation of generation-time helpers.
- Ensure unresolved nested-helper diagnostics apply only after branch pruning to the selected branch; helpers in the unselected branch must not poison a valid branch choice.

## Follow-ups from Milestone 42 review

- Document explicitly that selected candidate variant attributes are the default primitive-attribute generation context unless `GenerationContext.primitive_attributes` is supplied.
- Add a translation-boundary regression where a raw generation branch is first pruned by lowering and then accepted by C++ translation because branch provenance is present.
- Consider hardening empty selected-branch handling so it returns a structured diagnostic rather than relying only on the `PrunedGenerationBranch` invariant.

## Follow-ups from M43 planning review

- Addressed in Milestone 43: fixed the stale `base::in` inventory citation to
  use the stronger `repr_change.tsl:1210-1225` evidence.
- Addressed in Milestone 43: exact accepted forms are written as
  `type<generation>(base::signed_of(type<generation>(base::in)))` and
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`; shorthand
  wording is labeled prose-only where retained.
- Addressed in Milestone 43: `GenerationContext.type_tag_override` is the
  concrete override field, and `TSL-LOWER-GEN-TYPE-CONTEXT-MISSING` triggers
  when no override, no context-selected type tag, and no selected candidate
  type tag is available.
