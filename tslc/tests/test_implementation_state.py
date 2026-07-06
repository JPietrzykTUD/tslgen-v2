from __future__ import annotations

from tslc.catalog.model import Extension, Implementation, Primitive
from tslc.ir.scan import scan
from tslc.lower.implementation_state import (
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


def _state(family: str, body: str) -> ImplementationState:
    selected = SelectedImplementation(
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
    return infer_direct_implementation_state(selected, scan(body))
