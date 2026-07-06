use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct SumOp {
    total: i64,
}

impl<V> tsl::algo::UnaryAggregateKernel<V> for SumOp
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::HaddImpl,
{
    type Output = i64;

    fn accumulate(&mut self, value: V::RegisterType) {
        self.total += i64::from(tsl::hadd::<V>(value));
    }

    fn finalize(&self) -> Self::Output {
        self.total
    }
}

struct PairSumOp {
    total: i64,
}

impl<V> tsl::algo::BinaryAggregateKernel<V> for PairSumOp
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::AddImpl
        + tsl::detail::primitives::HaddImpl,
{
    type Output = i64;

    fn accumulate(&mut self, left: V::RegisterType, right: V::RegisterType) {
        let sum = tsl::add::<V>(left, right);
        self.total += i64::from(tsl::hadd::<V>(sum));
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

fn main() {
    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    let expected_unary = expected_sum(&left);
    let expected_binary = expected_pair_sum(&left, &right);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let mut unary = SumOp { total: 0 };
            let unary_result = tsl::algo::aggregate_unary($policy, &mut unary, &left);
            assert_eq!(unary_result, expected_unary);

            let mut binary = PairSumOp { total: 0 };
            let binary_result = tsl::algo::aggregate_binary($policy, &mut binary, &left, &right);
            assert_eq!(binary_result, expected_binary);
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
