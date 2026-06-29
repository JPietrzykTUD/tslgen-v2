# TSLc C++ Documentation Facade Header Prompt

Implement the C++ documentation facade header slice.

Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

The generated documentation tooling currently builds one Sphinx site under
`<output>/docs/site`. C++ documentation flows through Doxygen XML and Breathe.
Rust documentation flows through `cargo doc --no-deps` and is copied under the
same site.

The current C++ Doxygen input is still the generated implementation header set.
That is the wrong final shape: a full default run can produce very large,
template-heavy profile headers, making Doxygen slow while forcing it to parse
implementation details that are not needed for user-facing docs.

## Goal

Generate a compact C++ documentation facade header and point Doxygen at it.

The facade should be emitted as a generated artifact, for example:

```text
<output>/cpp/docs/input/tsl_api_docs.hpp
```

It must contain the complete documentation surface for the selected generation
run:

- public primitive declaration stubs;
- every selected concrete specialization as a documented declaration/stub;
- specialization facts such as extension, concrete backend types, requirements,
  safety, result type, and parameter types;
- no implementation bodies;
- no includes of the generated profile implementation headers.

## Boundary Rules

- Generate the facade from typed render/lowered documentation data.
- Do not make `tslc.maintenance.documentation` inspect the catalog, parse TSIL,
  scrape generated implementation headers, or infer primitive semantics.
- Keep the maintenance tool after-write only: it should render/copy doc assets
  and run Doxygen/Sphinx/Rustdoc over already-written artifacts.
- Do not special-case primitive or extension names in production documentation
  code.
- Keep Doxygen XML plus Breathe as the C++ site path; do not reintroduce a
  parallel Doxygen HTML site.

## Suggested Implementation Shape

1. Add a C++ renderer artifact for the facade header under `cpp/docs/input`.
2. Render wrapper/API declaration stubs from the same typed documentation values
   used by inline Doxygen comments.
3. Render one specialization stub per selected `LoweredSpecialization`, carrying
   already-known concrete C++ spellings and lowered safety/requirement facts.
4. Update `supplementary/docs/cpp/Doxyfile.in` or its render values so Doxygen
   `INPUT` points to the facade header directory/file, not `cpp/include`.
5. Update documentation maintenance tests so fake Doxygen sees the facade input.
6. Add a regression check that full generated C++ profile headers are not used
   as Doxygen input.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_cpp_render*.py
bash -n dev.sh
./dev.sh document --primitives add --profiles avx2 --backends cpp,rust --output-root ./tslctmp/dev-doc-facade-smoke
test -f ./tslctmp/dev-doc-facade-smoke/cpp/docs/input/tsl_api_docs.hpp
test -f ./tslctmp/dev-doc-facade-smoke/docs/site/cpp_api.html
git diff --check
```

If full-corpus timing is checked, record it as observational evidence, not as a
unit-test dependency.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking boundary issues from optional docs polish.
