use crate::tsl_core::{Scalar, Simd, SimdVector, StaticSimdVector};

#[doc(hidden)]
mod representation;
pub use self::representation::{dataparallel, RebindBase, ReboundBase, VectorFor};

#[doc(hidden)]
mod masks;
pub use self::masks::{
    mask_layout, IntegralMask, IntegralMaskWord, MaskFromIntegral, MaskLayout,
};
use self::masks::{
    append_indices_from_mask, append_selected_indices_from_mask, scalar_mask_from_bool,
    validate_integral_mask_vector, validate_mask_layout_vector,
};

#[doc(hidden)]
mod kernel_traits;
pub use self::kernel_traits::{
    BinaryAggregateKernel, BinaryConsumeKernel, BinaryKernel, BinaryPredicateKernel, ChunkKernel,
    CompressStore, LoadStore, MaskPopulationCount, MaskedBinaryAggregateKernel,
    MaskedBinaryConsumeKernel, MaskedBinaryKernel, MaskedStore, MaskedUnaryAggregateKernel,
    MaskedUnaryConsumeKernel, MaskedUnaryKernel, SelectedLoad, UnaryAggregateKernel,
    UnaryConsumeKernel, UnaryKernel, UnaryPredicateKernel,
};

#[doc(hidden)]
mod validation;
use self::validation::{
    chunk_count_for_lanes, selected_address_error,
};
#[allow(unused_imports)]
pub(crate) use self::validation::{selected_row_pointer, selected_row_scale};

#[doc(hidden)]
mod families;
pub use self::families::{
@{algorithm_family_reexports}
};
