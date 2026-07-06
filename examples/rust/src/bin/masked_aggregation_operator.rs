use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}

struct MaskedSumOp {
    total: i64,
}

impl<V> tsl::algo::MaskedUnaryAggregateKernel<V> for MaskedSumOp
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::HaddImpl
        + tsl::detail::primitives::Set1Impl,
{
    type Output = i64;

    fn accumulate(&mut self, active: V::MaskType, value: V::RegisterType) {
        let zero = tsl::set1::<V>(0);
        let selected = tsl::blend::<V>(active, zero, value);
        self.total += i64::from(tsl::hadd::<V>(selected));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}

struct MaskedPairSumOp {
    total: i64,
}

impl<V> tsl::algo::MaskedBinaryAggregateKernel<V> for MaskedPairSumOp
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

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 7) % 41) as i32 - 20;
        *right_value = ((i * 13) % 59) as i32 - 29;
    }
}

fn expected_masked_sum(left: &[i32], right: &[i32]) -> i64 {
    left.iter()
        .zip(right)
        .filter_map(|(&left_value, &right_value)| {
            (left_value < right_value).then_some(i64::from(left_value))
        })
        .sum()
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
    let mut left = vec![0i32; 1003];
    let mut right = vec![0i32; 1003];
    fill_inputs(&mut left, &mut right);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;
            let mask_count = tsl::algo::integral_mask_chunk_count::<_, i32>(policy, left.len());
            let mut masks = vec![0u64; mask_count];
            let mut less_than = LessThan;
            let produced =
                tsl::algo::predicate_binary(policy, &mut less_than, &left, &right, &mut masks);
            assert_eq!(produced, masks.len());

            let mut unary = MaskedSumOp { total: 0 };
            let unary_result = tsl::algo::aggregate_masked_unary(policy, &mut unary, &left, &masks);
            assert_eq!(unary_result, expected_masked_sum(&left, &right));

            let mut binary = MaskedPairSumOp { total: 0 };
            let binary_result =
                tsl::algo::aggregate_masked_binary(policy, &mut binary, &left, &right, &masks);
            assert_eq!(binary_result, expected_masked_pair_sum(&left, &right));
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
