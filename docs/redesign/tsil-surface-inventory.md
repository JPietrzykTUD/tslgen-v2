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
| Generation control | `if<generation>(...)`, `else<generation>`, `loop<unroll>(...)`, `loop<range>(...)`, `let<type>(...)`, and `var<...>(...)` | lowerable directive over generation context | Semantic lowering requires typed generation context and selected-branch behavior. Directive-envelope classification alone must not parse surrounding statements as a general language. |
| Backend control | `if<compile>(...)`, `else<compile>`, and `switch<compile>(...)` occur in `tsldata/primitives/bitwise/shifts.tsl`, `tsldata/primitives/conversion/repr_change.tsl`, `tsldata/primitives/conversion/cast.tsl`, and `tsldata/primitives/load_store/rnd_access.tsl`. `if<runtime>` and `else<runtime>` were explicitly searched and are absent from the current corpus. | backend-control directive | Backend-owned lowering/rendering directive. The C++ translation map has `flow_if_static`, `flow_else_if_static`, `flow_if_runtime`, and `flow_else_if_runtime`, but the current source corpus uses compile-time control, not runtime control. |
| Generation/backend queries | `type<generation>(base::in)`, `value<generation>(vector::length)`, `type<backend>(vector::as_extension(scalar))`, and `value<backend>(intrin::suffix(...))` | typed query / translation request | Treat as lowerable query islands only with explicit typed context. Rendering must consume translated values, not evaluate raw nested text. |
| Intrinsic composition | `intrin_compose<add>(left, right)`, `intrin_compose<srli, suffix=value<backend>(...)>(...)`, and immediate metadata such as `immediate(2)=1` | backend-owned semantic operation | Lower to typed backend-intrinsic composition requests when selected. Backend spellings come from backend translation rules, not hardwired generator tables. |
| Direct intrinsic calls | `intrin<_mm512_srl_epi32>(...)`, `intrin<svptrue_b8>()`, `intrin<svst1>(...)` | backend-owned operation | Candidate for typed backend-call requests; not raw renderer inference and not a cross-backend semantic primitive by itself. |
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

## Next Implementation Recommendation

The next implementation milestone should be:

```text
Milestone 128: Real TSIL Payload Envelope Body Intake Slice
```

Goal:

Parse and catalog exactly the real source-authored `tsil` implementation
payload envelope from `.tsl` files into the M126 `ImplementationBody` line
model, without lowering `emit_return(...)`, primitive calls, helper calls,
intrinsics, assignments, loops, or backend-control directives yet.

Why this is the next high-value step:

- Every later lowering slice needs real `tsil` payloads in the clean product
  path; synthetic `body <operation>(...)` fixtures are no longer a good guide.
- It preserves the source-body design decision: raw text by default, with
  future lowerable islands added only by focused milestones.
- It makes future M129-style work possible, such as selecting one exact
  `emit_return(...)` directive family, without forcing the generator to become
  a TSIL compiler.

M128 must not render raw TSIL as generated backend code and must not evaluate
backend translation maps, helper semantics, or primitive-call dependencies.
