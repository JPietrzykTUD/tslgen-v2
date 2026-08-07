# Adding A Target Extension

An extension is one vertical compiler slice.

It crosses source data, profiles, backends, tests, and verification.

Keep the slice additive.

Avoid extension-name branches in primitive lowering and templates.

## 1. Define The Target Contract

Record these facts first:

| Fact | Example |
| --- | --- |
| Extension | `wasm128` |
| Extension family | `wasm` |
| Profile family | `wasm32` |
| Machine profile | `wasm32-simd128` |
| Required feature | `simd128` |
| Vector width | `128` bits |
| C++ target | `wasm32-wasip1` |
| Rust target | `wasm32-wasip1` |
| Runner | `wasmtime` |

Also choose a small primitive and type slice.

The first slice must prove the whole path.

## 2. Understand The Ownership Chain

```text
target_families.tsl
  -> admits extension/feature families and owns shared compiler spellings

machine_profiles.json
  -> selects concrete target features, flags, and a runner

extension.tsl
  -> defines vector types, headers, masks, and intrinsic policy

primitive implementations
  -> declare required features and TSIL bodies

backend dialects and assets
  -> spell already-decided target code

verifier
  -> builds and runs the generated project
```

Each file owns one kind of fact.

Do not repeat the same decision across layers.

## 3. Add The Target Family

Edit `tsldata/detail/target_families.tsl`.

Add the extension family:

```tsl
known_extension_families [scalar, generic_like, x86, arm, cuda, wasm]
```

Declare each machine-profile and `requires` feature once. Add a shared compiler
spelling only when it differs from the source token:

```tsl
known_target_features [simd128]
target_feature_spellings:
  source_name:
    cpp "cpp-spelling"
    rust "rust-spelling"
```

The scalar form (`source_name "shared-spelling"`) applies to every backend.
Machine-profile `alternatives` are reserved for genuine profile-specific
overrides; do not repeat a shared spelling in every profile.

Add or update the profile family:

```tsl
profile_families:
  wasm32:
    extension_families [wasm]
    runner_kinds [wasmtime]
    sort_order 30
    backends:
      cpp:
        feature_flags true
        target "wasm32-wasip1"
      rust:
        feature_flags true
        target "wasm32-wasip1"
```

For a GNU/Linux cross family, backend profile data may additionally declare
`compiler_role`, `cmake_system_name`, `cmake_system_processor`, and
`pass_target_to_compiler`. These typed facts flow into verification; do not
branch on a profile or extension name in the verifier. Set
`pass_target_to_compiler false` for prefixed GNU drivers that already encode
the target.

This file owns routing, documentation classification, and shared target-feature
capabilities.

It does not own primitive selection.

It does not own intrinsic names.

It does not own build commands.

## 4. Add The Machine Profile

Edit `supplementary/buildsystem/machine_profiles.json`.

```json
{
  "wasm32": [
    {
      "name": "wasm32-simd128",
      "target_features": "simd128",
      "backend_flags": {"cpp": []},
      "supported_backends": ["cpp", "rust"],
      "runner": {"kind": "wasmtime", "profile": "default"}
    }
  ]
}
```

`target_features` is a capability set.

An implementation with `requires [simd128]` needs that capability.

Wasm target features are not host CPU probes.

`supported_backends` restricts profile emission and CI shards. Omit it to keep
the profile family's registered backends; use an explicit list for a C++-only or
Rust-only target. Unsupported requested pairs produce a recorded informational
skip and no fallback profile for that backend.

## 5. Add Extension Metadata

Edit `tsldata/extensions/extension.tsl`.

```tsl
extension wasm128:
  extension_name "wasm128"
  family "wasm"
  intrinsic_style "wasm"
  vector_bits 128
  native_sort_order 800
  default_test_target true
  cpp:
    supported true
    headers ["wasm_simd128.h"]
  rust:
    supported true
    type_name "Wasm128"
    arch_module "wasm32"
```

Also define:

- register types for every supported scalar type;
- intrinsic prefixes and suffixes;
- mask representation;
- backend support;
- activation rules when needed.

Use explicit register mappings when native registration needs concrete tags.

Base `wasm128` needs no `active_when` rule.

The profile admits the family.

The implementation `requires` field gates the feature.

## 6. Model Compiler-Vector Overlays Explicitly

An overlay names semantic backend capabilities rather than concrete compiler facts:

| Field | Effect |
| --- | --- |
| `compiler_capabilities [clang_vector_types]` | Requests the backend-owned Clang vector contract, including its header group, compiler IDs, probes, macros, and diagnostics. |
| `compiler_capabilities [ext_vector_type_boolean]` | Adds the semantic Boolean-vector requirement. |
| `dataparallel_inference false` | Excludes the overlay from normal inference. |

Concrete compiler IDs, feature tests, preprocessor macros, and probe sources belong
to the backend capability registry, not extension source data.

Use `vector::fixed` for the hardware fallback.

Use `cast<bitcast>` at representation boundaries.

Do not name `sse`, `avx2`, `avx512`, or `neon` in the fallback body.

Dependency closure selects the concrete hardware extension.

## 7. Add An Intrinsic Dialect Only When Needed

Reuse an existing intrinsic style when possible.

Add a new typed style when the composition rule differs.

Example:

```text
x86 operation-first:
  _mm256_add_epi32

Wasm lane-shape-first:
  wasm_i32x4_add
  core::arch::wasm32::i32x4_add
```

The extension declares:

```tsl
intrinsic_style "wasm"
```

The backend intrinsic dialect interprets that value.

Do not build intrinsic names in a project template.

Do not rewrite raw primitive text.

Verify names against the target toolchain.

## 8. Add A Small Primitive Slice

Start with operations that prove construction, memory, and arithmetic.

For `wasm128`:

```text
set_zero  set1  load  store  from_array  to_array  add  sub
```

Start with a small type set:

```text
si32  ui32  f32
```

Gate each Wasm implementation:

```tsl
requires [simd128]
implementation:
  tsil """
    complete(intrin<add, build>(left, right));
    """
```

Use typed regions:

- `intrin<...>`;
- `call<primitive=...>(...)`;
- `cast<...>(...)`;
- `complete(...)`.

Add a new TSIL concept when the existing vocabulary cannot express the intent.

Do not hide semantics in a template.

## 9. Connect Verification

Non-native targets need explicit verifier facts.

For WebAssembly:

- accept an injectable Wasmtime path;
- accept runner kind `wasmtime`;
- build C++ for WASI;
- build Rust for `wasm32-wasip1`;
- enable Rust feature `+simd128`;
- run generated Wasm binaries through Wasmtime.

Missing tools must produce a deterministic skip or diagnostic.

Do not make the default test suite depend on local hardware or network access.

## 10. Test Each Boundary

| Boundary | Prove |
| --- | --- |
| Catalog | Extension and profile facts are typed correctly. |
| Selection | `requires` admits only capable profiles. |
| Backend | Headers, types, modules, and intrinsics are correct. |
| Lowering | The first primitive slice lowers for C++ and Rust. |
| Safety | Raw memory and intrinsic use keep the right safety state. |
| Verifier | Target, flags, runner, and skip behavior are correct. |

The connection should look like this:

```text
wasm32-simd128 + simd128
  -> selects wasm128 implementation
  -> lowers intrin<add, build>
  -> emits wasm_i32x4_add or core::arch::wasm32::i32x4_add
  -> builds wasm32-wasip1
  -> runs through Wasmtime
```

## 11. Generate A Smoke Project

```bash
tslc check \
  --primitive add \
  --profile wasm32-simd128 \
  --type si32 \
  --backend cpp \
  --backend rust

tslc generate \
  --primitives add,sub,set1,set_zero,load,store,from_array,to_array \
  --profiles wasm32-simd128 \
  --types si32,ui32,f32 \
  --backends cpp,rust \
  --output-root ./tslctmp/wasm-simd-smoke \
  --no-format
```

Inspect:

- C++ target headers;
- C++ target flags;
- Rust target-feature attributes;
- generated profile registration;
- representative intrinsic names.

Use `./tslctmp/...` for output.

Do not commit generated smoke projects.

## 12. Validate

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog.py \
  tslc/tests/test_backend_target_capability.py \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_build_verify_config.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

Run generated builds when toolchains are available.

Keep runner and toolchain detection skippable.

## 13. Expand Deliberately

Expand only after the vertical slice is stable.

Add types first.

Then add primitive families.

Update coverage baselines last.

## Review Checklist

- Target-family routing is source data.
- Machine-profile capabilities are explicit.
- Extension metadata owns target facts.
- Primitive bodies declare feature requirements.
- Backend dialects own target spelling.
- Templates only format decided values.
- Missing tools skip cleanly.
- Generated output is deterministic.
- The next similar extension remains additive.
