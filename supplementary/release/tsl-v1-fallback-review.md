# TSL v1 scalable-target fallback review

Status: reviewed implementation-quality exceptions for the v1 release
candidate. This record does not claim target-native performance parity.

## Policy and evidence boundary

The release contract classifies every stable callable identity as
accelerated-core, target-neutral portable utility, or target-specific. An
emitted accelerated-core realization classified as `fallback` is permitted
only when its exact callable identity occurs in
`accelerated_core.fallback_exceptions`. An emitted `unknown` realization is
never permitted. The exact target-support ratchet records the implementation
state for each profile, type, target, and conversion realization, so an
exception cannot hide a later `native` or `composed` to `fallback` regression.

The candidate snapshot records fallback realizations only under exact reviewed
accelerated-core identities and contains no unknown realizations. The only
additional fallback identity is `to_ostream#o:=(o,v,s)`, which is an explicitly
portable utility and therefore needs no accelerated-core exception.

The performance evidence in this review is structural: the compiler-owned
implementation graph and generated code identify whether a path uses native
vector dependencies, a lane loop, scalar memory operations, or fixed-profile
compatibility code. QEMU results are correctness evidence only. Native SVE and
RVV benchmark measurements remain mandatory release-attestation work in Slice
8; no number obtained under emulation may be presented as performance evidence.

## Reviewed exception groups

### Lane arithmetic and conversion

Exact identities:

- `abs#v:=(v)`
- `cast[cast=convert]#v:=v->base:ToBase`
- `convert_down[cast=convert,direction=down]#v:=(v,sImm)->base:ToBase`
- `convert_lanes#v:=v->vector:ToVec`
- `convert_up[cast=convert,direction=up]#v:=(v,sImm)->base:ToBase`
- `div#v:=(v,v)`
- `div[mask=pass_through]#v:=(m,v,v)`
- `div[mask=zero]#v:=(m,v,v)`
- `mod#v:=(v,v)`
- `mod[mask=pass_through]#v:=(m,v,v)`
- `mod[mask=zero]#v:=(m,v,v)`
- `mod_imm#v:=(v,sImm)`
- `mod_imm[mask=pass_through]#v:=(m,v,sImm)`
- `mod_imm[mask=zero]#v:=(m,v,sImm)`
- `load_convert_up#v:=cptr+->base:ToBase`

These identities have mixed realization quality. For example, scalable SVE
integer division is composed and floating division is native, while remaining
fixed-profile/type realizations retain fallback provenance. Lane conversions
currently use a vector-length loop with runtime lane extraction and insertion;
this is an intentionally conservative semantic implementation, especially for
the specified saturating/NaN conversion behavior. Modulo composes quotient,
multiplication, subtraction, and masking where available. The structural
performance risk is therefore explicit: conversion may be scalarized and
modulo/division cost may exceed one target instruction. Correctness coverage
includes signed, unsigned, floating, masked, width-changing, equal-lane, and
checked lane-count-mismatch cases. Baseline RVV `cast`, `convert_up`, and
`load_convert_up` deliberately stage runtime-VL lanes through typed temporary
storage. This closes the stable semantic surface without assuming VLEN or
inventing unsupported register multiplicities; direct widening/narrowing
recipes remain future optimizations where the concrete source/target pair has
an ISA mapping.

Decision: acceptable as a correctness-preserving v1 implementation, not as a
native-performance claim. Native measurements must prioritize
`convert_lanes`, integer division, and modulo.

### Indexed memory

Exact identities:

- `gather#v:=(cptr,vidx,sImm)`
- `gather[mask=pass_through]#v:=(m,cptr,vidx,v,sImm)`
- `gather_narrow#v:=(cptr,cptr,sImm)`
- `gather_narrow_partial#v:=(cptr,vidx,sImm)`
- `scatter#void:=(ptr,vidx,v,sImm)`
- `scatter[mask=zero]#void:=(m,ptr,vidx,v,sImm)`

The scalable implementations preserve runtime lane and predicate semantics but
use conservative store/load bridges and scalar element accesses in paths for
which the source model does not yet express one direct target intrinsic. Their
cost is O(runtime lanes), and irregular memory latency can dominate. The
generated suite exercises real `tsl::sve` index registers, pointer-index narrow
gathers, tiled masks, partial results, inactive lanes, misalignment,
out-of-range indices, checked error selection, and scatter no-write canaries.

Decision: acceptable because semantic availability and checked failure behavior
are complete and the fallback cost is disclosed. Native gather/scatter lowering
is a high-priority optimization candidate and must be measured against this
baseline on native SVE and RVV hardware.

### Permutation, compression, expansion, and conflicts

Exact identities:

- `compress[mask=zero,op=pack]#v:=(m,v)`
- `compress_store[aligned=true,op=pack]#void:=(m,ptr,v)`
- `conflict#v:=v`
- `conflict_free#m:=(m,v)`
- `expand[mask=pass_through,op=expand]#v:=(m,v,v)`
- `expand_load[aligned=true,op=expand]#v:=(m,cptr)`
- `mask_deinterleave_odd#m:=(m,m)`
- `align_right_lanes#v:=(v,v,sImm)`
- `interleave_lo#v:=(v,v)`
- `mask_interleave_lo#m:=(m,m)`
- `permute_lanes#v:=(v,sImm)`
- `permute_lanes#v:=(v,vidx)`
- `permute_lanes[mask=pass_through]#v:=(m,v,v,vidx)`
- `permute_lanes[mask=zero]#v:=(m,v,vidx)`
- `table_lookup#v:=(v,vidx,v)`
- `reverse#v:=(v)`

These are cross-lane algorithms. Their implementation graphs compose supported
vector comparisons, masks, selects, loads/stores, and lane operations, with
loops where the baseline ISA or current typed vocabulary has no direct mapping.
The likely performance lever is substantial: native compact/table operations or
better target-specific recipes can remove O(VL) work and temporary memory.
Value tests cover masks, ordering, inactive lanes, index selection, and scalable
tail behavior.

Decision: acceptable as explicitly non-native semantic baselines. Native
benchmarking should compare data distributions as well as vector lengths,
because mask density and conflict rate affect the useful speedup.

### Masked extrema reductions

Exact identities:

- `hmax#s:=(m,v)`
- `hmin#s:=(m,v)`

Unmasked RVV add, minimum, maximum, AND, and OR reductions use baseline-V
reduction intrinsics. Masked maximum and minimum retain a runtime-VL scalar
path because the public empty-mask result is zero, while an RVV masked
reduction always includes its scalar seed. Choosing a neutral seed is
type-specific and would also change the documented floating NaN and signed-zero
behavior. The conservative path tests the exact public semantics and makes its
O(VL) cost visible.

Decision: acceptable for v1 correctness. A later native recipe must prove
empty-mask, NaN, infinity, signed-zero, and integer-boundary equivalence before
it replaces this fallback.

### Baseline-V bit counts

Exact identities:

- `lzc#v:=v`
- `popcnt#v:=v`

The v1 RVV target promises baseline V 1.0 and explicitly excludes optional
extensions. Per-lane vector count-leading-zero and population-count operations
are supplied by Zvbb, so the baseline implementation uses correct typed
software composition instead of silently raising the target requirement.

Decision: acceptable and required for the advertised baseline-V surface. A
future Zvbb target extension should add native implementations without
replacing or weakening this baseline path.

### Integral-mask helpers

Exact identities:

- `extract_imask#im:=(im,usize)->base:ToBase`
- `insert_imask#im:=(imt,im,usize)->base:ToBase`
- `lzc_imask#usize:=m`
- `overlay_imask#im:=(im,im,usize)`
- `shift_left_imask#im:=(im,usize)`
- `shift_right_imask#im:=(im,usize)`
- `tzc#usize:=m`

These operations manipulate the public integral-mask representation or reduce
a predicate to a scalar count. They are not data-lane arithmetic and may need
multiple mask chunks for scalable vectors. Fixed-SVE base-width extraction and
insertion walk the source predicate and rebuild the destination predicate with
typed mask operations; this is required because SVE's integral-mask policy is
the native predicate rather than a scalar bitset. Their structural cost is
bounded by the represented lane or mask-chunk count and is visible as fallback
rather than being mislabeled target-native. Edge tests cover zero, width-sized
shifts, runtime predicate lengths, replacement, clipping, and base-width
changes.

Decision: acceptable. Native measurements should confirm that these helpers do
not dominate mask-heavy algorithms.

### Fixed-profile representation compatibility

Exact identities:

- `extract[cast=reinterpret]#v:=(v,sImm)->extension:ToExtension`
- `set#v:=(lanes<s>)`

These fallbacks occur only in fixed SVE profile realizations, not the runtime
scalable `sve` contract. They preserve the legacy fixed-shape surface with
compile-time lane materialization or representation extraction. Runtime-scalable
fixed-shape forms are explicitly excluded by the release support contract.

Decision: acceptable for SVE128/SVE256/SVE512 compatibility. They must not be
used as evidence for vector-length-agnostic support.

## Reproducible checks

The review is backed by these repository-root commands:

```bash
./dev.sh check --profile sve --backend cpp --strict
./dev.sh check --profile rvv --backend cpp --strict
./dev.sh target-ratchet --require-complete
./dev.sh test --primitives gather,gather_narrow_partial,scatter,extract_value_at,insert_value_at,set_mask_lane,load,store --profiles sve --backends cpp
./dev.sh test --profiles rvv --backends cpp --output-root ./tslctmp/rvv-slice7
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_value_tests.py -k sve_runtime_semantics
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_rvv_downstream_consumer.py
```

The focused SVE gate cross-compiles a real project and runs it with
`qemu-aarch64`. The full RVV gate cross-compiles all 19,643 specializations and
runs all 4,448 planned cases with `qemu-riscv64`; the same binary also passes at
VLEN 256 and 512. Together they include scalable lane extraction/insertion,
predicate-lane mutation, indexed loads/stores, partial gather, equal-width
conversion, checked lane-count mismatch, checked index bounds and alignment,
inactive mask lanes, tail lanes, and scatter failure no-write behavior. The
[RVV evidence record](tsl-v1-rvv-evidence.md) captures the exact inventory and
generic downstream-consumer boundary.

Before the final v1.0.0 tag, Slice 8 must append native benchmark attestations
for representative identities from every group. If those runs expose an
unacceptable fallback cost, that fact is a release decision: optimize the path
or narrow the advertised performance claim; do not reclassify it as native.
