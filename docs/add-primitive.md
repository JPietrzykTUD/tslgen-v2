# Adding A Primitive

Add primitives in `tsldata/primitives/`.

Keep primitive behavior in source data.

Change `tslc` only when the compiler lacks a real typed concept.

## 1. Define The Contract

Write the contract before the implementation.

Record:

- the operation;
- the signature;
- parameter names;
- generic axes;
- lane behavior;
- safety requirements;
- supported types and extensions.

Example:

```tsl
prim<v:=(v,v)> add(left, right):
```

The signature connects source names to typed parameter kinds:

```text
v := (v, v)
       |  |
       |  +-- right: vector
       +----- left: vector

result: vector
```

Use a literal name.

Do not hide unusual behavior behind a generic name.

## 2. Choose The Source File

Find the closest family under `tsldata/primitives/`.

Copy its local structure.

Check nearby primitives for:

- signature style;
- `generic_params`;
- `requires` maps;
- safety declarations;
- tests;
- reusable primitive calls.

Use `call<primitive=...>(...)` for reusable generated operations.

Do not add a Python branch for one primitive name.

## 3. Add Documentation

Use all three source fields:

```tsl
brief_description "Adds corresponding vector lanes."
detailed_description """
  Each output lane depends on the matching input lanes.
  Overflow follows the selected lane type.
  """
semantics """
  input: register left, register right
  for each lane i:
    result[i] = left[i] + right[i]
  return result
  """
```

| Field | Purpose |
| --- | --- |
| `brief_description` | One API sentence. |
| `detailed_description` | User-visible details and edge cases. |
| `semantics` | A direct operation listing. |

These fields are source-owned text.

They do not control lowering.

## 4. Declare Generic Axes

Use `generic_params` for public type or value axes.

```tsl
generic_params:
  IndicesType:
    kind simd_type
    constraints:
      base_types [?i64]
  N:
    kind int
    default 1
```

The compiler derives behavior from `kind`.

It must not infer a generic kind from the parameter name.

Keep source constraints in the source contract.

## 5. Declare A Registered Semantic Overload Only When Needed

Use `overload` when same-name declarations differ along an axis already owned
by `tsldata/detail/overload_axes.tsl`:

```tsl
overload:
  axis registered_axis
  value registered_value
  primary true
```

The block accepts exactly `axis`, `value`, and optional boolean `primary`.
Exactly one source declaration in the complete same-name family declares
`primary true`; that value becomes primary for every sibling declaration with
the same value. The compiler validates the distinguishing operand from the
registry's signature-kind rules. It does not infer an overload from primitive
or parameter names.

Do not use this block for immediates, masks, generic parameters, result targets,
or implementation safety. Those facts retain their existing source and typed
owners. Semantic overload metadata is currently catalog/editor behavior and
does not change generated API names.

## 6. Add Benchmark Facts Only When Needed

Most workload behavior comes from the signature.

Use `benchmarks:` only for missing semantic facts.

```tsl
benchmarks:
  latency_chain data
  operand_domains:
    divisor nonzero
```

The field and domain vocabularies are closed.

See [Variant benchmarking and autotuning](variant-benchmarking.md).

## 7. Add Tests As Data

Author expected values in `tests:`.

```tsl
tests:
  - {tags [basic], type "ui16", index_type "ui64", scale 2,
     case {inputs [[100, 101, 102, 103, 104], [0, 4]],
           expected [100, 104, 0, 0]}}
```

Common axes:

| Field | Meaning |
| --- | --- |
| `type` | Main vector scalar type. |
| `to_type` | Target scalar type. |
| `to_extension` | Target extension. |
| `index` | Compile-time lane or segment index. |
| `index_type` | Scalar type of a `vidx` input. |
| `scale` | Compile-time scale. |
| `offset` | Offset axis. |
| `src_offset` | Source offset. |
| `dst_offset` | Destination offset. |
| `alignment` | Alignment axis. |
| `attrs` | Values for wildcard attributes. |
| `role "compile"` | Compile-only case. |

Start with one `basic` case for each supported scalar type.

Add edge cases for unusual semantics.

Do not put renderer function names in source tests.

The planner derives generated test names from typed axes.

## 8. Add Implementations

Make support explicit for each extension and type group.

```tsl
impls:
  [avx2, sse, neon, generic]:
    [dword]:
      requires:
        avx2 [avx, avx2]
        sse [sse, sse2]
        neon [neon]
        generic []
      safety:
        internal_unsafe true
        caller_unsafe false
        reasons [intrinsic]
      implementation:
        tsil """
          complete(intrin<add, build>(left, right));
          """
```

Prefer this order:

1. Use a direct intrinsic.
2. Compose existing primitives.
3. Add a small reusable helper primitive.
4. Use a generic typed-TSIL fallback.

Selection uses typed facts:

```text
signature + type group + extension + requires + generic axes + safety
  -> selected implementation
```

Selection must not depend on a primitive-name branch in Python.

## 9. Add Compiler Support Only For A Missing Concept

Use the smallest typed boundary.

| Need | Owner |
| --- | --- |
| New source field | Parser and catalog validation. |
| New domain fact | Frozen catalog model. |
| New shared body semantics | Typed TSIL region. |
| New backend spelling | Backend translation or asset. |
| New test shape | Typed value-test planner. |

Typical paths:

```text
tslc/src/tslc/catalog/model.py
tslc/src/tslc/catalog/validation/
tslc/src/tslc/lower/
tslc/src/tslc/value_tests/
tslc/tests/
```

Keep raw dictionaries at parsing boundaries.

Use frozen typed values downstream.

Do not repair malformed source silently.

Emit a source-located diagnostic.

## 10. Check The Full Connection

```text
primitive source
  -> catalog validation
  -> typed Primitive
  -> implementation selection
  -> TSIL scanning and lowering
  -> backend render model
  -> generated wrapper
  -> generated value test
```

Inspect at least one C++ artifact.

Inspect at least one Rust artifact.

## 11. Validate

Run focused checks:

```bash
tslc check \
  --primitive PRIMITIVE_NAME \
  --profile scalar \
  --backend cpp \
  --type si32
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_value_test_planning.py
git diff --check
```

Generate both backends:

```bash
./dev.sh generate \
  --primitives PRIMITIVE_NAME \
  --profiles scalar \
  --backends cpp,rust
```

Build and run generated tests when output behavior changed:

```bash
./dev.sh test \
  --primitives PRIMITIVE_NAME \
  --profiles scalar,avx2 \
  --backends cpp,rust
```

Use `./tslctmp/...` for scratch output.

Use an emulator only for a profile that requires one.

## Review Checklist

- The signature matches the parameter names.
- Documentation states special semantics.
- Tests cover supported types and edge cases.
- Requirements match the target features.
- Safety is explicit.
- Unsupported cases produce diagnostics or skips.
- Python does not branch on the primitive name.
- Renderers only format planned values.
- The next similar primitive remains mostly source data.
