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

struct SquareWhere;

impl<V> tsl::algo::MaskedUnaryKernel<V> for SquareWhere
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, _active: V::MaskType, value: V::RegisterType) -> V::RegisterType {
        tsl::mul::<V>(value, value)
    }
}

struct AddWhere;

impl<V> tsl::algo::MaskedBinaryKernel<V> for AddWhere
where
    V: StaticSimdVector<BaseType = i32> + tsl::detail::primitives::AddImpl,
{
    fn apply(
        &mut self,
        _active: V::MaskType,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType {
        tsl::add::<V>(left, right)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = (i % 31) as i32 - 15;
        *right_value = ((i * 7) % 43) as i32 - 21;
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

            let unary_preserved = -123456;
            let mut unary_output = vec![unary_preserved; left.len()];
            let mut square = SquareWhere;
            tsl::algo::transform_where_unary(policy, &mut square, &left, &masks, &mut unary_output);

            for (i, actual) in unary_output.iter().enumerate() {
                let expected = if left[i] < right[i] {
                    left[i] * left[i]
                } else {
                    unary_preserved
                };
                assert_eq!(*actual, expected);
            }

            let binary_preserved = -654321;
            let mut binary_output = vec![binary_preserved; left.len()];
            let mut add = AddWhere;
            tsl::algo::transform_where_binary(
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
                    binary_preserved
                };
                assert_eq!(*actual, expected);
            }
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
