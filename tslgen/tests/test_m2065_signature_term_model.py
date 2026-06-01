from __future__ import annotations

import re
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Implementation, ImplementationBody, Primitive
from tslgen.domain.signatures import (
    PrimitiveSignature,
    SignatureParameterTerm,
    SignatureTerm,
    SignatureTermKind,
    parse_primitive_signature,
    signature_parameter_terms,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import build_selected_implementation_lowering_context
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedPrimitive,
    ParsedRawStringLine,
)
from tslgen.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBSERVED_SIGNATURES = (
    "m:=()",
    "m:=(m,m)",
    "m:=(m,s)",
    "m:=(m,v)",
    "m:=(m,v,v)",
    "m:=(m,v,v,v)",
    "m:=(v,v)",
    "m:=(v,v,v)",
    "m:=m",
    "m:=ptr",
    "m:=s",
    "m:=v",
    "o:=(o,v,s)",
    "ptr:=(s)",
    "ptr:=(s,s)",
    "s:=(m,v)",
    "s:=(s,s)",
    "s:=(s,s,s)",
    "s:=(v,s)",
    "s:=m",
    "s:=ptr",
    "s:=s",
    "s:=v",
    "s:=v[idx]",
    "s[]:=v",
    "v:=()",
    "v:=(m,ptr)",
    "v:=(m,ptr,v)",
    "v:=(m,ptr,vidx,v,sImm)",
    "v:=(m,v)",
    "v:=(m,v,s)",
    "v:=(m,v,sImm)",
    "v:=(m,v,v)",
    "v:=(m,v,v,v)",
    "v:=(ptr,vidx,sImm)",
    "v:=(s,s)",
    "v:=(v,s)",
    "v:=(v,sImm)",
    "v:=(v,v)",
    "v:=(v,v,sImm)",
    "v:=m",
    "v:=ptr",
    "v:=ptr+",
    "v:=s",
    "v:=s...",
    "v:=s[]",
    "v:=sequence",
    "v:=v",
    "void:=(m,ptr,v)",
    "void:=(m,ptr,vidx,v,sImm)",
    "void:=(ptr)",
    "void:=(ptr,m)",
    "void:=(ptr,ptr,s,s)",
    "void:=(ptr,s)",
    "void:=(ptr,v)",
    "void:=(ptr,vidx,v,sImm)",
)


def test_m2065_signature_values_are_dataclasses_and_enums() -> None:
    assert is_dataclass(SignatureTerm)
    assert is_dataclass(PrimitiveSignature)
    assert is_dataclass(SignatureParameterTerm)
    assert issubclass(SignatureTermKind, Enum)
    assert SignatureTermKind.SCALAR_IMMEDIATE.value == "sImm"


def test_m2065_parses_every_observed_corpus_signature() -> None:
    observed = _corpus_signatures()

    assert observed == _OBSERVED_SIGNATURES
    for signature_text in observed:
        result = parse_primitive_signature(signature_text, _location())
        assert result.diagnostics == (), signature_text
        assert result.signature is not None
        assert result.signature.source_text == signature_text


def test_m2065_signature_parser_preserves_immediate_term_kind() -> None:
    result = parse_primitive_signature("v:=(v,sImm)", _location())

    assert result.diagnostics == ()
    assert result.signature == PrimitiveSignature(
        result=SignatureTerm(SignatureTermKind.VECTOR, "v"),
        parameters=(
            SignatureTerm(SignatureTermKind.VECTOR, "v"),
            SignatureTerm(SignatureTermKind.SCALAR_IMMEDIATE, "sImm"),
        ),
        source_text="v:=(v,sImm)",
    )


def test_m2065_catalog_promotes_accepted_header_to_typed_signature(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "tiny_add.tsl",
        """prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    body add(left, right)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitive = catalog_result.catalog.primitives[0]
    assert primitive.signature == "v:=(v,v)"
    assert primitive.signature_model == PrimitiveSignature(
        result=SignatureTerm(SignatureTermKind.VECTOR, "v"),
        parameters=(
            SignatureTerm(SignatureTermKind.VECTOR, "v"),
            SignatureTerm(SignatureTermKind.VECTOR, "v"),
        ),
        source_text="v:=(v,v)",
    )
    assert tuple(
        (binding.name, binding.term.kind)
        for binding in primitive.parameter_signature_terms
    ) == (
        ("left", SignatureTermKind.VECTOR),
        ("right", SignatureTermKind.VECTOR),
    )


def test_m2065_catalog_binds_simm_terms_from_parsed_signature() -> None:
    parsed = ParsedDocument(
        path="fixture.tsl",
        primitives=(
            ParsedPrimitive(
                name="convert_up",
                signature="v:=(v,sImm)",
                parameters=("data", "index"),
                implementations=(
                    ParsedImplementation(
                        extension="scalar",
                        type_tag="si32",
                        body=ParsedImplementationBody(
                            lines=(
                                ParsedRawStringLine(
                                    text="emit_return(data);",
                                    source=_location(3, 5),
                                ),
                            ),
                            source=_location(3, 5),
                            envelope=PARSED_TSIL_BODY_ENVELOPE,
                        ),
                        source=_location(2, 3),
                    ),
                ),
                source=_location(),
            ),
        ),
    )

    catalog_result = CatalogBuilder().build((parsed,))

    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitive = catalog_result.catalog.primitives[0]
    assert primitive.template == "unknown"
    assert primitive.signature_model == _signature("v:=(v,sImm)")
    assert tuple(
        (binding.name, binding.term.kind)
        for binding in primitive.parameter_signature_terms
    ) == (
        ("data", SignatureTermKind.VECTOR),
        ("index", SignatureTermKind.SCALAR_IMMEDIATE),
    )


def test_m2065_selected_context_exposes_parameter_signature_terms() -> None:
    signature = _signature("v:=(v,sImm)")
    parameter_terms = signature_parameter_terms(
        signature,
        ("data", "index"),
        _location(),
    )
    assert parameter_terms.diagnostics == ()
    selected = _selected(
        signature=signature,
        parameter_terms=parameter_terms.bindings,
        parameter_names=("data", "index"),
    )

    context = build_selected_implementation_lowering_context(selected)

    assert context.signature_model is signature
    assert tuple(
        (binding.name, binding.term.kind)
        for binding in context.parameter_signature_terms
    ) == (
        ("data", SignatureTermKind.VECTOR),
        ("index", SignatureTermKind.SCALAR_IMMEDIATE),
    )


def test_m2065_parameter_names_do_not_define_immediacy() -> None:
    runtime_signature = _signature("v:=(v,v)")
    runtime_terms = signature_parameter_terms(
        runtime_signature,
        ("data", "index"),
        _location(),
    )
    immediate_signature = _signature("v:=(v,sImm)")
    immediate_terms = signature_parameter_terms(
        immediate_signature,
        ("data", "anything"),
        _location(),
    )

    assert runtime_terms.diagnostics == ()
    assert runtime_terms.bindings[1].name == "index"
    assert runtime_terms.bindings[1].term.kind is SignatureTermKind.VECTOR
    assert immediate_terms.diagnostics == ()
    assert immediate_terms.bindings[1].name == "anything"
    assert immediate_terms.bindings[1].term.kind is SignatureTermKind.SCALAR_IMMEDIATE


def test_m2065_rejects_unknown_signature_terms() -> None:
    result = parse_primitive_signature("v:=(v,unknown)", _location())

    assert result.signature is None
    assert _codes(result.diagnostics) == ("TSL-SIGNATURE-UNKNOWN-TERM",)
    assert "unknown" in result.diagnostics[0].message


def test_m2065_rejects_parameter_count_mismatch() -> None:
    result = signature_parameter_terms(
        _signature("v:=(v,sImm)"),
        ("data",),
        _location(),
    )

    assert result.bindings == ()
    assert _codes(result.diagnostics) == (
        "TSL-SIGNATURE-PARAMETER-COUNT-MISMATCH",
    )


def _signature(text: str) -> PrimitiveSignature:
    result = parse_primitive_signature(text, _location())
    assert result.diagnostics == ()
    assert result.signature is not None
    return result.signature


def _corpus_signatures() -> tuple[str, ...]:
    signatures: set[str] = set()
    pattern = re.compile(r"prim<(?P<signature>[^>]+)>")
    for path in sorted((_REPO_ROOT / "tsldata" / "primitives").rglob("*.tsl")):
        text = path.read_text(encoding="utf-8")
        signatures.update(match.group("signature") for match in pattern.finditer(text))
    return tuple(sorted(signatures))


def _selected(
    *,
    signature: PrimitiveSignature,
    parameter_terms: tuple[SignatureParameterTerm, ...],
    parameter_names: tuple[str, ...],
) -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature=signature.source_text,
        parameters=parameter_names,
        template="unknown",
        implementations=(implementation,),
        source=source,
        signature_model=signature,
        parameter_signature_terms=parameter_terms,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="scalar",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    return SourceDocument(
        path=(tmp_path / name).resolve(),
        text=text,
        digest="test-digest",
        kind="tsl",
    )


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
