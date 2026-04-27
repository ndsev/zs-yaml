"""zs_yaml — YAML as a text format for zserio test data.

``zs_yaml`` lets you author and inspect zserio-encoded data in YAML rather
than raw binary or JSON. The YAML carries the schema reference in a
``_meta`` section, so a single round-trip is enough to (de)serialise:

.. code-block:: python

    from zs_yaml import yaml_to_bin, bin_to_yaml

    yaml_to_bin("input.yaml", "output.bin")    # serialise YAML → zserio binary
    bin_to_yaml("input.bin", "output.yaml")    # deserialise back to YAML
                                               # (target YAML must already
                                               # contain a `_meta` section)

The ``_meta`` section names the schema module and type::

    _meta:
      schema_module: ndslive.schema.smart.v2024_11.tile.api
      schema_type: SmartLayerTile

What's in this package
======================

Conversion entry points
    :func:`yaml_to_bin`, :func:`bin_to_yaml`,
    :func:`yaml_to_json`, :func:`json_to_yaml`,
    :func:`bin_to_dict` — the everyday API.
    Defined in :mod:`zs_yaml.convert`; advanced helpers
    (``yaml_to_yaml``, ``yaml_to_pyobj``, ``pyobj_to_yaml``) live there too.

Transformation engine
    :class:`YamlTransformer` and :exc:`TransformationError` — for use when
    you need to drive transformations programmatically rather than via the
    CLI. Defined in :mod:`zs_yaml.yaml_transformer`.

Version info
    :func:`get_version_info`, :data:`__version__`.

Built-in YAML transformations (e.g. ``!insert_yaml``, ``!repeat_node``,
``!from_wgs84_2d``) are documented in the package's USAGE guide rather
than as Python API — they're invoked from inside YAML files via the
``_f:`` marker, not by Python ``import``.

Command-line
============

Most users will reach for the CLI rather than this Python API:

.. code-block:: shell

    zs-yaml input.yaml output.bin
    zs-yaml input.bin  output.yaml
"""

from .convert import yaml_to_json, yaml_to_bin, bin_to_yaml, bin_to_dict, json_to_yaml
from .yaml_transformer import YamlTransformer, TransformationError

try:
    from ._version import __version__
except ImportError:
    # Fallback for editable installs
    try:
        from importlib.metadata import version
        __version__ = version("zs-yaml")
    except Exception:
        __version__ = "0.0.0+unknown"


def get_version_info():
    """Return the installed zs_yaml version string."""
    return __version__


__all__ = [
    # Conversion entry points
    "yaml_to_bin",
    "bin_to_yaml",
    "yaml_to_json",
    "json_to_yaml",
    "bin_to_dict",
    # Transformation engine
    "YamlTransformer",
    "TransformationError",
    # Version info
    "get_version_info",
    "__version__",
]
