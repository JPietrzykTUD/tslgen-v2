use tsl::profile;
use tsl::tsl_algorithm::VectorFor;
use tsl::tsl_core::{SimdVector, StaticSimdVector};

struct Add;

impl<V> profile::algo::BinaryKernel<V> for Add
where
    V: StaticSimdVector + profile::detail::primitives::AddImpl,
{
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType {
        profile::add::<V>(left, right)
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = (i % 37) as i32 - 18;
        *right_value = ((i * 3) % 29) as i32 - 14;
    }
}

fn verify(left: &[i32], right: &[i32], output: &[i32]) {
    for ((actual, left_value), right_value) in output.iter().zip(left.iter()).zip(right.iter()) {
        assert_eq!(*actual, *left_value + *right_value);
    }
}

fn verify_register_facade<Policy>(policy: Policy)
where
    Policy: VectorFor<profile::algo::Profile, i32>,
    <Policy as VectorFor<profile::algo::Profile, i32>>::Vec: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::AddImpl
        + profile::detail::primitives::LoadImpl<false>,
    <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as SimdVector>::RegisterType:
        profile::detail::primitives::StoreImplArg<
            <Policy as VectorFor<profile::algo::Profile, i32>>::Vec,
            false,
        >,
{
    let count =
        <<Policy as VectorFor<profile::algo::Profile, i32>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    let mut left = vec![0i32; count];
    let mut right = vec![0i32; count];
    let mut output = vec![0i32; count];
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
    let sum = profile::algo::add::<_, i32>(policy, left_values, right_values);
    unsafe {
        profile::store::<<Policy as VectorFor<profile::algo::Profile, i32>>::Vec, false, _>(
            output.as_mut_ptr(),
            sum,
        )
    };

    verify(&left, &right, &output);
}

fn main() {
    let scalar_sum = profile::algo::add::<_, i32>(tsl::dataparallel::fixed::<1>(), 11, 31);
    assert_eq!(scalar_sum, 42);
    verify_register_facade(tsl::dataparallel::generic::<8>());

    let mut left = vec![0i32; 1000];
    let mut right = vec![0i32; 1000];
    fill_inputs(&mut left, &mut right);

    let mut fixed_output = vec![0i32; left.len()];
    let mut fixed = Add;
    profile::algo::transform_binary(
        tsl::dataparallel::fixed::<1>(),
        &mut fixed,
        &left,
        &right,
        &mut fixed_output,
    );
    verify(&left, &right, &fixed_output);

    let mut generic_output = vec![0i32; left.len()];
    let mut generic = Add;
    profile::algo::transform_binary(
        tsl::dataparallel::generic::<8>(),
        &mut generic,
        &left,
        &right,
        &mut generic_output,
    );
    verify(&left, &right, &generic_output);
}
