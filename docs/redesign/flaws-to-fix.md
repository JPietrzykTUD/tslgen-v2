# Flaws To Fix

This document records known design mismatches that are not blocking the current
thin-slice prototype work, but should be revisited once enough of the
generator is wired end to end. Entries here are not active requirements by
themselves; a future milestone must still select and validate any fix.

## FTF-001: Mask Lane Constants Look Like Generation Values But Behave Like Support Helpers

Current `.tsl` uses:

```text
value<generation>(mask::lane::all_true)
value<generation>(mask::lane::all_false)
```

The legacy generator evidence maps those forms to backend/support helper
expressions, for example C++ helper/default expressions and Rust
helper/default expressions. That makes these forms conceptually different
from ordinary generation-time values such as scalar byte sizes or boolean
primitive attributes.

This is inconsistent with the current clean-redesign treatment of
`details::*` calls. Other support helpers such as `details::arith_add`,
`details::arith_mul`, `details::arith_rem`, `details::popcount`,
`details::clz`, `details::ctz`, and `details::mask_test` are source-authored
backend/support helper calls and are preserved as raw source text by default.
By contrast, `mask::lane::all_true` and `mask::lane::all_false` appear inside
TSIL `value<generation>(...)` wrappers, which suggests semantic lowering even
though the observable result is backend/support helper text.

Future work should choose one coherent direction:

- represent mask lane constants as typed backend/support-helper requests after
  lowering, then let backend rendering translate them;
- move the source convention toward explicit support helper calls, similar to
  `details::*`, if the TSL language is allowed to change;
- or document a deliberate special case explaining why these support-helper
  constants remain TSIL generation values.

Until that fix is selected, do not resolve mask lane constants to Python
booleans, integers, raw backend strings, or hardcoded target-language text in
generation lowering.
