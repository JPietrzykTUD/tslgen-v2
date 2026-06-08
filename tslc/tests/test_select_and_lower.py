"""Selection + lowering produce backend-correct functions."""

from __future__ import annotations

import pytest

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Catalog
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.select.target import Target


def _lower(catalog: Catalog, backend: str, prim: str, ext: str, tag: str):
    selection = Selector().select(
        catalog, Target(backend=backend, primitive_name=prim, extension=ext, type_tag=tag)
    )
    assert selection.selected is not None, selection.diagnostics
    translation = BackendTranslation(catalog=catalog, backend_id=backend)
    result = Lowerer().lower(selection.selected, catalog, translation)
    assert result.function is not None, result.diagnostics
    return result.function


def test_unknown_primitive_and_extension_are_errors(catalog: Catalog) -> None:
    selector = Selector()
    nope = selector.select(catalog, Target("cpp", "does_not_exist", "avx2", "si32"))
    assert nope.selected is None
    assert nope.diagnostics[0].code == "TSL-SELECT-UNKNOWN-PRIMITIVE"

    bad_ext = selector.select(catalog, Target("cpp", "add", "nope", "si32"))
    assert bad_ext.selected is None
    assert bad_ext.diagnostics[0].code == "TSL-SELECT-UNKNOWN-EXTENSION"


def test_scalar_add_is_raw_passthrough(catalog: Catalog) -> None:
    cpp = _lower(catalog, "cpp", "add", "scalar", "si32")
    assert cpp.result_type == "int32_t"
    assert cpp.body_text == "return left + right;"

    rust = _lower(catalog, "rust", "sub", "scalar", "f64")
    assert rust.result_type == "f64"
    assert rust.body_text == "return left - right;"


@pytest.mark.parametrize(
    ("tag", "cpp_reg", "suffix"),
    [
        ("si32", "__m256i", "epi32"),
        ("ui32", "__m256i", "epi32"),  # signed_of normalizes ui -> si (no epu)
        ("si8", "__m256i", "epi8"),
        ("f32", "__m256", "ps"),
        ("f64", "__m256d", "pd"),
    ],
)
def test_avx2_add_composes_intrinsic(catalog: Catalog, tag, cpp_reg, suffix) -> None:
    cpp = _lower(catalog, "cpp", "add", "avx2", tag)
    assert cpp.result_type == cpp_reg
    # C++: return framing from the emit_return template, no unsafe.
    assert cpp.body_text == f"return _mm256_add_{suffix}(left, right);"

    rust = _lower(catalog, "rust", "add", "avx2", tag)
    # Rust: the intrinsic value is wrapped in unsafe at the backend boundary.
    assert rust.body_text == (
        f"return unsafe {{ core::arch::x86_64::_mm256_add_{suffix}(left, right) }};"
    )
    assert rust.result_type.startswith("core::arch::x86_64::")


def test_unsigned_avx2_never_uses_epu(catalog: Catalog) -> None:
    for tag in ("ui8", "ui16", "ui32", "ui64"):
        cpp = _lower(catalog, "cpp", "add", "avx2", tag)
        assert "epu" not in cpp.body_text
