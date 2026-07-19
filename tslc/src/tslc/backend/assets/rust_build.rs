use std::process::Command;

const TRACKED_ENVIRONMENT: &[&str] = &[
    "RUSTC",
    "RUSTC_LINKER",
    "RUSTC_WRAPPER",
    "RUSTC_WORKSPACE_WRAPPER",
    "RUSTFLAGS",
    "CARGO_ENCODED_RUSTFLAGS",
    "CARGO_CFG_TARGET_FEATURE",
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
    "TSL_RUST_BENCHMARK_CONTEXT",
];

fn main() {
    for name in ["HOST", "TARGET"] {
        println!("cargo:rerun-if-env-changed={}", name);
    }
    let host = required("HOST");
    let target = required("TARGET");
    emit("TSL_BUILD_HOST", &host);
    emit("TSL_BUILD_TARGET", &target);

    if std::env::var_os("CARGO_FEATURE_VARIANT_BENCHMARKS").is_none() {
        return;
    }
    for name in TRACKED_ENVIRONMENT {
        println!("cargo:rerun-if-env-changed={}", name);
    }

    let rustc = required("RUSTC");
    let target_linker_key = format!(
        "CARGO_TARGET_{}_LINKER",
        target.replace('-', "_").to_ascii_uppercase(),
    );
    println!("cargo:rerun-if-env-changed={target_linker_key}");

    let rustc_verbose = Command::new(&rustc)
        .args(["--version", "--verbose"])
        .output()
        .expect("cannot execute rustc to capture the benchmark tune context");
    if !rustc_verbose.status.success() {
        panic!("rustc --version --verbose failed while capturing the benchmark tune context");
    }
    let rustc_verbose = String::from_utf8(rustc_verbose.stdout)
        .expect("rustc --version --verbose did not produce UTF-8")
        .trim()
        .replace(['\r', '\n'], " | ");

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

    emit("TSL_RUSTC_VERBOSE_VERSION", &rustc_verbose);
    emit("TSL_RUST_LINKER", &linker);
    emit("TSL_RUSTC_WRAPPER", &optional("RUSTC_WRAPPER"));
    emit(
        "TSL_RUSTC_WORKSPACE_WRAPPER",
        &optional("RUSTC_WORKSPACE_WRAPPER"),
    );
    emit("TSL_RUST_TARGET_CPU", &target_cpu);
    emit("TSL_RUST_TARGET_FEATURES", &target_features);
    emit("TSL_RUST_CARGO_FEATURES", &cargo_features);
    emit("TSL_RUST_CARGO_PROFILE", &required("PROFILE"));
    emit("TSL_RUST_OPT_LEVEL", &required("OPT_LEVEL"));
    emit("TSL_RUST_DEBUG", &required("DEBUG"));
    emit(
        "TSL_RUST_DEBUG_ASSERTIONS",
        &profile_setting("DEBUG_ASSERTIONS", "@{default_debug_assertions}"),
    );
    emit(
        "TSL_RUST_OVERFLOW_CHECKS",
        &profile_setting("OVERFLOW_CHECKS", "@{default_overflow_checks}"),
    );
    emit("TSL_RUST_LTO", &profile_setting("LTO", "@{default_lto}"));
    emit(
        "TSL_RUST_CODEGEN_UNITS",
        &profile_setting("CODEGEN_UNITS", "@{default_codegen_units}"),
    );
    let cargo_incremental = optional("CARGO_INCREMENTAL");
    let cargo_build_incremental = optional("CARGO_BUILD_INCREMENTAL");
    let incremental = if !cargo_incremental.is_empty() {
        cargo_incremental
    } else if !cargo_build_incremental.is_empty() {
        cargo_build_incremental
    } else {
        profile_setting("INCREMENTAL", "@{default_incremental}")
    };
    emit("TSL_RUST_INCREMENTAL", &incremental);
    emit("TSL_RUST_PANIC", &optional("CARGO_CFG_PANIC"));
    emit("TSL_RUSTFLAGS", &rustflags);
    emit("TSL_RUST_ENCODED_RUSTFLAGS", &encoded_rustflags);
    emit("TSL_RUST_PROFILE_OVERRIDES", &profile_overrides);
    emit(
        "TSL_RUST_BENCHMARK_CONTEXT",
        &optional("TSL_RUST_BENCHMARK_CONTEXT"),
    );
}

fn required(name: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| panic!("Cargo did not provide {}", name))
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
    TRACKED_ENVIRONMENT
        .iter()
        .filter(|name| {
            name.starts_with("CARGO_PROFILE_BENCH_")
                || matches!(**name, "CARGO_INCREMENTAL" | "CARGO_BUILD_INCREMENTAL")
        })
        .filter_map(|name| std::env::var(name).ok().map(|value| (*name, value)))
        .map(|(name, value)| format!("{}={}", name, value))
        .collect::<Vec<_>>()
        .join(";")
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
