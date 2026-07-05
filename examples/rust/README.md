# Rust Examples

This directory contains consumer-side examples for the generated Rust TSL
library. The examples are ordinary Cargo binaries that depend on a generated
`tsl_generated` crate.

## Build Prerequisite

Generate a Rust TSL project first. The default example manifest looks for the
generated crate under `tslctmp/examples/generated/rust`:

```bash
./dev.sh generate \
  --primitives mul \
  --profiles scalar \
  --backends rust \
  --types si32 \
  --output-root ./tslctmp/examples/generated
```

Then run the examples:

```bash
cargo run --manifest-path examples/rust/Cargo.toml --bin unary_operator
```

## Examples

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

Rust helper coverage currently starts with `transform_unary`. Add matching Rust
examples here as additional Rust helper APIs are generated.
