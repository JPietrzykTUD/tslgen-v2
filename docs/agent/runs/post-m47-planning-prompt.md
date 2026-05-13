# Post-M47 Planning Prompt: Next Generation-Time Helper Slice

Use this prompt only after M47 is accepted.

Read `docs/agent/current-redesign-state.md` first.

Do not implement code.

Plan the next milestone after accepted M47. Candidate direction from prior
reviews: a narrow signedness/type predicate branch-pruning slice over typed M43
inputs, unless current evidence suggests a smaller/higher-priority target.

Consider candidates:

- `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
- vector/register metadata queries
- prefix/post/infix/immediate modifier families
- direct intrinsic calls
- primitive calls/loops

Select exactly one next milestone or explicitly defer implementation if evidence
is insufficient.

Update redesign docs as needed. Run `git diff --check`.

Return files changed, selected next milestone, evidence used, deferrals, and
validation result.
