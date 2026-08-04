"""Read-only host and toolchain evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, cast

from pipcost.records import digest_file
from pipcost.workspace import WorkspacePaths


def _first_cpu_record() -> dict[str, str]:
    path = Path("/proc/cpuinfo")
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            break
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return result


def cpu_flags() -> frozenset[str]:
    record = _first_cpu_record()
    value = record.get("flags", record.get("Features", ""))
    return frozenset(value.lower().split())


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _cache_records() -> list[dict[str, str | None]]:
    root = Path("/sys/devices/system/cpu/cpu0/cache")
    result: list[dict[str, str | None]] = []
    if not root.is_dir():
        return result
    for path in sorted(root.glob("index*")):
        result.append(
            {
                "level": _read_optional(path / "level"),
                "type": _read_optional(path / "type"),
                "size": _read_optional(path / "size"),
                "shared_cpu_list": _read_optional(path / "shared_cpu_list"),
            }
        )
    return result


def _numa_records() -> list[dict[str, str | None]]:
    root = Path("/sys/devices/system/node")
    result: list[dict[str, str | None]] = []
    if not root.is_dir():
        return result
    for path in sorted(root.glob("node[0-9]*")):
        suffix = path.name.removeprefix("node")
        if not suffix.isdigit():
            continue
        result.append(
            {
                "node": suffix,
                "cpu_list": _read_optional(path / "cpulist"),
                "distance": _read_optional(path / "distance"),
            }
        )
    return result


def host_record() -> dict[str, object]:
    cpu = _first_cpu_record()
    affinity: list[int] | None = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity = sorted(os.sched_getaffinity(0))
        except OSError:
            affinity = None
    governor = _read_optional(
        Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    )
    frequency = _read_optional(
        Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    )
    dmi_product = _read_optional(Path("/sys/class/dmi/id/product_name")) or ""
    virtual_products = (
        "kvm",
        "qemu",
        "vmware",
        "virtual machine",
        "virtualbox",
    )
    virtualization = "hypervisor" in cpu_flags() or any(
        item in dmi_product.lower() for item in virtual_products
    )
    return {
        "schema_version": 1,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu": {
            "vendor": cpu.get("vendor_id", cpu.get("CPU implementer")),
            "family": cpu.get("cpu family"),
            "model": cpu.get("model"),
            "stepping": cpu.get("stepping"),
            "model_name": cpu.get("model name", cpu.get("Processor")),
            "flags": sorted(cpu_flags()),
            "online_count": os.cpu_count(),
            "affinity": affinity,
            "caches": _cache_records(),
            "numa_nodes": _numa_records(),
            "frequency_governor": governor,
            "current_frequency_khz": frequency,
        },
        "virtualization_detected": virtualization,
        "performance_counters": {
            "perf_executable": shutil.which("perf"),
            "paranoid": _read_optional(Path("/proc/sys/kernel/perf_event_paranoid")),
        },
    }


def profile_requirements(
    machine_profiles_path: Path,
    profile: str,
) -> tuple[str, ...]:
    value = json.loads(machine_profiles_path.read_text(encoding="utf-8"))
    for entries in value.values():
        for entry in entries:
            if entry.get("name") == profile:
                features = str(entry.get("target_features", "")).split()
                return tuple(sorted(feature.lower() for feature in features))
    raise ValueError(f"unknown machine profile {profile!r}")


def native_profile_report(
    machine_profiles_path: Path,
    profile: str,
) -> dict[str, object]:
    required = profile_requirements(machine_profiles_path, profile)
    if profile == "scalar":
        required = ()
    visible = cpu_flags()
    ignored = {"nosimd-invalid"}
    missing = sorted(
        feature
        for feature in required
        if feature not in visible and feature not in ignored
    )
    return {
        "profile": profile,
        "required_features": list(required),
        "missing_features": missing,
        "native": not missing,
    }


def compiler_record(command: str) -> dict[str, object]:
    executable = shutil.which(command)
    if executable is None:
        return {
            "command": command,
            "available": False,
            "executable": None,
            "version": None,
        }
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    version = (completed.stdout or completed.stderr).splitlines()
    return {
        "command": command,
        "available": completed.returncode == 0,
        "executable": str(Path(executable).resolve()),
        "digest": digest_file(Path(executable).resolve()),
        "version": version[0] if version else "",
    }


def tslc_doctor(
    paths: WorkspacePaths,
    *,
    source_root: Path,
    profile: str,
    compiler: str,
) -> dict[str, Any]:
    work_root = paths.output_path("doctor", source_root.name, profile)
    command = [
        sys.executable,
        "-m",
        "tslc",
        "doctor",
        "--sources",
        str(source_root / "tsldata"),
        "--machine-profiles",
        str(source_root / "supplementary" / "buildsystem" / "machine_profiles.json"),
        "--backend",
        "cpp",
        "--profile",
        profile,
        "--compiler",
        f"cpp={compiler}",
        "--work-root",
        str(work_root),
        "--format",
        "json",
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(source_root / "tslc" / "src")
    completed = subprocess.run(
        command,
        cwd=source_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        report = cast(dict[str, Any], json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"tslc doctor did not return JSON: {completed.stderr.strip()}"
        ) from exc
    report["command"] = command
    report["returncode"] = completed.returncode
    return report
