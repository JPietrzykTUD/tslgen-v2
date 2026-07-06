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

struct LeftNegative;

impl<V> tsl::algo::BinaryPredicateKernel<V> for LeftNegative
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::Less_thanImpl
        + tsl::detail::primitives::Set1Impl,
{
    fn test(&mut self, left: V::RegisterType, _right: V::RegisterType) -> V::MaskType {
        tsl::less_than::<V>(left, tsl::set1::<V>(0))
    }
}

fn fill_inputs(input: &mut [i32], threshold: &mut [i32]) {
    for (i, (input_value, threshold_value)) in
        input.iter_mut().zip(threshold.iter_mut()).enumerate()
    {
        *input_value = ((i * 17) % 61) as i32 - 30;
        *threshold_value = ((i * 11) % 43) as i32 - 21;
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
    let mut input = vec![0i32; 1003];
    let mut threshold = vec![0i32; 1003];
    fill_inputs(&mut input, &mut threshold);

    macro_rules! run_layout {
        ($policy:expr, $layout:ty, $mask_count:expr, $init:expr) => {{
            let policy = $policy;
            let mask_count = $mask_count;
            let mut masks = vec![$init; mask_count];

            let mut less_than_for_mask = LessThan;
            let masks_produced = tsl::algo::predicate_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut less_than_for_mask,
                &input,
                &threshold,
                &mut masks,
            );
            assert_eq!(masks_produced, masks.len());

            let mut output = vec![i32::MAX; input.len()];
            let mut negative = Negative;
            let produced = tsl::algo::select_masked_unary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut negative,
                &input,
                &masks,
                &mut output,
            );
            verify_selected(
                &output,
                produced,
                input.len(),
                |i| input[i] < threshold[i] && input[i] < 0,
                |i| input[i],
            );

            let mut left_negative_for_mask = LeftNegative;
            let masks_produced = tsl::algo::predicate_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut left_negative_for_mask,
                &input,
                &threshold,
                &mut masks,
            );
            assert_eq!(masks_produced, masks.len());

            output.fill(i32::MAX);
            let mut less_than = LessThan;
            let produced = tsl::algo::select_masked_binary_mask_layout::<_, $layout, _, i32>(
                policy,
                &mut less_than,
                &input,
                &threshold,
                &masks,
                &mut output,
            );
            verify_selected(
                &output,
                produced,
                input.len(),
                |i| input[i] < 0 && input[i] < threshold[i],
                |i| input[i],
            );
        }};
    }

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;
            run_layout!(
                policy,
                tsl::algo::mask_layout::Integral,
                tsl::algo::integral_mask_chunk_count::<_, i32>(policy, input.len()),
                Default::default()
            );
            run_layout!(
                policy,
                tsl::algo::mask_layout::Native,
                tsl::algo::native_mask_chunk_count::<_, i32>(policy, input.len()),
                Default::default()
            );
            run_layout!(
                policy,
                tsl::algo::mask_layout::Bytes,
                tsl::algo::byte_mask_count::<_, i32>(policy, input.len()),
                0u8
            );
            run_layout!(
                policy,
                tsl::algo::mask_layout::Bits,
                tsl::algo::bit_mask_count::<_, i32>(policy, input.len()),
                0xFFu8
            );
        }};
    }

    run_policy!(tsl::algo::parallelism::native());
    run_policy!(tsl::algo::parallelism::fixed::<1>());
    run_policy!(tsl::algo::parallelism::generic::<4>());
    run_policy!(tsl::algo::parallelism::generic::<16>());
}
