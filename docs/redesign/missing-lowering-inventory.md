# Missing Lowering Inventory

This document is the living inventory of known missing lowering work. It keeps
the deferred lowering surface in one place so future milestones can choose the
next focused slice without rediscovering the same gaps from the roadmap,
behavioral matrix, and open questions.

The inventory is documentation only. It is not a runtime input, generated
artifact, source scanner, dependency-closure plan, or completeness oracle.
Future milestones may cite it, but implementation must still be driven by
typed redesign contracts, explicit evidence, diagnostics, and tests.

## Current Baseline

Accepted through M100:

- Generation-time lowering handles only the accepted typed helper/predicate
  forms from M38, M41-M43, M48, M51-M59, and M67-M72.
- Selected body lowering handles only the accepted M60-M63 selected-body
  handoff/form/body-IR/envelope path.
- Exact array-body lowering handles only the accepted M64-M76 structural and
  request forms plus M87-M92 return/package/backend-handoff slices.
- Stage 8 operation packages, completion manifests, gap inventories, stage
  assembly, backend-translation request inventories, and the exact C++
  backend-uninit translation-result boundary are accepted through M93-M100.
- Broad backend translation, Stage 9 planning, renderer-ready IR, rendering,
  generated output, dependency closure, Rust uninit translation, and broad TSIL
  semantics remain deferred unless a milestone explicitly selects a narrow
  slice.

M99 is accepted:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
```

For M99, "backend-translation request inventory" means a typed Stage 8
inventory/provenance view over already accepted deferred/backend-scoped request
facts. It does not translate, resolve, evaluate, plan, or render those facts.
The accepted M99 inventory records exact-array
`exact_array_backend_value_uninit_array`, selected-body
`selected_body_direct_intrinsic_handoff`, and
`no_accepted_backend_scoped_request` states.

Post-M99 planning selected and M100 execution accepted:

```text
Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice
```

M100 is the first accepted request-to-translation-result boundary. It narrows
only the exact-array `exact_array_backend_value_uninit_array` request to typed
C++ backend-uninit translation-result state from explicit typed rule/metadata
input. It does not render C++ or Rust code, start Stage 9 backend planning,
resolve Rust `value_array_uninit`, evaluate generic backend helpers, resolve
selected-body direct intrinsics, read backend maps/catalogs/manifests, or treat
this inventory as a runtime input.

Post-M100 planning selects:

```text
Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice
```

M101 is planned as a behavior-preserving consolidation milestone before adding
more lowering features. It defines a smaller vocabulary for lowering facts,
requests, results, inventories, provenance, rule inputs, and stage envelopes,
then applies that contract only to the accepted M99/M100 backend-translation
request/result path. It must not introduce new backend semantics, Stage 9
planning, rendering, output, Rust translation, generic backend helper
evaluation, raw source parsing, source repair, direct-intrinsic/SVE semantics,
or a broad inheritance/registry/dispatcher mechanism.

M97's no-known-gap state is not a statement that no lowering work is missing.
It only means the accepted M96 manifest has no currently supported
manifest-visible unresolved backend-handoff dependency records. This document
tracks the broader known missing lowering surface.

## Missing Work

| Area | Evidence paths | Current accepted boundary | Required typed fact/request | Candidate milestone | Boundary notes |
| --- | --- | --- | --- | --- | --- |
| Stage 8 to backend handoff | `tsldata/primitives/load_store/array.tsl`, accepted M92/M96/M97/M99 records | M99 accepts the first cross-package backend-scoped request inventory over accepted package/manifest/gap facts; M100 accepts one exact C++ backend-uninit translation-result boundary after that inventory. | Additional typed request families as they are accepted; later backend resolution/translation consumes the inventory. | Accepted M99 plus accepted M100 for one exact C++ backend-uninit result | M100 is translation-result only: no Stage 9 planning, rendering, output, scheduling, dependency closure, or inferred requests. |
| Backend value/type requests | `tsldata/detail/lang/types/types_cpp.tsl`, `tsldata/detail/lang/translate_cpp.tsl`, array/uninit evidence | M72 preserves exact `value<backend>(uninit::array)` as deferred state; M92 carries it as handoff; M99 inventories it as `exact_array_backend_value_uninit_array`; M100 resolves that exact C++ request to a typed translation-result value from explicit typed rule input. | Typed backend value/type request records over already resolved semantic values; additional exact/broad value/type results remain missing. | Accepted M100 for exact C++ uninit; later backend-request slices for Rust and broader values/types | Do not parse raw helper text, read backend maps/catalogs/manifests during lowering, or evaluate backend maps in renderers. Rust remains deferred because its `value_array_uninit` spelling needs typed `{type}` context not accepted for this request. |
| Lowering IR taxonomy and provenance | Accepted M57-M100 lowering stage/result modules; M99/M100 backend-translation request/result path | Typed IR is explicit, but many recent slices encode provenance and milestone history in narrow one-off request/result classes. | A smaller contract distinguishing semantic facts, requests, results, inventories, provenance, rule inputs, and stage envelopes; shared provenance shape where safe. | Planned M101 over M99/M100 only | Behavior-preserving consolidation only: no new lowering semantics, no broad hierarchy, no registry/dispatcher, and no weakening of diagnostics or object-identity guarantees. |
| Direct intrinsics | `tsldata/primitives/load_store/array.tsl`, `load_store/store.tsl`, accepted M62/M63/M76/M95 facts | M62/M63/M95 preserve only selected assignment direct-intrinsic facts; M76 preserves one exact post-branch call-site structural request. | Typed direct-intrinsic call/body request records and diagnostics. | Later direct-intrinsic slice | No SVE hardwiring, byte-size-to-token inference, or intrinsic-text dispatch. |
| Intrinsic modifiers | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `frozen/tsl-gen/tsl_gen/tsil.lark` | M38 and M45 cover selected compose/suffix behavior for narrow add output paths. | Typed modifier records for prefix, suffix, infix, post, and immediate fields. | Later modifier slice | Translation consumes typed records; renderers do not infer modifiers. |
| Primitive calls and dependencies | `frozen/tsl-gen/tsl_gen/tsil_engine/dependencies.py`, `tsldata/primitives/**.tsl` | Candidate fallback visibility exists; semantic TSIL call AST and dependency closure remain deferred. | Typed primitive-call IR, dependency request records, and closure policy. | Later call/dependency slice | No dependency closure hidden inside lowering inventories. |
| Body structure | `frozen/tsl-gen/tsl_gen/tsil.lark`, `tsldata/primitives/load_store/*.tsl` | M64-M76 and M87 cover only named exact array-body slots and trailing `emit_return(tmp);` request structure. | Typed body model for loops, variables, scopes, assignments, indexing, declarations, arrays, stores, returns, and casts. | Later body-model slices | Introduce real TSIL/body models when needed; do not grow regex-like recognition. |
| Generation expressions | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `load_store/*.tsl` | M55-M59 cover size-byte value, selected arithmetic, equality predicates, and one exact branch-chain form. M48/M51/M52 cover selected signedness forms. | Typed evaluator functions for selected comparison, boolean, arithmetic, nested expression, and branch families. | Later generation-expression slices | Preserve selected-branch-only diagnostics; no renderer evaluation. |
| Vector/register metadata | `tsldata/primitives/load_store/load.tsl`, `store.tsl`, `conversion/repr_change.tsl` | M70/M71 resolve only exact array-initialization vector length/alignment requests from explicit metadata. | Typed vector/register/generic metadata facts and validation. | Later vector-metadata slices | Metadata must be supplied before lowering evaluation; no host CPU or token inference. |
| Source-body coverage | `tsldata/primitives/**.tsl` | Accepted narrow forms are named exact shapes; nearby malformed forms are diagnostic boundaries. | Explicit accepted forms or typed parser/model slices. | Per-family slices | Do not repair, complete, reorder, normalize, or guess source bodies. |
| Renderer-ready body IR | Accepted M93-M99 package/manifest/gap/request-inventory state | Current Stage 8 packages, manifests, gaps, and request inventories are provenance/readiness only, not renderer-ready IR. | Backend-translated body/value IR after typed request resolution. | Later Stage 8/Stage 9 boundary | Keep Stage 8 inventories separate from renderer readiness. |
| Backend maps and support decisions | `tsldata/detail/lang/*.tsl`, backend manifests | M40/M45/M46 cover selected translation values for native add; M99 adds inventory only. | Typed backend translation results and support diagnostics. | Stage 9/backend slices | Backend translation consumes typed requests and metadata; no raw generation helper text. |
| Output integration | `frozen/out/**`, `frozen/run_all.sh`, generated-output docs | Narrow output/report/test slices are accepted, but broad output remains outside lowering. | Renderer-ready values, artifact plans, writers, and optional toolchain execution policies. | Output/backend phases | Not lowering work, but blocked on typed lowering/backend results. |

## Guardrails

- Treat accepted `.tsl` bodies as source inputs, not repair targets.
- Consume accepted typed Stage 8 facts; do not reparse raw implementation text
  unless a future milestone explicitly creates a typed body parser/model.
- Do not use source locations, extension ids, backend ids, primitive names,
  selected type tags, direct-intrinsic tokens, or hardware-looking tokens as
  semantic dispatch keys.
- Keep inventories as inventories: no backend planning, operation scheduling,
  dependency closure, renderer-ready IR, rendering, output, hidden backfeeds,
  or fixpoint behavior.
- Keep M100 translation results as typed backend value state only: no
  renderer-ready IR, generated source, artifact plans, Stage 9 planning, Rust,
  direct-intrinsic/SVE semantics, or generic backend helper evaluation.
- Keep new ownership in focused private modules and keep public facade changes
  narrow and tested.
- Before adding another feature-specific lowering request/result family, check
  whether a taxonomy/provenance consolidation slice is needed instead.

## Maintenance Rule

Every future lowering planning or execution milestone should update this file
when it accepts, resolves, narrows, or newly discovers a lowering gap. If a
milestone deliberately leaves a gap unresolved, record the boundary rather than
encoding the gap as a silent assumption.
