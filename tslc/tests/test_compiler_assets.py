from __future__ import annotations

from pathlib import Path
import re
import tomllib

import pytest

from rust_project_test_support import render_rust_artifacts_for_test
from tslc.backend.algorithm_contracts import ALGORITHM_PUBLIC_FAMILIES
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_declaration_holes,
    cpp_algorithm_public_declarations,
)
from tslc.backend.cpp_static_public_declarations import (
    cpp_static_declaration_holes,
)
from tslc.backend.precondition_error_rendering import (
    cpp_precondition_error,
    rust_precondition_error,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_package import RustPackageConfig
from tslc.backend.rust_policy_manifest import load_rust_policy_manifest
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
from tslc.backend.rust_static_selection import plan_rust_static_selection
from tslc.backend.rust_static_public_declarations import (
    rust_static_declaration_holes,
)
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_algorithm_contracts import rust_algorithm_contract_holes
from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_declaration_holes,
    rust_profile_algorithm_public_declarations,
)
from tslc.backend.public_declarations import PublicDeclarationKind
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.preconditions import PreconditionErrorKind
from tslc.compiler_assets import (
    RenderAssets,
    load_default_render_assets,
    load_default_tsl_grammar,
)
from tslc.sources import SourceDocument
from tslc.syntax.ast import ParsedTslScalarValue
from tslc.syntax.parser import TslParser

RUST_POLICY_MANIFEST = load_rust_policy_manifest()


def test_checked_error_assets_match_the_typed_error_registry() -> None:
    assets = load_default_render_assets()
    cpp = assets.fill(
        "tsl_core.hpp", **cpp_static_declaration_holes("tsl_core.hpp")
    )
    rust = assets.fill("tsl_core.rs", **rust_static_declaration_holes())

    cpp_start = cpp.index("enum class precondition_error")
    cpp_end = cpp.index("};", cpp_start)
    cpp_enum = cpp[cpp_start:cpp_end]
    cpp_spellings = ("none",) + tuple(
        cpp_precondition_error(error, qualified=False)
        for error in PreconditionErrorKind
    )
    assert tuple(
        line.strip().removesuffix(",")
        for line in cpp_enum.splitlines()[1:]
        if line.strip()
    ) == cpp_spellings

    rust_start = rust.index("pub enum PreconditionError")
    rust_end = rust.index("}\n", rust_start)
    rust_enum = rust[rust_start:rust_end]
    rust_spellings = tuple(
        rust_precondition_error(error, prefix="")
        for error in PreconditionErrorKind
    )
    assert tuple(
        line.strip().removesuffix(",")
        for line in rust_enum.splitlines()[1:]
        if line.startswith("    ") and not line.startswith("    ///")
    ) == rust_spellings
    assert rust_enum.count("    ///") == len(PreconditionErrorKind)


def test_rust_cpu_identity_uses_msrv_compatible_cpuid_calls() -> None:
    cpu_identity = load_default_render_assets().text(
        "tsl_rust_cpu_identity.rs"
    )

    assert "#[allow(unused_unsafe)]" in cpu_identity
    assert "let (vendor_leaf, identity) = unsafe {" in cpu_identity
    assert "std::arch::x86_64::__cpuid(0)" in cpu_identity
    assert "std::arch::x86_64::__cpuid(1)" in cpu_identity


def test_render_assets_freeze_and_fill_templates() -> None:
    files = {"plain.txt": "plain", "demo.tmpl": "hello @{name}"}
    assets = RenderAssets(files)

    files["plain.txt"] = "changed"

    assert assets.text("plain.txt") == "plain"
    assert assets.fill("demo.tmpl", name="tslc") == "hello tslc"
    with pytest.raises(KeyError, match="missing.txt"):
        assets.text("missing.txt")
    with pytest.raises(TypeError):
        assets.files["plain.txt"] = "changed"  # type: ignore[index]

def test_parser_consumes_injected_grammar() -> None:
    document = SourceDocument(
        Path("inline.tsl"),
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        "d",
        "tsl",
    )

    parsed = TslParser(load_default_tsl_grammar()).parse((document,))

    assert parsed.diagnostics == ()
    assert parsed.documents[0].primitives[0].name == "id"

def test_boolean_tokens_do_not_capture_identifier_prefixes() -> None:
    document = SourceDocument(
        Path("boolean_identifier_prefix.tsl"),
        "prim<v:=(v,v)> select(true_values, false_values):\n"
        "  enabled true\n",
        "d",
        "tsl",
    )

    parsed = TslParser(load_default_tsl_grammar()).parse((document,))

    assert parsed.diagnostics == ()
    primitive = parsed.documents[0].primitives[0]
    assert primitive.parameters == ("true_values", "false_values")
    enabled = primitive.fields_by_name("enabled")[0].field.value
    assert isinstance(enabled, ParsedTslScalarValue)
    assert enabled.text == "true"

def test_rust_project_renderer_consumes_injected_assets() -> None:
    assets = RenderAssets(
        {
            "rustfmt.toml": "# injected rustfmt\n",
            "tsl_core.rs": "// injected core\n",
            "tsl_algorithm.rs": "// injected algorithm\n",
            "tsl_rust_cpu_identity.rs": "// injected CPU identity\n",
            "tsl_rust_policy_json.rs": "// injected policy JSON\n",
            "tsl_rust_variant_policy.rs": "// injected policy consumer\n",
            "tsl_rust_variant_policy_protocol.rs": (
                "// injected policy protocol\n"
            ),
            "tsl_rust_variant_policy_validation.rs": (
                "// injected policy validation\n"
            ),
            "rust_benchmark_main.rs.tmpl": "// injected bench @{profile_slug}\n",
            "rust_benchmark_target.toml.tmpl": (
                "// injected benchmark target @{profile_slug}\n"
            ),
            "rust_build.rs": "// injected build host/target marker\n",
            "rust_cargo.toml.tmpl": "[features]\n@{features}@{bench_targets}\n",
            "rust_documentation.rs.tmpl": "// injected docs@{bodies}\n",
            "rust_facade.rs.tmpl": (
                "// injected facade\n@{representation_impls}@{element_impls}\n"
            ),
            "rust_lib.rs.tmpl": (
                "// injected lib\n"
                "@{primitive_tags}@{profile_modules}@{benchmark_modules}"
            ),
            "rust_lib_benchmark_profile.rs.tmpl": (
                "// injected benchmark module @{profile_slug}\n"
            ),
            "rust_lib_profile.rs.tmpl": "",
            "rust_profile_metadata.rs.tmpl": "",
            "rust_profile_module.rs.tmpl": "",
            "rust_readme.md.tmpl": (
                "# @{package_name}\n@{documentation_url}\n@{repository_url}\n"
            ),
            "rust_smoke.rs": "// injected smoke\n",
        }
    )

    rendered = {
        artifact.logical_path: artifact.content
        for artifact in render_rust_artifacts_for_test(
            (),
            assets,
            media_type="text/rust",
            selection_plan=plan_rust_policy_selection(
                (), RUST_POLICY_MANIFEST
            ),
            static_selection_plan=plan_rust_static_selection(()),
        )
    }

    assert rendered["rust/src/tsl_core.rs"] == "// injected core\n"
    assert rendered["rust/src/tsl_algorithm.rs"] == "// injected algorithm\n"
    assert rendered["rust/src/tsl_facade.rs"] == "// injected facade\n\n"
    assert rendered["rust/src/tsl_rust_cpu_identity.rs"] == (
        "// injected CPU identity\n"
    )
    assert rendered["rust/tsl_rust_policy_json.rs"] == "// injected policy JSON\n"
    assert rendered["rust/tsl_rust_variant_policy.rs"] == (
        "// injected policy consumer\n"
    )
    assert rendered["rust/tsl_rust_variant_policy_protocol.rs"] == (
        "// injected policy protocol\n"
    )
    assert rendered["rust/tsl_rust_variant_policy_validation.rs"] == (
        "// injected policy validation\n"
    )
    assert rendered["rust/build.rs"] == "// injected build host/target marker\n"
    assert rendered["rust/src/lib.rs"] == "// injected lib\n"
    assert rendered["rust/src/tsl_documentation.rs"] == "// injected docs\n"
    assert rendered["rust/rustfmt.toml"] == "# injected rustfmt\n"
    assert rendered["rust/tests/smoke.rs"] == "// injected smoke\n"
    assert rendered["rust/README.md"].startswith("# tsl\n")
    assert "default = []" in rendered["rust/Cargo.toml"]
    assert "std = []" in rendered["rust/Cargo.toml"]
    assert 'runtime-dispatch = ["std"]' in rendered["rust/Cargo.toml"]
    assert "[[bench]]" not in rendered["rust/Cargo.toml"]

def test_rust_project_renderer_uses_typed_release_metadata() -> None:
    package = RustPackageConfig(
        name="custom-tsl",
        version="2.3.4",
        description="Custom generated SIMD package",
        edition="2024",
        rust_version="1.85",
        license="MIT",
        repository="https://example.test/repository",
        documentation="https://example.test/docs",
        readme="CRATE.md",
    )
    rendered = {
        artifact.logical_path: artifact.content
        for artifact in render_rust_artifacts_for_test(
            (),
            load_default_render_assets(),
            media_type="text/rust",
            selection_plan=plan_rust_policy_selection(
                (), RUST_POLICY_MANIFEST
            ),
            static_selection_plan=plan_rust_static_selection(()),
            package_config=package,
        )
    }

    manifest = tomllib.loads(rendered["rust/Cargo.toml"])
    assert manifest["package"] == {
        "name": "custom-tsl",
        "version": "2.3.4",
        "description": "Custom generated SIMD package",
        "edition": "2024",
        "rust-version": "1.85",
        "license": "MIT",
        "repository": "https://example.test/repository",
        "documentation": "https://example.test/docs",
        "readme": "CRATE.md",
        "autoexamples": False,
        "include": [
            "Cargo.toml",
            "LICENSE",
            "CRATE.md",
            "rustfmt.toml",
            "public-api.json",
            "build.rs",
            "*.rs",
            "src/**",
            "tests/**",
            "benches/**",
            "bench/**",
        ],
    }
    assert manifest["features"] == {
        "default": [],
        "std": [],
        "runtime-dispatch": ["std"],
    }
    assert "rust/CRATE.md" in rendered
    assert "# custom-tsl" in rendered["rust/CRATE.md"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("name", "bad package"),
        ("name", "a" * 65),
        ("version", "01.0.0"),
        ("version", "1.0.0-01"),
        ("description", ""),
        ("edition", "2030"),
        ("rust_version", "nightly"),
        ("license", "MIT\nApache-2.0"),
        ("repository", "repository"),
        ("documentation", "https://example.test/docs path"),
        ("readme", "../README.md"),
        ("readme", "docs/README.md"),
        ("readme", "docs\\README.md"),
    ),
)
def test_rust_package_config_rejects_invalid_metadata(
    field: str,
    value: str,
) -> None:
    metadata = {
        "name": "tsl",
        "version": "1.2.3",
        "description": "Generated SIMD package",
        "edition": "2021",
        "rust_version": "1.89",
        "license": "Apache-2.0",
        "repository": "https://example.test/repository",
        "documentation": "https://example.test/docs",
        "readme": "README.md",
    }
    metadata[field] = value

    with pytest.raises(ValueError):
        RustPackageConfig(**metadata)

def test_rust_project_renderer_wires_opt_in_profile_benchmarks() -> None:
    profiles = tuple(
        EmittedProfile(
            MachineProfile(name, "test", frozenset(), {}),
            {"rust": {}},
            immediate_split_names=frozenset(),
        )
        for name in ("scalar", "avx2")
    )

    rendered = {
        artifact.logical_path: artifact.content
        for artifact in render_rust_artifacts_for_test(
            profiles,
            load_default_render_assets(),
            media_type="text/rust",
            selection_plan=plan_rust_policy_selection(
                profiles, RUST_POLICY_MANIFEST
            ),
            static_selection_plan=plan_rust_static_selection(profiles),
        )
    }

    cargo = rendered["rust/Cargo.toml"]
    assert "default = []\nstd = []\nruntime-dispatch = [\"std\"]" in cargo
    assert cargo.count("[[bench]]") == 2
    for profile_slug in ("scalar", "avx2"):
        target_name = f"tsl_variant_bench_{profile_slug}"
        assert (
            f'[[bench]]\nname = "{target_name}"\n'
            f'path = "benches/{target_name}.rs"\n'
            "harness = false"
        ) in cargo
        benchmark_main = rendered[f"rust/benches/{target_name}.rs"]
        assert "TSL_RUST_VARIANT_POLICY_ACTIVE" in benchmark_main
        assert (
            f"    std::process::exit(tsl::{target_name}::main());"
            in benchmark_main
        )

    lib = rendered["rust/src/lib.rs"]
    assert (
        "#[cfg(tsl_variant_benchmarks)]\n"
        "#[doc(hidden)]\n"
        "pub mod tsl_benchmark_core;"
    ) in lib
    for profile_slug in ("scalar", "avx2"):
        assert (
            "#[cfg(tsl_variant_benchmarks)]\n"
            "#[doc(hidden)]\n"
            f"pub mod tsl_variant_bench_{profile_slug};"
        ) in lib

def test_rust_algorithm_facade_wrappers_are_static_render_asset() -> None:
    assets = load_default_render_assets()

    wrappers = assets.text("rust_algo_wrappers.rs")
    holes = rust_profile_algorithm_declaration_holes()

    assert "@{profile_algorithm_declaration_transform_unary_checked}" in wrappers
    assert (
        "pub fn transform_unary_checked<Policy, Op, T>"
        in holes["profile_algorithm_declaration_transform_unary_checked"]
    )
    assert (
        "crate::tsl_algorithm::transform_unary_checked::<Profile, Policy, Op, T>"
        in wrappers
    )

def test_rust_algorithm_reserved_name_manifest_matches_static_asset() -> None:
    reachability = ("profile", "algo")
    declarations = (
        *rust_profile_algorithm_public_declarations(reachability),
        *rust_profile_scaled_checked_algorithm_declarations(reachability),
    )
    public_names = frozenset(declaration.name for declaration in declarations)

    assert public_names == RUST_ALGORITHM_RESERVED_NAMES


def test_cpp_algorithm_name_manifest_matches_static_asset() -> None:
    declarations = cpp_algorithm_public_declarations()
    public_names = frozenset(
        declaration.name
        for declaration in declarations
        if declaration.kind is PublicDeclarationKind.FUNCTION
    )

    assert public_names == ALGORITHM_PUBLIC_FAMILIES


def test_algorithm_assets_have_one_typed_declaration_hole_per_record() -> None:
    assets = load_default_render_assets()
    cpp_holes = cpp_algorithm_declaration_holes()
    rust_holes = rust_profile_algorithm_declaration_holes()

    cpp_asset = assets.text("tsl_algorithm.hpp")
    rust_asset = assets.text("rust_algo_wrappers.rs")
    assert all(cpp_asset.count(f"@{{{name}}}") == 1 for name in cpp_holes)
    assert all(rust_asset.count(f"@{{{name}}}") == 1 for name in rust_holes)


def test_rust_algorithm_names_cover_shared_public_families() -> None:
    families = {
        re.sub(r"(?:_mask_layout|_scaled|_checked|_raw)+$", "", name)
        for name in RUST_ALGORITHM_RESERVED_NAMES
    }

    assert families == ALGORITHM_PUBLIC_FAMILIES


def test_package_resource_reads_stay_in_compiler_asset_boundary() -> None:
    package_root = Path(__file__).resolve().parents[1] / "src" / "tslc"
    checked = (
        package_root / "syntax" / "parser.py",
        package_root / "render" / "_common.py",
        package_root / "render" / "cpp_project.py",
        package_root / "render" / "rust_project.py",
        package_root / "render" / "tests_project.py",
        package_root / "value_tests" / "render_cpp.py",
        package_root / "value_tests" / "render_rust.py",
    )

    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert "importlib import resources" not in text
        assert "resources.files" not in text
