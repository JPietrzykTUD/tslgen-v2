//! Rust benchmark context validation, policy production, and report publication.

use std::collections::HashSet;
use std::fmt::Write as _;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::path::{Path, PathBuf};

use crate::tsl_benchmark_core::{json_escape, output_identity, Options, RawSample};
use crate::tsl_benchmark_reducer::{
    reduce_profile, validate_decisions, validate_specs, CandidateSetSpec, Decision,
};
use crate::tsl_rust_cpu_identity::{cpu_id, precise_x86_cpu_id};

pub const RUST_BACKEND_ID: &str = "rust";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BuildContext {
    pub rustc_verbose_version: &'static str,
    pub cargo_verbose_version: &'static str,
    pub host: &'static str,
    pub target: &'static str,
    pub linker: &'static str,
    pub rustc_wrapper: &'static str,
    pub rustc_workspace_wrapper: &'static str,
    pub target_cpu: &'static str,
    pub target_features: &'static str,
    pub cargo_features: &'static str,
    pub cargo_profile: &'static str,
    pub opt_level: &'static str,
    pub debug_assertions: &'static str,
    pub overflow_checks: &'static str,
    pub lto: &'static str,
    pub codegen_units: &'static str,
    pub panic: &'static str,
    pub incremental: &'static str,
    pub debug: &'static str,
    pub rustflags: &'static str,
    pub encoded_rustflags: &'static str,
    pub profile_overrides: &'static str,
    pub benchmark_codegen_contract: &'static str,
    pub external_context: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReportMetadata {
    pub policy_schema_version: u32,
    pub protocol_version: u32,
    pub backend: &'static str,
    pub profile: &'static str,
    pub manifest_hash: &'static str,
    pub required_features: &'static str,
    pub required_rustflags: &'static [&'static str],
    pub required_incremental_environment: &'static str,
    pub build_context: BuildContext,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ScenarioSetting {
    pub stable_id: String,
    pub scenario: String,
    pub rounds: usize,
    pub minimum_sample_ns: u64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct TuneContext {
    pub build: BuildContext,
    pub required_features: String,
    pub threshold: f64,
    pub rounds_override: Option<usize>,
    pub minimum_sample_ns_override: Option<u64>,
    pub scenario_settings: Vec<ScenarioSetting>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RustPolicyDocument {
    pub schema_version: u32,
    pub protocol_version: u32,
    pub backend: String,
    pub profile: String,
    pub manifest_hash: String,
    pub tune_context: TuneContext,
    pub cpu_id: String,
    pub decisions: Vec<Decision>,
}

pub fn build_policy_document(
    specs: &[CandidateSetSpec],
    decisions: &[Decision],
    metadata: ReportMetadata,
    options: &Options,
    cpu_identity: String,
) -> Result<RustPolicyDocument, String> {
    validate_metadata(metadata)?;
    validate_policy_codegen_guard(metadata)?;
    validate_decisions(specs, decisions, options.threshold())?;
    if !precise_x86_cpu_id(&cpu_identity) {
        return Err(format!(
            "Rust policy production requires a precise native x86 CPU identity, got {cpu_identity}"
        ));
    }
    let tune_context = tune_context(specs, metadata, options);
    validate_policy_tune_context(&tune_context)?;
    let document = RustPolicyDocument {
        schema_version: metadata.policy_schema_version,
        protocol_version: metadata.protocol_version,
        backend: metadata.backend.to_string(),
        profile: metadata.profile.to_string(),
        manifest_hash: metadata.manifest_hash.to_string(),
        tune_context,
        cpu_id: cpu_identity,
        decisions: decisions.to_vec(),
    };
    validate_policy_document(&document, specs, metadata, options, &document.cpu_id)?;
    Ok(document)
}

pub fn validate_policy_document(
    document: &RustPolicyDocument,
    specs: &[CandidateSetSpec],
    expected: ReportMetadata,
    options: &Options,
    expected_cpu_id: &str,
) -> Result<(), String> {
    validate_metadata(expected)?;
    validate_policy_codegen_guard(expected)?;
    let expected_context = tune_context(specs, expected, options);
    validate_policy_tune_context(&expected_context)?;
    if document.schema_version != expected.policy_schema_version
        || document.protocol_version != expected.protocol_version
        || document.backend != RUST_BACKEND_ID
        || document.backend != expected.backend
        || document.profile != expected.profile
        || document.manifest_hash != expected.manifest_hash
        || document.tune_context != expected_context
        || document.cpu_id != expected_cpu_id
        || !precise_x86_cpu_id(&document.cpu_id)
    {
        return Err(
            "Rust benchmark policy does not match its backend, manifest, tune context, and CPU"
                .to_string(),
        );
    }
    validate_decisions(specs, &document.decisions, options.threshold())
}

fn tune_context(
    specs: &[CandidateSetSpec],
    metadata: ReportMetadata,
    options: &Options,
) -> TuneContext {
    TuneContext {
        build: metadata.build_context,
        required_features: metadata.required_features.to_string(),
        threshold: options.threshold(),
        rounds_override: options.rounds_override(),
        minimum_sample_ns_override: options.minimum_sample_ns_override(),
        scenario_settings: specs
            .iter()
            .flat_map(|spec| {
                spec.scenarios.iter().map(|scenario| ScenarioSetting {
                    stable_id: spec.stable_id.to_string(),
                    scenario: scenario.scenario.to_string(),
                    rounds: options.rounds(scenario.rounds),
                    minimum_sample_ns: options.minimum_sample_ns(scenario.minimum_sample_ns),
                })
            })
            .collect(),
    }
}

fn validate_policy_tune_context(context: &TuneContext) -> Result<(), String> {
    if context.build.external_context.is_empty() {
        return Err(
            "Rust policy production requires TSL_RUST_BENCHMARK_CONTEXT to identify the exact build-local context"
                .to_string(),
        );
    }
    if !context.build.rustc_wrapper.is_empty() || !context.build.rustc_workspace_wrapper.is_empty()
    {
        return Err("Rust policy production does not support compiler wrappers".to_string());
    }
    Ok(())
}

fn validate_metadata(metadata: ReportMetadata) -> Result<(), String> {
    let context = metadata.build_context;
    let required = [
        metadata.backend,
        metadata.profile,
        metadata.manifest_hash,
        context.rustc_verbose_version,
        context.cargo_verbose_version,
        context.host,
        context.target,
        context.linker,
        context.target_cpu,
        context.cargo_features,
        context.cargo_profile,
        context.opt_level,
        context.debug_assertions,
        context.overflow_checks,
        context.lto,
        context.codegen_units,
        context.panic,
        context.incremental,
        context.debug,
        context.benchmark_codegen_contract,
        metadata.required_incremental_environment,
    ];
    if metadata.backend != RUST_BACKEND_ID
        || required.iter().any(|value| value.is_empty())
        || metadata.required_rustflags.is_empty()
        || metadata
            .required_rustflags
            .iter()
            .any(|value| value.is_empty())
    {
        return Err(
            "Rust benchmark metadata has a wrong backend or missing tune context".to_string(),
        );
    }
    Ok(())
}

fn validate_policy_codegen_guard(metadata: ReportMetadata) -> Result<(), String> {
    let context = metadata.build_context;
    let encoded_flags = if context.encoded_rustflags.is_empty() {
        Vec::new()
    } else {
        context.encoded_rustflags.split('\u{1f}').collect::<Vec<_>>()
    };
    let expected_overrides = format!(
        "CARGO_INCREMENTAL={}",
        metadata.required_incremental_environment
    );
    if encoded_flags != metadata.required_rustflags
        || context.incremental != metadata.required_incremental_environment
        || context.profile_overrides != expected_overrides
    {
        return Err(
            "Rust policy production requires the exact compiler-owned codegen guard"
                .to_string(),
        );
    }
    Ok(())
}

pub fn write_reports(
    specs: &[CandidateSetSpec],
    samples: &[RawSample],
    decisions: &[Decision],
    metadata: ReportMetadata,
    options: &Options,
) -> Result<(), String> {
    validate_specs(specs)?;
    validate_metadata(metadata)?;
    validate_decisions(specs, decisions, options.threshold())?;
    let reduced = reduce_profile(specs, samples, options)?;
    if reduced != decisions {
        return Err("benchmark decisions do not match the validated sample evidence".to_string());
    }
    let cpu_identity = cpu_id();
    let tune_context = tune_context(specs, metadata, options);
    let raw = render_samples(samples, metadata, &tune_context, &cpu_identity)?;
    let summary = render_summary(decisions, metadata, options, &cpu_identity);
    let policy = if options.policy_json_path.is_some() {
        Some(render_policy_json(&build_policy_document(
            specs,
            decisions,
            metadata,
            options,
            cpu_identity.clone(),
        )?))
    } else {
        None
    };

    let mut documents = Vec::new();
    if let Some(path) = options.results_path.as_deref() {
        documents.push(PendingDocument {
            path,
            label: "benchmark results",
            content: &raw,
        });
    }
    if let Some(path) = options.summary_path.as_deref() {
        documents.push(PendingDocument {
            path,
            label: "benchmark summary",
            content: &summary,
        });
    }
    if let (Some(path), Some(policy)) = (options.policy_json_path.as_deref(), policy.as_ref()) {
        documents.push(PendingDocument {
            path,
            label: "Rust benchmark policy",
            content: policy,
        });
    }
    let staged = stage_documents(&documents)?;
    if options.results_path.is_none() {
        let mut output = std::io::stdout().lock();
        if let Err(error) = output
            .write_all(raw.as_bytes())
            .and_then(|()| output.flush())
        {
            cleanup_staged(&staged);
            return Err(format!("cannot write benchmark results: {error}"));
        }
    }
    commit_staged(staged)?;
    Ok(())
}

fn render_samples(
    samples: &[RawSample],
    metadata: ReportMetadata,
    tune_context: &TuneContext,
    cpu_identity: &str,
) -> Result<String, String> {
    let tune_context = render_tune_context(tune_context);
    let mut document = String::new();
    for sample in samples {
        writeln!(
            &mut document,
            concat!(
                "{{\"backend\":\"{}\",\"protocol_version\":{},",
                "\"profile\":\"{}\",\"manifest_hash\":\"{}\",",
                "\"tune_context\":{},\"cpu_id\":\"{}\",",
                "\"stable_id\":\"{}\",\"scenario\":\"{}\",",
                "\"candidate\":\"{}\",\"round\":{},\"iterations\":{},",
                "\"elapsed_ns\":{}}}"
            ),
            json_escape(metadata.backend),
            metadata.protocol_version,
            json_escape(metadata.profile),
            json_escape(metadata.manifest_hash),
            tune_context,
            json_escape(cpu_identity),
            json_escape(sample.stable_id),
            json_escape(sample.scenario),
            json_escape(sample.candidate),
            sample.round,
            sample.iterations,
            sample.elapsed_ns,
        )
        .unwrap();
    }
    Ok(document)
}

fn render_summary(
    decisions: &[Decision],
    metadata: ReportMetadata,
    options: &Options,
    cpu_identity: &str,
) -> String {
    let mut summary = String::new();
    writeln!(&mut summary, "Rust TSL variant benchmark summary").unwrap();
    writeln!(&mut summary, "backend: {}", metadata.backend).unwrap();
    writeln!(&mut summary, "profile: {}", metadata.profile).unwrap();
    writeln!(&mut summary, "manifest: {}", metadata.manifest_hash).unwrap();
    writeln!(&mut summary, "cpu: {cpu_identity}").unwrap();
    writeln!(&mut summary, "threshold: {}", options.threshold()).unwrap();
    for decision in decisions {
        writeln!(
            &mut summary,
            "{}: {} ({}, minimum improvement {})",
            decision.stable_id, decision.selected, decision.status, decision.minimum_improvement,
        )
        .unwrap();
    }
    summary
}

fn render_policy_json(document: &RustPolicyDocument) -> String {
    let mut output = String::new();
    write!(
        &mut output,
        concat!(
            "{{\"schema_version\":{},\"protocol_version\":{},",
            "\"backend\":\"{}\",\"profile\":\"{}\",",
            "\"manifest_hash\":\"{}\",\"tune_context\":{},",
            "\"cpu_id\":\"{}\",\"decisions\":["
        ),
        document.schema_version,
        document.protocol_version,
        json_escape(&document.backend),
        json_escape(&document.profile),
        json_escape(&document.manifest_hash),
        render_tune_context(&document.tune_context),
        json_escape(&document.cpu_id),
    )
    .unwrap();
    for (index, decision) in document.decisions.iter().enumerate() {
        if index != 0 {
            output.push(',');
        }
        write!(
            &mut output,
            concat!(
                "{{\"stable_id\":\"{}\",\"selected\":\"{}\",",
                "\"status\":\"{}\",\"minimum_improvement\":{}}}"
            ),
            json_escape(&decision.stable_id),
            json_escape(&decision.selected),
            json_escape(&decision.status),
            decision.minimum_improvement,
        )
        .unwrap();
    }
    output.push_str("]}\n");
    output
}

fn render_tune_context(tune_context: &TuneContext) -> String {
    let context = tune_context.build;
    let mut output = format!(
        concat!(
            "{{\"rustc_verbose_version\":\"{}\",\"cargo_verbose_version\":\"{}\",",
            "\"host\":\"{}\",",
            "\"target\":\"{}\",\"linker\":\"{}\",",
            "\"rustc_wrapper\":\"{}\",\"rustc_workspace_wrapper\":\"{}\",",
            "\"target_cpu\":\"{}\",",
            "\"target_features\":\"{}\",\"required_features\":\"{}\",",
            "\"cargo_features\":\"{}\",\"cargo_profile\":\"{}\",",
            "\"opt_level\":\"{}\",\"debug_assertions\":\"{}\",",
            "\"overflow_checks\":\"{}\",\"lto\":\"{}\",\"codegen_units\":\"{}\",",
            "\"panic\":\"{}\",\"incremental\":\"{}\",\"debug\":\"{}\",",
            "\"rustflags\":\"{}\",\"encoded_rustflags\":\"{}\",",
            "\"profile_overrides\":\"{}\",\"benchmark_codegen_contract\":\"{}\",",
            "\"external_context\":\"{}\",\"threshold\":{},\"rounds_override\":{},",
            "\"minimum_sample_ns_override\":{},\"scenario_settings\":["
        ),
        json_escape(context.rustc_verbose_version),
        json_escape(context.cargo_verbose_version),
        json_escape(context.host),
        json_escape(context.target),
        json_escape(context.linker),
        json_escape(context.rustc_wrapper),
        json_escape(context.rustc_workspace_wrapper),
        json_escape(context.target_cpu),
        json_escape(context.target_features),
        json_escape(&tune_context.required_features),
        json_escape(context.cargo_features),
        json_escape(context.cargo_profile),
        json_escape(context.opt_level),
        json_escape(context.debug_assertions),
        json_escape(context.overflow_checks),
        json_escape(context.lto),
        json_escape(context.codegen_units),
        json_escape(context.panic),
        json_escape(context.incremental),
        json_escape(context.debug),
        json_escape(context.rustflags),
        json_escape(context.encoded_rustflags),
        json_escape(context.profile_overrides),
        json_escape(context.benchmark_codegen_contract),
        json_escape(context.external_context),
        tune_context.threshold,
        json_optional_usize(tune_context.rounds_override),
        json_optional_u64(tune_context.minimum_sample_ns_override),
    );
    for (index, setting) in tune_context.scenario_settings.iter().enumerate() {
        if index != 0 {
            output.push(',');
        }
        write!(
            &mut output,
            concat!(
                "{{\"stable_id\":\"{}\",\"scenario\":\"{}\",",
                "\"rounds\":{},\"minimum_sample_ns\":{}}}"
            ),
            json_escape(&setting.stable_id),
            json_escape(&setting.scenario),
            setting.rounds,
            setting.minimum_sample_ns,
        )
        .unwrap();
    }
    output.push_str("]}");
    output
}

fn json_optional_usize(value: Option<usize>) -> String {
    value.map_or_else(|| "null".to_string(), |value| value.to_string())
}

fn json_optional_u64(value: Option<u64>) -> String {
    value.map_or_else(|| "null".to_string(), |value| value.to_string())
}

struct PendingDocument<'a> {
    path: &'a Path,
    label: &'static str,
    content: &'a str,
}

struct StagedDocument {
    path: PathBuf,
    temporary_path: PathBuf,
    backup_path: PathBuf,
    label: &'static str,
}

fn stage_documents(documents: &[PendingDocument<'_>]) -> Result<Vec<StagedDocument>, String> {
    validate_report_output_paths(
        &documents
            .iter()
            .map(|document| document.path)
            .collect::<Vec<_>>(),
    )?;
    let mut staged = Vec::with_capacity(documents.len());
    for (index, document) in documents.iter().enumerate() {
        let (temporary_path, backup_path) = staging_paths(document.path, index)?;
        let mut output = match OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary_path)
        {
            Ok(output) => output,
            Err(error) => {
                cleanup_staged(&staged);
                return Err(format!(
                    "cannot stage {} {}: {error}",
                    document.label,
                    document.path.display(),
                ));
            }
        };
        let result = output
            .write_all(document.content.as_bytes())
            .and_then(|()| output.sync_all());
        if let Err(error) = result {
            drop(output);
            cleanup_staged(&staged);
            let _ = std::fs::remove_file(&temporary_path);
            return Err(format!(
                "cannot stage {} {}: {error}",
                document.label,
                document.path.display(),
            ));
        }
        staged.push(StagedDocument {
            path: document.path.to_path_buf(),
            temporary_path,
            backup_path,
            label: document.label,
        });
    }
    Ok(staged)
}

pub(crate) fn validate_report_output_paths(paths: &[&Path]) -> Result<(), String> {
    let mut reserved = HashSet::new();
    for (index, path) in paths.iter().enumerate() {
        let (temporary_path, backup_path) = staging_paths(path, index)?;
        for candidate in [path.to_path_buf(), temporary_path, backup_path] {
            let identity = output_identity(&candidate)?;
            if !reserved.insert(identity) {
                return Err(
                    "benchmark report paths collide with reserved staging paths".to_string()
                );
            }
        }
    }
    Ok(())
}

fn staging_paths(path: &Path, index: usize) -> Result<(PathBuf, PathBuf), String> {
    let file_name = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "benchmark report path has no UTF-8 file name".to_string())?;
    Ok((
        path.with_file_name(format!(
            ".{file_name}.{}.{}.tsl-tmp",
            std::process::id(),
            index,
        )),
        path.with_file_name(format!(
            ".{file_name}.{}.{}.tsl-backup",
            std::process::id(),
            index,
        )),
    ))
}

fn commit_staged(staged: Vec<StagedDocument>) -> Result<(), String> {
    if let Err(error) = preflight_destinations(&staged) {
        cleanup_staged(&staged);
        return Err(error);
    }
    let mut backed_up = vec![false; staged.len()];
    for (index, document) in staged.iter().enumerate() {
        if document.path.exists() {
            if let Err(error) = std::fs::rename(&document.path, &document.backup_path) {
                let rollback = restore_backups(&staged, &backed_up);
                cleanup_staged(&staged);
                return Err(with_rollback_error(
                    format!(
                        "cannot preserve existing {} {}: {error}",
                        document.label,
                        document.path.display(),
                    ),
                    rollback,
                ));
            }
            backed_up[index] = true;
        }
    }
    for (index, document) in staged.iter().enumerate() {
        if let Err(error) = std::fs::rename(&document.temporary_path, &document.path) {
            let mut rollback_errors = Vec::new();
            for published in staged[..index].iter().rev() {
                if let Err(rollback_error) = std::fs::remove_file(&published.path) {
                    rollback_errors.push(format!(
                        "cannot remove partially published {}: {rollback_error}",
                        published.path.display(),
                    ));
                }
            }
            if let Err(rollback_error) = restore_backups(&staged, &backed_up) {
                rollback_errors.push(rollback_error);
            }
            cleanup_staged(&staged[index..]);
            return Err(with_rollback_error(
                format!(
                    "cannot publish {} {}: {error}",
                    document.label,
                    document.path.display(),
                ),
                if rollback_errors.is_empty() {
                    Ok(())
                } else {
                    Err(rollback_errors.join("; "))
                },
            ));
        }
    }
    for (document, had_backup) in staged.iter().zip(backed_up) {
        if had_backup {
            let _ = std::fs::remove_file(&document.backup_path);
        }
    }
    Ok(())
}

fn preflight_destinations(staged: &[StagedDocument]) -> Result<(), String> {
    for document in staged {
        if document.backup_path.exists() {
            return Err(format!(
                "cannot publish {} {}: backup path already exists",
                document.label,
                document.path.display(),
            ));
        }
        match std::fs::symlink_metadata(&document.path) {
            Ok(metadata) if !metadata.file_type().is_file() => {
                return Err(format!(
                    "cannot publish {} {}: destination must be a regular file",
                    document.label,
                    document.path.display(),
                ));
            }
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => {
                return Err(format!(
                    "cannot inspect {} {}: {error}",
                    document.label,
                    document.path.display(),
                ));
            }
        }
    }
    Ok(())
}

fn restore_backups(staged: &[StagedDocument], backed_up: &[bool]) -> Result<(), String> {
    let mut errors = Vec::new();
    for (document, had_backup) in staged.iter().zip(backed_up).rev() {
        if *had_backup {
            if let Err(error) = std::fs::rename(&document.backup_path, &document.path) {
                errors.push(format!(
                    "cannot restore {} from {}: {error}",
                    document.path.display(),
                    document.backup_path.display(),
                ));
            }
        }
    }
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors.join("; "))
    }
}

fn with_rollback_error(message: String, rollback: Result<(), String>) -> String {
    match rollback {
        Ok(()) => message,
        Err(error) => format!("{message}; rollback failed: {error}"),
    }
}

fn cleanup_staged(staged: &[StagedDocument]) {
    for document in staged {
        let _ = std::fs::remove_file(&document.temporary_path);
    }
}
