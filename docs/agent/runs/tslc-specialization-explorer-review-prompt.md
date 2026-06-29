# TSLc React Specialization Explorer Review Prompt

You are reviewing the React/Vite specialization explorer slice for `tslc`.

## Scope

Review the generated documentation explorer that emits compact
`docs/specializations/specializations.json`, builds a React/Vite docs app, and
copies the static bundle into the built Sphinx site. Check whether the
implementation is still aligned with the main TSLc design principles:
primitive/extension agnosticism, KISS, typed boundaries, DRY ownership, clear
side-effect boundaries, semantic logic before rendering, diagnostics over
silent behavior, determinism, maintainability, and extensibility by typed data.

## Files To Inspect

- `tslc/src/tslc/render/documentation_project.py`
- `tslc/src/tslc/render/project.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/backend/cpp.py`
- `tslc/src/tslc/maintenance/documentation.py`
- `supplementary/docs/site/specializations/react/package.json`
- `supplementary/docs/site/specializations/react/package-lock.json`
- `supplementary/docs/site/specializations/react/index.html`
- `supplementary/docs/site/specializations/react/src/App.jsx`
- `supplementary/docs/site/specializations/react/src/main.jsx`
- `supplementary/docs/site/specializations/react/src/styles.css`
- `supplementary/docs/site/specializations.rst.in`
- `dev.sh`
- `.devcontainer/Dockerfile`
- `tslc/tests/test_maintenance_documentation.py`
- `tslc/tests/test_specialization.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Review Questions

- Is `specializations.json` derived only from typed lowered/render facts, or did
  any catalog scanning, TSIL parsing, primitive-name classification, or backend
  semantic inference leak into the documentation renderer?
- Does the compact schema stay display-oriented and deterministic, with string
  tables, interned feature/safety sets, and grouped rows instead of repeated
  per-specialization objects?
- Is the C++ Doxygen facade now an API declaration surface only, with
  per-specialization browsing handled by the static explorer?
- Is the React app presentation-only? It may filter and display records, but
  must not encode support-policy semantics or hard-coded primitive/extension
  classifiers.
- Does the rendered interaction match the `docReact/` intent: collapsed filter
  rail and primitive accordion rows?
- Does the selected primitive row put documentation before specialization
  browsing, followed by compact summary pills and a faceted emitted-record
  inventory?
- Does the filter rail expose requirements, typed extension families, data
  types, backends, and safety, without reintroducing raw target toggles?
- Is `ptr` omitted from the data-type filter because it is not a specialization
  axis?
- Does extension-family filtering consume the typed family field emitted in the
  compact docs schema rather than deriving families from extension-name
  spellings?
- Does the inventory group by typed display facts such as profile, display
  width, backend, extension, or safety, with expandable concrete rows?
- Did the old yes/no/partial support matrix disappear, so the explorer shows
  emitted records only and does not infer missing support?
- Does the built bundle avoid unbound runtime globals such as
  `React.createElement`, so `/specializations/index.html` renders rather than
  showing a blank page?
- Is the npm/Vite build clearly after-write documentation tooling rather than
  part of parsing, selection, lowering, or backend rendering?
- Are artifact paths deterministic and suitable for static hosting, including
  GitHub Pages?
- Are tests checking the boundary instead of snapshotting brittle generated UI
  details?
- Is Node/npm limited to documentation generation, with normal generation/build
  paths still free of React tooling?
- Do external documentation tools run with a stable UTF-8 locale instead of
  inheriting unsupported caller locale settings?

## Suggested Validation

Run:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py tslc/tests/test_specialization.py::test_artifact_layout tslc/tests/test_specialization.py::test_cpp_documentation_facade_contains_api_declarations_only tslc/tests/test_specialization.py::test_specialization_explorer_data_contains_all_selected_specializations
npm --prefix supplementary/docs/site/specializations/react ci --no-audit --no-fund
npm --prefix supplementary/docs/site/specializations/react run build
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives add --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles avx2 --output-root ./tslctmp/doc-explorer-review-smoke
PYTHONPATH=tslc/src python -m tslc.maintenance.documentation --output-root ./tslctmp/doc-explorer-review-smoke --backends cpp,rust
./dev.sh document --primitives add --profiles avx2 --backends cpp,rust --output-root ./tslctmp/dev-doc-explorer-review-smoke
LC_ALL=definitely_not_a_real_locale LANG=also_not_a_real_locale ./dev.sh document --primitives add --profiles avx2 --backends cpp,rust --output-root ./tslctmp/locale-doc-review-smoke
! rg -n 'React\.createElement' ./tslctmp/dev-doc-explorer-review-smoke/docs/site/specializations/assets/*.js
git diff --check
```

Optional static checks:

```bash
rg -n 'getSupportValue|matrixTargets|matrixBackends|enabledTargets|SupportMatrix|supportMatrix|modernX86TargetKeys|WASM SIMD|Partial|extension_name ==|primitive_name ==|source_primitive ==|tsil|ImplementationBody' tslc/src/tslc/render/documentation_project.py supplementary/docs/site/specializations/react/src
rg -n 'INPUT|tsl_api_docs|cpp/include' ./tslctmp/doc-explorer-review-smoke/cpp/docs/doxygen/Doxyfile
test -f ./tslctmp/doc-explorer-review-smoke/docs/site/specializations/index.html
find ./tslctmp/doc-explorer-review-smoke/docs/site/specializations/assets -type f
test -f ./tslctmp/doc-explorer-review-smoke/docs/site/specializations/specializations.json
python - <<'PY'
import json
from pathlib import Path
path = Path('./tslctmp/doc-explorer-review-smoke/docs/site/specializations/specializations.json')
data = json.loads(path.read_text())
assert data['schema_version'] == 3
assert 'family' in data['columns']
print(data['schema_version'], path.stat().st_size)
PY
```

## Expected Verdict

Return one of:

- `Accept`
- `Needs Revision`
- `Return To Planner`
- `Reject`

Lead with findings ordered by severity. Include exact file and line references.
If accepted, identify the next most useful documentation follow-up.
