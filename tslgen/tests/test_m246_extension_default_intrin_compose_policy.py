from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendComposedIntrinsicInvocation,
    BackendIntrinsicComposeDefaultPolicy,
    BackendIntrinsicLiteralFragment,
    BackendIntrinsicNameText,
    BackendTranslatedIntrinsicModifier,
    assemble_backend_intrinsic_invocation,
    resolve_backend_intrinsic_compose_default_policy,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import (
    Catalog,
    ExtensionCatalog,
    ExtensionName,
    Implementation,
    ImplementationBody,
    Primitive,
    TypeTag,
)
from tslgen.io.sources import SourceDocument, SourceLoader
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser


ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
INTRINSIC_INVOCATIONS_MODULE = (
    ROOT / "tslgen" / "src" / "tslgen" / "backends" / "intrinsic_invocations.py"
)
EXTENSION_CATALOG_MODULE = (
    ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "extension_catalog.py"
)


def test_m246_extension_catalog_promotes_default_compose_policy() -> None:
    catalog = _catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)

    avx2 = catalog.extensions.get("avx2")
    assert avx2 is not None
    assert avx2.intrinsic_compose_policy is not None
    assert _prefix(avx2.intrinsic_compose_policy, "cpp") == "_mm256_"
    assert _prefix(avx2.intrinsic_compose_policy, "rust") == (
        "core::arch::x86_64::_mm256_"
    )
    assert _suffix(avx2.intrinsic_compose_policy, "f32") == "ps"
    assert _suffix(avx2.intrinsic_compose_policy, "ui8") == "epu8"

    neon = catalog.extensions.get("neon")
    assert neon is not None
    assert neon.intrinsic_compose_policy is not None
    assert _prefix(neon.intrinsic_compose_policy, "cpp") == ""
    assert _prefix(neon.intrinsic_compose_policy, "rust") == (
        "core::arch::aarch64::"
    )
    assert _suffix(neon.intrinsic_compose_policy, "si32") == "s32"


def test_m246_inherited_extension_policy_is_visible() -> None:
    catalog = _catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)

    avx2 = catalog.extensions.get("avx2")
    avx2_vl = catalog.extensions.get("avx2_vl")
    assert avx2 is not None
    assert avx2_vl is not None
    assert avx2.intrinsic_compose_policy is not None
    assert avx2_vl.intrinsic_compose_policy is not None
    assert _prefix(avx2_vl.intrinsic_compose_policy, "cpp") == "_mm256_"
    assert _suffix(avx2_vl.intrinsic_compose_policy, "si32") == "epi32"


def test_m246_assembles_default_cpp_x86_compose_names_from_extension_policy() -> None:
    extension_catalog = _extension_catalog()

    sse = _assemble_with_default_policy(
        extension_catalog,
        backend="cpp",
        extension="sse",
        type_tag="f32",
    )
    avx2 = _assemble_with_default_policy(
        extension_catalog,
        backend="cpp",
        extension="avx2",
        type_tag="f32",
    )
    avx512 = _assemble_with_default_policy(
        extension_catalog,
        backend="cpp",
        extension="avx512",
        type_tag="si32",
    )

    assert sse.intrinsic_name == BackendIntrinsicNameText("_mm_add_ps")
    assert avx2.intrinsic_name == BackendIntrinsicNameText("_mm256_add_ps")
    assert avx512.intrinsic_name == BackendIntrinsicNameText("_mm512_add_epi32")


def test_m246_assembles_default_rust_x86_compose_name_from_extension_policy() -> None:
    invocation = _assemble_with_default_policy(
        _extension_catalog(),
        backend="rust",
        extension="avx2",
        type_tag="f64",
    )

    assert invocation.intrinsic_name == BackendIntrinsicNameText(
        "core::arch::x86_64::_mm256_add_pd"
    )


def test_m246_assembles_default_neon_compose_name_from_extension_policy() -> None:
    extension_catalog = _extension_catalog()

    cpp = _assemble_with_default_policy(
        extension_catalog,
        text="intrin_compose<vaddq>(left, right)",
        backend="cpp",
        extension="neon",
        type_tag="si32",
    )
    rust = _assemble_with_default_policy(
        extension_catalog,
        text="intrin_compose<vaddq>(left, right)",
        backend="rust",
        extension="neon",
        type_tag="f32",
    )

    assert cpp.intrinsic_name == BackendIntrinsicNameText("vaddq_s32")
    assert rust.intrinsic_name == BackendIntrinsicNameText(
        "core::arch::aarch64::vaddq_f32"
    )


def test_m246_explicit_source_prefix_and_suffix_override_defaults() -> None:
    request = _compose_request(
        "intrin_compose<add, prefix=source_prefix, suffix=source_suffix>"
        "(left, right)"
    )
    policy = _default_policy(
        _extension_catalog(),
        backend="cpp",
        extension="avx2",
        type_tag="f32",
    )
    translations = (
        _translated(
            _field(request, "prefix"),
            BackendIntrinsicLiteralFragment("custom_"),
        ),
        _translated(
            _field(request, "suffix"),
            BackendIntrinsicLiteralFragment("custom_suffix"),
        ),
    )

    result = assemble_backend_intrinsic_invocation(
        request,
        "cpp",
        translations,
        default_compose_policy=policy,
    )

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == BackendIntrinsicNameText(
        "custom_add_custom_suffix"
    )
    assert tuple(part.modifier is not None for part in result.invocation.name_parts) == (
        True,
        False,
        True,
    )


def test_m246_explicit_prefix_only_keeps_default_suffix() -> None:
    request = _compose_request("intrin_compose<add, prefix=source_prefix>(left, right)")
    policy = _default_policy(
        _extension_catalog(),
        backend="cpp",
        extension="avx2",
        type_tag="f32",
    )

    result = assemble_backend_intrinsic_invocation(
        request,
        "cpp",
        (
            _translated(
                _field(request, "prefix"),
                BackendIntrinsicLiteralFragment("custom_"),
            ),
        ),
        default_compose_policy=policy,
    )

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == BackendIntrinsicNameText(
        "custom_add_ps"
    )
    assert tuple(part.modifier is not None for part in result.invocation.name_parts) == (
        True,
        False,
        False,
    )


def test_m246_explicit_suffix_only_keeps_default_prefix() -> None:
    request = _compose_request("intrin_compose<add, suffix=source_suffix>(left, right)")
    policy = _default_policy(
        _extension_catalog(),
        backend="cpp",
        extension="avx2",
        type_tag="f32",
    )

    result = assemble_backend_intrinsic_invocation(
        request,
        "cpp",
        (
            _translated(
                _field(request, "suffix"),
                BackendIntrinsicLiteralFragment("custom_suffix"),
            ),
        ),
        default_compose_policy=policy,
    )

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == BackendIntrinsicNameText(
        "_mm256_add_custom_suffix"
    )
    assert tuple(part.modifier is not None for part in result.invocation.name_parts) == (
        False,
        False,
        True,
    )


def test_m246_reports_default_policy_backend_mismatch() -> None:
    request = _compose_request("intrin_compose<add>(left, right)")
    policy = _default_policy(
        _extension_catalog(),
        backend="cpp",
        extension="avx2",
        type_tag="f32",
    )

    result = assemble_backend_intrinsic_invocation(
        request,
        "rust",
        default_compose_policy=policy,
    )

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-BACKEND-MISMATCH",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == policy.source


def test_m246_resolve_default_policy_diagnostics_are_stable() -> None:
    extension_catalog = _extension_catalog()

    assert _codes(
        resolve_backend_intrinsic_compose_default_policy(
            extension_catalog,
            "c17",
            "avx2",
            "f32",
            _location(),
        ).diagnostics
    ) == ("TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-UNSUPPORTED-BACKEND",)
    assert _codes(
        resolve_backend_intrinsic_compose_default_policy(
            extension_catalog,
            "cpp",
            "missing",
            "f32",
            _location(),
        ).diagnostics
    ) == ("TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-UNKNOWN-EXTENSION",)
    assert _codes(
        resolve_backend_intrinsic_compose_default_policy(
            extension_catalog,
            "cpp",
            "scalar",
            "f32",
            _location(),
        ).diagnostics
    ) == ("TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-POLICY",)
    assert _codes(
        resolve_backend_intrinsic_compose_default_policy(
            extension_catalog,
            "cpp",
            "avx2",
            "bool",
            _location(),
        ).diagnostics
    ) == ("TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-TYPE-SUFFIX",)


def test_m246_reports_missing_backend_prefix_from_policy() -> None:
    catalog = _catalog_from_texts(
        _types_text(),
        (
            "extension.tsl",
            """extension custom:
  extension_name "custom"
  intrinsic_compose:
    prefix:
      cpp "custom_"
    suffix:
      by_type:
        si32 "i32"
""",
        ),
    )

    result = resolve_backend_intrinsic_compose_default_policy(
        catalog.extensions,
        "rust",
        "custom",
        "si32",
        _location(),
    )

    assert result.policy is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-BACKEND-PREFIX",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location is not None


def test_m246_reports_malformed_policy_shape_in_extension_catalog() -> None:
    result = _catalog_result_from_texts(
        _types_text(),
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  intrinsic_compose:
    prefix:
      cpp "broken_"
    suffix:
      si32 "i32"
""",
        ),
    )

    assert result.catalog is None
    assert _codes(result.diagnostics) == (
        "TSL-CATALOG-MALFORMED-INTRINSIC-COMPOSE-POLICY",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location is not None


def test_m246_rejects_wildcard_or_group_suffix_policy_entries() -> None:
    result = _catalog_result_from_texts(
        _types_text(),
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  intrinsic_compose:
    prefix:
      cpp "broken_"
    suffix:
      by_type:
        ?i? "epi32"
""",
        ),
    )

    assert result.catalog is None
    assert _codes(result.diagnostics) == (
        "TSL-CATALOG-UNSUPPORTED-INTRINSIC-COMPOSE-SUFFIX-TYPE",
        "TSL-CATALOG-MALFORMED-INTRINSIC-COMPOSE-POLICY",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location is not None


def test_m246_rejects_unknown_suffix_policy_entries() -> None:
    result = _catalog_result_from_texts(
        _types_text(),
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  intrinsic_compose:
    prefix:
      cpp "broken_"
    suffix:
      by_type:
        si32 "i32"
        f128 "f128"
""",
        ),
    )

    assert result.catalog is None
    assert _codes(result.diagnostics) == (
        "TSL-CATALOG-UNKNOWN-INTRINSIC-COMPOSE-SUFFIX-TYPE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location is not None


def test_m246_backend_modules_have_no_local_intrinsic_spelling_table() -> None:
    source = (
        INTRINSIC_INVOCATIONS_MODULE.read_text(encoding="utf-8")
        + "\n"
        + EXTENSION_CATALOG_MODULE.read_text(encoding="utf-8")
    )

    for forbidden in (
        "_mm256_",
        "core::arch::x86_64::_mm",
        "epi32",
        "vaddq_s32",
        "float32x4_t",
        "tslgenold",
        "frozen/",
    ):
        assert forbidden not in source


def _assemble_with_default_policy(
    extension_catalog: ExtensionCatalog,
    *,
    text: str = "intrin_compose<add>(left, right)",
    backend: str,
    extension: str,
    type_tag: str,
) -> BackendComposedIntrinsicInvocation:
    request = _compose_request(text)
    policy = _default_policy(
        extension_catalog,
        backend=backend,
        extension=extension,
        type_tag=type_tag,
    )
    result = assemble_backend_intrinsic_invocation(
        request,
        backend,
        default_compose_policy=policy,
    )
    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    return result.invocation


def _default_policy(
    extension_catalog: ExtensionCatalog,
    *,
    backend: str,
    extension: str,
    type_tag: str,
) -> BackendIntrinsicComposeDefaultPolicy:
    result = resolve_backend_intrinsic_compose_default_policy(
        extension_catalog,
        backend,
        extension,
        type_tag,
        _location(),
    )
    assert result.diagnostics == ()
    assert result.policy is not None
    return result.policy


def _compose_request(text: str) -> BackendIntrinsicComposeHandoffRequest:
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_intrinsic_discovery(
        _selected(),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    assert isinstance(segment.request, BackendIntrinsicComposeHandoffRequest)
    return segment.request


def _selected() -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="unknown",
        implementations=(implementation,),
        source=source,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _translated(
    field: BackendIntrinsicModifierField,
    value,
    *,
    backend: str = "cpp",
) -> BackendTranslatedIntrinsicModifier:
    return BackendTranslatedIntrinsicModifier(
        backend=BackendId(backend),
        field=field,
        name=field.name,
        value=value,
        source=field.source,
    )


def _field(
    request: BackendIntrinsicComposeHandoffRequest,
    name: str,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == name)
    assert len(matches) == 1
    return matches[0]


def _catalog_from_paths(*paths: Path) -> Catalog:
    source_result = SourceLoader().load(tuple(paths))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _extension_catalog() -> ExtensionCatalog:
    return _catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL).extensions


def _catalog_from_texts(*documents: tuple[str, str]) -> Catalog:
    result = _catalog_result_from_texts(*documents)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _catalog_result_from_texts(*documents: tuple[str, str]):
    sources = tuple(
        SourceDocument(
            path=Path(name),
            text=text,
            digest="",
            kind="tsl",
        )
        for name, text in documents
    )
    parse_result = TslParser().parse(sources)
    assert parse_result.diagnostics == ()
    return CatalogBuilder().build(parse_result.documents)


def _types_text() -> tuple[str, str]:
    return (
        "types.tsl",
        """types:
  ?i? {types [si32]}
  si32 {types [si32]}
""",
    )


def _prefix(policy, backend: str) -> str:
    matches = tuple(item for item in policy.prefixes if item.backend == backend)
    assert len(matches) == 1
    return matches[0].spelling


def _suffix(policy, type_tag: str) -> str:
    matches = tuple(
        item for item in policy.suffixes if item.type_tag == TypeTag(type_tag)
    )
    assert len(matches) == 1
    return matches[0].suffix


def _codes(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(path=Path("fixture.tsl"), line=line, column=column)
