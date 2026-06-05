from pathlib import Path

from tslgen.backends import (
    BackendExtensionRegisterTypeKey,
    BackendTranslatedTypeSpelling,
    translate_backend_type_spelling_request,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTypeSpellingText,
)
from tslgen.domain.catalog import ExtensionCatalog, ExtensionName, TypeTag
from tslgen.io.sources import SourceLoader
from tslgen.lowering import (
    BackendTypeSpellingRequest,
    CurrentVector,
    LoweredVectorMemberType,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser


_REPO_ROOT = Path(__file__).resolve().parents[2]
_LANG_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"
_TYPES_TSL = _REPO_ROOT / "tsldata" / "detail" / "types.tsl"
_EXTENSIONS_TSL = _REPO_ROOT / "tsldata" / "extensions" / "extension.tsl"
_TYPE_SPELLING_MODULE = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "backends" / "type_spelling.py"
)


def test_m245_translates_current_vector_register_spelling_from_extension_catalog() -> None:
    backend_catalog = _backend_catalog()
    extension_catalog = _extension_catalog()
    cpp_request = _request(
        "cpp",
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("f32")),
        "type<backend>(Vec)",
    )
    rust_request = _request(
        "rust",
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("f64")),
        "type<backend>(Vec)",
    )

    cpp = translate_backend_type_spelling_request(
        cpp_request,
        backend_catalog,
        extension_catalog=extension_catalog,
    )
    rust = translate_backend_type_spelling_request(
        rust_request,
        backend_catalog,
        extension_catalog=extension_catalog,
    )

    assert cpp.diagnostics == ()
    assert rust.diagnostics == ()
    assert cpp.spelling == BackendTranslatedTypeSpelling(
        request=cpp_request,
        backend=BackendId("cpp"),
        spelling=BackendTypeSpellingText("__m256"),
        metadata_kind="extension_register_type",
        metadata_key=BackendExtensionRegisterTypeKey(
            extension=ExtensionName("avx2"),
            type_tag=TypeTag("f32"),
        ),
        metadata_source=_resolved_register_source(
            extension_catalog,
            "avx2",
            "f32",
            "cpp",
        ),
        source=_location(),
    )
    assert rust.spelling is not None
    assert rust.spelling.spelling == BackendTypeSpellingText(
        "core::arch::x86_64::__m256d"
    )
    assert rust.spelling.metadata_kind == "extension_register_type"
    assert rust.spelling.metadata_key == BackendExtensionRegisterTypeKey(
        extension=ExtensionName("avx2"),
        type_tag=TypeTag("f64"),
    )


def test_m245_translates_vector_register_member_request() -> None:
    request = _request(
        "rust",
        LoweredVectorMemberType(
            member="register",
            extension=ExtensionName("sse"),
            type_tag=TypeTag("si32"),
        ),
        "type<backend>(vector::register)",
    )

    result = translate_backend_type_spelling_request(
        request,
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.diagnostics == ()
    assert result.spelling is not None
    assert result.spelling.spelling == BackendTypeSpellingText(
        "core::arch::x86_64::__m128i"
    )


def test_m245_translates_representative_neon_register_spelling() -> None:
    request = _request(
        "cpp",
        CurrentVector(extension=ExtensionName("neon"), type_tag=TypeTag("si8")),
        "type<backend>(Vec)",
    )

    result = translate_backend_type_spelling_request(
        request,
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.diagnostics == ()
    assert result.spelling is not None
    assert result.spelling.spelling == BackendTypeSpellingText("int8x16_t")


def test_m245_all_resolved_extension_register_facts_translate() -> None:
    backend_catalog = _backend_catalog()
    extension_catalog = _extension_catalog()
    facts = tuple(
        fact
        for extension in extension_catalog.extensions
        for fact in extension.resolved_vector_register_types
    )

    assert len(facts) > 100
    for fact in facts:
        request = _request(
            fact.backend,
            CurrentVector(
                extension=ExtensionName(fact.extension),
                type_tag=TypeTag(fact.type_tag),
            ),
            "type<backend>(Vec)",
        )

        result = translate_backend_type_spelling_request(
            request,
            backend_catalog,
            extension_catalog=extension_catalog,
        )

        assert result.diagnostics == ()
        assert result.spelling is not None
        assert result.spelling.backend == BackendId(fact.backend)
        assert result.spelling.spelling == BackendTypeSpellingText(fact.spelling)
        assert result.spelling.metadata_source == fact.source
        assert result.spelling.metadata_key == BackendExtensionRegisterTypeKey(
            extension=ExtensionName(fact.extension),
            type_tag=TypeTag(fact.type_tag),
        )


def test_m245_reports_missing_extension_catalog_for_vector_requests() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("f32")),
            "type<backend>(Vec)",
        ),
        _backend_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-EXTENSION-CATALOG",
    )


def test_m245_reports_unknown_extension() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            CurrentVector(extension=ExtensionName("missing"), type_tag=TypeTag("f32")),
            "type<backend>(Vec)",
        ),
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-UNKNOWN-EXTENSION",
    )
    assert "missing" in result.diagnostics[0].message


def test_m245_reports_unsupported_vector_member() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            LoweredVectorMemberType(
                member="mask",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f32"),
            ),
            "type<backend>(vector::mask)",
        ),
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-VECTOR-MEMBER",
    )


def test_m245_reports_unsupported_backend_before_extension_lookup() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "c17",
            CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("f32")),
            "type<backend>(Vec)",
        ),
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-BACKEND",
    )


def test_m245_reports_missing_register_spelling_for_known_backend() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "rust",
            CurrentVector(extension=ExtensionName("sve"), type_tag=TypeTag("f32")),
            "type<backend>(Vec)",
        ),
        _backend_catalog(),
        extension_catalog=_extension_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-VECTOR-REGISTER-SPELLING",
    )
    assert "sve" in result.diagnostics[0].message
    assert "f32" in result.diagnostics[0].message


def test_m245_type_spelling_module_has_no_local_register_spelling_table() -> None:
    source = _TYPE_SPELLING_MODULE.read_text(encoding="utf-8")

    assert "resolved_vector_register_types" in source
    for forbidden in (
        "__m128",
        "__m256",
        "__m512",
        "int8x16_t",
        "float32x4_t",
        "svfloat32_t",
        "core::arch::x86_64::__m",
        "core::arch::aarch64",
        "tslgenold",
    ):
        assert forbidden not in source


def _backend_catalog() -> BackendMetadataCatalog:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _extension_catalog() -> ExtensionCatalog:
    source_result = SourceLoader().load((_TYPES_TSL, _EXTENSIONS_TSL))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog.extensions


def _resolved_register_source(
    extension_catalog: ExtensionCatalog,
    extension_name: str,
    type_tag: str,
    backend: str,
) -> SourceLocation:
    extension = extension_catalog.get(extension_name)
    assert extension is not None
    matches = tuple(
        fact
        for fact in extension.resolved_vector_register_types
        if fact.type_tag == type_tag and fact.backend == backend
    )
    assert len(matches) == 1
    return matches[0].source


def _request(
    backend: str,
    value: object,
    source_text: str,
) -> BackendTypeSpellingRequest:
    return BackendTypeSpellingRequest(
        backend=backend,
        value=value,  # type: ignore[arg-type]
        source_text=source_text,
        source=_location(),
    )


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("body.tsl"), line, column)


def _codes(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
