from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


type HardwareFlagProvider = Callable[[], tuple[str, ...]]


def no_hardware_flags() -> tuple[str, ...]:
    return ()


def detect_proc_cpuinfo_flags(cpuinfo_path: Path = Path("/proc/cpuinfo")) -> tuple[str, ...]:
    try:
        lines = cpuinfo_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()

    for line in lines:
        if line.lower().startswith("flags") and ":" in line:
            return tuple(sorted(set(line.split(":", 1)[1].strip().split())))
    return ()
