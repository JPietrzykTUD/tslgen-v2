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

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = (i % 41) as i32 - 20;
        *right_value = ((i * 5) % 37) as i32 - 18;
    }
}

fn mask_lane_is_set(mask: u64, lane: usize) -> bool {
    ((mask >> lane) & 1) != 0
}

fn verify_masks<F>(masks: &[u64], lanes: usize, count: usize, mut expected: F)
where
    F: FnMut(usize) -> bool,
{
    for i in 0..count {
        let chunk = i / lanes;
        let lane = i % lanes;
        assert_eq!(mask_lane_is_set(masks[chunk], lane), expected(i));
    }
}

fn main() {
    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    macro_rules! run_policy {
        ($policy:expr, $lanes:expr) => {{
            let policy = $policy;
            let mask_count = tsl::algo::integral_mask_chunk_count::<_, i32>(policy, left.len());

            let mut unary_masks = vec![0u64; mask_count];
            let mut negative = Negative;
            let produced =
                tsl::algo::predicate_unary(policy, &mut negative, &left, &mut unary_masks);
            assert_eq!(produced, unary_masks.len());
            verify_masks(&unary_masks, $lanes, left.len(), |i| left[i] < 0);

            let mut binary_masks = vec![0u64; mask_count];
            let mut less_than = LessThan;
            let produced = tsl::algo::predicate_binary(
                policy,
                &mut less_than,
                &left,
                &right,
                &mut binary_masks,
            );
            assert_eq!(produced, binary_masks.len());
            verify_masks(&binary_masks, $lanes, left.len(), |i| left[i] < right[i]);
        }};
    }

    run_policy!(tsl::algo::parallelism::native(), 1);
    run_policy!(tsl::algo::parallelism::fixed::<1>(), 1);
    run_policy!(tsl::algo::parallelism::generic::<4>(), 4);
    run_policy!(tsl::algo::parallelism::generic::<16>(), 16);
}
