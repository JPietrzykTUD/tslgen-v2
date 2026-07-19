"""Registry of supported value-test case kinds and their typed requirements."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from tslc.value_tests.case_components import (
    ValueTestCaseCapability,
    ValueTestCaseRequirements,
    ValueTestFact,
)

_RESULT = frozenset({ValueTestFact.RESULT_KIND})
_SCALABLE_VALUE_FACTS = frozenset(
    {
        ValueTestFact.RESULT_KIND,
        ValueTestFact.SCALABLE_RUNTIME,
        ValueTestFact.SCALABLE_VALUE_HARNESS,
    }
)
_SCALABLE_MASK_FACTS = frozenset(
    {
        ValueTestFact.RESULT_KIND,
        ValueTestFact.SCALABLE_RUNTIME,
        ValueTestFact.SCALABLE_MASK_CHECK,
    }
)
_CONVERSION_TARGET_FACTS = frozenset(
    {ValueTestFact.TARGET_LAYOUT, ValueTestFact.TARGET_LANES}
)
_DIFFERENTIAL_FACTS = frozenset(
    {ValueTestFact.RESULT_KIND, ValueTestFact.DIFFERENTIAL}
)

_CASE_REQUIREMENTS = {
    "array_to_vector": ValueTestCaseRequirements(
        expected="lanes", vector_inputs="one", vector_inputs_match_lanes=True
    ),
    "broadcast": ValueTestCaseRequirements(
        expected="lanes",
        required_facts=frozenset({ValueTestFact.SCALAR_INPUT}),
    ),
    "compile_only": ValueTestCaseRequirements(required_facts=_RESULT),
    "convert": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_facts=_CONVERSION_TARGET_FACTS
        | frozenset({ValueTestFact.INDEX_VALUE}),
    ),
    "differential": ValueTestCaseRequirements(
        vector_inputs="non_empty", required_facts=_DIFFERENTIAL_FACTS
    ),
    "differential_fuzz": ValueTestCaseRequirements(
        required_facts=_DIFFERENTIAL_FACTS, fuzz_case=True
    ),
    "extension_extract": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        required_facts=frozenset(
            {ValueTestFact.REPRESENTATION, ValueTestFact.INDEX_VALUE}
        ),
    ),
    "extension_insert": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="non_empty",
        required_facts=frozenset(
            {ValueTestFact.REPRESENTATION, ValueTestFact.INDEX_VALUE}
        ),
    ),
    "extension_result": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="non_empty",
        required_facts=_CONVERSION_TARGET_FACTS
        | frozenset({ValueTestFact.REPRESENTATION, ValueTestFact.RESULT_KIND}),
        vector_inputs_match_lanes=True,
    ),
    "generic_golden": ValueTestCaseRequirements(
        expected="lanes", required_facts=_RESULT, vector_inputs_match_lanes=True
    ),
    "immediate": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        required_facts=frozenset({ValueTestFact.IMMEDIATE}),
        vector_inputs_match_lanes=True,
    ),
    "indexed_load": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="non_empty",
        required_facts=frozenset(
            {
                ValueTestFact.IMMEDIATE,
                ValueTestFact.TARGET_LANES,
                ValueTestFact.INDEX_STYLE,
                ValueTestFact.INDEX_LANES,
            }
        ),
    ),
    "indexed_store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="non_empty",
        required_facts=frozenset(
            {
                ValueTestFact.IMMEDIATE,
                ValueTestFact.MEMORY_LENGTH,
                ValueTestFact.INDEX_STYLE,
                ValueTestFact.INDEX_LANES,
            }
        ),
    ),
    "lane_list": ValueTestCaseRequirements(
        expected="lanes", vector_inputs="one", vector_inputs_match_lanes=True
    ),
    "load": ValueTestCaseRequirements(
        expected="lanes", vector_inputs="one", vector_inputs_match_lanes=True
    ),
    "load_convert": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_facts=_CONVERSION_TARGET_FACTS,
    ),
    "mask_logic": ValueTestCaseRequirements(expected="one", mask_inputs="non_empty"),
    "mask_pointer_load": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        required_facts=frozenset({ValueTestFact.MEMORY_LENGTH}),
    ),
    "mask_result": ValueTestCaseRequirements(expected="one"),
    "mask_store": ValueTestCaseRequirements(
        expected="non_empty",
        mask_inputs="one",
        required_facts=frozenset(
            {ValueTestFact.MEMORY_LENGTH, ValueTestFact.MEMORY_STORAGE}
        ),
    ),
    "mask_to_vector": ValueTestCaseRequirements(
        expected="lanes", mask_inputs="one"
    ),
    "masked": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        mask_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "masked_pointer_load": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        mask_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "masked_pointer_store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        mask_inputs="one",
        required_facts=frozenset({ValueTestFact.MEMORY_LENGTH}),
        vector_inputs_match_lanes=True,
    ),
    "memory_copy": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        scalar_inputs="one",
        required_facts=frozenset({ValueTestFact.MEMORY_LENGTH}),
    ),
    "pointer_free": ValueTestCaseRequirements(scalar_inputs="one"),
    "pointer_lifetime": ValueTestCaseRequirements(scalar_inputs="non_empty"),
    "reduction": ValueTestCaseRequirements(
        expected="one", vector_inputs="one", vector_inputs_match_lanes=True
    ),
    "repr_cast": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_facts=_CONVERSION_TARGET_FACTS,
    ),
    "scalar_pointer_load": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        required_facts=frozenset({ValueTestFact.MEMORY_LENGTH}),
    ),
    "scalar_result": ValueTestCaseRequirements(
        expected="one", required_facts=_RESULT
    ),
    "scalar_vector": ValueTestCaseRequirements(expected="lanes"),
    "scalable_golden": ValueTestCaseRequirements(
        expected="lanes", required_facts=_SCALABLE_VALUE_FACTS
    ),
    "scalable_mask_constant": ValueTestCaseRequirements(
        expected="one", required_facts=_SCALABLE_MASK_FACTS
    ),
    "scalable_mask_conversion": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="one",
        required_facts=_SCALABLE_MASK_FACTS
        | frozenset({ValueTestFact.SCALABLE_MASK_INPUTS}),
    ),
    "scalable_mask_logic": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="non_empty",
        required_facts=_SCALABLE_MASK_FACTS
        | frozenset({ValueTestFact.SCALABLE_MASK_INPUTS}),
    ),
    "scalable_mask_result": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        required_facts=_SCALABLE_MASK_FACTS
        | frozenset({ValueTestFact.SCALABLE_LOAD}),
    ),
    "scalable_mask_store": ValueTestCaseRequirements(
        expected="non_empty",
        mask_inputs="one",
        required_facts=frozenset(
            {
                ValueTestFact.TARGET_LAYOUT,
                ValueTestFact.RESULT_KIND,
                ValueTestFact.SCALABLE_RUNTIME,
                ValueTestFact.SCALABLE_MASK_INPUTS,
            }
        ),
    ),
    "scalable_masked": ValueTestCaseRequirements(
        expected="lanes",
        mask_inputs="one",
        required_facts=_SCALABLE_VALUE_FACTS
        | frozenset({ValueTestFact.SCALABLE_MASK_INPUTS}),
    ),
    "scalable_masked_mask_result": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        mask_inputs="one",
        required_facts=_SCALABLE_MASK_FACTS
        | frozenset(
            {ValueTestFact.SCALABLE_LOAD, ValueTestFact.SCALABLE_MASK_INPUTS}
        ),
    ),
    "store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        required_facts=frozenset({ValueTestFact.MEMORY_LENGTH}),
        vector_inputs_match_lanes=True,
    ),
    "target_imask": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="non_empty",
        scalar_inputs="one",
        required_facts=frozenset(
            {
                ValueTestFact.RESULT_KIND,
                ValueTestFact.TARGET_LAYOUT,
                ValueTestFact.TARGET_LANES,
                ValueTestFact.REPRESENTATION_LAYOUT,
            }
        ),
    ),
    "status_pointer": ValueTestCaseRequirements(
        scalar_inputs="one", required_facts=_RESULT
    ),
    "stream": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        scalar_inputs="one",
        required_facts=frozenset({ValueTestFact.TEXT_EXPECTED}),
        vector_inputs_match_lanes=True,
    ),
    "vector_to_array": ValueTestCaseRequirements(
        expected="lanes", vector_inputs="one", vector_inputs_match_lanes=True
    ),
}


def _case_capabilities(
    requirements: Mapping[str, ValueTestCaseRequirements],
) -> tuple[ValueTestCaseCapability, ...]:
    return tuple(
        ValueTestCaseCapability(kind, requirement)
        for kind, requirement in sorted(requirements.items())
    )


def _case_requirements(
    capabilities: tuple[ValueTestCaseCapability, ...],
) -> Mapping[str, ValueTestCaseRequirements]:
    result: dict[str, ValueTestCaseRequirements] = {}
    for capability in capabilities:
        if capability.kind in result:
            raise ValueError(f"duplicate value-test case kind {capability.kind!r}")
        result[capability.kind] = capability.requirements
    return MappingProxyType(result)


DEFAULT_VALUE_TEST_CASE_CAPABILITIES = _case_capabilities(_CASE_REQUIREMENTS)
DEFAULT_VALUE_TEST_CASE_KINDS = frozenset(
    capability.kind for capability in DEFAULT_VALUE_TEST_CASE_CAPABILITIES
)
DEFAULT_VALUE_TEST_CASE_REQUIREMENTS = _case_requirements(
    DEFAULT_VALUE_TEST_CASE_CAPABILITIES
)
