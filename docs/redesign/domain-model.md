# Domain Model

This document defines the target domain model from first principles. Class sketches are illustrative contracts, not implementation code to copy directly.

## Terminology

| Term | Meaning |
| --- | --- |
| TSL source | A `.tsl` file containing domain declarations. |
| Primitive | A named SIMD operation family or variant, such as `add`, `load`, `store`, or `mask_true`. |
| Signature | A compact shape such as `v:=(v,v)` that describes semantic input/output categories. |
| Attribute | A variant selector such as `mask=zero`, `aligned=true`, `cast=convert`, or `direction=up`. |
| Template | A normalized operation shape such as `binary`, `masked_binary`, or `load`; used by planners and backends. |
| Type tag | A concrete type identifier such as `si32`, `ui8`, or `f64`. |
| Type group | A named set of type tags such as `?i?`, `arith`, `f?`, or `dqword`. |
| Lane set | A named relation between lane counts and type tags used by tests. |
| Extension | A hardware target or abstraction such as `sse`, `avx2`, `avx512`, `neon`, `sve`, `scalar`, or `generic`. |
| Backend | An output language or artifact family such as C++ or Rust. |
| Implementation | A backend-eligible body or intrinsic choice for a primitive, target extension, type group, and requirement set. |
| TSIL | The implementation language embedded in TSL strings. |
| Artifact | A generated file-like output with logical name, extension, content, and metadata. |
| Diagnostic | A structured message with severity, code, source location, and actionable text. |

## Model Layers

The model has three layers:

1. Syntax layer: source documents, spans, syntax nodes, raw values.
2. Domain catalog layer: typed semantic declarations from TSL and manifests.
3. Pipeline IR layer: selected candidates, lowered operations, render plans, artifacts.

The syntax layer may use flexible data structures. The domain and pipeline layers should not use arbitrary dictionaries as primary objects.

## Core Value Objects

### Source Identity

```python
@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: Path
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None

@dataclass(frozen=True, slots=True)
class SourceSpan:
    location: SourceLocation
    text: str | None = None
```

Invariants:

- `line` and `column` are one-based when present.
- Locations are carried into diagnostics, not into core equality checks unless needed.

### Catalog Values

Some TSL fields are extensible. Preserve structured values with a constrained immutable value type:

```python
CatalogValue = str | int | float | bool | None | tuple["CatalogValue", ...] | FrozenMap[str, "CatalogValue"]
```

Invariants:

- Parser-private keys do not enter catalog values.
- Order is preserved for tuples and deterministic for maps.
- Field-level preservation does not replace typed accessors for known fields.
- Repeated keys inside nested preserved fields are retained as grouped tuple values until
  a later semantic stage defines whether they should merge, override, or diagnose.

### Names And IDs

Use small value objects or validated string aliases for:

- `PrimitiveName`
- `TemplateName`
- `ExtensionName`
- `BackendId`
- `LanguageId`
- `TypeTag`
- `TypeGroupName`
- `LaneSetName`
- `FeatureFlag`

Invariants:

- Names are non-empty.
- Normalization is explicit and stage-specific. For example, feature flags normalize through the flag catalog; primitive names should not be silently case-normalized.

### Machine Feature Profiles

Machine feature profiles are build metadata facts, not compiler capability
rules.

```python
@dataclass(frozen=True, slots=True)
class FeatureFlagNormalization:
    spelling: FeatureFlagSpelling
    normalized: FeatureFlagName
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class MachineFeatureAlternative:
    feature: FeatureFlagName
    spelling: FeatureFlagSpelling

@dataclass(frozen=True, slots=True)
class MachineFeatureProfile:
    family: MachineProfileFamily
    name: MachineProfileName
    features: tuple[FeatureFlagName, ...]
    alternatives: tuple[MachineFeatureAlternative, ...]
    source: SourceLocation
```

Invariants:

- Feature flags normalize through the flag normalization catalog.
- Profile data may be loaded from JSON at the configuration/build metadata
  boundary, but downstream code consumes typed profile values.
- The scalar `NOSIMD-INVALID` source spelling means no SIMD feature flags.
- Alternative values are source-provided build/presentation spellings, not
  compiler support fallbacks.
- Compiler capability policy, host autodetection, and compiler option spelling
  are separate backend/tooling concerns.

### Backend Metadata

Backend metadata records language type spellings and translation templates as
typed catalog facts. These are inputs to later backend translation stages, not
rendered output.

```python
@dataclass(frozen=True, slots=True)
class BackendLanguageTypeSpelling:
    backend: BackendId
    type_key: BackendTypeKey
    spelling: BackendTypeSpellingText
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendTranslationTemplate:
    backend: BackendId
    key: BackendTranslationKey
    template: BackendTemplateText
    source: SourceLocation
```

Invariants:

- C++ and Rust are the active backend metadata sources in the current product
  path; C17 remains deferred evidence.
- Translation template text is inert until a later typed backend translation
  rule explicitly consumes it.
- A backend metadata catalog can answer missing-type and missing-translation
  lookups with diagnostics instead of raw key errors.
- Raw dictionaries may exist at parse/loader boundaries only; backend/output
  stages consume typed metadata values.

Backend type spelling translation is a backend/output result boundary over
typed lowering requests and typed backend metadata:

```python
@dataclass(frozen=True, slots=True)
class BackendTranslatedTypeSpelling:
    request: BackendTypeSpellingRequest
    backend: BackendId
    spelling: BackendTypeSpellingText
    metadata_kind: Literal["language_type", "translation_template"]
    metadata_key: BackendTypeKey | BackendTranslationKey
    metadata_source: SourceLocation
    source: SourceLocation
```

Invariants:

- The request is already a typed lowering handoff value; this boundary never
  parses raw `type<backend>(...)` text.
- Scalar spelling uses explicit `si* -> s*` and `ui* -> u*` normalization
  before looking up active language-map metadata.
- `LoweredSizeType()` is the only accepted translation-template-backed type
  spelling in the first slice and resolves through `type_size`.
- Vector, register, mask, generic, extension-transform, and arbitrary template
  fulfillment remain unsupported until selected by a later milestone.

Backend value translation is a backend/output result boundary over typed
backend value requests and typed backend metadata:

```python
BackendValueText = NewType("BackendValueText", str)

@dataclass(frozen=True, slots=True)
class BackendTranslatedValue:
    request: BackendValueRequest
    backend: BackendId
    value: BackendValueText
    metadata_key: BackendTranslationKey
    metadata_source: SourceLocation
    source: SourceLocation
```

Invariants:

- The request is already a typed lowering handoff value; this boundary never
  parses raw `value<backend>(...)` text.
- Metadata-only value requests may be fulfilled from exact backend translation
  metadata keys when the template has no unresolved named placeholders.
- Literal braces in backend text are not placeholders. Named `{type}`-style
  fields require typed semantic inputs and are diagnostics until a later rule
  provides those inputs explicitly.
- Intrinsic composition modifiers are supported only for selected typed
  modifier families. Literal modifier fragments, type-derived suffixes, and
  selected x86-family prefix fragments are accepted backend translation facts.
  Other intrinsic suffix/prefix requests, source operations, control
  directives, mask constants, primitive calls, and rendering remain unsupported
  until selected by later milestones.

Backend intrinsic modifier translation is a backend/output result boundary
over typed `BackendIntrinsicComposeHandoffRequest` values. It translates final
literal modifier components that were already accepted by lowering, plus
selected metadata-backed semantic modifier families:

```python
@dataclass(frozen=True, slots=True)
class BackendTranslatedIntrinsicModifier:
    backend: BackendId
    field: BackendIntrinsicModifierField
    name: BackendIntrinsicModifierName
    value: (
        BackendIntrinsicLiteralFragment
        | BackendIntrinsicInfixSeparator
        | BackendIntrinsicImmediateLiteral
        | BackendIntrinsicImmediateParameterReference
        | BackendIntrinsicImmediateGenericParameterReference
    )
    source: SourceLocation
```

Invariants:

- The request is already a typed M182 handoff value; this boundary never parses
  raw `intrin_compose<...>(...)` source text.
- Translation is per modifier. It does not assemble intrinsic names, inspect
  intrinsic arguments, validate intrinsic base tokens, or render output.
- Literal `suffix`, `post`, `infix`, `infix_sep`, and integer `immediate(N)`
  forms may be translated when they are already final fragments.
- Type-derived suffix operands
  `suffix=value<backend>(intrin::suffix(TYPE))` may be translated through
  typed extension context and backend metadata when `TYPE` has already lowered
  to a scalar type identity.
- Current-type suffix operands
  `suffix=value<backend>(intrin::suffix)` and
  `infix=value<backend>(intrin::suffix)` may be translated through typed
  selected/current `TypeTag`, selected extension context, and backend metadata.
  The field name controls later placement; this boundary does not assemble
  final intrinsic names.
- Named suffix operands for the exact form
  `suffix=value<backend>(intrin::suffix("stream"))` may be translated through
  selected extension context and backend metadata for `sse`, `sse_vl`, `avx2`,
  `avx2_vl`, and `avx512`. The quoted value is a named policy, not raw emitted
  text or general quoted-string suffix support.
- Destination/return-type suffix operands may be translated for `suffix` and
  `infix` fields only after selected-binding lowering has produced a
  `BackendValueTypeOperand(LoweredScalarTypeIdentity(...))`. Source-owned
  names such as `ToBase` or `ResultBase` are not backend keywords and raw
  symbol operands are still rejected.
- The exact legacy marker `infix=to_type_suffix` may be lowered as a
  destination/return-type suffix only when the selected primitive declares
  `return_type: base: NAME` and the selected target supplies the matching
  `TargetReturnTypeBaseBinding`. The marker is represented by a small typed
  semantic modifier operand, not by a fake `value<backend>(...)` island or a
  raw backend string.
- Selected x86-family prefix operands
  `prefix=value<backend>(intrin::prefix)` may be translated through selected
  extension context and backend metadata for `sse`, `sse_vl`, `avx2`,
  `avx2_vl`, and `avx512`.
- Metadata-backed modifier translation maps typed facts to backend metadata
  keys. Fragment text comes from the backend metadata catalog, not hardcoded
  Python strings.
- Rust `core::arch::*` intrinsic qualification, intrinsic-name assembly,
  arbitrary quoted suffixes, unresolved raw symbol suffixes, unresolved raw
  symbol immediates, wildcard-looking fragments, quoted-string infix suffixes,
  and unbound or context-free `infix=to_type_suffix` remain unsupported
  diagnostics until later typed rules explicitly provide those semantics.

Backend intrinsic invocation assembly is a backend/output result boundary
over accepted direct/composed intrinsic handoff requests and translated
intrinsic modifier values:

```python
BackendIntrinsicNamePartRole = Literal["prefix", "base", "infix", "suffix", "post"]

@dataclass(frozen=True, slots=True)
class BackendIntrinsicInvocationArguments:
    text: BackendIntrinsicArgumentPayloadText
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicNamePart:
    role: BackendIntrinsicNamePartRole
    text: BackendIntrinsicNameText
    source: SourceLocation
    modifier: BackendTranslatedIntrinsicModifier | None = None

@dataclass(frozen=True, slots=True)
class BackendIntrinsicInvocationImmediate:
    argument_index: int
    value: (
        BackendIntrinsicImmediateLiteral
        | BackendIntrinsicImmediateParameterReference
        | BackendIntrinsicImmediateGenericParameterReference
    )
    source: SourceLocation
    modifier: BackendTranslatedIntrinsicModifier

@dataclass(frozen=True, slots=True)
class BackendDirectIntrinsicInvocation:
    backend: BackendId
    request: BackendDirectIntrinsicHandoffRequest
    intrinsic_name: BackendIntrinsicNameText
    arguments: BackendIntrinsicInvocationArguments
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendComposedIntrinsicInvocation:
    backend: BackendId
    request: BackendIntrinsicComposeHandoffRequest
    intrinsic_name: BackendIntrinsicNameText
    name_parts: tuple[BackendIntrinsicNamePart, ...]
    arguments: BackendIntrinsicInvocationArguments
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...]
    source: SourceLocation
```

Invariants:

- Assembly consumes typed handoff requests and typed translated modifiers. It
  never parses raw `intrin<...>(...)` / `intrin_compose<...>(...)` source
  text and never re-enters lowering.
- Direct invocations are accepted only when the direct angle payload is already
  a literal backend intrinsic name. Placeholder/template-like payloads are
  diagnostics, not renderer input.
- Composed invocation names are assembled deterministically from translated
  `prefix`, base, `infix`, `suffix`, `post`, and `infix_sep` values.
- Intrinsic argument payloads remain opaque source text with provenance.
- Immediate modifier translations become typed compile-time metadata for a
  later renderer; this boundary does not decide C++ non-type template syntax
  or Rust const generic syntax.
- Language renderers consume assembled invocation values. They do not decide
  intrinsic-name assembly, suffix/prefix semantics, immediacy, or direct-name
  placeholder resolution.

C++ intrinsic call rendering is a backend/output render-result boundary over
assembled M213 invocation values:

```python
CppIntrinsicCallText = NewType("CppIntrinsicCallText", str)

@dataclass(frozen=True, slots=True)
class CppRenderedIntrinsicCall:
    invocation: BackendAssembledIntrinsicInvocation
    call_text: CppIntrinsicCallText
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class CppIntrinsicCallRenderResult:
    call: CppRenderedIntrinsicCall | None
    diagnostics: tuple[Diagnostic, ...] = ()
```

Invariants:

- Rendering consumes only assembled M213 direct/composed invocation values.
  It does not parse raw TSIL or reassemble intrinsic names.
- M214 supports only backend `cpp`; non-C++ invocation values are diagnostics.
- The rendered call text is exactly
  `assembled_name(opaque_argument_payload)`, with `assembled_name()` for empty
  payloads.
- Argument payload text remains opaque and is not split, normalized, repaired,
  or recursively lowered.
- Immediate metadata is preserved for later wrapper/signature/template work.
  M214 does not render C++ non-type template syntax.

Rust intrinsic call rendering is a backend/output render-result boundary over
assembled M213 invocation values plus an explicit architecture module:

```python
@dataclass(frozen=True, slots=True)
class RustArchitectureModule:
    name: str

RustIntrinsicCallText = NewType("RustIntrinsicCallText", str)

@dataclass(frozen=True, slots=True)
class RustRenderedIntrinsicCall:
    invocation: BackendAssembledIntrinsicInvocation
    architecture_module: RustArchitectureModule
    call_text: RustIntrinsicCallText
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class RustIntrinsicCallRenderResult:
    call: RustRenderedIntrinsicCall | None
    diagnostics: tuple[Diagnostic, ...] = ()
```

Invariants:

- Rendering consumes only assembled M213 direct/composed invocation values.
  It does not parse raw TSIL or reassemble intrinsic names.
- M219 supports only backend `rust`; non-Rust invocation values are
  diagnostics.
- The rendered call text is exactly
  `core::arch::{module}::{assembled_name}(opaque_argument_payload)`, with
  `core::arch::{module}::{assembled_name}()` for empty payloads.
- `RustArchitectureModule` is an explicit typed render input. The renderer
  never infers `x86_64`, `aarch64`, or any other module from intrinsic name
  text.
- Argument payload text remains opaque and is not split, normalized, repaired,
  or recursively lowered.
- Immediate metadata is preserved for later wrapper/signature/template work.
  M219 does not render Rust const-generic syntax.

C++ body-token substitution rendering is a presentation boundary over accepted
backend-intrinsic handoff streams and already-rendered C++ intrinsic calls:

```python
CppBodyText = NewType("CppBodyText", str)

@dataclass(frozen=True, slots=True)
class CppRenderedBodyTokens:
    handoff: BackendIntrinsicHandoff
    text: CppBodyText
    calls: tuple[CppRenderedIntrinsicCall, ...]
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class CppBodyTokenRenderResult:
    body: CppRenderedBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()
```

Invariants:

- Rendering preserves opaque text segments exactly and in source order.
- Rendering substitutes only `BackendIntrinsicHandoffRequestSegment` values
  that have matching `CppRenderedIntrinsicCall` values. Matching uses the typed
  request object preserved through the invocation/call provenance, not raw text
  rescans.
- Surrounding target-like syntax such as `return`, assignments, indexing,
  braces, semicolons, and operators remains raw source text. M215 does not
  parse or synthesize statement shapes.
- Opaque non-text body-token segments are unsupported diagnostics until those
  tokens are lowered/rendered by a selected future boundary.
- Rendered calls and flattened typed immediate metadata are preserved on the
  result for later wrapper/signature/template work.

## Primitive Model

```python
@dataclass(frozen=True, slots=True)
class Signature:
    result: SignatureTerm
    parameters: tuple[SignatureTerm, ...]
    repeated_parameter: bool = False

@dataclass(frozen=True, slots=True)
class PrimitiveParameter:
    name: str
    type_hint: str | None = None
    span: SourceSpan | None = None

@dataclass(frozen=True, slots=True)
class PrimitiveAttributes:
    values: FrozenMap[str, CatalogValue]

@dataclass(frozen=True, slots=True)
class PrimitiveReturnTypeBinding:
    kind: Literal["base", "extension"]
    name: str
    span: SourceSpan

class GenericParameterKind(Enum):
    INT = "int"
    BOOL = "bool"
    SIMD_TYPE = "simd_type"

@dataclass(frozen=True, slots=True)
class GenericParameter:
    name: str
    kind: GenericParameterKind
    default: int | bool | None
    span: SourceSpan

@dataclass(frozen=True, slots=True)
class PrimitiveDeclaration:
    name: PrimitiveName
    signature: Signature
    parameters: tuple[PrimitiveParameter, ...]
    attributes: PrimitiveAttributes
    return_type_binding: PrimitiveReturnTypeBinding | None
    documentation: PrimitiveDocumentation
    generic_parameters: tuple[GenericParameter, ...]
    immediate: ImmediateSpec | None
    tests: tuple[PrimitiveTestSpec, ...]
    implementations: tuple[ImplementationSpec, ...]
    source: SourceSpan
```

Relationships:

- A primitive name can have many declarations.
- A declaration resolves to one template after signature and attribute validation.
- A declaration can expand into multiple concrete variants when it has boolean wildcard attributes.
- A declaration may optionally introduce one primitive-local return-type
  binding such as `base: ResultBase` or `extension: TargetExtension`.
- A declaration may introduce primitive-local generic parameters. These are
  compile-time/template parameters of the primitive interface, not runtime
  value parameters.

Invariants:

- Parameter count must match the signature shape after repeated/immediate rules are applied.
- Attributes must be valid for the signature and template.
- Generic parameter names are arbitrary source-defined identifiers. The
  observed kinds are `int`, `bool`, and `simd_type`; defaults are typed as
  integers, booleans, or absent.
- Return-type binding names are arbitrary source-defined identifiers, not
  generator keywords. `ToBase` and `ToExtension` are corpus examples only.
- Absence of `return_type` is normal and means the declaration has no
  return-type binding.
- A declaration must have a stable source identity for diagnostics.
- Wildcard attributes must not survive past variant expansion.

## Signature Model

Signatures should be parsed into terms rather than treated only as strings.

Supported terms observed in repository evidence include:

- `v`: vector register
- `m`: mask
- `s`: scalar
- `sImm`: scalar immediate
- `ptr`: pointer
- `vidx`: vector index
- `void`: no return value
- `o`: output stream
- `sequence`: sequence value
- `s[]`: scalar array
- `v[idx]`: indexed vector element
- `ptr+`: pointer with conversion semantics
- `s...`: repeated scalar parameters

Invariants:

- Normalized string form is stable.
- Unknown terms produce diagnostics unless introduced through a documented extension point.
- Primitive parameter names bind positionally to signature parameter terms in
  the catalog. Compile-time immediate evidence comes from the bound term, such
  as `sImm`, not from user-owned names such as `index` or `Index`.
- Selected lowering context carries the typed primitive signature and
  parameter-to-term bindings when a selected implementation is lowered.
- Signature-to-template resolution is data-driven.

## Template Model

```python
@dataclass(frozen=True, slots=True)
class OperationTemplate:
    name: TemplateName
    description: str | None
    shape: OperationShape
    required_fields: frozenset[str]
    optional_fields: frozenset[str]
    source: SourceSpan
```

Invariants:

- Required fields must be satisfied by primitive attributes or implementation metadata at the documented validation point.
- Template shape is descriptive and should eventually be parsed for validation.

Concepts:

- Templates are domain operation shapes, not Jinja filenames.
- Backend renderers may map templates to rendering strategies, but that mapping must not leak into primitive semantics.

## Type And Lane Model

```python
@dataclass(frozen=True, slots=True)
class TypeGroup:
    name: TypeGroupName
    members: tuple[TypeTag, ...]
    source: SourceSpan

@dataclass(frozen=True, slots=True)
class LaneSet:
    name: LaneSetName
    lanes: tuple[int, ...]
    types: tuple[TypeTag, ...]
    source: SourceSpan
```

Invariants:

- Type group expansion preserves declared order.
- Lane counts are positive integers.
- A test referencing a lane set must use a type included by that lane set, directly or through a compatible type group.

## Extension Model

```python
@dataclass(frozen=True, slots=True)
class Extension:
    name: ExtensionName
    extension_name: str | None
    vendor: str | None
    inherits: ExtensionName | None
    family: str | None
    intrinsic_style: str | None
    vector_bits: VectorBits | None
    native_sort_order: int | None
    autodetect: bool | None
    lscpu_flags: tuple[FeatureFlag, ...]
    mask_repr: MaskRepresentation | None
    mask_width: MaskWidth | None
    mask_vector_loadable: bool | None
    runtime_lanes: bool | None
    default_test_target: bool | None
    cpp: ExtensionBackendMetadata
    rust: ExtensionBackendMetadata
    signature_support_exclude: tuple[str, ...]
    test_filter_exclude_templates: tuple[str, ...]
    test_sizes_bits: tuple[int, ...]
    vector_register_types: tuple[VectorRegisterTypeEntry, ...]
    resolved_vector_register_types: tuple[ResolvedVectorRegisterType, ...]
    vector_register_type_policy: ExtensionTypePolicy | None
    size_parameter: ExtensionSizeParameter | None
    mask_type_policy: ExtensionTypePolicy | None
    integral_mask_type_policy: ExtensionTypePolicy | None
    source: SourceSpan

@dataclass(frozen=True, slots=True)
class ExtensionCatalog:
    extensions: tuple[Extension, ...]
```

Supporting values:

```python
VectorBits = FixedBits | SizedBits | ScalableBits
MaskRepresentation = Literal["bitset", "vector", "scalar", "bitset_array", "lane_bitmask"]
MaskWidth = Literal["lanes"] | int

@dataclass(frozen=True, slots=True)
class ExtensionBackendMetadata:
    supported: bool | None
    type_name: str | None
    generation_support: tuple[ExtensionName, ...]
    headers: tuple[str, ...]
    header_guard: str | None
    test_suite_name: str | None
    test_support_header: str | None
    source: SourceSpan | None

@dataclass(frozen=True, slots=True)
class VectorRegisterTypeEntry:
    selector: TypeTag | TypeGroupName
    backend_spellings: tuple[BackendTypeSpelling, ...]

@dataclass(frozen=True, slots=True)
class ResolvedVectorRegisterType:
    extension: ExtensionName
    type_tag: TypeTag
    backend: BackendId
    spelling: str

@dataclass(frozen=True, slots=True)
class ExtensionTypePolicy:
    kind: Literal[
        "base_type",
        "fixed_array",
        "lane_bitmask",
        "native_predicate",
        "native_predicate_by_lanes",
        "same_as_mask_type",
        "bool",
        "unsigned_scalar",
    ]
    element: str | None
    length: str | None
    width: str | None
    backend_spellings: tuple[BackendTypeSpelling, ...]
    backend_lane_spellings: tuple[BackendLaneTypeSpelling, ...]

@dataclass(frozen=True, slots=True)
class ExtensionSizeParameter:
    kind: str
    name: str
    source: SourceSpan
```

Invariants:

- Inheritance references an existing extension.
- Inheritance graph is acyclic.
- `runtime_lanes=true` means test and generation planning cannot assume a fixed lane count from vector bits alone.
- `vector_bits="sized"` requires a size parameter when concrete artifacts/tests are planned.
- Backend support is explicit; lack of support filters candidates for that backend.
- Vector register facts are source-data facts attached to extensions, not
  renderer-side inference. Native fixed-width x86 extensions may use
  type-group selectors such as `?i?`; NEON and SVE use concrete per-type
  entries where signedness affects the native type spelling.
- `generic` uses a compile-time lane-count fixed-array policy for register
  storage. Rust generic registers must not be modeled as runtime-growing
  vectors.
- Vector mask type and integral mask type are separate policies. For
  `lane_bitmask`, the valid semantic bit count is exactly the lane count even
  when backend storage uses the smallest wider unsigned integer type.

## Implementation Model

```python
@dataclass(frozen=True, slots=True)
class ImplementationSelector:
    kind: Literal["extension", "type_group"]
    raw: str
    names: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class LowerableOperationFragment:
    operation: str
    arguments: tuple[str, ...]
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class RawStringToken:
    text: str
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class SelfPrimitiveReference:
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class NamedPrimitiveReference:
    name: str
    source_span: SourceSpan

PrimitiveCallTarget = SelfPrimitiveReference | NamedPrimitiveReference

@dataclass(frozen=True, slots=True)
class PrimitiveCallSelector:
    target: PrimitiveCallTarget
    specialization: str | None
    attrs: str | None
    source_text: str
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class PrimitiveCallArgument:
    text: str
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class PrimitiveCall:
    selector: PrimitiveCallSelector
    payload: str
    source_span: SourceSpan
    arguments: tuple[PrimitiveCallArgument, ...] = ()

@dataclass(frozen=True, slots=True)
class LowerableDirective:
    name: str
    arguments: tuple[str, ...]
    source_span: SourceSpan
    primitive_call: PrimitiveCall | None = None
    payload_tokens: tuple["PayloadToken", ...] = ()

PayloadToken = RawStringToken | LowerableDirective
BodyToken = RawStringToken | LowerableOperationFragment | LowerableDirective

@dataclass(frozen=True, slots=True)
class ImplementationBody:
    tokens: tuple[BodyToken, ...]
    source_span: SourceSpan

@dataclass(frozen=True, slots=True)
class ImplementationSpec:
    extension_selector: ImplementationSelector
    type_selector: ImplementationSelector
    body: ImplementationBody
    source_span: SourceSpan
    requires_value: CatalogValue | None
    fields: FrozenMap[str, CatalogValue]
    extra_fields: FrozenMap[str, CatalogValue]
```

Invariants:

- Implementation specs are immutable values promoted from primitive `impls`
  fields before selection planning and candidate selection consume selected
  branches.
- Promotion may be selector-aware; unsupported unselected branches are deferred
  instead of making the whole primitive invalid.
- Selectors preserve raw text and normalized selector names.
- Implementation bodies preserve source-owned token order. Raw text tokens may
  contain line breaks, indentation, braces, assignments, semicolons, and other
  source-authored text; lowerable tokens mark only documented generator-owned
  islands.
- M126 accepts only the existing `body <operation>(...)` source line, promoted
  as one `LowerableOperationFragment` token; broader TSIL text and mixed
  raw/lowerable token streams require separate accepted milestones.
- M128 accepts exact quoted `tsil` payload envelopes in the current narrow
  outer fixture shape and promotes their payload content to ordered
  `RawStringToken` values. Those raw tokens are catalog data only until a later
  milestone selects exact lowerable TSIL islands.
- M129 classifies exact `emit_return(...)` payload lines as
  `LowerableDirective` tokens with opaque source-text arguments. The
  directive boundary does not imply expression, operator, helper, call, or
  backend rendering semantics.
- M130 classifies selected exact TSIL directive envelopes
  `var<...>(...)`, `let<...>(...)`, `loop<...>(...)`, `if<...>(...)`,
  `switch<...>(...)`, and `else<...>` as `LowerableDirective` tokens with
  opaque selector and payload arguments. Raw prefix/suffix text such as a
  leading `}` before `else<...>` or trailing `{` / `;` remains
  `RawStringToken` data. The
  directive boundary does not imply block matching, branch evaluation, loop
  execution, type inference, expression parsing, helper/call lowering, or
  backend rendering semantics.
- M132 classifies exact TSIL `call<primitive=...>(...)` islands in raw
  body-token text as `LowerableDirective` tokens named `call` with opaque
  arguments `(primitive, selector, payload)`. Raw prefix/suffix text remains
  `RawStringToken` data. The call boundary does not imply primitive
  resolution, dependency closure, `@self` interpretation, argument splitting,
  directive-payload segmentation, expression parsing, or backend rendering.
- M133 lowers only the exact self-contained
  `LowerableDirective(name="call", arguments=("primitive", "add", "left, right"))`
  body token for the already supported scalar `add(left, right)` shape by
  reusing the existing typed add-operation lowering path. Other selected
  primitive-call tokens remain opaque and produce
  `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`; no general primitive resolution,
  dependency closure, `@self` interpretation, argument splitting, or backend
  call rendering is implied.
- M134 lets selected lowerable directives retain opaque source-text arguments
  while also exposing source-owned payload tokens for exact lowerable islands.
  The first accepted payload-token producer is `emit_return(...)`, and the
  first accepted payload island is the existing M132
  `call<primitive=...>(...)` token shape. Non-`emit_return` directive payloads
  remain opaque, and the payload-token boundary does not imply general
  expression parsing, recursive directive-payload parsing, dependency closure,
  `@self` interpretation, argument splitting, or backend call rendering.
- M135 gives recognized `call<primitive=...>(...)` tokens a typed
  source-owned selector representation while preserving the existing opaque
  directive arguments. The selector distinguishes `@self` from named primitive
  references and preserves optional specialization and `attrs[...]` payloads
  as opaque source text. Call arguments remain opaque. The selector
  representation does not imply primitive resolution, dependency closure,
  `@self` expansion, specialization or attrs interpretation, argument
  splitting, recursive call parsing, expression parsing, or backend call
  rendering.
- M136 gives recognized `call<primitive=...>(...)` tokens an ordered
  source-owned argument-list representation while preserving the original
  opaque call payload. Arguments are raw payload values with source locations,
  split only at top-level commas while respecting nested parentheses and square
  brackets. The argument-list boundary does not imply primitive resolution,
  `@self` expansion, argument identifier resolution, nested call semantics,
  helper/cast/operator parsing, recursive argument lowering, or backend call
  rendering.
- M137 keeps `PrimitiveCall` as source-owned structured call data and uses it
  for unsupported-call diagnostics. The diagnostic context names the selector
  target kind, selector source text, optional opaque specialization and attrs
  payloads, raw argument count, raw argument payload texts, and the opaque call
  payload while making primitive-call dependency resolution the explicit
  missing capability. It still does not resolve primitive references, expand
  `@self`, interpret arguments, lower nested calls, or render backend call
  syntax.
- M138 classifies primitive-call target references using the already built
  catalog and selected implementation context. Named calls look up only the
  base primitive name; `@self` identifies the currently selected primitive as
  the base target. Specialization and `attrs[...]` payloads stay opaque and
  are reported as unresolved target-reference dimensions. The boundary still
  does not select dependency implementations, lower dependency bodies,
  interpret specialization or attrs, expand dependency closure, or render
  backend call syntax.
- M144 lowers selector payloads for already recognized `PrimitiveCall` values.
  Specialization entries become typed type values, extension operands, symbols,
  or literals. `attrs[...]` entries become typed selector attributes. This is a
  selector-payload boundary only: it does not match primitive-call targets,
  select dependency implementations, lower dependency bodies, recursively lower
  call arguments, or render backend call syntax.
- M171 lets primitive-call target matching consume one exact two-entry selector
  payload shape: an already concrete vector selector plus an already lowered
  selected return-type binding value. The matched target is decorated with the
  target primitive's local `return_type` binding name, so caller-local names do
  not leak into dependency contexts.
- M172 lets primitive-call target matching consume already lowered
  `LoweredVectorTransformType` selector values as concrete vectors only when
  their extension is concrete and their base type resolves to a concrete
  scalar `TypeTag`. Alias names remain source-local and are not interpreted.
- M173 resolves exact `LoweredVectorMemberType` values to
  `LoweredScalarTypeIdentity` only when catalog extension metadata proves a
  concrete backend-neutral scalar `TypeTag`. Fixed `lane_bitmask` policies can
  produce exact unsigned scalar tags from selected vector lane counts only when
  both the selected scalar tag and produced unsigned tag have accepted scalar
  descriptors; native predicate, generic, runtime-lane, missing metadata, and
  unsupported member cases remain diagnostics or unresolved backend-owned
  facts.
- M174 completes accepted `ScalarTypeDescriptor` coverage for current concrete
  arithmetic tags `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`,
  `ui64`, `f32`, and `f64`. These descriptors are explicit typed facts;
  pointer-like tags such as `ptr` and backend spellings remain outside this
  lowering descriptor boundary.
- M175 lets generation value `type::*` scalar type arguments consume
  descriptor-backed `LoweredVectorMemberType` facts by invoking the M173
  resolver when an explicit `Catalog` is supplied. The result feeds existing
  scalar descriptor lookup; catalog-missing and unsupported vector-member
  cases remain diagnostics.
- M175.5 adds a focused fixed byte-size rule for `type::size_bytes(...)` over
  `LoweredVectorMemberType` values. Register bytes come from fixed
  `extension.vector_bits / 8`; lane-bitmask mask bytes come from selected
  lane count; lane-keyed native predicate bytes come from explicit
  lane-capacity metadata. Backend spelling text, SVE/scalable sizes, and
  generic symbolic sizes remain outside this lowering fact.
- M177 accepts a typed backend/support-helper request boundary for exact
  `value<generation>(mask::lane::all_true)` and
  `value<generation>(mask::lane::all_false)` forms. These constants are not
  `LoweredGenerationValue[int|bool]`; the request records polarity and source
  provenance for later backend translation without carrying helper text.
- M153 confirms that `details::arith_add`, `details::arith_mul`,
  `details::arith_rem`, `details::popcount`, `details::clz`,
  `details::clz_recursive`, `details::ctz`, and `details::mask_test` are
  source-authored/backend-support helper calls by default. They are represented
  as raw body text or raw directive payload text unless a future milestone
  explicitly introduces typed support-helper availability facts. They must not
  be modeled as semantic operation fragments or rewritten to backend operators
  during lowering.
- M139 records primitive declaration attributes as source-owned catalog facts
  and expands boolean wildcard declaration attributes into deterministic
  concrete primitive variants. Concrete variants must not carry wildcard
  attribute values; provenance remains tied to the source declaration and
  wildcard attribute location. Implementation body text does not participate
  in declaration-attribute expansion.
- M140 extends explicit target selection with concrete primitive attributes.
  Matching compares only the requested target attribute key, optional key
  argument, and value against concrete `Primitive.attributes`. It ignores
  provenance-only catalog fields such as source spans,
  `Primitive.declared_attributes`, and `PrimitiveAttribute.declared_value`.
- `requires_value` remains structurally preserved for the existing flag and
  selector normalization rules.
- Unknown extra fields remain preserved as `extra_fields` so future milestones
  can type them without losing source data.
- Selected list-backed implementation variants are diagnostics until an
  explicit variant policy is accepted. "First dict wins" is rejected hidden
  behavior.

## Selection Model

```python
@dataclass(frozen=True, slots=True)
class TargetAttribute:
    key: str
    value: str
    key_argument: str | None = None

@dataclass(frozen=True, slots=True)
class TargetReturnTypeBaseBinding:
    name: str
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class TargetReturnTypeExtensionBinding:
    name: str
    extension: ExtensionName

@dataclass(frozen=True, slots=True)
class TargetVectorTypeBinding:
    name: str
    extension: ExtensionName
    type_tag: TypeTag

TargetSpecializationBinding = (
    TargetReturnTypeBaseBinding
    | TargetReturnTypeExtensionBinding
    | TargetVectorTypeBinding
)

@dataclass(frozen=True, slots=True)
class Target:
    backend: BackendId
    primitive_name: PrimitiveName
    extension: ExtensionName
    type_tag: TypeTag
    attributes: tuple[TargetAttribute, ...] = ()
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = ()

@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    target: Target
    primitive: Primitive
    implementation: ImplementationSpec
```

Invariants:

- Selected implementations are sorted by stable identity.
- Each selected implementation has a resolved template and concrete type tag.
- Unsupported backend or missing language maps are diagnostics, not renderer surprises.
- Concrete primitive attribute selection is part of the explicit `Target`, not
  a separate `SelectionRequest` dimension.
- Attribute-variant matching compares only `TargetAttribute.key`,
  `TargetAttribute.key_argument`, and `TargetAttribute.value` against concrete
  `Primitive.attributes`.
- Attribute-variant matching ignores provenance-only catalog fields, including
  source spans, `Primitive.declared_attributes`, and
  `PrimitiveAttribute.declared_value`.
- Selected specialization bindings are explicit selected facts. Return-type
  base/extension bindings must validate against the primitive-local
  `return_type` declaration before type or selector-payload lowering consumes
  them. Vector/type bindings are explicit concrete `ExtensionName + TypeTag`
  facts for observed `ToType`-style queries and primitive-call selector
  payloads; M169/M170 do not derive them from implementation selector trees.

## Lowering Context Model

Milestone 141 introduces a small selected implementation lowering context owned
by the lowering boundary. It is constructed from an already selected
`SelectedImplementation`, not from source-file reads or legacy evidence.

```python
@dataclass(frozen=True, slots=True)
class SelectedImplementationLoweringContext:
    target: Target
    primitive: Primitive
    implementation: Implementation
    primitive_name: PrimitiveName
    primitive_attributes: tuple[PrimitiveAttribute, ...]
    backend: BackendId
    extension: ExtensionName
    type_tag: TypeTag
    signature: Signature
    template: TemplateName
    parameter_names: tuple[ParameterName, ...]
    primitive_source: SourceLocation
    implementation_source: SourceLocation
    selected_specialization_bindings: tuple[TargetSpecializationBinding, ...]
    current_vector_keyword: str
    current_scalar_keyword: str
```

Invariants:

- `primitive` and `implementation` preserve the selected catalog object
  identity for diagnostics and traceability.
- `primitive_attributes` is the selected concrete `Primitive.attributes` tuple
  chosen by target selection.
- `selected_specialization_bindings` is copied from the explicit target and is
  the only M169/M170 source for return-type base/extension symbols or explicit
  vector/type specialization symbols.
- Declaration provenance such as `Primitive.declared_attributes` and
  `PrimitiveAttribute.declared_value` is not a separate semantic selector.
- `Vec` is a current selected-context vector value: exactly the selected
  extension plus type tag, not a primitive specialization key and not a
  backend type spelling. The selected extension identity must resolve against
  the M143.1 extension catalog before later call-selector lowering depends on
  it.
- `scalar` is the current selected-context scalar/base type keyword derived
  from the selected type tag.
- `MaskVec`, `GenericVec`, and any other source identifier are not context
  built-ins. They are aliases only after the selected body binds them with
  exact `let<type>(...)` directives.

## Type Query Lowering Model

Milestones 142 and 143 add a selected-body type environment and an
observed-corpus type value model. It is built from
`SelectedImplementationLoweringContext` and the selected implementation body,
not from fresh source-file reads, `tsldata`, `frozen`, or `tslgenold`.

```python
@dataclass(frozen=True, slots=True)
class CurrentVector:
    extension: ExtensionName
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredCurrentScalarType:
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredScalarTypeIdentity:
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredSizeType:
    pass

@dataclass(frozen=True, slots=True)
class LoweredIntrinsicVectorImaskType:
    pass

@dataclass(frozen=True, slots=True)
class LoweredSpecializationTypeSymbol:
    name: str

@dataclass(frozen=True, slots=True)
class LoweredVectorMemberType:
    member: Literal[
        "register",
        "mask",
        "imask",
        "mask_underlying",
        "offset_base",
    ]
    extension: ExtensionName
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredBaseTransformType:
    transform: Literal["signed_of", "unsigned_of", "generic", "id"]
    value: LoweredTypeValue

@dataclass(frozen=True, slots=True)
class LoweredGenericRegisterType:
    vector_type: LoweredTypeValue

@dataclass(frozen=True, slots=True)
class LoweredVectorTransformType:
    transform: Literal["transform", "transform_extension"]
    base_type: LoweredTypeValue
    extension: ExtensionName

@dataclass(frozen=True, slots=True)
class LoweredVectorAsExtensionType:
    base_type: LoweredTypeValue
    extension: ExtensionName

@dataclass(frozen=True, slots=True)
class LoweredTypeIsSamePredicate:
    left: LoweredTypeValue
    right: LoweredTypeValue

LoweredTypePredicate = LoweredTypeIsSamePredicate

@dataclass(frozen=True, slots=True)
class LoweredTypeSelectType:
    condition: LoweredTypePredicate
    then_type: LoweredTypeValue
    else_type: LoweredTypeValue

@dataclass(frozen=True, slots=True)
class BackendTypeSpellingRequest:
    backend: BackendId
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class LoweredBackendTypeReference:
    request: BackendTypeSpellingRequest

LoweredTypeValue = (
    LoweredBackendTypeReference
    | LoweredBaseTransformType
    | CurrentVector
    | LoweredCurrentScalarType
    | LoweredGenericRegisterType
    | LoweredIntrinsicVectorImaskType
    | LoweredScalarTypeIdentity
    | LoweredSizeType
    | LoweredSpecializationTypeSymbol
    | LoweredTypeSelectType
    | LoweredVectorAsExtensionType
    | LoweredVectorMemberType
    | LoweredVectorTransformType
)

@dataclass(frozen=True, slots=True)
class LoweredTypeAliasBinding:
    alias_name: str
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SelectedTypeEnvironment:
    context: SelectedImplementationLoweringContext
    context_symbols: tuple[str, ...]
    alias_bindings: tuple[LoweredTypeAliasBinding, ...]
    diagnostics: tuple[Diagnostic, ...]

```

`CurrentVector` is the concrete value behind the `Vec` keyword. It is the
small `CurrentVector(extension: ExtensionName, type_tag: TypeTag)` value, not
a backend spelling, target-language alias, or general type hierarchy. M144
renames the accepted M143 `LoweredCurrentVectorType` concept to this domain
name rather than keeping a second class for the same concept.

## Generation Value Query Lowering Model

Milestone 155 adds a selected-context generation-value result boundary for
isolated `value<generation>(...)` query islands. It is built from the already
selected implementation context, optional selected type environment, catalog
extension metadata supplied by the caller, scalar type facts, and selected
primitive attributes. It does not read source files, `tsldata`, `frozen`, or
`tslgenold` at lowering time.

```python
LoweredGenerationValueKind = Literal[
    "generation.integer_literal",
    "vector.length",
    "vector.alignment",
    "type.size_bytes",
    "type.is_signed",
    "type.is_same",
    "primitive.attribute",
    "generic.length",
    "generic.runtime_length",
    "generation.integer_comparison",
    "generation.boolean_condition",
    "generation.arithmetic.add",
    "generation.arithmetic.sub",
    "generation.arithmetic.mul",
    "generation.arithmetic.div",
    "generation.arithmetic.rem",
]
LoweredGenerationValuePayload = int | bool

@dataclass(frozen=True, slots=True)
class LoweredGenerationValue:
    kind: LoweredGenerationValueKind
    value: LoweredGenerationValuePayload
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationValueQueryLoweringResult:
    value: LoweredGenerationValue | None
    diagnostics: tuple[Diagnostic, ...]
```

Invariants:

- `vector.length` and `vector.alignment` consume only selected extension/type
  facts plus catalog extension metadata and scalar size facts.
- `type.size_bytes`, `type.is_signed`, and `type.is_same` lower each
  `TYPE_EXPR` argument through the accepted type-query lowering model before
  evaluating supported scalar type values.
- `primitive.attribute` consumes only selected concrete boolean primitive
  attributes.
- `generation.integer_literal` is a base-10 integer literal accepted only as
  an operand inside an explicit generation arithmetic call.
- `generation.arithmetic.add`, `generation.arithmetic.sub`,
  `generation.arithmetic.mul`, `generation.arithmetic.div`, and
  `generation.arithmetic.rem` are produced only by explicit
  `arith<generation>::OP(ARG, ARG)` calls. Their operands recursively lower
  through this generation-value model and must be integers. Division and
  remainder use deterministic truncating integer division; zero right operands
  are diagnostics.
- `generic.length` and `generic.runtime_length` are produced only by the exact
  `generic::length(TYPE_EXPR)` and `generic::runtime_length(TYPE_EXPR)`
  generation-expression calls inside a selected generation-time context.
  `TYPE_EXPR` is lowered through the selected type environment first. The
  result is an integer only when the lowered type is a concrete fixed vector
  with concrete extension, scalar type tag, and catalog lane metadata.
- `generation.integer_comparison` is produced only by generation-control
  condition lowering for exact comparison leaves over accepted integer
  generation values and base-10 integer literals. The integer side may be a
  wrapped `value<generation>(...)` query or a bare accepted generation
  expression such as `type::size_bytes(...)` or
  `arith<generation>::mul(...)`.
- `generation.boolean_condition` is produced only when generation-control
  condition lowering combines accepted boolean leaves with the finite typed
  grammar operators `!`, `&&`, `||`, or parenthesized grouping. It is consumed
  by branch selection, not by backend rendering or raw source replacement.
- Unsupported query families, unsupported lowered type values, unresolved
  aliases/specializations, missing facts, malformed query shapes, runtime or
  size-parameter-only generic vector metadata, and non-concrete attributes
  produce diagnostics.
- This model is not a branch pruner, loop executor, expression parser,
  selector-attribute substitution engine, backend renderer, or raw text
  replacement mechanism.

## Generation-Control Region Lowering Model

Milestone 156 adds a narrow result boundary for exact selected
`if<generation>(...) { ... } else<generation> { ... }` body-token regions.
M160 broadens the same boundary to exact classified
`if<generation>` / `else if<generation>` chains with an optional final
`else<generation>` fallback. It consumes accepted boolean
`LoweredGenerationValue` conditions and preserves source-owned token slices
for the selected and unselected branches. Branch contents are not parsed or
rendered by this model.

```python
@dataclass(frozen=True, slots=True)
class LoweredGenerationControlBranch:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class LoweredGenerationControlRegion:
    condition: LoweredGenerationValue
    selected_branch: LoweredGenerationControlBranch
    unselected_branch: LoweredGenerationControlBranch
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationControlRegionLoweringResult:
    region: LoweredGenerationControlRegion | None
    diagnostics: tuple[Diagnostic, ...]
```

Invariants:

- The accepted M156 two-arm shape is exactly a generation `if` directive, raw
  `{` opener, true-branch token slice, raw `}` close, generation `else`
  directive, raw `{` opener, false-branch token slice, and raw `}` close.
- The accepted M160 branch-chain shape is a leading generation `if` arm
  followed by one or more classified `else if<generation>` arms and an
  optional final `else<generation>` fallback. The close brace before a
  conditional continuation may share the raw token suffix `else`, but the next
  arm must be a classified generation `if` directive token. Source-next-line
  `else if<generation>(...) { BODY }` continuations are represented as a raw
  `else` prefix token followed by a classified generation `if` directive and
  source-owned raw `{`, body, and `}` tokens.
- The condition must be an accepted M155 boolean query for primitive
  attributes, scalar signedness, or scalar type sameness, or an M158 exact
  integer comparison predicate over a left-side accepted integer generation
  value query and a base-10 integer literal.
- Branch-chain arms are evaluated in source order. The first true conditional
  arm wins. Later conditions and all unselected body tokens remain opaque and
  silent. If no condition is true, a final `else<generation>` fallback is
  selected when present; otherwise lowering produces a deterministic no-match
  diagnostic.
- When a fallback arm is selected, `LoweredGenerationControlRegion.condition`
  records the last evaluated false conditional value as provenance; the
  fallback itself does not synthesize a new condition value.
- Integer generation values such as vector length, vector alignment, or scalar
  size bytes remain invalid branch conditions unless consumed by an accepted
  M158 comparison predicate.
- Branch token slices are source-owned body tokens. Raw helper text,
  classified directives, nested raw braces, and adjacent raw tokens remain
  untouched for later lowering/rendering milestones.
- Inline/unclassified branch-chain text and plain-else shapes are diagnostic
  boundaries, not source repair targets.
- M158 comparison predicates are a condition boundary only. M159 can supply
  explicit `arith<generation>::...` integer values on the left side, but raw
  operator parsing, right-hand value queries, precedence, and a TSIL
  expression AST remain out of scope.

Milestone 157 does not add another IR model. It uses
`LoweredGenerationControlRegion.selected_branch` as a source-owned token slice
handoff into the existing direct body-lowering path. The temporary
`ImplementationBody` built from selected branch tokens is a local adapter for
composition; it is not a new stage envelope, renderer input, or recursive TSIL
statement model. The unselected branch remains available as provenance in the
M156/M160 result but is not parsed or diagnosed by the handoff. For M160
chains, the existing single `unselected_branch` field aggregates the
unselected arm token slices as provenance; it is not a recursive branch-list
IR or renderer contract.

## Generation Loop Region Lowering Model

Milestone 161 adds a narrow semantic fact for exact generation loop envelopes.
It records loop metadata and body-token provenance only; it is not a loop
executor, statement model, renderer contract, or source-repair mechanism.

```python
@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopBody:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopRegion:
    index_name: str
    start: LoweredGenerationValue
    end: LoweredGenerationValue
    step: LoweredGenerationValue
    body: LoweredGenerationLoopBody
    source: SourceLocation
    unroll_count: LoweredGenerationValue | None = None

@dataclass(frozen=True, slots=True)
class GenerationLoopRegionLoweringResult:
    region: LoweredGenerationLoopRegion | None
    diagnostics: tuple[Diagnostic, ...]
```

Invariants:

- The accepted region shape is exactly an optional
  `loop<unroll>(COUNT)` directive followed immediately by a
  `loop<range>(INDEX, START, END, STEP)` directive, raw `{` opener,
  source-owned body token slice, and matching raw `}` close.
- `INDEX` is an identifier. M161 records the name but does not substitute it
  into body text.
- `START`, `END`, `STEP`, and optional `COUNT` lower only as base-10 integer
  literals in this loop-bound context or as accepted integer
  `value<generation>(...)` queries. Integer literals do not become a general
  standalone generation-value query family.
- Unsupported symbols such as variable-dependent bounds are diagnostics.
  Nested loop bodies may be preserved as tokens, but nested loop execution or
  dependence on an outer index is not M161 behavior.
- Body tokens remain source-owned and opaque. Raw helpers, primitive-call
  islands, generation-control directives, nested loops, assignments, array
  indexing, casts, intrinsics, and raw target-language text are not parsed or
  rendered by this model.

Milestone 162 adds a source-ordered discovery fact for exact M161 loop regions
inside larger body token streams:

```python
@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopRegionSegment:
    region: LoweredGenerationLoopRegion
    source: SourceLocation

LoweredGenerationLoopDiscoverySegment = (
    LoweredGenerationLoopOpaqueSegment | LoweredGenerationLoopRegionSegment
)

@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopDiscovery:
    segments: tuple[LoweredGenerationLoopDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationLoopDiscoveryLoweringResult:
    discovery: LoweredGenerationLoopDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M162 discovery model is a token-span provenance fact, not a statement
model. It supports multiple exact top-level loop regions in source order,
preserves all non-loop tokens as opaque spans, and reuses the M161 region
fact for each loop slice. Surrounding token names such as `var<...>` or
`emit_return(...)` do not affect discovery behavior.
Discovery tracks raw brace depth only to avoid treating loops inside unrelated
opaque raw-brace scopes as top-level; it does not interpret those scopes as
statements or control flow.

Milestone 163 adds variable-declaration discovery values:

```python
GenerationVariableDeclarationSelector = Literal[
    "init_register",
    "infer",
    "const_infer",
    "typed",
]

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationText:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationRequest:
    selector: GenerationVariableDeclarationSelector
    name: str
    name_source: SourceLocation
    payload_text: str
    source: SourceLocation
    explicit_type: GenerationVariableDeclarationText | None = None
    initializer: GenerationVariableDeclarationText | None = None

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationRequestSegment:
    declaration: GenerationVariableDeclarationRequest
    source: SourceLocation

GenerationVariableDeclarationDiscoverySegment = (
    GenerationVariableDeclarationOpaqueSegment
    | GenerationVariableDeclarationRequestSegment
)

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationDiscovery:
    segments: tuple[GenerationVariableDeclarationDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationDiscoveryLoweringResult:
    discovery: GenerationVariableDeclarationDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M163 declaration model records unresolved declaration facts/requests over
source-owned body tokens. It preserves non-var tokens as opaque spans and
keeps explicit type and initializer payloads as source text. It is not a
symbol table, type inference result, backend declaration rendering plan, or
statement AST.

Milestone 164 adds backend value query discovery values:

```python
@dataclass(frozen=True, slots=True)
class BackendValueQueryRequest:
    query_text: str
    query_source: SourceLocation
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendValueQueryOpaqueTextSegment:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendValueQueryOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendValueQueryRequestSegment:
    request: BackendValueQueryRequest
    source: SourceLocation

BackendValueQueryDiscoverySegment = (
    BackendValueQueryOpaqueTextSegment
    | BackendValueQueryOpaqueTokenSegment
    | BackendValueQueryRequestSegment
)

@dataclass(frozen=True, slots=True)
class BackendValueQueryDiscovery:
    segments: tuple[BackendValueQueryDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendValueQueryDiscoveryLoweringResult:
    discovery: BackendValueQueryDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M164 backend value query model is a request-intake boundary over exact
`value<backend>(...)` islands. It preserves opaque source text around requests
and carries backend-owned query payload text forward unresolved. It is not a
backend translation result, expression AST, declaration initializer evaluator,
or renderer-ready value.

Milestone 165 adds backend-control directive discovery values:

```python
BackendControlDirectiveName = Literal["if", "else", "switch"]
BackendControlDirectiveSelector = Literal["compile"]

@dataclass(frozen=True, slots=True)
class BackendControlDirectiveRequest:
    directive_name: BackendControlDirectiveName
    selector: BackendControlDirectiveSelector
    selector_source: SourceLocation
    source_text: str
    source: SourceLocation
    payload_text: str | None = None
    payload_source: SourceLocation | None = None

@dataclass(frozen=True, slots=True)
class BackendControlDirectiveOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendControlDirectiveRequestSegment:
    request: BackendControlDirectiveRequest
    source: SourceLocation

BackendControlDirectiveDiscoverySegment = (
    BackendControlDirectiveOpaqueSegment
    | BackendControlDirectiveRequestSegment
)

@dataclass(frozen=True, slots=True)
class BackendControlDirectiveDiscovery:
    segments: tuple[BackendControlDirectiveDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendControlDirectiveDiscoveryLoweringResult:
    discovery: BackendControlDirectiveDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M165 backend-control model is a request-intake boundary over already
classified `if<compile>`, `else<compile>`, and `switch<compile>` directive
tokens. It preserves non-control body tokens as opaque spans and carries
backend-owned condition/selector payload text forward unresolved. It is not a
branch-selection result, block model, backend flow translation result, or
renderer-ready statement.

Milestone 166 adds backend intrinsic request discovery values:

```python
BackendIntrinsicKind = Literal["intrin", "intrin_compose"]

@dataclass(frozen=True, slots=True)
class BackendIntrinsicRequest:
    intrinsic_kind: BackendIntrinsicKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicOpaqueTextSegment:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicRequestSegment:
    request: BackendIntrinsicRequest
    source: SourceLocation

BackendIntrinsicDiscoverySegment = (
    BackendIntrinsicOpaqueTextSegment
    | BackendIntrinsicOpaqueTokenSegment
    | BackendIntrinsicRequestSegment
)

@dataclass(frozen=True, slots=True)
class BackendIntrinsicDiscovery:
    segments: tuple[BackendIntrinsicDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicDiscoveryLoweringResult:
    discovery: BackendIntrinsicDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M166 backend intrinsic model is a request-intake boundary over exact
`intrin<...>(...)` and `intrin_compose<...>(...)` islands in source-owned
text. It preserves surrounding text and non-raw body tokens as opaque spans
and carries backend-owned angle payload and argument text forward unresolved.
It is not an intrinsic-name validator, argument AST, modifier evaluator,
backend intrinsic translation result, or renderer-ready call.

Milestone 182 adds backend intrinsic handoff values for the semantic boundary
after M166 discovery:

```python
BackendIntrinsicModifierName = Literal[
    "suffix",
    "prefix",
    "post",
    "infix",
    "infix_sep",
    "immediate",
]

BackendIntrinsicModifierOperand = (
    BackendIntrinsicModifierBackendValueOperand
    | BackendIntrinsicModifierIntegerOperand
    | BackendIntrinsicModifierStringOperand
    | BackendIntrinsicModifierSymbolOperand
)

@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierField:
    name: BackendIntrinsicModifierName
    key_text: str
    value: BackendIntrinsicModifierOperand
    source_text: str
    source: SourceLocation
    key_source: SourceLocation
    value_source: SourceLocation
    immediate_index: int | None = None
    immediate_index_text: str | None = None

BackendIntrinsicHandoffRequest = (
    BackendDirectIntrinsicHandoffRequest
    | BackendIntrinsicComposeHandoffRequest
)

@dataclass(frozen=True, slots=True)
class BackendIntrinsicHandoffRequestSegment:
    request: BackendIntrinsicHandoffRequest
    island: BackendIntrinsicRequest
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendIntrinsicHandoff:
    segments: tuple[BackendIntrinsicHandoffSegment, ...]
    source: SourceLocation
```

The M182 model is a semantic handoff boundary over already discovered M166
request islands. Direct `intrin<...>(...)` requests preserve angle and
argument payload text opaque. `intrin_compose<...>(...)` requests expose only
the top-level base token and source-ordered modifier fields. Modifier operands
remain unresolved symbols, integers, strings, or exact M181 backend-value
requests. The model is not an intrinsic renderer, argument AST, backend map
lookup, direct intrinsic name-template parser, or recursive TSIL parser.

Milestone 167 adds source-operation request discovery values for the exact
`cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)` keyword families:

```python
SourceOperationKind = Literal["cast", "mem", "io"]

@dataclass(frozen=True, slots=True)
class SourceOperationRequest:
    operation_kind: SourceOperationKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SourceOperationOpaqueTextSegment:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SourceOperationOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SourceOperationRequestSegment:
    request: SourceOperationRequest
    source: SourceLocation

SourceOperationDiscoverySegment = (
    SourceOperationOpaqueTextSegment
    | SourceOperationOpaqueTokenSegment
    | SourceOperationRequestSegment
)

@dataclass(frozen=True, slots=True)
class SourceOperationDiscovery:
    segments: tuple[SourceOperationDiscoverySegment, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SourceOperationDiscoveryLoweringResult:
    discovery: SourceOperationDiscovery | None
    diagnostics: tuple[Diagnostic, ...]
```

The M167 source-operation model is a request-intake boundary over exact
balanced source islands. It preserves surrounding text, contiguous raw
body-token split islands, and non-raw body tokens as opaque spans while
carrying mode/operation and argument payload text forward unresolved. It is
not a cast/memory/I/O operation-name validator, type-lowering result,
argument AST, backend translation result, or renderer-ready call.

Milestone 183 adds source-operation selector handoff values over accepted
M167 source-operation requests:

```python
class CastSourceOperationSelector(Enum):
    STATIC = "static"
    REINTERPRET = "reinterpret"
    BITCAST = "bitcast"
    SATURATING = "saturating"

class MemorySourceOperationSelector(Enum):
    COPY = "copy"
    ALLOC = "alloc"
    ALLOC_ALIGNED = "alloc_aligned"
    FREE = "free"

class IoSourceOperationSelector(Enum):
    WRITE = "write"
    WRITE_BASE = "write_base"
    WRITE_BIN = "write_bin"
    ENDL = "endl"

@dataclass(frozen=True, slots=True)
class CastSourceOperationHandoffRequest:
    selector: CastSourceOperationSelector
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class MemorySourceOperationHandoffRequest:
    selector: MemorySourceOperationSelector
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class IoSourceOperationHandoffRequest:
    selector: IoSourceOperationSelector
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SourceOperationHandoffRequestSegment:
    request: SourceOperationHandoffRequest
    island: SourceOperationRequest
    source: SourceLocation
```

The M183 model is a semantic handoff boundary over already discovered M167
request islands. The handoff classifies only the top-level selector payload
into finite enum values and preserves the original M167 request island for
angle payload text, argument payload text, complete source-island text, raw
request identity, and diagnostics. It is not a cast/memory/I/O translator,
argument splitter, nested payload scanner, backend map lookup, or
renderer-ready call model.

Milestone 185 adds mask keyword request values for exact `mask<...>(...)`
islands. These values live in the focused `mask_keywords` lowering module so
the already large shared model module does not become the default home for
another narrow family:

```python
class MaskKeywordSelector(Enum):
    ZERO = "zero"
    TEST = "test"
    SET = "set"
    SET_ONE = "set:1"

@dataclass(frozen=True, slots=True)
class MaskKeywordRequest:
    selector: MaskKeywordSelector
    selector_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class MaskKeywordOpaqueTextSegment:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class MaskKeywordOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class MaskKeywordRequestSegment:
    request: MaskKeywordRequest
    source: SourceLocation
```

The M185 model classifies only the top-level selector payload into the finite
enum and preserves argument payload text as opaque source-owned provenance. It
is not a mask translator, argument splitter, recursive payload scanner,
backend helper mapper, renderer-ready call model, or replacement for M177 mask
lane constant requests.

Milestone 187 adds backend/output source-island request values for exact
`assume_aligned<...>(...)`, `array_type<...>`, and `pack<...>(...)` islands.
These values also live in a focused lowering module instead of extending the
already large shared model module:

```python
class BackendOutputRequestKind(Enum):
    ASSUME_ALIGNED = "assume_aligned"
    ARRAY_TYPE = "array_type"
    PACK = "pack"

@dataclass(frozen=True, slots=True)
class BackendOutputRequest:
    kind: BackendOutputRequestKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    source_text: str
    source: SourceLocation
    argument_text: str | None = None
    argument_source: SourceLocation | None = None

@dataclass(frozen=True, slots=True)
class BackendOutputOpaqueTextSegment:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendOutputOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class BackendOutputRequestSegment:
    request: BackendOutputRequest
    source: SourceLocation
```

The M187 model is a request-identity boundary for backend/output-owned
source forms. It preserves the exact angle payload and optional call argument
payload as source-owned text. `array_type<...>` is angle-only;
`assume_aligned<...>(...)` and `pack<...>(...)` are call-shaped. The model is
not an alignment evaluator, array-type/type-layout model, pack translator,
argument splitter, recursive payload scanner, backend map lookup, declaration
model, or renderer-ready call model.

Milestone 144 adds selector-payload values:

```python
@dataclass(frozen=True, slots=True)
class ExtensionOperand:
    name: ExtensionName
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SelectorSymbol:
    name: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SelectorLiteral:
    text: str
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class SelectorAttribute:
    key: str
    value: str
    source: SourceLocation
    key_argument: str | None = None

SelectorSpecializationValue = (
    LoweredTypeValue | ExtensionOperand | SelectorLiteral | SelectorSymbol
)

@dataclass(frozen=True, slots=True)
class PrimitiveCallSelectorPayload:
    target: PrimitiveCallTarget
    specializations: tuple[SelectorSpecializationValue, ...]
    attributes: tuple[SelectorAttribute, ...]
    source_text: str
    source: SourceLocation
    selected_return_binding_names: tuple[str | None, ...] = ()

@dataclass(frozen=True, slots=True)
class PrimitiveCallTargetMatch:
    selected: SelectedImplementation
    selector_payload: PrimitiveCallSelectorPayload
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class PrimitiveCallTargetMatchingResult:
    match: PrimitiveCallTargetMatch | None
    diagnostics: tuple[Diagnostic, ...]

@dataclass(frozen=True, slots=True)
class PrimitiveCallArgumentBinding:
    parameter_name: str
    argument: PrimitiveCallArgument

@dataclass(frozen=True, slots=True)
class PrimitiveCallReference:
    primitive_call: PrimitiveCall
    target_match: PrimitiveCallTargetMatch
    bindings: tuple[PrimitiveCallArgumentBinding, ...]
    source: SourceLocation

@dataclass(frozen=True, slots=True)
class PrimitiveCallArgumentBindingResult:
    reference: PrimitiveCallReference | None
    diagnostics: tuple[Diagnostic, ...]

@dataclass(frozen=True, slots=True)
class LoweredPrimitiveCallExpression:
    reference: PrimitiveCallReference

@dataclass(frozen=True, slots=True)
class PrimitiveCallExpressionLoweringResult:
    expression: LoweredPrimitiveCallExpression | None
    diagnostics: tuple[Diagnostic, ...]

@dataclass(frozen=True, slots=True)
class PrimitiveCallReferenceInventory:
    references: tuple[PrimitiveCallReference, ...]
    diagnostics: tuple[Diagnostic, ...]

@dataclass(frozen=True, slots=True)
class PrimitiveCallDependencyClosure:
    selected: tuple[SelectedImplementation, ...]
    references: tuple[PrimitiveCallReference, ...]
    diagnostics: tuple[Diagnostic, ...]

@dataclass(frozen=True, slots=True)
class PrimitiveCallClosureLoweringPackage:
    closure: PrimitiveCallDependencyClosure
    lowered_functions: LoweredFunctionSet
    diagnostics: tuple[Diagnostic, ...]
```

M170 keeps the same selector-payload value model. It only extends the accepted
sources of `SelectorSpecializationValue`: exact bare selector parts may now
consume explicit M169 `TargetSpecializationBinding` facts. A base binding
produces a scalar type value, an extension binding produces `ExtensionOperand`,
and a vector/type binding produces `CurrentVector`. Unbound arbitrary selector
names still produce `SelectorSymbol`; declared extension binding names without
selected facts produce the accepted selected-binding diagnostic rather than a
raw extension or symbol fallback.

Invariants:

- Context symbols are exactly the current `Vec` and `scalar` spellings for
  the selected implementation.
- Alias bindings are ordered by selected body token order.
- Alias references resolve only to earlier bindings in the same selected body.
- Alias bindings preserve the full lowered type value, including any resolved
  extension identity carried by `Vec` or vector type transforms. This is an
  alias-preservation rule, not a general type-system or selector-matching
  rule.
- `type<generation>(...)` produces semantic type values, never backend text.
- `type<backend>(...)` produces a `BackendTypeSpellingRequest`; it does not
  render backend type text.
- M151 consolidates primitive-call lowering ownership in a cohesive resolver
  and dependency collector. Selector payloads, target matches, argument
  bindings, expression results, inventories, and closures remain typed facts
  and result envelopes, not separate durable middleware stages.
- The primitive-call resolver consumes one recognized primitive call and
  composes selector-payload lowering, target matching, raw argument binding,
  and optional expression creation. It preserves raw argument text and source
  provenance without parsing, validating, normalizing, or repairing argument
  expressions.
- The primitive-call dependency collector walks selected body tokens in source
  order, records resolved primitive-call references, and computes closure by
  stable selected-target identity. It does not schedule dependencies, lower
  dependency bodies beyond the accepted selected-function lowerer, render
  backend call text, or render backend type text.
- Primitive-call closure lowering packages preserve the accepted closure and
  run existing selected-function lowering in closure selected order. They
  accumulate closure diagnostics and selected-function lowering diagnostics
  without scheduling, rendering primitive-call invocations, backend rendering,
  or parsing argument expressions.
- M152 keeps primitive-call substep ownership on the focused
  selector-payload helper, `PrimitiveCallResolver`, and
  `PrimitiveCallDependencyCollector` instead of exposing compatibility-shaped
  `Lowerer.lower_primitive_call_*` facade methods. `Lowerer` remains the
  selected-function/type lowering owner and may compose a closure-lowering
  package by combining the dependency collector with `lower_all(...)`.
- A `type<backend>(...)` expression nested inside a generation type transform
  is represented as `LoweredBackendTypeReference`, preserving the request as a
  semantic input to that type transform without rendering it.
- Observed specialization names such as `ToBase`, `ToType`, and
  `ToExtension` are `LoweredSpecializationTypeSymbol` values only when they
  appear inside supported observed type transforms and no explicit M169
  selected binding resolves them. M168.5 records primitive-local
  `return_type` declarations for arbitrary source names such as
  `base: ToBase` or `extension: ToExtension`; M169 resolves those names only
  through explicit selected specialization bindings.
- Raw source text is retained only as diagnostic/provenance context, not as a
  semantic value consumed by renderers.

## Dependency Analysis Model

Milestone 9 keeps the required dependency closure at primitive-name granularity.
Milestone 19 adds an optional candidate-specific layer that is still derived
from the accepted dependency graph and selected implementation candidates:

```python
@dataclass(frozen=True, slots=True)
class CandidateDependencyEdge:
    source_candidate_id: str
    target_candidate_id: str
    reference: DependencyReference

@dataclass(frozen=True, slots=True)
class CandidateDependencyIssue:
    source_candidate_id: str
    target_primitive_name: PrimitiveName
    reason: Literal["ambiguous", "missing", "unsupported"]
    candidate_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class CandidateDependencyClosure:
    required_candidate_ids: tuple[str, ...]
    required_primitive_names: tuple[PrimitiveName, ...]
    fallback_primitive_names: tuple[PrimitiveName, ...]
```

Milestone 32 keeps this closure as dependency-stage data and adds stable report
DTOs so API/report consumers do not have to depend on raw dependency internals:

```python
@dataclass(frozen=True, slots=True)
class CandidateDependencyReport:
    is_available: bool
    edge_rows: tuple[CandidateDependencyEdgeRow, ...]
    issue_rows: tuple[CandidateDependencyIssueRow, ...]
    fallback_primitive_names: tuple[PrimitiveName, ...]
    diagnostic_counts: tuple[DiagnosticCount, ...]
```

Invariants:

- Candidate-specific edges are emitted only for uniquely resolved target
  candidates.
- Ambiguous, missing, or lowering-dependent target references remain explicit
  fallback primitive names.
- Primitive-level dependency closure remains visible even when
  candidate-specific report rows are available.
- Dependency extraction remains conservative until TSIL lowering has a semantic
  representation of calls.

## Lowering And IR Model

The redesign should introduce IR only when a milestone needs it. The expected layers are:

```python
@dataclass(frozen=True, slots=True)
class SemanticOperation:
    op: str
    operands: tuple[SemanticExpression, ...]
    result_type: SemanticType | None

@dataclass(frozen=True, slots=True)
class LoweredBody:
    statements: tuple[BackendNeutralStatement, ...]
    dependencies: tuple[PrimitiveDependency, ...]
```

Milestone 18 introduces the first concrete lowering boundary as typed-opaque
models:

```python
@dataclass(frozen=True, slots=True)
class LoweringRequest:
    strategy: Literal["mini_tsil", "typed_opaque"]
    backend_id: BackendId | None
    generation_context: GenerationContext

@dataclass(frozen=True, slots=True)
class ClassifiedPayload:
    body_kind: str
    classification: Literal["tsil", "intrinsic", "backend_specific", "opaque"]
    raw_payload: CatalogValue
    text: str | None
    has_generation_condition: bool

@dataclass(frozen=True, slots=True)
class LoweringInput:
    candidate: SelectedImplementation
    payload: ClassifiedPayload

@dataclass(frozen=True, slots=True)
class TsilParameterReference:
    name: str

@dataclass(frozen=True, slots=True)
class TsilBinaryExpression:
    operator: Literal["+"]
    left: TsilParameterReference
    right: TsilParameterReference

@dataclass(frozen=True, slots=True)
class TsilReturnStatement:
    expression: TsilBinaryExpression

@dataclass(frozen=True, slots=True)
class LoweringPlan:
    request: LoweringRequest
    input_set: LoweringInputSet
    implementations: tuple[LoweredImplementation, ...]
```

Invariants:

- Lowering inputs are built from selected implementation candidates, not parser
  trees or raw source files.
- Opaque TSIL text is not a lowered body and must not be rendered as production
  backend code without a later lowering slice.
- Generation-time branch markers are represented at the lowering boundary even
  before they are evaluated.
- Milestone 27 lowers only direct parameter-add returns shaped as
  `emit_return(<parameter> + <parameter>);` into backend-neutral
  `TsilReturnStatement` values. Other expression, call, branch, loop, intrinsic,
  and backend-specific payloads remain unsupported.
- Future semantic dependency references are extracted from parsed TSIL, not just
  backend text; Milestones 9 and 19 retain conservative marker extraction until
  a TSIL AST exists.
- Backend translation maps consume semantic operation identifiers.
- Backend-specific syntax enters through backend lowerers.

## Backend Model

```python
@dataclass(frozen=True, slots=True)
class BackendManifest:
    version: int
    backend_id: BackendId
    language_id: LanguageId
    artifacts: tuple[ArtifactSpec, ...]
    template_policy: BackendTemplatePolicy

@dataclass(frozen=True, slots=True)
class BackendManifestSet:
    manifests: tuple[BackendManifest, ...]

class Backend(Protocol):
    id: BackendId
    def plan(self, selected: SelectionResult, catalog: Catalog) -> BackendPlan: ...
    def render(self, plan: BackendPlan) -> ArtifactSet: ...
```

Invariants:

- A backend cannot read source files, CPU flags, or output directories during render.
- Backend support and language maps are validated before planning.
- Template engines are implementation details behind a renderer.
- Active backend IDs are `cpp` and `rust` for the current roadmap. C17 is
  deferred evidence and is not an active backend ID.

Milestone 30 adds a typed metadata boundary for catalog language and translation
data:

```python
@dataclass(frozen=True, slots=True)
class LanguageTypeEntry:
    source_type: str
    target_type: str
    fields: FrozenMap[str, CatalogValue]

@dataclass(frozen=True, slots=True)
class LanguageTypeMap:
    backend_id: BackendId
    entries: tuple[LanguageTypeEntry, ...]

@dataclass(frozen=True, slots=True)
class TranslationSnippet:
    name: str
    template: str

@dataclass(frozen=True, slots=True)
class TranslationMap:
    backend_id: BackendId
    snippets: tuple[TranslationSnippet, ...]

@dataclass(frozen=True, slots=True)
class BackendMetadataBoundary:
    manifests: BackendManifestSet
    metadata: BackendMetadataCatalog
    active_backend_ids: tuple[BackendId, ...]
```

Invariants:

- Language maps preserve raw source type keys and target type names; they do not
  normalize TSL type tags or select SIMD vector types.
- Translation maps preserve raw snippet templates; they are not evaluated by
  renderers in this milestone.
- Active manifests require a language map for `language_id` and a translation
  map for `backend_id`.

## Test Model

```python
@dataclass(frozen=True, slots=True)
class PrimitiveTestSpec:
    name: str | None
    explicit_extension: ExtensionName | None
    type_tag: TypeTag | TypeGroupName | None
    to_type: TypeTag | TypeGroupName | None
    lane_set: LaneSetName | None
    attrs: PrimitiveAttributes
    case: TestCaseData
    fields: FrozenMap[str, CatalogValue]

@dataclass(frozen=True, slots=True)
class TestVariant:
    primitive: PrimitiveName
    template: TemplateName
    backend: BackendId
    extension: ExtensionName
    type_tag: TypeTag
    lanes: int | None
    inputs: tuple[CatalogValue, ...]
    expected: CatalogValue | None
```

Invariants:

- Test variants are derived after selection so unsupported implementations do not produce executable tests.
- Lane resizing rules are explicit policies.
- Tests with unknown type, lane set, extension, or primitive call produce diagnostics.

## Artifact Model

```python
@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    backend_id: BackendId
    kind: str
    logical_path: str
    candidate_ids: tuple[str, ...]
    dependency_primitive_names: tuple[PrimitiveName, ...]
    metadata: FrozenMap[str, CatalogValue]

@dataclass(frozen=True, slots=True)
class ArtifactPlan:
    backend_id: BackendId
    descriptors: tuple[ArtifactDescriptor, ...]
    metadata: FrozenMap[str, CatalogValue]

@dataclass(frozen=True, slots=True)
class Artifact:
    logical_name: str
    extension: str
    content: str

@dataclass(frozen=True, slots=True)
class ArtifactSet:
    artifacts: tuple[Artifact, ...]
    metadata: FrozenMap[str, CatalogValue]
```

Invariants:

- Artifact descriptors are content-free planning values.
- Logical name plus extension identifies a target path relative to an output root.
- Artifact ordering is deterministic.
- Artifact content is UTF-8 text unless a future binary artifact type is introduced explicitly.

## Generated Project Model

```python
@dataclass(frozen=True, slots=True)
class GeneratedProfileSet:
    profiles: tuple[MachineFeatureProfile, ...]
    default_profile: MachineFeatureProfile

@dataclass(frozen=True, slots=True)
class BackendProfileRenderModel:
    family: MachineProfileFamily
    profile_name: MachineProfileName
    features: tuple[FeatureFlagName, ...]
    alternatives: tuple[MachineFeatureAlternative, ...]
    file_stem: ProfileFileStem
    cpp_macro: CppProfileMacro
    rust_feature: RustProfileFeature
    rust_module: RustProfileModule

@dataclass(frozen=True, slots=True)
class BackendProjectRenderModel:
    backend_id: str
    project_name: str
    root_path: str
    public_entry_path: str
    smoke_test_path: str
    profiles: tuple[BackendProfileRenderModel, ...]
    default_profile: MachineProfileName

@dataclass(frozen=True, slots=True)
class GeneratedProjectRenderModel:
    cpp: BackendProjectRenderModel
    rust: BackendProjectRenderModel
```

Invariants:

- `GeneratedProfileSet` is resolved from typed machine profile catalog facts.
  Omitted profile selection resolves to `scalar`; reserved `all` resolves to
  all known profiles in catalog order; explicit names preserve request order.
  The default profile is `scalar` when it is part of the generated set and the
  first selected profile otherwise.
- `BackendProjectRenderModel` is presentation data for an already-decided
  skeleton output. It may carry profile names, generated file stems, C++
  profile macros, Rust feature names, and smoke-test paths, but it must not
  carry raw TSIL, catalog objects, lowering requests, unresolved backend
  metadata, primitive bodies, or compiler capability decisions.
- C++ generated projects expose `cpp/include/tsl.hpp` and profile headers under
  `cpp/include/profiles/`. Rust generated projects expose `rust/src/lib.rs`
  and profile modules under `rust/src/profiles/`.
- The render model is consumed before artifact writing. The writer receives
  only an `ArtifactSet`, not primitive dependency information or profile
  selection policy.

## Primitive Template Render Model

M217 introduces a minimal primitive-template render model for
presentation-only template rendering. M218 adds the typed already-decided
primitive render model that feeds this context.

```python
@dataclass(frozen=True, slots=True)
class PrimitiveTemplateRenderContext:
    backend_id: str
    template_path: str
    logical_path: str
    profile_name: str
    media_type: str
    includes: tuple[str, ...]
    imports: tuple[str, ...]
    namespace_open: str
    namespace_close: str
    module_open: str
    module_close: str
    primitive_declarations: tuple[str, ...]
    primitive_definitions: tuple[str, ...]
    rendered_body_text: str
    metadata: tuple[ArtifactMetadata, ...]
```

Invariants:

- The context is dedicated to primitive templates and does not reuse
  `ProjectSkeletonRenderContext`.
- Fields are already-decided presentation values. The context must not carry
  raw TSIL needing interpretation, unresolved lowering requests, catalog
  objects, primitive selectors, dependency rules, backend metadata lookup
  keys, or type/intrinsic selection inputs.
- Template paths resolve under `supplementary/templates/{cpp,rust}/` for the
  accepted C++ and Rust primitive-template files.
- Rendering returns an in-memory `ArtifactSet`; artifact writing and build
  verification remain later boundaries.

M218 primitive render models distinguish already-rendered presentation values
from raw source, raw TSIL, unresolved lowering/backend requests, and catalog or
selection inputs:

```python
@dataclass(frozen=True, slots=True)
class PrimitiveBackendId:
    text: str

@dataclass(frozen=True, slots=True)
class PrimitiveProfileName:
    text: str

@dataclass(frozen=True, slots=True)
class PrimitiveArtifactLogicalPath:
    text: str

@dataclass(frozen=True, slots=True)
class PrimitiveRenderSortKey:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedIncludeLine:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedImportLine:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedNamespaceText:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedModuleText:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedPrimitiveDeclarationText:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedPrimitiveDefinitionText:
    text: str

@dataclass(frozen=True, slots=True)
class RenderedPrimitiveBodyText:
    text: str

@dataclass(frozen=True, slots=True)
class PrimitiveRenderRecord:
    sort_key: PrimitiveRenderSortKey
    declarations: tuple[RenderedPrimitiveDeclarationText, ...]
    definitions: tuple[RenderedPrimitiveDefinitionText, ...]
    body_text: RenderedPrimitiveBodyText | None

@dataclass(frozen=True, slots=True)
class BackendPrimitiveRenderModel:
    backend_id: PrimitiveBackendId
    logical_path: PrimitiveArtifactLogicalPath
    profile_name: PrimitiveProfileName
    includes: tuple[RenderedIncludeLine, ...]
    imports: tuple[RenderedImportLine, ...]
    namespace_open: RenderedNamespaceText | None
    namespace_close: RenderedNamespaceText | None
    module_open: RenderedModuleText | None
    module_close: RenderedModuleText | None
    primitives: tuple[PrimitiveRenderRecord, ...]
```

Invariants:

- `PrimitiveRenderRecord.sort_key` is deterministic presentation ordering for
  already-rendered records. It is not dependency closure or topological
  dependency sorting; real dependency order remains a later render-plan
  boundary.
- C++ models consume include and namespace presentation fields. Rust models
  consume import and module presentation fields. Backend-inappropriate
  presentation fields are diagnostics, not silent drops.
- The adapter produces M217 `PrimitiveTemplateRenderContext` values only after
  rejecting raw TSIL/source sentinel values, unresolved semantic sentinel
  values, unsupported value shapes, unsupported backend ids, and
  backend-inappropriate fields.
- The adapter does not parse source, lower TSIL, translate backend semantics,
  select primitive implementations, plan dependencies, write artifacts, or run
  build verification.

## Diagnostics Model

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    location: SourceLocation | None
    notes: tuple[str, ...] = ()
```

Invariants:

- Codes are stable and testable.
- Messages are actionable.
- A pipeline result can contain partial outputs only if diagnostics do not include errors.

## Object Lifecycle

1. `SourceDocument` is created by the loader.
2. Parser produces syntax nodes with spans.
3. Catalog builder converts syntax into typed declarations.
4. Validator resolves cross-references and records diagnostics.
5. Expander creates concrete primitive variants.
6. Selector creates supported implementation candidates.
7. Dependency analyzer expands selected primitive set when requested.
8. Lowerer transforms implementation bodies into IR.
9. Backend planner creates render jobs and wrapper/test plans.
10. Renderer creates artifacts.
11. Writer commits artifacts to disk and reports digests.
12. Build verifier checks written generated projects when requested.

## Concepts That Should Not Leak Into The Domain Model

- Jinja template file names.
- Legacy module names and function names.
- CLI argument parser objects.
- `/proc/cpuinfo` and host-specific shell behavior.
- Output directory paths.
- Mutable global registries.
- Parser-private keys such as `_block`, `_spans`, or `_value_spans`.
- Compatibility facade names from `frozen/tsl-gen/tsl_gen/api.py`.
- Existing incomplete sketch paths like `tslgen.src.tslgen`.
