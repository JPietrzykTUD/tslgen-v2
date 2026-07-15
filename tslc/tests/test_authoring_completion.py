"""Parsed cursor-context and catalog-completion behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.authoring_completion import authoring_completions
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser


_PATH = Path("tslctmp/authoring-completion.tsl").resolve()


def test_empty_file_and_primitive_header_complete_declarations_and_shapes(
    catalog: Catalog,
) -> None:
    empty = authoring_cursor_context(_parsed(""), _PATH, "", 0)
    declarations = authoring_completions(empty, catalog)

    assert {item.label for item in declarations} >= {
        "prim",
        "extension",
        "types",
        "language",
        "target_families",
    }
    primitive = next(item for item in declarations if item.label == "prim")
    assert primitive.snippet is True
    assert "${1:v:=v}" in primitive.insert_text

    text = "prim<v"
    header = authoring_cursor_context(None, _PATH, text, len(text))
    shapes = authoring_completions(header, catalog)

    assert shapes
    assert all(item.label.startswith("v") for item in shapes)
    assert all(item.commit_characters == (">",) for item in shapes)


@pytest.mark.parametrize(
    ("baseline", "edited", "included", "excluded"),
    (
        (
            'prim<v:=v> probe(value):\n  brief_description "x"\n',
            "prim<v:=v> probe(value):\n  bri",
            {"brief_description"},
            {"active_when", "si32"},
        ),
        (
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
            "prim<v:=v> probe(value):\n  impls:\n    sca",
            {"scalar"},
            {"arith", "requires"},
        ),
        (
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      ari",
            {"arith"},
            {"scalar", "requires"},
        ),
        (
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        ",
            {"implementation", "safety", "variants"},
            {"requires", "si32", "arith"},
        ),
        (
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        safety:\n          internal_unsafe false\n",
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        safety:\n          internal_unsafe false\n          ",
            {"caller_unsafe", "reasons"},
            {"internal_unsafe", "implementation"},
        ),
        (
            'prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        implementation:\n          tsil "complete(value);"\n',
            "prim<v:=v> probe(value):\n  impls:\n    scalar:\n      arith:\n        implementation:\n          ",
            {"tsl"},
            {"tsil", "requires"},
        ),
        (
            "prim<v:=v> probe(value):\n  generic_params:\n    ToType:\n      kind simd_type\n",
            "prim<v:=v> probe(value):\n  generic_params:\n    ToType:\n      kind simd_type\n      ",
            {"base_types", "constraints", "specialize_base"},
            {"kind", "requires"},
        ),
        (
            "extension sample:\n  active_when:\n    target_features [sse]\n",
            "extension sample:\n  active_when:\n    target_features [sse]\n    ",
            {"compile_modes"},
            {"target_features", "si32"},
        ),
        (
            "extension sample:\n  cpp:\n    supported true\n",
            "extension sample:\n  cpp:\n    supported true\n    ",
            {"headers", "compile_guards", "dataparallel_inference"},
            {"supported", "active_when"},
        ),
    ),
)
def test_parsed_mapping_context_proposes_only_valid_missing_fields(
    catalog: Catalog,
    baseline: str,
    edited: str,
    included: set[str],
    excluded: set[str],
) -> None:
    labels = _labels(catalog, baseline, edited)

    assert included <= labels
    assert labels.isdisjoint(excluded)


def test_requires_and_datatype_lists_use_distinct_vocabularies(
    catalog: Catalog,
) -> None:
    requires_baseline = (
        "prim<v:=v> probe(value):\n"
        "  impls:\n"
        "    avx512:\n"
        "      arith:\n"
        "        requires [avx512f]\n"
    )
    requires_edited = requires_baseline.replace("avx512f]", "avx512_", 1)
    features = _labels(
        catalog,
        requires_baseline,
        requires_edited,
        target_features=("avx512_fp16",),
    )

    assert "avx512_fp16" in features
    assert "si32" not in features
    assert "arith" not in features

    types_baseline = "types:\n  custom {types [si32]}\n"
    types_edited = "types:\n  custom {types [si"
    datatypes = _labels(catalog, types_baseline, types_edited)

    assert {"si8", "si16", "si32", "si64"} <= datatypes
    assert "avx512_fp16" not in datatypes


def test_scoped_requires_selectors_and_repeatable_implementation_branches(
    catalog: Catalog,
) -> None:
    scoped_baseline = (
        "prim<v:=v> probe(value):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        requires:\n"
        "          avx512:\n"
        "            dword [avx512f]\n"
    )
    extension_edit = scoped_baseline.split("          avx512:", 1)[0] + "          avx"
    assert "avx512" in _labels(catalog, scoped_baseline, extension_edit)

    type_edit = scoped_baseline.split("            dword", 1)[0] + "            dwo"
    assert "dword" in _labels(catalog, scoped_baseline, type_edit)

    repeated_type_edit = (
        "prim<v:=v> probe(value):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        requires []\n"
        "      ari"
    )
    assert "arith" in _labels(catalog, scoped_baseline, repeated_type_edit)


def test_inline_test_map_completion_uses_map_fields_and_closed_values(
    catalog: Catalog,
) -> None:
    baseline = (
        "prim<v:=v> probe(value):\n"
        "  tests:\n"
        "    - {tags [basic], type si32, role value, case {inputs [], expected []}}\n"
    )
    field_edit = baseline.split("role value", 1)[0] + "ro"
    fields = _labels(catalog, baseline, field_edit)

    assert "role" in fields
    assert "requires" not in fields

    value_edit = baseline.split("role value", 1)[0] + "role va"
    roles = _labels(catalog, baseline, value_edit)

    assert roles == {"value"}


def test_representation_target_axis_and_where_are_contextual(
    catalog: Catalog,
) -> None:
    target_baseline = (
        "prim<v:=(v,sImm)> extract(value, index):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        ToExtension:\n"
        "          scalar:\n"
        "            requires []\n"
    )
    target_edit = (
        "prim<v:=(v,sImm)> extract(value, index):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        ToExtension:\n"
        "          "
    )
    targets = _labels(catalog, target_baseline, target_edit)

    assert {"avx2", "where"} <= targets
    assert "requires" not in targets

    where_baseline = target_baseline.replace(
        "          scalar:\n            requires []\n",
        "          where:\n            family same_as\n            width smaller_than\n",
    )
    where_edit = where_baseline + "            "
    where_fields = _labels(catalog, where_baseline, where_edit)

    assert {"safety", "implementation", "variants"} <= where_fields
    assert "family" not in where_fields
    assert "width" not in where_fields


def test_results_are_unique_sorted_and_carry_replacement_ranges(
    catalog: Catalog,
) -> None:
    baseline = 'prim<v:=v> probe(value):\n  brief_description "x"\n'
    edited = "prim<v:=v> probe(value):\n  bri"
    context = authoring_cursor_context(_parsed(baseline), _PATH, edited, len(edited))
    completions = authoring_completions(context, catalog)

    labels = [item.label for item in completions]
    assert labels == sorted(set(labels))
    item = next(item for item in completions if item.label == "brief_description")
    assert edited[item.replacement_range.start : item.replacement_range.end] == "bri"
    assert item.detail == "primitive field"


def test_incomplete_line_fallback_keeps_the_anchored_declaration(
    catalog: Catalog,
) -> None:
    baseline = (
        'prim<v:=v> first(value):\n  brief_description "first"\n'
        'prim<v:=v> second(value):\n  brief_description "second"\n'
    )
    edited = (
        'prim<v:=v> first(value):\n  brief_description "first"\n'
        "  # inserted invalid work\n"
        "  # another line\n"
        "  sem"
        'prim<v:=v> second(value):\n  brief_description "second"\n'
    )
    cursor = edited.index("  sem") + len("  sem")
    context = authoring_cursor_context(_parsed(baseline), _PATH, edited, cursor)
    labels = {item.label for item in authoring_completions(context, catalog)}

    assert context.declaration_name == "first"
    assert "semantics" in labels


def _labels(
    catalog: Catalog,
    baseline: str,
    edited: str,
    *,
    target_features: tuple[str, ...] = (),
) -> set[str]:
    offset = len(edited.rstrip("\n"))
    context = authoring_cursor_context(
        _parsed(baseline),
        _PATH,
        edited,
        offset,
    )
    return {
        item.label
        for item in authoring_completions(
            context,
            catalog,
            target_features=target_features,
        )
    }


def _parsed(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return parsed
