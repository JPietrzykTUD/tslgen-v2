# Open Questions

This file tracks unresolved questions. Do not guess answers that materially affect architecture.

## OQ-001: What Exact Python Version Should The Redesign Target?

Status: Answered

Why it matters:

`tslgen/pyproject.toml` currently requires Python `>=3.14`, which is restrictive and may not match deployment expectations.

Decision:

Target Python `>=3.14` for the redesign. The dev container has Python 3.14.4 installed, and the existing `tslgen/pyproject.toml` already declares `requires-python = ">=3.14"`.

Considered answers:

- Keep `>=3.14`.
- Use a stable lower baseline such as `>=3.12`.
- Match the repository/devcontainer runtime.

Required evidence:

- Dev-container runtime: Python 3.14.4 is installed.
- Existing packaging sketch: `tslgen/pyproject.toml` declares `>=3.14`.
- Language features actually required should still be kept conservative and documented as implementation proceeds.

Implementation blocked:

No. Packaging and syntax choices may use Python 3.14 as the baseline. Implementations should still avoid unnecessary version-specific cleverness.

## OQ-002: Should Backend Manifests Remain YAML?

Why it matters:

Legacy evidence stores backend behavior in YAML under `frozen/generator_specs`. The redesign can preserve YAML as a data format or move manifests into TSL/Python.

Possible answers:

- Keep YAML with typed schemas.
- Convert manifests into TSL data.
- Define backend manifests in Python plugin modules.

Required evidence:

- Who edits backend manifests.
- Desired external stability.
- Whether non-Python contributors need to add backend behavior.

Implementation blocked:

No for early milestones. Backend manifest milestone is blocked.

## OQ-003: What Is The Explicit Policy For List-Backed Implementation Variants?

Why it matters:

Some legacy selection paths accept list-backed implementation entries and select the first dict. This is likely accidental or underspecified.

Possible answers:

- Reject list variants until a selector field exists.
- Add priority fields.
- Add predicate-based variant matching.
- Preserve first-match only where golden evidence requires it.

Required evidence:

- Search current `tsldata/` for list-backed implementation variants.
- Identify whether generated outputs depend on ordering.
- Ask domain owners for intended semantics.

Implementation blocked:

Selection of ambiguous variants is blocked. Basic selection for simple map variants is not blocked.

## OQ-004: How Much Byte-For-Byte Output Compatibility Is Required?

Why it matters:

Strict generated output compatibility can constrain rendering and formatting decisions.

Possible answers:

- Byte-for-byte compatibility for selected public headers only.
- Semantic compatibility with new formatting.
- Golden compatibility only for representative fixtures.

Required evidence:

- Consumers of generated headers/source.
- Existing release expectations.
- Selected golden baseline outputs.

Implementation blocked:

Backend golden milestone is blocked until policy is chosen. Earlier model/parser milestones are not blocked.

## OQ-005: What Is The Long-Term TSIL Grammar And Semantics?

Why it matters:

TSIL includes calls, loops, type expressions, generation-time values, attributes, and backend translations. String rewriting will not scale.

Possible answers:

- Formalize TSIL grammar before backend work.
- Implement a minimal parser for dependency extraction first.
- Defer full TSIL semantics until after first backend slice.

Required evidence:

- `frozen/tsl-gen/tsl_gen/tsil.lark`
- TSIL bodies in `tsldata/primitives/**.tsl`
- Existing lowering behavior that must be preserved.

Implementation blocked:

Dependency and lowering milestones are partially blocked. Catalog milestones are not blocked.

## OQ-006: How Should Generic/Sized Extensions Be Represented?

Why it matters:

Extensions such as `generic` and `oneAPIfpga` have `vector_bits "sized"` and tests use `test_sizes_bits`. Rendering may require type parameters such as `Bits`.

Possible answers:

- Model sized extensions as extension plus size parameter.
- Expand sized extensions into concrete target variants during selection/test planning.
- Treat sized bits as backend-specific generic parameters.

Required evidence:

- `tsldata/extensions/extension.tsl`
- Backend templates for generic and oneAPIfpga.
- Existing generated outputs for `frozen/out/tsl/tsl_generic.hpp`.

Implementation blocked:

Full generic backend planning is blocked. Basic fixed-width selection is not blocked.

## OQ-007: What Is The Correct Policy For Runtime-Lane Extensions Such As SVE?

Why it matters:

SVE has scalable vector length and runtime lane behavior. Test planning and generated code cannot assume fixed lanes.

Possible answers:

- Treat runtime-lane extensions as a separate test/generation mode.
- Skip specific templates according to manifest until full support exists.
- Generate runtime-lane-aware tests for all supported templates.

Required evidence:

- `tsldata/extensions/extension.tsl`
- `frozen/generator_specs/tests.yaml`
- `frozen/run_all.sh` SVE behavior.

Implementation blocked:

SVE test planning and backend slices are blocked. Fixed-lane backends are not blocked.

## OQ-008: Which CLI Compatibility Is Required?

Why it matters:

Legacy workflows expose `run_all.sh`, `run_tests.py`, and `python -m tsl_gen` options. The new CLI can be cleaner, but users may rely on existing flags.

Possible answers:

- New CLI with no compatibility promises.
- Compatibility subcommands or aliases for common legacy workflows.
- Keep shell workflow as wrapper around new CLI.

Required evidence:

- Current users and automation.
- CI scripts.
- Documentation or release expectations.

Implementation blocked:

CLI milestone is blocked. Core API is not blocked.

## OQ-009: Should Generated Documentation Be In Scope?

Why it matters:

Legacy workflows generate TSL/TSIL documentation with MkDocs and coverage reports.

Possible answers:

- Include documentation generation as a later backend/reporting feature.
- Keep documentation tooling separate from the generator.
- Defer until code generation stabilizes.

Required evidence:

- Required docs outputs.
- Consumers of `frozen/docs` and generated site.

Implementation blocked:

Documentation generation is blocked. Core generation is not blocked.

## OQ-010: What Backends Are First-Class For The First Release?

Why it matters:

Evidence supports C++, C17, and Rust, but implementation priority affects architecture and test coverage.

Possible answers:

- C++ only first, with backend protocol ready for others.
- C++ and Rust.
- C++, C17, and Rust from the start.

Required evidence:

- User priorities.
- Existing consumer workflows.
- Golden baseline needs.

Implementation blocked:

Full backend implementation priority is blocked. Backend interface design is not blocked.

## OQ-011: Should Type And Template Shapes Be Parsed Or Kept As Strings Initially?

Why it matters:

`tsldata/detail/templates.tsl` has shape strings like `(vector, vector) -> vector`. They are useful for validation and docs but not yet formalized.

Possible answers:

- Parse shapes in the catalog milestone.
- Keep as strings and parse when needed.
- Replace with structured fields in TSL data.

Required evidence:

- How shapes are used by generators and tests.
- Whether shape strings are authoritative or descriptive.

Implementation blocked:

Not for early catalog construction. Stronger validation is blocked.

## OQ-012: What Is The Error Policy For Unknown Extra Fields?

Why it matters:

TSL data may include backend- or future-specific fields. Strict rejection improves safety but may block extensibility.

Possible answers:

- Preserve unknown fields with warnings.
- Reject unknown fields outside documented extension maps.
- Allow unknown fields by namespace/prefix.

Required evidence:

- Current extra fields in `tsldata/`.
- Expected authoring workflow.

Implementation blocked:

Validation strictness is partially blocked. Catalog can preserve extra fields now.

## Follow-ups from Milestone 2 review

- Add focused tests for invalid UTF-8 and read failure diagnostics where practical.
- Standardize whether file-level diagnostics use synthetic locations such as `line=1, column=1` or `location=None` before CLI diagnostic rendering.
- Clarify whether source digests are computed over normalized text or raw bytes before digest behavior becomes externally visible.

## Follow-ups from Milestone 3 review

- Clarify parser public API exports and keep Lark construction private. 
- In Milestone 4, verify SyntaxNode structure is sufficient for typed catalog construction without parser-private leakage. 
- Consider changing the corpus test to assert “all discovered files parse” without hard-coding the count, or document the count as an intentional current-corpus check.

## Follow-ups from Milestone 4 review

- Replace generic `CatalogEntry` with typed models for flags, language type maps, translation maps, primitive tests, and implementation specs when later milestones require semantic access to those concepts.
- Revisit whether catalog construction should remain in `domain` or move to a boundary/conversion module if the strict target-architecture dependency rule becomes important.
- Add focused tests for duplicate fields inside extension, template, and primitive bodies if duplicate fields are intended to remain structural errors.
- Watch repeated nested field representation: tuple-grouped repeated fields may need a richer representation if occurrence identity matters during later validation.

## Follow-ups from Milestone 5 review

- Add focused tests for invalid signature syntax with source locations.
- Add direct tests for `v:=sequence` parameter-count behavior.
- Clarify whether repeated declaration parameters must include `...`.
- Treat the signature rule table as typed behavioral data; consider moving it to a typed manifest once rule churn slows.

## Follow-ups from Milestone 6 review

- Add typed flag models and flag-alias normalization before or during Milestone 7.
- Promote primitive tests and implementation specs out of generic `CatalogValue` structures when later stages depend on them.
- Add a focused test for all-unknown selectors in unambiguously extension-keyed `requires` maps.
- Revisit conservative `requires` validation once flags and implementation specs are typed.
- Decide whether `ReferenceValidatedCatalog` should remain a marker-only pipeline gate or gain stronger typed invariants in later stages.