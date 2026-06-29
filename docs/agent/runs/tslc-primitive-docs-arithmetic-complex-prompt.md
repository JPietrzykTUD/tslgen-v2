# TSLc Primitive Documentation Batch Prompt: Arithmetic Complex

## Context

Continue the active primitive documentation corpus goal:

- add `detailed_description` and `semantics` to every primitive declaration;
- keep `brief_description` as the short summary;
- treat `semantics` as raw documentation-only pseudocode, not executable TSIL;
- do not add vague filler;
- mark unclear semantics explicitly instead of inventing behavior.

The metadata admission slice has already added parser/schema/model/builder
support for:

- `brief_description`
- `detailed_description`
- `semantics`

Batch 1 has documented:

- all primitives in `tsldata/primitives/arithmetic/fundamental.tsl`;
- all primitives in `tsldata/primitives/arithmetic/select.tsl`.

Current inventory after batch 1:

```text
140 primitive declarations total
9 declarations with detailed_description
9 declarations with semantics
```

## Goal

Add `detailed_description` and `semantics` to every primitive declaration in:

```text
tsldata/primitives/arithmetic/complex.tsl
```

Keep the authored text precise and source-owned. Do not derive semantics from a
specific extension or backend. For masked primitives, describe zeroing versus
pass-through behavior explicitly. For immediate primitives, describe the scalar
immediate operand. If modulo/division edge cases are backend/type-defined, say
that rather than over-specifying behavior.

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
