"""Implementation safety is a typed source and lowering contract."""

from __future__ import annotations

from pathlib import Path

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, ImplementationSafety
from tslc.catalog.signatures import parse_signature
from tslc.catalog.validation import validate_catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import Diagnostic
from tslc.lower.dependencies import CallDependency, VectorIdentity
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.pipeline import (
    CallDependencyOrigin,
    _LoweredSlot,
    _profile_with_required_features,
    _pruned_reason,
    _prune_unresolved,
    _propagate_transitive_call_facts,
)
from tslc.target_text import LoweredBody, RenderPlaceholder, render_sequence
from tslc.select.selector import Selector
from tslc.sources import SourceDocument, SourceLoader
from tslc.syntax.ast import ParsedImplementationSelectorEntry
from tslc.syntax.parser import TslParser


def test_implementation_safety_is_promoted_and_inherited() -> None:
    diagnostics, catalog = _catalog_from_source(
        _base_source(
            "    scalar:\n"
            "      safety:\n"
            "        internal_unsafe true\n"
            "        reasons [intrinsic]\n"
            "      ints:\n"
            "        safety:\n"
            "          caller_unsafe true\n"
            "          reasons [raw_pointer]\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
        )
    )

    assert diagnostics == ()
    primitive = catalog.primitives_named("id", unmasked=False)[0]
    safety = primitive.implementations[0].safety
    assert safety.internal_unsafe is True
    assert safety.caller_unsafe is True
    assert safety.reasons == frozenset({"intrinsic", "raw_pointer"})


def test_malformed_implementation_safety_is_diagnosed() -> None:
    diagnostics, _ = _catalog_from_source(
        _base_source(
            "    scalar:\n"
            "      ints:\n"
            "        safety:\n"
            "          caller_unsafe maybe\n"
            "          reasons raw_pointer\n"
            "          typo true\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
        )
    )

    codes = {diagnostic.code for diagnostic in diagnostics}
    assert "TSL-CATALOG-INVALID-ENUM" in codes
    assert "TSL-CATALOG-MALFORMED-SAFETY" in codes
    assert "TSL-CATALOG-UNKNOWN-FIELD" in codes


def test_safety_inside_implementation_body_is_diagnosed() -> None:
    diagnostics, _ = _catalog_from_source(
        _base_source(
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            "          safety:\n"
            "            internal_unsafe true\n"
            '          tsil "complete(data);"\n'
        )
    )

    diagnostic = next(
        diagnostic for diagnostic in diagnostics if diagnostic.code == "TSL-CATALOG-UNKNOWN-FIELD"
    )
    assert "implementation body" in diagnostic.message
    assert "safety" in diagnostic.message


def test_caller_unsafe_callees_transitively_require_internal_unsafe() -> None:
    callee = _slot(
        "callee",
        safety=ImplementationSafety(
            internal_unsafe=True,
            caller_unsafe=True,
            reasons=frozenset({"raw_pointer"}),
        ),
    )
    caller = _slot(
        "caller",
        body="return callee::<Self>(data);",
        callees=frozenset(
            {
                CallDependency(
                    primitive="callee",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                )
            }
        ),
    )

    _propagate_transitive_call_facts([caller, callee], frozenset())

    assert caller.spec.safety.caller_unsafe is False
    assert caller.spec.safety.internal_unsafe is True
    assert "unsafe_callee" in caller.spec.safety.reasons
    assert "raw_pointer" in caller.spec.safety.reasons
    assert caller.spec.body.requires_unsafe is False
    assert caller.spec.body_text == "return callee::<Self>(data);"


def test_transitive_safety_keeps_runtime_and_immediate_overloads_distinct() -> None:
    runtime = _slot("shift_like")
    immediate = _slot(
        "shift_like",
        safety=ImplementationSafety(
            internal_unsafe=True,
            reasons=frozenset({"intrinsic"}),
        ),
        param_kinds=("v", "sImm"),
        immediate=("shift", "u32"),
    )

    _propagate_transitive_call_facts([runtime, immediate], frozenset())

    assert runtime.spec.body.requires_unsafe is False
    assert immediate.spec.body.requires_unsafe is True
    assert immediate.spec.body_text == "unsafe { return data; }"


def test_call_facts_propagate_bottom_up_recursively() -> None:
    leaf = _slot(
        "leaf",
        required_features=frozenset({"avx512f"}),
        safety=ImplementationSafety(
            internal_unsafe=True,
            caller_unsafe=True,
            reasons=frozenset({"raw_pointer"}),
        ),
    )
    middle = _slot(
        "middle",
        required_features=frozenset({"avx2"}),
        callees=frozenset(
            {
                CallDependency(
                    primitive="leaf",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                )
            }
        ),
    )
    root = _slot(
        "root",
        callees=frozenset(
            {
                CallDependency(
                    primitive="middle",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                )
            }
        ),
    )

    _propagate_transitive_call_facts([root, middle, leaf], frozenset())

    assert middle.spec.required_features == frozenset({"avx2", "avx512f"})
    assert root.spec.required_features == frozenset({"avx2", "avx512f"})
    assert middle.spec.safety.internal_unsafe is True
    assert root.spec.safety.internal_unsafe is True
    assert "unsafe_callee" in middle.spec.safety.reasons
    assert "unsafe_callee" in root.spec.safety.reasons
    assert middle.spec.body.requires_unsafe is False
    assert root.spec.body.requires_unsafe is False


def test_call_facts_propagate_implementation_state_bottom_up() -> None:
    fallback_leaf = _slot(
        "fallback_leaf",
        implementation_state=ImplementationState.FALLBACK,
    )
    unknown_leaf = _slot(
        "unknown_leaf",
        implementation_state=ImplementationState.UNKNOWN,
    )
    fallback_caller = _slot(
        "fallback_caller",
        implementation_state=ImplementationState.COMPOSED,
        callees=frozenset(
            {
                CallDependency(
                    primitive="fallback_leaf",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                )
            }
        ),
    )
    unknown_caller = _slot(
        "unknown_caller",
        implementation_state=ImplementationState.COMPOSED,
        callees=frozenset(
            {
                CallDependency(
                    primitive="unknown_leaf",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                )
            }
        ),
    )
    root = _slot(
        "root",
        implementation_state=ImplementationState.NATIVE,
        callees=frozenset(
            {
                CallDependency(
                    primitive="fallback_caller",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                ),
                CallDependency(
                    primitive="unknown_caller",
                    mask_policy=None,
                    source=VectorIdentity("si32", "scalar"),
                ),
            }
        ),
    )

    _propagate_transitive_call_facts(
        [root, fallback_caller, unknown_caller, fallback_leaf, unknown_leaf],
        frozenset(),
    )

    assert fallback_caller.spec.implementation_state is ImplementationState.FALLBACK
    assert unknown_caller.spec.implementation_state is ImplementationState.UNKNOWN
    assert root.spec.implementation_state is ImplementationState.FALLBACK


def test_pruned_variant_dependency_keeps_variant_origin() -> None:
    dependency = CallDependency(
        primitive="missing",
        mask_policy=None,
        source=VectorIdentity("si32", "scalar"),
    )
    caller = _slot(
        "caller",
        callees=frozenset({dependency}),
        callee_origins=(
            CallDependencyOrigin(
                dependency,
                "implementation variant 'alt'",
            ),
        ),
    )

    grouped, pruned = _prune_unresolved([caller], frozenset())

    assert grouped == {}
    assert pruned == [caller]
    assert caller.unresolved_callee is not None
    assert caller.unresolved_callee.origin == "implementation variant 'alt'"
    assert _pruned_reason(caller) == (
        "pruned: implementation variant 'alt' calls missing<scalar, si32>, "
        "but that specialization is not generated for this profile"
    )


def test_render_profile_features_include_transitive_lowered_requirements() -> None:
    profile = MachineProfile(
        name="fixture",
        family="x86",
        features=frozenset({"sse2"}),
        alternatives={},
    )
    grouped = {
        "rust": {
            "root": [
                _spec(
                    "root",
                    required_features=frozenset({"avx2", "avx512f"}),
                )
            ]
        }
    }

    effective = _profile_with_required_features(profile, grouped)

    assert effective.features == frozenset({"sse2", "avx2", "avx512f"})
    assert effective.name == profile.name


def test_rust_backend_formats_caller_unsafe_contract() -> None:
    spec = _spec(
        "needs_contract",
        safety=ImplementationSafety(
            internal_unsafe=True,
            caller_unsafe=True,
            reasons=frozenset({"raw_pointer"}),
        ),
    )

    rendered = RustBackend().render_primitive("needs_contract", (spec,))

    assert "pub trait Needs_contractImpl: StaticSimdVector" in rendered
    assert "    unsafe fn apply(data: Self::RegisterType)" in rendered
    assert (
        "pub unsafe fn needs_contract<S: detail::primitives::Needs_contractImpl>"
        in rendered
    )
    assert (
        "unsafe { <S as detail::primitives::Needs_contractImpl>::apply(data) }"
        in rendered
    )


def test_rust_backend_emits_target_features_on_impl_body() -> None:
    body = LoweredBody.from_render_text(
        render_sequence(
            (
                "return ",
                RenderPlaceholder("current_owner", "Self"),
                "::lane_count() as i32;",
            )
        )
    )
    spec = _spec(
        "needs_features",
        body=body,
        required_features=frozenset({"avx2", "sse4_1"}),
    )

    rendered = RustBackend(
        feature_alternatives={"sse4_1": "sse4.1"}
    ).render_primitive("needs_features", (spec,))

    assert "    fn apply(data: Self::RegisterType)" in rendered
    assert '#[target_feature(enable = "avx2")]' in rendered
    assert '#[target_feature(enable = "sse4.1")]' in rendered
    assert "unsafe fn __tsl_target_feature_body(" in rendered
    assert "data: <Simd<i32, Scalar> as SimdVector>::RegisterType" in rendered
    assert "return <Simd<i32, Scalar> as SimdVector>::lane_count() as i32;" in rendered
    assert "return Self::lane_count() as i32;" not in rendered
    assert "unsafe { __tsl_target_feature_body(data) }" in rendered


def test_rust_target_features_preserve_raw_self_text() -> None:
    body = LoweredBody.from_render_text(
        render_sequence(
            (
                'let literal = "Self::literal";\n',
                "// Self::line_comment\n",
                "/* Self::block_comment */\n",
                "let Selfish = data;\n",
                "return ",
                RenderPlaceholder("current_owner", "Self"),
                "::lane_count() as i32;",
            )
        )
    )
    spec = _spec(
        "preserves_raw_text",
        body=body,
        required_features=frozenset({"avx2"}),
    )

    rendered = RustBackend().render_primitive("preserves_raw_text", (spec,))

    assert 'let literal = "Self::literal";' in rendered
    assert "// Self::line_comment" in rendered
    assert "/* Self::block_comment */" in rendered
    assert "let Selfish = data;" in rendered
    assert "return <Simd<i32, Scalar> as SimdVector>::lane_count() as i32;" in rendered


def test_rust_backend_can_disable_target_feature_emission() -> None:
    spec = _spec(
        "needs_features",
        required_features=frozenset({"avx2"}),
    )

    rendered = RustBackend(
        emit_target_features=False
    ).render_primitive("needs_features", (spec,))

    assert "#[target_feature" not in rendered
    assert "unsafe fn __tsl_target_feature_body" not in rendered
    assert "return data;" in rendered


def test_source_call_to_caller_unsafe_primitive_uses_local_unsafe(
    catalog: Catalog,
    machine_profiles,
) -> None:
    selected = Selector().select_profile(
        catalog, machine_profiles["sse2"], "to_array", ("si8",)
    ).selected
    slot = next(
        item
        for item in selected
        if item.extension.isa_name == "sse" and item.type_tag == "si8"
    )

    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "rust"),
    ).specialization

    assert lowered is not None
    assert lowered.body.requires_unsafe is False
    assert "MaybeUninit" in lowered.body_text
    assert "unsafe { store::<Self, false, _>(tmp.data(), a) }" in lowered.body_text
    assert not lowered.body_text.startswith("unsafe {")


def test_implementation_variants_lower_and_render_as_detail_symbols() -> None:
    diagnostics, catalog = _catalog_from_source(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        + _base_source(
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
            "        variants:\n"
            "          alt:\n"
            "            safety:\n"
            "              internal_unsafe true\n"
            "              reasons [intrinsic]\n"
            '            tsil "complete(data);"\n'
        )
    )
    assert diagnostics == ()
    profile = MachineProfile(
        name="fixture",
        family="generic",
        features=frozenset(),
        alternatives={},
    )
    slot = Selector().select_profile(catalog, profile, "id", ("si32",)).selected[0]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert cpp is not None
    assert rust is not None
    assert tuple(variant.name for variant in cpp.variant_bodies) == ("alt",)
    assert cpp.safety.internal_unsafe is True
    assert cpp.body.requires_unsafe is False
    assert cpp.variant_bodies[0].body.requires_unsafe is True
    cpp_source = CppBackend().render_primitive("id", (cpp,))
    assert "struct id_impl<" in cpp_source
    assert "struct id_impl_alt<" in cpp_source
    assert "::tsl::detail::primitives::id_impl<" in cpp_source
    assert "::tsl::detail::primitives::id_impl_alt<" not in cpp_source

    rust_source = RustBackend().render_primitive("id", (rust,))
    assert "pub trait IdImpl" in rust_source
    assert "pub trait Id_altImpl" in rust_source
    assert "<S as detail::primitives::IdImpl>::apply(data)" in rust_source
    assert "<S as detail::primitives::Id_altImpl>::apply(data)" not in rust_source
    assert "unsafe { return data; }" in rust_source


def test_primitive_corpus_implementation_bodies_have_local_safety(
    data_root: Path,
    ) -> None:
    documents = SourceLoader().load_dir(data_root / "primitives")
    assert documents.diagnostics == ()
    parsed = TslParser(load_default_tsl_grammar()).parse(documents.documents)
    assert parsed.diagnostics == ()

    missing: list[str] = []

    def walk(
        primitive_name: str,
        entry: ParsedImplementationSelectorEntry,
    ) -> None:
        has_safety = any(field.key.text == "safety" for field in entry.fields)
        for envelope in entry.body_envelopes:
            if not has_safety:
                missing.append(
                    f"{envelope.envelope_source.path}:"
                    f"{envelope.envelope_source.line}: {primitive_name}"
                )
        for variant in entry.variants:
            variant_has_safety = any(
                field.key.text == "safety" for field in variant.fields
            )
            for envelope in variant.body_envelopes:
                if not has_safety and not variant_has_safety:
                    missing.append(
                        f"{envelope.envelope_source.path}:"
                        f"{envelope.envelope_source.line}: {primitive_name}"
                    )
        for child in entry.children:
            walk(primitive_name, child)

    for document in parsed.documents:
        for declaration in document.primitives:
            for entry in declaration.impl_entries:
                walk(declaration.name, entry)

    assert missing == []


def test_primitive_corpus_safety_covers_direct_unsafe_facts(
    catalog: Catalog,
) -> None:
    violations: list[str] = []
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        has_pointer_parameter = shape is not None and "ptr" in shape.param_kinds
        for implementation in primitive.implementations:
            location = (
                f"{implementation.source.path}:{implementation.source.line}"
                if implementation.source is not None
                else f"{primitive.name}:{implementation.selector_path}"
            )
            _require_safety_fact(
                violations,
                location,
                implementation.body_text,
                implementation.safety,
                token="intrin<",
                reason="intrinsic",
            )
            _require_safety_fact(
                violations,
                location,
                implementation.body_text,
                implementation.safety,
                token="mem<",
                reason="raw_memory",
            )
            if has_pointer_parameter:
                if (
                    not implementation.safety.internal_unsafe
                    or not implementation.safety.caller_unsafe
                    or "raw_pointer" not in implementation.safety.reasons
                ):
                    violations.append(f"{location}: missing raw_pointer safety")
            for variant in implementation.variants:
                variant_location = (
                    f"{variant.source.path}:{variant.source.line}"
                    if variant.source is not None
                    else f"{primitive.name}:{implementation.selector_path}:{variant.name}"
                )
                variant_safety = implementation.safety.merge(variant.safety)
                _require_safety_fact(
                    violations,
                    variant_location,
                    variant.body_text,
                    variant_safety,
                    token="intrin<",
                    reason="intrinsic",
                )
                _require_safety_fact(
                    violations,
                    variant_location,
                    variant.body_text,
                    variant_safety,
                    token="mem<",
                    reason="raw_memory",
                )

    assert violations == []


def _catalog_from_source(source: str):
    document = SourceDocument(Path("safety_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    return diagnostics, result.catalog


def _require_safety_fact(
    violations: list[str],
    location: str,
    body_text: str,
    safety: ImplementationSafety,
    *,
    token: str,
    reason: str,
) -> None:
    if token not in body_text:
        return
    if not safety.internal_unsafe or reason not in safety.reasons:
        violations.append(f"{location}: missing {reason} safety")


def _base_source(impls: str) -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "  cpp:\n"
        "    supported true\n"
        "  rust:\n"
        "    supported true\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        f"{impls}"
    )


def _slot(
    primitive_name: str,
    *,
    body: str = "return data;",
    safety: ImplementationSafety = ImplementationSafety(),
    required_features: frozenset[str] = frozenset(),
    implementation_state: ImplementationState = ImplementationState.UNKNOWN,
    param_kinds: tuple[str, ...] = ("v",),
    immediate: tuple[str, str] | None = None,
    callees: frozenset[CallDependency] = frozenset(),
    callee_origins: tuple[CallDependencyOrigin, ...] = (),
) -> _LoweredSlot:
    return _LoweredSlot(
        backend="rust",
        spec=_spec(
            primitive_name,
            body=body,
            safety=safety,
            required_features=required_features,
            implementation_state=implementation_state,
            param_kinds=param_kinds,
            immediate=immediate,
        ),
        callees=callees,
        callee_origins=callee_origins,
    )


def _spec(
    primitive_name: str,
    *,
    body: str | LoweredBody = "return data;",
    safety: ImplementationSafety = ImplementationSafety(),
    required_features: frozenset[str] = frozenset(),
    implementation_state: ImplementationState = ImplementationState.UNKNOWN,
    param_kinds: tuple[str, ...] = ("v",),
    immediate: tuple[str, str] | None = None,
) -> LoweredSpecialization:
    param_names = ("data", "shift") if param_kinds == ("v", "sImm") else ("data",)
    lowered_body = (
        body
        if isinstance(body, LoweredBody)
        else LoweredBody.from_text(
            body,
            unsafe_block_renderer=lambda rendered: f"unsafe {{ {rendered} }}",
            requires_unsafe=safety.internal_unsafe,
        )
    )
    return LoweredSpecialization(
        backend_id="rust",
        primitive_name=primitive_name,
        source_primitive_name=primitive_name,
        extension_name="scalar",
        type_tag="si32",
        base_type_spelling="i32",
        register_spelling="i32",
        result_kind="v",
        param_names=param_names,
        param_kinds=param_kinds,
        body=lowered_body,
        immediate=immediate,
        register_is_base=True,
        required_features=required_features,
        implementation_state=implementation_state,
        safety=safety,
    )
