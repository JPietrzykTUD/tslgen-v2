"""Render direct Rust candidate calls and register benchmark batches."""

from __future__ import annotations

from tslc.backend.rust import RustBackend
from tslc.backend.rust_policy_selection import RustPolicySelectionProfile
from tslc.benchmark._render_rust_common import indent, rust_string_literal
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkRegisterScenario,
    SpecializationKey,
)
from tslc.benchmark.render_rust_correctness import render_correctness
from tslc.benchmark.render_rust_scenarios import render_scenario


def render_candidate_set(
    set_index: int,
    candidate_set: BenchmarkCandidateSet,
    *,
    profile_module: str,
    policy_selection: RustPolicySelectionProfile,
) -> str:
    if any(
        not isinstance(scenario, BenchmarkRegisterScenario)
        for scenario in candidate_set.scenarios
    ):
        raise ValueError("Rust benchmark renderer supports only register scenarios")
    backend = RustBackend(emit_target_features=False)
    selected_keys = {selection.key for selection in policy_selection.selections}
    selection_key = (
        candidate_set.key if candidate_set.key in selected_keys else None
    )
    vector = backend.concrete_vector_type(candidate_set.specialization)
    invokes = "\n\n".join(
        _render_invoke(
            backend,
            set_index,
            candidate_index,
            candidate_set,
            profile_module=profile_module,
            selection_key=selection_key,
        )
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    correctness = "\n\n".join(
        render_correctness(
            set_index,
            candidate_index,
            candidate_set,
            profile_module=profile_module,
        )
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    scenarios = "\n\n".join(
        render_scenario(
            set_index,
            scenario_index,
            candidate_set,
            scenario,
            profile_module=profile_module,
        )
        for scenario_index, scenario in enumerate(candidate_set.scenarios)
        if isinstance(scenario, BenchmarkRegisterScenario)
    )
    correctness_calls = "\n".join(
        f"    correct_{set_index}_{candidate_index}()?;"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    scenario_calls = "\n".join(
        f"    run_scenario_{set_index}_{scenario_index}(options, samples)?;"
        for scenario_index, _scenario in enumerate(candidate_set.scenarios)
    )
    candidates = ", ".join(
        rust_string_literal(candidate.variant_id)
        for candidate in candidate_set.candidates
    )
    scenarios_specs = "\n".join(
        "    ScenarioSpec { "
        f"scenario: {rust_string_literal(scenario.scenario_id)}, "
        f"rounds: {scenario.timing.rounds}, "
        f"minimum_sample_ns: {scenario.timing.minimum_sample_ns}u64 "
        "},"
        for scenario in candidate_set.scenarios
    )
    return f"""type Vec_{set_index} = {vector};
type Reg_{set_index} = <Vec_{set_index} as SimdVector>::RegisterType;
type Base_{set_index} = <Vec_{set_index} as SimdVector>::BaseType;
const CANDIDATES_{set_index}: [&str; {len(candidate_set.candidates)}] = [{candidates}];
const SCENARIOS_{set_index}: [ScenarioSpec; {len(candidate_set.scenarios)}] = [
{scenarios_specs}
];

{invokes}

{correctness}

{scenarios}

fn correct_candidate_set_{set_index}() -> Result<(), String> {{
{correctness_calls}
    Ok(())
}}

fn run_candidate_set_{set_index}(
    options: &Options,
    samples: &mut Vec<RawSample>,
) -> Result<(), String> {{
{scenario_calls}
    Ok(())
}}"""


def _render_invoke(
    backend: RustBackend,
    set_index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    *,
    profile_module: str,
    selection_key: SpecializationKey | None,
) -> str:
    spec = candidate_set.specialization
    parameters = tuple(
        f"value_{position}: Reg_{set_index}"
        for position, kind in enumerate(spec.param_kinds)
        if kind == "v"
    )
    if len(parameters) != len(spec.param_kinds):
        raise ValueError("Rust register benchmark candidates require vector parameters")
    arguments = tuple(
        f"value_{position}" for position, _kind in enumerate(spec.param_kinds)
    )
    candidate = candidate_set.candidates[candidate_index]
    expression = backend.render_direct_implementation_call(
        spec,
        None if candidate.is_default else candidate.variant_id,
        arguments,
        module_prefix=f"crate::{profile_module}",
        overload_parameter_positions=candidate_set.key.overload_parameter_positions,
        selection_key=selection_key,
    )
    return f"""fn invoke_{set_index}_{candidate_index}(
{indent(',\n'.join(parameters), 4)}
) -> Reg_{set_index} {{
    {expression}
}}"""


__all__ = ("render_candidate_set",)
