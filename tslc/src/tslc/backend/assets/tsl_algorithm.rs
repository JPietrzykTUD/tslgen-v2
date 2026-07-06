use crate::tsl_core::{Generic as GenericExtension, Scalar, Simd, SimdVector, StaticSimdVector};

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

pub mod mask_layout {
    #[derive(Clone, Copy, Debug, Default)]
    pub struct Integral;

    #[derive(Clone, Copy, Debug, Default)]
    pub struct Native;

    #[derive(Clone, Copy, Debug, Default)]
    pub struct Bytes;

    #[derive(Clone, Copy, Debug, Default)]
    pub struct Bits;
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

pub trait SelectedLoad<V: StaticSimdVector, const SCALE: u32> {
    unsafe fn load_selected(input: *const V::BaseType, indices: *const usize) -> V::RegisterType;
}

pub trait IntegralMaskWord: Copy + Default {
    const BITS: usize;

    fn zero() -> Self {
        Self::default()
    }

    fn one_at(lane: usize) -> Self;
    fn count_ones(self) -> u32;
    fn bit_and(self, other: Self) -> Self;
    fn lane_is_set(self, lane: usize) -> bool;
    fn with_lane_set(self, lane: usize) -> Self;
}

macro_rules! impl_integral_mask_word {
    ($($type:ty),* $(,)?) => {
        $(
            impl IntegralMaskWord for $type {
                const BITS: usize = <$type>::BITS as usize;

                fn one_at(lane: usize) -> Self {
                    debug_assert!(lane < <Self as IntegralMaskWord>::BITS);
                    (1 as $type) << lane
                }

                fn count_ones(self) -> u32 {
                    self.count_ones()
                }

                fn bit_and(self, other: Self) -> Self {
                    self & other
                }

                fn lane_is_set(self, lane: usize) -> bool {
                    debug_assert!(lane < <Self as IntegralMaskWord>::BITS);
                    ((self >> lane) & 1) != 0
                }

                fn with_lane_set(self, lane: usize) -> Self {
                    self | Self::one_at(lane)
                }
            }
        )*
    };
}

impl_integral_mask_word!(u8, u16, u32, u64);

pub trait IntegralMask<V: StaticSimdVector> {
    fn to_integral(mask: V::MaskType) -> V::ImaskType;
}

pub trait MaskFromIntegral<V: StaticSimdVector> {
    fn to_mask(mask: V::ImaskType) -> V::MaskType;
}

unsafe fn packed_bit_mask_set(masks: *mut u8, row: usize, active: bool) {
    let byte = row / 8;
    let bit = row % 8;
    let mask = 1u8 << bit;
    let current = unsafe { masks.add(byte).read() };
    let next = if active {
        current | mask
    } else {
        current & !mask
    };
    unsafe {
        masks.add(byte).write(next);
    }
}

unsafe fn packed_bit_mask_test(masks: *const u8, row: usize) -> bool {
    let byte = row / 8;
    let bit = row % 8;
    ((unsafe { masks.add(byte).read() } >> bit) & 1) != 0
}

pub trait MaskLayout<Profile, V: StaticSimdVector>
where
    V::ImaskType: IntegralMaskWord,
{
    type Storage: Copy;

    const ROW_ORIENTED: bool;

    fn storage_count(count: usize, lanes: usize) -> usize;
    unsafe fn clear_for_predicate(masks: *mut Self::Storage, count: usize);
    unsafe fn store_mask(
        masks: *mut Self::Storage,
        chunk: usize,
        element: usize,
        mask: V::MaskType,
    );
    unsafe fn store_integral_mask(masks: *mut Self::Storage, chunk: usize, mask: V::ImaskType);
    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        chunk: usize,
        element: usize,
        lane: usize,
        active: bool,
    );
    unsafe fn load_mask(masks: *const Self::Storage, chunk: usize, element: usize) -> V::MaskType;
    unsafe fn lane_active(
        masks: *const Self::Storage,
        chunk: usize,
        element: usize,
        lane: usize,
    ) -> bool;
}

impl<Profile, V> MaskLayout<Profile, V> for mask_layout::Integral
where
    V: StaticSimdVector,
    V::ImaskType: IntegralMaskWord,
    Profile: IntegralMask<V> + MaskFromIntegral<V>,
{
    type Storage = V::ImaskType;

    const ROW_ORIENTED: bool = false;

    fn storage_count(count: usize, lanes: usize) -> usize {
        chunk_count_for_lanes(count, lanes)
    }

    unsafe fn clear_for_predicate(_masks: *mut Self::Storage, _count: usize) {}

    unsafe fn store_mask(
        masks: *mut Self::Storage,
        chunk: usize,
        _element: usize,
        mask: V::MaskType,
    ) {
        unsafe {
            masks
                .add(chunk)
                .write(<Profile as IntegralMask<V>>::to_integral(mask));
        }
    }

    unsafe fn store_integral_mask(masks: *mut Self::Storage, chunk: usize, mask: V::ImaskType) {
        unsafe {
            masks.add(chunk).write(mask);
        }
    }

    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        chunk: usize,
        _element: usize,
        lane: usize,
        active: bool,
    ) {
        let mut mask = unsafe { masks.add(chunk).read() };
        if active {
            mask = mask.with_lane_set(lane);
        }
        unsafe {
            masks.add(chunk).write(mask);
        }
    }

    unsafe fn load_mask(masks: *const Self::Storage, chunk: usize, _element: usize) -> V::MaskType {
        <Profile as MaskFromIntegral<V>>::to_mask(unsafe { masks.add(chunk).read() })
    }

    unsafe fn lane_active(
        masks: *const Self::Storage,
        chunk: usize,
        _element: usize,
        lane: usize,
    ) -> bool {
        (unsafe { masks.add(chunk).read() }).lane_is_set(lane)
    }
}

impl<Profile, V> MaskLayout<Profile, V> for mask_layout::Native
where
    V: StaticSimdVector,
    V::MaskType: Copy,
    V::ImaskType: IntegralMaskWord,
    Profile: IntegralMask<V> + MaskFromIntegral<V>,
{
    type Storage = V::MaskType;

    const ROW_ORIENTED: bool = false;

    fn storage_count(count: usize, lanes: usize) -> usize {
        chunk_count_for_lanes(count, lanes)
    }

    unsafe fn clear_for_predicate(_masks: *mut Self::Storage, _count: usize) {}

    unsafe fn store_mask(
        masks: *mut Self::Storage,
        chunk: usize,
        _element: usize,
        mask: V::MaskType,
    ) {
        unsafe {
            masks.add(chunk).write(mask);
        }
    }

    unsafe fn store_integral_mask(masks: *mut Self::Storage, chunk: usize, mask: V::ImaskType) {
        unsafe {
            masks
                .add(chunk)
                .write(<Profile as MaskFromIntegral<V>>::to_mask(mask));
        }
    }

    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        chunk: usize,
        _element: usize,
        lane: usize,
        active: bool,
    ) {
        let stored = unsafe { masks.add(chunk).read() };
        let mut mask = <Profile as IntegralMask<V>>::to_integral(stored);
        if active {
            mask = mask.with_lane_set(lane);
        }
        unsafe {
            masks
                .add(chunk)
                .write(<Profile as MaskFromIntegral<V>>::to_mask(mask));
        }
    }

    unsafe fn load_mask(masks: *const Self::Storage, chunk: usize, _element: usize) -> V::MaskType {
        unsafe { masks.add(chunk).read() }
    }

    unsafe fn lane_active(
        masks: *const Self::Storage,
        chunk: usize,
        _element: usize,
        lane: usize,
    ) -> bool {
        let mask = <Profile as IntegralMask<V>>::to_integral(unsafe { masks.add(chunk).read() });
        mask.lane_is_set(lane)
    }
}

impl<Profile, V> MaskLayout<Profile, V> for mask_layout::Bytes
where
    V: StaticSimdVector,
    V::ImaskType: IntegralMaskWord,
    Profile: IntegralMask<V> + MaskFromIntegral<V>,
{
    type Storage = u8;

    const ROW_ORIENTED: bool = true;

    fn storage_count(count: usize, _lanes: usize) -> usize {
        count
    }

    unsafe fn clear_for_predicate(_masks: *mut Self::Storage, _count: usize) {}

    unsafe fn store_mask(
        masks: *mut Self::Storage,
        _chunk: usize,
        element: usize,
        mask: V::MaskType,
    ) {
        let imask = <Profile as IntegralMask<V>>::to_integral(mask);
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            let active = imask.lane_is_set(lane);
            unsafe {
                masks.add(element + lane).write(if active { 1 } else { 0 });
            }
            lane += 1;
        }
    }

    unsafe fn store_integral_mask(masks: *mut Self::Storage, _chunk: usize, mask: V::ImaskType) {
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            let active = mask.lane_is_set(lane);
            unsafe {
                masks.add(lane).write(if active { 1 } else { 0 });
            }
            lane += 1;
        }
    }

    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        _chunk: usize,
        element: usize,
        _lane: usize,
        active: bool,
    ) {
        unsafe {
            masks.add(element).write(if active { 1 } else { 0 });
        }
    }

    unsafe fn load_mask(masks: *const Self::Storage, _chunk: usize, element: usize) -> V::MaskType {
        let mut imask = V::ImaskType::zero();
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            if (unsafe { masks.add(element + lane).read() }) != 0 {
                imask = imask.with_lane_set(lane);
            }
            lane += 1;
        }
        <Profile as MaskFromIntegral<V>>::to_mask(imask)
    }

    unsafe fn lane_active(
        masks: *const Self::Storage,
        _chunk: usize,
        element: usize,
        _lane: usize,
    ) -> bool {
        (unsafe { masks.add(element).read() }) != 0
    }
}

impl<Profile, V> MaskLayout<Profile, V> for mask_layout::Bits
where
    V: StaticSimdVector,
    V::ImaskType: IntegralMaskWord,
    Profile: IntegralMask<V> + MaskFromIntegral<V>,
{
    type Storage = u8;

    const ROW_ORIENTED: bool = true;

    fn storage_count(count: usize, _lanes: usize) -> usize {
        chunk_count_for_lanes(count, 8)
    }

    unsafe fn clear_for_predicate(masks: *mut Self::Storage, count: usize) {
        let bytes = chunk_count_for_lanes(count, 8);
        let mut i = 0usize;
        while i < bytes {
            unsafe {
                masks.add(i).write(0);
            }
            i += 1;
        }
    }

    unsafe fn store_mask(
        masks: *mut Self::Storage,
        _chunk: usize,
        element: usize,
        mask: V::MaskType,
    ) {
        let imask = <Profile as IntegralMask<V>>::to_integral(mask);
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            unsafe {
                packed_bit_mask_set(masks, element + lane, imask.lane_is_set(lane));
            }
            lane += 1;
        }
    }

    unsafe fn store_integral_mask(masks: *mut Self::Storage, _chunk: usize, mask: V::ImaskType) {
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            unsafe {
                packed_bit_mask_set(masks, lane, mask.lane_is_set(lane));
            }
            lane += 1;
        }
    }

    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        _chunk: usize,
        element: usize,
        _lane: usize,
        active: bool,
    ) {
        unsafe {
            packed_bit_mask_set(masks, element, active);
        }
    }

    unsafe fn load_mask(masks: *const Self::Storage, _chunk: usize, element: usize) -> V::MaskType {
        let mut imask = V::ImaskType::zero();
        let mut lane = 0usize;
        while lane < V::ELEMENT_COUNT {
            if unsafe { packed_bit_mask_test(masks, element + lane) } {
                imask = imask.with_lane_set(lane);
            }
            lane += 1;
        }
        <Profile as MaskFromIntegral<V>>::to_mask(imask)
    }

    unsafe fn lane_active(
        masks: *const Self::Storage,
        _chunk: usize,
        element: usize,
        _lane: usize,
    ) -> bool {
        unsafe { packed_bit_mask_test(masks, element) }
    }
}

pub trait MaskedStore<V: StaticSimdVector> {
    unsafe fn store_mask_unaligned(
        mask: V::MaskType,
        ptr: *mut V::BaseType,
        value: V::RegisterType,
    );
}

pub trait CompressStore<V: StaticSimdVector> {
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
    unsafe fn apply(&mut self, ptr: *const V::BaseType, offset: usize, count: usize);
}

fn validate_integral_mask_vector<V: StaticSimdVector>(helper_name: &str) -> usize
where
    V::ImaskType: IntegralMaskWord,
{
    let lanes = V::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "{} requires a vector with at least one lane",
        helper_name,
    );
    assert!(
        lanes <= <V::ImaskType as IntegralMaskWord>::BITS,
        "{} requires an integral mask storage type with at least one bit per lane",
        helper_name,
    );
    lanes
}

fn chunk_count_for_lanes(count: usize, lanes: usize) -> usize {
    (count / lanes) + if count % lanes == 0 { 0 } else { 1 }
}

pub(crate) fn selected_row_scale<T, const SCALE: u32>() -> usize {
    let scale = if SCALE == 0 {
        core::mem::size_of::<T>()
    } else {
        SCALE as usize
    };
    assert!(scale > 0, "tsl::algo selected-row scale must be nonzero");
    scale
}

pub(crate) fn selected_row_pointer<T, const SCALE: u32>(input: *const T, index: usize) -> *const T {
    let byte_offset = index.wrapping_mul(selected_row_scale::<T, SCALE>());
    (input as *const u8).wrapping_add(byte_offset) as *const T
}

fn validate_selected_indices<T>(helper_name: &str, input: &[T], indices: &[usize]) {
    for &index in indices {
        assert!(
            index < input.len(),
            "{} requires selected row ids to be valid element indexes",
            helper_name,
        );
    }
}

fn scalar_mask_from_bool<Profile, T>(active: bool) -> <Simd<T, Scalar> as SimdVector>::MaskType
where
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: MaskFromIntegral<Simd<T, Scalar>>,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let imask = if active {
        <<Simd<T, Scalar> as SimdVector>::ImaskType as IntegralMaskWord>::one_at(0)
    } else {
        <<Simd<T, Scalar> as SimdVector>::ImaskType as IntegralMaskWord>::zero()
    };
    <Profile as MaskFromIntegral<Simd<T, Scalar>>>::to_mask(imask)
}

unsafe fn append_indices_from_mask<Mask>(
    mask: Mask,
    indices: *mut usize,
    produced: &mut usize,
    base_index: usize,
    lanes: usize,
) where
    Mask: IntegralMaskWord,
{
    let mut lane = 0usize;
    while lane < lanes {
        if mask.lane_is_set(lane) {
            unsafe {
                indices.add(*produced).write(base_index + lane);
            }
            *produced += 1;
        }
        lane += 1;
    }
}

unsafe fn append_selected_indices_from_mask<Mask>(
    mask: Mask,
    input_indices: *const usize,
    output_indices: *mut usize,
    produced: &mut usize,
    base_index: usize,
    lanes: usize,
) where
    Mask: IntegralMaskWord,
{
    let mut lane = 0usize;
    while lane < lanes {
        if mask.lane_is_set(lane) {
            unsafe {
                output_indices
                    .add(*produced)
                    .write(input_indices.add(base_index + lane).read());
            }
            *produced += 1;
        }
        lane += 1;
    }
}

pub fn integral_mask_chunk_count<Profile, Policy, T>(_policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::integral_mask_chunk_count",
    );
    chunk_count_for_lanes(count, lanes)
}

fn validate_mask_layout_vector<V: StaticSimdVector>(helper_name: &str) -> usize
where
    V::ImaskType: IntegralMaskWord,
{
    validate_integral_mask_vector::<V>(helper_name)
}

pub fn mask_chunk_count<Profile, Policy, Layout, T>(_policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::mask_chunk_count",
    );
    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
        count, lanes,
    )
}

pub fn native_mask_chunk_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Native: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Native, T>(policy, count)
}

pub fn byte_mask_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Bytes: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Bytes, T>(policy, count)
}

pub fn bit_mask_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Bits: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Bits, T>(policy, count)
}

pub fn for_each_chunk<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, data: &[T])
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec> + ChunkKernel<Simd<T, Scalar>>,
{
    unsafe {
        for_each_chunk_raw::<Profile, Policy, Op, T>(policy, op, data.as_ptr(), data.len());
    }
}

pub unsafe fn for_each_chunk_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    data: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec> + ChunkKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::for_each_chunk requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        unsafe {
            <Op as ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
                op,
                data.add(offset),
                offset,
                lanes,
            );
        }
        offset += lanes;
    }

    while offset < count {
        unsafe {
            <Op as ChunkKernel<Simd<T, Scalar>>>::apply(op, data.add(offset), offset, 1);
        }
        offset += 1;
    }
}

pub fn predicate_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &mut [<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::predicate_unary requires enough mask chunks for the input",
    );
    unsafe {
        predicate_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn predicate_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *mut <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            masks.add(produced).write(imask);
        }
        produced += 1;
        offset += lanes;
    }

    if offset < count {
        let mut tail_mask =
            <<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType as IntegralMaskWord>::zero();
        let mut lane = 0usize;
        while offset < count {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
            let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
            if <<Simd<T, Scalar> as SimdVector>::ImaskType as IntegralMaskWord>::lane_is_set(
                imask, 0,
            ) {
                tail_mask = tail_mask.with_lane_set(lane);
            }
            offset += 1;
            lane += 1;
        }
        unsafe {
            masks.add(produced).write(tail_mask);
        }
        produced += 1;
    }

    produced
}

pub fn predicate_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &mut [<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::predicate_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::predicate_binary requires enough mask chunks for the input",
    );
    unsafe {
        predicate_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn predicate_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *mut <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            masks.add(produced).write(imask);
        }
        produced += 1;
        offset += lanes;
    }

    if offset < count {
        let mut tail_mask =
            <<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType as IntegralMaskWord>::zero();
        let mut lane = 0usize;
        while offset < count {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let mask =
                <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
            let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
            if <<Simd<T, Scalar> as SimdVector>::ImaskType as IntegralMaskWord>::lane_is_set(
                imask, 0,
            ) {
                tail_mask = tail_mask.with_lane_set(lane);
            }
            offset += 1;
            lane += 1;
        }
        unsafe {
            masks.add(produced).write(tail_mask);
        }
        produced += 1;
    }

    produced
}

pub fn predicate_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &mut [<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::predicate_unary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        predicate_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn predicate_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *mut <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_unary_mask_layout",
    );
    unsafe {
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::clear_for_predicate(
            masks, count,
        );
    }

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_mask(
                masks, chunk, offset, mask,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        if <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::ROW_ORIENTED {
            let mut lane = 0usize;
            while offset < count {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
                let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
                unsafe {
                    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_tail_lane(
                        masks,
                        chunk,
                        offset,
                        lane,
                        imask.lane_is_set(0),
                    );
                }
                offset += 1;
                lane += 1;
            }
        } else {
            let mut tail_mask =
                <<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType as IntegralMaskWord>::zero();
            let mut lane = 0usize;
            while offset < count {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
                let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
                if imask.lane_is_set(0) {
                    tail_mask = tail_mask.with_lane_set(lane);
                }
                offset += 1;
                lane += 1;
            }
            unsafe {
                <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_integral_mask(
                    masks, chunk, tail_mask,
                );
            }
        }
    }

    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
        count, lanes,
    )
}

pub fn predicate_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &mut [<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::predicate_binary_mask_layout requires left and right slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::predicate_binary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        predicate_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn predicate_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *mut <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::predicate_binary_mask_layout",
    );
    unsafe {
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::clear_for_predicate(
            masks, count,
        );
    }

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_mask(
                masks, chunk, offset, mask,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        if <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::ROW_ORIENTED {
            let mut lane = 0usize;
            while offset < count {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let mask = <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(
                    op,
                    left_value,
                    right_value,
                );
                let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
                unsafe {
                    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_tail_lane(
                        masks,
                        chunk,
                        offset,
                        lane,
                        imask.lane_is_set(0),
                    );
                }
                offset += 1;
                lane += 1;
            }
        } else {
            let mut tail_mask =
                <<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType as IntegralMaskWord>::zero();
            let mut lane = 0usize;
            while offset < count {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let mask = <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(
                    op,
                    left_value,
                    right_value,
                );
                let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
                if imask.lane_is_set(0) {
                    tail_mask = tail_mask.with_lane_set(lane);
                }
                offset += 1;
                lane += 1;
            }
            unsafe {
                <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::store_integral_mask(
                    masks, chunk, tail_mask,
                );
            }
        }
    }

    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
        count, lanes,
    )
}

pub fn count_unary<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, input: &[T]) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    unsafe { count_unary_raw::<Profile, Policy, Op, T>(policy, op, input.as_ptr(), input.len()) }
}

pub unsafe fn count_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        produced += imask.count_ones() as usize;
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn count_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::count_binary requires left and right slices of equal length",
    );
    unsafe {
        count_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn count_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        produced += imask.count_ones() as usize;
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        let mask =
            <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn count_masked_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::count_masked_unary requires enough mask chunks for the input",
    );
    unsafe {
        count_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn count_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        produced += input_mask.bit_and(predicate_mask).count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn count_masked_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::count_masked_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::count_masked_binary requires enough mask chunks for the input",
    );
    unsafe {
        count_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn count_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        produced += input_mask.bit_and(predicate_mask).count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let predicate = <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(
                    op,
                    left_value,
                    right_value,
                );
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn count_masked_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::count_masked_unary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        count_masked_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn count_masked_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_unary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        produced += input_imask.bit_and(predicate_mask).count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn count_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::count_masked_binary_mask_layout requires left and right slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::count_masked_binary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        count_masked_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn count_masked_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_masked_binary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        produced += input_imask.bit_and(predicate_mask).count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let predicate =
                <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn count_selected_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    validate_selected_indices("tsl::algo::count_selected_unary", input, indices);
    unsafe {
        count_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
    }
}

pub unsafe fn count_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    unsafe {
        count_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            selected_count,
        )
    }
}

pub unsafe fn count_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_selected_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        produced += imask.count_ones() as usize;
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn count_selected_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::count_selected_binary requires left and right slices of equal length",
    );
    validate_selected_indices("tsl::algo::count_selected_binary", left, indices);
    unsafe {
        count_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
    }
}

pub unsafe fn count_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    unsafe {
        count_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            selected_count,
        )
    }
}

pub unsafe fn count_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::count_selected_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        produced += imask.count_ones() as usize;
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        let mask =
            <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert!(
        output.len() >= input.len(),
        "tsl::algo::select_unary requires enough output slots for the input",
    );
    unsafe {
        select_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                mask,
                output.add(produced),
                value,
            );
        }
        produced +=
            <Profile as MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>>::mask_population_count(
                mask,
            );
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(produced),
                    value,
                );
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_binary requires left and right slices of equal length",
    );
    assert!(
        output.len() >= left.len(),
        "tsl::algo::select_binary requires enough output slots for the input",
    );
    unsafe {
        select_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                mask,
                output.add(produced),
                left_value,
            );
        }
        produced +=
            <Profile as MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>>::mask_population_count(
                mask,
            );
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        let mask =
            <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(produced),
                    left_value,
                );
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_masked_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_unary requires enough mask chunks for the input",
    );
    assert!(
        output.len() >= input.len(),
        "tsl::algo::select_masked_unary requires enough output slots for the input",
    );
    unsafe {
        select_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        let active_mask = input_mask.bit_and(predicate_mask);
        let active = <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(
            active_mask,
        );
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                active,
                output.add(produced),
                value,
            );
        }
        produced +=
            <Profile as MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>>::mask_population_count(
                active,
            );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    unsafe {
                        <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                            output.add(produced),
                            value,
                        );
                    }
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn select_masked_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_masked_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_binary requires enough mask chunks for the input",
    );
    assert!(
        output.len() >= left.len(),
        "tsl::algo::select_masked_binary requires enough output slots for the input",
    );
    unsafe {
        select_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        let active_mask = input_mask.bit_and(predicate_mask);
        let active = <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(
            active_mask,
        );
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                active,
                output.add(produced),
                left_value,
            );
        }
        produced +=
            <Profile as MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>>::mask_population_count(
                active,
            );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let predicate = <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(
                    op,
                    left_value,
                    right_value,
                );
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    unsafe {
                        <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                            output.add(produced),
                            left_value,
                        );
                    }
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn select_masked_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_unary_mask_layout requires enough mask storage for the input",
    );
    assert!(
        output.len() >= input.len(),
        "tsl::algo::select_masked_unary_mask_layout requires enough output slots for the input",
    );
    unsafe {
        select_masked_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_masked_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_unary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        let active_mask = input_imask.bit_and(predicate_mask);
        let active = <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(
            active_mask,
        );
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                active,
                output.add(produced),
                value,
            );
        }
        produced += active_mask.count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                        output.add(produced),
                        value,
                    );
                }
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn select_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_masked_binary_mask_layout requires left and right slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_binary_mask_layout requires enough mask storage for the input",
    );
    assert!(
        output.len() >= left.len(),
        "tsl::algo::select_masked_binary_mask_layout requires enough output slots for the input",
    );
    unsafe {
        select_masked_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_masked_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_binary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        let active_mask = input_imask.bit_and(predicate_mask);
        let active = <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(
            active_mask,
        );
        unsafe {
            <Profile as CompressStore<<Policy as VectorFor<Profile, T>>::Vec>>::compress_store(
                active,
                output.add(produced),
                left_value,
            );
        }
        produced += active_mask.count_ones() as usize;
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let predicate =
                <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                        output.add(produced),
                        left_value,
                    );
                }
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn select_indices_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert!(
        indices.len() >= input.len(),
        "tsl::algo::select_indices_unary requires enough output slots for the input",
    );
    unsafe {
        select_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_indices_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_indices_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            append_indices_from_mask(imask, indices, &mut produced, offset, lanes);
        }
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                indices.add(produced).write(offset);
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_indices_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_indices_binary requires left and right slices of equal length",
    );
    assert!(
        indices.len() >= left.len(),
        "tsl::algo::select_indices_binary requires enough output slots for the input",
    );
    unsafe {
        select_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_indices_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_indices_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            append_indices_from_mask(imask, indices, &mut produced, offset, lanes);
        }
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        let mask =
            <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                indices.add(produced).write(offset);
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_masked_indices_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_indices_unary requires enough mask chunks for the input",
    );
    assert!(
        indices.len() >= input.len(),
        "tsl::algo::select_masked_indices_unary requires enough output slots for the input",
    );
    unsafe {
        select_masked_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_masked_indices_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        unsafe {
            append_indices_from_mask(
                input_mask.bit_and(predicate_mask),
                indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    unsafe {
                        indices.add(produced).write(offset);
                    }
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn select_masked_indices_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_masked_indices_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_indices_binary requires enough mask chunks for the input",
    );
    assert!(
        indices.len() >= left.len(),
        "tsl::algo::select_masked_indices_binary requires enough output slots for the input",
    );
    unsafe {
        select_masked_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_masked_indices_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        unsafe {
            append_indices_from_mask(
                input_mask.bit_and(predicate_mask),
                indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let input_mask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if input_mask.lane_is_set(lane) {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let predicate = <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(
                    op,
                    left_value,
                    right_value,
                );
                let predicate_mask =
                    <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
                if predicate_mask.lane_is_set(0) {
                    unsafe {
                        indices.add(produced).write(offset);
                    }
                    produced += 1;
                }
            }
            offset += 1;
            lane += 1;
        }
    }

    produced
}

pub fn select_masked_indices_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_indices_unary_mask_layout requires enough mask storage for the input",
    );
    assert!(
        indices.len() >= input.len(),
        "tsl::algo::select_masked_indices_unary_mask_layout requires enough output slots for the input",
    );
    unsafe {
        select_masked_indices_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn select_masked_indices_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_unary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let predicate =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        unsafe {
            append_indices_from_mask(
                input_imask.bit_and(predicate_mask),
                indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let predicate = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                unsafe {
                    indices.add(produced).write(offset);
                }
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn select_masked_indices_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_masked_indices_binary_mask_layout requires left and right slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::select_masked_indices_binary_mask_layout requires enough mask storage for the input",
    );
    assert!(
        indices.len() >= left.len(),
        "tsl::algo::select_masked_indices_binary_mask_layout requires enough output slots for the input",
    );
    unsafe {
        select_masked_indices_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn select_masked_indices_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    indices: *mut usize,
    count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_masked_indices_binary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= count {
        let input_mask = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let input_imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                input_mask,
            );
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let predicate = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let predicate_mask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(
                predicate,
            );
        unsafe {
            append_indices_from_mask(
                input_imask.bit_and(predicate_mask),
                indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    let mut lane = 0usize;
    while offset < count {
        if unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        } {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let predicate =
                <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
            let predicate_mask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(predicate);
            if predicate_mask.lane_is_set(0) {
                unsafe {
                    indices.add(produced).write(offset);
                }
                produced += 1;
            }
        }
        offset += 1;
        lane += 1;
    }

    produced
}

pub fn select_selected_indices_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    input_indices: &[usize],
    output_indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    validate_selected_indices(
        "tsl::algo::select_selected_indices_unary",
        input,
        input_indices,
    );
    assert!(
        output_indices.len() >= input_indices.len(),
        "tsl::algo::select_selected_indices_unary requires enough output slots for the selected rows",
    );
    unsafe {
        select_selected_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            input_indices.as_ptr(),
            output_indices.as_mut_ptr(),
            input_indices.len(),
        )
    }
}

pub unsafe fn select_selected_indices_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    input_indices: *const usize,
    output_indices: *mut usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    unsafe {
        select_selected_indices_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            input_indices,
            output_indices,
            selected_count,
        )
    }
}

pub unsafe fn select_selected_indices_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    input_indices: *const usize,
    output_indices: *mut usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_selected_indices_unary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                input_indices.add(offset),
            )
        };
        let mask =
            <Op as UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(op, value);
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            append_selected_indices_from_mask(
                imask,
                input_indices,
                output_indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                input_indices.add(offset),
            )
        };
        let mask = <Op as UnaryPredicateKernel<Simd<T, Scalar>>>::test(op, value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                output_indices
                    .add(produced)
                    .write(input_indices.add(offset).read());
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn select_selected_indices_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    input_indices: &[usize],
    output_indices: &mut [usize],
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::select_selected_indices_binary requires left and right slices of equal length",
    );
    validate_selected_indices(
        "tsl::algo::select_selected_indices_binary",
        left,
        input_indices,
    );
    assert!(
        output_indices.len() >= input_indices.len(),
        "tsl::algo::select_selected_indices_binary requires enough output slots for the selected rows",
    );
    unsafe {
        select_selected_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            input_indices.as_ptr(),
            output_indices.as_mut_ptr(),
            input_indices.len(),
        )
    }
}

pub unsafe fn select_selected_indices_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    input_indices: *const usize,
    output_indices: *mut usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    unsafe {
        select_selected_indices_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            input_indices,
            output_indices,
            selected_count,
        )
    }
}

pub unsafe fn select_selected_indices_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    input_indices: *const usize,
    output_indices: *mut usize,
    selected_count: usize,
) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
        + IntegralMask<Simd<T, Scalar>>,
    Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryPredicateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::select_selected_indices_binary",
    );

    let mut offset = 0usize;
    let mut produced = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                input_indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                input_indices.add(offset),
            )
        };
        let mask = <Op as BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::test(
            op,
            left_value,
            right_value,
        );
        let imask =
            <Profile as IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>>::to_integral(mask);
        unsafe {
            append_selected_indices_from_mask(
                imask,
                input_indices,
                output_indices,
                &mut produced,
                offset,
                lanes,
            );
        }
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                input_indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                input_indices.add(offset),
            )
        };
        let mask =
            <Op as BinaryPredicateKernel<Simd<T, Scalar>>>::test(op, left_value, right_value);
        let imask = <Profile as IntegralMask<Simd<T, Scalar>>>::to_integral(mask);
        if imask.lane_is_set(0) {
            unsafe {
                output_indices
                    .add(produced)
                    .write(input_indices.add(offset).read());
            }
            produced += 1;
        }
        offset += 1;
    }

    produced
}

pub fn transform_selected_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
    validate_selected_indices("tsl::algo::transform_selected_unary", input, indices);
    assert!(
        output.len() >= indices.len(),
        "tsl::algo::transform_selected_unary requires enough output slots for the selected rows",
    );
    unsafe {
        transform_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            output.as_mut_ptr(),
            indices.len(),
        );
    }
}

pub unsafe fn transform_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    output: *mut T,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
    unsafe {
        transform_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            output,
            selected_count,
        );
    }
}

pub unsafe fn transform_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    output: *mut T,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::transform_selected_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        let result = <Op as UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        let result = <Op as UnaryKernel<Simd<T, Scalar>>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
}

pub fn transform_selected_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_selected_binary requires left and right slices of equal length",
    );
    validate_selected_indices("tsl::algo::transform_selected_binary", left, indices);
    assert!(
        output.len() >= indices.len(),
        "tsl::algo::transform_selected_binary requires enough output slots for the selected rows",
    );
    unsafe {
        transform_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            output.as_mut_ptr(),
            indices.len(),
        );
    }
}

pub unsafe fn transform_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    output: *mut T,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
    unsafe {
        transform_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            output,
            selected_count,
        );
    }
}

pub unsafe fn transform_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    output: *mut T,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::transform_selected_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        let result = <Op as BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        let result = <Op as BinaryKernel<Simd<T, Scalar>>>::apply(op, left_value, right_value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
}

pub fn consume_selected_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    validate_selected_indices("tsl::algo::consume_selected_unary", input, indices);
    unsafe {
        consume_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        );
    }
}

pub unsafe fn consume_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            selected_count,
        );
    }
}

pub unsafe fn consume_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_selected_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(op, value);
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, value);
        offset += 1;
    }
}

pub fn consume_selected_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::consume_selected_binary requires left and right slices of equal length",
    );
    validate_selected_indices("tsl::algo::consume_selected_binary", left, indices);
    unsafe {
        consume_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        );
    }
}

pub unsafe fn consume_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            selected_count,
        );
    }
}

pub unsafe fn consume_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_selected_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<Simd<T, Scalar>>>::consume(op, left_value, right_value);
        offset += 1;
    }
}

pub fn aggregate_selected_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    validate_selected_indices("tsl::algo::aggregate_selected_unary", input, indices);
    unsafe {
        aggregate_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
    }
}

pub unsafe fn aggregate_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            selected_count,
        )
    }
}

pub unsafe fn aggregate_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_selected_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(op, value);
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, value);
        offset += 1;
    }

    <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

pub fn aggregate_selected_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::aggregate_selected_binary requires left and right slices of equal length",
    );
    validate_selected_indices("tsl::algo::aggregate_selected_binary", left, indices);
    unsafe {
        aggregate_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
    }
}

pub unsafe fn aggregate_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            selected_count,
        )
    }
}

pub unsafe fn aggregate_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_selected_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, left_value, right_value);
        offset += 1;
    }

    <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

pub fn transform_where_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        input.len(),
        output.len(),
        "tsl::algo::transform_where_unary requires input and output slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_where_unary requires enough mask chunks for the input",
    );
    unsafe {
        transform_where_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn transform_where_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let result = <Op as MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op, active, value,
        );
        unsafe {
            <Profile as MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_mask_unaligned(
                active,
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if imask.lane_is_set(lane) {
                let value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
                };
                let active = scalar_mask_from_bool::<Profile, T>(true);
                let result = <Op as MaskedUnaryKernel<Simd<T, Scalar>>>::apply(op, active, value);
                unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                        output.add(offset),
                        result,
                    );
                }
            }
            offset += 1;
            lane += 1;
        }
    }
}

pub fn transform_where_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_where_binary requires left and right slices of equal length",
    );
    assert_eq!(
        left.len(),
        output.len(),
        "tsl::algo::transform_where_binary requires input and output slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_where_binary requires enough mask chunks for the input",
    );
    unsafe {
        transform_where_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn transform_where_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let result = <Op as MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            active,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_mask_unaligned(
                active,
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            if imask.lane_is_set(lane) {
                let left_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
                };
                let right_value = unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
                };
                let active = scalar_mask_from_bool::<Profile, T>(true);
                let result = <Op as MaskedBinaryKernel<Simd<T, Scalar>>>::apply(
                    op,
                    active,
                    left_value,
                    right_value,
                );
                unsafe {
                    <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                        output.add(offset),
                        result,
                    );
                }
            }
            offset += 1;
            lane += 1;
        }
    }
}

pub fn transform_masked_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        input.len(),
        output.len(),
        "tsl::algo::transform_masked_unary requires input and output slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_masked_unary requires enough mask chunks for the input",
    );
    unsafe {
        transform_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn transform_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let result = <Op as MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op, active, value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let result = <Op as MaskedUnaryKernel<Simd<T, Scalar>>>::apply(op, active, value);
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(offset),
                    result,
                );
            }
            offset += 1;
            lane += 1;
        }
    }
}

pub fn transform_masked_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_masked_binary requires left and right slices of equal length",
    );
    assert_eq!(
        left.len(),
        output.len(),
        "tsl::algo::transform_masked_binary requires input and output slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_masked_binary requires enough mask chunks for the input",
    );
    unsafe {
        transform_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn transform_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let result = <Op as MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            active,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let result = <Op as MaskedBinaryKernel<Simd<T, Scalar>>>::apply(
                op,
                active,
                left_value,
                right_value,
            );
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(offset),
                    result,
                );
            }
            offset += 1;
            lane += 1;
        }
    }
}

pub fn transform_where_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        input.len(),
        output.len(),
        "tsl::algo::transform_where_unary_mask_layout requires input and output slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_where_unary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        transform_where_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn transform_where_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_unary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let result = <Op as MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op, active, value,
        );
        unsafe {
            <Profile as MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_mask_unaligned(
                active,
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    while offset < count {
        let lane = offset % lanes;
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        };
        if active {
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            let scalar_active = scalar_mask_from_bool::<Profile, T>(true);
            let result =
                <Op as MaskedUnaryKernel<Simd<T, Scalar>>>::apply(op, scalar_active, value);
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(offset),
                    result,
                );
            }
        }
        offset += 1;
    }
}

pub fn transform_where_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_where_binary_mask_layout requires left and right slices of equal length",
    );
    assert_eq!(
        left.len(),
        output.len(),
        "tsl::algo::transform_where_binary_mask_layout requires input and output slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_where_binary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        transform_where_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn transform_where_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>
        + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_where_binary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let result = <Op as MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            active,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_mask_unaligned(
                active,
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    while offset < count {
        let lane = offset % lanes;
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        };
        if active {
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            let scalar_active = scalar_mask_from_bool::<Profile, T>(true);
            let result = <Op as MaskedBinaryKernel<Simd<T, Scalar>>>::apply(
                op,
                scalar_active,
                left_value,
                right_value,
            );
            unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(
                    output.add(offset),
                    result,
                );
            }
        }
        offset += 1;
    }
}

pub fn transform_masked_unary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        input.len(),
        output.len(),
        "tsl::algo::transform_masked_unary_mask_layout requires input and output slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_unary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            input.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_masked_unary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        transform_masked_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn transform_masked_unary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_unary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        let result = <Op as MaskedUnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op, active, value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    while offset < count {
        let lane = offset % lanes;
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        };
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        let scalar_active = scalar_mask_from_bool::<Profile, T>(active);
        let result = <Op as MaskedUnaryKernel<Simd<T, Scalar>>>::apply(op, scalar_active, value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
}

pub fn transform_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_masked_binary_mask_layout requires left and right slices of equal length",
    );
    assert_eq!(
        left.len(),
        output.len(),
        "tsl::algo::transform_masked_binary_mask_layout requires input and output slices of equal length",
    );
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_binary_mask_layout",
    );
    let required =
        <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
            left.len(),
            lanes,
        );
    assert!(
        masks.len() >= required,
        "tsl::algo::transform_masked_binary_mask_layout requires enough mask storage for the input",
    );
    unsafe {
        transform_masked_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn transform_masked_binary_mask_layout_raw<Profile, Policy, Layout, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::transform_masked_binary_mask_layout",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::load_mask(
                masks, chunk, offset,
            )
        };
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let result = <Op as MaskedBinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            active,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
        chunk += 1;
    }

    while offset < count {
        let lane = offset % lanes;
        let active = unsafe {
            <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::lane_active(
                masks, chunk, offset, lane,
            )
        };
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        let scalar_active = scalar_mask_from_bool::<Profile, T>(active);
        let result = <Op as MaskedBinaryKernel<Simd<T, Scalar>>>::apply(
            op,
            scalar_active,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
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
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
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
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
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
        let result = <Op as UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        let result = <Op as UnaryKernel<Simd<T, Scalar>>>::apply(op, value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
}

pub fn transform_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    output: &mut [T],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::transform_binary requires left and right slices of equal length",
    );
    assert_eq!(
        left.len(),
        output.len(),
        "tsl::algo::transform_binary requires input and output slices of equal length",
    );
    unsafe {
        transform_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn transform_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    output: *mut T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::transform_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        let result = <Op as BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
            op,
            left_value,
            right_value,
        );
        unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::store_unaligned(
                output.add(offset),
                result,
            );
        }
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        let result = <Op as BinaryKernel<Simd<T, Scalar>>>::apply(op, left_value, right_value);
        unsafe {
            <Profile as LoadStore<Simd<T, Scalar>>>::store_unaligned(output.add(offset), result);
        }
        offset += 1;
    }
}

pub fn consume_unary<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, input: &[T])
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_unary_raw::<Profile, Policy, Op, T>(policy, op, input.as_ptr(), input.len());
    }
}

pub unsafe fn consume_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(op, value);
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        <Op as UnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, value);
        offset += 1;
    }
}

pub fn consume_binary<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, left: &[T], right: &[T])
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::consume_binary requires left and right slices of equal length",
    );
    unsafe {
        consume_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn consume_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        <Op as BinaryConsumeKernel<Simd<T, Scalar>>>::consume(op, left_value, right_value);
        offset += 1;
    }
}

pub fn consume_masked_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::consume_masked_unary requires enough mask chunks for the input",
    );
    unsafe {
        consume_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        );
    }
}

pub unsafe fn consume_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op, active, value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            <Op as MaskedUnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, active, value);
            offset += 1;
            lane += 1;
        }
    }
}

pub fn consume_masked_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::consume_masked_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::consume_masked_binary requires enough mask chunks for the input",
    );
    unsafe {
        consume_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        );
    }
}

pub unsafe fn consume_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            active,
            left_value,
            right_value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            <Op as MaskedBinaryConsumeKernel<Simd<T, Scalar>>>::consume(
                op,
                active,
                left_value,
                right_value,
            );
            offset += 1;
            lane += 1;
        }
    }
}

pub fn aggregate_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_unary_raw::<Profile, Policy, Op, T>(policy, op, input.as_ptr(), input.len())
    }
}

pub unsafe fn aggregate_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(op, value);
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        <Op as UnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, value);
        offset += 1;
    }

    <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

pub fn aggregate_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::aggregate_binary requires left and right slices of equal length",
    );
    unsafe {
        aggregate_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn aggregate_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        <Op as BinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, left_value, right_value);
        offset += 1;
    }

    <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

pub fn aggregate_masked_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_unary",
    );
    let required = chunk_count_for_lanes(input.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::aggregate_masked_unary requires enough mask chunks for the input",
    );
    unsafe {
        aggregate_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        )
    }
}

pub unsafe fn aggregate_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op, active, value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            <Op as MaskedUnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, active, value);
            offset += 1;
            lane += 1;
        }
    }

    <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

pub fn aggregate_masked_binary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    assert_eq!(
        left.len(),
        right.len(),
        "tsl::algo::aggregate_masked_binary requires left and right slices of equal length",
    );
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_binary",
    );
    let required = chunk_count_for_lanes(left.len(), lanes);
    assert!(
        masks.len() >= required,
        "tsl::algo::aggregate_masked_binary requires enough mask chunks for the input",
    );
    unsafe {
        aggregate_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        )
    }
}

pub unsafe fn aggregate_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            active,
            left_value,
            right_value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            <Op as MaskedBinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(
                op,
                active,
                left_value,
                right_value,
            );
            offset += 1;
            lane += 1;
        }
    }

    <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}
