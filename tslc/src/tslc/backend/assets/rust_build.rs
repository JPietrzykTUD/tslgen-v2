use std::process::Command;

#[path = "src/tsl_rust_cpu_identity.rs"]
mod tsl_rust_cpu_identity;
@{policy_modules}
#[path = "tsl_rust_policy_json.rs"]
mod tsl_rust_policy_json;
#[path = "tsl_rust_variant_policy_protocol.rs"]
mod tsl_rust_variant_policy_protocol;
#[path = "tsl_rust_variant_policy_validation.rs"]
mod tsl_rust_variant_policy_validation;
#[path = "tsl_rust_variant_policy.rs"]
mod tsl_rust_variant_policy;

use tsl_rust_variant_policy::{BuildContext, GeneratedProfile};

const POLICY_ENVIRONMENT: &str = "TSL_RUST_VARIANT_POLICY_FILE";
const BENCHMARK_CODEGEN_CONTRACT: &str = "@{benchmark_codegen_contract}";
const POLICY_PROFILES: &[GeneratedProfile] = @{policy_profiles};

const TRACKED_ENVIRONMENT: &[&str] = &[
    "CARGO",
    "RUSTC",
    "RUSTC_LINKER",
    "RUSTC_WRAPPER",
    "RUSTC_WORKSPACE_WRAPPER",
    "RUSTFLAGS",
    "CARGO_ENCODED_RUSTFLAGS",
    "CARGO_CFG_PANIC",
    "PROFILE",
    "OPT_LEVEL",
    "DEBUG",
    "CARGO_INCREMENTAL",
    "CARGO_BUILD_INCREMENTAL",
    "CARGO_PROFILE_BENCH_OPT_LEVEL",
    "CARGO_PROFILE_BENCH_DEBUG",
    "CARGO_PROFILE_BENCH_DEBUG_ASSERTIONS",
    "CARGO_PROFILE_BENCH_OVERFLOW_CHECKS",
    "CARGO_PROFILE_BENCH_LTO",
    "CARGO_PROFILE_BENCH_PANIC",
    "CARGO_PROFILE_BENCH_INCREMENTAL",
    "CARGO_PROFILE_BENCH_CODEGEN_UNITS",
    "CARGO_PROFILE_BENCH_RPATH",
    "CARGO_PROFILE_BENCH_STRIP",
    "CARGO_PROFILE_BENCH_SPLIT_DEBUGINFO",
    "CARGO_PROFILE_BENCH_PACKAGE_TSL_OPT_LEVEL",
    "CARGO_PROFILE_BENCH_PACKAGE_TSL_DEBUG",
    "CARGO_PROFILE_BENCH_PACKAGE_TSL_DEBUG_ASSERTIONS",
    "CARGO_PROFILE_BENCH_PACKAGE_TSL_OVERFLOW_CHECKS",
    "CARGO_PROFILE_BENCH_PACKAGE_TSL_CODEGEN_UNITS",
    "TSL_RUST_BENCHMARK_CONTEXT",
];

fn main() {
    println!("cargo::rustc-check-cfg=cfg(tsl_value_tests)");
    println!("cargo::rustc-check-cfg=cfg(tsl_variant_benchmarks)");
    println!("cargo:rerun-if-env-changed={POLICY_ENVIRONMENT}");
    for name in [
        "HOST",
        "TARGET",
        "CARGO_CFG_TARGET_ARCH",
        "CARGO_CFG_TARGET_FEATURE",
    ] {
        println!("cargo:rerun-if-env-changed={}", name);
    }
    let host = required("HOST");
    let target = required("TARGET");
    emit("TSL_BUILD_HOST", &host);
    emit("TSL_BUILD_TARGET", &target);

    let benchmark_enabled = std::env::var_os("CARGO_FEATURE_VARIANT_BENCHMARKS").is_some();
    let policy_input = std::env::var_os(POLICY_ENVIRONMENT);
    if policy_input.is_some() {
        emit("TSL_RUST_VARIANT_POLICY_ACTIVE", "1");
    }
    let out_dir = required("OUT_DIR");
    if policy_input.is_none() {
        tsl_rust_variant_policy::materialize_default_mapping(
            std::path::Path::new(&out_dir),
            POLICY_PROFILES,
        )
        .unwrap_or_else(|error| panic!("Rust authored-default mapping failed: {error}"));
    }
    if benchmark_enabled || policy_input.is_some() {
        force_context_revalidation(std::path::Path::new(&out_dir));
    }
    if !benchmark_enabled && policy_input.is_none() {
        return;
    }
    for name in TRACKED_ENVIRONMENT {
        println!("cargo:rerun-if-env-changed={}", name);
    }

    let rustc = required("RUSTC");
    let cargo = required("CARGO");
    let target_linker_key = format!(
        "CARGO_TARGET_{}_LINKER",
        target.replace('-', "_").to_ascii_uppercase(),
    );
    println!("cargo:rerun-if-env-changed={target_linker_key}");

    let rustc_verbose = command_verbose_version(&rustc, "rustc");
    let cargo_verbose = command_verbose_version(&cargo, "cargo");

    let linker = std::env::var("RUSTC_LINKER")
        .or_else(|_| std::env::var(&target_linker_key))
        .unwrap_or_else(|_| "rustc-default".to_string());
    let rustflags = optional("RUSTFLAGS");
    let encoded_rustflags = optional("CARGO_ENCODED_RUSTFLAGS");
    let target_features = optional("CARGO_CFG_TARGET_FEATURE");
    let target_cpu = rustflag_value(&rustflags, &encoded_rustflags, "target-cpu")
        .unwrap_or_else(|| "rustc-default".to_string());
    let cargo_features = cargo_features();
    let profile_overrides = profile_overrides();
    let cargo_incremental = optional("CARGO_INCREMENTAL");
    let cargo_build_incremental = optional("CARGO_BUILD_INCREMENTAL");
    let incremental = if !cargo_incremental.is_empty() {
        cargo_incremental
    } else if !cargo_build_incremental.is_empty() {
        cargo_build_incremental
    } else {
        profile_setting("INCREMENTAL", "@{default_incremental}")
    };
    let context = BuildContext {
        rustc_verbose_version: rustc_verbose,
        cargo_verbose_version: cargo_verbose,
        host,
        target,
        linker,
        rustc_wrapper: optional("RUSTC_WRAPPER"),
        rustc_workspace_wrapper: optional("RUSTC_WORKSPACE_WRAPPER"),
        target_cpu,
        target_features,
        cargo_features,
        cargo_profile: required("PROFILE"),
        opt_level: required("OPT_LEVEL"),
        debug_assertions: profile_setting("DEBUG_ASSERTIONS", "@{default_debug_assertions}"),
        overflow_checks: profile_setting("OVERFLOW_CHECKS", "@{default_overflow_checks}"),
        lto: profile_setting("LTO", "@{default_lto}"),
        codegen_units: profile_setting("CODEGEN_UNITS", "@{default_codegen_units}"),
        panic: optional("CARGO_CFG_PANIC"),
        incremental,
        debug: required("DEBUG"),
        rustflags,
        encoded_rustflags,
        profile_overrides,
        benchmark_codegen_contract: BENCHMARK_CODEGEN_CONTRACT.to_string(),
        external_context: optional("TSL_RUST_BENCHMARK_CONTEXT"),
    };

    if benchmark_enabled {
        emit_benchmark_context(&context);
    }
    if let Some(policy_input) = policy_input {
        let manifest_dir = required("CARGO_MANIFEST_DIR");
        tsl_rust_variant_policy::consume_policy(
            policy_input,
            std::path::Path::new(&manifest_dir),
            std::path::Path::new(&out_dir),
            &context,
            POLICY_PROFILES,
        )
        .unwrap_or_else(|error| panic!("Rust variant policy validation failed: {error}"));
    }
}

fn emit_benchmark_context(context: &BuildContext) {
    emit("TSL_RUSTC_VERBOSE_VERSION", &context.rustc_verbose_version);
    emit("TSL_CARGO_VERBOSE_VERSION", &context.cargo_verbose_version);
    emit("TSL_RUST_LINKER", &context.linker);
    emit("TSL_RUSTC_WRAPPER", &context.rustc_wrapper);
    emit(
        "TSL_RUSTC_WORKSPACE_WRAPPER",
        &context.rustc_workspace_wrapper,
    );
    emit("TSL_RUST_TARGET_CPU", &context.target_cpu);
    emit("TSL_RUST_TARGET_FEATURES", &context.target_features);
    emit("TSL_RUST_CARGO_FEATURES", &context.cargo_features);
    emit("TSL_RUST_CARGO_PROFILE", &context.cargo_profile);
    emit("TSL_RUST_OPT_LEVEL", &context.opt_level);
    emit("TSL_RUST_DEBUG", &context.debug);
    emit("TSL_RUST_DEBUG_ASSERTIONS", &context.debug_assertions);
    emit("TSL_RUST_OVERFLOW_CHECKS", &context.overflow_checks);
    emit("TSL_RUST_LTO", &context.lto);
    emit("TSL_RUST_CODEGEN_UNITS", &context.codegen_units);
    emit("TSL_RUST_INCREMENTAL", &context.incremental);
    emit("TSL_RUST_PANIC", &context.panic);
    emit("TSL_RUSTFLAGS", &context.rustflags);
    emit("TSL_RUST_ENCODED_RUSTFLAGS", &context.encoded_rustflags);
    emit("TSL_RUST_PROFILE_OVERRIDES", &context.profile_overrides);
    emit("TSL_RUST_BENCHMARK_CONTEXT", &context.external_context);
}

fn required(name: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| panic!("Cargo did not provide {}", name))
}

fn command_verbose_version(command: &str, label: &str) -> String {
    let output = Command::new(command)
        .args(["--version", "--verbose"])
        .output()
        .unwrap_or_else(|error| {
            panic!("cannot execute {label} to capture the benchmark tune context: {error}")
        });
    if !output.status.success() {
        panic!("{label} --version --verbose failed while capturing the benchmark tune context");
    }
    String::from_utf8(output.stdout)
        .unwrap_or_else(|_| panic!("{label} --version --verbose did not produce UTF-8"))
        .trim()
        .replace(['\r', '\n'], " | ")
}

fn optional(name: &str) -> String {
    std::env::var(name).unwrap_or_default()
}

fn profile_setting(name: &str, default: &str) -> String {
    std::env::var(format!("CARGO_PROFILE_BENCH_{}", name)).unwrap_or_else(|_| default.to_string())
}

fn cargo_features() -> String {
    environment_with_prefix("CARGO_FEATURE_")
}

fn profile_overrides() -> String {
    let mut entries = std::env::vars()
        .filter(|(name, _value)| {
            name.starts_with("CARGO_PROFILE_")
                || matches!(name.as_str(), "CARGO_INCREMENTAL" | "CARGO_BUILD_INCREMENTAL")
        })
        .collect::<Vec<_>>();
    entries.sort_unstable();
    for (name, _value) in &entries {
        println!("cargo:rerun-if-env-changed={}", name);
    }
    entries
        .into_iter()
        .map(|(name, value)| format!("{}={}", name, value))
        .collect::<Vec<_>>()
        .join(";")
}

fn force_context_revalidation(out_dir: &std::path::Path) {
    let sentinel = out_dir.join(".tsl-rust-context-revalidate-always-missing");
    match std::fs::symlink_metadata(&sentinel) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => panic!(
            "cannot inspect reserved Rust context revalidation path {}: {error}",
            sentinel.display()
        ),
        Ok(_) => panic!(
            "reserved Rust context revalidation path {} must remain absent",
            sentinel.display()
        ),
    }
    let value = sentinel.to_string_lossy();
    if value.contains('\r') || value.contains('\n') {
        panic!("Rust context revalidation path cannot contain line breaks");
    }
    println!("cargo:rerun-if-changed={}", value);
}

fn environment_with_prefix(prefix: &str) -> String {
    let mut entries = std::env::vars()
        .filter(|(name, _value)| name.starts_with(prefix))
        .collect::<Vec<_>>();
    entries.sort_unstable();
    entries
        .into_iter()
        .map(|(name, value)| format!("{}={}", name, value))
        .collect::<Vec<_>>()
        .join(";")
}

fn rustflag_value(rustflags: &str, encoded: &str, key: &str) -> Option<String> {
    if !encoded.is_empty() {
        return rustflag_value_from_words(&encoded.split('\u{1f}').collect::<Vec<_>>(), key);
    }
    rustflag_value_from_words(&rustflags.split_whitespace().collect::<Vec<_>>(), key)
}

fn rustflag_value_from_words(words: &[&str], key: &str) -> Option<String> {
    let mut result = None;
    for (index, word) in words.iter().enumerate() {
        for prefix in [
            format!("-C{key}="),
            format!("--codegen={key}="),
            format!("{key}="),
        ] {
            if let Some(value) = word.strip_prefix(&prefix) {
                result = Some(value.to_string());
            }
        }
        if matches!(*word, "-C" | "--codegen") {
            if let Some(value) = words
                .get(index + 1)
                .and_then(|next| next.strip_prefix(&format!("{key}=")))
            {
                result = Some(value.to_string());
            }
        }
    }
    result
}

fn emit(name: &str, value: &str) {
    if value.contains('\n') || value.contains('\r') {
        panic!("benchmark tune-context value {} contains a newline", name);
    }
    println!("cargo:rustc-env={}={}", name, value);
}
