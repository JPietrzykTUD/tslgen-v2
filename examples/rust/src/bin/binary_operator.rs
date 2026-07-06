use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct Add;

impl<V> tsl::algo::BinaryKernel<V> for Add
where
    V: StaticSimdVector + tsl::detail::primitives::AddImpl,
{
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType {
        tsl::add::<V>(left, right)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = (i % 37) as i32 - 18;
        *right_value = ((i * 3) % 29) as i32 - 14;
    }
}

fn verify(left: &[i32], right: &[i32], output: &[i32]) {
    for ((actual, left_value), right_value) in output.iter().zip(left.iter()).zip(right.iter()) {
        assert_eq!(*actual, *left_value + *right_value);
    }
}

fn main() {
    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    let mut native_output = vec![0i32; left.len()];
    let mut native = Add;
    tsl::algo::transform_binary(
        tsl::algo::parallelism::native(),
        &mut native,
        &left,
        &right,
        &mut native_output,
    );
    verify(&left, &right, &native_output);

    let mut fixed_output = vec![0i32; left.len()];
    let mut fixed = Add;
    tsl::algo::transform_binary(
        tsl::algo::parallelism::fixed::<1>(),
        &mut fixed,
        &left,
        &right,
        &mut fixed_output,
    );
    verify(&left, &right, &fixed_output);

    let mut generic_output = vec![0i32; left.len()];
    let mut generic = Add;
    tsl::algo::transform_binary(
        tsl::algo::parallelism::generic::<8>(),
        &mut generic,
        &left,
        &right,
        &mut generic_output,
    );
    verify(&left, &right, &generic_output);
}
