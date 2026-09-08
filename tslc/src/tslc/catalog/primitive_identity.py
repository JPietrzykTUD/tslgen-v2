"""Canonical identity formatting for one primitive declaration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def primitive_declaration_identity(
    name: str,
    signature: str,
    attributes: Mapping[str, str] | Iterable[tuple[str, str]],
    result_target: tuple[str, ...] | None,
    overload: tuple[str, str, bool] | None,
) -> str:
    attribute_items = (
        attributes.items() if isinstance(attributes, Mapping) else attributes
    )
    ordered_attributes = tuple(sorted(attribute_items))
    attribute_text = ""
    if ordered_attributes:
        attribute_text = "[" + ",".join(
            f"{key}={value}" for key, value in ordered_attributes
        ) + "]"
    target_text = ""
    if result_target:
        target_text = "->" + ":".join(result_target)
    overload_text = ""
    if overload is not None:
        axis, value, primary = overload
        overload_text = f"@{axis}={value}" + (":primary" if primary else "")
    return f"{name}{attribute_text}#{signature}{target_text}{overload_text}"


__all__ = ("primitive_declaration_identity",)
