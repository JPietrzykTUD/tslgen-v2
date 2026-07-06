use tsl_generated::tsl_core::StaticSimdVector;
use tsl_generated::tsl_scalar as tsl;

struct ChunkSum {
    base: *const i32,
    total: i64,
    visited: usize,
    metadata_ok: bool,
}

impl ChunkSum {
    fn new(input: &[i32]) -> Self {
        Self {
            base: input.as_ptr(),
            total: 0,
            visited: 0,
            metadata_ok: true,
        }
    }

    fn is_valid(&self, expected_total: i64, expected_count: usize) -> bool {
        self.metadata_ok && self.total == expected_total && self.visited == expected_count
    }
}

impl<V> tsl::algo::ChunkKernel<V> for ChunkSum
where
    V: StaticSimdVector<BaseType = i32>
        + tsl::detail::primitives::LoadImpl<false>
        + tsl::detail::primitives::HaddImpl,
{
    unsafe fn apply(&mut self, ptr: *const V::BaseType, offset: usize, count: usize) {
        let expected_ptr = unsafe { self.base.add(offset) };
        if ptr != expected_ptr || count != V::ELEMENT_COUNT {
            self.metadata_ok = false;
        }

        let values = unsafe { tsl::load::<V, false>(ptr) };
        self.total += i64::from(tsl::hadd::<V>(values));
        self.visited += count;
    }
}

fn fill_input(input: &mut [i32]) {
    for (i, value) in input.iter_mut().enumerate() {
        *value = ((i * 29) % 73) as i32 - 36;
    }
}

fn expected_sum(input: &[i32]) -> i64 {
    input.iter().map(|value| i64::from(*value)).sum()
}

fn main() {
    let mut input = vec![0i32; 1003];
    fill_input(&mut input);
    let expected = expected_sum(&input);

    let mut native = ChunkSum::new(&input);
    tsl::algo::for_each_chunk(tsl::algo::parallelism::native(), &mut native, &input);
    assert!(native.is_valid(expected, input.len()));

    let mut fixed = ChunkSum::new(&input);
    tsl::algo::for_each_chunk(tsl::algo::parallelism::fixed::<1>(), &mut fixed, &input);
    assert!(fixed.is_valid(expected, input.len()));

    let mut generic4 = ChunkSum::new(&input);
    tsl::algo::for_each_chunk(
        tsl::algo::parallelism::generic::<4>(),
        &mut generic4,
        &input,
    );
    assert!(generic4.is_valid(expected, input.len()));

    let mut generic16 = ChunkSum::new(&input);
    tsl::algo::for_each_chunk(
        tsl::algo::parallelism::generic::<16>(),
        &mut generic16,
        &input,
    );
    assert!(generic16.is_valid(expected, input.len()));
}
