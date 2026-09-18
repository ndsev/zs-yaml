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
    extern_bytes_provider,
    extract_extern_as_yaml,
    insert_yaml_as_extern,
    set_extern_bytes_provider,
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


def test_extern_bytes_provider():
    """A registered provider answers insert_yaml_as_extern instead of zs-yaml."""
    print("\nTesting the extern-bytes provider hook...")

    payload_abs = os.path.join(SCRIPT_DIR, 'payload.yaml')
    seen = []

    with tempfile.TemporaryDirectory() as td:
        wrapper_path = os.path.join(td, 'wrapper.yaml')
        with open(wrapper_path, 'w') as f:
            f.write(_wrapper_yaml(1, payload_abs))  # ZLIB

        # Baseline: what zs-yaml produces with no provider registered.
        baseline_bin = os.path.join(td, 'baseline.bin')
        yaml_to_bin(wrapper_path, baseline_bin)
        baseline, _ = bin_to_dict(baseline_bin, 'extern_compression.api', 'CompressedBlob')
        baseline_extern = baseline['data']

        def declining_provider(path, compression_type):
            seen.append((path, compression_type))
            return None

        with extern_bytes_provider(declining_provider):
            declined_bin = os.path.join(td, 'declined.bin')
            yaml_to_bin(wrapper_path, declined_bin)

        assert seen == [(os.path.abspath(payload_abs), CompressionType.ZLIB)], (
            f"provider was called with {seen!r}; expected one call with the "
            f"absolute payload path and the resolved CompressionType"
        )
        with open(baseline_bin, 'rb') as a, open(declined_bin, 'rb') as b:
            assert a.read() == b.read(), (
                "a provider that declines must leave the output unchanged"
            )
        print("   ✓ provider receives (abs path, resolved CompressionType); "
              "declining changes nothing")

        # A provider that answers must have its bytes used verbatim.
        sentinel = ([1, 2, 3, 4], 32)

        with extern_bytes_provider(lambda path, ct: sentinel):
            served_bin = os.path.join(td, 'served.bin')
            yaml_to_bin(wrapper_path, served_bin)

        served, _ = bin_to_dict(served_bin, 'extern_compression.api', 'CompressedBlob')
        assert served['data']['buffer'] == sentinel[0], (
            f"provider bytes not used: got {served['data']['buffer']!r}"
        )
        assert served['data']['bitSize'] == sentinel[1]
        assert served['data'] != baseline_extern, (
            "the sentinel should differ from what zs-yaml produces, otherwise "
            "this assertion proves nothing"
        )
        print("   ✓ provider bytes are used verbatim")

        # Calling insert_yaml_as_extern directly needs a host transformer that
        # does not itself contain an extern reference, otherwise building it
        # would consult the provider too.
        host_path = os.path.join(td, 'host.yaml')
        with open(host_path, 'w') as f:
            f.write("_meta:\n  schema_module: extern_compression.api\n"
                    "  schema_type: Payload\n")
        host = YamlTransformer(host_path)

        # bytes are accepted and normalized to a list, so the tree keeps the
        # same shape (and stays JSON-serializable) either way.
        with extern_bytes_provider(lambda path, ct: (b'\x01\x02\x03\x04', 32)):
            result = insert_yaml_as_extern(host, payload_abs, compression_type=1)
        assert result == {"buffer": [1, 2, 3, 4], "bitSize": 32}, (
            f"bytes from a provider were not normalized to a list: {result!r}"
        )
        print("   ✓ a bytes buffer is normalized to a list of ints")

        # With template_args the path alone does not identify the bytes, so the
        # provider must not be consulted.
        calls = []
        with extern_bytes_provider(lambda path, ct: calls.append(path) or sentinel):
            with_args = insert_yaml_as_extern(
                host, payload_abs, template_args={'unused': 'x'}, compression_type=1,
            )
        assert not calls, f"provider consulted despite template_args: {calls!r}"
        assert with_args == baseline_extern, (
            "bypassing the provider must produce what zs-yaml produces anyway"
        )
        print("   ✓ not consulted when template_args are given")

    # The context manager restores whatever was registered before.
    marker = lambda path, ct: None
    set_extern_bytes_provider(marker)
    try:
        with extern_bytes_provider(lambda path, ct: None):
            pass
        import zs_yaml.built_in_transformations as bt
        assert bt._extern_bytes_provider is marker, (
            "extern_bytes_provider() did not restore the previous provider"
        )
    finally:
        set_extern_bytes_provider(None)
    print("   ✓ extern_bytes_provider() restores the previous registration")


if __name__ == "__main__":
    try:
        test_compress_unit()
        test_compression_type_arg_resolution()
        test_roundtrip_via_extract_extern()
        test_extern_bytes_provider()
        print("\n✅ All compression tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
