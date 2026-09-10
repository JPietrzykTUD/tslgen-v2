"""Backend helper manifests are the shared source of selection and render needs."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from tslc.backend.algorithm_surface import AlgorithmSemanticFamily
from tslc.backend.cpp_algorithm import cpp_unavailable_algorithm_helper_declaration
from tslc.backend.cpp_algorithm_plan import plan_cpp_algorithm_admission
from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    CPP_HELPER_MANIFEST,
    HelperFeature,
    PrimitiveRequirement,
)


@dataclass(frozen=True)
class _Specialization:
    source_primitive_name: str
    mask_policy: str | None = None


class _Catalog:
    def __init__(self, names: set[str]) -> None:
        self.names = names

    def primitives_named(self, name: str, *, unmasked: bool) -> tuple[str, ...]:
        del unmasked
        return (name,) if name in self.names else ()


class _EmittedProfile:
    def __init__(
        self,
        name: str,
        specializations: dict[str, tuple[_Specialization, ...]],
    ) -> None:
        self.profile = SimpleNamespace(name=name)
        self._specializations = specializations

    def specializations(
        self, backend_id: str
    ) -> dict[str, tuple[_Specialization, ...]]:
        assert backend_id == "cpp"
        return self._specializations


def test_manifest_matches_source_identity_not_emitted_name() -> None:
    by_emitted_name = {
        "backend_specific_masked_store": (
            _Specialization("store", "pass_through"),
        )
    }

    assert CPP_HELPER_MANIFEST.supports(  # type: ignore[arg-type]
        "masked_write",
        {
            **by_emitted_name,
        },
    )


def test_mask_policy_is_an_explicit_helper_requirement() -> None:
    missing = CPP_HELPER_MANIFEST.missing_requirements(  # type: ignore[arg-type]
        "masked_write",
        {
            "load": (_Specialization("load"),),
            "store": (_Specialization("store"),),
        },
    )

    assert PrimitiveRequirement("store", "pass_through") in missing


def test_new_manifest_requirement_automatically_becomes_a_closure_root() -> None:
    manifest = BackendHelperManifest(
        "fake",
        (
            HelperFeature(
                "helper",
                (
                    PrimitiveRequirement("load"),
                    PrimitiveRequirement("new_helper_primitive"),
                    PrimitiveRequirement("load", "zero"),
                ),
            ),
        ),
    )

    assert manifest.source_primitives == ("load", "new_helper_primitive")
    assert manifest.closure_seed_primitives(  # type: ignore[arg-type]
        _Catalog({"load", "new_helper_primitive"})
    ) == ("load", "new_helper_primitive")


def test_every_cpp_algorithm_helper_has_a_partial_profile_lookup_declaration() -> None:
    requirements = tuple(
        dict.fromkeys(
            requirement
            for feature in CPP_HELPER_MANIFEST.features
            for requirement in feature.requirements
        )
    )

    declarations = tuple(
        cpp_unavailable_algorithm_helper_declaration(requirement)
        for requirement in requirements
    )

    assert len(declarations) == len(requirements)
    assert all(declaration.endswith("= delete;") for declaration in declarations)


def test_cpp_algorithm_admission_is_granular_around_compaction() -> None:
    requirement_specs = (
        _Specialization(requirement.source_name, requirement.mask_policy)
        for feature in CPP_HELPER_MANIFEST.features
        for requirement in feature.requirements
        if requirement.source_name != "compress_store"
    )
    grouped: dict[str, list[_Specialization]] = {}
    for specialization in requirement_specs:
        grouped.setdefault(specialization.source_primitive_name, []).append(
            specialization
        )
    specializations = {
        name: tuple(group) for name, group in grouped.items()
    }
    profile = _EmittedProfile("synthetic", specializations)

    plan = plan_cpp_algorithm_admission((profile,))  # type: ignore[arg-type]

    assert plan.supported
    assert tuple(
        header.semantic_family for header in plan.family_headers
    ) == (
        AlgorithmSemanticFamily.UTILITY,
        AlgorithmSemanticFamily.ITERATION,
        AlgorithmSemanticFamily.PREDICATE,
        AlgorithmSemanticFamily.COUNT,
    )
    assert plan.remaining_semantic_families == (
        AlgorithmSemanticFamily.SELECT,
        AlgorithmSemanticFamily.TRANSFORM,
        AlgorithmSemanticFamily.CONSUME,
        AlgorithmSemanticFamily.AGGREGATE,
    )
    assert "transform_unary" in plan.admitted_family_names
    assert "predicate_unary" in plan.admitted_family_names
    absent = {
        family
        for family in (
            "select_unary",
            "select_binary",
            "select_masked_unary",
            "select_masked_binary",
            "select_indices_unary",
            "select_indices_binary",
            "select_masked_indices_unary",
            "select_masked_indices_binary",
            "select_selected_indices_unary",
            "select_selected_indices_binary",
        )
        if family not in plan.admitted_family_names
    }
    assert absent == {
        "select_unary",
        "select_binary",
        "select_masked_unary",
        "select_masked_binary",
    }
    compaction_gaps = tuple(
        gap for gap in plan.gaps if gap.feature_name == "compaction"
    )
    assert {
        (gap.backend_id, gap.profile_name, gap.family_name, gap.requirement)
        for gap in compaction_gaps
    } == {
        (
            "cpp",
            "synthetic",
            family_name,
            PrimitiveRequirement("compress_store"),
        )
        for family_name in absent
    }

    specializations["compress_store"] = (_Specialization("compress_store"),)
    completed = plan_cpp_algorithm_admission(
        (_EmittedProfile("synthetic", specializations),)  # type: ignore[arg-type]
    )
    assert set(absent) <= set(completed.admitted_family_names)
