"""Primitive scaffolding stays catalog-backed and syntactically valid."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.lsp.primitive_scaffold import (
    primitive_scaffold,
    primitive_shape_choices,
)
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def test_primitive_shape_choices_use_corpus_parameter_names(catalog: Catalog) -> None:
    choices = primitive_shape_choices(catalog)

    assert tuple(choice.signature for choice in choices) == tuple(
        sorted(choice.signature for choice in choices)
    )
    binary = next(choice for choice in choices if choice.signature == "v:=(v,v)")
    assert binary.parameters == ("left", "right")
    assert binary.declarations > 0


def test_primitive_scaffold_appends_valid_source_and_focuses_description(
    catalog: Catalog,
) -> None:
    original = 'description "Scaffold test"\n'
    scaffold = primitive_scaffold(
        catalog,
        original,
        signature="v:=(v,v)",
        name="scaffold_probe",
    )
    combined = original + scaffold.insert_text

    assert "prim<v:=(v,v)> scaffold_probe(left, right):" in scaffold.insert_text
    assert scaffold.insert_text.startswith("\n")
    assert combined[
        len(original) + scaffold.focus_offset - 1 :
        len(original) + scaffold.focus_offset + 1
    ] == '""'

    parsed = TslParser(load_default_tsl_grammar()).parse(
        (
            SourceDocument(
                path=Path("scaffold.tsl"),
                text=combined,
                digest="",
                kind="tsl",
            ),
        )
    )
    assert parsed.diagnostics == ()
    assert parsed.documents[0].primitives[-1].name == "scaffold_probe"


def test_primitive_scaffold_rejects_unknown_shapes_and_names(
    catalog: Catalog,
) -> None:
    with pytest.raises(ValueError, match="unknown primitive signature shape"):
        primitive_scaffold(
            catalog,
            "",
            signature="unknown:=(shape)",
            name="probe",
        )
    with pytest.raises(ValueError, match="must start with"):
        primitive_scaffold(
            catalog,
            "",
            signature="v:=(v,v)",
            name="not-valid",
        )
    with pytest.raises(ValueError, match="already exists"):
        primitive_scaffold(
            catalog,
            "",
            signature="v:=(v,v)",
            name="add",
        )
