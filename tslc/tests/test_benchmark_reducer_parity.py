"""Golden protocol fixtures for independent C++ and Rust reducers."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tslc.compiler_assets import load_default_render_assets


FIXTURE_PATH = Path(__file__).with_name("benchmark_reducer_v1.json")


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_reducer_fixture_is_target_neutral_and_complete() -> None:
    fixture = _fixture()

    assert fixture["schema_version"] == 1
    assert fixture["candidates"] == ["default", "alternative"]
    assert fixture["scenarios"] == ["throughput", "latency"]
    names = [case["name"] for case in fixture["cases"]]
    assert len(names) == len(set(names))
    assert set(names) == {
        "stable",
        "scenario_conflict",
        "dispersion_noise",
        "below_threshold",
    }
    for case in fixture["cases"]:
        assert set(case) == {"name", "scenarios", "expected"}
        assert set(case["scenarios"]) == set(fixture["scenarios"])
        assert set(case["expected"]) == {
            "selected",
            "status",
            "minimum_improvement",
        }
        assert case["expected"]["selected"] in fixture["candidates"]
        assert case["expected"]["status"] in {"selected", "inconclusive"}
        assert isinstance(case["expected"]["minimum_improvement"], (int, float))
        for scenario in fixture["scenarios"]:
            rounds = case["scenarios"][scenario]
            assert len(rounds) >= 3
            for round_samples in rounds:
                assert len(round_samples) == len(fixture["candidates"])
                assert all(
                    len(sample) == 2
                    and all(isinstance(value, int) and value > 0 for value in sample)
                    for sample in round_samples
                )


@pytest.mark.generated_build
def test_cpp_and_rust_reducers_match_shared_golden_fixture(tmp_path: Path) -> None:
    cxx = shutil.which("c++")
    rustc = shutil.which("rustc")
    if cxx is None or rustc is None:
        pytest.skip("native C++ and Rust compilers are required")

    fixture = _fixture()
    assets = load_default_render_assets()
    cpp_header = tmp_path / "tsl_benchmark_core.hpp"
    rust_core = tmp_path / "tsl_benchmark_core.rs"
    rust_reducer = tmp_path / "tsl_benchmark_reducer.rs"
    cpp_header.write_text(assets.text("tsl_benchmark_core.hpp"), encoding="utf-8")
    rust_core.write_text(assets.text("tsl_benchmark_core.rs"), encoding="utf-8")
    rust_reducer.write_text(
        assets.text("tsl_benchmark_reducer.rs"), encoding="utf-8"
    )

    cpp_source = tmp_path / "driver.cpp"
    rust_source = tmp_path / "driver.rs"
    cpp_source.write_text(_cpp_driver(fixture), encoding="utf-8")
    rust_source.write_text(_rust_driver(fixture), encoding="utf-8")
    cpp_binary = tmp_path / "cpp-reducer"
    rust_binary = tmp_path / "rust-reducer"

    compiled_cpp = _run((cxx, "-std=c++17", str(cpp_source), "-o", str(cpp_binary)))
    assert compiled_cpp.returncode == 0, compiled_cpp.stderr
    compiled_rust = _run(
        (rustc, "--edition=2021", str(rust_source), "-o", str(rust_binary))
    )
    assert compiled_rust.returncode == 0, compiled_rust.stderr

    cpp_decisions = _decisions(_run((str(cpp_binary),)))
    rust_decisions = _decisions(_run((str(rust_binary),)))
    assert cpp_decisions.keys() == rust_decisions.keys()
    expected = {case["name"]: case["expected"] for case in fixture["cases"]}
    for name in cpp_decisions:
        cpp_selected, cpp_status, cpp_score = cpp_decisions[name]
        rust_selected, rust_status, rust_score = rust_decisions[name]
        assert (cpp_selected, cpp_status) == (rust_selected, rust_status)
        assert cpp_score == pytest.approx(rust_score, abs=1e-12)
        assert cpp_selected == expected[name]["selected"]
        assert cpp_status == expected[name]["status"]
        assert cpp_score == pytest.approx(expected[name]["minimum_improvement"], abs=1e-12)


def _cpp_driver(fixture: dict[str, object]) -> str:
    threshold = repr(fixture["threshold"])
    cases = []
    for case in fixture["cases"]:
        samples = ",\n".join(
            "            tsl::benchmark::RawSample{"
            f'"fixture", "{scenario}", "{candidate}", {round_index}, '
            f"{iterations}, {elapsed}" + "}"
            for scenario in fixture["scenarios"]
            for round_index, pair in enumerate(case["scenarios"][scenario])
            for candidate, (elapsed, iterations) in zip(
                fixture["candidates"], pair, strict=True
            )
        )
        cases.append(
            "    {\n"
            "        std::vector<tsl::benchmark::RawSample> samples{\n"
            f"{samples}\n"
            "        };\n"
            "        auto decision = tsl::benchmark::reduce_candidate_set(\n"
            '            "fixture", {"default", "alternative"}, '
            f'{{"throughput", "latency"}}, samples, {threshold});\n'
            f'        std::cout << "{case["name"]}|" << decision.selected << "|"\n'
            '                  << decision.status << "|" << std::setprecision(17)\n'
            "                  << decision.minimum_improvement << '\\n';\n"
            "    }"
        )
    return (
        '#include "tsl_benchmark_core.hpp"\n'
        "#include <iomanip>\n"
        "#include <iostream>\n\n"
        "int main() {\n"
        f"{chr(10).join(cases)}\n"
        "}\n"
    )


def _rust_driver(fixture: dict[str, object]) -> str:
    threshold = repr(fixture["threshold"])
    cases = []
    for case in fixture["cases"]:
        samples = ",\n".join(
            "            RawSample {"
            f' stable_id: "fixture", scenario: "{scenario}", '
            f'candidate: "{candidate}", round: {round_index}, '
            f"iterations: {iterations}, elapsed_ns: {elapsed}" + " }"
            for scenario in fixture["scenarios"]
            for round_index, pair in enumerate(case["scenarios"][scenario])
            for candidate, (elapsed, iterations) in zip(
                fixture["candidates"], pair, strict=True
            )
        )
        cases.append(
            "    {\n"
            "        let samples = vec![\n"
            f"{samples}\n"
            "        ];\n"
            "        let decision = reduce_candidate_set(&spec, &samples, &options).unwrap();\n"
            f'        println!("{case["name"]}|{{}}|{{}}|{{:.17}}", '
            "decision.selected, decision.status, decision.minimum_improvement);\n"
            "    }"
        )
    return (
        '#[path = "tsl_benchmark_core.rs"]\n'
        "mod core;\n"
        '#[path = "tsl_benchmark_reducer.rs"]\n'
        "mod tsl_benchmark_reducer;\n"
        "mod tsl_benchmark_core { pub use crate::core::*; }\n"
        "use core::{Options, RawSample};\n"
        "use tsl_benchmark_reducer::{CandidateSetSpec, ScenarioSpec, reduce_candidate_set};\n\n"
        "static CANDIDATES: [&str; 2] = [\"default\", \"alternative\"];\n"
        "static SCENARIOS: [ScenarioSpec; 2] = [\n"
        "    ScenarioSpec { scenario: \"throughput\", rounds: 3, minimum_sample_ns: 1 },\n"
        "    ScenarioSpec { scenario: \"latency\", rounds: 3, minimum_sample_ns: 1 },\n"
        "];\n\n"
        "fn main() {\n"
        "    let options = Options::parse([\"--rounds\".to_string(), \"3\".to_string(), "
        "\"--minimum-sample-ns\".to_string(), \"1\".to_string(), "
        f'"--threshold".to_string(), "{threshold}".to_string()]).unwrap();\n'
        "    let spec = CandidateSetSpec { stable_id: \"fixture\", candidates: &CANDIDATES, "
        "scenarios: &SCENARIOS, policy_supported: true };\n"
        f"{chr(10).join(cases)}\n"
        "}\n"
    )


def _run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _decisions(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, tuple[str, str, float]]:
    assert completed.returncode == 0, completed.stderr
    decisions = {}
    for line in completed.stdout.splitlines():
        name, selected, status, score = line.split("|")
        decisions[name] = (selected, status, float(score))
    return decisions
