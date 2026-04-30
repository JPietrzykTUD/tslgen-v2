# Execution Agent Template

Use this prompt when assigning an implementation milestone to a coding agent.

```text
You are implementing one milestone from the clean-room TSL generator redesign.

Repository rules:
- This is a clean redesign, not a legacy rewrite.
- Do not organize work around `frozen/` modules.
- Use `frozen/` only as evidence for required behavior.
- Treat `tslgen/` and `tsldata/` as exploratory/current data, not binding architecture.
- Do not modify implementation code outside the selected milestone scope.

Milestone:
<paste one milestone from docs/redesign/implementation-roadmap.md>

Before coding:
1. Read AGENTS.md and PLANS.md.
2. Read the relevant redesign docs:
   - docs/redesign/requirements.md
   - docs/redesign/behavioral-spec.md
   - docs/redesign/domain-model.md
   - docs/redesign/target-architecture.md
   - docs/redesign/pipeline-design.md
   - docs/redesign/testing-strategy.md
   - docs/redesign/open-questions.md
3. State the milestone goal, exact scope, validation criteria, and out-of-scope items.

Implementation requirements:
- Build a thin vertical slice.
- Use typed Python and explicit domain/configuration objects.
- Keep pure logic separate from filesystem, hardware, CLI, and artifact-writing side effects.
- Return structured diagnostics from validation logic.
- Keep ordering deterministic.
- Add tests required by the milestone.
- Do not add a runtime dependency on `frozen/`.

Validation:
- Run targeted tests.
- Report any tests not run and why.
- Update redesign docs if you discover new behavior, decisions, or open questions.

Stop conditions:
- Stop and update docs/redesign/open-questions.md if a required behavior cannot be inferred from evidence.
- Stop if the milestone would require speculative architecture outside its scope.

Final response:
- Summarize changed files.
- Summarize tests run.
- Note docs updated.
- Note unresolved blockers or follow-up milestones.
```
