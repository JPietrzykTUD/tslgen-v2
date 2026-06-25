# TSLc Metadata Audit Tool Review Prompt

## Goal

Review the metadata audit maintenance tool for source-owned `safety:` and
`requires` fields.

## Scope

Files to inspect:

- `tslc/src/tslc/maintenance/metadata_audit.py`
- `tslc/src/tslc/maintenance/coverage_inventory.py`
- `tslc/src/tslc/maintenance/__init__.py`
- `tslc/tests/test_metadata_audit.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

Background files:

- `tslc/src/tslc/pipeline.py`
- `tslc/src/tslc/select/selector.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/tests/test_safety_contract.py`

## Expected Design

- The tool is a maintenance script, not part of normal generation. It should
  not change compiler behavior or silently repair source during generation.
- Suggestions are typed records with kind, confidence, source location, before
  and after text, rationale, and an optional narrow edit.
- Safety suggestions should be high-confidence direct facts only:
  `intrin<...>`, `mem<...>`, and pointer-taking signatures.
- Requirement suggestions should come from typed selected/lowered call facts,
  not from intrinsic-name guessing or renderer inspection.
- Automatic `requires` edits should remain conservative: simple local
  `requires [..]` replacement or leaf-selector insertion only. Scoped maps and
  broad nested selectors should stay manual suggestions.
- Interactive mode should let a user inspect/apply/skip suggestions without
  changing non-accepted edits.
- Source edits should be span-based and deterministic; this must not become a
  general TSL formatter.

## Validation Already Run

```bash
python -m compileall -q tslc/src/tslc/maintenance tslc/tests/test_metadata_audit.py
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_metadata_audit.py
```

Result: `3 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.metadata_audit --help
```

Result: passed.

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.metadata_audit --sources tsldata --checks safety --machine-profiles supplementary/buildsystem/machine_profiles.json
```

Result: `0 suggestion(s), 0 applicable`.

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.metadata_audit --sources tsldata --checks requires --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles avx2 --backends cpp --types si32 --primitives add
```

Result: `9 suggestion(s), 0 applicable`; the nonzero exit was expected because
check-only mode found low-confidence manual suggestions.

```bash
./verify.sh
```

Result: passed all targeted validations, including 207 non-build tests and 53
generated-build tests.

## Review Questions

1. Does the tool preserve the source-truth boundary, or does it drift into
   compiler-side source repair?
2. Are automatic edits restricted enough for KISS and source-body integrity?
3. Are requirement suggestions driven by typed selected/lowered facts rather
   than primitive, extension, or intrinsic name branches?
4. Is the interactive/apply/check behavior clear and deterministic?
5. Are the tests sufficient for suggestion generation and source patching?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

For any non-`Accept` verdict, include concrete findings with file/line
references and the smallest recommended next action.
