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

struct LeftNegative;

impl<V> profile::algo::BinaryPredicateKernel<V> for LeftNegative
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::Less_thanImpl
        + profile::detail::primitives::Set1Impl,
{
    fn test(&mut self, left: V::RegisterType, _right: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(left, profile::set1::<V>(0))
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 23) % 71) as i32 - 35;
        *right_value = ((i * 13) % 53) as i32 - 26;
    }
}

fn make_selection(count: usize) -> Vec<usize> {
    let mut indices = Vec::new();
    for row in (0..count).rev() {
        if row % 3 == 0 || row % 11 == 0 {
            indices.push(row);
        }
    }
    indices
}

fn expected_count<F>(count: usize, mut predicate: F) -> usize
where
    F: FnMut(usize) -> bool,
{
    (0..count).filter(|&i| predicate(i)).count()
}

fn expected_selected_count<F>(indices: &[usize], mut predicate: F) -> usize
where
    F: FnMut(usize) -> bool,
{
    indices.iter().filter(|&&i| predicate(i)).count()
}

fn main() {
    let mut left = vec![0i32; 1003];
    let mut right = vec![0i32; 1003];
    fill_inputs(&mut left, &mut right);

    let indices = make_selection(left.len());
    let expected_unary = expected_count(left.len(), |i| left[i] < 0);
    let expected_binary = expected_count(left.len(), |i| left[i] < right[i]);
    let expected_masked = expected_count(left.len(), |i| left[i] < right[i] && left[i] < 0);
    let expected_selected_unary = expected_selected_count(&indices, |i| left[i] < 0);
    let expected_selected_binary = expected_selected_count(&indices, |i| left[i] < right[i]);

    macro_rules! run_mask_layout {
        ($policy:expr, $layout:ty, $mask_count:expr, $init:expr) => {{
            let policy = $policy;
            let mask_count = $mask_count;
            let mut masks = vec![$init; mask_count];

            let mut less_than_for_mask = LessThan;
            let produced = profile::algo::predicate_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut less_than_for_mask,
                &left,
                &right,
                &mut masks,
            );
            assert_eq!(produced, masks.len());

            let mut masked_negative = Negative;
            let masked_unary = profile::algo::count_masked_unary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut masked_negative,
                &left,
                &masks,
            );
            assert_eq!(masked_unary, expected_masked);

            let mut masked_left_negative = LeftNegative;
            let masked_binary = profile::algo::count_masked_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut masked_left_negative,
                &left,
                &right,
                &masks,
            );
            assert_eq!(masked_binary, expected_masked);
        }};
    }

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut negative = Negative;
            let unary = profile::algo::count_unary(policy, &mut negative, &left);
            assert_eq!(unary, expected_unary);

            let mut less_than = LessThan;
            let binary = profile::algo::count_binary(policy, &mut less_than, &left, &right);
            assert_eq!(binary, expected_binary);

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

            let mut selected_negative = Negative;
            let selected_unary =
                profile::algo::count_selected_unary(policy, &mut selected_negative, &left, &indices);
            assert_eq!(selected_unary, expected_selected_unary);

            let mut selected_less_than = LessThan;
            let selected_binary = profile::algo::count_selected_binary(
                policy,
                &mut selected_less_than,
                &left,
                &right,
                &indices,
            );
            assert_eq!(selected_binary, expected_selected_binary);

            let mut scaled_less_than = LessThan;
            let scaled_selected_binary = unsafe {
                profile::algo::count_selected_binary_scaled_raw::<4, _, _, i32>(
                    policy,
                    &mut scaled_less_than,
                    left.as_ptr(),
                    right.as_ptr(),
                    indices.as_ptr(),
                    indices.len(),
                )
            };
            assert_eq!(scaled_selected_binary, expected_selected_binary);
        }};
    }

    run_policy!(tsl::dataparallel::native());
    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
