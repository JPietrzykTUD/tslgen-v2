"""Reviewed policy and semantic-family data for the checked-API census."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Classification = Literal[
    "semantic guarantee",
    "static well-formedness constraint",
    "dynamic precondition",
    "implementation hazard",
    "tooling-only validation",
]

BASELINE_VERSION = 5
DECLARATION_ROOT = Path("tslc/tests/fixtures/checked_api")
CPP_DECLARATIONS = DECLARATION_ROOT / "cpp_declarations.snap"
RUST_DECLARATIONS = DECLARATION_ROOT / "rust_declarations.snap"

POLICY = {
    "checked_suffix": "_checked",
    "eligibility": (
        "catastrophic dynamic caller precondition; complete pre-side-effect check "
        "must be expressible from the checked signature"
    ),
    "cpp_value_result": "direct value return plus final precondition_error& output",
    "cpp_void_result": "nodiscard precondition_error return",
    "rust_value_result": "Result<T, PreconditionError>",
    "rust_void_result": "Result<(), PreconditionError>",
    "unchecked_rust": "unsafe fn when violating the caller contract can cause UB",
    "failure_value": (
        "initialized backend-owned placeholder with no TSL-defined value; the "
        "ordinary operation is not invoked"
    ),
}

ABI_EVIDENCE = {
    "environment": "x86-64 System V",
    "gcc": "GCC 15.2.0",
    "clang": "Clang 21.1.8",
    "msvc": "not available in the original Linux ABI-probe environment",
    "raw_return": "value returned in ymm0; no value-result memory output",
    "chosen_return": "value returned in ymm0; scalar error written through rdi",
    "aggregate_return": "hidden result pointer in rdi; vector value written to memory",
    "status_with_value_output": "status returned in eax; vector value written through rdi",
    "optimized_inline_call": "immediately consumed vector result did not materialize on the stack",
}

VALIDATION_LIMITS = {
    "all_profile_rust_render": (
        "not a valid census input: the current all-profile Rust request reports "
        "TSL-BACKEND-RUST-AMBIGUOUS-TARGET-PROFILES before artifact rendering"
    ),
    "census_strategy": (
        "scan canonical source bodies, render assets, and emitters; obtain public "
        "caller-safety identities from the validated typed catalog"
    ),
}


@dataclass(frozen=True, slots=True)
class SemanticFamily:
    family_id: str
    classification: Classification
    backend_consequence: str
    checked_feasibility: str
    review: str


FAMILIES = (
    SemanticFamily(
        "tooling_only",
        "tooling-only validation",
        "Failure is confined to generated tests, builds, documentation stubs, or benchmarks.",
        "not applicable",
        "It is not part of a generated runtime API contract.",
    ),
    SemanticFamily(
        "static_representation_or_lane_shape",
        "static well-formedness constraint",
        "C++ or Rust currently diagnoses an impossible compiler-selected representation at runtime.",
        "no checked twin; validate statically",
        "Sizes, lane counts, and mask-storage capacity are compiler-owned specialization facts.",
    ),
    SemanticFamily(
        "static_immediate_nonzero",
        "static well-formedness constraint",
        "Rust emits a const assertion; invalid authored immediates do not reach a call.",
        "no checked twin; keep a compile-time diagnostic",
        "The operand is an immediate rather than caller-controlled runtime data.",
    ),
    SemanticFamily(
        "static_immediate_range",
        "static well-formedness constraint",
        "C++ and Rust emit a compile-time assertion for an invalid conversion chunk index.",
        "no checked twin; keep a compile-time diagnostic",
        "The source-authored valid range is resolved from the selected source and target base widths.",
    ),
    SemanticFamily(
        "integer_zero_divisor",
        "dynamic precondition",
        "Unchecked C++ and unsafe Rust assume nonzero active integer divisors; checked companions report a typed zero-divisor error before invocation.",
        "implemented for runtime integer division/remainder; checks active divisor lanes",
        "Floating-point zero remains valid, static immediates remain compile-time constraints, and masked forms inspect active lanes only.",
    ),
    SemanticFamily(
        "lane_index",
        "dynamic precondition",
        "Rust facade calls panic today; an unchecked C++ or Rust primitive may access outside its logical lanes.",
        "complete from the runtime index and typed logical lane count",
        "Total operations such as test_imask remain excluded when out-of-range has defined semantics.",
    ),
    SemanticFamily(
        "contiguous_extent",
        "dynamic precondition",
        "Rust slice facades panic when a contiguous input or output is too short.",
        "complete with a valid slice/span signature; not honest for a bare pointer",
        "The checked signature must establish an addressable extent.",
    ),
    SemanticFamily(
        "algorithm_equal_extents",
        "dynamic precondition",
        "Unchecked C++ and unsafe Rust algorithms assume that every secondary range covers the driving extent; checked companions report insufficient input.",
        "implemented from the checked algorithm's range or slice arguments",
        "Every secondary extent is compared before dispatch or output writes.",
    ),
    SemanticFamily(
        "algorithm_output_capacity",
        "dynamic precondition",
        "Unchecked C++ and unsafe Rust algorithms assume sufficient output/index capacity; checked companions report insufficient output.",
        "implemented from the checked algorithm's input and output ranges",
        "Capacity is checked before the raw kernel performs a write.",
    ),
    SemanticFamily(
        "algorithm_mask_capacity",
        "dynamic precondition",
        "Unchecked C++ and unsafe Rust algorithms assume sufficient mask storage; checked companions report insufficient input or output.",
        "implemented from the input extent, mask layout, lane count, and mask range",
        "The typed algorithm contract owns the storage relation.",
    ),
    SemanticFamily(
        "algorithm_selected_index",
        "dynamic precondition",
        "Unchecked C++ and unsafe Rust selected-row algorithms assume valid scaled addresses; checked companions report overflow, misalignment, or an out-of-bounds index.",
        "implemented by validating every selected address before kernel dispatch",
        "The check uses a valid index range, input extent, and compile-time byte scale.",
    ),
    SemanticFamily(
        "implementation_exhaustiveness",
        "implementation hazard",
        "Rust panics if compiler-selected scalar cast types escape the supported closed set.",
        "no checked twin; repair typed validation/exhaustiveness",
        "This is a compiler/backend defect if reachable, not invalid caller data.",
    ),
    SemanticFamily(
        "implementation_invariant",
        "implementation hazard",
        "A debug assertion or unwrap fails if an internal compiler-owned invariant is broken.",
        "no checked twin; retain or replace with compiler validation",
        "The condition is not part of the public call domain.",
    ),
    SemanticFamily(
        "contiguous_memory_contract",
        "dynamic precondition",
        "Raw C++ pointers remain unchecked; Rust public exposure must be unsafe until a safe slice wrapper discharges the contract.",
        "implemented for scalar/vector loads and stores from a span/slice carrying the exact readable or writable extent and selected alignment",
        "The checked view establishes the represented range; constructing an invalid C++ span still violates its documented object invariant.",
    ),
    SemanticFamily(
        "mask_memory_contract",
        "dynamic precondition",
        "Raw mask representation loads/stores have the same pointer hazard plus layout-dependent capacity.",
        "no honest twin until a new typed mask-storage layout contract projects exact capacity into span/slice signatures",
        "Packed, register-lane, axis-selected, and scalable mask representations do not share one existing element-count rule.",
    ),
    SemanticFamily(
        "selected_memory_contract",
        "dynamic precondition",
        "Expand/compress operations may access a mask-dependent number of elements through a selected aligned or unaligned memory contract.",
        "implemented for compress-store and expand-load from a range plus capacity derived from the active mask; selected alignment is checked before nonempty aligned access",
        "Validation must precede any compress-store output write; an all-inactive operation accesses no memory and does not reject an empty unaligned view.",
    ),
    SemanticFamily(
        "indexed_memory_contract",
        "dynamic precondition",
        "Gather/scatter paths may access invalid addresses for active indices.",
        "implemented for vector-index gather/scatter, including partial narrow gather, from a valid base view, typed scale, and active-index validation; pointer-indexed narrow gather remains omitted",
        "Pointer-indexed narrow gather requires a second extent-carrying index view before an honest checked twin can be emitted.",
    ),
    SemanticFamily(
        "deallocation_provenance",
        "dynamic precondition",
        "Mismatched, dead, or foreign allocation provenance can cause undefined behavior.",
        "no honest pointer-only checked twin; design an owning allocation API separately",
        "A runtime pointer inspection cannot prove matching live allocation provenance.",
    ),
    SemanticFamily(
        "random_output_contract",
        "dynamic precondition",
        "The random-step intrinsic writes through a raw output pointer on success.",
        "implemented with a mutable one-element-or-larger span/slice and an insufficient-extent result",
        "The checked range establishes writable storage before the hardware-random operation is invoked.",
    ),
    SemanticFamily(
        "raw_copy_contract",
        "dynamic precondition",
        "Invalid ranges or prohibited overlap can cause undefined behavior or corruption.",
        "no honest twin for the current vector-base count ABI; first add byte-capacity source/destination views, a size-domain contract, and an explicit overlap contract",
        "The byte unit is declared, but count and copy kind currently use signed, unsigned, or floating vector-base scalars; pointer-only inputs cannot discharge capacity or overlap obligations.",
    ),
    SemanticFamily(
        "conversion_input_contract",
        "dynamic precondition",
        "Widening loads read multiple source elements through a raw pointer.",
        "implemented with a source span/slice whose minimum element count is the target vector's logical lane count",
        "The typed result-target relationship owns the exact required source extent.",
    ),
)
FAMILY_BY_ID = {family.family_id: family for family in FAMILIES}


__all__ = (
    "ABI_EVIDENCE",
    "BASELINE_VERSION",
    "CPP_DECLARATIONS",
    "FAMILIES",
    "FAMILY_BY_ID",
    "POLICY",
    "RUST_DECLARATIONS",
    "VALIDATION_LIMITS",
    "Classification",
    "SemanticFamily",
)
