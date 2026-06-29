# TSLc Documentation Tooling Review Prompt

You are reviewing the completed generated documentation tooling slice.

Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

Generated C++ and Rust APIs already contain inline Doxygen/rustdoc comments.
This slice adds an after-write maintenance command that builds browsable
documentation from an already generated output tree:

- C++: Doxygen XML consumed by Breathe;
- Rust: `cargo doc --no-deps`, copied under the generated site;
- Site: one Sphinx HTML tree under `<output>/docs/site`;
- `./dev.sh document`: generate + format + document;
- `./dev.sh build` and `./dev.sh test`: still format by default through the CLI,
  with documentation generation opt-in via `TSLC_DOCUMENT=1`.

Documentation site generation must remain maintenance/output tooling. It must
not become a catalog parser, lowering stage, renderer-side semantic decision, or
required dependency for ordinary build/test gates.

## Files To Review

- `tslc/src/tslc/maintenance/documentation.py`
- `tslc/tests/test_maintenance_documentation.py`
- `supplementary/docs/cpp/Doxyfile.in`
- `supplementary/docs/site/conf.py.in`
- `supplementary/docs/site/index.rst.in`
- `supplementary/docs/site/cpp_api.rst.in`
- `supplementary/docs/site/rust_api.rst.in`
- `supplementary/docs/site/_static/tslc.css`
- `dev.sh`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Focus

Prioritize findings where the implementation violates:

- clear side-effect boundaries: documentation tooling should operate only on a
  written generated project;
- KISS/prototype-first: no broad docs framework, plugin registry, or semantic
  catalog reprocessing;
- semantic logic before rendering: docs tooling should not inspect primitive
  semantics or reinterpret `semantics`;
- deterministic output paths under `<output>/cpp/docs`,
  `<output>/rust/docs`, and `<output>/docs/site`;
- dependency hygiene: Doxygen/Sphinx/Cargo should be required for
  `document`, not for ordinary build/test unless `TSLC_DOCUMENT=1`;
- Breathe should consume Doxygen XML only, with no parallel Doxygen HTML site
  required for the C++ API;
- maintainability of assets and command construction.

Check especially that extra `dev.sh` CLI overrides such as `--backends ...` and
`--output-root ...` are respected by the documentation step, and that tests do
not require real Doxygen, Sphinx, or Cargo.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py
bash -n dev.sh
PYTHONPATH=tslc/src python -m tslc.maintenance.documentation --output-root ./tslctmp/doc-inline-smoke --backends cpp,rust --dry-run
git diff --check
```

Recommended script-level smoke without real documentation tools:

```bash
# Create fake doxygen/sphinx/cargo executables, then:
TSLC_DOXYGEN=/tmp/tslc-fake-doxygen TSLC_SPHINX_BUILD=/tmp/tslc-fake-sphinx-build TSLC_CARGO=/tmp/tslc-fake-cargo ./dev.sh document --primitives add --profiles avx2 --backends cpp --output-root ./tslctmp/dev-doc-tool-smoke
```

Optional live-tool validation, only if Doxygen, Sphinx, and Cargo are installed:

```bash
./dev.sh document --primitives add --profiles avx2 --backends cpp,rust
test -f ./tslctmp/verify/docs/site/index.html
test -f ./tslctmp/verify/docs/site/cpp_api.html
test -f ./tslctmp/verify/docs/site/rust/index.html
```

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking boundary issues from optional docs polish.
