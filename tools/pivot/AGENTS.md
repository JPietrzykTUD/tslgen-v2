# PIVOT Downstream-Tool Instructions

## Scope

These instructions apply to `tools/pivot/`. The root `AGENTS.md`, `CHARTER.md`,
and `PLANS.md` also apply. Read this directory's `CHARTER.md` and use the
repository `design-review` skill before design and after focused validation.
The approved extraction and rework are recorded in
[`todo/pivot-export-rework-plan.md`](../../todo/pivot-export-rework-plan.md).

## Product And Package Boundary

- The distribution is `tslc-pivot`, the Python package is `tslc_pivot`, and the
  executable is `tslc-pivot`.
- PIVOT is independently packaged downstream tooling. It is not a `tslc`
  backend, compiler stage, subcommand, plugin, or semantic projection.
- Dependencies point from `tslc_pivot` to `tslc`, never in reverse. Do not add
  a compatibility shim, dynamic plugin framework, or PIVOT registration to the
  compiler.
- Public compiler APIs are preferred. Direct imports of typed compiler classes
  are acceptable while the package is deliberately lockstep with the repository
  compiler revision. Inventory private imports in one compatibility-focused
  module or test; do not wrap every compiler type merely to hide imports.
- Instantiate and configure compiler services locally. Do not monkey-patch
  classes, mutate registries or defaults, or create import-time side effects.
- PIVOT work does not authorize `tslc/` or `tsldata/` changes. An explicitly
  approved extraction may remove existing reverse awareness from core;
  otherwise stop and propose a separate projection-neutral compiler or
  source-data slice.

## Fact Ownership

Reuse compiler-owned source discovery and validation, catalogs, machine
profiles, implementation selection, call dependency identity, capabilities,
intrinsic and signature-type projection, fixed-vector spellings, TSIL scanning,
and ordinary lowering. Do not reproduce those policies in this package.

PIVOT owns only its export-specific profile cover, admitted straight-line
subset, residual target-text interpretation, binding and temporary identities,
recursive flattening, cycle reporting, YAML schema and paths, skips,
diagnostics, and coverage baseline.

## Target-Text And Dataflow Rules

- The output is a completely flattened, deterministic list of plain C++ or Rust
  instructions. Runtime branches and loops remain unsupported.
- Keep PIVOT semantics in immutable typed values once target text has been
  parsed. Binding references and locals must be identities, not names inferred
  later by global text replacement.
- Parse only the bounded residual syntax required by the supported corpus.
  Reject unknown, ambiguous, or malformed syntax with a structured,
  source-located skip where practical.
- Regex may recognize one token or reject one local form. Do not use it for
  statement splitting, context-blind identifier substitution, parenthesis
  surgery, alpha-renaming, or source repair.
- Distinguish binding references from qualified names, members, literals,
  comments, callable names, Rust paths, and delimiter groups. Preserve
  deterministic evaluation and instruction order during recursive inlining.
- PIVOT interpretations never become compiler facts and never feed back into
  source validation, normal lowering, generated projects, tests, or benchmarks.

## Coverage And Diagnostics

- Treat the durable full-corpus manifest as the non-regression authority.
  Ratchet the exact multiset of nominal definition identities and `direct`
  hashes, not aggregate counts alone. Nominal identities can collide in the
  current schema, so preserve their multiplicity and collision census.
- Coverage may grow. Do not remove a baseline entry, reduce its multiplicity,
  or refresh a changed hash without a focused reproduction and an explicitly
  reviewed product or correctness decision.
- Keep skips and diagnostics structured, actionable, source-located where
  practical, stably ordered, and clearly identified as PIVOT-owned.
- Never preserve coverage by emitting a guessed or silently corrupted mapping.
- Treat `tests/baselines/body_census.json` as the typed-body authority. Every
  emitted definition occurrence must have a constructed body, including fixed
  wrappers and nominal collisions; hidden failures, malformed or lost capture
  acceptance, or an unexplained semantic digest change blocks the slice.
- Keep `tests/baselines/full_export.json` authoritative for production parser
  and inliner output. Definition occurrence, order, artifact, semantic skip,
  or `direct`-hash changes require explicit review under the charter. Exact
  source spans remain deterministic location evidence, but location-only
  movement does not constitute a semantic incompatibility.

## Validation

Run tool checks independently from core compiler checks:

```bash
python -m compileall -q tools/pivot/src/tslc_pivot
PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q tools/pivot/tests
(cd tools/pivot && python -m mypy)
```

The tool suite must cover package/CLI isolation, compiler-registry and default
immutability, exact compiler-version compatibility, fresh lowering state,
calls, locals, final results, alternative variants, unsafe framing, reserved-
token corruption, parser edge cases, fail-closed rejection, recursive inlining,
exact body-entry association, YAML schema/goldens, full-export entry-multiset
and hash ratchets, span-free body-census semantic digest, normalized
body-location digest, and cross-`PYTHONHASHSEED` determinism.
Validate ordinary generation remains unchanged from outside the compiler
package.

Regenerate the durable production and typed-body manifests
only through `python tools/pivot/scripts/update_full_export_baseline.py`. The
updater must remain fail-closed for removed entries, reduced multiplicity,
replaced `direct` hashes, semantic skip changes, and body-semantic changes.
Corpus provenance and source-location evidence may refresh without the
incompatible-baseline override when those semantic ratchets are unchanged.

For packaging and command checks:

```bash
python -m pip install --no-deps -e ./tslc
python -m pip install --no-deps -e ./tools/pivot
tslc --help
tslc-pivot --help
git diff --check
```

Keep generated exports, manifests under construction, and test scratch below
`./tslctmp/pivot-rework/`.

## Stop Conditions

Stop and request a separate decision when preserving coverage appears to
require a `tsldata` workaround or compiler semantic change; a proposed compiler
API exists only for PIVOT; CLI compatibility would restore core awareness; an
output difference cannot be classified; or a new parser/runtime dependency
introduces unreviewed packaging, licensing, native-build, or Python-version
constraints.
