#!/usr/bin/env python3
"""
Equivalence tests for the optional rapidyaml-backed loader (the [fast] extra).

The whole promise of the extra is that selecting it changes how long a
conversion takes and nothing else, so what is pinned here is that promise:

  * the loader builds the same Python tree as PyYAML, value for value and type
    for type, over a scalar corpus and over every YAML file in examples/;
  * constructs it does not reimplement (anchors, merge keys, explicit tags,
    multi-document streams) and inputs it cannot parse come back from PyYAML,
    with PyYAML's own errors;
  * a full team1.yaml -> binary conversion is byte-identical either way;
  * loader selection behaves as documented, including when rapidyaml is not
    installed.

The selection tests run with or without rapidyaml. The equivalence tests are
skipped when it is not installed; run `pip install zs-yaml[fast]` for those.
"""
import glob
import hashlib
import math
import os
import sys
import tempfile
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import yaml

from zs_yaml import yaml_transformer as _yt
from zs_yaml.yaml_transformer import YamlTransformer

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.abspath(os.path.join(HERE, '..'))

try:
    import ryml  # noqa: F401
    HAVE_RYML = True
except ImportError:
    HAVE_RYML = False


# --------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------

# Every plain-scalar shape PyYAML's implicit resolver recognises, plus the
# shapes that must NOT be resolved because they are quoted or block scalars.
SCALARS = """
ints:
  dec: 42
  neg: -17
  plus: +17
  zero: 0
  oct: 0o14
  oct_legacy: 014
  hex: 0xC
  hex_upper: 0XFF
  bin: 0b1010
  underscored: 1_000_000
  sexagesimal: 190:20:30
floats:
  simple: 1.5
  negative: -2.25
  exponent: 6.8523015e+5
  leading_dot: .5
  trailing_dot: 5.
  inf: .inf
  neg_inf: -.Inf
  nan: .NaN
  underscored: 1_000.5
  sexagesimal: 190:20:30.15
bools:
  yes_: yes
  no_: no
  true_: true
  false_: false
  on_: on
  off_: off
  y_upper: TRUE
  mixed: False
nulls:
  tilde: ~
  word: null
  upper: NULL
  empty:
strings:
  word: hello
  spaced: hello world
  looks_int: "42"
  looks_bool: "yes"
  looks_null: "null"
  looks_float: '1.5'
  leading_zero_str: "007"
  colon_in_quotes: "a: b"
  unicode: "caf\\u00e9 \\u00fcber stra\\u00dfe"
  emoji: "tile \\U0001F5FA"
  version_like: 1.2.3
  dashes: a-b-c
  empty_quoted: ""
timestamps:
  date: 2026-06-09
  datetime: 2026-06-09 14:30:00
  iso: 2026-06-09T14:30:00.5Z
blocks:
  literal: |
    line one
    line two
  literal_strip: |-
    no trailing newline
  folded: >
    folded one
    folded two
  literal_numeric: |
    42
nested:
  empty_map: {}
  empty_seq: []
  flow_map: {a: 1, b: two, c: null}
  flow_seq: [1, two, 3.5, true, ~]
  deep:
    - - - leaf
    - key: {inner: [1, 2, {deepest: yes}]}
non_string_keys:
  1: int key
  2.5: float key
  true: bool key
  ~: null key
  "3": quoted-digit key
"""

# Constructs the loader hands back to PyYAML rather than reimplementing.
DELEGATED = {
    "anchor and alias": "base: &a 1\nuse: *a\n",
    "anchored mapping": "base: &m {k: 1}\ncopy: *m\n",
    "merge key via alias": "base: &m\n  a: 1\n  b: 2\nderived:\n  <<: *m\n  b: 3\n",
    "merge key inline": "derived:\n  <<: {a: 1}\n  b: 2\n",
    "explicit tag": "a: !!str 42\nb: !!int '7'\n",
    "explicit seq tag": "a: !!seq [1, 2]\n",
    "single doc with marker": "---\na: 1\n",
    "empty document": "",
    "comments only": "# nothing here\n",
    "root scalar": "42\n",
    "root sequence": "- 1\n- two\n",
    "ampersand in scalar": "a: \"tom & jerry\"\n",
    "asterisk in scalar": "a: \"2 * 3\"\n",
    "bang in scalar": "a: \"wow!\"\n",
    "angle brackets in scalar": "a: \"x << y\"\n",
}

# Shapes that are easy to get subtly wrong: whichever loader handles them, the
# answer must be the same one, down to the exception class when they raise.
EDGE_CASES = {
    "complex key": "? [1, 2]\n: value\n",
    "duplicate keys": "a: 1\na: 2\n",
    "crlf line endings": "a: 1\r\nb: two\r\n",
    "byte order mark": "\ufeffa: 1\n",
    "trailing spaces": "a: 1   \nb: two  \n",
    "inline comment": "a: 1  # trailing comment\nb: two\n",
    "document end marker": "a: 1\n...\n",
    "yaml directive": "%YAML 1.2\n---\na: 1\n",
    "null in sequence": "- \n- x\n",
    "empty collections": "a:\nb: {}\nc: []\n",
    "nesting past the recursion limit":
        "".join(f"{' ' * i}k{i}:\n" for i in range(2000)) + " " * 2000 + "leaf\n",
    "long flow sequence": "a: [" + ",".join(str(i) for i in range(2000)) + "]\n",
}

# Inputs no loader should accept. PyYAML's error is the one users know, so the
# ryml path must raise the same class of error.
MALFORMED = {
    "unterminated flow": "a: [1, 2\n",
    "bad indentation": "a:\n  - b\n c: 1\n",
    "tab indent": "\ta: 1\n",
    "unterminated quote": "a: 'unterminated\n",
}


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def _diff(a, b, path="$"):
    """Return a description of the first difference, or None if equal.

    Types are compared exactly: YAML's 1, 1.0 and true all compare equal in
    Python, and conflating them is precisely the failure this test exists to
    catch.
    """
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__} ({a!r} vs {b!r})"
    if isinstance(a, dict):
        ka, kb = list(a.keys()), list(b.keys())
        if ka != kb or [type(k) for k in ka] != [type(k) for k in kb]:
            return f"{path}: keys {ka!r} != {kb!r}"
        for k in ka:
            d = _diff(a[k], b[k], f"{path}[{k!r}]")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if isinstance(a, float):
        if math.isnan(a) and math.isnan(b):
            return None
        if a != b:
            return f"{path}: {a!r} != {b!r}"
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def _raised(call):
    """Return the yaml.YAMLError `call` raised, or None if it raised nothing."""
    try:
        call()
    except yaml.YAMLError as e:
        return e
    return None


def _assert_equivalent(source, label):
    from zs_yaml import _ryml_loader

    expected = yaml.load(source, Loader=yaml.CLoader)
    actual = _ryml_loader.load(source)
    d = _diff(expected, actual)
    assert d is None, f"{label}: ryml loader diverges from PyYAML at {d}"


# --------------------------------------------------------------------------
# Equivalence tests (need rapidyaml)
# --------------------------------------------------------------------------

def test_scalar_corpus():
    print("Testing scalar resolution against PyYAML...")
    _assert_equivalent(SCALARS, "scalar corpus")
    # Guard the guard: the comparison must actually reject a type change, or
    # everything above would pass vacuously.
    assert _diff({"a": 1}, {"a": 1.0}) is not None, "_diff ignores int/float"
    assert _diff({"a": 1}, {"a": True}) is not None, "_diff ignores int/bool"
    assert _diff({"a": "1"}, {"a": 1}) is not None, "_diff ignores str/int"
    n = len(yaml.load(SCALARS, Loader=yaml.CLoader))
    print(f"   \u2713 {n} scalar groups resolve identically")


def test_example_yaml_files():
    print("\nTesting every YAML file under examples/ ...")
    paths = sorted(glob.glob(os.path.join(EXAMPLES_DIR, '**', '*.yaml'), recursive=True))
    assert paths, f"no YAML files found under {EXAMPLES_DIR}"
    for path in paths:
        with open(path, 'r') as f:
            source = f.read()
        _assert_equivalent(source, os.path.relpath(path, EXAMPLES_DIR))
    print(f"   \u2713 {len(paths)} example files load identically")


def test_delegated_constructs():
    print("\nTesting constructs handed back to PyYAML...")
    for label, source in DELEGATED.items():
        _assert_equivalent(source, label)
    print(f"   \u2713 {len(DELEGATED)} delegated constructs match PyYAML")


def test_edge_cases():
    print("\nTesting edge cases...")
    from zs_yaml import _ryml_loader

    # _diff descends one frame per level, and one case is nested deeper than
    # the default limit on purpose. The loaders handle that document; the
    # comparison below needs room to check that they handled it the same way.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 10000))
    try:
        _compare_edge_cases(_ryml_loader)
    finally:
        sys.setrecursionlimit(limit)
    print(f"   \u2713 {len(EDGE_CASES)} edge cases behave identically")


def _compare_edge_cases(_ryml_loader):
    for label, source in EDGE_CASES.items():
        try:
            expected, expected_error = yaml.load(source, Loader=yaml.CLoader), None
        except Exception as e:
            expected, expected_error = None, type(e)
        try:
            actual, actual_error = _ryml_loader.load(source), None
        except Exception as e:
            actual, actual_error = None, type(e)
        assert actual_error is expected_error, (
            f"{label}: PyYAML raised {expected_error}, ryml loader raised {actual_error}"
        )
        if expected_error is None:
            d = _diff(expected, actual)
            assert d is None, f"{label}: ryml loader diverges from PyYAML at {d}"


def test_multi_document_matches_pyyaml():
    print("\nTesting multi-document input...")
    from zs_yaml import _ryml_loader

    source = "a: 1\n---\nb: 2\n"
    try:
        yaml.load(source, Loader=yaml.CLoader)
        raise AssertionError("PyYAML unexpectedly accepted a multi-document stream")
    except yaml.YAMLError:
        pass
    try:
        _ryml_loader.load(source)
        raise AssertionError("ryml loader accepted a multi-document stream")
    except yaml.YAMLError:
        pass
    print("   \u2713 both loaders reject it with a yaml.YAMLError")


def test_malformed_input_reports_like_pyyaml():
    print("\nTesting malformed input...")
    from zs_yaml import _ryml_loader

    for label, source in MALFORMED.items():
        expected = _raised(lambda: yaml.load(source, Loader=yaml.CLoader))
        assert expected is not None, f"{label}: PyYAML unexpectedly accepted it"
        actual = _raised(lambda: _ryml_loader.load(source))
        assert actual is not None, f"{label}: ryml loader unexpectedly accepted it"
        assert type(actual) is type(expected), (
            f"{label}: ryml loader raised {type(actual).__name__}, "
            f"PyYAML raises {type(expected).__name__}"
        )
        assert str(actual) == str(expected), (
            f"{label}: error text differs\n  pyyaml: {expected}\n  ryml:   {actual}"
        )
    print(f"   \u2713 {len(MALFORMED)} malformed inputs raise PyYAML's own error")


def test_memoized_coercion_matches_uncached():
    print("\nTesting the memoized scalar coercion...")
    from zs_yaml import _ryml_loader

    _ryml_loader.clear_scalar_cache()
    first = _ryml_loader.load(SCALARS)
    assert _ryml_loader._SCALAR_CACHE, "scalar cache stayed empty; memo is not in use"
    second = _ryml_loader.load(SCALARS)   # served from the memo
    d = _diff(first, second)
    assert d is None, f"memoized load differs from the first load at {d}"
    _ryml_loader.clear_scalar_cache()
    third = _ryml_loader.load(SCALARS)
    d = _diff(first, third)
    assert d is None, f"load after clearing the memo differs at {d}"
    print(f"   \u2713 memo holds {len(_ryml_loader._SCALAR_CACHE)} entries and changes no value")


def test_conversion_is_byte_identical():
    print("\nTesting team1.yaml -> binary under both loaders...")
    from zs_yaml.convert import yaml_to_bin

    def build(loader):
        fd, bin_path = tempfile.mkstemp(suffix='.bin')
        os.close(fd)
        try:
            YamlTransformer.clear_cache()
            previous = YamlTransformer.LOADER
            YamlTransformer.LOADER = loader
            try:
                yaml_to_bin(os.path.join(HERE, 'team1.yaml'), bin_path)
            finally:
                YamlTransformer.LOADER = previous
            with open(bin_path, 'rb') as f:
                return f.read()
        finally:
            os.unlink(bin_path)

    from_pyyaml = build('pyyaml')
    from_ryml = build('ryml')
    h_pyyaml = hashlib.sha256(from_pyyaml).hexdigest()
    h_ryml = hashlib.sha256(from_ryml).hexdigest()
    assert h_pyyaml == h_ryml, (
        f"team1.yaml: outputs differ (pyyaml={h_pyyaml}, ryml={h_ryml})"
    )
    print(f"   \u2713 {len(from_pyyaml):,} bytes, sha256 {h_pyyaml[:16]} either way")


def test_loader_propagates_into_includes():
    print("\nTesting loader propagation into included documents...")
    seen = []

    class RecordingTransformer(YamlTransformer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen.append((os.path.basename(self.yaml_file_path), self._load_yaml))

    from zs_yaml import _ryml_loader

    RecordingTransformer.get_or_create(os.path.join(HERE, 'team1.yaml'), loader='ryml')
    assert len(seen) > 1, "team1.yaml pulls in includes; none were transformed"
    wrong = [name for name, fn in seen if fn is not _ryml_loader.load]
    assert not wrong, f"these included documents did not inherit the loader: {wrong}"
    print(f"   \u2713 all {len(seen)} documents in the tree used the ryml loader")


# --------------------------------------------------------------------------
# Selection tests (run with or without rapidyaml)
# --------------------------------------------------------------------------

class _EnvVar:
    """Set (or unset, with None) ZS_YAML_LOADER for the duration of a block."""
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        self.previous = os.environ.get(_yt.LOADER_ENV_VAR)
        if self.value is None:
            os.environ.pop(_yt.LOADER_ENV_VAR, None)
        else:
            os.environ[_yt.LOADER_ENV_VAR] = self.value

    def __exit__(self, *exc):
        if self.previous is None:
            os.environ.pop(_yt.LOADER_ENV_VAR, None)
        else:
            os.environ[_yt.LOADER_ENV_VAR] = self.previous


class _RapidyamlMissing:
    """Make the rapidyaml probe fail, so the no-wheel paths can be tested."""
    def __enter__(self):
        from zs_yaml import _ryml_loader
        self.module = _ryml_loader
        self.previous = _ryml_loader.ensure_available

        def fail():
            raise ImportError(
                "The rapidyaml backend requires the 'fast' extra. "
                "Install with: pip install zs-yaml[fast]"
            )

        _ryml_loader.ensure_available = fail

    def __exit__(self, *exc):
        self.module.ensure_available = self.previous


def test_default_is_pyyaml():
    print("\nTesting loader selection...")
    with _EnvVar(None):
        assert _yt._resolve_loader(None) is _yt._load_pyyaml, (
            "the default loader must stay PyYAML"
        )
    print("   \u2713 default is PyYAML")


def test_env_var_outranks_code():
    with _EnvVar('pyyaml'):
        assert _yt._resolve_loader('ryml') is _yt._load_pyyaml, (
            f"{_yt.LOADER_ENV_VAR}=pyyaml must override a loader chosen in code"
        )
        previous = YamlTransformer.LOADER
        YamlTransformer.LOADER = 'ryml'
        try:
            assert _yt._resolve_loader(None) is _yt._load_pyyaml, (
                f"{_yt.LOADER_ENV_VAR}=pyyaml must override YamlTransformer.LOADER"
            )
        finally:
            YamlTransformer.LOADER = previous
    print(f"   \u2713 {_yt.LOADER_ENV_VAR} outranks both code paths")


def test_unknown_loader_name_raises():
    with _EnvVar(None):
        for selection, label in ((lambda: _yt._resolve_loader('rapidyaml'), 'argument'),):
            try:
                selection()
                raise AssertionError(f"unknown loader name via {label} did not raise")
            except ValueError as e:
                assert 'rapidyaml' in str(e) and 'ryml' in str(e), f"unhelpful message: {e}"
    with _EnvVar('nonsense'):
        try:
            _yt._resolve_loader(None)
            raise AssertionError("unknown loader name via env var did not raise")
        except ValueError:
            pass
    print("   \u2713 an unrecognised loader name raises on both paths")


def test_missing_rapidyaml_raises_when_selected_by_env():
    with _EnvVar('ryml'), _RapidyamlMissing():
        try:
            _yt._resolve_loader(None)
            raise AssertionError(
                f"{_yt.LOADER_ENV_VAR}=ryml without rapidyaml must raise, not fall back"
            )
        except ImportError as e:
            assert 'zs-yaml[fast]' in str(e), f"message does not say how to install: {e}"
    print("   \u2713 missing rapidyaml raises when selected by environment variable")


def test_missing_rapidyaml_warns_when_selected_in_code():
    with _EnvVar(None), _RapidyamlMissing():
        for describe, select in (
            ("loader= argument", lambda: _yt._resolve_loader('ryml')),
            ("YamlTransformer.LOADER", None),
        ):
            if select is None:
                previous = YamlTransformer.LOADER
                YamlTransformer.LOADER = 'ryml'
                select = lambda: _yt._resolve_loader(None)
            else:
                previous = None
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    resolved = select()
                assert resolved is _yt._load_pyyaml, (
                    f"{describe}: must fall back to PyYAML, got {resolved}"
                )
                assert len(caught) == 1 and issubclass(caught[0].category, RuntimeWarning), (
                    f"{describe}: expected one RuntimeWarning, got "
                    f"{[w.category.__name__ for w in caught]}"
                )
                assert 'zs-yaml[fast]' in str(caught[0].message), (
                    f"{describe}: warning does not say how to install: {caught[0].message}"
                )
            finally:
                if previous is not None:
                    YamlTransformer.LOADER = previous
    print("   \u2713 missing rapidyaml warns and falls back when selected in code")


def test_transform_still_works_without_rapidyaml():
    with _EnvVar(None), _RapidyamlMissing():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            transformer = YamlTransformer(os.path.join(HERE, 'team1.yaml'), loader='ryml')
        assert transformer.data['name'] == 'Dream Team', (
            "falling back to PyYAML must still produce the document"
        )
    print("   \u2713 a document still converts when the fallback is taken")


if __name__ == "__main__":
    try:
        test_default_is_pyyaml()
        test_env_var_outranks_code()
        test_unknown_loader_name_raises()
        test_missing_rapidyaml_raises_when_selected_by_env()
        test_missing_rapidyaml_warns_when_selected_in_code()
        test_transform_still_works_without_rapidyaml()

        if not HAVE_RYML:
            print("\n\u26a0\ufe0f  rapidyaml is not installed; equivalence tests skipped.")
            print("   Install it with: pip install zs-yaml[fast]")
            sys.exit(0)

        test_scalar_corpus()
        test_example_yaml_files()
        test_delegated_constructs()
        test_edge_cases()
        test_multi_document_matches_pyyaml()
        test_malformed_input_reports_like_pyyaml()
        test_memoized_coercion_matches_uncached()
        test_conversion_is_byte_identical()
        test_loader_propagates_into_includes()

        print("\n\u2705 All ryml loader tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n\u274c Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
