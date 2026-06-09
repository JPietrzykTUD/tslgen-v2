"""Profile-aware selection + lowering into specializations."""

from __future__ import annotations

import pytest

from tslc.backend.translation import BackendTranslation
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector

_TYPES = ("si32", "ui32", "f32", "f64")


def _slots(catalog, profile, primitive):
    return Selector().select_profile(catalog, profile, primitive, _TYPES).selected


def _by_key(catalog, profile, primitive):
    return {
        (s.type_tag, s.extension.name): s for s in _slots(catalog, profile, primitive)
    }


def test_unknown_primitive_is_error(catalog: Catalog, machine_profiles) -> None:
    result = Selector().select_profile(
        catalog, machine_profiles["avx2"], "does_not_exist", _TYPES
    )
    assert result.selected == ()
    assert result.diagnostics[0].code == "TSL-SELECT-UNKNOWN-PRIMITIVE"


def test_profile_reachability(catalog: Catalog, machine_profiles) -> None:
    # scalar profile: only the scalar extension is reachable.
    scalar = {s.extension.name for s in _slots(catalog, machine_profiles["scalar"], "add")}
    assert scalar == {"scalar"}

    # avx profile: avx2 integer add needs the avx2 flag (absent) -> falls to sse;
    # but avx2 float add only needs `avx`, so it IS reachable.
    avx = _by_key(catalog, machine_profiles["avx"], "add")
    assert avx[("si32", "avx2")] if ("si32", "avx2") in avx else True  # not present
    assert ("si32", "avx2") not in avx
    assert ("si32", "sse") in avx
    assert ("f32", "avx2") in avx  # float add reachable via [avx]

    # avx2 profile: sse + avx2 (and scalar) all reachable.
    avx2 = {s.extension.name for s in _slots(catalog, machine_profiles["avx2"], "add")}
    assert {"scalar", "sse", "avx2"} <= avx2


def test_type_group_specificity_resolves_hadd(catalog: Catalog, machine_profiles) -> None:
    # hadd avx2 has both an f64-specific body and an arith-general body; the
    # specific one must win at generation time.
    slots = _by_key(catalog, machine_profiles["avx2"], "hadd")
    chosen = slots[("f64", "avx2")]
    assert chosen.implementation.type_group == "f64"


@pytest.mark.parametrize(
    ("type_tag", "suffix"), [("si32", "epi32"), ("ui32", "epi32"), ("f32", "ps")]
)
def test_lower_add_avx2(catalog: Catalog, machine_profiles, type_tag, suffix) -> None:
    slots = _by_key(catalog, machine_profiles["avx2"], "add")
    slot = slots[(type_tag, "avx2")]

    cpp = Lowerer().lower(slot, catalog, BackendTranslation(catalog, "cpp")).specialization
    assert cpp is not None
    assert cpp.extension_name == "avx2"
    assert cpp.body_text == f"return _mm256_add_{suffix}(left, right);"
    assert cpp.result_kind == "v"

    rust = Lowerer().lower(slot, catalog, BackendTranslation(catalog, "rust")).specialization
    assert rust is not None
    assert rust.body_text == (
        f"unsafe {{ return core::arch::x86_64::_mm256_add_{suffix}(left, right); }}"
    )


def test_lower_scalar_add_has_no_unsafe(catalog: Catalog, machine_profiles) -> None:
    slot = _by_key(catalog, machine_profiles["scalar"], "add")[("si32", "scalar")]
    cpp = Lowerer().lower(slot, catalog, BackendTranslation(catalog, "cpp")).specialization
    assert cpp.base_type_spelling == "int32_t"
    assert cpp.body_text == "return left + right;"
    rust = Lowerer().lower(slot, catalog, BackendTranslation(catalog, "rust")).specialization
    assert rust.base_type_spelling == "i32"
    assert rust.body_text == "return left + right;"


def test_hadd_reduction_lowers_for_f64(catalog: Catalog, machine_profiles) -> None:
    slot = _by_key(catalog, machine_profiles["avx2"], "hadd")[("f64", "avx2")]
    cpp = Lowerer().lower(slot, catalog, BackendTranslation(catalog, "cpp")).specialization
    assert cpp is not None
    assert cpp.result_kind == "s"  # s:=v -> scalar result
    assert cpp.param_names == ("vec",)
    # multi-statement body: var declarations + assignment + scalar return
    assert "auto const lo = _mm256_extractf128_pd(vec, 0);" in cpp.body_text
    assert "return _mm_cvtsd_f64(temp);" in cpp.body_text
