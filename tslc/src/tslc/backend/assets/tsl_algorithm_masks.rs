use super::representation::representation_sealed;
use super::validation::chunk_count_for_lanes;
use crate::tsl_core::{Scalar, Simd, SimdVector, StaticSimdVector};

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

impl representation_sealed::IntegralMaskWord for u8 {}
impl representation_sealed::IntegralMaskWord for u16 {}
impl representation_sealed::IntegralMaskWord for u32 {}
impl representation_sealed::IntegralMaskWord for u64 {}

impl representation_sealed::MaskLayout for mask_layout::Integral {}
impl representation_sealed::MaskLayout for mask_layout::Native {}
impl representation_sealed::MaskLayout for mask_layout::Bytes {}
impl representation_sealed::MaskLayout for mask_layout::Bits {}

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait IntegralMaskWord:
    Copy + Default + representation_sealed::IntegralMaskWord
{
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

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait MaskLayout<Profile, V: StaticSimdVector>: representation_sealed::MaskLayout
where
    V::ImaskType: IntegralMaskWord,
{
    type Storage: Copy;

    const ROW_ORIENTED: bool;

    fn storage_count(count: usize, lanes: usize) -> usize;
    /// # Safety
    ///
    /// `masks` must be valid for every storage element implied by `count`.
    unsafe fn clear_for_predicate(masks: *mut Self::Storage, count: usize);
    /// # Safety
    ///
    /// `masks` must be valid for the selected chunk and element.
    unsafe fn store_mask(
        masks: *mut Self::Storage,
        chunk: usize,
        element: usize,
        mask: V::MaskType,
    );
    /// # Safety
    ///
    /// `masks` must be valid for the selected chunk.
    unsafe fn store_integral_mask(masks: *mut Self::Storage, chunk: usize, mask: V::ImaskType);
    /// # Safety
    ///
    /// `masks` must be valid for the selected chunk, element, and lane.
    unsafe fn store_tail_lane(
        masks: *mut Self::Storage,
        chunk: usize,
        element: usize,
        lane: usize,
        active: bool,
    );
    /// # Safety
    ///
    /// `masks` must be valid for the selected chunk and element.
    unsafe fn load_mask(masks: *const Self::Storage, chunk: usize, element: usize) -> V::MaskType;
    /// # Safety
    ///
    /// `masks` must be valid for the selected chunk, element, and lane.
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

pub(super) fn validate_integral_mask_vector<V: StaticSimdVector>(helper_name: &str) -> usize
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

pub(super) fn scalar_mask_from_bool<Profile, T>(active: bool) -> <Simd<T, Scalar> as SimdVector>::MaskType
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

pub(super) unsafe fn append_indices_from_mask<Mask>(
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

pub(super) unsafe fn append_selected_indices_from_mask<Mask>(
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

pub(super) fn validate_mask_layout_vector<V: StaticSimdVector>(helper_name: &str) -> usize
where
    V::ImaskType: IntegralMaskWord,
{
    validate_integral_mask_vector::<V>(helper_name)
}
