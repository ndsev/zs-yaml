#!/usr/bin/env python3
"""
Equivalence test for the optional zs_yaml_native C loader.

The native loader must produce exactly the same Python tree as the
ryml-binding loader and as ``yaml.load(..., yaml.CSafeLoader)`` — including
PyYAML 1.1 scalar-resolution quirks (octal/hex/sexagesimal integers, floats
requiring a dot and a signed exponent, bool/null token tables).

Skipped automatically if ``zs_yaml_native`` is not built/installed.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    import zs_yaml_native  # noqa: F401
except ImportError:
    print("zs_yaml_native not built; skipping native loader test.")
    print("(build via: python native/setup.py build_ext --inplace)")
    sys.exit(0)

import yaml

from zs_yaml import _ryml_loader


EDGE_CASES = """
ints: [0, -0, 7, -42, 123456789012345678901234567890, 0x1F, 0o17, 0b101, 007, 1_000, 1:30]
floats: [0.5, -3.25, 1.0e+5, 2.5e-3, .5, 5., .inf, -.inf, .nan, 1e5, 1.0e5, 00.5, 9007199254740993.0]
bools: [yes, No, TRUE, false, On, off]
nulls: [~, null, NULL, ]
strs: ["quoted", 'single', plain string, "0123", '1.5', 2026-06-12T10:00:00Z, v1.2.3, +5, 5e3]
nested: {a: [1, {b: c}], d: {e: [f, 0.25]}}
empty_map: {}
empty_seq: []
big: [18446744073709551615, -9223372036854775808, 999999999999999999, 1000000000000000000]
"""


def _native_load(buf: bytes):
    return zs_yaml_native.load(buf, _ryml_loader._coerce_plain_scalar)


def _binding_load(buf: bytes):
    _ryml_loader._ensure_ryml()
    import ryml
    tree = ryml.parse_in_arena(buf)
    return _ryml_loader._walk(tree, tree.root_id())


def _trees_equal(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_trees_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_trees_equal(x, y) for x, y in zip(a, b))
    return a == b


def _random_doc(rng: random.Random) -> bytes:
    lines = []
    for i in range(rng.randint(3, 12)):
        kind = rng.randrange(5)
        if kind == 0:
            lines.append(f"key{i}: {rng.randint(-10**12, 10**12)}")
        elif kind == 1:
            lines.append(f"key{i}: {rng.uniform(-1e6, 1e6):.{rng.randint(1, 12)}f}")
        elif kind == 2:
            lines.append(f"key{i}: {rng.uniform(-1, 1):.6e}".replace("e", "e+").replace("e+-", "e-"))
        elif kind == 3:
            values = ", ".join(str(rng.randint(0, 10**9)) for _ in range(rng.randint(1, 30)))
            lines.append(f"key{i}: [{values}]")
        else:
            lines.append(f"key{i}:")
            lines.append(f"  nested: [a, 0.5, -7, true, null]")
    return "\n".join(lines).encode()


def test_equivalence():
    rng = random.Random(20260612)
    cases = [EDGE_CASES.encode()]
    cases.extend(_random_doc(rng) for _ in range(200))

    for index, buf in enumerate(cases):
        native_tree = _native_load(buf)
        binding_tree = _binding_load(buf)
        pyyaml_tree = yaml.load(buf, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
        assert _trees_equal(native_tree, binding_tree), f"native != binding for case {index}"
        assert _trees_equal(native_tree, pyyaml_tree), f"native != pyyaml for case {index}"

    print(f"OK: native == binding == pyyaml for {len(cases)} documents")


if __name__ == "__main__":
    test_equivalence()
