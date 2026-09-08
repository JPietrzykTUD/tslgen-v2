"""Typed primitive-call precondition forwarding, discharge, and auditing."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from tslc.catalog.arithmetic import ArithmeticOperandBinding
from tslc.catalog.call_preconditions import (
    CallArgumentBinding,
    CallPreconditionDisposition,
    CallPreconditionDispositionKind,
    CallPreconditionObligationStatus,
    resolve_call_preconditions,
)
from tslc.catalog.model import Catalog, Primitive, PrimitiveMaskMode
from tslc.catalog.preconditions import PreconditionKind, PrimitivePrecondition
from tslc.catalog.validation import validate_call_precondition_dispositions
from tslc.diagnostics import SourceSpan
from tslc.maintenance.call_precondition_audit import (
    audit_call_preconditions,
    serialize_call_precondition_audit,
)


def test_exact_root_operand_identities_forward_a_callee_condition(
    catalog: Catalog,
) -> None:
    caller = _primitive(catalog, "mod")
    callee = _primitive(catalog, "div")

    resolution = resolve_call_preconditions(
        caller,
        (callee,),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO, forward=True),),
        (CallArgumentBinding(0, 0), CallArgumentBinding(1, 1)),
        same_vector=True,
        type_tag="si32",
        attributes={},
        source=None,
    )

    assert len(resolution.obligations) == 1
    assert resolution.obligations[0].resolved
    assert resolution.stale_dispositions == ()


def test_recursive_call_can_forward_an_unchanged_root_condition(
    catalog: Catalog,
) -> None:
    primitive = _primitive(catalog, "mod")

    resolution = resolve_call_preconditions(
        primitive,
        (primitive,),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO, forward=True),),
        (CallArgumentBinding(0, 0), CallArgumentBinding(1, 1)),
        same_vector=True,
        type_tag="si32",
        attributes={},
        source=None,
    )

    assert resolution.unresolved == ()


def test_forwarding_rejects_a_changed_vector_identity(catalog: Catalog) -> None:
    resolution = resolve_call_preconditions(
        _primitive(catalog, "mod"),
        (_primitive(catalog, "div"),),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO, forward=True),),
        (CallArgumentBinding(0, 0), CallArgumentBinding(1, 1)),
        same_vector=False,
        type_tag="si32",
        attributes={},
        source=None,
    )

    obligation = resolution.obligations[0]
    assert obligation.status is CallPreconditionObligationStatus.INVALID_FORWARD
    assert "crosses a vector identity" in (obligation.reason or "")


def test_forwarding_rejects_a_changed_memory_payload_extent(
    catalog: Catalog,
) -> None:
    resolution = resolve_call_preconditions(
        _primitive(catalog, "load_convert_up"),
        (_primitive(catalog, "load", attributes={"aligned": "false"}),),
        (_disposition(PreconditionKind.CONTIGUOUS_MEMORY_EXTENT, forward=True),),
        (CallArgumentBinding(0, 0),),
        same_vector=True,
        type_tag="f32",
        attributes={"aligned": "false"},
        source=None,
    )

    obligation = resolution.obligations[0]
    assert obligation.status is CallPreconditionObligationStatus.INVALID_FORWARD
    assert "matching root precondition" in (obligation.reason or "")


def test_forwarding_rejects_a_transformed_bound_operand(catalog: Catalog) -> None:
    caller = _primitive(catalog, "mod")
    callee = _primitive(catalog, "div")

    resolution = resolve_call_preconditions(
        caller,
        (callee,),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO, forward=True),),
        (CallArgumentBinding(0, 0),),
        same_vector=True,
        type_tag="si32",
        attributes={},
        source=None,
    )

    obligation = resolution.obligations[0]
    assert obligation.status is CallPreconditionObligationStatus.INVALID_FORWARD
    assert "exact caller parameter" in (obligation.reason or "")


def test_mask_sensitive_forwarding_requires_the_exact_control_mask(
    catalog: Catalog,
) -> None:
    caller = _primitive(catalog, "mod", mask=PrimitiveMaskMode.ZERO)
    callee = _primitive(catalog, "div", mask=PrimitiveMaskMode.ZERO)
    disposition = _disposition(
        PreconditionKind.ACTIVE_DIVISOR_NONZERO,
        forward=True,
    )

    exact = resolve_call_preconditions(
        caller,
        (callee,),
        (disposition,),
        tuple(CallArgumentBinding(index, index) for index in range(3)),
        same_vector=True,
        type_tag="si32",
        attributes={"mask": "zero"},
        source=None,
    )
    missing_mask = resolve_call_preconditions(
        caller,
        (callee,),
        (disposition,),
        (CallArgumentBinding(1, 1), CallArgumentBinding(2, 2)),
        same_vector=True,
        type_tag="si32",
        attributes={"mask": "zero"},
        source=None,
    )

    assert exact.obligations[0].resolved
    assert (
        missing_mask.obligations[0].status
        is CallPreconditionObligationStatus.INVALID_FORWARD
    )


def test_type_inapplicable_dynamic_condition_needs_no_disposition(
    catalog: Catalog,
) -> None:
    resolution = resolve_call_preconditions(
        _primitive(catalog, "mod"),
        (_primitive(catalog, "div"),),
        (),
        (CallArgumentBinding(0, 0), CallArgumentBinding(1, 1)),
        same_vector=True,
        type_tag="f32",
        attributes={},
        source=None,
    )

    assert resolution.obligations == ()


def test_explicit_discharge_covers_compile_time_and_local_memory_proofs(
    catalog: Catalog,
) -> None:
    immediate = resolve_call_preconditions(
        _primitive(catalog, "mod_imm"),
        (_primitive(catalog, "mod"),),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO),),
        (CallArgumentBinding(0, 0),),
        same_vector=True,
        type_tag="si32",
        attributes={},
        source=None,
    )
    local_memory = resolve_call_preconditions(
        _primitive(catalog, "to_array"),
        (_primitive(catalog, "store", attributes={"aligned": "false"}),),
        (_disposition(PreconditionKind.CONTIGUOUS_MEMORY_EXTENT),),
        (CallArgumentBinding(1, 0),),
        same_vector=True,
        type_tag="si32",
        attributes={"aligned": "false"},
        source=None,
    )

    assert tuple(item.resolved for item in immediate.obligations) == (True,)
    assert tuple(item.callee_condition for item in local_memory.obligations) == (
        PreconditionKind.CONTIGUOUS_MEMORY_EXTENT,
    )
    assert local_memory.obligations[0].resolved


def test_forwarding_rejects_ambiguous_overload_operand_identities(
    catalog: Catalog,
) -> None:
    caller = _primitive(catalog, "mod")
    callee = _primitive(catalog, "div")
    condition = callee.preconditions[0]
    binding = condition.operand_bindings[0]
    assert isinstance(binding, ArithmeticOperandBinding)
    ambiguous = replace(
        callee,
        preconditions=(
            PrimitivePrecondition(
                condition.kind,
                (
                    replace(
                        binding,
                        parameter_name="dividend",
                        parameter_index=0,
                        non_mask_ordinal=0,
                    ),
                ),
                condition.source,
            ),
        ),
    )

    resolution = resolve_call_preconditions(
        caller,
        (callee, ambiguous),
        (_disposition(PreconditionKind.ACTIVE_DIVISOR_NONZERO, forward=True),),
        (CallArgumentBinding(0, 0), CallArgumentBinding(1, 1)),
        same_vector=True,
        type_tag="si32",
        attributes={},
        source=None,
    )

    assert (
        resolution.obligations[0].status
        is CallPreconditionObligationStatus.INVALID_FORWARD
    )
    assert "ambiguous" in (resolution.obligations[0].reason or "")


def test_catalog_reports_missing_invalid_and_stale_dispositions_at_source(
    catalog: Catalog,
) -> None:
    cases = (
        (
            "complete(call<primitive=div>(dividend, divisor));",
            "TSL-CATALOG-MISSING-CALL-PRECONDITION",
            "call<",
        ),
        (
            "complete(call<primitive=div, forward[active_divisor_nonzero]>("
            "dividend, call<primitive=set1>(1)));",
            "TSL-CATALOG-INVALID-CALL-PRECONDITION-FORWARD",
            "active_divisor_nonzero",
        ),
        (
            "complete(call<primitive=add, discharge[active_divisor_nonzero]>("
            "dividend, divisor));",
            "TSL-CATALOG-STALE-CALL-PRECONDITION",
            "active_divisor_nonzero",
        ),
    )
    for offset, (body, code, token) in enumerate(cases, start=20):
        source = SourceSpan(Path("call-proof.tsl"), offset, 5, offset, 5 + len(body))
        mutated = _replace_primitive_body(
            catalog,
            _primitive(catalog, "mod"),
            body,
            source,
        )
        diagnostics = []

        validate_call_precondition_dispositions(mutated, diagnostics)

        diagnostic = next(item for item in diagnostics if item.code == code)
        assert diagnostic.span is not None
        assert diagnostic.span.line == offset
        if token == "active_divisor_nonzero":
            assert diagnostic.span.column == source.column + body.index(token)


def test_current_corpus_call_precondition_report_is_complete_and_deterministic(
    data_root: Path,
) -> None:
    audit, diagnostics = audit_call_preconditions((data_root,))

    assert diagnostics == ()
    assert audit is not None
    assert audit.disposition_counts == {"forward": 11, "discharge": 138}
    assert len(audit.entries) == 149
    first = serialize_call_precondition_audit(audit, root=data_root.parent)
    assert serialize_call_precondition_audit(audit, root=data_root.parent) == first
    payload = json.loads(first)
    assert payload["schema_version"] == 1
    assert payload["summary"]["unresolved"] == 0


def _primitive(
    catalog: Catalog,
    name: str,
    *,
    mask: PrimitiveMaskMode | None = None,
    attributes: dict[str, str] | None = None,
) -> Primitive:
    return next(
        primitive
        for primitive in catalog.primitives_named(name, unmasked=False)
        if primitive.mask_mode is mask
        and (
            attributes is None
            or all(
                primitive.attributes.get(key) == value
                for key, value in attributes.items()
            )
        )
    )


def _disposition(
    condition: PreconditionKind,
    *,
    forward: bool = False,
) -> CallPreconditionDisposition:
    kind = (
        CallPreconditionDispositionKind.FORWARD
        if forward
        else CallPreconditionDispositionKind.DISCHARGE
    )
    return CallPreconditionDisposition(
        condition,
        kind,
        forwarded_root=condition if forward else None,
    )


def _replace_primitive_body(
    catalog: Catalog,
    primitive: Primitive,
    body: str,
    source: SourceSpan,
) -> Catalog:
    implementation = replace(
        primitive.implementations[0],
        body_text=body,
        body_source=source,
        variants=(),
    )
    replacement = replace(primitive, implementations=(implementation,))
    return replace(
        catalog,
        primitives=tuple(
            replacement if item is primitive else item for item in catalog.primitives
        ),
    )
