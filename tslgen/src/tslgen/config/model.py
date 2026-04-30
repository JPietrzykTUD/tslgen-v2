from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_STANDARD_LIBRARY_ROOT = Path("tsldata")
DEFAULT_SOURCE_EXTENSIONS: tuple[str, ...] = (".tsl",)


def normalize_source_extension(extension: str) -> str:
    normalized = extension.casefold()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized


@dataclass(frozen=True, slots=True)
class SourceConfig:
    explicit_paths: tuple[Path, ...] = ()
    include_standard_library: bool = False
    standard_library_root: Path = DEFAULT_STANDARD_LIBRARY_ROOT
    allowed_extensions: tuple[str, ...] = DEFAULT_SOURCE_EXTENSIONS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "explicit_paths",
            tuple(Path(path) for path in self.explicit_paths),
        )
        object.__setattr__(self, "standard_library_root", Path(self.standard_library_root))
        object.__setattr__(
            self,
            "allowed_extensions",
            tuple(
                sorted(
                    {
                        normalize_source_extension(extension)
                        for extension in self.allowed_extensions
                    }
                )
            ),
        )

    @classmethod
    def explicit(cls, paths: tuple[Path, ...]) -> SourceConfig:
        return cls(explicit_paths=paths, include_standard_library=False)

    @classmethod
    def standard_library(cls, root: Path = DEFAULT_STANDARD_LIBRARY_ROOT) -> SourceConfig:
        return cls(include_standard_library=True, standard_library_root=root)
