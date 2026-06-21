# TSLc Catalog/Profile Validation Review Prompt

## Accepted State

This is an ad hoc `tslc/` worktree review prompt, not a numbered `tslgen/`
redesign milestone. The old numbered `tslgen/` milestone line remains paused
and must not be resumed from this prompt.

The implemented slice adds a real validation boundary for catalog and machine
profile data before selection, lowering, backend dialect creation, or rendering.
It is layered on top of the current `tslc` worktree, whose typed render rewrite
is still relevant background.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md`
- `tslc/src/tslc/catalog/validation/__init__.py`
- `tslc/src/tslc/catalog/validation/invariants.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/catalog/validation/requires_validation.py`
- `tslc/src/tslc/catalog/validation/source_spans.py`
- `tslc/src/tslc/catalog/machine_profiles.py`
- `tslc/src/tslc/pipeline.py`
- `tslc/tests/test_catalog_validation.py`

## Scope

Review the validation pass and confirm that:

- catalog validation runs after parse/catalog promotion and before selection,
  lowering, or backend creation;
- diagnostics cover duplicate source keys, unknown fields, invalid enum-like
  strings, missing backend spellings, missing scalar type spellings, bad
  extension inheritance, inheritance cycles, and malformed `requires` shapes;
- diagnostics use structured `Diagnostic` values with deterministic sorting and
  source locations where parsed TSL spans are available;
- machine profile loading reports diagnostics for malformed JSON, duplicate JSON
  keys, unknown fields, invalid families, duplicate names, malformed flags, and
  malformed alternative spellings;
- unsupported backend requests are diagnosed before `create_backend_dialect(...)`
  can raise a plain Python exception;
- `requires` validation remains structural and does not become feature/profile
  selection;
- the validation package split keeps a narrow public `validate_catalog(...)`
  boundary while separating catalog invariants, parsed-source schema checks,
  `requires` shape checks, and source-span helpers;
- existing valid `tsldata/` and machine profile data still pass cleanly.

## Out Of Scope

- Do not broaden TSL syntax or repair source bodies.
- Do not add profile feature selection, fallback policy, or host CPU detection.
- Do not change generated C++ or Rust output intentionally.
- Do not migrate or resume the old numbered `tslgen/` milestone line.
- Do not require exact legacy diagnostic wording.

## Required Validation

Run or confirm:

```bash
git diff --check
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python - <<'PY'
from pathlib import Path
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.validation import validate_catalog

load = SourceLoader().load_dir(Path("tsldata"))
parsed = TslParser().parse(load.documents)
built = CatalogBuilder().build(parsed)
assert built.catalog is not None
diagnostics = validate_catalog(built.catalog, parsed)
assert diagnostics == (), diagnostics
PY
./verify.sh
```

The implementation run on 2026-06-21 passed `./verify.sh` with 115 non-build
tests and 53 generated-build tests across its shards.

## Expected Output

Return a review verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with blocking findings and cite file/line references. If accepted, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
required by `docs/agent/next-run-prompt-protocol.md`.

## Stop Rule

Do not implement revisions during review unless a focused revision task is
explicitly created. Do not start the paused old `tslgen/` milestone line in this
run.
