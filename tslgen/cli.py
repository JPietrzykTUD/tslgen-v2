from pathlib import Path
from typing import Annotated, Literal, Optional, List, Iterable

from cyclopts import App, Parameter

from tslgen.core.context import GlobalContext, expand_goal, SupportedLanguage, GenerationGoal
from tslgen.core.types import ConcreteType

app = App()

type HardwareMode = Literal["auto-detect", "explicit"]

def validate_cli(**kwargs) -> None:
    hardware_mode: HardwareMode = kwargs["hardware_mode"]
    hardware_flags: Optional[List[str]] = kwargs["hardware_flags"]

    if hardware_mode == "explicit" and not hardware_flags:
        raise ValueError(
            '--hardware-mode explicit requires --hardware-flags'
        )

    if hardware_mode == "auto-detect" and hardware_flags:
        raise ValueError(
            '--hardware-flags may not be provided when '
            '--hardware-mode auto-detect is selected'
        )

def ends_with_path(path: Path, subpath: Path) -> bool:
    p = path.parts
    s = subpath.parts
    return len(s) <= len(p) and p[-len(s):] == s

def find_all_paths_ending_with(paths: Iterable[Path], subpath: Path) -> list[Path]:
    return [path for path in paths if ends_with_path(path, subpath)]


app = App(validator=validate_cli)

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
        Parameter(consume_multiple=True, help="Allowed values: ui8 ui16 ui32 ui64 si8 si16 si32 si64 f32 f64"),
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
) -> None:
    if hardware_mode == "auto-detect":
        flags = detect_hardware_flags()
    else:
        # Validator guarantees that hardware_flags is present in this branch.
        flags = hardware_flags
    
    tsl_data_base_path = Path(__file__).parent / "tsldata"
    all_primitive_paths = [
        f for f in tsl_data_base_path.joinpath("primitives").rglob("*.tsl")
    ]
    primitive_files_paths = []
    if primitive_files is not None:
        for primitive_file in primitive_files:
            c_path = find_all_paths_ending_with(all_primitive_paths, Path(primitive_file))
            if c_path is None:
                raise ValueError(f"Primitive file '{primitive_file}' not found in data directory.")
            primitive_files_paths.extend(c_path)
    else:
        primitive_files_paths = all_primitive_paths

    config = GlobalContext(
        relevant_hw_support_flags=flags,
        relevant_data_files=primitive_files_paths,
        relevant_types=types,
        relevant_extensions=extensions,
        relevant_primitive_names=primitives,
        relevant_languages=lang,
        generation_goal=expand_goal(goal)
    )
    print(config)

if __name__ == "__main__":
    app()