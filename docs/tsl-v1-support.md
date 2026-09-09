# TSL generated C++/Rust library 1.0.0 support contract

This file is generated from the typed TSL catalog, machine profiles, support
policy, public-API baseline, package metadata, and
`supplementary/release/tsl-v1-policy.json`. Do not edit it by hand.

Release status: **release-candidate**.

## Product and component versions

The generated C++/Rust library is the product carrying `1.0.0`. `tslc` and
the VS Code extension have independent compatibility policies and remain on
their own `0.x` version lines.

| Component | Version | Compatibility |
| --- | --- | --- |
| Generated TSL library | `1.0.0` | stable v1 product |
| `tslc` | `0.1.0a1` | independent |
| `vscode-tsl` | `0.1.1` | independent |

## Backend/profile/type matrix

Every listed profile supports the stable scalar element domain shown in
its row. Individual primitive signatures can narrow that domain through
their source-owned type groups; the exact callable table and reviewed slot
exclusions below remain authoritative for those cases.

| Backend | Release profile rule | Profile | Target family | Shape | Stable scalar element types |
| --- | --- | --- | --- | --- | --- |
| `cpp` | `all_supported` | `neon` | `aarch64` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sve` | `aarch64` | runtime-scalable | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sve128` | `aarch64` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sve256` | `aarch64` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sve512` | `aarch64` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `scalar` | `generic` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `rvv` | `riscv` | runtime-scalable | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `wasm32-simd128` | `wasm32` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `avx` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `avx2` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `cannonlake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `cascadelake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `cascadelake-oneapi` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `cooperlake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `cooperlake-oneapi` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `icelake_rockerlake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `icelake_rockerlake-oneapi` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `kml` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `knl` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sapphire_emerald_granite_rapids` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sapphire_emerald_granite_rapids-oneapi` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `skylake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `skylake-oneapi` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sse` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sse2` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `sse3` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `tigerlake` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `zen4` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `cpp` | `all_supported` | `zen5` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `avx` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `avx2` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `knl` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `sse` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `sse2` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |
| `rust` | `explicit` | `sse3` | `x86` | fixed/static | `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64` |

The Rust rows name emitted physical profiles. Every generated Rust package
also contains the compiler-created generic fallback selected when no emitted
target-feature predicate matches; it is not a separately requested machine
profile or Cargo feature.

C++ v1 includes the declared SVE, fixed-width SVE, and RV64 Vector 1.0
profiles below. These claims do not imply SVE2, undeclared optional RVV
extensions or LMULs, or stable Rust SVE/RVV.

| Scope | Backend | Profile → target extension | Runtime-scalable profiles | Excludes |
| --- | --- | --- | --- | --- |
| `arm-sve` | `cpp` | `sve` → `sve`, `sve128` → `sve128`, `sve256` → `sve256`, `sve512` → `sve512` | `sve` | SVE2; stable Rust SVE |
| `riscv-vector` | `cpp` | `rvv` → `rvv` | `rvv` | optional RVV extensions; LMUL values other than the declared LMUL=1 profile; stable Rust RVV |

## Stable callable universe

- Scalar types: `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`, `f32`, `f64`.
- Primitive callable families: 185.
- Algorithm callable families: 44.
- Accelerated-core callable families: 177.
- Portable utility callable families: 7.
- Portable utility names: `allocate`, `allocate_aligned`, `custom_sequence`, `deallocate`, `memory_cp`, `sequence`, `to_ostream`.
- Fixed-shape signature kinds: `lanes<s>`, `s[]`.

The exact callable-family records below are projected from
`coverage/tsl-v1-public-api.json`; generated projects also carry their
scope-exact backend declaration manifests.

Public-API baseline SHA-256: `d980572e9061775302913d2962c7dbb3a2e917972dfd03a062de749c32c5e7f4`.

### Primitive callable families

| Identity | Checked | Fixed-shape only | Semantic categories |
| --- | --- | --- | --- |
| `abs#v:=(v)` | no | no | not yet annotated |
| `add#v:=(v,v)` | no | no | arithmetic |
| `add[mask=pass_through]#v:=(m,v,v)` | no | no | arithmetic |
| `add[mask=zero]#v:=(m,v,v)` | no | no | arithmetic |
| `align_right_lanes#v:=(v,v,sImm)` | no | no | not yet annotated |
| `allocate#ptr:=(usize)` | no | no | not yet annotated |
| `allocate_aligned#ptr:=(usize,usize)` | no | no | not yet annotated |
| `between_exclusive#m:=(v,v,v)` | no | no | not yet annotated |
| `between_exclusive[mask=zero]#m:=(m,v,v,v)` | no | no | not yet annotated |
| `between_inclusive#m:=(v,v,v)` | no | no | not yet annotated |
| `between_inclusive[mask=zero]#m:=(m,v,v,v)` | no | no | not yet annotated |
| `between_left_inclusive#m:=(v,v,v)` | no | no | not yet annotated |
| `between_left_inclusive[mask=zero]#m:=(m,v,v,v)` | no | no | not yet annotated |
| `between_right_inclusive#m:=(v,v,v)` | no | no | not yet annotated |
| `between_right_inclusive[mask=zero]#m:=(m,v,v,v)` | no | no | not yet annotated |
| `binary_and#v:=(v,v)` | no | no | operation |
| `binary_and[mask=pass_through]#v:=(m,v,v)` | no | no | operation |
| `binary_and[mask=zero]#v:=(m,v,v)` | no | no | operation |
| `binary_andnot#v:=(v,v)` | no | no | operation |
| `binary_andnot[mask=pass_through]#v:=(m,v,v)` | no | no | operation |
| `binary_andnot[mask=zero]#v:=(m,v,v)` | no | no | operation |
| `binary_or#v:=(v,v)` | no | no | operation |
| `binary_or[mask=pass_through]#v:=(m,v,v)` | no | no | operation |
| `binary_or[mask=zero]#v:=(m,v,v)` | no | no | operation |
| `binary_xor#v:=(v,v)` | no | no | operation |
| `binary_xor[mask=pass_through]#v:=(m,v,v)` | no | no | operation |
| `binary_xor[mask=zero]#v:=(m,v,v)` | no | no | operation |
| `blend_add[mask=pass_through]#v:=(m,v,v,v)` | no | no | not yet annotated |
| `cast[cast=convert]#v:=v->base:ToBase` | no | no | operation, conversion |
| `compress[mask=zero,op=pack]#v:=(m,v)` | no | no | not yet annotated |
| `compress_store[aligned=true,op=pack]#void:=(m,ptr,v)` | yes | no | operation, memory |
| `concat#v:=(v,v)->extension:ToExtension` | no | no | not yet annotated |
| `conflict#v:=v` | no | no | not yet annotated |
| `conflict_free#m:=(m,v)` | no | no | not yet annotated |
| `convert_down[cast=convert,direction=down]#v:=(v,sImm)->base:ToBase` | no | no | not yet annotated |
| `convert_lanes#v:=v->vector:ToVec` | yes | no | operation, conversion |
| `convert_up[cast=convert,direction=up]#v:=(v,sImm)->base:ToBase` | no | no | not yet annotated |
| `count_matches#s:=(v,s)` | no | no | not yet annotated |
| `custom_sequence#v:=(s,s)` | no | no | not yet annotated |
| `deallocate#void:=(ptr)` | no | no | not yet annotated |
| `div#v:=(v,v)` | yes | no | arithmetic |
| `div[mask=pass_through]#v:=(m,v,v)` | yes | no | arithmetic |
| `div[mask=zero]#v:=(m,v,v)` | yes | no | arithmetic |
| `equal#m:=(v,v)` | no | no | operation |
| `equal[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `expand[mask=pass_through,op=expand]#v:=(m,v,v)` | no | no | not yet annotated |
| `expand_load[aligned=true,op=expand]#v:=(m,cptr)` | yes | no | operation, memory |
| `extract[cast=reinterpret]#v:=(v,sImm)->extension:ToExtension` | no | no | not yet annotated |
| `extract_imask#im:=(im,usize)->base:ToBase` | no | no | not yet annotated |
| `extract_imask#im:=(im,usize)->extension:ToExtension` | no | no | not yet annotated |
| `extract_value#s:=v[idx]` | no | no | operation |
| `extract_value_at#s:=(v,usize)` | yes | no | operation |
| `from_array#v:=s[]` | no | yes | operation |
| `gather#v:=(cptr,vidx,sImm)` | yes | no | operation, memory |
| `gather[mask=pass_through]#v:=(m,cptr,vidx,v,sImm)` | yes | no | operation, memory |
| `gather_narrow#v:=(cptr,cptr,sImm)` | no | no | not yet annotated |
| `gather_narrow_partial#v:=(cptr,vidx,sImm)` | yes | no | operation, memory |
| `greater_than#m:=(v,v)` | no | no | operation |
| `greater_than[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `greater_than_or_equal#m:=(v,v)` | no | no | operation |
| `greater_than_or_equal[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `hadd#s:=(m,v)` | no | no | operation |
| `hadd#s:=v` | no | no | operation |
| `hand#s:=(m,v)` | no | no | operation |
| `hand#s:=v` | no | no | operation |
| `hmax#s:=(m,v)` | no | no | operation |
| `hmax#s:=v` | no | no | operation |
| `hmin#s:=(m,v)` | no | no | operation |
| `hmin#s:=v` | no | no | operation |
| `hor#s:=(m,v)` | no | no | operation |
| `hor#s:=v` | no | no | operation |
| `insert[cast=reinterpret]#v:=(vt,v,sImm)->extension:ToExtension` | no | no | not yet annotated |
| `insert_imask#im:=(imt,im,usize)->base:ToBase` | no | no | not yet annotated |
| `insert_imask#im:=(imt,im,usize)->extension:ToExtension` | no | no | not yet annotated |
| `insert_value#v:=(v,s)` | no | no | operation |
| `insert_value_at#v:=(v,usize,s)` | yes | no | operation |
| `interleave_lo#v:=(v,v)` | no | no | not yet annotated |
| `inv#v:=v` | no | no | operation |
| `inv[mask=pass_through]#v:=(m,v)` | no | no | operation |
| `inv[mask=zero]#v:=(m,v)` | no | no | operation |
| `less_than#m:=(v,v)` | no | no | operation |
| `less_than[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `less_than_or_equal#m:=(v,v)` | no | no | operation |
| `less_than_or_equal[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `load[aligned=false,mask=pass_through]#v:=(m,cptr,v)` | yes | no | operation, memory |
| `load[aligned=false,mask=zero]#v:=(m,cptr)` | yes | no | operation, memory |
| `load[aligned=false]#v:=cptr` | yes | no | operation, memory |
| `load[aligned=true,mask=pass_through]#v:=(m,cptr,v)` | yes | no | operation, memory |
| `load[aligned=true,mask=zero]#v:=(m,cptr)` | yes | no | operation, memory |
| `load[aligned=true]#v:=cptr` | yes | no | operation, memory |
| `load_convert_up#v:=cptr+->base:ToBase` | yes | no | operation, memory |
| `load_mask_repr[aligned=false,packed=false]#m:=cptr` | no | no | not yet annotated |
| `load_mask_repr[aligned=false,packed=true]#m:=cptr` | no | no | not yet annotated |
| `load_mask_repr[aligned=true,packed=false]#m:=cptr` | no | no | not yet annotated |
| `load_mask_repr[aligned=true,packed=true]#m:=cptr` | no | no | not yet annotated |
| `load_scalar[aligned=false]#s:=cptr` | yes | no | operation, memory |
| `lzc#v:=v` | no | no | not yet annotated |
| `lzc_imask#usize:=m` | no | no | not yet annotated |
| `lzc_scalar#usize:=s` | no | no | not yet annotated |
| `mask_binary_and#m:=(m,m)` | no | no | operation |
| `mask_binary_not#m:=m` | no | no | operation |
| `mask_binary_or#m:=(m,m)` | no | no | operation |
| `mask_binary_xor#m:=(m,m)` | no | no | operation |
| `mask_deinterleave_odd#m:=(m,m)` | no | no | not yet annotated |
| `mask_false[value=zero]#m:=()` | no | no | operation |
| `mask_interleave_lo#m:=(m,m)` | no | no | not yet annotated |
| `mask_population_count#usize:=m` | no | no | operation |
| `mask_true[value=all]#m:=()` | no | no | operation |
| `masked_set1[mask=zero]#v:=(m,v,s)` | no | no | not yet annotated |
| `max#v:=(v,v)` | no | no | not yet annotated |
| `memory_cp#void:=(ptr,cptr,s,s)` | no | no | not yet annotated |
| `min#v:=(v,v)` | no | no | not yet annotated |
| `mod#v:=(v,v)` | yes | no | arithmetic |
| `mod[mask=pass_through]#v:=(m,v,v)` | yes | no | arithmetic |
| `mod[mask=zero]#v:=(m,v,v)` | yes | no | arithmetic |
| `mod_imm#v:=(v,sImm)` | no | no | arithmetic |
| `mod_imm[mask=pass_through]#v:=(m,v,sImm)` | no | no | arithmetic |
| `mod_imm[mask=zero]#v:=(m,v,sImm)` | no | no | arithmetic |
| `mov[mask=pass_through]#v:=(m,v,v)` | no | no | not yet annotated |
| `mov[mask=zero,op=keep]#v:=(m,v)` | no | no | not yet annotated |
| `mul#v:=(v,v)` | no | no | arithmetic |
| `mul[mask=pass_through]#v:=(m,v,v)` | no | no | arithmetic |
| `mul[mask=zero]#v:=(m,v,v)` | no | no | arithmetic |
| `mul_imm#v:=(v,sImm)` | no | no | not yet annotated |
| `mul_imm[mask=pass_through]#v:=(m,v,sImm)` | no | no | not yet annotated |
| `mul_imm[mask=zero]#v:=(m,v,sImm)` | no | no | not yet annotated |
| `neg#v:=v` | no | no | arithmetic |
| `nequal#m:=(v,v)` | no | no | operation |
| `nequal[mask=zero]#m:=(m,v,v)` | no | no | operation |
| `overlay_imask#im:=(im,im,usize)` | no | no | not yet annotated |
| `permute_lanes#v:=(v,sImm)` | no | no | not yet annotated |
| `permute_lanes#v:=(v,vidx)` | no | no | not yet annotated |
| `permute_lanes[mask=pass_through]#v:=(m,v,v,vidx)` | no | no | not yet annotated |
| `permute_lanes[mask=zero]#v:=(m,v,vidx)` | no | no | not yet annotated |
| `popcnt#v:=v` | no | no | not yet annotated |
| `random_step#usize:=(ptr)` | yes | no | operation, memory |
| `reinterpret[cast=reinterpret]#v:=v->base:ToBase` | no | no | operation, conversion |
| `resize_down#v:=v->extension:ToExtension` | no | no | not yet annotated |
| `resize_up_undef[value=undef]#v:=v->extension:ToExtension` | no | no | not yet annotated |
| `resize_up_zero[value=zero]#v:=v->extension:ToExtension` | no | no | not yet annotated |
| `reverse#v:=(v)` | no | no | not yet annotated |
| `scatter#void:=(ptr,vidx,v,sImm)` | yes | no | operation, memory |
| `scatter[mask=zero]#void:=(m,ptr,vidx,v,sImm)` | yes | no | operation, memory |
| `select[mask=pass_through]#v:=(m,v,v)` | no | no | operation |
| `sequence#v:=()` | no | no | not yet annotated |
| `set#v:=(lanes<s>)` | no | yes | not yet annotated |
| `set1#v:=s` | no | no | operation |
| `set_mask_lane#m:=(m,usize,usize)` | yes | no | operation |
| `set_undef[value=undef]#v:=()` | no | no | not yet annotated |
| `set_zero[value=zero]#v:=()` | no | no | operation |
| `shift_left#v:=(v,s)@count_distribution=uniform:primary` | no | no | operation |
| `shift_left#v:=(v,sImm)@count_distribution=uniform` | no | no | operation |
| `shift_left#v:=(v,v)@count_distribution=per_lane` | no | no | operation |
| `shift_left[mask=pass_through]#v:=(m,v,sImm)@count_distribution=uniform` | no | no | operation |
| `shift_left_imask#im:=(im,usize)` | no | no | not yet annotated |
| `shift_left_wrapping#v:=(v,s)@count_distribution=uniform:primary` | no | no | operation, shift |
| `shift_left_wrapping#v:=(v,v)@count_distribution=per_lane` | no | no | operation, shift |
| `shift_right#v:=(v,s)@count_distribution=uniform:primary` | no | no | operation |
| `shift_right#v:=(v,sImm)@count_distribution=uniform` | no | no | operation |
| `shift_right#v:=(v,v)@count_distribution=per_lane` | no | no | operation |
| `shift_right_imask#im:=(im,usize)` | no | no | not yet annotated |
| `shift_right_wrapping#v:=(v,s)@count_distribution=uniform:primary` | no | no | operation, shift |
| `shift_right_wrapping#v:=(v,v)@count_distribution=per_lane` | no | no | operation, shift |
| `store[aligned=false,mask=pass_through]#void:=(m,ptr,v)@payload_extent=vector` | yes | no | operation, memory |
| `store[aligned=false]#void:=(ptr,s)@payload_extent=scalar` | yes | no | operation, memory |
| `store[aligned=false]#void:=(ptr,v)@payload_extent=vector:primary` | yes | no | operation, memory |
| `store[aligned=true,mask=pass_through]#void:=(m,ptr,v)@payload_extent=vector` | yes | no | operation, memory |
| `store[aligned=true]#void:=(ptr,s)@payload_extent=scalar` | yes | no | operation, memory |
| `store[aligned=true]#void:=(ptr,v)@payload_extent=vector:primary` | yes | no | operation, memory |
| `store_mask_repr[aligned=false,packed=false]#void:=(ptr,m)` | no | no | not yet annotated |
| `store_mask_repr[aligned=false,packed=true]#void:=(ptr,m)` | no | no | not yet annotated |
| `store_mask_repr[aligned=true,packed=false]#void:=(ptr,m)` | no | no | not yet annotated |
| `store_mask_repr[aligned=true,packed=true]#void:=(ptr,m)` | no | no | not yet annotated |
| `sub#v:=(v,v)` | no | no | arithmetic |
| `sub[mask=pass_through]#v:=(m,v,v)` | no | no | arithmetic |
| `sub[mask=zero]#v:=(m,v,v)` | no | no | arithmetic |
| `table_lookup#v:=(v,vidx,v)` | no | no | not yet annotated |
| `test_imask#im:=(im,usize)` | no | no | operation |
| `to_array#s[]:=v` | no | yes | operation |
| `to_integral#im:=m` | no | no | operation |
| `to_mask#m:=im` | no | no | operation |
| `to_ostream#o:=(o,v,s)` | no | no | not yet annotated |
| `to_vector#v:=m` | no | no | not yet annotated |
| `tzc#usize:=m` | no | no | not yet annotated |
| `unequal_zero[value=zero]#m:=v` | no | no | not yet annotated |

### Algorithm callable families

`aggregate_binary`, `aggregate_masked_binary`, `aggregate_masked_unary`, `aggregate_selected_binary`, `aggregate_selected_unary`, `aggregate_unary`, `bit_mask_count`, `byte_mask_count`, `consume_binary`, `consume_masked_binary`, `consume_masked_unary`, `consume_selected_binary`, `consume_selected_unary`, `consume_unary`, `count_binary`, `count_masked_binary`, `count_masked_unary`, `count_selected_binary`, `count_selected_unary`, `count_unary`, `for_each_chunk`, `integral_mask_chunk_count`, `mask_chunk_count`, `native_mask_chunk_count`, `predicate_binary`, `predicate_unary`, `select_binary`, `select_indices_binary`, `select_indices_unary`, `select_masked_binary`, `select_masked_indices_binary`, `select_masked_indices_unary`, `select_masked_unary`, `select_selected_indices_binary`, `select_selected_indices_unary`, `select_unary`, `transform_binary`, `transform_masked_binary`, `transform_masked_unary`, `transform_selected_binary`, `transform_selected_unary`, `transform_unary`, `transform_where_binary`, `transform_where_unary`.

### Target-specific callables

- `random_step`: x86 RDRAND operation with no portable fallback.

### Reviewed target-slot exclusions

- `TSL-V1-RUNTIME-SCALABLE-FIXED-WIDTH-REPRESENTATION` (sve, rvv/cpp; concat#v:=(v,v)->extension:ToExtension, extract[cast=reinterpret]#v:=(v,sImm)->extension:ToExtension, extract_imask#im:=(im,usize)->base:ToBase, extract_imask#im:=(im,usize)->extension:ToExtension, insert[cast=reinterpret]#v:=(vt,v,sImm)->extension:ToExtension, insert_imask#im:=(imt,im,usize)->base:ToBase, insert_imask#im:=(imt,im,usize)->extension:ToExtension, resize_down#v:=v->extension:ToExtension, resize_up_undef[value=undef]#v:=v->extension:ToExtension, resize_up_zero[value=zero]#v:=v->extension:ToExtension; types all): The callable changes between statically ordered register widths or fixed mask windows and has no truthful meaning for one runtime-scalable register type.
- `TSL-V1-FIXED-SVE-NO-COMPATIBLE-WIDTH` (sve128, sve256, sve512/cpp; concat#v:=(v,v)->extension:ToExtension, extract[cast=reinterpret]#v:=(v,sImm)->extension:ToExtension, extract_imask#im:=(im,usize)->extension:ToExtension, insert[cast=reinterpret]#v:=(vt,v,sImm)->extension:ToExtension, insert_imask#im:=(imt,im,usize)->extension:ToExtension, resize_down#v:=v->extension:ToExtension, resize_up_undef[value=undef]#v:=v->extension:ToExtension, resize_up_zero[value=zero]#v:=v->extension:ToExtension; types all): A fixed-SVE profile emits exactly one fixed-SVE register width, so no distinct same-family source or destination width exists for this representation-change callable.
- `TSL-V1-NO-WIDER-SCALAR-TYPE` (sve, sve128, sve256, sve512, rvv/cpp; convert_up[cast=convert,direction=up]#v:=(v,sImm)->base:ToBase, load_convert_up#v:=cptr+->base:ToBase; types si64, ui64, f64): The stable scalar domain has no wider target lane type for these source types.
- `TSL-V1-NO-WIDER-SCALAR-TYPE` (sve128, sve256, sve512/cpp; extract_imask#im:=(im,usize)->base:ToBase; types si64, ui64, f64): The stable scalar domain has no wider target lane type for these source types.
- `TSL-V1-NO-NARROWER-SCALAR-TYPE` (sve, sve128, sve256, sve512, rvv/cpp; convert_down[cast=convert,direction=down]#v:=(v,sImm)->base:ToBase; types si8, ui8, f32): The stable scalar domain has no supported narrower target lane type for these source types.
- `TSL-V1-NO-NARROWER-SCALAR-TYPE` (sve128, sve256, sve512/cpp; insert_imask#im:=(imt,im,usize)->base:ToBase; types si8, ui8): The stable scalar domain has no supported narrower target lane type for these source types.

## Safety API

Unsuffixed calls perform the operation directly and do not sanitize inputs.
Documented caller preconditions remain the caller's responsibility. A
`*_checked` companion exists only when all applicable catastrophic runtime
preconditions are complete, checkable, and representable. Operations without
such a precondition deliberately have no checked twin.

C++ value-returning checked calls return the ordinary scalar/vector/register
type directly and report through a final `precondition_error&`. On failure the
ordinary operation is not invoked and the returned object is initialized but
semantically unspecified: inspect the error before using it. Void checked calls
return `precondition_error` directly.

Rust checked calls return `Result<T, PreconditionError>` or
`Result<(), PreconditionError>`. An unsuffixed Rust function is `unsafe` only
when the caller owns an outstanding catastrophic obligation. Internal raw-memory
staging (`internal_unsafe`/`raw_memory`) does not by itself make the public Rust
function unsafe; raw-pointer validity or another typed caller precondition does.
A checked range or slice cannot prove forged-reference validity, object lifetime,
provenance, or freedom from concurrent mutation.

## Implementation quality policy

The accelerated core contains every stable primitive family except the
explicit target-neutral utility names above and target-specific callables.
This conservative default prevents incomplete semantic annotations from
silently weakening the quality gate. A fallback in that set is forbidden
unless its exact identity is a
reviewed exception with correctness and performance evidence. There are
currently 50 exceptions.
Their review record is `supplementary/release/tsl-v1-fallback-review.md`.

The coarse implementation-state meanings are:

- `native`: the selected body is one direct expression or one target intrinsic
- `composed`: the selected body composes typed primitive calls, control flow, or multiple direct operations
- `fallback`: the selected extension family or lowered body explicitly uses a portable fallback
- `unknown`: opaque target text or incomplete typed evidence prevents a stronger claim
