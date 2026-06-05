from pathlib import Path

from tslgen.backends import (
    BackendTranslatedTypeSpelling,
    translate_backend_type_spelling_request,
    translate_backend_type_spelling_requests,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendLanguageTypeSpelling,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
    BackendTypeKey,
    BackendTypeSpellingText,
)
from tslgen.lowering import (
    BackendTypeSpellingRequest,
    CurrentVector,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LANG_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"


def test_m192_translates_cpp_scalar_identity_through_normalized_metadata_key() -> None:
    request = _request(
        "cpp",
        LoweredScalarTypeIdentity(type_tag="si32"),
        "type<backend>(scalar::si32)",
    )
    catalog = _active_catalog()

    result = translate_backend_type_spelling_request(request, catalog)

    assert result.diagnostics == ()
    assert result.spelling == BackendTranslatedTypeSpelling(
        request=request,
        backend=BackendId("cpp"),
        spelling=BackendTypeSpellingText("int32_t"),
        metadata_kind="language_type",
        metadata_key=BackendTypeKey("s32"),
        metadata_source=SourceLocation(
            (_LANG_ROOT / "types" / "types_cpp.tsl").resolve(),
            4,
            3,
        ),
        source=_location(),
    )


def test_m192_translates_rust_scalar_identity_through_normalized_metadata_key() -> None:
    request = _request(
        "rust",
        LoweredScalarTypeIdentity(type_tag="ui32"),
        "type<backend>(scalar::ui32)",
    )

    result = translate_backend_type_spelling_request(request, _active_catalog())

    assert result.diagnostics == ()
    assert result.spelling is not None
    assert result.spelling.backend == BackendId("rust")
    assert result.spelling.metadata_kind == "language_type"
    assert result.spelling.metadata_key == BackendTypeKey("u32")
    assert result.spelling.spelling == BackendTypeSpellingText("u32")


def test_m192_translates_size_type_through_type_size_translation_metadata() -> None:
    cpp_request = _request("cpp", LoweredSizeType(), "type<backend>(size_t)")
    rust_request = _request("rust", LoweredSizeType(), "type<backend>(size_t)")
    catalog = _active_catalog()

    cpp = translate_backend_type_spelling_request(cpp_request, catalog)
    rust = translate_backend_type_spelling_request(rust_request, catalog)

    assert cpp.diagnostics == ()
    assert rust.diagnostics == ()
    assert cpp.spelling is not None
    assert rust.spelling is not None
    assert cpp.spelling.metadata_kind == "translation_template"
    assert cpp.spelling.metadata_key == BackendTranslationKey("type_size")
    assert cpp.spelling.spelling == BackendTypeSpellingText("std::size_t")
    assert rust.spelling.metadata_kind == "translation_template"
    assert rust.spelling.metadata_key == BackendTranslationKey("type_size")
    assert rust.spelling.spelling == BackendTypeSpellingText("usize")


def test_m192_batch_translation_preserves_request_order() -> None:
    requests = (
        _request("cpp", LoweredScalarTypeIdentity(type_tag="si32"), "first"),
        _request("rust", LoweredSizeType(), "second"),
        _request("cpp", LoweredScalarTypeIdentity(type_tag="f64"), "third"),
    )

    result = translate_backend_type_spelling_requests(requests, _active_catalog())

    assert result.diagnostics == ()
    assert tuple(spelling.request for spelling in result.spellings) == requests
    assert tuple(str(spelling.spelling) for spelling in result.spellings) == (
        "int32_t",
        "usize",
        "double",
    )


def test_m192_reports_missing_backend_metadata_catalog() -> None:
    result = translate_backend_type_spelling_request(
        _request("cpp", LoweredSizeType(), "type<backend>(size_t)"),
        None,
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-METADATA",
    )
    assert result.diagnostics[0].location == _location()


def test_m192_reports_unsupported_backend_id() -> None:
    result = translate_backend_type_spelling_request(
        _request("c17", LoweredSizeType(), "type<backend>(size_t)"),
        _active_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-BACKEND",
    )
    assert "cpp, rust" in result.diagnostics[0].message


def test_m192_reports_unsupported_scalar_tag_before_metadata_lookup() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            LoweredScalarTypeIdentity(type_tag="bool"),
            "type<backend>(scalar::bool)",
        ),
        _active_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-SCALAR-TAG",
    )


def test_m192_reports_missing_scalar_spelling_in_backend_metadata() -> None:
    catalog = BackendMetadataCatalog(
        type_spellings=(),
        translation_templates=(
            _translation("cpp", "type_size", "std::size_t"),
        ),
    )

    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            LoweredScalarTypeIdentity(type_tag="si32"),
            "type<backend>(scalar::si32)",
        ),
        catalog,
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-SCALAR-SPELLING",
    )
    assert "s32" in result.diagnostics[0].message


def test_m192_reports_missing_size_type_translation_in_backend_metadata() -> None:
    catalog = BackendMetadataCatalog(
        type_spellings=(_type_spelling("cpp", "s32", "int32_t"),),
        translation_templates=(),
    )

    result = translate_backend_type_spelling_request(
        _request("cpp", LoweredSizeType(), "type<backend>(size_t)"),
        catalog,
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-SIZE-TYPE",
    )
    assert "type_size" in result.diagnostics[0].message


def test_m192_vector_requests_require_extension_catalog_metadata() -> None:
    result = translate_backend_type_spelling_request(
        _request(
            "cpp",
            CurrentVector(extension="avx2", type_tag="si32"),
            "type<backend>(Vec)",
        ),
        _active_catalog(),
    )

    assert result.spelling is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-TYPE-SPELLING-MISSING-EXTENSION-CATALOG",
    )
    assert "extension catalog" in result.diagnostics[0].message


def _active_catalog() -> BackendMetadataCatalog:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


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


def _type_spelling(
    backend: str,
    key: str,
    spelling: str,
) -> BackendLanguageTypeSpelling:
    return BackendLanguageTypeSpelling(
        backend=BackendId(backend),
        type_key=BackendTypeKey(key),
        spelling=BackendTypeSpellingText(spelling),
        source=_location(),
    )


def _translation(
    backend: str,
    key: str,
    template: str,
) -> BackendTranslationTemplate:
    return BackendTranslationTemplate(
        backend=BackendId(backend),
        key=BackendTranslationKey(key),
        template=BackendTemplateText(template),
        source=_location(),
    )


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("body.tsl"), line, column)


def _codes(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
