"""Primitive-call dependency closure over selected implementations."""

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import Catalog
from tslgen.lowering.model import (
    PrimitiveCallDependencyClosure,
    PrimitiveCallReference,
)
from tslgen.lowering.primitive_call_inventory import (
    lower_primitive_call_reference_inventory,
)

_SelectedIdentity = tuple[
    str,
    str,
    str,
    str,
    tuple[tuple[str, str, str], ...],
]


def lower_primitive_call_dependency_closure(
    root: SelectedImplementation,
    catalog: Catalog,
) -> PrimitiveCallDependencyClosure:
    """Discover selected implementations reachable through primitive calls."""

    selected: list[SelectedImplementation] = [root]
    references: list[PrimitiveCallReference] = []
    diagnostics: list[Diagnostic] = []
    seen: set[_SelectedIdentity] = {_selected_identity(root)}
    queue: list[SelectedImplementation] = [root]

    while queue:
        current = queue.pop(0)
        inventory = lower_primitive_call_reference_inventory(current, catalog)
        diagnostics.extend(inventory.diagnostics)

        for reference in inventory.references:
            references.append(reference)
            dependency = reference.target_match.selected
            identity = _selected_identity(dependency)
            if identity in seen:
                continue
            seen.add(identity)
            selected.append(dependency)
            queue.append(dependency)

    return PrimitiveCallDependencyClosure(
        selected=tuple(selected),
        references=tuple(references),
        diagnostics=tuple(diagnostics),
    )


def _selected_identity(selected: SelectedImplementation) -> _SelectedIdentity:
    return selected.target.sort_key()
