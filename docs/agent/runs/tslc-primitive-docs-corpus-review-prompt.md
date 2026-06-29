# TSLc Primitive Documentation Corpus Review Prompt

You are reviewing the completed primitive documentation metadata corpus sweep
in `tsldata/primitives`.

Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

The documentation metadata admission slice added primitive fields:

- `brief_description`: short human-readable summary;
- `detailed_description`: longer human-readable prose;
- `semantics`: raw documentation-only pseudocode.

The corpus sweep added `detailed_description` and `semantics` to every
primitive declaration under `tsldata/primitives`. The new fields must remain
source-owned documentation metadata. They must not be interpreted as TSIL,
lowered as compiler semantics, used for primitive selection, or used to repair
source bodies.

Corpus style: keep both fields as readable indented multiline strings in the
source data. A future documentation renderer may normalize common indentation
for output, but the corpus should stay pleasant to read.

## Files To Review

- `tsldata/primitives/**/*.tsl`
- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/tests/test_catalog_validation.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Focus

Prioritize findings where the sweep violates:

- documentation-only semantics: `semantics` must not imply executable TSIL;
- primitive- and extension-agnostic compiler design;
- typed catalog boundaries;
- maintainability and readable source data;
- deterministic catalog loading and generation;
- diagnostics over silent behavior for malformed fields.

Check that every primitive declaration has both fields and that the prose does
not overclaim behavior the implementation does not guarantee. In particular,
look closely at memory, mask representation, conversion, conflict, gather, and
scatter primitives, where wording can accidentally promise alignment, aliasing,
overflow, NaN, or duplicate-index behavior more strongly than the source bodies
support.

## Suggested Validation

```bash
python - <<'PY'
from pathlib import Path

missing = []
prims = detail = sem = 0
for path in sorted(Path("tsldata/primitives").rglob("*.tsl")):
    current = None
    has_detail = False
    has_sem = False
    for line in path.read_text().splitlines():
        if line.startswith("prim"):
            if current is not None and not (has_detail and has_sem):
                missing.append((path, current, has_detail, has_sem))
            prims += 1
            current = line.strip()
            has_detail = False
            has_sem = False
        elif line.startswith("  detailed_description"):
            detail += 1
            has_detail = True
        elif line.startswith("  semantics"):
            sem += 1
            has_sem = True
    if current is not None and not (has_detail and has_sem):
        missing.append((path, current, has_detail, has_sem))

print(f"primitives={prims} detailed_description={detail} semantics={sem}")
if missing:
    for item in missing:
        print(item)
    raise SystemExit(1)
PY

PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --profiles scalar --coverage --output-root ./tslctmp/doc-metadata-smoke
git diff --check
```

Optional architecture scan:

```bash
rg -n 'detailed_description|semantics' tslc/src/tslc
```

Expected result: production code should only parse, validate, promote, store,
or eventually render these fields. It should not lower or execute them.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking design issues from acceptable documentation cleanup.
