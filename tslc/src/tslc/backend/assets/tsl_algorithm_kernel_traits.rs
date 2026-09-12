use crate::tsl_core::StaticSimdVector;

pub trait LoadStore<V: StaticSimdVector> {
    /// # Safety
    ///
    /// `ptr` must be valid to read one unaligned vector of initialized lanes.
    unsafe fn load_unaligned(ptr: *const V::BaseType) -> V::RegisterType;
    /// # Safety
    ///
    /// `ptr` must be valid to write one unaligned vector of lanes.
    unsafe fn store_unaligned(ptr: *mut V::BaseType, value: V::RegisterType);
}

pub trait SelectedLoad<V: StaticSimdVector, const SCALE: u32> {
    /// # Safety
    ///
    /// `input` and `indices` must be valid for every lane read by the
    /// implementation, including the byte scale selected by `SCALE`.
    unsafe fn load_selected(input: *const V::BaseType, indices: *const usize) -> V::RegisterType;
}

pub trait MaskedStore<V: StaticSimdVector> {
    /// # Safety
    ///
    /// `ptr` must be valid for every lane written by `mask`.
    unsafe fn store_mask_unaligned(
        mask: V::MaskType,
        ptr: *mut V::BaseType,
        value: V::RegisterType,
    );
}

pub trait CompressStore<V: StaticSimdVector> {
    /// # Safety
    ///
    /// `ptr` must be valid for the number of active lanes in `mask`.
    unsafe fn compress_store(mask: V::MaskType, ptr: *mut V::BaseType, value: V::RegisterType);
}

pub trait MaskPopulationCount<V: StaticSimdVector> {
    fn mask_population_count(mask: V::MaskType) -> usize;
}

pub trait UnaryKernel<V: StaticSimdVector> {
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType;
}

pub trait BinaryKernel<V: StaticSimdVector> {
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType;
}

impl<V, Kernel> BinaryKernel<V> for &mut Kernel
where
    V: StaticSimdVector,
    Kernel: BinaryKernel<V> + ?Sized,
{
    fn apply(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::RegisterType {
        <Kernel as BinaryKernel<V>>::apply(*self, left, right)
    }
}

pub trait UnaryPredicateKernel<V: StaticSimdVector> {
    fn test(&mut self, value: V::RegisterType) -> V::MaskType;
}

pub trait BinaryPredicateKernel<V: StaticSimdVector> {
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType;
}

pub trait MaskedUnaryKernel<V: StaticSimdVector> {
    fn apply(&mut self, active: V::MaskType, value: V::RegisterType) -> V::RegisterType;
}

pub trait MaskedBinaryKernel<V: StaticSimdVector> {
    fn apply(
        &mut self,
        active: V::MaskType,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType;
}

pub trait UnaryConsumeKernel<V: StaticSimdVector> {
    fn consume(&mut self, value: V::RegisterType);
}

pub trait BinaryConsumeKernel<V: StaticSimdVector> {
    fn consume(&mut self, left: V::RegisterType, right: V::RegisterType);
}

pub trait MaskedUnaryConsumeKernel<V: StaticSimdVector> {
    fn consume(&mut self, active: V::MaskType, value: V::RegisterType);
}

pub trait MaskedBinaryConsumeKernel<V: StaticSimdVector> {
    fn consume(&mut self, active: V::MaskType, left: V::RegisterType, right: V::RegisterType);
}

pub trait UnaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(&mut self, value: V::RegisterType);
    fn finalize(&self) -> Self::Output;
}

pub trait BinaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(&mut self, left: V::RegisterType, right: V::RegisterType);
    fn finalize(&self) -> Self::Output;
}

pub trait MaskedUnaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(&mut self, active: V::MaskType, value: V::RegisterType);
    fn finalize(&self) -> Self::Output;
}

pub trait MaskedBinaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(&mut self, active: V::MaskType, left: V::RegisterType, right: V::RegisterType);
    fn finalize(&self) -> Self::Output;
}

pub trait ChunkKernel<V: StaticSimdVector> {
    /// # Safety
    ///
    /// `ptr.add(offset)` must be valid for the lanes the implementation reads,
    /// bounded by `count`.
    unsafe fn apply(&mut self, ptr: *const V::BaseType, offset: usize, count: usize);
}
