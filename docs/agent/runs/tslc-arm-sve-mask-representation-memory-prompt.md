# Prompt: Add C++ SVE Mask Representation Memory Coverage

Implement the next narrow C++ SVE mask-memory slice after mask-to-vector.

## Context

Current C++ SVE value-test coverage includes scalable value, masked value,
mask-result, masked mask-result, mask-logic, mask-constant, mask-conversion,
and mask-to-vector cases. Rust SVE remains unsupported because stable Rust
stdarch does not expose the required SVE API in this environment.

Evidence sampled after the mask-to-vector slice:

- `./dev.sh explain --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve`
  selects the SVE body, but lowering fails for all selected attribute slots
  because the body uses fixed
  `value<generation>(vector::length)` and `mask<test>(mask, lane)` /
  `mask<test>(mask, i)` on a native SVE predicate.
- `./dev.sh explain --primitive load_mask_repr --profile sve --type ui32 --backend cpp --extension sve`
  shows the unpacked path lowering through existing typed primitives, while
  the packed path still exposes the same fixed-lane predicate tension.
- `./dev.sh explain --primitive mask_population_count --profile sve --type ui32 --backend cpp --extension sve`
  already lowers through native `svcntp_b32`.
- `lzc_imask` and `tzc` currently declare no SVE implementation bodies.

## Goal

Make the smallest honest progress on C++ SVE mask representation memory,
starting with `store_mask_repr` (`void:=(ptr,m)`), without adding
primitive-name or extension-name compiler branches.

## Expected Design Shape

- Prefer a source-owned SVE implementation that uses native scalable SVE
  predicate operations or existing typed primitives.
- Do not reintroduce fixed `vector::length` for SVE or use
  `array_for<simd<T, sve>>`.
- Do not make `mask<test>` magically support native predicates by guessing a
  packed representation.
- If packed mask representation needs a reusable typed helper, model that
  helper explicitly through source/catalog metadata or a narrow TSIL/value
  capability before rendering.
- Keep `param_types` as source metadata unless this slice proves a typed
  lowering/rendering contract is needed.
- Add or adapt authored SVE tests only for shapes that the implementation can
  honestly execute through QEMU.
- Keep renderers consuming already-decided plans; no catalog inspection or
  primitive-specific rendering branches.

## Evidence Commands

Start with:

```bash
./dev.sh explain --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve
./dev.sh dump --stage segments --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve --format text
./dev.sh explain --primitive load_mask_repr --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive mask_population_count --profile sve --type ui32 --backend cpp --extension sve
```

Use these to decide whether the first slice should repair only
`store_mask_repr`, repair the paired `load_mask_repr` packed path too, or stop
for a typed design decision.

## Validation

After implementation, run focused validation appropriate to the chosen slice,
for example:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-repr ./dev.sh test --profiles sve --primitives store_mask_repr --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
./dev.sh ratchet
git diff --check
```

If the slice also changes `load_mask_repr`, include it in the generated test
command and inspect generated `values_sve.cpp` / `tsl_sve.hpp` for the expected
native SVE mask-memory operations.

## Guardrails

- Do not add compiler-side branches on `store_mask_repr`, `load_mask_repr`, or
  `sve`.
- Do not create a fake fixed lane count for scalable vectors.
- Do not silently skip malformed or unsupported mask-memory test shapes.
- Keep C++ SVE scope separate from Rust SVE parity.
- Update ADR/current-state/handoff docs if the slice introduces a new typed
  source or value-test contract.
