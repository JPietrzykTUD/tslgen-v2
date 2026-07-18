"""The PIVOT executable owns its CLI and project-configuration behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tslc_pivot import cli as pivot_cli


def test_standalone_help_names_only_the_pivot_executable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        pivot_cli.main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert help_text.startswith("usage: tslc-pivot")
    assert "tslc export pivot" not in help_text


def test_config_discovery_accepts_multiple_source_roots(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extra_sources = tmp_path / "extra-sources"
    extra_sources.mkdir()
    output = tmp_path / "pivot-output"
    config = tmp_path / "tslc.toml"
    config.write_text(
        "[tslc]\n"
        f"sources = [{json.dumps(str(data_root))}, "
        f"{json.dumps(str(extra_sources))}]\n"
        f"machine_profiles = {json.dumps(str(machine_profiles_path))}\n"
        'backends = ["cpp", "rust"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    status = pivot_cli.main(
        [
            "--primitives",
            "add",
            "--profiles",
            "avx2",
            "--types",
            "si8",
            "--language",
            "cpp",
            "--output-root",
            str(output),
        ]
    )

    assert status == 0
    assert (output / "cpp" / "add.yaml").is_file()
