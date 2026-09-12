fn main() {
    let answer =
        tsl::profile::algo::add::<_, i32>(tsl::dataparallel::fixed::<1>(), 20, 22);
    assert_eq!(answer, 42);
}
