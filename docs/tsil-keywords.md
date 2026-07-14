# TSIL Keyword Regions

This file inventories the TSIL keyword regions currently recognized by `tslc`.
The compiler source of truth is
`tslc/src/tslc/ir/region_registry.py`; the lowering implementations live under
`tslc/src/tslc/lower/region_handlers/`.

TSIL bodies are not target-language ASTs. The scanner splits a body into raw
target text plus recognized keyword regions. Raw text passes through; each
region is lowered by a focused handler.

This inventory describes the supported contract, not every token the permissive
scanner can happen to preserve as raw text. Each keyword section lists every
currently supported selector form. The expandable examples show representative
lowering for C++ and Rust. Output can vary with the selected extension, scalar
type, primitive signature, attributes, and backend capability; examples that
depend on those values state their context. They show the region expansion, not
the surrounding generated function or Rust `unsafe` block.

The recognized keywords, in registry order, are:

| Keyword | Shape | Purpose |
| --- | --- | --- |
| `intrin` | call | Invoke or compose a target intrinsic. |
| `helper` | call | Invoke a compiler-owned portable helper. |
| `op` | call | Render a backend-divergent operator. |
| `var` | call | Declare a local value or scratch array. |
| `let` | call | Bind a lowering-time type alias. |
| `mask` | call | Construct, inspect, or update masks. |
| `mem` | call | Perform raw byte-memory operations. |
| `lanes` | call | Read a generation-known lane-list element. |
| `array` | call | Assign one element of backend-owned array storage. |
| `io` | call | Invoke formatted vector output. |
| `cast` | call | Render a backend-specific cast. |
| `call` | call | Invoke another generated primitive wrapper. |
| `if` | `if` block | Select or emit a conditional branch. |
| `select_expr` | call | Render an expression-level conditional. |
| `assume_aligned` | call | Apply a backend alignment hint. |
| `loop` | loop block | Emit or expand a loop. |
| `switch` | switch block | Emit compile-time multi-way selection. |
| `type` | call | Splice a resolved type or vector spelling. |
| `value` | call | Splice a resolved value fragment. |
| `complete` | call | Return the primitive result. |

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

Catalog validation checks malformed region shells before lowering. Regions with
structured selectors or argument shells, such as `intrin`, `helper`, `var`,
`let`, `mask`, `array`, `cast`, `call`, `type`, and `value`, have extra shell
validation before backend lowering.

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
these supported modifiers:

- `prefix=QUERY`: override the extension's intrinsic prefix with text.
- `suffix=QUERY`: override the selected type's suffix; `suffix=""` explicitly
  requests no suffix.
- `infix=QUERY`: insert text or a type suffix after the base name.
- `infix_sep=QUERY`: separator between the base and `infix`; the default is
  empty.
- `post=TEXT`: append `_<TEXT>`; `post=mask` is omitted unless the extension
  uses native predicate masks.
- `immediate(N)=VALUE`: identify positional argument `N` as an immediate. C++
  keeps it positional; Rust forwards it as a const generic. A primitive's
  immediate policy can instead request Rust literal-`match` dispatch.

`build` without brackets selects the default prefix and type suffix. The
special infix value `to_type_suffix` uses the in-scope `ToType` suffix.

Lowering marks the body as internally unsafe for intrinsic use, resolves any
build modifiers through the query evaluator, and asks the backend intrinsic
dialect to spell the call. C++ emits the positional intrinsic call. Rust may add
`core::arch::*` qualification, turn immediates into const generics, or emit a
literal `match` for immediates that require literal const arguments.

<details>
<summary>Representative expansion: AVX2, <code>si32</code></summary>

```tsil
intrin<add, build>(left, right)
```

```cpp
_mm256_add_epi32(left, right)
```

```rust
core::arch::x86_64::_mm256_add_epi32(left, right)
```

</details>

### `helper`

Syntax:

```tsil
helper<name>(args)
helper<name, template_arg, ...>(args)
```

Use `helper` to call compiler-owned runtime/helper functions from portable
fallback bodies. The shared C++/Rust helper ids are `arith_add`, `arith_mul`,
`arith_rem`, `popcount`, `clz`, and `ctz`; they are not target-language paths.
C++ additionally defines `clz_recursive`, which accepts selector template
arguments. A helper is supported only when the selected backend has a
`helper_<name>` translation template.

Lowering looks for a backend translate template named `helper_<name>`.
C++ currently maps helpers to `::tsl::detail::helpers`, while Rust maps them to
`crate::tsl_core::detail::helpers`. This keeps primitive implementation
internals free to live under `detail::primitives` without raw helper lookup
depending on lexical namespace/module scope.

<details>
<summary>Representative expansion</summary>

```tsil
helper<arith_add>(left, right)
```

```cpp
::tsl::detail::helpers::arith_add(left, right)
```

```rust
crate::tsl_core::detail::helpers::arith_add(left, right)
```

</details>

### `op`

Syntax:

```tsil
op<name>(arg0, arg1, ...)
```

Use `op` for operators whose spelling or semantics differ by backend, such as
wrapping arithmetic or bit negation. Portable operators can remain raw target
text.

The currently supported names are `add`, `sub`, `mul`, and `bit_negate`.

Lowering looks for a backend translate template named `op_<name>` and passes
arguments as `{a0}`, `{a1}`, and so on. Unsupported operator names are skipped
with a lowering diagnostic.

<details>
<summary>Representative expansion</summary>

```tsil
op<add>(left, right)
```

```cpp
(left + right)
```

```rust
left.tsl_add(right)
```

</details>

### `var`

Syntax:

```tsil
var<infer>(name, value)
var<const_infer>(name, value)
var<typed>(type, name, value)
var<const_typed>(type, name, value)
var<runtime_array>(element_type, name, count)
var<init_register>(name)
var<const_init_register>(name)
```

Use `var` for backend-neutral local declarations. The inferred forms let the
backend choose the local type spelling. The typed forms render an explicit type.
The register forms declare zero-initialized vector registers.
`const_init_register` is immutable in Rust; the current C++ translation uses the
same mutable zero-initialized register declaration as `init_register`.

Lowering renders the appropriate `var_*` backend translate template. A typed
declaration initialized with `value(uninit::array)` routes to the
type-carrying `var_array_uninit` template so Rust can use `MaybeUninit` while
C++ can use a normal value-initialized array. `var<runtime_array>` declares
mutable runtime-sized scratch storage for `count` elements of `element_type`;
the backend owns cleanup and exposes `name` as pointer-like storage for the
current function body. It is currently C++-only; Rust has no
`var_runtime_array` translation and skips specializations that reach this form.
Both `value(uninit::array)` and `value(uninit::scalar)` route through the
backend's dedicated typed-storage template: Rust uses `MaybeUninit`, while C++
currently value-initializes with `{}`.

<details>
<summary>Representative expansion</summary>

```tsil
var<const_typed>(type(scalar::size), count, 4)
```

```cpp
const std::size_t count = 4;
```

```rust
let count: usize = 4;
```

</details>

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
vector alias in the lowering scope. It emits no statement in either backend;
later raw text, calls, and queries are rendered with the alias substituted.

<details>
<summary>Representative expansion: current base is <code>si32</code></summary>

```tsil
let<type>(Unsigned, type(base::unsigned_of(base::in)));
var<typed>(Unsigned, result, 0)
```

```cpp
uint32_t result = 0;
```

```rust
let mut result: u32 = 0;
```

</details>

### `mask`

Syntax:

```tsil
mask<lane_true>()
mask<lane_false>()
mask<none>()
mask<all>()
mask<test>(mask, index)
mask<test, imask>(imask, index)
mask<set>(mask, index)
mask<clear>(mask, index)
mask<set_to>(mask, index, value)
```

Use `mask` for backend-neutral mask lane constants and mask bit operations in
portable fallback bodies. `mask<lane_true>()` and `mask<lane_false>()` produce
the scalar lane payload values used by lane-register masks. `mask<none>()` and
`mask<all>()` produce all-inactive/all-active mask containers.
`mask<test, imask>()` tests a packed integral mask bitset. The other forms
operate on an existing mask container. Native mask bodies often use intrinsics
directly instead.

Lowering chooses templates based on the selected extension's mask
representation: `mask_none_*`, `mask_all_*`, `mask_test_*`, `mask_set_*`,
`mask_clear_*`, `mask_set_to_*`, or `mask_test_imask`. Unsupported
operation/representation pairs are skipped with a lowering diagnostic.

Current translation coverage is representation-specific:

- scalar booleans, generic/exact lane bitmasks, and
  `native_predicate_by_lanes` masks support `none`, `all`, `test`, `set`,
  `clear`, and `set_to`;
- C++ comparison-lane vectors support the same six container operations;
- fixed-width lane-register masks support `test`; their construction is
  expressed through primitives rather than `mask<none>`/`mask<all>`;
- scalable `native_predicate` masks do not have these container templates and
  use mask primitives or native predicate intrinsics instead;
- `lane_true` and `lane_false` are independent of the container operation
  matrix. `test, imask` uses the packed-integral-mask template and therefore
  applies only to integer-like integral masks.

<details>
<summary>Representative expansion: integral-mask bit test</summary>

```tsil
mask<test, imask>(bits, lane)
```

```cpp
(((static_cast<std::uint64_t>(bits) >> lane) & 1ull) != 0)
```

```rust
((((bits) as u64 >> lane) & 1u64) != 0)
```

</details>

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

`count` and `count_bytes` are byte counts. `mem<alloc_aligned>` keeps the
source order `(count, align)` even though the backend helper/API receives
alignment first.

<details>
<summary>Representative expansion</summary>

```tsil
mem<copy>(dst, src, count_bytes);
```

```cpp
std::memcpy(dst, src, count_bytes);
```

```rust
crate::tsl_core::mem_copy(dst, src, count_bytes);
```

</details>

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

<details>
<summary>Representative expansion</summary>

```tsil
lanes<at>(values, 3)
```

```cpp
values[3]
```

```rust
values[3]
```

</details>

### `array`

Syntax:

```tsil
array<set>(array, index, value)
```

Use `array<set>` to assign one element of array-backed local storage when the
backend owns the index type. Catalog validation accepts only the `set` selector
with exactly three arguments. Lowering recursively renders all three arguments
and uses the backend's `array_set` translation.

<details>
<summary>Representative expansion</summary>

```tsil
array<set>(lanes, Index, value)
```

```cpp
lanes[Index] = value
```

```rust
lanes[(Index) as usize] = value
```

</details>

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

<details>
<summary>Representative expansion</summary>

```tsil
io<format>(out, values, modifier);
```

```cpp
::tsl::ostream_write(out, values, modifier);
```

```rust
crate::tsl_core::ostream_write(out, &values, modifier);
```

</details>

### `cast`

Syntax:

```tsil
cast<variant>(type_expression, expr)
cast<reinterpret, type=ptr>(type_expression, expr)
cast<reinterpret, type=const_ptr>(type_expression, expr)
```

Use `cast` when a body needs backend-specific cast spelling. Current translate
tables provide exactly these value variants for C++ and Rust: `static`,
`saturating`, `reinterpret`, `bitcast`, `const`, and `dynamic`. In Rust,
`reinterpret` and `bitcast` both use `bit_cast`; `const` and `dynamic` use
Rust's `as` cast. Consequently, use the semantic variant that matches the
operation rather than assuming identical target-language mechanics.

Catalog validation checks selector shape and nudges pointer casts toward
`type=ptr` or `type=const_ptr` instead of target types with trailing `*`.
Lowering resolves the type expression through the query evaluator, then renders
the backend `cast_<variant>` template. Pointer casts use backend syntax hooks so
C++ can emit `reinterpret_cast<T *>` while Rust can emit raw pointer casts or
address-of casts.

<details>
<summary>Representative expansion</summary>

```tsil
cast<static>(type(scalar::size), index)
```

```cpp
static_cast<std::size_t>(index)
```

```rust
(index) as usize
```

</details>

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
call-site policy values. The current corpus uses `aligned=true|false`,
`aligned=value(primitive::attribute(aligned))`, and
`mask=pass_through|zero`; boolean callee axes are otherwise data-driven.

Catalog validation parses the selector shape. Lowering resolves vector/type
arguments and attributes, applies policy-driven name splits such as mask or
immediate variants, forwards primitive boolean axes, borrows arguments for Rust
when the callee expects references, and asks the backend syntax dialect to
render the wrapper call. Calls to callees marked unsafe are wrapped in an unsafe
render field.

The first bracket entry is the vector target. `Vec` means the current vector;
queries, aliases, SIMD type parameters, and `Vec<Base>` can choose another
vector. Remaining entries forward decimal immediates, extensions, type/vector
queries, or in-scope generic parameters.

<details>
<summary>Representative expansion: current vector target</summary>

```tsil
call<primitive=add[Vec]>(left, right)
```

```cpp
::tsl::add<Vec>(left, right)
```

```rust
add::<Self>(left, right)
```

</details>

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

An unresolved `if<generation>` is skipped; it is never left as a runtime branch.
Runtime `else if` chains are represented as nested bare `if` regions in the
`else` block.

<details>
<summary>Bare runtime branch</summary>

```tsil
if(active) {
  complete(value);
} else {
  complete(fallback);
}
```

```cpp
if (active) {
  return value;
} else {
  return fallback;
}
```

```rust
if active {
  return value;
} else {
  return fallback;
}
```

</details>

<details>
<summary>Generation-time branch</summary>

For a selected `si32` input type, the condition is true and the untaken branch
does not reach either backend:

```tsil
if<generation>(type::is_same(base::in, si32)) {
  complete(signed_path);
} else<generation> {
  complete(other_path);
}
```

```cpp
return signed_path;
```

```rust
return signed_path;
```

</details>

<details>
<summary>Fully resolved compile-time branch</summary>

For a selected `si32` input type, this condition also resolves during lowering:

```tsil
if<compile>(type::is_signed(base::in)) {
  complete(signed_path);
} else<compile> {
  complete(unsigned_path);
}
```

```cpp
return signed_path;
```

```rust
return signed_path;
```

</details>

<details>
<summary>Compile-time branch with a symbolic boolean generic</summary>

```tsil
if<compile>(PreserveSign) {
  complete(data);
} else<compile> {
  complete(zero);
}
```

```cpp
if constexpr (PreserveSign) {
  return data;
} else {
  return zero;
}
```

```rust
if PreserveSign {
  return data;
} else {
  return zero;
}
```

</details>

### `select_expr`

Syntax:

```tsil
select_expr(condition, if_true, if_false)
```

Use `select_expr` for expression-level runtime choice when a body needs a
portable conditional value. All three arguments are recursively lowered TSIL
expression fragments; the two arms should be expressions, not statement bodies.
For statement-level branching, use `if`.

Catalog validation requires exactly three arguments and no selector. Lowering
renders the condition and both arms recursively, then asks the backend syntax
dialect to emit an expression conditional. C++ emits a conditional operator.
Rust emits an `if { ... } else { ... }` expression.

<details>
<summary>Representative expansion</summary>

```tsil
select_expr(active, value, fallback)
```

```cpp
((active) ? (value) : (fallback))
```

```rust
(if active { value } else { fallback })
```

</details>

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

<details>
<summary>Representative expansion: resolved alignment is 32</summary>

```tsil
assume_aligned<value(vector::alignment)>(ptr)
```

```cpp
::tsl::assume_aligned<32>(ptr)
```

```rust
ptr
```

</details>

### `loop`

Syntax:

```tsil
loop<backend>(var, start, end, step) { body }
loop<backend, unroll>(var, start, end, step) { body }
loop<generation>(var, start, end, step) { body }
loop<generation, scoped>(var, start, end, step) { body }
```

Use `loop<backend>` for loops that should remain in generated target code. Add
`unroll` when a backend unroll hint should be emitted if the trip count is known
at generation time. Use `loop<generation>` when the loop should expand fragments
during lowering, for example to build an intrinsic argument list. Add `scoped`
when the expanded body contains statements or declarations that require a
separate lexical block per iteration.

Lowering renders backend loops with the `loop_backend` template and optional
`loop_backend_unroll` template. Generation loops evaluate integer bounds,
temporarily bind the loop variable as a generation-time integer, render the
body once per iteration, and emit the concatenated result. A `scoped`
generation loop wraps each expanded iteration in its own lexical block,
matching the declaration scope of a real loop iteration; an ordinary generation
loop emits the fragments directly. The binding is available to `value(...)`
queries and intrinsic `immediate(N)=...` modifiers in the body. Zero steps are
diagnosed as errors.

`loop<backend, unroll>` emits `TSL_UNROLL(count)` in C++ only when the trip
count is generation-known. Rust currently has no unroll-hint template and emits
the ordinary Rust loop. `loop<generation>` and
`loop<generation, scoped>` produce the same expanded fragments for both
backends, apart from nested keyword expansions.

<details>
<summary>Backend loop</summary>

```tsil
loop<backend>(i, 0, lanes, 1) {
  touch(i);
}
```

```cpp
for (std::size_t i = 0; i < lanes; i += 1) {
  touch(i);
}
```

```rust
for i in (0..lanes).step_by(1) {
  touch(i);
}
```

</details>

<details>
<summary>Backend loop with an unroll request</summary>

```tsil
loop<backend, unroll>(i, 0, 4, 1) {
  touch(i);
}
```

```cpp
TSL_UNROLL(4)
for (std::size_t i = 0; i < 4; i += 1) {
  touch(i);
}
```

```rust
for i in (0..4).step_by(1) {
  touch(i);
}
```

</details>

<details>
<summary>Generation loop without per-iteration scopes</summary>

```tsil
loop<generation>(i, 0, 3, 1) {
  values[value(i)] = value(i);
}
```

```cpp
values[0] = 0;
values[1] = 1;
values[2] = 2;
```

```rust
values[0] = 0;
values[1] = 1;
values[2] = 2;
```

</details>

<details>
<summary>Scoped generation loop used for statements</summary>

```tsil
loop<generation, scoped>(i, 0, 2, 1) {
  var<const_infer>(lane, value(i));
  consume(lane);
}
```

```cpp
{
  auto const lane = 0;
  consume(lane);
}
{
  auto const lane = 1;
  consume(lane);
}
```

```rust
{
  let lane = 0;
  consume(lane);
}
{
  let lane = 1;
  consume(lane);
}
```

</details>

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

If the rendered selector is already a literal arm label, lowering keeps the
same target construct but suppresses implementation-state effects from the
untaken arms. `_` is the optional default arm.

<details>
<summary>Representative expansion</summary>

```tsil
switch<compile>(scale) {
  1 => { complete(unit); }
  _ => { complete(fallback); }
}
```

```cpp
if constexpr (scale == 1) {
  return unit;
} else {
  return fallback;
}
```

```rust
match scale {
  1 => {
    return unit;
  }
  _ => {
    return fallback;
  }
}
```

</details>

### `type`

Syntax:

```tsil
type(query)
```

Use `type` to splice a generated backend type or vector spelling into a TSIL
body. It accepts one query argument and no selector. The complete query-function
inventory appears below the keyword sections.

Inside other query arguments, type-valued leaves can be passed directly. For
example, prefer `value(type::size_bytes(base::in))` over the redundant
`value(type::size_bytes(type(base::in)))`.

Lowering evaluates the whole region with the query evaluator. Type values
become backend scalar spellings, text values pass through as text, and vector
values become backend vector spellings. If the query cannot be resolved,
lowering records a skip and leaves the original region text.

<details>
<summary>Representative expansion: current vector target</summary>

```tsil
type(vector::register)
```

```cpp
typename Vec::register_type
```

```rust
Self::RegisterType
```

</details>

### `value`

Syntax:

```tsil
value(query)
```

Use `value` to splice generated constants or backend-specific value fragments
into an expression. It accepts one query argument and no selector. The complete
query-function inventory appears below the keyword sections.

Lowering uses the same query evaluator as `type`. Text values become literal
rendered text, type values become backend scalar spellings, and vector values
become backend vector spellings. Unresolved queries are skipped and left as
their original region text.

<details>
<summary>Representative expansion: SIMD type parameter <code>IndexVec</code></summary>

```tsil
value(generic::length(IndexVec))
```

```cpp
IndexVec::lane_count_v
```

```rust
IndexVec::ELEMENT_COUNT
```

</details>

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

<details>
<summary>Representative expansion</summary>

```tsil
complete(result);
```

```cpp
return result;
```

```rust
return result;
```

</details>

## Query Function Inventory

`type(...)`, `value(...)`, `let<type>`, generation conditions, intrinsic build
modifiers, call selector entries, and alignment selectors share one typed query
evaluator. These are all registered query function heads:

| Query head | Accepted form and result |
| --- | --- |
| `base::in` | `base::in`: the selected scalar type. |
| `base::signed_of` | `base::signed_of(TYPE)`: same-width signed type. |
| `base::unsigned_of` | `base::unsigned_of(TYPE)`: same-width unsigned type. |
| `type` | `type(X)`: one-argument identity wrapper used by the `type` region. |
| `value` | `value(X)`: one-argument identity wrapper used by the `value` region. |
| `select` | `select(BOOL, THEN, ELSE)`: choose equal-kind query values during lowering. |
| `intrin::prefix` | `intrin::prefix`: selected extension/backend intrinsic prefix. |
| `intrin::suffix` | `intrin::suffix` or `intrin::suffix(TYPE_OR_NAME)`: selected or named intrinsic suffix. |
| `type::is_same` | `type::is_same(TYPE, TYPE)`: generation-time type equality. |
| `type::size_bytes` | `type::size_bytes(TYPE)`: scalar byte width. |
| `type::size_bits` | `type::size_bits(TYPE)`: scalar bit width. |
| `type::same_size` | `type::same_size(TYPE, TYPE)`: generation-time width equality. |
| `type::is_signed` | `type::is_signed(TYPE)`: generation-time signedness predicate. |
| `primitive::attribute` | `primitive::attribute(NAME)`: selected primitive attribute as a boolean. |
| `vector::register` | `vector::register`: current vector register type. |
| `register::generic` | `register::generic(TYPE_OR_VECTOR)`: concrete register type. |
| `vector::mask` | `vector::mask`: current vector mask type. |
| `vector::imask` | `vector::imask`: current packed integral-mask type. |
| `vector::alignment` | `vector::alignment`: natural register alignment in bytes. |
| `vector::length` | `vector::length`: static/generation-known lane count; unresolved for scalable vectors. |
| `vector::runtime_length` | `vector::runtime_length`: runtime-valid lane-count expression. |
| `vector::as_extension` | `vector::as_extension(EXT)`: current base under another extension. |
| `vector::fixed` | `vector::fixed`: C++ hardware-backed fixed-width fallback facade selected for a compiler-builtin vector. |
| `vector::as_base` | `vector::as_base(TYPE)`: another base under the current extension. |
| `vector::window_base` | `vector::window_base(TYPE)`: rebase while preserving total vector width. |
| `vector::as` | `vector::as(EXT, TYPE)`: explicit extension and base pair. |
| `base::generic` | `base::generic(VECTOR)`: vector or SIMD-parameter base type. |
| `generic::length` | `generic::length(VECTOR)`: static lane count for a vector value or SIMD type parameter. |
| `generic::runtime_length` | `generic::runtime_length(VECTOR)`: runtime-valid lane count for a vector value or SIMD type parameter. |

Query leaves can also be:

- scalar tags (`si32`, `f64`, and so on) and `scalar::<tag>` spellings such as
  `scalar::size`;
- in-scope target-type and extension symbols, `let<type>` aliases, SIMD type
  parameters, and generation-loop integer bindings;
- quoted text and bare identifiers, which become text fragments;
- `x86::cmp_eq_oq`, `x86::cmp_gt_oq`, `x86::cmp_ge_oq`, `x86::cmp_lt_oq`,
  `x86::cmp_le_oq`, `x86::cmp_neq_uq`, and `x86::mm_fround_to_zero`, which
  resolve through backend value templates;
- `uninit::array` and `uninit::scalar` inside `value(...)`, which are consumed
  specially by typed `var` declarations.

Queries are eagerly evaluated from the leaves inward. Wrong arity, wrong value
kind, an unavailable backend spelling, or an unsupported scalable/static lane
request leaves the query unresolved; the owning keyword then emits a structured
skip diagnostic rather than guessing.
