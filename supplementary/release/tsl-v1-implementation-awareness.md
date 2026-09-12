# TSL v1 implementation-awareness audit

Status: reviewed coarse v1 contract. This record freezes existing compiler
behavior; it does not introduce hazards, performance scores, consumer
contracts, or a capability-certificate schema.

## Findings

No architecture-boundary violation remains after the Slice 11 fixes. Two
projection defects were found:

1. Concrete analysis accepted only primitive/profile/backend/extension/type
   coordinates. A family such as `add` therefore combined the ordinary and two
   masked callables and reported `composed`, although the ordinary generated
   query reported `native`. Lowering now preserves the authored signature and
   attributes. `tslc analyze --signature ... --attribute ...` selects that
   existing identity, and the VS Code explorer always sends it. Omitting the
   filters intentionally remains a conservative family aggregate.
2. The compiler protocol already emitted `symbolic` dependency nodes with a
   symbolic vector reference, but the TypeScript client accepted only resolved,
   unresolved, and cycle nodes with concrete extensions. The client now accepts
   and presents the compiler-owned symbolic form without inferring a target.

The stage inspector had another ambiguity rather than a semantic error: it
drives `Lowerer` directly and therefore cannot show propagated facts. Its text
and JSON now label the result `direct-lowering`; `analyze`, the final `explain`
verdict, generated queries, and release coverage use the post-closure state.

## Fact ownership

| Fact | Canonical source/typed owner | Finalization | Projections |
| --- | --- | --- | --- |
| Authored callable identity | `Primitive.signature` and sorted `Primitive.attributes` in `catalog/model.py` | copied to `LoweredSpecialization.source_signature` and `.source_attributes` | exact analysis/editor selection and source provenance |
| Implementation state | `ImplementationState`, `RegionImplementationEffect`, and `ImplementationStateFacts` in `lower/implementation_facts.py`; registered TSIL effects in `lower/region_handlers/registry.py` | direct state is inferred during typed region lowering; `_pipeline_closure.py` joins live callees and capability alternatives conservatively | generated C++/Rust queries, concrete analysis, explain, target-support coverage; inspect labels only the direct state |
| Active dependencies | `CallDependency`, `CallDependencyOrigin`, and vector-reference types in `lower/dependencies.py`; region handlers record them in `LoweringEffects` | `_pipeline_closure.py` resolves the same keys used for pruning, retains symbolic edges, terminates cycles, and records unresolved origins | analysis tree, explain dependency verdicts, checked-companion admission, generated closure |
| Target features | `RequirementClause.flags`, extension activation, and `MachineProfile.features` | `Selector` chooses applicable requirements; closure unions requirements of live concrete callees | selection/explain, lowered model, backend attributes/flags, target-support evidence |
| Compiler capabilities | typed compiler requirements on `RequirementClause.compiler` plus backend capability registries | `Selector` chooses the capability frontier; closure preserves alternatives and propagates only requirements shared by alternative callee branches | explain/inspect, backend guards, generated compile probes, target-support realization identity |
| Safety | `ImplementationSafety` in `catalog/model.py`, typed primitive preconditions, and region/lowering effects | closure propagates unsafe-callee implementation boundaries and unresolved preconditions; public caller unsafety remains distinct from internal unsafe operations | Rust `unsafe`, ordinary/checked API planning, explain/inspect, generated documentation |
| Primitive semantics | typed arithmetic, operation, memory, conversion, shift, overload, operand-role, and precondition records under `catalog/` | `LoweredPrimitiveSemantics` carries finalized source facts across the backend-neutral boundary | checked guards, API planning, value tests, documentation, stage inspection |

Backends format these lowered values. They do not parse target text or classify
state, safety, dependencies, features, capabilities, or primitive semantics.
The VS Code client validates the JSON wire shape and presents labels/icons; it
does not select implementations or infer semantic state.

## Coarse generated query contract

The stable state set is `native | composed | fallback | unknown`:

- `native`: a direct target expression, operation, intrinsic, or intrinsic
  sequence in the selected body, including irreducible local representation
  mechanics;
- `composed`: typed primitive calls, control flow, or shared semantic regions;
- `fallback`: an explicit portable fallback body or fallback extension family;
- `unknown`: opaque target text or incomplete typed evidence prevents a
  stronger claim.

The propagated join is conservative: `fallback` dominates `unknown`, then
`composed`, then `native`. This is a structural classification. `native` does
not mean one machine instruction and none of the states is a performance
promise.

C++ exposes `tsl::implementation_state`,
`tsl::implementation_state_of<Primitive, Args...>::value`, and the
`tsl::implementation_state_v<Primitive, Args...>` shorthand. Generated profile
headers specialize the query. The unspecialized primary template returns
`unknown`, so an unrecognized C++ query fails closed.

Rust exposes `tsl_core::ImplementationState` and
`tsl_core::ImplementationStateOf<Primitive, Vec, Args>::VALUE`; the selected
profile implements the trait. Rust has no blanket implementation, so an
unsupported query is a compile-time error rather than a fabricated state.
Boolean axes and immediates use the generated `BoolArg`/integer argument
wrappers. The exact C++ and Rust examples and argument rules are documented in
`docs/tslc-cli.md`.

## Projection agreement and deterministic evidence

The following representative evidence is covered by focused tests and local
commands:

| Case | Evidence |
| --- | --- |
| Native | exact `add`, `v:=(v,v)`, AVX2 `si32` analysis has one root and reports `native`; the generated query is backed by the same propagated `LoweredSpecialization` |
| Composed | the unfiltered `add` family aggregate includes both masked callables and conservatively reports `composed`; exact callable filters prevent this aggregate from masquerading as the ordinary API |
| Fallback | classifier tests cover fallback extension families and explicit backend loops; the target-support snapshot records reviewed scalable fallback realizations |
| Unknown | opaque/unclassified-region tests produce `unknown`; `implementation_quality_gaps` rejects every emitted release realization with absent or unknown state |
| Unresolved | analysis retains a source-reasoned unresolved edge or root with state `unknown`; dependency pruning uses the same key and reason owner |
| Symbolic | analysis retains generic vector references with status/state `symbolic/unknown`; the editor parser and tree now accept that exact wire form |
| Determinism | two exact `add` JSON analyses from the same input snapshot are byte-identical; analysis unit tests prove deterministic cycles and symbolic edges |
| Generated query reachability | external CMake/FetchContent and Cargo path-dependency consumers compile and evaluate the C++ and Rust scalar `add` queries as `fallback` |

The maintained release gate is deliberately stricter than the general
analysis API: `coverage target-ratchet` treats an emitted `unknown` (or missing
state) as a quality gap, while a fallback in the accelerated core requires an
exact reviewed exception. General authoring tools still report unknown and
unresolved states instead of hiding or guessing them.

The complementary `coverage implementation-ratchet` covers every exact corpus
slot in every backend/profile scope of the v1 product contract. It maps
`fallback` to `generic_fallback`, and maps non-emitted or emitted-unknown
outcomes to `unsupported` while retaining the original pipeline stage, state,
and stable reason. The mapping consumes `TargetSupportEntry` directly and never
classifies rendered target text. Its baseline ratchets exact realization
identities and quality degradation; grouping identical records across profiles
is only a serialization compression. Every emitted unknown is also an absolute
quality failure, including during a baseline update.

## Deferred beyond v1

The coarse query does not expose a hazard list, dependency paths, temporary
storage, scalarization likelihood, cost, measured performance, or verification
attestation. Those remain compiler-side evidence or later v1.x design work.
If a capability manifest is added, deterministic compiler facts and
environment-specific verification attestations must remain separate.

## Local validation

- full Python suite: 2,826 passed, 126 skipped;
- focused implementation-state, analysis, explain, stage-dump, generated API,
  ratchet, declaration-manifest, and census tests: passed;
- generated C++/Rust external query consumers: 2 passed;
- generated scalar/AVX2 warning, lint, and documentation quality build: passed;
- VS Code unit tests: 23 passed plus 2 grammar tests;
- VS Code integration tests: 2 passed;
- mypy: 367 source files clean;
- corpus check, release contract, target-support ratchet, compileall, and
  `git diff --check`: passed.
