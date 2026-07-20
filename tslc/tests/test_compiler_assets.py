from __future__ import annotations

from pathlib import Path
import re

import pytest

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.catalog.machine_profiles import MachineProfile
from tslc.compiler_assets import (
    RenderAssets,
    load_default_render_assets,
    load_default_tsl_grammar,
)
from tslc.render.rust_project import rust_artifacts
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


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
            "rust_lib.rs.tmpl": (
                "// injected lib\n"
                "@{primitive_tags}@{profile_modules}@{benchmark_modules}"
            ),
            "rust_lib_benchmark_profile.rs.tmpl": (
                "// injected benchmark module @{profile_slug}\n"
            ),
            "rust_smoke.rs": "// injected smoke\n",
        }
    )

    rendered = {
        artifact.logical_path: artifact.content
        for artifact in rust_artifacts(
            (),
            assets,
            media_type="text/rust",
            selection_plan=plan_rust_policy_selection(()),
        )
    }

    assert rendered["rust/src/tsl_core.rs"] == "// injected core\n"
    assert rendered["rust/src/tsl_algorithm.rs"] == "// injected algorithm\n"
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
    assert 'default = ["scalar"]' in rendered["rust/Cargo.toml"]
    assert "value_tests = []" in rendered["rust/Cargo.toml"]
    assert "variant_benchmarks = []" in rendered["rust/Cargo.toml"]
    assert "[[bench]]" not in rendered["rust/Cargo.toml"]


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
        for artifact in rust_artifacts(
            profiles,
            load_default_render_assets(),
            media_type="text/rust",
            selection_plan=plan_rust_policy_selection(profiles),
        )
    }

    cargo = rendered["rust/Cargo.toml"]
    assert "value_tests = []\nvariant_benchmarks = []" in cargo
    assert cargo.count("[[bench]]") == 2
    for profile_slug in ("scalar", "avx2"):
        target_name = f"tsl_variant_bench_{profile_slug}"
        assert (
            f'[[bench]]\nname = "{target_name}"\n'
            f'path = "benches/{target_name}.rs"\n'
            'harness = false\n'
            f'required-features = ["variant_benchmarks", "{profile_slug}"]'
        ) in cargo
        benchmark_main = rendered[f"rust/benches/{target_name}.rs"]
        assert "TSL_RUST_VARIANT_POLICY_ACTIVE" in benchmark_main
        assert (
            f"    std::process::exit(tsl::{target_name}::main());"
            in benchmark_main
        )

    lib = rendered["rust/src/lib.rs"]
    assert (
        '#[cfg(feature = "variant_benchmarks")]\n'
        "#[doc(hidden)]\n"
        "pub mod tsl_benchmark_core;"
    ) in lib
    for profile_slug in ("scalar", "avx2"):
        assert (
            '#[cfg(all(feature = "variant_benchmarks", '
            f'feature = "{profile_slug}"))]\n'
            "#[doc(hidden)]\n"
            f"pub mod tsl_variant_bench_{profile_slug};"
        ) in lib


def test_rust_algorithm_facade_wrappers_are_static_render_asset() -> None:
    assets = load_default_render_assets()

    wrappers = assets.text("rust_algo_wrappers.rs")

    assert "pub fn transform_unary<Policy, Op, T>" in wrappers
    assert "crate::tsl_algorithm::transform_unary::<Profile, Policy, Op, T>" in wrappers


def test_rust_algorithm_reserved_name_manifest_matches_static_asset() -> None:
    wrappers = load_default_render_assets().text("rust_algo_wrappers.rs")
    public_names = frozenset(
        re.findall(
            r"^\s+pub (?:unsafe )?fn ([A-Za-z_][A-Za-z0-9_]*)",
            wrappers,
            flags=re.MULTILINE,
        )
    )

    assert public_names == RUST_ALGORITHM_RESERVED_NAMES


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
