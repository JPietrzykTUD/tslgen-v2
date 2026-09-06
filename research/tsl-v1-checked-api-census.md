# TSL v1 checked-API baseline census

This generated maintenance report tracks the reviewed evidence at the current checked-API migration checkpoint. Its lexical runtime-site scan is tooling evidence only; production semantics must come from typed source/catalog facts and finalized backend plans.

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

- Exact generated runtime-failure sites: 154
- Exact typed public callable identities with at least one `caller_unsafe` implementation: 33
- Checked source-contract coverage gaps among those identities: 14
- Applicable source safety-metadata gaps: 138 (26 require caller unsafety)

Runtime sites by classification:

- dynamic precondition: 6
- implementation hazard: 8
- static well-formedness constraint: 22
- tooling-only validation: 118

## Reviewed semantic families

| Family | Classification | Backend consequence | Complete-check feasibility |
| --- | --- | --- | --- |
| `tooling_only` | tooling-only validation | Failure is confined to generated tests, builds, documentation stubs, or benchmarks. | not applicable |
| `static_representation_or_lane_shape` | static well-formedness constraint | C++ or Rust currently diagnoses an impossible compiler-selected representation at runtime. | no checked twin; validate statically |
| `static_immediate_nonzero` | static well-formedness constraint | Rust emits a const assertion; invalid authored immediates do not reach a call. | no checked twin; keep a compile-time diagnostic |
| `integer_zero_divisor` | dynamic precondition | Unchecked C++ and unsafe Rust assume nonzero active integer divisors; checked companions report a typed zero-divisor error before invocation. | implemented for runtime integer division/remainder; checks active divisor lanes |
| `lane_index` | dynamic precondition | Rust facade calls panic today; an unchecked C++ or Rust primitive may access outside its logical lanes. | complete from the runtime index and typed logical lane count |
| `contiguous_extent` | dynamic precondition | Rust slice facades panic when a contiguous input or output is too short. | complete with a valid slice/span signature; not honest for a bare pointer |
| `algorithm_equal_extents` | dynamic precondition | Unchecked C++ and unsafe Rust algorithms assume that every secondary range covers the driving extent; checked companions report insufficient input. | implemented from the checked algorithm's range or slice arguments |
| `algorithm_output_capacity` | dynamic precondition | Unchecked C++ and unsafe Rust algorithms assume sufficient output/index capacity; checked companions report insufficient output. | implemented from the checked algorithm's input and output ranges |
| `algorithm_mask_capacity` | dynamic precondition | Unchecked C++ and unsafe Rust algorithms assume sufficient mask storage; checked companions report insufficient input or output. | implemented from the input extent, mask layout, lane count, and mask range |
| `algorithm_selected_index` | dynamic precondition | Unchecked C++ and unsafe Rust selected-row algorithms assume valid scaled addresses; checked companions report overflow, misalignment, or an out-of-bounds index. | implemented by validating every selected address before kernel dispatch |
| `implementation_exhaustiveness` | implementation hazard | Rust panics if compiler-selected scalar cast types escape the supported closed set. | no checked twin; repair typed validation/exhaustiveness |
| `implementation_invariant` | implementation hazard | A debug assertion or unwrap fails if an internal compiler-owned invariant is broken. | no checked twin; retain or replace with compiler validation |
| `contiguous_memory_contract` | dynamic precondition | Raw C++ pointers remain unchecked; Rust public exposure must be unsafe until a safe slice wrapper discharges the contract. | requires a span/slice carrying readable or writable extent and selected alignment |
| `mask_memory_contract` | dynamic precondition | Raw mask representation loads/stores have the same pointer hazard plus layout-dependent capacity. | requires a span/slice and a typed mask-layout capacity plan |
| `selected_memory_contract` | dynamic precondition | Expand/compress operations may access a mask-dependent number of elements. | implemented for compress-store and expand-load from a range plus capacity derived from the active mask |
| `indexed_memory_contract` | dynamic precondition | Gather/scatter paths may access invalid addresses for active indices. | implemented for vector-index gather/scatter, including partial narrow gather, from a valid base view, typed scale, and active-index validation; pointer-indexed narrow gather remains omitted |
| `deallocation_provenance` | dynamic precondition | Mismatched, dead, or foreign allocation provenance can cause undefined behavior. | no honest pointer-only checked twin; design an owning allocation API separately |
| `random_output_contract` | dynamic precondition | The random-step intrinsic writes through a raw output pointer on success. | requires a mutable reference/view, or an owning optional/result value API |
| `raw_copy_contract` | dynamic precondition | Invalid ranges or prohibited overlap can cause undefined behavior or corruption. | requires valid source/destination views plus an explicit overlap contract/check |
| `conversion_input_contract` | dynamic precondition | Widening loads read multiple source elements through a raw pointer. | requires a source span/slice with the lowering-resolved element count |

## Exact generated runtime sites

### `tooling_only` (118)

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
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:43` — owner `explicit_and_convenience_dispatch_match` — `assert_eq` — `assert_eq!(convenient, explicit);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:42` — owner `explicit_and_convenience_dispatch_match` — `assert_eq` — `assert_eq!(explicit, [9_i32; 8]);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:38` — owner `explicit_and_convenience_dispatch_match` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:40` — owner `explicit_and_convenience_dispatch_match` — `unwrap` — `.unwrap();`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:57` — owner `mutable_user_operation_state_is_preserved` — `assert_eq` — `assert_eq!(output, [9_i32; 8]);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:58` — owner `mutable_user_operation_state_is_preserved` — `assert` — `assert!(operation.applications > 0);`
- `tslc/src/tslc/backend/assets/rust_dispatch_external_test.rs.tmpl:55` — owner `mutable_user_operation_state_is_preserved` — `unwrap` — `.unwrap();`
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
- `tslc/src/tslc/backend/rust_documentation_api.py:117` — owner `documentation_checked_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:228` — owner `documentation_free_function` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:208` — owner `documentation_overloaded_checked_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:152` — owner `documentation_overloaded_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/backend/rust_documentation_api.py:58` — owner `documentation_wrapper` — `unimplemented` — `" unimplemented!()\n"`
- `tslc/src/tslc/benchmark/render_cpp.py:229` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy has an unterminated decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:233` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy selects an unavailable candidate for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:226` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy repeats a decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp.py:224` — owner `_render_policy_read` — `throw` — `throw std::runtime_error("policy has no decision for " + std::string({stable_id}));`
- `tslc/src/tslc/benchmark/render_cpp_scenarios.py:469` — owner `_render_measure_dispatch` — `throw` — `default: throw std::runtime_error("invalid candidate index");`
- `tslc/src/tslc/render/rust_dispatch.py:579` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(ENTRY_CALLS.load(Ordering::SeqCst), 2);",`
- `tslc/src/tslc/render/rust_dispatch.py:599` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(HARDWARE_ENTRY_CALLS.load(Ordering::SeqCst), 0);",`
- `tslc/src/tslc/render/rust_dispatch.py:566` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:578` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(SELECTION_CALLS.load(Ordering::SeqCst), 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:580` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(output, [9 as TestElement; 8]);",`
- `tslc/src/tslc/render/rust_dispatch.py:598` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(output, [9 as TestElement; 8]);",`
- `tslc/src/tslc/render/rust_dispatch.py:565` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(detector.detect_calls, 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:577` — owner `_unit_tests` — `assert_eq` — `" assert_eq!(detector.detect_calls, 1);",`
- `tslc/src/tslc/render/rust_dispatch.py:529` — owner `_unit_tests` — `assert_eq` — `f" assert_eq!(table.{field}, {entry.entry_index});",`
- `tslc/src/tslc/render/rust_dispatch.py:521` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/render/rust_dispatch.py:558` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/render/rust_dispatch.py:585` — owner `_unit_tests` — `expect` — `' let _guard = TEST_LOCK.lock().expect("dispatch test lock");',`
- `tslc/src/tslc/render/rust_dispatch.py:571` — owner `_unit_tests` — `unwrap` — `"ops::Add, &left, &right, &mut output).unwrap();"`
- `tslc/src/tslc/render/rust_dispatch.py:575` — owner `_unit_tests` — `unwrap` — `"ops::Add, &left, &right, &mut output).unwrap();"`
- `tslc/src/tslc/render/rust_dispatch.py:596` — owner `_unit_tests` — `unwrap` — `"ops::Add, &left, &right, &mut output).unwrap();"`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:35` — owner `_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:473` — owner `_differential` — `assert_eq` — `f" for i in 0..{case.lanes} {{ assert_eq!("`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:481` — owner `_differential` — `assert` — `" assert!(hw.lane_eq(reference), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:494` — owner `_differential` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(hw[i].{comparison}(reference[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:289` — owner `_extension_extract` — `assert` — `f" for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:324` — owner `_extension_insert` — `assert` — `f" for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:364` — owner `_extension_result` — `assert` — `f" for i in 0..{expected_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:259` — owner `_fixed_extension_load_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:194` — owner `_fixed_extension_repr_cast` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:115` — owner `_lane_convert` — `assert` — `f" for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:227` — owner `_load_convert` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:66` — owner `_repr_cast` — `assert` — `f" for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py:161` — owner `_target_imask` — `assert_eq` — `f' assert_eq!(result, expected, "{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:448` — owner `_checked_precondition` — `assert` — `f" assert!(matches!(result, Err({error})), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:67` — owner `_generic_golden` — `assert_eq` — `f" for i in 0..{case.lanes} {{ assert_eq!(mask_bit(result as u64, i), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:509` — owner `_lane_assert` — `assert` — `f" for i in 0..{lanes} {{ assert!({result_name}[i].{comparison}(expected[i]), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:267` — owner `_mask_logic` — `assert_eq` — `f" assert_eq!(mask_bit(result as u64, {lane}), {bit}, "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:240` — owner `_mask_result` — `assert_eq` — `f" assert_eq!(mask_bit(result as u64, {lane}), {bit}, "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:320` — owner `_mask_store` — `assert` — `f" for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), ",`
- `tslc/src/tslc/value_tests/_render_rust_core.py:394` — owner `_reduction` — `assert` — `f" assert!(result.lane_eq(expected), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:474` — owner `_runtime_failure` — `assert_eq` — `f' assert_eq!(message, Some("{marker}"), "{case.case_name}: wrong panic payload");',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:470` — owner `_runtime_failure` — `panic` — `f' Ok(_) => panic!("{case.case_name}: expected integer-zero-divisor panic"),',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:349` — owner `_scalar_result` — `assert` — `f" assert!(result.lane_eq(expected), "`
- `tslc/src/tslc/value_tests/_render_rust_core.py:495` — owner `_status_pointer` — `assert_eq` — `f' assert_eq!(value, before, "{case.case_name}: failure modified output");',`
- `tslc/src/tslc/value_tests/_render_rust_core.py:493` — owner `_status_pointer` — `assert` — `f' assert!(status <= 1, "{case.case_name}: invalid status {{status}}");',`
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

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6730` — owner `aggregate_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:5041` — owner `aggregate_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4921` — owner `aggregate_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6654` — owner `aggregate_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::aggregate_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6370` — owner `consume_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4792` — owner `consume_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4675` — owner `consume_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6301` — owner `consume_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::consume_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:869` — owner `for_each_chunk_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::for_each_chunk requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6220` — owner `transform_binary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4538` — owner `transform_selected_binary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_selected_binary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:4404` — owner `transform_selected_unary_scaled_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_selected_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:6134` — owner `transform_unary_raw` — `assert` — `assert!( lanes > 0, "tsl::algo::transform_unary requires a vector with at least one lane", );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:662` — owner `validate_integral_mask_vector` — `assert` — `assert!( lanes <= <V::ImaskType as IntegralMaskWord>::BITS, "{} requires an integral mask storage type with at least one bit per lane", helper_name, );`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:657` — owner `validate_integral_mask_vector` — `assert` — `assert!( lanes > 0, "{} requires a vector with at least one lane", helper_name, );`
- `tslc/src/tslc/backend/assets/tsl_core.hpp:508` — owner `require_same_lanes` — `throw` — `throw std::invalid_argument( "lane-preserving conversion requires equal source and target lane counts" );`
- `tslc/src/tslc/backend/assets/tsl_core.hpp:506` — owner `require_same_lanes` — `trap` — `__builtin_trap();`
- `tslc/src/tslc/backend/assets/tsl_core.rs:290` — owner `bit_cast` — `assert_eq` — `assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());`
- `tslc/src/tslc/backend/assets/tsl_core.rs:304` — owner `reinterpret_unchecked` — `assert_eq` — `assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());`
- `tslc/src/tslc/backend/assets/tsl_core.rs:753` — owner `require_same_lanes` — `assert_eq` — `assert_eq!( source_lanes, target_lanes, "lane-preserving conversion requires equal source and target lane counts" );`

### `static_immediate_nonzero` (2)

The operand is an immediate rather than caller-controlled runtime data.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:680` — owner `selected_row_scale` — `assert` — `assert!(scale > 0, "tsl::algo selected-row scale must be nonzero");`
- `tslc/src/tslc/backend/rust_signatures.py:139` — owner `_arithmetic_precondition` — `assert` — `f"const {{ assert!(({precondition.parameter_name} as "`

### `lane_index` (4)

Total operations such as test_imask remain excluded when out-of-range has defined semantics.

- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:157` — owner `lane` — `assert` — `assert!(index < N, "lane index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:170` — owner `set_lane` — `assert` — `assert!(index < N, "lane index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:345` — owner `set` — `assert` — `assert!(index < N, "mask index {index} is out of bounds for {N} lanes");`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:333` — owner `test` — `assert` — `assert!(index < N, "mask index {index} is out of bounds for {N} lanes");`

### `contiguous_extent` (2)

The checked signature must establish an addressable extent.

- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:219` — owner `copy_to_slice` — `assert` — `assert!( destination.len() >= N, "destination slice has {} elements but {N} are required", destination.len() );`
- `tslc/src/tslc/backend/assets/rust_facade.rs.tmpl:186` — owner `from_slice` — `assert` — `assert!( source.len() >= N, "source slice has {} elements but {N} are required", source.len() );`

### `implementation_exhaustiveness` (5)

This is a compiler/backend defect if reachable, not invalid caller data.

- `tslc/src/tslc/backend/assets/tsl_core.rs:1137` — owner `saturating_cast_value` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:1094` — owner `saturating_from_f64` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:1009` — owner `saturating_from_i128` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:1052` — owner `saturating_from_u128` — `panic` — `panic!("unsupported saturating cast")`
- `tslc/src/tslc/backend/assets/tsl_core.rs:966` — owner `scalar_as_cast_value` — `panic` — `panic!("unsupported scalar-as cast")`

### `implementation_invariant` (3)

The condition is not part of the public call domain.

- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:146` — owner `lane_is_set` — `debug_assert` — `debug_assert!(lane < <Self as IntegralMaskWord>::BITS);`
- `tslc/src/tslc/backend/assets/tsl_algorithm.rs:133` — owner `one_at` — `debug_assert` — `debug_assert!(lane < <Self as IntegralMaskWord>::BITS);`
- `tslc/src/tslc/backend/assets/tsl_core.rs:734` — owner `ostream_write` — `unwrap` — `.unwrap()`

## Typed `caller_unsafe` public paths

These identities come from `Catalog` and `ImplementationSafety`, not target-text inspection. A family records whether a future checked form can be honest; it does not itself authorize generation.

### `contiguous_memory_contract` (13)

- `load v:=(m,cptr,v)`; attributes `aligned=false, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `store void:=(m,ptr,v)`; attributes `aligned=false, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load v:=(m,cptr)`; attributes `aligned=false, mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load v:=cptr`; attributes `aligned=false`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 22; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load_scalar s:=cptr`; attributes `aligned=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 15; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice carrying readable or writable extent and selected alignment
- `store void:=(ptr,s)`; attributes `aligned=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 14; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `store void:=(ptr,v)`; attributes `aligned=false`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 26; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load v:=(m,cptr,v)`; attributes `aligned=true, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `store void:=(m,ptr,v)`; attributes `aligned=true, mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load v:=(m,cptr)`; attributes `aligned=true, mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 24; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `load v:=cptr`; attributes `aligned=true`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 22; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `store void:=(ptr,s)`; attributes `aligned=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 14; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning
- `store void:=(ptr,v)`; attributes `aligned=true`; result target `none`; reasons `compiler_builtin, intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 26; checked source status `declared`; preconditions `contiguous_memory_extent, selected_memory_alignment`; coverage: source preconditions are available for backend check planning

Review: A pointer and caller-claimed count cannot establish lifetime or provenance.

### `mask_memory_contract` (8)

- `load_mask_repr m:=cptr`; attributes `aligned=false, packed=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=false, packed=false`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `load_mask_repr m:=cptr`; attributes `aligned=false, packed=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=false, packed=true`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `load_mask_repr m:=cptr`; attributes `aligned=true, packed=false`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=true, packed=false`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `load_mask_repr m:=cptr`; attributes `aligned=true, packed=true`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan
- `store_mask_repr void:=(ptr,m)`; attributes `aligned=true, packed=true`; result target `none`; reasons `compiler_builtin, raw_memory, raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: requires a span/slice and a typed mask-layout capacity plan

Review: Packed and lane-mask representations require different element counts.

### `selected_memory_contract` (2)

- `expand_load v:=(m,cptr)`; attributes `aligned=true, op=expand`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 20; checked source status `declared`; preconditions `compacted_memory_extent`; coverage: source preconditions are available for backend check planning
- `compress_store void:=(m,ptr,v)`; attributes `aligned=true, op=pack`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 22; checked source status `declared`; preconditions `compacted_memory_extent`; coverage: source preconditions are available for backend check planning

Review: Validation must precede any compress-store output write.

### `indexed_memory_contract` (6)

- `gather v:=(m,cptr,vidx,v,sImm)`; attributes `mask=pass_through`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 21; checked source status `declared`; preconditions `indexed_memory_address_valid`; coverage: source preconditions are available for backend check planning
- `scatter void:=(m,ptr,vidx,v,sImm)`; attributes `mask=zero`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29; checked source status `declared`; preconditions `indexed_memory_address_valid`; coverage: source preconditions are available for backend check planning
- `gather v:=(cptr,vidx,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29; checked source status `declared`; preconditions `indexed_memory_address_valid`; coverage: source preconditions are available for backend check planning
- `gather_narrow v:=(cptr,cptr,sImm)`; attributes `none`; result target `none`; reasons `raw_pointer`; caller-unsafe implementations 17; checked source status `coverage_gap`; preconditions `none`; coverage: implemented for vector-index gather/scatter, including partial narrow gather, from a valid base view, typed scale, and active-index validation; pointer-indexed narrow gather remains omitted
- `gather_narrow_partial v:=(cptr,vidx,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 18; checked source status `declared`; preconditions `indexed_memory_address_valid`; coverage: source preconditions are available for backend check planning
- `scatter void:=(ptr,vidx,v,sImm)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 29; checked source status `declared`; preconditions `indexed_memory_address_valid`; coverage: source preconditions are available for backend check planning

Review: Pointer-indexed narrow gather requires a second extent-carrying index view before an honest checked twin can be emitted.

### `deallocation_provenance` (1)

- `deallocate void:=(ptr)`; attributes `none`; result target `none`; reasons `raw_memory, raw_pointer`; caller-unsafe implementations 11; checked source status `coverage_gap`; preconditions `none`; coverage: no honest pointer-only checked twin; design an owning allocation API separately

Review: A runtime pointer inspection cannot prove matching live allocation provenance.

### `random_output_contract` (1)

- `random_step usize:=(ptr)`; attributes `none`; result target `none`; reasons `intrinsic, raw_pointer`; caller-unsafe implementations 3; checked source status `coverage_gap`; preconditions `none`; coverage: requires a mutable reference/view, or an owning optional/result value API

Review: The current status result does not establish output pointer validity.

### `raw_copy_contract` (1)

- `memory_cp void:=(ptr,cptr,s,s)`; attributes `none`; result target `none`; reasons `raw_memory, raw_pointer`; caller-unsafe implementations 34; checked source status `coverage_gap`; preconditions `none`; coverage: requires valid source/destination views plus an explicit overlap contract/check

Review: Omit the twin unless every range and overlap obligation is represented.

### `conversion_input_contract` (1)

- `load_convert_up v:=cptr+`; attributes `none`; result target `base,ToBase`; reasons `intrinsic, raw_memory, raw_pointer`; caller-unsafe implementations 74; checked source status `coverage_gap`; preconditions `none`; coverage: requires a source span/slice with the lowering-resolved element count

Review: The result-target relationship determines the exact required source extent.

## Source safety-metadata completeness caveat

The existing typed metadata audit finds additional direct body/signature facts whose source-owned safety metadata is incomplete. Applying those suggestions could change generated Rust safety and is therefore intentionally outside Slice 0. The exact gap set is locked in the JSON baseline.

The 26 caller-visible gaps are:

- `tsldata/primitives/load_store/pack_expand.tsl:594` — load_convert_up avx512/si8/ToBase/si16
- `tsldata/primitives/load_store/pack_expand.tsl:607` — load_convert_up avx512/si8/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:619` — load_convert_up avx512/si8/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:639` — load_convert_up avx512/ui8/ToBase/ui16
- `tsldata/primitives/load_store/pack_expand.tsl:652` — load_convert_up avx512/ui8/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:664` — load_convert_up avx512/ui8/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:684` — load_convert_up avx512/si16/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:696` — load_convert_up avx512/si16/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:711` — load_convert_up avx512/ui16/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:723` — load_convert_up avx512/ui16/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:738` — load_convert_up avx512/si32/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:753` — load_convert_up avx512/ui32/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:768` — load_convert_up avx512/f32/ToBase/f64
- `tsldata/primitives/load_store/pack_expand.tsl:832` — load_convert_up [avx2, avx2_vl]/si8/ToBase/si16
- `tsldata/primitives/load_store/pack_expand.tsl:865` — load_convert_up [avx2, avx2_vl]/ui8/ToBase/ui16
- `tsldata/primitives/load_store/pack_expand.tsl:898` — load_convert_up [avx2, avx2_vl]/si16/ToBase/si32
- `tsldata/primitives/load_store/pack_expand.tsl:931` — load_convert_up [avx2, avx2_vl]/ui16/ToBase/ui32
- `tsldata/primitives/load_store/pack_expand.tsl:964` — load_convert_up [avx2, avx2_vl]/si32/ToBase/si64
- `tsldata/primitives/load_store/pack_expand.tsl:981` — load_convert_up [avx2, avx2_vl]/ui32/ToBase/ui64
- `tsldata/primitives/load_store/pack_expand.tsl:998` — load_convert_up [avx2, avx2_vl]/f32/ToBase/f64
- `tsldata/primitives/load_store/rnd_access.tsl:437` — gather sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:805` — gather_narrow_partial sve/[bword, dword]
- `tsldata/primitives/load_store/rnd_access.tsl:996` — gather_narrow sve/[bword, dword]
- `tsldata/primitives/load_store/rnd_access.tsl:1397` — gather sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:1803` — scatter sve/arith
- `tsldata/primitives/load_store/rnd_access.tsl:2322` — scatter sve/arith

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
