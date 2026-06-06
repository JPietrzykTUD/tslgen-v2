from __future__ import annotations

import ast
from pathlib import Path

from tslgen.domain.catalog import ExtensionCatalog, TypeTag
from tslgen.domain.machine_profiles import MachineProfileName
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceLoader
from tslgen.pipeline import (
    SelectedPrimitiveBodyRenderEntry,
    SelectedPrimitiveProjectResult,
    build_primitive_project_artifacts_from_selected_bodies,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog
from tslgen.pipeline.build_verifier import (
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering.generated_project import build_generated_project_render_model
from tslgen.syntax.parser import TslParser


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"
_LANGUAGE_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"
_TYPES_PATH = _REPO_ROOT / "tsldata" / "detail" / "types.tsl"
_EXTENSIONS_PATH = _REPO_ROOT / "tsldata" / "extensions" / "extension.tsl"
_FUNDAMENTAL_PATH = (
    _REPO_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
)
_PIPELINE_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "primitive_project_pipeline.py"
)
_GENERATED_PROJECT_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "rendering" / "generated_project.py"
)
_INTEGER_TYPE_TAGS = ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64")
_FLOAT_TYPE_TAGS = ("f32", "f64")
_SIGNED_INTEGER_SUFFIX_BY_TYPE_TAG = {
    "si8": "epi8",
    "ui8": "epi8",
    "si16": "epi16",
    "ui16": "epi16",
    "si32": "epi32",
    "ui32": "epi32",
    "si64": "epi64",
    "ui64": "epi64",
}
_FLOAT_SUFFIX_BY_TYPE_TAG = {
    "f32": "ps",
    "f64": "pd",
}
_REGISTER_TYPE_BY_TYPE_TAG = {
    "f32": ("__m512", "core::arch::x86_64::__m512"),
    "f64": ("__m512d", "core::arch::x86_64::__m512d"),
    **{
        type_tag: ("__m512i", "core::arch::x86_64::__m512i")
        for type_tag in _INTEGER_TYPE_TAGS
    },
}
_SELECTED_AVX512_UNMASKED_BINARY_ARITHMETIC_MATRIX = tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name=primitive_name,
        selector_path=("avx512", "?i?"),
        extension="avx512",
        type_tag=type_tag,
        function_name=f"{primitive_name}_avx512_{type_tag}",
        parameters=("left", "right"),
    )
    for primitive_name in ("add", "sub")
    for type_tag in _INTEGER_TYPE_TAGS
) + tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name=primitive_name,
        selector_path=("avx512", "f?"),
        extension="avx512",
        type_tag=type_tag,
        function_name=f"{primitive_name}_avx512_{type_tag}",
        parameters=("left", "right"),
    )
    for primitive_name in ("add", "sub")
    for type_tag in _FLOAT_TYPE_TAGS
)


def test_m253_avx512_feature_options_prefer_canonical_normalized_spellings() -> None:
    model = _project_model_for_profiles(("skylake",))
    profile = _profile(model.cpp.profiles, "skylake")

    cpp_options = tuple(str(option) for option in profile.cpp_target_feature_options)
    rust_features = tuple(str(feature) for feature in profile.rust_target_features)

    for option in ("-mavx512f", "-mavx512cd", "-mavx512vl", "-mavx512dq", "-mavx512bw"):
        assert option in cpp_options
    for feature in ("+avx512f", "+avx512cd", "+avx512vl", "+avx512dq", "+avx512bw"):
        assert feature in rust_features
    for legacy_alias in ("avx3f", "avx3cd", "avx3vl", "avx3dq", "avx3bw"):
        assert f"-m{legacy_alias}" not in cpp_options
        assert f"+{legacy_alias}" not in rust_features


def test_m253_feature_options_preserve_explicit_profile_alternatives() -> None:
    model = _project_model_for_profiles(("icelake-rockerlake",))
    profile = _profile(model.cpp.profiles, "icelake-rockerlake")

    cpp_options = tuple(str(option) for option in profile.cpp_target_feature_options)
    rust_features = tuple(str(feature) for feature in profile.rust_target_features)

    assert "-mavx512f" in cpp_options
    assert "+avx512f" in rust_features
    for spelling in ("vpclmulqdq", "gfni", "vaes"):
        assert f"-m{spelling}" in cpp_options
        assert f"+{spelling}" in rust_features
    for canonical_with_underscore in (
        "avx512_vpclmulqdq",
        "avx512_gfni",
        "avx512_vaes",
    ):
        assert f"-m{canonical_with_underscore}" not in cpp_options
        assert f"+{canonical_with_underscore}" not in rust_features


def test_m253_all_avx512_profiles_avoid_legacy_avx3_output_spellings() -> None:
    profile_names = _known_avx512_profile_names()
    assert profile_names == (
        "cannonlake",
        "cascadelake",
        "cooperlake",
        "icelake-rockerlake",
        "kml",
        "knl",
        "sapphirerapids",
        "skylake",
        "tigerlake",
        "zen4",
        "zen5",
    )
    model = _project_model_for_profiles(profile_names)

    for profile in (*model.cpp.profiles, *model.rust.profiles):
        assert not any(
            "avx3" in str(option_or_feature)
            for option_or_feature in (
                *profile.cpp_target_feature_options,
                *profile.rust_target_features,
            )
        ), profile.profile_name

    icelake = _profile(model.cpp.profiles, "icelake-rockerlake")
    assert "-mvpclmulqdq" in tuple(str(option) for option in icelake.cpp_target_feature_options)
    assert "+vpclmulqdq" in tuple(str(feature) for feature in icelake.rust_target_features)


def test_m253_real_avx512_unmasked_binary_arithmetic_matrix_renders_typed_calls() -> None:
    result = _build_real_avx512_unmasked_binary_arithmetic_matrix()

    assert result.diagnostics == ()
    assert result.model is not None
    assert len(result.selections) == len(_SELECTED_AVX512_UNMASKED_BINARY_ARITHMETIC_MATRIX)
    assert {selection.primitive.name for selection in result.selections} == {"add", "sub"}
    assert {selection.body_envelope.selector_path for selection in result.selections} == {
        ("avx512", "?i?"),
        ("avx512", "f?"),
    }
    assert {selection.type_tag for selection in result.selections} == {
        TypeTag(type_tag) for type_tag in (*_INTEGER_TYPE_TAGS, *_FLOAT_TYPE_TAGS)
    }

    by_path = _artifact_content_by_path(result)
    assert tuple(by_path) == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/skylake.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/skylake.rs",
        "rust/tests/smoke.rs",
    )

    cmake = by_path["cpp/CMakeLists.txt"]
    cargo = by_path["rust/Cargo.toml"]
    assert "-mavx512f" in cmake
    assert "-mavx3f" not in cmake
    assert "+avx512f" in cargo
    assert "+avx3f" not in cargo

    cpp_profile = by_path["cpp/include/profiles/skylake.hpp"]
    rust_profile = by_path["rust/src/profiles/skylake.rs"]
    assert "#include <immintrin.h>" in cpp_profile

    for primitive_name in ("add", "sub"):
        for type_tag, suffix in _SIGNED_INTEGER_SUFFIX_BY_TYPE_TAG.items():
            _assert_cpp_function(
                cpp_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type="__m512i",
                call=f"_mm512_{primitive_name}_{suffix}(left, right)",
            )
            _assert_rust_function(
                rust_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type="core::arch::x86_64::__m512i",
                call=f"core::arch::x86_64::_mm512_{primitive_name}_{suffix}(left, right)",
            )

        for type_tag, suffix in _FLOAT_SUFFIX_BY_TYPE_TAG.items():
            cpp_register, rust_register = _REGISTER_TYPE_BY_TYPE_TAG[type_tag]
            _assert_cpp_function(
                cpp_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type=cpp_register,
                call=f"_mm512_{primitive_name}_{suffix}(left, right)",
            )
            _assert_rust_function(
                rust_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type=rust_register,
                call=f"core::arch::x86_64::_mm512_{primitive_name}_{suffix}(left, right)",
            )

    for width in ("8", "16", "32", "64"):
        assert f"_mm512_add_epu{width}" not in cpp_profile
        assert f"_mm512_sub_epu{width}" not in cpp_profile
        assert f"core::arch::x86_64::_mm512_add_epu{width}" not in rust_profile
        assert f"core::arch::x86_64::_mm512_sub_epu{width}" not in rust_profile

    assert "?i?" not in cpp_profile
    assert "avx512_?i?" not in cpp_profile
    assert "?i?" not in rust_profile
    assert "avx512_?i?" not in rust_profile
    assert "core::arch::x86_64::core::arch::x86_64" not in rust_profile


def test_m253_real_avx512_unmasked_binary_arithmetic_matrix_is_deterministic() -> None:
    first = _build_real_avx512_unmasked_binary_arithmetic_matrix()
    second = _build_real_avx512_unmasked_binary_arithmetic_matrix()

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m253_real_avx512_unmasked_binary_arithmetic_matrix_builds_cpp_and_rust(
    tmp_path: Path,
) -> None:
    result = _build_real_avx512_unmasked_binary_arithmetic_matrix()

    assert result.diagnostics == ()
    assert result.model is not None

    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        result.artifacts,
        output_root,
        mode="manifest-clean",
    )

    assert write_report.diagnostics == ()
    assert sorted(record.logical_path for record in write_report.written) == [
        artifact.logical_path for artifact in result.artifacts.artifacts
    ]

    report = verify_generated_project(
        output_root,
        result.model,
        policy=BuildVerificationPolicy(cxx_compiler="clang++"),
    )

    assert report.diagnostics == ()
    assert [
        (command.command.backend_id, command.command.profile_name, command.command.step)
        for command in report.commands
    ] == [
        ("cpp", "skylake", "configure"),
        ("cpp", "skylake", "build"),
        ("cpp", "skylake", "test"),
        ("rust", "skylake", "test"),
    ]
    assert all(command.returncode == 0 for command in report.commands)


def test_m253_project_boundaries_keep_avx512_slice_generic_and_typed() -> None:
    pipeline_source = _PIPELINE_PATH.read_text(encoding="utf-8")
    generated_project_source = _GENERATED_PROJECT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(pipeline_source)
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    for forbidden in (
        "_mm512_",
        "_mm512_add",
        "_mm512_sub",
        "core::arch::x86_64::_mm512",
        "base::signed_of",
        "intrin_compose<add",
        "intrin_compose<sub",
        "real_avx512",
        "real_add",
        "real_sub",
        "binary_arithmetic",
        "tslgenold",
    ):
        assert forbidden not in pipeline_source
    for suffix in (
        "epi8",
        "epi16",
        "epi32",
        "epi64",
        "epu8",
        "epu16",
        "epu32",
        "epu64",
        '"ps"',
        '"pd"',
    ):
        assert suffix not in pipeline_source
    for semantic_feature_table_value in ("avx3f", "avx512f", "avx512bw", "vpclmulqdq"):
        assert semantic_feature_table_value not in generated_project_source
    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )


def _build_real_avx512_unmasked_binary_arithmetic_matrix() -> SelectedPrimitiveProjectResult:
    return build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        extension_catalog=_extension_catalog(),
        flag_catalog=_flag_catalog(),
        requested_profiles=("skylake",),
        selected_entries=_SELECTED_AVX512_UNMASKED_BINARY_ARITHMETIC_MATRIX,
    )


def _project_model_for_profiles(profiles: tuple[str, ...]):
    selection = select_generated_profiles(_machine_profiles(), profiles)
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    result = build_generated_project_render_model(
        selection.profile_set,
        _flag_catalog(),
    )
    assert result.diagnostics == ()
    assert result.model is not None
    return result.model


def _known_avx512_profile_names() -> tuple[str, ...]:
    names = [
        str(profile.name)
        for profile in _machine_profiles().profiles
        if str(profile.family) == "x86"
        and any(str(feature).startswith("avx512") for feature in profile.features)
    ]
    return tuple(sorted(names))


def _assert_cpp_function(
    source: str,
    *,
    primitive_name: str,
    type_tag: str,
    register_type: str,
    call: str,
) -> None:
    assert (
        f"inline {register_type} {primitive_name}_avx512_{type_tag}"
        f"({register_type} left, {register_type} right) {{\n"
        f"  return {call};\n"
        "}"
    ) in source


def _assert_rust_function(
    source: str,
    *,
    primitive_name: str,
    type_tag: str,
    register_type: str,
    call: str,
) -> None:
    function = _function_text(source, f"{primitive_name}_avx512_{type_tag}")
    assert f"left: {register_type}" in function
    assert f"right: {register_type}" in function
    assert f") -> {register_type}" in function
    assert f"unsafe {{ {call} }}" in function


def _source_documents():
    result = SourceLoader().load((_FUNDAMENTAL_PATH,))
    assert result.diagnostics == ()
    return result.documents


def _machine_profile_result():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.flag_catalog is not None
    return result


def _machine_profiles():
    return _machine_profile_result().catalog


def _flag_catalog():
    return _machine_profile_result().flag_catalog


def _backend_metadata():
    result = load_active_backend_metadata_catalog(_LANGUAGE_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _extension_catalog() -> ExtensionCatalog:
    source_result = SourceLoader().load((_TYPES_PATH, _EXTENSIONS_PATH))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog.extensions


def _artifact_content_by_path(
    result: SelectedPrimitiveProjectResult,
) -> dict[str, str]:
    return {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}


def _function_text(source: str, function_name: str) -> str:
    start = source.index(f"pub fn {function_name}(")
    next_function = source.find("\npub fn ", start + 1)
    if next_function == -1:
        return source[start:]
    return source[start:next_function]


def _profile(profiles, name: str):
    for profile in profiles:
        if profile.profile_name == MachineProfileName(name):
            return profile
    raise AssertionError(f"missing profile {name!r}")
