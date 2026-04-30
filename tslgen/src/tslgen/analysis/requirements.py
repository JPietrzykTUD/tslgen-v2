from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog, CatalogEntry
from tslgen.domain.values import CatalogValue


@dataclass(frozen=True, slots=True, order=True)
class FeatureFlag:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("feature flag name must be non-empty")


@dataclass(frozen=True, slots=True)
class FlagCatalog:
    aliases: FrozenMap[str, FeatureFlag]
    normalized_names: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "normalized_names", frozenset(self.normalized_names))

    def normalize(
        self,
        flag_name: str,
        *,
        location: SourceLocation | None = None,
    ) -> Result[FeatureFlag]:
        if not flag_name:
            return Result.failure(
                (
                    Diagnostic.error(
                        "TSL-FLAG-UNKNOWN",
                        "feature flag name must be non-empty",
                        location=location,
                    ),
                )
            )
        alias = self.aliases.get(flag_name)
        if alias is not None:
            return Result.ok(alias)
        if flag_name in self.normalized_names:
            return Result.ok(FeatureFlag(flag_name))
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-FLAG-UNKNOWN",
                    f"unknown feature flag {flag_name!r}",
                    location=location,
                ),
            )
        )

    def normalize_all(
        self,
        flag_names: Iterable[str],
        *,
        location: SourceLocation | None = None,
    ) -> Result[tuple[FeatureFlag, ...]]:
        diagnostics: list[Diagnostic] = []
        flags: set[FeatureFlag] = set()
        for flag_name in flag_names:
            normalized = self.normalize(flag_name, location=location)
            diagnostics.extend(normalized.diagnostics)
            if normalized.is_ok:
                flags.add(normalized.unwrap())
        ordered = tuple(sorted(flags, key=lambda flag: flag.name))
        if has_errors(diagnostics):
            return Result.failure(diagnostics)
        return Result.ok(ordered, diagnostics=diagnostics)


@dataclass(frozen=True, slots=True)
class RequirementConstraint:
    extension_names: tuple[str, ...]
    type_group_names: tuple[str, ...]
    required_flags: tuple[FeatureFlag, ...]
    selector_path: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "extension_names", tuple(self.extension_names))
        object.__setattr__(self, "type_group_names", tuple(self.type_group_names))
        object.__setattr__(
            self,
            "required_flags",
            tuple(sorted(self.required_flags, key=lambda flag: flag.name)),
        )
        object.__setattr__(self, "selector_path", tuple(self.selector_path))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.extension_names,
            self.type_group_names,
            tuple(flag.name for flag in self.required_flags),
            self.selector_path,
        )


def build_flag_catalog(catalog: Catalog) -> Result[FlagCatalog]:
    flag_entry = _flag_entry(catalog)
    if flag_entry is None:
        return Result.ok(FlagCatalog(FrozenMap.empty(), frozenset()))

    diagnostics: list[Diagnostic] = []
    aliases: dict[str, FeatureFlag] = {}
    for alias, value in flag_entry.fields.items():
        normalized_name = _normalized_flag_value(value)
        if normalized_name is None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-FLAG-SHAPE",
                    f"flag alias {alias!r} must define a string 'normalized' field",
                    location=flag_entry.source_span.location,
                )
            )
            continue
        aliases[alias] = FeatureFlag(normalized_name)

    if has_errors(diagnostics):
        return Result.failure(diagnostics)

    normalized_names = frozenset(flag.name for flag in aliases.values())
    return Result.ok(
        FlagCatalog(
            aliases=FrozenMap(aliases),
            normalized_names=normalized_names,
        ),
        diagnostics=diagnostics,
    )


def normalize_flags(
    catalog: Catalog,
    flag_names: Iterable[str],
    *,
    location: SourceLocation | None = None,
) -> Result[tuple[FeatureFlag, ...]]:
    flag_catalog = build_flag_catalog(catalog)
    if not flag_catalog.is_ok:
        return Result.failure(flag_catalog.diagnostics)
    return flag_catalog.unwrap().normalize_all(flag_names, location=location)


def _flag_entry(catalog: Catalog) -> CatalogEntry | None:
    for entry in catalog.entries:
        if entry.kind == "flags" and entry.name == "flags":
            return entry
    return None


def _normalized_flag_value(value: CatalogValue) -> str | None:
    if not isinstance(value, FrozenMap):
        return None
    normalized = value.get("normalized")
    if isinstance(normalized, str):
        return normalized
    return None
