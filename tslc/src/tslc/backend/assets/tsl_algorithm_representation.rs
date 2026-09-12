use crate::tsl_core::{Generic as GenericExtension, Simd, SimdVector, StaticSimdVector};

pub mod dataparallel {
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

pub(super) mod representation_sealed {
    pub trait VectorPolicy {}
    pub trait RebindBase {}
    pub trait IntegralMaskWord {}
    pub trait MaskLayout {}
}

impl representation_sealed::VectorPolicy for dataparallel::Native {}
impl<const N: usize> representation_sealed::VectorPolicy for dataparallel::Fixed<N> {}
impl<const N: usize> representation_sealed::VectorPolicy for dataparallel::Generic<N> {}

impl<V: SimdVector> representation_sealed::RebindBase for V {}

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait VectorFor<Profile, T>: representation_sealed::VectorPolicy {
    type Vec: StaticSimdVector<BaseType = T>;
}

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait RebindBase<ToBase>: SimdVector + representation_sealed::RebindBase {
    type Vec: StaticSimdVector<BaseType = ToBase>;
}

impl<V, ToBase> RebindBase<ToBase> for V
where
    V: SimdVector,
    V::WithBaseType<ToBase>: StaticSimdVector<BaseType = ToBase>,
{
    type Vec = V::WithBaseType<ToBase>;
}

pub type ReboundBase<V, ToBase> = <V as RebindBase<ToBase>>::Vec;

impl<Profile, T, const N: usize> VectorFor<Profile, T> for dataparallel::Generic<N>
where
    Simd<T, GenericExtension<N>>: StaticSimdVector<BaseType = T>,
{
    type Vec = Simd<T, GenericExtension<N>>;
}
