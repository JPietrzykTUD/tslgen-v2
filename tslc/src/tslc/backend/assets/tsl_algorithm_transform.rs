use super::*;

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

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
