# TSL Examples

This directory contains small consumer-side examples for the generated C++ TSL
library. They are not compiler tests by themselves; they demonstrate how a user
project can consume generated C++ artifacts through CMake.

## Build Prerequisite

Generate a C++ TSL project first. The default example CMake configuration looks
for the generated output root under `tslctmp/examples/generated` and consumes
its `cpp/` project through `FetchContent`:

```bash
./dev.sh generate \
  --primitives add,mul,hadd,less_than,set1,blend \
  --profiles scalar \
  --backends cpp \
  --types si32 \
  --output-root ./tslctmp/examples/generated
```

Then configure, build, and run the examples:

```bash
cmake -S examples/cpp -B tslctmp/examples/build \
  -DTSL_GENERATED_ROOT_DIR="$PWD/tslctmp/examples/generated" \
  -DTSL_PROFILE=scalar
cmake --build tslctmp/examples/build
ctest --test-dir tslctmp/examples/build --output-on-failure
```

If the environment chooses an unwanted C++ compiler, pass the compiler
explicitly when configuring:

```bash
env CXX=g++ CC=gcc cmake -S examples/cpp -B tslctmp/examples/build \
  -DTSL_GENERATED_ROOT_DIR="$PWD/tslctmp/examples/generated" \
  -DTSL_PROFILE=scalar
```

The generated-package CI workflow also publishes a packaged generated TSL archive
as a GitHub Release asset for version tags. A downstream CMake project can
consume such an archive directly:

```bash
cmake -S examples/cpp -B tslctmp/examples/build \
  -DTSL_GENERATED_URL="https://github.com/<owner>/<repo>/releases/download/<tag>/tsl-generated-<tag>.tar.gz" \
  -DTSL_PROFILE=scalar
```

Normal push and manual CI runs upload a workflow artifact for inspection, but
tagged releases are the stable URL-shaped dependency intended for
`FetchContent`.

## Examples

### `unary_operator.cpp`

Demonstrates `tsl::algo::transform_unary` with a register-level square
operation:

```cpp
struct square_op {
  template <class Vec>
  typename Vec::register_type operator()(
      typename tsl::reg_param<Vec>::type value) const {
    return tsl::mul<Vec>(value, value);
  }
};
```

The example allocates 1000 `std::int32_t` values, fills them, and verifies the
same operation through native, exact scalar, and portable generic policies:

- `transform_unary(...)` defaults to `dataparallel::native`, the selected
  profile's natural vector shape for the element type.
- `transform_unary<1>` requests the exact scalar lane count and forwards to
  `dataparallel::fixed<1>` internally.
- `transform_unary<tsl::dataparallel::generic<4>>` demonstrates a portable
  four-lane generic vector without requiring a matching hardware mapping.
- `transform_unary<tsl::dataparallel::generic<128>>` demonstrates a large
  portable generic vector and why
  operations should accept values through
  `tsl::reg_param<Vec>::type`.
- `alignment::peel_to_aligned` can be requested explicitly when matching input
  and output alignment offsets should use a scalar prologue before the aligned
  vector loop.
- `alignment::assume_inputs_aligned` and
  `alignment::assume_output_aligned` can be used when only the input load or
  output store side has an alignment promise.

The example also verifies exact in-place operation (`input == output`). Shifted
or partial input/output overlap is not part of the dense transform contract.

`Vec::register_type` names the actual register object type. `tsl::reg_param`
names the generated-library parameter-passing convention for that object:
native/scalar registers are passed by value, while array-backed generic
registers are passed by `const&` to avoid large copies.

The example also demonstrates the generated primitive policy facade for a pure
binary register transform:

```cpp
auto squared = tsl::mul<tsl::dataparallel::generic<8>, std::int32_t>(
    values,
    values);
```

The canonical primitive call remains `tsl::mul<Vec>(...)`; the policy facade is
a thin convenience wrapper that maps `(Policy, T)` to `Vec` and forwards.

The same example uses policy facades for plain contiguous memory access:

```cpp
auto values =
    tsl::load<tsl::dataparallel::generic<8>, std::int32_t, false>(input);
tsl::store<tsl::dataparallel::generic<8>, std::int32_t, false>(
    output,
    values);
```

The final `false` is the compile-time alignment promise. Unmasked `load` and
register `store` are covered; masked/gather/compress forms remain explicit
primitive/helper contracts.

It also demonstrates target-base conversion facades:

```cpp
auto casted =
    tsl::cast<tsl::dataparallel::generic<8>, std::int32_t, std::uint32_t>(
        values);
auto bits =
    tsl::reinterpret<
        tsl::dataparallel::generic<8>,
        std::int32_t,
        std::uint32_t>(values);
```

These map the source vector from `(Policy, FromT)` and rebind its base type for
the target vector.

### `binary_operator.cpp`

Demonstrates `tsl::algo::transform_binary` with a register-level add operation:

```cpp
struct add_op {
  template <class Vec>
  typename Vec::register_type operator()(
      typename tsl::reg_param<Vec>::type left,
      typename tsl::reg_param<Vec>::type right) const {
    return tsl::add<Vec>(left, right);
  }
};
```

The example allocates two 1000-element `std::int32_t` inputs, fills them, and
verifies the native default plus direct `transform_binary<1>`,
`transform_binary<tsl::dataparallel::generic<4>>`, and
`transform_binary<tsl::dataparallel::generic<128>>` policies. It
exercises the same helper-owned loop, alignment, load, tail, and store mechanics
as the unary example, but for two contiguous input columns.

It also demonstrates the generated primitive policy facade:

```cpp
auto sum = tsl::add<tsl::dataparallel::generic<8>, std::int32_t>(
    left_values,
    right_values);
```

The canonical primitive call remains `tsl::add<Vec>(...)`; the policy facade is
a thin convenience wrapper that maps `(Policy, T)` to `Vec` and forwards.

The example also calls `alignment::peel_to_aligned` on shifted input and output
regions, demonstrating the explicit scalar-prologue policy for dense transforms.
It verifies exact in-place output aliases for both binary operands
(`output == left` and `output == right`). Shifted or partial overlap remains a
caller error.
It also instantiates `alignment::assume_inputs_aligned` and
`alignment::assume_output_aligned`; for binary transforms the input-side promise
covers both input columns.

### `chunk_operator.cpp`

Demonstrates `tsl::algo::for_each_chunk`, the low-level escape hatch for
advanced algorithms that need chunk pointer metadata. The helper owns vector
type inference and chunk/tail enumeration, but the operation owns memory effects.

The example receives `(chunk_ptr, offset, count)`, verifies the metadata, loads
the chunk itself with `tsl::load<Vec, false>`, and sums the values. It verifies
the native default, exact scalar `fixed<1>`, and portable generic widths `4`
and `16`.

### `range_operator.cpp`

Demonstrates the C++17 range overloads for helpers. These overloads accept
objects compatible with `std::data(range)` and `std::size(range)`, then forward
to the pointer+count APIs.

The example uses `std::vector<std::int32_t>` ranges with dense transforms,
predicate materialization, masked selection, masked aggregation, masked
consume, and `for_each_chunk`. Range overloads do not allocate or resize
outputs; output and mask ranges must already contain enough storage.

### `predicate_operator.cpp`

Demonstrates `tsl::algo::predicate_unary` and `tsl::algo::predicate_binary`,
which map contiguous input columns to an integral mask stream:

```cpp
struct less_than_op {
  template <class Vec>
  typename Vec::mask_type operator()(
      typename tsl::reg_param<Vec>::type left,
      typename tsl::reg_param<Vec>::type right) const {
    return tsl::less_than<Vec>(left, right);
  }
};
```

The unary case marks negative input values, and the binary case marks
`left < right`. The helper stores one `Vec::imask_type` per vector chunk and
returns the number of produced mask chunks. The example verifies exact scalar
`fixed<1>` plus portable generic widths `4` and `16`. It intentionally does
not use `128` lanes because
the current integral mask contract requires `Vec::imask_type` to have at least
one bit per lane.

The example also demonstrates generated primitive policy facades for unmasked
predicates and mask-only operations:

```cpp
auto mask = tsl::less_than<tsl::dataparallel::generic<4>, std::int32_t>(
    left_values,
    right_values);
auto all = tsl::mask_true<tsl::dataparallel::generic<4>, std::int32_t>();
auto active =
    tsl::mask_binary_and<tsl::dataparallel::generic<4>, std::int32_t>(
        all,
        mask);
```

Predicate facades return the selected vector's native `mask_type`. The example
uses `tsl::to_integral<Vec>(mask)` before checking lanes, so the verification
is independent of whether the native mask is a scalar boolean, an integral
bitset, or a hardware mask register. Mask-operation facades consume and produce
that same native `mask_type`; they do not materialize helper-owned mask streams.
The example also calls `tsl::mask_population_count<Policy, T>` on a native mask
and compares it with the expected active-lane count.

### `where_operator.cpp`

Demonstrates `tsl::algo::transform_where_unary` and
`tsl::algo::transform_where_binary`. These helpers consume the integral mask
stream produced by `predicate_binary`, transform active lanes, and preserve
inactive output lanes.

The example verifies both shapes:

- unary where: square active input values, leave inactive output unchanged.
- binary where: add active input pairs, leave inactive output unchanged.

The operation may accept the active mask as its first register-level argument,
but simple operations that only accept value registers also work because the
helper owns masked storage.

### `masked_operator.cpp`

Demonstrates `tsl::algo::transform_masked_unary` and
`tsl::algo::transform_masked_binary`. These helpers consume the same integral
mask stream as the where helpers, but they store every output lane. The
operation receives the activity mask and must return meaningful values for
inactive lanes.

The example verifies both shapes:

- unary masked full-store: square active input values, write the original input
  value for inactive lanes.
- binary masked full-store: add active input pairs, write the left input value
  for inactive lanes.

The example initializes output with sentinel values, so it fails if inactive
lanes are merely preserved instead of explicitly written by the masked
full-store helper.

### `native_mask_operator.cpp`

Demonstrates `tsl::algo::mask_layout::native` for predicate, where, and masked
full-store helpers. The helper stores one `Vec::mask_type` per vector chunk
instead of one integral `Vec::imask_type`.

The example uses `native_mask_type` and `native_mask_chunk_count` to allocate
caller-owned native mask storage. It verifies exact scalar `fixed<1>` plus
portable generic widths `4` and `16`, including a non-multiple input length so
the native tail path is exercised.

### `byte_mask_operator.cpp`

Demonstrates `tsl::algo::mask_layout::bytes` for predicate, where, and masked
full-store helpers. The helper stores one `std::uint8_t` activity value per
input row, using `0` for inactive and `1` for active.

The example uses `byte_mask_type` and `byte_mask_count` for caller-owned byte
mask storage. It verifies byte materialization, exact scalar `fixed<1>` plus
portable generic widths `4` and `16`, and a non-multiple input length so scalar
tail handling is covered.

### `bit_mask_operator.cpp`

Demonstrates `tsl::algo::mask_layout::bits` for predicate, where, and masked
full-store helpers. The helper stores one activity bit per row using
little-endian bit order inside each byte: row `i` is stored in byte `i / 8`,
bit `i % 8`.

The example uses `bit_mask_type` and `bit_mask_count` for caller-owned packed
mask storage. It verifies the packed representation, including that bits beyond
the logical row count are cleared in the final byte.

### `selection_operator.cpp`

Demonstrates `tsl::algo::select_unary` and `tsl::algo::select_binary`,
compacting `N -> K` helpers. The operation produces a predicate mask, and the
helper writes only active left-input values densely to the output range. For
`select_binary`, the predicate sees both inputs while the compacted values come
from the left input.

The example filters negative `std::int32_t` values, filters one value stream
against a per-row threshold stream, verifies returned produced counts, and
checks that selected values keep their original order. It also verifies that
output positions after `produced` are not touched.

### `masked_selection_operator.cpp`

Demonstrates `tsl::algo::select_masked_unary` and
`tsl::algo::select_masked_binary`, compacting helpers that combine an input
mask with an operation-produced predicate mask. A row is selected only when
both masks are active.

The example builds input masks with `predicate_unary` and `predicate_binary`,
then selects left-input values from the active rows. It verifies compacted
order, the returned produced count, untouched output positions after
`produced`, exact scalar `fixed<1>` plus portable generic widths `4` and `16`,
and integral, native, byte, and packed-bit mask layouts.

### `selection_vector_operator.cpp`

Demonstrates selection-vector production with `select_indices_unary`,
`select_indices_binary`, `select_masked_indices_unary`, and
`select_masked_indices_binary`. These helpers write selected row ids into a
caller-provided unsigned integral output range instead of compacting values.

The example uses `std::uint32_t` row ids, verifies stable input order and
returned produced counts, and checks that positions after `produced` are not
touched. The masked cases consume integral, native, byte, and packed-bit mask
layouts.

### `selected_transform_operator.cpp`

Demonstrates selection-vector consumption with `transform_selected_unary` and
`transform_selected_binary`. These helpers read caller-owned row ids, load the
selected input rows in that order, apply the operation, and write a dense output
range.

The helper uses `gather_narrow` for 32-bit and 64-bit pointer-backed row-id
streams, falling back to scalar or portable generic loading where needed. Plain
`gather` is reserved for a future row source that consumes caller-owned
index-register chunks, because it needs an index register rather than a row-id
pointer. A `Scale` template argument may override the default byte scale of
`sizeof(T)`. The example uses a `std::size_t` reverse-ordered row-id stream to
prove output order follows the selection vector rather than the input batch.

### `selected_refinement_operator.cpp`

Demonstrates selection-vector refinement with
`select_selected_indices_unary` and `select_selected_indices_binary`. These
helpers read an existing caller-owned row-id stream, evaluate the predicate on
the selected input rows, and write a new dense row-id stream containing the
original row ids whose selected rows passed the predicate.

Like other selected-row helpers, refinement uses `gather_narrow` for 32-bit and
64-bit pointer-backed row-id streams, falling back to scalar or portable
generic loading where needed. The example verifies pointer and range overloads
for selected-row widths `1`, `4`, and `16`, including that output order follows
the input selection vector.

### `selected_aggregate_consume_operator.cpp`

Demonstrates selected-row sink helpers: `aggregate_selected_unary`,
`aggregate_selected_binary`, `consume_selected_unary`, and
`consume_selected_binary`. These helpers consume caller-owned row ids, load
selected input rows in that order, and either return an aggregate finalizer
value or update a stateful sink.

Like selected transforms, these helpers use `gather_narrow` for 32-bit and
64-bit pointer-backed row-id streams, falling back to scalar or portable
generic loading where needed. The example checks pointer and range overloads
for selected-row widths `1`, `4`, and `16`.

### `count_operator.cpp`

Demonstrates predicate cardinality helpers: `count_unary`, `count_binary`,
`count_masked_unary`, `count_masked_binary`, `count_selected_unary`, and
`count_selected_binary`. These helpers evaluate a predicate operation and
return the number of active rows without materializing a mask, compacted
values, or row ids.

The masked helpers combine the input mask with the operation-produced predicate
mask before counting. The selected helpers count matching rows from an existing
selection vector using the same selected-row loading policy as selected
transforms. The example verifies exact scalar `fixed<1>` plus portable generic
widths `4` and `16` for dense/masked counts, selected-row widths `1`, `4`, and
`16` for selected counts, and covers integral, native, byte, and packed-bit mask
layouts.

### `aggregation_operator.cpp`

Demonstrates `tsl::algo::aggregate_unary` and
`tsl::algo::aggregate_binary`. The helpers own contiguous partitioning,
vector/scalar loading, and tail handling. The operation owns accumulator state
and returns the final value through `finalize()`.

The example sums 1000 `std::int32_t` values with unary and binary operations
that call `tsl::hadd<Vec>` for each chunk and accumulate into a
`std::int64_t` scalar. It verifies the native default, exact scalar `fixed<1>`,
and portable generic widths `4` and `16`.

It also demonstrates generated primitive policy facades for reductions:

```cpp
auto sum = tsl::hadd<tsl::dataparallel::generic<4>, std::int32_t>(values);
auto matches =
    tsl::count_matches<tsl::dataparallel::generic<4>, std::int32_t>(
        values,
        needle);
```

### `masked_aggregation_operator.cpp`

Demonstrates `tsl::algo::aggregate_masked_unary` and
`tsl::algo::aggregate_masked_binary`. The helpers own contiguous partitioning,
mask loading, value loading, and scalar tail handling. The operation must
accept the activity mask, ignore inactive lanes in its accumulator state, and
return the final value through `finalize()`.

The example builds masks with `predicate_binary`, then sums only active rows
for integral, native, byte, and packed-bit mask layouts. It verifies exact
scalar `fixed<1>` plus portable generic widths `4` and `16` with a non-multiple
input length.

### `consume_operator.cpp`

Demonstrates `tsl::algo::consume_unary` and `tsl::algo::consume_binary`.
Consume helpers own contiguous partitioning, loading, and scalar tail handling,
but produce no helper-owned output.

The example passes stateful sink operations by lvalue, proving the helper does
not copy away operation state. The unary sink sums one input column, and the
binary sink sums `left + right` for each input pair.

### `masked_consume_operator.cpp`

Demonstrates `tsl::algo::consume_masked_unary` and
`tsl::algo::consume_masked_binary`. These helpers own mask loading, contiguous
value loading, and scalar tail handling, but produce no helper-owned output.

The example passes mask-aware stateful sinks by lvalue and verifies that only
active lanes contribute to the observed state. It covers integral, native,
byte, and packed-bit mask layouts with exact scalar `fixed<1>` plus portable
generic widths `4` and `16`.

## CI Integration

The generated-package CI workflow runs these examples through
`supplementary/ci/verify_generated_consumers.sh` after producing generated TSL
artifacts. New C++ examples should be added to `examples/cpp/CMakeLists.txt` so
they are automatically built and exercised by that consumer verification step.
