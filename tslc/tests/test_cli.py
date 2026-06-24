"""CLI value-test options stay thin and explicit."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tslc import cli


def test_cli_test_flag_enables_existing_value_test_paths(
    monkeypatch, tmp_path, capsys
) -> None:
    calls: dict[str, object] = {}

    def fake_generate_project(source_paths, **kwargs):
        calls["generate"] = (source_paths, kwargs)
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(), object())),
            rendered=SimpleNamespace(verify=object()),
        )

    def fake_write_artifacts(artifacts, output_root):
        calls["write"] = (artifacts, output_root)
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify_project(output_root, verify, **kwargs):
        calls["verify"] = (output_root, verify, kwargs)
        return SimpleNamespace(
            skipped=(),
            diagnostics=(),
            commands=(
                SimpleNamespace(
                    command=SimpleNamespace(
                        backend_id="cpp",
                        profile_name="avx2",
                        step="build-values",
                        argv=("cmake", "--build", "build"),
                    ),
                    returncode=0,
                    stdout="quiet build output",
                    stderr="",
                ),
                SimpleNamespace(
                    command=SimpleNamespace(
                        backend_id="cpp",
                        profile_name="avx2",
                        step="test",
                        argv=("ctest", "--test-dir", "build", "--output-on-failure"),
                    ),
                    returncode=0,
                    stdout="100% tests passed\n",
                    stderr="",
                ),
                SimpleNamespace(
                    command=SimpleNamespace(
                        backend_id="rust",
                        profile_name="avx2",
                        step="test",
                        argv=("cargo", "test", "--features", "avx2,value_tests"),
                    ),
                    returncode=0,
                    stdout="test result: ok\n",
                    stderr="",
                ),
            ),
        )

    monkeypatch.setattr(cli, "generate_project", fake_generate_project)
    monkeypatch.setattr(cli, "write_artifacts", fake_write_artifacts)
    monkeypatch.setattr(cli, "verify_project", fake_verify_project)

    rc = cli.main(
        [
            "--sources",
            "tsldata",
            "--machine-profiles",
            "supplementary/buildsystem/machine_profiles.json",
            "--primitives",
            "add",
            "--profiles",
            "avx2",
            "--backends",
            "cpp",
            "--output-root",
            str(tmp_path),
            "--test",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, generate_kwargs = calls["generate"]
    assert generate_kwargs["test_harness"] is True
    assert generate_kwargs["value_test_warnings"] is True
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["run_value_tests"] is True
    assert "building and running generated value tests" in captured.out
    assert "[test-output] cpp avx2: ctest --test-dir build --output-on-failure" in captured.out
    assert "100% tests passed" in captured.out
    assert "[test-output] rust avx2: cargo test --features avx2,value_tests" in captured.out
    assert "test result: ok" in captured.out
    assert "quiet build output" not in captured.out
    assert "build/test-verified" in captured.out


def test_cli_test_flag_requires_output_root(monkeypatch, capsys) -> None:
    def fail_generate_project(*_args, **_kwargs):
        raise AssertionError("generation should not run without an output root")

    monkeypatch.setattr(cli, "generate_project", fail_generate_project)

    rc = cli.main(
        [
            "--sources",
            "tsldata",
            "--machine-profiles",
            "supplementary/buildsystem/machine_profiles.json",
            "--test",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "--test requires --output-root" in captured.err
