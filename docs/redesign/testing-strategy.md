# Testing Strategy

Testing must prove behavior, boundaries, and determinism. The goal is not to preserve legacy internals. It is to preserve required observable behavior and make future changes safe.

## Test Principles

- Test pure logic without filesystem, hardware, shell, or template side effects.
- Use repository-grounded fixtures from `tsldata/` where useful.
- Use small synthetic fixtures for invalid cases.
- Prefer structured assertions over string matching except for golden output and diagnostics text.
- Golden files should cover stable generated artifacts, not every intermediate detail.
- Hardware detection must be mocked or injected.
- Determinism tests should run the same stage twice and compare results.

## Recommended Test Layout

```text
tslgen/
  tests/
    fixtures/
      tsl/
        valid/
        invalid/
      manifests/
      golden/
        cpp/
        rust/
        diagnostics/
    unit/
      test_diagnostics.py
      test_source_loading.py
      test_tsl_parser.py
      test_catalog_builder.py
      test_signature_rules.py
      test_reference_validation.py
      test_selection.py
      test_dependencies.py
      test_artifacts.py
      test_artifact_writer.py
      test_testgen_planning.py
      test_lowering.py
      test_reporting.py
    integration/
      test_pipeline_catalog.py
      test_pipeline_cpp_slice.py
      test_artifact_writer_pipeline.py
      test_cli.py
      test_validation_baseline.py
    regression/
      test_tsldata_parse.py
      test_signature_resolution_legacy_observed.py
      test_extension_selection_legacy_observed.py
```

Existing `tslgen/tests` can be reshaped as milestones land.

## Unit Tests

Unit tests should cover:

- Diagnostics and result types.
- Frozen map/value behavior.
- Source path resolution and loading.
- TSL grammar examples.
- Catalog object construction.
- Signature parsing and normalization.
- Attribute validation.
- Template required-field validation.
- Type group and lane set expansion.
- Extension inheritance and backend support.
- Feature requirement normalization.
- Selection candidate ordering.
- Artifact writer behavior.
- Production test-source declaration normalization and planning.
- Lowering request/result construction and unsupported-payload diagnostics.
- Report rendering without filesystem side effects.

Unit tests should not:

- Depend on host CPU flags.
- Invoke compilers.
- Write outside temporary directories.
- Read from `frozen/` except explicit regression fixtures if copied or referenced read-only.

## Parser Tests

Parser tests must include:

- `prim<v:=(v,v)> add(left, right):`
- Attribute lists such as `[mask=zero]`, `[aligned=*]`, and `[aligned=*, packed=*]`.
- Inline maps such as `{types [si8, ui8]}`.
- Multiline maps and lists.
- Multiline TSIL strings.
- Key lists such as `[generic, oneAPIfpga, oneAPIfpgaRTL]`.
- Parameterized keys or attributes such as `arg_count(values)=return_vector_length`.
- Comments with `#` and `//`.
- Invalid indentation and malformed string diagnostics.

Regression parser test:

- Parse every `.tsl` file under `tsldata/` and assert no errors.

## Catalog Tests

Catalog tests should assert:

- Type groups from `tsldata/detail/types.tsl`.
- Lane sets from `tsldata/detail/lane_sets.tsl`.
- Flag aliases from `tsldata/detail/flags.tsl`.
- Extension metadata from `tsldata/extensions/extension.tsl`.
- Template metadata from `tsldata/detail/templates.tsl`.
- Representative primitive declarations from `tsldata/primitives/arithmetic/fundamental.tsl`.

Tests should verify typed fields and preserved extra fields separately.

## Validation Tests

Validation fixtures should include:

- Unknown extension in implementation block.
- Unknown type group in implementation category.
- Unknown lane set in test.
- Unknown test type and `to_type`.
- Invalid `mask`.
- Invalid `aligned` and `packed`.
- Invalid `op` for masked load/store shapes.
- Missing required template field such as `aligned` for `load`.
- Extension inheritance unknown parent, self-parent, and cycle.
- Duplicate definitions where the new model forbids them.

Diagnostics tests should assert:

- Stable code.
- Severity.
- Path.
- Line and column when source exists.
- Message contains the invalid value and expected alternatives.

## Property-Style Tests

Property-style tests are useful for:

- Signature normalization idempotence.
- Flag normalization idempotence.
- Frozen value thaw/freeze round trips.
- Wildcard expansion count for `n` boolean wildcards.
- Deterministic ordering independent of input map order.
- Artifact writer digest stability.

These can be written with Hypothesis if adopted, or as small generated test loops if dependencies should remain minimal.

## Golden-File Tests

Golden tests should start small:

- One simple C++ primitive artifact, such as a binary operation for scalar or
  generic, after Milestone 22 expands beyond summary artifacts.
- One masked primitive artifact once mask semantics are implemented.
- One load/store artifact with `aligned` wildcard expansion.
- One production test source artifact after Milestone 17 establishes test-source
  planning and a rendering slice exists.
- One diagnostic report snapshot for a representative invalid fixture.

Golden update policy:

- Only update golden files when the behavior change is intentional.
- Mention the design decision or requirement update in the change.
- Keep golden inputs small enough that diffs are readable.

Golden harness helpers should:

- Compare rendered artifacts by logical path.
- Use exact content comparison unless a specific normalization policy is
  documented for that fixture.
- Assert deterministic artifact digest maps when a render path is expected to
  be stable.
- Stay in test infrastructure; production renderers must not depend on golden
  test helpers.

## Artifact Writer Tests

Milestone 16 introduces the first accepted filesystem mutation boundary. Tests
for that milestone must use temporary directories and assert:

- Absolute artifact paths, parent traversal, duplicate paths, and paths outside
  the output root are rejected before writing.
- First writes create parent directories and produce deterministic `written`
  records.
- Repeated writes with identical content produce `skipped_unchanged` records
  when skip-unchanged is enabled.
- Changed content rewrites the file and updates the digest.
- Dry-run reports match the planned mutation statuses without touching files.
- Write reports sort paths and diagnostics deterministically.

No renderer test should need to touch the real filesystem. Rendering tests
should produce `ArtifactSet` values; writer tests should consume them.

## Production Test-Source Planning Tests

Milestone 17 tests should distinguish generated production tests from tests of
the generator itself. They should assert:

- TSL `tests` declarations normalize into typed declaration objects.
- Plans filter by primitive, type, extension, backend, and selected candidate.
- Unsupported declaration shapes produce diagnostics rather than being ignored.
- Planned test artifact descriptors have stable logical paths and metadata.
- The golden harness can snapshot plans without becoming a production planning
  dependency.

Compiler invocation, runtime execution, hardware autodetection, and broad
generated test framework behavior remain out of scope until explicitly
milestoned.

## Lowering Tests

Milestone 18 tests should prove the boundary before proving full TSIL semantics.
They should assert:

- Lowering requests are built from selected implementation candidates and typed
  context, not raw catalog dictionaries.
- Unsupported or deferred payloads return diagnostics with stable codes and
  source context when available.
- If a minimal TSIL subset is parsed, unsupported constructs fail explicitly.
- Generation-time conditions such as `if<generation>(...)` are represented and,
  if implemented, evaluated in lowering rather than rendering.
- Lowering results are deterministic for identical candidate input.

Dependency and backend tests may consume lowered outputs only for the supported
slice. They must not rescan raw implementation payloads to bypass lowering.

## Validation Baseline Tests

Milestone 21 should make the broad check surface explicit. If a validation
script or command is added, tests should assert:

- The documented command succeeds in the dev container for the production
  package and accepted tests.
- Exploratory or quarantined modules are not imported by public API, CLI, or
  accepted pipeline tests.
- Validation does not require network access, host CPU features, compiler
  availability, or generated-output churn.
- Failures distinguish production regressions from intentionally unsupported
  sketches.

## Integration Tests

Integration tests should cover:

- Source loading to parsed documents.
- Parsed documents to catalog.
- Catalog validation over selected `tsldata/` files.
- Selection request to candidate set.
- Candidate set to minimal backend artifact.
- Rendered artifact set to write report using a temporary output root.
- Test-source planning from selected catalog/test declarations.
- CLI with explicit flags and temp output.

Integration tests should use temporary directories for writes and explicit CPU flags.

## Regression Tests Against Legacy-Observed Behavior

Regression tests should map observed behavior to new requirements, not old modules.

Examples:

- Signature `v:=(v,v)` resolves to `binary`, evidenced by `frozen/generator_specs/signatures.yaml`.
- Extension `avx2_vl` inherits/falls back to `avx2`, evidenced by `tsldata/extensions/extension.tsl`.
- `avx3f` normalizes to `avx512f`, evidenced by `tsldata/detail/flags.tsl`.
- `load` requires `aligned`, evidenced by `tsldata/detail/templates.tsl`.
- `aligned=*` expands to true and false variants, evidenced by `tsldata/primitives/load_store/load.tsl`.

Avoid tests that assert legacy function names or exception types.

## Deterministic Output Tests

Determinism tests should assert:

- Same input paths in different order produce the same catalog ordering where order is semantic or sorted.
- Same selection request produces identical candidate identities.
- Same backend plan renders identical artifact content.
- Same artifact set writes identical write reports and digest maps.
- Same production test-source request produces identical test artifact
  descriptors.
- Same lowering input produces identical lowered results or diagnostics.
- Parallel-enabled stages produce identical outputs with one worker and multiple workers.

## Test Fixtures

Use three fixture classes:

- Repository fixtures: read-only references to `tsldata/` for broad compatibility.
- Minimal valid fixtures: small files under `tests/fixtures/tsl/valid`.
- Minimal invalid fixtures: targeted files under `tests/fixtures/tsl/invalid`.

Fixture guidelines:

- Keep invalid fixtures focused on one error family unless testing accumulation.
- Include comments showing which requirement the fixture covers.
- Avoid copying large legacy outputs unless a golden test needs them.

## Toolchain Tests

Generated C++/Rust compile tests are valuable but should be optional or separately marked because they depend on compilers, target hardware, qemu, rustup targets, and flags.

Recommended markers:

- `unit`
- `integration`
- `golden`
- `toolchain`
- `slow`

Default CI should run unit, integration, and golden tests that are host-independent.

## Coverage Goals

Early milestones:

- High coverage for diagnostics, parsing, catalog construction, and validation.

Middle milestones:

- Branch coverage for selection, feature requirements, wildcard expansion, and extension fallback.

Backend milestones:

- Representative template coverage, not exhaustive template count.
- Golden coverage for stable generated artifacts.

Post-Milestone-15 milestones:

- Writer path-safety and skip-unchanged coverage before any CLI writes files.
- Generated test-source planning coverage before generated tests are rendered or
  executed.
- Lowering boundary diagnostics before broad TSIL parsing.
- Validation baseline coverage before claiming repository-wide checks.

## Review Expectations

Reviewers should check:

- Tests exercise new architecture, not legacy compatibility shims.
- Invalid inputs produce diagnostics rather than crashes.
- Deterministic tests exist for any new ordering-sensitive collection.
- Golden files are readable and intentionally scoped.
