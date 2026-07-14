# Compiler Instructions

## Scope

These instructions apply to `tslc/`. The root `AGENTS.md`, `CHARTER.md`, and
`PLANS.md` also apply. Read `tslc/CHARTER.md` for the compiler contract and the
relevant part of `tslc/DESCRIPTION.md` before changing architecture.

## Compiler Pipeline Ownership

The pipeline is:

```text
loaded sources/assets -> parse -> catalog -> select -> scan TSIL -> lower
  -> close dependencies/finalize names -> validate/plan -> render -> write/verify
```

- `tslc/src/tslc/sources.py` and `tslc/src/tslc/compiler_assets.py` own source
  and static-asset loading.
- `tslc/src/tslc/syntax/` owns parsed source models and parsing, not domain
  behavior.
- `tslc/src/tslc/catalog/` promotes parsed input into validated, immutable
  domain objects.
- `tslc/src/tslc/select/` chooses explicit implementation slots for a
  target/profile.
- `tslc/src/tslc/ir/` owns recursive TSIL segments and lexical region
  recognition.
- `tslc/src/tslc/lower/` turns selected catalog facts and regions into typed lowered
  specializations.
- `tslc/src/tslc/backend/` owns backend capabilities, target projection and
  translation, emitted profiles/functions, helper manifests, and pre-render
  validation.
- `tslc/src/tslc/value_tests/` and `tslc/src/tslc/benchmark/` plan typed
  executable-test and benchmark behavior before rendering.
- `tslc/src/tslc/render/` formats finalized, validated render values.
- `tslc/src/tslc/output/` writes artifacts and performs explicit build/test
  verification.

Do not move behavior to a later stage merely because that stage has convenient
access to strings or filesystem paths.

## Typed Design Rules

- Use typed Python and keep boundaries mypy-friendly.
- Prefer `@dataclass(frozen=True, slots=True)` for domain and value objects.
- Plain dictionaries are acceptable at parser, configuration, and explicit
  metadata boundaries. Catalog, selection, lowering, backend, planning, and
  render logic consume typed values.
- Stateful concepts such as catalogs, selectors, generators, backend dialects,
  diagnostic reporters, and artifact writers should own their invariants in
  small classes or protocols.
- Use pure functions for small stateless transformations.
- Result values should carry substantive stage outputs and structured
  diagnostics directly; do not build request/result/handoff wrapper families.
- Preserve source locations for diagnostics where practical. Pure compiler
  logic returns diagnostics and does not call `SystemExit`; the CLI owns process
  exit behavior.
- Keep filesystem reads in source/config/static-asset loading. Keep writes in
  artifact writing or explicit maintenance tools. Parsing through rendering
  should not perform incidental I/O.
- Sort filesystem traversal and externally observable mappings at their
  boundaries. Generated output and diagnostics must be deterministic.
- Split modules before they become catch-all files.

## TSIL Boundary

- A TSIL body is a recursive sequence of `RawText` and recognized `Region`
  segments, not a C/C++/Rust AST.
- Recognize exact documented source forms. Diagnose malformed or unsupported
  nearby forms instead of silently repairing them.
- Scanning owns delimiters, nesting, spans, comments, and recursive segments;
  it does not own expression semantics.
- Shared semantics become typed TSIL regions or lowering values, not raw-string
  rewrite ladders.
- Region shell validation and region lowering are separate concerns.
- A new region must use the shared descriptor/registry, recursive scanner, and
  lowerer registration paths. Use `.agents/skills/add-tsil-region/SKILL.md` for
  the complete workflow.

## Backend And Rendering Boundary

- Backend code translates typed lowered values. Templates format already
  decided render values.
- Templates must not select implementations, resolve types, choose intrinsics,
  gate features, compute dependency closure, parse TSIL, or repair source.
- Register backend IDs and capabilities at the backend registry/support-policy
  boundary; do not scatter backend string lists.
- Diagnose unsupported capabilities before rendering or artifact writing.
- Static backend files, templates, and helpers packaged with the compiler live
  under `tslc/src/tslc/backend/assets/`. Generated-documentation inputs remain
  under `supplementary/docs/`; machine profiles remain under
  `supplementary/buildsystem/`.
- A backend with substantially different expression syntax must fail clearly
  until the required raw forms have typed TSIL representations.
- Use `.agents/skills/add-tslc-backend/SKILL.md` for backend additions.

## Validation

Run tests from the repository root so source-data paths and workspace scratch
configuration remain correct.

```bash
# Parser, catalog, and validation
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py

# TSIL scanning and lowering
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_*.py

# Backend and render model
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py

# Output and verification configuration
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_output_format.py

# Documentation maintenance
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py

# Full Python logic suite
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
```

Also consider, in proportion to the change:

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
git diff --check
```

Run the opt-in generated gates when project layout, backend codegen,
verification, or executable value tests change:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Keep hardware and toolchain detection injectable, skippable, or explicitly
gated. Report unavailable generated verification rather than hiding it.

## Compiler Documentation

- `README.md` is the compiler quick start.
- `CHARTER.md` is the stable compiler-specific design contract.
- `DESCRIPTION.md` explains the current architecture and may change as owned
  modules or behavior change.

Update these files when their claims cease to match active code or workflow,
not as a substitute for tests or typed ownership.
