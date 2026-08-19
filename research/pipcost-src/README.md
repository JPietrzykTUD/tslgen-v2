# PIPCost

PIPCost is a downstream research prototype for the fixed columnar query:

```sql
SELECT SUM(c) FROM t WHERE a < p1 AND b > p2;
```

Its immediate purpose is deliberately narrow: determine whether the best
materialized active-row representation changes predictably with selectivity,
working set, batch size, and SIMD width. It is seed evidence for a possible
representation-aware pipeline optimizer, not a query engine and not evidence
that such an optimizer is already useful.

## What actually uses TSL

The SIMD candidates are not handwritten intrinsic kernels:

- `batch_native_mask`, `batch_integral_mask`, and `batch_bitmask` call TSL's
  `predicate_binary` and `aggregate_masked_unary` algorithms with different
  TSL mask-layout types;
- `batch_positions_u32` calls TSL's `select_indices_binary` and
  `aggregate_selected_unary` algorithms;
- their `full_*` counterparts use the same TSL algorithms with relation-wide
  materialization;
- `fused_mask` uses generated TSL primitives (`load`, `set1`, `less_than`,
  `mask_binary_and`, `select`, and `hadd`) in one non-materializing loop.

Native mask materialization is supported through
`tsl::algo::mask_layout::native`; it is not a prototype-specific mask encoding.

Generation defaults to the repository's stable TSL tag `v0.2.7`. PIPCost
resolves that tag to an exact commit, extracts only the compiler, source corpus,
and machine-profile catalog below `tslctmp/pipcost/tsl-sources/`, and launches
an isolated generator process with that snapshot's `tslc.api`. Every generated
manifest records the requested TSL ref, resolved commit, source-tree digest,
compiler-package version, compiler coverage, and artifact digests.

`v0.2.7` is the TSL repository release. The `tslc` Python package inside that
release still declares version `0.1.0a1`; these are different version
namespaces. The Python dependency therefore remains `tslc==0.1.0a1`, while the
experiment and generated evidence explicitly pin TSL `v0.2.7`.

## Clean experimental roles

Each study distinguishes two roles:

- `candidate_plans` are semantically comparable alternatives that the oracle
  and fitted model may choose;
- `reference_plans` are measured controls, never optimizer candidates.

The representation pilot holds batch materialization constant and compares:

- native TSL mask chunks;
- integral masks (`to_integral` at the TSL algorithm boundary);
- packed bits;
- 32-bit position lists.

It separately measures three references:

- `fused_mask`: explicit TSL SIMD, no materialized intermediate;
- `scalar_autovec`: plain branchless C++ compiled with optimization and target
  flags, with compiler vectorization enabled;
- `scalar_no_vector`: the identical plain C++ source compiled with GCC
  `-fno-tree-vectorize -fno-tree-slp-vectorize` or Clang
  `-fno-vectorize -fno-slp-vectorize`.

A faster fused or scalar reference is reported relative to the candidate
oracle, but cannot win the representation study. This prevents the original
confound where “fused versus materialized” was mistaken for “representation
choice.” Build manifests record the effective compile commands. Use
`pipcost check --disassemble` to validate interactively that the
compiler-enabled control really vectorized; a label alone is not proof. Every
`pipcost run` requires the same disassembly gate and embeds its result in the
immutable run record.

The batch pilot asks a different question. It compares fused, batch-local
native-mask materialization, and relation-wide native-mask materialization.
That is an execution/materialization study, not a representation study.

## SIMD widths

Width is varied by separate immutable builds rather than by mixing binaries in
one run:

| Config | TSL profile | `int32` lanes | Nominal width |
|---|---:|---:|---:|
| `pilot-representation-sse2.json` | `sse2` | 4 | 128 bit |
| `pilot-representation.json` | `avx2` | 8 | 256 bit |
| `pilot-representation-skylake.json` | `skylake` | 16 | 512 bit |

The host-native gate rejects a profile whose required ISA features are not
available. Cross-width conclusions require completed runs for all relevant
configs; merely having the configs is not empirical evidence.

## Quick start

Run from the repository root:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=tslc/src:research/pipcost-src/src

python -m pipcost doctor --tsl-ref v0.2.7 --profile avx2
python -m pipcost generate --tsl-ref v0.2.7 --profile avx2 --simd-lanes 8
python -m pipcost build --tsl-ref v0.2.7 --profile avx2 --simd-lanes 8 --compiler c++
python -m pipcost check --tsl-ref v0.2.7 --profile avx2 --simd-lanes 8 --compiler c++ --disassemble
python -m pipcost run --config research/pipcost-src/configs/smoke.json
```

Every command prints JSON. All generated and runtime output is written below
`tslctmp/pipcost/`; source code remains below `research/pipcost-src/`.

The `run` command writes a complete immutable run, including raw paired
samples, build and TSL provenance, plan roles, summary, candidate-only oracle,
reference reports, and a `COMPLETE` marker. Use:

```bash
python -m pipcost summarize --run <run-id>
python -m pipcost fit --run <run-id>
python -m pipcost evaluate --run <run-id> --model <model.json>
```

`fit` stops when Scientific Gate A is not passed unless
`--allow-inconclusive` is supplied. Smoke measurements check workflow and
correctness only. They are not publication-quality performance evidence.

## Current limits

The prototype still studies one synthetic, single-threaded filter-filter-sum
pipeline on one host and compiler per run. It has no database integration,
parallel execution, cache-counter validation, multi-consumer reuse, nulls,
encodings, or end-to-end optimizer. The current implementation can falsify a
small representation-selection premise; it cannot substantiate a general
pipeline cost model or publication claim by itself.
