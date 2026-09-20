"""C++ algorithm helper bindings and compatibility declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.backend.helper_requirements import (
    CPP_HELPER_MANIFEST,
    PrimitiveRequirement,
)
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.semantics import ResolvedPrimitiveProvider


class CppAlgorithmHelperForm(StrEnum):
    """Backend-owned callable forms used by C++ algorithm assets."""

    CONTIGUOUS_READ = "contiguous_read"
    CONTIGUOUS_WRITE = "contiguous_write"
    MASKED_WRITE = "masked_write"
    SELECTED_READ = "selected_read"
    INTEGRAL_MASK = "integral_mask"
    MASK_FROM_INTEGRAL = "mask_from_integral"
    COMPACTION = "compaction"
    MASK_POPULATION_COUNT = "mask_population_count"
    MASK_INTERSECTION = "mask_intersection"

    @property
    def requirement(self) -> PrimitiveRequirement:
        requirements = CPP_HELPER_MANIFEST.requirements(self.value)
        if len(requirements) != 1:
            raise ValueError(
                f"C++ algorithm helper form {self.value!r} must bind one requirement"
            )
        return requirements[0]

    @property
    def template_hole(self) -> str:
        return f"algorithm_helper_{self.value}"

    @property
    def unavailable_symbol(self) -> str:
        return f"tslc_unavailable_algorithm_helper_{self.value}"


@dataclass(frozen=True, slots=True)
class CppAlgorithmCallableSignature:
    """One backend-specific helper signature used for deleted lookup targets."""

    template_parameters: tuple[str, ...]
    result_type: str
    parameter_types: tuple[str, ...]
    parameters_on_new_line: bool = False

    def __post_init__(self) -> None:
        if (
            not self.template_parameters
            or not self.result_type
            or not self.parameter_types
            or any(
                not value
                for value in (*self.template_parameters, *self.parameter_types)
            )
        ):
            raise ValueError("C++ algorithm helper signatures must be complete")


@dataclass(frozen=True, slots=True)
class CppAlgorithmHelperBinding:
    """A semantic helper form bound to its source and emitted C++ identities."""

    form: CppAlgorithmHelperForm
    provider: ResolvedPrimitiveProvider | None
    emitted_callable_name: str
    mask_policy: PrimitiveMaskMode | None
    signature: CppAlgorithmCallableSignature

    def __post_init__(self) -> None:
        if not self.emitted_callable_name:
            raise ValueError("C++ algorithm helper bindings require a callable name")
        if self.mask_policy != self.requirement.mask_policy:
            raise ValueError("C++ algorithm helper binding has the wrong mask policy")
        if (
            self.provider is not None
            and self.provider.requirement != self.requirement.provider
        ):
            raise ValueError("C++ algorithm helper binding has a foreign provider")
        if self.signature != _CPP_ALGORITHM_HELPER_SIGNATURES[self.form]:
            raise ValueError("C++ algorithm helper binding has the wrong signature")

    @property
    def requirement(self) -> PrimitiveRequirement:
        return self.form.requirement

    @property
    def template_hole(self) -> str:
        return self.form.template_hole


_CPP_ALGORITHM_HELPER_SIGNATURES: Mapping[
    CppAlgorithmHelperForm, CppAlgorithmCallableSignature
] = MappingProxyType(
    {
        CppAlgorithmHelperForm.CONTIGUOUS_READ: CppAlgorithmCallableSignature(
            ("class Vec", "bool Aligned"),
            "typename Vec::register_type",
            ("typename Vec::base_type const*",),
            parameters_on_new_line=True,
        ),
        CppAlgorithmHelperForm.CONTIGUOUS_WRITE: CppAlgorithmCallableSignature(
            ("class Vec", "bool Aligned"),
            "void",
            ("typename Vec::base_type*", "typename Vec::register_type"),
        ),
        CppAlgorithmHelperForm.MASKED_WRITE: CppAlgorithmCallableSignature(
            ("class Vec", "bool Aligned"),
            "void",
            (
                "typename Vec::mask_type",
                "typename Vec::base_type*",
                "typename Vec::register_type",
            ),
        ),
        CppAlgorithmHelperForm.SELECTED_READ: CppAlgorithmCallableSignature(
            ("class Vec", "class IndexVec", "std::size_t Scale"),
            "typename Vec::register_type",
            (
                "typename Vec::base_type const*",
                "typename IndexVec::base_type const*",
            ),
            parameters_on_new_line=True,
        ),
        CppAlgorithmHelperForm.INTEGRAL_MASK: CppAlgorithmCallableSignature(
            ("class Vec",),
            "typename Vec::imask_type",
            ("typename Vec::mask_type",),
        ),
        CppAlgorithmHelperForm.MASK_FROM_INTEGRAL: CppAlgorithmCallableSignature(
            ("class Vec",),
            "typename Vec::mask_type",
            ("typename Vec::imask_type",),
        ),
        CppAlgorithmHelperForm.COMPACTION: CppAlgorithmCallableSignature(
            ("class Vec", "bool Aligned"),
            "void",
            (
                "typename Vec::mask_type",
                "typename Vec::base_type*",
                "typename Vec::register_type",
            ),
        ),
        CppAlgorithmHelperForm.MASK_POPULATION_COUNT: (
            CppAlgorithmCallableSignature(
                ("class Vec",),
                "std::size_t",
                ("typename Vec::mask_type",),
            )
        ),
        CppAlgorithmHelperForm.MASK_INTERSECTION: CppAlgorithmCallableSignature(
            ("class Vec",),
            "typename Vec::mask_type",
            ("typename Vec::mask_type", "typename Vec::mask_type"),
        ),
    }
)


if tuple(form.value for form in CppAlgorithmHelperForm) != tuple(
    feature.name for feature in CPP_HELPER_MANIFEST.features
):
    raise ValueError("C++ algorithm helper forms must match the helper manifest")


def cpp_algorithm_helper_signature(
    form: CppAlgorithmHelperForm,
) -> CppAlgorithmCallableSignature:
    """Return the exact callable signature for one semantic helper form."""

    return _CPP_ALGORITHM_HELPER_SIGNATURES[form]


def cpp_algorithm_helper_holes(
    bindings: tuple[CppAlgorithmHelperBinding, ...],
) -> Mapping[str, str]:
    """Callable-name holes consumed by the C++ algorithm detail assets."""

    expected = tuple(CppAlgorithmHelperForm)
    actual = tuple(binding.form for binding in bindings)
    if actual != expected:
        raise ValueError("C++ algorithm helper bindings must cover forms in order")
    return MappingProxyType(
        {
            binding.template_hole: binding.emitted_callable_name
            for binding in bindings
        }
    )


def cpp_unavailable_algorithm_helper_declaration(
    binding: CppAlgorithmHelperBinding,
) -> str:
    """A deleted lookup target for a helper called only by rejected forms."""

    signature = binding.signature
    parameters = ", ".join(signature.parameter_types)
    if signature.parameters_on_new_line:
        parameters = f"\n    {parameters}"
    return (
        f"template <{', '.join(signature.template_parameters)}>\n"
        f"inline {signature.result_type} {binding.emitted_callable_name}("
        f"{parameters}) = delete;"
    )


__all__ = (
    "CppAlgorithmCallableSignature",
    "CppAlgorithmHelperBinding",
    "CppAlgorithmHelperForm",
    "cpp_algorithm_helper_holes",
    "cpp_algorithm_helper_signature",
    "cpp_unavailable_algorithm_helper_declaration",
)
