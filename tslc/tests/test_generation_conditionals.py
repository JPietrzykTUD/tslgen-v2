"""Generation-time `if<generation>` conditional + the enablers it surfaced:

- `type::is_same` query and `||`/`&&` boolean conditions,
- the `intrin::suffix("stream")` named (whole-register) suffix policy,
- extension-scoped `requires` and bracketed multi-extension selectors,

all delivering the SIMD comparison family (signed + unsigned + float) on sse/avx2.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
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


# --- native-predicate masks (avx512 / _vl) -----------------------------------


def test_mask_policy_promoted_into_extension(catalog: Catalog) -> None:
    assert catalog.extensions["avx2"].mask_policy.kind == "lane_bitmask"
    avx512 = catalog.extensions["avx512"]
    assert avx512.mask_policy.kind == "native_predicate_by_lanes"
    assert avx512.vector_bits == 512
    assert avx512.mask_policy.cpp_by_lanes[16] == "__mmask16"
    # avx2_vl is native-predicate despite inheriting the lane-bitmask avx2 block.
    assert catalog.extensions["avx2_vl"].mask_policy.kind == "native_predicate_by_lanes"


def test_post_mask_appends_mask_only_for_native_predicate(catalog: Catalog, machine_profiles) -> None:
    # avx512 (native predicate): post=mask selects the mask-returning intrinsic.
    sky = _spec(catalog, machine_profiles, "skylake", "equal", "avx512", "si32")
    assert sky is not None and "_mm512_cmpeq_epi32_mask" in sky.body_text
    # avx2 (lane-bitmask): post=mask is a no-op, the compare yields the vector mask.
    av = _spec(catalog, machine_profiles, "avx2", "equal", "avx2", "si32")
    assert av is not None and "_mm256_cmpeq_epi32" in av.body_text
    assert "_mask" not in av.body_text


def test_native_mask_registration_per_profile(
    data_root, machine_profiles_path, tmp_path
) -> None:
    # Same ISA tag `avx2`, two mask policies depending on the profile's selected block.
    from tslc.api import write_artifacts  # noqa: PLC0415

    def _mask_line(profile: str) -> str:
        result = generate_project(
            [data_root],
            machine_profiles_path=machine_profiles_path,
            primitives=["equal"],
            profiles=[profile],
        )
        write_artifacts(result.artifacts, tmp_path / profile)
        hpp = (tmp_path / profile / "cpp" / "include" / f"tsl_{profile}.hpp").read_text()
        # the mask_type line of the `simd<T, avx2>` registration
        block = hpp.split("struct simd<T, avx2>")[1]
        return block.split("using mask_type =")[1].split(";")[0]

    assert "register_type" in _mask_line("avx2")  # lane-bitmask
    assert "native_mask<256" in _mask_line("skylake")  # avx2_vl native predicate


# --- masked-variant selection: native blend (first mask-consuming primitive) --


def test_masked_only_primitive_is_selectable(catalog: Catalog, machine_profiles) -> None:
    # `blend` exists only as `[mask=pass_through]`; it must still resolve by name and
    # lower its native body, consuming the mask as a parameter (kind `m`).
    spec = _spec(catalog, machine_profiles, "skylake", "blend", "avx512", "si32")
    assert spec is not None
    assert spec.result_kind == "v" and spec.param_kinds == ("m", "v", "v")
    assert "_mm512_mask_blend_epi32(mask, left, right)" in spec.body_text


# --- ptr / void kinds: scalar load/store (leaf of the array/reduction chain) ---


def test_scalar_load_store_kinds(catalog: Catalog, machine_profiles) -> None:
    # `store<void:=(ptr,v)>` and `load<v:=ptr>` introduce the ptr param + void result
    # kinds. Scalar bodies are raw pointer ops; void carries no emit_return.
    store = _spec(catalog, machine_profiles, "scalar", "store", "scalar", "si32")
    assert store is not None
    assert store.result_kind == "void" and store.param_kinds == ("ptr", "v")
    assert "*ptr = data;" in store.body_text

    load = _spec(catalog, machine_profiles, "scalar", "load", "scalar", "si32")
    assert load is not None
    assert load.result_kind == "v" and load.param_kinds == ("ptr",)
    assert "return *ptr;" in load.body_text


def test_scalar_load_store_rust_is_unsafe(catalog: Catalog, machine_profiles) -> None:
    # Dereferencing a raw pointer is unsafe in Rust even without intrinsics.
    store = _spec(catalog, machine_profiles, "scalar", "store", "scalar", "si32", backend="rust")
    assert store is not None and store.body_text.startswith("unsafe {")


# --- boolean-wildcard attribute axis: SIMD load/store (both aligned variants) --


def test_aligned_wildcard_expands_to_both_variants(catalog: Catalog) -> None:
    # `[aligned=*]` store expands into concrete aligned/unaligned primitives.
    aligned = {
        p.attributes.get("aligned")
        for p in catalog.primitives_named("store")
        if p.signature == "void:=(ptr,v)"
    }
    assert aligned == {"true", "false"}


def test_simd_store_emits_both_aligned_variants(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    from tslc.api import write_artifacts  # noqa: PLC0415

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["store"],
        profiles=["avx2"],
        backends=["cpp"],
    )
    write_artifacts(result.artifacts, tmp_path)
    hpp = (tmp_path / "cpp" / "include" / "tsl_avx2.hpp").read_text()
    # both variants coexist, keyed by the bool axis param on the impl + wrapper
    assert "template <class Vec, bool Aligned>" in hpp
    assert "store_impl<tsl::simd<int32_t, tsl::avx2>, false>" in hpp
    assert "store_impl<tsl::simd<int32_t, tsl::avx2>, true>" in hpp
    # unaligned uses storeu + a pointer reinterpret; aligned uses store + assume_aligned
    assert "_mm256_storeu_si256(reinterpret_cast<typename Vec::register_type *>(ptr)" in hpp
    assert "_mm256_store_si256(reinterpret_cast<typename Vec::register_type *>(::tsl::assume_aligned<32>(ptr))" in hpp


def test_simd_store_pointer_cast_rust(catalog: Catalog, machine_profiles) -> None:
    # The pointer reinterpret diverges: Rust uses `ptr as *mut …`, not bit_cast.
    spec = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "store", ("si32",))
        .selected
        if s.extension.name == "avx2" and s.primitive.attributes.get("aligned") == "false"
    )
    from tslc.lower.lowerer import Lowerer  # noqa: PLC0415

    body = Lowerer().lower(spec, catalog, BackendTranslation(catalog, "rust")).specialization.body_text
    assert "ptr as *mut Self::RegisterType" in body


# --- overload dispatch: store's (ptr,v) / (ptr,s) signatures --------------------


def test_store_overload_dispatch(data_root, machine_profiles_path, tmp_path) -> None:
    from tslc.api import write_artifacts  # noqa: PLC0415

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["store"],
        profiles=["avx2"],
    )
    write_artifacts(result.artifacts, tmp_path)
    hpp = (tmp_path / "cpp" / "include" / "tsl_avx2.hpp").read_text()
    # C++: one impl with two `apply` overloads (vector + scalar) resolved by arg type;
    # a generic-arg wrapper.
    assert hpp.count("struct store_impl<tsl::simd<int32_t, tsl::avx2>, false>") == 1
    assert "apply(typename Vec::base_type * ptr, typename tsl::reg_param<Vec>::type" in hpp
    assert "apply(typename Vec::base_type * ptr, typename Vec::base_type" in hpp
    assert "class Arg1" in hpp
    rs = (tmp_path / "rust" / "src" / "tsl_avx2.rs").read_text()
    # Rust: an arg-dispatch trait implemented for each concrete argument type.
    assert "pub trait StoreImplArg" in rs
    assert "for core::arch::x86_64::__m256i {" in rs
    assert "for i32 {" in rs


def test_store_scalar_dedup(data_root, machine_profiles_path, tmp_path) -> None:
    # On scalar, register_type == base_type, so the (ptr,v)/(ptr,s) overloads collapse to
    # one — emitted once (no redefinition).
    from tslc.api import write_artifacts  # noqa: PLC0415

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["store"],
        profiles=["scalar"],
        backends=["cpp"],
    )
    write_artifacts(result.artifacts, tmp_path)
    hpp = (tmp_path / "cpp" / "include" / "tsl_scalar.hpp").read_text()
    block = hpp.split("struct store_impl<tsl::simd<int32_t, tsl::scalar>, false>")[1].split("};")[0]
    assert block.count("static inline") == 1  # the two signatures deduped to one apply
