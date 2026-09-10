use super::*;

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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_unary}
pub fn select_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_unary}
    Ok(unsafe {
        select_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_binary}
pub fn select_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_binary}
    Ok(unsafe {
        select_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_unary}
pub fn select_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_unary}
    Ok(unsafe {
        select_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_binary}
pub fn select_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_binary}
    Ok(unsafe {
        select_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_unary_mask_layout}
pub fn select_masked_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_unary_mask_layout}
    Ok(unsafe {
        select_masked_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_binary_mask_layout}
pub fn select_masked_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_binary_mask_layout}
    Ok(unsafe {
        select_masked_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            output.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_indices_unary}
pub fn select_indices_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_indices_unary}
    Ok(unsafe {
        select_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_indices_binary}
pub fn select_indices_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_indices_binary}
    Ok(unsafe {
        select_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_indices_unary}
pub fn select_masked_indices_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_indices_unary}
    Ok(unsafe {
        select_masked_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_indices_binary}
pub fn select_masked_indices_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_indices_binary}
    Ok(unsafe {
        select_masked_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_indices_unary_mask_layout}
pub fn select_masked_indices_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_indices_unary_mask_layout}
    Ok(unsafe {
        select_masked_indices_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_masked_indices_binary_mask_layout}
pub fn select_masked_indices_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_masked_indices_binary_mask_layout}
    Ok(unsafe {
        select_masked_indices_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            indices.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_selected_indices_unary}
pub fn select_selected_indices_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    input_indices: &[usize],
    output_indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_selected_indices_unary}
    Ok(unsafe {
        select_selected_indices_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            input_indices.as_ptr(),
            output_indices.as_mut_ptr(),
            input_indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_select_selected_indices_binary}
pub fn select_selected_indices_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    input_indices: &[usize],
    output_indices: &mut [usize],
) -> Result<usize, crate::PreconditionError>
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
@{check_select_selected_indices_binary}
    Ok(unsafe {
        select_selected_indices_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            input_indices.as_ptr(),
            output_indices.as_mut_ptr(),
            input_indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_selected_unary}
pub fn transform_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
@{check_transform_selected_unary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_selected_binary}
pub fn transform_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
        + SelectedLoad<Simd<T, Scalar>, 0>
        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
@{check_transform_selected_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_selected_unary}
pub fn consume_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_selected_unary}
    unsafe {
        consume_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_selected_binary}
pub fn consume_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_selected_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_selected_unary}
pub fn aggregate_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> Result<<Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_selected_unary}
    Ok(unsafe {
        aggregate_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_selected_binary}
pub fn aggregate_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> Result<<Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_selected_binary}
    Ok(unsafe {
        aggregate_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_where_unary}
pub fn transform_where_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_where_unary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_where_binary}
pub fn transform_where_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_where_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_masked_unary}
pub fn transform_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_masked_unary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_masked_binary}
pub fn transform_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_masked_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_where_unary_mask_layout}
pub fn transform_where_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_where_unary_mask_layout}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_where_binary_mask_layout}
pub fn transform_where_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_where_binary_mask_layout}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_masked_unary_mask_layout}
pub fn transform_masked_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_masked_unary_mask_layout}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_transform_masked_binary_mask_layout}
pub fn transform_masked_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
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
@{check_transform_masked_binary_mask_layout}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Applies a unary kernel after validating that `output` covers every input.
///
/// A longer output is accepted and elements beyond `input.len()` are untouched.
/// On failure the operation is not invoked and `output` is unchanged.
@{docs_transform_unary}
pub fn transform_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + UnaryKernel<Simd<T, Scalar>>,
{
@{check_transform_unary}
    unsafe {
        transform_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Applies a binary kernel after validating every related range extent.
///
/// Longer secondary/output ranges are accepted and their suffixes are untouched.
/// On failure the operation is not invoked and `output` is unchanged.
@{docs_transform_binary}
pub fn transform_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    output: &mut [T],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec> + BinaryKernel<Simd<T, Scalar>>,
{
@{check_transform_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_binary}
pub fn consume_binary_checked<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, left: &[T], right: &[T]) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_binary}
    unsafe {
        consume_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_masked_unary}
pub fn consume_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<(), crate::PreconditionError>
where
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
@{check_consume_masked_unary}
    unsafe {
        consume_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_masked_binary}
pub fn consume_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<(), crate::PreconditionError>
where
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
@{check_consume_masked_binary}
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
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_binary}
pub fn aggregate_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
) -> Result<<Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_binary}
    Ok(unsafe {
        aggregate_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_masked_unary}
pub fn aggregate_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<<Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
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
@{check_aggregate_masked_unary}
    Ok(unsafe {
        aggregate_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_masked_binary}
pub fn aggregate_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<<Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
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
@{check_aggregate_masked_binary}
    Ok(unsafe {
        aggregate_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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
