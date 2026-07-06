use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

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

struct LessThan;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, right)
    }
}

fn fill_input(input: &mut [i32]) {
    for (i, value) in input.iter_mut().enumerate() {
        *value = ((i * 17) % 53) as i32 - 26;
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 17) % 53) as i32 - 26;
        *right_value = ((i * 11) % 47) as i32 - 23;
    }
}

fn verify_selected<F, G>(
    output: &[i32],
    produced: usize,
    count: usize,
    mut predicate: F,
    mut selected_value: G,
) where
    F: FnMut(usize) -> bool,
    G: FnMut(usize) -> i32,
{
    let mut expected_count = 0usize;
    for i in 0..count {
        if predicate(i) {
            assert_eq!(output[expected_count], selected_value(i));
            expected_count += 1;
        }
    }
    assert_eq!(produced, expected_count);
    for value in output.iter().take(count).skip(produced) {
        assert_eq!(*value, i32::MAX);
    }
}

fn main() {
    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut input = vec![0i32; 1000];
            fill_input(&mut input);
            let mut output = vec![i32::MAX; input.len()];
            let mut negative = Negative;
            let produced = tsl::algo::select_unary(policy, &mut negative, &input, &mut output);
            verify_selected(
                &output,
                produced,
                input.len(),
                |i| input[i] < 0,
                |i| input[i],
            );

            let mut left = vec![0i32; 1003];
            let mut right = vec![0i32; 1003];
            fill_inputs(&mut left, &mut right);
            output.resize(left.len(), i32::MAX);
            output.fill(i32::MAX);
            let mut less_than = LessThan;
            let produced =
                tsl::algo::select_binary(policy, &mut less_than, &left, &right, &mut output);
            verify_selected(
                &output,
                produced,
                left.len(),
                |i| left[i] < right[i],
                |i| left[i],
            );
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
