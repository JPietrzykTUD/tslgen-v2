# Rust Examples

This directory contains consumer-side examples for the generated Rust TSL
library. The examples are ordinary Cargo binaries that depend on a generated
`tsl_generated` crate.

## Build Prerequisite

Generate a Rust TSL project first. The default example manifest looks for the
generated crate under `tslctmp/examples/generated/rust`:

```bash
./dev.sh generate \
  --primitives add,blend,hadd,less_than,mul,set1 \
  --profiles scalar \
  --backends rust \
  --types si32 \
  --output-root ./tslctmp/examples/generated
```

Then run the examples:

```bash
cargo run --manifest-path examples/rust/Cargo.toml --bin unary_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin binary_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin chunk_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin range_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin predicate_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin where_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin masked_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin native_mask_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin byte_mask_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin bit_mask_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin consume_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin masked_consume_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin aggregation_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin masked_aggregation_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin count_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin selection_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin masked_selection_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin selection_vector_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin selected_transform_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin selected_refinement_operator
cargo run --manifest-path examples/rust/Cargo.toml --bin selected_aggregate_consume_operator
```

## Parity Matrix

Rust examples are added only when the generated Rust helper API they demonstrate
exists, so the examples stay tied to generated helper behavior rather than
scalar-only lookalikes.

| C++ example | Rust example | Status |
| --- | --- | --- |
| `unary_operator.cpp` | `unary_operator.rs` | Done: `transform_unary` |
| `binary_operator.cpp` | `binary_operator.rs` | Done: `transform_binary` |
| `chunk_operator.cpp` | `chunk_operator.rs` | Done: `for_each_chunk` |
| `range_operator.cpp` | `range_operator.rs` | Done: Rust slice APIs cover the range-style helper contract |
| `predicate_operator.cpp` | `predicate_operator.rs` | Done: `predicate_unary`, `predicate_binary` with integral masks |
| `where_operator.cpp` | `where_operator.rs` | Done: `transform_where_unary`, `transform_where_binary` with integral masks |
| `masked_operator.cpp` | `masked_operator.rs` | Done: `transform_masked_unary`, `transform_masked_binary` with integral masks |
| `native_mask_operator.cpp` | `native_mask_operator.rs` | Done: `mask_layout::Native` with `predicate_binary_mask_layout`, `transform_where_unary_mask_layout`, `transform_masked_binary_mask_layout` |
| `byte_mask_operator.cpp` | `byte_mask_operator.rs` | Done: `mask_layout::Bytes` with byte-per-row mask storage |
| `bit_mask_operator.cpp` | `bit_mask_operator.rs` | Done: `mask_layout::Bits` with packed-bit mask storage and tail-bit clearing |
| `selection_operator.cpp` | `selection_operator.rs` | Done: `select_unary`, `select_binary` |
| `masked_selection_operator.cpp` | `masked_selection_operator.rs` | Done: masked compact selection with integral/native/byte/packed-bit masks |
| `selection_vector_operator.cpp` | `selection_vector_operator.rs` | Done: dense and masked selection-vector production with `usize` row ids and integral/native/byte/packed-bit masks |
| `selected_transform_operator.cpp` | `selected_transform_operator.rs` | Done: `transform_selected_unary`, `transform_selected_binary` over `usize` row ids |
| `selected_refinement_operator.cpp` | `selected_refinement_operator.rs` | Done: `select_selected_indices_unary`, `select_selected_indices_binary` over `usize` row ids |
| `selected_aggregate_consume_operator.cpp` | `selected_aggregate_consume_operator.rs` | Done: `aggregate_selected_unary`, `aggregate_selected_binary`, `consume_selected_unary`, `consume_selected_binary` over `usize` row ids |
| `count_operator.cpp` | `count_operator.rs` | Done: dense counts, integral/native/byte/packed-bit masked counts, selected-row counts |
| `aggregation_operator.cpp` | `aggregation_operator.rs` | Done: `aggregate_unary`, `aggregate_binary` |
| `masked_aggregation_operator.cpp` | `masked_aggregation_operator.rs` | Done: `aggregate_masked_unary`, `aggregate_masked_binary` with integral masks |
| `consume_operator.cpp` | `consume_operator.rs` | Done: `consume_unary`, `consume_binary` |
| `masked_consume_operator.cpp` | `masked_consume_operator.rs` | Done: `consume_masked_unary`, `consume_masked_binary` with integral masks |

## Implemented Examples

### `unary_operator.rs`

Demonstrates `tsl::algo::transform_unary` with a register-level square
operation:

```rust
struct Square;

impl<V> tsl::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        tsl::mul::<V>(value, value)
    }
}
```

The example allocates 1000 `i32` values, fills them, and verifies the same
operation through:

- `parallelism::native()`
- `parallelism::fixed::<1>()`
- `parallelism::generic::<8>()`

### `binary_operator.rs`

Demonstrates `tsl::algo::transform_binary` with a register-level add operation:

```rust
struct Add;

impl<V> tsl::algo::BinaryKernel<V> for Add
where
    V: StaticSimdVector + tsl::detail::primitives::AddImpl,
{
    fn apply(
        &mut self,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType {
        tsl::add::<V>(left, right)
    }
}
```

The example allocates two 1000-element `i32` inputs, fills them, and verifies
the native, fixed scalar, and explicit generic policies.

### `chunk_operator.rs`

Demonstrates `tsl::algo::for_each_chunk`, the low-level escape hatch for
algorithms that need chunk pointer metadata and want to own memory effects:

```rust
struct ChunkSum {
    base: *const i32,
    total: i64,
    visited: usize,
    metadata_ok: bool,
}

impl<V> tsl::algo::ChunkKernel<V> for ChunkSum
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::LoadImpl<false>
        + tsl::detail::primitives::HaddImpl,
{
    unsafe fn apply(&mut self, ptr: *const V::BaseType, offset: usize, count: usize) {
        let values = unsafe { tsl::load::<V, false>(ptr) };
        self.total += i64::from(tsl::hadd::<V>(values));
        self.visited += count;
    }
}
```

The example allocates 1003 `i32` values, verifies chunk metadata, and sums the
input through native, fixed scalar, and explicit generic policies. The Rust
example uses explicit `generic::<4>()` and `generic::<16>()` policies where the
C++ scalar-profile example uses fixed lane-count overloads that can fall back to
generic vectors.

### `range_operator.rs`

Demonstrates the Rust range-style helper surface. Rust helpers take slices
directly, so the range-style contract is the primary safe API rather than a
separate overload layer. The example composes:
`transform_unary`, `transform_binary`, `predicate_binary`,
`select_masked_unary`, `aggregate_masked_binary`,
`consume_masked_unary`, and `for_each_chunk`.

```rust
let policy = tsl::algo::parallelism::generic::<4>();
tsl::algo::transform_unary(policy, &mut square, &left, &mut output);
```

The example verifies transformed output, integral mask chunk production,
masked compaction, masked aggregation, masked consumption, and chunk metadata
using one shared set of input slices.

### `predicate_operator.rs`

Demonstrates `tsl::algo::predicate_unary` and
`tsl::algo::predicate_binary`. Predicate helpers own contiguous partitioning,
loading, scalar tail handling, conversion from native mask to integral mask,
and writing one integral mask chunk per vector chunk:

```rust
struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}
```

The unary predicate checks `value < 0` using `tsl::set1::<V>(0)` and
`tsl::less_than::<V>`. The example verifies the produced integral mask stream
for native, fixed scalar, and explicit generic policies. The generated Rust
helper support roots pull in `to_integral`; the example generation command
still requests the predicate primitives used by the operation itself.

### `where_operator.rs`

Demonstrates `tsl::algo::transform_where_unary` and
`tsl::algo::transform_where_binary` with integral mask chunks produced by
`predicate_binary`. Where helpers own contiguous partitioning, mask conversion,
loading, masked storage, and scalar tail handling. Inactive output lanes are
preserved:

```rust
struct SquareWhere;

impl<V> tsl::algo::MaskedUnaryKernel<V> for SquareWhere
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, _active: V::MaskType, value: V::RegisterType) -> V::RegisterType {
        tsl::mul::<V>(value, value)
    }
}
```

The binary where operation uses `tsl::add::<V>`. The example initializes output
buffers with sentinel values and verifies that inactive rows keep those values
for native, fixed scalar, and explicit generic policies.

### `masked_operator.rs`

Demonstrates `tsl::algo::transform_masked_unary` and
`tsl::algo::transform_masked_binary` with the same integral mask chunks used by
the where example. Masked full-store helpers own partitioning, mask conversion,
loading, scalar tail handling, and storing every output lane. The operation is
responsible for meaningful inactive-lane values:

```rust
struct SquareOrOriginal;

impl<V> tsl::algo::MaskedUnaryKernel<V> for SquareOrOriginal
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, active: V::MaskType, value: V::RegisterType) -> V::RegisterType {
        let squared = tsl::mul::<V>(value, value);
        tsl::blend::<V>(active, value, squared)
    }
}
```

The binary masked operation uses `tsl::add::<V>` and `tsl::blend::<V>` to write
`left + right` for active rows and the original left value for inactive rows.
The example initializes output buffers with sentinel values and verifies no
sentinel survives, proving inactive rows are explicitly written rather than
preserved.

### `native_mask_operator.rs`

Demonstrates layout-aware predicate and transform helpers with
`tsl::algo::mask_layout::Native`. Native masks are stored as the vector's
generated `MaskType` rather than as integral mask chunks:
`predicate_binary_mask_layout`, `transform_where_unary_mask_layout`, and
`transform_masked_binary_mask_layout`.

### `byte_mask_operator.rs`

Demonstrates `tsl::algo::mask_layout::Bytes`, where mask storage is one `u8`
per input row. The example verifies the byte mask contents before using the same
mask buffer with where and masked transforms.

### `bit_mask_operator.rs`

Demonstrates `tsl::algo::mask_layout::Bits`, where mask storage is packed into
`u8` words. The example initializes the mask buffer with set bits and verifies
that predicate generation clears inactive and out-of-range tail bits.

### `consume_operator.rs`

Demonstrates `tsl::algo::consume_unary` and `tsl::algo::consume_binary`.
Consume helpers own contiguous partitioning, loading, and scalar tail handling,
but produce no helper-owned output:

```rust
struct SumSink {
    total: i64,
}

impl<V> tsl::algo::UnaryConsumeKernel<V> for SumSink
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::HaddImpl,
{
    fn consume(&mut self, value: V::RegisterType) {
        self.total += i64::from(tsl::hadd::<V>(value));
    }
}
```

The binary sink uses `tsl::add::<V>` and `tsl::hadd::<V>` to accumulate
`left + right`. The example verifies native, fixed scalar, and explicit generic
policies.

### `masked_consume_operator.rs`

Demonstrates `tsl::algo::consume_masked_unary` and
`tsl::algo::consume_masked_binary` with integral mask chunks produced by
`predicate_binary`. Masked consume helpers own contiguous partitioning, mask
conversion, loading, and scalar tail handling, but produce no helper-owned
output:

```rust
struct MaskedSumSink {
    total: i64,
}

impl<V> tsl::algo::MaskedUnaryConsumeKernel<V> for MaskedSumSink
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::HaddImpl
        + tsl::detail::primitives::Set1Impl,
{
    fn consume(&mut self, active: V::MaskType, value: V::RegisterType) {
        let zero = tsl::set1::<V>(0);
        let selected = tsl::blend::<V>(active, zero, value);
        self.total += i64::from(tsl::hadd::<V>(selected));
    }
}
```

The binary sink uses `tsl::add::<V>`, `tsl::blend::<V>`, and `tsl::hadd::<V>`
to accumulate `left + right` only for active rows. The example verifies native,
fixed scalar, and explicit generic policies.

### `aggregation_operator.rs`

Demonstrates `tsl::algo::aggregate_unary` and `tsl::algo::aggregate_binary`.
Aggregate helpers own contiguous partitioning, loading, scalar tail handling,
and returning the operation's final value:

```rust
struct SumOp {
    total: i64,
}

impl<V> tsl::algo::UnaryAggregateKernel<V> for SumOp
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::HaddImpl,
{
    type Output = i64;

    fn accumulate(&mut self, value: V::RegisterType) {
        self.total += i64::from(tsl::hadd::<V>(value));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}
```

The binary aggregate uses `tsl::add::<V>` and `tsl::hadd::<V>` to accumulate
`left + right`. The example verifies native, fixed scalar, and explicit generic
policies.

### `masked_aggregation_operator.rs`

Demonstrates `tsl::algo::aggregate_masked_unary` and
`tsl::algo::aggregate_masked_binary` with integral mask chunks produced by
`predicate_binary`. Masked aggregate helpers own contiguous partitioning, mask
conversion, loading, scalar tail handling, and returning the operation's final
value:

```rust
struct MaskedSumOp {
    total: i64,
}

impl<V> tsl::algo::MaskedUnaryAggregateKernel<V> for MaskedSumOp
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::HaddImpl
        + tsl::detail::primitives::Set1Impl,
{
    type Output = i64;

    fn accumulate(&mut self, active: V::MaskType, value: V::RegisterType) {
        let zero = tsl::set1::<V>(0);
        let selected = tsl::blend::<V>(active, zero, value);
        self.total += i64::from(tsl::hadd::<V>(selected));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}
```

The binary aggregate uses `tsl::add::<V>`, `tsl::blend::<V>`, and
`tsl::hadd::<V>` to accumulate `left + right` only for active rows. The example
verifies native, fixed scalar, and explicit generic policies.

### `count_operator.rs`

Demonstrates dense, masked, and selected-row predicate cardinality helpers:
`tsl::algo::count_unary`, `tsl::algo::count_binary`,
`tsl::algo::count_masked_unary`, `tsl::algo::count_masked_binary`,
`tsl::algo::count_masked_unary_mask_layout`,
`tsl::algo::count_masked_binary_mask_layout`,
`tsl::algo::count_selected_unary`, and
`tsl::algo::count_selected_binary`.
The dense helpers evaluate predicate kernels and return the number of active
lanes. The masked helpers additionally intersect the predicate mask with a
caller-owned mask stream:

```rust
struct Negative;

impl<V> tsl::algo::UnaryPredicateKernel<V> for Negative
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::Less_thanImpl
        + tsl::detail::primitives::Set1Impl,
{
    fn test(&mut self, value: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(value, tsl::set1::<V>(0))
    }
}
```

The example builds integral, native, byte-per-row, and packed-bit mask streams,
then counts rows matching dense unary, dense binary, masked unary, and masked
binary predicates for native, fixed scalar, and explicit generic policies. It
also counts over a `usize` selection vector, including the scaled raw selected
binary entry point where `SCALE = 4` matches `sizeof(i32)`.

### `selection_operator.rs`

Demonstrates dense compacting selection helpers:
`tsl::algo::select_unary` and `tsl::algo::select_binary`. These helpers
evaluate predicate kernels, compact selected input values into caller-provided
output storage, and return the number of produced values:

```rust
struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}
```

The unary selection compacts negative input values. The binary selection tests
`left < right` and compacts values from the left input, matching the C++
helper contract. Unwritten output slots remain untouched.

### `masked_selection_operator.rs`

Demonstrates layout-aware masked compacting selection helpers:
`tsl::algo::select_masked_unary_mask_layout` and
`tsl::algo::select_masked_binary_mask_layout`. These helpers intersect a
caller-owned mask stream with the operation predicate, compact selected input
values into caller-provided output storage, and return the number of produced
values.

The example builds integral, native, byte-per-row, and packed-bit mask streams
with `predicate_binary_mask_layout`, then compacts negative input values only
where the input mask is active. It also builds a negative mask stream and runs
a masked binary `left < right` selection. As with dense selection, the compacted
values come from the left/input range and unwritten output slots remain
untouched.

### `selection_vector_operator.rs`

Demonstrates selection-vector production helpers:
`tsl::algo::select_indices_unary`, `tsl::algo::select_indices_binary`,
`tsl::algo::select_masked_indices_unary`, and
`tsl::algo::select_masked_indices_binary`, plus their layout-aware masked
counterparts. These helpers evaluate predicate kernels and write selected row
ids as `usize` values into caller-provided output storage:

```rust
struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}
```

The example verifies dense unary and binary row-id streams, then builds
integral, native, byte-per-row, and packed-bit mask streams with
`predicate_binary_mask_layout` and verifies masked unary and binary row-id
streams. Output order follows input row order, and unwritten slots remain
untouched.

### `selected_transform_operator.rs`

Demonstrates selection-vector consumer helpers:
`tsl::algo::transform_selected_unary` and
`tsl::algo::transform_selected_binary`. These helpers read caller-owned
`usize` row ids, load the selected rows, apply ordinary register-level kernels,
and write dense selected output values.

The example builds a reversed selection vector, squares selected values with
the unary helper, adds selected left/right values with the binary helper, and
also exercises the unsafe raw const-scale entry point with `SCALE = 4`.
Concrete generated vector policies use `gather_narrow` to bridge the
pointer-backed `usize` row-id stream into selected loads; portable generic
policies keep a scalar lane fallback for the default `SCALE = 0` case. Unwritten
output slots remain untouched.

### `selected_refinement_operator.rs`

Demonstrates selection-vector refinement helpers:
`tsl::algo::select_selected_indices_unary` and
`tsl::algo::select_selected_indices_binary`. These helpers read caller-owned
`usize` row ids, evaluate predicates on the selected rows, and write the
matching original row ids densely to caller-provided output storage.

The example builds a reversed selection vector, refines it with a unary
negative predicate and a binary `left < right` predicate, and also exercises the
unsafe raw const-scale binary entry point with `SCALE = 4`. Concrete generated
vector policies load selected rows through `gather_narrow`; unwritten output
slots remain untouched.

### `selected_aggregate_consume_operator.rs`

Demonstrates selected-row sink helpers:
`tsl::algo::aggregate_selected_unary`,
`tsl::algo::aggregate_selected_binary`,
`tsl::algo::consume_selected_unary`, and
`tsl::algo::consume_selected_binary`. These helpers read caller-owned `usize`
row ids, load selected rows, and pass selected values to ordinary aggregate or
consume kernels.

The example builds a reversed selection vector, verifies unary and binary
selected sums through aggregate helpers, verifies the same totals through
consume helpers, and exercises the unsafe raw const-scale binary aggregate
entry point with `SCALE = 4`. Concrete generated vector policies load selected
rows through `gather_narrow`.
