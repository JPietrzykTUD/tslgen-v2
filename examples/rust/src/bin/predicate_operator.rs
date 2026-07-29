use tsl::profile;
use tsl::tsl_algorithm::{IntegralMask, VectorFor};
use tsl::tsl_core::{SimdVector, StaticSimdVector};

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

fn verify_unequal_zero_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32>,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec:
        StaticSimdVector<BaseType = i32>
            + profile::detail::primitives::Unequal_zeroImpl
            + profile::detail::primitives::LoadImpl<false>,
    profile::algo::Profile: IntegralMask<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec>,
    <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as SimdVector>::ImaskType: Into<u64>,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let input: Vec<i32> = (0..count).map(|value| value as i32 - 2).collect();

    let values = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(
            input.as_ptr(),
        )
    };
    let mask = profile::algo::unequal_zero::<_, i32>(policy, values);
    let bits: u64 = <profile::algo::Profile as IntegralMask<
        <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
    >>::to_integral(mask)
    .into();

    for (lane, value) in input.iter().enumerate() {
        assert_eq!(mask_lane_is_set(bits, lane), *value != 0);
    }
}

fn verify_less_than_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32> + Copy,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec:
        StaticSimdVector<BaseType = i32>
            + profile::detail::primitives::Less_thanImpl
            + profile::detail::primitives::Mask_trueImpl
            + profile::detail::primitives::Mask_binary_andImpl
            + profile::detail::primitives::Mask_binary_notImpl
            + profile::detail::primitives::LoadImpl<false>,
    profile::algo::Profile: IntegralMask<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec>,
    <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as SimdVector>::ImaskType: Into<u64>,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let mut left = vec![0i32; count];
    let mut right = vec![0i32; count];
    fill_inputs(&mut left, &mut right);

    let left_values = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(
            left.as_ptr(),
        )
    };
    let right_values = unsafe {
        profile::load::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false>(
            right.as_ptr(),
        )
    };
    let mask = profile::algo::less_than::<_, i32>(policy, left_values, right_values);
    let all = profile::algo::mask_true::<_, i32>(policy);
    let active = profile::algo::mask_binary_and::<_, i32>(policy, all, mask);
    let inactive = profile::algo::mask_binary_not::<_, i32>(policy, active);
    let all_bits: u64 = <profile::algo::Profile as IntegralMask<
        <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
    >>::to_integral(all)
    .into();
    let active_bits: u64 = <profile::algo::Profile as IntegralMask<
        <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
    >>::to_integral(active)
    .into();
    let inactive_bits: u64 = <profile::algo::Profile as IntegralMask<
        <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
    >>::to_integral(inactive)
    .into();

    for lane in 0..count {
        let expected = left[lane] < right[lane];
        assert!(mask_lane_is_set(all_bits, lane));
        assert_eq!(mask_lane_is_set(active_bits, lane), expected);
        assert_eq!(mask_lane_is_set(inactive_bits, lane), !expected);
    }
}

fn main() {
    verify_unequal_zero_facade(tsl::dataparallel::fixed::<1>());
    verify_unequal_zero_facade(tsl::dataparallel::generic::<4>());
    verify_less_than_facade(tsl::dataparallel::fixed::<1>());
    verify_less_than_facade(tsl::dataparallel::generic::<4>());

    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    macro_rules! run_policy {
        ($policy:expr, $lanes:expr) => {{
            let policy = $policy;
            let mask_count = profile::algo::integral_mask_chunk_count::<_, i32>(policy, left.len());

            let mut unary_masks = vec![0u64; mask_count];
            let mut negative = Negative;
            let produced =
                profile::algo::predicate_unary(policy, &mut negative, &left, &mut unary_masks);
            assert_eq!(produced, unary_masks.len());
            verify_masks(&unary_masks, $lanes, left.len(), |i| left[i] < 0);

            let mut binary_masks = vec![0u64; mask_count];
            let mut less_than = LessThan;
            let produced = profile::algo::predicate_binary(
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

    run_policy!(tsl::dataparallel::fixed::<1>(), 1);
    run_policy!(tsl::dataparallel::generic::<4>(), 4);
    run_policy!(tsl::dataparallel::generic::<16>(), 16);
}
