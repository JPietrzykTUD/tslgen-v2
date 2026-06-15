"""Primitive signature shapes.

A signature like ``v:=(v,v)`` or ``s:=v`` describes the *kinds* of a primitive's
result and parameters in semantic terms — vector (``v``), scalar (``s``), mask
(``m``), pointer (``ptr``), etc. The backend turns each kind into a concrete type
spelling; this module only recovers the shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A ``[name]`` index annotation on a param kind (``v[idx]`` = a vector indexed by a compile-time
# index, the lane `extract_value` returns). Decorative — the index itself is a `generic_params`
# entry (`Index {kind int}`), so the param's kind is just the bare ``v``. Empty ``[]`` is NOT
# matched: that is the array kind ``s[]``, which must be preserved.
_INDEX_ANNOTATION = re.compile(r"\[[A-Za-z_]\w*\]$")


@dataclass(frozen=True, slots=True)
class SignatureShape:
    result_kind: str
    param_kinds: tuple[str, ...]


def parse_signature(text: str) -> SignatureShape | None:
    """Parse ``RESULT:=PARAMS`` into a :class:`SignatureShape`.

    ``PARAMS`` is either a single kind (``s:=v``) or a parenthesized,
    comma-separated list (``v:=(v,v)``). Returns ``None`` if it does not match.
    """

    result_text, separator, params_text = text.partition(":=")
    if not separator:
        return None
    params_text = params_text.strip()
    if params_text.startswith("(") and params_text.endswith(")"):
        params_text = params_text[1:-1]
    param_kinds = tuple(
        _INDEX_ANNOTATION.sub("", part.strip())
        for part in params_text.split(",")
        if part.strip()
    )
    return SignatureShape(result_kind=result_text.strip(), param_kinds=param_kinds)
