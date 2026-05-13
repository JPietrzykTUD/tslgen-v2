# Milestone 48 Review Prompt

You are the Codex reviewer for the clean-room `tslgen` redesign.

Do not implement code. Do not start Milestone 49.

## Accepted State

Milestones 1 through 47 are accepted.

Post-M47 planning is accepted. Milestone 48 execution is complete and awaiting
review:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Review Target

Review only the Milestone 48 implementation and documentation update.

M48 must remain generation-time semantic lowering only. It may evaluate only:

```text
value<generation>(type::is_signed(type<generation>(base::in)))
```

over typed M43 `GenerationTypeRef(kind="base.in")` values, and prune exact
`if<generation> ... else<generation>` branches with M42-style provenance.

## Scope To Review

- The exact signedness condition prunes `si32` to the true branch and `ui32` to
  the false branch.
- The condition consumes the M43 base type query model instead of inventing a
  downstream raw-text semantic path.
- Branch provenance remains typed and deterministic.
- Selected-branch-only unresolved-helper diagnostics still hold.
- Diagnostics cover malformed branches, unsupported predicates, unsupported
  nested type queries, missing type context, unknown tags,
  unsupported/non-integer tags, wildcard/generic tags, and selected raw helper
  leakage.
- Backend translation still rejects raw unresolved generation helper text.
- Renderers do not evaluate generation-time helpers.
- Documentation and workflow state describe M48 as implemented but pending
  review, not accepted.

## Out Of Scope

- Code changes during review.
- Milestone 49 or later planning.
- Plain `else` branch syntax.
- Shift or conversion output parity.
- Backend translation, backend rendering, generated output, CLI/report/writer
  work, Rust output, compiler execution, or generated-test execution.
- Prefix/post/infix/immediate modifiers or broad translation-map evaluation.
- Vector/register metadata, vector transforms, masks, casts, loops,
  `if<compile>`, primitive calls, variables, aliases, and direct
  `intrin<...>` parsing.
- Runtime dependency on `frozen/`.

## Suggested Validation

Run targeted validation as needed:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_cpp_backend_vertical_slice.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If you run different or additional checks, report the exact commands and
results.

## Review Verdicts

Return one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

For `Accept With Follow-Ups`, the follow-ups must be non-blocking and recorded
in `docs/agent/current-redesign-state.md`.

For `Needs Revision`, create a narrow revision prompt and focused re-review
prompt under `docs/agent/runs/`, then update
`docs/agent/current-redesign-state.md` to point at the revision prompt.

For `Accept` or `Accept With Follow-Ups`, create the next concrete prompt under
`docs/agent/runs/` according to `docs/agent/next-run-prompt-protocol.md`. If
human acceptance is required before advancing beyond M48 review, create a
post-M48 acceptance finalization prompt rather than a Milestone 49 executor
prompt.

## Expected Output Format

Return a review report with:

1. Verdict.
2. Scope reviewed.
3. Findings by severity, with file and line references.
4. Architecture and boundary assessment.
5. Diagnostics and determinism assessment.
6. Test coverage assessment.
7. Documentation/state assessment.
8. Checks run, with exact results.
9. Required follow-ups, if any.
10. Next run prompt created.
11. Current state updated: yes/no.
