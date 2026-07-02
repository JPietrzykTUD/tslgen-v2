"""Implementation safety is a typed source and lowering contract."""

from __future__ import annotations

from pathlib import Path

from tslc.backend.translation import create_backend_dialect
from tslc.backend.rust import RustBackend
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, ImplementationSafety
from tslc.catalog.signatures import parse_signature
from tslc.catalog.validation import validate_catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import Diagnostic
from tslc.lower.dependencies import CallDependency, VectorIdentity
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.pipeline import (
    _LoweredSlot,
    _profile_with_required_features,
    _propagate_transitive_call_facts,
)
from tslc.render.model import LoweredBody
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

    assert "pub trait Needs_contractImpl: SimdVector" in rendered
    assert "    unsafe fn apply(data: Self::RegisterType)" in rendered
    assert (
        "pub unsafe fn needs_contract<S: detail::primitives::Needs_contractImpl>"
        in rendered
    )
    assert (
        "unsafe { <S as detail::primitives::Needs_contractImpl>::apply(data) }"
        in rendered
    )


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
    param_kinds: tuple[str, ...] = ("v",),
    immediate: tuple[str, str] | None = None,
    callees: frozenset[CallDependency] = frozenset(),
) -> _LoweredSlot:
    return _LoweredSlot(
        backend="rust",
        spec=_spec(
            primitive_name,
            body=body,
            safety=safety,
            required_features=required_features,
            param_kinds=param_kinds,
            immediate=immediate,
        ),
        callees=callees,
    )


def _spec(
    primitive_name: str,
    *,
    body: str = "return data;",
    safety: ImplementationSafety = ImplementationSafety(),
    required_features: frozenset[str] = frozenset(),
    param_kinds: tuple[str, ...] = ("v",),
    immediate: tuple[str, str] | None = None,
) -> LoweredSpecialization:
    param_names = ("data", "shift") if param_kinds == ("v", "sImm") else ("data",)
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
        body=LoweredBody.from_text(
            body,
            backend_id="rust",
            requires_unsafe=safety.internal_unsafe,
        ),
        immediate=immediate,
        register_is_base=True,
        required_features=required_features,
        safety=safety,
    )
