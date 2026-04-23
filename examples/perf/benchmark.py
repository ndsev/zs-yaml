#!/usr/bin/env python3
"""Benchmark yaml_to_bin on the perf example.

Generates the perf YAML on demand, runs yaml_to_bin N times, reports the
median wall time, and (if a reference binary is present) verifies the
output is byte-identical to it.

Usage:
    python benchmark.py [--runs 3] [--records 5000] [--points-per-record 5]
"""
import argparse
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.join(HERE, "zs_gen_api"))

from zs_yaml.convert import yaml_to_bin  # noqa: E402

from generate_perf_yaml import generate  # noqa: E402

YAML_PATH = os.path.join(HERE, "perf.yaml")
BIN_PATH = os.path.join(HERE, "perf.bin")
REFERENCE_BIN = os.path.join(HERE, "perf_reference.bin")


def ensure_yaml(records: int, points_per_record: int) -> None:
    if not os.path.exists(YAML_PATH):
        print(f"Generating {YAML_PATH}...")
        generate(records, points_per_record, YAML_PATH)


def run_once() -> float:
    if os.path.exists(BIN_PATH):
        os.remove(BIN_PATH)
    t0 = time.perf_counter()
    yaml_to_bin(YAML_PATH, BIN_PATH)
    return time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--records", type=int, default=5000)
    parser.add_argument("--points-per-record", type=int, default=5)
    parser.add_argument("--write-reference", action="store_true",
                        help="Overwrite perf_reference.bin with the freshly produced bin")
    args = parser.parse_args()

    ensure_yaml(args.records, args.points_per_record)

    yaml_size = os.path.getsize(YAML_PATH)
    print(f"Input: {YAML_PATH} ({yaml_size / (1024 * 1024):.2f} MiB)")

    timings = []
    for i in range(args.runs):
        elapsed = run_once()
        timings.append(elapsed)
        print(f"  run {i + 1}: {elapsed:.3f}s")

    median = statistics.median(timings)
    bin_size = os.path.getsize(BIN_PATH)
    print(f"yaml_to_bin median: {median:.3f}s "
          f"(min {min(timings):.3f}s, max {max(timings):.3f}s, runs={args.runs})")
    print(f"Output bin: {bin_size / (1024 * 1024):.2f} MiB")

    if args.write_reference:
        import shutil
        shutil.copyfile(BIN_PATH, REFERENCE_BIN)
        print(f"Wrote reference bin -> {REFERENCE_BIN}")
        return 0

    if os.path.exists(REFERENCE_BIN):
        with open(BIN_PATH, "rb") as a, open(REFERENCE_BIN, "rb") as b:
            if a.read() == b.read():
                print("Output matches perf_reference.bin byte-for-byte.")
                return 0
            print("MISMATCH: output differs from perf_reference.bin")
            return 1
    else:
        print("No perf_reference.bin yet; run with --write-reference to pin one.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
