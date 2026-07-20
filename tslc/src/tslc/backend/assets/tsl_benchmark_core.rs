//! Standard-library-only mechanics for generated Rust variant benchmarks.

use std::fmt::Write as _;
use std::path::{Component, Path, PathBuf};
use std::time::{Duration, Instant};

#[derive(Clone, Debug, PartialEq)]
pub struct Options {
    pub results_path: Option<PathBuf>,
    pub summary_path: Option<PathBuf>,
    pub policy_json_path: Option<PathBuf>,
    rounds_override: Option<usize>,
    minimum_sample_ns_override: Option<u64>,
    threshold: f64,
    pub self_test: bool,
    pub help: bool,
}

impl Options {
    pub fn parse(arguments: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut arguments = arguments.into_iter();
        let mut options = Self {
            results_path: None,
            summary_path: None,
            policy_json_path: None,
            rounds_override: None,
            minimum_sample_ns_override: None,
            threshold: 0.05,
            self_test: false,
            help: false,
        };
        while let Some(argument) = arguments.next() {
            let mut value = || {
                arguments
                    .next()
                    .ok_or_else(|| format!("missing value for {argument}"))
            };
            match argument.as_str() {
                "--results" => options.results_path = Some(PathBuf::from(value()?)),
                "--summary" => options.summary_path = Some(PathBuf::from(value()?)),
                "--policy-json" => {
                    options.policy_json_path = Some(PathBuf::from(value()?));
                }
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
                "--threshold" => {
                    let threshold = value()?
                        .parse::<f64>()
                        .map_err(|_| "--threshold must be a number".to_string())?;
                    if !threshold.is_finite() || !(0.0..1.0).contains(&threshold) {
                        return Err("--threshold must be finite and in [0, 1)".to_string());
                    }
                    options.threshold = threshold;
                }
                "--self-test" => options.self_test = true,
                "--help" | "-h" => options.help = true,
                // Cargo appends this libtest-compatible marker to `cargo bench`
                // invocations even when the custom target has `harness = false`.
                "--bench" => {}
                _ => return Err(format!("unknown benchmark option: {argument}")),
            }
        }
        let paths = [
            options.results_path.as_ref(),
            options.summary_path.as_ref(),
            options.policy_json_path.as_ref(),
        ]
        .into_iter()
        .flatten()
        .map(|path| output_identity(path))
        .collect::<Result<Vec<_>, _>>()?;
        if paths
            .iter()
            .enumerate()
            .any(|(index, path)| paths[index + 1..].contains(path))
        {
            return Err("benchmark output paths must be distinct".to_string());
        }
        Ok(options)
    }

    pub fn rounds(&self, default: usize) -> usize {
        self.rounds_override.unwrap_or(default)
    }

    pub fn minimum_sample_ns(&self, default: u64) -> u64 {
        self.minimum_sample_ns_override.unwrap_or(default)
    }

    pub fn threshold(&self) -> f64 {
        self.threshold
    }

    pub fn rounds_override(&self) -> Option<usize> {
        self.rounds_override
    }

    pub fn minimum_sample_ns_override(&self) -> Option<u64> {
        self.minimum_sample_ns_override
    }
}

pub(crate) fn output_identity(path: &Path) -> Result<PathBuf, String> {
    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|error| format!("cannot resolve benchmark output path: {error}"))?
            .join(path)
    };
    if let Ok(canonical) = std::fs::canonicalize(&absolute) {
        return Ok(canonical);
    }
    if let (Some(parent), Some(file_name)) = (absolute.parent(), absolute.file_name()) {
        if let Ok(canonical_parent) = std::fs::canonicalize(parent) {
            return Ok(canonical_parent.join(file_name));
        }
    }
    let mut normalized = PathBuf::new();
    for component in absolute.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            _ => normalized.push(component.as_os_str()),
        }
    }
    Ok(normalized)
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
