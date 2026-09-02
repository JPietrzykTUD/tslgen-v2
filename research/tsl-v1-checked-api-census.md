# TSL v1 checked-API baseline census

This generated maintenance report freezes the evidence reviewed before the checked-API refactor. Its lexical runtime-site scan is tooling evidence only; production semantics must come from typed source/catalog facts and finalized backend plans.

## Frozen public policy

- Public suffix: `_checked`
- Eligibility: catastrophic dynamic caller precondition; complete pre-side-effect check must be expressible from the checked signature.
- C++ value result: direct value return plus final precondition_error& output.
- C++ void result: nodiscard precondition_error return.
- Rust value result: `Result<T, PreconditionError>`.
- Rust void result: `Result<(), PreconditionError>`.
- Unchecked Rust: `unsafe fn when violating the caller contract can cause UB`.
- Failed C++ value result: initialized backend-owned placeholder with no TSL-defined value; the ordinary operation is not invoked.

## Inventory summary

- Exact generated runtime-failure sites: 231
- Exact typed public callable identities with at least one `caller_unsafe` implementation: 33
- Applicable source safety-metadata gaps: 138 (26 require caller unsafety)

Runtime sites by classification:

- dynamic precondition: 92
- implementation hazard: 8
- static well-formedness constraint: 22
- tooling-only validation: 109

## Reviewed semantic families

| Family | Classification | Backend consequence | Complete-check feasibility |
| --- | --- | --- | --- |
| `tooling_only` | tooling-only validation | Failure is confined to generated tests, builds, documentation stubs, or benchmarks. | not applicable |
| `static_representation_or_lane_shape` | static well-formedness constraint | C++ or Rust currently diagnoses an impossible compiler-selected representation at runtime. | no checked twin; validate statically |
| `static_immediate_nonzero` | static well-formedness constraint | Rust emits a const assertion; invalid authored immediates do not reach a call. | no checked twin; keep a compile-time diagnostic |
| `integer_zero_divisor` | dynamic precondition | C++ throws or traps and Rust panics in the current generated implementation. | complete for runtime integer division/remainder; check active divisor lanes |
| `lane_index` | dynamic precondition | Rust facade calls panic today; an unchecked C++ or Rust primitive may access outside its logical lanes. | complete from the runtime index and typed logical lane count |
| `contiguous_extent` | dynamic precondition | Rust slice facades panic when a contiguous input or output is too short. | complete with a valid slice/span signature; not honest for a bare pointer |
| `algorithm_equal_extents` | dynamic precondition | Rust generated algorithms panic when related slices have different extents. | complete from the checked algorithm's slice arguments |
| `algorithm_output_capacity` | dynamic precondition | Rust generated algorithms panic when an output/index buffer is too short. | complete from the checked algorithm's input and output slices |
| `algorithm_mask_capacity` | dynamic precondition | Rust generated algorithms panic when mask storage cannot cover the input. | complete from the input extent, mask layout, lane count, and mask slice |
| `algorithm_selected_index` | dynamic precondition | Rust generated algorithms panic when a selected row index is outside the input. | complete by validating every selected index before kernel dispatch |
| `implementation_exhaustiveness` | implementation hazard | Rust panics if compiler-selected scalar cast types escape the supported closed set. | no checked twin; repair typed validation/exhaustiveness |
| `implementation_invariant` | implementation hazard | A debug assertion or unwrap fails if an internal compiler-owned invariant is broken. | no checked twin; retain or replace with compiler validation |
| `contiguous_memory_contract` | dynamic precondition | Raw C++ pointers remain unchecked; Rust public exposure must be unsafe until a safe slice wrapper discharges the contract. | requires a span/slice carrying readable or writable extent and selected alignment |
| `mask_memory_contract` | dynamic precondition | Raw mask representation loads/stores have the same pointer hazard plus layout-dependent capacity. | requires a span/slice and a typed mask-layout capacity plan |
| `selected_memory_contract` | dynamic precondition | Expand/compress operations may access a mask-dependent number of elements. | requires a range plus capacity derived from the active mask |
| `indexed_memory_contract` | dynamic precondition | Gather/scatter paths may access invalid addresses for active indices. | requires a valid base view, extent, typed scale, and active-index validation |
| `deallocation_provenance` | dynamic precondition | Mismatched, dead, or foreign allocation provenance can cause undefined behavior. | no honest pointer-only checked twin; design an owning allocation API separately |
| `random_output_contract` | dynamic precondition | The random-step intrinsic writes through a raw output pointer on success. | requires a mutable reference/view, or an owning optional/result value API |
| `raw_copy_contract` | dynamic precondition | Invalid ranges or prohibited overlap can cause undefined behavior or corruption. | requires valid source/destination views plus an explicit overlap contract/check |
| `conversion_input_contract` | dynamic precondition | Widening loads read multiple source elements through a raw pointer. | requires a source span/slice with the lowering-resolved element count |

## Exact generated runtime sites

### `tooling_only` (109)

It is not part of a generated runtime API contract.

- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:125` — owner `if` — `throw` — `throw std::runtime_error("--threshold must be in [0, 1)");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:122` — owner `if` — `throw` — `throw std::runtime_error("unknown benchmark option: " + argument);`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:127` — owner `if` — `throw` — `throw std::runtime_error("--rounds must be at least 3");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:142` — owner `main` — `throw` — `throw std::runtime_error("--render-policy requires --policy-header");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:154` — owner `output` — `throw` — `throw std::runtime_error("cannot open results output");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:110` — owner `parse_options` — `throw` — `throw std::runtime_error("missing value for " + argument);`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:82` — owner `read_policy` — `throw` — `throw std::runtime_error("variant policy has missing or unexpected decisions");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:77` — owner `read_policy` — `throw` — `throw std::runtime_error( "variant policy does not match this manifest, compiler context, and CPU");`
- `tslc/src/tslc/backend/assets/cpp_benchmark.cpp.tmpl:44` — owner `render_policy_header` — `throw` — `throw std::runtime_error("policy contains an unknown specialization or candidate: " + decision.stable_id + "/" + decision.selected);`
- `tslc/src/tslc/backend/assets/rust_benchmark.rs.tmpl:141` — owner `cross_target_build_is_not_native` — `assert` — `assert!(!super::native_build_matches( "x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu", ));`
- `tslc/src/tslc/backend/assets/rust_benchmark_main.rs.tmpl:4` — owner `file_scope` — `panic` — `panic!("TSL_RUST_VARIANT_POLICY_FILE must be unset for benchmark targets");`
- `tslc/src/tslc/backend/assets/rust_build.rs:210` — owner `command_verbose_version` — `panic` — `panic!("{label} --version --verbose failed while capturing the benchmark tune context");`
- `tslc/src/tslc/backend/assets/rust_build.rs:213` — owner `command_verbose_version` — `panic` — `panic!("{label} --version --verbose did not produce UTF-8")`
- `tslc/src/tslc/backend/assets/rust_build.rs:207` — owner `command_verbose_version` — `panic` — `panic!("cannot execute {label} to capture the benchmark tune context: {error}")`
- `tslc/src/tslc/backend/assets/rust_build.rs:330` — owner `emit` — `panic` — `panic!("benchmark tune-context value {} contains a newline", name);`
- `tslc/src/tslc/backend/assets/rust_build.rs:252` — owner `force_context_revalidation` — `panic` — `panic!( "cannot inspect reserved Rust context revalidation path {}: {error}", sentinel.display() )`
- `tslc/src/tslc/backend/assets/rust_build.rs:263` — owner `force_context_revalidation` — `panic` — `panic!("Rust context revalidation path cannot contain line breaks");`
- `tslc/src/tslc/backend/assets/rust_build.rs:256` — owner `force_context_revalidation` — `panic` — `panic!( "reserved Rust context revalidation path {} must remain absent", sentinel.display() )`
- `tslc/src/tslc/backend/assets/rust_build.rs:167` — owner `main` — `panic` — `panic!("Rust variant policy validation failed: {error}")`
- `tslc/src/tslc/backend/assets/rust_build.rs:88` — owner `main` — `panic` — `panic!("Rust authored-default mapping failed: {error}")`
- `tslc/src/tslc/backend/assets/rust_build.rs:199` — owner `required` — `panic` — `panic!("Cargo did not provide {}", name)`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:40` — owner `explicit_and_convenience_dispatch_match` — `assert_eq` — `assert_eq!(convenient, explicit);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:39` — owner `explicit_and_convenience_dispatch_match` — `assert_eq` — `assert_eq!(explicit, [9_i32; 8]);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:57` — owner `mutable_user_operation_state_is_preserved` — `assert_eq` — `assert_eq!(output, [9_i32; 8]);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:58` — owner `mutable_user_operation_state_is_preserved` — `assert` — `assert!(operation.applications > 0);`
- `tslc/src/tslc/backend/assets/rust_smoke.rs:3` — owner `smoke` — `assert` — `assert!(true);`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:101` — owner `calibrate` — `throw` — `throw std::runtime_error("benchmark calibration exceeded iteration limit");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:139` — owner `input` — `throw` — `throw std::runtime_error("cannot open policy file: " + path);`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:166` — owner `json_string_field` — `throw` — `throw std::runtime_error("policy is missing field '" + field + "'");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:178` — owner `json_string_field` — `throw` — `throw std::runtime_error("unterminated policy string field '" + field + "'");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:170` — owner `json_string_field` — `throw` — `throw std::runtime_error("policy field '" + field + "' has no value");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:174` — owner `json_string_field` — `throw` — `throw std::runtime_error("policy field '" + field + "' is not a string");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:148` — owner `output` — `throw` — `throw std::runtime_error("cannot write benchmark artifact: " + path);`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:152` — owner `output` — `throw` — `throw std::runtime_error("cannot finish benchmark artifact: " + path);`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:341` — owner `reducer_self_test` — `throw` — `throw std::runtime_error("benchmark reducer self-test failed");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.hpp:48` — owner `rotating_mask_bits` — `throw` — `throw std::runtime_error("invalid compact-mask benchmark dimensions");`
- `tslc/src/tslc/backend/assets/tsl_benchmark_core.rs:287` — owner `json_escape` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:413` — owner `render_policy_json` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:429` — owner `render_policy_json` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:350` — owner `render_samples` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:363` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:364` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:365` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:366` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:367` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:368` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:379` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:389` — owner `render_summary` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_benchmark_policy.rs:498` — owner `render_tune_context` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/tsl_rust_policy_json.rs:425` — owner `Err` — `expect` — `.expect("JSON number spelling is ASCII");`
- `tslc/src/tslc/backend/assets/tsl_rust_policy_json.rs:486` — owner `string_segment` — `expect` — `.expect("JSON string segment comes from validated UTF-8 input")`
- `tslc/src/tslc/backend/assets/tsl_rust_variant_policy_validation.rs:271` — owner `Err` — `unreachable` — `unreachable!("descriptor status was validated")`
- `tslc/src/tslc/backend/rust_documentation_api.py:104` — owner `documentation_free_function` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:84` — owner `documentation_overloaded_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:54` — owner `documentation_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/benchmark/render_cpp.py:229` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy has an unterminated decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:233` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy selects an unavailable candidate for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:226` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy repeats a decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:224` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy has no decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp_scenarios.py:469` — owner `_render_measure_dispatch` — `throw` — `default: throw std::runtime_error("invalid candidate index");`
- `tslc/src/tslc/render/rust_dispatch.py:571` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(ENTRY_CALLS.load(Ordering::SeqCst), 2);",`
- `tslc/src/tslc/render/rust_dispatch.py:591` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(HARDWARE_ENTRY_CALLS.load(Ordering::SeqCst), 0);",`
- `tslc/src/tslc/render/rust_dispatch.py:558` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:570` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:572` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(output, [9 as TestElement; 8]);",`
- `tslc/src/tslc/render/rust_dispatch.py:590` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(output, [9 as TestElement; 8]);",`
- `tslc/src/tslc/render/rust_dispatch.py:557` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(detector.detect_calls, 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:569` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(detector.detect_calls, 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:521` — owner `_unit_tests` — `assert_eq` — `f" assert_eq!(table.{field}, {entry.entry_index});",`
- `tslc/src/tslc/render/rust_dispatch.py:513` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/render/rust_dispatch.py:550` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/render/rust_dispatch.py:577` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:35` — owner `_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:471` — owner `_differential` — `assert_eq` — `f" for i in 0..{case.lanes} {{ assert_eq!("`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:479` — owner `_differential` — `assert` — `" assert!(hw.lane_eq(reference), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:492` — owner `_differential` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(hw[i].{comparison}(reference[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:289` — owner `_extension_extract` — `assert` — `f" for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:324` — owner `_extension_insert` — `assert` — `f" for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:364` — owner `_extension_result` — `assert` — `f" for i in 0..{expected_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:259` — owner `_fixed_extension_load_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:194` — owner `_fixed_extension_repr_cast` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:115` — owner `_lane_convert` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:227` — owner `_load_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:66` — owner `_repr_cast` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:161` — owner `_target_imask` — `assert_eq` — `f' assert_eq!(result, expected, "{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:63` — owner `_generic_golden` — `assert_eq` — `f" for i in 0..{case.lanes} {{ assert_eq!(mask_bit(result as u64, i), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:460` — owner `_lane_assert` — `assert` — `f" for i in 0..{lanes} {{ assert!({result_name}[i].{comparison}(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:260` — owner `_mask_logic` — `assert_eq` — `f" assert_eq!(mask_bit(result as u64, {lane}), {bit}, "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:233` — owner `_mask_result` — `assert_eq` — `f" assert_eq!(mask_bit(result as u64, {lane}), {bit}, "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:313` — owner `_mask_store` — `assert` — `f" for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), ",`
- `tslc/src/tslc/value_tests/_render_rust_core.py:383` — owner `_reduction` — `assert` — `f" assert!(result.lane_eq(expected), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:425` — owner `_runtime_failure` — `assert_eq` — `f' assert_eq!(message, Some("{marker}"), "{case.case_name}: wrong panic payload");',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:421` — owner `_runtime_failure` — `panic` — `f' Ok(_) => panic!("{case.case_name}: expected integer-zero-divisor panic"),',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:340` — owner `_scalar_result` — `assert` — `f" assert!(result.lane_eq(expected), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:446` — owner `_status_pointer` — `assert_eq` — `f' assert_eq!(value, before, "{case.case_name}: failure modified output");',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:444` — owner `_status_pointer` — `assert` — `f' assert!(status <= 1, "{case.case_name}: invalid status {{status}}");',`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:344` — owner `_indexed_load` — `assert` — `f" for i in 0..{lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:395` — owner `_indexed_store` — `assert` — `f" for i in 0..{buflen} {{ assert!(data[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:41` — owner `_load` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:130` — owner `_mask_pointer_load` — `assert_eq` — `f" assert_eq!(mask_bit(result as u64, {lane}), {bit}, "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:174` — owner `_masked_pointer_load` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:206` — owner `_masked_pointer_store` — `assert` — `f" for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:240` — owner `_memory_copy` — `assert` — `f" for i in 0..{dst_len} {{ assert!(dst[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:279` — owner `_pointer_free` — `assert` — `f' assert!(!ptr.is_null(), "{case.case_name}: setup allocation failed");',`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:259` — owner `_pointer_lifetime` — `assert_eq` — `f" assert_eq!((ptr as usize) % {alignment}usize, 0, "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:255` — owner `_pointer_lifetime` — `assert` — `f' assert!(!ptr.is_null(), "{case.case_name}: null pointer");',`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:96` — owner `_scalar_pointer_load` — `assert` — `f" assert!(result.lane_eq(expected), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:70` — owner `_store` — `assert` — `f" for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_memory.py:421` — owner `_stream` — `assert_eq` — `f" assert_eq!(result.as_str(), {expected}, \"{case.case_name}\");",`

### `static_representation_or_lane_shape` (20)

Sizes, lane counts, and mask-storage capacity are compiler-owned specialization facts.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6999` — owner `aggregate_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5213` — owner `aggregate_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5091` — owner `aggregate_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6922` — owner `aggregate_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6629` — owner `consume_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4965` — owner `consume_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4848` — owner `consume_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6560` — owner `consume_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:851` — owner `for_each_chunk_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::for_each_chunk requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6483` — owner `transform_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4716` — owner `transform_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4578` — owner `transform_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6395` — owner `transform_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:662` — owner `validate_integral_mask_vector` — `assert` — `assert!( lanes <= <V::ImaskType as IntegralMaskWord>::BITS, "{} requires an integral mask storage type with at least one bit per lane", helper_name, );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:657` — owner `validate_integral_mask_vector` — `assert` — `assert!( lanes > 0, "{} requires a vector with at least one lane", helper_name, );`
- `tslc/src/tslc/backend/assets/tsl_core.hpp:383` — owner `require_same_lanes` — `throw` — `throw std::invalid_argument( "lane-preserving conversion requires equal source and target lane counts" );`
- `tslc/src/tslc/backend/assets/tsl_core.hpp:381` — owner `require_same_lanes` — `trap` — `__builtin_trap();`
- `tslc/src/tslc/backend/assets/tsl_core.rs:252` — owner `bit_cast` — `assert_eq` — `assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());`
- `tslc/src/tslc/backend/assets/tsl_core.rs:266` — owner `reinterpret_unchecked` — `assert_eq` — `assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());`
- `tslc/src/tslc/backend/assets/tsl_core.rs:661` — owner `require_same_lanes` — `assert_eq` — `assert_eq!( source_lanes, target_lanes, "lane-preserving conversion requires equal source and target lane counts" );`

### `static_immediate_nonzero` (2)

The operand is an immediate rather than caller-controlled runtime data.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:680` — owner `selected_row_scale` — `assert` — `assert!(scale > 0, "tsl::algo selected-row scale must be nonzero");`
- `tslc/src/tslc/backend/rust_signatures.py:121` — owner `_arithmetic_precondition` — `assert` — `f"const {{ assert!(({precondition.parameter_name} as "`

### `integer_zero_divisor` (3)

Floating-point zero remains valid and masked forms inspect active lanes only.

- `tslc/src/tslc/backend/assets/tsl_core.hpp:421` — owner `arith_zero_divisor_fail` — `throw` — `throw std::domain_error("TSL_ARITH_INTEGER_ZERO_DIVISOR");`
- `tslc/src/tslc/backend/assets/tsl_core.hpp:419` — owner `arith_zero_divisor_fail` — `trap` — `__builtin_trap();`
- `tslc/src/tslc/backend/assets/tsl_core.rs:688` — owner `arith_zero_divisor_fail` — `panic` — `panic!("TSL_ARITH_INTEGER_ZERO_DIVISOR")`

### `lane_index` (5)

Total operations such as test_imask remain excluded when out-of-range has defined semantics.

- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:157` — owner `lane` — `assert` — `assert!(index < N, "lane index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:169` — owner `set_lane` — `assert` — `assert!(index < N, "lane index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:339` — owner `set` — `assert` — `assert!(index < N, "mask index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:327` — owner `test` — `assert` — `assert!(index < N, "mask index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/render/rust_facade_comprehensive.py:491` — owner `_bounds_checks` — `assert` — `f' assert!({_identifier(name)} < {lanes}, '`

### `contiguous_extent` (2)

The checked signature must establish an addressable extent.

- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:215` — owner `copy_to_slice` — `assert` — `assert!( destination.len() >= N, "destination slice has {} elements but {N} are required", destination.len() );`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:182` — owner `from_slice` — `assert` — `assert!( source.len() >= N, "source slice has {} elements but {N} are required", source.len() );`

### `algorithm_equal_extents` (37)

All extents can be compared before dispatch or output writes.

- `tslc/src/tslc/backend/assets/rust_dispatch.rs.tmpl:88` — owner `transform_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "runtime transform_binary requires equally sized inputs", );`
- `tslc/src/tslc/backend/assets/rust_dispatch.rs.tmpl:93` — owner `transform_binary` — `assert_eq` — `assert_eq!( left.len(), output.len(), "runtime transform_binary requires equally sized input and output", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6962` — owner `aggregate_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::aggregate_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:7158` — owner `aggregate_masked_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::aggregate_masked_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5138` — owner `aggregate_selected_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::aggregate_selected_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6593` — owner `consume_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::consume_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6781` — owner `consume_masked_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::consume_masked_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4892` — owner `consume_selected_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::consume_selected_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1545` — owner `count_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::count_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2022` — owner `count_masked_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::count_masked_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1762` — owner `count_masked_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::count_masked_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2297` — owner `count_selected_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::count_selected_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1294` — owner `predicate_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::predicate_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1010` — owner `predicate_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::predicate_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2573` — owner `select_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3462` — owner `select_indices_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_indices_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3192` — owner `select_masked_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_masked_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2860` — owner `select_masked_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_masked_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4005` — owner `select_masked_indices_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_masked_indices_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3709` — owner `select_masked_indices_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_masked_indices_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4325` — owner `select_selected_indices_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::select_selected_indices_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6441` — owner `transform_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6446` — owner `transform_binary` — `assert_eq` — `assert_eq!( left.len(), output.len(), "tsl::algo::transform_binary requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6224` — owner `transform_masked_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_masked_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6229` — owner `transform_masked_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), output.len(), "tsl::algo::transform_masked_binary_mask_layout requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5672` — owner `transform_masked_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_masked_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5677` — owner `transform_masked_binary` — `assert_eq` — `assert_eq!( left.len(), output.len(), "tsl::algo::transform_masked_binary requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6102` — owner `transform_masked_unary_mask_layout` — `assert_eq` — `assert_eq!( input.len(), output.len(), "tsl::algo::transform_masked_unary_mask_layout requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5553` — owner `transform_masked_unary` — `assert_eq` — `assert_eq!( input.len(), output.len(), "tsl::algo::transform_masked_unary requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4633` — owner `transform_selected_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_selected_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6360` — owner `transform_unary` — `assert_eq` — `assert_eq!( input.len(), output.len(), "tsl::algo::transform_unary requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5949` — owner `transform_where_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_where_binary_mask_layout requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5954` — owner `transform_where_binary_mask_layout` — `assert_eq` — `assert_eq!( left.len(), output.len(), "tsl::algo::transform_where_binary_mask_layout requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5407` — owner `transform_where_binary` — `assert_eq` — `assert_eq!( left.len(), right.len(), "tsl::algo::transform_where_binary requires left and right slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5412` — owner `transform_where_binary` — `assert_eq` — `assert_eq!( left.len(), output.len(), "tsl::algo::transform_where_binary requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5815` — owner `transform_where_unary_mask_layout` — `assert_eq` — `assert_eq!( input.len(), output.len(), "tsl::algo::transform_where_unary_mask_layout requires input and output slices of equal length", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5281` — owner `transform_where_unary` — `assert_eq` — `assert_eq!( input.len(), output.len(), "tsl::algo::transform_where_unary requires input and output slices of equal length", );`

### `algorithm_output_capacity` (16)

Capacity can be checked before the raw kernel performs a write.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2578` — owner `select_binary` — `assert` — `assert!( output.len() >= left.len(), "tsl::algo::select_binary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3467` — owner `select_indices_binary` — `assert` — `assert!( indices.len() >= left.len(), "tsl::algo::select_indices_binary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3363` — owner `select_indices_unary` — `assert` — `assert!( indices.len() >= input.len(), "tsl::algo::select_indices_unary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3209` — owner `select_masked_binary_mask_layout` — `assert` — `assert!( output.len() >= left.len(), "tsl::algo::select_masked_binary_mask_layout requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2873` — owner `select_masked_binary` — `assert` — `assert!( output.len() >= left.len(), "tsl::algo::select_masked_binary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4022` — owner `select_masked_indices_binary_mask_layout` — `assert` — `assert!( indices.len() >= left.len(), "tsl::algo::select_masked_indices_binary_mask_layout requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3722` — owner `select_masked_indices_binary` — `assert` — `assert!( indices.len() >= left.len(), "tsl::algo::select_masked_indices_binary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3873` — owner `select_masked_indices_unary_mask_layout` — `assert` — `assert!( indices.len() >= input.len(), "tsl::algo::select_masked_indices_unary_mask_layout requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3587` — owner `select_masked_indices_unary` — `assert` — `assert!( indices.len() >= input.len(), "tsl::algo::select_masked_indices_unary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3044` — owner `select_masked_unary_mask_layout` — `assert` — `assert!( output.len() >= input.len(), "tsl::algo::select_masked_unary_mask_layout requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2717` — owner `select_masked_unary` — `assert` — `assert!( output.len() >= input.len(), "tsl::algo::select_masked_unary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4335` — owner `select_selected_indices_binary` — `assert` — `assert!( output_indices.len() >= input_indices.len(), "tsl::algo::select_selected_indices_binary requires enough output slots for the selected rows", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4171` — owner `select_selected_indices_unary` — `assert` — `assert!( output_indices.len() >= input_indices.len(), "tsl::algo::select_selected_indices_unary requires enough output slots for the selected rows", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2457` — owner `select_unary` — `assert` — `assert!( output.len() >= input.len(), "tsl::algo::select_unary requires enough output slots for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4639` — owner `transform_selected_binary` — `assert` — `assert!( output.len() >= indices.len(), "tsl::algo::transform_selected_binary requires enough output slots for the selected rows", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4505` — owner `transform_selected_unary` — `assert` — `assert!( output.len() >= indices.len(), "tsl::algo::transform_selected_unary requires enough output slots for the selected rows", );`

### `algorithm_mask_capacity` (28)

The finalized algorithm plan already owns these facts.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:7167` — owner `aggregate_masked_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::aggregate_masked_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:7059` — owner `aggregate_masked_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::aggregate_masked_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6790` — owner `consume_masked_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::consume_masked_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6686` — owner `consume_masked_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::consume_masked_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2035` — owner `count_masked_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::count_masked_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1771` — owner `count_masked_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::count_masked_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1904` — owner `count_masked_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::count_masked_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1654` — owner `count_masked_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::count_masked_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1307` — owner `predicate_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::predicate_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1019` — owner `predicate_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::predicate_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:1152` — owner `predicate_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::predicate_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:900` — owner `predicate_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::predicate_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3205` — owner `select_masked_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2869` — owner `select_masked_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4018` — owner `select_masked_indices_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_indices_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3718` — owner `select_masked_indices_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_indices_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3869` — owner `select_masked_indices_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_indices_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3583` — owner `select_masked_indices_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_indices_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:3040` — owner `select_masked_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:2713` — owner `select_masked_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::select_masked_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6242` — owner `transform_masked_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_masked_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5686` — owner `transform_masked_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_masked_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6115` — owner `transform_masked_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_masked_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5562` — owner `transform_masked_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_masked_unary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5967` — owner `transform_where_binary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_where_binary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5421` — owner `transform_where_binary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_where_binary requires enough mask chunks for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5828` — owner `transform_where_unary_mask_layout` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_where_unary_mask_layout requires enough mask storage for the input", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5290` — owner `transform_where_unary` — `assert` — `assert!( masks.len() >= required, "tsl::algo::transform_where_unary requires enough mask chunks for the input", );`

### `algorithm_selected_index` (1)

The check requires a valid index slice and input extent.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:691` — owner `validate_selected_indices` — `assert` — `assert!( index < input.len(), "{} requires selected row ids to be valid element indexes", helper_name, );`

### `implementation_exhaustiveness` (5)

This is a compiler/backend defect if reachable, not invalid caller data.

- `tslc/src/tslc/backend/assets/tsl_core.rs:1019` — owner `saturating_cast_value` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:976` — owner `saturating_from_f64` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:891` — owner `saturating_from_i128` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:934` — owner `saturating_from_u128` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:848` — owner `scalar_as_cast_value` — `panic` — `panic!("unsupported scalar-as cast")`

### `implementation_invariant` (3)

The condition is not part of the public call domain.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:146` — owner `lane_is_set` — `debug_assert` — `debug_assert!(lane < <Self as IntegralMaskWord>::BITS);`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:133` — owner `one_at` — `debug_assert` — `debug_assert!(lane < <Self as IntegralMaskWord>::BITS);`
- `tslc/src/tslc/backend/assets/tsl_core.rs:642` — owner `ostream_write` — `unwrap` — `.unwrap()`

## Typed `caller_unsafe` public paths

These identities come from `Catalog` and `ImplementationSafety`, not target-text inspection. A family records whether a future checked form can be honest; it does not itself authorize generation.

### `contiguous_memory_contract` (13)

- `load v:=(m,cptr,v)`; attributes `aligned=false, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `store void:=(m,ptr,v)`; attributes `aligned=false, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `load v:=(m,cptr)`; attributes `aligned=false, mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `load v:=cptr`; attributes `aligned=false`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 22
- `load_scalar s:=cptr`; attributes `aligned=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 15
- `store void:=(ptr,s)`; attributes `aligned=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 14
- `store void:=(ptr,v)`; attributes `aligned=false`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 26
- `load v:=(m,cptr,v)`; attributes `aligned=true, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `store void:=(m,ptr,v)`; attributes `aligned=true, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `load v:=(m,cptr)`; attributes `aligned=true, mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24
- `load v:=cptr`; attributes `aligned=true`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 22
- `store void:=(ptr,s)`; attributes `aligned=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 14
- `store void:=(ptr,v)`; attributes `aligned=true`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 26

Review: A pointer and caller-claimed count cannot establish lifetime or provenance.

### `mask_memory_contract` (8)

- `load_mask_repr m:=cptr`; attributes `aligned=false, packed=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=false, packed=false`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17
- `load_mask_repr m:=cptr`; attributes `aligned=false, packed=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=false, packed=true`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17
- `load_mask_repr m:=cptr`; attributes `aligned=true, packed=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=true, packed=false`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17
- `load_mask_repr m:=cptr`; attributes `aligned=true, packed=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=true, packed=true`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17

Review: Packed and lane-mask representations require different element counts.

### `selected_memory_contract` (2)

- `expand_load v:=(m,cptr)`; attributes `aligned=true, op=expand`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 20
- `compress_store void:=(m,ptr,v)`; attributes `aligned=true, op=pack`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 22

Review: Validation must precede any compress-store output write.

### `indexed_memory_contract` (6)

- `gather v:=(m,cptr,vidx,v,sImm)`; attributes `mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 21
- `scatter void:=(m,ptr,vidx,v,sImm)`; attributes `mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29
- `gather v:=(cptr,vidx,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29
- `gather_narrow v:=(cptr,cptr,sImm)`; attributes `none`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17
- `gather_narrow_partial v:=(cptr,vidx,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 18
- `scatter void:=(ptr,vidx,v,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29

Review: Bare pointers do not provide enough evidence for an honest checked twin.

### `deallocation_provenance` (1)

- `deallocate void:=(ptr)`; attributes `none`; result target `none`; reasons `raw_memory, raw_pointer`; caller-unsafe implementations 11

Review: A runtime pointer inspection cannot prove matching live allocation provenance.

### `random_output_contract` (1)

- `random_step usize:=(ptr)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 3

Review: The current status result does not establish output pointer validity.

### `raw_copy_contract` (1)

- `memory_cp void:=(ptr,cptr,s,s)`; attributes `none`; result target `none`; reasons `raw_memory, raw_pointer`; caller-unsafe implementations 34

Review: Omit the twin unless every range and overlap obligation is represented.

### `conversion_input_contract` (1)

- `load_convert_up v:=cptr+`; attributes `none`; result target `base,ToBase`; reasons `intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 74

Review: The result-target relationship determines the exact required source extent.

## Source safety-metadata completeness caveat

The existing typed metadata audit finds additional direct body/signature facts whose source-owned safety metadata is incomplete. Applying those suggestions could change generated Rust safety and is therefore intentionally outside Slice 0. The exact gap set is locked in the JSON baseline.

The 26 caller-visible gaps are:

- `tsldata/primitives/load_store/pack_expand.tsl:577` — load_convert_up avx512/si8/ToBase/si16
- `tsldata/primitives/load_store/pack_expand.tsl:590` — load_convert_up avx512/si8/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:602` — load_convert_up avx512/si8/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:622` — load_convert_up avx512/ui8/ToBase/ui16
- `tsldata/primitives/load_store/pack_expand.tsl:635` — load_convert_up avx512/ui8/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:647` — load_convert_up avx512/ui8/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:667` — load_convert_up avx512/si16/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:679` — load_convert_up avx512/si16/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:694` — load_convert_up avx512/ui16/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:706` — load_convert_up avx512/ui16/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:721` — load_convert_up avx512/si32/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:736` — load_convert_up avx512/ui32/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:751` — load_convert_up avx512/f32/ToBase/f64
- `tsldata/primitives/load_store/pack_expand.tsl:815` — load_convert_up [avx2, avx2_vl]/si8/ToBase/si16
- `tsldata/primitives/load_store/pack_expand.tsl:848` — load_convert_up [avx2, avx2_vl]/ui8/ToBase/ui16
- `tsldata/primitives/load_store/pack_expand.tsl:881` — load_convert_up [avx2, avx2_vl]/si16/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:914` — load_convert_up [avx2, avx2_vl]/ui16/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:947` — load_convert_up [avx2, avx2_vl]/si32/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:964` — load_convert_up [avx2, avx2_vl]/ui32/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:981` — load_convert_up [avx2, avx2_vl]/f32/ToBase/f64
- `tsldata/primitives/load_store/rnd_access.tsl:428` — gather sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:787` — gather_narrow_partial sve/[bword, dword]
- `tsldata/primitives/load_store/rnd_access.tsl:978` — gather_narrow sve/[bword, dword]
- `tsldata/primitives/load_store/rnd_access.tsl:1368` — gather sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:1764` — scatter sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:2272` — scatter sve/arith

## Representative declaration snapshots

These are contract snapshots, not current generated declarations. Later slices make the compiler emit them.

### C++

```cpp
template<class Vec>
[[nodiscard]] TSL_FORCE_INLINE auto extract_value_at_checked(
    typename Vec::register_type value,
    std::size_t index,
    tsl::precondition_error& error
) noexcept -> typename Vec::base_type;

template<class Vec>
[[nodiscard]] TSL_FORCE_INLINE auto div_checked(
    reg_param_t<Vec> dividend,
    reg_param_t<Vec> divisor,
    tsl::precondition_error& error
) noexcept -> typename Vec::register_type;

template<class Vec>
[[nodiscard]] TSL_FORCE_INLINE auto load_checked(
    tsl::span<const typename Vec::base_type> source,
    tsl::precondition_error& error
) noexcept -> typename Vec::register_type;
```

### Rust

```rust
pub fn extract_value_at_checked<T, const N: usize>(
    value: Simd<T, N>,
    index: usize,
) -> Result<T, PreconditionError>;

pub fn div_checked<T, const N: usize>(
    dividend: Simd<T, N>,
    divisor: Simd<T, N>,
) -> Result<Simd<T, N>, PreconditionError>;

pub fn load_checked<T, const N: usize>(
    source: &[T],
) -> Result<Simd<T, N>, PreconditionError>;
```

## C++ ABI evidence

The maintained probe is `tslc/tests/fixtures/checked_api/abi_probe.cpp`. It compiles with warnings as errors and its tests inspect out-of-line and optimized call-site assembly.

- Environment: x86-64 System V
- Compilers observed: GCC 15.2.0; Clang 21.1.8
- MSVC: not available in the Slice 0 Linux environment
- Raw return: value returned in ymm0; no value-result memory output
- Chosen value-plus-error-out: value returned in ymm0; scalar error written through rdi
- Rejected value-owning aggregate: hidden result pointer in rdi; vector value written to memory
- Rejected status-plus-value-output: status returned in eax; vector value written through rdi
- Optimized call site: immediately consumed vector result did not materialize on the stack

## Validation limits

- All-profile Rust render: not a valid census input: the current all-profile Rust request reports TSL-BACKEND-RUST-AMBIGUOUS-TARGET-PROFILES before artifact rendering.
- Census strategy: scan canonical source bodies, render assets, and emitters; obtain public caller-safety identities from the validated typed catalog.

## Maintenance

Run `PYTHONPATH=tslc/src python -m tslc.maintenance.checked_api_census` to check the exact baseline and report. After reviewing an intended evidence change, pass `--update` to accept it.
