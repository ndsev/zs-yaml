#!/usr/bin/env python3
"""
Tests for the public ``data_to_zserio_object`` API.

We build a Team object two ways from the same transformed dict — via the new
public ``data_to_zserio_object`` and via the JSON detour
(``json.dump`` + ``zserio.from_json_stream``) — and assert their serialized
binary output is byte-identical.
"""
import io
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import zserio

from zs_yaml import data_to_zserio_object
from zs_yaml.yaml_transformer import YamlTransformer


def _serialize(zs_obj) -> bytes:
    writer = zserio.BitStreamWriter()
    zs_obj.write(writer)
    return bytes(writer.byte_array)


def test_data_to_zserio_object_matches_json_detour():
    print("Testing data_to_zserio_object byte-equality vs JSON detour...")

    # Use the existing team1.yaml as the source
    transformer = YamlTransformer("team1.yaml")
    data = transformer.data
    meta = transformer.metadata

    import importlib
    module = importlib.import_module(meta["schema_module"])
    Team = getattr(module, meta["schema_type"])

    # Path A: new public API
    obj_direct = data_to_zserio_object(data, Team)
    bytes_direct = _serialize(obj_direct)

    # Path B: JSON detour (what ndslive-yaml currently does)
    json_str = json.dumps(data)
    obj_json = zserio.from_json_string(Team, json_str)
    bytes_json = _serialize(obj_json)

    assert bytes_direct == bytes_json, (
        f"Mismatch: direct={len(bytes_direct)} bytes, json_detour={len(bytes_json)} bytes"
    )
    print(f"  ✓ identical {len(bytes_direct):,} bytes via both paths")
    return True


def test_init_args_passthrough():
    """Verify that ``init_args=None`` and ``init_args=()`` are equivalent."""
    print("\nTesting init_args=None vs init_args=()...")
    transformer = YamlTransformer("team1.yaml")
    import importlib
    module = importlib.import_module(transformer.metadata["schema_module"])
    Team = getattr(module, transformer.metadata["schema_type"])

    obj_a = data_to_zserio_object(transformer.data, Team)
    obj_b = data_to_zserio_object(transformer.data, Team, init_args=())
    obj_c = data_to_zserio_object(transformer.data, Team, init_args=None)
    assert _serialize(obj_a) == _serialize(obj_b) == _serialize(obj_c)
    print("  ✓ all three forms produce identical output")
    return True


if __name__ == "__main__":
    try:
        test_data_to_zserio_object_matches_json_detour()
        test_init_args_passthrough()
        print("\n✅ data_to_zserio_object tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
