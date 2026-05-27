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
class PrimitiveDeclaration:
    name: PrimitiveName
    signature: Signature
    parameters: tuple[PrimitiveParameter, ...]
    attributes: PrimitiveAttributes
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

Invariants:

- Parameter count must match the signature shape after repeated/immediate rules are applied.
- Attributes must be valid for the signature and template.
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
    vendor: str
    family: str
    intrinsic_style: str
    vector_bits: VectorBits
    native_sort_order: int
    autodetect: bool
    lscpu_flags: tuple[FeatureFlag, ...]
    mask: MaskModel
    runtime_lanes: bool
    default_test_target: bool
    backend_support: FrozenMap[BackendId, BackendExtensionSupport]
    inherits: ExtensionName | None
    signature_support: SignatureSupportPolicy
    test_filter: TestFilterPolicy
    test_sizes_bits: tuple[int, ...]
    source: SourceSpan
```

Supporting values:

```python
VectorBits = FixedBits | SizedBits | ScalableBits
MaskRepresentation = Literal["bitset", "vector", "scalar", "bitset_array"]
MaskWidth = Literal["lanes"] | int
```

Invariants:

- Inheritance references an existing extension.
- Inheritance graph is acyclic.
- `runtime_lanes=true` means test and generation planning cannot assume a fixed lane count from vector bits alone.
- `vector_bits="sized"` requires a size parameter when concrete artifacts/tests are planned.
- Backend support is explicit; lack of support filters candidates for that backend.

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
class Target:
    backend: BackendId
    primitive_name: PrimitiveName
    extension: ExtensionName
    type_tag: TypeTag
    attributes: tuple[TargetAttribute, ...] = ()

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
    current_vector_keyword: str
    current_scalar_keyword: str
```

Invariants:

- `primitive` and `implementation` preserve the selected catalog object
  identity for diagnostics and traceability.
- `primitive_attributes` is the selected concrete `Primitive.attributes` tuple
  chosen by target selection.
- Declaration provenance such as `Primitive.declared_attributes` and
  `PrimitiveAttribute.declared_value` is not a separate semantic selector.
- `Vec` is a current selected-context vector keyword derived from the selected
  extension plus type tag, not a primitive specialization key.
- `scalar` is the current selected-context scalar/base type keyword derived
  from the selected type tag.
- `MaskVec`, `GenericVec`, and any other source identifier are not context
  built-ins. They are aliases only after the selected body binds them with
  exact `let<type>(...)` directives.

## Type Query Lowering Model

Milestone 142 adds a small selected-body type environment. It is built from
`SelectedImplementationLoweringContext` and the selected implementation body,
not from fresh source-file reads, `tsldata`, `frozen`, or `tslgenold`.

```python
@dataclass(frozen=True, slots=True)
class LoweredCurrentVectorType:
    extension: ExtensionName
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredCurrentScalarType:
    type_tag: TypeTag

@dataclass(frozen=True, slots=True)
class LoweredVectorAsExtensionType:
    scalar: LoweredCurrentScalarType
    extension: ExtensionName

LoweredTypeValue = (
    LoweredCurrentVectorType
    | LoweredCurrentScalarType
    | LoweredVectorAsExtensionType
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

@dataclass(frozen=True, slots=True)
class BackendTypeSpellingRequest:
    backend: BackendId
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation
```

Invariants:

- Context symbols are exactly the current `Vec` and `scalar` spellings for
  the selected implementation.
- Alias bindings are ordered by selected body token order.
- Alias references resolve only to earlier bindings in the same selected body.
- `type<backend>(...)` produces a `BackendTypeSpellingRequest`; it does not
  render backend type text.
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
