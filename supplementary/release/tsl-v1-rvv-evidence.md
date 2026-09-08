# TSL v1 RVV semantic-coverage evidence

Date: 2026-09-08

Status: compiler, generated-product, emulator, and CHORYS-shaped consumer
evidence complete. Native RVV hardware and the actual CHORYS integration remain
mandatory release-candidate attestations; this document does not claim them.

## Support boundary

The v1 RVV contract is the repository's RV64 baseline V 1.0 profile with
ELEN=64 and the stable TSL scalar-type set. Optional extensions such as Zvbb
are not silently added to that baseline. Operations without a baseline-V
instruction retain a typed, reviewed composed or fallback implementation.

All scalable implementations derive their working lane counts from the active
RVV vector type. They do not encode a fixed VLEN. Width-changing paths use the
typed source and destination vector shapes; indexed-memory paths use the typed
index-vector shape and preserve inactive-lane non-access semantics.

## Safety boundary

The RVV slice adds implementations; it does not change any pre-existing
implementation's safety declaration. Of the 115 new RVV implementation leaves,
13 are caller-unsafe, and all 13 belong to raw-pointer APIs such as load/store,
gather/scatter, compacted memory, conversion load, or byte copy. Those primitive
identities were already caller-unsafe on their existing targets. RVV merely makes
the same unchecked contract available for the new profile, with a checked
companion wherever the typed preconditions can be represented completely.

`internal_unsafe` is not a caller contract. A specialization that stages lanes
through compiler-owned runtime storage is still safe to call when all raw-pointer
preconditions are discharged inside the implementation. The flag records that a
generated body needs an internal unsafe-operation boundary; `caller_unsafe`
records a raw body/signature obligation that escapes to the caller. Typed
catastrophic preconditions, such as a runtime lane index, independently make the
ordinary public call unchecked and cause an honest `_checked` companion to be
planned. This is also the compiler's effective treatment of the older scalable
SVE fallbacks, even where their source-authored metadata has not yet been
reconciled with inferred facts.

One separate compile-time contract remains scheduled for Slice 9:
`convert_up`/`convert_down` chunk indices need a typed width-dependent range and
an invalid-instantiation diagnostic. They must not be silently clamped, and the
compile-time immediate does not justify a runtime `_checked` overload.

## Exact support result

The compiler-owned target ratchet reports the following RVV-only inventory:

| Fact | Result |
| --- | ---: |
| Exact callable slots | 1,753 |
| Realization outcomes | 1,904 |
| Emitted | 1,904 |
| Absent, pruned, or deferred | 0 |
| Native | 374 |
| Composed | 944 |
| Reviewed fallback | 586 |
| Unknown | 0 |
| Reviewed fixed-shape exclusions | 26 |
| Unreviewed implementation-quality gaps | 0 |

The exclusions are public contract facts for shapes that cannot honestly be
represented by a runtime-sized scalable register. They are not failed lowering
attempts. The implementation-state counts are deliberately separate: exact
semantic availability does not imply that every operation is one native RVV
instruction.

Strict RVV C++ checking lowers 19,643 specializations and reports only 30
reviewed unsupported fixed-shape selections. The exact fallback identities and
their structural performance risks are recorded in
[`tsl-v1-fallback-review.md`](tsl-v1-fallback-review.md).

## Generated value evidence

The full generated RVV C++ corpus contains 19,643 specializations and 4,448
planned value cases. It cross-compiles warning-clean and the same generated
`tsl_values` binary passes under QEMU at VLEN 128, 256, and 512 with ELEN 64.

This run covers foundation and representation operations, integer and floating
arithmetic, reductions, masks and tails, indexed memory, permutation,
compression/expansion, conflicts, conversions, runtime lane counts, and the
ordinary and checked error paths represented by generated value tests. QEMU is
correctness evidence only; it is not performance evidence.

During the full run, scalable scatter exposed a verifier defect: its scalar
expected buffer replayed the authored fixed lane count instead of the active
runtime VL. The renderer now constructs the oracle by replaying exactly the
runtime lanes in order, including repeated indices, byte scaling, and tiled
masks. A focused planning test ratchets that behavior.

## CHORYS-shaped consumer

[`chorys_rvv_kernel.cpp`](../../tslc/tests/fixtures/release/chorys_rvv_kernel.cpp)
is a generated-library consumer at the same boundary used by a CHORYS-style
RISC-V integration:

- it loads two runtime-VL vectors and applies an add/multiply transform through
  the ordinary API;
- it repeats the transform through checked loads and a checked store;
- it compares every output lane with an independent scalar oracle; and
- it verifies insufficient-span errors and the checked store's no-write
  canary.

The consumer cross-compiles with the RVV GCC toolchain under `-Wall -Wextra
-Werror` and the same binary passes under QEMU at VLEN 128 and 256.

This is deliberately called *CHORYS-shaped*. The upstream CHORYS kernel and a
native RVV machine are not present in this repository. Before `v1.0.0`, the
actual integration must be built against the same generated-input identity and
must agree with its scalar oracle on native hardware.

## Reproducible commands

Run from the repository root:

```bash
./dev.sh target-ratchet --require-complete --profile rvv
PYTHONPATH=tslc/src python -m tslc check --profile rvv --backend cpp --strict
./dev.sh test --profiles rvv --backends cpp \
  --output-root ./tslctmp/rvv-slice7

timeout --signal=KILL 60s qemu-riscv64 \
  -L /usr/riscv64-linux-gnu \
  -cpu max,v=true,vext_spec=v1.0,vlen=256,elen=64 \
  ./tslctmp/rvv-slice7/cpp/build/rvv/tsl_values
timeout --signal=KILL 60s qemu-riscv64 \
  -L /usr/riscv64-linux-gnu \
  -cpu max,v=true,vext_spec=v1.0,vlen=512,elen=64 \
  ./tslctmp/rvv-slice7/cpp/build/rvv/tsl_values

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_chorys_rvv_consumer.py
```

The profile-owned generated test supplies the VLEN=128 run. Slice 8 must move
all three vector lengths into typed verifier runner variants so these commands
and CI consume one reusable matrix rather than workflow or shell knowledge.

## Open release attestations

- Run the full RVV value suite on native baseline-V hardware and record the
  machine, compiler, flags, semantic-manifest digest, and exact outcome.
- Build and run the actual CHORYS integration kernel against the same generated
  product and scalar oracle.
- Benchmark the exact fallback groups on native hardware. If cost invalidates a
  performance claim, optimize the implementation or narrow that claim; do not
  relabel a fallback as native.
