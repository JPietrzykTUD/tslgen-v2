"""Typed PIVOT lowering, body construction, and inlining tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from tslc.backend.registry import create_backend_dialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.lower.dependencies import (
    CallDependency,
    GenericVectorReference,
    VectorIdentity,
)
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import SelectedImplementation, Selector
from tslc.target_text import (
    LiteralText,
    LoweredBody,
    RenderSequence,
    TemplateApplication,
    UnsafeBlockText,
    literal_text,
)
from tslc_pivot.body_ir import (
    PivotBody,
    PivotBodyBuildResult,
    PivotCall,
    PivotFixedCall,
    PivotLocal,
    PivotResidualStatementSequence,
    PivotResidualText,
    PivotBodyCategory,
    PivotBodyCensus,
    PivotBodyEntry,
    PivotBodyOrigin,
    pivot_body_census_digest,
    pivot_body_census_location_digest,
)
from tslc_pivot.model import PivotDefinition, PivotLanguage
from tslc_pivot.body_builder import build_pivot_body, synthetic_pivot_body
from tslc_pivot.lowering_capture import (
    CAPTURE_CLOSE,
    CAPTURE_OPEN,
    PivotCapturedCall,
    PivotBodyCapture,
    PivotBodyCaptureScope,
    PivotCapturedResult,
    PivotCaptureNode,
    capture_source_collision,
    pivot_capture_region_lowerers,
)


_SOURCE = SourceSpan(Path("body-pipeline.tsl"), 10, 3, 30, 1)
_DEPENDENCY = CallDependency(
    primitive="add",
    mask_policy=None,
    source=VectorIdentity("si8", "avx2"),
)
_CAPTURE_NAMESPACE = "a" * 24


def _token(kind: str, ordinal: int) -> str:
    return (
        f"{CAPTURE_OPEN}{_CAPTURE_NAMESPACE}:{kind}:{ordinal}"
        f"{CAPTURE_CLOSE}"
    )


def _capture(*nodes: PivotCaptureNode) -> PivotBodyCapture:
    return PivotBodyCapture(
        (),
        tuple(nodes),
        _CAPTURE_NAMESPACE,
    )


def test_body_lowering_retains_nested_calls_local_shadowing_and_result(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    slot = _add_slot(catalog, machine_profiles)
    result, capture = _lower_body(
        catalog,
        slot,
        PivotLanguage.CPP,
        """
        var<infer>(left, call<primitive=add[Vec]>(left, right));
        var<const_infer>(left, call<primitive=add[Vec]>(left, right));
        complete(call<primitive=add[Vec], attrs[mask=zero]>(
          call<primitive=add[Vec]>(left, right), left
        ));
        """,
    )

    body = _body(result)
    assert tuple(binding.authored_name for binding in body.parameters) == (
        "left",
        "right",
    )
    assert tuple(binding.identity.ordinal for binding in body.parameters) == (0, 1)
    assert len(body.statements) == 2
    first, second = body.statements
    assert isinstance(first, PivotLocal)
    assert isinstance(second, PivotLocal)
    assert (first.binding.authored_name, first.binding.identity.ordinal) == ("left", 2)
    assert (second.binding.authored_name, second.binding.identity.ordinal) == ("left", 3)
    assert first.mutable is True
    assert second.mutable is False

    first_call = _only_call(first.initializer.pieces)
    assert first_call.dependency == CallDependency(
        "add", None, VectorIdentity("si8", "avx2")
    )
    assert first_call.attrs == ()
    assert len(first_call.arguments) == 2
    assert first_call.source is not None
    assert first_call.source.path == _SOURCE.path

    outer = _only_call(body.result.value.pieces)
    assert outer.dependency == CallDependency(
        "add", "zero", VectorIdentity("si8", "avx2")
    )
    assert outer.attrs == (("mask", "zero"),)
    assert len(outer.arguments) == 2
    nested = _only_call(outer.arguments[0].pieces)
    assert nested.dependency.primitive == "add"
    assert body.call_count == 4
    assert body.call_depth == 2
    assert body.local_count == 2
    assert body.result.source is not None
    assert body.result.source.path == _SOURCE.path
    assert len(capture.nodes) == 7


def test_raw_assignment_remains_an_ordered_residual_statement_sequence(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    result, _captured = _lower_body(
        catalog,
        _add_slot(catalog, machine_profiles),
        PivotLanguage.CPP,
        """
        var<const_infer>(tmp, left);
        tmp = right;
        complete(tmp);
        """,
    )

    body = _body(result)
    assert len(body.statements) == 2
    assert isinstance(body.statements[0], PivotLocal)
    residual = body.statements[1]
    assert isinstance(residual, PivotResidualStatementSequence)
    assert "tmp = right;" in "".join(
        piece.text for piece in residual.expression.pieces if hasattr(piece, "text")
    )


def test_generation_loop_produces_distinct_typed_call_occurrences(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    result, capture = _lower_body(
        catalog,
        _add_slot(catalog, machine_profiles),
        PivotLanguage.CPP,
        """
        loop<generation>(i, 0, 2, 1) {
          call<primitive=add[Vec]>(left, right);
        }
        complete(left);
        """,
    )

    body = _body(result)
    assert body.call_count == 2
    call_nodes = [node for node in capture.nodes if isinstance(node, PivotCapturedCall)]
    assert len(call_nodes) == 2
    assert call_nodes[0].token != call_nodes[1].token


def test_rust_unsafe_framing_and_template_fields_stay_structural() -> None:
    call = PivotCapturedCall(
        _token("call", 0),
        _DEPENDENCY,
        (),
        (),
        _SOURCE,
    )
    complete = PivotCapturedResult(
        _token("complete", 1),
        TemplateApplication("test", "wrap({value})", {"value": call}),
        _SOURCE,
    )
    capture = _capture(call, complete)
    lowered = LoweredBody(
        content=UnsafeBlockText(complete),
        unsafe_block_renderer=lambda body: f"unsafe {{ {body} }}",
        requires_unsafe=True,
    )

    body = _body(build_pivot_body(PivotLanguage.RUST, lowered, capture, _SOURCE))

    assert body.requires_unsafe is True
    assert body.statements == ()
    assert any(isinstance(piece, PivotCall) for piece in body.result.value.pieces)
    residual = "".join(
        piece.text for piece in body.result.value.pieces if hasattr(piece, "text")
    )
    assert residual == "wrap()"
    assert "unsafe" not in residual


def test_template_validation_stays_fail_closed() -> None:
    missing = PivotCapturedResult(
        _token("complete", 0),
        TemplateApplication("missing", "wrap({value})", {}),
        _SOURCE,
    )
    missing_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(missing),
        _capture(missing),
        _SOURCE,
    )
    assert _unsupported_code(missing_result) == (
        "TSL-PIVOT-BODY-MALFORMED-TEMPLATE"
    )

    unresolved = PivotCapturedResult(
        _token("complete", 0),
        TemplateApplication("unresolved", "{value}", {"value": "{other}"}),
        _SOURCE,
    )
    unresolved_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(unresolved),
        _capture(unresolved),
        _SOURCE,
    )
    assert _unsupported_code(unresolved_result) == (
        "TSL-PIVOT-BODY-MALFORMED-TEMPLATE"
    )

    class FutureRenderText:
        def render(self, context: object | None = None) -> str:
            del context
            raise RuntimeError("an unknown render value must not be invoked")

    unknown = PivotCapturedResult(
        _token("complete", 0),
        TemplateApplication(
            "unknown", "wrap({value})", {"value": FutureRenderText()}
        ),
        _SOURCE,
    )
    unknown_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(unknown),
        _capture(unknown),
        _SOURCE,
    )
    assert _unsupported_code(unknown_result) == (
        "TSL-PIVOT-BODY-UNKNOWN-RENDER-TEXT"
    )

    used_only = PivotCapturedResult(
        _token("complete", 0),
        TemplateApplication(
            "unused",
            "{value}",
            {
                "value": "safe",
                "unused": UnsafeBlockText(literal_text("not rendered")),
            },
        ),
        _SOURCE,
    )
    used_only_body = _body(
        build_pivot_body(
            PivotLanguage.RUST,
            LoweredBody.from_render_text(used_only),
            _capture(used_only),
            _SOURCE,
        )
    )
    assert used_only_body.requires_unsafe is False


def test_synthetic_fixed_wrapper_is_an_explicit_typed_call() -> None:
    result = synthetic_pivot_body(
        PivotLanguage.CPP,
        ("left", "right"),
        "add",
        "__m128i",
        _SOURCE,
    )

    body = _body(result)
    assert body.statements == ()
    assert body.call_count == 1
    assert len(body.result.value.pieces) == 1
    call = body.result.value.pieces[0]
    assert isinstance(call, PivotFixedCall)
    assert (call.callable_name, call.vector_type) == ("add", "__m128i")
    argument_texts = []
    for argument in call.arguments:
        piece = argument.pieces[0]
        assert isinstance(piece, PivotResidualText)
        argument_texts.append(piece.text)
    assert tuple(argument_texts) == ("left", "right")


def test_body_semantic_digest_ignores_source_paths_and_spans(
    tmp_path: Path,
) -> None:
    left_root = tmp_path / "checkout-a"
    right_root = tmp_path / "checkout-b"
    left = _fixed_census(left_root, Path("sources/demo.tsl"))
    right = _fixed_census(right_root, Path("sources/demo.tsl"))
    moved = _fixed_census(right_root, Path("sources/moved.tsl"))
    shifted = _fixed_census(right_root, Path("sources/demo.tsl"), line=20)
    changed = _fixed_census(
        right_root,
        Path("sources/demo.tsl"),
        callable_name="other",
    )

    left_digest = pivot_body_census_digest((left,))

    assert pivot_body_census_digest((right,)) == left_digest
    assert pivot_body_census_digest((moved,)) == left_digest
    assert pivot_body_census_digest((shifted,)) == left_digest
    assert pivot_body_census_digest((changed,)) != left_digest


def test_body_location_digest_normalizes_roots_but_retains_locations(
    tmp_path: Path,
) -> None:
    left_root = tmp_path / "checkout-a"
    right_root = tmp_path / "checkout-b"
    left = _fixed_census(left_root, Path("sources/demo.tsl"))
    right = _fixed_census(right_root, Path("sources/demo.tsl"))
    moved = _fixed_census(right_root, Path("sources/moved.tsl"))
    shifted = _fixed_census(right_root, Path("sources/demo.tsl"), line=20)

    left_digest = pivot_body_census_location_digest(
        (left,), source_root=left_root
    )
    right_digest = pivot_body_census_location_digest(
        (right,), source_root=right_root
    )

    assert left_digest == right_digest
    assert pivot_body_census_location_digest(
        (moved,), source_root=right_root
    ) != right_digest
    assert pivot_body_census_location_digest(
        (shifted,), source_root=right_root
    ) != right_digest


def test_body_call_retains_compiler_caller_unsafe_fact(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    result, _captured = _lower_body(
        catalog,
        _add_slot(catalog, machine_profiles),
        PivotLanguage.RUST,
        "complete(call<primitive=load[Vec]>(left));",
    )

    body = _body(result)
    call = _only_call(body.result.value.pieces)
    assert call.dependency.primitive == "load"
    assert call.requires_unsafe is True
    assert body.requires_unsafe is True

    flattened_call = PivotCapturedCall(
        _token("call", 0),
        _DEPENDENCY,
        (),
        (),
        _SOURCE,
        True,
    )
    flattened_complete = PivotCapturedResult(
        _token("complete", 1),
        literal_text(flattened_call.token),
        _SOURCE,
    )
    flattened_body = _body(
        build_pivot_body(
            PivotLanguage.RUST,
            LoweredBody.from_render_text(flattened_complete),
            _capture(flattened_call, flattened_complete),
            _SOURCE,
        )
    )
    assert _only_call(flattened_body.result.value.pieces).requires_unsafe is True
    assert flattened_body.requires_unsafe is True


@pytest.mark.parametrize(
    ("lowered", "capture", "code"),
    (
        (
            LoweredBody.from_text("value;"),
            _capture(),
            "TSL-PIVOT-BODY-NO-COMPLETE",
        ),
        (
            LoweredBody.from_render_text(
                PivotCapturedResult(
                    _token("complete", 0), literal_text("  "), _SOURCE
                )
            ),
            _capture(
                PivotCapturedResult(
                    _token("complete", 0), literal_text("  "), _SOURCE
                ),
            ),
            "TSL-PIVOT-BODY-FOREIGN-CAPTURE",
        ),
    ),
)
def test_missing_or_foreign_final_result_is_typed(
    lowered: LoweredBody,
    capture: PivotBodyCapture,
    code: str,
) -> None:
    result = build_pivot_body(PivotLanguage.CPP, lowered, capture, _SOURCE)

    assert result.body is None
    assert tuple(reason.code for reason in result.unsupported) == (code,)
    assert result.unsupported[0].source == _SOURCE


def test_final_result_must_be_nonempty_unique_and_last() -> None:
    empty = PivotCapturedResult(
        _token("complete", 0), literal_text("  "), _SOURCE
    )
    empty_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(empty),
        _capture(empty),
        _SOURCE,
    )
    assert _unsupported_code(empty_result) == "TSL-PIVOT-BODY-EMPTY-EXPRESSION"

    first = PivotCapturedResult(
        _token("complete", 0), literal_text("left"), _SOURCE
    )
    second = PivotCapturedResult(
        _token("complete", 1), literal_text("right"), _SOURCE
    )
    duplicate_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(RenderSequence((first, second))),
        _capture(first, second),
        _SOURCE,
    )
    assert _unsupported_code(duplicate_result) == (
        "TSL-PIVOT-BODY-DUPLICATE-COMPLETE"
    )

    nonfinal_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(RenderSequence((first, LiteralText("; tail;")))),
        _capture(first),
        _SOURCE,
    )
    assert _unsupported_code(nonfinal_result) == (
        "TSL-PIVOT-BODY-NONFINAL-COMPLETE"
    )


def test_capture_adapter_rejects_malformed_unknown_repeated_and_lost_nodes() -> None:
    malformed = PivotCapturedResult("not-a-token", literal_text("x"), _SOURCE)
    malformed_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(malformed),
        _capture(malformed),
        _SOURCE,
    )
    assert _unsupported_code(malformed_result) == "TSL-PIVOT-BODY-MALFORMED-CAPTURE"

    unknown_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_text(_token("complete", 99)),
        _capture(),
        _SOURCE,
    )
    assert _unsupported_code(unknown_result) == "TSL-PIVOT-BODY-UNKNOWN-CAPTURE"

    truncated_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_text(f"{CAPTURE_OPEN}test:complete:0"),
        _capture(),
        _SOURCE,
    )
    assert _unsupported_code(truncated_result) == (
        "TSL-PIVOT-BODY-MALFORMED-CAPTURE"
    )

    complete = PivotCapturedResult(
        _token("complete", 0), literal_text("x"), _SOURCE
    )
    repeated_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(RenderSequence((complete, complete))),
        _capture(complete),
        _SOURCE,
    )
    assert _unsupported_code(repeated_result) == (
        "TSL-PIVOT-BODY-REPEATED-CAPTURE"
    )

    lost = PivotCapturedCall(_token("call", 1), _DEPENDENCY, (), (), _SOURCE)
    lost_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(complete),
        _capture(complete, lost),
        _SOURCE,
    )
    assert _unsupported_code(lost_result) == (
        "TSL-PIVOT-BODY-UNCONSUMED-CAPTURE"
    )


@pytest.mark.parametrize(
    "token",
    (
        f"{CAPTURE_OPEN}{'a' * 8}:complete:0{CAPTURE_CLOSE}",
        f"{CAPTURE_OPEN}{_CAPTURE_NAMESPACE}:unknown:0{CAPTURE_CLOSE}",
        f"{CAPTURE_OPEN}{_CAPTURE_NAMESPACE}:complete:wrong{CAPTURE_CLOSE}",
        _token("complete", 1),
    ),
)
def test_capture_records_require_exact_token_grammar(token: str) -> None:
    complete = PivotCapturedResult(token, literal_text("x"), _SOURCE)
    result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_render_text(complete),
        _capture(complete),
        _SOURCE,
    )

    assert _unsupported_code(result) == "TSL-PIVOT-BODY-MALFORMED-CAPTURE"


def test_only_declared_variant_captures_are_ignored() -> None:
    complete = PivotCapturedResult(
        _token("complete", 0), literal_text("x"), _SOURCE
    )
    variant_source = SourceSpan(_SOURCE.path, 40, 1, 45, 1)
    variant_call = PivotCapturedCall(
        _token("call", 1), _DEPENDENCY, (), (), variant_source
    )
    capture = _capture(complete, variant_call)
    lowered = LoweredBody.from_render_text(complete)

    unexpected = build_pivot_body(
        PivotLanguage.CPP,
        lowered,
        capture,
        _SOURCE,
    )
    assert _unsupported_code(unexpected) == (
        "TSL-PIVOT-BODY-OUT-OF-BODY-CAPTURE"
    )

    accepted = build_pivot_body(
        PivotLanguage.CPP,
        lowered,
        capture,
        _SOURCE,
        alternative_sources=(variant_source,),
    )
    assert _body(accepted).result.value.pieces[0] == PivotResidualText(
        "x", _SOURCE
    )


def test_capture_scope_is_fresh_reentrant_and_failure_safe(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    scope = PivotBodyCaptureScope("test")
    slot = _add_slot(catalog, machine_profiles)
    source = "var<infer>(tmp, left); complete(tmp);"

    first, first_capture = _lower_body(
        catalog, slot, PivotLanguage.CPP, source, scope=scope
    )
    with scope.capture(("outer",), _SOURCE) as outer:
        assert scope.current() is outer
        with scope.capture(("inner",), _SOURCE) as inner:
            assert scope.current() is inner
        assert scope.current() is outer
    try:
        with scope.capture(("left", "right"), _SOURCE):
            raise RuntimeError("deliberate failed operation")
    except RuntimeError:
        pass
    second, second_capture = _lower_body(
        catalog, slot, PivotLanguage.CPP, source, scope=scope
    )

    assert first == second
    assert first_capture != second_capture
    assert first_capture.namespace != second_capture.namespace
    assert {node.token for node in first_capture.nodes}.isdisjoint(
        node.token for node in second_capture.nodes
    )
    foreign_result = build_pivot_body(
        PivotLanguage.CPP,
        LoweredBody.from_text(first_capture.nodes[-1].token),
        second_capture,
        _SOURCE,
    )
    assert _unsupported_code(foreign_result) == (
        "TSL-PIVOT-BODY-UNKNOWN-CAPTURE"
    )
    assert tuple(
        statement.binding.identity.ordinal
        for statement in _body(first).statements
        if isinstance(statement, PivotLocal)
    ) == (2,)
    with pytest.raises(RuntimeError, match="active capture"):
        scope.current()
    with pytest.raises(FrozenInstanceError):
        _body(first).requires_unsafe = True  # type: ignore[misc]


def test_unresolved_explicit_call_vector_is_rejected_by_pivot_lowering(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    slot = _add_slot(catalog, machine_profiles)
    source = scan(
        "complete(call<primitive=add[Vec<DefinitelyUnknown>]>(left, right));",
        source=_SOURCE,
    )
    backend = create_backend_dialect(catalog, PivotLanguage.CPP.value)

    standard = Lowerer().lower(slot, catalog, backend, body_segments=source)

    body_scope = PivotBodyCaptureScope("test")
    with body_scope.capture(tuple(slot.primitive.parameters), _SOURCE):
        body = Lowerer(
            region_lowerers=pivot_capture_region_lowerers(body_scope)
        ).lower(slot, catalog, backend, body_segments=source)

    assert tuple(item.code for item in standard.diagnostics) == (
        "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
    )
    assert tuple(item.code for item in body.diagnostics) == (
        "TSL-PIVOT-UNSUPPORTED-CALL-TYPEARGS",
    )


def test_symbolic_call_vector_is_rejected_before_pivot_capture(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    slot = next(
        item
        for item in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "permute_lanes",
            ("si32",),
            backend_id="cpp",
        )
        .selected
        if item.extension.isa_name == "avx2"
        and any(param.kind == "simd_type" for param in item.primitive.generic_params)
    )
    source = scan(
        "complete(call<primitive=to_array[IndicesType]>(indexes));",
        source=_SOURCE,
    )
    backend = create_backend_dialect(catalog, PivotLanguage.CPP.value)

    standard = Lowerer().lower(slot, catalog, backend, body_segments=source)

    assert standard.specialization is not None, standard.diagnostics
    symbolic = {
        origin.dependency.source
        for origin in standard.specialization.call_dependency_origins
        if isinstance(
            origin.dependency.source,
            GenericVectorReference,
        )
    }
    assert len(symbolic) == 1
    assert isinstance(next(iter(symbolic)), GenericVectorReference)
    assert next(iter(symbolic)).parameter_name == "IndicesType"

    body_scope = PivotBodyCaptureScope("test")
    with body_scope.capture(tuple(slot.primitive.parameters), _SOURCE):
        body = Lowerer(
            region_lowerers=pivot_capture_region_lowerers(body_scope)
        ).lower(slot, catalog, backend, body_segments=source)

    assert body.specialization is None
    assert tuple(item.code for item in body.diagnostics) == (
        "TSL-PIVOT-UNSUPPORTED-CALL-TYPEARGS",
    )


def test_source_nul_is_rejected_before_capture() -> None:
    unsupported = capture_source_collision("before\x00after", _SOURCE)

    assert unsupported is not None
    assert unsupported.code == "TSL-PIVOT-CAPTURE-TOKEN-COLLISION"
    assert unsupported.phase == "capture"
    assert unsupported.source == _SOURCE


def _add_slot(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> SelectedImplementation:
    selection = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "add",
        ("si8",),
        backend_id="cpp",
    )
    return next(
        item
        for item in selection.selected
        if item.extension.isa_name == "avx2"
        and item.primitive.attributes.get("mask") is None
    )


def _lower_body(
    catalog: Catalog,
    slot: SelectedImplementation,
    language: PivotLanguage,
    source_text: str,
    *,
    scope: PivotBodyCaptureScope | None = None,
) -> tuple[PivotBodyBuildResult, PivotBodyCapture]:
    active_scope = scope or PivotBodyCaptureScope("test")
    lowerer = Lowerer(region_lowerers=pivot_capture_region_lowerers(active_scope))
    with active_scope.capture(tuple(slot.primitive.parameters), _SOURCE) as builder:
        lowered = lowerer.lower(
            slot,
            catalog,
            create_backend_dialect(catalog, language.value),
            body_segments=scan(source_text, source=_SOURCE),
        )
        capture = builder.freeze()
    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    return (
        build_pivot_body(
            language,
            lowered.specialization.body,
            capture,
            _SOURCE,
        ),
        capture,
    )


def _body(result: PivotBodyBuildResult) -> PivotBody:
    assert result.unsupported == ()
    assert result.body is not None
    return result.body


def _fixed_census(
    root: Path,
    relative_source: Path,
    *,
    line: int = 1,
    callable_name: str = "demo",
) -> PivotBodyCensus:
    source = SourceSpan(root / relative_source, line, 1, line + 1, 1)
    body = synthetic_pivot_body(
        PivotLanguage.CPP,
        ("value",),
        callable_name,
        "__m128i",
        source,
    )
    return PivotBodyCensus(
        PivotLanguage.CPP,
        (
            PivotBodyEntry(
                document="demo",
                definition=PivotDefinition(
                    isa="tsl_128",
                    dtype="int8",
                    signature=(("value", "__m128i"), ("result", "__m128i")),
                    direct=(f"result = {callable_name}<__m128i>(value);",),
                ),
                occurrence=0,
                origin=PivotBodyOrigin.FIXED_WRAPPER,
                category=PivotBodyCategory.SYNTHETIC_FIXED,
                body=body,
            ),
        ),
    )


def _only_call(pieces: tuple[object, ...]) -> PivotCall:
    calls = tuple(piece for piece in pieces if isinstance(piece, PivotCall))
    assert len(calls) == 1
    return calls[0]


def _unsupported_code(result: PivotBodyBuildResult) -> str:
    assert result.body is None
    assert len(result.unsupported) == 1
    return result.unsupported[0].code
