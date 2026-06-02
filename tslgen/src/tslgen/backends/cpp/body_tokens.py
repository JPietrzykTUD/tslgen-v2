"""C++ body-token rendering by substituting rendered backend intrinsic islands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.backends.body_token_contract import (
    BodyTokenRenderPolicy,
    BodyTokenRenderedIntrinsicCall,
    BodyTokenRenderedIntrinsicCallText,
    render_intrinsic_body_tokens_from_handoff,
)
from tslgen.backends.cpp.intrinsic_calls import CppRenderedIntrinsicCall
from tslgen.backends.intrinsic_invocations import BackendIntrinsicInvocationImmediate
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

CppBodyText = NewType("CppBodyText", str)

_CPP_BODY_TOKEN_POLICY = BodyTokenRenderPolicy(
    backend=BackendId("cpp"),
    backend_label="C++",
    diagnostic_code_prefix="TSL-CPP-BODY-TOKENS",
)
_CPP_TYPE_VALUE_BODY_TOKEN_POLICY = TypeValueBodyTokenRenderPolicy(
    backend=BackendId("cpp"),
    backend_label="C++",
    diagnostic_code_prefix="TSL-CPP-TYPE-VALUE-BODY-TOKENS",
)


@dataclass(frozen=True, slots=True)
class CppRenderedBodyTokens:
    handoff: BackendIntrinsicHandoff
    text: CppBodyText
    calls: tuple[CppRenderedIntrinsicCall, ...]
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CppBodyTokenRenderResult:
    body: CppRenderedBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class CppRenderedTypeQueryBodyTokens:
    handoff: BackendTypeQueryHandoff
    text: CppBodyText
    spellings: tuple[BackendTranslatedTypeSpelling, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CppTypeQueryBodyTokenRenderResult:
    body: CppRenderedTypeQueryBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class CppRenderedValueQueryBodyTokens:
    handoff: BackendValueQueryHandoff
    text: CppBodyText
    values: tuple[BackendTranslatedValue, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CppValueQueryBodyTokenRenderResult:
    body: CppRenderedValueQueryBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_cpp_body_tokens_from_intrinsic_handoff(
    handoff: BackendIntrinsicHandoff,
    rendered_calls: tuple[CppRenderedIntrinsicCall, ...],
) -> CppBodyTokenRenderResult:
    """Render a body token stream by replacing intrinsic request segments."""

    original_by_request_id = {
        id(call.invocation.request): call for call in rendered_calls
    }
    contract_result = render_intrinsic_body_tokens_from_handoff(
        handoff,
        tuple(_contract_call(call) for call in rendered_calls),
        _CPP_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return CppBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_calls = tuple(
        original_by_request_id[id(call.request)] for call in contract_result.body.calls
    )
    return CppBodyTokenRenderResult(
        body=CppRenderedBodyTokens(
            handoff=handoff,
            text=CppBodyText(str(contract_result.body.text)),
            calls=ordered_calls,
            immediates=contract_result.body.immediates,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def render_cpp_body_tokens_from_type_query_handoff(
    handoff: BackendTypeQueryHandoff,
    translated_spellings: tuple[BackendTranslatedTypeSpelling, ...],
) -> CppTypeQueryBodyTokenRenderResult:
    """Render a body token stream by replacing backend type query segments."""

    original_by_request_id = {
        id(spelling.request): spelling for spelling in translated_spellings
    }
    contract_result = render_type_body_tokens_from_handoff(
        handoff,
        tuple(rendered_type_spelling_value(spelling) for spelling in translated_spellings),
        _CPP_TYPE_VALUE_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return CppTypeQueryBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_spellings = tuple(
        original_by_request_id[id(value.request)]
        for value in contract_result.body.values
    )
    return CppTypeQueryBodyTokenRenderResult(
        body=CppRenderedTypeQueryBodyTokens(
            handoff=handoff,
            text=CppBodyText(str(contract_result.body.text)),
            spellings=ordered_spellings,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def render_cpp_body_tokens_from_value_query_handoff(
    handoff: BackendValueQueryHandoff,
    translated_values: tuple[BackendTranslatedValue, ...],
) -> CppValueQueryBodyTokenRenderResult:
    """Render a body token stream by replacing backend value query segments."""

    original_by_request_id = {
        id(value.request): value for value in translated_values
    }
    contract_result = render_value_body_tokens_from_handoff(
        handoff,
        tuple(rendered_backend_value(value) for value in translated_values),
        _CPP_TYPE_VALUE_BODY_TOKEN_POLICY,
    )

    if contract_result.diagnostics:
        return CppValueQueryBodyTokenRenderResult(
            body=None,
            diagnostics=contract_result.diagnostics,
        )

    assert contract_result.body is not None
    ordered_values = tuple(
        original_by_request_id[id(value.request)]
        for value in contract_result.body.values
    )
    return CppValueQueryBodyTokenRenderResult(
        body=CppRenderedValueQueryBodyTokens(
            handoff=handoff,
            text=CppBodyText(str(contract_result.body.text)),
            values=ordered_values,
            source=contract_result.body.source,
        ),
        diagnostics=(),
    )


def _contract_call(call: CppRenderedIntrinsicCall) -> BodyTokenRenderedIntrinsicCall:
    return BodyTokenRenderedIntrinsicCall(
        backend=call.invocation.backend,
        request=call.invocation.request,
        text=BodyTokenRenderedIntrinsicCallText(str(call.call_text)),
        immediates=call.immediates,
        source=call.source,
    )
