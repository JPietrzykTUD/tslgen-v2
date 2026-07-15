"""Compiler-owned primitive shape discovery and declaration scaffolding."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re

from tslc.catalog.model import Catalog, Primitive

_PRIMITIVE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class PrimitiveShapeChoice:
    signature: str
    parameters: tuple[str, ...]
    declarations: int

    def payload(self) -> dict[str, object]:
        return {
            "signature": self.signature,
            "parameters": list(self.parameters),
            "declarations": self.declarations,
        }


@dataclass(frozen=True, slots=True)
class PrimitiveScaffold:
    insert_text: str
    focus_offset: int

    def payload(self, *, document_version: int | None) -> dict[str, object]:
        return {
            "insertText": self.insert_text,
            "focusOffset": self.focus_offset,
            "documentVersion": document_version,
            "error": None,
        }


def primitive_shape_choices(catalog: Catalog) -> tuple[PrimitiveShapeChoice, ...]:
    """Return corpus-backed shapes with deterministic, idiomatic parameter names."""

    counts: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
    seen: set[tuple[object, ...]] = set()
    for primitive in catalog.primitives:
        identity = _declaration_identity(primitive)
        if identity in seen:
            continue
        seen.add(identity)
        counts[primitive.signature][primitive.parameters] += 1

    return tuple(
        PrimitiveShapeChoice(
            signature=signature,
            parameters=min(
                parameter_counts,
                key=lambda parameters: (-parameter_counts[parameters], parameters),
            ),
            declarations=sum(parameter_counts.values()),
        )
        for signature, parameter_counts in sorted(counts.items())
    )


def primitive_scaffold(
    catalog: Catalog,
    document_text: str,
    *,
    signature: str,
    name: str,
) -> PrimitiveScaffold:
    """Render a new declaration at EOF and point focus into its brief description."""

    choices = {choice.signature: choice for choice in primitive_shape_choices(catalog)}
    choice = choices.get(signature)
    if choice is None:
        raise ValueError(f"unknown primitive signature shape {signature!r}")
    stripped_name = name.strip()
    if _PRIMITIVE_NAME.fullmatch(stripped_name) is None:
        raise ValueError(
            "primitive name must start with a letter or underscore and contain only "
            "letters, digits, and underscores"
        )
    if any(primitive.name == stripped_name for primitive in catalog.primitives):
        raise ValueError(f"primitive {stripped_name!r} already exists")

    separator = _append_separator(document_text)
    parameters = ", ".join(choice.parameters)
    header = f"prim<{choice.signature}> {stripped_name}({parameters}):\n"
    brief_prefix = '  brief_description "'
    declaration = (
        f"{header}"
        f'{brief_prefix}"\n'
        '  detailed_description """\n'
        "    \n"
        '    """\n'
        '  semantics """\n'
        "    \n"
        '    """\n'
    )
    insert_text = separator + declaration
    return PrimitiveScaffold(
        insert_text=insert_text,
        focus_offset=len(separator) + len(header) + len(brief_prefix),
    )


def _declaration_identity(primitive: Primitive) -> tuple[object, ...]:
    source = primitive.header_source or primitive.source
    return (
        primitive.name,
        primitive.signature,
        primitive.parameters,
        None if source is None else source.path,
        None if source is None else source.line,
        None if source is None else source.column,
    )


def _append_separator(text: str) -> str:
    if not text or text.endswith("\n\n"):
        return ""
    if text.endswith("\n"):
        return "\n"
    return "\n\n"


__all__ = (
    "PrimitiveScaffold",
    "PrimitiveShapeChoice",
    "primitive_scaffold",
    "primitive_shape_choices",
)
