use tsl::tsl_core::StaticSimdVector;
use tsl::profile;

struct LessThan;

impl<V> profile::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(left, right)
    }
}

struct SquareWhere;

impl<V> profile::algo::MaskedUnaryKernel<V> for SquareWhere
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, _active: V::MaskType, value: V::RegisterType) -> V::RegisterType {
        profile::mul::<V>(value, value)
    }
}

struct AddOrLeft;

impl<V> profile::algo::MaskedBinaryKernel<V> for AddOrLeft
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::AddImpl
        + profile::detail::primitives::BlendImpl,
    V::RegisterType: Copy,
{
    fn apply(
        &mut self,
        active: V::MaskType,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType {
        let sum = profile::add::<V>(left, right);
        profile::blend::<V>(active, left, sum)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 7) % 41) as i32 - 20;
        *right_value = ((i * 11) % 47) as i32 - 23;
    }
}

fn main() {
    const COUNT: usize = 1003;

    let mut left = vec![0i32; COUNT];
    let mut right = vec![0i32; COUNT];
    fill_inputs(&mut left, &mut right);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;
            let mask_count = profile::algo::native_mask_chunk_count::<_, i32>(policy, left.len());
            let mut masks = vec![Default::default(); mask_count];

            let mut predicate = LessThan;
            let produced = profile::algo::predicate_binary_mask_layout::<
                _,
                profile::algo::mask_layout::Native,
                _,
                i32,
            >(policy, &mut predicate, &left, &right, &mut masks);
            assert_eq!(produced, masks.len());

            let preserved = -345678;
            let mut unary_output = vec![preserved; left.len()];
            let mut square = SquareWhere;
            profile::algo::transform_where_unary_mask_layout::<
                _,
                profile::algo::mask_layout::Native,
                _,
                i32,
            >(policy, &mut square, &left, &masks, &mut unary_output);

            for (i, actual) in unary_output.iter().enumerate() {
                let expected = if left[i] < right[i] {
                    left[i] * left[i]
                } else {
                    preserved
                };
                assert_eq!(*actual, expected);
            }

            let mut binary_output = vec![0i32; left.len()];
            let mut add = AddOrLeft;
            profile::algo::transform_masked_binary_mask_layout::<
                _,
                profile::algo::mask_layout::Native,
                _,
                i32,
            >(policy, &mut add, &left, &right, &masks, &mut binary_output);

            for (i, actual) in binary_output.iter().enumerate() {
                let expected = if left[i] < right[i] {
                    left[i] + right[i]
                } else {
                    left[i]
                };
                assert_eq!(*actual, expected);
            }
        }};
    }

    run_policy!(tsl::dataparallel::native());
    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
