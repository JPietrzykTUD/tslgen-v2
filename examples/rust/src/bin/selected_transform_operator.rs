use tsl::tsl_core::StaticSimdVector;
use tsl::profile;

struct Square;

impl<V> profile::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        profile::mul::<V>(value, value)
    }
}

struct Add;

impl<V> profile::algo::BinaryKernel<V> for Add
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::AddImpl,
{
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType {
        profile::add::<V>(left, right)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 13) % 47) as i32 - 23;
        *right_value = ((i * 7) % 31) as i32 - 15;
    }
}

fn make_selection(count: usize) -> Vec<usize> {
    let mut indices = Vec::new();
    for row in (0..count).rev() {
        if row % 3 == 0 || row % 5 == 0 {
            indices.push(row);
        }
    }
    indices
}

fn verify_unary(left: &[i32], indices: &[usize], output: &[i32], sentinel: i32) {
    for (i, &row) in indices.iter().enumerate() {
        assert_eq!(output[i], left[row] * left[row]);
    }
    for value in output.iter().skip(indices.len()) {
        assert_eq!(*value, sentinel);
    }
}

fn verify_binary(left: &[i32], right: &[i32], indices: &[usize], output: &[i32], sentinel: i32) {
    for (i, &row) in indices.iter().enumerate() {
        assert_eq!(output[i], left[row] + right[row]);
    }
    for value in output.iter().skip(indices.len()) {
        assert_eq!(*value, sentinel);
    }
}

fn main() {
    const COUNT: usize = 1003;
    const SENTINEL: i32 = 7_654_321;

    let mut left = vec![0i32; COUNT];
    let mut right = vec![0i32; COUNT];
    fill_inputs(&mut left, &mut right);
    let indices = make_selection(COUNT);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut output = vec![SENTINEL; COUNT];
            let mut square = Square;
            profile::algo::transform_selected_unary(policy, &mut square, &left, &indices, &mut output);
            verify_unary(&left, &indices, &output, SENTINEL);

            output.fill(SENTINEL);
            let mut add = Add;
            profile::algo::transform_selected_binary(
                policy,
                &mut add,
                &left,
                &right,
                &indices,
                &mut output,
            );
            verify_binary(&left, &right, &indices, &output, SENTINEL);

            output.fill(SENTINEL);
            let mut scaled_square = Square;
            unsafe {
                profile::algo::transform_selected_unary_scaled_raw::<4, _, _, _>(
                    policy,
                    &mut scaled_square,
                    left.as_ptr(),
                    indices.as_ptr(),
                    output.as_mut_ptr(),
                    indices.len(),
                );
            }
            verify_unary(&left, &indices, &output, SENTINEL);
        }};
    }

    run_policy!(tsl::dataparallel::native());
    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
