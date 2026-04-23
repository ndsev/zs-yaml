#!/usr/bin/env python3
"""Deterministically generate a sizeable perf YAML for benchmarking.

Produces examples/perf/perf.yaml with a Dataset containing a parameterized
number of records, each with a short nested array of Points. Matches the
"large array of small records with nested small arrays" pattern from
issue #21 - the shape where the JSON tokenizer cost dominates.

Usage:
    python generate_perf_yaml.py [--records N] [--points-per-record M] [--out PATH]
"""
import argparse
import os

DEFAULT_RECORDS = 5000
DEFAULT_POINTS_PER_RECORD = 5
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf.yaml")


def generate(records: int, points_per_record: int, out_path: str) -> None:
    with open(out_path, "w") as f:
        f.write("_meta:\n")
        f.write("  schema_module: perf.api\n")
        f.write("  schema_type: Dataset\n")
        f.write("\n")
        f.write('name: "perf-dataset"\n')
        f.write("records:\n")
        for i in range(records):
            f.write(f"  - id: {i}\n")
            f.write(f'    label: "record-{i:08d}"\n')
            f.write("    points:\n")
            for j in range(points_per_record):
                x = (i * 31 + j) & 0x7FFFFFFF
                y = (i * 17 - j) & 0x7FFFFFFF
                f.write(f"      - x: {x}\n")
                f.write(f"        y: {y}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=DEFAULT_RECORDS)
    parser.add_argument("--points-per-record", type=int, default=DEFAULT_POINTS_PER_RECORD)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    generate(args.records, args.points_per_record, args.out)
    size = os.path.getsize(args.out)
    print(f"Wrote {args.out} ({size / (1024 * 1024):.2f} MiB, {args.records} records x {args.points_per_record} points)")


if __name__ == "__main__":
    main()
