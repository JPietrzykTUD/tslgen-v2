# Post-Commit Design Health Repair Plan

## Status and authority

Status: planned, not implemented.

This plan addresses the findings from the design review of commit
`2e3e187c19e2fec20fb1522d7556abe703e74bd2`. It is governed by the repository
and compiler charters, `PLANS.md`, the scoped compiler/source/editor/PIVOT
instructions, and the current typed source and tests. The review established
that the overall compiler and Rust-facade architecture remains healthy; these
are focused corrections, not permission to redesign the Rust API or recreate
TSL semantics in a facade, verifier, editor, CI script, or downstream tool.

Implement one numbered slice per commit, in order. Do not combine the semantic
dependency correction with CI, benchmark-policy, or baseline-maintenance work.

## Goal and completion criteria

The repair is complete when:

1. the generated Rust policy producer/consumer contract is exercised by its
   comprehensive fail-closed test in CI;
2. a free SIMD type parameter remains symbolic in dependency facts and can
   never acquire a fabricated extension;
3. Rust verification retains profiles that do not depend on a failed
   host-target query;
4. CI tests both exhaustive per-profile Rust generation and at least one real
   multi-profile Rust package;
5. an additive PIVOT definition cannot hide a change to any stable product
   fact;
6. architecture documentation describes the live Rust benchmark cfg contract;
7. no fix adds domain knowledge to the Rust facade, editor client, CI scripts,
   or PIVOT;
8. full compiler, PIVOT, editor, and focused generated gates pass.

## Fixed ownership and scope

- `tsldata` continues to own primitive contracts and generic-parameter
  semantics. No source-data change is expected for these findings.
- `tslc.lower.dependencies` owns typed call identities. The pipeline owns
  dependency scheduling, exact closure, pruning, and transitive fact
  propagation.
- Rust benchmark assets and benchmark planning own the private cfg/codegen
  contract. Tests and CI consume that contract; they do not redefine it.
- Rust verification owns toolchain probing and per-profile admission.
- GitHub matrix code owns CI grouping only. It must not infer compiler
  selection or target compatibility.
- PIVOT remains a lockstep, one-way downstream consumer. It must adapt to
  compiler-owned dependency facts or fail closed; it may not repair them.
- The Python authoring server owns TSL vocabulary and semantic projections.
  The TypeScript editor remains transport and presentation only.

Out of scope:

- changing the settled Rust facade API;
- changing `convert_lanes` to require the same extension;
- adding Rust- or CI-specific metadata to `tsldata`;
- reintroducing Cargo profile or `variant_benchmarks` features;
- parsing target text to recover a generic vector identity;
- weakening policy equality, PIVOT baselines, or compiler diagnostics;
- a general verifier, dependency-graph, CI-matrix, or editor framework.

## Editor audit: `operand_roles` is already implemented

No editor implementation slice is required.

Current source recognizes and projects `operand_roles` through every relevant
compiler-owned layer:

- parsing and typed syntax in `tslc/src/tslc/syntax/parser.py` and
  `tslc/src/tslc/syntax/ast.py`;
- primitive schema and semantic validation in
  `tslc/src/tslc/catalog/validation/_schema_primitives.py` and
  `tslc/src/tslc/catalog/semantic_promotion.py`;
- completion in `tslc/src/tslc/authoring_completion.py`;
- hover, navigation, and references in `tslc/src/tslc/catalog_index.py`;
- semantic tokens in `tslc/src/tslc/catalog_authoring_index.py`;
- the editor-neutral LSP adapter in `tslc/src/tslc/lsp/`.

The TextMate grammar also needs no `operand_roles` keyword entry: outer TSL
fields use one generic field matcher. Only registered TSIL region keywords are
generated into the grammar.

The installed `tsl-project.tsl-language-support@0.1.1` is a contributor
package without a bundled Python server. Its TSL output shows that it starts
`/opt/venv/bin/tslc`, and that executable is an editable install of this
workspace. The installed client/grammar and repository client/grammar match.
Focused authoring/LSP tests, grammar freshness, and the current corpus check
pass.

Operational recovery:

1. Save the document and confirm its language mode is **TSL**.
2. Run **TSL: Restart Language Server**. A window reload is an equivalent,
   broader restart.
3. Check the **TSL** output channel and confirm the server path is
   `/opt/venv/bin/tslc` or the intended bundled runtime.
4. If the diagnostic remains, compare its exact code/source with
   `tslc check <path>`. A fresh current server reporting a role error usually
   means the field placement, role name, or parameter binding is invalid, not
   that `operand_roles` is unknown.
5. If an older same-version VSIX or bundled runtime is actually active, run
   `./dev.sh editor-install` and then reload. The installer uninstalls the
   existing same-version package before replacing it.

If a minimal valid `operand_roles` document still produces
`TSL-CATALOG-UNKNOWN-FIELD` after that procedure, stop and open a separate
authoring slice using `extend-tslc-authoring`; do not add a TypeScript keyword
table. A future published bundled build should also receive a version bump so
two semantically different runtimes are not distributed as `0.1.1`.

## Execution order

### Slice 1 — restore Rust policy-consumption evidence and documentation

**Outcome:** the live private cfg contract is tested end to end and the
architecture description agrees with generated Cargo behavior.

Expected files:

- `tslc/tests/test_rust_policy_consumption.py`;
- `.github/workflows/generated-build.yml`;
- `tslc/DESCRIPTION.md`;
- `tslc/src/tslc/backend/assets/tsl_benchmark_self_test.rs`, only if its
  synthetic feature record is stale.

Work:

1. Remove every obsolete `--features variant_benchmarks` argument from the
   policy-consumption test.
2. Use the existing compiler-owned policy environment/codegen helper to supply
   `--cfg tsl_variant_benchmarks`; do not duplicate its flag spelling.
3. Replace the obsolete `variant_benchmarks,value_tests` mismatch probe with a
   real additional public feature, preferably `std`.
4. Delete or invert the expectation that an internal profile feature must be
   present. Absence of profile Cargo features is now the valid contract.
5. Rename the old feature-build case to describe cfg/codegen activation and
   prove it succeeds without the removed feature.
6. Keep the ordinary no-policy/no-cfg probe: it must retain the authored
   fallback.
7. Add
   `test_generated_rust_policy_is_applied_fail_closed_and_invalidated` to the
   generated-benchmark CI loop as its own pytest process.
8. Update `tslc/DESCRIPTION.md` to say that the hot loop and policy build use
   the unpublished `tsl_variant_benchmarks` cfg plus the exact compiler-owned
   codegen contract. Remove references to benchmark/profile Cargo features.

Acceptance:

- the comprehensive generated test reaches every valid, stale, malformed,
  foreign, feature-mismatched, CPU-mismatched, and context-mismatched case;
- invalid policy input fails before consumer code is compiled;
- a valid policy changes the selected implementation;
- generated `Cargo.toml` still exposes no `variant_benchmarks` feature;
- documentation agrees with `docs/variant-benchmarking.md`, `rust_build.rs`,
  `rust_lib.rs.tmpl`, and generated Cargo metadata.

Guardrails:

- do not reintroduce a Cargo feature;
- do not weaken exact compiler, target, CPU, context, feature-set, wrapper, or
  codegen comparisons;
- keep activation detection in the generated build-script asset, not Python
  rendering or CI.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_rust_policy_consumption.py \
  tslc/tests/test_rust_benchmark_rendering.py

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_rust_policy_consumption.py::test_generated_rust_policy_is_applied_fail_closed_and_invalidated

rg -n 'variant_benchmarks.*feature|profile features' tslc/DESCRIPTION.md
git diff --check
```

### Slice 2 — make PIVOT baseline additions fail closed

**Outcome:** legitimate coverage growth cannot mask unrelated output,
diagnostic, collision, or semantic-skip changes. This guard must land before
the generic-dependency correction can affect PIVOT evidence.

Expected files:

- `tools/pivot/src/tslc_pivot/baseline.py`;
- `tools/pivot/tests/test_baseline_update.py`.

Work:

1. Preserve the exact definition-inventory removal/replacement check.
2. Remove the early return when `candidate_inventory - previous_inventory` is
   nonempty.
3. Always compare every `_STABLE_PRODUCT_FACT_FIELDS` entry.
4. Continue to allow pure additive definition growth and location-only
   refreshes when stable product facts are unchanged.
5. Keep `allow_reviewed_incompatible_baseline=True` as the only escape hatch
   for a reviewed stable-product incompatibility.
6. Add a parameterized regression: retain the previous definition, add one
   definition, and independently change `skip_semantic_inventory_sha256`,
   artifacts, and diagnostics. Each case must be rejected and name the changed
   field.
7. Extend the override test to prove that the same combined change succeeds
   only with the explicit override.

Acceptance:

- additions cannot suppress a stable-product mismatch;
- pure additions remain accepted;
- removals, reduced multiplicity, and replaced direct hashes remain rejected;
- current committed manifests regenerate without a diff;
- manifest schema and compiler/PIVOT dependency direction do not change.

The existing PIVOT charter, scoped instructions, and README already require
fail-closed updates and explicit review. Do not duplicate that policy in more
documentation. During implementation, first run an incompatible refresh
without the override and record exact identity/hash/skip/body deltas before any
reviewed override is used.

Validation:

```bash
PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q \
  tools/pivot/tests/test_baseline_update.py \
  tools/pivot/tests/test_full_export_baseline.py

python tools/pivot/scripts/update_full_export_baseline.py
git diff --exit-code -- tools/pivot/tests/baselines
git diff --check
```

### Slice 3 — represent generic SIMD call dependencies symbolically

**Outcome:** `ToVec` and any renamed SIMD type parameter retain their real
identity and optional base binding without inheriting the caller's extension.

Expected compiler files:

- `tslc/src/tslc/lower/dependencies.py`;
- `tslc/src/tslc/lower/region_handlers/calls.py`;
- `tslc/src/tslc/pipeline.py`;
- `tslc/src/tslc/_pipeline_closure.py`;
- `tslc/src/tslc/concrete_analysis.py`;
- `tslc/src/tslc/maintenance/explain.py`;
- focused lowering, closure, analysis, and safety tests.

Data model:

1. Add one frozen typed reference such as
   `GenericVectorReference(parameter_name, base_tag)`.
2. Let a call's source/target reference be either the existing concrete
   `VectorIdentity` or this symbolic reference.
3. A specialized base binding such as `f64` is retained, but
   `extension_isa` does not exist on the symbolic type. An unbound base remains
   explicitly unknown.
4. Keep concrete slot keys concrete. A symbolic reference must never enter an
   exact `_SlotKey`.

Compiler behavior:

1. `resolve_lowered_call_vector()` returns the symbolic reference whenever the
   expression is a declared SIMD type parameter. It must not borrow the current
   or relative extension.
2. Call rendering continues to spell the authored type parameter. Rendering
   and dependency identity remain separate.
3. Worklist discovery treats concrete dependencies exactly as today. A
   symbolic dependency with a known base requests the callee/base across the
   applicable profile/request representation scope rather than selecting one
   extension. An unknown base remains a symbolic trait-constrained call.
4. Exact availability, pruning, safety propagation, feature propagation, and
   implementation-state propagation apply only to concrete dependency edges.
5. A symbolic edge is structurally valid only when the referenced
   `LoweredTypeParam` exists and its compiler-derived bounds include the
   callee. Missing parameter/bound facts fail closed with a deterministic
   diagnostic; they do not fall back to the caller vector.
6. Sorting, labels, concrete analysis, and explain output handle both reference
   variants. Use a stable explicit label such as
   `to_array<ToVec[base=f64]>`; never print a fabricated ISA.
7. Preserve the existing shared parsed-call path and `_type_param_bounds`
   ownership. Do not create a second call parser or a Rust-specific dependency
   classifier.

Tests:

- replace the current `f64,avx2` expectation in
  `test_lower_generic_paths.py` with the symbolic `ToVec` fact;
- use a renamed parameter such as `Dst` to prove there is no name special case;
- prove known base binding is retained and extension is absent;
- prove a valid symbolic bound does not exact-match or prune against an
  arbitrary AVX2 slot;
- prove a missing symbolic bound fails closed;
- retain concrete-edge pruning and transitive safety/feature/state regressions;
- prove profile worklist discovery keeps the necessary callee family without
  constraining the symbolic target extension;
- prove analysis/explain output is deterministic and visibly symbolic;
- build C++ and Rust for an AVX2 source converted to an equal-lane generic
  target representation.

Downstream compatibility gate:

PIVOT directly consumes compiler call identities. Audit and adapt
`tools/pivot/src/tslc_pivot/lowering_capture.py`, `planner.py`, and
`body_ir.py` plus boundary/body tests in the same lockstep compatibility
portion of this slice.

- PIVOT may resolve a symbolic vector only if its own typed export context
  supplies the complete concrete vector identity.
- It must never substitute the caller's/current extension.
- If the PIVOT schema/context cannot represent that choice, emit a structured
  PIVOT-owned unsupported skip before call inlining.
- Run the guarded baseline update without an override. If sound fail-closed
  behavior removes existing definitions or changes semantic bodies, stop for
  explicit product/correctness review before accepting the baseline delta.
  Aggregate coverage growth elsewhere is not sufficient.

Guardrails:

- do not constrain `convert_lanes` to the same extension in `tsldata`;
- do not infer an extension from parameter names, target spelling, backend
  output, or implementation text;
- do not union concrete ISA features into a generic caller;
- do not preserve PIVOT coverage by retaining the fabricated identity.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_lower_generic_paths.py \
  tslc/tests/test_masks_and_calls.py \
  tslc/tests/test_safety_contract.py \
  tslc/tests/test_concrete_analysis.py

PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q tools/pivot/tests

./dev.sh build --primitives convert_lanes,to_array,set_zero,from_array \
  --profiles scalar,avx2 --backends cpp,rust

python -m compileall -q tslc/src/tslc tools/pivot/src/tslc_pivot
(cd tslc && python -m mypy)
(cd tools/pivot && python -m mypy)
```

### Slice 4 — isolate Rust host-target discovery failures

**Outcome:** a failed or malformed `rustc -vV` result removes only profiles
that require discovered host-target spelling.

Expected files:

- `tslc/src/tslc/output/_verify_rust.py`;
- `tslc/tests/test_build_verify_config.py`.

Work:

1. Partition profiles into those that require host discovery and those that
   are independent because they are scalar/featureless or already have an
   explicit target.
2. Query `rustc -vV` once when the dependent partition is nonempty.
3. On query failure, retain the independent partition and add deterministic
   skip evidence naming the dependent profiles.
4. On malformed successful output, emit
   `TSL-BUILD-VERIFY-RUST-HOST-TARGET`, retain the independent partition, and
   omit dependent commands.
5. On success, continue converting dependent profiles to explicit
   `--target <host>` builds with target-specific Cargo Rust flags.
6. Preserve the injected `BuildCommandRunner` path and existing per-target
   preflight isolation.

Acceptance:

- mixed scalar plus AVX2 verification still executes scalar when host discovery
  fails or is malformed;
- AVX2 is explicitly skipped and no AVX2 Cargo command is planned in those
  cases;
- an explicit caller-supplied target bypasses host discovery;
- successful discovery uses `CARGO_TARGET_<HOST>_RUSTFLAGS`, explicit
  `--target`, and the current build/test mode;
- SDE value tests still compile for the discovered host and run through SDE.

Guardrails:

- do not infer host triples from `platform`, CPU features, or CI environment;
- do not restore global `RUSTFLAGS` for target features;
- do not add a wrapper model when a direct local partition is sufficient.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
git diff --check
```

### Slice 5 — add explicit multi-profile Rust CI evidence

**Outcome:** singleton shards continue proving every profile independently,
while one additional lane proves that compatible Rust profiles coexist in one
distributed crate.

Expected files:

- `.github/scripts/profile_shards.jq`;
- `tslc/tests/test_ci_profile_shards.py`;
- generated build/value workflow files only if an additional matrix field is
  required.

Work:

1. Preserve all current singleton Rust shards and existing C++ chunking.
2. Append one explicitly named Rust coexistence shard containing the already
   validated set `sse,sse2,sse3,avx,avx2,knl`.
3. If needed, mark the entry as a CI-purpose `coexistence` lane so matrix tests
   can distinguish intentional duplicate profile coverage from exhaustive
   shards.
4. Let both generated-build and generated-value workflows consume it unless CI
   runtime evidence shows the value lane is prohibitively expensive. Any
   build-only exception must be explicit in the workflow, not inferred in jq.
5. Update the matrix test to prove:
   - exhaustive shards still contain every profile exactly once per backend;
   - only the named coexistence lane intentionally repeats profiles;
   - its exact ordered set is stable;
   - OneAPI-gated groups remain isolated;
   - C++ chunking remains unchanged.

Guardrails:

- the profile list is a curated CI smoke contract, not compiler semantics;
- do not derive target compatibility in jq;
- do not add CI grouping metadata to `tsldata` or machine profiles;
- do not replace exhaustive singleton coverage with only aggregate chunks.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_ci_profile_shards.py

./dev.sh build --primitives add --backends rust \
  --profiles sse,sse2,sse3,avx,avx2,knl

./dev.sh test --primitives add --backends rust \
  --profiles sse,sse2,sse3,avx,avx2,knl

git diff --check
```

## Final validation and post-review

After all slices:

```bash
python -m compileall -q tslc/src/tslc tools/pivot/src/tslc_pivot
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)

PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q tools/pivot/tests
(cd tools/pivot && python -m mypy)

PYTHONPATH=tslc/src python -m tslc check
(cd editors/vscode-tsl && npm test)

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_rust_policy_consumption.py::test_generated_rust_policy_is_applied_fail_closed_and_invalidated

git diff --check
```

Run the `design-review` playbook again after focused validation. The review
must confirm:

- no symbolic vector was collapsed into a concrete extension;
- no Rust/API/CI/editor/PIVOT name classifier was introduced;
- exact concrete dependency pruning and propagation remain unchanged;
- generated Rust benchmark policy remains fail closed;
- PIVOT baseline changes, if any, were reviewed by exact identity and semantic
  digest rather than aggregate counts;
- commits and baseline refreshes remain coherent with the numbered slices.
