# TSLc Primitive Documentation Batch Prompt: Comparison Ranges

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
- `tsldata/primitives/arithmetic/horizontal.tsl`
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/bitwise/bit_counts.tsl`
- `tsldata/primitives/bitwise/horizontal.tsl`
- `tsldata/primitives/comparison/fundamental.tsl`

Current inventory after the comparison fundamental batch:

```text
140 primitive declarations total
73 declarations with detailed_description
73 declarations with semantics
```

Use readable indented multiline fields:

```tsl
  detailed_description """
    Prose starts indented inside the multiline string.
    """
  semantics """
    input: register x, register left, register right
    for each lane i:
      result[i] = left[i] <= x[i] and x[i] <= right[i]
    return mask result
    """
```

## Goal

Add `detailed_description` and `semantics` to every primitive declaration in:

```text
tsldata/primitives/comparison/range.tsl
```

Keep the authored text precise and source-owned. Cover inclusive, left-only
inclusive, right-only inclusive, and exclusive range checks, including masked
zero forms. Describe inactive masked lanes as false/cleared. For floating-point
unordered cases, state that behavior follows the selected backend comparison
implementation unless the source body makes a narrower promise.

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
