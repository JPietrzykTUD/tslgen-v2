from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from tslgen.analysis.expansion import PrimitiveVariant
from tslgen.analysis.requirements import FeatureFlag, RequirementConstraint
from tslgen.analysis.selection import SelectionPlan, VariantImplementationPlan
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.implementations import (
    ImplementationSpec,
    implementation_specs_from_primitive,
)
from tslgen.domain.values import CatalogMap, CatalogValue


@dataclass(frozen=True, slots=True)
class ImplementationCandidate:
    candidate_id: str
    variant: PrimitiveVariant
    emitted_primitive_name: str
    source_primitive_name: str
    template_name: str
    backend: str | None
    target_extension: str
    source_extension: str
    type_tag: str
    required_flags: tuple[FeatureFlag, ...]
    implementation: ImplementationSpec

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate id must be non-empty")
        if not self.target_extension:
            raise ValueError("target extension must be non-empty")
        if not self.source_extension:
            raise ValueError("source extension must be non-empty")
        if not self.type_tag:
            raise ValueError("candidate type tag must be non-empty")
        object.__setattr__(
            self,
            "required_flags",
            tuple(sorted(self.required_flags, key=lambda flag: flag.name)),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.emitted_primitive_name,
            self.source_primitive_name,
            self.template_name,
            self.backend or "",
            self.target_extension,
            self.source_extension,
            self.type_tag,
            tuple(flag.name for flag in self.required_flags),
            self.variant.variant_id,
            self.implementation.extension_selector.raw,
            self.implementation.type_selector.raw,
            self.implementation.body.kind,
        )


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    plan: SelectionPlan
    candidates: tuple[ImplementationCandidate, ...]
    candidates_by_id: FrozenMap[str, ImplementationCandidate] = field(init=False)

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda candidate: candidate.key))
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(
            self,
            "candidates_by_id",
            FrozenMap((candidate.candidate_id, candidate) for candidate in candidates),
        )


def select_implementation_candidates(
    plan: SelectionPlan,
    catalog: Catalog,
) -> Result[CandidateSelection]:
    diagnostics: list[Diagnostic] = []
    if plan.request.backend is not None and not _known_backend(catalog, plan.request.backend):
        diagnostics.append(
            Diagnostic.error(
                "TSL-CANDIDATE-UNKNOWN-BACKEND",
                f"selection request references unknown backend {plan.request.backend!r}",
            )
        )

    implementation_plans = {
        _implementation_plan_key(implementation_plan): implementation_plan
        for implementation_plan in plan.implementation_plans
    }
    candidates: list[ImplementationCandidate] = []
    for variant in plan.variants:
        selected = _candidates_for_variant(
            variant,
            catalog,
            plan,
            implementation_plans,
        )
        diagnostics.extend(selected.diagnostics)
        if selected.is_ok:
            candidates.extend(selected.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        CandidateSelection(plan=plan, candidates=tuple(candidates)),
        diagnostics=ordered,
    )


def _candidates_for_variant(
    variant: PrimitiveVariant,
    catalog: Catalog,
    plan: SelectionPlan,
    implementation_plans: dict[tuple[str, str, str], VariantImplementationPlan],
) -> Result[tuple[ImplementationCandidate, ...]]:
    planned_selector_keys = frozenset(
        (implementation_plan.extension_selector.raw, implementation_plan.type_selector.raw)
        for implementation_plan in implementation_plans.values()
        if implementation_plan.variant_id == variant.variant_id
    )
    if not planned_selector_keys:
        if plan.allowed_extensions:
            return Result.failure((_no_candidate_diagnostic(variant),))
        return Result.ok(())

    specs_result = implementation_specs_from_primitive(
        variant.source.declaration,
        include_extension_selector=lambda selector: any(
            extension_selector == selector.raw
            for extension_selector, _ in planned_selector_keys
        ),
        include_type_selector=lambda extension_selector, type_selector: (
            extension_selector.raw,
            type_selector.raw,
        )
        in planned_selector_keys,
    )
    diagnostics = list(specs_result.diagnostics)
    if not specs_result.is_ok:
        return Result.failure(diagnostics)

    specs = specs_result.unwrap().specs
    if not specs:
        return Result.ok(())

    candidates: list[ImplementationCandidate] = []
    for spec in specs:
        source_extensions = _source_extensions_by_target(
            catalog,
            spec.extension_selector.names,
            plan.allowed_extensions,
        )
        if not source_extensions:
            continue

        implementation_plan = implementation_plans.get(
            (
                variant.variant_id,
                spec.extension_selector.raw,
                spec.type_selector.raw,
            )
        )
        if implementation_plan is None:
            continue

        for target_extension, source_extension in source_extensions:
            if not _supports_backend(catalog, target_extension, plan.request.backend):
                continue
            type_tags = _expand_selector_type_tags(
                catalog,
                implementation_plan.type_selector.names,
            )
            for type_tag in type_tags:
                required_flags = _matching_required_flags(
                    catalog,
                    implementation_plan.requirements,
                    target_extension=target_extension,
                    source_extension=source_extension,
                    type_tag=type_tag,
                )
                if not _supports_required_flags(plan, required_flags):
                    continue
                candidates.append(
                    _candidate(
                        variant=variant,
                        plan=plan,
                        target_extension=target_extension,
                        source_extension=source_extension,
                        type_tag=type_tag,
                        required_flags=required_flags,
                        spec=spec,
                    )
                )

    if plan.allowed_extensions and not candidates and not diagnostics:
        diagnostics.append(_no_candidate_diagnostic(variant))

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(candidates), diagnostics=ordered)


def _no_candidate_diagnostic(variant: PrimitiveVariant) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CANDIDATE-NONE",
        f"primitive variant {variant.variant_id!r} has no implementation "
        "candidate for the requested selector constraints",
        location=variant.source.declaration.source_span.location,
    )


def _candidate(
    *,
    variant: PrimitiveVariant,
    plan: SelectionPlan,
    target_extension: str,
    source_extension: str,
    type_tag: str,
    required_flags: tuple[FeatureFlag, ...],
    spec: ImplementationSpec,
) -> ImplementationCandidate:
    emitted_primitive_name = variant.primitive_name
    source_primitive_name = variant.primitive_name
    candidate_id = _candidate_id(
        variant=variant,
        backend=plan.request.backend,
        target_extension=target_extension,
        source_extension=source_extension,
        type_tag=type_tag,
        required_flags=required_flags,
        spec=spec,
    )
    return ImplementationCandidate(
        candidate_id=candidate_id,
        variant=variant,
        emitted_primitive_name=emitted_primitive_name,
        source_primitive_name=source_primitive_name,
        template_name=variant.template_name,
        backend=plan.request.backend,
        target_extension=target_extension,
        source_extension=source_extension,
        type_tag=type_tag,
        required_flags=required_flags,
        implementation=spec,
    )


def _candidate_id(
    *,
    variant: PrimitiveVariant,
    backend: str | None,
    target_extension: str,
    source_extension: str,
    type_tag: str,
    required_flags: tuple[FeatureFlag, ...],
    spec: ImplementationSpec,
) -> str:
    flags = "+".join(flag.name for flag in required_flags) or "none"
    backend_name = backend if backend is not None else "any"
    return (
        f"{variant.variant_id}|backend={backend_name}|target={target_extension}"
        f"|source={source_extension}|type={type_tag}|flags={flags}"
        f"|impl={spec.extension_selector.raw}/{spec.type_selector.raw}"
        f"/{spec.body.kind}"
    )


def _source_extensions_by_target(
    catalog: Catalog,
    selector_names: tuple[str, ...],
    allowed_extensions: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    selector_set = frozenset(selector_names)
    pairs: list[tuple[str, str]] = []
    for target_extension in allowed_extensions:
        for source_extension in _extension_fallback_chain(catalog, target_extension):
            if source_extension in selector_set:
                pairs.append((target_extension, source_extension))
                break
    return tuple(pairs)


def _extension_fallback_chain(catalog: Catalog, extension_name: str) -> tuple[str, ...]:
    chain: list[str] = []
    seen: set[str] = set()
    current_name: str | None = extension_name
    while current_name is not None and current_name not in seen:
        seen.add(current_name)
        extension = catalog.extensions_by_name.get(current_name)
        if extension is None:
            break
        chain.append(current_name)
        inherited = extension.fields.get("inherits")
        current_name = inherited if isinstance(inherited, str) else None
    return tuple(chain)


def _expand_selector_type_tags(
    catalog: Catalog,
    type_group_names: tuple[str, ...],
) -> tuple[str, ...]:
    tags: list[str] = []
    seen: set[str] = set()
    for type_group_name in type_group_names:
        for type_tag in _expand_type_group(catalog, type_group_name, ()):
            if type_tag not in seen:
                seen.add(type_tag)
                tags.append(type_tag)
    return tuple(tags)


def _expand_type_group(
    catalog: Catalog,
    type_group_name: str,
    stack: tuple[str, ...],
) -> tuple[str, ...]:
    if type_group_name in stack:
        return ()
    type_group = catalog.type_groups_by_name.get(type_group_name)
    if type_group is None:
        return ()

    tags: list[str] = []
    seen: set[str] = set()
    next_stack = (*stack, type_group_name)
    for member in type_group.members:
        member_tags: tuple[str, ...]
        if member == type_group_name:
            member_tags = (member,)
        elif member in catalog.type_groups_by_name:
            member_tags = _expand_type_group(catalog, member, next_stack)
        else:
            member_tags = (member,)
        for member_tag in member_tags:
            if member_tag not in seen:
                seen.add(member_tag)
                tags.append(member_tag)
    return tuple(tags)


def _matching_required_flags(
    catalog: Catalog,
    requirements: tuple[RequirementConstraint, ...],
    *,
    target_extension: str,
    source_extension: str,
    type_tag: str,
) -> tuple[FeatureFlag, ...]:
    flags: set[FeatureFlag] = set()
    for requirement in requirements:
        if not _extension_requirement_matches(
            catalog,
            requirement,
            target_extension=target_extension,
            source_extension=source_extension,
        ):
            continue
        if not _type_requirement_matches(catalog, requirement, type_tag):
            continue
        flags.update(requirement.required_flags)
    return tuple(sorted(flags, key=lambda flag: flag.name))


def _extension_requirement_matches(
    catalog: Catalog,
    requirement: RequirementConstraint,
    *,
    target_extension: str,
    source_extension: str,
) -> bool:
    if not requirement.extension_names:
        return True
    allowed_context = frozenset(
        extension
        for requirement_extension in requirement.extension_names
        for extension in _extension_fallback_chain(catalog, requirement_extension)
    )
    return target_extension in allowed_context or source_extension in allowed_context


def _type_requirement_matches(
    catalog: Catalog,
    requirement: RequirementConstraint,
    type_tag: str,
) -> bool:
    if not requirement.type_group_names:
        return True
    return any(
        type_tag in _expand_type_group(catalog, type_group_name, ())
        for type_group_name in requirement.type_group_names
    )


def _supports_required_flags(
    plan: SelectionPlan,
    required_flags: tuple[FeatureFlag, ...],
) -> bool:
    if not plan.request.cpu_flags:
        return True
    available = frozenset(flag.name for flag in plan.normalized_cpu_flags)
    return frozenset(flag.name for flag in required_flags) <= available


def _supports_backend(
    catalog: Catalog,
    extension_name: str,
    backend: str | None,
) -> bool:
    if backend is None:
        return True

    saw_backend_metadata = False
    for fallback_name in _extension_fallback_chain(catalog, extension_name):
        extension = catalog.extensions_by_name.get(fallback_name)
        if extension is None:
            continue
        backend_fields = _as_map(extension.fields.get(backend))
        if backend_fields is None:
            continue
        saw_backend_metadata = True
        supported = backend_fields.get("supported")
        if supported is False:
            return False
        if supported is True:
            return True
    return not saw_backend_metadata


def _known_backend(catalog: Catalog, backend: str) -> bool:
    return any(
        isinstance(extension.fields.get(backend), FrozenMap)
        for extension in catalog.extensions
    )


def _implementation_plan_key(
    implementation_plan: VariantImplementationPlan,
) -> tuple[str, str, str]:
    return (
        implementation_plan.variant_id,
        implementation_plan.extension_selector.raw,
        implementation_plan.type_selector.raw,
    )


def _selector_items(selector: str) -> tuple[str, ...]:
    stripped = selector.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return ()
        raw_items = tuple(item.strip() for item in inner.split(",") if item.strip())
    else:
        raw_items = (stripped,)
    return tuple(_selector_base_name(item) for item in raw_items)


def _selector_base_name(selector_item: str) -> str:
    if "<" in selector_item and selector_item.endswith(">"):
        return selector_item.split("<", 1)[0]
    return selector_item


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return cast(CatalogMap, value)
    return None
