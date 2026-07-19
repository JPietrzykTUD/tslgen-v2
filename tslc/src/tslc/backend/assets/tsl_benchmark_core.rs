//! Standard-library-only support for generated Rust variant benchmarks.

use std::fmt::Write as _;
use std::hint::black_box;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Options {
    pub results_path: Option<PathBuf>,
    rounds_override: Option<usize>,
    minimum_sample_ns_override: Option<u64>,
    pub self_test: bool,
}

impl Options {
    pub fn parse(arguments: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut arguments = arguments.into_iter();
        let mut options = Self {
            results_path: None,
            rounds_override: None,
            minimum_sample_ns_override: None,
            self_test: false,
        };
        while let Some(argument) = arguments.next() {
            let mut value = || {
                arguments
                    .next()
                    .ok_or_else(|| format!("missing value for {argument}"))
            };
            match argument.as_str() {
                "--results" => options.results_path = Some(PathBuf::from(value()?)),
                "--rounds" => {
                    let rounds = value()?
                        .parse::<usize>()
                        .map_err(|_| "--rounds must be an integer".to_string())?;
                    if rounds < 3 {
                        return Err("--rounds must be at least 3".to_string());
                    }
                    options.rounds_override = Some(rounds);
                }
                "--minimum-sample-ns" => {
                    let minimum = value()?
                        .parse::<u64>()
                        .map_err(|_| "--minimum-sample-ns must be an integer".to_string())?;
                    if minimum == 0 {
                        return Err("--minimum-sample-ns must be positive".to_string());
                    }
                    options.minimum_sample_ns_override = Some(minimum);
                }
                "--self-test" => options.self_test = true,
                // Cargo appends this libtest-compatible marker to `cargo bench`
                // invocations even when the custom target has `harness = false`.
                "--bench" => {}
                _ => return Err(format!("unknown benchmark option: {argument}")),
            }
        }
        Ok(options)
    }

    pub fn rounds(&self, default: usize) -> usize {
        self.rounds_override.unwrap_or(default)
    }

    pub fn minimum_sample_ns(&self, default: u64) -> u64 {
        self.minimum_sample_ns_override.unwrap_or(default)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RawSample {
    pub stable_id: &'static str,
    pub scenario: &'static str,
    pub candidate: &'static str,
    pub round: usize,
    pub iterations: usize,
    pub elapsed_ns: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReportMetadata {
    pub protocol_version: u32,
    pub profile: &'static str,
    pub manifest_hash: &'static str,
}

pub fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

pub trait BenchmarkValue: Copy + Default + PartialEq {
    fn bounded(bits: u64) -> Self;
    fn shift_count(bits: u64) -> Self;
}

macro_rules! signed_benchmark_value {
    ($($ty:ty),* $(,)?) => {$(
        impl BenchmarkValue for $ty {
            fn bounded(bits: u64) -> Self {
                let limit = (<$ty>::MAX as i64).min(1000);
                ((bits % (2 * limit + 1) as u64) as i64 - limit) as Self
            }

            fn shift_count(bits: u64) -> Self {
                (bits % (std::mem::size_of::<Self>() as u64 * 8)) as Self
            }
        }
    )*};
}

macro_rules! unsigned_benchmark_value {
    ($($ty:ty),* $(,)?) => {$(
        impl BenchmarkValue for $ty {
            fn bounded(bits: u64) -> Self {
                let limit = (<$ty>::MAX as u64).min(2000);
                (bits % (limit + 1)) as Self
            }

            fn shift_count(bits: u64) -> Self {
                (bits % (std::mem::size_of::<Self>() as u64 * 8)) as Self
            }
        }
    )*};
}

macro_rules! float_benchmark_value {
    ($($ty:ty),* $(,)?) => {$(
        impl BenchmarkValue for $ty {
            fn bounded(bits: u64) -> Self {
                let centered = (bits % 20_001) as i64 - 10_000;
                centered as Self / 257.0
            }

            fn shift_count(bits: u64) -> Self {
                (bits % (std::mem::size_of::<Self>() as u64 * 8)) as Self
            }
        }
    )*};
}

signed_benchmark_value!(i8, i16, i32, i64);
unsigned_benchmark_value!(u8, u16, u32, u64);
float_benchmark_value!(f32, f64);

pub fn next_value<T: BenchmarkValue>(state: &mut u64) -> T {
    T::bounded(splitmix64(state))
}

pub fn next_nonzero_value<T: BenchmarkValue>(state: &mut u64) -> T {
    loop {
        let value = next_value::<T>(state);
        if value != T::default() {
            return value;
        }
    }
}

pub fn next_shift_count<T: BenchmarkValue>(state: &mut u64) -> T {
    T::shift_count(splitmix64(state))
}

pub fn elapsed_ns(begin: Instant, end: Instant) -> u64 {
    duration_ns(end.saturating_duration_since(begin))
}

fn duration_ns(duration: Duration) -> u64 {
    duration.as_nanos().min(u64::MAX as u128) as u64
}

pub fn calibrate(
    mut measure: impl FnMut(usize) -> Result<u64, String>,
    minimum_sample_ns: u64,
) -> Result<usize, String> {
    let mut iterations = 1usize;
    while measure(iterations)? < minimum_sample_ns {
        if iterations > (1usize << 30) {
            return Err("benchmark calibration exceeded iteration limit".to_string());
        }
        iterations *= 2;
    }
    Ok(iterations)
}

pub fn candidate_order(candidate_count: usize, schedule: u64) -> Result<Vec<usize>, String> {
    if candidate_count == 0 {
        return Err("benchmark candidate schedule cannot be empty".to_string());
    }
    let reverse = schedule & 1 != 0;
    let rotation = ((schedule >> 1) as usize) % candidate_count;
    Ok((0..candidate_count)
        .map(|offset| {
            let ordered = if reverse {
                candidate_count - 1 - offset
            } else {
                offset
            };
            (rotation + ordered) % candidate_count
        })
        .collect())
}

pub fn json_escape(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len() + 8);
    for character in value.chars() {
        match character {
            '\\' => escaped.push_str("\\\\"),
            '"' => escaped.push_str("\\\""),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            character if character <= '\u{1f}' => {
                write!(&mut escaped, "\\u{:04x}", character as u32).unwrap();
            }
            character => escaped.push(character),
        }
    }
    escaped
}

pub fn write_samples(
    samples: &[RawSample],
    metadata: ReportMetadata,
    results_path: Option<&Path>,
) -> Result<(), String> {
    let mut document = String::new();
    for sample in samples {
        writeln!(
            &mut document,
            concat!(
                "{{\"backend\":\"rust\",\"protocol_version\":{},",
                "\"profile\":\"{}\",\"manifest_hash\":\"{}\",",
                "\"stable_id\":\"{}\",\"scenario\":\"{}\",",
                "\"candidate\":\"{}\",\"round\":{},\"iterations\":{},",
                "\"elapsed_ns\":{}}}"
            ),
            metadata.protocol_version,
            json_escape(metadata.profile),
            json_escape(metadata.manifest_hash),
            json_escape(sample.stable_id),
            json_escape(sample.scenario),
            json_escape(sample.candidate),
            sample.round,
            sample.iterations,
            sample.elapsed_ns,
        )
        .unwrap();
    }
    if let Some(path) = results_path {
        std::fs::write(path, document)
            .map_err(|error| format!("cannot write benchmark results {}: {error}", path.display()))
    } else {
        let mut output = std::io::stdout().lock();
        output
            .write_all(document.as_bytes())
            .and_then(|()| output.flush())
            .map_err(|error| format!("cannot write benchmark results: {error}"))
    }
}

pub fn runtime_self_test() -> Result<(), String> {
    let options = Options::parse([
        "--rounds".to_string(),
        "3".to_string(),
        "--minimum-sample-ns".to_string(),
        "1".to_string(),
        "--self-test".to_string(),
    ])?;
    if options.rounds(9) != 3 || options.minimum_sample_ns(9) != 1 || !options.self_test {
        return Err("benchmark option self-test failed".to_string());
    }
    let mut first_state = 7;
    let mut second_state = 7;
    let first = next_value::<i16>(&mut first_state);
    if first != next_value::<i16>(&mut second_state) || first_state != second_state {
        return Err("benchmark generator self-test failed".to_string());
    }
    if next_nonzero_value::<i8>(&mut first_state) == 0 {
        return Err("benchmark nonzero generator self-test failed".to_string());
    }
    let mut order = candidate_order(3, 5)?;
    order.sort_unstable();
    if order != [0, 1, 2] {
        return Err("benchmark schedule self-test failed".to_string());
    }
    if calibrate(|iterations| Ok(iterations as u64 * 10), 35)? != 4 {
        return Err("benchmark calibration self-test failed".to_string());
    }
    if json_escape("a\n\"b\\") != "a\\n\\\"b\\\\" {
        return Err("benchmark JSON self-test failed".to_string());
    }
    black_box(first);
    Ok(())
}
