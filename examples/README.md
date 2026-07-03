# TSL Examples

This directory contains small consumer-side examples for the generated C++ TSL
library. They are not compiler tests by themselves; they demonstrate how a user
project can consume generated artifacts through CMake.

## Build Prerequisite

Generate a C++ TSL project first. The default example CMake configuration looks
for the generated output root under `tslctmp/examples/generated` and consumes
its `cpp/` project through `FetchContent`:

```bash
./dev.sh generate \
  --primitives add,mul \
  --profiles scalar \
  --backends cpp \
  --types si32 \
  --output-root ./tslctmp/examples/generated
```

Then configure, build, and run the examples:

```bash
cmake -S examples -B tslctmp/examples/build \
  -DTSL_GENERATED_ROOT_DIR="$PWD/tslctmp/examples/generated" \
  -DTSL_PROFILE=scalar
cmake --build tslctmp/examples/build
ctest --test-dir tslctmp/examples/build --output-on-failure
```

If the environment chooses an unwanted C++ compiler, pass the compiler
explicitly when configuring:

```bash
env CXX=g++ CC=gcc cmake -S examples -B tslctmp/examples/build \
  -DTSL_GENERATED_ROOT_DIR="$PWD/tslctmp/examples/generated" \
  -DTSL_PROFILE=scalar
```

The generated-package CI workflow also publishes a packaged generated TSL archive
as a GitHub Release asset for version tags. A downstream CMake project can
consume such an archive directly:

```bash
cmake -S examples -B tslctmp/examples/build \
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
same operation through native and exact data-parallel policies:

- `transform_unary(...)` defaults to `parallelism::native`, the selected
  profile's natural vector shape for the element type.
- `transform_unary<1>`, `transform_unary<4>`, and `transform_unary<128>`
  request exact lane counts. They forward to `parallelism::fixed<N>` internally,
  using a matching static native vector when available or the portable
  `tsl::generic<N>` vector otherwise.
- `transform_unary<128>` demonstrates a large portable generic vector and why
  operations should accept values through
  `tsl::reg_param<Vec>::type`.

`Vec::register_type` names the actual register object type. `tsl::reg_param`
names the generated-library parameter-passing convention for that object:
native/scalar registers are passed by value, while array-backed generic
registers are passed by `const&` to avoid large copies.

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
`transform_binary<4>`, and `transform_binary<128>` exact-lane overloads. It
exercises the same helper-owned loop, alignment, load, tail, and store mechanics
as the unary example, but for two contiguous input columns.

## CI Integration

The generated-package CI workflow runs these examples through
`supplementary/ci/verify_generated_consumers.sh` after producing generated TSL
artifacts. New examples should be added to `examples/CMakeLists.txt` so they are
automatically built and exercised by that consumer verification step.
