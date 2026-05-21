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

Accepted through M98:

- Generation-time lowering handles only the accepted typed helper/predicate
  forms from M38, M41-M43, M48, M51-M59, and M67-M72.
- Selected body lowering handles only the accepted M60-M63 selected-body
  handoff/form/body-IR/envelope path.
- Exact array-body lowering handles only the accepted M64-M76 structural and
  request forms plus M87-M92 return/package/backend-handoff slices.
- Stage 8 operation packages, completion manifests, gap inventories, and
  stage assembly are accepted through M93-M98.
- Backend translation, Stage 9 planning, renderer-ready IR, rendering,
  generated output, dependency closure, and broad TSIL semantics remain
  deferred unless a milestone explicitly selects a narrow slice.

Post-M98 planning selected and human acceptance recorded M99 as the next
lowering milestone:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
```

For M99, "backend-translation request inventory" means a typed Stage 8
inventory/provenance view over already accepted deferred/backend-scoped request
facts. It must not translate, resolve, evaluate, plan, or render those facts.

M97's no-known-gap state is not a statement that no lowering work is missing.
It only means the accepted M96 manifest has no currently supported
manifest-visible unresolved backend-handoff dependency records. This document
tracks the broader known missing lowering surface.

## Missing Work

| Area | Evidence paths | Current accepted boundary | Required typed fact/request | Candidate milestone | Boundary notes |
| --- | --- | --- | --- | --- | --- |
| Stage 8 to backend handoff | `tsldata/primitives/load_store/array.tsl`, accepted M92/M96/M97 records | M92 has one exact-array backend-handoff request. M96/M97 expose package manifests and lowering-observed gaps. | Cross-package backend-scoped request inventory over accepted package/manifest/gap facts. | M99 | Inventory only: no backend maps, Stage 9 planning, rendering, or inferred requests. |
| Backend value/type requests | `tsldata/detail/lang/types/types_cpp.tsl`, `tsldata/detail/lang/translate_cpp.tsl`, array/uninit evidence | M72 preserves exact `value<backend>(uninit::array)` as deferred state; M92 carries it as handoff. | Typed backend value/type request records over already resolved semantic values. | Later backend-request slices | Do not parse raw helper text or evaluate backend maps in renderers. |
| Direct intrinsics | `tsldata/primitives/load_store/array.tsl`, `load_store/store.tsl`, accepted M62/M63/M76/M95 facts | M62/M63/M95 preserve only selected assignment direct-intrinsic facts; M76 preserves one exact post-branch call-site structural request. | Typed direct-intrinsic call/body request records and diagnostics. | Later direct-intrinsic slice | No SVE hardwiring, byte-size-to-token inference, or intrinsic-text dispatch. |
| Intrinsic modifiers | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `frozen/tsl-gen/tsl_gen/tsil.lark` | M38 and M45 cover selected compose/suffix behavior for narrow add output paths. | Typed modifier records for prefix, suffix, infix, post, and immediate fields. | Later modifier slice | Translation consumes typed records; renderers do not infer modifiers. |
| Primitive calls and dependencies | `frozen/tsl-gen/tsl_gen/tsil_engine/dependencies.py`, `tsldata/primitives/**.tsl` | Candidate fallback visibility exists; semantic TSIL call AST and dependency closure remain deferred. | Typed primitive-call IR, dependency request records, and closure policy. | Later call/dependency slice | No dependency closure hidden inside lowering inventories. |
| Body structure | `frozen/tsl-gen/tsl_gen/tsil.lark`, `tsldata/primitives/load_store/*.tsl` | M64-M76 and M87 cover only named exact array-body slots and trailing `emit_return(tmp);` request structure. | Typed body model for loops, variables, scopes, assignments, indexing, declarations, arrays, stores, returns, and casts. | Later body-model slices | Introduce real TSIL/body models when needed; do not grow regex-like recognition. |
| Generation expressions | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `load_store/*.tsl` | M55-M59 cover size-byte value, selected arithmetic, equality predicates, and one exact branch-chain form. M48/M51/M52 cover selected signedness forms. | Typed evaluator functions for selected comparison, boolean, arithmetic, nested expression, and branch families. | Later generation-expression slices | Preserve selected-branch-only diagnostics; no renderer evaluation. |
| Vector/register metadata | `tsldata/primitives/load_store/load.tsl`, `store.tsl`, `conversion/repr_change.tsl` | M70/M71 resolve only exact array-initialization vector length/alignment requests from explicit metadata. | Typed vector/register/generic metadata facts and validation. | Later vector-metadata slices | Metadata must be supplied before lowering evaluation; no host CPU or token inference. |
| Source-body coverage | `tsldata/primitives/**.tsl` | Accepted narrow forms are named exact shapes; nearby malformed forms are diagnostic boundaries. | Explicit accepted forms or typed parser/model slices. | Per-family slices | Do not repair, complete, reorder, normalize, or guess source bodies. |
| Renderer-ready body IR | Accepted M93-M98 package/manifest/gap state | Current Stage 8 packages and manifests are provenance/readiness only, not renderer-ready IR. | Backend-translated body/value IR after typed request resolution. | Later Stage 8/Stage 9 boundary | Keep Stage 8 inventories separate from renderer readiness. |
| Backend maps and support decisions | `tsldata/detail/lang/*.tsl`, backend manifests | M40/M45/M46 cover selected translation values for native add; M99 remains inventory only. | Typed backend translation results and support diagnostics. | Stage 9/backend slices | Backend translation consumes typed requests and metadata; no raw generation helper text. |
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
- Keep new ownership in focused private modules and keep public facade changes
  narrow and tested.

## Maintenance Rule

Every future lowering planning or execution milestone should update this file
when it accepts, resolves, narrows, or newly discovers a lowering gap. If a
milestone deliberately leaves a gap unresolved, record the boundary rather than
encoding the gap as a silent assumption.
