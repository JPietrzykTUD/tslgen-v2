use super::*;

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_predicate_unary}
pub fn predicate_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &mut [<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
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
@{check_predicate_unary}
    Ok(unsafe {
        predicate_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_predicate_binary}
pub fn predicate_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &mut [<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
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
@{check_predicate_binary}
    Ok(unsafe {
        predicate_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_predicate_unary_mask_layout}
pub fn predicate_unary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &mut [<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> Result<usize, crate::PreconditionError>
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
@{check_predicate_unary_mask_layout}
    Ok(unsafe {
        predicate_unary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_mut_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_predicate_binary_mask_layout}
pub fn predicate_binary_mask_layout_checked<Profile, Policy, Layout, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &mut [<Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::Storage],
) -> Result<usize, crate::PreconditionError>
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
@{check_predicate_binary_mask_layout}
    Ok(unsafe {
        predicate_binary_mask_layout_raw::<Profile, Policy, Layout, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_mut_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
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
