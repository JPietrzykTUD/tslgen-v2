from pathlib import Path

from tslgen.backends import (
    BackendTranslatedValue,
    BackendValueText,
    translate_backend_value_request,
    translate_backend_value_requests,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
)
from tslgen.lowering import (
    BackendConstantValueRequest,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendUninitValueRequest,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LANG_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"


def test_m193_translates_cpp_array_uninit_when_template_has_no_placeholders() -> None:
    request = BackendUninitValueRequest(
        backend="cpp",
        kind="array",
        source_text="value<backend>(uninit::array)",
        source=_location(),
    )

    result = translate_backend_value_request(request, _active_catalog())

    assert result.diagnostics == ()
    assert result.value == BackendTranslatedValue(
        request=request,
        backend=BackendId("cpp"),
        value=BackendValueText("{}"),
        metadata_key=BackendTranslationKey("value_array_uninit"),
        metadata_source=SourceLocation(
            (_LANG_ROOT / "translate_cpp.tsl").resolve(),
            80,
            3,
        ),
        source=_location(),
    )


def test_m193_translates_cpp_and_rust_metadata_only_values() -> None:
    catalog = _active_catalog()

    cpp_constant = translate_backend_value_request(
        BackendConstantValueRequest(
            backend="cpp",
            name="x86::mm_fround_to_zero",
            source_text="value<backend>(x86::mm_fround_to_zero)",
            source=_location(),
        ),
        catalog,
    )
    rust_scalar = translate_backend_value_request(
        BackendUninitValueRequest(
            backend="rust",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(),
        ),
        catalog,
    )

    assert cpp_constant.diagnostics == ()
    assert rust_scalar.diagnostics == ()
    assert cpp_constant.value is not None
    assert cpp_constant.value.value == BackendValueText("_MM_FROUND_TO_ZERO")
    assert cpp_constant.value.metadata_key == BackendTranslationKey(
        "value_mm_fround_to_zero"
    )
    assert rust_scalar.value is not None
    assert rust_scalar.value.value == BackendValueText(
        "{ #[allow(invalid_value)] unsafe { "
        "core::mem::MaybeUninit::uninit().assume_init() } }"
    )
    assert rust_scalar.value.metadata_key == BackendTranslationKey("value_uninit")


def test_m193_diagnoses_rust_array_uninit_placeholder_instead_of_formatting() -> None:
    request = BackendUninitValueRequest(
        backend="rust",
        kind="array",
        source_text="value<backend>(uninit::array)",
        source=_location(),
    )

    result = translate_backend_value_request(request, _active_catalog())

    assert result.value is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNRESOLVED-PLACEHOLDER",
    )
    assert "{type}" not in result.diagnostics[0].message
    assert "type" in result.diagnostics[0].message


def test_m193_batch_translation_preserves_request_order_and_accumulates_errors() -> None:
    requests = (
        BackendUninitValueRequest(
            backend="cpp",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(column=1),
        ),
        BackendUninitValueRequest(
            backend="rust",
            kind="array",
            source_text="value<backend>(uninit::array)",
            source=_location(column=40),
        ),
        BackendConstantValueRequest(
            backend="rust",
            name="x86::mm_fround_to_zero",
            source_text="value<backend>(x86::mm_fround_to_zero)",
            source=_location(column=80),
        ),
    )

    result = translate_backend_value_requests(requests, _active_catalog())

    assert tuple(value.request for value in result.values) == (requests[0], requests[2])
    assert tuple(str(value.value) for value in result.values) == (
        "{}",
        "core::arch::x86_64::_MM_FROUND_TO_ZERO",
    )
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNRESOLVED-PLACEHOLDER",
    )
    assert result.diagnostics[0].location == _location(column=40)


def test_m193_reports_missing_backend_metadata_catalog() -> None:
    result = translate_backend_value_request(
        BackendUninitValueRequest(
            backend="cpp",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(),
        ),
        None,
    )

    assert result.value is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-MISSING-METADATA",
    )
    assert result.diagnostics[0].location == _location()


def test_m193_reports_unsupported_backend_id() -> None:
    result = translate_backend_value_request(
        BackendUninitValueRequest(
            backend="c17",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(),
        ),
        _active_catalog(),
    )

    assert result.value is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-BACKEND",
    )
    assert "cpp, rust" in result.diagnostics[0].message


def test_m193_reports_missing_translation_metadata_entry() -> None:
    catalog = BackendMetadataCatalog(
        type_spellings=(),
        translation_templates=(
            _translation("cpp", "value_array_uninit", "{}"),
        ),
    )

    result = translate_backend_value_request(
        BackendUninitValueRequest(
            backend="cpp",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(),
        ),
        catalog,
    )

    assert result.value is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-MISSING-TRANSLATION",
    )
    assert "value_uninit" in result.diagnostics[0].message


def test_m193_reports_unsupported_request_values_without_broadening() -> None:
    suffix = translate_backend_value_request(
        BackendIntrinsicSuffixValueRequest(
            backend="cpp",
            argument=None,
            source_text="value<backend>(intrin::suffix)",
            source=_location(),
        ),
        _active_catalog(),
    )
    prefix = translate_backend_value_request(
        BackendIntrinsicPrefixValueRequest(
            backend="cpp",
            source_text="value<backend>(intrin::prefix)",
            source=_location(),
        ),
        _active_catalog(),
    )

    assert suffix.value is None
    assert prefix.value is None
    assert _codes(suffix.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-REQUEST",
    )
    assert _codes(prefix.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-REQUEST",
    )


def test_m193_reports_unsupported_uninit_and_constant_selectors() -> None:
    catalog = _active_catalog()

    uninit = translate_backend_value_request(
        BackendUninitValueRequest(
            backend="cpp",
            kind="register",  # type: ignore[arg-type]
            source_text="value<backend>(uninit::register)",
            source=_location(),
        ),
        catalog,
    )
    constant = translate_backend_value_request(
        BackendConstantValueRequest(
            backend="cpp",
            name="x86::unknown",  # type: ignore[arg-type]
            source_text="value<backend>(x86::unknown)",
            source=_location(),
        ),
        catalog,
    )

    assert uninit.value is None
    assert constant.value is None
    assert _codes(uninit.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-UNINIT",
    )
    assert _codes(constant.diagnostics) == (
        "TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-CONSTANT",
    )


def _active_catalog() -> BackendMetadataCatalog:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


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
