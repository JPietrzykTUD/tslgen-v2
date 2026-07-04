# Adding A Primitive To `tsldata`

This guide is the human checklist for adding or changing a TSL primitive. It is
written from the `gather_narrow_partial` slice, but the rules are general.

The design goal is simple: a new primitive should mostly be source data plus
focused typed compiler support when the current compiler vocabulary is missing a
real concept. Avoid primitive-name branches in Python.

## 1. Name The Contract

Before editing, write down the primitive contract in plain language.

- What does the primitive compute?
- What is the signature, for example `v:=(v,v)` or `v:=(cptr,vidx,sImm)`?
- Which parameters are compile-time axes, such as immediate values, target
  types, target extensions, or SIMD type parameters?
- Which lanes are meaningful in the result?
- Is the primitive lane-local or cross-lane?
- Is it safe for the caller, or does it dereference raw pointers, use uninit
  memory, or rely on target intrinsics?

If the name needs to carry unusual semantics, prefer a literal name over a short
but surprising one. For example, `gather_narrow_partial` says that the loaded
element type is narrower than the index vector type and that only part of the
result is filled.

## 2. Find The Existing Family

Start in the closest existing file under `tsldata/primitives/`.

Look for:

- neighboring signatures;
- existing generic parameters;
- existing `requires` shape;
- existing tests and tags;
- existing safety declarations;
- existing helper primitives that should be reused through
  `call<primitive=...>(...)`.

Keep the primitive in source data when possible. Only change `tslc` when the new
shape needs a typed compiler concept that is missing.

## 3. Add Source Documentation

Every new primitive should carry source-owned documentation fields:

```tsl
brief_description "One short sentence."
detailed_description """
  A fuller user-facing explanation. Keep indentation readable in the source.
  Describe special behavior, edge cases, and backend-dependent semantics.
  """
semantics """
  input: register left, register right
  for each lane i:
    result[i] = left[i] + right[i]
  return result
  """
```

Use `brief_description` for a short API sentence. Use
`detailed_description` for user-facing details. Use `semantics` as a raw,
non-interpreted listing for the operation.

Do not add renderer-only text to these fields.

## 4. Declare Generic Axes

Use `generic_params` for type or value axes that are part of the API:

```tsl
generic_params:
  IndicesType {kind simd_type, base_types [?i64]}
  N {kind int, default 1}
```

Keep constraints source-owned when they are part of the primitive contract. For
example, a SIMD type parameter can declare `base_types` when the primitive only
accepts index vectors with specific scalar bases.

Avoid hard-coding parameter names in Python. If compiler support needs to know
which generic parameters are SIMD types, derive that from `generic_params`.

## 5. Write Tests As Data

The `tests:` block is authored source, not generated output. Prefer one
fundamental `basic` case per supported scalar type, plus corner cases when the
primitive has them.

Use typed test fields for semantic axes:

```tsl
tests:
  - {tags [basic], type "ui16", index_type "ui64", scale 2,
     case {inputs [[100, 101, 102, 103, 104], [0, 4]],
           expected [100, 104, 0, 0]}}
```

Common fields:

- `type`: result/source scalar type tag for the main `Vec`;
- `to_type`: target scalar type for representation-changing primitives;
- `to_extension`: target extension for extension-changing primitives;
- `index`: compile-time lane or segment index;
- `index_type`: scalar type tag for a `vidx` input when it differs from `type`;
- `scale`, `offset`, `src_offset`, `dst_offset`, `alignment`;
- `attrs`: authored attribute values for wildcard attributes;
- `role "compile"` for deterministic compile-only cases.

Do not encode renderer function names in tests. Test names are derived from the
primitive name and typed axes.

## 6. Fill The Extension Matrix

For each implementation group, make the support contract explicit:

```tsl
impls:
  [avx512, avx2, sse, neon, generic]:
    [bword, dword]:
      requires:
        avx512:
          bword [avx512f, avx512bw]
          dword [avx512f]
        avx2 [avx, avx2]
        sse [sse, sse2]
        neon [neon]
        generic []
      safety:
        internal_unsafe true
        caller_unsafe true
        reasons [raw_pointer]
      implementation:
        tsil "..."
```

Prefer this order:

1. Direct intrinsic implementation when it is clear and better.
2. Composition through existing primitives when it preserves semantics.
3. Small new helper primitive when a reusable operation is missing.
4. Generic fallback through existing primitives and typed TSIL regions.

Do not make `tslc` know that a primitive name is special. Selection should be
driven by signatures, type groups, requirements, safety, generic parameters, and
extension metadata.

## 7. Add Compiler Support Only For Missing Concepts

If source parsing, validation, lowering, value tests, or rendering cannot express
the primitive, add the smallest typed boundary.

Typical places:

- `tslc/src/tslc/catalog/model.py`: add a frozen domain field.
- `tslc/src/tslc/catalog/test_promotion.py`: promote parsed source to the typed
  field.
- `tslc/src/tslc/catalog/validation/`: validate accepted source fields and
  diagnose malformed nearby forms.
- `tslc/src/tslc/lower/`: lower new typed facts or TSIL regions.
- `tslc/src/tslc/value_tests/`: plan typed value-test cases and render only
  already-decided values.
- `tslc/tests/`: prove the new boundary with focused tests.

Keep raw dictionaries and parser shapes at the edge. Downstream code should
consume typed objects.

## 8. Verify In Layers

Start with focused Python checks:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_value_test_planning.py
git diff --check
```

Then generate the primitive across the selected profiles and backends:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --primitives PRIMITIVE_NAME \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --output-root ./tslctmp/TEST \
  --value-test-warnings
```

When the slice touches generated build or executable value tests, run the
generated test path too:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --primitives PRIMITIVE_NAME \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --output-root ./tslctmp/TEST \
  --test \
  --value-test-warnings
```

Use `--sde` or configured QEMU runners only when testing profiles that need an
emulator.

## 9. Review The Boundary

Before finishing, check:

- Could the next similar primitive be added mostly through `tsldata`?
- Did any Python code branch on a primitive name or extension name?
- Are unsupported cases represented as diagnostics or explicit deferred support?
- Are value-test renderers formatting plans rather than inspecting the catalog?
- Are diagnostics deterministic and source-located where practical?
- Does the primitive have documentation, tests, safety, requirements, and
  extension coverage?

If the answer to any of these is no, fix the boundary before adding more source
data.
