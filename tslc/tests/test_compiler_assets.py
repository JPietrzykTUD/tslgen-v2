from __future__ import annotations

from pathlib import Path
import re

import pytest

from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
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
            "rust_cargo.toml.tmpl": "[features]\n@{features}\n",
            "rust_documentation.rs.tmpl": "// injected docs@{bodies}\n",
            "rust_lib.rs.tmpl": "// injected lib\n@{primitive_tags}@{profile_modules}",
            "rust_smoke.rs": "// injected smoke\n",
        }
    )

    rendered = {
        artifact.logical_path: artifact.content
        for artifact in rust_artifacts((), assets, media_type="text/rust")
    }

    assert rendered["rust/src/tsl_core.rs"] == "// injected core\n"
    assert rendered["rust/src/tsl_algorithm.rs"] == "// injected algorithm\n"
    assert rendered["rust/src/lib.rs"] == "// injected lib\n"
    assert rendered["rust/src/tsl_documentation.rs"] == "// injected docs\n"
    assert rendered["rust/rustfmt.toml"] == "# injected rustfmt\n"
    assert rendered["rust/tests/smoke.rs"] == "// injected smoke\n"
    assert 'default = ["scalar"]' in rendered["rust/Cargo.toml"]


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
