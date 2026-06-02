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
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.lowering.model import BackendIntrinsicHandoff

RustBodyText = NewType("RustBodyText", str)

_RUST_BODY_TOKEN_POLICY = BodyTokenRenderPolicy(
    backend=BackendId("rust"),
    backend_label="Rust",
    diagnostic_code_prefix="TSL-RUST-BODY-TOKENS",
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


def _contract_call(call: RustRenderedIntrinsicCall) -> BodyTokenRenderedIntrinsicCall:
    return BodyTokenRenderedIntrinsicCall(
        backend=call.invocation.backend,
        request=call.invocation.request,
        text=BodyTokenRenderedIntrinsicCallText(str(call.call_text)),
        immediates=call.immediates,
        source=call.source,
    )
