# TSIL Keyword Regions

This file is the TSIL region reference.

The registry is the source of truth:

```text
tslc/src/tslc/ir/region_registry.py
```

Lowerers live here:

```text
tslc/src/tslc/lower/region_handlers/
```

## Mental Model

TSIL is not a C++ AST.

TSIL is not a Rust AST.

The scanner splits one body into recursive segments:

```text
body
  -> RawText
  -> Region(keyword, selector, children)
```

Raw text passes through.

Recognized regions are validated and lowered.

The keyword vocabulary is closed:

```python
TSIL_REGION_KEYWORDS: frozenset[str]
```

The frozenset is derived from `DEFAULT_TSIL_REGION_DESCRIPTORS`.

Each keyword has its own selector vocabulary.

Selectors are not one shared open map.

## Processing Connection

```text
descriptor registry
  -> scanner
  -> Region
  -> catalog shell validation
  -> keyword lowerer
  -> backend translation or syntax dialect
  -> render-ready C++ or Rust
```

The scanner owns boundaries.

Validation owns source shape.

Lowering owns semantics.

Backends own target spelling.

Renderers do not parse TSIL.

## Region Shapes

Most regions are calls:

```tsil
keyword<selector>(arguments)
keyword(arguments)
```

Three regions own blocks:

```tsil
if<selector>(condition) { then_body } else<selector> { else_body }
loop<selector>(var, start, end, step) { body }
switch<compile>(selector) { label => { body } _ => { body } }
```

Arguments are scanned recursively.

A statement terminator is consumed when the region is a statement.

## Registered Keywords

The order matches the descriptor registry.

| Keyword | Shape | Purpose |
| --- | --- | --- |
| `intrin` | Call | Invoke a target intrinsic. |
| `helper` | Call | Invoke a compiler-owned helper. |
| `op` | Call | Render a backend-specific operator. |
| `var` | Call | Declare local storage. |
| `let` | Call | Bind a lowering-time type alias. |
| `mask` | Call | Construct or update a mask. |
| `mem` | Call | Perform raw byte-memory operations. |
| `lanes` | Call | Read a generation-known lane-list element. |
| `array` | Call | Update backend-owned array storage. |
| `io` | Call | Format vector output. |
| `address` | Call | Take a typed address or mutable borrow. |
| `cast` | Call | Render a backend-specific cast. |
| `call` | Call | Invoke a generated primitive wrapper. |
| `if` | Block | Select or emit a branch. |
| `select_expr` | Call | Render an expression conditional. |
| `assume_aligned` | Call | Apply an alignment hint. |
| `loop` | Block | Emit or expand a loop. |
| `switch` | Block | Emit compile-time selection. |
| `type` | Call | Splice a resolved type. |
| `value` | Call | Splice a resolved value. |
| `complete` | Call | Return the primitive result. |

## Keyword Inventory

### `intrin`

Accepted forms:

```tsil
intrin<name>(args)
intrin<base, build>(args)
intrin<base, build[modifier=value, ...]>(args)
```

`intrin<name>` uses the given intrinsic name.

`build` composes a name from extension and type facts.

Supported modifiers:

| Modifier | Effect |
| --- | --- |
| `prefix=QUERY` | Override the extension prefix. |
| `suffix=QUERY` | Override the type suffix. |
| `infix=QUERY` | Insert an infix after the base name. |
| `infix_sep=QUERY` | Set the separator before the infix. |
| `post=TEXT` | Append `_<TEXT>`. |
| `immediate(N)=VALUE` | Mark argument `N` as an immediate. |

`suffix=""` removes the suffix.

`infix=to_type_suffix` uses the in-scope `ToType` suffix.

`post=mask` is omitted for non-predicate masks.

C++ keeps immediates positional.

Rust may use const generics or literal `match` dispatch.

Intrinsic use marks the implementation internally unsafe.

<details>
<summary>Example: AVX2 <code>si32</code></summary>

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

Accepted forms:

```tsil
helper<name>(args)
helper<name, template_arg, ...>(args)
```

Shared helper IDs:

```text
arith_add  arith_mul  arith_rem  popcount  clz  ctz
```

C++ also supports `clz_recursive` with selector template arguments.

The ID is backend-neutral.

Lowering looks up `helper_<name>` in backend translation data.

An absent translation is an unsupported-helper diagnostic.

<details>
<summary>Example</summary>

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

Accepted form:

```tsil
op<name>(arg0, arg1, ...)
```

Supported names:

```text
add  sub  mul  bit_negate
```

Use `op` only when backend semantics or spelling differ.

Portable operators can remain raw text.

Lowering looks up `op_<name>`.

Arguments become `{a0}`, `{a1}`, and so on.

<details>
<summary>Example</summary>

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

Accepted forms:

```tsil
var<infer>(name, value)
var<const_infer>(name, value)
var<typed>(type, name, value)
var<const_typed>(type, name, value)
var<runtime_array>(element_type, name, count)
var<init_register>(name)
var<const_init_register>(name)
```

`infer` lets the backend infer the type.

`typed` renders an explicit type.

`init_register` creates a zero-initialized vector register.

`runtime_array` creates pointer-like scratch storage.

`runtime_array` is currently C++-only.

Typed `value(uninit::array)` and `value(uninit::scalar)` use backend storage templates.

Rust uses `MaybeUninit`.

C++ currently uses normal local storage.

<details>
<summary>Example</summary>

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

Accepted form:

```tsil
let<type>(Name, type_expression)
```

The selector must be `type`.

`Name` must be an identifier.

Lowering resolves the type expression.

It adds an alias to lowering scope.

It emits no statement.

<details>
<summary>Example: current base is <code>si32</code></summary>

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

Accepted forms:

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

`lane_true` and `lane_false` return lane payload values.

`none` and `all` construct mask containers.

`test, imask` reads a packed integral mask bit.

Other operations use the selected mask representation.

Supported container operations vary by representation.

The common set is `none`, `all`, `test`, `set`, `clear`, and `set_to`.

Scalable native predicates use native primitives or intrinsics instead.

An unsupported representation pair produces a lowering diagnostic.

<details>
<summary>Example: packed integral mask</summary>

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

Accepted forms:

```tsil
mem<copy>(dst, src, count)
mem<set>(ptr, value, count)
mem<alloc>(count)
mem<alloc_aligned>(count, align)
mem<free>(ptr)
```

Counts are byte counts.

`alloc_aligned` keeps source order `(count, align)`.

The backend template reorders arguments when needed.

Raw memory use marks the implementation internally unsafe.

<details>
<summary>Example</summary>

```tsil
mem<copy>(dst, src, count_bytes)
```

```cpp
std::memcpy(dst, src, count_bytes)
```

```rust
crate::tsl_core::mem_copy(dst, src, count_bytes)
```

</details>

### `lanes`

Accepted form:

```tsil
lanes<at>(lane_list_param, index)
```

The parameter must have `lanes<s>` kind.

The index must resolve during generation.

Known bounds are checked.

<details>
<summary>Example</summary>

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

Accepted form:

```tsil
array<set>(array, index, value)
```

`set` is the only selector.

Exactly three arguments are required.

The backend owns index spelling.

<details>
<summary>Example</summary>

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

Accepted form:

```tsil
io<format>(out, array, modifier)
```

`format` is the only supported selector.

The runtime helper owns per-lane formatting.

<details>
<summary>Example</summary>

```tsil
io<format>(out, values, modifier)
```

```cpp
::tsl::ostream_write(out, values, modifier)
```

```rust
crate::tsl_core::ostream_write(out, &values, modifier)
```

</details>

### `address`

Accepted forms:

```tsil
address<of>(expr)
address<borrow_mut>(expr)
```

Use `address<of>` when a semantic operation needs the address of an object.
Use `address<borrow_mut>` only when the source explicitly requires a mutable
borrow. Backends own the concrete address spelling; common lowering never
parses `&` or `&mut` from raw target text.

<details>
<summary>Example</summary>

```tsil
cast<reinterpret, type=const_ptr>(void, address<of>(data))
```

```cpp
reinterpret_cast<void const *>(&data)
```

```rust
core::ptr::addr_of!(data).cast::<u8>()
```

</details>

### `cast`

Accepted forms:

```tsil
cast<variant>(type_expression, expr)
cast<reinterpret, type=ptr>(type_expression, expr)
cast<reinterpret, type=const_ptr>(type_expression, expr)
```

Supported value variants:

```text
static  saturating  reinterpret  bitcast  const  dynamic
```

Use `type=ptr` or `type=const_ptr` for pointer casts.

Do not place a trailing `*` in the target type.

The query evaluator resolves the target type.

The backend owns cast syntax.

Rust `reinterpret` and `bitcast` both use `bit_cast`.

Choose the semantic variant, not a target-language spelling.

<details>
<summary>Example</summary>

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

Accepted forms:

```tsil
call<primitive=name>(args)
call<primitive=name[VecOrTypeArgs], attrs[key=value, ...]>(args)
call<primitive=@self[...], attrs[key=value, ...]>(args)
```

`@self` names the primitive being lowered.

The first bracket entry is the vector target.

`Vec` means the current vector.

Later entries forward immediates, types, extensions, or generic parameters.

Current authored attributes include:

```text
aligned=true
aligned=false
aligned=value(primitive::attribute(aligned))
mask=pass_through
mask=zero
```

Lowering also forwards data-driven boolean axes.

Rust borrows arguments when the callee expects references.

Unsafe callees produce an unsafe render field.

<details>
<summary>Example: current vector</summary>

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

Accepted forms:

```tsil
if(condition) { then_body } else { else_body }
if<generation>(condition) { then_body } else<generation> { else_body }
if<compile>(condition) { then_body } else<compile> { else_body }
```

Bare `if` is a runtime branch.

`if<generation>` must resolve during lowering.

An unresolved generation condition produces a lowering skip.

`if<compile>` resolves during lowering when possible.

A symbolic boolean generic remains a target compile-time branch.

C++ uses `if constexpr` for that case.

Rust uses a const-parameter-dependent `if`.

<details>
<summary>Example: runtime branch</summary>

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

### `select_expr`

Accepted form:

```tsil
select_expr(condition, if_true, if_false)
```

No selector is allowed.

Exactly three arguments are required.

All arguments are recursive expression fragments.

Use `if` for statement branches.

<details>
<summary>Example</summary>

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

Accepted form:

```tsil
assume_aligned<alignment_expression>(ptr)
```

The selector must resolve to an alignment.

C++ emits an alignment hint.

Rust currently returns the pointer unchanged.

The selected aligned intrinsic still carries the Rust assumption.

<details>
<summary>Example: alignment resolves to 32</summary>

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

Accepted forms:

```tsil
loop<backend>(var, start, end, step) { body }
loop<backend, unroll>(var, start, end, step) { body }
loop<generation>(var, start, end, step) { body }
loop<generation, scoped>(var, start, end, step) { body }
```

`backend` emits a target loop.

`backend, unroll` adds a C++ hint when the trip count is known.

Rust currently emits the normal loop.

`generation` expands the body during lowering.

`generation, scoped` adds one lexical block per expansion.

The generation variable is available to `value(...)` and immediate modifiers.

A zero step is an error.

<details>
<summary>Example: backend loop</summary>

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

### `switch`

Accepted form:

```tsil
switch<compile>(selector) {
  1 => { body }
  2 => { body }
  _ => { fallback_body }
}
```

`compile` is the only selector.

Labels are compile-time values.

`_` is the optional default arm.

C++ emits an `if constexpr` chain.

Rust emits `match`.

Untaken arms do not contribute implementation-state effects when the selector is known.

<details>
<summary>Example</summary>

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
  1 => { return unit; }
  _ => { return fallback; }
}
```

</details>

### `type`

Accepted form:

```tsil
type(query)
```

No selector is allowed.

Exactly one query is required.

Type values become scalar type spellings.

Vector values become vector type spellings.

Text values pass through.

An unresolved query produces a lowering skip.

<details>
<summary>Example: current vector register</summary>

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

Accepted form:

```tsil
value(query)
```

No selector is allowed.

Exactly one query is required.

The same typed evaluator serves `type` and `value`.

The surrounding region states the source intent.

An unresolved query produces a lowering skip.

<details>
<summary>Example: SIMD type parameter <code>IndexVec</code></summary>

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

Accepted form:

```tsil
complete(expr)
```

The expression is lowered recursively.

The backend `complete` template frames the return.

Safety framing stays in typed render fields.

<details>
<summary>Example</summary>

```tsil
complete(result)
```

```cpp
return result;
```

```rust
return result;
```

</details>

## Query Function Inventory

All query sites use one typed evaluator.

Query sites include:

- `type(...)`;
- `value(...)`;
- `let<type>`;
- generation conditions;
- intrinsic modifiers;
- call selectors;
- alignment selectors.

The function-head vocabulary is closed.

Its source of truth is `DEFAULT_QUERY_FUNCTIONS` in
`tslc/src/tslc/lower/queries.py`.

| Query head | Accepted form and result |
| --- | --- |
| `base::in` | `base::in`: selected scalar type. |
| `base::signed_of` | `base::signed_of(TYPE)`: same-width signed type. |
| `base::unsigned_of` | `base::unsigned_of(TYPE)`: same-width unsigned type. |
| `type` | `type(X)`: one-argument identity wrapper for `type`. |
| `value` | `value(X)`: one-argument identity wrapper for `value`. |
| `select` | `select(BOOL, THEN, ELSE)`: select equal-kind values. |
| `intrin::prefix` | `intrin::prefix`: selected intrinsic prefix. |
| `intrin::suffix` | `intrin::suffix` or `intrin::suffix(TYPE_OR_NAME)`: intrinsic suffix. |
| `type::is_same` | `type::is_same(TYPE, TYPE)`: type equality. |
| `type::size_bytes` | `type::size_bytes(TYPE)`: scalar byte width. |
| `type::size_bits` | `type::size_bits(TYPE)`: scalar bit width. |
| `type::same_size` | `type::same_size(TYPE, TYPE)`: width equality. |
| `type::is_signed` | `type::is_signed(TYPE)`: signedness predicate. |
| `primitive::attribute` | `primitive::attribute(NAME)`: selected boolean attribute. |
| `vector::register` | `vector::register`: current vector register type. |
| `register::generic` | `register::generic(TYPE_OR_VECTOR)`: concrete register type. |
| `vector::mask` | `vector::mask`: current mask type. |
| `vector::imask` | `vector::imask`: current packed mask type. |
| `vector::alignment` | `vector::alignment`: natural alignment in bytes. |
| `vector::length` | `vector::length`: static lane count. |
| `vector::runtime_length` | `vector::runtime_length`: runtime lane-count expression. |
| `vector::as_extension` | `vector::as_extension(EXT)`: current base under another extension. |
| `vector::fixed` | `vector::fixed`: fixed-width hardware fallback facade. |
| `vector::as_base` | `vector::as_base(TYPE)`: another base under the current extension. |
| `vector::window_base` | `vector::window_base(TYPE)`: rebase while preserving vector width. |
| `vector::as` | `vector::as(EXT, TYPE)`: explicit extension and base. |
| `base::generic` | `base::generic(VECTOR)`: vector base type. |
| `generic::length` | `generic::length(VECTOR)`: static generic-vector lane count. |
| `generic::runtime_length` | `generic::runtime_length(VECTOR)`: runtime generic-vector lane count. |

## Query Leaves

Queries may also contain these leaves:

- scalar tags such as `si32` and `f64`;
- `scalar::<tag>` names such as `scalar::size`;
- target-type symbols;
- extension symbols;
- `let<type>` aliases;
- SIMD type parameters;
- generation-loop integers;
- quoted text;
- bare text identifiers;
- registered backend value names;
- `uninit::array` and `uninit::scalar` in `value(...)`.

Current registered x86 value names include:

```text
x86::cmp_eq_oq
x86::cmp_gt_oq
x86::cmp_ge_oq
x86::cmp_lt_oq
x86::cmp_le_oq
x86::cmp_neq_uq
x86::mm_fround_to_zero
```

## Query Evaluation Rules

Queries evaluate from leaves inward.

Each function checks arity and value kinds.

Static lane queries do not guess for scalable vectors.

Missing backend spellings remain unresolved.

The owning keyword emits a structured diagnostic or skip.

Prefer direct type leaves inside query arguments:

```tsil
value(type::size_bytes(base::in))
```

Avoid redundant wrappers:

```tsil
value(type::size_bytes(type(base::in)))
```
