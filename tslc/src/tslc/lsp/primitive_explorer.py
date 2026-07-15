"""Compiler-owned primitive and concrete-slot explorer projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS, SCALAR_TYPE_ORDER
from tslc.catalog.signatures import parse_signature
from tslc.catalog_index import CatalogIndex
from tslc.diagnostics import SourceSpan
from tslc.select.selector import SelectedImplementation, Selector

SlotOrigin = Literal["authored", "broader", "inherited"]


@dataclass(frozen=True, slots=True)
class ExplorerImplementation:
    """One selected source body that can satisfy an explorer slot."""

    primitive: str
    signature: str
    parameters: tuple[str, ...]
    extension: str
    type_group: str
    selector_path: tuple[str, ...]
    source: SourceSpan
    origin: SlotOrigin


@dataclass(frozen=True, slots=True)
class ExplorerSlot:
    """One visible ``(extension, type)`` cell for a concrete profile/backend."""

    extension: str
    type_tag: str
    implementations: tuple[ExplorerImplementation, ...] = ()
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.implementations)

    @property
    def origins(self) -> tuple[SlotOrigin, ...]:
        order = {"authored": 0, "broader": 1, "inherited": 2}
        return tuple(
            sorted(
                {implementation.origin for implementation in self.implementations},
                key=order.__getitem__,
            )
        )


@dataclass(frozen=True, slots=True)
class ExplorerPrimitive:
    """One callable primitive family in the selected file/corpus scope."""

    name: str
    signatures: tuple[str, ...]
    definitions: tuple[SourceSpan, ...]
    available_slots: int
    total_slots: int
    calls: tuple[str, ...]
    called_by: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveExplorer:
    """Sidebar facts for one concrete profile/backend and optional primitive."""

    profile: str
    backend: str
    profiles: tuple[str, ...]
    backends: tuple[str, ...]
    stale: bool
    primitives: tuple[ExplorerPrimitive, ...]
    selected_primitive: str | None
    slots: tuple[ExplorerSlot, ...]


class PrimitiveExplorerCache:
    """Reuse one profile/backend/scope selection matrix across tree requests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._catalog: Catalog | None = None
        self._index: CatalogIndex | None = None
        self._profiles: Mapping[str, MachineProfile] | None = None
        self._backends: tuple[str, ...] = ()
        self._profile = ""
        self._backend = ""
        self._path: Path | None = None
        self._primitives: tuple[ExplorerPrimitive, ...] = ()
        self._slots_by_name: dict[str, tuple[ExplorerSlot, ...]] = {}

    def project(
        self,
        catalog: Catalog,
        index: CatalogIndex,
        profiles: Mapping[str, MachineProfile],
        backends: tuple[str, ...],
        *,
        profile: str,
        backend: str,
        path: Path | None,
        selected_primitive: str | None,
        stale: bool,
    ) -> PrimitiveExplorer:
        with self._lock:
            if not self._matches(
                catalog, index, profiles, backends, profile, backend, path
            ):
                self._rebuild(
                    catalog, index, profiles, backends, profile, backend, path
                )
            names = {primitive.name for primitive in self._primitives}
            selected = selected_primitive if selected_primitive in names else None
            return PrimitiveExplorer(
                profile,
                backend,
                tuple(sorted(profiles)),
                tuple(sorted(backends)),
                stale,
                self._primitives,
                selected,
                self._slots_by_name.get(selected or "", ()),
            )

    def _matches(
        self,
        catalog: Catalog,
        index: CatalogIndex,
        profiles: Mapping[str, MachineProfile],
        backends: tuple[str, ...],
        profile: str,
        backend: str,
        path: Path | None,
    ) -> bool:
        return bool(
            self._catalog is catalog
            and self._index is index
            and self._profiles is profiles
            and self._backends == backends
            and self._profile == profile
            and self._backend == backend
            and self._path == path
        )

    def _rebuild(
        self,
        catalog: Catalog,
        index: CatalogIndex,
        profiles: Mapping[str, MachineProfile],
        backends: tuple[str, ...],
        profile: str,
        backend: str,
        path: Path | None,
    ) -> None:
        names = _primitive_names(catalog, index, path)
        selector = Selector()
        machine_profile = profiles[profile]
        extension_names = selector.emitted_extensions(
            catalog, machine_profile, backend_id=backend
        )
        slots_by_name = {
            name: _primitive_slots(
                catalog,
                selector,
                machine_profile,
                backend,
                extension_names,
                name,
            )
            for name in names
        }
        primitives = tuple(
            ExplorerPrimitive(
                name=name,
                signatures=tuple(
                    sorted(
                        {
                            primitive.signature
                            for primitive in catalog.primitives_named(
                                name, unmasked=False
                            )
                        }
                    )
                ),
                definitions=_scoped_definitions(index, name, path),
                available_slots=sum(
                    slot.available for slot in slots_by_name[name]
                ),
                total_slots=len(slots_by_name[name]),
                calls=index.primitive_calls.get(name, ()),
                called_by=index.primitive_callers.get(name, ()),
            )
            for name in names
        )
        self._catalog = catalog
        self._index = index
        self._profiles = profiles
        self._backends = backends
        self._profile = profile
        self._backend = backend
        self._path = path
        self._primitives = primitives
        self._slots_by_name = slots_by_name


def primitive_explorer(
    catalog: Catalog,
    index: CatalogIndex,
    profiles: Mapping[str, MachineProfile],
    backends: tuple[str, ...],
    *,
    profile: str | None = None,
    backend: str | None = None,
    path: Path | None = None,
    selected_primitive: str | None = None,
    preferred_profiles: tuple[str, ...] = (),
    stale: bool = False,
    cache: PrimitiveExplorerCache | None = None,
) -> PrimitiveExplorer:
    """Build deterministic index/selection facts without scanning or lowering bodies."""

    profile_name = _selected_profile(profiles, profile, preferred_profiles)
    backend_id = _selected_backend(backends, backend)
    if not profile_name or not backend_id:
        return PrimitiveExplorer(
            profile_name,
            backend_id,
            tuple(sorted(profiles)),
            tuple(sorted(backends)),
            stale,
            (),
            None,
            (),
        )

    return (cache or PrimitiveExplorerCache()).project(
        catalog,
        index,
        profiles,
        backends,
        profile=profile_name,
        backend=backend_id,
        path=path.resolve() if path is not None else None,
        selected_primitive=selected_primitive,
        stale=stale,
    )


def _primitive_names(
    catalog: Catalog, index: CatalogIndex, path: Path | None
) -> tuple[str, ...]:
    names = sorted({primitive.name for primitive in catalog.primitives})
    if path is None:
        return tuple(names)
    return tuple(
        name
        for name in names
        if any(span.path.resolve() == path for span in index.primitive_definitions.get(name, ()))
    )


def _scoped_definitions(
    index: CatalogIndex, name: str, path: Path | None
) -> tuple[SourceSpan, ...]:
    spans = index.primitive_definitions.get(name, ())
    if path is not None:
        spans = tuple(span for span in spans if span.path.resolve() == path)
    return tuple(sorted(spans, key=_span_key))


def _primitive_slots(
    catalog: Catalog,
    selector: Selector,
    profile: MachineProfile,
    backend: str,
    extension_names: tuple[str, ...],
    primitive_name: str,
) -> tuple[ExplorerSlot, ...]:
    selection = selector.select_profile(
        catalog,
        profile,
        primitive_name,
        DEFAULT_SCALAR_TYPE_TAGS,
        backend_id=backend,
    )
    selected: dict[tuple[str, str], list[ExplorerImplementation]] = {}
    for item in selection.selected:
        source = _implementation_source(item)
        if source is None:
            continue
        key = (item.extension.isa_name, item.type_tag)
        implementation = item.implementation
        selected.setdefault(key, []).append(
            ExplorerImplementation(
                primitive=item.primitive.name,
                signature=item.primitive.signature,
                parameters=item.primitive.parameters,
                extension=implementation.extension,
                type_group=implementation.type_group,
                selector_path=implementation.selector_path,
                source=source,
                origin=_slot_origin(catalog, item),
            )
        )

    keys = (
        set(selected)
        if _is_free_function(catalog, selector, primitive_name)
        else {
            (extension, type_tag)
            for extension in extension_names
            for type_tag in DEFAULT_SCALAR_TYPE_TAGS
        }
    )
    keys.update(selected)
    return tuple(
        ExplorerSlot(
            extension=extension,
            type_tag=type_tag,
            implementations=_unique_implementations(selected.get((extension, type_tag), ())),
            unavailable_reason=(
                None
                if (extension, type_tag) in selected
                else (
                    f"No implementation is selected for {primitive_name}<{type_tag}> "
                    f"on {extension} with profile {profile.name!r} and backend {backend!r}."
                )
            ),
        )
        for extension, type_tag in sorted(
            keys,
            key=lambda item: (
                item[0],
                SCALAR_TYPE_ORDER.get(item[1], 999),
                item[1],
            ),
        )
    )


def _is_free_function(
    catalog: Catalog, selector: Selector, primitive_name: str
) -> bool:
    primitives = catalog.primitives_named(primitive_name, unmasked=False)
    shapes = tuple(parse_signature(primitive.signature) for primitive in primitives)
    return bool(shapes) and all(
        shape is not None and selector.support.shape_is_free_function(shape)
        for shape in shapes
    )


def _implementation_source(item: SelectedImplementation) -> SourceSpan | None:
    implementation = item.implementation
    return (
        implementation.body_source
        or implementation.selector_source
        or implementation.source
        or item.primitive.source
    )


def _slot_origin(catalog: Catalog, item: SelectedImplementation) -> SlotOrigin:
    implementation = item.implementation
    if implementation.extension != item.extension.isa_name:
        return "inherited"
    if catalog.type_group_members(implementation.type_group) != (item.type_tag,):
        return "broader"
    return "authored"


def _unique_implementations(
    values: tuple[ExplorerImplementation, ...] | list[ExplorerImplementation],
) -> tuple[ExplorerImplementation, ...]:
    unique = {
        (
            value.primitive,
            value.signature,
            value.parameters,
            value.extension,
            value.type_group,
            value.selector_path,
            _span_key(value.source),
            value.origin,
        ): value
        for value in values
    }
    return tuple(unique[key] for key in sorted(unique))


def _selected_profile(
    profiles: Mapping[str, MachineProfile],
    requested: str | None,
    preferred: tuple[str, ...],
) -> str:
    if requested in profiles:
        return requested or ""
    configured = tuple(name for name in preferred if name in profiles)
    if configured:
        # Start with a useful coverage matrix before the author explicitly
        # selects a profile. Configuration order remains the stable tie-break.
        return max(
            configured,
            key=lambda name: (
                len(profiles[name].features) + len(profiles[name].compile_modes),
                -configured.index(name),
            ),
        )
    if "scalar" in profiles:
        return "scalar"
    return min(profiles, default="")


def _selected_backend(backends: tuple[str, ...], requested: str | None) -> str:
    if requested in backends:
        return requested or ""
    if "cpp" in backends:
        return "cpp"
    return min(backends, default="")


def _span_key(span: SourceSpan) -> tuple[str, int, int, int, int]:
    return (
        span.path.resolve().as_posix(),
        span.line,
        span.column,
        span.end_line or span.line,
        span.end_column or span.column,
    )


__all__ = (
    "ExplorerImplementation",
    "ExplorerPrimitive",
    "ExplorerSlot",
    "PrimitiveExplorer",
    "PrimitiveExplorerCache",
    "primitive_explorer",
)
