# Post-M47 Boundary Auditor Subagent Prompt

You are the boundary auditor subagent for post-M47 planning.

Do not implement code.

## Task

Verify that the proposed next milestone preserves accepted boundaries.

## Accepted boundaries

- M43 owns base type generation queries.
- M45 owns suffix modifier translation.
- M46 owns backend type spelling.
- M47 owns selected native integer output rendering.
- Renderers must not evaluate generation-time helpers or backend modifiers.
- Backend translation must not parse raw generation helper text.
- `frozen/` is evidence only.

## Check proposed signedness branch slice

The likely next slice is:

```text
if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }
```

Check whether this belongs in generation-time semantic lowering and whether it
can be implemented without backend translation or rendering changes.

## Output

Return:

1. Boundary assessment.
2. What the next milestone may implement.
3. What it must not implement.
4. Required diagnostics.
5. Required tests.
6. Risks of drift.
