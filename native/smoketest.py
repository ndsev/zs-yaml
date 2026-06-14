"""Post-build smoke test for the native wheel (run by cibuildwheel).

Exercises the rapidyaml parse + python-tree build in C end-to-end, so the test
catches both a failed import (missing/unlinked vendored rapidyaml symbol) and a
broken parse.
"""
import zs_yaml_native

# coerce_callback is applied to plain scalars the C parser does not fast-path
# itself; identity keeps the test standalone (no zs-yaml dependency). We assert
# structure and tolerate the int fast path ("1" may come back as 1), since full
# scalar-coercion parity is covered by zs-yaml's own suite.
tree = zs_yaml_native.load(b"a: 1\nb:\n  - x\n  - y\n", lambda s: s)
assert set(tree) == {"a", "b"}, tree
assert str(tree["a"]) == "1", tree
assert tree["b"] == ["x", "y"], tree
print("zs_yaml_native OK:", tree)
