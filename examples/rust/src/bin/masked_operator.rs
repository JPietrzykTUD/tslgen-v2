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

struct SquareOrOriginal;

impl<V> tsl::algo::MaskedUnaryKernel<V> for SquareOrOriginal
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::BlendImpl
        + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, active: V::MaskType, value: V::RegisterType) -> V::RegisterType {
        let squared = tsl::mul::<V>(value, value);
        tsl::blend::<V>(active, value, squared)
    }
}

struct AddOrLeft;

impl<V> tsl::algo::MaskedBinaryKernel<V> for AddOrLeft
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::AddImpl
        + tsl::detail::primitives::BlendImpl,
    V::RegisterType: Copy,
{
    fn apply(
        &mut self,
        active: V::MaskType,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType {
        let sum = tsl::add::<V>(left, right);
        tsl::blend::<V>(active, left, sum)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = (i % 29) as i32 - 14;
        *right_value = ((i * 11) % 47) as i32 - 23;
    }
}

fn main() {
    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
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

            let unary_sentinel = -777777;
            let mut unary_output = vec![unary_sentinel; left.len()];
            let mut square = SquareOrOriginal;
            tsl::algo::transform_masked_unary(
                policy,
                &mut square,
                &left,
                &masks,
                &mut unary_output,
            );

            for (i, actual) in unary_output.iter().enumerate() {
                let expected = if left[i] < right[i] {
                    left[i] * left[i]
                } else {
                    left[i]
                };
                assert_eq!(*actual, expected);
                assert_ne!(*actual, unary_sentinel);
            }

            let binary_sentinel = -888888;
            let mut binary_output = vec![binary_sentinel; left.len()];
            let mut add = AddOrLeft;
            tsl::algo::transform_masked_binary(
                policy,
                &mut add,
                &left,
                &right,
                &masks,
                &mut binary_output,
            );

            for (i, actual) in binary_output.iter().enumerate() {
                let expected = if left[i] < right[i] {
                    left[i] + right[i]
                } else {
                    left[i]
                };
                assert_eq!(*actual, expected);
                assert_ne!(*actual, binary_sentinel);
            }
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
