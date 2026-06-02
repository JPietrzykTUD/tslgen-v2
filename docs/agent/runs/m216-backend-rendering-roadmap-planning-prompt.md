# M216 Backend Rendering Roadmap Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M215 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, architecture/boundary,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 215: C++ Body Token Substitution Rendering
```

M215 added a focused C++ body-token substitution renderer for accepted
backend-intrinsic handoff streams. It preserves raw text spans and substitutes
matching M214 rendered intrinsic calls for request segments by typed request
object/provenance. It does not invent statement syntax, parse surrounding C++,
render Rust, render generated projects, or reopen lowering.

The next task is no longer to select another narrow C++ token-family slice.
The accepted direction is a template-first backend/rendering roadmap that keeps
C++ and Rust in parity and reaches compile-tested generated primitive output
early.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/rendering/supplementary.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/cpp/body_tokens.py`
- `supplementary/buildsystem/cpp/templates/`
- `supplementary/buildsystem/rust/templates/`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`
- accepted handoff/translation modules for backend type queries, backend value
  queries, source operations, backend-output requests, backend control,
  masks, generation loops, and generation declarations as needed.

## Goal

Plan the next backend/rendering sequence after M215.

The plan must preserve these accepted boundaries:

- Backend-facing milestones should keep C++ and Rust in parity unless the
  prompt records a concrete reason for a temporary one-backend slice.
- Primitive templates move near the front of backend/output work so C++/Rust
  wrapper and artifact text does not accumulate as large raw strings in Python.
- Templates are presentation-only over already-decided typed render values.
- The implementation-body model remains:

```text
raw source text spans + lowerable/renderable token islands
```

Raw spans stay raw. Already-lowered/rendered token islands are substituted.
Surrounding syntax is not interpreted.

## Provisional Roadmap To Validate

Validate, refine, and record this ten-step sequence:

1. **M216: Backend rendering roadmap planning.**
   Record backend parity, template-first rendering, and early compile/test
   gates.
2. **M217: Primitive template boundary.**
   Add/define C++ and Rust primitive templates under
   `supplementary/templates/{cpp,rust}/`, with presentation-only guardrails and
   typed render context requirements. This should not add backend semantics.
3. **M218: Typed primitive render context.**
   Define the already-decided values primitive templates may consume, such as
   selected primitive name, profile, signature render facts, includes/imports,
   and rendered body text values.
4. **M219: Rust intrinsic call rendering parity.**
   Bring Rust to parity with C++ M214 from typed M213 invocation IR, including
   explicit `core::arch::*` path policy.
5. **M220: Shared body-token substitution contract.**
   Introduce only the minimal typed replacement/provenance contract needed by
   two accepted consumers. Avoid raw-text matching and avoid a broad registry.
6. **M221: C++/Rust body-token substitution parity.**
   Use the shared contract to feed rendered intrinsic/type/value/source-operation
   token islands into backend body text for both backends.
7. **M222: Primitive render plan.**
   Build a typed plan for selected primitive, selected profile, topologically
   ordered dependencies, signature facts, and rendered body-token output.
8. **M223: First real generated primitive.**
   Render one tiny primitive through C++ and Rust templates, write artifacts,
   and compile/test generated output.
9. **M224: Expand primitive coverage.**
   Add a small dependency-bearing selected subset while continuing to
   compile/test both backends.
10. **M225: Profile matrix / corpus subset.**
    Compile/test selected profiles and a broader realistic corpus slice.

## Planning Questions

Answer these before selecting the next concrete milestone:

- Is the ten-step roadmap dependency order sound given the accepted M188-M215
  implementation?
- Should M217 add actual minimal primitive template files now, or should it
  first define the typed template boundary and guardrails more explicitly?
- What is the smallest C++/Rust primitive template pair that proves the
  presentation-only boundary without smuggling backend semantics into
  templates?
- Which Python modules currently contain acceptable tiny render snippets and
  which are at risk of accumulating language code that belongs in templates?
- What typed values must exist before a primitive template can render a real
  primitive without deciding semantics?
- Which parity gap is more urgent after templates: Rust intrinsic call
  rendering or the shared body-token replacement contract?
- How soon can a generated real primitive be written and compiled with the
  existing `ArtifactWriter` and `BuildVerifier`?
- Does any step need to be split to avoid overengineering or broad dispatcher
  behavior?

## Scope Options

Choose exactly one next executable milestone. Expected candidate:

- **M217: Primitive template boundary.** Establish the C++/Rust primitive
  template location, typed presentation context contract, and tests/guardrails
  proving templates do not own semantic decisions.

If evidence shows a different first step is required before primitive
templates, record the blocker and choose only that one prerequisite.

## Guardrails

- Do not implement production code or tests in M216.
- Do not reopen lowering or add raw TSIL rescans.
- Do not parse `return`, `emit_return(...)`, assignments, loops, braces,
  semicolons, operators, array indexing, or surrounding target-language syntax.
- Do not render or interpret `details::*` helpers.
- Do not invent a special return-statement, assignment, loop, or expression
  renderer.
- Do not continue C++-only backend rendering unless the plan records a concrete
  parity reason and a nearby Rust catch-up milestone.
- Do not put backend semantic decisions in templates.
- Do not add a broad registry, dispatcher, worklist, or replacement framework
  unless the plan names at least two accepted concrete consumers and a minimal
  contract they both need.
- Preserve source-authored raw text exactly when it is not a selected
  lowerable/renderable island.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: accepted backend/rendering outputs, template assets,
   writer/verifier behavior, and current C++/Rust parity gaps.
2. Architecture/boundary auditor: template-first policy, presentation-only
   templates, raw-span preservation, no statement parsing, no lowering reopen,
   and no overbroad replacement framework.
3. Documentation auditor: roadmap/state/prompt consistency and whether the
   M216-M225 plan is captured coherently.
4. Validation auditor: required validation command and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused documentation or
prompt fixes and rerun the relevant focused audit. If any returns
`Return To Planner` or `Reject`, record that result and create the appropriate
next prompt.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Report the exact result.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the planning result;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- update other redesign docs only if the planning decision changes or
  clarifies an accepted design boundary;
- do not start the next milestone.

## Final Report

Report:

1. Planning result.
2. Selected next milestone and why it is useful.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
