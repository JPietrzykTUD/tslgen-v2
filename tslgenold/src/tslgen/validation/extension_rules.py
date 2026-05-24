from __future__ import annotations

from collections.abc import Iterator

from tslgen.core.diagnostics import Diagnostic, SourceLocation, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog
from tslgen.domain.extensions import Extension
from tslgen.domain.values import CatalogMap, CatalogValue


def validate_extension_references(catalog: Catalog) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for extension in catalog.extensions:
        diagnostics.extend(_validate_inheritance_parent(extension, catalog))
        diagnostics.extend(_validate_generation_support(extension, catalog))
        diagnostics.extend(_validate_excluded_templates(extension, catalog))
    diagnostics.extend(_validate_inheritance_cycles(catalog))
    return sort_diagnostics(diagnostics)


def _validate_inheritance_parent(
    extension: Extension,
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    parent = _string_value(extension.fields.get("inherits"))
    if parent is None:
        return ()
    if parent == extension.name:
        return (
            Diagnostic.error(
                "TSL-REF-EXTENSION-SELF",
                f"extension {extension.name!r} must not inherit from itself",
                location=extension.source_span.location,
            ),
        )
    if parent not in catalog.extensions_by_name:
        return (
            _unknown_reference_diagnostic(
                code="TSL-REF-UNKNOWN-EXTENSION",
                owner_kind="extension",
                owner_name=extension.name,
                field_name="inherits",
                target_kind="extension",
                reference=parent,
                location=extension.source_span.location,
            ),
        )
    return ()


def _validate_generation_support(
    extension: Extension,
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for value_map in _walk_maps(extension.fields):
        generation_support = value_map.get("generation_support")
        if generation_support is None:
            continue
        for reference in _string_sequence(generation_support):
            if reference not in catalog.extensions_by_name:
                diagnostics.append(
                    _unknown_reference_diagnostic(
                        code="TSL-REF-UNKNOWN-EXTENSION",
                        owner_kind="extension",
                        owner_name=extension.name,
                        field_name="generation_support",
                        target_kind="extension",
                        reference=reference,
                        location=extension.source_span.location,
                    )
                )
    return tuple(diagnostics)


def _validate_excluded_templates(
    extension: Extension,
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for value_map in _walk_maps(extension.fields):
        excluded_templates = value_map.get("exclude_templates")
        if excluded_templates is None:
            continue
        for reference in _string_sequence(excluded_templates):
            if reference not in catalog.templates_by_name:
                diagnostics.append(
                    _unknown_reference_diagnostic(
                        code="TSL-REF-UNKNOWN-TEMPLATE",
                        owner_kind="extension",
                        owner_name=extension.name,
                        field_name="exclude_templates",
                        target_kind="template",
                        reference=reference,
                        location=extension.source_span.location,
                    )
                )
    return tuple(diagnostics)


def _validate_inheritance_cycles(catalog: Catalog) -> tuple[Diagnostic, ...]:
    parents = {
        extension.name: parent
        for extension in catalog.extensions
        if (
            (parent := _string_value(extension.fields.get("inherits"))) is not None
            and parent != extension.name
            and parent in catalog.extensions_by_name
        )
    }

    diagnostics: list[Diagnostic] = []
    resolved: set[str] = set()
    emitted_cycles: set[frozenset[str]] = set()
    for start in sorted(parents):
        seen_index: dict[str, int] = {}
        chain: list[str] = []
        current = start
        while current in parents:
            if current in seen_index:
                cycle = tuple(chain[seen_index[current] :])
                cycle_key = frozenset(cycle)
                if cycle_key not in emitted_cycles:
                    emitted_cycles.add(cycle_key)
                    diagnostics.append(_cycle_diagnostic(cycle, catalog))
                break
            if current in resolved:
                break
            seen_index[current] = len(chain)
            chain.append(current)
            current = parents[current]
        resolved.update(chain)
    return tuple(diagnostics)


def _cycle_diagnostic(cycle: tuple[str, ...], catalog: Catalog) -> Diagnostic:
    owner = catalog.extensions_by_name[cycle[0]]
    cycle_path = " -> ".join((*cycle, cycle[0]))
    return Diagnostic.error(
        "TSL-REF-EXTENSION-CYCLE",
        f"extension inheritance cycle detected: {cycle_path}",
        location=owner.source_span.location,
    )


def _walk_maps(value: CatalogValue) -> Iterator[CatalogMap]:
    if isinstance(value, FrozenMap):
        yield value
        for child in value.values():
            yield from _walk_maps(child)
    elif isinstance(value, tuple):
        for child in value:
            yield from _walk_maps(child)


def _string_value(value: CatalogValue | None) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _string_sequence(value: CatalogValue) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, tuple):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _unknown_reference_diagnostic(
    *,
    code: str,
    owner_kind: str,
    owner_name: str,
    field_name: str,
    target_kind: str,
    reference: str,
    location: SourceLocation,
) -> Diagnostic:
    return Diagnostic.error(
        code,
        f"{owner_kind} {owner_name!r} field {field_name!r} references unknown "
        f"{target_kind} {reference!r}",
        location=location,
    )
