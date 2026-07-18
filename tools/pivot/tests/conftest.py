"""Shared fixtures for the standalone PIVOT tool tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _REPO_ROOT / "tsldata"
_MACHINE_PROFILES = (
    _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
)


@pytest.fixture(scope="session")
def data_root() -> Path:
    return _DATA_ROOT


@pytest.fixture(scope="session")
def machine_profiles_path() -> Path:
    return _MACHINE_PROFILES


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    documents = SourceLoader().load_dir(_DATA_ROOT)
    assert documents.diagnostics == ()
    parsed = TslParser(load_default_tsl_grammar()).parse(documents.documents)
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return result.catalog


@pytest.fixture(scope="session")
def machine_profiles(catalog: Catalog) -> Mapping[str, MachineProfile]:
    result = load_machine_profiles_checked(_MACHINE_PROFILES, catalog.target_families)
    assert result.diagnostics == ()
    return result.profiles
