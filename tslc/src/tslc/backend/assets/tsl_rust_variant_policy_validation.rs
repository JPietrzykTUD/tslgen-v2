//! Semantic validation and mapping selection for Rust benchmark policies.

use std::collections::HashSet;

use crate::tsl_rust_cpu_identity::{cpu_id, precise_x86_cpu_id};
use crate::tsl_rust_variant_policy_protocol::{
    BuildContext, Descriptor, GeneratedProfile, Policy, TuneContext, BACKEND_ID,
    BENCHMARK_PROTOCOL_VERSION, DESCRIPTOR_SCHEMA_VERSION, POLICY_SCHEMA_VERSION,
};

pub(crate) const BENCHMARK_FEATURE_ENV: &str = "CARGO_FEATURE_VARIANT_BENCHMARKS";

pub(crate) fn validate_descriptor(
    descriptor: &Descriptor,
    profile: &GeneratedProfile,
    context: &BuildContext,
) -> Result<(), String> {
    if descriptor.schema_version != DESCRIPTOR_SCHEMA_VERSION
        || descriptor.policy_schema_version != POLICY_SCHEMA_VERSION
        || descriptor.protocol_version != BENCHMARK_PROTOCOL_VERSION
    {
        return Err(
            "generated Rust policy descriptor has an unsupported schema or protocol".to_string(),
        );
    }
    if descriptor.backend != BACKEND_ID
        || descriptor.profile != profile.name
        || descriptor.profile_family != "x86"
        || descriptor.benchmark_codegen_contract != context.benchmark_codegen_contract
    {
        return Err(
            "generated Rust policy descriptor has a foreign backend, profile, family, or codegen contract"
                .to_string(),
        );
    }
    validate_sha256(&descriptor.manifest_hash, "descriptor manifest hash")?;
    unique_nonempty(
        &descriptor.required_features,
        "descriptor required features",
    )?;
    if descriptor.required_features.is_empty() || descriptor.decisions.is_empty() {
        return Err("generated Rust policy descriptor requires features and decisions".to_string());
    }

    let mut stable_ids = HashSet::new();
    for decision in &descriptor.decisions {
        if decision.stable_id.is_empty() || !stable_ids.insert(decision.stable_id.as_str()) {
            return Err(
                "generated Rust policy descriptor has empty or duplicate stable IDs".to_string(),
            );
        }
        let candidate_ids = decision
            .candidates
            .iter()
            .map(|candidate| candidate.id.as_str())
            .collect::<Vec<_>>();
        if candidate_ids.first() != Some(&"default")
            || candidate_ids.iter().any(|candidate| candidate.is_empty())
            || candidate_ids.iter().copied().collect::<HashSet<_>>().len() != candidate_ids.len()
        {
            return Err(format!(
                "descriptor decision {} has an invalid candidate inventory",
                decision.stable_id
            ));
        }
        for candidate in &decision.candidates {
            validate_sha256(
                &candidate.body_hash,
                &format!("body hash for {}/{}", decision.stable_id, candidate.id),
            )?;
        }
        if decision.scenarios.is_empty() {
            return Err(format!(
                "descriptor decision {} has no scenarios",
                decision.stable_id
            ));
        }
        let mut scenario_ids = HashSet::new();
        for scenario in &decision.scenarios {
            if scenario.id.is_empty() || !scenario_ids.insert(scenario.id.as_str()) {
                return Err(format!(
                    "descriptor decision {} has empty or duplicate scenarios",
                    decision.stable_id
                ));
            }
        }
        unique_nonempty(
            &decision.specialization_required_features,
            "specialization required features",
        )?;
        if decision
            .specialization_required_features
            .iter()
            .any(|feature| !descriptor.required_features.contains(feature))
        {
            return Err(format!(
                "descriptor decision {} requires a feature outside its profile",
                decision.stable_id
            ));
        }
        match decision.status.as_str() {
            "supported" => {
                if !decision.reason.is_empty()
                    || decision.mappings.len() != decision.candidates.len()
                    || decision
                        .mappings
                        .iter()
                        .zip(&decision.candidates)
                        .any(|(mapping, candidate)| mapping.candidate != candidate.id)
                {
                    return Err(format!(
                        "supported descriptor decision {} has incomplete mappings",
                        decision.stable_id
                    ));
                }
            }
            "report_only" => {
                if decision.reason.is_empty() || !decision.mappings.is_empty() {
                    return Err(format!(
                        "report-only descriptor decision {} has invalid mappings",
                        decision.stable_id
                    ));
                }
            }
            _ => {
                return Err(format!(
                    "descriptor decision {} has unknown status {:?}",
                    decision.stable_id, decision.status
                ));
            }
        }
    }
    let expected_mapping_count = descriptor
        .decisions
        .iter()
        .filter(|decision| decision.status == "supported")
        .map(|decision| decision.candidates.len())
        .sum::<usize>();
    if profile.mappings.len() != expected_mapping_count {
        return Err("generated Rust policy mapping inventory is stale or incomplete".to_string());
    }
    let mut generated_mappings = HashSet::new();
    for mapping in profile.mappings {
        if mapping.stable_id.is_empty()
            || mapping.candidate.is_empty()
            || mapping.source.trim().is_empty()
            || !generated_mappings.insert((mapping.stable_id, mapping.candidate))
        {
            return Err(
                "generated Rust policy mapping inventory has empty or duplicate entries"
                    .to_string(),
            );
        }
    }
    for decision in descriptor
        .decisions
        .iter()
        .filter(|decision| decision.status == "supported")
    {
        for candidate in &decision.candidates {
            if !generated_mappings.contains(&(decision.stable_id.as_str(), candidate.id.as_str())) {
                return Err(
                    "generated Rust policy mapping inventory does not match the benchmark descriptor"
                        .to_string(),
                );
            }
        }
    }
    Ok(())
}
pub(crate) fn validate_policy(
    policy: &Policy,
    descriptor: &Descriptor,
    profile: &GeneratedProfile,
    context: &BuildContext,
) -> Result<String, String> {
    if policy.schema_version != descriptor.policy_schema_version
        || policy.protocol_version != descriptor.protocol_version
    {
        return Err("Rust variant policy has an unsupported schema or protocol".to_string());
    }
    if policy.backend != descriptor.backend
        || policy.profile != descriptor.profile
        || policy.profile != profile.name
        || policy.manifest_hash != descriptor.manifest_hash
    {
        return Err(
            "Rust variant policy has a foreign backend, profile, or stale manifest/body inventory"
                .to_string(),
        );
    }
    validate_tune_context(&policy.tune_context, descriptor, profile, context)?;
    let current_cpu = cpu_id();
    if !precise_x86_cpu_id(&policy.cpu_id)
        || policy.cpu_id != current_cpu
        || !precise_x86_cpu_id(&current_cpu)
    {
        return Err("Rust variant policy was produced for a different native CPU".to_string());
    }
    if policy.decisions.len() != descriptor.decisions.len() {
        return Err("Rust variant policy has missing or unexpected decisions".to_string());
    }

    let mut seen = HashSet::new();
    let mut mapping =
        String::from("// Generated by tslc build-time Rust variant policy consumption.\n");
    for (decision, expected) in policy.decisions.iter().zip(&descriptor.decisions) {
        if decision.stable_id != expected.stable_id || !seen.insert(decision.stable_id.as_str()) {
            return Err(
                "Rust variant policy has duplicate, missing, or reordered decisions".to_string(),
            );
        }
        if !decision.minimum_improvement.is_finite()
            || !(0.0..1.0).contains(&decision.minimum_improvement)
        {
            return Err(format!(
                "Rust variant policy has an invalid score for {}",
                decision.stable_id
            ));
        }
        let _selected = expected
            .candidates
            .iter()
            .position(|candidate| candidate.id == decision.selected)
            .ok_or_else(|| {
                format!(
                    "Rust variant policy selects unavailable candidate {}/{}",
                    decision.stable_id, decision.selected
                )
            })?;
        match expected.status.as_str() {
            "supported" if decision.selected == "default" => {
                if decision.status != "inconclusive" || decision.minimum_improvement != 0.0 {
                    return Err(format!(
                        "Rust variant policy has an invalid default decision for {}",
                        decision.stable_id
                    ));
                }
            }
            "supported" => {
                if decision.status != "selected"
                    || decision.minimum_improvement < policy.tune_context.threshold
                {
                    return Err(format!(
                        "Rust variant policy alternative is not valid for {}",
                        decision.stable_id
                    ));
                }
            }
            "report_only" => {
                if decision.selected != "default"
                    || decision.status != "report_only"
                    || decision.minimum_improvement != 0.0
                {
                    return Err(format!(
                        "Rust variant policy attempts to select report-only decision {}",
                        decision.stable_id
                    ));
                }
            }
            _ => unreachable!("descriptor status was validated"),
        }
        if expected.status == "supported" {
            let selected_mapping = profile
                .mappings
                .iter()
                .find(|mapping| {
                    mapping.stable_id == decision.stable_id
                        && mapping.candidate == decision.selected
                })
                .ok_or_else(|| {
                    format!(
                        "generated Rust mapping is missing for {}/{}",
                        decision.stable_id, decision.selected
                    )
                })?;
            mapping.push_str(selected_mapping.source);
            mapping.push_str("\n\n");
        }
    }
    Ok(mapping)
}

fn validate_tune_context(
    tune: &TuneContext,
    descriptor: &Descriptor,
    profile: &GeneratedProfile,
    current: &BuildContext,
) -> Result<(), String> {
    if !tune.threshold.is_finite() || !(0.0..1.0).contains(&tune.threshold) {
        return Err("Rust variant policy threshold must be finite and in [0, 1)".to_string());
    }
    if tune.rounds_override.is_some_and(|rounds| rounds < 3)
        || tune
            .minimum_sample_ns_override
            .is_some_and(|minimum| minimum == 0)
    {
        return Err("Rust variant policy has invalid timing overrides".to_string());
    }
    if tune.build.external_context.is_empty()
        || current.external_context.is_empty()
        || !tune.build.rustc_wrapper.is_empty()
        || !current.rustc_wrapper.is_empty()
        || !tune.build.rustc_workspace_wrapper.is_empty()
        || !current.rustc_workspace_wrapper.is_empty()
    {
        return Err(
            "Rust policy consumption requires a wrapper-free, explicitly identified build-local context"
                .to_string(),
        );
    }
    validate_codegen_guard(&tune.build, profile, "producer")?;
    validate_codegen_guard(current, profile, "consumer")?;

    for (name, policy_value, current_value) in [
        (
            "rustc_verbose_version",
            tune.build.rustc_verbose_version.as_str(),
            current.rustc_verbose_version.as_str(),
        ),
        (
            "cargo_verbose_version",
            tune.build.cargo_verbose_version.as_str(),
            current.cargo_verbose_version.as_str(),
        ),
        ("host", tune.build.host.as_str(), current.host.as_str()),
        (
            "target",
            tune.build.target.as_str(),
            current.target.as_str(),
        ),
        (
            "linker",
            tune.build.linker.as_str(),
            current.linker.as_str(),
        ),
        (
            "target_cpu",
            tune.build.target_cpu.as_str(),
            current.target_cpu.as_str(),
        ),
        (
            "target_features",
            tune.build.target_features.as_str(),
            current.target_features.as_str(),
        ),
        (
            "cargo_profile",
            tune.build.cargo_profile.as_str(),
            current.cargo_profile.as_str(),
        ),
        (
            "opt_level",
            tune.build.opt_level.as_str(),
            current.opt_level.as_str(),
        ),
        (
            "debug_assertions",
            tune.build.debug_assertions.as_str(),
            current.debug_assertions.as_str(),
        ),
        (
            "overflow_checks",
            tune.build.overflow_checks.as_str(),
            current.overflow_checks.as_str(),
        ),
        ("lto", tune.build.lto.as_str(), current.lto.as_str()),
        (
            "codegen_units",
            tune.build.codegen_units.as_str(),
            current.codegen_units.as_str(),
        ),
        ("panic", tune.build.panic.as_str(), current.panic.as_str()),
        (
            "incremental",
            tune.build.incremental.as_str(),
            current.incremental.as_str(),
        ),
        ("debug", tune.build.debug.as_str(), current.debug.as_str()),
        (
            "rustflags",
            tune.build.rustflags.as_str(),
            current.rustflags.as_str(),
        ),
        (
            "encoded_rustflags",
            tune.build.encoded_rustflags.as_str(),
            current.encoded_rustflags.as_str(),
        ),
        (
            "benchmark_codegen_contract",
            tune.build.benchmark_codegen_contract.as_str(),
            current.benchmark_codegen_contract.as_str(),
        ),
        (
            "external_context",
            tune.build.external_context.as_str(),
            current.external_context.as_str(),
        ),
    ] {
        if policy_value != current_value {
            return Err(format!(
                "Rust variant policy tune context differs from the consumer {}",
                name
            ));
        }
    }
    if tune.build.benchmark_codegen_contract != descriptor.benchmark_codegen_contract {
        return Err("Rust variant policy has a foreign benchmark codegen contract".to_string());
    }

    let policy_features = cargo_feature_set(&tune.build.cargo_features)?;
    let consumer_features = cargo_feature_set(&current.cargo_features)?;
    let expected_features = HashSet::from([
        profile.feature_environment.to_string(),
        BENCHMARK_FEATURE_ENV.to_string(),
    ]);
    if consumer_features != expected_features || policy_features != expected_features {
        return Err(
            "Rust variant policy producer and consumer Cargo features do not match".to_string(),
        );
    }

    let required = descriptor.required_features.join(",");
    if tune.required_features != required {
        return Err("Rust variant policy has foreign required target features".to_string());
    }
    let target_features = comma_set(&current.target_features, "target features")?;
    for feature in &descriptor.required_features {
        if !target_features.contains(feature.as_str()) || !native_feature_available(feature) {
            return Err(format!(
                "native consumer does not support required Rust target feature {feature:?}"
            ));
        }
    }

    let expected_settings = descriptor
        .decisions
        .iter()
        .flat_map(|decision| {
            decision.scenarios.iter().map(move |scenario| {
                (
                    decision.stable_id.as_str(),
                    scenario.id.as_str(),
                    tune.rounds_override.unwrap_or(scenario.rounds),
                    tune.minimum_sample_ns_override
                        .unwrap_or(scenario.minimum_sample_ns),
                )
            })
        })
        .collect::<Vec<_>>();
    if tune.scenario_settings.len() != expected_settings.len()
        || tune
            .scenario_settings
            .iter()
            .zip(expected_settings)
            .any(|(actual, expected)| {
                (
                    actual.stable_id.as_str(),
                    actual.scenario.as_str(),
                    actual.rounds,
                    actual.minimum_sample_ns,
                ) != expected
            })
    {
        return Err(
            "Rust variant policy has missing, reordered, or stale scenario settings".to_string(),
        );
    }
    Ok(())
}

fn validate_codegen_guard(
    context: &BuildContext,
    profile: &GeneratedProfile,
    label: &str,
) -> Result<(), String> {
    let encoded_flags = if context.encoded_rustflags.is_empty() {
        Vec::new()
    } else {
        context.encoded_rustflags.split('\u{1f}').collect::<Vec<_>>()
    };
    let expected_overrides = format!(
        "CARGO_INCREMENTAL={}",
        profile.required_incremental_environment
    );
    if encoded_flags != profile.required_rustflags
        || context.incremental != profile.required_incremental_environment
        || context.profile_overrides != expected_overrides
    {
        return Err(format!(
            "Rust policy {label} lacks the exact compiler-owned codegen guard"
        ));
    }
    Ok(())
}

pub(crate) fn validate_native_context(context: &BuildContext) -> Result<(), String> {
    if context.host != context.target {
        return Err("Rust policy consumption is native-only; HOST must equal TARGET".to_string());
    }
    if !context.host.starts_with("x86_64-") {
        return Err("Rust policy consumption currently requires native x86-64".to_string());
    }
    Ok(())
}

fn cargo_feature_set(value: &str) -> Result<HashSet<String>, String> {
    let mut features = HashSet::new();
    if value.is_empty() {
        return Ok(features);
    }
    for entry in value.split(';') {
        let (name, enabled) = entry
            .split_once('=')
            .ok_or_else(|| format!("invalid Cargo feature tune-context entry {entry:?}"))?;
        if !name.starts_with("CARGO_FEATURE_")
            || name.len() == "CARGO_FEATURE_".len()
            || enabled != "1"
            || !features.insert(name.to_string())
        {
            return Err(format!(
                "invalid or duplicate Cargo feature tune-context entry {entry:?}"
            ));
        }
    }
    Ok(features)
}

fn comma_set<'a>(value: &'a str, label: &str) -> Result<HashSet<&'a str>, String> {
    let mut values = HashSet::new();
    for item in value.split(',') {
        if item.is_empty() || !values.insert(item) {
            return Err(format!("{label} contains an empty or duplicate entry"));
        }
    }
    Ok(values)
}

#[cfg(target_arch = "x86_64")]
fn native_feature_available(feature: &str) -> bool {
    match feature {
        "sse" => std::arch::is_x86_feature_detected!("sse"),
        "sse2" => std::arch::is_x86_feature_detected!("sse2"),
        _ => false,
    }
}

#[cfg(not(target_arch = "x86_64"))]
fn native_feature_available(_feature: &str) -> bool {
    false
}

fn validate_sha256(value: &str, label: &str) -> Result<(), String> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(format!("{label} is not a lowercase SHA-256 digest"));
    }
    Ok(())
}

fn unique_nonempty(values: &[String], label: &str) -> Result<(), String> {
    if values.iter().any(String::is_empty)
        || values
            .iter()
            .map(String::as_str)
            .collect::<HashSet<_>>()
            .len()
            != values.len()
    {
        return Err(format!("{label} contains an empty or duplicate value"));
    }
    Ok(())
}
