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

impl<V> profile::algo::UnaryConsumeKernel<V> for SumOp
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::HaddImpl,
{
    fn consume(&mut self, value: V::RegisterType) {
        self.total += i64::from(profile::hadd::<V>(value));
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

impl<V> profile::algo::BinaryConsumeKernel<V> for PairSumOp
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

fn make_selection(count: usize) -> Vec<usize> {
    let mut indices = Vec::new();
    for row in (0..count).rev() {
        if row % 4 == 0 || row % 7 == 0 {
            indices.push(row);
        }
    }
    indices
}

fn expected_unary_sum(input: &[i32], indices: &[usize]) -> i64 {
    indices.iter().map(|&row| i64::from(input[row])).sum()
}

fn expected_binary_sum(left: &[i32], right: &[i32], indices: &[usize]) -> i64 {
    indices
        .iter()
        .map(|&row| i64::from(left[row]) + i64::from(right[row]))
        .sum()
}

fn main() {
    const COUNT: usize = 1003;

    let mut left = vec![0i32; COUNT];
    let mut right = vec![0i32; COUNT];
    fill_inputs(&mut left, &mut right);
    let indices = make_selection(COUNT);

    let expected_unary = expected_unary_sum(&left, &indices);
    let expected_binary = expected_binary_sum(&left, &right, &indices);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut unary_aggregate = SumOp { total: 0 };
            let unary_result =
                profile::algo::aggregate_selected_unary(policy, &mut unary_aggregate, &left, &indices);
            assert_eq!(unary_result, expected_unary);

            let mut binary_aggregate = PairSumOp { total: 0 };
            let binary_result = profile::algo::aggregate_selected_binary(
                policy,
                &mut binary_aggregate,
                &left,
                &right,
                &indices,
            );
            assert_eq!(binary_result, expected_binary);

            let mut unary_consume = SumOp { total: 0 };
            profile::algo::consume_selected_unary(policy, &mut unary_consume, &left, &indices);
            assert_eq!(unary_consume.total, expected_unary);

            let mut binary_consume = PairSumOp { total: 0 };
            profile::algo::consume_selected_binary(
                policy,
                &mut binary_consume,
                &left,
                &right,
                &indices,
            );
            assert_eq!(binary_consume.total, expected_binary);

            let mut scaled_binary = PairSumOp { total: 0 };
            let scaled_result = unsafe {
                profile::algo::aggregate_selected_binary_scaled_raw::<4, _, _, _>(
                    policy,
                    &mut scaled_binary,
                    left.as_ptr(),
                    right.as_ptr(),
                    indices.as_ptr(),
                    indices.len(),
                )
            };
            assert_eq!(scaled_result, expected_binary);
        }};
    }

    run_policy!(tsl::dataparallel::native());
    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
