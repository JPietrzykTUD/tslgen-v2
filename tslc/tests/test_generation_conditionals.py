"""Generation-time `if<generation>` conditional + the enablers it surfaced:

- `type::is_same` query and `||`/`&&` boolean conditions,
- the `intrin::suffix("stream")` named (whole-register) suffix policy,
- extension-scoped `requires` and bracketed multi-extension selectors,

all delivering the SIMD comparison family (signed + unsigned + float) on sse/avx2.
"""

from __future__ import annotations

from pathlib import Path

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Catalog
from tslc.lower.context import LoweringContext
from tslc.lower.lowerer import Lowerer
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue
from tslc.select.selector import Selector


def _spec(catalog, machine_profiles, profile, primitive, ext, type_tag, backend="cpp"):
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if s.extension.name == ext
    )
    return Lowerer().lower(slot, catalog, BackendTranslation(catalog, backend)).specialization


def _ctx(catalog, ext_name, type_tag, backend="cpp"):
    return LoweringContext(
        extension=catalog.extensions[ext_name],
        type_tag=type_tag,
        translation=BackendTranslation(catalog, backend),
    )


# --- query layer -------------------------------------------------------------


def test_type_is_same_query(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx = _ctx(catalog, "avx2", "ui16")
    assert ev.evaluate("type::is_same(type<generation>(base::in), ui16)", ctx) == BoolValue(True)
    assert ev.evaluate("type::is_same(type<generation>(base::in), ui8)", ctx) == BoolValue(False)


def test_named_stream_suffix_resolves_per_extension(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    # whole-register integer suffix: si128 on sse, si256 on avx2.
    assert ev.evaluate('intrin::suffix("stream")', _ctx(catalog, "avx2", "si32")) == TextValue("si256")
    assert ev.evaluate('intrin::suffix("stream")', _ctx(catalog, "sse", "si32")) == TextValue("si128")


# --- if<generation> lowering (taken branch only) -----------------------------


def test_unsigned_compare_resolves_branch_no_dead_code(catalog: Catalog, machine_profiles) -> None:
    # ui16 greater_than flips the sign bit (0x8000 for ui16) chosen by if<generation>,
    # then compares as signed. The emitted body must contain only the taken branch.
    spec = _spec(catalog, machine_profiles, "avx2", "greater_than", "avx2", "ui16")
    assert spec is not None, "unsigned avx2 greater_than should lower"
    body = spec.body_text
    assert "if<generation>" not in body and "else<generation>" not in body
    assert "0x8000" in body and "0x80000000" not in body  # only the ui16 sign bit
    assert "_mm256_cmpgt_epi16" in body  # compared as signed int16


def test_signed_and_float_compares_lower_on_avx2(catalog: Catalog, machine_profiles) -> None:
    for prim, expect in [
        ("equal", "_mm256_cmpeq_epi32"),
        ("greater_than", "_mm256_cmpgt_epi32"),
    ]:
        spec = _spec(catalog, machine_profiles, "avx2", prim, "avx2", "si32")
        assert spec is not None and expect in spec.body_text


# --- selection enablers ------------------------------------------------------


def test_extension_scoped_requires_selects_binary_op(catalog: Catalog, machine_profiles) -> None:
    # binary_xor's avx2 body uses `requires: avx2 [avx, avx2]` (extension-keyed) and
    # the whole-register `si256` suffix; it must select and lower on avx2.
    spec = _spec(catalog, machine_profiles, "avx2", "binary_xor", "avx2", "si32")
    assert spec is not None
    assert "_mm256_xor_si256" in spec.body_text


def test_bracketed_multi_extension_selector_expands(catalog: Catalog, machine_profiles) -> None:
    # set1's body lives under `[avx2, sse]:`; expansion makes it select for both.
    exts = {
        s.extension.name
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "set1", ("si32",))
        .selected
    }
    assert {"avx2", "sse"} <= exts


def test_boolean_or_condition_lowers_set1(catalog: Catalog, machine_profiles) -> None:
    # set1's integer body branches on `is_same(.,si64) || is_same(.,ui64)`; the OR
    # must evaluate at generation time so the body lowers (here: the 64-bit path).
    spec = _spec(catalog, machine_profiles, "avx2", "set1", "avx2", "si64")
    assert spec is not None
    assert "if<generation>" not in spec.body_text
