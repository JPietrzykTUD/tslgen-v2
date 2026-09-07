"""Typed checked contracts for generated whole-array algorithms."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.algorithm_contracts import (
    ALGORITHM_CONTRACTS,
    AlgorithmContract,
    AlgorithmAliasRule,
    AlgorithmMaskStorageKind,
    AlgorithmRangeBinding,
    AlgorithmRangeCondition,
    AlgorithmRangeConditionKind,
    AlgorithmRangeRole,
    AlgorithmResultKind,
)
from tslc.backend.cpp_algorithm_contracts import (
    render_cpp_algorithm_check,
    render_cpp_checked_algorithm_definition,
    render_cpp_checked_algorithm_definitions,
)
from tslc.backend.rust_algorithm_contracts import (
    render_rust_algorithm_check,
    render_rust_algorithm_error_docs,
    render_rust_scaled_checked_algorithm,
    rust_algorithm_contract_holes,
)
from tslc.catalog.preconditions import PreconditionErrorKind
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors


_FIXTURES = Path(__file__).parent / "fixtures" / "checked_api"


@pytest.fixture(scope="module")
def algorithm_checked_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("algorithm-checked-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "load", "store"],
        profiles=["scalar"],
        type_tags=["si32"],
        backends=["cpp", "rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root


def test_transform_pilot_contracts_are_typed_and_ordered() -> None:
    unary = ALGORITHM_CONTRACTS["transform_unary"]
    binary = ALGORITHM_CONTRACTS["transform_binary"]

    assert unary.result_kind is AlgorithmResultKind.VOID
    assert unary.alias_rules[0].allow_exact_alias
    assert unary.alias_rules[0].readable_range_names == ("input",)
    assert unary.conditions == (
        AlgorithmRangeCondition(
            AlgorithmRangeConditionKind.COVERS,
            "output",
            "input",
            PreconditionErrorKind.INSUFFICIENT_OUTPUT,
        ),
    )
    assert tuple(condition.range_name for condition in binary.conditions) == (
        "right",
        "output",
    )
    assert tuple(condition.error for condition in binary.conditions) == (
        PreconditionErrorKind.INSUFFICIENT_INPUT,
        PreconditionErrorKind.INSUFFICIENT_OUTPUT,
    )


def test_algorithm_contract_registry_covers_every_checked_family() -> None:
    assert len(ALGORITHM_CONTRACTS) == 47
    assert {
        condition.kind
        for contract in ALGORITHM_CONTRACTS.values()
        for condition in contract.conditions
    } == {
        AlgorithmRangeConditionKind.COVERS,
        AlgorithmRangeConditionKind.MASK_COVERS,
        AlgorithmRangeConditionKind.SELECTED_ADDRESSES,
    }
    assert {
        binding.mask_storage
        for contract in ALGORITHM_CONTRACTS.values()
        for binding in contract.ranges
        if binding.mask_storage is not None
    } == {
        AlgorithmMaskStorageKind.INTEGRAL_CHUNKS,
        AlgorithmMaskStorageKind.LAYOUT_STORAGE,
    }


def test_generated_checked_surface_exactly_projects_the_registry() -> None:
    assets = load_default_render_assets()
    holes = rust_algorithm_contract_holes()
    rust = assets.fill("tsl_algorithm.rs", **holes)
    profile = assets.fill("rust_algo_wrappers.rs", **holes)
    expected = set(ALGORITHM_CONTRACTS)
    expected_scaled = {
        f"{contract.name}_scaled"
        for contract in ALGORITHM_CONTRACTS.values()
        if any(
            binding.role is AlgorithmRangeRole.DRIVING_INDEX
            for binding in contract.ranges
        )
    }
    for surface in (rust, profile):
        checked = set(
            re.findall(
                r"^\s*pub fn ([a-z_]+)_checked<",
                surface,
                flags=re.MULTILINE,
            )
        )
        assert checked == expected | expected_scaled
        aliases = set(
            re.findall(
                r"^\s*pub use self::[a-z_]+_raw as ([a-z_]+);",
                surface,
                flags=re.MULTILINE,
            )
        )
        assert aliases == expected

    for contract in ALGORITHM_CONTRACTS.values():
        start = rust.index(f"pub fn {contract.name}_checked<")
        end = rust.index("\n/// # Safety", start)
        checked_definition = rust[start:end]
        if contract.result_kind is AlgorithmResultKind.VOID:
            assert "Ok(unsafe {" not in checked_definition
            assert "Ok(())" in checked_definition
        else:
            assert "Ok(unsafe {" in checked_definition

    cpp = render_cpp_checked_algorithm_definitions()
    cpp_checked = set(
        re.findall(r"\b([a-z_]+)_checked\(", cpp)
    )
    expected_cpp = {
        contract.name
        for contract in ALGORITHM_CONTRACTS.values()
        if not any(
            binding.mask_storage is AlgorithmMaskStorageKind.LAYOUT_STORAGE
            for binding in contract.ranges
        )
    }
    assert cpp_checked == expected_cpp


def test_contract_rejects_an_output_condition_with_an_input_error() -> None:
    with pytest.raises(ValueError, match="error disagrees with its range role"):
        AlgorithmContract(
            name="invalid",
            ranges=(
                AlgorithmRangeBinding(
                    "input", AlgorithmRangeRole.DRIVING_INPUT
                ),
                AlgorithmRangeBinding(
                    "output", AlgorithmRangeRole.VALUE_OUTPUT
                ),
            ),
            conditions=(
                AlgorithmRangeCondition(
                    AlgorithmRangeConditionKind.COVERS,
                    "output",
                    "input",
                    PreconditionErrorKind.INSUFFICIENT_INPUT,
                ),
            ),
            result_kind=AlgorithmResultKind.VOID,
        )


def test_backend_checks_project_the_typed_binding_names() -> None:
    contract = ALGORITHM_CONTRACTS["transform_unary"]
    changed = replace(
        contract,
        ranges=(
            AlgorithmRangeBinding("source", AlgorithmRangeRole.DRIVING_INPUT),
            AlgorithmRangeBinding("destination", AlgorithmRangeRole.VALUE_OUTPUT),
        ),
        conditions=(
            replace(
                contract.conditions[0],
                range_name="destination",
                reference_name="source",
            ),
        ),
        alias_rules=(
            AlgorithmAliasRule(
                "destination", ("source",), allow_exact_alias=True
            ),
        ),
    )

    assert "destination.len() < source.len()" in render_rust_algorithm_check(
        changed
    )
    cpp = render_cpp_algorithm_check(changed)
    assert "detail::range_size(destination)" in cpp
    assert "detail::range_size(source)" in cpp

    selected = ALGORITHM_CONTRACTS["transform_selected_unary"]
    default_docs = render_rust_algorithm_error_docs(selected)
    scaled_docs = render_rust_algorithm_error_docs(
        selected, scaled_selected=True
    )
    assert "PreconditionError::Misaligned" not in default_docs
    assert "PreconditionError::Misaligned" in scaled_docs

    renamed_selected = replace(
        selected,
        ranges=tuple(
            replace(
                binding,
                name={
                    AlgorithmRangeRole.DRIVING_INDEX: "rows",
                    AlgorithmRangeRole.SELECTED_INPUT: "source_values",
                    AlgorithmRangeRole.VALUE_OUTPUT: "destination_values",
                }.get(binding.role, binding.name),
            )
            for binding in selected.ranges
        ),
        conditions=tuple(
            replace(
                condition,
                range_name={
                    "input": "source_values",
                    "output": "destination_values",
                }.get(condition.range_name, condition.range_name),
                reference_name={
                    "indices": "rows",
                }.get(condition.reference_name, condition.reference_name),
            )
            for condition in selected.conditions
        ),
        alias_rules=tuple(
            replace(
                rule,
                writable_range_name="destination_values",
                readable_range_names=tuple(
                    {
                        "input": "source_values",
                        "indices": "rows",
                    }.get(name, name)
                    for name in rule.readable_range_names
                ),
            )
            for rule in selected.alias_rules
        ),
    )
    rendered_selected = render_rust_scaled_checked_algorithm(renamed_selected)
    assert "rows.as_ptr()" in rendered_selected
    assert "source_values.as_ptr()" in rendered_selected
    assert "destination_values.as_mut_ptr()" in rendered_selected

    rendered_cpp = render_cpp_checked_algorithm_definition(renamed_selected)
    assert "class RowsRange" in rendered_cpp
    assert "class SourceValuesRange" in rendered_cpp
    assert "class DestinationValuesRange" in rendered_cpp
    assert "const RowsRange& rows" in rendered_cpp
    assert "const SourceValuesRange& source_values" in rendered_cpp
    assert "DestinationValuesRange& destination_values" in rendered_cpp


def test_generated_transform_checked_surfaces_use_contract_guards(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "mul", "load", "store"],
        profiles=["scalar"],
        type_tags=["si32"],
        backends=["cpp", "rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }

    cpp = artifacts["cpp/include/tsl_algorithm_checked.hpp"]
    assert "transform_unary_checked(" in cpp
    assert "precondition_error::insufficient_output" in cpp
    assert "precondition_error::overlapping_ranges" in cpp
    binary = cpp[cpp.index("transform_binary_checked(") :]
    binary_signature = binary[: binary.index("{")]
    assert "class Alignment" not in binary_signature
    assert "transform_binary<Parallelism, alignment::detect>" in binary
    assert binary.index("range_size(right)") < binary.index(
        "range_size(output)"
    )

    rust = artifacts["rust/src/tsl_algorithm.rs"]
    profile = artifacts["rust/src/tsl_scalar.rs"]
    assert "pub fn transform_unary_checked<" in rust
    assert "return Err(crate::PreconditionError::InsufficientOutput);" in rust
    assert "pub use self::transform_unary_raw as transform_unary;" in rust
    assert "pub fn transform_binary_checked<" in profile
    assert "pub use self::transform_binary_raw as transform_binary;" in profile
    assert "/// # Errors" in rust
    assert "`crate::PreconditionError::InsufficientOutput`" in rust
    assert "/// Checked profile wrapper for `transform_binary`." in profile
    checked_binary = rust[
        rust.index("pub fn transform_binary_checked<") : rust.index(
            "pub unsafe fn transform_binary_raw<"
        )
    ]
    assert "assert" not in checked_binary
    cpp_binary = cpp[
        cpp.index("Checked range form of `transform_binary`") :
        cpp.index("Fixed-width checked range form of `transform_binary`")
    ]
    assert "@par Errors" in cpp_binary
    assert "`precondition_error::insufficient_input`" in cpp_binary
    assert "`precondition_error::overlapping_ranges`" in cpp_binary


@pytest.mark.generated_build
def test_cpp_transform_checked_pilot_preserves_outputs_on_failure(
    algorithm_checked_project: Path,
    tmp_path: Path,
) -> None:
    compilers = tuple(
        compiler
        for name in ("g++", "clang++")
        if (compiler := shutil.which(name)) is not None
    )
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "algorithm_transform_consumer.cpp"
    include = algorithm_checked_project / "cpp" / "include"
    for compiler in compilers:
        binary = tmp_path / f"algorithm-{Path(compiler).name.replace('+', 'x')}"
        completed = subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fno-exceptions",
                "-DTSL_PROFILE_SCALAR=1",
                "-I",
                str(include),
                str(source),
                "-o",
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        subprocess.run((str(binary),), check=True)


@pytest.mark.generated_build
def test_rust_transform_checked_pilot_preserves_outputs_on_failure(
    algorithm_checked_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    project = algorithm_checked_project / "rust"
    source = _FIXTURES / "algorithm_transform_consumer.rs"
    binary_source = project / "src" / "bin"
    binary_source.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, binary_source / source.name)
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(tmp_path / "cargo-target")
    completed = subprocess.run(
        (cargo, "run", "--release", "--bin", "algorithm_transform_consumer"),
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
