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

Rust helper coverage currently includes dense unary/binary transforms,
slice/range-style composition, chunk enumeration, integral predicate
materialization, integral-mask where transforms, integral-mask masked
full-store transforms, native/byte/packed-bit mask predicate and transform
examples, dense consume helpers,
integral-mask masked consume helpers, dense aggregate helpers, and
integral-mask masked aggregate helpers, dense/mask-layout/selected-row count helpers, and
dense/mask-layout compacting selection helpers, plus dense/mask-layout
selection-vector production helpers, selected-row transform consumers, and
selected-row refinement consumers, plus selected-row aggregate and consume
sinks. The Rust README tracks remaining C++ parity with a helper-by-helper
matrix.
