use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct Square;

impl<V> tsl::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        tsl::mul::<V>(value, value)
    }
}

fn verify(input: &[i32], output: &[i32]) {
    for (actual, value) in output.iter().zip(input.iter()) {
        assert_eq!(*actual, value * value);
    }
}

fn main() {
    let input: Vec<i32> = (0..1000).map(|value| value - 500).collect();

    let mut native_output = vec![0i32; input.len()];
    let mut native = Square;
    tsl::algo::transform_unary(
        tsl::algo::parallelism::native(),
        &mut native,
        &input,
        &mut native_output,
    );
    verify(&input, &native_output);

    let mut fixed_output = vec![0i32; input.len()];
    let mut fixed = Square;
    tsl::algo::transform_unary(
        tsl::algo::parallelism::fixed::<1>(),
        &mut fixed,
        &input,
        &mut fixed_output,
    );
    verify(&input, &fixed_output);

    let mut generic_output = vec![0i32; input.len()];
    let mut generic = Square;
    tsl::algo::transform_unary(
        tsl::algo::parallelism::generic::<8>(),
        &mut generic,
        &input,
        &mut generic_output,
    );
    verify(&input, &generic_output);
}
