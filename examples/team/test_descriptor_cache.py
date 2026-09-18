#!/usr/bin/env python3
"""Pins that the compound descriptor cache hits across top-level conversions.

The cache exists so a process converting many documents against the same
schema builds each compound's descriptor once. Keying it on the ``TypeInfo``
object silently defeated that: a generated ``type_info()`` returns a fresh
``TypeInfo`` graph on every call, so every top-level conversion missed on
every compound, rebuilt the whole descriptor tree, and kept the dead graphs
alive as cache keys. Wall-clock is too noisy to catch that on CI, so these
tests count descriptor constructions directly.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from zs_yaml import convert
from zs_yaml.convert import yaml_to_bin, bin_to_dict

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM_YAML = os.path.join(HERE, "team1.yaml")
SCHEMA_MODULE = "team.api"
SCHEMA_TYPE = "Team"


class _CountingDescriptor(convert._CompoundDescriptor):
    """Records every descriptor build so a test can assert on the count."""
    count = 0

    def __init__(self, type_info):
        _CountingDescriptor.count += 1
        super().__init__(type_info)


def _count_builds(fn):
    """Run ``fn`` and return how many compound descriptors it had to build."""
    original = convert._CompoundDescriptor
    convert._CompoundDescriptor = _CountingDescriptor
    _CountingDescriptor.count = 0
    try:
        fn()
    finally:
        convert._CompoundDescriptor = original
    return _CountingDescriptor.count


def test_type_info_is_rebuilt_per_call():
    """The premise: a TypeInfo-keyed cache could never hit across conversions."""
    from team.api import Team

    print("Testing that Team.type_info() yields a fresh object per call...")
    first, second = Team.type_info(), Team.type_info()
    assert first is not second, (
        "type_info() returned the same object twice; if zserio starts memoizing "
        "it, the class key below is still correct but this test's rationale "
        "needs revisiting"
    )
    assert first.py_type is second.py_type, "py_type must be stable across calls"
    print("   ✓ fresh TypeInfo per call, stable py_type")
    return True


def test_cache_hits_across_top_level_conversions():
    """A second yaml_to_bin over the same schema builds no descriptor at all."""
    print("\nTesting descriptor cache across repeated yaml_to_bin...")
    convert._COMPOUND_CACHE.clear()

    with tempfile.TemporaryDirectory() as tmp:
        first_bin = os.path.join(tmp, "first.bin")
        second_bin = os.path.join(tmp, "second.bin")

        first_builds = _count_builds(lambda: yaml_to_bin(TEAM_YAML, first_bin))
        assert first_builds > 0, "cold conversion must build the descriptors"

        second_builds = _count_builds(lambda: yaml_to_bin(TEAM_YAML, second_bin))
        assert second_builds == 0, (
            f"second conversion rebuilt {second_builds} descriptor(s); the cache "
            f"is not hitting across top-level conversions "
            f"(cold build was {first_builds})"
        )

        with open(first_bin, "rb") as a, open(second_bin, "rb") as b:
            assert a.read() == b.read(), "cached descriptors changed the output"

    print(f"   ✓ cold conversion built {first_builds} descriptors, second built 0")
    print("   ✓ both conversions produced identical bytes")
    return True


def test_cache_is_shared_between_directions():
    """bin_to_dict reuses the descriptors yaml_to_bin already built."""
    print("\nTesting descriptor cache across yaml_to_bin -> bin_to_dict...")
    convert._COMPOUND_CACHE.clear()

    with tempfile.TemporaryDirectory() as tmp:
        bin_path = os.path.join(tmp, "team.bin")
        yaml_to_bin(TEAM_YAML, bin_path)

        builds = _count_builds(
            lambda: bin_to_dict(bin_path, SCHEMA_MODULE, SCHEMA_TYPE)
        )
        assert builds == 0, (
            f"bin_to_dict rebuilt {builds} descriptor(s) that yaml_to_bin had "
            f"already built for the same classes"
        )

    print("   ✓ reverse direction built 0 descriptors")
    return True


def test_cache_is_keyed_on_the_generated_class():
    """Every cache key is a generated class, so keys cannot be recycled."""
    print("\nTesting descriptor cache key type...")
    convert._COMPOUND_CACHE.clear()

    with tempfile.TemporaryDirectory() as tmp:
        yaml_to_bin(TEAM_YAML, os.path.join(tmp, "team.bin"))

    keys = list(convert._COMPOUND_CACHE)
    assert keys, "conversion cached nothing"
    non_classes = [k for k in keys if not isinstance(k, type)]
    assert not non_classes, f"non-class cache keys: {non_classes}"

    from team.api import Team
    assert Team in convert._COMPOUND_CACHE, (
        f"Team missing from cache keys: {[k.__name__ for k in keys]}"
    )
    print(f"   ✓ all {len(keys)} cache keys are generated classes")
    return True


if __name__ == "__main__":
    try:
        test_type_info_is_rebuilt_per_call()
        test_cache_hits_across_top_level_conversions()
        test_cache_is_shared_between_directions()
        test_cache_is_keyed_on_the_generated_class()
        print("\n✅ All descriptor cache tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
