# Post-M47 Planner Subagent Prompt

You are the planner subagent for the post-M47 redesign phase.

Do not implement code.

## Task

Propose the next numbered milestone after accepted M47.

Expected candidate:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

Verify whether this is the best next slice.

## Read

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`

## Consider candidates

Compare:

- signedness/type predicate branch pruning over M43 `GenerationTypeRef`
- vector/register metadata queries
- prefix/post/infix/immediate modifiers
- backend type spelling expansion
- broader native rendering
- generated tests or CLI/report parity

## Output

Return:

1. Recommended next milestone title.
2. Goal.
3. Scope.
4. Out of scope.
5. Required inputs.
6. Expected outputs.
7. Tests required.
8. Validation.
9. Docs to update.
10. Review risks.
