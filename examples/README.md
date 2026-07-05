# TSL Examples

This directory contains checked-in consumer examples for generated TSL
libraries.

- `cpp/` contains C++ examples built with CMake against generated `cpp/`
  artifacts.
- `rust/` contains Rust examples built with Cargo against generated `rust/`
  artifacts.

The generated-package CI consumer check runs both language example sets through
`supplementary/ci/verify_generated_consumers.sh` after producing generated TSL
artifacts.

Rust helper coverage currently starts with `transform_unary`, so the Rust tree
has a real unary example first. Add Rust examples alongside new generated Rust
helper APIs as those APIs reach parity with the C++ helper surface.
