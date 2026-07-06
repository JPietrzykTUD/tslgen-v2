use tsl::tsl_algorithm::VectorFor;
use tsl::tsl_core::StaticSimdVector;
use tsl::profile;

struct SumOp {
    total: i64,
}

impl<V> profile::algo::UnaryAggregateKernel<V> for SumOp
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::HaddImpl,
{
    type Output = i64;

    fn accumulate(&mut self, value: V::RegisterType) {
        self.total += i64::from(profile::hadd::<V>(value));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}

struct PairSumOp {
    total: i64,
}

impl<V> profile::algo::BinaryAggregateKernel<V> for PairSumOp
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::AddImpl
        + profile::detail::primitives::HaddImpl,
{
    type Output = i64;

    fn accumulate(&mut self, left: V::RegisterType, right: V::RegisterType) {
        let sum = profile::add::<V>(left, right);
        self.total += i64::from(profile::hadd::<V>(sum));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 13) % 61) as i32 - 30;
        *right_value = ((i * 17) % 67) as i32 - 33;
    }
}

fn expected_sum(input: &[i32]) -> i64 {
    input.iter().map(|value| i64::from(*value)).sum()
}

fn expected_pair_sum(left: &[i32], right: &[i32]) -> i64 {
    left.iter()
        .zip(right.iter())
        .map(|(left_value, right_value)| i64::from(*left_value) + i64::from(*right_value))
        .sum()
}

fn verify_reduction_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32> + Copy,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::Count_matchesImpl
        + profile::detail::primitives::HaddImpl
        + profile::detail::primitives::LoadImpl<false>,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let mut left = vec![0i32; count];
    let mut right = vec![0i32; count];
    fill_inputs(&mut left, &mut right);

    let values_for_sum = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(left.as_ptr())
    };
    let sum = profile::algo::hadd::<_, i32>(policy, values_for_sum);
    assert_eq!(i64::from(sum), expected_sum(&left));

    let values_for_count = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(left.as_ptr())
    };
    let matches = profile::algo::count_matches::<_, i32>(policy, values_for_count, left[0]);
    let expected_matches = left.iter().filter(|value| **value == left[0]).count() as i32;
    assert_eq!(matches, expected_matches);
}

fn verify_mask_reduction_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32> + Copy,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec:
        StaticSimdVector<BaseType = i32>
            + profile::detail::primitives::Less_thanImpl
            + profile::detail::primitives::LoadImpl<false>
            + profile::detail::primitives::Mask_population_countImpl,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let mut left = vec![0i32; count];
    let mut right = vec![0i32; count];
    fill_inputs(&mut left, &mut right);

    let left_values = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(left.as_ptr())
    };
    let right_values = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(right.as_ptr())
    };
    let mask = profile::algo::less_than::<_, i32>(policy, left_values, right_values);
    let count = profile::algo::mask_population_count::<_, i32>(policy, mask);
    let expected = left
        .iter()
        .zip(right.iter())
        .filter(|(left_value, right_value)| left_value < right_value)
        .count();
    assert_eq!(count, expected);
}

fn main() {
    verify_reduction_facade(tsl::dataparallel::fixed::<1>());
    verify_reduction_facade(tsl::dataparallel::generic::<4>());
    verify_mask_reduction_facade(tsl::dataparallel::fixed::<1>());
    verify_mask_reduction_facade(tsl::dataparallel::generic::<4>());

    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    let expected_unary = expected_sum(&left);
    let expected_binary = expected_pair_sum(&left, &right);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let mut unary = SumOp { total: 0 };
            let unary_result = profile::algo::aggregate_unary($policy, &mut unary, &left);
            assert_eq!(unary_result, expected_unary);

            let mut binary = PairSumOp { total: 0 };
            let binary_result = profile::algo::aggregate_binary($policy, &mut binary, &left, &right);
            assert_eq!(binary_result, expected_binary);
        }};
    }

    run_policy!(tsl::dataparallel::native());
    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
