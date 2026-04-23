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

from zserio.creator import ZserioTreeCreator
from zserio.bitbuffer import BitBuffer
from zserio.exception import PythonRuntimeException
from zserio.typeinfo import TypeAttribute
from zserio.walker import Walker, WalkObserver

from .yaml_transformer import YamlTransformer, TransformationError


class _CachedZserioTreeCreator(ZserioTreeCreator):
    """ZserioTreeCreator with a per-TypeInfo cache for field lookups.

    zserio's stock `_find_member_info` is an O(N) linear scan over the
    compound's fields on every call. For schemas with many fields and many
    records, that dominates the creator overhead. The cache makes lookups
    O(1) at the cost of one dict build per unique compound type.
    """

    _fields_cache = {}

    @staticmethod
    def _find_member_info(type_info, name):
        tid = id(type_info)
        mp = _CachedZserioTreeCreator._fields_cache.get(tid)
        if mp is None:
            mp = {m.schema_name: m for m in type_info.attributes[TypeAttribute.FIELDS]}
            _CachedZserioTreeCreator._fields_cache[tid] = mp
        member = mp.get(name)
        if member is None:
            raise PythonRuntimeException(
                f"ZserioTreeCreator: Field '{name}' not found in '{type_info.schema_name}'!"
            )
        return member


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


def _convert_scalar(value, type_info):
    if value is None:
        return None
    if TypeAttribute.ENUM_ITEMS in type_info.attributes:
        if isinstance(value, str):
            return _enum_from_string(value, type_info)
        return type_info.py_type(value)
    if TypeAttribute.BITMASK_VALUES in type_info.attributes:
        if isinstance(value, str):
            return _bitmask_from_string(value, type_info)
        return type_info.py_type.from_value(value)
    return value


def _bitbuffer_from_dict(value):
    buffer = value.get('buffer', [])
    bit_size = value.get('bitSize', len(buffer) * 8)
    return BitBuffer(bytes(buffer), bit_size)


def _bytes_from_dict(value):
    return bytearray(value.get('buffer', []))


def _build_object_value(schema_name, value):
    if schema_name == "extern":
        return _bitbuffer_from_dict(value)
    if schema_name == "bytes":
        return _bytes_from_dict(value)
    return None


def _walk_compound(creator, data):
    for key, value in data.items():
        field_type = creator.get_field_type(key)
        schema_name = field_type.schema_name
        if isinstance(value, dict):
            object_value = _build_object_value(schema_name, value)
            if object_value is not None:
                creator.set_value(key, object_value)
            else:
                creator.begin_compound(key)
                _walk_compound(creator, value)
                creator.end_compound()
        elif isinstance(value, list):
            creator.begin_array(key)
            _walk_array(creator, value)
            creator.end_array()
        else:
            creator.set_value(key, _convert_scalar(value, field_type))


def _walk_array(creator, items):
    element_type = creator.get_element_type()
    schema_name = element_type.schema_name
    for item in items:
        if isinstance(item, dict):
            object_value = _build_object_value(schema_name, item)
            if object_value is not None:
                creator.add_value_element(object_value)
            else:
                creator.begin_compound_element()
                _walk_compound(creator, item)
                creator.end_compound_element()
        elif isinstance(item, list):
            raise ValueError("Nested arrays are not supported by zserio")
        else:
            creator.add_value_element(_convert_scalar(item, element_type))


def _dict_to_zserio_object(data, ImportedType, init_args):
    creator = _CachedZserioTreeCreator(ImportedType.type_info(), *init_args)
    creator.begin_root()
    _walk_compound(creator, data)
    return creator.end_root()


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


def _encode_value(value, type_info):
    if value is None:
        return None
    schema_name = type_info.schema_name
    if schema_name == "extern":
        return {"buffer": list(value.buffer), "bitSize": value.bitsize}
    if schema_name == "bytes":
        return {"buffer": list(value)}
    if TypeAttribute.ENUM_ITEMS in type_info.attributes:
        return _stringify_enum(value, type_info)
    if TypeAttribute.BITMASK_VALUES in type_info.attributes:
        return _stringify_bitmask(value, type_info)
    return value


class _DictBuilder(WalkObserver):
    """Walker observer that builds a plain dict mirroring zserio's JSON format."""

    def __init__(self):
        self._stack = []
        self.result = None

    def _place(self, member_info, container):
        parent = self._stack[-1]
        if isinstance(parent, list):
            parent.append(container)
        else:
            parent[member_info.schema_name] = container

    def begin_root(self, compound):
        self.result = {}
        self._stack.append(self.result)

    def end_root(self, compound):
        self._stack.pop()

    def begin_array(self, array, member_info):
        new_array = []
        self._stack[-1][member_info.schema_name] = new_array
        self._stack.append(new_array)

    def end_array(self, array, member_info):
        self._stack.pop()

    def begin_compound(self, compound, member_info, element_index=None):
        new_compound = {}
        self._place(member_info, new_compound)
        self._stack.append(new_compound)

    def end_compound(self, compound, member_info, element_index=None):
        self._stack.pop()

    def visit_value(self, value, member_info, element_index=None):
        encoded = _encode_value(value, member_info.type_info)
        parent = self._stack[-1]
        if isinstance(parent, list):
            parent.append(encoded)
        else:
            parent[member_info.schema_name] = encoded


def _zserio_object_to_dict(zserio_object):
    builder = _DictBuilder()
    Walker(builder).walk(zserio_object)
    return builder.result


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
