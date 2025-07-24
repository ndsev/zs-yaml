from .convert import yaml_to_json, yaml_to_bin, bin_to_yaml, json_to_yaml
from .yaml_transformer import YamlTransformer

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
    return __version__