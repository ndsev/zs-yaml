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
import tempfile
import os

from .yaml_transformer import YamlTransformer

def _json_to_zs_bin(json_input_path, bin_output_path, module_name, type_name):
    """
    Converts a JSON file to a binary file using Zserio serialization.

    Args:
        json_input_path (str): Path to the input JSON file.
        bin_output_path (str): Path to the output binary file.
        module_name (str): Name of the Zserio module containing the schema.
        type_name (str): Name of the Zserio type to be used for serialization.

    Raises:
        ValueError: If the specified Zserio type is not found in the module.
    """
    module = importlib.import_module(module_name)
    ImportedType = getattr(module, type_name)
    if ImportedType is None:
        raise ValueError(f"Type {type_name} not found in module {module_name}")
    zserio_object = zserio.from_json_file(ImportedType, json_input_path)
    zserio.serialize_to_file(zserio_object, bin_output_path)


def yaml_to_json(yaml_input_path, json_output_path, transformer=None):
    """
    Converts a YAML file to a JSON file.

    Args:
        yaml_input_path (str): Path to the input YAML file.
        json_output_path (str): Path to the output JSON file.
        transformer (YamlTransformer, optional): YamlTransformer instance for applying
            custom transformations. If not provided, a default instance will be used.

    Returns:
        dict: The _meta section from the YAML file, if present.
    """
    if transformer is None:
        transformer = YamlTransformer()

    with open(yaml_input_path, 'r') as yaml_file:
        data = yaml.safe_load(yaml_file)

    meta = data.pop('_meta', {})
    transformation_module = meta.get('transformation_module')

    if transformation_module:
        transformer.load_functions(transformation_module)

    if transformer:
        data = transformer.transform(data)

    with open(json_output_path, 'w') as json_file:
        json.dump(data, json_file, indent=2)

    return meta


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


def yaml_to_bin(yaml_input_path, bin_output_path, transformer=None):
    """
    Converts a YAML file to a binary file using Zserio serialization.

    Args:
        yaml_input_path (str): Path to the input YAML file.
        bin_output_path (str): Path to the output binary file.
        transformer (YamlTransformer, optional): YamlTransformer instance for applying
            custom transformations. If not provided, a default instance will be used.

    Raises:
        ValueError: If schema_module and schema_type are not specified in the _meta
            section of the YAML file.
    """
    if transformer is None:
        transformer = YamlTransformer()

    with tempfile.NamedTemporaryFile(delete=False) as temp_json_file:
        temp_json_path = temp_json_file.name

    try:
        meta = yaml_to_json(yaml_input_path, temp_json_path, transformer)
        schema_module = meta.get('schema_module')
        schema_type = meta.get('schema_type')

        if not schema_module or not schema_type:
            raise ValueError("Error: schema_module and schema_type must be specified in the _meta section for binary output")

        _json_to_zs_bin(temp_json_path, bin_output_path, schema_module, schema_type)
    finally:
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)


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
    with open(yaml_output_path, 'r') as yaml_file:
        meta = yaml.safe_load(yaml_file)

    schema_module = meta.get('_meta', {}).get('schema_module')
    schema_type = meta.get('_meta', {}).get('schema_type')
    if not schema_module or not schema_type:
        raise ValueError("Error: schema_module and schema_type must be specified in the _meta section of the YAML file")

    module = importlib.import_module(schema_module)
    ImportedType = getattr(module, schema_type)
    if ImportedType is None:
        raise ValueError(f"Type {schema_type} not found in module {schema_module}")

    zserio_object = zserio.deserialize_from_file(ImportedType, bin_input_path)
    json_data = zserio.to_json_string(zserio_object)

    data = json.loads(json_data)

    # Create a new dictionary to ensure _meta comes first
    final_data = {'_meta': meta['_meta']}
    final_data.update(data)

    with open(yaml_output_path, 'w') as yaml_file:
        yaml.safe_dump(final_data, yaml_file, default_flow_style=False, sort_keys=False)