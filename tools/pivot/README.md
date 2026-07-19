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

## Implementation Pipeline

The production exporter has one typed, PIVOT-owned path:

1. `exporter.py` loads one compiler catalog snapshot and machine profiles.
2. `planner.py` asks compiler selectors and lowerers for concrete backend slots;
   `profiles.py` chooses the deterministic contributing profile cover.
3. `lowering_capture.py` replaces only the `call`, inferred `var`, and final
   `complete` TSIL handlers. It retains binding identities, typed dependencies,
   resolved attributes, arguments, source spans, and unsafe facts.
4. `body_builder.py` converts the captured compiler render stream into an
   immutable `PivotBody`. A per-lowering, collision-checked reserved token is
   decoded immediately to its typed capture node wherever an eager compiler
   render value made a token necessary. Foreign, repeated, malformed, lost, or
   unconsumed tokens fail closed; tests prove that no token reaches YAML.
5. `target_expression.py` parses the bounded residual C++ or Rust expression
   subset. Binding references carry `PivotBindingId` values; qualified paths,
   members, callable names, raw identifiers, literals, trivia, and delimiter
   groups remain distinct nodes.
6. `inliner.py` recursively composes typed calls from compiler-selected
   dependencies, allocates locals and call results deterministically, detects
   cycles and arity failures, and renders one flattened instruction list.
7. `documents.py` owns schema conflicts, exact definition deduplication,
   collision occurrences, skip ordering, and body-census association;
   `render_yaml.py` only formats those decided documents.

Argument parentheses and Rust return-group normalization are renderer rules
over parsed nodes. There is no statement regex splitter, context-blind
identifier replacement, marker-parenthesis scanner, or raw-text alpha-renamer.
Compiler backend syntax remains the sole spelling owner for synthetic
fixed-vector calls.

The canonical corpus emits 186 documents and 16,620 definition occurrences,
including 4,730 multi-statement definitions and 328 nominal-identity collision
groups. `tests/baselines/full_export.json` ratchets every definition occurrence,
`direct` hash, artifact, and exact skip fact. `tests/baselines/body_census.json`
associates a successfully constructed typed body with every emitted occurrence;
it records zero construction failures. The ordered artifact digest is
`78ede4c2f285414fefa5da989d135e6b24ea6609f29d2ce5a082926efcb5ccf6`.

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

The body census is architectural evidence rather than part of the external
YAML schema. Any reviewed change to lowering capture, body construction,
parsing, or inlining must update its digest without weakening the full-export
definition and artifact ratchets.

Regenerate both committed authorities only through their guarded
maintenance tool:

```bash
python tools/pivot/scripts/update_full_export_baseline.py
```

The production ratchet accepts added entries but refuses removed entries,
reduced multiplicity, or replaced `direct` hashes. Because an addition also
changes the complete body census, the combined command still requires explicit
review for that evidence change. Use
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
