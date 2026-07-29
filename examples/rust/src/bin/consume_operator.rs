use tsl::profile;
use tsl::tsl_core::StaticSimdVector;

struct SumSink {
    total: i64,
}

impl<V> profile::algo::UnaryConsumeKernel<V> for SumSink
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::HaddImpl,
{
    fn consume(&mut self, value: V::RegisterType) {
        self.total += i64::from(profile::hadd::<V>(value));
    }
}

struct PairSumSink {
    total: i64,
}

impl<V> profile::algo::BinaryConsumeKernel<V> for PairSumSink
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::AddImpl
        + profile::detail::primitives::HaddImpl,
{
    fn consume(&mut self, left: V::RegisterType, right: V::RegisterType) {
        let sum = profile::add::<V>(left, right);
        self.total += i64::from(profile::hadd::<V>(sum));
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 19) % 67) as i32 - 33;
        *right_value = ((i * 23) % 71) as i32 - 35;
    }
}

fn expected_unary_sum(input: &[i32]) -> i64 {
    input.iter().map(|value| i64::from(*value)).sum()
}

fn expected_binary_sum(left: &[i32], right: &[i32]) -> i64 {
    left.iter()
        .zip(right.iter())
        .map(|(left_value, right_value)| i64::from(*left_value) + i64::from(*right_value))
        .sum()
}

fn main() {
    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    let expected_unary = expected_unary_sum(&left);
    let expected_binary = expected_binary_sum(&left, &right);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let mut unary = SumSink { total: 0 };
            profile::algo::consume_unary($policy, &mut unary, &left);
            assert_eq!(unary.total, expected_unary);

            let mut binary = PairSumSink { total: 0 };
            profile::algo::consume_binary($policy, &mut binary, &left, &right);
            assert_eq!(binary.total, expected_binary);
        }};
    }

    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
