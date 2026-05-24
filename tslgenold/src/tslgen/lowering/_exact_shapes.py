from __future__ import annotations

from dataclasses import dataclass
import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result


_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"


@dataclass(frozen=True, slots=True)
class ExactSelectedBodyAssignmentShape:
    target_text: str
    direct_intrinsic_tokens: tuple[str, ...]
    rhs_pattern: re.Pattern[str]

    def __post_init__(self) -> None:
        if not self.target_text:
            raise ValueError("exact selected-body target text must be non-empty")
        tokens = tuple(self.direct_intrinsic_tokens)
        if not tokens:
            raise ValueError(
                "exact selected-body direct-intrinsic token set must be non-empty",
            )
        if any(not token for token in tokens):
            raise ValueError(
                "exact selected-body direct-intrinsic tokens must be non-empty",
            )
        object.__setattr__(self, "direct_intrinsic_tokens", tokens)

    def supports_direct_intrinsic_token(self, token: str) -> bool:
        return token in self.direct_intrinsic_tokens


@dataclass(frozen=True, slots=True)
class ExactSelectedBodyAssignmentParse:
    assignment_target_text: str
    opaque_rhs_text: str
    direct_intrinsic_token_text: str


EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE = ExactSelectedBodyAssignmentShape(
    target_text="pg",
    direct_intrinsic_tokens=(
        "svptrue_b16",
        "svptrue_b32",
        "svptrue_b64",
    ),
    rhs_pattern=re.compile(
        rf"\Aintrin\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*\(\s*\)\Z",
    ),
)

EXACT_PREDICATE_INIT_TYPE_TOKEN = "svbool_t"
EXACT_PREDICATE_TOKEN = "pg"
EXACT_PREDICATE_INIT_DIRECT_INTRINSIC_TOKEN = "svptrue_b8"
EXACT_PREDICATE_INIT_SLOT_RE = re.compile(
    rf"\A\s*(?P<predicate_type>{_TSIL_IDENTIFIER})\s+"
    rf"(?P<predicate_token>{_TSIL_IDENTIFIER})\s*=\s*"
    rf"intrin\s*<\s*(?P<direct_intrinsic_token>{_TSIL_IDENTIFIER})\s*>\s*"
    r"\(\s*\)\s*;\s*\Z"
)

EXACT_POST_BRANCH_CALL_HEAD_TOKEN = "intrin"
EXACT_POST_BRANCH_INTRINSIC_TOKEN = "svst1"
EXACT_POST_BRANCH_MEMBER_ACCESS_TEXT = "tmp.data()"
EXACT_POST_BRANCH_MEMBER_ACCESS_BASE_TOKEN = "tmp"
EXACT_POST_BRANCH_MEMBER_ACCESS_MEMBER_TOKEN = "data"
EXACT_POST_BRANCH_SOURCE_OPERAND_TOKEN = "a"
EXACT_RETURN_EMISSION_CALL_HEAD_TOKEN = "emit_return"

EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE = re.compile(
    rf"\A\s*intrin\s*<\s*(?P<call_token>{_TSIL_IDENTIFIER})\s*>\s*"
    rf"\(\s*(?P<predicate_token>{_TSIL_IDENTIFIER})\s*,\s*"
    r"tmp\.data\(\)\s*,\s*a\s*\)\s*;\s*\Z",
)
POST_BRANCH_INTRINSIC_CALL_SITE_CONTAINER_RE = re.compile(
    rf"\A\s*(?P<call_head>{_TSIL_IDENTIFIER})\s*"
    rf"<\s*(?P<intrinsic_token>{_TSIL_IDENTIFIER})\s*>\s*"
    r"\((?P<arguments>.*)\)\s*;\s*\Z",
)
POST_BRANCH_MEMBER_ACCESS_ARGUMENT_RE = re.compile(
    rf"\A(?P<base_token>{_TSIL_IDENTIFIER})\."
    rf"(?P<member_token>{_TSIL_IDENTIFIER})\s*\(\s*\)\Z",
)
EXACT_RETURN_EMISSION_SLOT_RE = re.compile(
    rf"\A\s*(?P<emit_return_token>{EXACT_RETURN_EMISSION_CALL_HEAD_TOKEN})"
    rf"\s*\(\s*(?P<returned_token>{_TSIL_IDENTIFIER})\s*\)\s*;\s*\Z",
)


def parse_exact_selected_body_assignment_form(
    body_text: str,
    location: SourceLocation | None,
) -> Result[ExactSelectedBodyAssignmentParse]:
    stripped = body_text.strip()
    if stripped.count(";") > 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-EXTRA-STATEMENTS",
                    "selected-body assignment-form recognition supports only one "
                    "selected statement",
                    location=location,
                ),
            )
        )
    if not stripped.endswith(";"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition supports only "
                    "'pg = intrin<svptrue_b16|svptrue_b32|svptrue_b64>();'",
                    location=location,
                ),
            )
        )

    statement_text = stripped[:-1].strip()
    if "=" not in statement_text:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition requires one "
                    "assignment statement",
                    location=location,
                ),
            )
        )

    target_text, rhs_text = (
        part.strip()
        for part in statement_text.split("=", 1)
    )
    if not target_text or not rhs_text:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition requires both "
                    "assignment target text and RHS text",
                    location=location,
                ),
            )
        )
    if target_text != EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE.target_text:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-TARGET-UNSUPPORTED",
                    "selected-body assignment-form recognition supports only "
                    "the exact assignment target text 'pg'; got "
                    f"{target_text!r}",
                    location=location,
                ),
            )
        )

    match = EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE.rhs_pattern.fullmatch(rhs_text)
    if match is None:
        return Result.failure(
            (
                unsupported_selected_body_assignment_rhs_diagnostic(
                    rhs_text,
                    location,
                ),
            )
        )
    direct_intrinsic_token_text = match.group(1)
    if not EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE.supports_direct_intrinsic_token(
        direct_intrinsic_token_text,
    ):
        return Result.failure(
            (
                unsupported_selected_body_assignment_rhs_diagnostic(
                    rhs_text,
                    location,
                ),
            )
        )

    return Result.ok(
        ExactSelectedBodyAssignmentParse(
            assignment_target_text=target_text,
            opaque_rhs_text=rhs_text,
            direct_intrinsic_token_text=direct_intrinsic_token_text,
        )
    )


def unsupported_selected_body_assignment_rhs_diagnostic(
    rhs_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED",
        "selected-body assignment-form recognition supports only opaque RHS "
        "text shaped as 'intrin<svptrue_b16>()', 'intrin<svptrue_b32>()', "
        "or 'intrin<svptrue_b64>()'; got "
        f"{rhs_text!r}",
        location=location,
    )
