"""The CLI resolver never falls back to ambient process configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc_pivot import cli as pivot_cli


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_no_discovered_config_does_not_fall_back_to_process_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    sources = isolated / "sources"
    sources.mkdir()
    source = sources / "demo.tsl"
    source.write_text("primitive demo {}\n", encoding="utf-8")
    profiles = isolated / "profiles.json"
    profiles.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(_REPOSITORY_ROOT)
    monkeypatch.setattr(pivot_cli, "discover_config", lambda _root: None)

    invocation = pivot_cli.resolve_cli_invocation(
        (
            "--sources",
            "sources",
            "--machine-profiles",
            "profiles.json",
            "--language",
            "cpp",
            "--output-root",
            "output",
        ),
        working_directory=isolated,
    )

    assert invocation.project_config_path is None
    assert invocation.source_roots == (sources.resolve(),)
    assert invocation.request.source_paths == (source.resolve(),)
    assert invocation.request.machine_profiles_path == profiles.resolve()
    assert invocation.output_root == (isolated / "output").resolve()

    with pytest.raises(SystemExit) as exc:
        pivot_cli.resolve_cli_invocation(
            ("--language", "cpp", "--output-root", "output"),
            working_directory=isolated,
        )

    assert exc.value.code == 2
    assert "--sources is required when no tslc.toml" in capsys.readouterr().err
