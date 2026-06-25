# TSLc Source Specialization Requires Review

You are reviewing a focused source-data refinement after the primitive
finalization closure pass.

Review whether the new feature-gated implementations keep TSLc aligned with the
main design principles:

- primitive- and extension-agnostic compiler behavior;
- source-owned hardware capability facts through typed `requires`;
- KISS/prototype-first layering with fallbacks instead of new compiler plumbing;
- semantic selection before rendering;
- deterministic, maintainable implementation ordering.

## Files To Inspect

- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tsldata/primitives/misc/compress.tsl`
- `tsldata/primitives/misc/blend.tsl`
- `tslc/tests/test_select_and_lower.py`

## Review Questions

1. Do the new SSE4.1 `cast` and `to_mask` bodies use precise enough
   `requires` fields that they are selected only when the profile supports
   them?
2. Do the fallbacks remain available for lower-feature profiles, especially
   SSE/SSE2?
3. Are unsigned float-to-int conversions still kept on the fallback path rather
   than inventing unsupported intrinsic spellings?
4. Are `compress` and `blend` still relying on their existing feature-gated
   tiers and fallbacks without redundant child-extension bodies?
5. Do the regression tests assert selector behavior rather than renderer text
   beyond what is needed to prove the selected body?

## Validation Already Run

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `21 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast,to_mask,compress,blend --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `47258` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ CTest and Rust value tests ran through
Intel SDE for x86 profiles, with `neon` skipped because no x86 SDE chip alias
exists.

```bash
python -m compileall -q tslc/src/tslc
git diff --check
```

Result: passed.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, or `Needs Revision`.

Treat source-specific performance improvements beyond these bodies as
follow-ups unless the current changes break selection, correctness, or the
source-owned `requires` contract.
