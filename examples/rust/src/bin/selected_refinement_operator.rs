use tsl::profile;
use tsl::tsl_core::StaticSimdVector;

struct LessThan;

impl<V> profile::algo::BinaryPredicateKernel<V> for LessThan
where
    V: StaticSimdVector<BaseType = i32> + profile::detail::primitives::Less_thanImpl,
{
    fn test(&mut self, left: V::RegisterType, right: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(left, right)
    }
}

struct Negative;

impl<V> profile::algo::UnaryPredicateKernel<V> for Negative
where
    V: StaticSimdVector<BaseType = i32>
        + profile::detail::primitives::Less_thanImpl
        + profile::detail::primitives::Set1Impl,
{
    fn test(&mut self, value: V::RegisterType) -> V::MaskType {
        profile::less_than::<V>(value, profile::set1::<V>(0))
    }
}

fn fill_inputs(left: &mut [i32], right: &mut [i32]) {
    for (i, (left_value, right_value)) in left.iter_mut().zip(right.iter_mut()).enumerate() {
        *left_value = ((i * 19) % 67) as i32 - 33;
        *right_value = ((i * 5) % 37) as i32 - 18;
    }
}

fn make_selection(count: usize) -> Vec<usize> {
    let mut indices = Vec::new();
    for row in (0..count).rev() {
        if row % 2 == 0 || row % 7 == 0 {
            indices.push(row);
        }
    }
    indices
}

fn verify_refined_indices<F>(
    input_indices: &[usize],
    output_indices: &[usize],
    produced: usize,
    sentinel: usize,
    mut predicate: F,
) where
    F: FnMut(usize) -> bool,
{
    let mut expected_count = 0usize;
    for &row in input_indices {
        if predicate(row) {
            assert_eq!(output_indices[expected_count], row);
            expected_count += 1;
        }
    }
    assert_eq!(produced, expected_count);
    for value in output_indices.iter().skip(produced) {
        assert_eq!(*value, sentinel);
    }
}

fn main() {
    const COUNT: usize = 1003;
    const SENTINEL: usize = 999_999;

    let mut left = vec![0i32; COUNT];
    let mut right = vec![0i32; COUNT];
    fill_inputs(&mut left, &mut right);
    let indices = make_selection(COUNT);

    macro_rules! run_policy {
        ($policy:expr) => {{
            let policy = $policy;

            let mut refined = vec![SENTINEL; indices.len()];
            let mut negative = Negative;
            let produced = profile::algo::select_selected_indices_unary(
                policy,
                &mut negative,
                &left,
                &indices,
                &mut refined,
            );
            verify_refined_indices(&indices, &refined, produced, SENTINEL, |row| left[row] < 0);

            refined.fill(SENTINEL);
            let mut less_than = LessThan;
            let produced = profile::algo::select_selected_indices_binary(
                policy,
                &mut less_than,
                &left,
                &right,
                &indices,
                &mut refined,
            );
            verify_refined_indices(&indices, &refined, produced, SENTINEL, |row| {
                left[row] < right[row]
            });

            refined.fill(SENTINEL);
            let mut scaled_less_than = LessThan;
            let produced = unsafe {
                profile::algo::select_selected_indices_binary_scaled_raw::<4, _, _, _>(
                    policy,
                    &mut scaled_less_than,
                    left.as_ptr(),
                    right.as_ptr(),
                    indices.as_ptr(),
                    refined.as_mut_ptr(),
                    indices.len(),
                )
            };
            verify_refined_indices(&indices, &refined, produced, SENTINEL, |row| {
                left[row] < right[row]
            });
        }};
    }

    run_policy!(tsl::dataparallel::fixed::<1>());
    run_policy!(tsl::dataparallel::generic::<4>());
    run_policy!(tsl::dataparallel::generic::<16>());
}
