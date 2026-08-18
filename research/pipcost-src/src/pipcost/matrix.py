"""Deterministic scenario expansion and plan-role lookup."""

from __future__ import annotations

from itertools import product

from pipcost.config import ExperimentConfig, StudyConfig
from pipcost.domain import Scenario


def expand_scenarios(config: ExperimentConfig) -> tuple[Scenario, ...]:
    scenarios: dict[str, Scenario] = {}
    for study in config.studies:
        for rows, first, conditional, pattern, seed, raw_batch in product(
            study.rows,
            study.first_selectivities,
            study.conditional_selectivities,
            study.patterns,
            study.seeds,
            study.batch_rows,
        ):
            batch_rows = max(rows, 1) if raw_batch == "full" else int(raw_batch)
            scenario = Scenario(
                study=study.name,
                split=study.split,
                rows=rows,
                first_selectivity=first,
                conditional_selectivity=conditional,
                pattern=pattern,
                seed=seed,
                batch_rows=batch_rows,
                simd_lanes=config.simd_lanes,
                profile=config.profile,
            )
            existing = scenarios.get(scenario.scenario_id)
            if existing is not None and existing != scenario:
                raise ValueError(f"scenario ID collision for {scenario.scenario_id}")
            scenarios[scenario.scenario_id] = scenario
    return tuple(scenarios[key] for key in sorted(scenarios))


def _study(config: ExperimentConfig, scenario: Scenario) -> StudyConfig:
    return next(item for item in config.studies if item.name == scenario.study)


def candidate_plan_ids(
    config: ExperimentConfig,
    scenario: Scenario,
) -> tuple[str, ...]:
    return tuple(sorted(_study(config, scenario).candidate_plans))


def reference_plan_ids(
    config: ExperimentConfig,
    scenario: Scenario,
) -> tuple[str, ...]:
    return tuple(sorted(_study(config, scenario).reference_plans))


def requested_plan_ids(
    config: ExperimentConfig,
    scenario: Scenario,
) -> tuple[str, ...]:
    return tuple(sorted((*candidate_plan_ids(config, scenario), *reference_plan_ids(config, scenario))))
