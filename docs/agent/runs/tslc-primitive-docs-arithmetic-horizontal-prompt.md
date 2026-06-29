# TSLc Primitive Documentation Batch Prompt: Arithmetic Horizontal Reductions

## Context

Continue the active primitive documentation corpus goal:

- add `detailed_description` and `semantics` to every primitive declaration;
- keep `brief_description` as the short summary;
- treat `semantics` as raw documentation-only pseudocode, not executable TSIL;
- do not add vague filler;
- mark unclear semantics explicitly instead of inventing behavior.

Completed documentation batches:

- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/arithmetic/select.tsl`
- `tsldata/primitives/arithmetic/complex.tsl`
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/bitwise/bit_counts.tsl`
- `tsldata/primitives/bitwise/horizontal.tsl`

Current inventory after the bitwise horizontal batch:

```text
140 primitive declarations total
55 declarations with detailed_description
55 declarations with semantics
```

Use readable indented multiline fields:

```tsl
  detailed_description """
    Prose starts indented inside the multiline string.
    """
  semantics """
    input: register data
    for each lane i:
      result[i] = data[i]
    return result
    """
```

## Goal

Add `detailed_description` and `semantics` to every primitive declaration in:

```text
tsldata/primitives/arithmetic/horizontal.tsl
```

Keep the authored text precise and source-owned. Describe `hadd`, `hmax`, and
`hmin` as horizontal reductions over all lanes, and describe their masked
forms as reductions over active lanes only. Check tests and bodies before
stating empty-mask behavior. For floating-point extrema, avoid inventing NaN or
unordered comparison semantics unless the source body makes them explicit.

## Validation

Run at least:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles scalar --coverage --output-root ./tslctmp/doc-metadata-smoke
git diff --check
```

Also update:

- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

Do not mark the documentation corpus goal complete until every primitive
declaration under `tsldata/primitives` has both fields and the completion audit
proves it.
