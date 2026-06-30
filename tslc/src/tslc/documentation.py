"""Typed documentation values and language comment formatting."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent

from tslc.catalog.model import ImplementationSafety


@dataclass(frozen=True, slots=True)
class PrimitiveDocumentation:
    """Source-authored primitive documentation metadata.

    The text is documentation-only. It is carried to renderers as raw prose and
    pseudocode, not parsed or lowered as compiler semantics.
    """

    brief: str | None = None
    detailed: str | None = None
    semantics: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentationBlock:
    """A renderer-ready documentation block."""

    brief: str | None = None
    detailed: str | None = None
    semantics: str | None = None
    facts: tuple[tuple[str, str], ...] = ()
    facts_title: str = "Details"


def primitive_documentation(
    *,
    brief: str | None,
    detailed: str | None,
    semantics: str | None,
) -> PrimitiveDocumentation:
    return PrimitiveDocumentation(
        brief=_clean_text(brief),
        detailed=_clean_text(detailed),
        semantics=_clean_text(semantics),
    )


def documentation_block(
    docs: PrimitiveDocumentation,
    *,
    facts: tuple[tuple[str, str], ...] = (),
    facts_title: str = "Details",
) -> DocumentationBlock:
    return DocumentationBlock(
        brief=docs.brief,
        detailed=docs.detailed,
        semantics=docs.semantics,
        facts=tuple((key, value) for key, value in facts if value),
        facts_title=facts_title,
    )


def kind_description(kind: str) -> str:
    return _KIND_DESCRIPTIONS.get(kind, kind)


def result_summary(kind: str, type_spelling: str | None = None) -> str:
    description = kind_description(kind)
    if type_spelling:
        return f"{description} ({type_spelling})"
    return description


def parameter_summary(names: tuple[str, ...], kinds: tuple[str, ...]) -> str:
    if not names:
        return "none"
    return "; ".join(
        f"{name}: {kind_description(kind)}" for name, kind in zip(names, kinds)
    )


def safety_fact(safety: ImplementationSafety) -> str:
    parts = [
        "caller must uphold unsafe preconditions"
        if safety.caller_unsafe
        else "safe to call"
    ]
    if safety.internal_unsafe:
        parts.append("implementation uses unsafe operations internally")
    if safety.reasons:
        parts.append("reasons: " + ", ".join(sorted(safety.reasons)))
    return "; ".join(parts)


def render_cpp_doc(block: DocumentationBlock, *, indent: str = "") -> str:
    lines = _cpp_doc_lines(block)
    if not lines:
        return ""
    rendered = [f"{indent}/**"]
    for line in lines:
        rendered.append(f"{indent} *{(' ' + line) if line else ''}")
    rendered.append(f"{indent} */")
    return "\n".join(rendered)


def render_rust_doc(block: DocumentationBlock, *, indent: str = "") -> str:
    lines = _rust_doc_lines(block)
    if not lines:
        return ""
    return "\n".join(f"{indent}///{(' ' + line) if line else ''}" for line in lines)


def _cpp_doc_lines(block: DocumentationBlock) -> list[str]:
    lines: list[str] = []
    if block.brief:
        brief_lines = block.brief.splitlines()
        lines.append(f"@brief {brief_lines[0]}")
        lines.extend(brief_lines[1:])
    if block.detailed:
        if lines:
            lines.append("")
        lines.extend(block.detailed.splitlines())
    if block.semantics:
        if lines:
            lines.append("")
        lines.append("@par Semantics")
        lines.append("@code")
        lines.extend(block.semantics.splitlines())
        lines.append("@endcode")
    if block.facts:
        if lines:
            lines.append("")
        lines.append(f"@par {block.facts_title}")
        lines.extend(f"- {key}: {value}" for key, value in block.facts)
    return lines


def _rust_doc_lines(block: DocumentationBlock) -> list[str]:
    lines: list[str] = []
    if block.brief:
        lines.extend(block.brief.splitlines())
    if block.detailed:
        if lines:
            lines.append("")
        lines.extend(block.detailed.splitlines())
    if block.semantics:
        if lines:
            lines.append("")
        lines.append("# Semantics")
        lines.append("```text")
        lines.extend(block.semantics.splitlines())
        lines.append("```")
    if block.facts:
        if lines:
            lines.append("")
        lines.append(f"# {block.facts_title}")
        lines.extend(f"- {key}: {value}" for key, value in block.facts)
    return lines


def _clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = dedent(text).strip()
    return cleaned or None


_KIND_DESCRIPTIONS = {
    "v": "SIMD register",
    "s": "scalar value",
    "m": "SIMD mask",
    "im": "integral mask",
    "usize": "size value",
    "sImm": "compile-time immediate",
    "ptr": "mutable element pointer",
    "ptr+": "mutable advancing element pointer",
    "cptr": "const element pointer",
    "cptr+": "const advancing element pointer",
    "void": "no value",
    "s[]": "lane array",
    "lanes<s>": "lane list",
    "vt": "target SIMD register",
    "vidx": "index SIMD register",
    "o": "output stream",
}


__all__ = [
    "DocumentationBlock",
    "PrimitiveDocumentation",
    "documentation_block",
    "kind_description",
    "parameter_summary",
    "primitive_documentation",
    "render_cpp_doc",
    "render_rust_doc",
    "result_summary",
    "safety_fact",
]
