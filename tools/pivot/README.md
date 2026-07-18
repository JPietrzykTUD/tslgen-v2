# PIVOT Exporter

PIVOT export is an independently packaged, lockstep downstream tool. Its
distribution is `tslc-pivot`, its Python package is `tslc_pivot`, and its
command is `tslc-pivot`. Core `tslc` does not load, register, or ship the tool;
the dependency points only from PIVOT to the compiler.

Install both repository packages and inspect the standalone command:

```bash
python -m pip install --no-deps -e ./tslc
python -m pip install --no-deps -e ./tools/pivot
tslc-pivot --help
```

The root `tslc.toml` supplies source roots and machine profiles, so a complete
export from the repository root is:

```bash
tslc-pivot \
  --language cpp,rust \
  --output-root tslctmp/pivot-export
```

Use `--config PATH` to select another project file. Explicit `--sources` and
`--machine-profiles` values override its inputs; `--primitives`, `--profiles`,
and `--types` restrict the selected corpus. `--strict` fails if any selected
specialization is skipped, while `--show-skips` prints stable PIVOT-owned skip
records without changing success status.

## Output Contract

The exporter maps selected TSL primitive specializations and abstract vector
operations to deterministic C++ and Rust YAML documents. Each definition
contains its concrete target/type signature and a completely flattened
`direct` list of sequential language instructions. Runtime branches and loops
are outside the format.

PIVOT reuses compiler-owned source validation, catalog, profile, selection,
dependency, TSIL lowering, capability, intrinsic, and type-spelling facts. It
owns the PIVOT-specific profile cover, residual target-text interpretation,
binding-aware recursive flattening, YAML schema and paths, skips, diagnostics,
compatibility, and coverage evidence.

Unlike compiler-owned projections, this downstream tool may parse a bounded
subset of lowered C++ and Rust text. That interpretation remains local,
fail-closed, and PIVOT-owned; it does not change or extend compiler semantics.

The current admitted subset consists of concrete scalar or fixed-width
specializations whose lowered target text can be flattened into sequential
semicolon-terminated statements. Generation-time TSIL control regions may
disappear during ordinary lowering, but residual runtime branches, loops,
blocks, casts, comments, string literals, unresolved generated-library names,
and ambiguous substitutions are rejected. Only inferred locals and captured
primitive calls participate in recursive inlining.

## YAML Schema

The output tree contains one `cpp/<primitive>.yaml` or
`rust/<primitive>.yaml` document per emitted primitive and language. A document
has this shape:

```yaml
name: "add"
input:
  - "left"
  - "right"
output: "res"
definitions:
  - isa: "avx2"
    dtype: "int32"
    signature:
      left: "__m256i"
      right: "__m256i"
      res: "__m256i"
    direct:
      - "res = _mm256_add_epi32(left, right);"
```

Each nominal definition identity is
`(language, document, isa, dtype, signature)`. The current corpus can emit more
than one entry with the same nominal identity, so the compatibility manifest
also records multiplicity and each entry's `direct` hash. Every `direct` value
is a completely flattened, deterministic instruction list; the format cannot
represent runtime branching or loops.

## Compatibility And Coverage

The standalone package is intentionally pinned to the matching repository
`tslc` version rather than promising a stable third-party compiler API. Private
compiler imports are explicit lockstep dependencies and are checked by the
tool's boundary tests.

Every definition entry in the canonical full-corpus baseline must remain
emitted, including pre-existing nominal-identity collisions. Coverage may
increase, but aggregate counts cannot conceal a removed or replaced entry, and
changed `direct` hashes require focused review.

The manifest retains exact skip reasons and an inventory hash. Its
`reason-prefix-v1` census also groups those messages into stable evidence
families; this is a manifest-only classification until runtime skips gain typed
categories in the rework.

Regenerate the committed authority only through its guarded maintenance tool:

```bash
python tools/pivot/scripts/update_full_export_baseline.py
```

The command accepts additions but refuses removed entries, reduced
multiplicity, or replaced `direct` hashes. Use
`--allow-reviewed-incompatible-baseline` only after the explicit product or
correctness review named by the tool charter.

The approved migration and validation sequence is documented in the [PIVOT
export rework plan](../../todo/pivot-export-rework-plan.md).

Run tool validation independently from core compiler tests:

```bash
python -m compileall -q tools/pivot/src/tslc_pivot
PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q tools/pivot/tests
(cd tools/pivot && python -m mypy)
```

See [CHARTER.md](CHARTER.md) for the stable product boundary and
[AGENTS.md](AGENTS.md) for implementation and validation rules.
