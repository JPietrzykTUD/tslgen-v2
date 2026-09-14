"""Format C++ compatibility declarations for partially admitted algorithms."""

from __future__ import annotations

from tslc.backend.helper_requirements import PrimitiveRequirement
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.semantics import (
    COMPACTED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT,
    MASK_AND_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_POPULATION_COUNT_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
)


def cpp_unavailable_algorithm_helper_declaration(
    requirement: PrimitiveRequirement,
) -> str:
    """A deleted lookup target for a helper called only by rejected forms."""

    declarations = {
        PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT): (
            "template <class Vec, bool Aligned>\n"
            "inline typename Vec::register_type load(\n"
            "    typename Vec::base_type const*) = delete;"
        ),
        PrimitiveRequirement(CONTIGUOUS_VECTOR_STORE_REQUIREMENT): (
            "template <class Vec, bool Aligned>\n"
            "inline void store(typename Vec::base_type*, "
            "typename Vec::register_type) = delete;"
        ),
        PrimitiveRequirement(
            CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
            PrimitiveMaskMode.PASS_THROUGH,
        ): (
            "template <class Vec, bool Aligned>\n"
            "inline void store_mask(typename Vec::mask_type, "
            "typename Vec::base_type*, typename Vec::register_type) = delete;"
        ),
        PrimitiveRequirement(MASK_TO_INTEGRAL_REQUIREMENT): (
            "template <class Vec>\n"
            "inline typename Vec::imask_type to_integral("
            "typename Vec::mask_type) = delete;"
        ),
        PrimitiveRequirement(MASK_FROM_INTEGRAL_REQUIREMENT): (
            "template <class Vec>\n"
            "inline typename Vec::mask_type to_mask("
            "typename Vec::imask_type) = delete;"
        ),
        PrimitiveRequirement(INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT): (
            "template <class Vec, class IndexVec, std::size_t Scale>\n"
            "inline typename Vec::register_type gather_narrow(\n"
            "    typename Vec::base_type const*, "
            "typename IndexVec::base_type const*) = delete;"
        ),
        PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT): (
            "template <class Vec, bool Aligned>\n"
            "inline void compress_store(typename Vec::mask_type, "
            "typename Vec::base_type*, typename Vec::register_type) = delete;"
        ),
        PrimitiveRequirement(MASK_POPULATION_COUNT_REQUIREMENT): (
            "template <class Vec>\n"
            "inline std::size_t mask_population_count("
            "typename Vec::mask_type) = delete;"
        ),
        PrimitiveRequirement(MASK_AND_REQUIREMENT): (
            "template <class Vec>\n"
            "inline typename Vec::mask_type mask_binary_and("
            "typename Vec::mask_type, typename Vec::mask_type) = delete;"
        ),
    }
    try:
        return declarations[requirement]
    except KeyError as exc:
        raise ValueError(
            f"no C++ unavailable-helper declaration for {requirement!r}"
        ) from exc


__all__ = ("cpp_unavailable_algorithm_helper_declaration",)
