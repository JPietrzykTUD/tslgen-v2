# CPP-ADD-I32-TEST Provenance

This golden fixture covers the Milestone 49 generated C++ test-source parity
slice for `add_i32_basic`.

- Source test data: `tsldata/primitives/arithmetic/fundamental.tsl:6` provides
  the selected `add_i32_basic` input vectors and expected vector.
- Legacy source-shape evidence:
  - `frozen/jinja/cpp/test_file.j2:1-56` for include and
    `TEST(...){ ASSERT_TRUE(...) }` registration structure.
  - `frozen/jinja/cpp/partials/test_common.j2:1-13` for boolean test function
    and `Vec` alias shape.
  - `frozen/jinja/cpp/test_case.j2:51-63` for binary wrapper-call intent.
  - `frozen/jinja/cpp/partials/test_vectors.j2:38-50` for
    `store_vector(...)` expansion through `tsl::store_aligned_false<Vec>(...)`.
  - `frozen/generator_specs/tests.yaml:45-59` for C++ test-generation policy
    evidence.
- Renderer inputs: typed `TestSourcePlan` / `PlannedTestCase` data and explicit
  typed `BackendTypeSpelling(backend_id="cpp", type_tag="si32",
  spelling="int32_t", source_ref_kind="base.in")`.
- Deferred behavior: compiling or running generated tests, fetching or requiring
  `gtest`, broad support headers, runtime lane policy, mask handling, and
  generated-test framework expansion.

`frozen/` is evidence only; the renderer does not read or execute legacy
templates at runtime.
