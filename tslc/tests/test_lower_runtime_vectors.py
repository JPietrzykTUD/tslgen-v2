"""Runtime-vector storage and specialization constraint regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    CppBackend,
    create_backend_dialect,
    GenericParam,
    GenericParamBaseWidthConstraint,
    Implementation,
    Lowerer,
    Primitive,
    pytest,
    RustBackend,
    Selector,
    _RecordingDialect,
    _RecordingSyntax,
)


def test_runtime_array_var_lowers_sve_scratch_storage(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve"],
            "gather_narrow_partial",
            ("ui16",),
        )
        .selected
        if s.extension.name == "sve"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert (
        "std::vector<typename IndicesType::base_type> idx_array_storage"
        in cpp.body_text
    )
    assert "std::vector<uint16_t> result_storage" in cpp.body_text
    assert "auto *idx_array = idx_array_storage.data();" in cpp.body_text
    assert "auto *result = result_storage.data();" in cpp.body_text
    assert "std::malloc" not in cpp.body_text
    assert "std::free" not in cpp.body_text


@pytest.mark.parametrize("masked", [False, True])
def test_sve_gather_prefers_native_indexed_load_with_runtime_fallback(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "gather", ("ui32",))
        .selected
        if selected.extension.name == "sve"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svld1_gather_index" in lowered.body_text
    assert "if constexpr (scale == 4)" in lowered.body_text
    assert "IndicesType::extension_type" in lowered.body_text
    assert "index_lanes" in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert ("active_array_storage" in lowered.body_text) is masked


def test_sve_byte_gather_keeps_runtime_fallback_without_invalid_native_load(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "gather", ("ui8",))
        .selected
        if selected.extension.name == "sve"
        and "mask" not in selected.primitive.attribute_keys
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svld1_gather_index" not in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert "result_storage" in lowered.body_text


@pytest.mark.parametrize("masked", [False, True])
def test_sve_scatter_uses_runtime_index_and_predicate_storage(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "scatter", ("ui32",))
        .selected
        if selected.extension.name == "sve"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "index_lanes" in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert "val_array_storage" in lowered.body_text
    assert ("active_array_storage" in lowered.body_text) is masked
    assert "svst1_scatter" not in lowered.body_text


def test_simd_type_base_specialization_expands_gather_narrow_slots(
    catalog: Catalog, machine_profiles
) -> None:
    slots = [
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "gather_narrow", ("ui16",))
        .selected
        if s.extension.name == "avx2"
    ]

    assert {
        tuple((binding.param_name, binding.base_tag) for binding in slot.simd_type_base_bindings)
        for slot in slots
    } == {
        (("IndicesType", "si32"),),
        (("IndicesType", "ui32"),),
        (("IndicesType", "si64"),),
        (("IndicesType", "ui64"),),
    }


def test_simd_type_base_width_constraint_filters_specialized_slots(
    catalog: Catalog, machine_profiles
) -> None:
    impl = Implementation(
        ("avx2", "arith"),
        "avx2",
        "arith",
        "complete(index);",
        source_order=0,
    )
    primitive = Primitive(
        name="wide_index_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32", "?i64"),
                specialize_base=True,
                base_width_constraints=(GenericParamBaseWidthConstraint(">="),),
            ),
        ),
        implementations=(impl,),
    )
    probe_catalog = Catalog(
        primitives=(*catalog.primitives, primitive),
        type_groups=catalog.type_groups,
        extensions=catalog.extensions,
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=catalog.target_families,
    )

    slots = Selector().select_profile(
        probe_catalog,
        machine_profiles["avx2"],
        "wide_index_probe",
        ("ui64",),
    ).selected

    assert {
        tuple((binding.param_name, binding.base_tag) for binding in slot.simd_type_base_bindings)
        for slot in slots
    } == {
        (("IndexVec", "si64"),),
        (("IndexVec", "ui64"),),
    }


def test_simd_type_base_width_constraint_rejects_unsatisfied_slots(
    catalog: Catalog, machine_profiles
) -> None:
    impl = Implementation(
        ("avx2", "arith"),
        "avx2",
        "arith",
        "complete(index);",
        source_order=0,
    )
    primitive = Primitive(
        name="too_narrow_index_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
                specialize_base=True,
                base_width_constraints=(GenericParamBaseWidthConstraint(">="),),
            ),
        ),
        implementations=(impl,),
    )
    probe_catalog = Catalog(
        primitives=(*catalog.primitives, primitive),
        type_groups=catalog.type_groups,
        extensions=catalog.extensions,
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=catalog.target_families,
    )

    slots = Selector().select_profile(
        probe_catalog,
        machine_profiles["avx2"],
        "too_narrow_index_probe",
        ("ui64",),
    ).selected

    assert slots == ()


def test_param_types_default_overrides_rendered_pointer_type(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "gather_narrow", ("ui16",))
        .selected
        if s.extension.name == "avx2"
    )
    lowerer = Lowerer()

    cpp = lowerer.lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust_dialect = create_backend_dialect(catalog, "rust")
    recording_syntax = _RecordingSyntax(rust_dialect.syntax)
    rust = lowerer.lower(
        slot, catalog, _RecordingDialect(rust_dialect, recording_syntax)
    ).specialization

    assert cpp is not None
    assert rust is not None
    assert cpp.type_params[0].base_type_binding in {"si32", "ui32", "si64", "ui64"}
    assert rust.type_params[0].base_type_binding == cpp.type_params[0].base_type_binding
    assert cpp.param_type_overrides[1] == "typename IndicesType::base_type const *"
    assert rust.param_type_overrides[1] == "*const IndicesType::BaseType"
    assert recording_syntax.param_type_calls == [(True, True)]
    cpp_source = CppBackend().render_primitive("gather_narrow", (cpp,))
    rust_source = RustBackend().render_primitive("gather_narrow", (rust,))
    assert "typename IndicesType::base_type const * index_ptr" in cpp_source
    assert "class IndicesTypeBaseKey = ::tsl::detail::base_type_dispatch_key_t" in cpp_source
    assert "::tsl::detail::base_" in cpp_source
    assert "index_ptr: *const IndicesType::BaseType" in rust_source
    assert "IndicesTypeBaseKey" in rust_source
    assert "<IndicesType::BaseType as BaseTypeDispatch>::Key" in rust_source
