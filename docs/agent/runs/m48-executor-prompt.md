# Milestone 48 Executor Prompt

You are the Codex executor for the clean-room `tslgen` redesign.

Do not start Milestone 49.

## Accepted State

Milestones 1 through 47 are accepted.

Post-M47 planning is accepted and selected:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Goal

Implement the Milestone 48 generation-time semantic lowering slice:

```text
if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
  ...
} else<generation> {
  ...
}
```

The condition must consume typed M43 `GenerationTypeRef(kind="base.in")`
values and must prune the selected branch with M42-style provenance.

## Scope

- Recognize only the exact signedness condition:

  ```text
  value<generation>(type::is_signed(type<generation>(base::in)))
  ```

- Reuse the M42 generation branch pruning model and selected-branch-only
  unresolved-helper diagnostics.
- Resolve the inner `type<generation>(base::in)` through the M43 typed
  `GenerationTypeRef` model.
- Evaluate signedness as a typed boolean generation value for selected concrete
  integer tags already supported by M43:
  `si32 -> true` and `ui32 -> false`.
- Keep deterministic branch provenance and diagnostic ordering.
- Update docs only when implementation reveals a requirement, decision, or open
  question.

## Out Of Scope

- Milestone 49 or any later milestone.
- Plain `else` branch syntax, including conversion evidence in
  `repr_change.tsl`.
- Shift or conversion output parity.
- Direct intrinsic rendering.
- Backend suffix/type translation, prefix/post/infix/immediate modifiers, or
  broad translation-map evaluation.
- Backend rendering changes, generated output, CLI/report/writer work, Rust
  output, compiler execution, or generated-test execution.
- Vector/register metadata, vector transforms, masks, casts, loops,
  `if<compile>`, primitive calls, variables, aliases, and direct
  `intrin<...>` parsing.
- Signedness predicates over floats, masks, pointers, wildcard/generic tags,
  vector types, or backend-scoped type requests.
- Runtime dependency on `frozen/`.

## Evidence

- Exact M48 branch-shape evidence:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- Predicate-only evidence, not accepted branch syntax:
  `tsldata/primitives/conversion/repr_change.tsl:1210-1217`.
- Frozen evidence only:
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:319-339`,
  `:403-404`, `:4586-4596`, and `:5011-5097`.

Do not import or execute `frozen/`.

## Required Tests

- `si32` prunes to the true branch.
- `ui32` prunes to the false branch.
- Repeated pruning is deterministic.
- Unresolved helpers in the selected branch are diagnosed.
- Unresolved helpers in the unselected branch are not diagnosed.
- Diagnostics cover malformed branches, unsupported predicates, unsupported
  nested type query shapes, missing type context, unknown tags,
  unsupported/non-integer tags, wildcard/generic tags, and raw unresolved
  generation helpers at the backend translation boundary.
- Renderer non-evaluation regressions remain in force.

## Required Validation

Run the milestone-specific targeted tests plus:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If you change the accepted validation surface or discover a narrower required
targeted command, record it in the review packet.

## Next Prompt Requirement

Before final response, create:

```text
docs/agent/runs/m48-review-prompt.md
```

Update `docs/agent/current-redesign-state.md` so the current action is review
of Milestone 48 and the active run prompt points to that review prompt.

## Expected Output Format

Return a review packet with:

1. Selected milestone.
2. Original milestone scope.
3. Final implemented scope.
4. Whether replanning was needed.
5. Replanning classification, if any.
6. Files changed.
7. Architectural boundary created or changed.
8. Domain concepts introduced or changed.
9. Behavior now covered by tests.
10. Tests added or changed.
11. Checks run, with exact results.
12. Documentation updated.
13. Known limitations.
14. Open questions.
15. Recommended next milestone or review action.
16. Next run prompt created: `docs/agent/runs/m48-review-prompt.md`
17. Current state updated: yes/no
