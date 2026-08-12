from __future__ import annotations

from types import SimpleNamespace

from tslc.catalog.model import (
    Extension,
    ImaskPolicy,
    Implementation,
    MaskPolicy,
    Primitive,
)
from tslc.catalog.signatures import parse_signature
from tslc.catalog.target_families import ExtensionFamilyCapability
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS
from tslc.ir.region_syntax import segments_text
from tslc.ir.scan import scan
from tslc.ir.segments import Region
from tslc.lower.body_rendering import body_context, render_body
from tslc.lower.context import LoweringEnv, LoweringScope, LoweringSession
from tslc.lower.implementation_state import (
    IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS,
    ImplementationState,
    infer_direct_implementation_state,
)
from tslc.lower.region_handlers.control import IfLowerer, LoopLowerer, SwitchLowerer
from tslc.target_text import literal_text, render_sequence, render_text
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
    assert _state("native", "complete(data);") is ImplementationState.NATIVE
    assert _state("native", "complete(left + right);") is ImplementationState.UNKNOWN


def test_direct_state_recognizes_only_the_canonical_parameter_return() -> None:
    assert _state("native", "complete(data);") is ImplementationState.NATIVE
    assert _state("native", "complete(result);") is ImplementationState.UNKNOWN
    assert _state("native", "complete((data));") is ImplementationState.UNKNOWN
    assert (
        _state("native", "complete(/* identity */ data);")
        is ImplementationState.UNKNOWN
    )


def test_direct_state_classifies_mask_vector_identity_from_extension_policy() -> None:
    lane_bitmask = _selected(
        "native",
        "complete(mask);",
        signature="v := m",
        parameters=("mask",),
        mask_policy=MaskPolicy(kind="lane_bitmask"),
    )
    exact_lane_bitmask = _selected(
        "native",
        "complete(mask);",
        signature="v := m",
        parameters=("mask",),
        mask_policy=MaskPolicy(kind="exact_lane_bitmask"),
    )
    native_predicate = _selected(
        "native",
        "complete(mask);",
        signature="v := m",
        parameters=("mask",),
        mask_policy=MaskPolicy(kind="native_predicate"),
    )

    assert infer_direct_implementation_state(
        lane_bitmask,
        scan(lane_bitmask.implementation.body_text),
    ) is ImplementationState.NATIVE
    assert infer_direct_implementation_state(
        exact_lane_bitmask,
        scan(exact_lane_bitmask.implementation.body_text),
    ) is ImplementationState.UNKNOWN
    assert infer_direct_implementation_state(
        native_predicate,
        scan(native_predicate.implementation.body_text),
    ) is ImplementationState.UNKNOWN


def test_direct_state_classifies_mask_imask_identity_from_extension_policy() -> None:
    same_as_mask = _selected(
        "native",
        "complete(mask);",
        signature="im := m",
        parameters=("mask",),
        imask_policy=ImaskPolicy(kind="same_as_mask_type"),
    )
    lane_bitmask = _selected(
        "native",
        "complete(mask);",
        signature="im := m",
        parameters=("mask",),
        imask_policy=ImaskPolicy(kind="lane_bitmask"),
    )

    assert infer_direct_implementation_state(
        same_as_mask,
        scan(same_as_mask.implementation.body_text),
    ) is ImplementationState.NATIVE
    assert infer_direct_implementation_state(
        lane_bitmask,
        scan(lane_bitmask.implementation.body_text),
    ) is ImplementationState.UNKNOWN


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


def test_rendered_state_ignores_untaken_generation_branch() -> None:
    selected = _selected(
        "native",
        """
        complete(
          if<generation>(type::is_same(type(base::in), si32)) {
            intrin<add, build>(data)
          } else<generation> {
            loop<backend>(i, 0, 4, 1) { complete(data); }
          }
        );
        """,
    )

    result = _render_state(selected)

    assert result is ImplementationState.NATIVE


def test_rendered_state_ignores_unselected_literal_switch_arm() -> None:
    selected = _selected(
        "native",
        """
        complete(
          switch<compile>(1) {
            1 => { intrin<add, build>(data); }
            _ => { loop<backend>(i, 0, 4, 1) { complete(data); } }
          }
        );
        """,
    )

    result = _render_state(selected)

    assert result is ImplementationState.NATIVE


def test_loop_selector_classification_and_lowering_share_one_parse() -> None:
    body = "loop< generation ,   scoped >(i, 0, 2, 1) { complete(data); }"
    region = scan(body)[0]
    assert isinstance(region, Region)

    # State classification reads the odd-whitespace selector as a generation
    # loop: composition, not a backend-loop fallback.
    assert _state("native", body) is ImplementationState.COMPOSED

    # Lowering tokenizes the same selector through the same parser and expands
    # the loop instead of skipping it as unsupported.
    selected = _selected("native", body)
    context = LoweringSession(
        env=LoweringEnv(
            catalog=SimpleNamespace(),
            backend=SimpleNamespace(),
            extension=selected.extension,
            type_tag=selected.type_tag,
        )
    )
    rendered = LoopLowerer().lower(
        region, context, lambda segments: literal_text(segments_text(segments))
    )

    assert not context.effects.diagnostics
    assert render_text(rendered).count("complete(data)") == 2


def test_rendered_state_classifies_direct_identity_return() -> None:
    selected = _selected("native", "complete(data);")

    assert _render_state(selected) is ImplementationState.NATIVE


def test_rendered_state_classifies_direct_mask_vector_identity() -> None:
    selected = _selected(
        "native",
        "complete(mask);",
        signature="v := m",
        parameters=("mask",),
        mask_policy=MaskPolicy(kind="lane_bitmask"),
    )

    assert _render_state(selected) is ImplementationState.NATIVE


def _state(family: str, body: str) -> ImplementationState:
    return infer_direct_implementation_state(_selected(family, body), scan(body))


def _render_state(selected: SelectedImplementation) -> ImplementationState:
    shape = parse_signature(selected.primitive.signature)
    assert shape is not None
    backend = SimpleNamespace(backend_id="cpp", syntax=_FakeSyntax())
    context = body_context(
        LoweringEnv(
            catalog=SimpleNamespace(),
            backend=backend,
            extension=selected.extension,
            type_tag=selected.type_tag,
        ),
        LoweringScope(),
        shape,
        SimpleNamespace(requires_unsafe_frame=lambda shape: False),
    )
    result = render_body(
        selected=selected,
        shape=shape,
        context=context,
        segments=scan(selected.implementation.body_text),
        region_lowerers=(
            _CompleteLowerer(),
            IfLowerer(),
            SwitchLowerer(),
            _IntrinsicLowerer(),
            _LoopLowerer(),
        ),
    )
    assert result.rendered is not None
    return result.implementation_state


def _selected(
    family: str,
    body: str,
    *,
    signature: str = "v := v",
    parameters: tuple[str, ...] = ("data",),
    mask_policy: MaskPolicy | None = None,
    imask_policy: ImaskPolicy | None = None,
) -> SelectedImplementation:
    return SelectedImplementation(
        primitive=Primitive(
            name="id",
            signature=signature,
            parameters=parameters,
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
            mask_policy=mask_policy or MaskPolicy(),
            imask_policy=imask_policy or ImaskPolicy(),
        ),
        type_tag="si32",
        extension_family_capability=ExtensionFamilyCapability(
            family,
            implementation_fallback=family == "scalar",
        ),
    )


class _CompleteLowerer:
    keyword = "complete"

    def lower(self, region, context, render):
        return render(region.body)


class _IntrinsicLowerer:
    keyword = "intrin"

    def lower(self, region, context, render):
        return "native(data)"


class _LoopLowerer:
    keyword = "loop"

    def lower(self, region, context, render):
        return "for (...) { fallback(data); }"


class _FakeSyntax:
    def render_compile_switch(self, selector, arms):
        return render_sequence(tuple(body for _label, body in arms))
