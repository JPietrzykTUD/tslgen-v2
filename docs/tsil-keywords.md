# TSIL Keyword Regions

This file inventories the TSIL keyword regions currently recognized by `tslc`.
The compiler source of truth is
`tslc/src/tslc/ir/region_registry.py`; the lowering implementations live under
`tslc/src/tslc/lower/region_handlers/`.

TSIL bodies are not target-language ASTs. The scanner splits a body into raw
target text plus recognized keyword regions. Raw text passes through; each
region is lowered by a focused handler.

## Region Shapes

Most keywords use the call-shaped form:

```tsil
keyword<selector>(arguments)
keyword(arguments)
```

The scanner keeps selector text raw, recursively scans the argument payload,
and consumes a following statement terminator when a region appears as a
statement.

Block-bearing keywords have dedicated shapes:

```tsil
if<selector>(condition) { then_body } else<selector> { else_body }
loop<selector>(var, start, end, step) { body }
switch<compile>(selector) { label => { body } _ => { body } }
```

Catalog validation checks malformed region shells before lowering. Today,
`intrin`, `let`, `cast`, and `call` have extra shell validation because their
selectors have structured syntax.

## Keyword Inventory

### `intrin`

Syntax:

```tsil
intrin<name>(args)
intrin<base, build[modifier=value, ...]>(args)
```

Use `intrin` when a body must call a backend intrinsic. The direct form calls
the named intrinsic after backend qualification. The `build` form composes the
intrinsic name from the selected extension's prefix and type suffix, with
optional modifiers such as `prefix`, `suffix`, `infix`, `infix_sep`, `post`, and
`immediate(N)`.

Lowering marks the body as internally unsafe for intrinsic use, resolves any
build modifiers through the query evaluator, and asks the backend intrinsic
dialect to spell the call. C++ emits the positional intrinsic call. Rust may add
`core::arch::*` qualification, turn immediates into const generics, or emit a
literal `match` for immediates that require literal const arguments.

### `op`

Syntax:

```tsil
op<name>(arg0, arg1, ...)
```

Use `op` for operators whose spelling or semantics differ by backend, such as
wrapping arithmetic or bit negation. Portable operators can remain raw target
text.

Lowering looks for a backend translate template named `op_<name>` and passes
arguments as `{a0}`, `{a1}`, and so on. Unsupported operator names are skipped
with a lowering diagnostic.

### `var`

Syntax:

```tsil
var<infer>(name, value)
var<const_infer>(name, value)
var<typed>(type, name, value)
var<const_typed>(type, name, value)
var<init_register>(name)
var<const_init_register>(name)
```

Use `var` for backend-neutral local declarations. The inferred forms let the
backend choose the local type spelling. The typed forms render an explicit type.
The register forms declare zero-initialized vector registers.

Lowering renders the appropriate `var_*` backend translate template. A typed
declaration initialized with `value(uninit::array)` routes to the
type-carrying `var_array_uninit` template so Rust can use `MaybeUninit` while
C++ can use a normal value-initialized array.

### `let`

Syntax:

```tsil
let<type>(Name, type_expression)
```

Use `let<type>` to name a type expression inside a TSIL body, especially when
the expression would be repeated or when later queries need a stable symbolic
name.

Catalog validation requires exactly `let<type>(Name, type-expression)` with an
identifier name. Lowering evaluates the type expression and records a type or
vector alias in the lowering scope. It emits no statement; later raw text and
queries are rendered with the alias substituted.

### `mask`

Syntax:

```tsil
mask<lane_true>()
mask<lane_false>()
mask<zero>()
mask<all>()
mask<test>(mask, index)
mask<test, imask>(imask, index)
mask<set>(mask, index)
mask<clear>(mask, index)
mask<set_to>(mask, index, value)
```

Use `mask` for backend-neutral mask lane constants and mask bit operations in
portable fallback bodies. `mask<lane_true>()` and `mask<lane_false>()` produce
the scalar lane payload values used by lane-register masks. `mask<zero>()` and
`mask<all>()` produce all-inactive/all-active mask containers.
`mask<test, imask>()` tests a packed integral mask bitset. The other forms
operate on an existing mask container. Native mask bodies often use intrinsics
directly instead.

Lowering chooses templates based on the selected extension's mask
representation: `mask_zero_*`, `mask_all_*`, `mask_test_*`, `mask_set_*`,
`mask_clear_*`, `mask_set_to_*`, or `mask_test_imask`. Unsupported
operation/representation pairs are skipped with a lowering diagnostic.

### `mem`

Syntax:

```tsil
mem<copy>(dst, src, count)
mem<set>(ptr, value, count)
mem<alloc>(count)
mem<alloc_aligned>(count, align)
mem<free>(ptr)
```

Use `mem` for raw byte memory operations, allocation, and release in
backend-neutral bodies.

Lowering marks the body as internally unsafe for raw memory and renders backend
templates such as `mem_copy`, `mem_alloc`, and `mem_free`. C++ templates map to
standard-library memory calls; Rust templates map to TSL helper functions.

### `lanes`

Syntax:

```tsil
lanes<at>(lane_list_param, index)
```

Use `lanes<at>` to access one scalar element from a `lanes<s>` parameter, such
as a vector constructor that receives one value per lane.

Lowering verifies that the parameter is a lane-list parameter, evaluates the
index at generation time, checks known bounds, and emits an indexed expression
like `values[3]`.

### `io`

Syntax:

```tsil
io<format>(out, array, modifier)
```

Use `io<format>` for the vector output primitive's formatted text-stream write.
The runtime helper owns the per-lane formatting rules, so TSIL stays a single
portable call.

Lowering renders the `io_format` backend template. C++ emits the stream helper;
Rust emits the corresponding `tsl_core` helper call.

### `cast`

Syntax:

```tsil
cast<variant>(type_expression, expr)
cast<reinterpret, type=ptr>(type_expression, expr)
cast<reinterpret, type=const_ptr>(type_expression, expr)
```

Use `cast` when a body needs backend-specific cast spelling. Current translate
tables provide variants such as `static`, `saturating`, `reinterpret`,
`bitcast`, `const`, and `dynamic`, subject to backend support.

Catalog validation checks selector shape and nudges pointer casts toward
`type=ptr` or `type=const_ptr` instead of target types with trailing `*`.
Lowering resolves the type expression through the query evaluator, then renders
the backend `cast_<variant>` template. Pointer casts use backend syntax hooks so
C++ can emit `reinterpret_cast<T *>` while Rust can emit raw pointer casts or
address-of casts.

### `call`

Syntax:

```tsil
call<primitive=name>(args)
call<primitive=name[VecOrTypeArgs], attrs[key=value, ...]>(args)
call<primitive=@self[...], attrs[key=value, ...]>(args)
```

Use `call` to call another generated primitive wrapper without inlining its
body. `@self` calls the primitive currently being lowered. Bracket entries can
override the vector target or forward const/type arguments. `attrs[...]` carries
call-site policy values such as `aligned` or `mask`.

Catalog validation parses the selector shape. Lowering resolves vector/type
arguments and attributes, applies policy-driven name splits such as mask or
immediate variants, forwards primitive boolean axes, borrows arguments for Rust
when the callee expects references, and asks the backend syntax dialect to
render the wrapper call. Calls to callees marked unsafe are wrapped in an unsafe
render field.

### `if`

Syntax:

```tsil
if(condition) { then_body } else { else_body }
if<generation>(condition) { then_body } else<generation> { else_body }
if<compile>(condition) { then_body } else<compile> { else_body }
```

Use bare `if` for runtime branching and `if<generation>` or `if<compile>` for
branches that should be resolved while lowering when possible.

Lowering renders bare `if` through backend runtime-flow templates. For
`if<generation>` and fully resolved `if<compile>` conditions, the query
evaluator chooses a branch and only the taken body is emitted. If
`if<compile>` contains an in-scope symbolic generic parameter, lowering emits a
backend compile-time branch instead: C++ uses `if constexpr`, while Rust emits a
normal const-parameter-dependent `if`.

### `assume_aligned`

Syntax:

```tsil
assume_aligned<alignment_expression>(ptr)
```

Use `assume_aligned` when an aligned load/store path needs to tell the backend
that a pointer satisfies a known alignment.

Lowering resolves the selector through the query evaluator, then calls the
backend syntax dialect. C++ emits `::tsl::assume_aligned<N>(ptr)`. Rust
currently returns the pointer expression unchanged because stable Rust has no
equivalent hint and the selected aligned intrinsic already carries the
alignment assumption.

### `loop`

Syntax:

```tsil
loop<backend>(var, start, end, step) { body }
loop<backend, unroll>(var, start, end, step) { body }
loop<generation>(var, start, end, step) { body }
```

Use `loop<backend>` for loops that should remain in generated target code. Add
`unroll` when a backend unroll hint should be emitted if the trip count is known
at generation time. Use `loop<generation>` when the loop should expand during
lowering, for example to build an intrinsic argument list.

Lowering renders backend loops with the `loop_backend` template and optional
`loop_backend_unroll` template. Generation loops evaluate integer bounds,
temporarily bind the loop variable as a generation-time integer, render the
body once per iteration, and emit the concatenated result. Zero steps are
diagnosed as errors.

### `switch`

Syntax:

```tsil
switch<compile>(selector) {
  1 => { body }
  2 => { body }
  _ => { fallback_body }
}
```

Use `switch<compile>` for multi-way compile-time selection over a const value,
most often when each arm must call an intrinsic with a literal immediate.

The scanner captures each `label => { body }` arm and `_` as the default arm.
Lowering renders every arm body recursively and asks the backend syntax dialect
to emit the selection. C++ emits an `if constexpr` / `else if constexpr` chain.
Rust emits a `match` over the selector.

### `type`

Syntax:

```tsil
type(query)
```

Use `type` to splice a generated backend type spelling into a TSIL body. Common
queries include `base::in`, `base::signed_of(...)`, `base::unsigned_of(...)`,
`vector::register`, `vector::mask`, `vector::imask`, `vector::as_base(...)`,
and `vector::as_extension(...)`.

Lowering evaluates the whole region with the query evaluator. Type values
become backend scalar spellings, text values pass through as text, and vector
values become backend vector spellings. If the query cannot be resolved,
lowering records a skip and leaves the original region text.

### `value`

Syntax:

```tsil
value(query)
```

Use `value` to splice generated constants or backend-specific value fragments
into an expression. Common queries include `vector::length`,
`vector::alignment`, `generic::length(...)`, `type::size_bytes(...)`,
`primitive::attribute(...)`, and `select(...)`.

Lowering uses the same query evaluator as `type`. Text values become literal
rendered text, type values become backend scalar spellings, and vector values
become backend vector spellings. Unresolved queries are skipped and left as
their original region text.

### `complete`

Syntax:

```tsil
complete(expr)
```

Use `complete` to finish a primitive body with its return value.

Lowering renders the expression recursively, then asks the backend syntax
dialect to frame the return with the `complete` translate template. Current C++
and Rust translate tables both render this as `return {value}`. Any unsafe
framing needed by the body is tracked by lowered render fields rather than
decided in templates.
