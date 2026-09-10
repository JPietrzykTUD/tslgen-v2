"""Format C++ compatibility declarations for partially admitted algorithms."""

from __future__ import annotations

from tslc.backend.helper_requirements import PrimitiveRequirement
from tslc.catalog.model import PrimitiveMaskMode


def cpp_unavailable_algorithm_helper_declaration(
    requirement: PrimitiveRequirement,
) -> str:
    """A deleted lookup target for a helper called only by rejected forms."""

    key = (requirement.source_name, requirement.mask_policy)
    declarations = {
        ("load", None): (
            "template <class Vec, bool Aligned>\n"
            "inline typename Vec::register_type load(\n"
            "    typename Vec::base_type const*) = delete;"
        ),
        ("store", None): (
            "template <class Vec, bool Aligned>\n"
            "inline void store(typename Vec::base_type*, "
            "typename Vec::register_type) = delete;"
        ),
        ("store", PrimitiveMaskMode.PASS_THROUGH): (
            "template <class Vec, bool Aligned>\n"
            "inline void store_mask(typename Vec::mask_type, "
            "typename Vec::base_type*, typename Vec::register_type) = delete;"
        ),
        ("to_integral", None): (
            "template <class Vec>\n"
            "inline typename Vec::imask_type to_integral("
            "typename Vec::mask_type) = delete;"
        ),
        ("to_mask", None): (
            "template <class Vec>\n"
            "inline typename Vec::mask_type to_mask("
            "typename Vec::imask_type) = delete;"
        ),
        ("gather_narrow", None): (
            "template <class Vec, class IndexVec, std::size_t Scale>\n"
            "inline typename Vec::register_type gather_narrow(\n"
            "    typename Vec::base_type const*, "
            "typename IndexVec::base_type const*) = delete;"
        ),
        ("compress_store", None): (
            "template <class Vec, bool Aligned>\n"
            "inline void compress_store(typename Vec::mask_type, "
            "typename Vec::base_type*, typename Vec::register_type) = delete;"
        ),
        ("mask_population_count", None): (
            "template <class Vec>\n"
            "inline std::size_t mask_population_count("
            "typename Vec::mask_type) = delete;"
        ),
        ("mask_binary_and", None): (
            "template <class Vec>\n"
            "inline typename Vec::mask_type mask_binary_and("
            "typename Vec::mask_type, typename Vec::mask_type) = delete;"
        ),
    }
    try:
        return declarations[key]
    except KeyError as exc:
        raise ValueError(
            f"no C++ unavailable-helper declaration for {key!r}"
        ) from exc


__all__ = ("cpp_unavailable_algorithm_helper_declaration",)
