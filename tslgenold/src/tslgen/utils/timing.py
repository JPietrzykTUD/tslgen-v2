from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from functools import wraps
from threading import Lock, local
from time import perf_counter_ns
from typing import Any, Callable


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"Invalid boolean value {value!r}. "
        f"Use one of: 1,0,true,false,yes,no,on,off."
    )


def _parse_positive_int(value: str | None, default: int) -> int:
    if value is None:
        return default

    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"Expected integer >= 1, got {parsed}.")
    return parsed


class _TimingConfig:
    """
    Global defaults. These are read by TimedMeta at class creation time.
    """

    def __init__(self) -> None:
        self.enabled: bool = _parse_bool(os.getenv("ENABLE_TIMING"), False)
        self.sample_every: int = _parse_positive_int(
            os.getenv("TIMING_SAMPLE_EVERY"), 1
        )


TIMING_CONFIG = _TimingConfig()


def configure_timing_defaults(
    *,
    enabled: bool | None = None,
    sample_every: int | None = None,
) -> None:
    """
    Update global defaults that TimedMeta uses for newly created classes.

    Call this BEFORE defining or importing timed classes if you want
    zero overhead when timing is disabled.
    """
    if enabled is not None:
        TIMING_CONFIG.enabled = bool(enabled)

    if sample_every is not None:
        if sample_every < 1:
            raise ValueError(f"sample_every must be >= 1, got {sample_every}.")
        TIMING_CONFIG.sample_every = int(sample_every)


def add_timing_args(parser: argparse.ArgumentParser) -> None:
    """
    Add global timing switches to an argparse parser.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--timing",
        dest="timing_enabled",
        action="store_true",
        help="Enable timing instrumentation for newly created timed classes.",
    )
    group.add_argument(
        "--no-timing",
        dest="timing_enabled",
        action="store_false",
        help="Disable timing instrumentation for newly created timed classes.",
    )

    parser.set_defaults(timing_enabled=None)

    parser.add_argument(
        "--timing-sample-every",
        dest="timing_sample_every",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Time only every Nth call for newly created timed classes. "
            "N=1 means exact timing of every call."
        ),
    )


def configure_timing_from_args(args: argparse.Namespace) -> None:
    """
    Apply argparse values to the global timing defaults.

    Must be called BEFORE defining or importing classes that use TimedMeta
    if you want instrumentation to be skipped entirely when disabled.
    """
    enabled = getattr(args, "timing_enabled", None)
    sample_every = getattr(args, "timing_sample_every", None)
    configure_timing_defaults(enabled=enabled, sample_every=sample_every)


@dataclass
class TimingStat:
    # Estimated logical calls. Exact when sample_every == 1.
    calls: int = 0

    # How many calls were actually timed.
    sampled_calls: int = 0

    # Estimated total EXCLUSIVE time. Exact when sample_every == 1.
    total_ns: int = 0

    # Max of observed sampled exclusive calls only; not scaled.
    max_ns: int = 0

    @property
    def total_ms(self) -> float:
        return self.total_ns / 1_000_000.0

    @property
    def avg_ms(self) -> float:
        return (self.total_ns / self.calls) / 1_000_000.0 if self.calls else 0.0

    @property
    def max_ms(self) -> float:
        return self.max_ns / 1_000_000.0


@dataclass
class _CallFrame:
    start_ns: int
    child_ns: int = 0


class _ThreadStore:
    def __init__(self) -> None:
        self.class_stats: dict[str, TimingStat] = {}
        self.method_stats: dict[str, TimingStat] = {}
        self.sample_counters: dict[str, int] = {}
        self.call_stack: list[_CallFrame] = []


class TimingRegistry:
    """
    Fast path:
      - fetch thread-local store
      - mutate only thread-local dicts
      - no global lock per recorded call

    Slow path:
      - merge all per-thread stores when building reports

    Exclusive timing:
      - each thread maintains its own timed-call stack
      - parent exclusive time excludes sampled timed children

    Important:
      - exclusive timing is exact when sample_every == 1
      - with sampling > 1, exclusion is approximate for nested timed calls
    """

    def __init__(self) -> None:
        self._tls = local()
        self._stores_lock = Lock()
        self._stores: list[_ThreadStore] = []

    def _get_store(self) -> _ThreadStore:
        store = getattr(self._tls, "store", None)
        if store is None:
            store = _ThreadStore()
            self._tls.store = store
            with self._stores_lock:
                self._stores.append(store)
        return store

    def should_sample(self, key: str, sample_every: int) -> bool:
        if sample_every <= 1:
            return True

        store = self._get_store()
        n = store.sample_counters.get(key, 0) + 1
        store.sample_counters[key] = n
        return (n % sample_every) == 0

    def push_frame(self) -> None:
        store = self._get_store()
        store.call_stack.append(_CallFrame(start_ns=perf_counter_ns()))

    def pop_frame(self) -> tuple[int, int]:
        """
        Returns:
          (elapsed_ns, exclusive_ns)

        Also adds the full elapsed time to the parent frame's child_ns
        if a parent frame exists.
        """
        store = self._get_store()
        frame = store.call_stack.pop()

        elapsed_ns = perf_counter_ns() - frame.start_ns
        exclusive_ns = elapsed_ns - frame.child_ns

        if store.call_stack:
            store.call_stack[-1].child_ns += elapsed_ns

        return elapsed_ns, exclusive_ns

    def record_class(self, class_name: str, exclusive_ns: int, weight: int = 1) -> None:
        store = self._get_store()
        stat = store.class_stats.setdefault(class_name, TimingStat())
        stat.calls += weight
        stat.sampled_calls += 1
        stat.total_ns += exclusive_ns * weight
        if exclusive_ns > stat.max_ns:
            stat.max_ns = exclusive_ns

    def record_method(
        self, method_name: str, exclusive_ns: int, weight: int = 1
    ) -> None:
        store = self._get_store()
        stat = store.method_stats.setdefault(method_name, TimingStat())
        stat.calls += weight
        stat.sampled_calls += 1
        stat.total_ns += exclusive_ns * weight
        if exclusive_ns > stat.max_ns:
            stat.max_ns = exclusive_ns

    @staticmethod
    def _merge_dicts(dicts: list[dict[str, TimingStat]]) -> dict[str, TimingStat]:
        merged: dict[str, TimingStat] = {}

        for d in dicts:
            for name, stat in d.items():
                out = merged.setdefault(name, TimingStat())
                out.calls += stat.calls
                out.sampled_calls += stat.sampled_calls
                out.total_ns += stat.total_ns
                if stat.max_ns > out.max_ns:
                    out.max_ns = stat.max_ns

        return merged

    def class_report(self, limit: int | None = None) -> list[dict[str, int | float | str]]:
        with self._stores_lock:
            merged = self._merge_dicts([store.class_stats for store in self._stores])

        rows = [
            {
                "class": name,
                "calls": stat.calls,
                "sampled_calls": stat.sampled_calls,
                "total_ms": stat.total_ms,
                "avg_ms": stat.avg_ms,
                "max_ms": stat.max_ms,
            }
            for name, stat in merged.items()
        ]
        rows.sort(key=lambda row: row["total_ms"], reverse=True)
        return rows if limit is None else rows[:limit]

    def method_report(self, limit: int | None = None) -> list[dict[str, int | float | str]]:
        with self._stores_lock:
            merged = self._merge_dicts([store.method_stats for store in self._stores])

        rows = [
            {
                "method": name,
                "calls": stat.calls,
                "sampled_calls": stat.sampled_calls,
                "total_ms": stat.total_ms,
                "avg_ms": stat.avg_ms,
                "max_ms": stat.max_ms,
            }
            for name, stat in merged.items()
        ]
        rows.sort(key=lambda row: row["total_ms"], reverse=True)
        return rows if limit is None else rows[:limit]

    def reset(self) -> None:
        with self._stores_lock:
            for store in self._stores:
                store.class_stats.clear()
                store.method_stats.clear()
                store.sample_counters.clear()
                store.call_stack.clear()


TIMINGS = TimingRegistry()


def timed_detail(func: Callable | None = None, *, name: str | None = None):
    """
    Mark a method for fine-grained method-level timing.

    Methods wrapped by TimedMeta always contribute to per-class totals.
    Methods additionally marked with @timed_detail also contribute to the
    method-level report.
    """
    def decorate(f: Callable) -> Callable:
        setattr(f, "__timed_detail__", True)
        setattr(f, "__timed_detail_name__", name)
        return f

    if func is None:
        return decorate
    return decorate(func)


def _instrument_function(
    class_name: str,
    attr_name: str,
    func: Callable,
    sample_every: int,
) -> Callable:
    detail_enabled = getattr(func, "__timed_detail__", False)
    detail_name = getattr(func, "__timed_detail_name__", None)
    method_key = detail_name or f"{class_name}.{attr_name}"
    sample_key = method_key

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not TIMINGS.should_sample(sample_key, sample_every):
            return func(*args, **kwargs)

        TIMINGS.push_frame()
        try:
            return func(*args, **kwargs)
        finally:
            _elapsed_ns, exclusive_ns = TIMINGS.pop_frame()
            weight = sample_every if sample_every > 1 else 1
            TIMINGS.record_class(class_name, exclusive_ns, weight=weight)
            if detail_enabled:
                TIMINGS.record_method(method_key, exclusive_ns, weight=weight)

    return wrapper


class TimedMeta(type):
    """
    Class-level overrides:

      __timing_enabled__ = True | False
      __timing_sample_every__ = 1 | N

    If omitted, global defaults from TIMING_CONFIG are used.

    Important:
      For zero overhead when disabled, the class must be created while
      timing is disabled.
    """

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ):
        timing_enabled = bool(
            namespace.get("__timing_enabled__", TIMING_CONFIG.enabled)
        )
        sample_every = int(
            namespace.get("__timing_sample_every__", TIMING_CONFIG.sample_every)
        )
        if sample_every < 1:
            sample_every = 1

        if timing_enabled:
            for attr_name, attr_value in list(namespace.items()):
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    continue

                if isinstance(attr_value, staticmethod):
                    wrapped = _instrument_function(
                        name,
                        attr_name,
                        attr_value.__func__,
                        sample_every,
                    )
                    namespace[attr_name] = staticmethod(wrapped)
                elif isinstance(attr_value, classmethod):
                    wrapped = _instrument_function(
                        name,
                        attr_name,
                        attr_value.__func__,
                        sample_every,
                    )
                    namespace[attr_name] = classmethod(wrapped)
                elif callable(attr_value):
                    namespace[attr_name] = _instrument_function(
                        name,
                        attr_name,
                        attr_value,
                        sample_every,
                    )

        return super().__new__(mcls, name, bases, namespace)

    @staticmethod
    def class_timing_report(limit: int | None = None):
        return TIMINGS.class_report(limit=limit)

    @staticmethod
    def method_timing_report(limit: int | None = None):
        return TIMINGS.method_report(limit=limit)

    @staticmethod
    def reset_timing():
        TIMINGS.reset()


def class_timing_report(limit: int | None = None):
    return TIMINGS.class_report(limit=limit)


def method_timing_report(limit: int | None = None):
    return TIMINGS.method_report(limit=limit)


def reset_timing():
    TIMINGS.reset()


def print_timing_report(limit: int | None = None) -> None:
    class_rows = class_timing_report(limit=limit)
    method_rows = method_timing_report(limit=limit)

    print("\n=== Class timing report ===")
    if not class_rows:
        print("(empty)")
    else:
        for row in class_rows:
            print(
                f"{row['class']}: "
                f"calls={row['calls']}, "
                f"sampled={row['sampled_calls']}, "
                f"total_ms={row['total_ms']:.3f}, "
                f"avg_ms={row['avg_ms']:.6f}, "
                f"max_ms={row['max_ms']:.6f}"
            )

    print("\n=== Method timing report ===")
    if not method_rows:
        print("(empty)")
    else:
        for row in method_rows:
            print(
                f"{row['method']}: "
                f"calls={row['calls']}, "
                f"sampled={row['sampled_calls']}, "
                f"total_ms={row['total_ms']:.3f}, "
                f"avg_ms={row['avg_ms']:.6f}, "
                f"max_ms={row['max_ms']:.6f}"
            )