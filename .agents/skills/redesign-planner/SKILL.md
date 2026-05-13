# Redesign Planner Skill

Use this skill when planning a new implementation slice for the TSL generator redesign.

## Workflow

0. Read `docs/agent/current-redesign-state.md` if it exists.
1. Read `AGENTS.md` and `PLANS.md`.
2. Pick exactly one milestone from `docs/redesign/implementation-roadmap.md`.
3. Read the relevant redesign docs for that milestone.
4. Identify repository evidence needed for behavior, using `frozen/` only as evidence.
5. Produce a short implementation plan with:
   - Goal.
   - Scope.
   - Affected new modules.
   - Required tests.
   - Validation commands.
   - Out-of-scope items.
   - Open questions.
6. Stop if an unresolved architectural question blocks a clean slice.

## Rules

- Do not plan a module-by-module rewrite.
- Do not use legacy module names as the organizing principle.
- Prefer a thin vertical slice.
- Update `docs/redesign/open-questions.md` when evidence is insufficient.
