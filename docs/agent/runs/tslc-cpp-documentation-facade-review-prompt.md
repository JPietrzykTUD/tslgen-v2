# TSLc C++ Documentation Facade Review Prompt

You are reviewing the completed C++ documentation facade header slice.

Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

Generated documentation now builds one Sphinx site under `<output>/docs/site`.
C++ documentation flows through Doxygen XML and Breathe. Rust documentation
flows through `cargo doc --no-deps` and is copied under the same site.

This slice changes the C++ Doxygen input from the full generated implementation
headers to a compact documentation facade header:

```text
<output>/cpp/docs/input/tsl_api_docs.hpp
```

The facade should contain the complete documentation surface for the selected
generation run while avoiding implementation bodies and generated profile
headers.

## Files To Review

- `tslc/src/tslc/backend/cpp.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/maintenance/documentation.py`
- `tslc/tests/test_specialization.py`
- `tslc/tests/test_maintenance_documentation.py`
- `supplementary/docs/cpp/Doxyfile.in`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Focus

Prioritize findings where the implementation violates:

- primitive- and extension-agnostic behavior: no production branching on names
  like `add`, `avx2`, or profile identities;
- typed boundaries: facade content must come from `LoweredSpecialization` and
  renderer-ready documentation data, not catalog reprocessing or header scans;
- complete selected-specialization coverage: every selected C++ specialization
  should have a documented stub in the facade;
- no implementation leakage: the facade must not include generated profile
  headers or contain implementation bodies;
- clear side-effect boundaries: `tslc.maintenance.documentation` should only
  consume the written facade and invoke Doxygen/Sphinx/Rustdoc;
- DRY ownership: public API and specialization docs should reuse the C++
  backend documentation helpers rather than duplicating semantic formatting;
- deterministic output: facade ordering, stub names, Doxyfile input, and site
  paths should be stable.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py tslc/tests/test_specialization.py::test_artifact_layout tslc/tests/test_specialization.py::test_cpp_documentation_facade_contains_api_and_specialization_stubs
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives add --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles avx2 --output-root ./tslctmp/doc-facade-smoke
PYTHONPATH=tslc/src python -m tslc.maintenance.documentation --output-root ./tslctmp/doc-facade-smoke --backends cpp,rust
./dev.sh document --primitives add --profiles avx2 --backends cpp,rust --output-root ./tslctmp/dev-doc-facade-smoke
git diff --check
```

Optional full-corpus observation:

```bash
./dev.sh document --backends cpp --output-root ./tslctmp/dev-doc-facade-full-cpp
```

Treat full-corpus timing as evidence, not a required unit-test gate. A local
observation after implementation showed that the facade removes
implementation-header parsing but complete all-specialization docs remain large:
the full C++ facade was about `94M`, Doxygen XML reached about `524M`, and the
run was interrupted during the documentation stage. Review whether this is an
acceptable follow-up for Sphinx/Breathe scaling or a blocking issue in the
facade design.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking boundary issues from optional docs polish.
