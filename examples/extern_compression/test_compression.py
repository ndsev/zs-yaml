#!/usr/bin/env python3
"""Tests for compression support in insert_yaml_as_extern / extract_extern_as_yaml."""

import os
import sys
import tempfile
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..')))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'zs_gen_api'))

from zs_yaml.built_in_transformations import (
    CompressionType,
    _compress,
    extract_extern_as_yaml,
)
from zs_yaml.convert import yaml_to_bin, bin_to_dict
from zs_yaml.yaml_transformer import YamlTransformer

COMPRESSION_CASES = [
    ('NONE',   CompressionType.NO_COMPRESSION, 0),
    ('ZLIB',   CompressionType.ZLIB,           1),
    ('ZSTD',   CompressionType.ZSTD,           2),
    ('LZ4',    CompressionType.LZ4,            3),
    ('BROTLI', CompressionType.BROTLI,         4),
]


def test_compress_unit():
    """_compress round-trips via each algorithm's own decompressor."""
    print("Testing _compress unit round-trips...")
    import zlib, zstandard, lz4.frame, brotli
    data = b'hello world, repeatable payload for compression testing. ' * 20

    decompressors = {
        CompressionType.ZLIB:   zlib.decompress,
        CompressionType.ZSTD:   lambda b: zstandard.ZstdDecompressor().decompress(b),
        CompressionType.LZ4:    lz4.frame.decompress,
        CompressionType.BROTLI: brotli.decompress,
    }

    for name, ct, _ in COMPRESSION_CASES:
        compressed = _compress(data, ct)
        if ct == CompressionType.NO_COMPRESSION:
            assert compressed == data, "NO_COMPRESSION should be identity"
            print(f"   ✓ _compress[{name}] identity")
            continue
        assert decompressors[ct](compressed) == data, f"{name} round-trip failed"
        print(f"   ✓ _compress[{name}] round-trip")


def test_compression_type_arg_resolution():
    """compression_type accepts enum / string / int and rejects junk."""
    print("\nTesting compression_type argument resolution...")
    assert CompressionType.from_string("zstd") == CompressionType.ZSTD
    assert CompressionType.from_string("ZLIB") == CompressionType.ZLIB
    assert CompressionType(3) == CompressionType.LZ4
    try:
        CompressionType.from_string("nope")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown compression name should raise")
    print("   ✓ enum/string/int resolution ok")


def _wrapper_yaml(ct_int, abs_payload_path):
    return (
        "_meta:\n"
        "  schema_module: extern_compression.api\n"
        "  schema_type: CompressedBlob\n"
        "\n"
        f"compressionType: {ct_int}\n"
        "data:\n"
        "  _f: insert_yaml_as_extern\n"
        "  _a:\n"
        f"    file: \"{abs_payload_path}\"\n"
        f"    compression_type: {ct_int}\n"
    )


def _normalize_ct(value):
    if isinstance(value, CompressionType):
        return value.value
    if isinstance(value, str):
        return CompressionType.from_string(value).value
    return int(value)


def test_roundtrip_via_extract_extern():
    """wrapper.yaml -> bin -> dict -> extract_extern_as_yaml -> compare."""
    print("\nTesting end-to-end compression roundtrip...")

    payload_abs = os.path.join(SCRIPT_DIR, 'payload.yaml')
    with open(payload_abs) as f:
        expected = yaml.safe_load(f)
    expected_fields = {k: v for k, v in expected.items() if k != '_meta'}

    for name, ct, ct_int in COMPRESSION_CASES:
        with tempfile.TemporaryDirectory() as td:
            wrapper_path = os.path.join(td, f'wrapper_{name}.yaml')
            bin_path = os.path.join(td, f'blob_{name}.bin')
            with open(wrapper_path, 'w') as f:
                f.write(_wrapper_yaml(ct_int, payload_abs))

            yaml_to_bin(wrapper_path, bin_path)

            decoded, _ = bin_to_dict(bin_path, 'extern_compression.api', 'CompressedBlob')
            assert _normalize_ct(decoded['compressionType']) == ct_int, (
                f"[{name}] compressionType mismatch: got {decoded['compressionType']!r}, want {ct_int}"
            )

            host_yaml_path = os.path.join(td, f'host_{name}.yaml')
            with open(host_yaml_path, 'w') as f:
                f.write("_meta:\n  schema_module: extern_compression.api\n  schema_type: Payload\n")
            host_transformer = YamlTransformer(host_yaml_path)

            extracted_name = f'extracted_{name}.yaml'
            extract_extern_as_yaml(
                host_transformer,
                buffer=decoded['data']['buffer'],
                bitSize=decoded['data']['bitSize'],
                schema_module='extern_compression.api',
                schema_type='Payload',
                file_name=extracted_name,
                compression_type=ct_int,
            )

            with open(os.path.join(td, extracted_name)) as f:
                extracted = yaml.safe_load(f)
            extracted_fields = {k: v for k, v in extracted.items() if k != '_meta'}

            assert extracted_fields == expected_fields, (
                f"[{name}] extracted payload differs from input:\n"
                f"  got:      {extracted_fields!r}\n"
                f"  expected: {expected_fields!r}"
            )
            print(f"   ✓ roundtrip[{name}] ok")


if __name__ == "__main__":
    try:
        test_compress_unit()
        test_compression_type_arg_resolution()
        test_roundtrip_via_extract_extern()
        print("\n✅ All compression tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
