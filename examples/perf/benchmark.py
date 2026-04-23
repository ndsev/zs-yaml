#!/usr/bin/env python3
"""Benchmark yaml_to_bin and bin_to_dict on the perf example.

Generates the perf YAML on demand, runs yaml_to_bin N times, then runs
bin_to_dict N times. Reports median wall time for each direction and,
if reference artifacts are present, verifies byte-identical output.

Usage:
    python benchmark.py [--runs 3] [--records 5000] [--points-per-record 5]
"""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.join(HERE, "zs_gen_api"))

from zs_yaml.convert import yaml_to_bin, bin_to_dict  # noqa: E402

from generate_perf_yaml import generate  # noqa: E402

YAML_PATH = os.path.join(HERE, "perf.yaml")
BIN_PATH = os.path.join(HERE, "perf.bin")
REFERENCE_BIN = os.path.join(HERE, "perf_reference.bin")
REFERENCE_DICT = os.path.join(HERE, "perf_reference_dict.json")

SCHEMA_MODULE = "perf.api"
SCHEMA_TYPE = "Dataset"


def ensure_yaml(records: int, points_per_record: int) -> None:
    if not os.path.exists(YAML_PATH):
        print(f"Generating {YAML_PATH}...")
        generate(records, points_per_record, YAML_PATH)


def run_yaml_to_bin() -> float:
    if os.path.exists(BIN_PATH):
        os.remove(BIN_PATH)
    t0 = time.perf_counter()
    yaml_to_bin(YAML_PATH, BIN_PATH)
    return time.perf_counter() - t0


def run_bin_to_dict():
    t0 = time.perf_counter()
    data, _ = bin_to_dict(BIN_PATH, SCHEMA_MODULE, SCHEMA_TYPE)
    return time.perf_counter() - t0, data


def _report(label, timings):
    median = statistics.median(timings)
    print(f"{label} median: {median:.3f}s "
          f"(min {min(timings):.3f}s, max {max(timings):.3f}s, runs={len(timings)})")
    return median


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--records", type=int, default=5000)
    parser.add_argument("--points-per-record", type=int, default=5)
    parser.add_argument("--write-reference", action="store_true",
                        help="Overwrite reference artifacts with freshly produced output")
    args = parser.parse_args()

    ensure_yaml(args.records, args.points_per_record)

    yaml_size = os.path.getsize(YAML_PATH)
    print(f"Input: {YAML_PATH} ({yaml_size / (1024 * 1024):.2f} MiB)")

    # Forward: yaml -> bin
    print("\n[yaml_to_bin]")
    yaml_timings = []
    for i in range(args.runs):
        elapsed = run_yaml_to_bin()
        yaml_timings.append(elapsed)
        print(f"  run {i + 1}: {elapsed:.3f}s")
    _report("yaml_to_bin", yaml_timings)
    bin_size = os.path.getsize(BIN_PATH)
    print(f"Output bin: {bin_size / (1024 * 1024):.2f} MiB")

    # Reverse: bin -> dict
    print("\n[bin_to_dict]")
    bin_timings = []
    last_dict = None
    for i in range(args.runs):
        elapsed, last_dict = run_bin_to_dict()
        bin_timings.append(elapsed)
        print(f"  run {i + 1}: {elapsed:.3f}s")
    _report("bin_to_dict", bin_timings)

    if args.write_reference:
        import shutil
        shutil.copyfile(BIN_PATH, REFERENCE_BIN)
        print(f"\nWrote reference bin -> {REFERENCE_BIN}")
        with open(REFERENCE_DICT, "w") as f:
            json.dump(last_dict, f, indent=2, sort_keys=True)
        print(f"Wrote reference dict -> {REFERENCE_DICT}")
        return 0

    status = 0
    print()
    if os.path.exists(REFERENCE_BIN):
        with open(BIN_PATH, "rb") as a, open(REFERENCE_BIN, "rb") as b:
            if a.read() == b.read():
                print("bin matches perf_reference.bin byte-for-byte.")
            else:
                print("MISMATCH: bin differs from perf_reference.bin")
                status = 1
    else:
        print("No perf_reference.bin yet; run with --write-reference to pin one.")

    if os.path.exists(REFERENCE_DICT):
        with open(REFERENCE_DICT) as f:
            expected = json.load(f)
        if last_dict == expected:
            print("dict matches perf_reference_dict.json.")
        else:
            print("MISMATCH: dict differs from perf_reference_dict.json")
            status = 1
    else:
        print("No perf_reference_dict.json yet; run with --write-reference to pin one.")

    return status


if __name__ == "__main__":
    sys.exit(main())
