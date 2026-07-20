//! Generated Rust benchmark runtime integration self-test.

use std::hint::black_box;

use crate::tsl_benchmark_core::{
    calibrate, candidate_order, json_escape, next_nonzero_value, next_value, Options, RawSample,
};
use crate::tsl_benchmark_policy::{
    build_policy_document, validate_policy_document, validate_report_output_paths, BuildContext,
    ReportMetadata, RUST_BACKEND_ID,
};
use crate::tsl_benchmark_reducer::{
    reduce_candidate_set, reduce_profile, validate_decisions, CandidateSetSpec, ScenarioSpec,
};

pub fn runtime_self_test() -> Result<(), String> {
    let options = Options::parse([
        "--rounds".to_string(),
        "3".to_string(),
        "--minimum-sample-ns".to_string(),
        "1".to_string(),
        "--threshold".to_string(),
        "0.05".to_string(),
        "--self-test".to_string(),
    ])?;
    if options.rounds(9) != 3
        || options.minimum_sample_ns(9) != 1
        || options.threshold() != 0.05
        || !options.self_test
    {
        return Err("benchmark option self-test failed".to_string());
    }
    if Options::parse(["--threshold".to_string(), "NaN".to_string()]).is_ok() {
        return Err("benchmark non-finite threshold self-test failed".to_string());
    }
    if Options::parse([
        "--results".to_string(),
        "output.json".to_string(),
        "--summary".to_string(),
        "./output.json".to_string(),
    ])
    .is_ok()
    {
        return Err("benchmark output-alias self-test failed".to_string());
    }
    let first_output = std::path::PathBuf::from("output.json");
    let reserved_backup =
        first_output.with_file_name(format!(".output.json.{}.0.tsl-backup", std::process::id(),));
    if validate_report_output_paths(&[&first_output, &reserved_backup]).is_ok() {
        return Err("benchmark staging-path collision self-test failed".to_string());
    }
    let mut first_state = 7;
    let mut second_state = 7;
    let first = next_value::<i16>(&mut first_state);
    if first != next_value::<i16>(&mut second_state) || first_state != second_state {
        return Err("benchmark generator self-test failed".to_string());
    }
    if next_nonzero_value::<i8>(&mut first_state) == 0 {
        return Err("benchmark nonzero generator self-test failed".to_string());
    }
    let mut order = candidate_order(3, 5)?;
    order.sort_unstable();
    if order != [0, 1, 2] {
        return Err("benchmark schedule self-test failed".to_string());
    }
    if calibrate(|iterations| Ok(iterations as u64 * 10), 35)? != 4 {
        return Err("benchmark calibration self-test failed".to_string());
    }
    if json_escape("a\n\"b\\") != "a\\n\\\"b\\\\" {
        return Err("benchmark JSON self-test failed".to_string());
    }
    reducer_self_test(&options)?;
    black_box(first);
    Ok(())
}

fn reducer_self_test(options: &Options) -> Result<(), String> {
    static CANDIDATES: [&str; 2] = ["default", "alternative"];
    static SCENARIOS: [ScenarioSpec; 2] = [
        ScenarioSpec {
            scenario: "throughput",
            rounds: 3,
            minimum_sample_ns: 1,
        },
        ScenarioSpec {
            scenario: "latency",
            rounds: 3,
            minimum_sample_ns: 1,
        },
    ];
    let spec = CandidateSetSpec {
        stable_id: "self",
        candidates: &CANDIDATES,
        scenarios: &SCENARIOS,
        policy_supported: true,
    };
    let make_samples = |throughput: [u64; 3], latency: [u64; 3]| {
        let mut result = Vec::new();
        for (scenario, alternatives) in [("throughput", throughput), ("latency", latency)] {
            for (round, elapsed_ns) in alternatives.into_iter().enumerate() {
                result.push(RawSample {
                    stable_id: "self",
                    scenario,
                    candidate: "default",
                    round,
                    iterations: 1,
                    elapsed_ns: 100,
                });
                result.push(RawSample {
                    stable_id: "self",
                    scenario,
                    candidate: "alternative",
                    round,
                    iterations: 1,
                    elapsed_ns,
                });
            }
        }
        result
    };
    let stable = make_samples([80, 80, 80], [80, 80, 80]);
    let stable_decision = reduce_candidate_set(&spec, &stable, options)?;
    if stable_decision.selected != "alternative" || stable_decision.status != "selected" {
        return Err("stable reducer self-test failed".to_string());
    }
    let report_only_spec = CandidateSetSpec {
        policy_supported: false,
        ..spec
    };
    let report_only = reduce_profile(&[report_only_spec], &stable, options)?;
    if report_only[0].selected != "default"
        || report_only[0].status != "report_only"
        || report_only[0].minimum_improvement != 0.0
    {
        return Err("report-only reducer self-test failed".to_string());
    }
    let conflicting =
        reduce_candidate_set(&spec, &make_samples([80, 80, 80], [120, 120, 120]), options)?;
    let noisy = reduce_candidate_set(&spec, &make_samples([80, 120, 40], [80, 80, 80]), options)?;
    if conflicting.selected != "default" || noisy.selected != "default" {
        return Err("conservative reducer self-test failed".to_string());
    }
    let mut zero = stable.clone();
    zero[0].elapsed_ns = 0;
    if reduce_candidate_set(&spec, &zero, options).is_ok() {
        return Err("zero-duration reducer self-test failed".to_string());
    }
    let mut duplicate = stable.clone();
    duplicate[1] = duplicate[0].clone();
    if reduce_candidate_set(&spec, &duplicate, options).is_ok() {
        return Err("duplicate reducer self-test failed".to_string());
    }
    let mut unknown_scenario = stable.clone();
    unknown_scenario[0].scenario = "unknown";
    if reduce_candidate_set(&spec, &unknown_scenario, options).is_ok() {
        return Err("unknown-scenario reducer self-test failed".to_string());
    }
    let mut unknown_candidate = stable.clone();
    unknown_candidate[0].candidate = "unknown";
    if reduce_candidate_set(&spec, &unknown_candidate, options).is_ok() {
        return Err("unknown-candidate reducer self-test failed".to_string());
    }
    let short_options = Options::parse([
        "--rounds".to_string(),
        "3".to_string(),
        "--minimum-sample-ns".to_string(),
        "1".to_string(),
    ])?;
    if reduce_candidate_set(&spec, &stable[..8], &short_options).is_ok() {
        return Err("incomplete reducer self-test failed".to_string());
    }

    let context = BuildContext {
        rustc_verbose_version: "rustc self-test",
        cargo_verbose_version: "cargo self-test",
        host: "x86_64-self",
        target: "x86_64-self",
        linker: "self-linker",
        rustc_wrapper: "",
        rustc_workspace_wrapper: "",
        target_cpu: "self",
        target_features: "sse,sse2",
        cargo_features: "SSE2;VARIANT_BENCHMARKS",
        cargo_profile: "bench",
        opt_level: "3",
        debug_assertions: "false",
        overflow_checks: "false",
        lto: "false",
        codegen_units: "1",
        panic: "unwind",
        incremental: "0",
        debug: "false",
        rustflags: "",
        encoded_rustflags: "-Copt-level=3\u{1f}-Ccodegen-units=1",
        profile_overrides: "CARGO_INCREMENTAL=0",
        benchmark_codegen_contract: "profile.bench.v1",
        external_context: "self-context",
    };
    let metadata = ReportMetadata {
        policy_schema_version: 2,
        protocol_version: 1,
        backend: RUST_BACKEND_ID,
        profile: "self",
        manifest_hash: "self-manifest",
        required_features: "sse,sse2",
        required_rustflags: &["-Copt-level=3", "-Ccodegen-units=1"],
        required_incremental_environment: "0",
        build_context: context,
    };
    let mut incomplete_context = context;
    incomplete_context.external_context = "";
    if build_policy_document(
        &[spec],
        &[stable_decision.clone()],
        ReportMetadata {
            build_context: incomplete_context,
            ..metadata
        },
        options,
        "x86:SelfVendor12:6:1:1".to_string(),
    )
    .is_ok()
    {
        return Err("missing-context policy self-test failed".to_string());
    }
    let mut wrapper_context = context;
    wrapper_context.rustc_wrapper = "wrapper";
    if build_policy_document(
        &[spec],
        &[stable_decision.clone()],
        ReportMetadata {
            build_context: wrapper_context,
            ..metadata
        },
        options,
        "x86:SelfVendor12:6:1:1".to_string(),
    )
    .is_ok()
    {
        return Err("compiler-wrapper policy self-test failed".to_string());
    }
    let mut policy = build_policy_document(
        &[spec],
        &[stable_decision.clone()],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1".to_string(),
    )?;
    policy.backend = "cpp".to_string();
    if validate_policy_document(
        &policy,
        &[spec],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1",
    )
    .is_ok()
    {
        return Err("foreign policy self-test failed".to_string());
    }
    policy.backend = RUST_BACKEND_ID.to_string();
    policy.profile = "other-profile".to_string();
    if validate_policy_document(
        &policy,
        &[spec],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1",
    )
    .is_ok()
    {
        return Err("wrong-profile policy self-test failed".to_string());
    }
    policy.profile = metadata.profile.to_string();
    policy.manifest_hash = "stale".to_string();
    if validate_policy_document(
        &policy,
        &[spec],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1",
    )
    .is_ok()
    {
        return Err("stale policy self-test failed".to_string());
    }
    policy.manifest_hash = metadata.manifest_hash.to_string();
    policy.tune_context.build.rustc_verbose_version = "other rustc";
    if validate_policy_document(
        &policy,
        &[spec],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1",
    )
    .is_ok()
    {
        return Err("wrong-context policy self-test failed".to_string());
    }
    policy = build_policy_document(
        &[spec],
        &[stable_decision.clone()],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1".to_string(),
    )?;
    policy.cpu_id = "x86:OtherVendor1:6:1:1".to_string();
    if validate_policy_document(
        &policy,
        &[spec],
        metadata,
        options,
        "x86:SelfVendor12:6:1:1",
    )
    .is_ok()
    {
        return Err("wrong-CPU policy self-test failed".to_string());
    }
    let second_spec = CandidateSetSpec {
        stable_id: "self-second",
        ..spec
    };
    if validate_decisions(
        &[spec, second_spec],
        &[stable_decision.clone(), stable_decision],
        options.threshold(),
    )
    .is_ok()
    {
        return Err("duplicate-decision policy self-test failed".to_string());
    }
    Ok(())
}
