use crate::tsl_core::{Generic as GenericExtension, Scalar, Simd, StaticSimdVector};

pub mod parallelism {
    #[derive(Clone, Copy, Debug, Default)]
    pub struct Native;

    #[derive(Clone, Copy, Debug, Default)]
    pub struct Fixed<const N: usize>;

    #[derive(Clone, Copy, Debug, Default)]
    pub struct Generic<const N: usize>;

    pub const fn native() -> Native {
        Native
    }

    pub const fn fixed<const N: usize>() -> Fixed<N> {
        Fixed
    }

    pub const fn generic<const N: usize>() -> Generic<N> {
        Generic
    }
}

pub trait VectorFor<Profile, T> {
    type Vec: StaticSimdVector<BaseType = T>;
}

impl<Profile, T, const N: usize> VectorFor<Profile, T> for parallelism::Generic<N>
where
    Simd<T, GenericExtension<N>>: StaticSimdVector<BaseType = T>,
{
    type Vec = Simd<T, GenericExtension<N>>;
}

pub trait LoadStore<V: StaticSimdVector> {
    unsafe fn load_unaligned(ptr: *const V::BaseType) -> V::RegisterType;
    unsafe fn store_unaligned(ptr: *mut V::BaseType, value: V::RegisterType);
}

pub trait UnaryKernel<V: StaticSimdVector> {
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType;
}

pub fn transform_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        input.len(),
        output.len(),
        "tsl::algo::transform_unary requires input and output slices of equal length",
    );
    unsafe {
        transform_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn transform_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::transform_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let result =
            <Op as UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
    }

    while offset < count {
        let value = unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
        };
        let result = <Op as UnaryKernel<Simd<T, Scalar>>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += 1;
    }
}
