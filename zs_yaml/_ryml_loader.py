"""
rapidyaml-backed loader. Optional, opt-in via the ``[fast]`` extra.

Drop-in for ``yaml.load(content, Loader=yaml.CLoader)``: it parses with
rapidyaml and builds the same Python tree PyYAML would have built. Tag
determination delegates to PyYAML's own resolver patterns and scalar coercion
mirrors PyYAML's ``SafeConstructor``, so plain scalars resolve identically to
``int``/``float``/``bool``/``None``/``datetime``/``str``.

Anything this loader does not reimplement — anchors and aliases, merge keys,
explicit tags, multi-document streams, nesting past the Python recursion limit
— is handed to PyYAML for that document rather than guessed at, and so is any
input rapidyaml refuses to parse, which keeps error messages identical to the
default loader. The result is that selecting this loader changes how long a
conversion takes and nothing else.
"""
from __future__ import annotations

from typing import Any

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


def pyyaml_load(content) -> Any:
    """Hand a document to the default loader, the one this module matches.

    Deliberately the very function `YamlTransformer` uses when no loader is
    selected, so a delegated document goes through exactly the default path
    rather than a copy of it. The import is deferred because that module is
    what imports this one.
    """
    from zs_yaml.yaml_transformer import _load_pyyaml
    return _load_pyyaml(content)


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


# Coercion results are immutable scalars (str/int/float/bool/None/datetime),
# so they can be shared across occurrences. Mapping keys and enum-like values
# repeat millions of times in large documents; the memo replaces a regex
# resolution plus a numeric parse per occurrence with one dict hit. Capped so
# pathological inputs cannot grow it unbounded.
_SCALAR_CACHE: dict = {}
_SCALAR_CACHE_LIMIT = 1 << 20


def _coerce_plain_scalar(value: str) -> Any:
    try:
        return _SCALAR_CACHE[value]
    except KeyError:
        pass
    tag = _resolve_implicit_tag(value)
    if tag == _TAG_STR:
        result = value
    elif tag == _TAG_NULL:
        result = None
    elif tag == _TAG_BOOL:
        result = _BOOL_VALUES[value.lower()]
    elif tag == _TAG_INT:
        result = _to_int(value)
    elif tag == _TAG_FLOAT:
        result = _to_float(value)
    elif tag == _TAG_TIMESTAMP:
        result = _to_timestamp(value)
    else:
        result = value
    if len(_SCALAR_CACHE) < _SCALAR_CACHE_LIMIT:
        _SCALAR_CACHE[value] = result
    return result


def clear_scalar_cache():
    """Drop the memoized plain-scalar coercions. Exposed for tests."""
    _SCALAR_CACHE.clear()


def _text(csubstr) -> str:
    """Decode a rapidyaml string view; an absent one reads as the empty scalar.

    rapidyaml hands back ``None`` where a key or value is written but left
    empty (``key:`` with nothing after it), which is the empty plain scalar
    PyYAML resolves to ``None``.
    """
    return csubstr.tobytes().decode() if csubstr is not None else ""


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
            if not tree.has_key(c):
                key = None
            elif tree.is_key_plain(c):
                # Only plain scalars take implicit tags; a quoted or block key
                # is a string whatever it looks like, exactly as in PyYAML.
                key = _coerce_plain_scalar(_text(tree.key(c)))
            else:
                key = _text(tree.key(c))
            out[key] = _walk(tree, c)
            c = tree.next_sibling(c)
        return out
    if tree.has_val(node):
        if tree.is_val_plain(node):
            return _coerce_plain_scalar(_text(tree.val(node)))
        return _text(tree.val(node))
    return None


# Bytes that can introduce a construct this loader hands back to PyYAML:
# ``&`` an anchor, ``*`` an alias, ``!`` an explicit tag, ``<<`` a merge key.
# Scanning the raw buffer is a C-level find and keeps the per-node anchor/tag
# predicates off the common path; a document that merely contains these bytes
# inside a scalar pays one extra node walk and nothing more.
_DELEGATE_MARKERS = (b"&", b"*", b"!", b"<<")

# Per-node predicates that confirm what the byte scan only suspected.
_DELEGATE_PREDICATES = (
    "has_val_anchor", "has_key_anchor",
    "is_val_ref", "is_key_ref",
    "has_val_tag", "has_key_tag",
)


def _needs_pyyaml(tree, buf) -> bool:
    """True when the document uses a construct this loader does not reimplement."""
    if not any(marker in buf for marker in _DELEGATE_MARKERS):
        return False
    for node in range(tree.size()):
        for predicate in _DELEGATE_PREDICATES:
            if getattr(tree, predicate)(node):
                return True
    # A merge key without an alias, e.g. ``<<: {a: 1}``: PyYAML merges it,
    # this loader would keep a literal '<<' key, so hand it over as well.
    return b"<<" in buf and _has_merge_key(tree)


def _has_merge_key(tree) -> bool:
    for node in range(tree.size()):
        if tree.has_key(node) and _text(tree.key(node)) == "<<":
            return True
    return False


# Bound on first use, so importing this module without rapidyaml installed
# does not blow up — only load() requires it.
_NONE = None


def ensure_available():
    """Import rapidyaml, raising ImportError with install instructions if absent."""
    global _NONE
    if _NONE is not None:
        return
    try:
        import ryml
    except ImportError as exc:
        raise ImportError(
            "The rapidyaml backend requires the 'fast' extra. "
            "Install with: pip install zs-yaml[fast]"
        ) from exc
    _NONE = ryml.NONE


def load(content) -> Any:
    """Parse ``content`` into the Python tree ``yaml.load(..., yaml.CLoader)`` would build.

    Accepts ``str``, ``bytes``/``bytearray``, or a file-like object exposing ``.read()``.
    """
    ensure_available()
    import ryml  # imported lazily; guaranteed available after ensure_available()

    # `source` is what PyYAML gets whenever this document is handed back to
    # it: the caller's own object where possible, so its error messages name
    # the same kind of input the default loader would have named.
    if isinstance(content, (str, bytes, bytearray)):
        source = content
    else:
        source = content.read()
    buf = source.encode() if isinstance(source, str) else bytes(source)

    try:
        tree = ryml.parse_in_arena(buf)
    except ryml.ExceptionBasic:
        # rapidyaml rejected the input. Re-read it with PyYAML so the caller
        # sees the same YAMLError, with the same line and column, that the
        # default loader would have raised. rapidyaml also writes its own
        # diagnostic to stderr before raising; it has no callback hook to
        # silence that, so its message appears just above PyYAML's.
        return pyyaml_load(source)

    root = tree.root_id()
    if tree.is_stream(root):
        if tree.num_children(root) != 1:
            # Empty input, or a multi-document stream that PyYAML's single-
            # document load() rejects. Both belong to PyYAML.
            return pyyaml_load(source)
        root = tree.first_child(root)
    if _needs_pyyaml(tree, buf):
        return pyyaml_load(source)
    try:
        return _walk(tree, root)
    except RecursionError:
        # _walk descends in Python, so a document nested deeper than the
        # interpreter's recursion limit runs out of stack where PyYAML, which
        # descends in C, does not. The stack has unwound by the time we get
        # here, so PyYAML can read the document and the depth limit stays
        # exactly where it is on the default loader.
        return pyyaml_load(source)
