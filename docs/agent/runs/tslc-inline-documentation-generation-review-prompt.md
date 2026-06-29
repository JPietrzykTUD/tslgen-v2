# TSLc Inline Documentation Generation Review Prompt

You are reviewing the completed inline documentation generation slice for C++
and Rust.

Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

Primitive documentation metadata is now present in the catalog:

- `brief_description`: short human-readable summary;
- `detailed_description`: longer human-readable prose;
- `semantics`: raw documentation-only pseudocode.

This slice renders that metadata into generated API comments:

- C++ emits Doxygen comments;
- Rust emits rustdoc comments;
- concrete specialization docs include lowered backend/type/extension,
  requirement, attribute, immediate, target-vector, and safety facts;
- generic wrapper/dispatch docs use an `API` section for template/type
  parameters, return value, and runtime parameters;
- concrete impl/apply/free-function docs use a `Specialization` section with
  public-facing labels such as `SIMD register`, `scalar value`, and `lane
  array`, plus concrete backend register spellings where available.

The raw `semantics` field must remain documentation-only text. It must not be
parsed, evaluated, lowered as compiler semantics, used for primitive selection,
or used to repair source bodies.

## Files To Review

- `tslc/src/tslc/documentation.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/backend/cpp.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/tests/test_specialization.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Focus

Prioritize findings where the implementation violates:

- typed boundaries: documentation should flow through typed values, not parsed
  source documents or renderer-local catalog lookups;
- semantic logic before rendering: renderers should format already-decided
  documentation and lowered facts only;
- primitive- and extension-agnostic behavior: no primitive-name or
  extension-name classifiers should be introduced for documentation;
- documentation-only semantics: `semantics` should not be executable input;
- maintainability: documentation helpers should stay small, shared, and easy
  to extend for future documentation artifacts;
- deterministic generated output and stable formatting.

Check that C++ and Rust share the same documentation data boundary and differ
only in comment syntax. Also check that generated wrapper docs are not
misleading by presenting a concrete specialization as if it applied to the
whole overload family. Generated docs should not expose compiler-internal rows
such as `Context`, `Backend`, `Result kind`, `Parameter kinds`, or placeholder
sentences like "concrete specializations documented elsewhere".

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_specialization.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_safety_contract.py::test_rust_backend_formats_caller_unsafe_contract tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives add --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --profiles avx2 --output-root ./tslctmp/doc-inline-smoke
git diff --check
```

Optional architecture scan:

```bash
rg -n 'brief_description|detailed_description|semantics|PrimitiveDocumentation|DocumentationBlock' tslc/src/tslc
rg -n 'primitive.name|source_primitive_name|extension_name' tslc/src/tslc/documentation.py tslc/src/tslc/backend/cpp.py tslc/src/tslc/backend/rust.py
rg -n 'Context:|Backend:|Result kind:|Parameter kinds:|Concrete specializations' tslctmp/doc-inline-smoke/cpp/include tslctmp/doc-inline-smoke/rust/src
```

Expected result: production code should parse, validate, promote, carry, and
format documentation. It should not use documentation text for compiler
behavior or rediscover source semantics in renderers.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking design issues from future documentation polish.
