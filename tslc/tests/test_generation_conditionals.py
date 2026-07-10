"""Generation-time `if<generation>` conditional + the enablers it surfaced:

- `type::is_same` query and `||`/`&&` boolean conditions,
- the `intrin::suffix("stream")` named (whole-register) suffix policy,
- extension-scoped `requires` and bracketed multi-extension selectors,

all delivering the SIMD comparison family (signed + unsigned + float) on sse/avx2.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.lower.context import (
    LoweringEnv,
    LoweringScope,
    LoweringSession,
    SimdTypeParameterValue,
    VectorValue,
)
from tslc.lower.lowerer import Lowerer
from tslc.lower.queries import (
    DEFAULT_QUERY_FUNCTIONS,
    BoolValue,
    QueryEvaluator,
    TextValue,
    TypeValue,
)
from tslc.select.selector import Selector


def _spec(catalog, machine_profiles, profile, primitive, ext, type_tag, backend="cpp"):
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if s.extension.name == ext
    )
    return Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend)).specialization


def _ctx(catalog, ext_name, type_tag, backend="cpp"):
    return LoweringSession(
        env=LoweringEnv(
            catalog=catalog,
            backend=create_backend_dialect(catalog, backend),
            extension=catalog.extensions[ext_name],
            type_tag=type_tag,
        )
    )


# --- query layer -------------------------------------------------------------


def test_query_facade_separates_evaluator_from_namespace_functions() -> None:
    modules_by_head = {
        function.head: type(function).__module__ for function in DEFAULT_QUERY_FUNCTIONS
    }

    assert QueryEvaluator.__module__ == "tslc.lower.queries"
    assert modules_by_head["type::is_same"] == "tslc.lower._query_core"
    assert modules_by_head["type::same_size"] == "tslc.lower._query_core"
    assert modules_by_head["type::size_bits"] == "tslc.lower._query_core"
    assert modules_by_head["vector::length"] == "tslc.lower._query_vector"
    assert modules_by_head["vector::runtime_length"] == "tslc.lower._query_vector"


def test_type_is_same_query(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx = _ctx(catalog, "avx2", "ui16")
    assert ev.evaluate("type::is_same(type(base::in), ui16)", ctx) == BoolValue(True)
    assert ev.evaluate("type::is_same(type(base::in), ui8)", ctx) == BoolValue(False)
    assert ev.evaluate("type::same_size(type(base::in), si16)", ctx) == BoolValue(True)
    assert ev.evaluate("type::same_size(type(base::in), si32)", ctx) == BoolValue(False)


def test_type_size_queries_accept_type_values_without_wrapper(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx = _ctx(catalog, "avx2", "ui32")

    assert ev.evaluate("type::size_bytes(base::in)", ctx) == TextValue("4")
    assert ev.evaluate("type::size_bytes(type(base::in))", ctx) == TextValue("4")
    assert ev.evaluate("type::size_bits(base::in)", ctx) == TextValue("32")
    assert ev.evaluate("value(type::size_bits(base::in))", ctx) == TextValue("32")


def test_select_query_chooses_same_kind_generation_value(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx_f32 = _ctx(catalog, "avx2", "f32")
    ctx_f64 = _ctx(catalog, "avx2", "f64")

    query = (
        "select(value(type::is_same(type(base::in), f32)), "
        "ui32, ui64)"
    )

    assert ev.evaluate(query, ctx_f32) == TypeValue("ui32")
    assert ev.evaluate(query, ctx_f64) == TypeValue("ui64")
    assert ev.evaluate(
        "value<generation>(type::is_same(type(base::in), f32))", ctx_f32
    ) is None
    assert ev.evaluate(
        "select(value(type::is_same(type(base::in), f32)), "
        "ui32, scalar::size)",
        ctx_f32,
    ) is None


def test_runtime_vector_length_query_uses_static_or_declared_runtime_count(
    catalog: Catalog,
) -> None:
    ev = QueryEvaluator()

    assert ev.evaluate(
        "value(vector::runtime_length)", _ctx(catalog, "avx2", "si32")
    ) == TextValue("8")
    assert ev.evaluate(
        "value(vector::runtime_length)", _ctx(catalog, "generic", "si32")
    ) == TextValue("LANES")
    assert ev.evaluate(
        "value(vector::runtime_length)", _ctx(catalog, "sve", "si32")
    ) == TextValue("svcntb() / sizeof(int32_t)")
    assert ev.evaluate("value(vector::length)", _ctx(catalog, "sve", "si32")) is None


def test_named_stream_suffix_resolves_per_extension(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    # whole-register integer suffix: si128 on sse, si256 on avx2.
    assert ev.evaluate('intrin::suffix("stream")', _ctx(catalog, "avx2", "si32")) == TextValue("si256")
    assert ev.evaluate('intrin::suffix("stream")', _ctx(catalog, "sse", "si32")) == TextValue("si128")


def test_query_evaluator_returns_source_identities_for_type_and_vector_terms(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx = LoweringSession(
        env=LoweringEnv(
            catalog=catalog,
            backend=create_backend_dialect(catalog, "cpp"),
            extension=catalog.extensions["avx2"],
            type_tag="si32",
        ),
        scope=LoweringScope(
            target_type_symbols={"ToBase": "ui16", "ToType": "ui16"},
            type_symbols={"AliasBase": "ui32"},
            extension_symbols={"ToExtension": "sse"},
        ),
    )

    assert ev.evaluate("type(scalar::si16)", ctx) == TypeValue("si16")
    assert ev.evaluate("type<backend>(scalar::si16)", ctx) is None
    assert ev.evaluate("mask::lane::all_true", ctx) is None
    assert ev.evaluate("base::signed_of(AliasBase)", ctx) == TypeValue("si32")
    assert ev.evaluate(
        "type(vector::as_base(ToBase))", ctx
    ) == VectorValue(base_tag="ui16", extension_isa="avx2", lanes=16)
    assert ev.evaluate(
        "type(vector::as_extension(ToExtension))", ctx
    ) == VectorValue(base_tag="si32", extension_isa="sse", lanes=4)
    assert ev.evaluate(
        "type(vector::as(sse, ToBase))", ctx
    ) == VectorValue(base_tag="ui16", extension_isa="sse", lanes=8)
    assert ev.evaluate(
        "value(generic::runtime_length(vector::as(sve, ToBase)))", ctx
    ) == TextValue("svcntb() / sizeof(uint16_t)")
    assert ev.evaluate(
        "type(vector::transform_extension(ToBase))", ctx
    ) is None
    assert ev.evaluate(
        "type(vector::as_extension(sse, ToBase))", ctx
    ) is None


def test_simd_type_generic_params_are_queryable_by_authored_name(
    catalog: Catalog,
) -> None:
    ev = QueryEvaluator()
    cpp = LoweringSession(
        env=LoweringEnv(
            catalog=catalog,
            backend=create_backend_dialect(catalog, "cpp"),
            extension=catalog.extensions["avx2"],
            type_tag="si32",
            simd_type_param_names=frozenset({"IndexVec", "SourceVec"}),
        )
    )
    rust = LoweringSession(
        env=LoweringEnv(
            catalog=catalog,
            backend=create_backend_dialect(catalog, "rust"),
            extension=catalog.extensions["avx2"],
            type_tag="si32",
            simd_type_param_names=frozenset({"IndexVec"}),
        )
    )

    assert ev.evaluate("IndexVec", cpp) == SimdTypeParameterValue("IndexVec")
    assert ev.evaluate("SourceVec", cpp) == SimdTypeParameterValue("SourceVec")
    assert ev.evaluate("OtherVec", cpp) == TextValue("OtherVec")
    assert ev.evaluate("value(generic::length(OtherVec))", cpp) is None

    assert ev.evaluate("value(generic::length(IndexVec))", cpp) == TextValue(
        "IndexVec::lane_count_v"
    )
    assert ev.evaluate("value(generic::runtime_length(IndexVec))", cpp) == TextValue(
        "IndexVec::lane_count()"
    )
    assert ev.evaluate("type(base::generic(IndexVec))", cpp) == TextValue(
        "typename IndexVec::base_type"
    )
    assert ev.evaluate("type(register::generic(IndexVec))", cpp) == TextValue(
        "typename IndexVec::register_type"
    )

    assert ev.evaluate("value(generic::length(IndexVec))", rust) == TextValue(
        "IndexVec::ELEMENT_COUNT"
    )
    assert ev.evaluate("value(generic::runtime_length(IndexVec))", rust) == TextValue(
        "IndexVec::lane_count()"
    )
    assert ev.evaluate("type(base::generic(IndexVec))", rust) == TextValue(
        "IndexVec::BaseType"
    )
    assert ev.evaluate("type(register::generic(IndexVec))", rust) == TextValue(
        "IndexVec::RegisterType"
    )


def test_bound_simd_type_base_param_is_generation_queryable(catalog: Catalog) -> None:
    ev = QueryEvaluator()
    ctx = LoweringSession(
        env=LoweringEnv(
            catalog=catalog,
            backend=create_backend_dialect(catalog, "cpp"),
            extension=catalog.extensions["avx2"],
            type_tag="si32",
            simd_type_param_names=frozenset({"IndexVec"}),
            simd_type_param_base_bindings={"IndexVec": "ui32"},
        )
    )

    assert ev.evaluate("type(base::generic(IndexVec))", ctx) == TypeValue("ui32")
    assert ev.evaluate(
        "type::is_same(type(base::generic(IndexVec)), ui32)", ctx
    ) == BoolValue(True)
    assert ev.evaluate(
        "type::same_size(type(base::in), type(base::generic(IndexVec)))", ctx
    ) == BoolValue(True)


def test_lowering_env_freezes_simd_type_param_names(catalog: Catalog) -> None:
    names = {"IndexVec"}
    bindings = {"IndexVec": "ui32"}
    env = LoweringEnv(
        catalog=catalog,
        backend=create_backend_dialect(catalog, "cpp"),
        extension=catalog.extensions["avx2"],
        type_tag="si32",
        simd_type_param_names=names,
        simd_type_param_base_bindings=bindings,
    )

    names.add("OtherVec")
    bindings["IndexVec"] = "si64"

    assert env.simd_type_param_names == frozenset({"IndexVec"})
    assert dict(env.simd_type_param_base_bindings) == {"IndexVec": "ui32"}


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


def test_hand_float_bitwise_carrier_type_query_lowers(catalog: Catalog, machine_profiles) -> None:
    spec_f32 = _spec(catalog, machine_profiles, "avx2", "hand", "avx2", "f32")
    spec_f64 = _spec(catalog, machine_profiles, "avx2", "hand", "avx2", "f64")
    rust_f32 = _spec(catalog, machine_profiles, "avx2", "hand", "avx2", "f32", backend="rust")

    assert spec_f32 is not None and "static_cast<uint32_t>(0)" in spec_f32.body_text
    assert spec_f64 is not None and "static_cast<uint64_t>(0)" in spec_f64.body_text
    assert "select(" not in spec_f32.body_text
    assert "select(" not in spec_f64.body_text
    assert rust_f32 is not None
    assert "core::ptr::addr_of_mut!(result).cast::<u8>()" in rust_f32.body_text
    assert "core::ptr::addr_of!(data_arr[0]).cast::<u8>()" in rust_f32.body_text


def test_lzc_scalar_float_bitwise_path_does_not_need_offset_base(
    catalog: Catalog, machine_profiles
) -> None:
    spec_cpp = _spec(catalog, machine_profiles, "scalar", "lzc_scalar", "scalar", "f32")
    spec_rust = _spec(
        catalog, machine_profiles, "scalar", "lzc_scalar", "scalar", "f32", backend="rust"
    )

    assert spec_cpp is not None
    assert "detail::helpers::clz(bits)" in spec_cpp.body_text
    assert "offset_base" not in spec_cpp.body_text
    assert spec_rust is not None
    assert "detail::helpers::clz(bits)" in spec_rust.body_text
    assert "offset_base" not in spec_rust.body_text
    assert "bits{}" not in spec_rust.body_text
    assert "let mut bits" in spec_rust.body_text
    assert "core::ptr::addr_of_mut!(bits).cast::<u8>()" in spec_rust.body_text


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
    assert avx512.mask_policy.spelling_for_lanes("cpp", 16) == "__mmask16"
    # avx2_vl is native-predicate despite inheriting the lane-bitmask avx2 block.
    assert catalog.extensions["avx2_vl"].mask_policy.kind == "native_predicate_by_lanes"
    sve = catalog.extensions["sve"]
    assert sve.mask_policy.kind == "native_predicate"
    assert sve.mask_policy.spelling("cpp") == "svbool_t"


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


def test_mask_all_and_zero_lower_for_native_predicate_masks(
    catalog: Catalog, machine_profiles
) -> None:
    cpp_true = _spec(catalog, machine_profiles, "skylake", "mask_true", "avx512", "ui32")
    cpp_false = _spec(catalog, machine_profiles, "skylake", "mask_false", "avx512", "ui32")
    rust_true = _spec(
        catalog, machine_profiles, "skylake", "mask_true", "avx512", "ui32", backend="rust"
    )
    generic_true = _spec(catalog, machine_profiles, "avx2", "mask_true", "generic", "ui32")

    assert cpp_true is not None
    assert cpp_true.body_text == "return static_cast<typename Vec::mask_type>(~0ull);"
    assert cpp_false is not None
    assert cpp_false.body_text == "return 0;"
    assert rust_true is not None
    assert rust_true.body_text == "return u64::MAX as _;"
    assert generic_true is not None
    assert "LANES" in generic_true.body_text
    assert "mask<all>" not in cpp_true.body_text + rust_true.body_text + generic_true.body_text


def test_mask_test_imask_lowers_integral_mask_bit_test(
    catalog: Catalog, machine_profiles
) -> None:
    cpp = _spec(catalog, machine_profiles, "avx2", "test_imask", "avx2", "ui32")
    rust = _spec(
        catalog, machine_profiles, "scalar", "to_mask", "scalar", "ui32", backend="rust"
    )

    assert cpp is not None
    assert "static_cast<std::uint64_t>(mask)" in cpp.body_text
    assert "mask<test" not in cpp.body_text
    assert rust is not None
    assert rust.body_text == "return (((mask) as u64 >> 0) & 1u64) != 0;"


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
    # `store<void:=(ptr,v)>` and `load<v:=cptr>` introduce mutable/read-only pointer
    # params plus a void result kind. Scalar bodies are raw pointer ops; void carries no complete.
    store = _spec(catalog, machine_profiles, "scalar", "store", "scalar", "si32")
    assert store is not None
    assert store.result_kind == "void" and store.param_kinds == ("ptr", "v")
    assert "*ptr = data;" in store.body_text

    load = _spec(catalog, machine_profiles, "scalar", "load", "scalar", "si32")
    assert load is not None
    assert load.result_kind == "v" and load.param_kinds == ("cptr",)
    assert "return *ptr;" in load.body_text


def test_scalar_load_store_rust_is_unsafe(catalog: Catalog, machine_profiles) -> None:
    # Dereferencing a raw pointer is unsafe in Rust even without intrinsics.
    store = _spec(catalog, machine_profiles, "scalar", "store", "scalar", "si32", backend="rust")
    assert store is not None and store.body_text.startswith("unsafe {")


def test_runtime_if_uses_backend_condition_syntax(catalog: Catalog, machine_profiles) -> None:
    cpp = _spec(catalog, machine_profiles, "scalar", "blend", "scalar", "si32")
    rust = _spec(catalog, machine_profiles, "scalar", "blend", "scalar", "si32", backend="rust")

    assert cpp is not None and "if (mask) {" in cpp.body_text
    assert rust is not None and "if mask {" in rust.body_text
    assert "if (mask)" not in rust.body_text


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

    body = Lowerer().lower(
        spec, catalog, create_backend_dialect(catalog, "rust")
    ).specialization.body_text
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
