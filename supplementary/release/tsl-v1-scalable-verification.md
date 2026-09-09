# TSL v1 scalable verification evidence

Date: 2026-09-09

Status: local cross-build and QEMU evidence complete; native SVE and native RVV
release-candidate attestations remain mandatory.

## Exact generated identity

`tslc test` writes a versioned run attestation to
`.tslctmp/verification/attestation.json` beneath the selected output root. It
keeps run evidence separate from deterministic compiler semantics and links the
run to both:

- the digest of the immutable compiler input snapshot; and
- the SHA-256 digest of the generated `.tslc-manifest.json` artifact inventory.

The attestation records every exact command and explicit environment entry,
the runner kind and CPU/profile string, the declared runtime vector length,
return code, expectation result, captured output, diagnostics, and skips. A
missing manifest or an attestation write failure is a verification error.
After an invoked formatter, the artifact writer re-hashes exactly the paths
already owned by the manifest; consequently the attested manifest identifies
the formatted bytes passed to the build rather than the pre-format render.

## Reusable emulator matrices

The machine-profile catalog owns the matrices. CI and local verification do not
carry profile-name conditionals or extra shell invocations.

| Profile | Generated binary | Required executions |
| --- | --- | --- |
| scalable SVE | one `cpp/build/sve/tsl_values` | QEMU VL 128, 256, 512 |
| RVV baseline V 1.0, ELEN 64 | one `cpp/build/rvv/tsl_values` | QEMU VLEN 128, 256, 512 |
| SVE128 | one fixed-profile binary | QEMU VL 128 |
| SVE256 | one fixed-profile binary | QEMU VL 256 |
| SVE512 | one fixed-profile binary | QEMU VL 512 |

Every planned generated value or differential case is required. A missing
runner, skipped profile, timeout, failed command, or other incomplete profile
causes `tslc test` to fail rather than being counted as release evidence. Each
direct scalable execution has a 60-second verifier-owned timeout.

The required scalable showcase is an external generated-library consumer. It
filters positive `si32` values, reverse-gathers the selection, applies an affine
transform, and checks every element against a scalar oracle. Its masked tail
uses deliberately invalid inactive gather indices and a pass-through canary,
so an implementation that evaluates inactive addresses or corrupts inactive
lanes fails. Input, intermediate, and output buffers also carry boundary
canaries. CI compiles one SVE and one RVV binary and reuses each at the catalog-
owned 128-, 256-, and 512-bit executions. The two generated-build tests pass,
covering six executions with runtime lane counts 4, 8, and 16 and a one-lane
tail in every execution.

The full local RVV corpus generated 19,643 specializations and 4,448 value
cases. The same binary passed at VLEN 128, 256, and 512. The scalable SVE
corpus generated 19,648 specializations and 4,280 value cases; its one binary
passed at VL 128, 256, and 512. SVE128/256/512 generated 65,180
specializations in one project, and every fixed-profile value suite passed.

All three runs referenced compiler-input digest
`f37bfaab4767a5a1931f4b07f112f7a6235d86de24c00dc4b5ef8048363819e3`.
Their artifact-manifest digests and outcomes were:

| Scope | Artifact manifest SHA-256 | Commands / test executions | Outcome |
| --- | --- | ---: | --- |
| SVE VL 128/256/512 | `3b0c1ce978e5979acff7776a0a2ad212aa8bbcb569bf1f421d97a2f6f8c5fa17` | 12 / 3 | passed |
| SVE128/256/512 | `2d9054e90a2e737f8106fab872702bacda0136c86e780ddd784ffb74a769538a` | 30 / 3 | passed |
| RVV VLEN 128/256/512 | `c2ff72c8f87802f28a2ccae77d6490b14dc54d5481f5111dcd029bc2c77f2455` | 12 / 3 | passed |

The attested target preflights used Ubuntu GCC 15.2 cross compilers and the
executions used QEMU 10.2.1. Exact compiler flags and QEMU CPU strings are in
the command records rather than repeated as unaudited prose.

## Semantic edge coverage

The joint SVE/RVV plan contains 8,728 required cases and 3,323 coverage records;
all coverage records are `emitted` or `compile_only_emitted`. It exercises
scalable active-lane counts, partial loads/stores, inactive lanes and tails,
masks, checked invalid inputs and failure-path output preservation, lane and
memory indices, repeated scatter indices, aligned and deliberately unaligned
access, width-changing conversions, integer wrap semantics, and floating
conversion/rounding/NaN/infinity/signed-zero behavior. The generated checked
algorithm consumer separately verifies that prohibited overlapping ranges are
rejected before dispatch without changing output. `memory_cp` overlap remains
outside the checked primitive surface because its existing vector-base count
ABI cannot represent both byte capacities; that reviewed limitation is recorded
in the checked-API census rather than tested by invoking undefined behavior.

The release gate does not infer coverage from primitive names: planned cases
and verifier outcomes are joined by the typed backend/profile identity.

## Reproduction

Run from the repository root with the configured cross compilers and QEMU
runners:

```bash
./dev.sh test --profiles sve --backends cpp \
  --output-root ./tslctmp/v1-sve-scalable
./dev.sh test --profiles sve128,sve256,sve512 --backends cpp \
  --output-root ./tslctmp/v1-sve-fixed
./dev.sh test --profiles rvv --backends cpp \
  --output-root ./tslctmp/v1-rvv
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_algorithm_checked_api.py::test_cpp_transform_checked_pilot_preserves_outputs_on_failure \
  tslc/tests/test_scalable_release_showcase.py
```

The attestation files under each output root are the run records. QEMU results
are correctness evidence only. Emulator timings must not be used for latency,
throughput, fallback-cost, or other performance claims.

## Native release-candidate checklist

Before tagging `v1.0.0`, produce native SVE and RVV attestations that reference
the same compiler-input and release bundle-index identity. Each record must also
name the exact target bundle (`cpp-sve` or `cpp-rvv`) and its inner generated
artifact-manifest digest, and record:

- machine/vendor/model and architectural feature report;
- operating system, compiler executable/version, and exact flags;
- observed runtime vector length(s);
- full generated value/differential outcome with no skips;
- the actual CHORYS integration result and scalar-oracle comparison for RVV;
- attestation file checksum and reviewer; and
- separately labelled native performance evidence for any performance claim.

No local native SVE or RVV hardware was available for this slice. That absence
is an open release gate, not an emulator-derived success claim.
