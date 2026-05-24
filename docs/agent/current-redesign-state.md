# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 110 is accepted.

Post-M98 planning is accepted. It selected
`Milestone 99: Operation Package Backend-Translation Request Inventory Slice`,
and internal planning review returned `Accept With Follow-Ups`. Human
acceptance was recorded.

Post-M99 planning selected
`Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice`,
and internal planning review returned `Accept With Follow-Ups`. Human
acceptance was recorded.

The M100 execution-review loop returned `Accept With Follow-Ups` after focused
rule-validation, source/container diagnostic, determinism, and documentation
revisions. M100 added the typed
`exact_array_backend_uninit_translation_result` stage after the accepted M99
request-inventory stage when explicit typed C++ `value_array_uninit` rules are
supplied. It preserved accepted M99/M97/M96/M92/M72/M67 provenance identities
and kept rendering, output, Stage 9 planning, Rust translation, generic backend
helper evaluation, backend map/catalog/manifest reads, raw helper parsing,
source repair, and direct-intrinsic/SVE semantics out of scope.

Post-M100 planning selected
`Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice`.
The selected plan responds to the IR-complexity concern by defining a smaller
lowering IR taxonomy/provenance contract and applying it only to the accepted
M99/M100 backend-translation request/result path. Human acceptance was recorded.

The M101 execution-review loop returned `Accept With Follow-Ups`. M101 added a
small private lowering IR contract/provenance module, attached explicit
taxonomy contracts only to the accepted M99/M100 backend-translation
request/result path, consolidated repeated key-comparison and object-identity
mismatch helper shape, and preserved accepted M99/M100 behavior, keys,
diagnostics, source locations, object identities, stage names, ordering, and
public imports. It kept new lowering semantics, backend translation semantics,
new request/result families, rendering/output, Stage 9 planning, Rust
translation, generic backend helper evaluation, backend map/catalog/manifest
reads, raw source parsing, source repair, selected-body direct-intrinsic
resolution, SVE semantics, scheduling, dependency closure, broad hierarchies,
registries, dispatchers, hidden backfeeds, and fixpoint mechanisms out of
scope.

Post-M101 planning selected
`Milestone 102: Lowering IR Category Protocol Surface Slice`.
The selected plan responds to the concern that M101 added stable category
labels and contract attachments, but not yet a stable reusable typed protocol
surface for future lowering IR. Human acceptance was recorded.

The M102 execution-review loop returned `Accept With Follow-Ups` after a
focused protocol-conformance revision. M102 added a small private typed
category/protocol surface in `_lowering_ir_contracts.py` for lowering facts,
request IR, translation requests, translation results, inventories,
provenance, rule inputs, stage outputs, and diagnostic boundaries. The surface
is applied first to the accepted M99/M100 backend-translation request/result
path and requires typed contracts plus non-empty tuple keys for structural
conformance. It preserved accepted M99/M100 behavior, keys, diagnostics,
source locations, object identities, stage names, stage ordering, public
imports, and deterministic behavior. It kept new lowering semantics, new
request/result families, backend translation semantics, rendering/output,
Stage 9 planning, Rust translation, generic backend helper evaluation, backend
map/catalog/manifest reads, raw source parsing, source repair,
selected-body direct-intrinsic resolution, SVE semantics, scheduling,
dependency closure, broad inheritance, registries, dispatchers, callback
systems, plugin mechanisms, hidden backfeeds, fixpoint mechanisms, and
category-based semantic dispatch out of scope.

Post-M102 planning selected
`Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice`.
Internal planning review returned `Accept With Follow-Ups` after narrowing the
initial broad worklist idea into a static typed Stage 8 inventory/provenance
view over accepted concrete M99/M100 facts. Human acceptance was recorded.

The M103 execution-review loop returned `Accept With Follow-Ups` after a
focused fake-object validation revision. M103 added a private typed Stage 8
backend-boundary worklist inventory over accepted concrete M99 request
inventories and optional concrete M100 exact-array backend-uninit translation
results. It classifies accepted exact-array backend-uninit translated records,
exact-array backend-uninit unresolved requests, selected-body direct-intrinsic
deferred requests, and explicit no-accepted-backend-boundary-fact records while
preserving source object identity and deterministic ordering. It rejects
arbitrary protocol-shaped fake objects and malformed source containers with
diagnostics. It kept the worklist as a static inventory/provenance view only,
with no queue, scheduler, readiness oracle, Stage 9 backend plan,
renderer-ready IR, backend-map/catalog/manifest reads, source scanning,
translation lowerer calls, direct-intrinsic/SVE resolution, source repair,
category-based semantic dispatch, facade integration, stage-contract
integration, or `boundary.py`/`_lowering_ir_contracts.py` growth.

Post-M103 planning selected
`Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice`.
Internal planning review returned `Accept With Follow-Ups` after local
planning-doc revisions. Human acceptance was recorded. The selected plan
intentionally broadens beyond one literal M103 classification by treating
"M103 worklist entry to typed translation expansion result" as one documented
lowering gap. M104 remains a typed Stage 8 lowering slice: it may consume the
accepted `exact_array_backend_uninit_unresolved` and
`selected_body_direct_intrinsic_deferred` M103 worklist classifications, but
semantics must come only from explicit typed rule inputs over concrete typed
request/result objects. It must not turn the M103 worklist into a scheduler,
readiness oracle, Stage 9 plan, renderer-ready IR, backend-map evaluator,
source scanner, registry, dispatcher, hidden backfeed, or fixpoint mechanism.

The M104 execution-review loop returned `Accept With Follow-Ups`. M104 added
focused private backend translation expansion modules that consume only
accepted concrete M103 `Stage8BackendBoundaryWorklistInventoryIr` values and
produce typed resolved/deferred/unsupported translation expansion result
records. It accepts only the `exact_array_backend_uninit_unresolved` and
`selected_body_direct_intrinsic_deferred` M103 classifications. Missing rules
produce typed deferred records; mismatched, duplicate, or conflicting rules for
accepted entries produce typed unsupported records; malformed fake inputs and
malformed containers fail at the boundary with diagnostics. M104 preserves
M103/M99/M100 provenance and object identity, uses explicit
`Stage8BackendTranslationExpansionRule` inputs only, and does not infer from
SVE-looking tokens, extension ids, type tags, byte sizes, primitive names, raw
direct-intrinsic token text, source-location text, or hardware-looking tokens.
It kept rendering, renderer-ready IR, generated output, Stage 9 backend
planning, backend-map/catalog/manifest reads, source repair/reparse, Rust
rendering, scheduler/readiness behavior, dependency closure, registries,
dispatchers, callbacks, plugins, hidden backfeeds, fixpoint machinery,
category-based semantic dispatch, public facade integration,
`GenerationLoweringStageName`, `_stage_contracts.py`, `boundary.py`,
`_lowering_ir_contracts.py`, M99/M100 modules, and M103 worklist modules out of
scope.

Post-M104 planning selected
`Milestone 105: Clean KISS Generator Restart Charter Slice`. The selected plan
responds to the project owner's concern that the accepted M57-M104 lowering
path captured useful requirements but had become too complex for a research
prototype. M105 freezes the accumulated lowering/request/result/worklist chain
as evidence and plans a simpler object-oriented restart path from `.tsl`
source data to a validated catalog, selected implementations, and
deterministic C++ and Rust library artifacts. A user correction requires the
restart layout to move the current top-level `tslgen/` tree to `tslgenold/`
as old-state evidence while reserving `tslgen/` for the new clean
implementation. Local planning review returned `Accept With Follow-Ups`;
human acceptance was recorded.

The M105 documentation execution-review loop returned
`Accept With Follow-Ups`. M105 created
`docs/redesign/kiss-generator-restart.md`, recorded the restart as a
source-to-artifact product path, made M57-M104 evidence rather than default
architecture, and drafted M106 as the structural layout reset that must move
the current `tslgen/` tree to `tslgenold/` before clean restart product code
is added under a fresh `tslgen/`.

The M106 execution-review loop returned `Accept With Follow-Ups` after a
focused documentation cleanup. M106 moved the pre-restart top-level `tslgen/`
tree wholesale to `tslgenold/` as evidence-only old implementation state,
reserved a fresh top-level `tslgen/` path with only a README placeholder, and
updated layout/workflow docs. It kept `frozen/` unchanged and did not add
parser, catalog, generator, backend, renderer, writer, CLI, fixture, test, or
generated-output product code.

The M107 execution-review loop returned `Accept` after focused architecture,
documentation, and validation revisions. M107 added the first tiny clean
restart source-to-artifact slice under fresh `tslgen/`: explicit source
loading, narrow parsing for the documented M107 fixture form, typed catalog
values, parser-to-domain catalog promotion outside `domain`, explicit target
selection, deterministic C++ and Rust in-memory artifact values, focused
fixtures/tests, root pytest path configuration, and a repo-root import shim for
uninstalled validation. It preserved `tslgenold/` and `frozen/` as
evidence-only, did not port old modules, and did not add broad TSIL/body
semantics, dependency closure, backend manifests, CLI compatibility, artifact
writing, generated-output parity, lowering IR taxonomies, worklists,
registries, dispatchers, hidden backfeeds, or fixpoint mechanisms.

The M108 execution-review loop returned `Accept`. M108 added the first tiny
clean lowering boundary under fresh `tslgen/`: selected M107 `add` / `binary`
/ `scalar` / `si32` implementations lower into backend-neutral
`LoweredFunction` values with deterministic name, parameters, scalar type tag,
and binary-add expression. The generator now lowers after selection and before
backend emission, and C++/Rust emitters consume `LoweredFunction` values
instead of catalog bodies. M108 preserved M107 artifact contents, logical
paths, digests, diagnostics, and deterministic ordering. It did not import
from `tslgenold/` or `frozen/`, write generated files, port old lowering
modules, add broad TSIL/body semantics, expression parsing beyond the exact
fixture, branch pruning, dependency closure, backend manifests, type maps
beyond `si32`, lowering IR taxonomies, worklists, registries, dispatchers,
plugin systems, hidden backfeeds, or fixpoint mechanisms.

The M109 execution-review loop returned `Accept With Follow-Ups`. M109 added
the first explicit filesystem-write boundary for clean restart artifact values:
`ArtifactWriter` consumes existing in-memory `ArtifactSet` values and an
explicit output root, validates logical paths before writing, returns
deterministic typed write reports, and exposes `write_artifacts(...)` while
leaving `generate_from_paths(...)` pure and in-memory. It rejects absolute
logical paths, parent-directory escapes, duplicate logical paths, duplicate
normalized target paths, and file/directory collisions with structured
`TSL-WRITE-*` diagnostics before writing partial artifacts. It did not import
from `tslgenold/` or `frozen/`, add CLI integration, generated test execution,
CMake/Cargo scaffolding, broad output tree parity, output-root cleaning,
formatting or compiling generated C++/Rust, old writer migration, new lowering
semantics, backend manifests, dependency closure, registries, dispatchers,
plugin systems, hidden backfeeds, or fixpoint mechanisms.

The M110 execution-review loop returned `Accept With Follow-Ups`. M110
broadened the tiny clean lowering path from a one-off `si32` check into a
small lowering-owned scalar type descriptor table for `si32`, `ui32`, `f32`,
and `f64`. `LoweredFunction` now carries a backend-neutral descriptor with
tag, scalar kind, integer/floating family, bit width, and signedness. C++ and
Rust spellings remain backend-owned in their emitters. The parser/catalog
still preserve the exact tiny scalar `add(left, right)` source shape while
allowing identifier-like type tags, and syntactically valid but unsupported
tags fail in lowering with `TSL-LOWER-UNSUPPORTED-TYPE`. Existing `si32`
artifact bytes, logical paths, and digests remain stable. M110 did not import
from `tslgenold/` or `frozen/`, add CLI work, writer changes, vector/SIMD
semantics, broad TSIL parsing, backend-manifest/type-map reads, old
type/lowering migration, dependency closure, registries, dispatchers, plugin
systems, hidden backfeeds, fixpoint mechanisms, or a broad type-system
framework.

Post-M47 planning is accepted. The accepted planning result selected
Milestone 48, and the M48 execution-review loop returned `Accept`.

Post-M48 planning is accepted. It selected Milestone 49, and internal review
accepted the plan after local planning-doc revisions.

The M49 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M49 planning is accepted. It selected Milestone 50, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M50 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M50 planning is accepted. It selected Milestone 51, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M51 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M51 planning is accepted. It selected Milestone 52, and internal review
returned `Accept With Follow-Ups` after a workflow handoff correction.

The M52 execution-review loop returned `Accept With Follow-Ups` after a
documentation wording cleanup.

Post-M52 planning is accepted. It selected Milestone 53, and internal review
returned `Accept With Follow-Ups` after a workflow handoff wording correction.

The M53 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M53 planning is accepted. It selected Milestone 54, and internal review
returned `Accept With Follow-Ups` after a workflow handoff correction.

The M54 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M54 planning is accepted. It selected Milestone 55, and internal review
returned `Accept With Follow-Ups` after local planning-doc updates.

The M55 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M55 planning is accepted. It selected Milestone 56, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M56 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M56 planning is accepted after user-requested revision. It selected
`Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice`. The
roadmap also records draft staged-lowering follow-on candidates for a stage
pipeline boundary, branch-chain pruning, and opaque selected-body handoff; they
are not active for execution.

The M57 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M57 planning is accepted. It selected
`Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice`, and
internal review returned `Accept With Follow-Ups` after local state wording
corrections.

A user-requested workflow correction sharpened the M58 handoff: the generated
M58 execution prompt must require an extendable, maintainable typed lowering
stage contract, not a cosmetic wrapper or broad central string evaluator.

The M58 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M58 planning selected
`Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice`, and
internal review returned `Needs Revision` only for workflow handoff wording
that was corrected locally.

Post-M58 planning is accepted. It selected
`Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice`.

The M59 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M59 planning selected
`Milestone 60: Opaque Selected Branch Body Handoff Slice`, and internal review
returned `Accept With Follow-Ups` after workflow handoff corrections.

Post-M59 planning is accepted. It selected
`Milestone 60: Opaque Selected Branch Body Handoff Slice`.

The M60 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M60 planning is accepted. It selected
`Milestone 61: Selected Branch Body Assignment Form Recognition Slice`, and
internal review returned `Accept With Follow-Ups` after local state wording
corrections.

The M61 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M61 planning selected
`Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice`, and
internal review returned `Accept With Follow-Ups` after local planning-doc
updates.

Post-M61 planning is accepted. It selected
`Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice`.

The M62 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M62 planning selected
`Milestone 63: Backend-Neutral Selected Body Envelope IR Slice`, and internal
review returned `Accept With Follow-Ups` after local planning-doc updates.

Post-M62 planning is accepted. It selected
`Milestone 63: Backend-Neutral Selected Body Envelope IR Slice`.

The M63 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M63 planning selected
`Milestone 64: Exact Array Body Envelope Slot Assembly Slice`, and internal
review returned `Accept With Follow-Ups` after local planning-doc updates.

Post-M63 planning is accepted. It selected
`Milestone 64: Exact Array Body Envelope Slot Assembly Slice`.

The M64 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M64 planning selected
`Milestone 65: Exact Array Body Envelope Pipeline Integration Slice`, and
internal review returned `Accept With Follow-Ups` after a focused workflow
handoff correction.

Post-M64 planning is accepted. It selected
`Milestone 65: Exact Array Body Envelope Pipeline Integration Slice`.

The M65 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M65 planning selected
`Milestone 66: Exact Array Initialization Slot Form IR Slice`, and internal
review returned `Accept With Follow-Ups` after local planning-doc updates.

Post-M65 planning is accepted. It selected
`Milestone 66: Exact Array Initialization Slot Form IR Slice`.

The M66 execution-review loop returned `Accept` after one focused
public-boundary revision, generated package artifact cleanup, and focused
documentation wording revisions.

Post-M66 planning is accepted. It selected
`Milestone 67: Exact Array Initialization Helper Request IR Slice`, and
internal review returned `Accept With Follow-Ups` after a focused workflow
state correction.

The M67 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M67 planning is accepted. It selected
`Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice`,
and internal review returned `Accept With Follow-Ups` for the selected slice
after identifying a workflow handoff correction. Human acceptance included the
condition that M68 must avoid hardwiring.

The M68 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision documenting the M68 diagnostics. Review and
audit found no blocking implementation, validation, boundary, evidence, or
documentation issues after that revision.

Post-M68 planning is accepted. It selected
`Milestone 69: Exact Array Initialization Stage Pipeline Extraction Slice`,
and internal review returned `Accept With Follow-Ups` after local
planning-doc updates.

The M69 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, extensibility, documentation,
or evidence issues. Review recorded one non-blocking follow-up for explicit
pipeline-level M67 diagnostic propagation coverage.

Post-M69 planning is accepted. It selected
`Milestone 70: Exact Array Initialization Vector-Length Request Resolution Slice`,
and internal review returned `Accept With Follow-Ups` after local
planning-doc updates. The selected plan requires explicit typed
vector-length metadata before lowering evaluation and must not infer lane
counts from raw text, SVE tokens, vector-bit strings, host CPU state, catalog
data, backend maps, or renderers.

The M70 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or evidence
issues after that revision. M70 resolves only the exact M67
`value<generation>(vector::length)` request through typed M68/M69 pipeline
values and explicit typed vector-length metadata; vector alignment and backend
uninit remain unresolved.

Post-M70 planning selected
`Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice`,
and internal review returned `Accept With Follow-Ups` after local planning-doc
updates. The selected plan requires explicit typed vector-alignment metadata
before lowering evaluation and must not infer alignment from vector length,
vector bits, scalar byte size, selected type tags, SVE tokens, extension names,
host CPU state, catalog data, `tsldata`, backend maps, backend
vector-alignment spellings, or renderers.

Post-M70 planning is accepted. It selected
`Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice`.
Human acceptance was recorded.

The M71 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or evidence
issues after that revision. M71 resolves only the exact M67
`value<generation>(vector::alignment)` request through typed M67/M68/M69/M70
pipeline values and explicit typed vector-alignment metadata; backend uninit
remains unresolved.

Post-M71 planning selected
`Milestone 72: Exact Array Initialization Helper-Set Completion IR Slice`,
and internal review returned `Accept With Follow-Ups` after identifying a
workflow handoff correction. The selected plan completes the exact
array-initialization helper set as typed lowering state while keeping the
remaining `value<backend>(uninit::array)` request as a typed deferred
backend-value boundary. It must not add backend translation, rendering,
generated output, or declaration/array semantics. Human acceptance has been
recorded; M72 execution was the next action.

The M72 execution-review loop returned `Accept With Follow-Ups` after focused
documentation consistency revisions. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or
evidence issues after those revisions. M72 completes the exact first
array-initialization helper set as typed lowering state by packaging accepted
M68 base type, accepted M70 vector length, accepted M71 vector alignment, and
the remaining exact M67 `value<backend>(uninit::array)` request as a typed
deferred backend-value boundary. Backend translation, rendering, generated
output, and declaration/array semantics remain out of scope.

Post-M72 planning selected
`Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice`, and
internal review returned `Accept With Follow-Ups` after local planning-doc
updates. The selected plan consumes accepted M72 helper-set completions and
produces typed structural lowering state for the exact `array.tsl:105`
`var<typed>(array_type<...>, tmp, ...)` shell. It must remain structural IR
only: generic declaration/array semantics, allocation/lifetime, initializer
behavior, variable scope, store/return semantics, `tmp.data()`, `emit_return`,
backend uninit translation, backend translation/rendering, and generated
output remain out of scope. Human acceptance was recorded, and M73 execution
became the active workflow action.

The M73 execution-review loop returned `Accept` after one focused
documentation revision. Review and audit found no blocking implementation,
validation, boundary, extensibility, evidence, or documentation issues after
that revision. M73 consumes accepted M72 helper-set completions and produces
one typed exact first-slot declaration-shell structural IR value for the exact
`array.tsl:105` `var<typed>(array_type<...>, tmp, ...)` shell. It preserves
accepted M68 base type, accepted M70 vector length, accepted M71 vector
alignment, and the M72 deferred backend-uninit boundary. Backend uninit
translation, backend maps, rendering, generated output, generic declaration/
array semantics, allocation/lifetime, initializer behavior, variable scope,
store/return semantics, `tmp.data()`, `emit_return`, and direct-intrinsic/SVE
semantics remain out of scope.

Post-M73 planning selected
`Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice`,
and internal review returned `Accept With Follow-Ups` after local
planning-doc updates. The selected plan consumes accepted M64/M65 exact
array-body envelope state and accepted M73 declaration-shell IR, then produces
one typed source-ordered structural sequence for the exact `array.tsl:105-111`
body. Slot roles must remain structural/provenance labels only. Predicate,
store, return, `tmp.data()`, `emit_return`, `assume_aligned`,
direct-intrinsic/SVE semantics, backend translation, rendering, generated
output, generic body/declaration/array semantics, allocation/lifetime,
initializer behavior, and variable scope remain out of scope. Human acceptance
was recorded, and M74 execution became the active workflow action.

The M74 execution-review loop returned `Accept With Follow-Ups` after one
focused validation-coverage revision and final documentation wording cleanup.
Review and audit found no blocking implementation, validation, boundary,
extensibility, documentation, or evidence issues after those revisions. M74
consumes accepted typed M64/M65 exact array-body envelope state and accepted
M73 declaration-shell IR, then produces one typed source-ordered structural
sequence for the exact `array.tsl:105-111` body. Role labels remain
structural/provenance labels only; non-first slots remain opaque/unresolved
structural evidence. Backend translation, rendering, generated output,
generic body/declaration/array semantics, variable scope, allocation/lifetime,
initializer behavior, predicate/store/return semantics, `tmp.data()`,
`emit_return`, `assume_aligned`, direct-intrinsic/SVE semantics, broad TSIL
parsing, lowering-time file/catalog reads, `tsldata` reads during lowering,
host CPU queries, backend maps, and runtime `frozen/` use remain out of scope.

Post-M74 planning selected
`Milestone 75: Exact Predicate Path Structural Request IR Slice`. The selected
plan consumes accepted M74 structural sequence state and records the exact
predicate path across slot 1 predicate initialization, slot 2 accepted
selected/no-body predicate update evidence, and slot 3 post-branch
store-call predicate-token use. It must remain structural/request IR only:
SVE predicate semantics, byte-size-to-token inference, store semantics,
`svst1`, `tmp.data()`, `a`, backend maps, rendering, generated output,
variable scope, and broad body semantics remain out of scope.

Post-M74 planning is accepted. Human acceptance was recorded, and the M75
execution-review loop has completed.

The M75 execution-review loop returned `Accept With Follow-Ups` after one
focused validation-coverage revision. Review and audit found no blocking
implementation, boundary, extensibility, documentation, or evidence issues
after that revision. M75 consumes accepted M74 exact array-body structural
sequence state and accepted M63/M62 selected/no-body predicate update evidence,
then produces one typed exact predicate-path structural/request IR value for
slot 1 predicate initialization, slot 2 selected/no-body predicate update
evidence, and slot 3 post-branch store-call predicate-token use. The slice
keeps `svbool_t`, `pg`, `svptrue_b8`, selected `svptrue_b16/b32/b64`, and
slot-3 `pg` as structural tokens/request provenance only. SVE predicate
semantics, byte-size-to-token inference, variable scope, store semantics,
backend maps, rendering, generated output, broad predicate/body/store IR,
lowering-time file/catalog reads, `tsldata` reads during lowering, host CPU
queries, and runtime `frozen/` use remain out of scope.

Post-M75 planning selected
`Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice`.
The selected plan consumes accepted M75 predicate-path state and records the
exact `array.tsl:110` `intrin<svst1>(pg, tmp.data(), a);` call-site shape as
typed structural/request lowering state only. It must not define store
semantics, ARM/SVE intrinsic semantics, memory behavior, pointer semantics,
`tmp.data()` semantics, operand semantics, backend translation, renderer-ready
IR, generated output, variable scope, generic call/store/body IR, or broad TSIL
semantics.

Post-M75 planning is accepted. Human acceptance was recorded, and the M76
execution-review loop has completed.

The M76 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or evidence
issues after that revision. M76 consumes accepted M75 predicate-path state and
records the exact `array.tsl:110` `intrin<svst1>(pg, tmp.data(), a);`
call-site shape as typed structural/request lowering state only. The slice
keeps `intrin`, `svst1`, `pg`, `tmp.data()`, and `a` as structural
tokens/provenance only. Store semantics, ARM/SVE intrinsic semantics, memory
behavior, pointer semantics, operand semantics, variable scope, backend maps,
backend translation, rendering, generated output, generic call/store/body IR,
broad TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
lowering, host CPU queries, and runtime `frozen/` use remain out of scope.

Post-M76 planning selected
`Milestone 77: Composable Lowering Pipeline Module Boundary Slice`.
The selected plan is behavior-preserving lowering architecture work. It starts
moving the accepted Stage 8 lowering path behind typed, composable private
module/stage boundaries while preserving accepted M57-M76 behavior. It must
not add new lowering semantics, backend translation, rendering, generated
output, broad parsing, or hardwired extension semantics.

Post-M76 planning is accepted. Human acceptance was recorded, and the M77
execution-review loop has completed.

The M77 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or evidence
issues after that revision. M77 preserves accepted M57-M76 behavior while
moving exact selected-body/post-branch recognizer shapes and tokens into
`tslgen.lowering._exact_shapes` and adding `tslgen.lowering._pipeline` for the
accepted exact array-body pipeline tail. The pipeline snapshot records typed
stage facts and dependencies with no pending backfeeds. New lowering
semantics, backend translation, rendering, generated output, broad parsing,
extension hardwiring, file/catalog reads, `tsldata` reads, host CPU queries,
backend map reads, and runtime `frozen/` use remain out of scope.

Post-M77 planning selected
`Milestone 78: Lowering Boundary Package Decomposition Slice`.
The selected plan is behavior-preserving lowering package decomposition. It
must move the accepted exact array-body / array-initialization lowering package
out of `boundary.py` into private typed modules, preserve accepted M57-M77
behavior, keep public imports stable, and reduce `boundary.py` by at least
1,000 physical lines from the 12,371-line pre-M78 baseline. Human acceptance
was recorded.

The M78 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, documentation, or evidence
issues. M78 preserves accepted M57-M77 behavior while moving exact
array-initialization helper/slot shape rules into
`tslgen.lowering._array_body_shapes`, extracted exact array-body /
array-initialization diagnostics into
`tslgen.lowering._array_body_diagnostics`, and exact predicate-init structural
tokens into `tslgen.lowering._exact_shapes`. The public `tslgen.lowering` and
`tslgen.lowering.boundary` import surfaces remain stable. `boundary.py` now
measures 11,109 physical lines, which is 1,262 lines below the 12,371-line
pre-M78 baseline and satisfies the M78 reduction target. New lowering
semantics, backend translation, rendering, generated output, broad parsing,
extension hardwiring, file/catalog reads, `tsldata` reads, host CPU queries,
backend map reads, and runtime `frozen/` use remain out of scope.

Post-M78 planning selected
`Milestone 79: Exact Array-Body Typed Model Ownership Extraction Slice`.
The selected plan is behavior-preserving typed model ownership extraction. It
must move exact array-body / array-initialization model ownership into private
lowering modules, consolidate duplicated exact helper `Literal` aliases, and
tighten targeted `_array_body_diagnostics.py` helper typing where the new
typed model/protocol boundary supplies the needed inputs. It must preserve
accepted M57-M78 behavior, keep `boundary.py` as the public facade, prevent
private lowering modules from importing `boundary.py`, and materially reduce
the post-M78 11,109-line facade without treating line count as permission to
move unrelated shared lowering models. Human acceptance was recorded.

The M79 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, extensibility, documentation,
or evidence issues. M79 preserves accepted M57-M78 behavior while creating
`tslgen.lowering._array_body_models` as the private exact array-body /
array-initialization typed model owner, updating `_array_body_shapes.py` to
consume shared helper aliases/rules, and updating `_array_body_diagnostics.py`
to use protocol-typed helper inputs instead of targeted unconstrained `Any`
inputs. The public `tslgen.lowering` and `tslgen.lowering.boundary` import
surfaces remain stable. `boundary.py` now measures 8,915 physical lines, which
is 2,194 lines below the post-M78 11,109-line baseline and satisfies the M79
reduction target. New lowering semantics, helper evaluation, backend
translation, rendering, generated output, broad parsing, extension hardwiring,
file/catalog reads, `tsldata` reads, host CPU queries, backend map reads, and
runtime `frozen/` use remain out of scope.

Post-M79 planning selected
`Milestone 80: Exact Array-Body Validation Boundary Extraction Slice`.
The selected plan is behavior-preserving exact array-body validation boundary
extraction. It should move accepted exact validation, request-record
selection, metadata lookup validation, and small construction helper ownership
out of `boundary.py` only where the extraction can remain private, typed,
import-stable, and behavior-preserving. It must preserve accepted M57-M79
behavior, keep `boundary.py` as the public facade, prevent private lowering
modules from importing `boundary.py`, and materially reduce the post-M79
8,915-line facade without treating line count as permission to move unrelated
shared lowering models. Internal planning review returned `Needs Revision`
only for stale workflow handoff state; the handoff was corrected locally.
Human acceptance was required before M80 execution and is now recorded.

Post-M79 planning is accepted. It selected
`Milestone 80: Exact Array-Body Validation Boundary Extraction Slice`.
Human acceptance was recorded.

The M80 execution-review loop returned `Accept With Follow-Ups` after
documentation finalization. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or
evidence issues. M80 preserves accepted M57-M79 behavior while moving exact
array-body / array-initialization validation, request-record selection,
metadata lookup validation, and small construction helper ownership into
`tslgen.lowering._array_body_validation`. The public `tslgen.lowering` and
`tslgen.lowering.boundary` import surfaces remain stable. Private lowering
modules, including `_array_body_validation.py`, do not import `boundary.py`.
`boundary.py` now measures 7,208 physical lines, below the M80 threshold of
7,415 lines. New lowering semantics, helper evaluation, source-adapter
behavior, backend translation, rendering, generated output, broad parsing,
extension hardwiring, file/catalog reads, `tsldata` reads, host CPU queries,
backend map reads, and runtime `frozen/` use remain out of scope.

Post-M80 planning selected
`Milestone 81: Generation-Time Lowering Core Ownership Extraction Slice`.
The selected plan is behavior-preserving generation-time lowering core
ownership extraction. It should move accepted generation-time model, query,
control-flow, and diagnostic helper ownership out of `boundary.py` into
private typed modules while preserving accepted M42-M80 behavior. It must keep
`boundary.py` as the public facade, keep public imports stable, prevent private
lowering modules from importing `boundary.py`, leave source adapters and
facade-owned orchestration in `boundary.py` unless a tiny behavior-preserving
delegation is required, and materially reduce the post-M80 7,208-line facade
without using line count as permission for unrelated exact array-body moves or
new semantics. Human acceptance was recorded.

Post-M80 planning is accepted. It selected
`Milestone 81: Generation-Time Lowering Core Ownership Extraction Slice`.
Human acceptance was recorded.

The M81 execution-review loop returned `Accept With Follow-Ups` after one
focused maintainability revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or
evidence issues after that revision. M81 preserves accepted M42-M80 behavior
while moving generation-time model, query, control-flow, and diagnostic helper
ownership into `tslgen.lowering._generation_models`,
`tslgen.lowering._generation_queries`,
`tslgen.lowering._generation_control_flow`, and
`tslgen.lowering._generation_diagnostics`. The public `tslgen.lowering` and
`tslgen.lowering.boundary` import surfaces remain stable. Private lowering
modules do not import `boundary.py`. `boundary.py` now measures 5,438 physical
lines, below the M81 threshold of 5,808 lines. New lowering semantics, helper
evaluation, source-adapter behavior, backend translation, rendering,
generated output, broad parsing, extension hardwiring, file/catalog reads,
`tsldata` reads, host CPU queries, backend map reads, and runtime `frozen/`
use remain out of scope.

Post-M81 planning selected
`Milestone 82: Selected-Body Envelope Ownership Extraction Slice`.
The selected plan is behavior-preserving selected-body value-model ownership
extraction. It should move the minimal cohesive accepted M60-M63 selected-body
handoff/form/body-IR/envelope model cluster into a private typed module while
preserving accepted M42-M81 behavior and public import paths. It must keep
`boundary.py` as the public facade/coordinator, keep private lowering modules
from importing `boundary.py` or the package facade, avoid circular imports,
tighten exact array-body selected/no-selected envelope consumers where
possible, and add no new lowering semantics, selected-body semantics, helper
evaluation, backend translation, rendering, generated output, broad parsing,
or extension hardwiring. Human acceptance was recorded.

Post-M81 planning is accepted. It selected
`Milestone 82: Selected-Body Envelope Ownership Extraction Slice`.
Human acceptance was recorded.

The M82 execution-review loop returned `Accept`. Review and audit found no
blocking implementation, validation, boundary, extensibility, documentation,
or evidence issues. M82 preserves accepted M42-M81 behavior while moving the
selected-body handoff/form/body-IR/envelope value-model cluster into
`tslgen.lowering._selected_body_models`. `boundary.py` remains the public
facade/coordinator, public imports remain stable, private lowering modules do
not import `boundary.py` or the package facade, exact array-body consumers now
use concrete private selected-body envelope model checks, and `boundary.py`
now measures 4,965 physical lines, below the 5,438-line post-M81 baseline.
New lowering semantics, selected-body semantics, helper evaluation, source
adapter behavior, backend translation, rendering, generated output, broad
parsing, extension hardwiring, file/catalog reads, `tsldata` reads, host CPU
queries, backend map reads, and runtime `frozen/` use remain out of scope.

Post-M82 planning selected
`Milestone 83: GenerationLoweringStage Output Contract Extraction Slice`.
The selected plan is behavior-preserving stage-contract ownership extraction.
It should move the accepted `GenerationLoweringStage` stage-name/output
validation contract into a private typed lowering module while preserving
accepted M42-M82 behavior, public imports, stage names/order, output
identities, deterministic keys, pipeline snapshots, and invalid-stage/output
error behavior. It must keep `boundary.py` as facade/coordinator for
lower-candidate orchestration and source adapters, avoid circular imports,
avoid registries/dispatchers/fixpoint engines, and add no new stage behavior,
return/store/body semantics, backend translation, rendering, generated output,
broad parsing, or extension hardwiring. Internal planning review returned
`Accept` after a focused workflow-state wording correction.

Post-M82 planning is accepted. It selected
`Milestone 83: GenerationLoweringStage Output Contract Extraction Slice`.
Human acceptance was recorded.

The M83 execution-review loop returned `Accept With Follow-Ups`. Review and
audit found no blocking implementation, validation, boundary, extensibility,
documentation, or evidence issues after documentation finalization. M83
preserves accepted M42-M82 behavior while moving stage-name/output contract
ownership, the accepted mini-TSIL statement value-model dependency, and
`GenerationLoweringStage` into `tslgen.lowering._stage_contracts`.
`boundary.py` remains the public facade/coordinator, public imports remain
stable, private lowering modules do not import `boundary.py` or the package
facade, and `boundary.py` now measures 4,807 physical lines, below the
4,965-line M82 baseline. New stage behavior, new lowering semantics, exact
return-emission IR, return/store/body semantics, helper evaluation, source
adapter behavior, backend translation, rendering, generated output, broad
parsing, extension hardwiring, file/catalog reads, `tsldata` reads, host CPU
queries, backend map reads, and runtime `frozen/` use remain out of scope.

Post-M83 planning is accepted. It selected
`Milestone 84: Exact Array-Body Pipeline And Source Adapter Ownership Extraction Slice`.
The selected plan is behavior-preserving exact array-body
pipeline/source-adapter ownership extraction. It should move one cohesive
accepted M64-M76 exact array-body staged-lowering pipeline/source-adapter
cluster out of
`boundary.py` into private typed lowering modules while preserving accepted
M42-M83 behavior, public imports, diagnostics, source locations, stage
names/order, output identities, deterministic keys, selected-branch-only
behavior, and pipeline snapshots. It is the next large step toward making
`boundary.py` a small facade; the roughly 1,000-line facade goal remains a
campaign target, not permission to create a second monolith or move unrelated
code for line count. Human acceptance was recorded.

The M84 execution-review loop returned `Accept With Follow-Ups` after one
focused revision. Review and audit found no blocking implementation,
validation, boundary, extensibility, documentation, or evidence issues after
that revision. M84 preserves accepted M42-M83 behavior while moving exact
array-body pipeline/source-adapter ownership into
`tslgen.lowering._array_body_pipeline`,
`tslgen.lowering._array_body_sources`, and
`tslgen.lowering._array_body_lowering`; selected-body public lowerers and the
request/result/lower-candidate facade remain in `boundary.py`. Public imports,
diagnostics, source locations, stage names/order, output identities,
deterministic keys, selected-branch-only behavior, and pipeline snapshots
remain stable. `boundary.py` now measures 1,898 physical lines, below the
accepted M83 4,807-line baseline. M84 added no new lowering semantics, exact
return-emission IR, backend translation, rendering, generated output,
extension-specific shortcuts, file/catalog reads, `tsldata` reads, host CPU
queries, backend map reads, or runtime `frozen/` use.

Post-M84 planning selected
`Milestone 85: Selected-Body Lowering Ownership Extraction Slice`, and
internal planning review returned `Accept With Follow-Ups` after local
planning-doc updates. The selected plan is behavior-preserving lowering
architecture work. It moves the accepted M60-M63 selected-body lowering
function/source-helper ownership out of `boundary.py` into a private typed
module such as `tslgen.lowering._selected_body_lowering`, while preserving
public facade imports, diagnostics, source locations, stage names/order,
output identities, deterministic keys, selected-branch-only behavior, and
pipeline snapshots. Human acceptance was recorded, and M85 execution became
the active workflow action.

The M85 execution-review loop returned `Accept` after one focused revision.
Review and audit found no blocking implementation, validation, boundary,
extensibility, documentation, or evidence issues after that revision. M85
preserves accepted M42-M84 behavior while moving accepted M60-M63
selected-body lowerer/source-helper ownership into
`tslgen.lowering._selected_body_lowering`; `boundary.py` remains the public
facade/coordinator for request/result models, `_lower_input`,
`lower_candidates`, payload classification, mini-TSIL lowering, generation
control-flow pruning, and exact array-body pipeline orchestration. Public
imports, diagnostics, source locations, stage names/order, output identities,
deterministic keys, selected-branch-only behavior, and pipeline snapshots
remain stable. `boundary.py` now measures 1,417 physical lines, below the
accepted M84 1,898-line baseline. M85 added no new selected-body semantics,
broad TSIL/body/call/store/return semantics, exact return-emission IR,
backend translation, rendering, generated output, extension-specific
shortcuts, file/catalog reads, `tsldata` reads, host CPU queries, backend map
reads, or runtime `frozen/` use.

Post-M85 planning selected
`Milestone 86: Candidate Payload Intake And Mini-TSIL Leaf Lowering Extraction Slice`,
and internal planning/audit review returned `Accept With Follow-Ups` after
local planning-doc updates. The selected plan is behavior-preserving lowering
architecture work. It moves accepted candidate payload-intake helpers and the
accepted mini-TSIL leaf return lowerer out of `boundary.py` into focused
private typed modules while preserving payload classification, typed-opaque
behavior, direct parameter-add return lowering, `intrin_compose<add>` return
lowering, public facade imports, diagnostics, source locations, stage
names/order, output identities, deterministic keys, selected-branch-only
behavior, and pipeline snapshots. Human acceptance was recorded, and M86
execution became the active workflow action.

The M86 execution-review loop returned `Accept` with no focused revision.
Review and audit found no blocking implementation, validation, boundary,
extensibility, documentation, or evidence issues after finalization. M86 is
accepted as behavior-preserving candidate payload-intake and mini-TSIL leaf
return lowering ownership extraction. It moved accepted payload classification
and unsupported-payload diagnostics into `tslgen.lowering._lowering_inputs`,
and accepted direct parameter-add / `intrin_compose<add>` mini-TSIL leaf
return lowering into `tslgen.lowering._mini_tsil_lowering`. `boundary.py`
remains the public facade/coordinator for request/result models,
`LoweringInputSet`, `prepare_lowering_inputs`, `_lower_input`,
`lower_candidates`, generation query/control-flow staging, selected-body
lowering, and exact array-body pipeline orchestration. Public imports,
diagnostics, source locations, stage names/order, output identities,
deterministic keys, selected-branch-only behavior, and pipeline snapshots
remain stable. `boundary.py` now measures 1,145 physical lines, below the
accepted M85 1,417-line baseline. `_lowering_inputs.py` measures 128 lines
and `_mini_tsil_lowering.py` measures 188 lines. M86 added no new TSIL syntax,
broad return/body/call/store semantics, exact return-emission IR, backend
translation, rendering, generated output, extension-specific shortcuts,
file/catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
runtime `frozen/` use.

Post-M86 planning is accepted. It selected
`Milestone 87: Exact Return-Emission Structural Request IR Slice`. Human
acceptance was recorded, and M87 execution became the active workflow action.

The M87 execution-review loop returned `Accept With Follow-Ups` after one
focused maintainability revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or
evidence issues after that revision. M87 is accepted as exact return-emission
structural/request IR. It records only the exact trailing `emit_return(tmp);`
shape with insignificant whitespace, links the returned token to the accepted
M73 declaration-shell variable token through accepted M74/M76 provenance, and
adds the deterministic `return_emission_structural_request_lowering` stage
after the accepted M76 post-branch call-site stage. M87 added focused
`tslgen.lowering._return_emission` ownership and did not add source-body
repair, broad `emit_return(...)`, return/store/variable semantics, backend
translation, rendering, generated output, broad TSIL parsing, or runtime
`frozen/` use. The focused revision removed M87 output from the shared runtime
lowered-implementation source protocol to avoid broad protocol/backfeed creep.

Post-M87 planning selected
`Milestone 88: Exact Array Body Structural Package Assembly Slice`, and
internal review returned `Accept With Follow-Ups` after a focused workflow
state wording correction.

Post-M87 planning is accepted. It selected
`Milestone 88: Exact Array Body Structural Package Assembly Slice`. Human
acceptance was recorded, and M88 execution became the active workflow action.

The M88 execution-review loop returned `Accept With Follow-Ups` after one
focused extensibility revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, or documentation issues
after that revision. M88 is accepted as exact array-body structural package
assembly. It adds focused `tslgen.lowering._array_body_package` ownership,
assembles accepted M64-M87 exact array-body facts into one source-ordered typed
structural package, appends the deterministic
`array_body_structural_package_assembly` stage after the M87 return-emission
stage, and preserves member object identity/provenance. The focused revision
ensures protocol-shaped return-emission sources treat their entries as
untrusted runtime data and diagnose malformed entries instead of raising
attribute errors. M88 remains typed aggregation/provenance validation only; it
does not add source-body repair, semantic body lowering, declaration/store/
return/SVE/backend semantics, renderer-ready IR, rendering, generated output,
broad TSIL parsing, broad dispatch, hidden backfeeds, or runtime `frozen/` use.

Post-M88 planning is accepted. It selected
`Milestone 89: Exact Array Backend-Deferred Request Inventory Slice`, and
internal planning/audit returned `Recommend With Follow-Ups` for the selected
slice. The selected plan consumes the accepted M88 exact array-body structural
package and inventories the accepted M72/M67
`value<backend>(uninit::array)` deferred backend-value boundary as the only
supported typed inventory member. It must remain Stage 8 lowering inventory
and provenance validation only: no backend-uninit resolution, backend maps,
backend translation, Stage 9 backend planning, renderer-ready IR, rendering,
generated output, generic backend-value evaluation, source-body repair, or
broad body semantics. Human acceptance was recorded, and M89 execution became
the active workflow action.

The M89 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, documentation, or evidence
issues and no focused revision. M89 is accepted as exact array
backend-deferred request inventory. It adds focused
`tslgen.lowering._array_body_backend_deferred_requests` ownership, inventories
the accepted M72/M67 `value<backend>(uninit::array)` deferred backend-value
boundary from the accepted M88 structural package, appends the deterministic
`array_backend_deferred_request_inventory` stage after M88, and preserves M88
package, M72 deferred backend-uninit value, and M67 request-record object
identity/provenance. M89 remains Stage 8 inventory/provenance validation only;
it does not add backend-uninit resolution, backend maps/catalog reads, Stage 9
backend planning, renderer-ready IR, rendering, generated output, generic
backend-value evaluation, source-body repair, broad protocols, hidden
backfeeds, or broad body semantics.

Post-M89 planning is accepted. It selected
`Milestone 90: Exact Array Lowering Completion Package Slice`, and internal
planning/review returned `Accept With Follow-Ups` after tightening the
"completion" wording to mean Stage 8 exact lowering handoff completion only.
The selected plan consumes accepted M88 structural packages and accepted M89
backend-deferred inventories to produce one typed completion package with
explicit unresolved dependency records. It must not complete declaration,
array, store, return, SVE, backend, renderer, generated-output, broad TSIL, or
source-repair semantics. Human acceptance is recorded, and M90 execution is
the active workflow action.

The M90 execution-review loop returned `Accept With Follow-Ups` after one
focused diagnostic-boundary revision. Review and audit found no blocking
implementation, validation, boundary, extensibility, documentation, or evidence
issues after that revision. M90 is accepted as exact array lowering completion
package handoff. It adds focused
`tslgen.lowering._array_body_completion_package` ownership, packages accepted
M88 structural facts and accepted M89 backend-deferred inventory facts into
one typed Stage 8 completion package, records the accepted
`value_backend_uninit_array` member as a typed unresolved dependency, appends
the deterministic `array_lowering_completion_package` stage after M89, and
preserves M88/M89/M73/M72/M67 object identity/provenance. M90 remains Stage 8
lowering-side handoff packaging only; it does not add backend-uninit
resolution, backend maps/catalog reads, Stage 9 backend planning,
renderer-ready IR, rendering, generated output, generic backend-value
evaluation, source-body repair, broad protocols, hidden backfeeds, or semantic
body completion.

Post-M90 planning is accepted. It selected
`Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice`.
The selected plan is a behavior-preserving Stage 8 maintainability
consolidation that broadens the originally proposed aggregate extraction into
focused ownership for exact array pipeline results, stage/snapshot assembly,
and public handoff aggregation. It must preserve accepted M64-M90 behavior and
add no new lowering semantics, backend planning, backend maps, rendering,
generated output, broad TSIL parsing, source-body repair, broad protocols, or
fixpoint machinery. Planning review returned `Accept With Follow-Ups`, with
behavior-preserving scope, line-count, and import-boundary guardrails recorded
as non-blocking follow-ups. Human acceptance was recorded.

The M91 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation, validation, boundary, documentation, evidence, or
review issues. M91 is accepted as behavior-preserving Stage 8 exact array
pipeline ownership consolidation. It moves exact array pipeline result DTO/key
ownership into `tslgen.lowering._array_body_pipeline_results`, moves exact
stage construction plus result/snapshot assembly into
`tslgen.lowering._array_body_stage_assembly`, and keeps
`tslgen.lowering._array_body_pipeline` as orchestration over accepted M64-M90
lowerers and focused assembly helpers. M91 preserves accepted diagnostics,
source locations, public imports, stage names/order, artifact kinds,
deterministic keys, output identities, selected-branch-only behavior,
no-external-input boundaries, and pipeline snapshots. It adds no new lowering
semantics, backend planning, backend maps, rendering, generated output, broad
TSIL parsing, source-body repair, broad protocols, hidden backfeeds, fixpoint
machinery, or hardwiring.

Post-M91 planning selected
`Milestone 92: Exact Array Lowering Backend-Handoff Request Slice`.
The selected plan is a lowering-side typed handoff boundary over the accepted
M90 completion package and M91 stable pipeline ownership. It should produce
one concrete typed request for later backend planning that carries accepted
completion-package identity, unresolved dependency identity/provenance, and
deterministic keys without reading backend maps, resolving backend values,
creating Stage 9 backend plans, producing renderer-ready IR, rendering output,
or inferring declaration/array/store/return/SVE/body semantics. Planning
review returned `Accept With Follow-Ups`, with backend-boundary and
wrapper-only-abstraction guardrails recorded as non-blocking follow-ups. Human
acceptance is recorded.

The M92 execution-review loop returned `Accept With Follow-Ups` after a
focused documentation update recorded the M92 diagnostics and final
roadmap/status wording. Review and audit found no blocking implementation,
validation, boundary, extensibility, documentation, or evidence issues after
that revision. M92 is accepted as exact Stage 8 array lowering backend-handoff
request work. It adds focused
`tslgen.lowering._array_body_backend_handoff` ownership, consumes accepted M90
completion packages through M91 stable pipeline ownership, produces one typed
`array_backend_handoff_request` for later backend planning, appends that stage
after `array_lowering_completion_package`, and preserves accepted
M90/M89/M88/M72/M67 identity and provenance. M92 remains lowering-side
request/provenance data only; it does not resolve backend-uninit, read backend
maps/catalogs, create Stage 9 plans, create renderer-ready IR, render output,
generate artifacts, infer declaration/array/store/return/SVE/body semantics,
repair source text, broaden protocols, introduce hidden backfeeds, or add
fixpoint machinery.

Post-M92 planning selected
`Milestone 93: Dual-Source Lowering Operation Package Boundary Slice`.
The selected plan proves the lowering package shape is not array-only while
remaining narrow: it packages exactly accepted M86 mini-TSIL leaf return
values and accepted M92 exact array backend-handoff requests as distinct Stage
8 typed/provenance entries. Planning review returned `Accept With Follow-Ups`
after the initial cross-primitive wording was tightened from a broad operation
framework into a dual-source package boundary seed. Human acceptance was
recorded before M93 execution began.

The M93 execution-review loop returned `Accept With Follow-Ups` after focused
revision. The revision tightened narrow container candidate-context validation
and rejected manually constructed mini-TSIL return statements outside the
accepted M86 leaf-return shapes. M93 is accepted as Stage 8 dual-source
operation package boundary work: it adds focused
`tslgen.lowering._operation_package` ownership, exposes
`LoweredImplementation.operation_packages`, and appends
`lowering_operation_package` facts for accepted M86 mini-TSIL leaf returns and
accepted M92 exact array backend-handoff requests without adding backend
planning, renderer-ready IR, broad body semantics, source repair, registries,
or dispatchers.

Post-M93 planning is accepted. It selected
`Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice`.
Internal planning/review returned `Accept With Follow-Ups`. The selected plan
is behavior-preserving Stage 8 lowering maintainability work: split M93
operation-package diagnostics, accepted-source narrowing, mini-TSIL package
contract, and exact-array provenance validation into focused private modules
before adding more package families. Human acceptance was recorded, and M94
execution became the active workflow action.

The M94 execution-review loop returned `Accept With Follow-Ups` after one
focused validation-coverage revision. M94 is accepted as behavior-preserving
operation-package ownership work. It keeps `_operation_package.py` as a
19-line facade/re-export surface while moving package models, diagnostics,
accepted M86 mini-TSIL shape checks, accepted M92 exact-array provenance
checks, and source/stage/container narrowing into focused private modules.
Accepted M93 package behavior, public imports, diagnostics, source locations,
keys, identities, stage name/order, snapshots, deterministic ordering, and
selected-branch-only behavior are preserved. M94 adds no new package families,
new lowering semantics, backend planning, renderer-ready IR, rendering,
generated output, source repair, registries, dispatchers, broad source
protocols, hidden backfeeds, or fixpoint machinery.

M94 changed `tslgen/src/tslgen/lowering/_operation_package.py`, added
`_operation_package_diagnostics.py`, `_operation_package_exact_array.py`,
`_operation_package_mini_tsil.py`, `_operation_package_models.py`, and
`_operation_package_sources.py`, and updated
`tslgen/tests/unit/test_lowering_boundary.py`. Final line counts were
`boundary.py` 1,280, `_operation_package.py` 19,
`_operation_package_diagnostics.py` 136,
`_operation_package_exact_array.py` 174,
`_operation_package_mini_tsil.py` 36,
`_operation_package_models.py` 153, and
`_operation_package_sources.py` 604. Final validation passed: focused M94
pytest `38 passed, 293 deselected`, full lowering-boundary pytest
`331 passed`, lowering mypy `Success: no issues found in 34 source files`,
full tooling validation with corpus probes `3 passed`, unittest discovery
`665` tests OK, compileall OK, ruff OK, mypy OK across `138` source files,
and diff-check OK.

Post-M94 planning selected
`Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice`, and
internal planner, boundary, extensibility, and documentation review returned
`Accept With Follow-Ups`. Human acceptance was recorded, and M95 execution
became the active workflow action. The selected plan adds one focused Stage 8
operation-package family over accepted M63 selected-body envelopes and the
enclosed accepted M62 selected assignment/direct-intrinsic body IR. It records
`pg`, `svptrue_b*`, selected literals, type tags, branch ids, and source
locations as provenance only; it must not infer SVE/direct-intrinsic
semantics, byte-size-to-token mappings, backend support, renderer-ready IR,
source repairs, registries, dispatchers, hidden backfeeds, or fixpoint
behavior.

The M95 execution-review loop returned `Accept With Follow-Ups` after focused
revision. M95 is accepted as a Stage 8 selected-body direct-intrinsic
operation-package family over accepted M63 selected-body envelopes and the
enclosed accepted M62 selected assignment/direct-intrinsic body IR. The
revision moved selected-body package entry ownership into
`_operation_package_selected_body.py`, preserved no-selected envelope source
locations for explicit-family container diagnostics, and added wrong-stage and
boundary guardrail coverage. M95 preserves `pg`, `svptrue_b*`, selected
literals, type tags, branch ids, and source locations as provenance only; it
adds no SVE/direct-intrinsic semantics, byte-size-to-token inference, backend
planning, renderer-ready IR, rendering, generated output, source repair,
registries, dispatchers, hidden backfeeds, or fixpoint machinery.

M95 changed `tslgen/src/tslgen/lowering/__init__.py`,
`tslgen/src/tslgen/lowering/_operation_package.py`,
`tslgen/src/tslgen/lowering/_operation_package_models.py`,
`tslgen/src/tslgen/lowering/_operation_package_selected_body.py`,
`tslgen/src/tslgen/lowering/_operation_package_sources.py`,
`tslgen/src/tslgen/lowering/boundary.py`, and
`tslgen/tests/unit/test_lowering_boundary.py`. Final line counts were
`boundary.py` 1,300, `_operation_package.py` 23,
`_operation_package_diagnostics.py` 136,
`_operation_package_exact_array.py` 174,
`_operation_package_mini_tsil.py` 36,
`_operation_package_models.py` 171,
`_operation_package_selected_body.py` 186, and
`_operation_package_sources.py` 819. Final validation passed: focused M95
pytest `26 passed, 308 deselected`, full lowering-boundary pytest
`334 passed`, lowering mypy `Success: no issues found in 35 source files`,
full tooling validation with corpus probes `3 passed`, unittest discovery
`668` tests OK, compileall OK, ruff OK, mypy OK across `139` source files,
and diff-check OK.

Post-M95 planning selected
`Milestone 96: Stage-8 Lowering Completion Manifest Slice`, and internal
planner, boundary, extensibility, and documentation review returned
`Accept With Follow-Ups` after local planning-doc revisions. Human acceptance
was recorded, and M96 execution became the active workflow action. The selected
plan creates a deterministic Stage 8 lowering-only completion/readiness
manifest over accepted
`LoweringOperationPackageIr` facts and explicit unresolved dependency
references. "Completion" and "readiness" mean only accepted Stage 8
package/provenance assembly status; they do not mean semantic body completion,
backend readiness, renderer readiness, executable readiness, or
generated-output readiness.

The M96 execution-review loop returned `Accept With Follow-Ups` after one
focused revision. M96 is accepted as a Stage 8 lowering completion manifest
slice. It added `_lowering_completion_manifest.py` with
`Stage8LoweringCompletionManifestIr`, package/dependency manifest records, and
diagnostics; integrated the `lowering_completion_manifest` stage after
accepted `lowering_operation_package` facts; and preserved accepted package
and unresolved dependency references by object identity. M96 added no backend
translation, backend map/catalog reads, backend-uninit resolution, Stage 9
planning, renderer-ready IR, rendering, generated output, source repair,
broad TSIL/body parsing, registries, dispatchers, hidden backfeeds, fixpoint
machinery, scheduling, dependency solving, Rust, CLI/report/writer behavior,
or compiler execution.

M96 changed `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`,
`tslgen/src/tslgen/lowering/_stage_contracts.py`,
`tslgen/src/tslgen/lowering/boundary.py`, and
`tslgen/tests/unit/test_lowering_boundary.py`. Final line counts were
`boundary.py` 1,300, `_operation_package_sources.py` 819, and
`_lowering_completion_manifest.py` 776. Final validation passed: required
line count check `1300 / 819 / 776`, required py-compile with no output,
focused M96/manifest/operation-package pytest `17 passed, 326 deselected`,
full lowering-boundary pytest `343 passed`, lowering mypy
`Success: no issues found in 36 source files`, full tooling validation with
corpus probes `3 passed`, unittest discovery `677` tests OK, compileall OK,
ruff OK, mypy OK across `140` source files, and diff-check OK.

Post-M96 planning is accepted. It selected
`Milestone 97: Lowering Completion Gap Inventory Slice`, and internal planner,
boundary, extensibility, and documentation review returned
`Accept With Follow-Ups` after documentation-only planning updates. The
selected plan creates a typed Stage 8 lowering-owned gap inventory over
accepted M96 completion manifests. M97 records only lowering-observed gaps
visible from accepted manifest facts: initially accepted unresolved
backend-handoff dependency records, plus a deterministic no-known-gap state for
manifests without unresolved dependencies. It must not infer semantic body
completion, backend readiness, renderer readiness, operation scheduling,
dependency closure, or output readiness.

Human acceptance for post-M96 planning was recorded, and M97 execution became
the active workflow action.

The M97 execution-review loop returned `Accept With Follow-Ups` after focused
test-only revisions. M97 is accepted as a Stage 8 lowering completion gap
inventory slice. It added `_lowering_completion_gap_inventory.py` with typed
gap inventory and gap-record IR, diagnostics, validation, and assembly over
accepted M96 `Stage8LoweringCompletionManifestIr` facts; integrated the
`lowering_completion_gap_inventory` stage after
`lowering_completion_manifest`; and preserved source manifest, package record,
package object, unresolved dependency record, and source dependency request
object identity. M97 added no backend translation, backend map/catalog reads,
backend-uninit resolution, Stage 9 planning, dependency solving, operation
scheduling, renderer-ready IR, rendering, generated output, source repair, raw
body parsing, registries, dispatchers, hidden backfeeds, fixpoint behavior,
Rust, CLI/report/writer behavior, or compiler execution.

M97 changed `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`,
`tslgen/src/tslgen/lowering/_stage_contracts.py`,
`tslgen/src/tslgen/lowering/boundary.py`, and
`tslgen/tests/unit/test_lowering_boundary.py`. Final line counts were
`boundary.py` 1,285, `_operation_package_sources.py` 819,
`_lowering_completion_manifest.py` 776, and
`_lowering_completion_gap_inventory.py` 564. Final validation passed: required
line count check `1285 / 819 / 776 / 564`, required py-compile with no output,
focused M97/manifest/gap-inventory pytest `14 passed, 334 deselected`, full
lowering-boundary pytest `348 passed`, lowering mypy
`Success: no issues found in 37 source files`, full tooling validation with
corpus probes `3 passed`, unittest discovery `682` tests OK, compileall OK,
ruff OK, mypy OK across `141` source files, and diff-check OK.

Post-M97 planning selected
`Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice`,
and internal planner, boundary, extensibility, and documentation review
returned `Accept With Follow-Ups` after narrowing the proposal from broad
coordinator extraction to focused stage-assembly/result-assembly ownership.
The selected plan is behavior-preserving Stage 8 lowering architecture work:
move accepted stage construction and per-candidate operation-package ->
completion-manifest -> completion-gap-inventory result assembly out of
`boundary.py` into focused private ownership while preserving accepted
M57-M97 semantics, diagnostics, stage names, stage order, keys, object
identities, and public facade behavior.

Human acceptance for post-M97 planning was recorded, and M98 execution became
the active workflow action.

The M98 execution-review loop returned `Accept With Follow-Ups` after one
focused public-facade import correction and documentation finalization. M98 is
accepted as behavior-preserving Stage 8 stage-assembly ownership extraction.
It added `_lowering_stage_assembly.py` with focused ownership for accepted
`GenerationLoweringStage` construction helpers and per-candidate
operation-package -> completion-manifest -> completion-gap-inventory result
assembly. `boundary.py` remains the public facade and request/result model
owner; `_operation_package_sources.py` is unchanged. M98 added no new lowering
semantics, source-body parsing, source repair, backend translation, backend
map/catalog reads, backend-uninit resolution, Stage 9 planning, operation
scheduling, dependency closure, renderer-ready IR, rendering, generated
output, Rust, CLI/report/writer behavior, compiler execution, registries,
dispatchers, callback maps, hidden backfeeds, fixpoint machinery, or
hardwiring.

M98 changed `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`,
`tslgen/src/tslgen/lowering/boundary.py`, and
`tslgen/tests/unit/test_lowering_boundary.py`. Final line counts were
`boundary.py` 1,241, `_lowering_stage_assembly.py` 189,
`_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
and `_lowering_completion_gap_inventory.py` 564. Final validation passed:
required py-compile with no output, focused M98/stage-assembly/package/
manifest/gap-inventory pytest `27 passed, 325 deselected`, full
lowering-boundary pytest `352 passed`, lowering mypy
`Success: no issues found in 38 source files`, full tooling validation with
corpus probes `3 passed`, unittest discovery `686` tests OK, compileall OK,
ruff OK, mypy OK across `142` source files, and diff-check OK.

Post-M98 planning selected
`Milestone 99: Operation Package Backend-Translation Request Inventory Slice`,
and internal planning review returned `Accept With Follow-Ups`. The selected
plan is Stage 8 lowering inventory/provenance work only: it inventories
accepted backend-scoped request facts visible from accepted operation packages,
completion manifests, and gap inventories without translating backend values,
evaluating maps, creating Stage 9 plans, rendering output, scheduling
operations, solving dependencies, scanning raw source bodies, or inferring
direct-intrinsic/SVE semantics. Planning also added
`docs/redesign/missing-lowering-inventory.md` as the living inventory of known
missing lowering work.

The M99 execution-review loop returned `Accept` after focused extensibility and
validation revisions. M99 added typed Stage 8 backend-translation request
inventory/provenance ownership split across focused private modules, integrated
the new `lowering_backend_translation_request_inventory` stage after
`lowering_completion_gap_inventory`, preserved accepted package/manifest/gap
object identity, and kept backend translation, Stage 9 planning, rendering,
source repair, and raw body parsing out of scope.

Post-M99 planning selected
`Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice`,
and internal planning review returned `Accept With Follow-Ups`. The selected
plan resolves only the accepted M99 exact-array
`exact_array_backend_value_uninit_array` request into typed C++ backend
translation-result state. It does not render C++ or Rust code, start Stage 9
backend planning, evaluate generic backend helpers, parse raw source text,
repair source bodies, or handle Rust/direct-intrinsic/SVE semantics.

## Current Work State

Current required action:

```text
Execute Milestone 111.
```

Active run prompt:

```text
docs/agent/runs/m111-execution-review-loop-prompt.md
```

Active executor milestone:

```text
Milestone 111: Tiny Clean Binary Operation Lowering Table Slice
```

Latest review verdict:

```text
M110 execution-review loop returned Accept With Follow-Ups after layout,
architecture, documentation, and validation audits.
```

Next expected action:

```text
Run the active M111 execution-review-loop prompt. M111 should broaden the tiny
clean lowering path from a one-off `add` operation check to a small typed
binary-operation descriptor table, keep backend operator spellings
backend-owned, and avoid CLI work or broad expression parsing.
```

Accepted planning prompt:

```text
docs/agent/runs/post-m47-orchestrated-planning-plus-review-prompt.md
```

Accepted post-M48 planning prompt:

```text
docs/agent/runs/post-m48-planning-plus-review-prompt.md
```

Accepted M49 execution prompt:

```text
docs/agent/runs/m49-execution-review-loop-prompt.md
```

Accepted post-M49 planning prompt:

```text
docs/agent/runs/post-m49-planning-plus-review-prompt.md
```

Accepted post-M49 acceptance finalization prompt:

```text
docs/agent/runs/post-m49-acceptance-finalization-prompt.md
```

Accepted M50 execution prompt:

```text
docs/agent/runs/m50-execution-review-loop-prompt.md
```

Accepted post-M50 planning prompt:

```text
docs/agent/runs/post-m50-planning-plus-review-prompt.md
```

Accepted post-M50 acceptance finalization prompt:

```text
docs/agent/runs/post-m50-acceptance-finalization-prompt.md
```

Accepted M51 execution prompt:

```text
docs/agent/runs/m51-execution-review-loop-prompt.md
```

Accepted post-M51 planning prompt:

```text
docs/agent/runs/post-m51-planning-plus-review-prompt.md
```

Accepted post-M51 acceptance finalization prompt:

```text
docs/agent/runs/post-m51-acceptance-finalization-prompt.md
```

Accepted M52 execution prompt:

```text
docs/agent/runs/m52-execution-review-loop-prompt.md
```

Accepted post-M52 planning prompt:

```text
docs/agent/runs/post-m52-planning-plus-review-prompt.md
```

Accepted post-M52 acceptance finalization prompt:

```text
docs/agent/runs/post-m52-acceptance-finalization-prompt.md
```

Accepted M53 execution prompt:

```text
docs/agent/runs/m53-execution-review-loop-prompt.md
```

Accepted post-M53 planning prompt:

```text
docs/agent/runs/post-m53-planning-plus-review-prompt.md
```

Accepted post-M53 acceptance finalization prompt:

```text
docs/agent/runs/post-m53-acceptance-finalization-prompt.md
```

Accepted M54 execution prompt:

```text
docs/agent/runs/m54-execution-review-loop-prompt.md
```

Accepted post-M54 planning prompt:

```text
docs/agent/runs/post-m54-planning-plus-review-prompt.md
```

Accepted post-M54 acceptance finalization prompt:

```text
docs/agent/runs/post-m54-acceptance-finalization-prompt.md
```

Accepted M55 execution prompt:

```text
docs/agent/runs/m55-execution-review-loop-prompt.md
```

Accepted post-M55 planning prompt:

```text
docs/agent/runs/post-m55-planning-plus-review-prompt.md
```

Accepted post-M55 acceptance finalization prompt:

```text
docs/agent/runs/post-m55-acceptance-finalization-prompt.md
```

Accepted M56 execution-review loop prompt:

```text
docs/agent/runs/m56-execution-review-loop-prompt.md
```

Accepted post-M56 planning prompt:

```text
docs/agent/runs/post-m56-planning-plus-review-prompt.md
```

Accepted post-M56 acceptance finalization prompt:

```text
docs/agent/runs/post-m56-acceptance-finalization-prompt.md
```

Accepted M57 execution-review loop prompt:

```text
docs/agent/runs/m57-execution-review-loop-prompt.md
```

Accepted post-M57 planning prompt:

```text
docs/agent/runs/post-m57-planning-plus-review-prompt.md
```

Accepted post-M57 acceptance finalization prompt:

```text
docs/agent/runs/post-m57-acceptance-finalization-prompt.md
```

Accepted M58 execution-review loop prompt:

```text
docs/agent/runs/m58-execution-review-loop-prompt.md
```

Accepted post-M58 planning prompt:

```text
docs/agent/runs/post-m58-planning-plus-review-prompt.md
```

Accepted post-M58 acceptance finalization prompt:

```text
docs/agent/runs/post-m58-acceptance-finalization-prompt.md
```

Accepted M59 execution-review loop prompt:

```text
docs/agent/runs/m59-execution-review-loop-prompt.md
```

Accepted post-M59 planning prompt:

```text
docs/agent/runs/post-m59-planning-plus-review-prompt.md
```

Accepted post-M59 acceptance finalization prompt:

```text
docs/agent/runs/post-m59-acceptance-finalization-prompt.md
```

Accepted M60 execution-review loop prompt:

```text
docs/agent/runs/m60-execution-review-loop-prompt.md
```

Accepted post-M60 planning prompt:

```text
docs/agent/runs/post-m60-planning-plus-review-prompt.md
```

Accepted post-M60 acceptance finalization prompt:

```text
docs/agent/runs/post-m60-acceptance-finalization-prompt.md
```

Accepted M61 execution-review loop prompt:

```text
docs/agent/runs/m61-execution-review-loop-prompt.md
```

Completed post-M61 planning prompt:

```text
docs/agent/runs/post-m61-planning-plus-review-prompt.md
```

Accepted post-M61 acceptance finalization prompt:

```text
docs/agent/runs/post-m61-acceptance-finalization-prompt.md
```

Accepted M62 execution-review loop prompt:

```text
docs/agent/runs/m62-execution-review-loop-prompt.md
```

Completed post-M62 planning prompt:

```text
docs/agent/runs/post-m62-planning-plus-review-prompt.md
```

Accepted post-M62 acceptance finalization prompt:

```text
docs/agent/runs/post-m62-acceptance-finalization-prompt.md
```

Accepted M63 execution-review loop prompt:

```text
docs/agent/runs/m63-execution-review-loop-prompt.md
```

Completed post-M63 planning prompt:

```text
docs/agent/runs/post-m63-planning-plus-review-prompt.md
```

Accepted post-M63 acceptance finalization prompt:

```text
docs/agent/runs/post-m63-acceptance-finalization-prompt.md
```

Accepted M64 execution-review loop prompt:

```text
docs/agent/runs/m64-execution-review-loop-prompt.md
```

Completed post-M64 planning prompt:

```text
docs/agent/runs/post-m64-planning-plus-review-prompt.md
```

Accepted post-M64 acceptance finalization prompt:

```text
docs/agent/runs/post-m64-acceptance-finalization-prompt.md
```

Accepted M65 execution-review loop prompt:

```text
docs/agent/runs/m65-execution-review-loop-prompt.md
```

Completed post-M65 planning prompt:

```text
docs/agent/runs/post-m65-planning-plus-review-prompt.md
```

Accepted post-M65 acceptance finalization prompt:

```text
docs/agent/runs/post-m65-acceptance-finalization-prompt.md
```

Accepted M66 execution-review loop prompt:

```text
docs/agent/runs/m66-execution-review-loop-prompt.md
```

Completed post-M66 planning prompt:

```text
docs/agent/runs/post-m66-planning-plus-review-prompt.md
```

Accepted post-M66 acceptance finalization prompt:

```text
docs/agent/runs/post-m66-acceptance-finalization-prompt.md
```

Accepted M67 execution-review loop prompt:

```text
docs/agent/runs/m67-execution-review-loop-prompt.md
```

Completed post-M67 planning prompt:

```text
docs/agent/runs/post-m67-planning-plus-review-prompt.md
```

Accepted post-M67 acceptance finalization prompt:

```text
docs/agent/runs/post-m67-acceptance-finalization-prompt.md
```

Accepted M68 execution-review loop prompt:

```text
docs/agent/runs/m68-execution-review-loop-prompt.md
```

Completed post-M68 planning prompt:

```text
docs/agent/runs/post-m68-planning-plus-review-prompt.md
```

Accepted post-M68 acceptance finalization prompt:

```text
docs/agent/runs/post-m68-acceptance-finalization-prompt.md
```

Accepted M69 execution-review loop prompt:

```text
docs/agent/runs/m69-execution-review-loop-prompt.md
```

Completed post-M69 planning-plus-review prompt:

```text
docs/agent/runs/post-m69-planning-plus-review-prompt.md
```

Accepted post-M69 acceptance finalization prompt:

```text
docs/agent/runs/post-m69-acceptance-finalization-prompt.md
```

Accepted M70 execution-review loop prompt:

```text
docs/agent/runs/m70-execution-review-loop-prompt.md
```

Completed post-M70 planning-plus-review prompt:

```text
docs/agent/runs/post-m70-planning-plus-review-prompt.md
```

Accepted post-M70 acceptance finalization prompt:

```text
docs/agent/runs/post-m70-acceptance-finalization-prompt.md
```

Accepted M71 execution-review loop prompt:

```text
docs/agent/runs/m71-execution-review-loop-prompt.md
```

Completed post-M71 planning-plus-review prompt:

```text
docs/agent/runs/post-m71-planning-plus-review-prompt.md
```

Accepted post-M71 acceptance finalization prompt:

```text
docs/agent/runs/post-m71-acceptance-finalization-prompt.md
```

Accepted M72 execution-review loop prompt:

```text
docs/agent/runs/m72-execution-review-loop-prompt.md
```

Completed post-M72 planning-plus-review prompt:

```text
docs/agent/runs/post-m72-planning-plus-review-prompt.md
```

Accepted post-M72 acceptance finalization prompt:

```text
docs/agent/runs/post-m72-acceptance-finalization-prompt.md
```

Accepted M73 execution-review loop prompt:

```text
docs/agent/runs/m73-execution-review-loop-prompt.md
```

Completed post-M73 planning-plus-review prompt:

```text
docs/agent/runs/post-m73-planning-plus-review-prompt.md
```

Accepted post-M73 acceptance finalization prompt:

```text
docs/agent/runs/post-m73-acceptance-finalization-prompt.md
```

Accepted M74 execution-review loop prompt:

```text
docs/agent/runs/m74-execution-review-loop-prompt.md
```

Completed post-M74 planning-plus-review prompt:

```text
docs/agent/runs/post-m74-planning-plus-review-prompt.md
```

Accepted post-M74 acceptance finalization prompt:

```text
docs/agent/runs/post-m74-acceptance-finalization-prompt.md
```

Accepted M75 execution-review loop prompt:

```text
docs/agent/runs/m75-execution-review-loop-prompt.md
```

Completed post-M75 planning-plus-review prompt:

```text
docs/agent/runs/post-m75-planning-plus-review-prompt.md
```

Accepted post-M75 acceptance finalization prompt:

```text
docs/agent/runs/post-m75-acceptance-finalization-prompt.md
```

Accepted M76 execution-review loop prompt:

```text
docs/agent/runs/m76-execution-review-loop-prompt.md
```

Completed post-M76 planning-plus-review prompt:

```text
docs/agent/runs/post-m76-planning-plus-review-prompt.md
```

Accepted post-M76 acceptance-finalization prompt:

```text
docs/agent/runs/post-m76-acceptance-finalization-prompt.md
```

Accepted M77 execution-review loop prompt:

```text
docs/agent/runs/m77-execution-review-loop-prompt.md
```

Completed post-M77 planning-plus-review prompt:

```text
docs/agent/runs/post-m77-planning-plus-review-prompt.md
```

Accepted post-M77 acceptance-finalization prompt:

```text
docs/agent/runs/post-m77-acceptance-finalization-prompt.md
```

Accepted M78 execution-review loop prompt:

```text
docs/agent/runs/m78-execution-review-loop-prompt.md
```

Completed post-M78 planning-plus-review prompt:

```text
docs/agent/runs/post-m78-planning-plus-review-prompt.md
```

Accepted post-M78 acceptance-finalization prompt:

```text
docs/agent/runs/post-m78-acceptance-finalization-prompt.md
```

Completed M79 execution-review loop prompt:

```text
docs/agent/runs/m79-execution-review-loop-prompt.md
```

Completed post-M79 planning-plus-review prompt:

```text
docs/agent/runs/post-m79-planning-plus-review-prompt.md
```

Accepted post-M79 acceptance-finalization prompt:

```text
docs/agent/runs/post-m79-acceptance-finalization-prompt.md
```

Completed M80 execution-review loop prompt:

```text
docs/agent/runs/m80-execution-review-loop-prompt.md
```

Completed post-M80 planning-plus-review prompt:

```text
docs/agent/runs/post-m80-planning-plus-review-prompt.md
```

Completed M81 execution-review loop prompt:

```text
docs/agent/runs/m81-execution-review-loop-prompt.md
```

Completed post-M81 planning-plus-review prompt:

```text
docs/agent/runs/post-m81-planning-plus-review-prompt.md
```

Completed post-M81 acceptance-finalization prompt:

```text
docs/agent/runs/post-m81-acceptance-finalization-prompt.md
```

Completed M82 execution-review loop prompt:

```text
docs/agent/runs/m82-execution-review-loop-prompt.md
```

Completed post-M82 planning-plus-review prompt:

```text
docs/agent/runs/post-m82-planning-plus-review-prompt.md
```

Completed post-M82 acceptance-finalization prompt:

```text
docs/agent/runs/post-m82-acceptance-finalization-prompt.md
```

Completed M83 execution-review loop prompt:

```text
docs/agent/runs/m83-execution-review-loop-prompt.md
```

Completed post-M83 planning-plus-review prompt:

```text
docs/agent/runs/post-m83-planning-plus-review-prompt.md
```

Completed post-M83 acceptance-finalization prompt:

```text
docs/agent/runs/post-m83-acceptance-finalization-prompt.md
```

Completed M84 execution-review loop prompt:

```text
docs/agent/runs/m84-execution-review-loop-prompt.md
```

Completed post-M84 planning-plus-review prompt:

```text
docs/agent/runs/post-m84-planning-plus-review-prompt.md
```

Completed post-M84 acceptance-finalization prompt:

```text
docs/agent/runs/post-m84-acceptance-finalization-prompt.md
```

Completed M85 execution-review loop prompt:

```text
docs/agent/runs/m85-execution-review-loop-prompt.md
```

Completed post-M85 planning-plus-review prompt:

```text
docs/agent/runs/post-m85-planning-plus-review-prompt.md
```

Completed post-M85 acceptance-finalization prompt:

```text
docs/agent/runs/post-m85-acceptance-finalization-prompt.md
```

Completed M86 execution-review loop prompt:

```text
docs/agent/runs/m86-execution-review-loop-prompt.md
```

Completed post-M86 planning prompt:

```text
docs/agent/runs/post-m86-planning-plus-review-prompt.md
```

Completed post-M86 acceptance-finalization prompt:

```text
docs/agent/runs/post-m86-acceptance-finalization-prompt.md
```

Completed M87 execution-review loop prompt:

```text
docs/agent/runs/m87-execution-review-loop-prompt.md
```

Completed post-M87 planning-plus-review prompt:

```text
docs/agent/runs/post-m87-planning-plus-review-prompt.md
```

Completed post-M87 acceptance-finalization prompt:

```text
docs/agent/runs/post-m87-acceptance-finalization-prompt.md
```

Completed M88 execution-review loop prompt:

```text
docs/agent/runs/m88-execution-review-loop-prompt.md
```

Completed post-M88 planning-plus-review prompt:

```text
docs/agent/runs/post-m88-planning-plus-review-prompt.md
```

Completed post-M88 acceptance-finalization prompt:

```text
docs/agent/runs/post-m88-acceptance-finalization-prompt.md
```

Completed M89 execution-review loop prompt:

```text
docs/agent/runs/m89-execution-review-loop-prompt.md
```

Completed post-M89 planning-plus-review prompt:

```text
docs/agent/runs/post-m89-planning-plus-review-prompt.md
```

Completed post-M89 acceptance-finalization prompt:

```text
docs/agent/runs/post-m89-acceptance-finalization-prompt.md
```

Completed M90 execution-review loop prompt:

```text
docs/agent/runs/m90-execution-review-loop-prompt.md
```

Completed post-M90 planning-plus-review prompt:

```text
docs/agent/runs/post-m90-planning-plus-review-prompt.md
```

Completed post-M90 acceptance-finalization prompt:

```text
docs/agent/runs/post-m90-acceptance-finalization-prompt.md
```

Completed M91 execution-review loop prompt:

```text
docs/agent/runs/m91-execution-review-loop-prompt.md
```

Completed post-M91 planning-plus-review prompt:

```text
docs/agent/runs/post-m91-planning-plus-review-prompt.md
```

Completed post-M91 acceptance-finalization prompt:

```text
docs/agent/runs/post-m91-acceptance-finalization-prompt.md
```

Completed M92 execution-review loop prompt:

```text
docs/agent/runs/m92-execution-review-loop-prompt.md
```

Completed post-M92 planning-plus-review prompt:

```text
docs/agent/runs/post-m92-planning-plus-review-prompt.md
```

Completed post-M92 acceptance-finalization prompt:

```text
docs/agent/runs/post-m92-acceptance-finalization-prompt.md
```

Completed M93 execution-review loop prompt:

```text
docs/agent/runs/m93-execution-review-loop-prompt.md
```

Completed post-M93 planning-plus-review prompt:

```text
docs/agent/runs/post-m93-planning-plus-review-prompt.md
```

Completed post-M93 acceptance-finalization prompt:

```text
docs/agent/runs/post-m93-acceptance-finalization-prompt.md
```

Completed M94 execution-review loop prompt:

```text
docs/agent/runs/m94-execution-review-loop-prompt.md
```

Completed post-M94 planning-plus-review prompt:

```text
docs/agent/runs/post-m94-planning-plus-review-prompt.md
```

Completed post-M94 acceptance-finalization prompt:

```text
docs/agent/runs/post-m94-acceptance-finalization-prompt.md
```

Completed M95 execution-review loop prompt:

```text
docs/agent/runs/m95-execution-review-loop-prompt.md
```

Completed post-M95 planning-plus-review prompt:

```text
docs/agent/runs/post-m95-planning-plus-review-prompt.md
```

Completed post-M95 acceptance-finalization prompt:

```text
docs/agent/runs/post-m95-acceptance-finalization-prompt.md
```

Completed M96 execution-review loop prompt:

```text
docs/agent/runs/m96-execution-review-loop-prompt.md
```

Completed post-M96 planning-plus-review prompt:

```text
docs/agent/runs/post-m96-planning-plus-review-prompt.md
```

Completed post-M96 acceptance-finalization prompt:

```text
docs/agent/runs/post-m96-acceptance-finalization-prompt.md
```

Completed M97 execution-review loop prompt:

```text
docs/agent/runs/m97-execution-review-loop-prompt.md
```

Completed post-M97 planning-plus-review prompt:

```text
docs/agent/runs/post-m97-planning-plus-review-prompt.md
```

Completed post-M97 acceptance-finalization prompt:

```text
docs/agent/runs/post-m97-acceptance-finalization-prompt.md
```

Completed M98 execution-review loop prompt:

```text
docs/agent/runs/m98-execution-review-loop-prompt.md
```

Completed post-M98 planning-plus-review prompt:

```text
docs/agent/runs/post-m98-planning-plus-review-prompt.md
```

Completed post-M98 acceptance-finalization prompt:

```text
docs/agent/runs/post-m98-acceptance-finalization-prompt.md
```

Completed M99 execution-review-loop prompt:

```text
docs/agent/runs/m99-execution-review-loop-prompt.md
```

Completed post-M99 planning-plus-review prompt:

```text
docs/agent/runs/post-m99-planning-plus-review-prompt.md
```

Completed post-M99 acceptance-finalization prompt:

```text
docs/agent/runs/post-m99-acceptance-finalization-prompt.md
```

Completed M100 execution-review-loop prompt:

```text
docs/agent/runs/m100-execution-review-loop-prompt.md
```

Completed post-M100 planning-plus-review prompt:

```text
docs/agent/runs/post-m100-planning-plus-review-prompt.md
```

Completed post-M100 acceptance-finalization prompt:

```text
docs/agent/runs/post-m100-acceptance-finalization-prompt.md
```

Completed M101 execution-review-loop prompt:

```text
docs/agent/runs/m101-execution-review-loop-prompt.md
```

Completed post-M101 planning-plus-review prompt:

```text
docs/agent/runs/post-m101-planning-plus-review-prompt.md
```

Completed post-M101 acceptance-finalization prompt:

```text
docs/agent/runs/post-m101-acceptance-finalization-prompt.md
```

Completed M102 execution-review-loop prompt:

```text
docs/agent/runs/m102-execution-review-loop-prompt.md
```

Completed post-M102 planning-plus-review prompt:

```text
docs/agent/runs/post-m102-planning-plus-review-prompt.md
```

Completed post-M102 acceptance-finalization prompt:

```text
docs/agent/runs/post-m102-acceptance-finalization-prompt.md
```

Completed M103 execution-review-loop prompt:

```text
docs/agent/runs/m103-execution-review-loop-prompt.md
```

Completed post-M103 planning-plus-review prompt:

```text
docs/agent/runs/post-m103-planning-plus-review-prompt.md
```

Completed post-M103 acceptance-finalization prompt:

```text
docs/agent/runs/post-m103-acceptance-finalization-prompt.md
```

Completed M104 execution-review-loop prompt:

```text
docs/agent/runs/m104-execution-review-loop-prompt.md
```

Completed post-M104 planning-plus-review prompt:

```text
docs/agent/runs/post-m104-planning-plus-review-prompt.md
```

Completed post-M104 acceptance-finalization prompt:

```text
docs/agent/runs/post-m104-acceptance-finalization-prompt.md
```

Completed M105 execution-review-loop prompt:

```text
docs/agent/runs/m105-execution-review-loop-prompt.md
```

Completed M106 execution-review-loop prompt:

```text
docs/agent/runs/m106-execution-review-loop-prompt.md
```

Completed M107 execution-review-loop prompt:

```text
docs/agent/runs/m107-execution-review-loop-prompt.md
```

Completed M108 execution-review-loop prompt:

```text
docs/agent/runs/m108-execution-review-loop-prompt.md
```

Completed M109 execution-review-loop prompt:

```text
docs/agent/runs/m109-execution-review-loop-prompt.md
```

Completed M110 execution-review-loop prompt:

```text
docs/agent/runs/m110-execution-review-loop-prompt.md
```

Active M111 execution-review-loop prompt:

```text
docs/agent/runs/m111-execution-review-loop-prompt.md
```

## Current Boundary Rules

- `frozen/` is evidence only and must never become runtime input.
- `tslgenold/` is evidence-only old implementation state and must never become
  a runtime dependency of the clean restart package.
- M107 established the tiny clean source-to-artifact path under fresh
  `tslgen/`.
- M108 is limited to the exact M107 `add(left, right)` / `scalar` / `si32`
  body lowering boundary.
- M109 is limited to an explicit writer boundary for existing in-memory
  artifact values; parsing, catalog, selection, lowering, and backend emission
  must remain write-free.
- M110 is limited to a tiny clean scalar type lowering table over the accepted
  scalar `add(left, right)` path; it must not add CLI work, broad TSIL parsing,
  vector/SIMD semantics, backend-manifest reads, old type/lowering module
  migration, or a broad type-system framework.
- M111 is limited to a tiny clean binary-operation lowering table over the
  accepted scalar binary source form; it must not add CLI work, broad
  expression parsing, division/modulo semantics, vector/SIMD semantics,
  backend-manifest reads, old operation/lowering migration, or a broad
  expression/type framework.
- M43 produces backend-neutral `GenerationTypeRef` values.
- M45 produces explicit intrinsic suffix modifier values such as `epi32`.
- M46 produces explicit backend type-spelling values such as `int32_t` and
  `uint32_t`.
- M47 consumes M45 and M46 translated values for the selected native integer add
  output.
- Renderers must not infer suffixes, type spellings, generation-time helper
  semantics, or backend modifier semantics.
- Renderers must not evaluate generation-time helpers.
- Backend translation must not parse raw generation helper text.
- Future semantic behavior must be expressed as typed rules or typed evaluator
  functions over explicit IR/domain values.
- M48 is generation-time semantic lowering only.
- M48 consumes typed M43 `GenerationTypeRef(kind="base.in")` values for
  signedness predicate branch pruning.
- M48 includes no backend translation, rendering, generated output,
  CLI/report/writer, Rust, or compiler execution work.
- M49 is generated C++ test-source rendering only. It consumes typed
  `TestSourcePlan` / `PlannedTestCase` values for the selected scalar
  `add_i32_basic` case plus explicit typed C++ type-spelling input for
  `si32 -> int32_t`.
- M49 must not compile or run generated tests, fetch or require `gtest`, read
  legacy templates at runtime, infer type spellings locally, broaden
  generated-test parity, or modify generation-time lowering, backend
  translation, generated implementation output rendering, CLI/report/writer,
  Rust, or compiler execution behavior.
- M50 is reporting-adapter work only.
- M50 is selected-row only: primitive `add`, extension `avx2`, language `cpp`,
  and type `f32`.
- M50 produces only the selected legacy coverage JSON row adapter.
- M50 consumes accepted `PipelineCoverageReport` / primitive coverage DTOs or
  equivalent typed report data, plus a new M50 typed adapter request and
  selected-row fact value carrying the exact selected legacy-row facts.
- Legacy string-valued booleans are adapter/serialization output only; internal
  report values must remain typed.
- M50 must not implement whole `primitive_coverage.json` parity, row-count
  parity, broad coverage matrix parity, coverage HTML/site parity, CLI workflow
  compatibility, new CLI flags, writer/report file writes, backend rendering,
  generation-time lowering, backend translation, generated C++ implementation
  output, test-source rendering, Rust output, compiler execution, or
  generated-test execution.
- M50 must not read `frozen/`, legacy report tools, raw legacy JSON, or raw TSL
  at runtime.
- M50 must not rerun parsing, selection, lowering, backend rendering, or test
  planning during adapter serialization.
- M51 is generation-time semantic lowering only.
- M51 accepts only the exact signedness predicate branch form
  `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
  with plain `else`.
- M51 reuses M48 signedness predicate evaluation over typed M43
  `GenerationTypeRef(kind="base.in")` inputs.
- M51 reuses M42/M48 branch pruning, deterministic provenance, and
  selected-branch-only diagnostics.
- M51 treats plain `else` as equivalent to `else<generation>` only for this
  selected signedness predicate branch form.
- M51 must preserve existing `else<generation>` signedness branch behavior.
- M51 must not add broad plain-`else` support for arbitrary generation
  branches.
- M51 must not add primitive-attribute plain `else` support.
- M51 must not add conversion or shift body parity.
- M51 must not add `switch<compile>`, `if<compile>`, direct `intrin<...>`,
  `let`, `var`, calls, vector transforms, loops, aliases, casts, arrays,
  generic lengths, immediates, vector/register metadata, backend translation,
  backend rendering, generated C++ output, generated test sources, Rust output,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, broad TSIL parsing, or branch-body semantics.
- M51 must not broaden signedness predicates beyond the selected M43
  `si32`/`ui32` `base.in` inputs.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is selected M51
  branch-shape evidence only. Its enclosing `switch<compile>` and branch
  bodies remain out of scope.
- `frozen/` remains evidence only.
- M52 is generation-time semantic lowering only.
- M52 extends only the accepted M43/M48/M51 concrete integer
  type/signedness semantics from `si32`/`ui32` to the selected concrete integer
  tags `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
- M52 supports only the exact M43 type query forms
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`, and
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`.
- M52 supports only the exact M48/M51 signedness predicate branch forms
  over typed `GenerationTypeRef(kind="base.in")` inputs, with
  `else<generation>` or the M51 plain `else` spelling.
- M52 must express signed/unsigned companion behavior as typed rules or typed
  evaluator functions, not raw text rewriting.
- M52 must keep wildcard/group selectors such as `?i?`, `?i64`, `si?`,
  `ui?`, and `idqword` unsupported as selected concrete type tags during
  lowering.
- M52 must not add backend translation expansion, including suffix or
  type-spelling expansion beyond accepted M45/M46 `si32`/`ui32` behavior.
- M52 must not add C++ or Rust rendering, generated output, generated
  test sources, CLI/reporting, writer behavior, compiler execution,
  generated-test execution, vector/register metadata, vector length/alignment,
  generic lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, shift body parity, or conversion body parity.
- M53 is a semantic rule-source boundary slice only.
- M53 moves the accepted M52 concrete integer generation type/signedness
  semantics from a lowering-private table into typed domain/catalog rule values
  consumed by lowering.
- M53 must preserve behavior exactly for
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`,
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`, and the
  exact M48/M51 signedness predicate branch forms.
- M53 must preserve exactly the selected concrete tags `si8`, `ui8`, `si16`,
  `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
- M53 must preserve M52 diagnostics, deterministic ordering, branch provenance,
  and selected-branch-only diagnostics unless a narrower rule-source diagnostic
  is required for missing or inconsistent rule data.
- M53 must preserve backend-translation rejection of raw unresolved generation
  helpers and renderer non-evaluation.
- M53 must preserve M45/M46 backend translation limits and must not expand
  suffix or type-spelling translation beyond accepted selected `si32`/`ui32`
  behavior.
- M53 must not infer broad integer semantics from regex or tag spelling alone.
- M53 must not treat wildcard/group selectors such as `?i?`, `?i64`, `si?`,
  `ui?`, and `idqword` as selected concrete type tags during lowering.
- M53 must not add new generation-time helper forms, backend translation
  expansion, C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, vector length/alignment, generic
  lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, broad TSIL parsing, or runtime dependency on `frozen/`.
- M54 is a pipeline/lowering-input wiring slice only.
- M54 wires the accepted M53 `ConcreteIntegerGenerationRuleSet` through
  the normal catalog/lowering-input path for pipeline-facing use.
- M54 must build or expose concrete integer generation rules from typed
  catalog/type-group data before lowering evaluation.
- M54 must preserve all accepted M52/M53 type-query and signedness
  branch behavior, diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless an explicit catalog-derived
  rule-source diagnostic is required.
- M54 must prove explicit catalog-derived rule data is consumed by
  lowering and that missing or inconsistent explicit rule data is not hidden by
  a synthetic default fallback.
- M54 must preserve M45/M46 backend translation limits and must not
  expand suffix or type-spelling translation beyond accepted selected
  `si32`/`ui32` behavior.
- M54 must not add new generation-time helper forms, backend translation
  expansion, C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, vector length/alignment, generic
  lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, broad TSIL parsing, broad generic semantic-rule registries, or
  runtime dependency on `frozen/`.
- M54 must not make lowering read files, parse raw TSL, query the
  catalog during evaluation, or infer broad integer semantics from regex, tag
  spelling, wildcard/group selectors, or concrete-looking unselected tags.
- M55 is generation-time semantic lowering only.
- M55 selects exactly
  `value<generation>(type::size_bytes(type<generation>(base::in)))`.
- M55 produces typed integer generation values for explicit selected
  scalar tags: `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, `ui64`,
  `f32`, and `f64`.
- M55 must use explicit scalar size-byte rule/value records and must
  not reuse or mutate `ConcreteIntegerGenerationRuleSet` for float size
  semantics.
- M55 accepts `f32` and `f64` only for the exact size-bytes value query
  and must not broaden standalone `type<generation>(base::in)` or
  signed/unsigned companion behavior to floats.
- M55 must not infer sizes from regex, tag spelling, wildcard/group
  selectors, or unselected concrete-looking tags such as `si128`.
- M55 must not add arithmetic or comparisons over generation values,
  branch pruning from size values, enclosing body lowering, backend
  translation expansion, rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, Rust, compiler execution, generated-test
  execution, vector/register metadata, loops, casts, calls, direct
  `intrin<...>`, broad TSIL parsing, or runtime dependency on `frozen/`.
- M55 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.
- M56 is generation-time semantic lowering only.
- M56 selects exactly
  `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`.
- M56 consumes the M55 typed `GenerationValue(kind="type.size_bytes")`
  behavior and explicit scalar size-byte rules to produce typed scalar
  bit-width generation values.
- M56 must not add general arithmetic, operators other than the exact
  selected `* 8` expression, reversed operands, arbitrary literals,
  comparisons such as `== 2`, branch pruning, `else if<generation>`,
  branch-chain syntax, surrounding body lowering, backend translation,
  rendering, generated output, generated test sources, CLI/reporting, writer
  behavior, Rust, compiler execution, generated-test execution,
  vector/register metadata, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- M56 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.
- M57 is generation-time semantic lowering only.
- M57 selects exactly the size-byte equality generation predicates
  `value<generation>(type::size_bytes(type<generation>(base::in))) == 2`,
  `== 4`, and `== 8`.
- M57 consumes the M55 typed
  `GenerationValue(kind="type.size_bytes")` behavior and explicit scalar
  size-byte rules to produce typed boolean generation predicate values.
- M57 treats `si8`/`ui8` byte size `1` as `false` for all selected
  predicates and must not introduce branch-chain no-match policy.
- M57 must not add branch pruning, `if<generation>` parsing,
  `else if<generation>`, selected-arm/no-match provenance, direct
  `intrin<...>` calls, assignments, SVE array/load-store bodies, vector
  metadata, backend translation, rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, Rust, compiler execution,
  generated-test execution, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- M57 must not add standalone comparison forms outside the exact
  selected predicates, general comparison parsing, final `else`, broad
  no-final-else branch policy, or branch-body semantics.
- M57 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.
- M58 is generation-time semantic lowering stage-boundary work only.
- M58 must introduce a genuinely extendable and maintainable typed staged
  lowering contract, not merely rename or wrap current functions and not create
  a broad central string-matching or `if`/`elif` evaluator.
- M58 must give introduced or refined stage boundaries explicit typed inputs
  and outputs suitable for future stages.
- M58 organizes the accepted M55 `GenerationValue(kind="type.size_bytes")`,
  M56 `GenerationValue(kind="type.size_bits")`, and M57
  `GenerationPredicate(kind="type.size_bytes.equals")` results so later
  control-flow pruning can consume typed results without backend/rendering
  changes or raw helper re-evaluation.
- M58 must preserve accepted M55/M56/M57 observable lowered outputs exactly and
  preserve accepted M42/M48/M51 generation branch-pruning behavior exactly.
- M58 must not add new generation-time helper semantics, new arithmetic,
  comparison, or predicate semantics, size-byte equality branch-chain pruning,
  `else if<generation>` support, no-match provenance, selected branch body
  handoff, direct `intrin<...>` / SVE body lowering, vector/register metadata,
  backend translation expansion, rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, Rust, compiler execution, broad
  TSIL parsing, or runtime dependency on `frozen/`.
- M58 must not make lowering read files, parse raw TSL, or query the catalog
  during evaluation; catalog-derived rule construction must remain before
  evaluation.
- M59 is generation-time semantic lowering control-flow pruning only.
- M59 must consume typed M57/M58 predicate and stage outputs instead of
  re-evaluating raw generation helper text.
- M59 selects only the exact no-final-else SVE size-byte chain from
  `tsldata/primitives/load_store/array.tsl:107-109`, with documented
  `== 2`, `== 4`, and `== 8` arm order.
- M59 selects matching arms for byte sizes `2`, `4`, and `8`.
- M59 records explicit no-match provenance for byte size `1` without
  synthesizing a final `else`.
- M59 keeps all branch bodies opaque and must not introduce the M60 selected
  body handoff contract.
- M59 may include only the smallest typed reuse cleanup needed to avoid
  duplicating private staged-predicate assembly or re-evaluating raw helper
  text.
- M59 must preserve accepted M55/M57/M58 value, predicate, and stage outputs,
  backend raw-helper rejection, and renderer non-evaluation.
- M59 must not add broad `else if<generation>` syntax beyond the exact
  selected chain shape, final `else`, reordered chains, missing arms, duplicate
  arms, nested branches, broad no-final-else policy, standalone comparison
  evaluation, general comparison parsing, M60 opaque selected branch body
  handoff, direct `intrin<...>` / SVE body lowering, assignments, variables,
  arrays, calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting, writer
  behavior, Rust, compiler execution, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- M59 must not make lowering read files, parse raw TSL, or query the catalog
  during evaluation.
- M60 is generation-time semantic lowering only.
- M60 consumes accepted typed M59 branch-chain pruning/stage output.
- M60 introduces a distinct typed opaque selected-body handoff value or
  equivalent typed stage output.
- M60 must keep branch bodies opaque.
- M60 must not parse or lower selected or unselected body semantics.
- M60 must not synthesize a selected body for byte-size `1` no-match cases.
- M60 must not invoke mini TSIL lowering or produce direct-intrinsic/SVE
  `TsilStatement` values for the branch-chain path.
- M60 must preserve backend raw-helper rejection and renderer non-evaluation.
- M60 must not add direct `intrin<...>` / SVE body lowering, assignments,
  variables, arrays, calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M61 is generation-time lowering form-recognition work only.
- M61 must consume accepted typed M60 selected-body handoff outputs, not raw
  branch-chain text, raw TSL, catalog data, or `frozen/` runtime input.
- M61 may recognize only the exact selected single-statement assignment form
  from `tsldata/primitives/load_store/array.tsl:107-109`:
  `pg = intrin<svptrue_b16>();`, `pg = intrin<svptrue_b32>();`, and
  `pg = intrin<svptrue_b64>();`.
- M61 output must be typed/provenanced form metadata only, preserving target
  text, opaque RHS/direct-intrinsic token text, original body text, and
  M60 handoff identity.
- M61 must not lower assignment semantics, validate direct intrinsics, infer
  SVE predicate meaning, map byte-size literals to intrinsic suffixes, inspect
  unselected branch bodies, or synthesize a body/form for `si8`/`ui8`
  no-match cases.
- M61 must not add direct `intrin<...>` / SVE body lowering, declarations,
  variables, arrays, calls, casts, loops, multi-statement bodies,
  vector/register metadata, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M62 is accepted as generation-time lowering body-IR work only.
- M62 must consume accepted typed M61 `selected_body_form_recognition`
  outputs, not raw selected body text except as preserved provenance.
- M62 may produce unresolved typed selected assignment/direct-intrinsic body IR
  only for the exact M61-recognized single-statement form
  `pg = intrin<svptrue_b16|svptrue_b32|svptrue_b64>();`.
- M62 must expose a distinct post-form-recognition stage or typed value, such
  as `selected_body_ir_lowering`, rather than stretching M60 handoff or M61
  form-recognition metadata into a mixed dispatcher.
- M62 must preserve target text, direct-intrinsic token text, original RHS/body
  text, selected type/literal, and provenance as typed IR facts.
- M62 must not validate intrinsic names, infer SVE predicate meaning, prove
  `pg` scope/type, map byte-size literals to `svptrue_b*` tokens, create
  backend intrinsic IR, create backend translation requests, feed renderers, or
  emit generated output.
- M62 must not add broad assignment semantics, broad direct `intrin<...>`
  lowering, non-zero-argument calls, declarations, variables, arrays, stores,
  casts, loops, multi-statement bodies, `emit_return`, vector/register
  metadata, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M63 is generation-time lowering/body-envelope IR work only.
- M63 must consume only accepted typed M62 `selected_body_ir_lowering` outputs
  or equivalent typed M62 values: `SelectedAssignmentDirectIntrinsicBodyIr`
  and `NoSelectedAssignmentDirectIntrinsicBodyIr`.
- M63 must expose a distinct post-M62 stage or typed value, such as
  `selected_body_envelope_lowering`, rather than stretching M62 body IR into a
  mixed dispatcher.
- M63 must produce a backend-neutral selected-body envelope with deterministic
  ordering. For selected cases, the typed sequence is exact and singleton,
  wrapping only the existing M62 selected assignment/direct-intrinsic body IR.
- M63 must produce an explicit no-body envelope for M62 no-body-IR cases
  without synthesizing statements or body text.
- M63 may preserve M62 target text, direct-intrinsic token text, explicit
  empty argument list, original RHS/body text, selected type/literal, source
  location, branch identity, and provenance as typed facts.
- SVE-looking corpus text is evidence only. M63 must not make `svptrue_b*`,
  `pg`, `svbool_t`, `svst1`, vector metadata, backend uninit values, or
  `emit_return` architectural concepts or semantic rules.
- M63 must not parse preserved body text to derive semantics, validate direct
  intrinsics, infer SVE predicate/vector semantics, map byte sizes to
  intrinsic tokens, add assignment binding, declaration handling, variable
  scope, array/store/return lowering, vector length/alignment, backend
  translation, rendering, output, generated tests, CLI/report/writer behavior,
  Rust, compiler execution, broad TSIL parsing, lowering-time file reads, raw
  TSL parsing, catalog queries, runtime `frozen/` use, dictionaries/raw string
  keys as downstream semantic models, or backend-specific branches in the
  envelope stage.
- M64 is generation-time lowering/body-envelope slot assembly work only.
- M64 must consume accepted typed M63 `selected_body_envelope_lowering`
  outputs or equivalent typed M63 envelope values:
  `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`.
- M64 may assemble only the exact ordered structural array-body skeleton
  evidenced by `tsldata/primitives/load_store/array.tsl:105-111`.
- M64 must produce deterministic typed opaque slots around one selected-body
  slot that references the M63 envelope. Slot labels are structural/
  provenance labels only, not semantic statement kinds.
- M64 must not loosen M63's singleton selected-body envelope invariant or
  synthesize selected branch text for `si8`/`ui8` no-body cases.
- SVE-looking corpus text is evidence only. M64 must not make `svbool_t`,
  `pg`, `svptrue_b*`, `svst1`, `tmp.data()`, vector metadata, backend uninit
  values, or `emit_return` architectural concepts or semantic rules.
- M64 must not add declaration semantics, assignment binding, variable scope,
  array semantics, direct-intrinsic semantics, SVE predicate/vector semantics,
  byte-size-to-token inference, store semantics, return semantics, vector
  length/alignment evaluation, backend uninit semantics, backend translation,
  rendering, output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, broad TSIL parsing, lowering-time file reads, raw TSL
  parsing, catalog queries, runtime `frozen/` use, dictionaries/raw string keys
  as downstream semantic models, or backend-specific branches.
- M65 is generation-time lowering pipeline-integration work only.
- M65 must consume accepted M63 selected/no-body envelopes and accepted M64
  `ExactArrayBodyEnvelopeSkeleton` values supplied in memory.
- M65 must key skeleton lookup by typed candidate id, selected type tag, and
  branch-chain identity, not by raw body text.
- M65 must call the accepted M64 `assemble_exact_array_body_envelope` boundary,
  populate `LoweredImplementation.array_body_envelopes`, and append the
  `array_body_envelope_slot_assembly` stage after
  `selected_body_envelope_lowering`.
- M65 must make the skeleton-required policy concrete: no-skeleton input
  preserves existing M63-only behavior unless a candidate is explicitly marked
  as requiring a skeleton.
- M65 must diagnose missing required skeleton input, duplicate/conflicting
  skeletons, skeletons supplied for candidates without M63 envelopes, and
  skeleton/envelope provenance mismatches.
- M65 must not produce or recognize skeletons from raw payload text, parse
  broad TSIL or `array.tsl` during lowering evaluation, lower slot-specific
  semantics, treat M64 slot labels as semantic statement kinds, or add
  declaration, assignment, array, store, return, variable, `tmp.data()`,
  `emit_return`, direct-intrinsic, SVE predicate/vector/register,
  byte-size-to-`svptrue_b*`, vector length/alignment, backend uninit, backend
  translation, renderer-ready IR, rendering, output, CLI/report/writer, Rust,
  compiler, generated-test, file-read, catalog-query, raw TSL parsing, or
  runtime `frozen/` behavior.
- M66 is accepted as exact array-initialization slot form IR only. M66
  consumes accepted M65 `ExactArrayBodyEnvelopeIr` /
  `LoweredImplementation.array_body_envelopes` values or the typed
  `array_body_envelope_slot_assembly` stage, refines only the
  `opaque_pre_branch_array_initialization` slot at ordinal `0`, and preserves
  all other slots as opaque.
- M66 may use the typed slot's opaque source text only for local exact-form
  recognition of `tsldata/primitives/load_store/array.tsl:105`; it must not
  scan raw payloads, produce skeletons, parse broad TSIL, or dispatch behavior
  from raw text.
- M66 must not evaluate `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- M66 must not add generic declaration semantics, array allocation/lifetime,
  variable binding/scope, store/return lowering, `tmp.data()`,
  `emit_return`, SVE/direct-intrinsic semantics, vector metadata semantics,
  backend uninit semantics, backend translation, renderer-ready IR,
  rendering, output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, file/catalog reads, or runtime `frozen/` behavior.
- M67 is accepted as exact array-initialization helper-request IR only. M67
  consumes accepted M66 `ExactArrayInitializationSlotFormIr` values, the
  `array_initialization_slot_form_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M66
  `array_initialization_slot_forms` entry.
- M67 must classify exactly four M66 leaves into typed deferred request
  records: `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, and
  `value<backend>(uninit::array)`.
- M67 must preserve source leaf text, leaf kind, source locations, candidate
  id, selected type tag, branch-chain identity, envelope identity, slot
  ordinal, variable token `tmp`, and deterministic request ordering.
- M67 must not evaluate, resolve, translate, normalize, or render any helper.
- M67 must not call existing generation helper evaluators, including M43 base
  type resolution.
- M67 must not produce `GenerationTypeRef`, `GenerationValue`, vector metadata
  values, backend uninit values, backend translation requests, renderer-ready
  IR, generated output, generated tests, CLI/report/writer behavior, Rust, or
  compiler execution.
- M67 must not add generic helper parsing, generic `var` parsing, generic
  `array_type` parsing, declaration semantics, array allocation/lifetime,
  variable scope, store/return lowering, `tmp.data()`, `emit_return`,
  direct-intrinsic/SVE semantics, broad TSIL parsing, file/catalog reads during
  lowering, raw-text dispatch tables, or runtime `frozen/` use.
- M68 is accepted as exact array-initialization base-type helper
  request resolution only. M68 must consume accepted M67
  `ExactArrayInitializationHelperRequestIr` values, the
  `array_initialization_helper_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M67
  `array_initialization_helper_requests` entry.
- M68 must resolve only the M67 base-type request record with request ordinal
  `0`, request kind `generation_type`, and helper leaf kind
  `type_generation_base_in` into a typed result equivalent to
  `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`.
- M68 must preserve source M67 request IR, source request record, leaf source
  text as provenance only, source locations, candidate id, selected type tag,
  branch-chain identity, envelope identity, slot ordinal, variable token
  `tmp`, and deterministic result ordering.
- M68 must not parse, regex-match, normalize, or dispatch on M67
  `leaf_source_text`, M66 `original_slot_text`, raw TSIL, raw TSL, or helper
  strings.
- M68 must not hardwire request resolution through ad-hoc tables or `if`/`elif`
  branches keyed by raw helper text, selected type tags, or request ordinals.
  It must consume typed M67 request records and accepted typed
  rule/context inputs.
- M68 must not call raw query-string helper evaluators such as
  `resolve_generation_type_query(...)` on M67 leaf text unless such behavior is
  refactored behind a typed, non-text entry point and tests prove no raw helper
  text is parsed.
- M68 must not resolve `base.signed_of`, `base.unsigned_of`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- M68 must not produce `GenerationValue`, vector metadata values, backend
  uninit values, backend translation requests, renderer-ready IR, generated
  output, generated tests, CLI/report/writer behavior, Rust, or compiler
  execution.
- M68 must not add generic helper parsing, generic `var` parsing, generic
  `array_type` parsing, declaration semantics, array allocation/lifetime,
  variable scope, store/return lowering, `tmp.data()`, `emit_return`,
  direct-intrinsic/SVE semantics, broad TSIL parsing, file/catalog reads during
  lowering evaluation, catalog queries during evaluation, raw-text dispatch
  tables, or runtime `frozen/` use.
- M69 is accepted as behavior-preserving exact array-initialization stage
  pipeline extraction only. M69 extracts the accepted M64-M68
  array-initialization stage assembly tail from `_lower_input` into a private
  typed helper/result.
- M69 must preserve the same public `LoweredImplementation` fields, stage
  names, stage order, typed outputs, diagnostics, source locations,
  deterministic ordering, no-skeleton/no-body behavior, and generated-output
  state as accepted M68.
- M69 must keep accepted calls to M64/M66/M67/M68 lowering functions in the
  same order and with the same typed inputs.
- M69 must not add public IR, new `LoweredImplementation` fields, new stage
  names, renderer-facing values, semantic helper resolution, vector
  length/alignment resolution, backend uninit resolution, generic helper
  parsing, broad stage registries, raw helper-string dispatch, raw
  query-string helper evaluation, backend translation, rendering, generated
  output, generated tests, CLI/report/writer behavior, Rust, compiler
  execution, broad TSIL parsing, lowering-time file/catalog reads, `tsldata`
  reads during lowering evaluation, or runtime `frozen/` use.
- M70 is accepted as exact array-initialization
  vector-length request resolution only. M70 must resolve exactly the M67
  `value<generation>(vector::length)` request through the accepted M69
  extracted pipeline and explicit typed vector-length metadata supplied before
  lowering evaluation.
- M70 must consume typed M67/M68/M69 request/result values and typed candidate
  context. It must not parse M66 slot text, M67 leaf text, raw TSIL, raw TSL,
  `candidate_id`, SVE tokens, extension names, vector-bit strings, backend ids,
  or renderer names to produce semantic vector-length values.
- M70 must preserve accepted M68 base-type behavior and keep
  `value<generation>(vector::alignment)` and
  `value<backend>(uninit::array)` unresolved.
- M70 must not infer fixed lane counts from SVE/scalable/runtime-lane
  metadata. Runtime/scalable metadata must remain an explicit typed
  value/policy or produce diagnostics.
- M70 must not add broad vector/register metadata semantics, vector alignment
  resolution, backend uninit resolution, declaration/array semantics,
  direct-intrinsic/SVE semantics, generic helper dispatch, broad stage
  registries, backend translation, rendering, generated output, generated
  tests, CLI/report/writer behavior, Rust, compiler execution, broad TSIL
  parsing, lowering-time file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, or runtime `frozen/` use.
- M71 is accepted as exact array-initialization
  vector-alignment request resolution only. M71 must resolve exactly the M67
  `value<generation>(vector::alignment)` request through the accepted M69/M70
  extracted pipeline and explicit typed vector-alignment metadata supplied
  before lowering evaluation.
- M71 must consume typed M67/M68/M69/M70 request/result values and typed
  candidate context. It must not parse M66 slot text, M67 leaf text, raw TSIL,
  raw TSL, `candidate_id`, SVE tokens, extension names, vector-bit strings,
  selected type tags, backend ids, backend vector-alignment spellings, or
  renderer names to produce semantic vector-alignment values.
- M71 must preserve accepted M68 base-type behavior and accepted M70
  vector-length behavior, and keep `value<backend>(uninit::array)` unresolved.
- M71 must not infer alignment from vector length, vector bits, scalar byte
  size, selected type tags, extension names, SVE token text, host CPU state,
  catalog data, `tsldata`, backend maps, or renderer names.
- M71 must not add broad vector/register metadata semantics, backend uninit
  resolution, declaration/array semantics, aligned load/store semantics,
  `assume_aligned`, direct-intrinsic/SVE semantics, generic helper dispatch,
  broad stage registries, backend translation, rendering, generated output,
  generated tests, CLI/report/writer behavior, Rust, compiler execution, broad
  TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, or runtime `frozen/` use.
- M72 is accepted as exact array-initialization helper-set completion IR only.
  M72 consumes accepted M71
  vector-alignment resolution values and packages the exact helper set into one
  typed aggregate: accepted M68 base type, accepted M70 vector length,
  accepted M71 vector alignment, and the remaining exact M67
  `value<backend>(uninit::array)` request.
- M72 must keep backend uninit as a typed deferred backend-value request
  boundary. It must not translate or render backend uninit, query backend
  maps, create backend translation requests, produce renderer-ready values,
  or change generated output.
- M72 must not add broad `var`, `array_type`, declaration,
  allocation/lifetime, variable binding/scope, initializer, store, return,
  `tmp.data()`, `emit_return`, `assume_aligned`, direct-intrinsic/SVE
  semantics, generic helper dispatch, broad stage registries, broad TSIL
  parsing, lowering-time file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, or runtime `frozen/` use.
- M73 is accepted as exact first-slot declaration-shell structural IR only.
- M73 consumes accepted M72
  `ExactArrayInitializationHelperSetCompletionIr` values, the
  `array_initialization_helper_set_completion` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M72 completion.
- M73 produces one typed structural IR value for the exact
  `array.tsl:105` `var<typed>(array_type<...>, tmp, ...)` shell, preserving
  accepted M68 base type, accepted M70 vector length, accepted M71 vector
  alignment, and the M72 deferred backend-uninit boundary.
- M73 appends one deterministic stage after
  `array_initialization_helper_set_completion`.
- M73 uses source text only as provenance/invariant evidence and must not
  reparse M66 slot text or M67 helper leaf text as semantic input.
- M73 must not translate or render backend uninit, query backend maps, create
  backend translation requests, produce renderer-ready IR, render C++/Rust/
  backend text, change generated output, parse generic `var` or `array_type`,
  model allocation/lifetime/initializer/variable scope semantics, lower stores
  or returns, interpret `tmp.data()`, lower `emit_return`, add
  direct-intrinsic/SVE semantics, parse broad TSIL, read `tsldata`/catalog/
  backend maps during lowering evaluation, or depend on `frozen/` at runtime.
- M74 is accepted as exact array-body structural sequence and structural/
  provenance slot-role classification only.
- M74 must consume accepted typed M64/M65 exact array-body envelope state and
  accepted M73 `ExactArrayInitializationDeclarationShellIr` values, the
  corresponding stage outputs, or a typed `LoweredImplementation` carrying
  exactly one matching envelope and declaration shell.
- M74 must produce one typed source-ordered structural sequence for the exact
  `array.tsl:105-111` body, with five structural/provenance roles: first-slot
  declaration shell, opaque predicate-init-shaped slot, selected-body envelope
  slot, opaque post-branch store-call-shaped slot, and opaque
  return-emission-shaped slot.
- M74 must attach the accepted M73 declaration shell only to slot ordinal `0`
  and preserve the accepted M63/M64 selected/no-body envelope only in the
  selected-body slot.
- M74 must use source text only as provenance/invariant evidence and must not
  derive semantics from raw body text, corpus line numbers, helper strings,
  SVE tokens, backend ids, renderer names, or catalog data.
- M74 must not interpret `svbool_t`, `pg`, `intrin<svptrue_b8>`,
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `emit_return`,
  `assume_aligned`, stores, returns, direct intrinsics, SVE predicate/vector/
  register semantics, byte-size-to-token relationships, backend uninit,
  backend maps, rendering, generated output, generic body/declaration/array
  semantics, allocation/lifetime, initializer behavior, variable scope, broad
  TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, or runtime `frozen/` use.
- M75 is accepted as exact predicate path structural/request IR only.
- M75 must consume accepted typed M74 exact array-body structural sequence
  state and accepted M63/M62 selected/no-body predicate update evidence.
- M75 must produce one typed exact predicate-path structural/request IR value
  for the exact path across slot 1 predicate initialization, slot 2 selected/
  no-body predicate update evidence, and slot 3 post-branch store-call
  predicate-token use.
- M75 must keep `svbool_t`, `pg`, `svptrue_b8`, selected `svptrue_b16/b32/b64`,
  and slot-3 `pg` as structural tokens/request provenance only.
- M75 must not interpret SVE predicate semantics, byte-size-to-token
  relationships, stores, `svst1`, `tmp.data()`, `a`, backend maps, rendering,
  generated output, variable scope, generic predicate/body/store semantics,
  broad TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, backend map reads, or runtime
  `frozen/` use.
- M76 is accepted as exact post-branch intrinsic call-site structural/request
  IR only.
- M76 must consume accepted M75 `ExactPredicatePathStructuralRequestIr` values,
  the `predicate_path_structural_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M75 value.
- M76 must produce one typed exact post-branch intrinsic call-site
  structural/request IR value for the exact `array.tsl:110` shape
  `intrin<svst1>(pg, tmp.data(), a);`.
- M76 must keep `intrin`, `svst1`, `pg`, `tmp.data()`, and `a` as structural
  tokens/provenance only. The `pg` argument may be linked to accepted M75
  slot-3 predicate-token use; `tmp.data()` may be linked only to already
  accepted structural `tmp` provenance where carried through M73/M74/M75.
- M76 must not interpret store semantics, ARM/SVE intrinsic semantics, memory
  behavior, pointer semantics, operand semantics, `tmp.data()` semantics,
  variable scope/use-def/lifetime, declaration/array semantics, return
  semantics, backend maps, backend translation, renderer-ready IR, generated
  output, generic call/store/body semantics, broad TSIL parsing, lowering-time
  file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
  queries, backend map reads, or runtime `frozen/` use.
- M76 must not create generic call IR, generic store IR, broad helper
  registries, broad slot-role registries, broad stage registries, central
  semantic dispatchers, raw helper-string dispatch, renderer calls, generated
  artifacts, golden files, CLI/report/writer behavior, Rust behavior, compiler
  execution, or generated-test execution.
- Post-M76 planning selected M77 as behavior-preserving composable lowering
  pipeline/module-boundary work only.
- M77 must preserve accepted M57-M76 behavior, public lowering imports, stage
  names, output identities, diagnostics, and deterministic ordering.
- M77 may introduce private typed stage, pipeline, fact, request, dependency,
  artifact-store, or coordinator-boundary values only where needed for the
  accepted M58-M76 pattern.
- Future backfeeds must be represented as typed facts, typed requests,
  dependencies, or deterministic coordinator decisions. They must not be
  hidden recursive stage calls, broad registries, raw helper dispatch, or
  central semantic `if`/`elif` chains.
- Exact tokens such as `pg`, `svptrue_b16`, `svptrue_b32`, `svptrue_b64`,
  `intrin`, `svst1`, `tmp.data()`, and `a` must remain slice-local structural
  evidence unless a future accepted milestone introduces explicit typed
  semantic rules.
- M77 must not add new lowering semantics, whole-file rewrite behavior,
  generic call/body/store/return/declaration/array parsing or IR, backend
  translation, rendering, generated output, CLI/report/writer behavior, Rust,
  compiler execution, lowering-time file/catalog reads, `tsldata` reads,
  host CPU queries, backend map reads, or runtime `frozen/` use.
- M77 is accepted as behavior-preserving composable lowering pipeline/module
  boundary work. It adds private `tslgen.lowering._exact_shapes` and
  `tslgen.lowering._pipeline` modules while keeping public `tslgen.lowering`
  imports stable.
- M77's private pipeline snapshot records typed facts and dependencies for the
  accepted exact M69-M76 array-body tail and records no pending backfeed
  requests. It must not be treated as a generic registry, runtime plugin
  system, raw helper dispatcher, or semantic evaluator.
- M77's exact selected-body and post-branch shape tokens are slice-local
  structural evidence only. They must not become extension, SVE, store,
  memory, backend, renderer, or generated-output semantics without a future
  accepted typed semantic milestone.
- M78 is accepted as behavior-preserving lowering boundary package
  decomposition only.
- M78 moved exact array-initialization helper/slot shapes into
  `tslgen.lowering._array_body_shapes`, extracted exact array-body /
  array-initialization diagnostics into
  `tslgen.lowering._array_body_diagnostics`, and remaining M75 exact
  predicate-init recognizer tokens such as `svbool_t`, `pg`, and `svptrue_b8`
  into `tslgen.lowering._exact_shapes` as slice-local structural evidence.
- M78 kept public `tslgen.lowering` and `tslgen.lowering.boundary` import
  surfaces stable and reduced `boundary.py` to 11,109 physical lines from the
  12,371-line pre-M78 baseline.
- M79 is accepted as behavior-preserving exact array-body typed model
  ownership extraction. It moved exact array-body / array-initialization models
  into `tslgen.lowering._array_body_models`, kept public imports stable, kept
  private modules from importing `boundary.py`, and reduced `boundary.py` to
  8,915 physical lines from the 11,109-line post-M78 baseline.
- M80 is accepted as behavior-preserving exact array-body validation boundary
  extraction. It moved exact validation, request-record selection, metadata
  lookup validation, and small construction helpers into
  `tslgen.lowering._array_body_validation`, kept public imports stable, kept
  private modules from importing `boundary.py`, and reduced `boundary.py` to
  7,208 physical lines from the 8,915-line post-M79 baseline.
- M81 is accepted as behavior-preserving generation-time lowering core
  ownership extraction. It moved accepted generation-time model/query/
  control-flow/diagnostic helper ownership into private typed modules,
  preserved accepted M42-M80 behavior, kept source adapters/facade-owned
  orchestration in `boundary.py`, and reduced `boundary.py` to 5,438 physical
  lines from the 7,208-line post-M80 baseline.
- M82 is accepted as behavior-preserving selected-body value-model ownership
  extraction. It moved the minimal cohesive M60-M63 selected-body handoff/
  form/body-IR/envelope value-model cluster into
  `tslgen.lowering._selected_body_models`, kept `boundary.py` as the public
  facade/coordinator, preserved public imports and accepted behavior, tightened
  exact array-body selected/no-selected envelope consumers to concrete private
  model checks, and reduced `boundary.py` to 4,965 physical lines from the
  5,438-line post-M81 baseline.
- M83 is accepted as behavior-preserving `GenerationLoweringStage` output
  contract extraction. It moved the accepted stage-name/output validation
  contract, the accepted mini-TSIL statement value-model dependency, and
  `GenerationLoweringStage` into `tslgen.lowering._stage_contracts` while
  preserving public imports, stage names/order, output identities,
  deterministic keys, pipeline snapshots, and invalid-stage/output exception
  behavior. `boundary.py` remains the public facade/coordinator and now
  measures 4,807 physical lines from the 4,965-line M82 baseline.
- M84 is accepted as behavior-preserving exact array-body pipeline/
  source-adapter ownership extraction. It moved exact array-body pipeline,
  source-adapter, and exact-array public lowerer ownership into private typed
  lowering modules while preserving accepted M42-M83 behavior, public imports,
  diagnostics, source locations, stage names/order, output identities,
  deterministic keys, selected-branch-only behavior, and pipeline snapshots.
- M84 keeps `boundary.py` as the public facade for request/result models,
  selected-body public lowerers, `lower_candidates`, payload classification,
  and mini-TSIL lowering. Private exact array-body modules must not import
  `boundary.py` or the `tslgen.lowering` package facade.
- M84 did not create a second monolith, registry, generic dispatcher, callback
  map, plugin system, fixpoint/backfeed engine, raw-helper dispatcher,
  token-keyed semantic table, broad TSIL parser, broad source adapter, or new
  semantic evaluator.
- M84 did not add exact return-emission IR, `emit_return(tmp)`
  interpretation, `tmp.data()` semantics, store/call/body/return/declaration/
  array semantics beyond accepted exact structural/request records, backend
  translation, rendering, generated output, CLI/report/writer behavior, Rust,
  compiler execution, file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, backend map reads, or runtime `frozen/` use.
- M84 treats existing exact tokens as structural provenance or invariant
  evidence only, not semantic dispatch keys.
- M85 is accepted as behavior-preserving selected-body lowering ownership
  extraction. It moved accepted M60-M63 selected-body lowerer/source-helper
  ownership into `tslgen.lowering._selected_body_lowering` while preserving
  public facade behavior and imports through `tslgen.lowering` and
  `tslgen.lowering.boundary`.
- M85 did not move `LoweringRequest`, `LoweredImplementation`,
  `lower_candidates`, `_lower_input`, payload classification, mini-TSIL
  lowering, generation control-flow pruning, exact array-body pipeline/source
  modules, or request/result model ownership.
- M85 did not add new selected-body semantics, broad TSIL/body/call/store/
  return semantics, exact return-emission IR, backend translation, rendering,
  generated output, registries, generic dispatchers, callback maps,
  fixpoint/backfeed engines, raw-helper dispatch, file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime `frozen/` use.
- The M85 private selected-body lowering module does not import `boundary.py`,
  `tslgen.lowering`, `_array_body_sources.py`, or `_array_body_lowering.py` as
  convenience dispatchers. It uses a selected-body-local source-location
  helper for selected-body stage diagnostics.
- M86 is accepted as behavior-preserving candidate payload-intake and
  mini-TSIL leaf return lowering extraction. It moved `LoweringStrategy`,
  `PayloadClassification`, `ClassifiedPayload`, `LoweringInput`,
  `_classify_payload`, `_unsupported_payload_diagnostic`, and the accepted
  direct parameter-add / `intrin_compose<add>` mini-TSIL return lowerers into
  focused private typed modules.
- M86 kept `LoweringInputSet`, `LoweringRequest`, `GenerationContext`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, `_lower_input`, stage builders, `_context_for_candidate`,
  generation query payload lowering, generation control-flow pruning,
  selected-body lowering, exact array-body lowering, and exact array-body
  pipeline orchestration facade-owned.
- M86 did not introduce a handler registry, plugin system, callback map,
  ordered lowerer table, generic TSIL statement dispatcher, raw text rewrite
  engine, raw-helper dispatch, token-keyed semantic map, broad source-adapter
  protocol, fixpoint/backfeed engine, or broad TSIL/body/call/store/return
  semantics.
- The accepted M86 import direction is `boundary.py -> _lowering_inputs`,
  `boundary.py -> _mini_tsil_lowering`,
  `_mini_tsil_lowering -> _lowering_inputs and _stage_contracts`, and
  `_lowering_inputs -> candidates, diagnostics, result, values` only. The
  private modules must not import `boundary.py`, `tslgen.lowering`, selected-
  body lowering modules, exact array-body modules, backend modules, renderers,
  `tsldata`, or `frozen/`.
- M87 is generation-time/lowering structural-request work only.
- M87 consumes accepted M74 `ExactArrayBodyStructuralSequenceIr` provenance
  and accepted M76 post-branch call-site provenance as typed inputs.
- M87 records only the exact trailing `emit_return(tmp);` source shape,
  allowing insignificant whitespace.
- The M87 returned token must match the accepted M73 declaration-shell
  variable token as provenance only.
- M87 must not correct, normalize, rewrite, complete, reorder, or guess the
  intended meaning of malformed `.tsl` implementation bodies.
- Nearby or malformed return-emission forms are M87 diagnostic boundaries, not
  supported syntax.
- M87 must not broaden `emit_return(...)`, lower expressions inside
  `emit_return`, implement return-value semantics, variable lifetime/scope,
  `tmp.data()` semantics, store/call semantics, array semantics, backend
  translation, renderer-ready IR, rendering, generated output, generated
  tests, CLI/report/writer behavior, Rust, compiler execution, broad TSIL
  parsing, registries, dispatchers, plugin systems, raw helper dispatch, raw
  text rewriting, fixpoint/backfeed machinery, file/catalog reads, `tsldata`
  reads during lowering evaluation, backend map reads, host CPU queries, or
  runtime `frozen/` use.
- M87 must preserve accepted M64-M86 diagnostics, source locations, stage
  names/order, output identities, deterministic keys, selected-branch-only
  behavior, public imports, and pipeline snapshots.
- M87 is accepted as exact return-emission structural/request IR. It records
  only typed structural/provenance data in `ExactReturnEmissionStructuralRequestIr`
  and appends the deterministic `return_emission_structural_request_lowering`
  stage after the M76 post-branch call-site stage.
- M87's focused `_return_emission.py` module consumes direct M76 call-site
  values, the M76 stage output, or a private M76-only source protocol. It must
  not broaden the shared runtime lowered-implementation source protocol with
  M87 output.
- If M87 would turn an existing exact array-body module into a catch-all or
  push it materially past the roughly 1,000-line guardrail, prefer a focused
  private return-emission module with one-way imports and import-boundary
  tests, or document why a temporary exception is safer.
- M88 is accepted as exact array-body structural package assembly. It consumes
  accepted M64-M87 typed facts and assembles one source-ordered typed
  structural package only.
- M88 remains typed aggregation/provenance validation. It must not reparse or
  repair source bodies, infer declaration/store/return/SVE/backend semantics,
  query catalogs or backend maps, create renderer-ready IR, render output,
  generate code/tests, or broaden TSIL/body parsing.
- M88 uses focused private `_array_body_package.py` ownership. Protocol-shaped
  M87 sources are treated as untrusted runtime data and malformed entries must
  diagnose rather than raise or become implicit semantic inputs.
- M89 is accepted as exact array backend-deferred request inventory. It
  consumes accepted M88 package values and accepted M72/M67 backend-uninit
  typed facts only, preserving object identity/provenance.
- M89 remains Stage 8 typed inventory/provenance validation only. It must not
  resolve `value<backend>(uninit::array)`, read backend maps/catalogs or
  `tsldata/detail/lang`, add backend translation, Stage 9 backend planning,
  renderer-ready IR, rendering, generated output, generic backend-value
  evaluation, declaration/array/store/return/SVE semantics, raw helper
  dispatch, broad protocols, hidden backfeeds, or source-body repair.
- M90 is accepted as Stage 8 exact array lowering completion-package handoff
  work only. "Completion" means the accepted exact lowering handoff is
  packaged with explicit unresolved dependencies; it does not mean semantic
  body completion, backend readiness, renderer readiness, or generated output.
- M90 consumes accepted typed M88/M89 facts, validates context and
  identity/provenance, and produces one typed handoff package. It does not
  resolve backend values, read backend maps/catalogs, start Stage 9 backend
  planning, render output, infer declaration/store/return/SVE/backend
  semantics, repair source text, broaden TSIL parsing, or introduce generic
  backend-value evaluation.
- M90 uses focused private `_array_body_completion_package.py` ownership for
  completion-package logic. Future work must not grow `boundary.py`,
  `_array_body_pipeline.py`, `_array_body_models.py`,
  `_array_body_backend_deferred_requests.py`, or
  `_array_body_completion_package.py` into broader catch-all modules.
- M91 is accepted as behavior-preserving Stage 8 exact array pipeline
  ownership consolidation only. It moves exact array pipeline result DTO/key
  ownership into `_array_body_pipeline_results.py` and exact stage
  construction plus result/snapshot assembly into
  `_array_body_stage_assembly.py`.
- M91 preserves accepted M64-M90 diagnostics, source locations, stage
  names/order, output identities, deterministic keys, selected-branch-only
  behavior, public imports, no-external-input boundaries, and pipeline
  snapshots. It adds no backend planning, backend maps/catalog reads,
  renderer-ready IR, rendering, generated output, broad TSIL parsing,
  source-body repair, broad protocols, hidden backfeeds, fixpoint machinery,
  or hardwiring.
- M92 is accepted as a lowering-side backend-handoff request boundary only. It
  may consume accepted typed M90 completion packages through M91 stable
  ownership and produce one concrete typed handoff request for later backend
  planning, but it must not resolve backend values or start backend planning.
- M92 uses focused private `_array_body_backend_handoff.py` ownership for the
  handoff request. Future work must not stretch that module into backend
  planning, generic backend-helper evaluation, broad source protocols,
  renderer-ready IR, or generated-output ownership.
- M92 must preserve accepted M64-M91 diagnostics, source locations, stage
  names/order, output identities, deterministic keys, selected-branch-only
  behavior, public imports, no-external-input boundaries, and pipeline
  snapshots. It must not read backend maps/catalogs, create Stage 9 plans,
  create renderer-ready IR, render output, broaden TSIL parsing, repair source
  bodies, infer declaration/array/store/return/SVE/body semantics, introduce
  broad protocols, hidden backfeeds, fixpoint machinery, or hardwiring.
- M93 is accepted as a dual-source lowering operation package boundary only.
  It packages accepted M86 mini-TSIL leaf return values and accepted M92 exact
  array backend-handoff requests as distinct typed Stage 8 entries, but it
  must not become a broad cross-primitive operation framework.
- M93 must not add backend maps/catalog reads, backend-uninit resolution,
  Stage 9 backend planning, backend translation, renderer-ready IR, rendering,
  generated output, primitive dependency closure, operation scheduling,
  wrapper planning, artifact path planning, broad TSIL parsing, source repair,
  broad body/call/store/return/declaration/array/SVE semantics, registries,
  semantic dispatchers, hidden backfeeds, fixpoint machinery, or hardwiring.
- M94 is accepted as behavior-preserving operation-package maintainability
  work. It split M93 diagnostics, accepted-source narrowing, mini-TSIL
  package-contract checks, exact-array provenance validation, and package
  value models into focused private modules while preserving accepted M93
  package behavior exactly.
- M94 adds no new operation package families, new lowering semantics, backend
  maps/catalog reads, backend-uninit resolution, Stage 9 backend planning,
  backend translation, renderer-ready IR, rendering, generated output, broad
  source protocols, registries, semantic dispatchers, hidden backfeeds,
  fixpoint machinery, source repair, or hardwiring.
- M95 is accepted as a Stage 8 operation-package family slice over accepted
  M63 `SelectedBodyEnvelopeIr` values and enclosed accepted M62
  `SelectedAssignmentDirectIntrinsicBodyIr` values.
- M95 preserves selected-body direct-intrinsic facts as typed provenance
  only. `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `pg`, selected literals,
  selected type tags, branch ids, extension ids, primitive names, backend ids,
  and source locations must not become semantic dispatch keys.
- M95 does not infer byte size, vector width, predicate meaning, backend
  support, or SVE/direct-intrinsic semantics from direct-intrinsic tokens. It
  does not parse raw selected-body text, repair source bodies, add backend
  translation, Stage 9 planning, renderer-ready IR, rendering, generated
  output, broad TSIL/body semantics, registries, dispatchers, hidden
  backfeeds, fixpoint machinery, or hardwiring.
- M95 isolates selected-body package validation and entry ownership in
  `_operation_package_selected_body.py`. `_operation_package_sources.py`
  received only narrow explicit integration and must not grow into a generic
  source protocol, callback map, registry, or dispatcher.
- M96 is accepted as Stage 8 lowering manifest/provenance work only. It
  consumes accepted `LoweringOperationPackageIr` values as its primary input.
- M96 preserves M86 mini-TSIL leaf-return facts, M92 exact-array
  backend-handoff facts, and M95 selected-body direct-intrinsic facts only
  through accepted operation-package entries and already-preserved object
  references. It must not re-enter raw M86 statements, M92 handoff assembly,
  M63 envelopes, or the M90/M89/M72/M67 provenance chain except to validate
  already-preserved object references.
- M96 preserves accepted M92/M90 unresolved backend-handoff dependency
  references by object identity but does not resolve them.
- M96 "completion" and "readiness" mean accepted Stage 8 package/provenance
  assembly status only. They do not mean semantic body completion, backend
  readiness, renderer readiness, executable readiness, or generated-output
  readiness.
- Any M96 package graph is an identity/provenance graph of accepted
  operation-package records and explicit unresolved dependency references
  only. It must not become an operation DAG, operation schedule, dependency
  closure, backend plan, renderer IR, wrapper plan, artifact plan, package
  registry, source-family dispatcher, hidden backfeed, or fixpoint mechanism.
- M96 keeps manifest ownership in `_lowering_completion_manifest.py`.
  `boundary.py` coordinates the stage only, and `_operation_package_sources.py`
  is unchanged.
- M96 must not add backend translation, backend map/catalog reads,
  backend-uninit resolution, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, wrapper planning, artifact planning,
  renderer-ready IR, rendering, generated output, source repair, broad
  TSIL/body parsing, direct-intrinsic/SVE semantics, byte-size-to-token
  inference, registries, dispatchers, hidden backfeeds, fixpoint machinery,
  Rust, CLI/report/writer, compiler execution, or hardwiring.
- M97 is accepted as Stage 8 lowering gap-inventory work only. It consumes
  accepted M96 `Stage8LoweringCompletionManifestIr`
  values, `lowering_completion_manifest` stages, or a narrow one-manifest
  container.
- M97 "gap" means a lowering-observed deferred or unsupported fact visible
  from accepted M96 manifest facts only. The first supported gap category is
  accepted unresolved backend-handoff dependency records; manifests without
  such records produce a deterministic no-known-gap state.
- M97 preserves source manifest, package record, package object,
  unresolved dependency record, and source dependency request object identity.
- M97 keeps ownership in `_lowering_completion_gap_inventory.py`, keeps
  `_operation_package_sources.py` unchanged, and integrates one
  `lowering_completion_gap_inventory` stage after
  `lowering_completion_manifest`. Final line counts are `boundary.py` 1,285,
  `_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
  and `_lowering_completion_gap_inventory.py` 564.
- M97 does not infer semantic body completion, backend readiness, renderer
  readiness, dependency closure, operation scheduling, backend support,
  backend value resolution, or output readiness.
- M97 does not add backend translation, backend map/catalog reads,
  backend-uninit resolution, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, renderer-ready IR,
  rendering, generated output, source repair, raw body parsing, registries,
  dispatchers, hidden backfeeds, fixpoint machinery, Rust, CLI/report/writer,
  compiler execution, or hardwiring.
- M97 execution follow-up: `boundary.py` stayed under the guardrail partly by
  compressing stage-helper coordination. The next lowering slice should
  extract coordination/stage helper ownership before adding more state there.
- M98 is accepted as behavior-preserving Stage 8 stage-assembly ownership
  extraction only. It extracts accepted `GenerationLoweringStage` construction
  helpers and accepted per-candidate operation-package ->
  completion-manifest -> completion-gap-inventory result assembly into focused
  private `_lowering_stage_assembly.py` ownership.
- M98 keeps `boundary.py` as the public facade and request/result model owner.
  `LoweringRequest`, `LoweredImplementation`, `LoweringPlan`, public imports,
  accepted diagnostics, stage names, stage order, stage keys, output
  identities, deterministic ordering, selected-branch-only diagnostics, and
  object identity behavior must remain stable.
- M98 must not modify `_operation_package_sources.py` or route more
  coordination through it.
- M98 must not add new lowering semantics, new operation-package families,
  source-body parsing, source repair, backend translation, backend map/catalog
  reads, backend-uninit resolution, Stage 9 backend planning, operation
  scheduling, dependency closure, renderer-ready IR, rendering, generated
  output, Rust, CLI/report/writer behavior, compiler execution, registries,
  dispatchers, callback maps, hidden backfeeds, fixpoint machinery, or
  hardwiring.
- M98 line-count expectations: `boundary.py <= 1285`,
  `_operation_package_sources.py <= 819`, and the new stage-assembly module
  below the module-size guardrail.
- M99 is accepted as Stage 8 backend-translation request inventory/provenance
  work only. For M99, "backend-translation request inventory" means typed
  inventory of already accepted deferred/backend-scoped request facts; it does
  not translate, resolve, evaluate, plan, schedule, or render those facts.
- M99 consumes only accepted typed Stage 8 facts from M93-M98 operation
  packages, manifests, gap inventories, stage assembly, and their preserved
  object references. It must not parse raw `.tsl` source text, repair source
  bodies, normalize source bodies, infer package-family requests, or treat
  source locations, backend ids, extension ids, type tags, primitive names,
  selected literals, `svptrue_b*`, `pg`, or direct-intrinsic token text as
  semantic dispatch keys.
- M99 does not add backend map/catalog/lang reads, backend manifest reads,
  `tsldata/detail/lang` reads, backend-uninit resolution, generic
  `value<backend>(...)` / `type<backend>(...)` evaluation, Stage 9 planning,
  backend support decisions, operation scheduling, dependency solving,
  dependency closure, operation DAGs, wrapper planning, artifact planning,
  renderer-ready IR, rendering, generated output, generated tests, Rust,
  CLI/report/writer behavior, compiler execution, host hardware dependency,
  registries, dispatchers, callback maps, plugin systems, hidden backfeeds,
  fixpoint machinery, or hardwiring.
- `docs/redesign/missing-lowering-inventory.md` is a documentation-only
  inventory of known missing lowering work. It is not runtime input, a
  generated artifact, a source scanner, a dependency-closure plan, or a
  completeness oracle.
- M100 is a narrow typed translation-result boundary for accepted M99
  exact-array `exact_array_backend_value_uninit_array` records only.
- M100 may consume explicit typed C++ translation rule/metadata values
  supplied to the stage, but must not read `tsldata/detail/lang`, backend
  maps, catalogs, or manifests during lowering.
- M100 produces typed backend translation-result state only. It must
  not produce declaration/body IR, renderer-ready IR, render C++ or Rust code,
  create artifact plans, write output, start Stage 9 backend planning, schedule
  operations, solve dependencies, or perform dependency closure.
- M100 must reject or defer non-exact-array request records, including
  `selected_body_direct_intrinsic_handoff`, and must not infer
  direct-intrinsic/SVE semantics.
- Rust `value_array_uninit` translation remains deferred until the required
  typed type context and rules are accepted.
- M101 is a behavior-preserving lowering IR taxonomy and provenance
  consolidation slice over the accepted M99/M100 backend-translation
  request/result path only.
- M101 must distinguish semantic facts, requests, results, inventories,
  provenance values, rule inputs, and stage envelopes, and must not create a
  broad inheritance hierarchy, registry, dispatcher, callback system, hidden
  backfeed, fixpoint mechanism, backend-planning surface, rendering/output
  path, source-repair path, or new lowering semantics.
- M102 is accepted as a behavior-preserving lowering IR category protocol
  surface over the accepted M101 taxonomy and M99/M100 backend-translation
  request/result path only.
- M102 must keep the existing public `LoweringRequest` lowering-input bundle
  distinct from taxonomy-level request IR such as `LoweringRequestIr` or
  `TranslationRequestIr`.
- M102 structural conformance requires typed lowering IR contracts plus
  non-empty tuple keys, exact backend-translation owner namespace matching,
  and explicit `stage_envelope` contracts for stage-output recognition.
- M102 must not add new lowering semantics, new request/result families,
  backend translation semantics, rendering, generated output, Stage 9 planning,
  Rust translation, generic backend helper evaluation, backend map/catalog/
  manifest reads during lowering, raw source parsing, source repair,
  selected-body direct-intrinsic resolution, SVE semantics, scheduling,
  dependency closure, broad inheritance, registry, dispatcher, callback system,
  plugin mechanism, hidden backfeed, or fixpoint mechanism.
- M103 is accepted as a Stage 8 backend-translation boundary worklist inventory
  slice. "Worklist" means a static typed inventory/provenance view over
  accepted concrete M99/M100 facts, not an executable queue, scheduler,
  readiness oracle, dependency-closure plan, Stage 9 backend plan,
  renderer-ready IR, completeness oracle, source scanner, backend-map
  evaluator, registry, dispatcher, hidden backfeed, or fixpoint mechanism.
- M103 consumes only accepted concrete M99
  `Stage8BackendTranslationRequestInventoryIr` values and optional accepted
  concrete M100 `ExactArrayBackendUninitTranslationResultIr` values. It must
  preserve object identity to accepted request/no-request/result/deferred
  records and reject arbitrary fake objects that merely satisfy M102
  protocols.
- M103 keeps ownership in focused private modules, avoids `boundary.py`,
  `LoweredImplementation`, public facade, `_lower_input`, M99/M100 module, and
  `_lowering_ir_contracts.py` growth, and must not call translation lowerers
  to complete missing work.
- M103 did not add new `GenerationLoweringStageName` values or
  `_stage_contracts.py` integration, and any worklist-specific contract
  constants stay in the new focused module rather than
  `_lowering_ir_contracts.py`.
- M104 is accepted as a worklist-driven backend translation result expansion
  slice. The broadening is accepted only as one documented lowering gap:
  translating M103 worklist entries into typed resolved/deferred/unsupported
  translation expansion result records.
- M104 consumes only accepted concrete M103
  `Stage8BackendBoundaryWorklistInventoryIr` values and only the
  `exact_array_backend_uninit_unresolved` and
  `selected_body_direct_intrinsic_deferred` classifications. M103
  classifications may filter entries, but semantic behavior must come from
  concrete typed request/result objects plus explicit typed rule inputs.
- M104 does not dispatch by `svptrue_b*`, extension id, type tag, byte size,
  primitive name, raw direct-intrinsic token text, hardware-looking tokens, or
  source-location strings.
- M104 does not add backend-map/catalog/manifest reads during lowering,
  rendering, renderer-ready IR, generated output, Stage 9 backend planning,
  Rust rendering, source repair, raw source reparsing, operation scheduling,
  dependency closure, queues, scheduler/readiness behavior, registries,
  dispatchers, callbacks, plugins, hidden backfeeds, fixpoint machinery, or
  category-based semantic dispatch.
- M104 keeps ownership in new focused private result-expansion modules and
  avoids growth in `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules,
  and M103 worklist modules.
- M105 is documentation/architecture work only. It created
  `docs/redesign/kiss-generator-restart.md` and must not implement product
  code, tests, parser changes, generator changes, rendering, artifact writing,
  CLI behavior, or generated output.
- M105 treats accepted M57-M104 lowering/request/result/worklist artifacts as
  evidence for requirements and regression risks, not as the architecture to
  keep extending by default.
- The pre-restart top-level `tslgen/` tree has moved wholesale to
  `tslgenold/` as quarantined old-state evidence, and the new clean
  implementation owns the top-level `tslgen/` path.
- M106 completed the structural layout reset. Future restart product-code
  slices must keep `tslgenold/` and `frozen/` evidence-only.
- The restart product path is `.tsl` source data to validated catalog to
  selected implementations to deterministic C++ and Rust library artifacts.
- Restart milestones should prefer small object-oriented concepts with clear
  ownership and must not add new IR categories, request/result families,
  inventories, worklists, provenance wrappers, registries, dispatchers,
  hidden backfeeds, or fixpoint machinery unless at least two concrete
  accepted stages need the concept.
- Future lowering package decomposition must preserve accepted M57-M99
  diagnostics, stage names, stage ordering, output identities, keys,
  deterministic ordering, selected-branch-only diagnostics, public imports, and
  no-external-input boundaries.
- Future lowering package decomposition must not add new lowering semantics,
  generic body/call/store/return/declaration/array semantics, broad TSIL
  parsing, raw helper dispatch, backend translation, rendering, generated
  output, CLI/report/writer behavior, Rust, compiler execution,
  lowering-time file/catalog reads, `tsldata` reads, host CPU queries, backend
  map reads, runtime `frozen/` use, broad registries, runtime plugins, semantic
  dispatchers, hidden backfeeds, or fixpoint execution.

## Accepted Milestone 48

The Milestone 48 execution-review loop accepted:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

The slice remains generation-time semantic lowering only. It evaluates the
exact
`if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
plus `else<generation>` form over typed M43 `base.in` values. It does not
combine branch pruning with backend modifier translation, output rendering,
plain `else` conversion syntax, or broad shift/conversion body lowering.

## Accepted Milestone 49

The Milestone 49 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 49: Generated C++ Add I32 Test Source Parity Slice
```

The slice renders exactly one deterministic C++ `production_tests` artifact for
`add_i32_basic` at logical path `tests/add_i32_basic_test.cpp`. It consumes
typed `TestSourcePlan` / `PlannedTestCase` data plus explicit typed C++
type-spelling input for `si32 -> int32_t`; the renderer does not infer type
spellings, rescan raw TSL text, read or execute legacy templates, compile or run
generated tests, fetch or require `gtest`, or broaden generated-test parity.

## Accepted Milestone 50

The Milestone 50 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 50: Legacy Coverage JSON Adapter Row Slice
```

The slice renders exactly one deterministic legacy-style coverage JSON adapter
row for `add` / `avx2` / `cpp` / `f32`. It consumes typed
`PipelineCoverageReport` / `PrimitiveCoverageRow` data plus a selected typed
adapter request, produces a typed `LegacyCoverageSelectedRowFact`, and emits
legacy string-valued booleans only at the JSON serialization boundary. It
rejects aggregate primitive rows that would infer a selected row by cross
product and rejects unsupported direct row-fact serialization.

M50 remains reporting-adapter work only. It does not implement whole
`primitive_coverage.json` parity, row-count parity, broad coverage matrix
parity, HTML/site parity, CLI/report writing, backend rendering,
generation-time lowering, backend translation, generated C++ implementation
output, test-source rendering, Rust output, compiler execution, generated-test
execution, or runtime reads from `frozen/`, raw legacy JSON, or raw TSL.

## Accepted Milestone 51

The Milestone 51 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice
```

The slice is generation-time semantic lowering only. It extends the accepted
M48 signedness predicate branch pruning behavior to the documented plain
`else` form for the exact M48 predicate over typed M43 `base.in` values.
`PrunedGenerationBranch` records the accepted else syntax, and existing
`else<generation>` signedness branch behavior remains supported. Backend
translation, rendering, output generation, CLI/report/writer behavior, Rust,
compiler execution, generated-test execution, conversion body lowering, and
broader TSIL/plain-`else` support remain out of scope.

## Accepted Milestone 52

The Milestone 52 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 52: Concrete Integer Generation Type Semantics Slice
```

The slice is generation-time semantic lowering only. It extends the accepted
M43/M48/M51 concrete integer type and signedness semantics from `si32`/`ui32`
to `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64` for the
existing exact M43 type query forms and the existing exact M48/M51 signedness
predicate branch forms. Signed/unsigned companion behavior is expressed through
typed concrete-integer rules. Wildcard/group selectors remain unsupported as
selected concrete type tags. Backend suffix/type-spelling translation remains
limited to accepted M45/M46 `si32`/`ui32` behavior, and M52 adds no rendering,
generated output, generated test sources, CLI/reporting, writer behavior, Rust,
compiler execution, vector/register metadata, branch-body semantics, or broad
TSIL parsing.

## Accepted Milestone 53

The Milestone 53 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 53: Catalog-Validated Concrete Integer Generation Rule Source Slice
```

The slice is a semantic rule-source boundary only. It moves the accepted M52
concrete integer generation type/signedness semantics from a lowering-private
table into typed `ConcreteIntegerGenerationRuleSet` / rule values in the domain
layer, consumed by lowering through `GenerationContext`. It preserves M52
`GenerationTypeRef` outputs, signedness branch pruning, diagnostics,
deterministic ordering, branch provenance, and selected-branch-only diagnostics
for `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
Wildcard/group selectors and concrete-looking unselected tags remain
unsupported. M53 adds no new generation-time helper forms, backend translation
expansion, rendering, generated output, generated test sources, CLI/reporting,
writer behavior, Rust, compiler execution, broad TSIL parsing, or runtime
dependency on `frozen/`.

## Accepted Milestone 54

The Milestone 54 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice
```

The slice wires the accepted M53
`ConcreteIntegerGenerationRuleSet` through a normal catalog/lowering-input path
for pipeline-facing use. It exposes catalog-derived rule construction from
typed `Catalog.type_groups` and builds `LoweringRequest` values carrying those
immutable rules before lowering evaluation. It preserves M52/M53 type-query and
signedness-branch behavior, diagnostics, deterministic ordering, branch
provenance, selected-branch-only diagnostics, backend raw-helper rejection, and
renderer non-evaluation. M54 adds no new helper forms, backend translation
expansion, rendering, generated output, CLI/reporting/writer behavior, Rust,
compiler execution, broad TSIL parsing, or runtime dependency on `frozen/`.

## Accepted Milestone 55

The Milestone 55 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice
```

The slice is generation-time semantic lowering only. It resolves exactly
`value<generation>(type::size_bytes(type<generation>(base::in)))` to typed
`GenerationValue(kind="type.size_bytes", value=<bytes>, type_tag=<tag>)`
values for selected scalar tags `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`,
`si64`, `ui64`, `f32`, and `f64`. The accepted byte values are
`si8`/`ui8 -> 1`, `si16`/`ui16 -> 2`, `si32`/`ui32`/`f32 -> 4`, and
`si64`/`ui64`/`f64 -> 8`.

M55 uses explicit scalar size-byte rule/value records derived from typed
catalog/type-group data before lowering evaluation. It preserves standalone
`type<generation>(base::in)` and signed/unsigned companion behavior as
integer-only; `f32` and `f64` are accepted only for the exact size-bytes value
query. The focused revision tightened exact-query parsing so
`value<generation>(type::size_bytes(type<generation>(base::in),))` is rejected
with a stable arity diagnostic. M55 adds no generation-value arithmetic or
comparisons, branch pruning from size values, enclosing body lowering, backend
translation expansion, rendering, generated output, generated test sources,
CLI/reporting/writer behavior, Rust, compiler execution, generated-test
execution, broad TSIL parsing, or runtime dependency on `frozen/`.

## Accepted Milestone 56

The Milestone 56 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice
```

The slice is generation-time semantic lowering only. It resolves exactly
`value<generation>(type::size_bytes(type<generation>(base::in))) * 8` to typed
`GenerationValue(kind="type.size_bits", value=<bits>, type_tag=<tag>)` values
by reusing the accepted M55 `type.size_bytes` value and explicit scalar
size-byte rules. The accepted bit values are `si8`/`ui8 -> 8`,
`si16`/`ui16 -> 16`, `si32`/`ui32`/`f32 -> 32`, and
`si64`/`ui64`/`f64 -> 64`.

M56 preserves M55 context precedence and the M52-M55 generation-time lowering
boundaries. It adds no general arithmetic engine, operators beyond the exact
selected `* 8` form, reversed operands, arbitrary literals, comparisons,
branch pruning, `else if<generation>`, branch-chain syntax, surrounding body
lowering, backend translation, rendering, generated output, generated test
sources, CLI/reporting/writer behavior, Rust, compiler execution,
generated-test execution, vector/register metadata, broad TSIL parsing, or
runtime dependency on `frozen/`.

## Accepted Milestone 57

The Milestone 57 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice
```

The slice is generation-time semantic lowering only. It resolves exactly the
M57 size-byte equality predicates:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) == 2
value<generation>(type::size_bytes(type<generation>(base::in))) == 4
value<generation>(type::size_bytes(type<generation>(base::in))) == 8
```

M57 produces typed boolean
`GenerationPredicate(kind="type.size_bytes.equals", literal=<int>,
value=<bool>, type_tag=<tag>)` values by reusing the accepted M55
`GenerationValue(kind="type.size_bytes")` path and explicit scalar size-byte
rules. The accepted truth table is `si8`/`ui8 -> false for all selected
predicates`, `si16`/`ui16 -> true only for == 2`,
`si32`/`ui32`/`f32 -> true only for == 4`, and
`si64`/`ui64`/`f64 -> true only for == 8`.

M57 preserves M55/M56 context precedence and M52-M56 boundaries. It adds no
branch pruning, `if<generation>` parsing, `else if<generation>`, branch-chain
syntax, selected-arm/no-match provenance, general comparison parser, standalone
comparison forms outside the exact selected predicates, backend translation,
rendering, generated output, generated test sources, CLI/reporting/writer
behavior, Rust, compiler execution, broad TSIL parsing, or runtime dependency
on `frozen/`.

## Accepted Milestone 58

The Milestone 58 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice
```

The slice is generation-time semantic lowering stage-boundary work only. It
adds an explicit typed staged contract for accepted lowering outputs:
helper/expression recognition, typed generation values, typed generation
predicates, generation control-flow pruning, and selected-body lowering.

M58 exposes this contract through typed stage records on lowered
implementations while preserving the accepted observable fields for M55
`GenerationValue(kind="type.size_bytes")`, M56
`GenerationValue(kind="type.size_bits")`, M57
`GenerationPredicate(kind="type.size_bytes.equals")`, and M42/M48/M51 branch
pruning. M59 branch-chain pruning consumes typed predicate/stage results
without backend/rendering changes or raw helper re-evaluation.

M58 adds no new generation-time helper semantics, arithmetic/comparison
semantics, size-byte branch-chain pruning, `else if<generation>` support,
no-match provenance, selected branch body handoff, direct `intrin<...>` / SVE
body lowering, vector/register metadata, backend translation expansion,
rendering, generated output, generated test sources, CLI/reporting/writer
behavior, Rust, compiler execution, broad TSIL parsing, or runtime dependency
on `frozen/`.

## Accepted Milestone 59

The Milestone 59 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice
```

The slice is generation-time semantic lowering control-flow pruning only. It
recognizes exactly the documented SVE size-byte no-final-else branch chain in
`tsldata/primitives/load_store/array.tsl:107-109`, with ordered `== 2`,
`== 4`, and `== 8` arms.

M59 consumes the accepted staged M57 predicate results through typed
`GenerationValue(kind="type.size_bytes")`,
`GenerationPredicate(kind="type.size_bytes.equals")`, and
`GenerationLoweringStage` records instead of adding backend/rendering helper
evaluation or a broad raw-text branch-chain evaluator. Byte sizes `2`, `4`,
and `8` record selected-arm pruning provenance; byte size `1` records explicit
no-match provenance without synthesizing a final `else`.

Branch bodies remain opaque pruning metadata. M59 emits no selected-body
lowering stage for the branch-chain path and does not add M60 selected-body
handoff, direct `intrin<...>` / SVE body lowering, broad `else if<generation>`
syntax, final `else`, reordered/missing/duplicate/nested chain support,
standalone comparison evaluation, backend translation, rendering, output,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
or runtime dependency on `frozen/`.

## Accepted Milestone 60

The Milestone 60 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 60: Opaque Selected Branch Body Handoff Slice
```

The slice is generation-time semantic lowering only. It consumes typed M59
`GenerationSizeByteBranchChainPruning` / `generation_control_flow_pruning`
stage output and creates distinct typed opaque selected-body handoff records.

For byte sizes `2`, `4`, and `8`, M60 preserves candidate id, selected type
tag, selected literal, opaque body text, source/provenance, and originating
branch-chain identity. For byte size `1`, M60 records an explicit no-match
handoff and does not synthesize a selected body.

M60 keeps branch bodies opaque. It does not parse or lower selected or
unselected branch-body semantics, does not invoke mini TSIL lowering for the
branch-chain path, and does not produce direct-intrinsic/SVE `TsilStatement`
values. It preserves backend raw-helper rejection and renderer
non-evaluation, and adds no backend translation, rendering, output,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
runtime dependency on `frozen/`, lowering-time file reads, raw TSL parsing, or
catalog queries during evaluation.

## Accepted Milestone 61

The Milestone 61 execution-review loop accepted with non-blocking follow-ups
after one focused revision:

```text
Milestone 61: Selected Branch Body Assignment Form Recognition Slice
```

The slice is generation-time lowering form-recognition work only. It consumes
typed M60 `OpaqueSelectedBranchBodyHandoff` and
`NoSelectedBranchBodyHandoff` values and exposes selected-body assignment-form
metadata through a distinct `selected_body_form_recognition` stage.

For the selected `== 2`, `== 4`, and `== 8` branch bodies, M61 recognizes only
the exact `pg = intrin<svptrue_b16/b32/b64>();` single-statement assignment
forms and preserves candidate id, selected type tag, selected literal,
originating branch-chain identity, original opaque body text, statement
provenance, assignment target text, opaque RHS text, and direct-intrinsic token
text as form metadata. For byte-size `1` no-match cases, it records an
explicit no-selected-body/no-form result.

M61 does not lower assignment semantics, validate direct intrinsics, infer SVE
predicate meaning, map byte-size literals to intrinsic suffixes, inspect
unselected branch bodies, or synthesize a body/form for `si8`/`ui8` no-match
cases. It adds no backend translation, rendering, output, generated tests,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
runtime dependency on `frozen/`, lowering-time file reads, raw TSL parsing, or
catalog queries during evaluation.

## Accepted Milestone 62

The Milestone 62 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice
```

M62 consumes only typed M61 `selected_body_form_recognition` outputs and
produces unresolved backend-neutral selected-body IR for the exact selected
assignment/direct-intrinsic form. It preserves M61 target/token/text,
explicit empty argument list, and provenance fields as typed IR facts. It
keeps byte-size `1` no-match cases as explicit no-body-IR results and adds the
distinct `selected_body_ir_lowering` stage.

M62 does not validate SVE/backend intrinsic meaning, infer
byte-size-to-intrinsic mappings, create backend translation requests, feed
renderers, emit generated output, or parse broad TSIL body syntax.

## Known Follow-Ups

- Older post-M34 wording around "do not define M35 yet" may be cleaned up
  later. This is non-blocking for current planning.
- M105 execution follow-up addressed by documentation execution: the KISS
  restart charter was created as documentation/architecture work only, and no
  product code was added.
- M105 execution follow-up addressed by M106: old `tslgen/` state was moved to
  `tslgenold/` before clean product code starts under fresh `tslgen/`.
- M106 follow-up addressed by M107: M107 established its own targeted
  clean-package validation surface under fresh `tslgen/`; the old `tslgenold`
  validation profile remains evidence and must not be used as proof of the new
  product path.
- M108 documentation audit follow-up: if exported lowerer guard diagnostics
  become public contract, document the additional `TSL-LOWER-UNSUPPORTED-*`
  codes beyond `TSL-LOWER-UNSUPPORTED-BODY`.
- M109 documentation follow-up: reconcile the older general "Artifact Writing
  Behavior" section in `docs/redesign/behavioral-spec.md`, which still
  describes dry-run/skip/failed statuses and `TSL-ARTIFACT-WRITE-*` codes, with
  the clean restart M109 writer contract or mark that older behavior as
  deferred/future.
- M110 documentation follow-up: consider adding the exact backend spelling
  table for the M110 supported scalar tags to `docs/redesign/behavioral-spec.md`
  for discoverability.
- M110 documentation follow-up: consider adding a small cross-reference from
  the historical M107/M108 `si32` sections to the M110 scalar-type broadening
  so quick readers do not confuse historical baseline text with the current
  accepted surface.
- M106 architecture follow-up: before any release/stabilization work resumes,
  retire or rewrite `docs/redesign/stabilization-release-checklist.md` for the
  post-M106 clean restart; it still reads like the old `tslgen` package is an
  active release candidate and references `PYTHONPATH=tslgen/src`.
- M105 execution follow-up addressed by documentation execution: accepted
  M57-M104 tests are regression evidence for diagnostics, determinism,
  source-body integrity, and semantic-boundary risks, not constraints on the
  restart internals.
- M105 review follow-up: before the first clean product-code slice, reconcile
  older target-architecture references to `backends/registry.py` and
  "register manifest/capabilities" with the M105 no-registry-default charter.
- M105 review follow-up: when drafting the first clean product-code slice, keep
  backend selection as explicit configuration/simple ownership rather than a
  revived renderer registry or dispatcher.
- The retried evidence audit confirmed additional exact shift evidence ranges:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is selected M51
  branch-shape evidence only because it uses the M48 signedness predicate with
  plain `else`. Its enclosing `switch<compile>` and branch bodies remain
  out-of-scope conversion evidence.
- M49 review follow-up: harden the no-file-read regression so it also catches
  `pathlib.Path.read_text()` style reads; source inspection found the renderer
  pure/in-memory, so this is non-blocking.
- M49 review follow-up: consider deduplicating descriptor diagnostics for
  malformed descriptor cardinality in C++ test-source rendering.
- M49 docs follow-up: consider syncing `testing-strategy.md` with the full M49
  diagnostic list, including wrong selected-case cardinality and unsupported
  legacy-test features.
- M49 docs follow-up: clarify behavioral-spec wording that slightly conflates
  rendered artifact logical path with committed golden fixture path.
- M49 evidence follow-up: consider extending the `test_common.j2` evidence
  range if a future doc wants to claim the full macro closing shape.
- M50 review follow-up: harden the no-file-read regression so it wraps the full
  `selected_legacy_coverage_row_to_json(...)` adapter path, not only direct
  row-fact serialization. Source inspection and focused boundary review found
  the adapter pure/in-memory, so this is non-blocking.
- M50 evidence follow-up: consider adding an explicit active source/report data
  note to `add_avx2_f32_coverage_row.provenance.md`. Existing selected legacy
  row, field-construction evidence, and redesign baseline citations were
  accepted for M50.
- M51 review follow-up: consider gating plain `else` earlier in the lowering
  parser for an even tighter boundary. Current behavior accepts plain `else`
  only after the condition resolves to the supported typed signedness predicate
  and rejects primitive-attribute or arbitrary plain-`else` forms, so this is
  non-blocking.
- M52 planning follow-up: the active M52 execution prompt explicitly preserves
  M45/M46 `si32`/`ui32` backend translation limits while M52 expands only
  generation-time lowering semantics.
- M52 review follow-up: consider adding location assertions for the new and
  expanded M52 diagnostic cases; current tests assert code/severity/message but
  mostly not path, line, and column.
- M53 planning follow-up: addressed in
  `docs/agent/runs/m53-execution-review-loop-prompt.md`, which explicitly
  repeats the broad TSIL parsing prohibition while moving only concrete integer
  rule-source ownership.
- M53 review follow-up addressed by M54: catalog-derived concrete integer
  generation rules are now wired through a normal catalog/lowering-input path,
  with focused tests proving lowering consumes explicit catalog-built rules
  instead of hiding bad explicit rule data behind the synthetic default.
- M53 review follow-up: consider enforcing the exact selected-tag and
  companion-pair invariants in `ConcreteIntegerGenerationRuleSet` construction
  or making validated construction the only supported path.
- M53 review follow-up: add available source locations to
  `TSL-DOMAIN-GEN-RULE-*` diagnostics when `TypeGroup` source spans are
  available, especially unsupported selected-tag diagnostics.
- M53 docs/evidence follow-up: sync broader redesign docs from selected-plan
  wording to accepted/implemented M53 wording, and consider widening
  unsupported group-selector evidence beyond `tsldata/detail/types.tsl:20-24`
  if `dword` and `qword` remain part of known unsupported group classification.
- Repo-wide evidence follow-up: `tslgen/tests/unit/test_backend_artifact_model.py`
  still reads representative legacy backend manifest YAML from `frozen/` at
  unit-test runtime. This predates M52 and M52 lowering code has no `frozen/`
  runtime dependency, but a future cleanup may replace those reads with
  redesign-owned fixtures if the strict no-`frozen/` test-runtime policy is
  applied broadly.
- M54 review follow-up: add explicit negative test subcases for `dword` and
  `qword` selected tags. The implementation already classifies them as
  unsupported group selectors; the extra tests would tighten traceability to
  `tsldata/detail/types.tsl:25-26`.
- M55 review follow-up: consider tightening the shared generation-call
  argument splitter so earlier helper families also reject empty/trailing
  arguments consistently. M55 fixed the selected value-query path with a strict
  parser and regression test.
- M55 evidence follow-up: the already-used M55 execution prompt's IO evidence
  citation can be tightened later to name `tsldata/primitives/io/out.tsl:22`
  for the float test; the roadmap citation has been corrected.
- Post-M55 planning follow-up: exact size-byte equality branch pruning over
  `== 2`, `== 4`, and `== 8` remains a strong future lowering candidate, but
  it is deferred from M56 because it also opens `else if<generation>` branch
  chain syntax and selected-branch pruning policy.
- M56 docs/evidence follow-up: normalize remaining pre-acceptance wording in
  `docs/redesign/implementation-roadmap.md`,
  `docs/redesign/behavioral-spec.md`,
  `docs/redesign/frozen-parity-baselines.md`, and related
  `docs/redesign/open-questions.md` M56 mentions.
- M56 docs follow-up: add or update the helper inventory entry for the exact
  M56 `type.size_bytes * 8` bit-width expression.
- M56 review follow-up: consider tightening the arithmetic probe so a
  non-arithmetic value query with an unmatched closing parenthesis keeps M55
  malformed-query diagnostics separate from M56 arithmetic diagnostics.
- M56 test follow-up: add an explicit chained/mixed arithmetic rejection case,
  such as a `* 8 * 2` expression after the selected size-bytes value query.
- Post-M56 planning revision follow-up: branch-chain pruning over the selected
  size-byte equality predicates remains a strong future lowering candidate now
  that M57 predicate lowering is accepted.
- Post-M56 staged-lowering planning note: the intended value -> predicate ->
  control-flow -> selected-body lowering path remains the guiding sequence.
  M58 accepted the stage-boundary contract, M59 accepted exact branch-chain
  pruning, M60 accepted opaque selected-body handoff, and post-M60 planning is
  accepted for M61 assignment-form recognition.
- M57 review follow-up: keep the private top-level generation binary scanner
  narrow. It may recognize unsupported operators only to reject them and must
  not become a general comparison parser without a selected milestone.
- M57 evidence/test follow-up: add explicit unsupported-tag predicate coverage
  for `bword` and `fdqword`, matching the cited group evidence in
  `tsldata/detail/types.tsl:20-26`.
- M58 boundary follow-up addressed by M59: exact size-byte branch-chain pruning
  consumes typed `GenerationValue` / `GenerationPredicate` stage outputs, not
  raw `GenerationExpressionRecognition.source_text` provenance.
- M58 boundary follow-up: future opaque selected-body handoff should introduce
  its own typed body record rather than stretching the current
  `selected_body_lowering` stage beyond its accepted `TsilReturnStatement`
  output.
- M58 extensibility follow-up addressed by M59: branch-chain pruning reuses the
  typed staged predicate resolver and keeps the cleanup subordinate to the
  exact chain-pruning slice.
- Post-M58 planning follow-up addressed by M59: the execution prompt and
  implementation kept staged-predicate reuse subordinate to the exact
  branch-chain pruning slice.
- M59 review follow-up: consider adding one more unsupported-shape test for a
  non-size-byte `else if<generation>` chain.
- M59 boundary follow-up: consider adding an explicit nested branch-chain
  rejection test.
- M59 extensibility follow-up addressed by M60: the accepted M60
  implementation introduced distinct typed selected body handoff records
  instead of expanding
  `GenerationSizeByteBranchChainPruning.selected_statement_text` into a body
  handoff contract.
- M59 extensibility follow-up: consider a small naming or comment cleanup
  clarifying that `_parse_generation_size_byte_branch_chain` recognizes only
  chain shape while predicate semantics remain delegated to the staged
  predicate resolver.
- M59 evidence follow-up: consider adding a fixture comment clarifying that the
  unit-test `scalar: arith` harness exercises the exact chain shape and typed
  M55/M57 behavior, not scalar corpus evidence; corpus evidence remains the
  SVE chain in `tsldata/primitives/load_store/array.tsl:107-109`.
- M59 focused docs follow-up: the fixed lowering document preserves selected
  body handoff and no-runtime-`frozen/` deferrals in substance; a future docs
  cleanup may add the exact labels `M60` and `runtime frozen behavior` to that
  focused section if desired.
- Post-M59 planning follow-up: M60 handoff diagnostics must stay
  boundary-level, such as missing selected body/provenance or unsupported
  source stage, and must not classify direct intrinsics, assignments, arrays,
  calls, casts, loops, vector metadata, backend uninit, or SVE predicates.
- Post-M59 planning follow-up: the M60 executor must introduce a distinct typed
  opaque selected-body handoff value instead of expanding M59 pruning metadata
  into the reusable body-handoff contract.
- M60 validation follow-up: consider direct unit assertions for
  `TSL-LOWER-HANDOFF-BODY-MISSING` and
  `TSL-LOWER-HANDOFF-CANDIDATE-MISSING`. Existing M60 tests cover unsupported
  source-stage and missing-provenance diagnostics.
- M60 validation follow-up: one boundary audit observed a package-boundary
  build failure while running `python -m tslgen.tooling.validation`; the
  validation auditor and orchestrator reruns passed, so this is non-blocking
  unless it recurs.
- M60 extensibility follow-up: future body-lowering slices may want a clearer
  stage split or envelope because `selected_body_lowering` now carries both
  opaque handoff values and already-lowered `TsilReturnStatement` values.
- M60 extensibility follow-up: consider renaming
  `NoSelectedBranchBodyHandoff.selected_type_tag` to a less ambiguous
  `candidate_type_tag` or `evaluated_type_tag`.
- M60 extensibility follow-up: future control-flow forms should extend through
  typed source records rather than turning the M60 handoff helper into a broad
  dispatcher or raw-text evaluator.
- M60 evidence follow-up: add a short fixture comment clarifying that the
  `vector::length` body-helper fixture is synthetic opacity coverage, not
  corpus evidence for M60 body semantics.
- M60 docs follow-up addressed by post-M60 planning: update remaining
  pre-acceptance/status wording in
  `docs/redesign/implementation-roadmap.md`,
  `docs/redesign/target-architecture.md`,
  `docs/redesign/testing-strategy.md`, and
  `docs/redesign/design-decisions.md`.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/behavioral-spec.md` so the parity table includes
  M58/M59/M60 and narrows remaining gaps to broader branch-chain pruning
  beyond M59 and body handling beyond the M60 opaque handoff plus M61
  form-recognition slice.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/generation-time-semantic-lowering.md` and
  `docs/redesign/open-questions.md` so lowering and open-question summaries
  are current through M60 and M61 form recognition.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/frozen-parity-baselines.md` from selected opaque handoff
  candidate wording to accepted M60 opaque handoff wording while keeping
  broader body handling deferred beyond the M61 form-recognition slice.
- Post-M60 planning follow-up addressed by M61: M61 remained a single
  selected-body assignment-form recognition boundary and did not become direct
  intrinsic lowering, SVE predicate semantic lowering, assignment lowering,
  backend translation input, renderer-ready IR, or broad TSIL parsing.
- Post-M60 planning follow-up addressed by M61: the implementation introduced
  a distinct typed form-recognition value and `selected_body_form_recognition`
  stage rather than stretching `selected_body_lowering` into a mixed semantic
  dispatcher.
- M61 extensibility follow-up: future body-lowering slices may want an explicit
  typed unsupported selected-body-form result if they need to distinguish
  unsupported selected bodies from hard diagnostics.
- M61 extensibility follow-up: if later slices need exact statement spans,
  split `selected_statement_location` from the inherited M60 handoff/source
  provenance rather than overloading the same location.
- Post-M61 planning follow-up addressed by M62: the implementation keeps
  "Direct-Intrinsic" as unresolved backend-neutral selected-body IR, not
  backend intrinsic IR, SVE semantic validation, translation input,
  renderer-ready IR, or generated output.
- Post-M61 planning follow-up addressed by M62: the implementation introduced
  the distinct `selected_body_ir_lowering` body-IR stage/value instead of
  overloading M60 handoff or M61 form-recognition records.
- Post-M61 planning follow-up addressed by M62: the implementation includes a
  synthetic mismatch test between selected byte-size literal and
  direct-intrinsic token text to prove the slice preserves M61 typed facts
  instead of inferring a size-to-intrinsic mapping.
- M62 validation follow-up: consider asserting diagnostic location and message
  text for the unsupported M62 source/boundary diagnostic. The current test
  asserts diagnostic code and severity, and validation found this
  non-blocking.
- M64 boundary follow-up: a future skeleton-producing slice should clearly own
  the proof that an in-memory typed exact array-body skeleton corresponds to
  `tsldata/primitives/load_store/array.tsl:105-111`; M64 accepts typed
  skeleton input and does not broadly parse TSIL.
- M64 extensibility follow-up addressed by M65: `lower_candidates` now
  populates `array_body_envelopes` and appends the
  `array_body_envelope_slot_assembly` stage when matching typed/provenanced
  skeleton input is supplied.
- M64 extensibility follow-up: future slot-specific lowerers should consume the
  enclosing `ExactArrayBodyEnvelopeIr`, not standalone slots, and must keep
  `opaque_source_text` as provenance rather than a raw-text dispatcher.
- M64 validation follow-up: consider tightening message assertions for more
  invalid-skeleton diagnostics. The focused revision added direct duplicate
  `selected_body_envelope` slot message coverage.
- M64 evidence follow-up: consider adding a small fixture comment tying the
  inlined opaque array-body test snippets to
  `tsldata/primitives/load_store/array.tsl:105-111`.
- Post-M64 planning follow-up addressed by M65: the implementation makes the
  skeleton-required policy concrete. No-skeleton input preserves existing
  M63-only behavior unless a candidate is explicitly marked as requiring a
  skeleton.
- Post-M64 planning follow-up addressed by M65: the implementation adds
  explicit diagnostics and tests for missing required skeleton input,
  duplicate/conflicting skeletons, skeletons supplied for candidates without
  M63 envelopes, and skeleton/envelope provenance mismatches.
- M65 validation follow-up: add an explicit determinism test for integrated
  typed skeleton input ordering, such as reversed
  `array_body_envelope_skeletons` producing identical lowering output or
  diagnostics. Review found the implementation deterministic, but this direct
  test remains useful.
- Post-M65 planning follow-up addressed by M66: the implementation keeps the
  slice as exact array-initialization slot form IR, not semantic
  array/declaration lowering.
- Post-M65 planning follow-up addressed by M66: the implementation consumes
  typed M65 envelope/stage outputs only, and uses typed slot opaque text only
  for local exact-form recognition rather than raw payload scanning or
  raw-text dispatch.
- Post-M65 planning follow-up addressed by M66: the implementation keeps
  `type<generation>(base::in)`, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, and
  `value<backend>(uninit::array)` unresolved.
- M66 review follow-up addressed during the execution-review loop: remove the
  public caller-supplied slot override from
  `lower_exact_array_initialization_slot_form` so the public boundary always
  refines the selected M65 envelope's own slot `0`.
- M66 boundary follow-up addressed during the execution-review loop: remove an
  accidental untracked generated package artifact under
  `tslgen/tslgen-0.1.0a1`.
- M66 documentation follow-up addressed during the execution-review loop:
  align redesign docs so M66 is not described as deferred after
  implementation.
- Post-M66 planning follow-up for M67 execution: keep M67 as typed deferred
  helper-request/provenance IR only, not helper evaluation.
- Post-M66 planning follow-up for M67 execution: do not produce
  `GenerationTypeRef`, `GenerationValue`, backend translation requests,
  resolved vector metadata values, backend uninit values, renderer-ready IR,
  or generated output.
- Post-M66 planning follow-up for M67 execution: consume M66
  `ExactArrayInitializationSlotFormIr` / leaf records and do not reparse raw
  slot text or dispatch from raw helper strings.
- M67 review follow-up: consider tightening
  `ExactArrayInitializationHelperRequestRecord` model invariants so
  `request_kind` is validated against the expected leaf spec, not only
  produced correctly by the lowerer.
- M67 validation follow-up: strengthen bad-leaf diagnostic tests to assert
  exact path, line, column, and actionable message text for missing,
  duplicate, mismatched, and unsupported helper leaf diagnostics.
- M67 documentation revision follow-up addressed during the execution-review
  loop: document the typed `LoweredImplementation` source container and the
  new M67 diagnostic codes in the redesign docs.
- Post-M67 planning follow-up for M68 execution: M68 must be a typed
  request-resolution adapter over M67 IR, not a raw
  `type<generation>(...)` evaluator over M67 leaf text.
- Post-M67 acceptance condition for M68 execution: ensure no hardwiring.
  Resolution must not be implemented through ad-hoc tables or branches keyed
  by raw helper text, selected type tags, or request ordinals; it must use
  typed M67 request records plus accepted typed rule/context inputs.
- Post-M67 planning follow-up for M68 execution: keep vector length, vector
  alignment, backend uninit, declaration/array semantics, backend
  translation, rendering, and generated output out of scope.
- Post-M67 planning follow-up for M68 execution: do not use `Catalog`, file
  reads, `tsldata`, or `frozen/` during lowering evaluation; selected type
  context and rules must arrive through typed lowering request/context inputs.
- M68 execution addressed the post-M67 no-hardwiring and no-raw-helper
  follow-ups: review verified typed M67 request consumption, typed
  rule/context inputs, no raw M67 leaf-text evaluation, no backend/rendering
  expansion, and unresolved vector/backend requests preserved.
- M68 documentation revision follow-up addressed during the execution-review
  loop: document the new
  `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-*` diagnostic codes and inherited
  unsupported selected-type diagnostic path.
- M68 extensibility follow-up addressed by M69: the growing M64-M68
  `_lower_input` array-body stage assembly tail is now extracted into a
  private typed array-initialization stage pipeline helper/result.
- M68 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type `elif` table. Review found this is type
  validation rather than semantic dispatch, but it is a future maintainability
  pressure point as more stages are added.
- M68 extensibility follow-up: `_ExactArrayInitializationBaseTypeRequestRule`
  has an unused `result_kind`; remove it or let the typed rule drive the
  result-kind invariant before adding sibling vector/backend resolver rules.
- Post-M68 planning follow-up addressed by M69: execution stayed
  behavior-preserving and review verified identical public
  `LoweredImplementation` fields, stage names/order, typed outputs,
  diagnostics, deterministic behavior, no-skeleton/no-body behavior, and
  generated-output state.
- Post-M68 planning follow-up addressed by M69: the extraction did not become
  a broad stage registry, generic helper dispatcher, semantic resolver, vector
  metadata resolver, backend uninit resolver, declaration/array semantics
  slice, renderer path, or generated-output milestone.
- Post-M68 planning follow-up retained after M69: leave
  `GenerationLoweringStage.__post_init__` table cleanup and
  `_ExactArrayInitializationBaseTypeRequestRule.result_kind` cleanup as
  follow-ups for a later focused cleanup unless a purely mechanical touch is
  required by another selected slice.
- Post-M68 planning follow-up: after M69, revisit one vector metadata request
  slice from the extracted typed stage boundary rather than extending
  `_lower_input` directly.
- Post-M68 planning acceptance is superseded by accepted M69 execution.
- M69 review follow-up: consider adding an explicit pipeline-level M67
  diagnostic propagation test if a future slice touches the extracted
  array-initialization stage pipeline. Existing direct M67 helper-request
  diagnostic tests remain accepted coverage.
- Post-M69 planning follow-up for M70 execution: vector-length facts must be
  explicit typed metadata supplied before lowering evaluation. M70 must not
  infer lanes from raw helper text, SVE tokens, extension names, vector-bit
  strings, selected type tags, scalar sizes, host CPU state, catalog data,
  backend maps, renderer names, or raw `candidate_id` parsing.
- Post-M69 planning follow-up for M70 execution: preserve scalable/runtime-lane
  uncertainty as an explicit typed value/policy or diagnostics. Do not fake a
  fixed integer lane count for SVE/runtime-lane extensions.
- Post-M69 planning follow-up for M70 execution: keep vector alignment, backend
  uninit, declaration/array semantics, backend translation, rendering,
  generated output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, and runtime `frozen/` use out of scope.
- M70 execution follow-up: consider adding an explicit unit test that guards
  against catalog reads, `tsldata` reads, and host CPU queries during M70
  vector-length request resolution. Review found the implementation and
  broader validation clean; this is coverage hardening, not a blocker.
- M70 documentation follow-up addressed during the execution-review loop:
  update stale lowering-doc deferral wording so broad/generic vector-length
  semantics remain deferred while the exact M70 array-initialization
  vector-length request is carved out as resolved from explicit typed metadata.
- Post-M70 planning follow-up for M71 execution: vector-alignment facts must be
  explicit typed metadata supplied before lowering evaluation. M71 must not
  infer alignment from vector length, vector bits, scalar byte size, selected
  type tags, SVE token text, extension names, host CPU state, catalog data,
  `tsldata`, backend maps, backend vector-alignment spellings, renderer names,
  or raw `candidate_id` parsing.
- Post-M70 planning follow-up for M71 execution: preserve accepted M68
  base-type behavior, accepted M69 stage-pipeline behavior, accepted M70
  vector-length behavior, and keep backend uninit unresolved.
- Post-M70 planning follow-up for M71 execution: keep declaration/array
  semantics, aligned load/store semantics, `assume_aligned`, backend
  translation, rendering, generated output, generated tests, CLI/report/writer
  behavior, Rust, compiler execution, and runtime `frozen/` use out of scope.
- Post-M70 planning follow-up for M71 execution: include the M70 validation
  hardening follow-up by explicitly guarding against catalog reads, `tsldata`
  reads, and host CPU queries during request resolution.
- M71 execution addressed the post-M70 vector-alignment follow-ups: review
  verified explicit typed vector-alignment metadata, typed M67/M68/M69/M70
  request/result consumption, unchanged M68/M69/M70 behavior, unresolved
  backend uninit, and no backend/rendering/generated-output expansion.
- M71 documentation revision follow-up addressed during the execution-review
  loop: document the new
  `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-*` diagnostic codes and replace the
  stale roadmap handoff that still said post-M70 finalization was pending.
- M71 validation follow-up: consider adding a broader pipeline-level guard
  against catalog reads, `tsldata` reads, and host CPU queries. M71 includes
  direct resolver coverage and validation passed; this is hardening only.
- M71 extensibility follow-up: the exact array-initialization resolver pattern
  is becoming repetitive. If M72+ repeats the same provenance/request/metadata
  shape, consider a small private typed helper extraction rather than a broad
  registry or raw string dispatcher.
- M71 public-boundary follow-up: keep future `tslgen.lowering.__all__`
  additions limited to genuinely consumed typed boundary values as the
  exported lowering surface grows.
- M71 documentation follow-up: after M71 acceptance, sweep remaining
  pre-acceptance wording such as "selected" or "should" to
  accepted/implemented wording where appropriate in redesign docs.
- Post-M71 planning follow-up for M72 execution: M72 must complete the exact
  first-slot helper set as typed lowering state, not backend uninit
  translation. Backend uninit must remain a typed deferred backend-value
  request boundary with no backend text, translation request, renderer-ready
  value, or generated output.
- Post-M71 planning follow-up for M72 execution: M72 must not become
  declaration/array lowering. Keep broad `var`, `array_type`,
  allocation/lifetime, stores, returns, `tmp.data()`, and `emit_return` out of
  scope.
- Post-M71 planning follow-up for M72 execution: include relevant M69/M71
  hardening where practical, especially pipeline-level M67 diagnostic
  propagation coverage and no catalog/`tsldata`/host CPU/backend-map reads
  during M72 lowering evaluation.
- Post-M71 planning follow-up addressed during planning: stale M71
  pre-acceptance wording was updated across the redesign docs while preserving
  historical prior-planning context where appropriate.
- M72 execution addressed the post-M71 helper-set follow-ups: review verified
  typed M67/M68/M70/M71 request/result consumption, a typed deferred
  backend-uninit boundary, unchanged M68/M69/M70/M71 behavior, no backend
  translation/rendering/generated-output expansion, and no declaration/array
  semantics.
- M72 documentation revision follow-up addressed during the execution-review
  loop: stale M72 prospective wording was updated across redesign docs,
  including roadmap and parity-baseline handoff wording, while preserving the
  helper-set-only boundary.
- M72 review follow-up: the generic unsupported-source diagnostic for
  `lower_exact_array_initialization_helper_set_completion` omits the accepted
  `LoweredImplementation` source form from its final fallback wording. Review
  found this diagnostic wording issue non-blocking because the
  `LoweredImplementation` branch is implemented and tested.
- M72 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type validation table. It is not semantic
  dispatch, but the table is a growing maintainability pressure point before
  many more stages accumulate.
- Post-M72 planning follow-up for M73 execution: name and scope the slice as
  exact first-slot declaration-shell structural IR, not generic declaration or
  array semantics.
- Post-M72 planning follow-up for M73 execution: consume typed M72 helper-set
  completions and accepted first-slot provenance, with source text only as
  provenance/invariant evidence. Do not reparse raw slot/helper text as
  semantics.
- Post-M72 planning follow-up for M73 execution: keep backend uninit
  translation, backend maps, renderer-ready IR, generated output, generic
  `var`/`array_type` parsing, allocation/lifetime, initializer, variable
  scope, store, return, `tmp.data()`, `emit_return`, and direct-intrinsic/SVE
  semantics out of scope.
- Post-M72 planning follow-up for M73 execution: keep public IR additions
  narrow, preferably one genuinely consumed structural boundary value rather
  than a broad `VarIr`/`ArrayTypeIr` family or registry.
- M73 execution addressed the post-M72 planning follow-ups: review verified
  exact first-slot declaration-shell structural IR, typed M72 helper-set
  consumption, preserved first-slot provenance, source text used only as
  provenance/invariant evidence, deferred backend-uninit preservation, no
  backend translation/rendering/generated-output expansion, no generic
  declaration/array semantics, and one narrow consumed public IR addition.
- M73 documentation revision addressed the review blocker by recording the
  M73 diagnostic codes and updating stale planned/selected wording across the
  redesign docs while preserving the structural-only boundary.
- Post-M73 planning follow-up for M74 execution: role labels must remain
  structural/provenance labels only, not executable statement kinds or
  predicate/store/return/body semantics.
- Post-M73 planning follow-up for M74 execution: M74 must add at most one
  exact public structural-sequence IR value and one exact stage/output pairing;
  it must not add a generic body IR hierarchy, per-role public tuples,
  slot-role registry, broad stage registry, or semantic dispatcher.
- Post-M73 planning follow-up for M74 execution: derive roles from accepted
  typed M64/M65/M73 slot identity and provenance, not from raw text, line
  numbers, helper strings, SVE tokens, backend ids, renderer names, or catalog
  data.
- Post-M73 planning follow-up for M74 execution: preserve non-first slots as
  opaque/unresolved structural evidence and keep `tmp.data()`, `emit_return`,
  `assume_aligned`, store/return semantics, SVE/direct-intrinsic semantics,
  backend translation/rendering, and generated output out of scope.
- M74 execution addressed the post-M73 planning follow-ups: review verified
  exact structural/provenance-only role labels, one exact public structural
  sequence IR value with one exact stage/output pairing, typed M64/M65/M73
  source consumption, no raw text/helper/SVE/backend/catalog semantic
  dispatch, opaque non-first slot preservation, and no backend/rendering/
  generated-output expansion.
- M74 review follow-up: the public sequence currently carries a private
  `_ExactArrayBodyStructuralRole` tuple internally. Future consumers should
  keep that role detail internal or deliberately promote one exact role value;
  do not let it grow into per-role public tuples, a slot-role registry, broad
  body IR, or semantic dispatcher.
- M74 focused validation revision addressed the blocking diagnostic coverage
  gap by adding symmetric missing-envelope and duplicate-declaration-shell
  `LoweredImplementation` tests and preserving M73 shell source locations for
  missing-envelope diagnostics.
- Post-M74 planning follow-up for M75 execution: keep the selected slice as an
  exact predicate path structural/request IR only. Do not let it become SVE
  predicate semantics, byte-size-to-token inference, store-call lowering,
  variable scope, backend translation, renderer-ready IR, generated output, a
  slot-role registry, or broad body IR.
- M75 focused validation revision addressed the blocking coverage gaps by
  adding explicit malformed store-call shape coverage, nested M62
  `source_body_ir` provenance mismatch coverage, and a normal
  `lower_candidates` pipeline-level no-raw/no-external-state guard.
- M75 review follow-up: consider hardening
  `ExactPredicatePathStructuralRequestIr` constructor invariants so direct
  construction cannot represent non-exact predicate/update/store token facts
  that the resolver path rejects.
- M75 documentation follow-up: refresh the behavioral-spec TSIL semantic/
  lowering parity table to include M73, M74, and M75, and clean up
  post-acceptance planned/selected wording in the redesign docs.
- M75 validation follow-up: strengthen remaining M75 diagnostic tests with
  exact path, line, column, and actionable message assertions where practical.
- M75 extensibility follow-up: `GenerationLoweringStage.__post_init__`
  remains a central stage-name-to-output-type validation table. It is type
  validation rather than semantic dispatch, but it remains a growing
  maintainability pressure point.
- Post-M75 planning follow-up for M76 execution: keep the selected slice as an
  exact post-branch intrinsic call-site structural/request IR only. Do not let
  it become store semantics, ARM/SVE intrinsic semantics, memory behavior,
  pointer semantics, backend translation, renderer-ready IR, generated output,
  variable scope, generic call/store/body IR, or broad TSIL parsing.
- Post-M75 planning follow-up for M76 execution: `svst1`, `tmp.data()`, and
  `a` are exact corpus-shape tokens/provenance only. They must not become
  hardwired semantic outputs or dispatch keys; the only permitted linkage is
  structural provenance through accepted M75/M74/M73 values.
- Post-M75 planning follow-up for M76 execution: preserve accepted M57-M75
  behavior and selected-branch diagnostics, and include no-raw-helper,
  no-catalog, no-`tsldata`, no-host-CPU, no-backend-map, no-renderer, and
  no-`frozen/` regression coverage where practical.
- M76 documentation revision follow-up addressed during the execution-review
  loop: update stale planned/selected wording and record the new
  `TSL-LOWER-POST-BRANCH-CALL-SITE-*` diagnostic codes across the redesign
  docs.
- M76 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type validation table and is growing with each
  exact Stage 8 slice. Before several more exact lowering stages land, plan a
  small cleanup that preserves typed stage-specific attachment points without
  turning into a broad registry or dispatcher.
- M76 extensibility follow-up: keep future exact-shape recognizers
  slice-local. M76's comma-split parser is accepted only for the exact
  `intrin<svst1>(pg, tmp.data(), a);` shape and must not become a general
  call/body parser.
- Post-M76 planning follow-up for M77 execution: keep the refactor
  behavior-preserving and use it to isolate exact recognizer constants such as
  `pg`, `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `intrin`, `svst1`,
  `tmp.data()`, and `a` as slice-local structural evidence, not extension,
  SVE, store, memory, or backend semantics.
- Post-M76 planning follow-up for M77 execution: future backfeed support must
  be expressed as typed facts, typed requests, dependencies, or coordinator
  decisions. Do not implement speculative fixpoint/backfeed execution until a
  later milestone consumes a concrete typed need.
- M77 review follow-up: `_pipeline.py` is typed around stage names, artifact
  kinds, dependencies, and backfeed policy, but still carries `object` payloads
  for stage/value references. Future extraction should tighten this with a
  small local protocol or typed stage/value boundary when a concrete consumer
  needs it.
- M77 review follow-up: before real backfeed requests are used,
  `ExactArrayBodyPipelineSnapshot.key` should include request kind/source stage
  identity for pending backfeed requests, not only `request.key`.
- M77 review follow-up resolved by M78: remaining inline M75 predicate-init
  exact tokens such as `svbool_t`, `pg`, and `svptrue_b8` moved into
  `_exact_shapes.py` as slice-local structural evidence.
- M77 review follow-up: `GenerationLoweringStage.__post_init__` remains a
  growing stage/output validation table and should be revisited as the next
  maintainability pressure point before many more lowering stages are added.
- Post-M77 planning follow-up for M78 execution: replace fuzzy ownership with
  exact ownership criteria. Move only helpers exclusively consumed by the exact
  array-body / array-initialization package, or helpers required to preserve a
  coherent private extraction boundary; leave shared unrelated helpers in
  `boundary.py`.
- Post-M77 planning follow-up for M78 execution: watch circular imports. New
  private modules should depend on explicit typed inputs and moved shared
  values, not broad `boundary.py` internals that recreate the monolith.
- Post-M77 planning follow-up for M78 execution: object-oriented structure, if
  used, must be small and local to the exact decomposition boundary; broad
  class hierarchies are out of scope.
- M78 review follow-up: `_array_body_diagnostics.py` uses `Any` for several
  attribute-dependent diagnostic helper inputs to preserve one-way private
  imports and avoid circularity. A later decomposition slice should replace
  this with small local protocols or move the relevant typed models with the
  diagnostics.
- M78 review follow-up: exact helper `Literal` aliases are duplicated between
  `boundary.py` and `_array_body_shapes.py`; a later typed-model extraction
  should consolidate ownership to reduce drift risk.
- Post-M78 planning follow-up for M79 execution: M79 is allowed to combine
  duplicated helper alias cleanup and targeted diagnostic typing only as one
  exact array-body typed model ownership slice. It must not become broad
  package churn, a whole-file rewrite, or multiple unrelated cleanups.
- Post-M78 planning follow-up for M79 execution: `boundary.py` remains the
  public facade/coordinator. Private modules such as `_array_body_models.py`,
  `_array_body_shapes.py`, and `_array_body_diagnostics.py` must not import
  `boundary.py`; imports should remain one-way from the facade to private
  typed modules.
- Post-M78 planning follow-up for M79 execution: the line-count target is
  measured against the post-M78 11,109-line baseline, but line count must not
  drive movement of unrelated shared generation/lowering models or creation of
  a second monolith.
- Post-M78 planning follow-up for M79 execution: M79 must not add lowering
  semantics, helper evaluation, stage behavior, registries, dispatchers,
  fixpoint/backfeed execution, broad TSIL/body/call/store/return/declaration/
  array parsing, backend translation, rendering, generated output, CLI/report/
  writer behavior, Rust, compiler execution, file/catalog reads, `tsldata`
  reads, host CPU queries, backend map reads, or runtime `frozen/` use.
- M79 execution addressed the M78 follow-ups for duplicated exact helper
  `Literal` aliases and targeted `_array_body_diagnostics.py` `Any` helper
  inputs by moving exact model ownership into `_array_body_models.py` and
  sharing typed protocols with shapes and diagnostics.
- M79 review follow-up resolved by M80: committed private import-boundary
  regression coverage now proves accepted private lowering modules, including
  `_array_body_models.py`, `_array_body_shapes.py`,
  `_array_body_diagnostics.py`, `_array_body_validation.py`,
  `_exact_shapes.py`, and `_pipeline.py`, do not import `boundary.py`.
- M79 maintainability follow-up: private protocols in `_array_body_models.py`
  that mirror public generation model names, including `GenerationTypeRef` and
  `GenerationSelectedBodyEnvelopeIr`, are accepted for the import boundary but
  should be renamed, narrowed, or replaced by moved upstream model ownership
  when a concrete future slice touches that dependency.
- M79 maintainability follow-up: the structural M63-envelope `hasattr` checks
  in `_array_body_models.py` preserve the private import direction; if M63
  envelope ownership moves later, tighten this boundary deliberately instead
  of broadening structural checks.
- Post-M79 planning follow-up for M80 execution: keep M80 as
  behavior-preserving exact validation/request-record helper extraction only.
  Do not move source adapters or stage construction that still depend on
  facade-owned `GenerationLoweringStage` or `LoweredImplementation` unless a
  tiny dependency move is required and remains behavior-preserving.
- Post-M79 planning follow-up for M80 execution: create a private exact
  validation boundary such as `_array_body_validation.py` without importing
  `boundary.py`; use narrow local protocols only where necessary, and prefer
  leaving a helper in `boundary.py` over broadening structural protocols.
- Post-M79 planning follow-up for M80 execution: the line-count target is
  measured against the post-M79 8,915-line baseline, but line count must not
  drive movement of unrelated shared generation/lowering models, duplicate
  moved helpers, or creation of a second monolith.
- Post-M79 planning follow-up for M80 execution: M80 must not add lowering
  semantics, helper evaluation, stage behavior, source-adapter behavior,
  stage-construction frameworks, registries, dispatchers, fixpoint/backfeed
  execution, broad TSIL/body/call/store/return/declaration/array parsing,
  backend translation, rendering, generated output, CLI/report/writer
  behavior, Rust, compiler execution, file/catalog reads, `tsldata` reads,
  host CPU queries, backend map reads, or runtime `frozen/` use.
- M80 execution addressed the post-M79 planning follow-ups: review verified
  behavior-preserving exact validation/request-record helper extraction into
  `_array_body_validation.py`, one-way private imports, stable public facade
  imports, no source-adapter/stage-construction moves, no semantic expansion,
  and line-count reduction from 8,915 to 7,208 physical lines.
- M80 review follow-up resolved during finalization: the private-import
  regression test now detects direct absolute facade imports and common
  relative forms such as `from . import boundary` and
  `from .boundary import ...`.
- M80 maintainability follow-up: the selected/no-selected body envelope seam
  still uses narrow structural protocols/casts because the concrete M63
  envelope models remain facade-owned. A future lowering slice should either
  move selected-body envelope ownership deliberately or keep selected-body
  concrete checks at the facade boundary rather than broadening structural
  checks.
- Post-M80 planning follow-up for M81 execution: keep M81 as
  behavior-preserving generation-time lowering core extraction only. Do not add
  helper semantics, helper evaluation, broad helper families, broad TSIL
  parsing, backend translation/rendering/output, or generated artifacts.
- Post-M80 planning follow-up for M81 execution: keep source adapters and
  orchestration that still depend on `LoweringInput`, `LoweringRequest`,
  `LoweredImplementation`, `GenerationLoweringStage`, candidate selection, or
  exact array-body pipeline state in `boundary.py` unless a tiny delegation
  remains behavior-preserving.
- Post-M80 planning follow-up for M81 execution: create private generation
  modules without importing `boundary.py`; use narrow local protocols only
  where necessary, and prefer leaving helpers in `boundary.py` over broadening
  structural protocols.
- Post-M80 planning follow-up for M81 execution: the line-count target is
  measured against the post-M80 7,208-line baseline, but line count must not
  drive movement of unrelated exact array-body code, duplicate moved helpers,
  or creation of a second monolith.
- M81 execution addressed the post-M80 planning follow-ups: review verified
  behavior-preserving generation-time core extraction into private typed
  modules, one-way private imports, stable public facade imports, no semantic
  expansion, no source-adapter/stage-construction moves, and line-count
  reduction from 7,208 to 5,438 physical lines.
- M81 focused revision resolved the blocking maintainability review finding:
  `_generation_control_flow.py` no longer carries an over-broad
  facade-shaped candidate context or duplicate private `_context_for_candidate`
  construction. It uses a narrow private protocol and delegates query
  resolution through typed generation query helpers.
- M81 validation follow-up: the focused M81 selector is mostly
  ownership/import coverage. A future cleanup may broaden the focused command
  or add a small M81-tagged diagnostic source-location preservation check.
- M81 maintainability follow-up: `boundary.py` still repeats
  `_context_for_candidate(item, request)` and selected-type-tag expressions
  across the exact-array pipeline call sequence. A future cleanup may hoist
  those facade-local values for readability.
- Post-M81 planning follow-up for M82 execution: avoid moving only envelope
  classes if that would create circular imports through M62 body-IR ownership.
  Move the minimal cohesive selected-body value-model cluster needed for an
  import-safe private boundary.
- Post-M81 planning follow-up for M82 execution: do not broaden the existing
  selected/no-selected structural protocols to hide the seam. Prefer concrete
  private model ownership where possible, with narrow local protocols only
  where a facade-owned value must remain.
- Post-M81 planning follow-up for M82 execution: line-count reduction is useful
  but must not drive movement of unrelated exact array-body pipeline code,
  generation core helpers, source adapters, stage construction, or lowering
  behavior.
- M82 execution addressed the post-M81 planning follow-ups: review verified
  the minimal cohesive selected-body value-model cluster moved without circular
  imports, exact array-body consumers use concrete private selected-body
  envelope model checks instead of broad structural seams, source adapters and
  stage construction stayed facade-owned, and line-count reduction did not
  drive unrelated moves.
- M82 review recorded no non-blocking follow-ups.
- Post-M82 planning follow-up for M83 execution: keep M83 as
  behavior-preserving stage output-contract ownership extraction only. Do not
  add new stage names, new stage behavior, exact return-emission IR, pipeline
  payload rewrites, source adapters, broad TSIL/body/call/store/return/
  declaration/array semantics, helper evaluation, backend translation,
  rendering, generated output, or extension-specific shortcuts.
- Post-M82 planning follow-up for M83 execution: preserve public
  `GenerationLoweringStage` imports and stage behavior through
  `tslgen.lowering` and `tslgen.lowering.boundary`; private stage-contract
  modules must not import `boundary.py` or the package facade.
- Post-M82 planning follow-up for M83 execution: if the stage-output union
  depends on mini-TSIL statement models, move only the minimal value-model
  dependency needed to avoid circular imports, not mini-TSIL parsing or broad
  statement semantics.
- M83 execution addressed the post-M82 planning follow-ups: review verified
  stage-name/output compatibility now lives in the private typed
  `_stage_contracts.py` boundary, the minimal mini-TSIL value-model dependency
  moved without parsing/semantic expansion, public imports and stage behavior
  remain stable, source adapters and coordinator code stayed facade-owned, and
  line-count reduction did not drive unrelated moves.
- M83 validation follow-up: package-level alias coverage is intentionally
  unchanged. `tslgen.lowering.boundary` exposes `GenerationLoweringStageName`
  and `GenerationLoweringStageOutput`, while `tslgen.lowering` does not expose
  those aliases. A future public-surface cleanup may either document those
  aliases as boundary-only or explicitly export/test them from
  `tslgen.lowering`.
- Post-M83 planning follow-up for M84 execution: keep M84 as one cohesive
  behavior-preserving exact array-body pipeline/source-adapter ownership
  extraction. Do not combine it with exact return-emission IR, facade model
  extraction, mini-TSIL parsing movement, backend/rendering/output work, or
  broad source-adapter semantics.
- Post-M83 planning follow-up for M84 execution: the line-count goal is to
  continue shrinking `boundary.py` from the accepted M83 4,807-line baseline
  toward a roughly 1,000-line facade over multiple coherent milestones. M84
  should make a material reduction, with review pressure toward a facade below
  roughly 2,000 lines if the exact array-body ownership cluster can move
  without broad protocols, duplicate code, circular imports, or a second
  monolith.
- Post-M83 planning follow-up for M84 execution: private exact array-body
  pipeline/source modules must not import `boundary.py` or the
  `tslgen.lowering` package facade. Use narrow typed protocols only where a
  facade-owned value must remain, and prefer a smaller move over broad
  structural protocols or callback injection.
- Post-M83 planning follow-up for M84 execution: accepted exact tokens may
  move only as structural provenance or invariant evidence. They must not
  become raw-helper dispatch keys, extension/SVE semantics, backend/rendering
  behavior, or generated-output behavior.
- M84 execution addressed the post-M83 planning follow-ups: review verified
  exact array-body pipeline/source-adapter ownership moved into private typed
  modules, selected-body public lowerers remained boundary-owned in the
  accepted M84 baseline before the accepted M85 extraction, public imports and
  accepted behavior stayed stable, and private exact array-body modules do not
  import `boundary.py` or the `tslgen.lowering` package facade.
- M84 maintainability follow-up: `boundary.py` is now materially smaller at
  1,898 physical lines, but the long-running campaign target remains roughly
  1,000 lines. Future lowering decomposition should continue through cohesive
  ownership slices rather than line-count-only moves.
- M84 maintainability follow-up: `_array_body_lowering.py` and
  `_array_body_sources.py` must not become new catch-all modules. If they grow
  further, prefer another behavior-preserving split around a concrete typed
  ownership boundary.
- M84 validation follow-up: future tests may add lightweight guards against
  broad source-adapter protocols, generic dispatchers, or fixpoint/backfeed
  machinery if new lowering stages introduce pressure in that direction.
- M85 execution addressed the post-M84 planning follow-ups: review verified
  selected-body lowerer/source-helper ownership moved into
  `_selected_body_lowering.py`, selected-body behavior did not move into
  `_selected_body_models.py`, public facade imports and accepted behavior
  stayed stable, and the private selected-body lowering module does not import
  `boundary.py`, `tslgen.lowering`, `_array_body_sources.py`, or
  `_array_body_lowering.py` as convenience dispatchers.
- M85 focused revision restored source-location preservation for unsupported
  selected-body handoff diagnostics over `PrunedGenerationBranch` stage
  outputs and added focused regression coverage.
- Post-M85 planning follow-up for M86 execution: keep M86 as behavior-
  preserving payload-intake and mini-TSIL leaf-lowering extraction only. One
  planning subagent preferred exact return-emission structural/request IR as
  the next semantic frontier; record it as a continuing high-value follow-up,
  not as part of M86.
- Post-M85 planning follow-up for M86 execution: the payload-intake module may
  own only the exact payload-intake cluster named in the M86 plan. It must not
  absorb request/result models, `LoweringInputSet`, `prepare_lowering_inputs`,
  `lower_candidates`, `_lower_input`, stage builders, source adapters, or
  semantic lowering orchestration.
- Post-M85 planning follow-up for M86 execution: the mini-TSIL module is
  leaf-return lowering only. It must preserve the accepted direct parameter-add
  and `intrin_compose<add>` return forms without adding new TSIL syntax, broad
  expression/body/return semantics, generation helper evaluation, selected-
  body/exact-array dependencies, backend translation, or renderer-facing IR.
- M86 execution addressed the post-M85 planning follow-ups: review verified
  payload-intake ownership moved into `_lowering_inputs.py`, mini-TSIL leaf
  return-lowering ownership moved into `_mini_tsil_lowering.py`, request/result
  models and `_lower_input` remained facade-owned, accepted behavior stayed
  stable, and the private modules keep the planned one-way import direction.
- Post-M86 planning selects
  `Milestone 87: Exact Return-Emission Structural Request IR Slice`, and human
  acceptance was recorded. M87 should consume accepted M74 structural sequence
  provenance plus accepted M76 post-branch call-site provenance and record only
  the exact trailing `emit_return(tmp);` structural request, allowing
  insignificant whitespace and requiring `tmp` to match the accepted
  declaration-shell variable token.
- M87 must treat implementation bodies as source inputs, not repair targets.
  It may recognize the exact selected return-emission shape and emit typed IR;
  nearby or malformed forms are diagnostics/negative tests, not extra
  supported syntax. It must not correct, normalize into a different shape,
  infer intended operands, broaden `emit_return(...)`, interpret return value
  semantics, evaluate variable lifetime/scope, interpret `tmp.data()`, lower
  stores, add backend translation/rendering/output, or read catalogs,
  `tsldata`, backend maps, host CPU state, or `frozen/` at lowering time.
- Post-M86 planning also records durable workflow guardrails in `AGENTS.md`:
  lowering must not fix possibly wrong `.tsl` implementation bodies, and
  future implementation work should keep production files cohesive, prefer
  focused modules and encapsulated typed ownership, and plan a split or
  explicit temporary exception when a file approaches roughly 1,000 physical
  lines.
- M87 execution addressed the blocking extensibility review finding with a
  focused revision: `_return_emission.py` now consumes direct M76 call-site
  values, the M76 stage output, or a private M76-only source protocol, and the
  shared runtime lowered-implementation source protocol no longer includes
  `return_emission_structural_requests`.
- M87 non-blocking follow-up: improve the returned-token mismatch diagnostic
  so it names the actual returned token and expected declaration token.
- M87 maintainability follow-up: future exact array-body stages should split
  stage-specific source, validation, and diagnostic ownership instead of
  continuing to grow central exact array-body modules.
- M87 validation-hardening follow-up: future import-boundary tests may
  prefix-match backend/rendering submodules and include `frozen` / `tsldata`.
- Post-M89 planning follow-up for M90 execution: keep "completion" narrowed to
  Stage 8 exact lowering handoff completion only. M90 must not imply semantic
  completion of declaration, array, store, return, SVE, backend, renderer,
  generated-output, broad TSIL, or source-repair behavior.
- Post-M89 planning follow-up for M90 execution: put completion-package logic
  in focused private ownership and keep `boundary.py`, `_array_body_pipeline.py`,
  `_array_body_models.py`, and `_array_body_backend_deferred_requests.py` from
  becoming broader catch-all modules. If pipeline wiring growth is material,
  split focused ownership or document a temporary exception.
- Post-M89 planning follow-up for M90 execution: unresolved dependency records
  are typed handoff facts only. They must not become backend map keys, resolved
  text, renderer slots, artifact paths, scheduling decisions, broad protocols,
  hidden backfeeds, or fixpoint machinery.
- M90 execution follow-up: `boundary.py` is 1,226 lines and
  `_array_body_pipeline.py` is 1,043 lines. Future milestones should avoid
  adding another stage or aggregate field there without focused extraction or
  a documented temporary exception.
- M90 execution follow-up: `_array_body_completion_package.py` is 829 lines
  after the focused diagnostic-boundary revision. It should not absorb future
  backend-planning or dependency-expansion responsibilities; split source
  adaptation, diagnostics, or dependency modeling if it grows.
- M90 execution follow-up: the runtime source adapter is narrow and validated,
  but future slices should not broaden it into a shared protocol for arbitrary
  lowered-implementation facts.
- Post-M90 planning follow-up for M91 execution: keep M91 behavior-preserving.
  The milestone may consolidate exact array pipeline ownership, but it must
  not add semantic lowering, backend planning, rendering, generated output, or
  broad parser/source-adapter behavior.
- Post-M90 planning follow-up for M91 execution: materially reduce pressure on
  `boundary.py` and `_array_body_pipeline.py` by moving coherent ownership into
  focused private modules with one-way imports. Do not create a replacement
  monolith.
- Post-M90 planning follow-up for M91 execution: add or preserve
  import-boundary and behavior-preservation tests proving public exports,
  stage order, snapshot keys, diagnostics, and selected-branch-only behavior
  remain stable.
- M91 execution follow-up: `boundary.py` remains a 1,226-line broad
  compatibility facade. M91 did not grow it, but future lowering milestones
  should continue avoiding new ownership there and should prefer focused
  private modules with one-way imports.
- M92 execution addressed the post-M91 planning follow-ups: review verified
  the slice is a concrete typed lowering-side handoff request, not a wrapper-
  only abstraction, and unresolved dependency records remain request/
  provenance facts rather than backend map keys, resolved backend text,
  renderer slots, artifact paths, scheduling decisions, broad protocols,
  hidden backfeeds, or fixpoint machinery.
- M92 documentation re-review follow-up was addressed during finalization:
  wording in `generation-time-semantic-lowering.md` and `pipeline-design.md`
  no longer calls accepted M92 the "next" step.
- Post-M92 planning follow-up for M93 execution: keep M93 as a dual-source
  package boundary over exactly accepted M86 and M92 typed facts. Do not
  broaden it into a generic cross-primitive operation framework, operation
  registry, semantic dispatcher, dependency solver, backend plan, or renderer
  input.
- M93 execution follow-ups: `_operation_package.py` is cohesive but close to
  the 1,000-line guardrail, so the next package-family milestone should split
  diagnostics/provenance helpers before adding more families. `boundary.py`
  is 1,280 lines and should not absorb new ownership. Future package source
  narrowing must not evolve into a central semantic dispatcher.
- M94 execution addressed the post-M93 planning follow-ups: review verified
  behavior-preserving split ownership, `_operation_package.py` reduction from
  1,044 lines to 19 lines, no replacement operation-package monolith, and
  import-boundary coverage for every new operation-package module.
- M94 execution follow-up: `_operation_package_sources.py` remains focused at
  604 lines but necessarily uses duck-typed accepted containers through
  `hasattr`/`getattr` for the M93 surface. Future package-family work must not
  grow that into a generic source protocol or dispatcher.
- M94 execution follow-up: the current line-count test asserts each
  operation-package module remains below 1,000 lines. A future maintainability
  pass may choose a tighter threshold for operation-package private modules so
  a near-guardrail replacement monolith cannot technically pass.
- Post-M94 planning follow-up for M95 execution: prevent
  `_operation_package_sources.py` from growing into a generic source protocol,
  callback map, registry, or dispatcher while adding the selected-body
  direct-intrinsic package family. Use focused selected-body package ownership
  and keep `svptrue_b*`/`pg` fields as provenance only.
- M95 execution follow-up: `_operation_package_sources.py` is still below the
  1,000-line guardrail at 819 lines, but it is now the operation-package
  pressure point. Before adding another operation-package source family, split
  more source narrowing/package construction out of it rather than letting it
  grow into a central package router.
- M95 execution follow-up: `boundary.py` is exactly at the current 1,300-line
  guardrail. Future lowering work should avoid adding ownership there and
  should keep new behavior in focused private modules.
- M96 execution follow-up: `boundary.py` remains exactly at the 1,300-line
  guardrail and `_operation_package_sources.py` remains exactly at 819 lines.
  The next lowering slice should extract before adding ownership to either
  pressure point.
- M96 execution follow-up: if the Stage 8 manifest becomes public API later,
  add explicit facade/export stability tests. It is currently a private
  lowering module with stage-contract integration.
- M97 execution follow-up: `boundary.py` is still near the 1,300-line
  guardrail. The next lowering slice should avoid adding more coordination to
  `boundary.py` and should prefer extracting stage-helper or result-assembly
  ownership first if more state is needed.
- Post-M97 planning follow-up: M98 execution must keep the extracted module
  narrowly owned. It is a behavior-preserving stage-assembly/result-assembly
  extraction, not a generic coordinator, registry, dispatcher, hidden
  backfeed, fixpoint mechanism, or semantic lowering milestone.
- M98 execution follow-up: future lowering additions may reuse
  `_lowering_stage_assembly.py` for accepted stage construction/result
  assembly, but must not broaden it into a generic coordinator, registry,
  dispatcher, callback map, hidden backfeed, fixpoint mechanism, or semantic
  lowering milestone.
- Post-M98 planning follow-up for M99 execution: keep "backend-translation
  request inventory" wording anchored to Stage 8 inventory/provenance only.
  M99 must not implement backend translation, Stage 9 planning, dependency
  closure, operation scheduling, renderer-ready IR, source scanning, source
  repair, direct-intrinsic/SVE interpretation, or broad corpus completion.
- Future lowering milestones should update
  `docs/redesign/missing-lowering-inventory.md` when they accept, resolve,
  narrow, or discover lowering gaps.
- M99 implementation follow-up resolved during review: split request-inventory
  ownership into focused inventory, source-adapter, and diagnostics modules
  rather than leaving a near-guardrail private monolith.
- M99 validation follow-up resolved during review: add missing manifest
  container diagnostic tests and the required mypy annotation for the diagnostic
  case table.
- Post-M99 planning follow-up for M100 execution: keep translation metadata as
  explicit typed input and do not read backend maps/catalogs/manifests or
  `tsldata/detail/lang` during lowering.
- Post-M99 planning follow-up for M100 execution: keep C++ exact-array uninit
  translation-result state separate from renderer-ready IR, Stage 9 planning,
  generated output, Rust, generic backend helper evaluation, and
  direct-intrinsic/SVE semantics.
- Post-M99 planning follow-up for M100 execution: use focused module ownership
  and avoid growing `boundary.py`, M99 request-inventory modules, or existing
  near-guardrail backend translation modules into replacement monoliths.
- M100 execution follow-up: future milestones should avoid adding more
  orchestration to `boundary.py` without extracting boundary request/result
  assembly, because `boundary.py` remains close to the module-size guardrail.
- M101 validation follow-up: future diagnostic-sensitive slices should tighten
  diagnostic matrix tests to assert exact locations and important message
  snippets in addition to code/severity.
- M101 validation follow-up: `boundary.py` remains close to the 1300-line
  guardrail, so future orchestration should be extracted rather than added
  there.
- Post-M101 planning follow-ups for M102 execution were addressed during M102:
  negative protocol-conformance tests, import-boundary/forbidden-behavior
  tests, and keeping the category surface private without growing
  `boundary.py`.
- Post-M102 planning follow-ups for M103 execution were addressed during M103:
  the worklist remained a static inventory/provenance view, line-count
  guardrails/source assertions were added, and protocol-shaped fake-object
  negative tests were tightened after focused review.
- M103 follow-up for post-M103 planning: select exactly one worklist
  row/classification or documented lowering gap as the next focused
  implementation milestone. Addressed by selecting M104 as one documented
  lowering gap: M103 worklist entry to typed translation expansion result.
- M103 validation follow-up: future diagnostic-sensitive slices should keep
  tightening exact location and message-snippet assertions around malformed
  source/container diagnostics.
- Post-M103 planning follow-ups for M104 execution were addressed during M104:
  the broadening stayed constrained to explicit typed rule inputs and typed
  resolved/deferred/unsupported records; line-count/import-boundary tests
  prove no protected-module growth; fake-object/concrete-type negatives were
  added; and direct-intrinsic no-hardwiring behavior is tested.
- M104 implementation follow-up: consider tightening
  `Stage8BackendTranslationExpansionRule.rule_kind` from `str` to the existing
  `Stage8BackendTranslationExpansionRuleKind` alias in a later cleanup.
- M104 implementation follow-up: consider trimming M103 worklist contract
  constant re-exports from the private M104 facade module if ownership clarity
  becomes important.
- M104 validation follow-up: future diagnostic-sensitive slices should assert
  exact source path, line, column, and message snippets in addition to
  code/severity.
- M104 design follow-up: future Rust/type-context work should introduce
  explicit typed context instead of relying on M104's already-translated rule
  value.

## Stop Condition

No stop condition is active. The workflow is ready to run the active M111
execution-review-loop prompt.

## Validation Expectations

For docs-only planning tasks:

```bash
git diff --check
```

For M109 clean artifact writer boundary slice, validation completed with:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -c "from tslgen import ArtifactWriter, ArtifactWriteReport, Generator, Target, generate_from_paths, write_artifacts"
python -B -c "from pathlib import Path; files = [Path('tslgen/__init__.py'), *sorted(Path('tslgen/src/tslgen').rglob('*.py')), *sorted(Path('tslgen/tests').rglob('*.py'))]; [compile(path.read_text(), str(path), 'exec') for path in files]; print(f'compiled {len(files)} clean tslgen Python files')"
```

`git diff --check` returned exit 0 with no output. The targeted clean-package
test command returned exit 0 with `9 passed`. The public API import command
returned exit 0 with no output. The writer import command returned exit 0 with
no output. The no-write compile check returned exit 0 and printed
`compiled 29 clean tslgen Python files`.

For M110 clean scalar type lowering table slice, validation completed with:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -c "from tslgen.lowering import ScalarTypeDescriptor, lookup_scalar_type_descriptor, supported_scalar_type_tags"
python -B -m py_compile tslgen/src/tslgen/backends/cpp/backend.py tslgen/src/tslgen/backends/rust/backend.py tslgen/src/tslgen/lowering/__init__.py tslgen/src/tslgen/lowering/lowerer.py tslgen/src/tslgen/lowering/model.py tslgen/src/tslgen/lowering/scalar_types.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/syntax/parser.py tslgen/tests/test_m107_tiny_pipeline.py
```

`git diff --check` returned exit 0 with no output. The targeted clean-package
test command returned exit 0 with `16 passed`. The public API import command
returned exit 0 with no output. The scalar lowering import command returned
exit 0 with no output. The py_compile command returned exit 0 with no output.

For M108 clean lowering boundary slice, validation completed with:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -c "from tslgen.lowering import Lowerer, LoweredFunction, LoweredBinaryAddExpression"
python -B -c "from pathlib import Path; files = [Path('tslgen/__init__.py'), *sorted(Path('tslgen/src/tslgen').rglob('*.py')), *sorted(Path('tslgen/tests').rglob('*.py'))]; [compile(path.read_text(), str(path), 'exec') for path in files]; print(f'compiled {len(files)} clean tslgen Python files')"
```

`git diff --check` returned exit 0 with no output. The targeted clean-package
test command returned exit 0 with `7 passed`. The public API import command
returned exit 0 with no output. The lowering import command returned exit 0
with no output. The no-write compile check returned exit 0 and printed
`compiled 28 clean tslgen Python files`.

For M107 clean restart vertical slice, validation completed with:

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
PYTHONDONTWRITEBYTECODE=1 python -B -c "from tslgen import Artifact, ArtifactSet, Diagnostic, GenerationResult, Generator, SourceLocation, Target, TslProject, generate_from_paths; print('import surface ok')"
PYTHONPYCACHEPREFIX=/tmp/py-bench-m107-final-compile python -m compileall -q tslgen/__init__.py tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
```

`git diff --check` returned exit 0 with no output. The targeted clean-package
test command returned exit 0 with `4 passed`. The repo-root import-surface
check returned exit 0 and printed `import surface ok`. The compileall command
returned exit 0 with no output.

For M106 layout reset, validation completed with:

```bash
git diff --check
find tslgen -mindepth 1 -type f -print
git diff --name-only -- frozen
```

`git diff --check` returned exit 0 with no output. The fresh `tslgen/` file
check returned only `tslgen/README.md`. The frozen diff check returned exit 0
with no output.

For post-M101 acceptance finalization, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For M101, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or exact_array_backend_uninit_translation_result or m100 or m101"
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

The M101 line counts were `1284 tslgen/src/tslgen/lowering/boundary.py`,
`274 tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`,
`120 tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`,
`792 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`,
`207 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`,
`64 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`,
`614 tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`,
`275 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py`,
`85 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py`,
and `3715 total`. The py-compile command returned exit 0 with no output. The
focused M100/M101 result test returned `9 passed`. The focused M99/M100/M101
lowering-boundary command returned `5 passed, 352 deselected`. The focused
lowering mypy check returned `Success: no issues found in 46 source files`.
The standalone final `git diff --check` returned exit 0 with no output.

For M102, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or exact_array_backend_uninit_translation_result or m100 or m101 or m102"
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

The M102 line counts were `1284 tslgen/src/tslgen/lowering/boundary.py`,
`274 tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`,
`278 tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`,
`792 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`,
`207 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`,
`64 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`,
`614 tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`,
`275 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py`,
`85 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py`,
and `3873 total`. The py-compile command returned exit 0 with no output. The
focused backend-translation result test returned `12 passed in 14.57s`. The
focused M99/M100/M101/M102 lowering-boundary command returned
`5 passed, 352 deselected in 4.36s`. The focused lowering mypy check returned
`Success: no issues found in 46 source files`. The standalone final
`git diff --check` returned exit 0 with no output.

For post-M102 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M102 acceptance finalization, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For M103 execution and review, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

The M103 line counts were `1284 tslgen/src/tslgen/lowering/boundary.py`,
`278 tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`,
`792 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`,
`207 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`,
`64 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`,
`614 tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`,
`275 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py`,
`85 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py`,
`82 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`,
`71 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py`,
`324 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`,
`145 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`,
`195 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py`,
`188 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py`,
`644 tslgen/tests/unit/test_lowering_backend_boundary_worklist.py`, and
`5248 total`. The py-compile command returned exit 0 with no output. The
focused backend-boundary worklist test returned `7 passed in 13.79s`. The
focused backend-translation result regression test returned
`12 passed in 18.57s`. The focused lowering mypy check returned
`Success: no issues found in 53 source files`. The standalone final
`git diff --check` returned exit 0 with no output.

For post-M103 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M103 acceptance finalization, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For M104 execution and review, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_expansion.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

The M104 line counts were `1284 tslgen/src/tslgen/lowering/boundary.py`,
`278 tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`,
`792 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`,
`207 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`,
`64 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`,
`614 tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`,
`275 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py`,
`85 tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py`,
`82 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`,
`71 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py`,
`324 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`,
`145 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`,
`195 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py`,
`188 tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py`,
`394 tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py`,
`96 tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_diagnostics.py`,
`225 tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py`,
`89 tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py`,
`494 tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py`,
`787 tslgen/tests/unit/test_lowering_backend_translation_expansion.py`, and
`6689 total`. The py-compile command returned exit 0 with no output. The
focused backend translation expansion test returned `10 passed in 27.10s`.
The focused backend-boundary worklist regression test returned
`7 passed in 18.04s`. The focused backend-translation result regression test
returned `12 passed in 23.65s`. The focused lowering mypy check returned
`Success: no issues found in 59 source files`. The standalone final
`git diff --check` returned exit 0 with no output.

For post-M99 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M99 acceptance finalization, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M98 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M98 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m98-acceptance-finalization-prompt.md docs/agent/runs/m99-execution-review-loop-prompt.md docs/redesign/README.md docs/redesign/behavioral-spec.md docs/redesign/design-decisions.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/implementation-roadmap.md docs/redesign/missing-lowering-inventory.md docs/redesign/open-questions.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md
```

The command returned exit 0 with no output.

For M99 execution and review, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or completion_gap_inventory or completion_manifest or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M99 line counts were `1254 tslgen/src/tslgen/lowering/boundary.py`,
`819 tslgen/src/tslgen/lowering/_operation_package_sources.py`,
`776 tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`,
`564 tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`,
`223 tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`,
`770 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`,
`207 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`,
`64 tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`,
and `4677 total`. The py-compile command returned exit 0 with no output. The
focused M99/package/manifest/gap-inventory command returned
`27 passed, 330 deselected in 87.81s`. The full lowering-boundary suite
returned `357 passed in 741.11s (0:12:21)`. The focused lowering mypy check
returned `Success: no issues found in 41 source files`. The validation profile
returned exit 0 with corpus probes `3 passed in 19.42s`, unit discovery `691`
tests OK in `765.631s`, compileall OK, ruff `All checks passed!`, mypy
`Success: no issues found in 145 source files`, and diff-check OK. The
standalone final `git diff --check` returned exit 0 with no output.

For post-M95 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M95 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m95-acceptance-finalization-prompt.md docs/agent/runs/m96-execution-review-loop-prompt.md docs/redesign/design-decisions.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/implementation-roadmap.md docs/redesign/open-questions.md docs/redesign/pipeline-design.md docs/redesign/testing-strategy.md
```

The command returned exit 0 with no output.

For M96 execution and review, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package*.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m96 or completion_manifest or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The line-count command returned `boundary.py` 1,300,
`_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
and `2,895 total`. Py-compile returned exit 0 with no output. Focused pytest
returned `17 passed, 326 deselected in 18.10s`. Full lowering-boundary pytest
returned `343 passed in 148.42s`. Lowering mypy returned
`Success: no issues found in 36 source files`. Tooling validation returned
corpus probes `3 passed`, unittest discovery `Ran 677 tests ... OK`,
compileall OK, ruff `All checks passed!`, mypy
`Success: no issues found in 140 source files`, and diff-check OK. Standalone
`git diff --check` returned exit 0 with no output.

For post-M96 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M90 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M90 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m90-acceptance-finalization-prompt.md docs/agent/runs/m91-execution-review-loop-prompt.md docs/redesign/implementation-roadmap.md docs/redesign/behavioral-spec.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md docs/redesign/design-decisions.md docs/redesign/open-questions.md
```

The command returned exit 0 with no output.

For M91, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m91 or pipeline_ownership or exact_array_body_pipeline or lowering_completion"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Validation results:

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

For final M91 state and next-prompt updates, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For M92, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m92 or backend_handoff or lowering_completion or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Validation results:

- Line counts: `1245 tslgen/src/tslgen/lowering/boundary.py`,
  `616 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
  `667 tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`, and
  `2528 total`.
- Py-compile returned exit 0 with no output.
- Focused M92 pytest returned `17 passed, 306 deselected in 12.13s`.
- Full lowering-boundary pytest returned `323 passed in 107.02s`.
- Focused lowering mypy returned
  `Success: no issues found in 28 source files`.
- Full tooling validation returned exit 0 with corpus probes
  `3 passed in 10.44s`, unit discovery `657` tests OK in `239.885s`,
  compileall OK, ruff `All checks passed!`, mypy
  `Success: no issues found in 132 source files`, and diff-check OK.
- Standalone final `git diff --check` returned exit 0 with no output.

For post-M92 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M92 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m92-acceptance-finalization-prompt.md docs/agent/runs/m93-execution-review-loop-prompt.md docs/redesign/implementation-roadmap.md docs/redesign/behavioral-spec.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md docs/redesign/design-decisions.md docs/redesign/open-questions.md
```

The command returned exit 0 with no output.

For post-M91 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M91 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m91-acceptance-finalization-prompt.md docs/agent/runs/m92-execution-review-loop-prompt.md docs/redesign/implementation-roadmap.md docs/redesign/behavioral-spec.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md docs/redesign/design-decisions.md docs/redesign/open-questions.md
```

The command returned exit 0 with no output.

For post-M89 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M89 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m89-acceptance-finalization-prompt.md docs/agent/runs/m90-execution-review-loop-prompt.md docs/redesign/behavioral-spec.md docs/redesign/design-decisions.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/implementation-roadmap.md docs/redesign/open-questions.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md
```

The command returned exit 0 with no output.

For M90, validation completed after one focused diagnostic-boundary revision
with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m90 or lowering_completion or backend_deferred or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M90 line counts were `1226 tslgen/src/tslgen/lowering/boundary.py`,
`1043 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
`708 tslgen/src/tslgen/lowering/_array_body_package.py`,
`735 tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`,
`829 tslgen/src/tslgen/lowering/_array_body_completion_package.py`, and
`4541 total`. The py-compile command returned exit 0 with no output. The
focused M90 command returned `22 passed, 291 deselected in 9.98s`. The full
lowering-boundary suite returned `313 passed in 65.72s`. The focused lowering
mypy check returned `Success: no issues found in 25 source files`. The
validation profile returned exit 0 with corpus probes `3 passed in 6.78s`,
unit discovery `647` tests OK in `139.463s`, compileall OK, ruff
`All checks passed!`, mypy `Success: no issues found in 129 source files`,
and diff-check OK. The standalone final `git diff --check` returned exit 0
with no output.

For implementation milestones, run the milestone-specific targeted tests plus:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

For M78, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M78-focused module-decomposition/import-stability command also completed.

For M79, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m79"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M79 line count was `8915 tslgen/src/tslgen/lowering/boundary.py`.
The focused M79 command returned `3 passed, 257 deselected`. The full
lowering-boundary suite returned `260 passed`. The validation profile returned
exit 0 with unit discovery `594` tests OK, compileall OK, ruff OK, mypy OK,
and diff-check OK.

For M80, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m80"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M80 line count was `7208 tslgen/src/tslgen/lowering/boundary.py`.
The focused M80 command returned `2 passed, 260 deselected`. The full
lowering-boundary suite returned `262 passed`. The validation profile returned
exit 0 with corpus probes `3 passed`, unit discovery `596` tests OK,
compileall OK, ruff OK, mypy OK, and diff-check OK.

For M81, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m81 or size_byte_branch_chain or signedness_branch"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M81 line count was `5438 tslgen/src/tslgen/lowering/boundary.py`.
The focused M81 command returned `15 passed, 250 deselected`. The full
lowering-boundary suite returned `265 passed`. The focused lowering mypy check
returned `Success: no issues found in 13 source files`. The validation profile
returned exit 0 with corpus probes `3 passed`, unit discovery `599` tests OK,
compileall OK, ruff OK, mypy OK, and diff-check OK.

For M82, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m82"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M82 line count was `4965 tslgen/src/tslgen/lowering/boundary.py`.
The focused M82 command returned `3 passed, 265 deselected`. The full
lowering-boundary suite returned `268 passed`. The focused lowering mypy check
returned `Success: no issues found in 14 source files`. The validation profile
returned exit 0 with corpus probes `3 passed`, unit discovery `602` tests OK,
compileall OK, ruff OK, mypy `Success: no issues found in 118 source files`,
and diff-check OK.

For M83, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m83 or stage_contract or generation_lowering_stage"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M83 line count was `4807 tslgen/src/tslgen/lowering/boundary.py`.
The focused M83 command returned `7 passed, 265 deselected`. The full
lowering-boundary suite returned `272 passed`. The focused lowering mypy check
returned `Success: no issues found in 15 source files`. The validation profile
returned exit 0 with corpus probes `3 passed`, unit discovery `606` tests OK,
compileall OK, ruff OK, mypy `Success: no issues found in 119 source files`,
and diff-check OK.

For M84, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m84 or array_body_pipeline or array_body_sources or array_body_lowering or source_adapter or exact_array"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M84 line counts were `1898 tslgen/src/tslgen/lowering/boundary.py`,
`835 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
`1022 tslgen/src/tslgen/lowering/_array_body_sources.py`, and
`1378 tslgen/src/tslgen/lowering/_array_body_lowering.py`. The focused M84
command returned `88 passed, 188 deselected`. The full lowering-boundary suite
returned `276 passed`. The focused lowering mypy check returned
`Success: no issues found in 18 source files`. The validation profile returned
exit 0 with corpus probes `3 passed`, unit discovery `610` tests OK,
compileall OK, ruff OK, mypy `Success: no issues found in 122 source files`,
and diff-check OK. The standalone final `git diff --check` returned exit 0
with no output.

For M85, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m85 or selected_body_lowering or selected_body_handoff or selected_body_envelope"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M85 line counts were `1417 tslgen/src/tslgen/lowering/boundary.py` and
`538 tslgen/src/tslgen/lowering/_selected_body_lowering.py`. The focused M85
command returned `12 passed, 268 deselected`. The full lowering-boundary suite
returned `280 passed`. The focused lowering mypy check returned
`Success: no issues found in 19 source files`. The validation profile returned
exit 0 with corpus probes `3 passed`, unit discovery `614` tests OK,
compileall OK, ruff OK, mypy `Success: no issues found in 123 source files`,
and diff-check OK. The standalone final `git diff --check` returned exit 0
with no output.

For M86, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m86 or lowering_input or payload_classification or mini_tsil or typed_opaque"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M86 line counts were `1145 tslgen/src/tslgen/lowering/boundary.py`,
`128 tslgen/src/tslgen/lowering/_lowering_inputs.py`, and
`188 tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`. The focused M86
command returned `9 passed, 277 deselected`. The full lowering-boundary suite
returned `286 passed`. The focused lowering mypy check returned
`Success: no issues found in 21 source files`. The validation profile returned
exit 0 with corpus probes `3 passed`, unit discovery `620` tests OK,
compileall OK, ruff OK, mypy `Success: no issues found in 125 source files`,
and diff-check OK. The standalone final `git diff --check` returned exit 0
with no output.

For M87, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_return_emission.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_return_emission.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m87 or return_emission or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M87 line counts were `1163 tslgen/src/tslgen/lowering/boundary.py`,
`2629 tslgen/src/tslgen/lowering/_array_body_models.py`,
`1378 tslgen/src/tslgen/lowering/_array_body_lowering.py`,
`890 tslgen/src/tslgen/lowering/_array_body_pipeline.py`, and
`112 tslgen/src/tslgen/lowering/_return_emission.py`. The focused M87
command returned `6 passed, 286 deselected in 2.18s`. The full
lowering-boundary suite returned `292 passed in 39.25s`. The focused lowering
mypy check returned `Success: no issues found in 22 source files`. The
validation profile returned exit 0 with corpus probes `3 passed`, unit
discovery `626` tests OK, compileall OK, ruff OK, mypy
`Success: no issues found in 126 source files`, and diff-check OK. The
standalone final `git diff --check` returned exit 0 with no output.

For M88, validation completed after the focused extensibility revision with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m88 or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M88 line counts were `1183 tslgen/src/tslgen/lowering/boundary.py`,
`2629 tslgen/src/tslgen/lowering/_array_body_models.py`,
`950 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
`1111 tslgen/src/tslgen/lowering/_array_body_sources.py`,
`1890 tslgen/src/tslgen/lowering/_array_body_validation.py`,
`1205 tslgen/src/tslgen/lowering/_array_body_diagnostics.py`,
`112 tslgen/src/tslgen/lowering/_return_emission.py`,
`708 tslgen/src/tslgen/lowering/_array_body_package.py`, and `9788 total`.
The py-compile command returned exit 0 with no output. The focused M88 command
returned `8 passed, 291 deselected in 3.20s`. The full lowering-boundary suite
returned `299 passed in 44.20s`. The focused lowering mypy check returned
`Success: no issues found in 23 source files`. The validation profile returned
exit 0 with corpus probes `3 passed in 5.98s`, unit discovery `633` tests OK
in `111.925s`, compileall OK, ruff `All checks passed!`, mypy `Success: no
issues found in 127 source files`, and diff-check OK. The standalone final
`git diff --check` returned exit 0 with no output.

For M89, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m89 or backend_deferred or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M89 line counts were `1205 tslgen/src/tslgen/lowering/boundary.py`,
`708 tslgen/src/tslgen/lowering/_array_body_package.py`,
`998 tslgen/src/tslgen/lowering/_array_body_pipeline.py`,
`735 tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`,
and `3646 total`. The py-compile command returned exit 0 with no output. The
focused M89 command returned `15 passed, 291 deselected in 6.07s`. The full
lowering-boundary suite returned `306 passed in 64.22s`. The focused lowering
mypy check returned `Success: no issues found in 24 source files`. The
validation profile returned exit 0 with corpus probes `3 passed`, unit
discovery `640` tests OK, compileall OK, ruff OK, mypy `Success: no issues
found in 128 source files`, and diff-check OK. The standalone final
`git diff --check` returned exit 0 with no output.

For post-M97 planning, validation completed with:

```bash
git diff --check
```

The command returned exit 0 with no output.

For post-M97 acceptance finalization, validation completed with:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m97-acceptance-finalization-prompt.md docs/agent/runs/m98-execution-review-loop-prompt.md docs/redesign/behavioral-spec.md docs/redesign/design-decisions.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/implementation-roadmap.md docs/redesign/open-questions.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md
```

The command returned exit 0 with no output.

For M98 execution and review, validation completed with:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m98 or stage_assembly or completion_manifest or completion_gap_inventory or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The M98 line counts were `1241 tslgen/src/tslgen/lowering/boundary.py`,
`189 tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`,
`819 tslgen/src/tslgen/lowering/_operation_package_sources.py`,
`776 tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`,
`564 tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`, and
`3589 total`. The py-compile command returned exit 0 with no output. The
focused M98 command returned `27 passed, 325 deselected in 30.39s`. The full
lowering-boundary suite returned `352 passed in 210.49s (0:03:30)`. The
focused lowering mypy check returned
`Success: no issues found in 38 source files`. The validation profile returned
exit 0 with corpus probes `3 passed in 6.19s`, unit discovery `686` tests OK
in `272.384s`, compileall OK, ruff `All checks passed!`, mypy `Success: no
issues found in 142 source files`, and diff-check OK. The standalone final
`git diff --check` returned exit 0 with no output.
