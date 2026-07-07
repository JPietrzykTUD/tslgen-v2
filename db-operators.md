TSL is a research prototype from the field of database engineering.
Thus, the helper functions should aim at typical database operations.
We assume a column-oriented data model, where each column is represented as a vector of values.
Processing happens either column at a time or batch at a time, where a batch is a vector of values from a single column.
For the sake of simplicity in this document, we only talk about batches, where batches can have an arbitrary number of values.

# Operator Shape And Mask Semantics

Helper APIs should be named by observable database shape, not only by the SIMD
primitive used inside an operation:

- **Transformation / map**: `N -> N` value output.
- **Predicate / to-mask**: `N -> N` logical mask output.
- **Selection / compaction**: `N -> K` value output, where `0 <= K <= N`.
- **Predicate count / cardinality**: `N -> 1` count of active predicate lanes.
- **Aggregation / reduction**: `N -> 1` scalar output.
- **Consumption / sink**: `N -> 0` output.

This distinction matters because the helper owns memory effects:

- whether inactive lanes are written at all;
- whether inactive lanes are written with a default/operator-provided value;
- whether active lanes are compacted into a smaller output;
- how many output elements are produced.

The operator owns register-level value logic, but the helper owns output layout
and store behavior. Therefore masked `N -> N` transforms need an explicit write
policy. The initial useful policies are:

- **where / preserve**: active lanes are written, inactive output lanes are not
  written and therefore keep their previous value.
- **masked full transform / fill**: the helper writes all lanes; the operator is
  responsible for returning meaningful values for inactive lanes.
- **selection / compaction**: inactive lanes are removed from the output, and
  the helper reports the number of produced values.

Mask output layout is also a first-class contract, not a vague hint. A mask
batch may be represented as one native `Vec::mask_type` per vector chunk, one
integral `Vec::imask_type` per vector chunk, packed bits over the whole batch,
or one byte/bool per input element. These layouts should become explicit policy
tags in helper APIs.

Selection vectors are related but distinct. A selection vector stores row ids or
lane indexes for selected tuples, for example:

```text
input values + selected row ids -> output values
```

This is not just another mask encoding. A mask answers "is lane `i` active?"
while a selection vector answers "which logical row should be read next?".
Selection-vector consumers imply indexed loads, gathers, or scalar indirection,
and the selected cardinality may already be smaller than the original batch.
Helpers that consume or produce selection vectors should therefore be a separate
family from mask-layout policies.

The implemented producer side is deliberately narrow: selection-vector producer
helpers write selected dense row ids, in input order, to a caller-owned unsigned
integral output range and return the produced count.

The implemented consumer side is also deliberately narrow:
`transform_selected_*`, `aggregate_selected_*`, and `consume_selected_*` read
row ids from a caller-owned unsigned integral range, load selected values in
row-id order, and then apply the operation shape. Pointer-backed 32-bit and
64-bit row-id streams use `gather_narrow`; narrower unsigned integral row-id
streams can still fall back to scalar or portable generic selected loads.
`Scale == 0` preserves the default element-index contract by using a byte scale
of `sizeof(T)`.

The implemented refinement side sits between producer and consumer:
`select_selected_indices_*` reads an existing row-id stream, evaluates a
predicate over selected rows using the same scalar/generic fallback, and writes
a new dense row-id stream containing the original row ids that passed the
predicate.

# Helper Infrastructure Sketch

The helper infrastructure should be unified around a small number of orthogonal
axes and a small number of reusable implementation components. Dense transforms
should remain easy to call, but masks, selection vectors, compaction, and
aggregation should fit into the same mental model.

This does not mean there should be one giant public template that covers every
database operator. The public surface should stay named by observable operator
shape. The internal implementation can share vector selection, alignment
dispatch, row enumeration, load adapters, operation invocation, output writers,
and tail handling.

## Core Invariant

The helper owns physical execution mechanics:

- vector type selection from `T` and the requested parallelism policy;
- alignment dispatch;
- chunk and tail iteration;
- dense, masked, or selected row enumeration;
- contiguous loads, masked loads, indexed loads, or gathers;
- stores, masked stores, compaction stores, mask materialization, or aggregate
  finalization;
- output cardinality and returned produced counts.

The user operation owns only register-level logic:

- map one register to one register;
- combine several registers into one register;
- produce a predicate mask from one or more registers;
- update an aggregate register/state;
- optionally consume the helper-provided activity mask in explicitly masked
  helper families.

If an operation performs ordinary input/output pointer arithmetic itself, the
helper can no longer guarantee alignment behavior, tail coverage, output layout,
or produced cardinality.

## Public API Layer

The public API should be a set of named free functions in `tsl::algo`, grouped
by database operator shape:

```cpp
namespace tsl::algo {

template <class Parallelism = parallelism::native,
          class Alignment = alignment::detect,
          class Op,
          class T>
void transform_unary(Op&& op, T const* input, T* output, std::size_t count);

template <class Parallelism = parallelism::native,
          class Alignment = alignment::detect,
          class Op,
          class T>
void transform_binary(
    Op&& op,
    T const* left,
    T const* right,
    T* output,
    std::size_t count);

template <class Parallelism = parallelism::native,
          class Alignment = alignment::detect,
          class MaskLayout = mask_layout::integral,
          class Op,
          class T>
void transform_where_unary(
    Op&& op,
    T const* input,
    mask_storage_type<MaskLayout, Parallelism, T> const* masks,
    T* output,
    std::size_t count);

template <class Parallelism = parallelism::native,
          class Alignment = alignment::detect,
          class Op,
          class T>
std::size_t select_unary(
    Op&& predicate,
    T const* input,
    T* output,
    std::size_t count);

}  // namespace tsl::algo
```

The implemented helper families use policy-form overloads ordered as
`Parallelism`, `Alignment`, then optional `MaskLayout`, plus concise
`ParallelN` overloads ordered as `ParallelN`, `Alignment`, then optional
`MaskLayout`. The important part is that callers choose database shape by
function name, while parallelism, alignment, row source, and mask layout are
policy tags.

Dense `transform_unary` and `transform_binary` allow exact in-place output:
`output == input` for unary transforms, and `output == left` or
`output == right` for binary transforms. Shifted or otherwise partial overlap is
not part of the helper contract; the helper iterates forward and does not
buffer input or choose a `memmove`-style direction.

For the implemented dense helpers, the public shape is deliberately small:

```cpp
tsl::algo::transform_unary(op, input, output, count);
tsl::algo::transform_unary<4>(op, input, output, count);
tsl::algo::transform_unary<
    tsl::algo::parallelism::fixed<4>,
    tsl::algo::alignment::unaligned>(op, input, output, count);
```

`Vec` should not be a public template parameter of these helpers. The helper
derives the concrete generated vector type from `T` and the parallelism policy,
then invokes the operation with that internal `Vec`. The direct `N` overload is
the concise exact-lane spelling; it forwards to `parallelism::fixed<N>`.

## Axes

### Parallelism

Parallelism describes how the helper chooses the generated vector type.

```cpp
namespace tsl::algo::parallelism {
struct native {};                    // best native vector in the generated profile
template <std::size_t N> struct fixed {}; // exactly N elements per vector chunk
}
```

The mapping is internal:

```cpp
parallelism::native   -> tsl::dataparallel::simd_for_t<tsl::dataparallel::native, T>
parallelism::fixed<N> -> tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<N>, T>
```

The helper should assert that fixed parallelism produces a static lane count
equal to `N`.

### Alignment

Alignment describes the caller's memory-access promise.

```cpp
namespace tsl::algo::alignment {
struct detect {};         // runtime-dispatch each pointer once
struct unaligned {};      // always use unaligned load/store primitives
struct assume_aligned {}; // caller promises all operands match Vec alignment
struct assume_inputs_aligned {}; // caller promises dense transform inputs align
struct assume_output_aligned {}; // caller promises dense transform output aligns
struct peel_to_aligned {}; // scalar-prologue dense transforms when possible
}
```

`alignment::detect` is the default. It should check the relevant data pointers
against `Vec::vector_alignment` once before the loop, then dispatch to a
statically typed inner loop. Dense `transform_unary` and `transform_binary`
also accept `alignment::assume_inputs_aligned` and
`alignment::assume_output_aligned` for common mixed input/output promises
without runtime detection. `assume_inputs_aligned` means all dense transform
input loads are aligned; for binary transforms both input columns are promised
aligned. `assume_output_aligned` means the single dense transform output store
is aligned. Dense transforms also accept `alignment::peel_to_aligned`: if all
memory operands have compatible alignment residues, the helper runs scalar
iterations until the vector loop is aligned; otherwise it falls back to the
unaligned vector loop. Other helper families should not accept these
transform-only tags until they have an explicit contract for them.

### Row Source

The row source describes which logical input rows are visible to the operator.

```cpp
namespace tsl::algo::rows {
struct dense {};              // rows are 0, 1, 2, ... count - 1
struct native_mask {};        // activity is stored as Vec::mask_type chunks
struct integral_mask {};      // activity is stored as Vec::imask_type chunks
struct bit_mask {};           // activity is stored as packed bits
struct byte_mask {};          // activity is stored as one byte/bool per row
struct selection_vector {};   // activity is stored as explicit row ids
}
```

Dense rows and masks preserve the natural input order and usually read from
contiguous memory. Selection vectors enumerate logical rows explicitly and imply
indexed loads, gathers, or scalar indirection.

### Load Mode

The load mode describes how row-source positions become register values.

```cpp
namespace tsl::algo::load_mode {
struct contiguous {}; // load input + i
struct masked {};     // load input + i with an activity mask
struct indexed {};    // load input + selected_ids[i]
struct gather {};     // gather several selected ids into one Vec
}
```

The first implementation slices should focus on contiguous loads. Indexed and
gather modes are important for selection-vector consumers, dictionary lookups,
and hash/probe operators, but they are a separate complexity class.

### Output Mode

The output mode describes how computed values become observable output.

```cpp
namespace tsl::algo::output {
struct full_store {};       // write every lane, N -> N
struct where_store {};      // write active lanes only, N -> N, inactive preserved
struct compact_store {};    // write active lanes densely, N -> K
struct native_mask_store {};   // materialize Vec::mask_type chunks
struct integral_mask_store {}; // materialize Vec::imask_type chunks
struct bit_mask_store {};      // materialize packed bits
struct byte_mask_store {};     // materialize one byte/bool per row
struct aggregate {};        // fold into scalar/state, N -> 1
struct sink {};             // no helper-owned output, N -> 0
}
```

This is the axis that separates masked `N -> N` transforms from compaction.
Both may use masks internally, but they produce different batch layouts.

### Operation Arity

Operation arity describes how many value columns are loaded for each logical
row:

```cpp
namespace tsl::algo::arity {
struct unary {};
struct binary {};
struct ternary {};
}
```

Unary and binary helpers are enough for the first useful slices. Wider arity can
be added later without changing the row-source/output model.

### Mask Layout

Mask layout is used when masks are inputs or outputs. It is not the same as a
selection vector.

```cpp
namespace tsl::algo::mask_layout {
struct native {};
struct integral {};
struct bits {};
struct bytes {};
}
```

Native masks are closest to generated TSL primitives. Integral masks are often
convenient for storage, counting, and bit operations. Packed bits and byte masks
are batch-memory formats and need dedicated load/store logic.
The implemented packed-bit layout uses one bit per row in little-endian bit
order within each byte: row `i` maps to byte `i / 8`, bit `i % 8`.

### Tail Policy

Tail policy describes how the last partial chunk is handled.

Dense transforms can use a scalar tail loop with `tsl::simd<T, tsl::scalar>`.
Masked, predicate, and compaction helpers may prefer a partial activity mask
when the generated primitive set supports masked load/store or compress. The
tail policy should stay internal for the first public APIs; exposing it too
early would leak implementation details.

## Conceptual Pipeline

Most helper families can be described as the same high-level pipeline:

```text
for each logical chunk from the row source:
  build activity/tail information
  load one or more value registers
  call the user operation
  materialize according to the output mode
return any produced count, aggregate, or status
```

The helper owns row enumeration, pointer arithmetic, tail handling, mask
combination, memory writes, output counts, and alignment policy. The operator
owns register-level value logic.

## Internal Building Blocks

The reusable implementation should be layered roughly like this:

```text
public helper
  validates policy tags and pointer type compatibility
  derives Vec from T + Parallelism
  dispatches alignment policy
  calls one typed detail loop

detail loop
  enumerates chunks from a row source
  asks loaders to materialize register inputs
  invokes the user operation through the invocation adapter
  asks an output writer to materialize the result
  handles scalar or masked tail
  returns void, produced count, aggregate value, or sink status
```

The likely internal concepts are:

- `vector_for_parallelism<Parallelism, T>`: maps public shape to generated
  `Vec`.
- `alignment_dispatch`: turns `detect`, `unaligned`, or `assume_aligned` into
  static load/store alignment tags for one typed loop.
- `row_source`: yields dense chunks, mask chunks, or selected row ids.
- `loader`: turns row-source positions into one or more `Vec::register_type`
  values.
- `op_invoker`: supports `op.template operator()<Vec>(...)`,
  `op(vector_tag<Vec>{}, ...)`, and plain `op(...)` where possible.
- `output_writer`: performs full stores, where stores, compaction stores, mask
  materialization, aggregate updates, or sink calls.
- `tail_handler`: runs scalar tail or builds a tail activity mask.

These should be private implementation details. Users should see named
algorithm helpers, not a framework of executor objects.

## Operation Invocation

Operations should support both high-control functors and C++17-friendly tagged
callables:

```cpp
struct functor_op {
  template <class Vec>
  typename Vec::register_type operator()(
      typename tsl::reg_param<Vec>::type value) const;
};

auto tagged_op = [](auto tag, auto value) {
  using Vec = typename decltype(tag)::type;
  return tsl::mul<Vec>(value, value);
};
```

The invocation adapter should prefer the typed functor form, then the
`vector_tag<Vec>` form, then a plain callable. This lets simple scalar-looking
operations work when they are type-compatible, while still allowing explicit
generated-primitive calls.

## Generated Primitive Dependencies

Each helper family should declare the generated primitive roots it requires.
The C++ backend can then make sure those primitives are included whenever the
helper asset is shipped.

If a helper family appears to need a primitive that is not already in the
declared support-root set, pause the helper implementation and decide whether
that primitive belongs in `tsldata` and C++ generation policy. Do not silently
invent a local-only primitive inside the helper.

Implemented dense helpers require:

- `load`;
- `store`;
- the operation's own primitives, referenced directly by the user's operation.

Implemented integral-mask, native-mask, byte-mask, and packed-bit-mask
predicate/where/masked helpers additionally require:

- `to_integral` to materialize `Vec::mask_type` as one `Vec::imask_type` per
  vector chunk for predicate output;
- `to_mask` to turn stored integral masks back into `Vec::mask_type` for
  mask-consuming transforms and to build native-mask tail chunks from scalar
  tail results. Byte masks use the same conversion to build vector masks from
  per-row bytes, and packed-bit masks use it after unpacking row bits into an
  integral mask;
- `store_mask`, emitted from the generated `store` primitive's pass-through
  masked form, only for where-preserve output lanes. Masked full-store uses the
  ordinary full `store`.

Implemented value selection/compaction additionally requires:

- `compress_store` to write active lanes densely to the output range;
- `mask_population_count` to advance the output cursor by the number of active
  lanes in each vector chunk.

Implemented masked value selection/compaction additionally requires:

- `mask_binary_and` to combine the helper-provided input mask with the
  operation-produced predicate mask before compaction.

Implemented selection-vector producers additionally require:

- `to_integral` so the helper can enumerate active lanes from the
  operation-produced predicate mask and write row ids with ordinary scalar
  stores.

Implemented masked selection-vector producers additionally require:

- `mask_binary_and` to combine the helper-provided input mask with the
  operation-produced predicate mask before row-id output.

Implemented selected-row selection-vector refinement additionally requires:

- `to_integral` so the helper can enumerate active lanes from the predicate
  mask and copy the corresponding original row ids from the input selection
  vector to the output selection vector.

Implemented predicate count helpers additionally require:

- `mask_population_count` to add active vector lanes to the returned
  cardinality;
- `to_integral` for scalar tail predicate checks;
- `mask_binary_and` for masked count helpers, where the helper combines input
  activity with the operation-produced predicate before counting.

Implemented selected-row predicate count helpers additionally use
`gather_narrow` for pointer-backed 32-bit and 64-bit row-id streams. Narrower
unsigned integral row-id streams remain a portable generic fallback case.

Implemented selected-row transform consumers additionally require `store` for
dense selected output. Implemented selected-row aggregate and consume helpers
add no output primitive roots. These helpers load selected input rows through
`gather_narrow` for pointer-backed 32-bit and 64-bit row-id streams, then call
the operation. Operation-specific primitives remain normal user-operation
dependencies.

Implemented unary and binary aggregation do not add helper-owned primitive roots
beyond the dense input roots. The operation's own accumulator/finalization
primitives, such as `hadd`, remain normal user-operation dependencies.

Implemented masked aggregation adds no helper-owned primitive roots beyond the
existing mask-consuming and dense input roots. The helper loads masks and input
values, but the operation owns inactive-lane filtering and any
accumulator/finalization primitives it calls.

Implemented consume helpers do not add helper-owned primitive roots beyond the
dense input roots. The operation owns side effects, external state, and any
operation-specific primitives it calls.

Implemented `for_each_chunk` adds no helper-owned primitive roots. The helper
only enumerates chunks; any `load`, `store`, or other generated primitive calls
are normal operation dependencies.

Future families add more roots only when the observable shape needs them:

- other predicate mask layouts need mask materialization support for the
  selected `mask_layout`;
- binary, masked, or transform-and-select compaction helpers may need additional
  load, combine, or compact-store support depending on their exact output
  contract;
- future aggregate variants need horizontal reduction/finalization primitives
  or a scalar finalization path only when the helper, rather than the operation,
  owns that reduction step;
- selection-vector consumers need indexed load, gather, or scalar indirection
  support. The current pointer-backed selected consumers use `gather_narrow`.
  Plain `gather` is reserved for a future row source that consumes caller-owned
  index-register chunks.

`gather_narrow` is now part of the C++ helper support-root set because it maps
directly to caller-owned row-id pointers. A future plain-`gather` helper still
needs a separate public contract because it would consume an index register
rather than a row-id pointer range. It must not be selected from lane count
alone.

This dependency model should stay C++-backend policy. It should not become new
TSIL syntax or a new source-data concept.

## Public API Principle

The dense common case should stay simple:

```cpp
tsl::algo::transform_unary<8>(op, input, output, count);
```

More complex row sources should become explicit at the call site:

```cpp
tsl::algo::transform_where_unary<8>(
    op,
    tsl::algo::rows::native_mask{},
    input,
    mask,
    output,
    count);

tsl::algo::select_unary<8>(
    predicate,
    input,
    output,
    count);

tsl::algo::gather_transform_unary<8>(
    op,
    tsl::algo::rows::selection_vector{},
    input,
    selected_ids,
    output,
    selected_count);
```

These examples are sketches, not final API. The important rule is that a helper
name and policy set must reveal the observable batch shape.

## Candidate Helper Families

The axes above suggest these helper families:

- `transform_unary` / `transform_binary`: dense `N -> N` value output.
- `transform_where_unary` / `transform_where_binary`: masked `N -> N` value
  output with inactive output preserved.
- `transform_masked_unary` / `transform_masked_binary`: masked full-store
  `N -> N` value output where the operator owns inactive lane values.
- `predicate_unary` / `predicate_binary`: `N -> N` mask output with explicit
  mask layout.
- `select_unary` / `select_binary`: `N -> K` compacted left-value output plus
  produced count.
- `select_masked_unary` / `select_masked_binary`: mask-consuming `N -> K`
  compacted value output plus produced count.
- `select_indices_unary` / `select_indices_binary`: `N -> K` row-id output
  plus produced count.
- `select_masked_indices_unary` / `select_masked_indices_binary`:
  mask-consuming `N -> K` row-id output plus produced count.
- `select_selected_indices_unary` / `select_selected_indices_binary`:
  selection-vector refinement producing `K -> M` row-id output plus produced
  count.
- `transform_selected_unary` / `transform_selected_binary`: selection-vector
  consumer producing dense `K -> K` transformed value output in row-id order.
- `aggregate_selected_unary` / `aggregate_selected_binary`: selection-vector
  consumer producing `K -> 1` scalar/state output.
- `consume_selected_unary` / `consume_selected_binary`: selection-vector
  consumer producing no helper-owned output.
- `count_unary` / `count_binary`: predicate cardinality producing an
  `N -> 1` count without materializing masks, compacted values, or row ids.
- `count_masked_unary` / `count_masked_binary`: mask-consuming predicate
  cardinality producing an `N -> 1` count after combining input activity and
  predicate activity.
- `count_selected_unary` / `count_selected_binary`: selection-vector predicate
  cardinality producing a `K -> 1` count from selected row ids.
- `aggregate_unary` / `aggregate_binary`: `N -> 1` scalar/state output.
- `aggregate_masked_unary` / `aggregate_masked_binary`: mask-consuming
  `N -> 1` scalar/state output.
- `consume_unary` / `consume_binary`: `N -> 0` side-effect sink.
- `consume_masked_unary` / `consume_masked_binary`: mask-consuming `N -> 0`
  side-effect sink.
- `for_each_chunk`: low-level chunk enumeration escape hatch for operations
  that need pointer/chunk metadata and own their memory effects.
- future index-register consumers: indexed or gather-driven operators that
  consume caller-owned index-register chunks rather than row-id pointers.

## Incremental Implementation Order

The safest implementation order is:

1. Dense `transform_unary` and `transform_binary`: contiguous `N -> N` value
   output, scalar tail, generated `load`/`store`.
2. Predicate helpers: contiguous input, `N -> N` mask output, explicit
   `mask_layout`. Current implementation supports `mask_layout::integral` and
   `mask_layout::native`, `mask_layout::bytes`, and `mask_layout::bits`.
3. Where helpers: input mask plus value output, inactive output preserved.
   Current implementation consumes integral, native, byte, and packed-bit mask
   layouts.
4. Masked full-store helpers: input mask plus value output, inactive values
   supplied by the operation. Current implementation consumes integral and
   native mask chunks, byte masks, or packed-bit masks and writes every output
   lane.
5. Selection/compaction helpers: contiguous input, predicate operation,
   compacted output plus produced count. Current implementation supports
   `select_unary` and `select_binary`, which compact active left-input values.
6. Masked selection/compaction helpers: input mask plus predicate operation,
   compacted output plus produced count. Current implementation supports
   `select_masked_unary` and `select_masked_binary`, which compact left-input
   values whose stored input mask and operation-produced predicate mask are both
   active.
7. Selection-vector producer helpers: contiguous input, predicate operation,
   row-id output plus produced count. Current implementation supports
   `select_indices_unary` and `select_indices_binary`, which write selected
   dense row ids in input order to a caller-owned unsigned integral output
   range.
8. Masked selection-vector producer helpers: input mask plus predicate
   operation, row-id output plus produced count. Current implementation
   supports `select_masked_indices_unary` and `select_masked_indices_binary`
   for integral, native, byte, and packed-bit mask layouts.
9. Selected-row selection-vector refinement: selection vector plus one or more
   input columns, refined row-id output. Current implementation supports
   `select_selected_indices_unary` and `select_selected_indices_binary`, which
   preserve input selection-vector order and write original row ids.
10. Selected-row transform consumers: selection vector plus one or more input
   columns, dense selected output. Current implementation supports
   `transform_selected_unary` and `transform_selected_binary` with
   `gather_narrow` for pointer-backed 32-bit and 64-bit row-id streams.
11. Selected-row aggregate and consume helpers: selection vector plus one or
   more input columns, scalar/state output or no helper-owned output. Current
   implementation supports `aggregate_selected_unary`,
   `aggregate_selected_binary`, `consume_selected_unary`, and
   `consume_selected_binary` with the same selected-row loading policy.
12. Predicate count helpers: contiguous, mask-consuming, or selected-row input,
   operation, scalar cardinality output. Current implementation supports
   `count_unary`, `count_binary`, `count_masked_unary`, and
   `count_masked_binary` for integral, native, byte, and packed-bit mask
   layouts, plus `count_selected_unary` and `count_selected_binary` for
   selection-vector row sources.
13. Aggregation helpers: contiguous input, vector accumulator, scalar
   finalization. Current implementation supports `aggregate_unary` and
   `aggregate_binary`, where the operation owns accumulator state and exposes
   `finalize()`.
14. Masked aggregation helpers: input mask plus contiguous input, vector
   accumulator, scalar finalization. Current implementation supports
   `aggregate_masked_unary` and `aggregate_masked_binary` for integral, native,
   byte, and packed-bit mask layouts. The operation must accept the activity
   mask and account for inactive lanes in its accumulator state.
15. Consume helpers: contiguous input, no helper-owned output. Current
   implementation supports `consume_unary` and `consume_binary`.
16. Masked consume helpers: input mask plus contiguous input, no helper-owned
    output. Current implementation supports `consume_masked_unary` and
    `consume_masked_binary` for integral, native, byte, and packed-bit mask
    layouts. The operation must accept the activity mask and account for
    inactive lanes in its side effects or external state.
17. Chunk escape hatch: contiguous input pointer plus chunk metadata, no
    helper-owned memory effects. Current implementation supports
    `for_each_chunk`, where the operation receives `(chunk_ptr, offset, count)`
    for full vector chunks and scalar tail elements.
18. Range overloads: C++17 objects compatible with `std::data(range)` and
    `std::size(range)`. Current implementation forwards range calls to the
    pointer+count APIs and does not allocate, resize, or validate output
    capacity.
19. Future index-register row sources: caller-owned index-register chunks,
   plain `gather`, index-vector type, scale policy, fallback behavior, and
   output shape chosen by a separate helper family.

Each step should add the minimum generated primitive roots needed for that
family and should include a generated-library consumer example.

## Deliberate Non-Unification

Masks and selection vectors should share vocabulary as row sources, but they
should not be treated as interchangeable representations:

- masks are lane-activity descriptors for a dense row range;
- selection vectors are explicit row-id streams;
- masks preserve dense-position semantics;
- selection vectors may reorder rows or represent a pre-filtered subset;
- masks usually combine naturally with SIMD masked load/store;
- selection vectors require indexed access, gather, or scalar loops.

Similarly, compaction and aggregation should not both be called reduction.
Compaction preserves selected values and changes cardinality to `K`.
Aggregation combines values into one scalar or state.

# Unary Operations

## Unary Transformation: N in, N out
Unary transformations are operations that take a single input batch and produce a single output batch. In the context of database engineering, these transformations can include:
- **Value Mapping**: Transforming values from one representation to another, such as converting data types or applying functions to modify values.
- **Value Manipulation**: Performing operations on individual values, such as multiplying a numeric field by a constant.

### Example-Operation
```cpp
struct square_op {
    template <class Vec>
    typename Vec::register_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::mul<Vec>(value, value);
    }
};
```


## Unary Where Transformation: N in, N out, inactive output preserved
Unary where transformations take a single input batch and a validity/predicate
mask and produce a single output batch with the same logical cardinality.
Active lanes are transformed and written. Inactive lanes are not written by the
helper, so the previous output value is preserved.

In the context of database engineering, these transformations can include:
- **Value Mapping**: Transforming values from one representation to another only for active values.
- **Value Manipulation**: Performing operations on individual active values, such as multiplying a numeric field by a constant.

This is a different helper from compaction. The output still has `N` slots.

### Example-Operation
```cpp
struct square_where_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type mask, 
        typename tsl::reg_param<Vec>::type value
    ) const {
        (void)mask;
        return tsl::mul<Vec>(value, value);
    }
};
```

The helper is responsible for using a masked store with the same `mask`. The
operator computes the candidate value; it does not decide whether inactive
lanes are written.

## Unary Masked Full Transformation: N in, N out, inactive output filled
Unary masked full transformations also take a single input batch and a mask and
produce a single output batch with the same logical cardinality. Unlike a where
transformation, the helper stores all lanes. The operator must therefore return
meaningful values for inactive lanes.

This shape is useful when inactive output lanes should become a default value,
the original input value, or another operator-defined value.

### Example-Operation
```cpp
struct square_masked_fill_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type mask,
        typename tsl::reg_param<Vec>::type value
    ) const {
        const typename Vec::register_type squared_value = tsl::mul<Vec>(value, value);
        return tsl::blend<Vec>(mask, value, squared_value);
    }
};
```

## Unary Selection / Compaction: N in, K out, where 0 <= K <= N
Unary selection operations take a single input batch and produce a smaller
output batch by compacting active or selected lanes. These transformations
include:
- **Filtering**: Removing values that do not meet certain criteria, such as filtering out null values or values below a threshold.

This is not a reduction in the aggregation sense. The helper must own the
output write position and return or update the produced count.

### Example-Operation
```cpp
struct filter_lt_op {
    std::int32_t threshold_;

    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold_)));
    }
};
```

The helper compacts `value` for active lanes, writes the dense output range, and
returns the produced count. The predicate operation does not call `compress` or
write output memory itself.

Binary value selection follows the same output contract: the predicate sees
`(left, right)`, but the dense output stream contains selected values from
`left`. Callers that want to compact another column can pass that column as the
left input and encode the predicate accordingly.

## Masked Selection / Compaction: N in, K out, where 0 <= K <= N
Masked selection operations take one or more input batches and an input
validity mask, then produce a smaller output batch by compacting left-input
lanes that are both valid and selected. These transformations include:
- **Filtering**: Removing values that do not meet certain criteria, such as filtering out null values or values below a threshold, but only for the values that are marked as valid in the mask.

The implemented helper combines the input validity mask and the operator
predicate with logical AND before compaction. The operation only produces the
predicate mask.

### Example-Operation
```cpp
struct filter_masked_lt_op {
    std::int32_t threshold_;

    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold_)));
    }
};
```

## Selection Vector Production: N in, K row ids out, where 0 <= K <= N
Selection-vector production takes one or more dense input batches and writes
the row ids whose predicate is active. This keeps filtering as an intermediate
row-id stream instead of immediately compacting values.

The implemented helpers are:

- `select_indices_unary`
- `select_indices_binary`
- `select_masked_indices_unary`
- `select_masked_indices_binary`

The output element type is caller-provided and must be an unsigned integral
row-id type, such as `std::uint32_t` or `std::size_t`. The helper writes dense
input indexes in ascending input order, returns the produced count, and does
not touch output positions after `produced`.

### Example-Operation
```cpp
struct selected_row_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};
```

This is a producer-side selection-vector helper. It does not consume row ids,
perform indexed loads, or gather values. Consumer shapes remain separate because
they own the selected-load policy and, for pointer-backed row ids, use
`gather_narrow`.

## Selected-Row Selection Vector Refinement: K row ids in, M row ids out
Selected-row refinement consumes an existing selection vector and writes a new
selection vector. The helper evaluates the predicate on selected input rows,
but the output contains the original row ids, not positions inside the selected
stream.

The implemented helpers are:

- `select_selected_indices_unary`
- `select_selected_indices_binary`

This is the natural shape for chaining filters in a database engine:

```text
input columns + selected row ids -> refined selected row ids
```

Input and output selection-vector element types must be unsigned integral row-id
types. The helper preserves input selection-vector order, returns the produced
count, and does not touch output positions after `produced`.

### Example-Operation
```cpp
struct selected_filter_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};
```

Selected-row refinement uses the same selected-load policy as the other
selected-row consumers: pointer-backed 32-bit and 64-bit row-id streams use
`gather_narrow`, while narrower unsigned integral row-id streams remain a
portable generic fallback case. Signed integers and `bool` are rejected because
negative or truth-valued row ids are not meaningful byte offsets. A plain
`gather` path needs an index register, not just a pointer to row ids, so it
belongs to a separate index-register helper shape. The pointer-backed helpers
must not auto-promote to plain `gather` from lane count alone.

## Selected-Row Transformation: K selected row ids in, K values out
Selected-row transformations consume a selection vector and one or more dense
input batches. The helper reads selected row ids, loads those rows, invokes the
operation, and writes a dense output range in selection-vector order.

The implemented helpers are:

- `transform_selected_unary`
- `transform_selected_binary`
- `aggregate_selected_unary`
- `aggregate_selected_binary`
- `consume_selected_unary`
- `consume_selected_binary`

These helpers use `gather_narrow` for pointer-backed 32-bit and 64-bit row-id
streams and fall back to scalar or portable generic selected loads where
needed. Plain `gather` is not selected from lane count alone because it requires
a generated index-register construction path in addition to the value gather
primitive. A future plain-`gather` helper should consume caller-owned
index-register chunks as its row source. Transform helpers write dense selected
output values. Aggregate helpers call `finalize()` on the operation and return
that value. Consume helpers return `void` and rely on the operation's
externally visible state.

### Example-Operation
```cpp
struct selected_square_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::mul<Vec>(value, value);
    }
};
```

The caller owns the validity of row ids and output capacity. The helper does
not bounds-check the selection vector, resize output storage, or promise a
specific native gather instruction.

## Predicate Count / Cardinality: N or K in, 1 count out
Predicate count operations take one or more input batches and return the number
of rows whose predicate is active. They do not materialize a mask, compact
values, or write a selection vector.

The implemented helpers are:

- `count_unary`
- `count_binary`
- `count_masked_unary`
- `count_masked_binary`
- `count_selected_unary`
- `count_selected_binary`

Masked count helpers combine the input activity mask and the
operation-produced predicate mask before counting. Selected count helpers
evaluate the predicate over an existing selection vector and return how many
selected rows match. This is a separate shape from aggregation: the helper owns
the cardinality accumulation, while the operation only decides lane activity.

### Example-Operation
```cpp
struct count_negative_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};
```

The returned count is a `std::size_t`. Empty input returns `0`.


## Unary Aggregation: N in, 1 out
Unary aggregations are operations that take a single input batch and produce a single output value. These transformations can include:
- **Summation**: Calculating the sum of all values in a batch.
- **Average**: Calculating the average of all values in a batch.
- **Maximum/Minimum**: Finding the maximum or minimum value in a batch.

### Example-Operation
```cpp
struct sum_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(typename tsl::reg_param<Vec>::type value) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(value));
    }

    std::int64_t finalize() const {
        return total;
    }
};
```

The implemented dense aggregation contract is intentionally stateful:
`aggregate_unary` calls the operation with one loaded register, and
`aggregate_binary` calls it with two loaded registers. In both cases, the helper
calls the operation once per vector chunk and once per scalar tail element,
then returns `op.finalize()`. Identity values, reduction order, overflow
behavior, and floating-point policy are therefore explicit in the operation
rather than hidden in the helper.


## Masked Aggregation: N in, 1 out
Masked aggregations take one or more contiguous input batches plus a mask and
produce a single output value. These transformations can include:

- **Summation**: Calculating the sum of active values in a batch.
- **Average**: Calculating the average of active values in a batch.
- **Maximum/Minimum**: Finding the maximum or minimum active value in a batch.

### Example-Operation
```cpp
struct sum_masked_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) {
        const auto zero = tsl::set1<Vec>(static_cast<typename Vec::base_type>(0));
        const auto selected = tsl::blend<Vec>(active, zero, value);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }

    std::int64_t finalize() const {
        return total;
    }
};
```

The implemented masked aggregation contract is also stateful:
`aggregate_masked_unary` calls the operation with `(active_mask, value)`, and
`aggregate_masked_binary` calls it with `(active_mask, left, right)`. Unlike
where-style transforms, there is no masked store step after the operation.
Therefore masked aggregation requires a mask-aware operation; the helper does
not fall back to an unmasked operation because that would silently aggregate
inactive lanes.

## Unary ToMask Transformation: N in, N out
Unary to mask transformations are operations that take a single input batch and produce a single output batch, where the output batch has the same number of values as the input batch, but the meaning of the values is changed to a mask.
As in TSL a mask is a semantic type, this type of transformation needs an
explicit mask-layout policy. The output may be native masks, integral masks,
packed bits, or byte/bool values, depending on downstream needs. A selection
vector is a separate `N -> K row ids` shape, not a mask layout. These
transformations can include:
- **Masking**: Creating a mask based on certain conditions, such as marking values that meet specific criteria (e.g., values greater than a threshold) as true and others as false.

### Example-Operation
```cpp
struct filter_to_mask_lt_op {
    std::int32_t threshold_;

    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold_)));
    }
};
```


## Unary Masked ToMask Transformation: N in, N out
Unary masked to mask transformations are operations that take a single input batch and a mask and produce a single output batch, where the output batch has the same number of values as the input batch, but the meaning of the values is changed to a mask.
As in TSL a mask is a semantic type, this type of transformation needs an
explicit mask-layout policy. The helper must also define whether the output mask
contains only the operator predicate or the conjunction of input validity and
the operator predicate. These transformations can include:
- **Masking**: Creating a mask based on certain conditions, such as marking values that meet specific criteria (e.g., values greater than a threshold) as true and others as false, but only for the values that are marked as valid in the input mask.

### Example-Operation
```cpp
struct filter_masked_to_mask_lt_op {
    std::int32_t threshold_;

    template <class Vec>
    typename Vec::mask_type operator()(
        typename Vec::mask_type mask, 
        typename tsl::reg_param<Vec>::type value
    ) const {
        const auto predicate = tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold_)));
        return tsl::mask_binary_and<Vec>(mask, predicate);
    }
};
```


## Unary Consumption: N in, 0 out
Unary consumption operations are operations that take a single input batch and produce no output batch. These transformations can include:
- **Logging**: Recording information about the values in a batch for debugging or auditing purposes.

### Example-Operation
```cpp
struct sum_sink {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(typename tsl::reg_param<Vec>::type value) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(value));
    }
};
```

The helper returns `void`; the operation owns any externally visible effect.
Passing an lvalue operation lets callers observe mutated state after the helper
returns.


## Masked Consumption: N in, 0 out
Masked consumption operations take one or more input batches plus a mask and
produce no helper-owned output. These transformations can include:

- **Logging**: Recording active values for debugging or auditing.
- **Stateful sinks**: Updating external state only for active rows.

### Example-Operation
```cpp
struct masked_sum_sink {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) {
        const auto zero = tsl::set1<Vec>(static_cast<typename Vec::base_type>(0));
        const auto selected = tsl::blend<Vec>(active, zero, value);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }
};
```

The implemented masked consume helpers are `consume_masked_unary` and
`consume_masked_binary`. As with masked aggregation, the operation must accept
the activity mask because there is no later helper-owned output step that can
ignore inactive lanes.

# Binary Operations

## Binary Transformation: N in, N out
Binary transformations are operations that take two input batches and produce a single output batch. In the context of database engineering, these transformations can include:
- **Value Combination**: Combining values from two batches, such as adding corresponding values or concatenating strings.
- **Value Comparison**: Comparing values from two batches to produce a new batch of results, such as determining which values are greater or equal.
- **Value Manipulation**: Performing operations on pairs of values, such as multiplying corresponding values from two batches.
- **Value Mapping**: Applying a function to pairs of values from two batches to produce a new batch of results.

### Example-Operation
```cpp
struct add_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type value1,
        typename tsl::reg_param<Vec>::type value2) const {
        return tsl::add<Vec>(value1, value2);
    }
};

struct max_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type value1,
        typename tsl::reg_param<Vec>::type value2) const {
        return tsl::max<Vec>(value1, value2);
    }
};
```


## Binary Where Transformation: N in, N out, inactive output preserved
Binary where transformations take two input batches and a mask and produce a
single output batch with the same logical cardinality. Active lanes are
computed and written. Inactive output lanes are not written by the helper.

In the context of database engineering, these transformations can include:
- **Value Combination**: Combining active values from two batches, such as adding corresponding values or concatenating strings.
- **Value Comparison**: Comparing active values from two batches to produce a new batch of results.
- **Value Manipulation**: Performing operations on active pairs of values.
- **Value Mapping**: Applying a function to active pairs of values.

### Example-Operation
```cpp
struct add_where_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type mask, 
        typename tsl::reg_param<Vec>::type value1, 
        typename tsl::reg_param<Vec>::type value2
    ) const {
        (void)mask;
        return tsl::add<Vec>(value1, value2);
    }
};
```

As with unary where transforms, the helper owns the masked store. A separate
binary masked full transformation can exist when inactive lanes should be
filled by the operator rather than preserved in the output.


## Binary ToMask Transformation: N in, N out
Binary to mask transformations are operations that take two input batches and produce a single output batch, where the output batch has the same number of values as the input batches, but the meaning of the values is changed to a mask.
As in TSL a mask is a semantic type, this type of transformation needs an
explicit mask-layout policy. The output may be native masks, integral masks,
packed bits, or byte/bool values. A selection vector should be modeled as a
separate row-id output shape. These transformations can
include:
- **Masking**: Creating a mask based on comparisons between values from two batches, such as marking values that are equal or greater than a threshold.

### Example-Operation
```cpp
struct greater_than_mask_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type value1, 
        typename tsl::reg_param<Vec>::type value2
    ) const {
        return tsl::greater_than<Vec>(value1, value2);
    }
};
```


## Binary Masked ToMask Transformation: N in, N out
Binary masked to mask transformations are operations that take two input batches and a mask and produce a single output batch, where the output batch has the same number of values as the input batches, but the meaning of the values is changed to a mask.
As in TSL a mask is a semantic type, this type of transformation needs an
explicit mask-layout policy. The helper must also define whether the output mask
contains only the operator predicate or the conjunction of input validity and
the operator predicate. These transformations can include:
- **Masking**: Creating a mask based on comparisons between values from two batches, such as marking values that are equal or greater than a threshold, but only for the values that are marked as valid in the input mask.

### Example-Operation
```cpp
struct greater_than_mask_masked_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename Vec::mask_type mask,
        typename tsl::reg_param<Vec>::type value1, 
        typename tsl::reg_param<Vec>::type value2
    ) const {
        const auto predicate = tsl::greater_than<Vec>(value1, value2);
        return tsl::mask_binary_and<Vec>(mask, predicate);
    }
};
```


## Binary Consumption: N in, 0 out
Binary consumption operations are operations that take two input batches and produce no output batch. These transformations can include:
- **Container Manipulation**: Performing operations that modify the state of a container or data structure based on the values in the input batches, such as inserting or deleting elements.

### Example-Operation
```cpp
template <class KeyVec, class ValueVec>
struct hashmap_insert_op {

    const typename KeyVec::register_type empty_bucket_identifier_ = 
        tsl::set1<KeyVec>(tsl::mask_lane_all_true<KeyVec::base_type>());
    const std::size_t lzc_bit_count = sizeof(std::size_t) * CHAR_BIT;
    const std::size_t lzc_irrelevant_bit_count  = lzc_bit_count - detail::lane_count<KeyVec>();


    typename KeyVec::base_type * keys_;
    typename ValueVec::base_type * values_;
    std::size_t hashmap_size_;

    constexpr hashmap_insert_op(
        typename KeyVec::base_type * keys, 
        typename ValueVec::base_type * values, 
        std::size_t hashmap_size
    ) : keys_(keys), values_(values), hashmap_size_(hashmap_size) {}

    void operator()(
        typename tsl::reg_param<KeyVec>::type keys, 
        typename tsl::reg_param<ValueVec>::type values
    ) {
        const typename KeyVec::register_type hashed_keys = my_hash_function(keys);
        const auto hashed_array = tsl::to_array<KeyVec>(hashed_keys);
        const auto key_array = tsl::to_array<KeyVec>(keys);
        const auto value_array = tsl::to_array<ValueVec>(values);
        
        for (std::size_t i = 0; i < detail::lane_count<KeyVec>(); ++i) {
            const auto current_key = tsl::set1<KeyVec>(key_array[i]);
            auto const original_bucket = hashed_array[i];
            bool wrapped_around = false;
            auto current_bucket = hashed_array[i];
            while (true) {
                const auto bucket_values = tsl::load<KeyVec, false>(keys_ + current_bucket);
                const auto current_key_lzc = tsl::lzc_imask<KeyVec>(
                    tsl::equal<KeyVec>(current_key, bucket_values)
                );
                if (current_key_lzc != lzc_bit_count) {
                    std::size_t const bucket_index = current_key_lzc - lzc_irrelevant_bit_count;
                    // found the key, update the value
                    values_[current_bucket+bucket_index] = value_array[i];
                    break;
                }
                const auto empty_bucket_lzc = tsl::lzc_imask<KeyVec>(
                    tsl::equal<KeyVec>(current_key, bucket_values)
                );
                if (empty_bucket_lzc != lzc_bit_count) {
                    std::size_t const bucket_index = empty_bucket_lzc - lzc_irrelevant_bit_count;
                    // found an empty bucket, insert the key-value pair
                    keys_[current_bucket+bucket_index] = key_array[i];
                    values_[current_bucket+bucket_index] = value_array[i];
                    break;
                }
                current_bucket = (current_bucket + detail::lane_count<KeyVec>()) % hashmap_size_; // Linear probing to the next bucket
                if (current_bucket < original_bucket) {
                    wrapped_around = true;
                }
                if ((current_bucket >= original_bucket) && wrapped_around) {
                    throw std::runtime_error("Hashmap is full, cannot insert new key-value pair.");
                }
            }
        }
    }   
}
```

Interestingly, the `hashmap_insert_op` operation demonstrates, that we may should distinguish between `VecIt` for loading and `VecProc` for processing. If so, we could express something like "iterate scalar over data, process vectorized" in a more elegant way like in the following snippet:
```cpp
template <typename KeyT, typename ValueT, typename ProcVec>
struct hashmap_insert_op {

    const typename ProcVec::register_type empty_bucket_identifier_ = 
        tsl::set1<ProcVec>(tsl::mask_lane_all_true<ProcVec::base_type>());
    const std::size_t lzc_bit_count = sizeof(std::size_t) * CHAR_BIT;
    const std::size_t lzc_irrelevant_bit_count  = lzc_bit_count - detail::lane_count<ProcVec>();


    KeyT * keys_;
    ValueT * values_;
    std::size_t hashmap_size_;

    constexpr hashmap_insert_op(
        KeyT * keys, 
        ValueT * values, 
        std::size_t hashmap_size
    ) : keys_(keys), values_(values), hashmap_size_(hashmap_size) {}

    // Gather + Linear Probing
    void operator()(
        const KeyT key, 
        const ValueT value
    ) {
        const auto hash = my_hash_function(key);
        
        const auto current_key = tsl::set1<ProcVec>(key);
        auto current_bucket = hash;
        bool wrapped_around = false;
        while (true) {
            const auto bucket_values = tsl::load<ProcVec, false>(keys_ + current_bucket);
            const auto current_key_lzc = tsl::lzc_imask<ProcVec>(
                tsl::equal<ProcVec>(current_key, bucket_values)
            );
            if (current_key_lzc != lzc_bit_count) {
                std::size_t bucket_index = current_key_lzc - lzc_irrelevant_bit_count;
                values_[current_bucket+bucket_index] = value;
                break;
            }
            const auto empty_bucket_lzc = tsl::lzc_imask<ProcVec>(
                tsl::equal<ProcVec>(current_key, bucket_values)
            );
            if (empty_bucket_lzc != lzc_bit_count) {
                std::size_t const bucket_index = empty_bucket_lzc - lzc_irrelevant_bit_count;
                // found an empty bucket, insert the key-value pair
                keys_[current_bucket+bucket_index] = key;
                values_[current_bucket+bucket_index] = value;
                break;
            }
            current_bucket = (current_bucket + detail::lane_count<ProcVec>()) % hashmap_size_; // Linear probing to the next bucket
            if (current_bucket < original_bucket) {
                wrapped_around = true;
            }
            if ((current_bucket >= original_bucket) && wrapped_around) {
                throw std::runtime_error("Hashmap is full, cannot insert new key-value pair.");
            }
        }
    }   
}
```
