from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path
import sys

# Allow running this file directly via: python tests/test-timing.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "tsl-gen"))

from utils.timing import (
    TimedMeta,
    add_timing_args,
    configure_timing_from_args,
    print_timing_report,
    timed_detail,
)
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_timing_args(parser)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--iters", type=int, default=50)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Must happen BEFORE timed classes are created.
    configure_timing_from_args(args)

    class Parser(metaclass=TimedMeta):
        # Optional per-class override:
        # __timing_enabled__ = True
        # __timing_sample_every__ = 1

        def parse(self) -> None:
            time.sleep(0.002)
            self.tokenize()
            self.build_ast()
            time.sleep(0.002)

        @timed_detail
        def tokenize(self) -> None:
            time.sleep(0.003)

        @timed_detail
        def build_ast(self) -> None:
            time.sleep(0.004)

    class Optimizer(metaclass=TimedMeta):
        def optimize(self) -> None:
            time.sleep(0.001)

    def worker() -> None:
        parser_obj = Parser()
        optimizer_obj = Optimizer()
        for _ in range(args.iters):
            parser_obj.parse()
            optimizer_obj.optimize()

    threads = [threading.Thread(target=worker) for _ in range(args.threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    print_timing_report()


if __name__ == "__main__":
    main()