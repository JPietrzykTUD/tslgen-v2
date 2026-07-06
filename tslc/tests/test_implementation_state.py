from __future__ import annotations

from tslc.catalog.model import Extension, Implementation, Primitive
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS
from tslc.ir.scan import scan
from tslc.ir.segments import Region
from tslc.lower.implementation_state import (
    IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS,
    ImplementationState,
    infer_direct_implementation_state,
)
from tslc.select.selector import SelectedImplementation


def test_direct_state_classifies_intrinsic_call_composition_and_fallback() -> None:
    assert _state("native", "complete(intrin<add, build>(left, right));") is (
        ImplementationState.NATIVE
    )
    assert _state(
        "native",
        "complete(call<primitive=mov>(call<primitive=add>(left, right)));",
    ) is ImplementationState.COMPOSED
    assert _state(
        "native",
        "loop<backend>(i, 0, value(vector::length), 1) { complete(data); }",
    ) is ImplementationState.FALLBACK
    assert _state("scalar", "complete(op<add>(left, right));") is (
        ImplementationState.FALLBACK
    )
    assert _state("native", "complete(left + right);") is ImplementationState.UNKNOWN


def test_classifier_covers_registered_tsil_keywords() -> None:
    assert IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS == TSIL_REGION_KEYWORDS


def test_direct_state_fails_closed_for_unclassified_regions() -> None:
    intrinsic = Region(
        keyword="intrin",
        selector_text="add, build",
        body=(),
        full_text="intrin<add, build>()",
    )
    future_region = Region(
        keyword="future",
        selector_text="",
        body=(intrinsic,),
        full_text="future(intrin<add, build>())",
    )

    assert infer_direct_implementation_state(
        _selected("native", "future(intrin<add, build>());"),
        (future_region,),
    ) is ImplementationState.UNKNOWN


def _state(family: str, body: str) -> ImplementationState:
    return infer_direct_implementation_state(_selected(family, body), scan(body))


def _selected(family: str, body: str) -> SelectedImplementation:
    return SelectedImplementation(
        primitive=Primitive(
            name="id",
            signature="v := v",
            parameters=("data",),
            attribute_keys=(),
            implementations=(),
        ),
        implementation=Implementation(
            selector_path=("native", "ints"),
            extension="native",
            type_group="ints",
            body_text=body,
        ),
        extension=Extension(
            name=family,
            isa_name=family,
            family=family,
            compose_prefix={},
            compose_suffix_by_type={},
        ),
        type_tag="si32",
    )
