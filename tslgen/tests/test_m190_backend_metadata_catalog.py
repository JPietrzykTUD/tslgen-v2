from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendLanguageTypeSpelling,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
    BackendTypeKey,
    BackendTypeSpellingText,
)
from tslgen.pipeline.backend_metadata import (
    load_active_backend_metadata_catalog,
    load_backend_metadata_catalog,
    parse_backend_translation_map,
    parse_backend_type_map,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LANG_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"


def test_m190_loads_active_cpp_and_rust_metadata_as_typed_facts() -> None:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)

    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.catalog.backends == (BackendId("cpp"), BackendId("rust"))
    assert {str(item.backend) for item in result.catalog.type_spellings} == {
        "cpp",
        "rust",
    }
    assert {str(item.backend) for item in result.catalog.translation_templates} == {
        "cpp",
        "rust",
    }
    assert "c17" not in {str(backend) for backend in result.catalog.backends}

    cpp_s32 = result.catalog.type_spelling("cpp", "s32")
    assert cpp_s32.diagnostics == ()
    assert cpp_s32.value == BackendLanguageTypeSpelling(
        backend=BackendId("cpp"),
        type_key=BackendTypeKey("s32"),
        spelling=BackendTypeSpellingText("int32_t"),
        source=SourceLocation(
            (_LANG_ROOT / "types" / "types_cpp.tsl").resolve(),
            4,
            3,
        ),
    )

    rust_ptr = result.catalog.type_spelling("rust", "ptr")
    assert rust_ptr.diagnostics == ()
    assert rust_ptr.value is not None
    assert rust_ptr.value.spelling == BackendTypeSpellingText(
        "*mut core::ffi::c_void"
    )

    cpp_call = result.catalog.translation_template("cpp", "call")
    assert cpp_call.diagnostics == ()
    assert cpp_call.value == BackendTranslationTemplate(
        backend=BackendId("cpp"),
        key=BackendTranslationKey("call"),
        template=BackendTemplateText("::tsl::{name}<Vec>({args})"),
        source=SourceLocation((_LANG_ROOT / "translate_cpp.tsl").resolve(), 2, 3),
    )


def test_m190_preserves_rust_multiline_translation_without_evaluating_it() -> None:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None

    preamble = result.catalog.translation_template("rust", "preamble")

    assert preamble.diagnostics == ()
    assert preamble.value is not None
    assert str(preamble.value.template).startswith(
        "  #![allow(non_upper_case_globals)]\n"
    )
    assert "pub trait SimdVector" in preamble.value.template
    assert "pub fn arith_add<T: TslArith>(a: T, b: T) -> T" in preamble.value.template


def test_m190_templates_remain_inert_raw_template_text() -> None:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None

    rust_array = result.catalog.translation_template("rust", "array_type_aligned")

    assert rust_array.diagnostics == ()
    assert rust_array.value is not None
    assert rust_array.value.template == BackendTemplateText(
        "crate::tsl::Aligned::<{ {align} }, [{type}; {size}]>"
    )


def test_m190_unknown_lookup_returns_diagnostic_not_key_error() -> None:
    result = load_active_backend_metadata_catalog(_LANG_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None

    missing_type = result.catalog.type_spelling("cpp", "missing")
    missing_translation = result.catalog.translation_template("rust", "missing")

    assert missing_type.value is None
    assert [diagnostic.code for diagnostic in missing_type.diagnostics] == [
        "TSL-BACKEND-METADATA-UNKNOWN-TYPE-SPELLING"
    ]
    assert missing_translation.value is None
    assert [diagnostic.code for diagnostic in missing_translation.diagnostics] == [
        "TSL-BACKEND-METADATA-UNKNOWN-TRANSLATION"
    ]


def test_m190_duplicate_type_entries_are_diagnostics(tmp_path: Path) -> None:
    first = tmp_path / "types_cpp_a.tsl"
    second = tmp_path / "types_cpp_b.tsl"
    first.write_text('language cpp:\n  s32 {type "int32_t"}\n', encoding="utf-8")
    second.write_text('language cpp:\n  s32 {type "other"}\n', encoding="utf-8")

    result = load_backend_metadata_catalog((first, second), ())

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-METADATA-DUPLICATE-TYPE"
    ]
    assert result.diagnostics[0].location == SourceLocation(second.resolve(), 2, 3)


def test_m190_duplicate_translation_entries_are_diagnostics(tmp_path: Path) -> None:
    first = tmp_path / "translate_cpp_a.tsl"
    second = tmp_path / "translate_cpp_b.tsl"
    first.write_text('translation cpp:\n  call "{name}({args})"\n', encoding="utf-8")
    second.write_text('translation cpp:\n  call "other({args})"\n', encoding="utf-8")

    result = load_backend_metadata_catalog((), (first, second))

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-METADATA-DUPLICATE-TRANSLATION"
    ]
    assert result.diagnostics[0].location == SourceLocation(second.resolve(), 2, 3)


def test_m190_malformed_language_entry_is_diagnostic() -> None:
    result = parse_backend_type_map(
        'language cpp:\n  s32 {name "int32_t"}\n',
        Path("types_cpp.tsl"),
    )

    assert result.type_spellings == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-METADATA-MALFORMED-TYPE"
    ]


def test_m190_malformed_translation_entry_is_diagnostic() -> None:
    result = parse_backend_translation_map(
        "translation cpp:\n  call {name}({args})\n",
        Path("translate_cpp.tsl"),
    )

    assert result.translation_templates == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-METADATA-MALFORMED-TRANSLATION-ENTRY"
    ]


def test_m190_unclosed_multiline_translation_is_diagnostic() -> None:
    result = parse_backend_translation_map(
        'translation rust:\n  preamble """pub mod detail {\n',
        Path("translate_rust.tsl"),
    )

    assert [template.key for template in result.translation_templates] == [
        BackendTranslationKey("preamble")
    ]
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-METADATA-UNCLOSED-TRANSLATION-TEMPLATE"
    ]
