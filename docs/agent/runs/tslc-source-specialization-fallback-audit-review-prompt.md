# TSLc Source Specialization Fallback Audit Review

You are reviewing a focused source-data refinement after the source-owned
feature-gated specialization pass.

Review whether the fallback audit and `masked_set1` cleanup keep TSLc aligned
with the main design principles:

- primitive- and extension-agnostic compiler behavior;
- source-owned capability facts through typed `requires`;
- KISS/prototype-first source layering with typed primitive composition before
  adding new direct intrinsic bodies;
- DRY ownership of backend-specific behavior by the primitive that actually
  owns that behavior;
- semantic selection before rendering.

## Files To Inspect

- `tsldata/primitives/load_store/construct.tsl`
- `tslc/tests/test_select_and_lower.py`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

For context from the immediately preceding source-tier pass, also inspect:

- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `docs/agent/runs/tslc-source-specialization-requires-review-prompt.md`

## Review Questions

1. Does `masked_set1` correctly express its x86/NEON operation as
   `blend(mask, data, set1(scalar))` without losing existing lower-feature
   coverage?
2. Are `blend` and `set1` still the owners of backend-specific intrinsic
   selection and requirements, rather than moving those facts into
   `masked_set1` or compiler code?
3. Does the regression test assert the selected source composition without
   over-coupling to unrelated rendered formatting?
4. Is the fallback audit documentation honest about what was changed and what
   remains deferred to future primitive-by-primitive specialization slices?
5. Did the slice avoid adding compiler-side primitive or extension knowledge?

## Validation Already Run

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `22 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives masked_set1 --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `32776` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ CTest and Rust value tests ran through
Intel SDE for x86 profiles, with `neon` skipped because no x86 SDE chip alias
exists.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, or `Needs Revision`.

Treat further source-performance improvements as follow-ups unless the current
`masked_set1` composition breaks selection, correctness, or the source-owned
`requires` contract.
