"""Parsed cursor-context and catalog-completion behavior."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.authoring_completion import AuthoringCompletion, authoring_completions
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS, TSIL_REGION_KEYWORDS


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
        "overload_axes",
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


def test_primitive_overload_completion_is_registry_backed_and_axis_scoped(
    catalog: Catalog,
) -> None:
    baseline = (
        "prim<v:=(v,s)> probe(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
    )

    incomplete_root = "prim<v:=(v,s)> probe(data, count):\n  over"
    assert "overload" in _labels(catalog, baseline, incomplete_root)

    missing_baseline = baseline.replace("    value uniform\n", "")
    missing_field = missing_baseline + "    "
    fields = _labels(catalog, missing_baseline, missing_field)
    assert "value" in fields
    assert "axis" not in fields
    assert "primary" not in fields

    axis_edit = baseline.split("    axis count_distribution", 1)[0] + "    axis pay"
    assert _labels(catalog, baseline, axis_edit) == {"payload_extent"}

    count_value_edit = baseline.split("    value uniform", 1)[0] + "    value "
    assert _labels(catalog, baseline, count_value_edit) == {"per_lane", "uniform"}

    payload_baseline = baseline.replace("count_distribution", "payload_extent").replace(
        "uniform", "vector"
    )
    payload_value_edit = (
        payload_baseline.split("    value vector", 1)[0] + "    value "
    )
    assert _labels(catalog, payload_baseline, payload_value_edit) == {
        "scalar",
        "vector",
    }

    unknown_baseline = baseline.replace("count_distribution", "not_registered")
    unknown_value_edit = (
        unknown_baseline.split("    value uniform", 1)[0] + "    value "
    )
    assert _labels(catalog, unknown_baseline, unknown_value_edit) == set()

    primary_edit = baseline.split("    primary true", 1)[0] + "    primary "
    assert _labels(catalog, baseline, primary_edit) == {"false", "true"}


def test_overload_registry_completion_reuses_schema_and_typed_registry(
    catalog: Catalog,
) -> None:
    baseline = (
        "overload_axes:\n"
        "  count_distribution:\n"
        "    values:\n"
        "      uniform:\n"
        "        operand_kinds [s, sImm]\n"
        "      per_lane:\n"
        "        operand_kinds [v]\n"
    )

    assert "payload_extent" in _labels(catalog, baseline, "overload_axes:\n  pay")
    assert _labels(
        catalog,
        baseline,
        "overload_axes:\n  count_distribution:\n    val",
    ) == {"values"}
    values_baseline = baseline.replace(
        "      per_lane:\n        operand_kinds [v]\n",
        "",
    )
    assert _labels(
        catalog,
        values_baseline,
        "overload_axes:\n  count_distribution:\n    values:\n      per",
    ) == {"per_lane"}
    assert _labels(
        catalog,
        baseline,
        (
            "overload_axes:\n"
            "  count_distribution:\n"
            "    values:\n"
            "      uniform:\n"
            "        oper"
        ),
    ) == {"operand_kinds"}

    kind_edit = baseline.replace("operand_kinds [s, sImm]", "operand_kinds [sI")
    assert "sImm" in _labels(catalog, baseline, kind_edit)


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

    width_edit = where_baseline.replace("width smaller_than", "width tw")
    assert "twice_as_wide" in _labels(catalog, where_baseline, width_edit)


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


def test_every_registered_region_completes_at_a_valid_tsil_boundary(
    catalog: Catalog,
) -> None:
    labels = _tsil_labels(catalog, "")

    assert labels == TSIL_REGION_KEYWORDS
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS:
        prefix = descriptor.keyword[: max(1, len(descriptor.keyword) - 1)]
        assert descriptor.keyword in _tsil_labels(catalog, prefix)


@pytest.mark.parametrize(
    ("body", "included"),
    (
        ("intrin<name, b", {"build"}),
        ("intrin<name, build[s", {"suffix"}),
        ("intrin<name, build[i", {"immediate", "infix", "infix_sep"}),
        (
            "helper<arith_",
            {
                "arith_add",
                "arith_div",
                "arith_mul",
                "arith_rem",
                "arith_zero_divisor_fail",
            },
        ),
        ("op<a", {"add"}),
        ("var<const_", {"const_infer", "const_typed", "const_init_register"}),
        ("let<t", {"type"}),
        ("mask<t", {"test"}),
        ("mask<test, i", {"imask"}),
        ("mem<a", {"alloc", "alloc_aligned"}),
        ("lanes<a", {"at"}),
        ("array<s", {"set"}),
        ("io<f", {"format"}),
        ("cast<st", {"static"}),
        ("cast<reinterpret, t", {"type"}),
        ("cast<reinterpret, type=p", {"ptr"}),
        ("call<p", {"primitive"}),
        ("call<primitive=ad", {"add"}),
        ("call<primitive=add, a", {"attrs"}),
        ("call<primitive=add, attrs[m", {"mask"}),
        ("call<primitive=add, attrs[mask=p", {"pass_through"}),
        ("call<primitive=add, attrs[aligned=t", {"true"}),
        ("if<g", {"generation"}),
        ("loop<b", {"backend"}),
        ("loop<backend, u", {"unroll"}),
        ("loop<generation, s", {"scoped"}),
        ("switch<c", {"compile"}),
    ),
)
def test_registered_region_shells_complete_from_authoring_descriptors(
    catalog: Catalog,
    body: str,
    included: set[str],
) -> None:
    assert included <= _tsil_labels(catalog, body)


def test_region_shell_completion_uses_precise_replacement_ranges(
    catalog: Catalog,
) -> None:
    text, records = _tsil_completion_case(catalog, "call<primitive=ad")
    add = next(record for record in records if record.label == "add")

    assert text[add.replacement_range.start : add.replacement_range.end] == "ad"
    assert add.insert_text == "add"
    assert add.kind == "function"

    text, records = _tsil_completion_case(
        catalog,
        "call<primitive=add, attrs[mask=pa",
    )
    pass_through = next(record for record in records if record.label == "pass_through")

    assert (
        text[
            pass_through.replacement_range.start : pass_through.replacement_range.end
        ]
        == "pa"
    )


def test_inline_tsl_escapes_do_not_hide_later_tsil_completion(
    catalog: Catalog,
) -> None:
    prefix = (
        "prim<v:=v> probe(value):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil "'
    )
    baseline = prefix + r'complete(\"value\");' + '"\n'
    edited = prefix + r'complete(\"value\" + cal'
    context = authoring_cursor_context(
        _parsed(baseline),
        _PATH,
        edited,
        len(edited),
    )

    assert "call" in {
        record.label for record in authoring_completions(context, catalog)
    }


def test_typed_query_paths_complete_and_stop_at_terminal_or_invalid_paths(
    catalog: Catalog,
) -> None:
    text, records = _tsil_completion_case(catalog, "complete(base::s")
    signed = next(record for record in records if record.label == "signed_of")

    assert text[signed.replacement_range.start : signed.replacement_range.end] == "s"
    assert signed.detail == "TSIL query (type) → type"
    assert "select" not in {record.label for record in records}

    scalar_labels = _tsil_labels(
        catalog,
        "complete(type::is_same(base::in, scalar::s",
    )
    assert {"si8", "si16", "si32", "si64"} <= scalar_labels
    assert "signed_of" not in scalar_labels

    assert _tsil_labels(catalog, "complete(vector::length") == set()
    assert _tsil_labels(catalog, "complete(vector::bogus") == set()


def test_query_completion_uses_primitive_generic_and_selector_scope(
    catalog: Catalog,
) -> None:
    opener = (
        "prim<v:=v>[aligned=*] scoped_probe(data):\n"
        "  generic_params:\n"
        "    IndexVec {kind simd_type}\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil """'
    )
    baseline = opener + "\n            complete(data);\n          \"\"\"\n"

    def records(body: str) -> tuple[AuthoringCompletion, ...]:
        edited = opener + "\n            " + body
        context = authoring_cursor_context(
            _parsed(baseline),
            _PATH,
            edited,
            len(edited),
        )
        return authoring_completions(context, catalog)

    parameter = next(record for record in records("complete(da") if record.label == "data")
    generic = next(
        record
        for record in records("complete(generic::length(In")
        if record.label == "IndexVec"
    )
    attribute = next(
        record
        for record in records("complete(primitive::attribute(al")
        if record.label == "aligned"
    )

    assert parameter.detail == "primitive parameter"
    assert generic.detail == "generic parameter (simd_type)"
    assert attribute.detail == "primitive selector axis"


def test_parameter_completion_requires_reliable_primitive_scope(
    catalog: Catalog,
) -> None:
    opener = (
        "prim<v:=v> local_probe(local_value):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil """'
    )
    baseline = opener + "\n            complete(local_value);\n          \"\"\"\n"
    edited = opener + "\n            complete(local_"
    context = authoring_cursor_context(
        _parsed(baseline),
        _PATH,
        edited,
        len(edited),
    )

    assert "local_value" in {
        record.label for record in authoring_completions(context, catalog)
    }
    unreliable = replace(
        context,
        declaration_name=None,
        primitive_parameters=(),
        primitive_attributes=(),
        generic_parameters=(),
    )
    assert "local_value" not in {
        record.label for record in authoring_completions(unreliable, catalog)
    }


def test_intrinsic_build_query_values_use_the_same_typed_query_index(
    catalog: Catalog,
) -> None:
    for body in (
        "intrin<name, build[suffix=base::s",
        "intrin<name, build[immediate(2)=base::s",
    ):
        text, records = _tsil_completion_case(catalog, body)
        signed = next(record for record in records if record.label == "signed_of")

        assert text[signed.replacement_range.start : signed.replacement_range.end] == "s"
        assert signed.detail == "TSIL query (type) → type"


@pytest.mark.parametrize(
    "body",
    (
        "target_identifier ",
        "complete(target_identifier ",
        'complete("cal',
        "complete(/* cal",
        "// cal",
        "call<bogus, a",
        "call<primitive=add, unknown[x",
        "mask<test, wrong",
        "select_expr<",
    ),
)
def test_tsil_completion_stops_at_raw_or_invalid_shell_text(
    catalog: Catalog,
    body: str,
) -> None:
    assert _tsil_labels(catalog, body) == set()


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


def _tsil_labels(catalog: Catalog, body: str) -> set[str]:
    _text, records = _tsil_completion_case(catalog, body)
    return {record.label for record in records}


def _tsil_completion_case(
    catalog: Catalog,
    body: str,
) -> tuple[str, tuple[AuthoringCompletion, ...]]:
    opener = (
        "prim<v:=v> probe(value):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil """'
    )
    baseline = opener + '\n            complete(value);\n          """\n'
    edited = opener + "\n            " + body
    context = authoring_cursor_context(
        _parsed(baseline),
        _PATH,
        edited,
        len(edited),
    )
    return edited, authoring_completions(context, catalog)


def _parsed(text: str):
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return parsed
