"""CLI value-test options stay thin and explicit."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tslc import cli
from tslc._cli_options import merge_toolchains, parse_assignments, split_csv
from tslc.diagnostics import Diagnostic
from tslc.generation_command import (
    GenerationCommandSettings,
    GenerationPipeline,
    run_generation_command,
)
from tslc.output.verify_model import BackendToolchain
from tslc.value_tests.model import (
    ValueTestCasePlan,
    ValueTestInvocation,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)


def test_cli_reports_installed_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "package_version", lambda: "9.8.7-test")

    try:
        cli.main(["--version"])
    except SystemExit as error:
        assert error.code == 0

    assert capsys.readouterr().out == "tslc 9.8.7-test\n"


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
            "--runner",
            "sde=/tmp/sde64",
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
    assert verify_kwargs["runner_paths"] == {"sde": "/tmp/sde64"}
    assert "building and running generated value tests" in captured.out
    assert "through sde: /tmp/sde64" in captured.out
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
            "--runner",
            "qemu-aarch64=/usr/bin/qemu-aarch64",
            "--target",
            "rust=aarch64-unknown-linux-musl",
            "--linker",
            "rust=rust-lld",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["runner_paths"] == {
        "qemu-aarch64": "/usr/bin/qemu-aarch64"
    }
    rust_toolchain = verify_kwargs["toolchains"]["rust"]
    assert rust_toolchain.target == "aarch64-unknown-linux-musl"
    assert rust_toolchain.linker == "rust-lld"
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
    assert (
        "warning[TSL-BUILD-VERIFY-COMMAND-FAILED]: "
        "rust profile skylake test command failed"
    ) in captured.err
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
                    matches_expectation=True,
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


def test_cli_build_command_implies_verify_as_derived_setting(
    monkeypatch, tmp_path, capsys
) -> None:
    (tmp_path / "tslc.toml").write_text(
        "\n".join(
            (
                "[tslc]",
                'sources = ["data"]',
                'machine_profiles = "profiles.json"',
                'backends = ["cpp"]',
                'output_root = "out"',
                "",
            )
        ),
        encoding="utf-8",
    )
    calls: dict[str, object] = {}

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
        calls["verify"] = (output_root, verify, kwargs)
        return SimpleNamespace(skipped=(), diagnostics=(), commands=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "generate_project", fake_generate_project)
    monkeypatch.setattr(cli, "write_artifacts", fake_write_artifacts)
    monkeypatch.setattr(cli, "verify_project", fake_verify_project)

    rc = cli.main(["build", "--primitives", "add", "--profiles", "scalar", "--no-format"])

    captured = capsys.readouterr()
    assert rc == 0
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["run_value_tests"] is False
    assert "build-verified 0 commands" in captured.out


def _core_settings(**overrides: object) -> GenerationCommandSettings:
    settings: dict[str, object] = dict(
        sources=(Path("tsldata"),),
        machine_profiles=Path("supplementary/buildsystem/machine_profiles.json"),
        type_tags=("si32",),
        backends=("cpp",),
        generation_mode="partial",
        primitives=("add",),
        profiles=("scalar",),
        output_root=None,
        verify=False,
        run_value_tests=False,
        fuzz=False,
        coverage=False,
        value_test_warnings=False,
        format_artifacts=False,
        summary_file=None,
        toolchains={},
        runner_paths={},
        tool_paths={},
    )
    settings.update(overrides)
    return GenerationCommandSettings(**settings)


def test_generation_command_core_writes_artifacts_and_summary_once(
    tmp_path, capsys
) -> None:
    calls: dict[str, int] = {"generate": 0, "write": 0}
    summary_file = tmp_path / "summary.md"

    def fake_generate(source_paths, **kwargs):
        calls["generate"] += 1
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=None,
        )

    def fake_write(artifacts, output_root):
        calls["write"] += 1
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fail_verify(*_args, **_kwargs):
        raise AssertionError("generation-only runs must not verify")

    rc = run_generation_command(
        _core_settings(
            output_root=str(tmp_path / "out"),
            summary_file=str(summary_file),
        ),
        GenerationPipeline(generate=fake_generate, write=fake_write, verify=fail_verify),
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert calls == {"generate": 1, "write": 1}
    assert "wrote 1 files under" in captured.out
    assert f"wrote Markdown summary to {summary_file}" in captured.out
    content = summary_file.read_text(encoding="utf-8")
    assert content.count("### Generated value-test summary") == 1


def test_generation_command_core_verify_setting_runs_build_verification(
    tmp_path, capsys
) -> None:
    calls: dict[str, object] = {}

    def fake_generate(source_paths, **kwargs):
        return SimpleNamespace(
            diagnostics=(),
            coverage=(object(),),
            artifacts=SimpleNamespace(artifacts=(object(),)),
            rendered=SimpleNamespace(verify=object()),
        )

    def fake_write(artifacts, output_root):
        return SimpleNamespace(
            diagnostics=(),
            written=(Path(output_root) / "generated.txt",),
            output_root=Path(output_root),
        )

    def fake_verify(output_root, verify, **kwargs):
        calls["verify"] = (output_root, verify, kwargs)
        return SimpleNamespace(skipped=(), diagnostics=(), commands=())

    rc = run_generation_command(
        _core_settings(output_root=str(tmp_path), verify=True),
        GenerationPipeline(generate=fake_generate, write=fake_write, verify=fake_verify),
    )

    captured = capsys.readouterr()
    assert rc == 0
    _, _, verify_kwargs = calls["verify"]
    assert verify_kwargs["run_value_tests"] is False
    assert "build-verified 0 commands" in captured.out


def test_generation_command_core_generation_errors_exit_one_with_summary(
    tmp_path, capsys
) -> None:
    summary_file = tmp_path / "summary.md"

    def fake_generate(source_paths, **kwargs):
        return SimpleNamespace(
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-TEST-ERROR",
                    message="generation failed",
                ),
            ),
            coverage=(),
            artifacts=SimpleNamespace(artifacts=()),
            rendered=None,
        )

    def fail_write(*_args, **_kwargs):
        raise AssertionError("failed generation must not write artifacts")

    def fail_verify(*_args, **_kwargs):
        raise AssertionError("failed generation must not verify")

    rc = run_generation_command(
        _core_settings(
            output_root=str(tmp_path / "out"),
            summary_file=str(summary_file),
        ),
        GenerationPipeline(generate=fake_generate, write=fail_write, verify=fail_verify),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "error[TSL-TEST-ERROR]: generation failed" in captured.err
    content = summary_file.read_text(encoding="utf-8")
    assert content.count("### Generated value-test summary") == 1


def test_generation_command_core_value_tests_require_output_root(capsys) -> None:
    def fail_generate(*_args, **_kwargs):
        raise AssertionError("generation should not run without an output root")

    rc = run_generation_command(
        _core_settings(run_value_tests=True),
        GenerationPipeline(
            generate=fail_generate, write=fail_generate, verify=fail_generate
        ),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "--test requires --output-root" in captured.err


def test_split_csv_strips_and_drops_empty_items() -> None:
    assert split_csv(" cpp, rust ,,") == ("cpp", "rust")
    assert split_csv("") == ()


def test_parse_assignments_rejects_malformed_and_repeated_names() -> None:
    assert parse_assignments(["cpp=clang++", "rust= rustc "], "--compiler") == {
        "cpp": "clang++",
        "rust": "rustc",
    }
    with pytest.raises(ValueError, match=r"--compiler expects NAME=VALUE, got 'cpp'"):
        parse_assignments(["cpp"], "--compiler")
    with pytest.raises(ValueError, match=r"--compiler repeats name 'cpp'"):
        parse_assignments(["cpp=a", "cpp=b"], "--compiler")


def test_merge_toolchains_overlays_overrides_onto_configured_base() -> None:
    configured = {
        "rust": BackendToolchain.create(compiler="cargo", target="x86_64-unknown-linux-gnu")
    }

    merged = merge_toolchains(
        configured,
        {"cpp": "clang++"},
        {"rust": "aarch64-unknown-linux-musl"},
        {"rust": "rust-lld"},
    )

    assert merged["cpp"].compiler == ("clang++",)
    assert merged["rust"].compiler == ("cargo",)
    assert merged["rust"].target == "aarch64-unknown-linux-musl"
    assert merged["rust"].linker == "rust-lld"
    assert configured["rust"].target == "x86_64-unknown-linux-gnu"


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
