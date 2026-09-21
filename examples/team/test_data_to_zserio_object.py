#!/usr/bin/env python3
"""Tests for the public ``data_to_zserio_object`` API.

The function is what ``yaml_to_bin`` uses internally once the YAML has been
transformed. Callers that already hold the tree previously had to go through
``json.dumps`` + ``zserio.from_json_string``; these tests pin that the direct
route produces the same bytes as that detour.
"""
import importlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import zserio

from zs_yaml import data_to_zserio_object
from zs_yaml.convert import bin_to_dict, yaml_to_bin
from zs_yaml.yaml_transformer import YamlTransformer

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM_YAML = os.path.join(HERE, "team1.yaml")


def _serialize(zs_obj):
    writer = zserio.BitStreamWriter()
    zs_obj.write(writer)
    return bytes(writer.byte_array)


def _transformed_team():
    """Return (transformed data tree, generated Team class)."""
    transformer = YamlTransformer(TEAM_YAML)
    meta = transformer.get_meta()
    module = importlib.import_module(meta["schema_module"])
    return transformer.data, getattr(module, meta["schema_type"])


def test_matches_json_detour():
    """The direct route and the JSON detour produce identical bytes."""
    print("Testing data_to_zserio_object byte-equality vs the JSON detour...")
    data, Team = _transformed_team()

    bytes_direct = _serialize(data_to_zserio_object(data, Team))
    bytes_json = _serialize(zserio.from_json_string(Team, json.dumps(data)))

    assert bytes_direct == bytes_json, (
        f"mismatch: direct={len(bytes_direct)} bytes, "
        f"json detour={len(bytes_json)} bytes"
    )
    print(f"   ✓ identical {len(bytes_direct):,} bytes via both routes")
    return True


def test_matches_yaml_to_bin():
    """Building from the tree matches what yaml_to_bin writes for the file."""
    print("\nTesting data_to_zserio_object vs yaml_to_bin...")
    data, Team = _transformed_team()
    bytes_direct = _serialize(data_to_zserio_object(data, Team))

    with tempfile.TemporaryDirectory() as tmp:
        bin_path = os.path.join(tmp, "team.bin")
        yaml_to_bin(TEAM_YAML, bin_path)
        with open(bin_path, "rb") as f:
            bytes_file = f.read()

    assert bytes_direct == bytes_file, (
        f"mismatch: direct={len(bytes_direct)} bytes, "
        f"yaml_to_bin={len(bytes_file)} bytes"
    )
    print(f"   ✓ identical {len(bytes_direct):,} bytes")
    return True


def test_init_args_forms_are_equivalent():
    """``init_args`` omitted, ``None`` and ``()`` all mean no arguments."""
    print("\nTesting init_args=None vs init_args=() vs omitted...")
    data, Team = _transformed_team()

    a = _serialize(data_to_zserio_object(data, Team))
    b = _serialize(data_to_zserio_object(data, Team, init_args=()))
    c = _serialize(data_to_zserio_object(data, Team, init_args=None))
    assert a == b == c, "the three forms produced different output"
    print("   ✓ all three forms produce identical output")
    return True


def test_round_trips_with_bin_to_dict():
    """A tree from bin_to_dict feeds straight back into data_to_zserio_object."""
    print("\nTesting bin_to_dict -> data_to_zserio_object round-trip...")
    _, Team = _transformed_team()
    with tempfile.TemporaryDirectory() as tmp:
        bin_path = os.path.join(tmp, "team.bin")
        yaml_to_bin(TEAM_YAML, bin_path)
        with open(bin_path, "rb") as f:
            original = f.read()
        data, _meta = bin_to_dict(bin_path, "team.api", "Team")

    rebuilt = _serialize(data_to_zserio_object(data, Team))
    assert rebuilt == original, (
        f"round-trip changed the bytes: {len(rebuilt)} vs {len(original)}"
    )
    print(f"   ✓ round-trip reproduced {len(original):,} bytes")
    return True


if __name__ == "__main__":
    try:
        test_matches_json_detour()
        test_matches_yaml_to_bin()
        test_init_args_forms_are_equivalent()
        test_round_trips_with_bin_to_dict()
        print("\n✅ All data_to_zserio_object tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
