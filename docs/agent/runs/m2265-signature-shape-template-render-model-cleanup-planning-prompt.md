# M226.5 Signature-Shape Template Render-Model Cleanup Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M225 as accepted and M226 as stopped by preflight.

This is a planning task, not an implementation task. Use the orchestrated
planning/review workflow:

```text
main planner
-> read-only evidence/boundary/documentation subagents
-> focused planning revision if `Needs Revision`
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
```

M226 preflight found a plausible real x86 fixture but stopped before
implementation because the current primitive render boundary still requires
whole C++/Rust function assembly in Python. The observed candidate is
`tsldata/primitives/arithmetic/fundamental.tsl` `add` with signature
`v:=(v,v)` and an `avx2` `emit_return(intrin_compose<add, suffix=...>(left,
right));` body. The `new_chat_test` branch is negative evidence: it bundled
too many concerns into one M226 attempt.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/flaws-to-fix.md`
- `docs/agent/runs/m226-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/primitive_render_model.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `supplementary/templates/cpp/primitive.hpp.in`
- `supplementary/templates/rust/primitive.rs.in`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tsldata/primitives/arithmetic/fundamental.tsl`

Also inspect, read-only, the `new_chat_test` branch diff as cautionary
evidence. Do not cherry-pick it wholesale.

## Goal

Plan the smallest executable cleanup that lets a future M226 render the real
`v:=(v,v)` x86 intrinsic fixture without adding new raw C++/Rust
function/header/module strings in Python.

The plan must protect the accepted lowering model:

- implementation bodies remain raw source spans plus typed lowerable token
  values;
- lowered body-token values and backend-translated intrinsic values remain
  typed leaf inputs to rendering;
- the selected primitive signature shape is a typed selector carried from the
  catalog/lowering path;
- supplementary C++/Rust templates own presentation shape only.

## Planning Scope

Produce a concrete next executable milestone that answers:

- Which typed render-model fields are missing between lowering and primitive
  templates?
- Where should the exact `v:=(v,v)` signature-shape selector be carried?
- What minimal C++ and Rust supplementary shape templates should exist for
  `v:=(v,v)`?
- How should already-translated body-token leaf text be passed into those
  templates without template-side parsing or semantics?
- Does M226 also need a narrow selected-profile primitive artifact replacement
  policy before it can write `avx2` profile files, or can that wait?
- Which current Python whole-function string assembly must be removed or
  quarantined before M226 resumes?

The planned executable slice should be narrow enough that it can be reviewed
with tests before real intrinsic semantics are added.

## Guardrails

- Do not implement code in this planning task.
- Do not resume M226 inside this prompt.
- Do not plan a broad signature/template framework. Plan only the exact
  selected `v:=(v,v)` shape plus the typed extension point needed to reject
  unsupported shapes.
- Do not parse TSIL, infer source semantics, or repair source forms.
- Do not move backend semantic decisions into templates.
- Do not add new IR merely to preserve milestone history. Any proposed typed
  object must state its stable taxonomy category from AGENTS.md.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.
- Do not copy the `new_chat_test` branch wholesale.
- Keep C++ and Rust in parity.

## Required Planning Subagents

Run read-only subagents before finalizing the plan:

1. Evidence auditor: confirm the observed `v:=(v,v)` x86 fixture and summarize
   the `new_chat_test` diff only as negative evidence.
2. Boundary auditor: inspect current primitive render models/templates and
   identify the smallest missing typed boundary.
3. Documentation auditor: check that the proposed next prompt aligns with
   AGENTS.md, PLANS.md, and redesign docs.

If any reviewer returns `Needs Revision`, make only focused planning/doc fixes
and rerun the relevant focused review. If any returns `Return To Planner` or
`Reject`, stop and create the appropriate planner prompt.

## Expected Output

Update `docs/redesign/implementation-roadmap.md` with the accepted M226.5 plan
and the selected next executable milestone.

Update `docs/agent/current-redesign-state.md` to point at the next concrete
prompt.

Create the next concrete prompt under `docs/agent/runs/`. The next prompt may
be an execution-review loop only if M226.5 selects one small executable
cleanup; otherwise create a focused follow-up planning prompt.

## Required Validation

Run:

```bash
git diff --check
```

## Completion Rules

Before finishing:

- report the read-only subagent verdicts;
- report the exact validation result;
- do not mark M226 accepted;
- do not start the selected next milestone.

## Final Report

Report:

1. Planning summary.
2. Review/audit verdicts.
3. Validation command and exact result.
4. Next active prompt path.
