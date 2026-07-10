"""CLI value-test options stay thin and explicit."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tslc import cli
from tslc.diagnostics import Diagnostic
from tslc.value_tests.model import (
    ValueTestCasePlan,
    ValueTestInvocation,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)


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
            "--sde",
            "/tmp/sde64",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, generate_kwargs = calls["generate"]
    assert generate_kwargs["primitives"] == ["add"]
    assert generate_kwargs["test_harness"] is True
    assert generate_kwargs["value_test_warnings"] is True
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["run_value_tests"] is True
    assert verify_kwargs["sde_path"] == "/tmp/sde64"
    assert verify_kwargs["qemu_aarch64_path"] is None
    assert "building and running generated value tests" in captured.out
    assert "through Intel SDE: /tmp/sde64" in captured.out
    assert "[test-output] cpp avx2: ctest --test-dir build --output-on-failure" in captured.out
    assert "100% tests passed" in captured.out
    assert "[test-output] rust avx2: cargo test --features avx2,value_tests" in captured.out
    assert "test result: ok" in captured.out
    assert "quiet build output" not in captured.out
    assert "build/test-verified" in captured.out


def test_cli_qemu_aarch64_flag_is_forwarded(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    def fake_generate_project(source_paths, **kwargs):
        calls["generate"] = (source_paths, kwargs)
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=SimpleNamespace(verify=object()),
        )

    def fake_write_artifacts(artifacts, output_root):
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify_project(output_root, verify, **kwargs):
        calls["verify"] = (output_root, verify, kwargs)
        return SimpleNamespace(skipped=(), diagnostics=(), commands=())

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
            "neon",
            "--backends",
            "rust",
            "--output-root",
            str(tmp_path),
            "--test",
            "--qemu-aarch64",
            "/usr/bin/qemu-aarch64",
            "--rust-target",
            "aarch64-unknown-linux-musl",
            "--rust-linker",
            "rust-lld",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["qemu_aarch64_path"] == "/usr/bin/qemu-aarch64"
    assert verify_kwargs["rust_target"] == "aarch64-unknown-linux-musl"
    assert verify_kwargs["rust_linker"] == "rust-lld"
    assert "through qemu-aarch64: /usr/bin/qemu-aarch64" in captured.out


def test_cli_omitted_primitives_uses_all_catalog_default(monkeypatch, capsys) -> None:
    calls: dict[str, object] = {}

    def fake_generate_project(source_paths, **kwargs):
        calls["generate"] = (source_paths, kwargs)
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=None,
        )

    monkeypatch.setattr(cli, "generate_project", fake_generate_project)

    rc = cli.main(
        [
            "--sources",
            "tsldata",
            "--machine-profiles",
            "supplementary/buildsystem/machine_profiles.json",
            "--profiles",
            "avx2",
            "--backends",
            "rust",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, generate_kwargs = calls["generate"]
    assert "primitives" not in generate_kwargs
    assert "generated 1 specializations" in captured.out


def test_cli_omitted_profiles_uses_all_catalog_default(monkeypatch, capsys) -> None:
    calls: dict[str, object] = {}

    def fake_generate_project(source_paths, **kwargs):
        calls["generate"] = (source_paths, kwargs)
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=None,
        )

    monkeypatch.setattr(cli, "generate_project", fake_generate_project)

    rc = cli.main(
        [
            "--sources",
            "tsldata",
            "--machine-profiles",
            "supplementary/buildsystem/machine_profiles.json",
            "--backends",
            "cpp",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, generate_kwargs = calls["generate"]
    assert "profiles" not in generate_kwargs
    assert "generated 1 specializations" in captured.out


def test_cli_test_flag_fails_on_value_test_diagnostic(monkeypatch, tmp_path, capsys) -> None:
    def fake_generate_project(source_paths, **kwargs):
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=SimpleNamespace(verify=object()),
        )

    def fake_write_artifacts(artifacts, output_root):
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify_project(output_root, verify, **kwargs):
        return SimpleNamespace(
            skipped=(),
            diagnostics=(
                Diagnostic(
                    severity="warning",
                    code="TSL-BUILD-VERIFY-COMMAND-FAILED",
                    message="rust profile skylake test command failed",
                ),
            ),
            commands=(),
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
            "--output-root",
            str(tmp_path),
            "--test",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[verify] TSL-BUILD-VERIFY-COMMAND-FAILED" in captured.err
    assert "build/test-verified" not in captured.out


def test_cli_test_flag_fails_on_value_test_skip(monkeypatch, tmp_path, capsys) -> None:
    def fake_generate_project(source_paths, **kwargs):
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=SimpleNamespace(verify=object()),
        )

    def fake_write_artifacts(artifacts, output_root):
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify_project(output_root, verify, **kwargs):
        return SimpleNamespace(
            skipped=("cpp: profile neon requires qemu-aarch64",),
            diagnostics=(),
            commands=(),
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
            "--output-root",
            str(tmp_path),
            "--test",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[verify-skip] cpp: profile neon requires qemu-aarch64" in captured.err
    assert "build/test-verified" not in captured.out


def test_cli_test_flag_fails_when_planned_value_tests_do_not_run(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    def fake_generate_project(source_paths, **kwargs):
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=SimpleNamespace(
                verify=object(),
                value_tests=ValueTestProjectPlan(
                    profiles=(
                        ValueTestProfilePlan(
                            "cpp",
                            "wasm32-simd128",
                            (_value_case("add", "test_add_compiles"),),
                        ),
                    )
                ),
            ),
        )

    def fake_write_artifacts(artifacts, output_root):
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify_project(output_root, verify, **kwargs):
        return SimpleNamespace(
            skipped=(),
            diagnostics=(),
            commands=(
                SimpleNamespace(
                    command=SimpleNamespace(
                        backend_id="cpp",
                        profile_name="wasm32_simd128",
                        step="build-values",
                        argv=("cmake", "--build", "build"),
                    ),
                    returncode=0,
                    stdout="",
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
            "--output-root",
            str(tmp_path),
            "--test",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert (
        "[verify-incomplete] cpp profile wasm32-simd128 1/1 planned value-test "
        "cases not run"
    ) in captured.err
    assert "build/test-verified" not in captured.out


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


def _value_case(call_name: str, function_name: str) -> ValueTestCasePlan:
    return ValueTestCasePlan(
        kind="compile_only",
        function_name=function_name,
        case_name="compile",
        call_name=call_name,
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=4,
        invocation=ValueTestInvocation(result_kind="v"),
    )
