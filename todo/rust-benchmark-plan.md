# Rust Variant Benchmarking And Autotuning Plan

## Status And Decision

This is the Rust follow-on to [`BENCHMARK_PLAN.md`](BENCHMARK_PLAN.md). It does
not reopen the implemented C++ measurement protocol or the authored
implementation-variant model.

The agreed direction is:

1. make the existing typed benchmark planner backend-aware;
2. add an opt-in, report-only Rust benchmark before changing Rust wrapper
   selection;
3. prove a stable-Rust, compile-time policy seam with a forced non-default
   candidate;
4. add backend- and build-context-bound Rust policy production and consumption;
5. expose autotuning first as an explicit two-phase Cargo workflow; and
6. expand scenario and corpus coverage only after the fixed-width pilot is
   trustworthy.

This intentionally supersedes only the ordering in the `Rust Integration` and
`Slice 6: Rust Policy Evaluation` sections of `BENCHMARK_PLAN.md`. That plan
required policy consumption before any Rust benchmark generation. A report-only
harness cannot alter wrapper selection, so it may land first and provide useful
measurement evidence even if Rust policy consumption later fails its design
gate. The existing constraints remain in force: normal builds do not execute
benchmarks, `build.rs` never runs a benchmark, and an absent policy retains the
authored default.

Current code and tests remain the source of truth where the older plan describes
historical state.

## Goal

Generated Rust projects should be able to compare explicitly authored
implementation variants using the same typed correctness and workload semantics
as C++, then optionally compile a backend-local winner into public Rust wrappers
without runtime dispatch.

The completed first version has three distinct modes:

| Mode | Observable result | Changes wrapper selection? |
|---|---|---:|
| report | Native optimized Rust candidates produce deterministic JSONL samples | no |
| policy consumption | A validated precomputed Rust policy selects candidate bodies at compile time | yes |
| two-phase autotune | An explicit report/reduce command is followed by a policy-enabled Cargo build | yes |

One-invocation Cargo autotuning is not required for completion.

## Ownership And Boundaries

This is a compiler-owned backend capability and projection. It belongs in
`tslc`, not in an independently packaged downstream tool.

| Fact or decision | Canonical owner | Rust benchmark use |
|---|---|---|
| Source workload hints | `catalog` typed `PrimitiveBenchmarkSpec` | Resolve ambiguous dependency operands and constrained input domains |
| Selected default and named bodies | `LoweredSpecialization` and `variant_bodies` | Enumerate only variants that coexist in the emitted Rust closure |
| Concrete profile and specialization availability | `EmittedProfile` | Plan profile-local candidates and native execution requirements |
| Authored correctness materialization | `ValueTestProjectPlan` | Derive benchmark correctness cases; never use the default as the oracle |
| Workload families, seeds, timing parameters, and candidate identity | `benchmark/model.py`, `benchmark/scenarios.py`, and the planner | Share semantics across backend renderers |
| Rust type, trait, call, unsafe, and target-feature spelling | Rust backend modules | Render direct calls to already-emitted candidate implementations |
| Cargo target layout and optional feature wiring | Rust project renderer/assets | Keep benchmark compilation and execution opt-in |
| Sample reduction and policy validity | Generated benchmark runtime and typed policy protocol | Default on inconclusive evidence and reject foreign context |
| Compile-time policy mapping | Rust backend policy planner and renderer | Select exactly one implementation per supported specialization |
| Coverage evidence | Benchmark maintenance report | Keep Rust gaps separate from C++ gaps |

The benchmark subsystem must not parse generated Rust, infer trait names from
body text, or re-lower a variant. If a Rust symbol or invocation fact is not
available through a backend-owned helper, expose that fact at the Rust backend
boundary rather than reproducing its naming rules in the benchmark renderer.

Templates format complete Rust benchmark and policy render values. They do not
decide eligibility, correctness, scenario semantics, target features, or the
selected specialization identity.

## Current Evidence

- `BackendCapability` already owns optional benchmark planner and renderer
  hooks, and the pipeline merges the plans from every requested backend.
- `SpecializationKey`, candidate sets, correctness cases, scenarios, profile
  plans, coverage entries, and project plans already carry backend-neutral
  typed facts and explicit backend IDs.
- `benchmark/correctness.py` and `benchmark/scenarios.py` do not contain C++
  rendering decisions.
- `CppBenchmarkPlanner` is structurally reusable but currently hard-codes the
  C++ backend ID, C++ profile spellings/flags, C++ header-group admission, and
  C++ coverage identities.
- Rust lowering already preserves named variants. `RustBackend` emits distinct
  hidden traits and impls for them, including their normal unsafe and
  target-feature framing.
- The public Rust wrapper still calls the authored default trait. There is no
  Rust equivalent of the C++ selector/policy include.
- Generated Rust projects already have Cargo-feature-selected profiles and
  executable value tests, but no benchmark target or policy input.
- The tracked benchmark audit and baseline are explicitly C++-only. Rust must
  not be folded into that baseline in a way that lets one backend mask the
  other's regressions.

The initial proof uses the existing fixed-width `mul` variant for `sse2/si8` on
x86-64. An AVX2 instance may be added to native developer validation when the
host supports it, but AVX2 availability is not an ordinary CI assumption.

## Non-Goals

- No changes to `.tsl` benchmark vocabulary in the initial Rust slices.
- No new TSIL regions and no parsing or rewriting of opaque Rust target text.
- No C++ policy reuse for Rust and no claim that raw C++ and Rust timings are
  comparable.
- No benchmark execution during `tslc generate`, ordinary `cargo build`,
  ordinary `cargo test`, or `build.rs`.
- No runtime candidate switch, function pointer, startup calibration, or
  assumption that a constant branch will optimize away.
- No public Rust API change solely to expose tuning.
- No nightly-only language feature, overlapping trait implementation, or
  mandatory third-party benchmarking crate.
- No benchmark-driven rewrite of authored defaults in `tsldata`.
- No consumed policy from QEMU, SDE, Wasm, another emulator, or a cross build.
- No timing-based pass/fail assertion in ordinary CI.
- No one-command Cargo autotune promise and no Cargo workspace split in the
  first implementation.
- No corpus-wide Rust parity claim before backend-scoped coverage evidence
  exists.

## Settled Design Constraints

### Shared Planning, Separate Rendering

There is one backend-parameterized benchmark planner. It consumes the same
typed catalog, emitted-profile, value-test, correctness, and scenario facts for
C++ and Rust. Backend admission contains only a named
`profile × scenario-family` pair. Profile family, features, backend spellings,
compile modes, flags, and manifest content come from the live typed machine
profile rather than a copied backend snapshot; the planner must not become a
strategy framework.

C++ and Rust retain separate candidate, correctness, scenario, runtime, policy,
and project renderers. Target-language source generation is not generalized
into string fragments shared across languages.

The C++ manifest payload and hashes must remain stable unless a separately
versioned protocol change is explicitly required. Backend parameterization must
not silently invalidate existing C++ policies.

### Report Harness Shape

The Rust benchmark is a custom, standard-library-only Cargo benchmark target
with its own `main`, enabled only by an explicit benchmark feature and concrete
profile feature. Ordinary library and test commands neither build nor run it.

The hot timing loop should live in a generated, doc-hidden, feature-gated module
inside the library crate. The thin Cargo benchmark target invokes a complete
batch rather than adding a cross-crate call around every primitive operation.
Candidate calls go directly through the already-emitted default and named
variant traits. Correctness runs before any candidate is timed.

The first renderer supports only the existing fixed-width pure-register
scenario family. Other already-modeled families remain explicit Rust benchmark
coverage gaps until added in later focused slices.

Timing uses optimized native code, deterministic seeds and inputs, warm-up,
calibration, paired/interleaved candidate order, the existing conservative
round rules, and an optimization barrier appropriate for Rust. A generated
short-run/self-test mode validates mechanics; production defaults remain long
enough for useful measurements.

### Backend-Local Policies

A Rust policy is valid only for the Rust candidate manifest and tune context
that produced it. Even when C++ and Rust have identical variant names, their
policies and stable identities are not interchangeable.

The Rust tune context must cover at least:

- benchmark protocol and policy schema versions;
- exact candidate keys, body hashes, scenarios, correctness cases, and required
  target features;
- selected generated profile and Cargo feature set;
- `rustc -Vv` identity, host and target triples, linker, and target CPU/features;
- Cargo profile, optimization level, LTO, codegen units, panic strategy, and
  incremental/debug settings that affect code generation;
- explicit `RUSTFLAGS`/encoded Rust flags and benchmark-only codegen flags;
- runtime CPU identity; and
- reducer threshold, rounds, and minimum sample duration.

If exact equivalence with arbitrary downstream private flags cannot be proven,
the policy remains documented as build-local. Missing context fails closed; it
does not trigger an implicit retune.

### Compile-Time Selection

The Rust backend owns a generated selection trait/module with one complete,
non-overlapping mapping for every policy-supported concrete specialization.
Normal builds use a complete default mapping. A policy-enabled build replaces
that mapping with another complete mapping; it never layers specific impls over
a generic default.

The public wrapper signature and safety stay unchanged. It delegates through
the selected mapping, and optimized code contains only the chosen candidate.
Named candidate traits remain doc-hidden implementation details.

The initial policy-supported family is deliberately narrower than report
coverage: one fixed-width, non-overloaded, non-masked, non-axis,
non-representation-changing, non-immediate register shape. Immediate values,
const-generic axes, overloads, SIMD type parameters, and other shapes remain
report-only until a focused selection slice proves them without overlap or
runtime branching.

An `OUT_DIR` materializer may be used to validate a pre-existing policy and
write the complete selected mapping. If used, `build.rs` may read configuration,
validate metadata, and write deterministic files under `OUT_DIR`; it must never
run timing code or execute a generated target binary. It must also declare exact
Cargo rerun inputs. Generated source directories are never mutated.

### Explicit Two-Phase Autotune

The first autotune workflow is intentionally non-cyclic:

```text
policy-free optimized cargo bench
  -> correctness + raw samples + conservative reduction
  -> Rust policy JSON
  -> separate policy-enabled cargo build
  -> consumer compiled with the selected mapping
```

The benchmark build is always policy-free. The second build never reruns the
benchmark. A later convenience command may orchestrate these phases only after
the explicit workflow is stable.

## Vertical Implementation Slices

### Slice 0: Backend-Parameterized Planning And Rust Plan Evidence

**Outcome:** a Rust generation request produces deterministic typed Rust
benchmark candidate plans and structured planning coverage, while rendered Rust
projects remain unchanged.

Changes:

- Replace `CppBenchmarkPlanner` with a literal backend-parameterized planner;
  do not copy the planner.
- Parameterize specialization/value-test lookup, `SpecializationKey.backend_id`,
  coverage identity, backend header/group admission, and profile manifest
  spellings/flags.
- Preserve the current C++ plan, manifest payload, stable IDs, and hashes for
  representative fixtures.
- Register Rust benchmark planning in `RUST_BACKEND`; retain the no-op Rust
  benchmark artifact renderer for this slice.
- Add owner-equivalence tests showing that shared scenario and correctness
  facts come from their existing typed owners.
- Add an additive fake-backend probe proving the planner does not branch on a
  registry-owned backend-name list.

Focused validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_pipeline_structure.py \
  tslc/tests/test_generation_snapshot.py \
  tslc/tests/test_benchmark_variants.py \
  tslc/tests/test_rust_benchmark_planning.py
(cd tslc && python -m mypy)
```

Exit criterion: `mul/sse2/si8` has a Rust candidate set with authored
correctness and the same scenario semantics as its C++ counterpart, while the
backend-specific key/body hashes remain distinct and C++ evidence is unchanged.

### Slice 1: Report-Only Rust Register Benchmark Pilot

**Outcome:** a generated Rust project can explicitly compile and run one
policy-free, fixed-width register benchmark and emit inspectable JSONL samples.

Changes:

- Add focused Rust candidate, correctness, register-scenario, and project
  renderers; keep them separate from the C++ renderers.
- Add a standard-library-only Rust benchmark runtime asset for deterministic
  input generation, timing, calibration, schedule, barriers, sample records,
  errors, and self-tests.
- Generate a feature-gated in-crate benchmark module and a thin custom Cargo
  benchmark target for each supported concrete profile.
- Render candidate invocations through Rust-backend-owned trait/type helpers;
  never reconstruct names by parsing rendered source.
- Run every authored correctness case for every candidate before timing. A
  correctness failure makes the report command fail and produces no policy.
- Refuse native execution when the selected profile is not supported by the
  executing CPU. Cross builds may compile the target, but do not run it.
- Keep ordinary Cargo defaults, library APIs, tests, and wrapper selection
  unchanged.

Focused validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_rust_benchmark_rendering.py \
  tslc/tests/test_benchmark_variants.py
```

Generated validation uses a workspace-local `tslctmp` project and performs:

- ordinary `cargo check` and `cargo test` without benchmark features;
- `cargo bench --no-run` for the `sse2` pilot;
- the generated benchmark-runtime self-test; and
- one short native report run with reduced rounds/sample duration, asserting
  schema and candidate coverage but never a particular winner or duration.

Exit criterion: repeated native runs produce valid samples for default and
named Rust candidates, normal builds do not execute the harness, and optimized
assembly confirms the inner loop is not dominated by an extra per-operation
cross-crate call or optimized away.

### Slice 2: Stable-Rust Compile-Time Selection Gate

**Outcome:** a generated downstream Rust consumer can be compiled once with the
default mapping and once with a forced non-default mapping, with unchanged
public calls and no runtime dispatch.

Changes:

- Add the smallest backend-owned selection trait/module for the pilot register
  shape.
- Add a frozen Rust policy-selection plan that records the exact candidate for
  each supported `SpecializationKey` and a structured report-only reason for
  each unsupported key. Do not overload benchmark-report coverage with policy
  eligibility.
- Generate complete default and forced-policy mappings with no overlapping
  impls.
- Route the existing public wrapper through the mapping without changing its
  signature, safety, implementation-state semantics, or candidate bodies.
- Keep every unsupported specialization on the authored default and record it
  as policy-unsupported rather than inventing selection behavior.
- Add an optimized assembly/IR probe for default and forced alternative builds.

Focused validation:

- compile a real consumer invoking the ordinary public wrapper;
- prove a forced `generic_fallback` mapping is the implementation reached;
- inspect optimized output for the pilot and prove there is no candidate branch,
  function-pointer dispatch, or retained call to the unselected implementation;
- verify unset policy state produces byte-stable default generated source and
  unchanged public signatures; and
- run Rust value tests for both mappings.

Exit criterion: stable Rust expresses exact selection for the pilot without
nightly features, overlap, runtime dispatch, source-tree mutation, or public API
change. If this criterion fails, stop policy/autotune work; report-only Rust
benchmarking remains a valid completed feature.

### Slice 3: Rust Reducer And Backend-Scoped Policy Production

**Outcome:** the policy-free Rust benchmark can conservatively reduce its own
samples into a Rust-only policy document, but generated libraries do not consume
it yet.

Changes:

- Implement the existing median paired-improvement, win-count, dispersion, and
  default-on-inconclusive contract in the generated Rust runtime.
- Emit raw JSONL, a human-readable summary, and typed Rust policy JSON for
  profiles with a consumable mapping. The summary keeps the observed result for
  report-only sets while the policy decision remains the authored default;
  all-report-only profiles reject policy output.
- Bind policy decisions to the Rust backend ID, manifest, profile, exact tune
  context, and CPU identity.
- Reject incomplete correctness, missing scenarios/candidates, duplicate
  decisions, stale manifests, and non-finite or malformed sample values.
- Share protocol fixtures, not target-language implementation code, between
  C++ and Rust reducers.
- Add a golden differential test that feeds identical synthetic samples to both
  generated reducers and requires equivalent decisions.

Focused validation covers stable wins, conflicts between scenarios, noise,
insufficient rounds, zero durations, stale context, wrong backend, and runtime
self-tests. No wall-clock result is asserted.

Exit criterion: Rust never selects an alternative from incomplete, invalid,
foreign, or inconclusive evidence, and C++ reducer behavior remains unchanged.

### Slice 4: Precomputed Rust Policy Consumption

**Outcome:** an explicit policy-enabled Cargo build validates a precomputed Rust
policy and compiles the selected mapping; an ordinary build still uses the
authored default.

Changes:

- Add one explicit policy input, provisionally
  `TSL_RUST_VARIANT_POLICY_FILE`, at the generated Cargo/build boundary.
- Validate schema/protocol, backend, manifest/body hashes, profile, tune context,
  rustc/target settings, and native CPU identity before materializing selection.
- Render a complete policy mapping under `OUT_DIR`; never patch generated
  `src/` files.
- Declare deterministic `rerun-if-changed` and `rerun-if-env-changed` inputs.
- Fail clearly on missing, stale, foreign, partial, duplicate, or unsupported
  decisions. Never fall back silently after a policy was explicitly requested.
- Keep policy consumption native-only in the first version.

Focused validation:

- unset policy builds and runs the default consumer;
- a forced context-valid policy builds and runs the non-default consumer;
- wrong-backend, wrong-profile, wrong-rustc/context, wrong-CPU, stale-body, and
  partial policies fail before consumer compilation;
- changing/removing the policy invalidates the Cargo build-script output; and
- normal `cargo test` and generated Rust value tests remain green.

Exit criterion: a precomputed policy changes only its intended specialization,
all explicit invalid-policy cases fail closed, and the build process never runs
the benchmark.

### Slice 5: Explicit Two-Phase Rust Autotune Workflow

**Outcome:** documented commands first create a Rust policy from an optimized
native report and then build a real downstream consumer with that policy.

Changes:

- Document the policy-free `cargo bench` invocation with explicit profile and
  benchmark features.
- Document the separate policy-enabled `cargo build`/consumer invocation.
- Ensure the first phase cannot see or inherit an existing policy input.
- Record report and policy paths under the Cargo target/build tree, not the
  generated source tree.
- Add a generated-project integration test that uses short measurement settings
  to exercise the real graph, then rewrites one context-valid decision to a
  known alternative and proves that a downstream consumer received it.
- Update `docs/variant-benchmarking.md`, `tslc/DESCRIPTION.md`, and generated
  Cargo help only when the commands exist.

Exit criterion: the explicit two-phase workflow is cycle-free, default builds
remain non-executing, a real consumer observes a forced selected variant, and no
test depends on which candidate happens to win on the CI host.

### Slice 6: Backend-Scoped Coverage Ratchet

**Outcome:** Rust benchmark and policy coverage become durable,
backend-separated evidence without weakening the existing C++ ratchet.

Changes:

- Parameterize the benchmark maintenance audit by backend while preserving the
  existing C++ baseline and inventory.
- Add separate Rust issue identities, baseline, and shape inventory. Exact
  candidate identities and relevant content hashes are ratcheted; aggregate
  counts alone are insufficient.
- Distinguish report eligibility from policy-consumption eligibility so an
  immediate or overloaded candidate can remain honestly report-only.
- Add ARM native policy coverage only after CPU identity is specific enough to
  reject foreign machines. Emulator runs remain correctness/functional checks.

Exit criterion: every current Rust variant-bearing slot either reaches an
emitted report and, where supported, a policy mapping, or appears as a
deterministic actionable gap without altering C++ evidence.

### Optional Slice 7+: Evidence-Driven Scenario-Family Coverage

**Status:** Slices 0–6 complete the first Rust autotuning version. These
follow-ups expand report coverage; they are not prerequisites for claiming the
native SSE2 register workflow, policy production, or policy consumption.

**Outcome:** each independently justified follow-up adds complete report
behavior for one already-typed scenario family and closes only that family's
Rust coverage gaps.

Evidence-driven order:

1. **Completed:** add shared exact-lane planning plus Rust vector-result
   immediate reports for the six current native SSE2 candidate slots,
   retaining structured report-only Rust policy decisions; matching C++
   immediate evidence may improve wherever the same exact-width specialization
   is selected;
2. **Completed:** before enabling any additional machine profile, replace
   independent profile and scenario allowlists with explicit
   `profile × scenario-family` admission so capability expansion cannot admit
   an unintended Cartesian product;
3. **Completed:** add AVX2 one-vector scalar reductions after confirming 40
   exact candidate slots with authored correctness and two emitted candidates;
4. add integral-mask density or indexed hot-L1 loads only after choosing and
   proving their exact native target profiles; and
5. defer the Wasm-only vector-plus-scalar and vector-input mask-result families
   until benchmarking under a Wasm runtime is an explicit product decision.

The completed SSE2 immediate follow-up binds each authored immediate into its
direct Rust candidate call, uses exact-width correctness inputs, guards the
unary latency dependency against compiler collapse, and proves the native
`shufps` hot loop. All six decisions remain report-only with the explicit
`immediate specializations are report-only` reason.

The completed AVX2 reduction follow-up emits throughput reports for `hadd`,
`hand`, `hmax`, `hmin`, and `hor` across the eight fixed-width integer types.
All 40 candidate sets use authored exact-width scalar expectations and remain
report-only with the explicit
`scalar-result reduction specializations are report-only` reason. Native short
execution covers every set, and the `hadd/si32` assembly proof follows both
production target-feature call paths to distinct, call-free vector-reduction
bodies. Report-only summaries retain the observed result, while these
all-report-only profiles neither advertise nor produce a consumable policy.

Mask-density and indexed-load support remain deferred. The current exact Rust
gaps provide only two canonical AVX2 mask-density slots without a demonstrated
tuning question, while indexed loads are spread across AVX-512 profiles and do
not yet have one selected native profile and host proof. Their target choice and
workload value must be justified before adding either admission pair.

Each implemented family slice includes Rust correctness rendering, timing
rendering, manifest evidence, generated compilation, a short native mechanics
run, and an explicit policy-supported or structured report-only decision.
Policy selection for a family is a separate slice whenever its stable-Rust
mapping differs from the proven register mapping. Cross-compiled or emulated
correctness never substitutes for the native mechanics evidence required by a
timing slice.

Exit criterion for each implemented family: every selected candidate set in
that family either emits correct deterministic report artifacts or has one
precise backend-specific reason why it cannot. Unrelated families remain
unchanged; shared planner improvements may update matching C++ family evidence
but must not alter unrelated C++ candidate identities. A deferred family
remains an exact coverage gap rather than an incomplete implementation
commitment.

## Validation Matrix

Every implementation slice runs focused tests at its owning boundary, followed
by:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
git diff --check
```

Slices that change generated Rust layout, backend source, Cargo behavior, or
executable correctness also run the smallest relevant opt-in generated gates:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py \
  tslc/tests/test_benchmark_variants.py \
  tslc/tests/test_rust_benchmark_rendering.py
```

Validation must include these invariants:

| Boundary | Required proof |
|---|---|
| Planner | C++ plan/hash compatibility; Rust backend identity; deterministic ordering; additive fake backend |
| Renderer | No semantic inference from primitive names or Rust text; stable artifact order/content |
| Correctness | Every candidate passes authored expectations before timing |
| Harness | Optimized native compile; barrier and call-path assembly evidence; no winner timing assertion |
| Reducer | Golden C++/Rust decision parity over synthetic samples; default on noise/conflict |
| Policy | Wrong backend/profile/body/context/CPU fails closed; decisions are complete and unique |
| Selection | Forced non-default reaches ordinary wrapper; no runtime branch or public API change |
| Cargo | Normal build/test never runs benchmark; benchmark build is policy-free; writes stay in target/`OUT_DIR` |
| Coverage | Separate exact Rust and C++ issue identities and hashes |

Unavailable native hardware is an explicit generated-verification gap, not a
passing timing test. Functional emulator coverage may prove compilation and
correctness but never policy validity.

## Risks And Controls

- **Rust coherence and const generics:** a generic default plus specific policy
  impls may overlap. Use one complete replacement mapping and keep unsupported
  const-generic/immediate shapes report-only.
- **Measurement bias:** a separate Cargo benchmark crate can measure call
  boundaries rather than the operation. Keep the hot loop in the feature-gated
  library module and inspect optimized assembly.
- **Inlining differences:** do not add benchmark-only inlining that consumers do
  not receive. Any production inline annotation is a separate backend codegen
  decision with value/build tests.
- **Cargo cycles:** the benchmark build is policy-free and policy consumption is
  a second invocation. `build.rs` validates/materializes only; it never runs the
  benchmark.
- **Context gaps:** policies stay build-local and fail closed until all relevant
  rustc/Cargo/CPU inputs are captured.
- **Protocol drift:** C++ and Rust runtime implementations use shared golden
  fixtures and protocol-versioned outputs.
- **Coverage explosion:** begin with one x86 fixed-width register family and add
  backend-scoped evidence before widening.
- **Unsafe and target-feature calls:** invoke the already-emitted Rust candidate
  traits and preserve their backend-owned safety framing. Refuse non-native
  execution.
- **Build-script side effects:** write only deterministic `OUT_DIR` artifacts,
  declare all rerun inputs, perform no network access, and never mutate sources.
- **ARM policy portability:** an architecture-only `aarch64` fingerprint is not
  sufficient. Keep ARM report-only or machine-local until a precise fingerprint
  is owned and tested.

## Stop Conditions

Stop the policy/autotune sequence, while retaining report-only benchmarking, if:

- stable Rust selection requires a runtime branch, public API change, nightly
  specialization, or overlapping impls;
- production-equivalent candidate calls cannot be measured without unequal
  per-operation harness overhead;
- policy consumption requires executing benchmark code from `build.rs` or
  splitting the generated project into a broad workspace rewrite;
- the tune context cannot reject stale, foreign, or materially different
  compiler settings;
- the slice begins changing `.tsl` semantics merely to satisfy the harness; or
- native verification is unavailable for the only claimed policy-supported
  target.

Do not treat a noisy benchmark, incomplete corpus coverage, or an inconclusive
winner as an infrastructure blocker. Those outcomes retain the authored default
and remain explicit evidence.

## Completion Criteria

The Rust first version is complete when:

- Rust candidate planning reuses the same typed owners as C++ without duplicating
  workload semantics;
- an opt-in optimized native report validates every candidate before timing and
  emits deterministic backend-scoped evidence;
- normal generated Cargo builds and tests remain non-executing and authored-
  default;
- a forced valid Rust policy changes exactly one ordinary wrapper
  specialization at compile time with no runtime dispatch or API change;
- stale, foreign, partial, wrong-context, and wrong-CPU policies fail closed;
- the explicit two-phase workflow builds a real downstream consumer;
- C++ manifests, policies, coverage, and generated behavior do not regress;
- Rust report and policy gaps have separate exact coverage identities; and
- user and architecture documentation describe the commands, ownership, native
  restriction, and build-local policy limitation.

## Explicitly Deferred

- One-invocation Cargo autotuning or automatic recursive rebuild orchestration.
- Profile auto-detection for Rust benchmark execution.
- Remote, fleet-wide, or cross-compiled policy production and reuse.
- Raw C++ versus Rust performance comparison and result dashboards; those are
  downstream analysis concerns.
- Full scenario-family parity and corpus-wide zero-gap coverage.
- Policy selection for immediate values, axes, overloads, representation
  changes, scalable vectors, and SIMD type parameters until each has a stable
  compile-time proof.
- Nightly `portable_simd` or compiler-SIMD overlays.
- Automatic rewriting of authored defaults from benchmark results.
