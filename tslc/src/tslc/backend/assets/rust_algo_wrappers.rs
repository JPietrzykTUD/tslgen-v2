    pub fn transform_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
        output: &mut [T],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::transform_unary::<Profile, Policy, Op, T>(
            policy, op, input, output,
        );
    }

    pub unsafe fn transform_unary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: *const T,
        output: *mut T,
        count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, output, count,
            );
        }
    }

    pub fn transform_binary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
        output: &mut [T],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::transform_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, output,
        );
    }

    pub unsafe fn transform_binary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: *const T,
        right: *const T,
        output: *mut T,
        count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, output, count,
            );
        }
    }

    pub fn integral_mask_chunk_count<Policy, T>(
        policy: Policy,
        count: usize,
    ) -> usize
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
    {
        crate::tsl_algorithm::integral_mask_chunk_count::<Profile, Policy, T>(
            policy, count,
        )
    }

    pub fn mask_chunk_count<Policy, Layout, T>(
        policy: Policy,
        count: usize,
    ) -> usize
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
    {
        crate::tsl_algorithm::mask_chunk_count::<Profile, Policy, Layout, T>(
            policy, count,
        )
    }

    pub fn native_mask_chunk_count<Policy, T>(
        policy: Policy,
        count: usize,
    ) -> usize
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        mask_layout::Native: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
    {
        crate::tsl_algorithm::native_mask_chunk_count::<Profile, Policy, T>(
            policy, count,
        )
    }

    pub fn byte_mask_count<Policy, T>(
        policy: Policy,
        count: usize,
    ) -> usize
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        mask_layout::Bytes: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
    {
        crate::tsl_algorithm::byte_mask_count::<Profile, Policy, T>(
            policy, count,
        )
    }

    pub fn bit_mask_count<Policy, T>(
        policy: Policy,
        count: usize,
    ) -> usize
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        mask_layout::Bits: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
    {
        crate::tsl_algorithm::bit_mask_count::<Profile, Policy, T>(
            policy, count,
        )
    }

    pub fn predicate_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::predicate_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

    pub unsafe fn predicate_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::predicate_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

    pub fn predicate_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::predicate_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

    pub unsafe fn predicate_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::predicate_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }

    pub fn predicate_binary_mask_layout<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
        masks: &mut [
            <Layout as MaskLayout<
                Profile,
                <Policy as VectorFor<Profile, T>>::Vec,
            >>::Storage
        ],
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::predicate_binary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks)
    }

    pub unsafe fn predicate_binary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: *const T,
        right: *const T,
        masks: *mut <Layout as MaskLayout<
            Profile,
            <Policy as VectorFor<Profile, T>>::Vec,
        >>::Storage,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::predicate_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, count)
        }
    }

    pub fn count_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        )
    }

    pub unsafe fn count_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            )
        }
    }

    pub fn count_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_binary::<Profile, Policy, Op, T>(
            policy, op, left, right,
        )
    }

    pub unsafe fn count_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            )
        }
    }

    pub fn count_masked_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_masked_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

    pub unsafe fn count_masked_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

    pub fn count_masked_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_masked_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

    pub unsafe fn count_masked_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }

    pub fn count_masked_unary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_masked_unary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks)
    }

    pub unsafe fn count_masked_unary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_masked_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, count)
        }
    }

    pub fn count_masked_binary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_masked_binary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks)
    }

    pub unsafe fn count_masked_binary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, count)
        }
    }

    pub fn count_selected_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_selected_unary::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

    pub unsafe fn count_selected_unary_raw<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            )
        }
    }

    pub unsafe fn count_selected_unary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
            + IntegralMask<Simd<T, Scalar>>,
        Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryPredicateKernel<Simd<T, Scalar>>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count)
        }
    }

    pub fn count_selected_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::count_selected_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

    pub unsafe fn count_selected_binary_raw<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            )
        }
    }

    pub unsafe fn count_selected_binary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
            + IntegralMask<Simd<T, Scalar>>,
        Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryPredicateKernel<Simd<T, Scalar>>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::count_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count)
        }
    }

    pub fn select_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_unary::<Profile, Policy, Op, T>(
            policy, op, input, output,
        )
    }

    pub unsafe fn select_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, output, count,
            )
        }
    }

    pub fn select_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, output,
        )
    }

    pub unsafe fn select_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, output, count,
            )
        }
    }

    pub fn select_masked_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        )
    }

    pub unsafe fn select_masked_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            )
        }
    }

    pub fn select_masked_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        )
    }

    pub unsafe fn select_masked_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            )
        }
    }

    pub fn select_masked_unary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_unary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, output)
    }

    pub unsafe fn select_masked_unary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, output, count)
        }
    }

    pub fn select_masked_binary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_binary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, output)
    }

    pub unsafe fn select_masked_binary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:
            Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType: Copy,
        <Simd<T, Scalar> as SimdVector>::RegisterType: Copy,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, output, count)
        }
    }

    pub fn select_indices_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_indices_unary::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

    pub unsafe fn select_indices_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, count,
            )
        }
    }

    pub fn select_indices_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_indices_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

    pub unsafe fn select_indices_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, count,
            )
        }
    }

    pub fn select_masked_indices_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_indices_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks, indices,
        )
    }

    pub unsafe fn select_masked_indices_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, indices, count,
            )
        }
    }

    pub fn select_masked_indices_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_indices_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, indices,
        )
    }

    pub unsafe fn select_masked_indices_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, indices, count,
            )
        }
    }

    pub fn select_masked_indices_unary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_indices_unary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, indices)
    }

    pub unsafe fn select_masked_indices_unary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_indices_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, indices, count)
        }
    }

    pub fn select_masked_indices_binary_mask_layout<Policy, Layout, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_masked_indices_binary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, indices)
    }

    pub unsafe fn select_masked_indices_binary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_masked_indices_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, indices, count)
        }
    }

    pub fn select_selected_indices_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_selected_indices_unary::<Profile, Policy, Op, T>(
            policy, op, input, input_indices, output_indices,
        )
    }

    pub unsafe fn select_selected_indices_unary_raw<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_selected_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, input_indices, output_indices, selected_count,
            )
        }
    }

    pub unsafe fn select_selected_indices_unary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
            + IntegralMask<Simd<T, Scalar>>,
        Op: UnaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryPredicateKernel<Simd<T, Scalar>>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_selected_indices_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, input_indices, output_indices, selected_count)
        }
    }

    pub fn select_selected_indices_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::select_selected_indices_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, input_indices, output_indices,
        )
    }

    pub unsafe fn select_selected_indices_binary_raw<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_selected_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, input_indices, output_indices, selected_count,
            )
        }
    }

    pub unsafe fn select_selected_indices_binary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>
            + IntegralMask<Simd<T, Scalar>>,
        Op: BinaryPredicateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryPredicateKernel<Simd<T, Scalar>>,
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::select_selected_indices_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(
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

    pub fn transform_selected_unary<Policy, Op, T>(
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
        Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::transform_selected_unary::<Profile, Policy, Op, T>(
            policy, op, input, indices, output,
        );
    }

    pub unsafe fn transform_selected_unary_raw<Policy, Op, T>(
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
        Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, output, selected_count,
            );
        }
    }

    pub unsafe fn transform_selected_unary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, output, selected_count);
        }
    }

    pub fn transform_selected_binary<Policy, Op, T>(
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
        Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::transform_selected_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, indices, output,
        );
    }

    pub unsafe fn transform_selected_binary_raw<Policy, Op, T>(
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
        Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, output, selected_count,
            );
        }
    }

    pub unsafe fn transform_selected_binary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>
            + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::transform_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, output, selected_count);
        }
    }

    pub fn consume_selected_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
        indices: &[usize],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryConsumeKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::consume_selected_unary::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        );
    }

    pub unsafe fn consume_selected_unary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: *const T,
        indices: *const usize,
        selected_count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryConsumeKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::consume_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            );
        }
    }

    pub unsafe fn consume_selected_unary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
        policy: Policy,
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
        unsafe {
            crate::tsl_algorithm::consume_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count);
        }
    }

    pub fn consume_selected_binary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
        indices: &[usize],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryConsumeKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::consume_selected_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        );
    }

    pub unsafe fn consume_selected_binary_raw<Policy, Op, T>(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryConsumeKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::consume_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            );
        }
    }

    pub unsafe fn consume_selected_binary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>,
        Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryConsumeKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::consume_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count);
        }
    }

    pub fn aggregate_selected_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
        indices: &[usize],
    ) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryAggregateKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::aggregate_selected_unary::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

    pub unsafe fn aggregate_selected_unary_raw<Policy, Op, T>(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            )
        }
    }

    pub unsafe fn aggregate_selected_unary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>,
        Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count)
        }
    }

    pub fn aggregate_selected_binary<Policy, Op, T>(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryAggregateKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::aggregate_selected_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

    pub unsafe fn aggregate_selected_binary_raw<Policy, Op, T>(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0>
            + SelectedLoad<Simd<T, Scalar>, 0>,
        Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            )
        }
    }

    pub unsafe fn aggregate_selected_binary_scaled_raw<
        const SCALE: u32,
        Policy,
        Op,
        T,
    >(
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
        Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
            + SelectedLoad<Simd<T, Scalar>, SCALE>,
        Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count)
        }
    }

    pub fn transform_where_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_where_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        );
    }

    pub unsafe fn transform_where_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_where_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            );
        }
    }

    pub fn transform_where_unary_mask_layout<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
        masks: &[
            <Layout as MaskLayout<
                Profile,
                <Policy as VectorFor<Profile, T>>::Vec,
            >>::Storage
        ],
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_where_unary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, output);
    }

    pub unsafe fn transform_where_unary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: *const T,
        masks: *const <Layout as MaskLayout<
            Profile,
            <Policy as VectorFor<Profile, T>>::Vec,
        >>::Storage,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_where_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, output, count);
        }
    }

    pub fn transform_where_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_where_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        );
    }

    pub unsafe fn transform_where_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_where_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            );
        }
    }

    pub fn transform_masked_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_masked_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        );
    }

    pub unsafe fn transform_masked_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            );
        }
    }

    pub fn transform_masked_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_masked_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        );
    }

    pub unsafe fn transform_masked_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            );
        }
    }

    pub fn transform_masked_binary_mask_layout<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
        masks: &[
            <Layout as MaskLayout<
                Profile,
                <Policy as VectorFor<Profile, T>>::Vec,
            >>::Storage
        ],
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::transform_masked_binary_mask_layout::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, output);
    }

    pub unsafe fn transform_masked_binary_mask_layout_raw<Policy, Layout, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: *const T,
        right: *const T,
        masks: *const <Layout as MaskLayout<
            Profile,
            <Policy as VectorFor<Profile, T>>::Vec,
        >>::Storage,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::transform_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, output, count);
        }
    }

    pub fn consume_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryConsumeKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::consume_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        );
    }

    pub unsafe fn consume_unary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: *const T,
        count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryConsumeKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::consume_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            );
        }
    }

    pub fn consume_binary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryConsumeKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::consume_binary::<Profile, Policy, Op, T>(
            policy, op, left, right,
        );
    }

    pub unsafe fn consume_binary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: *const T,
        right: *const T,
        count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryConsumeKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::consume_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            );
        }
    }

    pub fn consume_masked_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::consume_masked_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        );
    }

    pub unsafe fn consume_masked_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::consume_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            );
        }
    }

    pub fn consume_masked_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::consume_masked_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        );
    }

    pub unsafe fn consume_masked_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::consume_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            );
        }
    }

    pub fn aggregate_unary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: &[T],
    ) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryAggregateKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::aggregate_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        )
    }

    pub unsafe fn aggregate_unary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        input: *const T,
        count: usize,
    ) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + UnaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            )
        }
    }

    pub fn aggregate_binary<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: &[T],
        right: &[T],
    ) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryAggregateKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::aggregate_binary::<Profile, Policy, Op, T>(
            policy, op, left, right,
        )
    }

    pub unsafe fn aggregate_binary_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        left: *const T,
        right: *const T,
        count: usize,
    ) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
    where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
            + LoadStore<Simd<T, Scalar>>,
        Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + BinaryAggregateKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            )
        }
    }

    pub fn aggregate_masked_unary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::aggregate_masked_unary::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

    pub unsafe fn aggregate_masked_unary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

    pub fn aggregate_masked_binary<Policy, Op, T>(
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        crate::tsl_algorithm::aggregate_masked_binary::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

    pub unsafe fn aggregate_masked_binary_raw<Policy, Op, T>(
        policy: Policy,
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
        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType:
            IntegralMaskWord,
        <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
    {
        unsafe {
            crate::tsl_algorithm::aggregate_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }

    pub fn for_each_chunk<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        data: &[T],
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + ChunkKernel<Simd<T, Scalar>>,
    {
        crate::tsl_algorithm::for_each_chunk::<Profile, Policy, Op, T>(
            policy, op, data,
        );
    }

    pub unsafe fn for_each_chunk_raw<Policy, Op, T>(
        policy: Policy,
        op: &mut Op,
        data: *const T,
        count: usize,
    ) where
        Policy: VectorFor<Profile, T>,
        <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
        Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
        Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec>
            + ChunkKernel<Simd<T, Scalar>>,
    {
        unsafe {
            crate::tsl_algorithm::for_each_chunk_raw::<Profile, Policy, Op, T>(
                policy, op, data, count,
            );
        }
    }
