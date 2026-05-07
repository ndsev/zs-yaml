#!/usr/bin/env python3
"""Structural perf-regression guard.

The 0.10 perf rewrite replaced `zserio.creator.ZserioTreeCreator` and
`zserio.walker.Walker` with a per-compound typeinfo descriptor cache.
Those two classes must never be instantiated on the `yaml_to_bin` /
`bin_to_dict` hot paths. This test asserts that invariant directly so a
future change that re-introduces the slow path fails CI - even on noisy
GitHub-hosted runners where wall-clock measurements are unreliable.
"""
import os
import sys
import tempfile
from unittest.mock import patch

import zserio.creator
import zserio.walker

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.join(HERE, "zs_gen_api"))

from zs_yaml.convert import yaml_to_bin, bin_to_dict  # noqa: E402

from generate_perf_yaml import generate  # noqa: E402

YAML_PATH = os.path.join(HERE, "perf.yaml")
SCHEMA_MODULE = "perf.api"
SCHEMA_TYPE = "Dataset"


def _ensure_yaml():
    if not os.path.exists(YAML_PATH):
        generate(records=200, points_per_record=3, out_path=YAML_PATH)


def _run_with_patches(fn):
    with patch.object(zserio.creator, "ZserioTreeCreator") as creator, \
         patch.object(zserio.walker, "Walker") as walker:
        fn()
        return creator.call_count, walker.call_count


def test_yaml_to_bin_skips_slow_path():
    _ensure_yaml()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        bin_path = tmp.name
    try:
        creator_calls, walker_calls = _run_with_patches(
            lambda: yaml_to_bin(YAML_PATH, bin_path)
        )
    finally:
        os.unlink(bin_path)
    assert creator_calls == 0, f"ZserioTreeCreator instantiated {creator_calls}x - slow path re-introduced"
    assert walker_calls == 0, f"Walker instantiated {walker_calls}x - slow path re-introduced"
    print("yaml_to_bin: no ZserioTreeCreator, no Walker - fast path confirmed")


def test_bin_to_dict_skips_slow_path():
    _ensure_yaml()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        bin_path = tmp.name
    try:
        yaml_to_bin(YAML_PATH, bin_path)
        creator_calls, walker_calls = _run_with_patches(
            lambda: bin_to_dict(bin_path, SCHEMA_MODULE, SCHEMA_TYPE)
        )
    finally:
        os.unlink(bin_path)
    assert creator_calls == 0, f"ZserioTreeCreator instantiated {creator_calls}x - slow path re-introduced"
    assert walker_calls == 0, f"Walker instantiated {walker_calls}x - slow path re-introduced"
    print("bin_to_dict: no ZserioTreeCreator, no Walker - fast path confirmed")


def main():
    test_yaml_to_bin_skips_slow_path()
    test_bin_to_dict_skips_slow_path()
    print("\nAll fast-path assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
