from pathlib import Path

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import Catalog, Extension, ResolvedVectorRegisterType
from tslgen.io.sources import SourceDocument, SourceLoader
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser


ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
TRANSLATE_RUST_TSL = ROOT / "tsldata" / "detail" / "lang" / "translate_rust.tsl"


def test_extension_catalog_promotes_current_extension_metadata() -> None:
    catalog = _build_catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)

    assert catalog is not None
    assert len(catalog.extensions.extensions) == 12

    avx2 = _extension(catalog, "avx2")
    assert avx2.vendor == "intel"
    assert avx2.extension_name == "avx2"
    assert avx2.family == "x86"
    assert avx2.intrinsic_style == "x86"
    assert avx2.vector_bits == 256
    assert avx2.native_sort_order == 300
    assert avx2.autodetect is True
    assert avx2.lscpu_flags == ("avx2",)
    assert avx2.cpp.supported is True
    assert avx2.cpp.headers == ("immintrin.h",)
    assert avx2.rust.type_name == "Avx2"
    assert avx2.rust.generation_support == ("sse",)
    assert avx2.signature_support_exclude == (
        "void:=(ptr,vidx,v,sImm)",
        "void:=(m,ptr,vidx,v,sImm)",
    )
    assert avx2.test_filter_exclude_templates == ("scatter", "masked_scatter")


def test_x86_register_facts_expand_type_groups_and_inherit_vl_variants() -> None:
    catalog = _build_catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)
    assert catalog is not None

    assert _register_spelling(catalog, "sse", "si32", "cpp") == "__m128i"
    assert (
        _register_spelling(catalog, "sse", "ui64", "rust")
        == "core::arch::x86_64::__m128i"
    )
    assert _register_spelling(catalog, "sse", "f32", "cpp") == "__m128"
    assert (
        _register_spelling(catalog, "sse", "f64", "rust")
        == "core::arch::x86_64::__m128d"
    )
    assert _register_spelling(catalog, "avx2", "si8", "cpp") == "__m256i"
    assert (
        _register_spelling(catalog, "avx512", "ui16", "rust")
        == "core::arch::x86_64::__m512i"
    )

    assert _register_spelling(catalog, "sse_vl", "f64", "cpp") == "__m128d"
    assert (
        _register_spelling(catalog, "avx2_vl", "si32", "rust")
        == "core::arch::x86_64::__m256i"
    )


def test_neon_and_sve_register_facts_are_concrete_per_type() -> None:
    catalog = _build_catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)
    assert catalog is not None

    assert _register_spelling(catalog, "neon", "si8", "cpp") == "int8x16_t"
    assert (
        _register_spelling(catalog, "neon", "ui8", "rust")
        == "core::arch::aarch64::uint8x16_t"
    )
    assert (
        _register_spelling(catalog, "neon", "f64", "rust")
        == "core::arch::aarch64::float64x2_t"
    )

    assert _register_spelling(catalog, "sve", "si16", "cpp") == "svint16_t"
    assert _register_spelling(catalog, "sve", "f32", "cpp") == "svfloat32_t"
    assert not _register_facts(catalog, "sve", "f32", "rust")


def test_scalar_generic_and_mask_policies_are_typed() -> None:
    catalog = _build_catalog_from_paths(TYPES_TSL, EXTENSIONS_TSL)
    assert catalog is not None

    sse = _extension(catalog, "sse")
    assert sse.mask_type_policy is not None
    assert sse.mask_type_policy.kind == "lane_bitmask"
    assert sse.mask_type_policy.width == "lanes"
    assert sse.integral_mask_type_policy is not None
    assert sse.integral_mask_type_policy.kind == "lane_bitmask"

    avx512 = _extension(catalog, "avx512")
    assert avx512.mask_type_policy is not None
    assert avx512.mask_type_policy.kind == "native_predicate_by_lanes"
    assert (
        _lane_spelling(avx512, backend="cpp", lanes=64) == "__mmask64"
    )
    assert (
        _lane_spelling(avx512, backend="rust", lanes=32)
        == "core::arch::x86_64::__mmask32"
    )
    assert avx512.integral_mask_type_policy is not None
    assert avx512.integral_mask_type_policy.kind == "same_as_mask_type"

    sse_vl = _extension(catalog, "sse_vl")
    assert sse_vl.mask_type_policy is not None
    assert sse_vl.mask_type_policy.kind == "native_predicate_by_lanes"
    assert _lane_spelling(sse_vl, backend="cpp", lanes=16) == "__mmask16"

    avx2_vl = _extension(catalog, "avx2_vl")
    assert avx2_vl.mask_type_policy is not None
    assert avx2_vl.mask_type_policy.kind == "native_predicate_by_lanes"
    assert _lane_spelling(avx2_vl, backend="cpp", lanes=32) == "__mmask32"
    assert (
        _lane_spelling(avx2_vl, backend="rust", lanes=32)
        == "core::arch::x86_64::__mmask32"
    )

    sve = _extension(catalog, "sve")
    assert sve.mask_type_policy is not None
    assert sve.mask_type_policy.kind == "native_predicate"
    assert _policy_spelling(sve, "cpp") == "svbool_t"

    scalar = _extension(catalog, "scalar")
    assert scalar.vector_register_type_policy is not None
    assert scalar.vector_register_type_policy.kind == "base_type"
    assert scalar.mask_type_policy is not None
    assert scalar.mask_type_policy.kind == "bool"
    assert scalar.integral_mask_type_policy is not None
    assert scalar.integral_mask_type_policy.kind == "unsigned_scalar"
    assert _policy_spelling(scalar, "rust", integral=True) == "u64"

    generic = _extension(catalog, "generic")
    assert generic.size_parameter is not None
    assert generic.size_parameter.kind == "lanes"
    assert generic.size_parameter.name == "LANES"
    assert generic.vector_register_type_policy is not None
    assert generic.vector_register_type_policy.kind == "fixed_array"
    assert generic.vector_register_type_policy.element == "base_type"
    assert generic.vector_register_type_policy.length == "LANES"
    assert "Vec" not in repr(generic.vector_register_type_policy)
    assert generic.mask_repr == "lane_bitmask"
    assert generic.mask_width == "lanes"

    assert _extension(catalog, "sse").mask_repr == "lane_bitmask"
    assert _extension(catalog, "avx2").mask_repr == "lane_bitmask"
    assert _extension(catalog, "neon").mask_repr == "lane_bitmask"


def test_rust_generic_source_shape_uses_lane_count_not_runtime_vectors() -> None:
    text = TRANSLATE_RUST_TSL.read_text(encoding="utf-8")

    assert "pub struct Generic<const LANES: usize>;" in text
    assert "pub struct Generic<const BITS: usize>;" not in text
    assert "[Self::BaseType::default(); Self::LANES]" in text
    assert "alloc::vec![Self::BaseType::default(); Self::LANES]" not in text


def test_malformed_extension_register_selector_is_diagnostic() -> None:
    catalog_result = _build_catalog_from_texts(
        (
            "types.tsl",
            """types:
  si32 {types [si32]}
""",
        ),
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  vector_register_types:
    unknown:
      cpp "broken_register"
""",
        ),
    )

    assert catalog_result.catalog is None
    assert _diagnostic_codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-UNKNOWN-TYPE-SELECTOR",
    )
    assert catalog_result.diagnostics[0].location is not None
    assert catalog_result.diagnostics[0].location.line == 4


def test_malformed_extension_policy_is_diagnostic() -> None:
    catalog_result = _build_catalog_from_texts(
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  mask_type_policy:
    width "lanes"
""",
        ),
    )

    assert catalog_result.catalog is None
    assert _diagnostic_codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-MALFORMED-EXTENSION-METADATA",
    )
    assert catalog_result.diagnostics[0].severity == "error"
    assert catalog_result.diagnostics[0].location is not None
    assert catalog_result.diagnostics[0].location.line == 3


def test_unknown_extension_policy_kind_is_diagnostic() -> None:
    catalog_result = _build_catalog_from_texts(
        (
            "extension.tsl",
            """extension broken:
  extension_name "broken"
  mask_type_policy:
    kind "runtime_vec"
""",
        ),
    )

    assert catalog_result.catalog is None
    assert _diagnostic_codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-UNSUPPORTED-EXTENSION-POLICY",
    )
    assert catalog_result.diagnostics[0].location is not None
    assert catalog_result.diagnostics[0].location.line == 4


def test_unknown_extension_parent_is_diagnostic() -> None:
    catalog_result = _build_catalog_from_texts(
        (
            "extension.tsl",
            """extension child:
  extension_name "child"
  inherits "missing"
""",
        ),
    )

    assert catalog_result.catalog is None
    assert _diagnostic_codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-UNKNOWN-EXTENSION-PARENT",
    )


def test_extension_inheritance_cycle_is_diagnostic() -> None:
    catalog_result = _build_catalog_from_texts(
        (
            "extension.tsl",
            """extension first:
  extension_name "first"
  inherits "second"

extension second:
  extension_name "second"
  inherits "first"
""",
        ),
    )

    assert catalog_result.catalog is None
    assert _diagnostic_codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-EXTENSION-INHERITANCE-CYCLE",
    )


def _build_catalog_from_paths(*paths: Path) -> Catalog | None:
    source_result = SourceLoader().load(tuple(paths))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    return catalog_result.catalog


def _build_catalog_from_texts(
    *documents: tuple[str, str],
):
    sources = tuple(
        SourceDocument(
            path=Path(name),
            text=text,
            digest="",
            kind="tsl",
        )
        for name, text in documents
    )
    parse_result = TslParser().parse(sources)
    assert parse_result.diagnostics == ()
    return CatalogBuilder().build(parse_result.documents)


def _extension(catalog: Catalog, name: str) -> Extension:
    extension = catalog.extensions.get(name)
    assert extension is not None
    return extension


def _register_spelling(
    catalog: Catalog,
    extension: str,
    type_tag: str,
    backend: str,
) -> str:
    facts = _register_facts(catalog, extension, type_tag, backend)
    assert len(facts) == 1
    return facts[0].spelling


def _register_facts(
    catalog: Catalog,
    extension: str,
    type_tag: str,
    backend: str,
) -> tuple[ResolvedVectorRegisterType, ...]:
    return tuple(
        fact
        for fact in _extension(catalog, extension).resolved_vector_register_types
        if fact.type_tag == type_tag and fact.backend == backend
    )


def _lane_spelling(extension: Extension, *, backend: str, lanes: int) -> str:
    assert extension.mask_type_policy is not None
    matches = tuple(
        spelling
        for spelling in extension.mask_type_policy.lane_spellings
        if spelling.backend == backend and spelling.lanes == lanes
    )
    assert len(matches) == 1
    return matches[0].spelling


def _policy_spelling(
    extension: Extension,
    backend: str,
    *,
    integral: bool = False,
) -> str:
    policy = (
        extension.integral_mask_type_policy
        if integral
        else extension.mask_type_policy
    )
    assert policy is not None
    matches = tuple(
        spelling for spelling in policy.spellings if spelling.backend == backend
    )
    assert len(matches) == 1
    return matches[0].spelling


def _diagnostic_codes(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)
