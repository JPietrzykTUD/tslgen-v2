//! Conservative reduction of validated Rust benchmark samples.

use std::collections::HashSet;

use crate::tsl_benchmark_core::{Options, RawSample};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ScenarioSpec {
    pub scenario: &'static str,
    pub rounds: usize,
    pub minimum_sample_ns: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CandidateSetSpec {
    pub stable_id: &'static str,
    pub candidates: &'static [&'static str],
    pub scenarios: &'static [ScenarioSpec],
    pub policy_supported: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Decision {
    pub stable_id: String,
    pub selected: String,
    pub status: String,
    pub minimum_improvement: f64,
}

pub fn reduce_profile(
    specs: &[CandidateSetSpec],
    samples: &[RawSample],
    options: &Options,
) -> Result<Vec<Decision>, String> {
    let mut decisions = reduce_profile_observations(specs, samples, options)?;
    for (spec, decision) in specs.iter().zip(&mut decisions) {
        if !spec.policy_supported {
            decision.selected = "default".to_string();
            decision.status = "report_only".to_string();
            decision.minimum_improvement = 0.0;
        }
    }
    validate_decisions(specs, &decisions, options.threshold())?;
    Ok(decisions)
}

pub fn reduce_profile_observations(
    specs: &[CandidateSetSpec],
    samples: &[RawSample],
    options: &Options,
) -> Result<Vec<Decision>, String> {
    validate_specs(specs)?;
    if !options.threshold().is_finite() || !(0.0..1.0).contains(&options.threshold()) {
        return Err("reducer threshold must be finite and in [0, 1)".to_string());
    }
    for sample in samples {
        if !specs.iter().any(|spec| spec.stable_id == sample.stable_id) {
            return Err(format!(
                "benchmark sample has unknown stable ID {}",
                sample.stable_id
            ));
        }
    }

    let mut decisions = Vec::with_capacity(specs.len());
    for spec in specs {
        let set_samples = samples
            .iter()
            .filter(|sample| sample.stable_id == spec.stable_id)
            .cloned()
            .collect::<Vec<_>>();
        decisions.push(reduce_candidate_set(spec, &set_samples, options)?);
    }
    Ok(decisions)
}

pub fn reduce_candidate_set(
    spec: &CandidateSetSpec,
    samples: &[RawSample],
    options: &Options,
) -> Result<Decision, String> {
    validate_spec(spec)?;
    validate_sample_inventory(spec, samples, options)?;

    let mut best = Decision {
        stable_id: spec.stable_id.to_string(),
        selected: "default".to_string(),
        status: "inconclusive".to_string(),
        minimum_improvement: 0.0,
    };
    for candidate in &spec.candidates[1..] {
        let mut dominates = true;
        let mut minimum_improvement = 1.0f64;
        for scenario in spec.scenarios {
            let rounds = options.rounds(scenario.rounds);
            let mut improvements = Vec::with_capacity(rounds);
            let mut wins = 0usize;
            for round in 0..rounds {
                let baseline = sample(samples, scenario.scenario, "default", round)?;
                let alternative = sample(samples, scenario.scenario, candidate, round)?;
                let baseline_ns = baseline.elapsed_ns as f64 / baseline.iterations as f64;
                let alternative_ns = alternative.elapsed_ns as f64 / alternative.iterations as f64;
                let improvement = (baseline_ns - alternative_ns) / baseline_ns;
                if !baseline_ns.is_finite()
                    || !alternative_ns.is_finite()
                    || !improvement.is_finite()
                {
                    return Err(format!(
                        "benchmark sample produced a non-finite value for {}/{}/{round}",
                        spec.stable_id, scenario.scenario,
                    ));
                }
                improvements.push(improvement);
                if improvement > 0.0 {
                    wins += 1;
                }
            }
            if improvements.len() < 3 {
                return Err(format!(
                    "benchmark scenario {}/{} has fewer than three paired rounds",
                    spec.stable_id, scenario.scenario,
                ));
            }
            let central = median(&improvements)?;
            let deviations = improvements
                .iter()
                .map(|improvement| (improvement - central).abs())
                .collect::<Vec<_>>();
            let dispersion = median(&deviations)?;
            let required_wins = (2 * improvements.len() + 2) / 3;
            if central < options.threshold()
                || wins < required_wins
                || dispersion > 0.02f64.max(central * 0.75)
            {
                dominates = false;
                break;
            }
            minimum_improvement = minimum_improvement.min(central);
        }
        if dominates && minimum_improvement > best.minimum_improvement {
            best.selected = (*candidate).to_string();
            best.status = "selected".to_string();
            best.minimum_improvement = minimum_improvement;
        }
    }
    Ok(best)
}

pub fn validate_specs(specs: &[CandidateSetSpec]) -> Result<(), String> {
    if specs.is_empty() {
        return Err("benchmark profile has no candidate sets".to_string());
    }
    let mut stable_ids = HashSet::new();
    for spec in specs {
        validate_spec(spec)?;
        if !stable_ids.insert(spec.stable_id) {
            return Err(format!("duplicate benchmark stable ID {}", spec.stable_id));
        }
    }
    Ok(())
}

fn validate_spec(spec: &CandidateSetSpec) -> Result<(), String> {
    if spec.stable_id.is_empty() {
        return Err("benchmark stable ID cannot be empty".to_string());
    }
    if spec.candidates.len() < 2 || spec.candidates[0] != "default" {
        return Err(format!(
            "benchmark candidate set {} must start with default and include an alternative",
            spec.stable_id,
        ));
    }
    let mut candidates = HashSet::new();
    for candidate in spec.candidates {
        if candidate.is_empty() || !candidates.insert(*candidate) {
            return Err(format!(
                "benchmark candidate set {} has an empty or duplicate candidate",
                spec.stable_id,
            ));
        }
    }
    if spec.scenarios.is_empty() {
        return Err(format!(
            "benchmark candidate set {} has no scenarios",
            spec.stable_id,
        ));
    }
    let mut scenarios = HashSet::new();
    for scenario in spec.scenarios {
        if scenario.scenario.is_empty() || !scenarios.insert(scenario.scenario) {
            return Err(format!(
                "benchmark candidate set {} has an empty or duplicate scenario",
                spec.stable_id,
            ));
        }
        if scenario.rounds < 3 || scenario.minimum_sample_ns == 0 {
            return Err(format!(
                "benchmark scenario {}/{} has invalid timing settings",
                spec.stable_id, scenario.scenario,
            ));
        }
    }
    Ok(())
}

fn validate_sample_inventory(
    spec: &CandidateSetSpec,
    samples: &[RawSample],
    options: &Options,
) -> Result<(), String> {
    let expected = spec
        .scenarios
        .iter()
        .map(|scenario| options.rounds(scenario.rounds) * spec.candidates.len())
        .sum::<usize>();
    if samples.len() != expected {
        return Err(format!(
            "benchmark candidate set {} expected {expected} samples, got {}",
            spec.stable_id,
            samples.len(),
        ));
    }
    let mut identities = HashSet::new();
    for value in samples {
        if value.stable_id != spec.stable_id {
            return Err(format!(
                "benchmark sample belongs to foreign stable ID {}",
                value.stable_id,
            ));
        }
        let Some(scenario) = spec
            .scenarios
            .iter()
            .find(|scenario| scenario.scenario == value.scenario)
        else {
            return Err(format!(
                "benchmark sample has unknown scenario {}/{}",
                spec.stable_id, value.scenario,
            ));
        };
        if !spec.candidates.contains(&value.candidate) {
            return Err(format!(
                "benchmark sample has unknown candidate {}/{}",
                spec.stable_id, value.candidate,
            ));
        }
        if value.round >= options.rounds(scenario.rounds) {
            return Err(format!(
                "benchmark sample has out-of-range round for {}/{}",
                spec.stable_id, value.scenario,
            ));
        }
        if value.iterations == 0 || value.elapsed_ns == 0 {
            return Err(format!(
                "benchmark sample has zero iterations or duration for {}/{}/{}",
                spec.stable_id, value.scenario, value.candidate,
            ));
        }
        if !identities.insert((value.scenario, value.candidate, value.round)) {
            return Err(format!(
                "duplicate benchmark sample for {}/{}/{}/{}",
                spec.stable_id, value.scenario, value.candidate, value.round,
            ));
        }
    }
    for scenario in spec.scenarios {
        for candidate in spec.candidates {
            for round in 0..options.rounds(scenario.rounds) {
                if !identities.contains(&(scenario.scenario, *candidate, round)) {
                    return Err(format!(
                        "missing benchmark sample for {}/{}/{candidate}/{round}",
                        spec.stable_id, scenario.scenario,
                    ));
                }
            }
        }
    }
    Ok(())
}

fn sample<'a>(
    samples: &'a [RawSample],
    scenario: &str,
    candidate: &str,
    round: usize,
) -> Result<&'a RawSample, String> {
    samples
        .iter()
        .find(|value| {
            value.scenario == scenario && value.candidate == candidate && value.round == round
        })
        .ok_or_else(|| format!("missing paired sample for {scenario}/{candidate}/{round}"))
}

fn median(values: &[f64]) -> Result<f64, String> {
    if values.is_empty() || values.iter().any(|value| !value.is_finite()) {
        return Err("cannot reduce empty or non-finite benchmark values".to_string());
    }
    let mut ordered = values.to_vec();
    ordered.sort_by(|left, right| left.total_cmp(right));
    let middle = ordered.len() / 2;
    let result = if ordered.len() % 2 == 0 {
        (ordered[middle - 1] + ordered[middle]) / 2.0
    } else {
        ordered[middle]
    };
    if result.is_finite() {
        Ok(result)
    } else {
        Err("benchmark median is non-finite".to_string())
    }
}

pub fn validate_decisions(
    specs: &[CandidateSetSpec],
    decisions: &[Decision],
    threshold: f64,
) -> Result<(), String> {
    if specs.len() != decisions.len() {
        return Err("benchmark policy has missing or unexpected decisions".to_string());
    }
    let mut stable_ids = HashSet::new();
    for (spec, decision) in specs.iter().zip(decisions) {
        if decision.stable_id != spec.stable_id || !stable_ids.insert(decision.stable_id.as_str()) {
            return Err(
                "benchmark policy has duplicate, missing, or reordered decisions".to_string(),
            );
        }
        if !spec.candidates.contains(&decision.selected.as_str()) {
            return Err(format!(
                "benchmark policy selects unavailable candidate {}/{}",
                decision.stable_id, decision.selected,
            ));
        }
        if !decision.minimum_improvement.is_finite() {
            return Err(format!(
                "benchmark policy has non-finite improvement for {}",
                decision.stable_id,
            ));
        }
        if decision.selected == "default" {
            if !matches!(decision.status.as_str(), "inconclusive" | "report_only")
                || decision.minimum_improvement != 0.0
            {
                return Err(format!(
                    "benchmark default decision has invalid status or score for {}",
                    decision.stable_id,
                ));
            }
        } else if decision.status != "selected"
            || !spec.policy_supported
            || decision.minimum_improvement < threshold
        {
            return Err(format!(
                "benchmark alternative decision is not policy-valid for {}",
                decision.stable_id,
            ));
        }
    }
    Ok(())
}
