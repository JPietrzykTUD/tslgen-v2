"""Shared fixtures: locate the corpus and build a catalog once."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles
from tslc.catalog.model import Catalog
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _REPO_ROOT / "tsldata"
_MACHINE_PROFILES = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"


@pytest.fixture(scope="session")
def data_root() -> Path:
    return _DATA_ROOT


@pytest.fixture(scope="session")
def machine_profiles_path() -> Path:
    return _MACHINE_PROFILES


@pytest.fixture(scope="session")
def machine_profiles() -> dict[str, MachineProfile]:
    return load_machine_profiles(_MACHINE_PROFILES)


@pytest.fixture(scope="session")
def fundamental_path() -> Path:
    return _DATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl"


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    documents = SourceLoader().load_dir(_DATA_ROOT)
    assert documents.diagnostics == ()
    parsed = TslParser().parse(documents.documents)
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return result.catalog
