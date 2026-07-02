"""Tests for the stage-dump pipeline inspector (maintenance/stage_dump.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.ir.scan import scan
from tslc.maintenance._segments_view import format_segment_tree, segment_to_json
from tslc.maintenance.stage_dump import run


def _run(stage: str, data_root: Path, machine_profiles_path: Path, **kwargs):
    return run(
        stage=stage,
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive=kwargs.get("primitive"),
        profile=kwargs.get("profile"),
        backend=kwargs.get("backend", "cpp"),
        type_tag=kwargs.get("type_tag"),
        extension=kwargs.get("extension"),
    )


# --------------------------------------------------------------------------- shared view


def test_segment_view_text_and_json_agree_on_structure() -> None:
    segments = scan("complete(intrin<add, build>(left, right));")
    text = format_segment_tree(segments)
    assert any("region complete" in line for line in text)
    assert any("region intrin<add, build>" in line for line in text)

    root = segment_to_json(segments[0])
    assert root["kind"] == "region" and root["keyword"] == "complete"
    assert root["terminated"] is True
    inner = [c for c in root["body"] if c["kind"] == "region"]
    assert inner and inner[0]["keyword"] == "intrin"


def test_segment_view_captures_loop_block_not_raw() -> None:
    # the design-central check: a recognized keyword island is a Region, not leaked RawText
    body = "loop<backend, unroll>(i, 0, value(n), 1) { result[i] = 0; }"
    root = segment_to_json(scan(body)[0])
    assert root["kind"] == "region" and root["keyword"] == "loop"
    assert root["block"]  # the { ... } body was captured


# --------------------------------------------------------------------------- catalog


def test_catalog_lists_primitive_and_implementations(
    data_root: Path, machine_profiles_path: Path
) -> None:
    text, payload, errors = _run("catalog", data_root, machine_profiles_path, primitive="add")
    assert errors == []
    assert "primitive add" in text
    names = {p["name"] for p in payload["primitives"]}
    assert names == {"add"}
    assert all(p["implementations"] for p in payload["primitives"])


def test_catalog_unknown_primitive_errors(
    data_root: Path, machine_profiles_path: Path
) -> None:
    _text, _payload, errors = _run("catalog", data_root, machine_profiles_path, primitive="nonesuch")
    assert errors and "nonesuch" in errors[0]


# --------------------------------------------------------------------------- segments


def test_segments_dumps_body_trees(data_root: Path, machine_profiles_path: Path) -> None:
    text, payload, errors = _run(
        "segments", data_root, machine_profiles_path, primitive="add", extension="avx2"
    )
    assert errors == []
    assert payload["stage"] == "segments"
    assert "region complete" in text
    # avx2 add lowers to an intrin call — visible in the tree
    assert "region intrin" in text


def test_segments_unknown_extension_errors(
    data_root: Path, machine_profiles_path: Path
) -> None:
    _text, _payload, errors = _run(
        "segments", data_root, machine_profiles_path, primitive="add", extension="nope"
    )
    assert errors


# --------------------------------------------------------------------------- selection


def test_selection_lists_slots_for_profile(
    data_root: Path, machine_profiles_path: Path
) -> None:
    text, payload, errors = _run(
        "selection", data_root, machine_profiles_path, profile="avx2", primitive="add", type_tag="si32"
    )
    assert errors == []
    slots = {(s["primitive"], s["extension"], s["type"]) for s in payload["slots"]}
    assert ("add", "avx2", "si32") in slots
    assert "body=[avx2 / ?i?]" in text


def test_selection_unknown_profile_errors(
    data_root: Path, machine_profiles_path: Path
) -> None:
    _text, _payload, errors = _run(
        "selection", data_root, machine_profiles_path, profile="nope", primitive="add"
    )
    assert errors and "nope" in errors[0]


# --------------------------------------------------------------------------- lowered


def test_lowered_shows_resolved_intrinsic_and_register(
    data_root: Path, machine_profiles_path: Path
) -> None:
    text, payload, errors = _run(
        "lowered",
        data_root,
        machine_profiles_path,
        profile="avx2",
        backend="cpp",
        primitive="add",
        type_tag="si32",
        extension="avx2",
    )
    assert errors == []
    spec = next(s for s in payload["specializations"] if s["slot"].startswith("add<avx2"))
    assert spec["lowered"] is True
    assert spec["register"] == "typename tsl::simd<int32_t, tsl::avx2>::register_type"
    assert spec["body"] == "return _mm256_add_epi32(left, right);"
    assert "epi32" in text


def test_lowered_rust_backend_differs(data_root: Path, machine_profiles_path: Path) -> None:
    _text, payload, errors = _run(
        "lowered",
        data_root,
        machine_profiles_path,
        profile="avx2",
        backend="rust",
        primitive="add",
        type_tag="si32",
        extension="avx2",
    )
    assert errors == []
    spec = next(s for s in payload["specializations"] if s["slot"].startswith("add<avx2"))
    # Rust qualifies the intrinsic via core::arch
    assert "core::arch" in spec["body"]
