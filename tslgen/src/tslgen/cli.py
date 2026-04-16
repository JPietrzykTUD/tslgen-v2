from pathlib import Path
from typing import Annotated, Iterable, List, Literal, Optional
from cyclopts import App, Parameter
import psutil

from tslgen.core.context import ALLOWED_LANGUAGES, GenerationGoal, GlobalContext, SupportedLanguage, expand_goal
from tslgen.core.types import ConcreteType


type HardwareMode = Literal["auto-detect", "explicit"]


def validate_cli(
    hardware_mode: HardwareMode = "auto-detect",
    hardware_flags: Optional[List[str]] = None,
    **_: object,
) -> None:

    if hardware_mode == "explicit" and not hardware_flags:
        raise ValueError("--hardware-mode explicit requires --hardware-flags")

    if hardware_mode == "auto-detect" and hardware_flags:
        raise ValueError(
            "--hardware-flags may not be provided when --hardware-mode auto-detect is selected"
        )


def detect_hardware_flags() -> List[str]:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return []

    try:
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("flags") and ":" in line:
                return line.split(":", 1)[1].strip().split()
    except OSError:
        return []

    return []


def ends_with_path(path: Path, subpath: Path) -> bool:
    p = path.parts
    s = subpath.parts
    return len(s) <= len(p) and p[-len(s) :] == s


def find_all_paths_ending_with(paths: Iterable[Path], subpath: Path) -> List[Path]:
    return [path for path in paths if ends_with_path(path, subpath)]


app = App()


@app.default
def main(
    hardware_mode: HardwareMode = "auto-detect",
    hardware_flags: Annotated[
        Optional[List[str]],
        Parameter(
            consume_multiple=True,
            help="Explicit hardware flags. Example: --hardware-flags avx2 sse4 bmi2",
        ),
    ] = None,
    primitive_files: Annotated[
        Optional[List[str]],
        Parameter(consume_multiple=True, help="One path, multiple values."),
    ] = None,
    types: Annotated[
        Optional[List[ConcreteType]],
        Parameter(
            consume_multiple=True,
            help="Allowed values: ui8 ui16 ui32 ui64 si8 si16 si32 si64 f32 f64",
        ),
    ] = None,
    extensions: Annotated[
        Optional[List[str]],
        Parameter(consume_multiple=True),
    ] = None,
    primitives: Annotated[
        Optional[List[str]],
        Parameter(consume_multiple=True),
    ] = None,
    lang: Annotated[
        Optional[List[SupportedLanguage]],
        Parameter(consume_multiple=True, help="Allowed values: cpp rust"),
    ] = None,
    goal: Annotated[
        GenerationGoal,
        Parameter(help="Allowed values: parse generate-tsl generate-tests"),
    ] = "generate-tsl",
    thread_count: Annotated[
        Optional[int],
        Parameter(help="Number of threads to use for generation. Default is number of CPU cores."),
    ] = None,
) -> None:
    if hardware_mode == "explicit" and not hardware_flags:
        print("Error: --hardware-mode explicit requires --hardware-flags")
        print("Run 'tslgen --help' for usage.")
        raise SystemExit(2)

    if hardware_mode == "auto-detect" and hardware_flags:
        print(
            "Error: --hardware-flags may not be provided when --hardware-mode auto-detect is selected"
        )
        print("Run 'tslgen --help' for usage.")
        raise SystemExit(2)

    if hardware_mode == "auto-detect":
        flags = detect_hardware_flags()
    else:
        # Validator guarantees hardware_flags is present in this branch.
        flags = hardware_flags

    project_root = Path(__file__).resolve().parents[2]
    tsl_data_base_path = project_root / "tsldata"
    all_primitive_paths = list(tsl_data_base_path.joinpath("primitives").rglob("*.tsl"))

    primitive_files_paths: List[Path]
    if primitive_files is not None:
        primitive_files_paths = []
        for primitive_file in primitive_files:
            matches = find_all_paths_ending_with(all_primitive_paths, Path(primitive_file))
            if not matches:
                raise ValueError(
                    f"Primitive file '{primitive_file}' not found in data directory."
                )
            primitive_files_paths.extend(matches)
    else:
        primitive_files_paths = all_primitive_paths

    if thread_count is None:
        thread_count = psutil.cpu_count(logical=False)

    config = GlobalContext(
        relevant_hw_support_flags=flags,
        relevant_data_files=primitive_files_paths,
        relevant_types=types,
        relevant_extensions=extensions,
        relevant_primitive_names=primitives,
        relevant_languages=lang or list(ALLOWED_LANGUAGES),
        generation_goal=expand_goal(goal),
        thread_count=thread_count,
    )
    print(config)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
