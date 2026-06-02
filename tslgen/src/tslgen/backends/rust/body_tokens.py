"""Rust body-token rendering by substituting rendered backend intrinsic islands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.backends.body_token_contract import (
    BodyTokenRenderPolicy,
    BodyTokenRenderedIntrinsicCall,
    BodyTokenRenderedIntrinsicCallText,
    render_intrinsic_body_tokens_from_handoff,
)
from tslgen.backends.intrinsic_invocations import BackendIntrinsicInvocationImmediate
from tslgen.backends.rust.intrinsic_calls import RustRenderedIntrinsicCall
from tslgen.backends.type_spelling import BackendTranslatedTypeSpelling
from tslgen.backends.type_value_body_tokens import (
    TypeValueBodyTokenRenderPolicy,
    rendered_backend_value,
    rendered_type_spelling_value,
    render_type_body_tokens_from_handoff,
    render_value_body_tokens_from_handoff,
)
from tslgen.backends.value_translation import BackendTranslatedValue
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.lowering.model import (
    BackendIntrinsicHandoff,
    BackendTypeQueryHandoff,
    BackendValueQueryHandoff,
)

RustBodyText = NewType("RustBodyText", str)

_RUST_BODY_TOKEN_POLICY = BodyTokenRenderPolicy(
    backend=BackendId("rust"),
    backend_label="Rust",
    diagnostic_code_prefix="TSL-RUST-BODY-TOKENS",
)
_RUST_TYPE_VALUE_BODY_TOKEN_POLICY = TypeValueBodyTokenRenderPolicy(
    backend=BackendId("rust"),
    backend_label="Rust",
    diagnostic_code_prefix="TSL-RUST-TYPE-VALUE-BODY-TOKENS",
)


@dataclass(frozen=True, slots=True)
class RustRenderedBodyTokens:
    handoff: BackendIntrinsicHandoff
    text: RustBodyText
    calls: tuple[RustRenderedIntrinsicCall, ...]
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RustBodyTokenRenderResult:
    body: RustRenderedBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class RustRenderedTypeQueryBodyTokens:
    handoff: BackendTypeQueryHandoff
    text: RustBodyText
    spellings: tuple[BackendTranslatedTypeSpelling, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RustTypeQueryBodyTokenRenderResult:
    body: RustRenderedTypeQueryBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class RustRenderedValueQueryBodyTokens:
    handoff: BackendValueQueryHandoff
    text: RustBodyText
    values: tuple[BackendTranslatedValue, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RustValueQueryBodyTokenRenderResult:
    body: RustRenderedValueQueryBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_rust_body_tokens_from_intrinsic_handoff(
    handoff: BackendIntrinsicHandoff,
    rendered_calls: tuple[RustRenderedIntrinsicCall, ...],
) -> RustBodyTokenRenderResult:
    """Render a body token stream by replacing intrinsic request segments."""

    original_by_request_id = {
        id(call.invocation.request): call for call in rendered_calls
    }
    contract_result = render_intrinsic_body_tokens_from_handoff(
        handoff,
        tuple(_contract_call(call) for call in rendered_calls),
        _RUST_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return RustBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_calls = tuple(
        original_by_request_id[id(call.request)] for call in contract_result.body.calls
    )
    return RustBodyTokenRenderResult(
        body=RustRenderedBodyTokens(
            handoff=handoff,
            text=RustBodyText(str(contract_result.body.text)),
            calls=ordered_calls,
            immediates=contract_result.body.immediates,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def render_rust_body_tokens_from_type_query_handoff(
    handoff: BackendTypeQueryHandoff,
    translated_spellings: tuple[BackendTranslatedTypeSpelling, ...],
) -> RustTypeQueryBodyTokenRenderResult:
    """Render a body token stream by replacing backend type query segments."""

    original_by_request_id = {
        id(spelling.request): spelling for spelling in translated_spellings
    }
    contract_result = render_type_body_tokens_from_handoff(
        handoff,
        tuple(rendered_type_spelling_value(spelling) for spelling in translated_spellings),
        _RUST_TYPE_VALUE_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return RustTypeQueryBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_spellings = tuple(
        original_by_request_id[id(value.request)]
        for value in contract_result.body.values
    )
    return RustTypeQueryBodyTokenRenderResult(
        body=RustRenderedTypeQueryBodyTokens(
            handoff=handoff,
            text=RustBodyText(str(contract_result.body.text)),
            spellings=ordered_spellings,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def render_rust_body_tokens_from_value_query_handoff(
    handoff: BackendValueQueryHandoff,
    translated_values: tuple[BackendTranslatedValue, ...],
) -> RustValueQueryBodyTokenRenderResult:
    """Render a body token stream by replacing backend value query segments."""

    original_by_request_id = {
        id(value.request): value for value in translated_values
    }
    contract_result = render_value_body_tokens_from_handoff(
        handoff,
        tuple(rendered_backend_value(value) for value in translated_values),
        _RUST_TYPE_VALUE_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return RustValueQueryBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_values = tuple(
        original_by_request_id[id(value.request)]
        for value in contract_result.body.values
    )
    return RustValueQueryBodyTokenRenderResult(
        body=RustRenderedValueQueryBodyTokens(
            handoff=handoff,
            text=RustBodyText(str(contract_result.body.text)),
            values=ordered_values,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def _contract_call(call: RustRenderedIntrinsicCall) -> BodyTokenRenderedIntrinsicCall:
    return BodyTokenRenderedIntrinsicCall(
        backend=call.invocation.backend,
        request=call.invocation.request,
        text=BodyTokenRenderedIntrinsicCallText(str(call.call_text)),
        immediates=call.immediates,
        source=call.source,
    )
