"""
This module contains the logic to cover the following conversions:
- yaml to bin: Converts a YAML file to a binary file using zserio serialization.
               Custom transformations can be applied to the YAML data before conversion.
- bin to yaml: Converts a binary file to a YAML file using zserio deserialization.
               The conversion requires the schema module and type information to be
               specified in the _meta section of the YAML file.
- json to yaml: Converts a JSON file to a YAML file. This is a plain conversion without
                applying any transformations.
- yaml to json: Converts a YAML file to a JSON file. Custom transformations can be applied
                to the YAML data before conversion.
"""

import yaml
import json
import importlib
import zserio

from zserio.bitbuffer import BitBuffer
from zserio.typeinfo import TypeAttribute, MemberAttribute

from .yaml_transformer import YamlTransformer, TransformationError

__all__ = [
    # Primary conversion entries are surfaced at the top-level `zs_yaml`
    # package via re-exports in `__init__.py`. This submodule's docs page
    # only documents the *advanced* extras to avoid duplicating the
    # primary surface in two places.
    "yaml_to_yaml",
    "yaml_to_pyobj",
    "pyobj_to_yaml",
    "data_to_zserio_object",
]


# Field kinds. Non-array kinds (0..5) mirror how a field value is shaped in the
# dict; array kinds (6..11) wrap the corresponding element kind.
_KIND_SCALAR = 0
_KIND_ENUM = 1
_KIND_BITMASK = 2
_KIND_EXTERN = 3
_KIND_BYTES = 4
_KIND_COMPOUND = 5
_KIND_ARRAY_SCALAR = 6
_KIND_ARRAY_ENUM = 7
_KIND_ARRAY_BITMASK = 8
_KIND_ARRAY_EXTERN = 9
_KIND_ARRAY_BYTES = 10
_KIND_ARRAY_COMPOUND = 11

_ARRAY_KIND = {
    _KIND_SCALAR: _KIND_ARRAY_SCALAR,
    _KIND_ENUM: _KIND_ARRAY_ENUM,
    _KIND_BITMASK: _KIND_ARRAY_BITMASK,
    _KIND_EXTERN: _KIND_ARRAY_EXTERN,
    _KIND_BYTES: _KIND_ARRAY_BYTES,
    _KIND_COMPOUND: _KIND_ARRAY_COMPOUND,
}


class _FieldDescriptor:
    __slots__ = ("schema_name", "property_name", "type_info", "kind", "type_args")

    def __init__(self, member_info):
        self.schema_name = member_info.schema_name
        self.property_name = member_info.attributes[MemberAttribute.PROPERTY_NAME]
        self.type_info = member_info.type_info
        self.type_args = member_info.attributes.get(MemberAttribute.TYPE_ARGUMENTS)
        ti_attrs = self.type_info.attributes
        sn = self.type_info.schema_name
        if sn == "extern":
            base = _KIND_EXTERN
        elif sn == "bytes":
            base = _KIND_BYTES
        elif TypeAttribute.ENUM_ITEMS in ti_attrs:
            base = _KIND_ENUM
        elif TypeAttribute.BITMASK_VALUES in ti_attrs:
            base = _KIND_BITMASK
        elif TypeAttribute.FIELDS in ti_attrs:
            base = _KIND_COMPOUND
        else:
            base = _KIND_SCALAR
        is_array = MemberAttribute.ARRAY_LENGTH in member_info.attributes
        self.kind = _ARRAY_KIND[base] if is_array else base


class _CompoundDescriptor:
    __slots__ = ("py_type", "is_choice", "fields", "by_name")

    def __init__(self, type_info):
        self.py_type = type_info.py_type
        self.is_choice = TypeAttribute.SELECTOR in type_info.attributes
        self.fields = [_FieldDescriptor(m) for m in type_info.attributes[TypeAttribute.FIELDS]]
        self.by_name = {fd.schema_name: fd for fd in self.fields}


_COMPOUND_CACHE = {}


def _compound_descriptor(type_info):
    # Key on the type_info object itself, not id(type_info): id() reuses memory
    # addresses after GC, which would return a stale descriptor pointing at the
    # fields of a previous, unrelated zserio class.
    desc = _COMPOUND_CACHE.get(type_info)
    if desc is None:
        desc = _CompoundDescriptor(type_info)
        _COMPOUND_CACHE[type_info] = desc
    return desc


# ---- string <-> enum/bitmask helpers (shared by forward and reverse) --------

def _parse_enum_string_value(string_value, type_info):
    for item_info in type_info.attributes[TypeAttribute.ENUM_ITEMS]:
        if string_value == item_info.schema_name:
            return item_info.py_item
    return None


def _parse_bitmask_string_value(string_value, type_info):
    value = 0
    for identifier_with_spaces in string_value.split('|'):
        identifier = identifier_with_spaces.strip()
        match = False
        for item_info in type_info.attributes[TypeAttribute.BITMASK_VALUES]:
            if identifier == item_info.schema_name:
                match = True
                value |= item_info.py_item.value
                break
        if not match:
            return None
    return value


def _parse_bitmask_numeric_string_value(string_value):
    number_len = 1
    while number_len < len(string_value) and '0' <= string_value[number_len] <= '9':
        number_len += 1
    return int(string_value[0:number_len])


def _enum_from_string(string_value, type_info):
    if string_value:
        first_char = string_value[0]
        if ('A' <= first_char <= 'Z') or ('a' <= first_char <= 'z') or first_char == '_':
            py_item = _parse_enum_string_value(string_value, type_info)
            if py_item is not None:
                return py_item
    raise ValueError(f"Cannot create enum '{type_info.schema_name}' from string value '{string_value}'")


def _bitmask_from_string(string_value, type_info):
    if string_value:
        first_char = string_value[0]
        if ('A' <= first_char <= 'Z') or ('a' <= first_char <= 'z') or first_char == '_':
            value = _parse_bitmask_string_value(string_value, type_info)
            if value is not None:
                return type_info.py_type.from_value(value)
        elif '0' <= first_char <= '9':
            value = _parse_bitmask_numeric_string_value(string_value)
            if value is not None:
                return type_info.py_type.from_value(value)
    raise ValueError(f"Cannot create bitmask '{type_info.schema_name}' from string value '{string_value}'")


def _stringify_enum(value, type_info):
    for item in type_info.attributes[TypeAttribute.ENUM_ITEMS]:
        if item.py_item == value:
            return item.schema_name
    return f"{value.value} /* no match */"


def _stringify_bitmask(value, type_info):
    bitmask_value = value.value
    parts = []
    value_check = 0
    for item_info in type_info.attributes[TypeAttribute.BITMASK_VALUES]:
        item_value = item_info.py_item.value
        is_zero = item_value == 0
        if ((not is_zero and bitmask_value & item_value == item_value)
                or (is_zero and bitmask_value == 0)):
            value_check |= item_value
            parts.append(item_info.schema_name)
    if not parts:
        return f"{bitmask_value} /* no match */"
    joined = " | ".join(parts)
    if bitmask_value != value_check:
        return f"{bitmask_value} /* partial match: {joined} */"
    return joined


def _bitbuffer_from_dict(value):
    buffer = value.get('buffer', [])
    bit_size = value.get('bitSize', len(buffer) * 8)
    return BitBuffer(bytes(buffer), bit_size)


def _bytes_from_dict(value):
    return bytearray(value.get('buffer', []))


def _convert_enum_value(value, type_info):
    if isinstance(value, str):
        return _enum_from_string(value, type_info)
    return type_info.py_type(value)


def _convert_bitmask_value(value, type_info):
    if isinstance(value, str):
        return _bitmask_from_string(value, type_info)
    return type_info.py_type.from_value(value)


# ---- forward: dict -> zserio object ----------------------------------------

def _build_compound(desc, data, args):
    obj = desc.py_type(*args)
    for key, value in data.items():
        fd = desc.by_name[key]
        _assign_field(obj, fd, value)
    return obj


def _assign_field(obj, fd, value):
    property_name = fd.property_name
    if value is None:
        setattr(obj, property_name, None)
        return
    kind = fd.kind
    ti = fd.type_info
    if kind == _KIND_SCALAR:
        setattr(obj, property_name, value)
    elif kind == _KIND_COMPOUND:
        setattr(obj, property_name, _construct_child(ti, value, obj, fd.type_args, None))
    elif kind == _KIND_ENUM:
        setattr(obj, property_name, _convert_enum_value(value, ti))
    elif kind == _KIND_BITMASK:
        setattr(obj, property_name, _convert_bitmask_value(value, ti))
    elif kind == _KIND_EXTERN:
        setattr(obj, property_name, _bitbuffer_from_dict(value))
    elif kind == _KIND_BYTES:
        setattr(obj, property_name, _bytes_from_dict(value))
    elif kind == _KIND_ARRAY_SCALAR:
        setattr(obj, property_name, list(value))
    elif kind == _KIND_ARRAY_COMPOUND:
        type_args = fd.type_args
        setattr(obj, property_name,
                [_construct_child(ti, v, obj, type_args, i) for i, v in enumerate(value)])
    elif kind == _KIND_ARRAY_ENUM:
        setattr(obj, property_name, [_convert_enum_value(v, ti) for v in value])
    elif kind == _KIND_ARRAY_BITMASK:
        setattr(obj, property_name, [_convert_bitmask_value(v, ti) for v in value])
    elif kind == _KIND_ARRAY_EXTERN:
        setattr(obj, property_name, [_bitbuffer_from_dict(v) for v in value])
    elif kind == _KIND_ARRAY_BYTES:
        setattr(obj, property_name, [_bytes_from_dict(v) for v in value])


def _construct_child(type_info, data, parent, type_args_lambdas, element_index):
    desc = _compound_descriptor(type_info)
    if type_args_lambdas:
        args = [lam(parent, element_index) for lam in type_args_lambdas]
    else:
        args = ()
    return _build_compound(desc, data, args)


def _dict_to_zserio_object(data, ImportedType, init_args):
    desc = _compound_descriptor(ImportedType.type_info())
    return _build_compound(desc, data, init_args or ())


def data_to_zserio_object(data, imported_type, init_args=None):
    """
    Build a Zserio object directly from an in-memory Python ``dict`` tree.

    This is the same fast path used internally by :func:`yaml_to_bin` and
    :func:`yaml_to_pyobj`: it walks the schema descriptor for ``imported_type``
    and assigns fields from ``data`` field-by-field, with no JSON detour. For
    payloads with large ``extern`` blobs (millions of bytes), this avoids the
    text-based JSON roundtrip that ``zserio.from_json_stream`` would otherwise
    perform.

    The expected ``data`` shape is the same dict tree produced by zs-yaml's
    transformer (or by :func:`bin_to_dict` in the reverse direction):

    - extern fields use ``{"buffer": [int, ...], "bitSize": int}``
    - bytes fields use ``{"buffer": [int, ...]}``
    - enums and bitmasks accept either their string spelling or numeric value
    - compound fields are nested dicts; arrays of compounds are lists of dicts

    Args:
        data: The transformed Python tree (without ``_meta``).
        imported_type: The generated zserio class (e.g. ``team.api.Team``).
        init_args: Optional iterable of zserio initialization arguments. ``None``
            and ``()`` are equivalent.

    Returns:
        An instance of ``imported_type`` populated from ``data``.
    """
    return _dict_to_zserio_object(data, imported_type, init_args)


# ---- reverse: zserio object -> dict ----------------------------------------

def _compound_to_dict(desc, obj):
    out = {}
    if desc.is_choice:
        choice_tag = obj.choice_tag
        if choice_tag != obj.UNDEFINED_CHOICE:
            fd = desc.fields[choice_tag]
            _read_field(obj, fd, out)
    else:
        for fd in desc.fields:
            _read_field(obj, fd, out)
    return out


def _read_field(obj, fd, out):
    value = getattr(obj, fd.property_name)
    schema_name = fd.schema_name
    if value is None:
        out[schema_name] = None
        return
    kind = fd.kind
    ti = fd.type_info
    if kind == _KIND_SCALAR:
        out[schema_name] = value
    elif kind == _KIND_COMPOUND:
        out[schema_name] = _compound_to_dict(_compound_descriptor(ti), value)
    elif kind == _KIND_ENUM:
        out[schema_name] = _stringify_enum(value, ti)
    elif kind == _KIND_BITMASK:
        out[schema_name] = _stringify_bitmask(value, ti)
    elif kind == _KIND_EXTERN:
        out[schema_name] = {"buffer": list(value.buffer), "bitSize": value.bitsize}
    elif kind == _KIND_BYTES:
        out[schema_name] = {"buffer": list(value)}
    elif kind == _KIND_ARRAY_SCALAR:
        out[schema_name] = list(value)
    elif kind == _KIND_ARRAY_COMPOUND:
        sub_desc = _compound_descriptor(ti)
        out[schema_name] = [_compound_to_dict(sub_desc, el) for el in value]
    elif kind == _KIND_ARRAY_ENUM:
        out[schema_name] = [_stringify_enum(v, ti) for v in value]
    elif kind == _KIND_ARRAY_BITMASK:
        out[schema_name] = [_stringify_bitmask(v, ti) for v in value]
    elif kind == _KIND_ARRAY_EXTERN:
        out[schema_name] = [{"buffer": list(v.buffer), "bitSize": v.bitsize} for v in value]
    elif kind == _KIND_ARRAY_BYTES:
        out[schema_name] = [{"buffer": list(v)} for v in value]


def _zserio_object_to_dict(zserio_object):
    return _compound_to_dict(_compound_descriptor(zserio_object.type_info()), zserio_object)


def _yaml_to_zserio_object(yaml_input_path):
    """
    Converts a YAML file to a Zserio object.

    Args:
        yaml_input_path (str): Path to the input YAML file.

    Returns:
        tuple: A tuple containing (zserio_object, meta)

    Raises:
        ValueError: If schema_module and schema_type are not specified in the _meta
            section of the YAML file.
    """
    try:
        transformed_data, meta = yaml_to_yaml(yaml_input_path)
    except TransformationError:
        raise
    except Exception as e:
        raise TransformationError(
            f"Failed to process YAML file: {e}",
            file_path=yaml_input_path,
            original_error=e
        )

    schema_module = meta.get('schema_module')
    schema_type = meta.get('schema_type')
    init_args = meta.get('initialization_args', [])

    if not schema_module or not schema_type:
        raise ValueError("Error: schema_module and schema_type must be specified in the _meta section")

    try:
        module = importlib.import_module(schema_module)
        ImportedType = getattr(module, schema_type)
        if ImportedType is None:
            raise ValueError(f"Type {schema_type} not found in module {schema_module}")

        zserio_object = _dict_to_zserio_object(transformed_data, ImportedType, init_args)
        return zserio_object, meta
    except TransformationError:
        raise
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'file_path') and e.file_path:
            file_prefix = f"Error in file '{e.file_path}':"
            if error_msg.startswith(file_prefix):
                error_msg = error_msg[len(file_prefix):].strip()
            raise TransformationError(
                error_msg,
                file_path=e.file_path,
                original_error=e
            )
        raise TransformationError(
            f"Failed to create {schema_type} from {schema_module}: {e}",
            file_path=yaml_input_path,
            original_error=e
        )

def yaml_to_bin(yaml_input_path, bin_output_path):
    """
    Converts a YAML file to a binary file using Zserio serialization.

    Args:
        yaml_input_path (str): Path to the input YAML file.
        bin_output_path (str): Path to the output binary file.
    """
    try:
        zserio_object, _ = _yaml_to_zserio_object(yaml_input_path)
        zserio.serialize_to_file(zserio_object, bin_output_path)
    except TransformationError:
        raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert YAML to binary: {e}",
            file_path=yaml_input_path,
            original_error=e
        )


def yaml_to_pyobj(yaml_input_path):
    """
    Converts a YAML file to an in-memory Python object using Zserio deserialization.

    Args:
        yaml_input_path (str): Path to the input YAML file.

    Returns:
        object: The deserialized Python object.
    """
    try:
        zserio_object, _ = _yaml_to_zserio_object(yaml_input_path)
        return zserio_object
    except TransformationError:
        raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert YAML to Python object: {e}",
            file_path=yaml_input_path,
            original_error=e
        )

def yaml_to_yaml(yaml_input_path, yaml_output_path=None):
    """
    Applies all transformations and template substitution to
    the input YAML to come up with the output YAML.

    Args:
        yaml_input_path (str): Path to the input YAML file.
        yaml_output_path (str): Path to the output YAML file.
    """
    transformer = YamlTransformer.get_or_create(yaml_input_path)
    meta = transformer.get_meta()

    if yaml_output_path:
        output_data = {'_meta': meta}
        output_data.update(transformer.data)
        with open(yaml_output_path, 'w') as yaml_file:
            yaml.dump(output_data, yaml_file, Dumper=yaml.CDumper, default_flow_style=False, sort_keys=False)

    return transformer.data, meta


def yaml_to_json(yaml_input_path, json_output_path):
    """
    Converts a YAML file to a JSON file.

    Args:
        yaml_input_path (str): Path to the input YAML file.
        json_output_path (str): Path to the output JSON file.

    Returns:
        dict: The _meta section from the YAML file, if present.
    """
    try:
        transformed_data, meta = yaml_to_yaml(yaml_input_path)

        with open(json_output_path, 'w') as json_file:
            json.dump(transformed_data, json_file, indent=2)

        return meta
    except TransformationError:
        raise  # Already has file context, just re-raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert YAML to JSON: {e}",
            file_path=yaml_input_path,
            original_error=e
        )


def json_to_yaml(json_input_path, yaml_output_path):
    """
    Converts a JSON file to a YAML file. This is a plain conversion without applying
    any transformations.

    Args:
        json_input_path (str): Path to the input JSON file.
        yaml_output_path (str): Path to the output YAML file.
    """
    with open(json_input_path, 'r') as json_file:
        data = json.load(json_file)
    with open(yaml_output_path, 'w') as yaml_file:
        yaml.safe_dump(data, yaml_file, default_flow_style=False, sort_keys=False)


def bin_to_dict(bin_input, schema_module, schema_type, init_args=None):
    """
    Converts binary data to a Python dictionary using Zserio deserialization.

    Args:
        bin_input (str or bytes): Path to the input binary file, or binary data as bytes.
        schema_module (str): The schema module name (e.g., 'ndslive.schema.smart.v2024_11.tile.api').
        schema_type (str): The schema type name (e.g., 'SmartLayerTile').
        init_args (list, optional): Initialization arguments for zserio deserialization.

    Returns:
        tuple: (data_dict, metadata_dict) where data_dict is the deserialized data
               and metadata_dict contains schema_module and schema_type.

    Raises:
        TransformationError: If deserialization fails.
    """
    if init_args is None:
        init_args = []

    try:
        module = importlib.import_module(schema_module)
        ImportedType = getattr(module, schema_type)
        if ImportedType is None:
            raise ValueError(f"Type {schema_type} not found in module {schema_module}")

        # Handle both file path and bytes input
        if isinstance(bin_input, bytes):
            zserio_object = zserio.deserialize_from_bytes(ImportedType, bin_input, *init_args)
        else:
            zserio_object = zserio.deserialize_from_file(ImportedType, bin_input, *init_args)

        data = _zserio_object_to_dict(zserio_object)

        metadata = {
            'schema_module': schema_module,
            'schema_type': schema_type
        }
        if init_args:
            metadata['initialization_args'] = init_args

        return data, metadata
    except Exception as e:
        file_info = bin_input if isinstance(bin_input, str) else "<bytes>"
        raise TransformationError(
            f"Failed to convert binary to dict: {e}",
            file_path=file_info,
            original_error=e
        )


def bin_to_yaml(bin_input_path, yaml_output_path):
    """
    Converts a binary file to a YAML file using Zserio deserialization.

    Args:
        bin_input_path (str): Path to the input binary file.
        yaml_output_path (str): Path to the output YAML file.

    Raises:
        ValueError: If schema_module and schema_type are not specified in the _meta
            section of the YAML file, or if the specified Zserio type is not found
            in the module.
    """
    try:
        with open(yaml_output_path, 'r') as yaml_file:
            meta = yaml.safe_load(yaml_file)

        schema_module = meta.get('_meta', {}).get('schema_module')
        schema_type = meta.get('_meta', {}).get('schema_type')
        init_args = meta.get('_meta', {}).get('initialization_args', [])

        if not schema_module or not schema_type:
            raise ValueError("Error: schema_module and schema_type must be specified in the _meta section of the YAML file")

        data, metadata = bin_to_dict(bin_input_path, schema_module, schema_type, init_args)

        # Create a new dictionary to ensure _meta comes first
        final_data = {'_meta': meta['_meta']}
        final_data.update(data)

        with open(yaml_output_path, 'w') as yaml_file:
            yaml.safe_dump(final_data, yaml_file, default_flow_style=False, sort_keys=False)
    except TransformationError:
        raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert binary to YAML: {e}",
            file_path=bin_input_path,
            original_error=e
        )


def pyobj_to_yaml(zserio_object, yaml_output_path):
    """
    Converts a zserio Python object to a YAML file.

    Args:
        zserio_object: The zserio Python object to convert.
        yaml_output_path (str): Path to the output YAML file.

    Raises:
        TransformationError: If the conversion fails.
    """
    try:
        # Extract schema information from the zserio object
        schema_module = zserio_object.__class__.__module__
        schema_type = zserio_object.__class__.__name__

        data = _zserio_object_to_dict(zserio_object)

        # Create a new dictionary to ensure _meta comes first
        final_data = {'_meta': {
            'schema_module': schema_module,
            'schema_type': schema_type
        }}
        final_data.update(data)

        # Write to YAML file
        with open(yaml_output_path, 'w') as yaml_file:
            yaml.dump(final_data, yaml_file, Dumper=yaml.CDumper, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise TransformationError(
            f"Failed to convert Python object to YAML: {e}",
            file_path=yaml_output_path,
            original_error=e
        )
