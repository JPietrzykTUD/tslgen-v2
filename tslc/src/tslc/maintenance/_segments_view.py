"""Shared views of a scanned TSIL body — the recursive ``Segment`` tree.

Both ``explain`` and ``stage_dump`` render the segment model (``RawText`` vs ``Region``); keeping
the renderers here means the two tools never drift on how they show a body. ``format_segment_tree``
is the human pretty-print; ``segment_to_json`` is the structured form for ``--format json``.
"""

from __future__ import annotations

from tslc.ir.segments import RawText, Segment


def format_segment_tree(segments: tuple[Segment, ...], indent: int = 0) -> list[str]:
    """Indented one-line-per-node pretty-print: raw-text previews and region keyword islands."""

    pad = "  " * indent
    lines: list[str] = []
    for segment in segments:
        if isinstance(segment, RawText):
            text = segment.text.strip()
            if not text:
                lines.append(f"{pad}raw: ⎵(whitespace)")
            else:
                preview = text if len(text) <= 70 else text[:67] + "..."
                lines.append(f"{pad}raw: {preview!r}")
        else:
            selector = f"<{segment.selector_text}>" if segment.selector_text else ""
            term = " ;" if segment.has_statement_terminator else ""
            lines.append(f"{pad}region {segment.keyword}{selector}(...){term}")
            lines.extend(format_segment_tree(segment.body, indent + 1))
            if segment.block:
                lines.append(f"{pad}  {{ block }}")
                lines.extend(format_segment_tree(segment.block, indent + 2))
            if segment.else_block:
                lines.append(f"{pad}  {{ else }}")
                lines.extend(format_segment_tree(segment.else_block, indent + 2))
            if segment.arms:
                for label, arm_body in segment.arms:
                    lines.append(f"{pad}  arm {label} =>")
                    lines.extend(format_segment_tree(arm_body, indent + 2))
    return lines


def segment_to_json(segment: Segment) -> dict:
    """The segment as a JSON-friendly nested dict (raw text kept verbatim)."""

    if isinstance(segment, RawText):
        return {"kind": "raw", "text": segment.text}
    node: dict = {
        "kind": "region",
        "keyword": segment.keyword,
        "selector": segment.selector_text,
        "terminated": segment.has_statement_terminator,
        "body": [segment_to_json(child) for child in segment.body],
    }
    if segment.block:
        node["block"] = [segment_to_json(child) for child in segment.block]
    if segment.else_block:
        node["else_block"] = [segment_to_json(child) for child in segment.else_block]
    if segment.arms:
        node["arms"] = [
            {"label": label, "body": [segment_to_json(child) for child in arm_body]}
            for label, arm_body in segment.arms
        ]
    return node
