"""TSL 1.x public callable-family compatibility ratchet."""

from tslc.maintenance import _repo_context
from tslc.maintenance.public_api_baseline import (
    build_public_api_baseline,
    canonical_baseline_path,
    serialize,
)


def test_public_api_matches_reviewed_v1_baseline() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None

    baseline = build_public_api_baseline(context)

    assert serialize(baseline) == canonical_baseline_path(context).read_text(
        encoding="utf-8"
    )
    assert baseline["cpp_core_identities"]
    assert baseline["rust_root_identities"]
    assert baseline["algorithm_callable_families"]
    assert baseline["checked_algorithm_contracts"]
    assert baseline["checked_precondition_contracts"]
    assert baseline["checked_error_contract"] == {
        "cpp_success": "none",
        "failures": [
            {
                "kind": "index_out_of_bounds",
                "cpp": "index_out_of_bounds",
                "rust": "IndexOutOfBounds",
            },
            {
                "kind": "zero_divisor",
                "cpp": "zero_divisor",
                "rust": "ZeroDivisor",
            },
            {
                "kind": "insufficient_extent",
                "cpp": "insufficient_extent",
                "rust": "InsufficientExtent",
            },
            {
                "kind": "insufficient_input",
                "cpp": "insufficient_input",
                "rust": "InsufficientInput",
            },
            {
                "kind": "insufficient_output",
                "cpp": "insufficient_output",
                "rust": "InsufficientOutput",
            },
            {
                "kind": "misaligned",
                "cpp": "misaligned",
                "rust": "Misaligned",
            },
            {
                "kind": "overlapping_ranges",
                "cpp": "overlapping_ranges",
                "rust": "OverlappingRanges",
            },
                {
                    "kind": "address_overflow",
                    "cpp": "address_overflow",
                    "rust": "AddressOverflow",
                },
                {
                    "kind": "lane_count_mismatch",
                    "cpp": "lane_count_mismatch",
                    "rust": "LaneCountMismatch",
                },
        ],
    }
    assert baseline["cpp_checked_algorithm_families"]
    assert baseline["version"] == 3
    exact = baseline["exact_backend_declarations"]
    assert exact["profiles"] == ["scalar", "avx2"]
    assert exact["cpp"]["schema_version"] == 1
    assert exact["rust"]["schema_version"] == 1
    for backend in ("cpp", "rust"):
        declarations = exact[backend]["declarations"]
        assert {item["stability"] for item in declarations} == {
            "stable",
            "unstable",
            "implementation_detail",
        }
        assert not any(
            item["stability"] == "stable" and item["kind"] == "overload_set"
            for item in declarations
        )
    cpp_declarations = exact["cpp"]["declarations"]
    span_data = next(
        item for item in cpp_declarations if item["identity"] == "tsl::span<T>::data"
    )
    assert span_data["qualifiers"] == ["const"]
    assert span_data["noexcept"] is True
    rust_declarations = exact["rust"]["declarations"]
    checked_root = next(
        item
        for item in rust_declarations
        if item["identity"] == "crate::load_masked_checked#v:=(m,cptr,v)"
    )
    assert checked_root["kind"] == "reexport"
    assert checked_root["checked_of"] == "crate::load_masked#v:=(m,cptr,v)"
    primitive_families = baseline["primitive_callable_families"]
    assert isinstance(primitive_families, list)
    gather = next(
        item
        for item in primitive_families
        if isinstance(item, dict)
        and item["name"] == "gather"
        and item["signature"] == "v:=(cptr,vidx,sImm)"
    )
    assert gather["parameters"] == ["base_ptr", "index", "scale"]
    assert gather["memory"]["indexed_lane_extent"] == "vector"
    assert gather["generic_parameters"][0]["name"] == "IndicesType"
    assert gather["preconditions"][0]["kind"] == "indexed_memory_address_valid"
