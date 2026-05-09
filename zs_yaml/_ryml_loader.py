"""
rapidyaml-backed loader. Optional, opt-in via the ``[fast]`` extra.

Drop-in for ``yaml.load(content, Loader=yaml.CLoader)`` for the subset of YAML
we use in zs-yaml: nested mappings/sequences and plain/quoted scalars resolved
to ``int``/``float``/``bool``/``None``/``datetime``/``str``. Tag determination
delegates to PyYAML's own resolver patterns, and scalar coercion mirrors
PyYAML's ``SafeConstructor``, so output is identical to PyYAML.
"""
from __future__ import annotations

from typing import Any
import datetime as _datetime

import yaml as _pyyaml
from yaml.resolver import Resolver as _Resolver


# These tags come from the YAML 1.1 spec; PyYAML's SafeConstructor uses them
# as keys into its constructor map.
_TAG_INT = "tag:yaml.org,2002:int"
_TAG_FLOAT = "tag:yaml.org,2002:float"
_TAG_BOOL = "tag:yaml.org,2002:bool"
_TAG_NULL = "tag:yaml.org,2002:null"
_TAG_TIMESTAMP = "tag:yaml.org,2002:timestamp"
_TAG_STR = "tag:yaml.org,2002:str"

# Boolean tokens accepted by PyYAML SafeConstructor (case-sensitive table).
_BOOL_VALUES = _pyyaml.constructor.SafeConstructor.bool_values

# A throwaway SafeConstructor instance is reused for the rare timestamp path.
_SAFE_CONSTRUCTOR = _pyyaml.constructor.SafeConstructor()


def _resolve_implicit_tag(value: str) -> str:
    """Return the YAML tag PyYAML would assign to a plain scalar string."""
    if not value:
        return _TAG_NULL
    first = value[0]
    for tag, regex in _Resolver.yaml_implicit_resolvers.get(first, ()):
        if regex.match(value):
            return tag
    for tag, regex in _Resolver.yaml_implicit_resolvers.get(None, ()):
        if regex.match(value):
            return tag
    return _TAG_STR


def _to_int(value: str) -> int:
    """Port of yaml.SafeConstructor.construct_yaml_int."""
    value = value.replace("_", "")
    sign = -1 if value[0] == "-" else +1
    if value[0] in "+-":
        value = value[1:]
    if value == "0":
        return 0
    if value.startswith("0b"):
        return sign * int(value[2:], 2)
    if value.startswith("0x"):
        return sign * int(value[2:], 16)
    if value[0] == "0":
        return sign * int(value, 8)
    if ":" in value:
        digits = [int(part) for part in value.split(":")]
        digits.reverse()
        base = 1
        result = 0
        for digit in digits:
            result += digit * base
            base *= 60
        return sign * result
    return sign * int(value)


def _to_float(value: str) -> float:
    """Port of yaml.SafeConstructor.construct_yaml_float."""
    value = value.replace("_", "").lower()
    sign = -1 if value[0] == "-" else +1
    if value[0] in "+-":
        value = value[1:]
    if value == ".inf":
        return sign * float("inf")
    if value == ".nan":
        return float("nan")
    if ":" in value:
        digits = [float(part) for part in value.split(":")]
        digits.reverse()
        base = 1
        result = 0.0
        for digit in digits:
            result += digit * base
            base *= 60
        return sign * result
    return sign * float(value)


def _to_timestamp(value: str):
    """Delegate to PyYAML for timestamp coercion (rare path; correctness > speed)."""
    node = _pyyaml.ScalarNode(_TAG_TIMESTAMP, value)
    return _SAFE_CONSTRUCTOR.construct_yaml_timestamp(node)


def _coerce_plain_scalar(value: str) -> Any:
    tag = _resolve_implicit_tag(value)
    if tag == _TAG_STR:
        return value
    if tag == _TAG_NULL:
        return None
    if tag == _TAG_BOOL:
        return _BOOL_VALUES[value.lower()]
    if tag == _TAG_INT:
        return _to_int(value)
    if tag == _TAG_FLOAT:
        return _to_float(value)
    if tag == _TAG_TIMESTAMP:
        return _to_timestamp(value)
    return value


def _walk(tree, node):
    """Materialize a ryml subtree into a Python dict / list / scalar."""
    if tree.is_seq(node):
        out = []
        c = tree.first_child(node)
        while c != _NONE:
            out.append(_walk(tree, c))
            c = tree.next_sibling(c)
        return out
    if tree.is_map(node):
        out = {}
        c = tree.first_child(node)
        while c != _NONE:
            kstr = tree.key(c).tobytes().decode() if tree.has_key(c) else ""
            if _is_key_quoted is not None and _is_key_quoted(tree, c):
                key = kstr
            else:
                key = _coerce_plain_scalar(kstr) if kstr else None
            out[key] = _walk(tree, c)
            c = tree.next_sibling(c)
        return out
    if tree.has_val(node):
        vstr = tree.val(node).tobytes().decode()
        if _is_val_quoted is not None and _is_val_quoted(tree, node):
            return vstr
        return _coerce_plain_scalar(vstr)
    return None


# Module-level handles bound at first use (so importing this module without
# rapidyaml installed doesn't blow up — only `load()` requires it).
_NONE = None
_is_val_quoted = None
_is_key_quoted = None


def _ensure_ryml():
    global _NONE, _is_val_quoted, _is_key_quoted
    if _NONE is not None:
        return
    try:
        import ryml  # noqa: WPS433 (lazy import is intentional)
    except ImportError as exc:  # pragma: no cover - exercised when extra not installed
        raise ImportError(
            "The rapidyaml backend requires the 'fast' extra. "
            "Install with: pip install zs-yaml[fast]"
        ) from exc
    _NONE = ryml.NONE
    _is_val_quoted = getattr(ryml.Tree, "is_val_quoted", None)
    _is_key_quoted = getattr(ryml.Tree, "is_key_quoted", None)


def load(content) -> Any:
    """Parse ``content`` and return a Python tree equivalent to ``yaml.load(..., yaml.CLoader)``.

    Accepts ``str``, ``bytes``/``bytearray``, or a file-like object exposing ``.read()``.
    """
    _ensure_ryml()
    import ryml  # imported lazily; guaranteed available after _ensure_ryml

    if isinstance(content, str):
        buf = content.encode()
    elif isinstance(content, (bytes, bytearray)):
        buf = bytes(content)
    else:
        raw = content.read()
        buf = raw.encode() if isinstance(raw, str) else raw

    tree = ryml.parse_in_arena(buf)
    return _walk(tree, tree.root_id())
