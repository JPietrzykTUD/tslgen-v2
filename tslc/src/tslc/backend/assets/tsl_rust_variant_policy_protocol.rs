//! Strict decoding for generated Rust benchmark descriptors and policy files.

use std::collections::HashSet;

use crate::tsl_rust_policy_json::{parse_json, JsonValue};

pub(crate) const DESCRIPTOR_SCHEMA_VERSION: u64 = @{descriptor_schema_version};
pub(crate) const POLICY_SCHEMA_VERSION: u64 = @{policy_schema_version};
pub(crate) const BENCHMARK_PROTOCOL_VERSION: u64 = @{benchmark_protocol_version};
pub(crate) const BACKEND_ID: &str = "rust";

#[derive(Clone, Copy, Debug)]
pub struct GeneratedTargetRequirement {
    pub target_arch: &'static str,
    pub target_features: &'static [&'static str],
}

#[derive(Clone, Copy, Debug)]
pub struct GeneratedProfile {
    pub name: &'static str,
    pub family: &'static str,
    pub target_arch: &'static str,
    pub target_features: &'static [&'static str],
    pub stronger_requirements: &'static [GeneratedTargetRequirement],
    pub descriptor_relative_path: &'static str,
    pub descriptor: &'static str,
    pub mappings: &'static [GeneratedMapping],
    pub materialized_mapping_file: &'static str,
    pub required_rustflags: &'static [&'static str],
    pub required_incremental_environment: &'static str,
}

#[derive(Clone, Copy, Debug)]
pub struct GeneratedMapping {
    pub stable_id: &'static str,
    pub candidate: &'static str,
    pub source: &'static str,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BuildContext {
    pub rustc_verbose_version: String,
    pub cargo_verbose_version: String,
    pub host: String,
    pub target: String,
    pub linker: String,
    pub rustc_wrapper: String,
    pub rustc_workspace_wrapper: String,
    pub target_cpu: String,
    pub target_features: String,
    pub cargo_features: String,
    pub cargo_profile: String,
    pub opt_level: String,
    pub debug_assertions: String,
    pub overflow_checks: String,
    pub lto: String,
    pub codegen_units: String,
    pub panic: String,
    pub incremental: String,
    pub debug: String,
    pub rustflags: String,
    pub encoded_rustflags: String,
    pub profile_overrides: String,
    pub benchmark_codegen_contract: String,
    pub external_context: String,
}

#[derive(Debug)]
pub(crate) struct Descriptor {
    pub(crate) schema_version: u64,
    pub(crate) policy_schema_version: u64,
    pub(crate) protocol_version: u64,
    pub(crate) backend: String,
    pub(crate) profile: String,
    pub(crate) profile_family: String,
    pub(crate) manifest_hash: String,
    pub(crate) required_features: Vec<String>,
    pub(crate) benchmark_codegen_contract: String,
    pub(crate) decisions: Vec<ExpectedDecision>,
}

#[derive(Debug)]
pub(crate) struct ExpectedDecision {
    pub(crate) stable_id: String,
    pub(crate) status: String,
    pub(crate) reason: String,
    pub(crate) candidates: Vec<ExpectedCandidate>,
    pub(crate) scenarios: Vec<ExpectedScenario>,
    pub(crate) specialization_required_features: Vec<String>,
    pub(crate) mappings: Vec<ExpectedMapping>,
}

#[derive(Debug)]
pub(crate) struct ExpectedCandidate {
    pub(crate) id: String,
    pub(crate) body_hash: String,
}

#[derive(Debug)]
pub(crate) struct ExpectedScenario {
    pub(crate) id: String,
    pub(crate) rounds: u64,
    pub(crate) minimum_sample_ns: u64,
}

#[derive(Debug)]
pub(crate) struct ExpectedMapping {
    pub(crate) candidate: String,
}

#[derive(Debug)]
pub(crate) struct Policy {
    pub(crate) schema_version: u64,
    pub(crate) protocol_version: u64,
    pub(crate) backend: String,
    pub(crate) profile: String,
    pub(crate) manifest_hash: String,
    pub(crate) tune_context: TuneContext,
    pub(crate) cpu_id: String,
    pub(crate) decisions: Vec<PolicyDecision>,
}

#[derive(Debug)]
pub(crate) struct TuneContext {
    pub(crate) build: BuildContext,
    pub(crate) required_features: String,
    pub(crate) threshold: f64,
    pub(crate) rounds_override: Option<u64>,
    pub(crate) minimum_sample_ns_override: Option<u64>,
    pub(crate) scenario_settings: Vec<ScenarioSetting>,
}

#[derive(Debug)]
pub(crate) struct ScenarioSetting {
    pub(crate) stable_id: String,
    pub(crate) scenario: String,
    pub(crate) rounds: u64,
    pub(crate) minimum_sample_ns: u64,
}

#[derive(Debug)]
pub(crate) struct PolicyDecision {
    pub(crate) stable_id: String,
    pub(crate) selected: String,
    pub(crate) status: String,
    pub(crate) minimum_improvement: f64,
}

pub(crate) fn parse_descriptor(input: &str) -> Result<Descriptor, String> {
    let value = parse_json(input)
        .map_err(|error| format!("invalid generated Rust policy descriptor: {error}"))?;
    exact_object(
        &value,
        &[
            "schema_version",
            "policy_schema_version",
            "protocol_version",
            "backend",
            "profile",
            "profile_family",
            "manifest_hash",
            "required_features",
            "benchmark_codegen_contract",
            "decisions",
        ],
        "generated Rust policy descriptor",
    )?;
    Ok(Descriptor {
        schema_version: required_u64(&value, "schema_version", "descriptor")?,
        policy_schema_version: required_u64(&value, "policy_schema_version", "descriptor")?,
        protocol_version: required_u64(&value, "protocol_version", "descriptor")?,
        backend: required_string(&value, "backend", "descriptor")?,
        profile: required_string(&value, "profile", "descriptor")?,
        profile_family: required_string(&value, "profile_family", "descriptor")?,
        manifest_hash: required_string(&value, "manifest_hash", "descriptor")?,
        required_features: string_array(
            required_member(&value, "required_features", "descriptor")?,
            "descriptor required_features",
        )?,
        benchmark_codegen_contract: required_string(
            &value,
            "benchmark_codegen_contract",
            "descriptor",
        )?,
        decisions: required_array(&value, "decisions", "descriptor")?
            .iter()
            .map(parse_expected_decision)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

fn parse_expected_decision(value: &JsonValue) -> Result<ExpectedDecision, String> {
    exact_object(
        value,
        &[
            "stable_id",
            "status",
            "reason",
            "candidates",
            "scenarios",
            "specialization_required_features",
            "mappings",
        ],
        "descriptor decision",
    )?;
    Ok(ExpectedDecision {
        stable_id: required_string(value, "stable_id", "descriptor decision")?,
        status: required_string(value, "status", "descriptor decision")?,
        reason: required_string(value, "reason", "descriptor decision")?,
        candidates: required_array(value, "candidates", "descriptor decision")?
            .iter()
            .map(parse_expected_candidate)
            .collect::<Result<Vec<_>, _>>()?,
        scenarios: required_array(value, "scenarios", "descriptor decision")?
            .iter()
            .map(parse_expected_scenario)
            .collect::<Result<Vec<_>, _>>()?,
        specialization_required_features: string_array(
            required_member(
                value,
                "specialization_required_features",
                "descriptor decision",
            )?,
            "descriptor specialization_required_features",
        )?,
        mappings: required_array(value, "mappings", "descriptor decision")?
            .iter()
            .map(parse_expected_mapping)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

fn parse_expected_candidate(value: &JsonValue) -> Result<ExpectedCandidate, String> {
    exact_object(value, &["id", "body_hash"], "descriptor candidate")?;
    Ok(ExpectedCandidate {
        id: required_string(value, "id", "descriptor candidate")?,
        body_hash: required_string(value, "body_hash", "descriptor candidate")?,
    })
}

fn parse_expected_scenario(value: &JsonValue) -> Result<ExpectedScenario, String> {
    exact_object(
        value,
        &[
            "id",
            "family",
            "kind",
            "seed",
            "batch_size",
            "rounds",
            "minimum_sample_ns",
        ],
        "descriptor scenario",
    )?;
    required_string(value, "family", "descriptor scenario")?;
    required_string(value, "kind", "descriptor scenario")?;
    required_u64(value, "seed", "descriptor scenario")?;
    required_u64(value, "batch_size", "descriptor scenario")?;
    Ok(ExpectedScenario {
        id: required_string(value, "id", "descriptor scenario")?,
        rounds: required_u64(value, "rounds", "descriptor scenario")?,
        minimum_sample_ns: required_u64(value, "minimum_sample_ns", "descriptor scenario")?,
    })
}

fn parse_expected_mapping(value: &JsonValue) -> Result<ExpectedMapping, String> {
    exact_object(value, &["candidate"], "descriptor mapping")?;
    Ok(ExpectedMapping {
        candidate: required_string(value, "candidate", "descriptor mapping")?,
    })
}

pub(crate) fn parse_policy(input: &str) -> Result<Policy, String> {
    let value =
        parse_json(input).map_err(|error| format!("invalid Rust variant policy: {error}"))?;
    exact_object(
        &value,
        &[
            "schema_version",
            "protocol_version",
            "backend",
            "profile",
            "manifest_hash",
            "tune_context",
            "cpu_id",
            "decisions",
        ],
        "Rust variant policy",
    )?;
    Ok(Policy {
        schema_version: required_u64(&value, "schema_version", "policy")?,
        protocol_version: required_u64(&value, "protocol_version", "policy")?,
        backend: required_string(&value, "backend", "policy")?,
        profile: required_string(&value, "profile", "policy")?,
        manifest_hash: required_string(&value, "manifest_hash", "policy")?,
        tune_context: parse_tune_context(required_member(&value, "tune_context", "policy")?)?,
        cpu_id: required_string(&value, "cpu_id", "policy")?,
        decisions: required_array(&value, "decisions", "policy")?
            .iter()
            .map(parse_policy_decision)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

fn parse_tune_context(value: &JsonValue) -> Result<TuneContext, String> {
    exact_object(
        value,
        &[
            "rustc_verbose_version",
            "cargo_verbose_version",
            "host",
            "target",
            "linker",
            "rustc_wrapper",
            "rustc_workspace_wrapper",
            "target_cpu",
            "target_features",
            "required_features",
            "cargo_features",
            "cargo_profile",
            "opt_level",
            "debug_assertions",
            "overflow_checks",
            "lto",
            "codegen_units",
            "panic",
            "incremental",
            "debug",
            "rustflags",
            "encoded_rustflags",
            "profile_overrides",
            "benchmark_codegen_contract",
            "external_context",
            "threshold",
            "rounds_override",
            "minimum_sample_ns_override",
            "scenario_settings",
        ],
        "policy tune_context",
    )?;
    let build = BuildContext {
        rustc_verbose_version: required_string(value, "rustc_verbose_version", "tune_context")?,
        cargo_verbose_version: required_string(value, "cargo_verbose_version", "tune_context")?,
        host: required_string(value, "host", "tune_context")?,
        target: required_string(value, "target", "tune_context")?,
        linker: required_string(value, "linker", "tune_context")?,
        rustc_wrapper: required_string(value, "rustc_wrapper", "tune_context")?,
        rustc_workspace_wrapper: required_string(value, "rustc_workspace_wrapper", "tune_context")?,
        target_cpu: required_string(value, "target_cpu", "tune_context")?,
        target_features: required_string(value, "target_features", "tune_context")?,
        cargo_features: required_string(value, "cargo_features", "tune_context")?,
        cargo_profile: required_string(value, "cargo_profile", "tune_context")?,
        opt_level: required_string(value, "opt_level", "tune_context")?,
        debug_assertions: required_string(value, "debug_assertions", "tune_context")?,
        overflow_checks: required_string(value, "overflow_checks", "tune_context")?,
        lto: required_string(value, "lto", "tune_context")?,
        codegen_units: required_string(value, "codegen_units", "tune_context")?,
        panic: required_string(value, "panic", "tune_context")?,
        incremental: required_string(value, "incremental", "tune_context")?,
        debug: required_string(value, "debug", "tune_context")?,
        rustflags: required_string(value, "rustflags", "tune_context")?,
        encoded_rustflags: required_string(value, "encoded_rustflags", "tune_context")?,
        profile_overrides: required_string(value, "profile_overrides", "tune_context")?,
        benchmark_codegen_contract: required_string(
            value,
            "benchmark_codegen_contract",
            "tune_context",
        )?,
        external_context: required_string(value, "external_context", "tune_context")?,
    };
    Ok(TuneContext {
        build,
        required_features: required_string(value, "required_features", "tune_context")?,
        threshold: required_f64(value, "threshold", "tune_context")?,
        rounds_override: optional_u64(value, "rounds_override", "tune_context")?,
        minimum_sample_ns_override: optional_u64(
            value,
            "minimum_sample_ns_override",
            "tune_context",
        )?,
        scenario_settings: required_array(value, "scenario_settings", "tune_context")?
            .iter()
            .map(parse_scenario_setting)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

fn parse_scenario_setting(value: &JsonValue) -> Result<ScenarioSetting, String> {
    exact_object(
        value,
        &["stable_id", "scenario", "rounds", "minimum_sample_ns"],
        "policy scenario setting",
    )?;
    Ok(ScenarioSetting {
        stable_id: required_string(value, "stable_id", "scenario setting")?,
        scenario: required_string(value, "scenario", "scenario setting")?,
        rounds: required_u64(value, "rounds", "scenario setting")?,
        minimum_sample_ns: required_u64(value, "minimum_sample_ns", "scenario setting")?,
    })
}

fn parse_policy_decision(value: &JsonValue) -> Result<PolicyDecision, String> {
    exact_object(
        value,
        &["stable_id", "selected", "status", "minimum_improvement"],
        "policy decision",
    )?;
    Ok(PolicyDecision {
        stable_id: required_string(value, "stable_id", "policy decision")?,
        selected: required_string(value, "selected", "policy decision")?,
        status: required_string(value, "status", "policy decision")?,
        minimum_improvement: required_f64(value, "minimum_improvement", "policy decision")?,
    })
}

fn exact_object(value: &JsonValue, fields: &[&str], label: &str) -> Result<(), String> {
    let members = value
        .as_object()
        .ok_or_else(|| format!("{label} must be an object, got {}", value.kind_name()))?;
    let actual = members
        .iter()
        .map(|(name, _value)| name.as_str())
        .collect::<HashSet<_>>();
    let expected = fields.iter().copied().collect::<HashSet<_>>();
    if actual != expected || members.len() != fields.len() {
        return Err(format!(
            "{label} has missing or unknown fields; expected {}",
            fields.join(", ")
        ));
    }
    Ok(())
}

fn required_member<'a>(
    value: &'a JsonValue,
    name: &str,
    label: &str,
) -> Result<&'a JsonValue, String> {
    value
        .member(name)
        .ok_or_else(|| format!("{label} is missing {name:?}"))
}

fn required_string(value: &JsonValue, name: &str, label: &str) -> Result<String, String> {
    let member = required_member(value, name, label)?;
    member.as_str().map(ToOwned::to_owned).ok_or_else(|| {
        format!(
            "{}.{} must be a string, got {}",
            label,
            name,
            member.kind_name()
        )
    })
}

fn required_u64(value: &JsonValue, name: &str, label: &str) -> Result<u64, String> {
    let member = required_member(value, name, label)?;
    member
        .as_number()
        .and_then(|number| number.as_u64())
        .ok_or_else(|| {
            format!(
                "{}.{} must be an unsigned integer, got {}",
                label,
                name,
                member.kind_name()
            )
        })
}

fn required_f64(value: &JsonValue, name: &str, label: &str) -> Result<f64, String> {
    let member = required_member(value, name, label)?;
    let result = member
        .as_number()
        .map(|number| number.as_f64())
        .ok_or_else(|| {
            format!(
                "{}.{} must be a number, got {}",
                label,
                name,
                member.kind_name()
            )
        })?;
    if !result.is_finite() {
        return Err(format!("{}.{} must be finite", label, name));
    }
    Ok(result)
}

fn optional_u64(value: &JsonValue, name: &str, label: &str) -> Result<Option<u64>, String> {
    let member = required_member(value, name, label)?;
    if member.is_null() {
        return Ok(None);
    }
    member
        .as_number()
        .and_then(|number| number.as_u64())
        .map(Some)
        .ok_or_else(|| format!("{}.{} must be null or an unsigned integer", label, name))
}

fn required_array<'a>(
    value: &'a JsonValue,
    name: &str,
    label: &str,
) -> Result<&'a [JsonValue], String> {
    let member = required_member(value, name, label)?;
    member.as_array().ok_or_else(|| {
        format!(
            "{}.{} must be an array, got {}",
            label,
            name,
            member.kind_name()
        )
    })
}

fn string_array(value: &JsonValue, label: &str) -> Result<Vec<String>, String> {
    value
        .as_array()
        .ok_or_else(|| format!("{label} must be an array, got {}", value.kind_name()))?
        .iter()
        .map(|item| {
            item.as_str()
                .map(ToOwned::to_owned)
                .ok_or_else(|| format!("{label} entries must be strings"))
        })
        .collect()
}
