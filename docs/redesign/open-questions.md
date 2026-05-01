# Open Questions

This file tracks unresolved questions. Do not guess answers that materially affect architecture.

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

Status: Answered for the Milestone 29 production-test rendering slice

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

Deferred answers:

- Executable generated assertions.
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

Not for Milestone 29. Broader generated-test behavior remains blocked on future
lane policy, assertion rendering, backend test harness, and execution
milestones.

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
`add_binary`, native `avx2/f32` `add_binary`, one future `add_i32_basic`
generated test source, and one future legacy-style coverage JSON row. Whole-file
header/report parity is not selected.

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
- Tiny sidecar files may use byte-for-byte parity when a future milestone
  selects them.
- C++ scalar `add_binary` and native `avx2/f32` code use semantic equivalence
  against frozen evidence plus redesign-owned exact golden output for the new
  renderer.
- Whole-file legacy whitespace, full header ordering, and full report byte
  parity are not selected.

Implementation blocked:

No for Milestones 36, 37, and 39 when they stay within the selected baseline.
Yes for any broader output family until that family records its parity level.

## OQ-032: Which TSIL Construct Should Follow The Mini Return Lowering?

Status: Narrowed for the next parity phase; exact fixture selected by
Milestone 35.

Why it matters:

Functional parity requires far more TSIL than the accepted direct
parameter-add return. The next TSIL step should be the smallest construct needed
by the selected C++ parity target, not a full grammar implementation.

Current recommendation:

Use `emit_return(intrin_compose<add>(left, right));` for one C++ floating-point
native `binary/add` slice. Defer integer suffix inference, primitive calls,
loops, variables, generation-time branches, type/value metadata, and Rust TSIL
lowering.

Milestone 35 selection:

The selected TSIL evidence is `tsldata/primitives/arithmetic/fundamental.tsl`
lines 77-80 for `avx2/f?` `emit_return(intrin_compose<add>(left, right));`.
The future native renderer baseline is the `simd<float, avx2>` specialization
in `frozen/out/tsl/tsl_native.hpp` lines 24337-24355.

Required evidence:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/tsl-gen/tsl_gen/tsil.lark`
- `frozen/tsl-gen/tsl_gen/tsil_engine/compiler.py`
- `tsldata/detail/lang/translate_cpp.tsl`

Implementation blocked:

No for Milestone 38 and Milestone 39 when they stay within the selected
`intrin_compose<add>` floating-point form. Yes for broader TSIL constructs until
their fixtures and expected models are selected.

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

Milestone 35 selection:

Use one future M41 workflow equivalent to:
`python -m tsl_gen --emit-lang cpp --input tsldata/primitives/arithmetic/fundamental.tsl --templates binary --primitives add --extensions scalar,avx2 --output <path>`.
The redesigned command may map this behavior through accepted `PipelineConfig`,
selection, rendering, and artifact writing; it must not import legacy CLI
modules or claim full `run_all.sh` compatibility.

Required evidence:

- `frozen/tsl-gen/tsl_gen/app/cli.py`
- `frozen/run_all.sh`
- `frozen/run_tests.py`

Implementation blocked:

No for C++ parity rendering. Yes for Milestone 41 and for any user-facing claim
of legacy CLI compatibility.

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

No for Milestone 40 test-source rendering. Yes for any milestone that compiles
or runs generated tests.

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
