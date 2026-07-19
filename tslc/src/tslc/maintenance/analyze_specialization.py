"""CLI adapter for explicit concrete-specialization analysis."""

from __future__ import annotations

import argparse
import json
import sys

from tslc.backend.registry import registered_backend_ids
from tslc.concrete_analysis import (
    ConcreteAnalysis,
    ConcreteAnalysisNode,
    analyze_concrete_specialization,
)
from tslc.diagnostics import (
    diagnostics_json,
    format_diagnostic,
    has_errors,
    span_json,
)
from tslc.maintenance import _repo_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc analyze",
        description=(
            "Analyze one concrete specialization's implementation state and "
            "active lowered call closure without rendering."
        ),
    )
    parser.add_argument("--primitive", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--type", required=True, dest="type_tag")
    parser.add_argument("--extension", required=True)
    parser.add_argument(
        "--to-target",
        default=None,
        help="for a representation-change primitive, the concrete target type/extension",
    )
    parser.add_argument(
        "--backend", default="cpp", choices=registered_backend_ids()
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="corpus root (default: the checkout's tsldata/)",
    )
    parser.add_argument(
        "--machine-profiles",
        default=None,
        help="machine profile catalog (default: the checkout's "
        "supplementary/buildsystem/machine_profiles.json)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    sources, machine_profiles = _repo_context.resolve_corpus_paths(
        parser, args.sources, args.machine_profiles
    )
    analysis, diagnostics = analyze_concrete_specialization(
        sources=sources,
        machine_profiles=machine_profiles,
        primitive=args.primitive,
        profile=args.profile,
        backend=args.backend,
        extension=args.extension,
        type_tag=args.type_tag,
        to_target=args.to_target,
    )
    if args.format == "json":
        payload = diagnostics_json(
            diagnostics,
            extra={
                "kind": "concrete_specialization_analysis",
                "analysis": None if analysis is None else analysis_json(analysis),
            },
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if analysis is not None:
            print(format_analysis_text(analysis))
        for diagnostic in diagnostics:
            print(format_diagnostic(diagnostic), file=sys.stderr)
    return 1 if analysis is None or has_errors(diagnostics) else 0


def analysis_json(analysis: ConcreteAnalysis) -> dict[str, object]:
    context = analysis.context
    return {
        "status": analysis.status,
        "inputDigest": analysis.input_digest,
        "context": {
            "primitive": context.primitive,
            "profile": context.profile,
            "backend": context.backend,
            "extension": context.extension,
            "type": context.type_tag,
            "toTarget": context.to_target,
        },
        "implementationState": analysis.implementation_state.value,
        "roots": [_node_json(node) for node in analysis.roots],
    }


def _node_json(node: ConcreteAnalysisNode) -> dict[str, object]:
    return {
        "status": node.status,
        "primitive": node.primitive,
        "backend": node.backend,
        "extension": node.extension,
        "type": node.type_tag,
        "implementationState": node.implementation_state.value,
        "origin": node.origin,
        "reason": node.reason,
        "parameters": list(node.param_names),
        "parameterKinds": list(node.param_kinds),
        "target": (
            None
            if node.target_extension is None or node.target_type is None
            else {"extension": node.target_extension, "type": node.target_type}
        ),
        "location": (
            None
            if node.source is None
            else {"path": str(node.source.path), "range": span_json(node.source)}
        ),
        "dependencies": [_node_json(child) for child in node.dependencies],
    }


def format_analysis_text(analysis: ConcreteAnalysis) -> str:
    context = analysis.context
    target = f" -> {context.to_target}" if context.to_target is not None else ""
    lines = [
        (
            f"analyzed {context.primitive}<{context.type_tag}{target}> "
            f"({context.profile}/{context.extension}/{context.backend}): "
            f"{analysis.implementation_state.value}"
        ),
        f"input snapshot: sha256:{analysis.input_digest}",
    ]
    for root in analysis.roots:
        _append_node_text(lines, root, depth=0)
    return "\n".join(lines)


def _append_node_text(
    lines: list[str], node: ConcreteAnalysisNode, *, depth: int
) -> None:
    suffix = f" — {node.reason}" if node.reason else ""
    origin = f" [{node.origin}]" if node.origin else ""
    target = (
        ""
        if node.target_extension is None or node.target_type is None
        else f" -> {node.target_type}<{node.target_extension}>"
    )
    lines.append(
        f"{'  ' * depth}- {node.primitive}<{node.extension}, {node.type_tag}>"
        f"{target}{origin}: {node.status}/{node.implementation_state.value}{suffix}"
    )
    for child in node.dependencies:
        _append_node_text(lines, child, depth=depth + 1)


__all__ = ("analysis_json", "format_analysis_text", "main")
