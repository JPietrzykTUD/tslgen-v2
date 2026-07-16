"""Shared fixtures: locate the corpus and build a catalog once."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.compiler_assets import (
    RenderAssets,
    load_default_render_assets,
    load_default_tsl_grammar,
)
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _REPO_ROOT / "tsldata"
_MACHINE_PROFILES = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
_GENERATED_BUILD_MARK = "generated_build"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-generated-builds",
        action="store_true",
        default=False,
        help="run tests that compile or execute generated C++/Rust projects",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        f"{_GENERATED_BUILD_MARK}: compiles or executes generated C++/Rust projects",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-generated-builds"):
        return
    skip_generated_build = pytest.mark.skip(
        reason="generated build/value tests require --run-generated-builds"
    )
    for item in items:
        if _GENERATED_BUILD_MARK in item.keywords:
            item.add_marker(skip_generated_build)


@pytest.fixture(scope="session")
def tsl_grammar() -> str:
    return load_default_tsl_grammar()


@pytest.fixture(scope="session")
def render_assets() -> RenderAssets:
    return load_default_render_assets()


@pytest.fixture(scope="session")
def data_root() -> Path:
    return _DATA_ROOT


@pytest.fixture(scope="session")
def machine_profiles_path() -> Path:
    return _MACHINE_PROFILES


@pytest.fixture(scope="session")
def machine_profiles() -> Mapping[str, MachineProfile]:
    result = load_machine_profiles_checked(_MACHINE_PROFILES)
    assert result.diagnostics == ()
    return result.profiles


@pytest.fixture(scope="session")
def fundamental_path() -> Path:
    return _DATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl"


@pytest.fixture(scope="session")
def catalog(tsl_grammar: str) -> Catalog:
    documents = SourceLoader().load_dir(_DATA_ROOT)
    assert documents.diagnostics == ()
    parsed = TslParser(tsl_grammar).parse(documents.documents)
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return result.catalog
