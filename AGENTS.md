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

## Semantic Rule Boundary

Semantic lowering and backend translation must express behavior as typed rules or typed evaluator functions over explicit IR/domain values.

Do not use ad-hoc dictionary mappings as the semantic model past parser/catalog boundaries. Dictionary-like metadata may be loaded at I/O or catalog boundaries, but downstream stages must consume typed objects, typed rule records, typed translation requests, or typed translation results.

A lookup table is acceptable only when its entries are typed rule values with documented supported cases, unsupported cases, diagnostics, and tests. It must not become an unreviewed shortcut from raw keys such as `(intrinsic, extension, type)` directly to emitted backend text.

Do not implement semantic behavior through raw text rewriting. String templates or rendered text may appear only after lowering/translation has produced typed values for the selected slice.

## Lowering IR Taxonomy And Complexity Guardrails

Typed IR exists to make semantic boundaries explicit, not to encode every
milestone's history as a new object family. Before adding a new lowering IR
class, request record, result record, inventory, package, or handoff type, the
plan must state which stable category it belongs to:

- semantic fact: an accepted domain value produced by lowering;
- request: a typed unresolved need for a later stage;
- result: a typed fulfillment of a request from explicit facts/rules;
- inventory: a deterministic collection of accepted facts, not readiness;
- provenance: source/object identity needed for diagnostics and traceability;
- rule input: explicit typed metadata supplied before evaluation;
- stage envelope: the named pipeline boundary carrying one of the above.

New IR should have a durable semantic reason to exist. Do not add a class whose
only purpose is to preserve a long chain of previous objects when a shared,
typed provenance value or narrower reference would express the same contract
more clearly. Object identity may be required for diagnostics and traceability,
but it should be encapsulated behind a named provenance contract instead of
repeated as ad hoc `source_*` fields through every result layer.

Names should describe the domain boundary, not the milestone trail. Exact or
narrow source forms may appear in source adapters and validation boundaries, but
the downstream IR taxonomy should remain small enough that future stages can
answer: what fact was produced, what request is unresolved, what result fulfills
it, and what provenance explains it?

When a planned milestone would introduce another narrow request/result family,
the planner must first check whether the right next slice is a taxonomy or
provenance consolidation. Consolidation milestones must preserve accepted
diagnostics, deterministic keys, object identity where required, public
imports, and boundary behavior; they must not use the cleanup as cover for new
backend semantics, rendering, source repair, or broad abstractions.

## Source Body Integrity

TSL implementation bodies are source inputs, not repair targets. The generator
may recognize documented exact forms, lower them into typed IR/facts, and emit
diagnostics for malformed or unsupported forms. It must not silently correct,
normalize, rewrite, complete, reorder, or guess the intended meaning of a
possibly wrong `.tsl` implementation body.

Milestones that handle narrow implementation-body shapes must name the accepted
forms exactly. Nearby forms, malformed variants, missing operands, surprising
tokens, or source-data mistakes are negative tests and diagnostic boundaries,
not invitations to add extra supported syntax. Generated output must reflect
accepted typed lowering/translation results only, never a best-effort repair of
the original source text.

## Module Size And Encapsulation Guardrails

Keep production files cohesive and small enough to review. Prefer multiple
focused modules with explicit ownership, typed value objects, typed rule
records, and narrow public functions over large catch-all files. Object-oriented
encapsulation is encouraged when a concept owns state, invariants, or behavior;
pure functions remain appropriate for simple stateless transformations.

When a production file approaches roughly 1,000 physical lines, or a milestone
would add a large new responsibility to an already substantial file, the plan
must either split the work into a focused module or document why a temporary
exception is safer. New private modules must not become replacement monoliths:
state their ownership, keep imports one-way where practical, avoid facade
back-imports, and add boundary tests for public surface stability and import
direction when the risk is meaningful.

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

## Codex Workflow State

Codex tasks must read `docs/agent/current-redesign-state.md` before planning,
executing, reviewing, or revising a milestone.

Concrete run prompts live under `docs/agent/runs/`. Reusable prompt templates
live under `docs/agent/prompt-templates/`. Subagent role definitions live under
`docs/agent/subagents/`.

The repository state file, not chat history, is the authoritative handoff for:

- accepted milestone
- current action
- active run prompt under `docs/agent/runs/`
- next expected verdict or action
- boundary rules
- known follow-ups
- validation expectations
- stop condition, if no next prompt should be generated

No Codex task is complete until it has written the next concrete prompt under
`docs/agent/runs/` and updated `docs/agent/current-redesign-state.md` to point
at it, unless the task intentionally ends the workflow and records an explicit
stop condition. The next-run prompt protocol lives in
`docs/agent/next-run-prompt-protocol.md`.

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

## Multi-Agent Workflow

When Codex subagents are used, the main thread acts as orchestrator.

Subagents may run in parallel for planning, review, validation, documentation
audits, or evidence audits. Only one write-capable executor should modify a
given worktree at a time. Review and audit subagents are read-only unless
explicitly assigned a focused revision task.

Subagents must follow the same clean-redesign rules:

- one milestone at a time
- no runtime dependency on `frozen/`
- typed boundaries and typed semantic rules
- explicit diagnostics
- deterministic validation
- no renderer-side semantic inference

The orchestrator owns final state updates to
`docs/agent/current-redesign-state.md`.

## Executor Review Loop

Codex may run an orchestrated executor-review loop when the active run prompt
explicitly asks for it.

The loop is:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if `Needs Revision`
-> focused re-review
-> next-run prompt generation
```

Rules:

- Only one write-capable executor or revision executor may modify a worktree at
  a time.
- Reviewer, validation-auditor, evidence-auditor, documentation-auditor, and
  boundary-auditor subagents are read-only.
- A revision executor may modify only files needed to fix the blocking review
  issues.
- The orchestrator owns the final verdict consolidation, state transition, and
  next prompt creation under `docs/agent/runs/`.
- If review returns `Return To Planner` or `Reject`, stop implementation and
  create the appropriate planner/rollback prompt instead of continuing.

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
