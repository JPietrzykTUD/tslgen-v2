"""Backend literal spelling helpers for value-test renderers."""

from __future__ import annotations

from tslc.catalog.scalar_types import scalar_bit_width


def cpp_literal(token: str, type_tag: str) -> str:
    if type_tag.startswith("f"):
        upper = token.upper()
        if upper in ("INFINITY", "+INFINITY"):
            return "INFINITY"
        if upper == "-INFINITY":
            return "-INFINITY"
        if upper in ("NAN", "+NAN", "-NAN"):
            return "NAN"
        if _is_numeric_token(token):
            target = "float" if type_tag == "f32" else "double"
            return f"static_cast<{target}>({token})"
        return token
    wrapped = _wrapped_int(token, type_tag)
    return wrapped if wrapped is not None else token


def cpp_literal_list(values: tuple[str, ...], type_tag: str) -> str:
    return ", ".join(cpp_literal(value, type_tag) for value in values)


def rust_literal(token: str, type_tag: str) -> str:
    if type_tag.startswith("f"):
        ty = "f32" if "32" in type_tag else "f64"
        upper = token.upper()
        if upper in ("INFINITY", "+INFINITY"):
            return f"{ty}::INFINITY"
        if upper == "-INFINITY":
            return f"{ty}::NEG_INFINITY"
        if upper in ("NAN", "+NAN", "-NAN"):
            return f"{ty}::NAN"
        if _is_numeric_token(token) and all(ch not in token.lower() for ch in (".", "e")):
            return f"{token}.0"
        return token
    wrapped = _wrapped_int(token, type_tag)
    return wrapped if wrapped is not None else token


def rust_literal_list(values: tuple[str, ...], type_tag: str) -> str:
    return ", ".join(rust_literal(value, type_tag) for value in values)


def token_truthy(token: str) -> bool:
    try:
        return int(token) != 0
    except ValueError:
        try:
            return float(token) != 0.0
        except ValueError:
            return True


def _wrapped_int(token: str, type_tag: str) -> str | None:
    bits = _type_bits(type_tag)
    if bits is None:
        return None
    try:
        value = int(token)
    except ValueError:
        return None
    value %= 1 << bits
    if type_tag.startswith("s") and value >= (1 << (bits - 1)):
        value -= 1 << bits
    return str(value)


def _is_numeric_token(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def _type_bits(type_tag: str) -> int | None:
    return scalar_bit_width(type_tag)


__all__ = (
    "cpp_literal",
    "cpp_literal_list",
    "rust_literal",
    "rust_literal_list",
    "token_truthy",
)
