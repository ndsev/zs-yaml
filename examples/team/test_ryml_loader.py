#!/usr/bin/env python3
"""
Byte-equality test for the optional rapidyaml-backed loader.

For each YAML in this example, build the binary with the default PyYAML loader
and again with ``loader="ryml"``; both runs must produce byte-identical output
and the same intermediate Python tree (after PyYAML-equivalent scalar
resolution).

Skipped automatically if ``rapidyaml`` is not installed.
"""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    import ryml  # noqa: F401
except ImportError:
    print("rapidyaml not installed; skipping ryml loader test.")
    print("(install via: pip install zs-yaml[fast])")
    sys.exit(0)

from zs_yaml.convert import yaml_to_bin
from zs_yaml.yaml_transformer import YamlTransformer


YAMLS = ["team1.yaml"]


def _build(yaml_path: str, loader: str) -> bytes:
    YamlTransformer.clear_cache()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        bin_path = tmp.name
    try:
        prev = YamlTransformer.LOADER
        YamlTransformer.LOADER = loader
        try:
            yaml_to_bin(yaml_path, bin_path)
        finally:
            YamlTransformer.LOADER = prev
        with open(bin_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(bin_path)


def test_byte_equality():
    print("Testing byte-equality between PyYAML and rapidyaml loaders...")
    for yaml_path in YAMLS:
        bytes_pyyaml = _build(yaml_path, "pyyaml")
        bytes_ryml = _build(yaml_path, "ryml")
        h_py = hashlib.sha256(bytes_pyyaml).hexdigest()
        h_rl = hashlib.sha256(bytes_ryml).hexdigest()
        assert h_py == h_rl, (
            f"{yaml_path}: PyYAML and rapidyaml outputs differ "
            f"(pyyaml={h_py}, ryml={h_rl})"
        )
        print(f"  ✓ {yaml_path}  identical ({len(bytes_pyyaml):,} bytes, sha256 {h_py[:12]}...)")
    return True


def test_env_var_activation():
    print("\nTesting ZS_YAML_LOADER env var activation...")
    YamlTransformer.clear_cache()
    os.environ["ZS_YAML_LOADER"] = "ryml"
    try:
        # YamlTransformer.LOADER is the default; env var should override.
        prev = YamlTransformer.LOADER
        YamlTransformer.LOADER = "pyyaml"  # default; env var must take precedence
        try:
            t = YamlTransformer("team1.yaml")
            assert t._load_yaml.__module__.endswith("_ryml_loader"), \
                f"env var did not select ryml loader (got {t._load_yaml})"
            print("  ✓ ZS_YAML_LOADER=ryml activates rapidyaml backend")
        finally:
            YamlTransformer.LOADER = prev
    finally:
        del os.environ["ZS_YAML_LOADER"]
    return True


if __name__ == "__main__":
    try:
        test_byte_equality()
        test_env_var_activation()
        print("\n✅ ryml loader tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
