use super::*;

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

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
