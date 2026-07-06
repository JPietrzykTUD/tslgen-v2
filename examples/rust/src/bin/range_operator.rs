use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct Square;

impl<V> tsl::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        tsl::mul::<V>(value, value)
    }
}

struct Add;

impl<V> tsl::algo::BinaryKernel<V> for Add
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::AddImpl,
{
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType {
        tsl::add::<V>(left, right)
    }
}

struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}

struct Negative;

impl<V> tsl::algo::UnaryPredicateKernel<V> for Negative
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::Less_thanImpl
        + tsl::detail::primitives::Set1Impl,
{
    fn test(&mut self, value: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(value, tsl::set1::<V>(0))
    }
}

struct MaskedPairSum {
    total: i64,
}

impl<V> tsl::algo::MaskedBinaryAggregateKernel<V> for MaskedPairSum
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::AddImpl
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::HaddImpl
        + tsl::detail::primitives::Set1Impl,
{
    type Output = i64;

    fn accumulate(&mut self, active: V::MaskType, left: V::RegisterType, right: V::RegisterType) {
        let zero = tsl::set1::<V>(0);
        let sum = tsl::add::<V>(left, right);
        let selected = tsl::blend::<V>(active, zero, sum);
        self.total += i64::from(tsl::hadd::<V>(selected));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}

struct MaskedSumSink {
    total: i64,
}

impl<V> tsl::algo::MaskedUnaryConsumeKernel<V> for MaskedSumSink
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::HaddImpl
        + tsl::detail::primitives::Set1Impl,
{
    fn consume(&mut self, active: V::MaskType, value: V::RegisterType) {
        let zero = tsl::set1::<V>(0);
        let selected = tsl::blend::<V>(active, zero, value);
        self.total += i64::from(tsl::hadd::<V>(selected));
    }
}

struct ChunkSum {
    base: *const i32,
    total: i64,
    visited: usize,
    metadata_ok: bool,
}

impl ChunkSum {
    fn new(input: &[i32]) -> Self {
        Self {
            base: input.as_ptr(),
            total: 0,
            visited: 0,
            metadata_ok: true,
        }
    }
}

impl<V> tsl::algo::ChunkKernel<V> for ChunkSum
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::LoadImpl<false>
        + tsl::detail::primitives::HaddImpl,
{
    unsafe fn apply(&mut self, ptr: *const V::BaseType, offset: usize, count: usize) {
        let expected_ptr = unsafe { self.base.add(offset) };
        if ptr != expected_ptr || count != V::ELEMENT_COUNT {
            self.metadata_ok = false;
        }

        let values = unsafe { tsl::load::<V, false>(ptr) };
        self.total += i64::from(tsl::hadd::<V>(values));
        self.visited += count;
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 31) % 79) as i32 - 39;
        *right_value = ((i * 17) % 61) as i32 - 30;
    }
}

fn sum_values(values: &[i32]) -> i64 {
    values.iter().map(|value| i64::from(*value)).sum()
}

fn expected_masked_pair_sum(left: &[i32], right: &[i32]) -> i64 {
    left.iter()
        .zip(right)
        .filter_map(|(&left_value, &right_value)| {
            (left_value < right_value).then_some(i64::from(left_value) + i64::from(right_value))
        })
        .sum()
}

fn main() {
    let count = 1003usize;
    let mut left = vec![0i32; count];
    let mut right = vec![0i32; count];
    let mut output = vec![0i32; count];
    let mut selected = vec![i32::MAX; count];
    fill_inputs(&mut left, &mut right);

    let policy = tsl::algo::parallelism::generic::<4>();

    let mut square = Square;
    tsl::algo::transform_unary(policy, &mut square, &left, &mut output);
    for (actual, input) in output.iter().zip(left.iter()) {
        assert_eq!(*actual, *input * *input);
    }

    let mut add = Add;
    tsl::algo::transform_binary(policy, &mut add, &left, &right, &mut output);
    for ((actual, left_value), right_value) in output.iter().zip(left.iter()).zip(right.iter()) {
        assert_eq!(*actual, *left_value + *right_value);
    }

    let mask_count = tsl::algo::integral_mask_chunk_count::<_, i32>(policy, count);
    let mut masks = vec![0u64; mask_count];
    let mut less_than = LessThan;
    let produced_masks =
        tsl::algo::predicate_binary(policy, &mut less_than, &left, &right, &mut masks);
    assert_eq!(produced_masks, masks.len());

    let mut negative = Negative;
    let produced =
        tsl::algo::select_masked_unary(policy, &mut negative, &left, &masks, &mut selected);
    let mut expected_selected = 0usize;
    for i in 0..count {
        if left[i] < right[i] && left[i] < 0 {
            assert_eq!(selected[expected_selected], left[i]);
            expected_selected += 1;
        }
    }
    assert_eq!(produced, expected_selected);
    for value in selected.iter().skip(produced) {
        assert_eq!(*value, i32::MAX);
    }

    let mut aggregate = MaskedPairSum { total: 0 };
    let aggregate_result =
        tsl::algo::aggregate_masked_binary(policy, &mut aggregate, &left, &right, &masks);
    assert_eq!(aggregate_result, expected_masked_pair_sum(&left, &right));

    let mut sink = MaskedSumSink { total: 0 };
    tsl::algo::consume_masked_unary(policy, &mut sink, &left, &masks);
    let expected_sink: i64 = left
        .iter()
        .zip(right.iter())
        .filter_map(|(&left_value, &right_value)| {
            (left_value < right_value).then_some(i64::from(left_value))
        })
        .sum();
    assert_eq!(sink.total, expected_sink);

    let mut chunk_sum = ChunkSum::new(&left);
    tsl::algo::for_each_chunk(policy, &mut chunk_sum, &left);
    assert!(chunk_sum.metadata_ok);
    assert_eq!(chunk_sum.visited, left.len());
    assert_eq!(chunk_sum.total, sum_values(&left));
}
