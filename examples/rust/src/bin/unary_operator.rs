use tsl::tsl_algorithm::{RebindBase, ReboundBase, VectorFor};
use tsl::tsl_core::{SimdVector, StaticSimdVector};
use tsl::profile;

struct Square;

impl<V> profile::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector + profile::detail::primitives::MulImpl,
    V::RegisterType: Copy,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        profile::mul::<V>(value, value)
    }
}

fn verify(input: &[i32], output: &[i32]) {
    for (actual, value) in output.iter().zip(input.iter()) {
        assert_eq!(*actual, value * value);
    }
}

fn verify_register_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32> + Copy,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::MulImpl
        + profile::detail::primitives::LoadImpl<false>,
    <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as SimdVector>::RegisterType:
        profile::detail::primitives::StoreImplArg<
            <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
            false,
        >,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let input: Vec<i32> = (0..count).map(|value| value as i32 - 4).collect();
    let mut output = vec![0i32; count];

    let factor1 = unsafe { profile::algo::load::<_, i32, false>(policy, input.as_ptr()) };
    let factor2 = unsafe { profile::algo::load::<_, i32, false>(policy, input.as_ptr()) };
    let squared = profile::algo::mul::<_, i32>(policy, factor1, factor2);
    unsafe { profile::algo::store::<_, i32, false>(policy, output.as_mut_ptr(), squared) };

    verify(&input, &output);
}

fn verify_conversion_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32> + Copy,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec:
        StaticSimdVector<BaseType = i32> + RebindBase<u32> + profile::detail::primitives::LoadImpl<false>,
    ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>:
        StaticSimdVector<BaseType = u32>,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec:
        profile::detail::primitives::CastImpl<
            ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>,
        > + profile::detail::primitives::ReinterpretImpl<
            ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>,
        >,
    <ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32> as SimdVector>::RegisterType:
        profile::detail::primitives::StoreImplArg<
            ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>,
            false,
        >,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let input: Vec<i32> = (1..=count).map(|value| value as i32).collect();
    let mut cast_output = vec![0u32; count];
    let mut reinterpret_output = vec![0u32; count];

    let values_for_cast = unsafe { profile::algo::load::<_, i32, false>(policy, input.as_ptr()) };
    let casted = profile::algo::cast::<_, i32, u32>(policy, values_for_cast);
    unsafe {
        profile::store::<ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>, false, _>(
            cast_output.as_mut_ptr(),
            casted,
        )
    };

    let values_for_reinterpret =
        unsafe { profile::algo::load::<_, i32, false>(policy, input.as_ptr()) };
    let reinterpreted = profile::algo::reinterpret::<_, i32, u32>(policy, values_for_reinterpret);
    unsafe {
        profile::store::<ReboundBase<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, u32>, false, _>(
            reinterpret_output.as_mut_ptr(),
            reinterpreted,
        )
    };

    for (index, value) in input.iter().enumerate() {
        let expected = *value as u32;
        assert_eq!(cast_output[index], expected);
        assert_eq!(reinterpret_output[index], expected);
    }
}

fn main() {
    let scalar_square = profile::algo::mul::<_, i32>(tsl::dataparallel::fixed::<1>(), 7, 7);
    assert_eq!(scalar_square, 49);
    verify_register_facade(tsl::dataparallel::native());
    verify_register_facade(tsl::dataparallel::generic::<8>());
    verify_conversion_facade(tsl::dataparallel::fixed::<1>());
    verify_conversion_facade(tsl::dataparallel::generic::<8>());

    let input: Vec<i32> = (0..1000).map(|value| value - 500).collect();

    let mut native_output = vec![0i32; input.len()];
    let mut native = Square;
    profile::algo::transform_unary(
        tsl::dataparallel::native(),
        &mut native,
        &input,
        &mut native_output,
    );
    verify(&input, &native_output);

    let mut fixed_output = vec![0i32; input.len()];
    let mut fixed = Square;
    profile::algo::transform_unary(
        tsl::dataparallel::fixed::<1>(),
        &mut fixed,
        &input,
        &mut fixed_output,
    );
    verify(&input, &fixed_output);

    let mut generic_output = vec![0i32; input.len()];
    let mut generic = Square;
    profile::algo::transform_unary(
        tsl::dataparallel::generic::<8>(),
        &mut generic,
        &input,
        &mut generic_output,
    );
    verify(&input, &generic_output);
}
