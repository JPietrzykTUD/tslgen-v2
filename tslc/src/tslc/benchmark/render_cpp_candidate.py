"""Render concrete C++ candidate harnesses from resolved benchmark scenarios."""

from __future__ import annotations

import json

from tslc.backend.cpp import implementation_name
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkIndexedLoadCorrectnessCase,
)
from tslc.benchmark.render_cpp_correctness import render_correctness
from tslc.benchmark.render_cpp_scenarios import render_scenario


def render_candidate_set(index: int, candidate_set: BenchmarkCandidateSet) -> str:
    """Render one candidate set without inferring any workload semantics."""

    correctness = "\n\n".join(
        render_correctness(index, candidate_index, candidate_set)
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    scenarios = "\n\n".join(
        render_scenario(index, scenario_index, candidate_set, scenario)
        for scenario_index, scenario in enumerate(candidate_set.scenarios)
    )
    scenario_runs = "\n".join(
        f"    run_scenario_{index}_{scenario_index}(set_samples, candidates, options);"
        for scenario_index, _scenario in enumerate(candidate_set.scenarios)
    )
    candidate_names = ", ".join(
        _cpp_string(candidate.variant_id) for candidate in candidate_set.candidates
    )
    scenario_names = ", ".join(
        _cpp_string(scenario.scenario_id) for scenario in candidate_set.scenarios
    )
    correctness_calls = " && ".join(
        f"correct_{index}_{candidate_index}()"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    stable_id = _cpp_string(candidate_set.stable_id)
    index_aliases = ""
    if candidate_set.key.simd_type_base_bindings:
        index_aliases = (
            f"using IndexVec_{index} = {index_vector_type(candidate_set)};\n"
            f"using IndexReg_{index} = typename IndexVec_{index}::register_type;\n"
            f"using IndexBase_{index} = typename IndexVec_{index}::base_type;\n"
        )
    return f'''using Vec_{index} = {vector_type(candidate_set)};
using Reg_{index} = typename Vec_{index}::register_type;
using Mask_{index} = typename Vec_{index}::mask_type;
using Imask_{index} = typename Vec_{index}::imask_type;
using Base_{index} = typename Vec_{index}::base_type;
using Result_{index} = {_result_type(candidate_set, index)};
{index_aliases}

{_render_invoke(index, candidate_set)}

{correctness}

{scenarios}

bool benchmark_set_{index}(std::vector<RawSample>& all_samples,
                           std::vector<Decision>& decisions,
                           Options const& options) {{
    if (!({correctness_calls})) {{
        std::cerr << "candidate correctness failed for " << {stable_id} << '\\n';
        return false;
    }}
    const std::array<std::string, {len(candidate_set.candidates)}> candidates = {{{candidate_names}}};
    const std::array<std::string, {len(candidate_set.scenarios)}> scenarios = {{{scenario_names}}};
    std::vector<RawSample> set_samples;
{scenario_runs}
    all_samples.insert(all_samples.end(), set_samples.begin(), set_samples.end());
    decisions.push_back(tsl::benchmark::reduce_candidate_set(
        {stable_id}, std::vector<std::string>(candidates.begin(), candidates.end()),
        std::vector<std::string>(scenarios.begin(), scenarios.end()), set_samples,
        options.threshold));
    return true;
}}'''


def _render_invoke(index: int, candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    implementation_arguments = ", ".join(
        (
            f"Vec_{index}",
            *((f"IndexVec_{index}",) if spec.type_params else ()),
            *((candidate_set.key.immediate,) if candidate_set.key.immediate else ()),
            *(default for _name, _type, default in spec.generic_params),
        )
    )
    params = ", ".join(
        f"{_parameter_type(kind, index)} value_{position}"
        for position, kind in enumerate(spec.param_kinds)
        if kind != "sImm"
    )
    arguments = ", ".join(
        f"value_{position}"
        for position, kind in enumerate(spec.param_kinds)
        if kind != "sImm"
    )
    branches: list[str] = []
    for candidate_index, candidate in enumerate(candidate_set.candidates):
        implementation = implementation_name(
            spec.primitive_name,
            None if candidate.is_default else candidate.variant_id,
        )
        keyword = "if" if candidate_index == 0 else "else if"
        branches.append(
            f"    {keyword} constexpr (Candidate == {candidate_index}) {{\n"
            f"        return ::tsl::detail::primitives::{implementation}"
            f"<{implementation_arguments}>::apply({arguments});\n"
            "    }"
        )
    return f'''template <std::size_t Candidate>
inline Result_{index} invoke_{index}({params}) {{
{chr(10).join(branches)}
    else {{
        static_assert(Candidate < {len(candidate_set.candidates)}, "invalid benchmark candidate");
        return Result_{index}{{}};
    }}
}}'''




def _result_type(candidate_set: BenchmarkCandidateSet, index: int) -> str:
    return {"v": f"Reg_{index}", "m": f"Mask_{index}", "s": f"Base_{index}"}[
        candidate_set.specialization.result_kind
    ]


def _parameter_type(kind: str, index: int) -> str:
    return {
        "v": f"typename ::tsl::reg_param<Vec_{index}>::type",
        "s": f"Base_{index}",
        "m": f"Mask_{index}",
        "im": f"Imask_{index}",
        "cptr": f"Base_{index} const*",
        "vidx": f"typename ::tsl::reg_param<IndexVec_{index}>::type",
    }[kind]


def vector_type(candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    return f"::tsl::simd<{spec.base_type_spelling}, ::tsl::{spec.extension_name}>"


def index_vector_type(candidate_set: BenchmarkCandidateSet) -> str:
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkIndexedLoadCorrectnessCase):
        raise ValueError("candidate set does not carry an indexed SIMD type")
    return (
        f"::tsl::simd<{correctness.index_base_spelling}, "
        f"::tsl::{candidate_set.specialization.extension_name}>"
    )


def _cpp_string(value: str) -> str:
    return json.dumps(value)


__all__ = ("index_vector_type", "render_candidate_set", "vector_type")
