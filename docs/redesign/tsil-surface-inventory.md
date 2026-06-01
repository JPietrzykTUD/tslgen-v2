# TSIL Surface Inventory

Milestone 127 inventories the TSIL surface used by the current source corpus.
The corpus ground truth is every current `.tsl` file under `tsldata/`; `frozen/`
is syntax and historical evidence only.

Survey commands:

```bash
rg --files tsldata -g "*.tsl"
rg -n "tsil|emit_return|call<primitive=|intrin|intrin_compose|details::|if<generation>|else<generation>|if<compile>|else<compile>|if<runtime>|else<runtime>|loop<|var<|let<|type<generation>|type<backend>|value<generation>|value<backend>" tsldata -g "*.tsl"
```

The survey found 41 current `.tsl` files. Simple token counts found 1328
`tsil` payload envelopes, including inline strings, multiline strings, and a
small number of `tsil:` block entries. These counts are search evidence, not a
semantic AST count.

Post-M211 status: the lowering surface is complete by current contract. The
inventory below remains the TSIL/source-surface map for backend/output
planning, but no row currently selects another lowering milestone.

## Boundary

M126 remains valid as a body-line and segment container boundary. Its
synthetic clean-restart `body <operation>(...)` fixture form is not evidence
that primitive-looking calls such as `sub(left, right)` are real TSIL calls.
Current `.tsl` primitive references use explicit TSIL constructs such as
`call<primitive=sub>(left, right)` or
`call<primitive=@self[...]>(...)`.

Direct primitive-looking names such as `add(...)`, `sub(...)`, `mul(...)`,
`div(...)`, `mod(...)`, `equal(...)`, and `nequal(...)` occur as primitive
declarations or backend support code, not as accepted TSIL primitive-call
syntax. For example, `prim<v:=(v,v)> sub(left, right):` is a declaration in
`tsldata/primitives/arithmetic/fundamental.tsl`, while real TSIL calls use
`call<primitive=...>`.

## Observed Buckets

| Bucket | Corpus evidence | Classification | Treatment |
| --- | --- | --- | --- |
| TSIL payload envelope | Inline `tsil "emit_return(left + right);"` in `tsldata/primitives/arithmetic/fundamental.tsl`; multiline `tsil """ ... """` in the same file; `tsil:` block entries in `tsldata/primitives/bitwise/shifts.tsl` | source-body envelope | Model first as source-owned `ImplementationBody` lines. Raw text is preserved by default; lowerable islands are introduced only by later milestones. |
| Return directive | `emit_return(left + right);`, multiline `emit_return(result);`, and nested `emit_return(call<primitive=...>(...));` across primitive files | lowerable directive | Candidate for a narrow directive milestone, but the returned expression must remain raw or separately segmented unless the exact expression family is selected. |
| Primitive calls | `call<primitive=set_zero[Vec]>()`, `call<primitive=sub>(left, right)`, `call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left[i], right[i])` | lowerable semantic operation / dependency edge | Parse as explicit primitive-call islands when selected. Do not infer from bare primitive-looking function names. |
| Generation control | `if<generation>(...)`, `else if<generation>(...)`, `else<generation>`, `loop<unroll>(...)`, `loop<range>(...)`, `let<type>(...)`, and `var<...>(...)` | lowerable directive over generation context | Semantic lowering requires typed generation context and selected-branch behavior. M160 accepts exact classified `if<generation>` / `else if<generation>` branch chains with optional final `else<generation>` fallback. M186 closes the post-M185 bare-condition gap as a small typed TSIL generation boolean condition grammar over accepted boolean/integer-comparison leaves, `!`, `&&`, `||`, and parentheses, not as arbitrary target-language expression parsing. M161 accepts exact `loop<range>(...)` region facts with optional adjacent `loop<unroll>(...)` metadata. M162 discovers every exact top-level M161 loop region inside arbitrary body token streams while preserving non-loop tokens as opaque spans, without executing loops or parsing loop bodies as a general language. M163 accepts exact top-level classified `var<init_register>`, `var<infer>`, `var<const_infer>`, and `var<typed>` declaration facts as unresolved backend-facing requests with opaque type/initializer payload text. |
| Backend control | `if<compile>(...)`, `else<compile>`, and `switch<compile>(...)` occur in `tsldata/primitives/bitwise/shifts.tsl`, `tsldata/primitives/conversion/repr_change.tsl`, `tsldata/primitives/conversion/cast.tsl`, `tsldata/primitives/conversion/mask_specific.tsl`, `tsldata/primitives/mask/bitwise.tsl`, and `tsldata/primitives/load_store/rnd_access.tsl`. `if<runtime>` and `else<runtime>` were explicitly searched and are absent from the current corpus. | backend-control directive | Backend-owned lowering/rendering directive. M165 records exact classified compile-control tokens as unresolved backend-control requests while preserving payloads and surrounding tokens opaque; it does not select branches, match raw blocks, or render flow. The C++ translation map has `flow_if_static`, `flow_else_if_static`, `flow_if_runtime`, and `flow_else_if_runtime`, but the current source corpus uses compile-time control, not runtime control. |
| Generation/backend queries | `type<generation>(base::in)`, `value<generation>(vector::length)`, `value<generation>(generic::length(OutVec))`, `type<backend>(vector::as_extension(scalar))`, and `value<backend>(intrin::suffix(...))` | typed query / translation request | Treat as lowerable query islands only with explicit typed context. M168 lowers exact `generic::length(TYPE_EXPR)` and fixed-vector `generic::runtime_length(TYPE_EXPR)` through the selected generation-expression boundary after type lowering; it does not scan opaque raw target-language text for `generic::*`. M164 accepts exact `value<backend>(...)` islands as unresolved backend-owned query requests over source-owned text. M181 hands the five observed top-level backend-value payload families to typed unresolved backend-value requests while keeping unsupported payloads diagnostic. Rendering must consume translated values, not evaluate raw nested text. |
| Intrinsic composition | `intrin_compose<add>(left, right)`, `intrin_compose<srli, suffix=value<backend>(...)>(...)`, and immediate metadata such as `immediate(2)=1` | backend-owned semantic operation | M166 records exact intrinsic request islands while preserving head/modifier and argument payload text opaque. M182 hands top-level `intrin_compose<...>` base/modifier fields to typed unresolved modifier facts and reuses M181 only for exact single `value<backend>(...)` modifier values. M195-M210 translate literal modifiers, type/current/symbol suffixes, prefixes, stream suffixes, `to_type_suffix`, literal immediates, selected `sImm` immediates, and selected indexed-vector generic immediates as typed backend modifier results. Intrinsic arguments, intrinsic invocation assembly, C++ non-type template rendering, Rust const generic rendering, and backend rendering remain deferred. Backend spellings come from backend translation rules, not hardwired generator tables. |
| Direct intrinsic calls | `intrin<_mm512_srl_epi32>(...)`, `intrin<svptrue_b8>()`, `intrin<svst1>(...)` | backend-owned operation | M166 records exact direct-intrinsic request islands; it does not infer semantics, split arguments, or render calls. |
| Cast/memory/I/O keyword calls | Examples include `cast<static>(...)`, `cast<reinterpret>(...)`, `cast<bitcast>(...)`, `cast<saturating>(...)`, `mem<copy>(...)`, `mem<alloc>(...)`, `mem<alloc_aligned>(...)`, `mem<free>(...)`, `io<write_base>(...)`, `io<write_bin>(...)`, `io<write>(...)`, and `io<endl>(...)` | source/backend-owned operation | M167 records exact request islands in source-owned text and contiguous raw body-token runs while preserving mode/operation and argument payload text opaque. M183 classifies only the observed exact selector payloads into typed finite selector values; argument payload lowering, operation translation, and rendering remain deferred. |
| Mask keyword calls | `mask<zero>()`, `mask<test>(...)`, `mask<set>(...)`, and `mask<set:1>(...)` | lowerable mask keyword request | M185 records exact mask keyword request islands in source-owned text and contiguous raw body-token runs, classifying only the observed selector payloads as typed finite values. Arguments, nested TSIL-looking text, and surrounding target-language-like text remain opaque; mask translation and rendering are deferred. |
| Backend/output source-island calls and constructors | `assume_aligned<...>(...)`, `array_type<...>`, and `pack<...>(...)` | backend/output request identity | M187 discovers all three exact source-island forms with opaque payload preservation. `array_type<...>` is angle-only in the current corpus; `assume_aligned<...>(...)` and `pack<...>(...)` are call-shaped. Alignment, array layout/type, pack semantics, argument splitting, nested payload lowering, and rendering remain backend/output-owned. |
| Arithmetic helper calls | `details::arith_add`, `details::arith_mul`, and `details::arith_rem` appear inside return expressions, assignments, and loops | backend/support helper | Preserve as source-authored calls to predefined backend/language support helpers. They are not semantic operation-lowering islands and should not be rewritten to `+`, `*`, or `%` by lowering. |
| Support helper calls | `details::popcount`, `details::clz`, `details::clz_recursive`, `details::ctz`, and `details::mask_test` | backend/support helper | Preserve as source-authored or backend-support helper calls unless a future milestone explicitly selects helper modeling. They should not be swept into arithmetic operator lowering. |
| Raw target-language-like text | Assignments such as `result[i] = ...`, declarations such as `svbool_t pg = ...`, pointer dereferences, `return;`, array indexing, casts, braces, and operators around TSIL islands | raw by default | Preserve as raw line text or raw string tokens around selected islands. Recognition of an island must not imply a full statement, scope, precedence, or type system parser. |
| Backend translation maps | `tsldata/detail/lang/translate_cpp.tsl` defines text templates such as `emit_return "return {value}"`, `loop_range`, `flow_if_static`, and `flow_if_runtime`; Rust has support helpers such as `arith_add`, `arith_sub`, `arith_mul`, and `arith_rem` | backend metadata, not primitive-body corpus | Translation declarations are source data for future typed backend rules. They are not runtime shortcuts for lowering and must not be consumed as raw dictionaries past catalog boundaries. |

## Representative Evidence

- `tsldata/primitives/arithmetic/fundamental.tsl:31` has inline
  `emit_return(left + right);`.
- `tsldata/primitives/arithmetic/fundamental.tsl:39` starts a multiline TSIL
  body with `var<init_register>`, `loop<unroll>`, `loop<range>`, indexed
  assignment, `call<primitive=@self[...]>(...)`, and `emit_return(result);`.
- `tsldata/primitives/comparison/fundamental.tsl:33`,
  `tsldata/primitives/comparison/fundamental.tsl:192`,
  `tsldata/primitives/comparison/fundamental.tsl:344`,
  `tsldata/primitives/comparison/fundamental.tsl:539`,
  `tsldata/primitives/comparison/fundamental.tsl:734`, and
  `tsldata/primitives/comparison/fundamental.tsl:900` show comparison
  operators inside `emit_return(...)`.
- `tsldata/primitives/bitwise/shifts.tsl:625` shows nested
  `if<generation>` and `if<compile>` directives.
- `tsldata/primitives/load_store/array.tsl:108` and
  `tsldata/primitives/load_store/array.tsl:109` show the current
  inline `else if<generation>(...) { BODY }` corpus form. M160 accepts this
  as an exact classified branch-chain token path over source-owned raw
  branch-body tokens; it still does not parse the raw target-language body.
- `tsldata/primitives/conversion/repr_change.tsl:1213` shows a
  generation-control-looking `} else {` form without `else<generation>`.
  M156 treats this as plain-else evidence outside the selected executable
  shape.
- `tsldata/primitives/arithmetic/complex.tsl:689` shows
  `details::arith_mul(...)` embedded inside indexed assignment.
- `tsldata/primitives/bitwise/bit_counts.tsl:79`,
  `tsldata/primitives/bitwise/bit_counts.tsl:90`, and
  `tsldata/primitives/bitwise/bit_counts.tsl:232` show `details::popcount`,
  `details::clz`, and `details::ctz` helper calls.
- `tsldata/primitives/load_store/rnd_access.tsl:65` and
  `tsldata/primitives/load_store/rnd_access.tsl:780` show raw pointer and
  indexed assignment text around lowerable calls and queries.
- `tsldata/detail/lang/translate_cpp.tsl:1` defines backend translation
  metadata, including return, loop, flow, cast, memory, and value templates.

## Current Recommendation

After M211 and the post-selected-immediate lowering completion gate, no next
lowering milestone is selected from this inventory. The active workflow moves
back to backend/output planning, where the next milestone should consume
accepted typed lowering facts, requests, handoffs, backend modifier
translation results, and source-owned opaque text rather than adding another
lowering slice by default.
