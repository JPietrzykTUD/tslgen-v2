"""First-class authoring commands stay side-effect-free and discoverable."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tslc import cli
from tslc import check_cli
from tslc import doctor as doctor_module
from tslc.api import generate_project
from tslc.authoring import check_catalog
from tslc.catalog.machine_profiles import MachineProfile
from tslc.doctor import diagnose
from tslc.maintenance import coverage_inventory
from tslc.output.verify_drivers import (
    BackendPreparation,
    CommandFollowUp,
    VerifyBackendDriver,
)
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandResult,
    ToolchainCommands,
    VerifyProfile,
)
from tslc.project_config import load_project_config


def test_catalog_check_does_not_load_render_assets(
    monkeypatch: pytest.MonkeyPatch, data_root: Path
) -> None:
    def fail() -> None:
        raise AssertionError("catalog checks must not load render assets")

    monkeypatch.setattr("tslc._pipeline_inputs.load_default_render_assets", fail)

    result = check_catalog((data_root,))

    assert result.catalog is not None
    assert result.diagnostics == ()
    assert result.source_paths


def test_slot_check_lowers_without_rendering(
    monkeypatch: pytest.MonkeyPatch,
    data_root: Path,
    machine_profiles_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("slot checks must not render")

    monkeypatch.setattr("tslc._pipeline_inputs.load_default_render_assets", fail)
    monkeypatch.setattr("tslc.pipeline.render_project", fail)

    status = cli.main(
        [
            "check",
            "--sources",
            str(data_root),
            "--machine-profiles",
            str(machine_profiles_path),
            "--primitive",
            "add",
            "--profile",
            "avx2",
            "--backend",
            "cpp",
            "--extension",
            "avx2",
            "--type",
            "si32",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert status == 0
    assert payload["mode"] == "slots"
    assert payload["coverage"] > 0
    assert payload["skipped"] == []


def test_slot_check_extension_filter_keeps_dependency_closure_concrete(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        (data_root,),
        machine_profiles_path=machine_profiles_path,
        primitives=("add",),
        profiles=("avx2",),
        type_tags=("si32",),
        extensions=("avx2",),
        backends=("cpp",),
        render_artifacts=False,
    )

    assert result.diagnostics == ()
    assert result.skipped == ()
    assert result.coverage
    assert {entry.extension for entry in result.coverage} == {"avx2"}
    assert {entry.type_tag for entry in result.coverage} == {"si32"}
    assert any(entry.source_primitive_name == "add" for entry in result.coverage)


def test_slot_check_strict_mode_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    modes: list[str] = []
    extensions: list[object] = []

    def fake_generate(*args: object, **kwargs: object) -> object:
        del args
        modes.append(str(kwargs["generation_mode"]))
        extensions.append(kwargs["extensions"])
        return SimpleNamespace(diagnostics=(), coverage=(), skipped=())

    monkeypatch.setattr(check_cli, "generate_project", fake_generate)
    common = [
        "--sources",
        str(tmp_path),
        "--machine-profiles",
        str(tmp_path / "profiles.json"),
        "--profile",
        "scalar",
        "--extension",
        "scalar",
        "--format",
        "json",
    ]

    assert check_cli.main(common) == 0
    capsys.readouterr()
    assert check_cli.main([*common, "--strict"]) == 0
    capsys.readouterr()

    assert modes == ["partial", "strict"]
    assert extensions == [["scalar"], ["scalar"]]


def test_catalog_list_and_show_have_stable_json(
    data_root: Path,
    machine_profiles_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = cli.main(
        [
            "list",
            "regions",
            "--sources",
            str(data_root),
            "--machine-profiles",
            str(machine_profiles_path),
            "--format",
            "json",
        ]
    )
    listed = json.loads(capsys.readouterr().out)
    assert status == 0
    assert "intrin" in listed["items"]

    status = cli.main(
        [
            "show",
            "region",
            "intrin",
            "--sources",
            str(data_root),
            "--format",
            "json",
        ]
    )
    shown = json.loads(capsys.readouterr().out)
    assert status == 0
    assert shown == {
        "accepted_forms": [
            "intrin<name>(args)",
            "intrin<base, build>(args)",
            "intrin<base, build[modifier=value, ...]>(args)",
        ],
        "body_shape": "call",
        "kind": "region",
        "name": "intrin",
        "purpose": "Invoke a target intrinsic.",
        "shell_validator": "intrin_selector",
    }


def test_project_config_paths_are_relative_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "tslc.toml"
    config_path.write_text(
        "\n".join(
            (
                "[tslc]",
                'sources = ["data"]',
                'machine_profiles = "profiles.json"',
                'backends = ["cpp"]',
                'authoring_profiles = ["scalar"]',
                'output_root = "out"',
                "[tslc.rust_package]",
                'name = "custom-tsl"',
                'version = "1.2.3"',
                'edition = "2024"',
                'rust_version = "1.85"',
                'license = "Apache-2.0"',
                'repository = "https://example.test/repository"',
                'documentation = "https://example.test/documentation"',
                'readme = "CRATE.md"',
                "[tslc.toolchains.cpp]",
                'compiler = "clang++"',
                "[tslc.runners]",
                'sde = "/opt/sde64"',
                "[tslc.tools]",
                'oneapi-cpp = "/opt/oneapi/icpx"',
                "",
            )
        ),
        encoding="utf-8",
    )

    config = load_project_config(config_path)

    assert config is not None
    assert config.sources == ((tmp_path / "data").resolve(),)
    assert config.machine_profiles == (tmp_path / "profiles.json").resolve()
    assert config.output_root == (tmp_path / "out").resolve()
    assert config.authoring_profiles == ("scalar",)
    assert config.toolchains["cpp"].compiler == ("clang++",)
    assert config.runner_paths == {"sde": "/opt/sde64"}
    assert config.tool_paths == {"oneapi-cpp": "/opt/oneapi/icpx"}
    assert config.rust_package.name == "custom-tsl"
    assert config.rust_package.version == "1.2.3"
    assert config.rust_package.edition == "2024"
    assert config.rust_package.rust_version == "1.85"
    assert config.rust_package.readme == "CRATE.md"


def test_generate_uses_discovered_backend_defaults_for_formatting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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

    def fake_generate(source_paths: object, **kwargs: object) -> object:
        calls["generate"] = (source_paths, kwargs)
        return SimpleNamespace(
            diagnostics=(),
            coverage=(),
            artifacts=SimpleNamespace(artifacts=()),
            rendered=None,
        )

    def fake_write(artifacts: object, output_root: object) -> object:
        del artifacts
        calls["write"] = output_root
        return SimpleNamespace(
            diagnostics=(), written=(), output_root=Path(output_root)
        )

    def fake_format(output_root: object, backends: object) -> object:
        calls["format"] = (output_root, backends)
        return SimpleNamespace(notes=(), formatted=())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "generate_project", fake_generate)
    monkeypatch.setattr(cli, "write_artifacts", fake_write)
    monkeypatch.setattr("tslc.output.format.format_generated", fake_format)

    status = cli.main(
        ["generate", "--primitives", "add", "--profiles", "scalar"]
    )

    assert status == 0
    source_paths, kwargs = calls["generate"]
    assert source_paths == ((tmp_path / "data").resolve(),)
    assert kwargs["backends"] == ["cpp"]
    assert calls["format"] == ((tmp_path / "out").resolve(), ("cpp",))


def test_doctor_uses_verifier_preflight_for_selected_backend_and_profile(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = diagnose(
        sources=(data_root,),
        machine_profiles=machine_profiles_path,
        backends=("cpp",),
        profiles=("scalar",),
        work_root=tmp_path / "doctor",
        runner=runner,
    )

    assert report["diagnostics"] == []
    assert [backend["id"] for backend in report["backends"]] == ["cpp"]
    profile = report["backends"][0]["profiles"][0]
    assert profile["name"] == "scalar"
    assert profile["build_ready"] is True
    assert profile["native_run"] is True
    assert [command.step for command in seen] == ["preflight"]


def test_doctor_reports_the_rust_target_attached_during_preparation(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "host-target":
            return BuildCommandResult(
                command=command,
                returncode=0,
                stdout="host: x86_64-unknown-linux-gnu\n",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = diagnose(
        sources=(data_root,),
        machine_profiles=machine_profiles_path,
        backends=("rust",),
        profiles=("avx2",),
        work_root=tmp_path / "doctor",
        runner=runner,
    )

    assert report["diagnostics"] == []
    profile = report["backends"][0]["profiles"][0]
    assert profile["name"] == "avx2"
    assert profile["build_ready"] is True
    assert profile["target"] == "x86_64-unknown-linux-gnu"
    assert [command.step for command in seen] == [
        "preflight",
        "host-target",
        "target-preflight",
    ]


def test_doctor_reports_registered_backend_through_capability_hooks(
    monkeypatch: pytest.MonkeyPatch,
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    """Doctor consumes backend-owned projections; no cpp/rust id dispatch."""

    from tslc.backend import registry
    from tslc.backend.cpp_capability import CPP_BACKEND

    def fake_verify_machine_profile(profile: object, family: object) -> VerifyProfile:
        del family
        return VerifyProfile(profile_name=profile.name, file_stem=profile.name)  # type: ignore[attr-defined]

    def fake_toolchain_commands(
        profile: VerifyProfile, config: object
    ) -> ToolchainCommands:
        del profile, config
        return ToolchainCommands(compiler=("fakecc",), target=None, linker=None)

    def fake_prepare(
        root: Path, backend: object, config: object, runner: object
    ) -> BackendPreparation:
        del root, config, runner
        return BackendPreparation(backend=backend)  # type: ignore[arg-type]

    fake_driver = VerifyBackendDriver(
        backend_id="fake",
        required_tools=(),
        prepare_backend=fake_prepare,
        command_groups=lambda root, backend, config: (),
        after_successful_command=(
            lambda result, profiles, config, runner: CommandFollowUp()
        ),
    )
    fake = replace(
        CPP_BACKEND,
        backend_id="fake",
        root_path="fake",
        verify_machine_profile=fake_verify_machine_profile,
        toolchain_commands=fake_toolchain_commands,
        verify_driver_factory=lambda: fake_driver,
        generated_format=None,
    )
    monkeypatch.setattr(
        registry, "BACKEND_CAPABILITIES", (*registry.BACKEND_CAPABILITIES, fake)
    )
    monkeypatch.setattr(registry, "_BY_ID", {**registry._BY_ID, "fake": fake})
    # The source corpus does not carry type spellings for the fake backend;
    # doctor's toolchain reporting is under test here, not corpus coverage.
    real_check_catalog = doctor_module.check_catalog
    monkeypatch.setattr(
        doctor_module,
        "check_catalog",
        lambda sources, *, backends: real_check_catalog(sources, backends=("cpp",)),
    )

    monkeypatch.setattr(
        MachineProfile,
        "supports_backend",
        lambda self, backend_id: backend_id == "fake",
    )

    report = diagnose(
        sources=(data_root,),
        machine_profiles=machine_profiles_path,
        backends=("fake",),
        profiles=("scalar",),
        work_root=tmp_path / "doctor",
        runner=lambda command: BuildCommandResult(command=command, returncode=0),
    )

    assert report["diagnostics"] == []
    assert [backend["id"] for backend in report["backends"]] == ["fake"]
    profile = report["backends"][0]["profiles"][0]
    assert profile["name"] == "scalar"
    assert profile["compiler"]["command"] == "fakecc"
    assert profile["build_ready"] is True


def test_project_config_tools_flow_into_doctor_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "tslc.toml"
    config_path.write_text(
        "\n".join(
            (
                "[tslc]",
                'sources = ["data"]',
                'machine_profiles = "profiles.json"',
                'backends = ["cpp"]',
                "[tslc.tools]",
                'oneapi-cpp = "/opt/oneapi/icpx"',
                'wasi-cpp = "/opt/wasi/clang++"',
                "",
            )
        ),
        encoding="utf-8",
    )
    config = load_project_config(config_path)
    assert config is not None
    args = SimpleNamespace(
        sources=None,
        machine_profiles=None,
        backend=[],
        backends=None,
        compiler=[],
        target=[],
        linker=[],
        runner=[],
        work_root=None,
    )

    settings = doctor_module._settings(args, config)

    assert settings.tool_paths == {
        "oneapi-cpp": "/opt/oneapi/icpx",
        "wasi-cpp": "/opt/wasi/clang++",
    }


def test_coverage_inventory_help_does_not_write(
    tmp_path: Path,
) -> None:
    output = tmp_path / "inventory.md"

    with pytest.raises(SystemExit) as exc:
        coverage_inventory.main(["--help", "--output", str(output)])

    assert exc.value.code == 0
    assert not output.exists()


def test_doctor_rvv_preflight_excludes_universal_overlay_headers(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = diagnose(
        sources=(data_root,),
        machine_profiles=machine_profiles_path,
        backends=("cpp",),
        profiles=("rvv",),
        work_root=tmp_path / "doctor",
        tool_paths={"riscv-cpp": "c++"},
        runner=runner,
    )

    assert report["diagnostics"] == []
    assert [command.step for command in seen] == ["target-preflight"]
    source = (
        tmp_path
        / "doctor/cpp/build/_compiler_preflight/rvv/tslc_target_check.cpp"
    ).read_text(encoding="utf-8")
    assert "#include <riscv_vector.h>" in source
    assert "ac_int.hpp" not in source
