# Agent Instructions

## Repository Purpose

This repository is being redesigned as a maintainable Python generator for TSL data and SIMD-oriented code artifacts. The legacy implementation in `frozen/` is evidence, not architecture. The exploratory sketch in `tslgen/` and the TSL data in `tsldata/` are useful context, but future implementation work must be driven by the redesign documents under `docs/redesign/`.

The system domain includes:

- A TSL data language for primitive operations, type groups, lane sets, backend translation maps, templates, and hardware extensions.
- Semantic validation and selection of primitive implementations by backend, extension, type, attributes, and feature requirements.
- Deterministic generation of C++, Rust, tests, support metadata, and future backend artifacts.

## Redesign Policy

This project is a clean-room redesign. Do not ask how to rewrite the old code file by file. Ask what system should exist given the observed domain requirements.

Agents must:

- Implement one thin architectural slice at a time.
- Preserve required observable behavior only when documented as a requirement.
- Prefer explicit typed models, small modules, pure functions, and clear side-effect boundaries.
- Keep implementation structure aligned with `docs/redesign/target-architecture.md` and `docs/redesign/pipeline-design.md`.
- Update docs when implementation reveals a requirement, decision, or open question.

Agents must not:

- Create a legacy-to-new module migration map as the primary plan.
- Preserve brittle legacy structures for convenience.
- Add compatibility wrappers around poor abstractions unless a documented external API requires it.
- Use global mutable state for pipeline state, selection state, diagnostics, templates, or configuration.
- Treat dictionaries as domain objects past the parser boundary.
- Hide file I/O inside parsing, validation, lowering, rendering, or selection logic.

## Legacy-Code Policy

`frozen/` may be inspected only as evidence for:

- Required behavior and compatibility constraints.
- Supported input forms and output artifacts.
- Domain concepts and invariants.
- Existing workflows and edge cases.
- Test and diagnostics expectations.

Do not organize new code around `frozen/tsl-gen/tsl_gen` modules. Do not port files, classes, or functions unless a redesign document explicitly identifies a small reusable idea worth re-expressing behind a new interface.

Useful legacy evidence includes:

- `frozen/tsl-gen/tsl_gen/tsl_data.lark` for TSL syntax.
- `frozen/generator_specs/signatures.yaml` for signature-to-template resolution behavior.
- `frozen/generator_specs/backend_cpp.yaml` and `frozen/generator_specs/backend_rust.yaml` for planned backend manifest concepts.
- `frozen/generator_specs/wrapper_shapes.yaml` for wrapper signature behavior.
- `frozen/generator_specs/tests.yaml` and `frozen/tsl-gen/tsl_gen/backend/tests/planner.py` for test planning behavior.
- `frozen/run_all.sh` and `frozen/run_tests.py` for workflows and generated side effects.

## Important Directories

- `docs/redesign/`: source of truth for requirements, behavior, architecture, pipeline, testing, and roadmap.
- `docs/agent/`: reusable prompts and review checklists for future agents.
- `tsldata/`: current TSL data corpus and likely source fixture set for the redesign.
- `tslgen/`: exploratory implementation sketch. Treat as non-binding.
- `frozen/`: legacy evidence only. Do not extend it for the redesigned implementation.
- `.agents/skills/`: optional repo-scoped workflows for redesign planning, execution, and review.

## Coding Conventions

When implementation begins:

- Use typed Python and keep mypy-friendly boundaries where practical.
- Prefer `@dataclass(frozen=True, slots=True)` for immutable domain/value objects unless another local convention is deliberately chosen.
- Use explicit configuration objects instead of loose argparse namespaces, environment reads, or globals.
- Use protocols/interfaces for backend-specific behavior.
- Keep parser output separate from the domain catalog.
- Accumulate diagnostics with source locations; avoid `SystemExit` from pure logic.
- Keep deterministic ordering for maps, plans, render jobs, artifacts, and diagnostics.
- Keep path resolution in loader/configuration layers, not in model or renderer code.

## Testing Expectations

Every implementation milestone needs tests proportionate to its risk:

- Unit tests for pure parsing, model normalization, validation, selection, lowering, and rendering helpers.
- Golden-file tests for generated text and artifact manifests.
- Integration tests for CLI/API slices.
- Regression tests for selected legacy-observed behavior from `frozen/` and `tsldata/`.
- Determinism tests that run the same pipeline twice and compare artifacts and diagnostics.
- Diagnostic tests that assert codes, severity, file path, line, column, and actionable message text.

Do not rely on host CPU features for normal unit tests. Hardware autodetection must be injectable.

## Documentation Expectations

Documentation is part of the implementation contract. Update:

- `docs/redesign/open-questions.md` when an issue cannot be resolved from evidence.
- `docs/redesign/design-decisions.md` when an architectural decision is made or revised.
- `docs/redesign/behavioral-spec.md` when new required behavior is confirmed.
- `docs/redesign/implementation-roadmap.md` when milestone scope changes.

Keep docs behavior-centered. Avoid describing work as porting or moving legacy modules.

## Implementation Workflow

1. Read `PLANS.md`.
2. Select exactly one milestone from `docs/redesign/implementation-roadmap.md`.
3. Read the docs relevant to that milestone.
4. Define scope, validation criteria, and out-of-scope work.
5. Implement the smallest usable vertical slice.
6. Add tests and fixtures.
7. Run targeted tests.
8. Update docs if evidence or design changed.
9. Stop if an unresolved architectural question would force speculative design.

## Review Workflow

Reviews must use `docs/agent/review-checklist.md`. Findings should focus on:

- Architecture consistency.
- Accidental legacy leakage.
- Domain model clarity.
- Validation and diagnostics quality.
- Deterministic output.
- Test coverage and fixture quality.
- Maintainability.

## Do-Not Rules

- Do not modify implementation code when the task is documentation-only.
- Do not edit generated outputs unless the task explicitly requires regenerated artifacts.
- Do not add hidden network, hardware, or environment dependencies to tests.
- Do not make `frozen/` a runtime dependency of new code.
- Do not silently skip diagnostics for malformed input.
- Do not write new generated files nondeterministically.
- Do not introduce broad abstractions until a milestone demonstrates the need.
