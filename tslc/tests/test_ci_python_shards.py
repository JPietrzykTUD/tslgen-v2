"""Python test shard selection for scoped GitHub Actions runs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest


def test_selected_tests_are_emitted_in_one_shard() -> None:
    module = _shard_module()

    shards = module.compute_shards(
        1,
        ("tslc/tests/test_ci_scope.py",),
    )

    assert len(shards) == 1
    assert [path.name for path in shards[0].paths] == ["test_ci_scope.py"]
    assert json.loads(shards[0].matrix_entry()["paths_json"]) == [
        "tslc/tests/test_ci_scope.py"
    ]


def test_selected_tests_must_be_direct_test_files() -> None:
    module = _shard_module()

    with pytest.raises(SystemExit, match="not a test file"):
        module.compute_shards(1, ("tslc/src/tslc/pipeline.py",))


def test_expensive_profile_rendering_suite_has_a_dedicated_full_shard() -> None:
    module = _shard_module()

    shards = module.compute_shards(4)
    profile_shard = next(
        shard
        for shard in shards
        if any(path.name == "test_profile_rendering.py" for path in shard.paths)
    )

    assert [path.name for path in profile_shard.paths] == [
        "test_profile_rendering.py"
    ]


def _shard_module() -> ModuleType:
    path = Path(".github/scripts/python_test_shards.py")
    spec = importlib.util.spec_from_file_location("tslc_python_test_shards", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
