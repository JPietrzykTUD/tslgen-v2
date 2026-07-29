use tsl::profile;
use tsl::tsl_core::StaticSimdVector;

struct LessThan;

impl<V> profile::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(left, right)
    }
}

struct Negative;

impl<V> profile::algo::UnaryPredicateKernel<V> for Negative
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::Less_thanImpl
        + profile::detail::primitives::Set1Impl,
{
    fn test(&mut self, value: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(value, profile::set1::<V>(0))
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 17) % 61) as i32 - 30;
        *right_value = ((i * 11) % 43) as i32 - 21;
    }
}

fn verify_indices<F>(indices: &[usize], produced: usize, count: usize, mut predicate: F)
where
    F: FnMut(usize) -> bool,
{
    let mut expected_count = 0usize;
    for i in 0..count {
        if predicate(i) {
            assert_eq!(indices[expected_count], i);
            expected_count += 1;
        }
    }
    assert_eq!(produced, expected_count);
    for value in indices.iter().take(count).skip(produced) {
        assert_eq!(*value, usize::MAX);
    }
}

fn main() {
    let mut left = vec![0i32; 1003];
    let mut right = vec![0i32; 1003];
    fill_inputs(&mut left, &mut right);

    macro_rules! run_mask_layout {
        ($policy:expr, $layout:ty, $mask_count:expr, $init:expr) => {{
            let policy = $policy;
            let mask_count = $mask_count;
            let mut masks = vec![$init; mask_count];

            let mut less_than_for_mask = LessThan;
            let masks_produced = profile::algo::predicate_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut less_than_for_mask,
                &left,
                &right,
                &mut masks,
            );
            assert_eq!(masks_produced, masks.len());

            let mut indices = vec![usize::MAX; left.len()];
            let mut masked_negative = Negative;
            let produced = profile::algo::select_masked_indices_unary_mask_layout::<
                _,
                $layout,
                _,
                i32,
            >(policy, &mut masked_negative, &left, &masks, &mut indices);
            verify_indices(&indices, produced, left.len(), |i| {
                left[i] < right[i] && left[i] < 0
            });

            indices.fill(usize::MAX);
            let mut masked_less_than = LessThan;
            let produced =
                profile::algo::select_masked_indices_binary_mask_layout::<_, $layout, _, i32>(
                    policy,
                    &mut masked_less_than,
                    &left,
                    &right,
                    &masks,
                    &mut indices,
                );
            verify_indices(&indices, produced, left.len(), |i| left[i] < right[i]);
        }};
    }

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut indices = vec![usize::MAX; left.len()];
            let mut negative = Negative;
            let produced =
                profile::algo::select_indices_unary(policy, &mut negative, &left, &mut indices);
            verify_indices(&indices, produced, left.len(), |i| left[i] < 0);

            indices.fill(usize::MAX);
            let mut less_than = LessThan;
            let produced = profile::algo::select_indices_binary(
                policy,
                &mut less_than,
                &left,
                &right,
                &mut indices,
            );
            verify_indices(&indices, produced, left.len(), |i| left[i] < right[i]);

            run_mask_layout!(
                policy,
                profile::algo::mask_layout::Integral,
                profile::algo::integral_mask_chunk_count::<_, i32>(policy, left.len()),
                Default::default()
            );
            run_mask_layout!(
                policy,
                profile::algo::mask_layout::Native,
                profile::algo::native_mask_chunk_count::<_, i32>(policy, left.len()),
                Default::default()
            );
            run_mask_layout!(
                policy,
                profile::algo::mask_layout::Bytes,
                profile::algo::byte_mask_count::<_, i32>(policy, left.len()),
                0u8
            );
            run_mask_layout!(
                policy,
                profile::algo::mask_layout::Bits,
                profile::algo::bit_mask_count::<_, i32>(policy, left.len()),
                0xFFu8
            );
        }};
    }

    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
