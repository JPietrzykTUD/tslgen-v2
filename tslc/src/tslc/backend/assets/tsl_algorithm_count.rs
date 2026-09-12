use super::*;

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_binary}
pub fn count_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
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
@{check_count_binary}
    Ok(unsafe {
        count_binary_raw::<Profile, Policy, Op, T>(
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_masked_unary}
pub fn count_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
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
@{check_count_masked_unary}
    Ok(unsafe {
        count_masked_unary_raw::<Profile, Policy, Op, T>(
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_masked_binary}
pub fn count_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
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
@{check_count_masked_binary}
    Ok(unsafe {
        count_masked_binary_raw::<Profile, Policy, Op, T>(
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_masked_unary_mask_layout}
pub fn count_masked_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
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
@{check_count_masked_unary_mask_layout}
    Ok(unsafe {
        count_masked_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_masked_binary_mask_layout}
pub fn count_masked_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
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
@{check_count_masked_binary_mask_layout}
    Ok(unsafe {
        count_masked_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_selected_unary}
pub fn count_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
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
@{check_count_selected_unary}
    Ok(unsafe {
        count_selected_unary_raw::<Profile, Policy, Op, T>(
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_count_selected_binary}
pub fn count_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
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
@{check_count_selected_binary}
    Ok(unsafe {
        count_selected_binary_raw::<Profile, Policy, Op, T>(
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

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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
