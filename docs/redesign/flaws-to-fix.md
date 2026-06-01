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

M176 selected the first direction for the clean generator boundary, and M177
implements exact typed backend/support-helper request discovery for current
mask lane constant islands. This does not fully eliminate the source-language
mismatch; it records how the generator should handle the current corpus while
leaving backend/helper rendering and any future `.tsl` source-convention
cleanup as separate decisions.

Until the later rendering path is implemented, do not resolve mask lane
constants to Python booleans, integers, raw backend strings, or hardcoded
target-language text in generation lowering.

## FTF-002: `intrin::suffix(si?)` Looks Like A Type-Group Artifact

Current `.tsl` contains one intrinsic modifier request with a wildcard-looking
type-group token as the suffix operand:

```text
tsldata/primitives/load_store/construct.tsl:30
intrin_compose<set1, suffix=value<backend>(intrin::suffix(si?))>(value)
```

This shape is suspicious source-data debt. `si?` names a signed-integer type
group pattern, not the selected concrete input/base type in the current
implementation context. Treating it as a valid suffix source would require the
generator to guess the author's intent or repair source text during backend
translation.

The expected source direction is to spell the modifier in terms of the current
selected input/base type, for example:

```text
suffix=value<backend>(intrin::suffix(base::in))
```

or the accepted equivalent if the TSL language later standardizes a different
current-type query.

Until a focused source-data cleanup milestone changes the `.tsl` corpus, keep
`intrin::suffix(si?)` as an explicit unsupported diagnostic boundary. Do not
add a semantic rule that interprets wildcard-looking type-group tokens as
selected concrete suffix inputs.

## FTF-003: `infix=to_type_suffix` Is A Legacy Destination-Suffix Shorthand

Current `.tsl` contains four intrinsic compose modifiers with the exact marker:

```text
tsldata/primitives/conversion/cast.tsl:62
tsldata/primitives/conversion/cast.tsl:71
tsldata/primitives/conversion/cast.tsl:81
tsldata/primitives/conversion/cast.tsl:90
infix=to_type_suffix
```

This marker appears to be a legacy shorthand for spelling the destination or
return-type suffix explicitly, for example:

```text
infix=value<backend>(intrin::suffix(ToBase))
```

where `ToBase` is only the current corpus spelling for the primitive-local
`return_type: base: ...` binding. The clean semantic meaning is "use the
selected destination/return base type suffix", resolved through the same typed
selected-binding context as explicit `intrin::suffix(NAME)` forms.

The shorthand is a source-convention mismatch because it hides a backend-value
query behind a bare symbol-like modifier value. Treat it as a compatibility
marker for the current corpus, not as a pattern to grow.

Future source cleanup should replace the shorthand with the explicit
`value<backend>(intrin::suffix(NAME))` spelling, using the actual
primitive-local return-type binding name.

Until that cleanup happens, any generator support for `infix=to_type_suffix`
must remain exact and selected-context gated. Do not translate raw
`to_type_suffix` as a literal fragment, do not make it a backend magic string,
and do not generalize it to arbitrary `*_suffix` marker spellings.

M206 adds that bounded compatibility bridge by lowering the exact marker
through primitive-local `return_type: base: NAME` context and a matching
selected return-type base binding. The source-convention flaw remains open
until the `.tsl` source uses the explicit backend suffix query directly.
