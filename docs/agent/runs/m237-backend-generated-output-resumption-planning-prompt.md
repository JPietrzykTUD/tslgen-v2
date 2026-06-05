# M237 Backend Generated-Output Resumption Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M236 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. M236 completed the closeout lowering cleanup and did not record a
blocking diagnostic issue. Per the M236 exit rule, this prompt returns the
workflow to backend/generated-output work.

Use read-only subagents for evidence, architecture/boundary, documentation,
and validation audits. The orchestrator owns final state and next-prompt
updates.

## Accepted State

Accepted through:

```text
Milestone 217: Primitive Template Boundary
Milestone 218: Typed Primitive Render Context
Milestone 222: Primitive Render Plan
Milestone 223: First Real Generated Primitive
Milestone 224: Parsed Tiny TSL To Generated Project
Milestone 225: Generated Profile Build Flags
Milestone 227: V/V Function-Shape Template Render Boundary
Milestone 229-M236: Parser/body/lowering foundation and closeout cleanup
```

M226/M228 real x86 intrinsic fixture attempts stopped before acceptance because
they pulled too many concerns into one slice. Since then, M229-M236 added the
outer TSL parser boundary, source-body lexical regions, recursive keyword
fragments, pairwise cleanup, shared primitive-call fragment adaptation, and
payload diagnostic propagation. The next task is to reassess backend/output
work from this cleaner baseline, not to continue primitive-call cleanup.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/flaws-to-fix.md`
- `docs/agent/runs/m216-backend-rendering-roadmap-planning-prompt.md`
- `docs/agent/runs/m226-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `docs/agent/runs/m2265-signature-shape-template-render-model-cleanup-planning-prompt.md`
- `docs/agent/runs/m228-restarted-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/rendering/primitive_render_model.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`
- `supplementary/buildsystem/cpp/`
- `supplementary/buildsystem/rust/`
- `tsldata/primitives/arithmetic/fundamental.tsl`

## Goal

Plan the next backend/generated-output milestone after the parser/lowering
detour.

The plan must answer:

1. What parts of the accepted generated-output path already work from parsed
   `.tsl` to generated C++/Rust project artifacts?
2. Which accepted parser/body/lowering changes from M229-M236 remove blockers
   from the stopped M228 real x86 intrinsic fixture?
3. Which blockers remain before real intrinsic output can be generated and
   compile-tested?
4. What is the smallest next executable backend/output slice?

## Planning Scope

Audit and record:

- Current flow through parsed `.tsl`, catalog construction, selection,
  lowering, backend translation, typed render plans, supplementary templates,
  generated-project composition, artifact writing, and build verification.
- The current C++/Rust parity state.
- Whether `tsldata/primitives/arithmetic/fundamental.tsl` `add` with an x86
  profile is now a viable next fixture or still too broad.
- Whether the next executable slice should be:
  - resumed real x86 intrinsic fixture;
  - a smaller backend translation/render bridge for already-lowered
    `intrin_compose` tokens;
  - generated-project compile/test verification for existing scalar output; or
  - another concrete backend/output prerequisite.
- Which typed values must be passed into templates so no C++/Rust code or
  semantic decisions drip into Python strings.

Choose exactly one next concrete prompt.

## Guardrails

- Do not implement production code or tests in M237.
- Do not reopen lowering or create another primitive-call cleanup prompt unless
  this planning review finds a concrete backend-output blocker caused by M236.
- Do not add raw C++/Rust function/header/module strings in Python.
- Do not put backend semantic decisions, primitive selection, dependency
  closure, type/intrinsic selection, feature gating, or source parsing into
  templates.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.
- Keep C++ and Rust in parity unless a concrete temporary split and catch-up
  prompt are recorded.

## Required Planning Subagents

Run read-only subagents:

1. Evidence auditor: inspect accepted backend/generated-output modules,
   templates, writer/verifier, and `fundamental.tsl` fixture evidence.
2. Architecture/boundary auditor: check template-first, presentation-only,
   typed render model, no renderer-side semantics, no lowering reopen, and
   C++/Rust parity.
3. Documentation auditor: verify roadmap/state/design docs record the selected
   backend-output resumption path and no primitive-call cleanup continuation.
4. Validation auditor: check required validation and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused planning/doc fixes
and rerun the relevant focused audit. If any returns `Return To Planner` or
`Reject`, record that result and create the appropriate next prompt.

## Required Validation

Run exactly:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M237 planning
  result.
- Update `docs/agent/current-redesign-state.md` to point at the next concrete
  prompt.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/redesign/design-decisions.md` or
  `docs/redesign/open-questions.md` only if the planning result changes or
  discovers a design boundary or blocker.

Do not start the selected backend/output milestone in M237.

## Final Report

Report:

1. Planning result.
2. Selected next milestone and why it is useful.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
