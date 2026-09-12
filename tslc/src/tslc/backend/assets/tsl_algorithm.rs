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
use self::validation::{chunk_count_for_lanes, selected_address_error};
#[allow(unused_imports)]
pub(crate) use self::validation::{selected_row_pointer, selected_row_scale};

#[doc(hidden)]
mod utility;
pub use self::utility::{
@{algorithm_utility_reexports}
};

#[doc(hidden)]
mod iteration;
pub use self::iteration::{
@{algorithm_iteration_reexports}
};

#[doc(hidden)]
mod predicate;
pub use self::predicate::{
@{algorithm_predicate_reexports}
};

#[doc(hidden)]
mod count;
pub use self::count::{
@{algorithm_count_reexports}
};

#[doc(hidden)]
mod select;
pub use self::select::{
@{algorithm_select_reexports}
};

#[doc(hidden)]
mod transform;
pub use self::transform::{
@{algorithm_transform_reexports}
};

#[doc(hidden)]
mod consume;
pub use self::consume::{
@{algorithm_consume_reexports}
};

#[doc(hidden)]
mod aggregate;
pub use self::aggregate::{
@{algorithm_aggregate_reexports}
};
