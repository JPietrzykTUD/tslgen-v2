"""Checked API twins are projected only from typed catastrophic preconditions."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.checked_api import checked_api_plan, public_call_requires_unsafe
from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_checked_api import plan_cpp_checked_api
from tslc.backend.rust import RustBackend
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.select.selector import Selector


_FIXTURES = Path(__file__).parent / "fixtures" / "checked_api"


def _lowered(
    catalog: Catalog,
    profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    backend: str,
) -> LoweredSpecialization:
    selected = Selector().select_profile(
        catalog,
        profiles["avx2"],
        primitive_name,
        ("si32",),
        backend_id=backend,
    )
    assert selected.diagnostics == ()
    slot = next(
        item
        for item in selected.selected
        if item.extension.name == "avx2"
        and item.primitive.name == primitive_name
        and item.primitive.attributes.get("mask") is None
    )
    result = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend))
    assert result.specialization is not None, result.diagnostics
    return result.specialization


def test_cpp_lane_checked_twin_has_direct_result_and_error_reference(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "extract_value_at", "cpp")
    rendered = CppBackend().render_primitive("extract_value_at", (spec,))
    docs = CppBackend().render_documentation_api_declaration(
        "extract_value_at", (spec,)
    )

    assert checked_api_plan((spec,)) is not None
    cpp_plan = plan_cpp_checked_api(
        (spec,), result_type="typename Vec::base_type"
    )
    assert cpp_plan is not None
    assert cpp_plan.failure_placeholder_expression == "typename Vec::base_type{}"
    assert cpp_plan.error_parameter_declaration.endswith("& error")
    assert "inline typename Vec::base_type extract_value_at(" in rendered
    assert "[[nodiscard]] TSL_FORCE_INLINE auto extract_value_at_checked(" in rendered
    assert "::tsl::precondition_error & error" in rendered
    assert "if (index >= Vec::lane_count())" in rendered
    assert "error = ::tsl::precondition_error::none;" in rendered
    assert "return typename Vec::base_type{};" in rendered
    assert "does not invoke the unchecked operation" in docs


def test_rust_lane_unchecked_is_unsafe_and_checked_returns_result(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "extract_value_at", "rust")
    rendered = RustBackend().render_primitive("extract_value_at", (spec,))
    internal = RustBackend().render_primitive_internal(
        "extract_value_at", (spec,)
    )
    docs = RustBackend().render_documentation_api(
        "extract_value_at", (spec,)
    )

    assert public_call_requires_unsafe((spec,))
    assert "pub unsafe fn extract_value_at<" in rendered
    assert "pub fn extract_value_at_checked<" in rendered
    assert "-> Result<S::BaseType, PreconditionError>" in rendered
    assert "if index >= S::lane_count()" in rendered
    assert "return Err(PreconditionError::IndexOutOfBounds);" in rendered
    assert "Ok(unsafe { extract_value_at::<S>(data, index) })" in rendered
    assert "pub trait Extract_value_atImpl" in internal
    assert "unsafe fn apply(" in internal
    assert "Safety: caller must uphold unsafe preconditions" in internal
    assert "/// # Errors" in docs
    assert "Returns `PreconditionError::IndexOutOfBounds`" in docs
    assert "/// # Safety" in docs


def test_total_integral_mask_test_gets_no_checked_twin_or_unsafe_surface(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "test_imask", "rust")
    rendered = RustBackend().render_primitive("test_imask", (spec,))

    assert checked_api_plan((spec,)) is None
    assert not public_call_requires_unsafe((spec,))
    assert "test_imask_checked" not in rendered
    assert "pub unsafe fn test_imask" not in rendered
    assert "pub fn test_imask" in rendered


def test_empty_specialization_group_has_no_checked_or_unsafe_api() -> None:
    assert checked_api_plan(()) is None
    assert not public_call_requires_unsafe(())


def test_insert_and_mask_set_follow_the_same_declared_lane_contract(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    for primitive_name in ("insert_value_at", "set_mask_lane"):
        cpp_spec = _lowered(catalog, machine_profiles, primitive_name, "cpp")
        cpp = CppBackend().render_primitive(primitive_name, (cpp_spec,))
        assert f"{primitive_name}_checked" in cpp
        assert "if (index >= Vec::lane_count())" in cpp

        rust_spec = _lowered(catalog, machine_profiles, primitive_name, "rust")
        rust = RustBackend().render_primitive(primitive_name, (rust_spec,))
        assert f"pub unsafe fn {primitive_name}<" in rust
        assert f"pub fn {primitive_name}_checked<" in rust
        assert "if index >= S::lane_count()" in rust


def test_rust_insert_uses_an_unchecked_storage_write(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "insert_value_at", "rust")
    assert "lane_set_unchecked" in spec.body_text
    assert "lanes[index]" not in spec.body_text


def test_checked_error_assets_are_evolution_safe_and_debug_inline_is_portable(
    render_assets,
) -> None:
    cpp = render_assets.text("tsl_core.hpp")
    rust = render_assets.text("tsl_core.rs")

    assert "#if defined(__OPTIMIZE__)" in cpp
    assert "#if defined(_DEBUG)" in cpp
    assert "#define TSL_FORCE_INLINE inline\n#endif" in cpp
    assert "#[non_exhaustive]\npub enum PreconditionError" in rust


@pytest.fixture(scope="module")
def checked_lane_cpp_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-lane-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "extract_value_at",
            "insert_value_at",
            "set_mask_lane",
            "test_imask",
        ],
        profiles=["scalar", "avx2"],
        type_tags=("si32",),
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root / "cpp" / "include"


def _cpp_compilers() -> tuple[str, ...]:
    return tuple(
        compiler
        for name in ("g++", "clang++")
        if (compiler := shutil.which(name)) is not None
    )


@pytest.mark.generated_build
def test_checked_lane_cpp_consumer_is_warning_clean_and_sanitizer_safe(
    checked_lane_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "lane_index_scalar_consumer.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        debug_binary = tmp_path / f"lane-debug-{compiler_id}"
        subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O0",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(checked_lane_cpp_project),
                str(source),
                "-o",
                str(debug_binary),
            ),
            check=True,
        )
        subprocess.run((str(debug_binary),), check=True)

    sanitizer_binary = tmp_path / "lane-sanitizer"
    subprocess.run(
        (
            compilers[0],
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(checked_lane_cpp_project),
            str(source),
            "-o",
            str(sanitizer_binary),
        ),
        check=True,
    )
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run((str(sanitizer_binary),), check=True, env=environment)


@pytest.mark.generated_build
def test_unchecked_lane_codegen_has_no_validation_branch(
    checked_lane_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "lane_index_codegen.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        assembly_path = tmp_path / f"lane-{compiler_id}.s"
        subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-fno-stack-protector",
                "-mavx2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-S",
                "-masm=intel",
                "-I",
                str(checked_lane_cpp_project),
                str(source),
                "-o",
                str(assembly_path),
            ),
            check=True,
        )
        assembly = assembly_path.read_text(encoding="utf-8")
        unchecked = re.search(
            r"^unchecked_lane:.*?(?=^\s*(?:\.size\s+unchecked_lane|\.Lfunc_end))",
            assembly,
            flags=re.MULTILINE | re.DOTALL,
        )
        checked = re.search(
            r"^checked_lane:.*?(?=^\s*(?:\.size\s+checked_lane|\.Lfunc_end))",
            assembly,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert unchecked is not None
        assert checked is not None
        assert re.search(r"\bcmp\b", unchecked.group()) is None
        assert re.search(r"\bj[a-z]+\b", unchecked.group()) is None
        assert re.search(r"\bcmp\b", checked.group()) is not None
        assert re.search(r"\bj[a-z]+\b", checked.group()) is not None
