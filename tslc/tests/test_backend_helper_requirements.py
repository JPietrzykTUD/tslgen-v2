"""Backend helper manifests are the shared source of selection and render needs."""

from __future__ import annotations

from dataclasses import dataclass

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


def test_manifest_matches_source_identity_not_emitted_name() -> None:
    by_emitted_name = {
        "backend_specific_masked_store": (
            _Specialization("store", "pass_through"),
        )
    }

    assert CPP_HELPER_MANIFEST.supports(  # type: ignore[arg-type]
        "algorithm",
        {
            **by_emitted_name,
            "load": (_Specialization("load"),),
            "store": (_Specialization("store"),),
            "to_integral": (_Specialization("to_integral"),),
            "to_mask": (_Specialization("to_mask"),),
            "gather_narrow": (_Specialization("gather_narrow"),),
            "compress_store": (_Specialization("compress_store"),),
            "mask_population_count": (_Specialization("mask_population_count"),),
            "mask_binary_and": (_Specialization("mask_binary_and"),),
        },
    )


def test_mask_policy_is_an_explicit_helper_requirement() -> None:
    missing = CPP_HELPER_MANIFEST.missing_requirements(  # type: ignore[arg-type]
        "algorithm",
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
