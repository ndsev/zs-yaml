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

from .yaml_transformer import YamlTransformer, TransformationError

def _yaml_to_zserio_object(yaml_input_path):
    """
    Converts a YAML file to a Zserio object.

    Args:
        yaml_input_path (str): Path to the input YAML file.

    Returns:
        tuple: A tuple containing (zserio_object, temp_json_path, meta)

    Raises:
        ValueError: If schema_module and schema_type are not specified in the _meta
            section of the YAML file.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json_file:
        temp_json_path = temp_json_file.name

    try:
        meta = yaml_to_json(yaml_input_path, temp_json_path)
    except TransformationError:
        raise  # Already has file context, just re-raise
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

        zserio_object = zserio.from_json_file(ImportedType, temp_json_path, *init_args)
        return zserio_object, temp_json_path, meta
    except TransformationError:
        raise  # Already has file context, just re-raise
    except Exception as e:
        # Check if this is a zserio error that might already have file context
        error_msg = str(e)
        if hasattr(e, 'file_path') and e.file_path:
            # This error already has file context from an included file
            # Strip redundant "Error in file '...':" prefix if present
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
    temp_json_path = None
    try:
        zserio_object, temp_json_path, _ = _yaml_to_zserio_object(yaml_input_path)
        zserio.serialize_to_file(zserio_object, bin_output_path)
    except TransformationError:
        raise  # Already has file context, just re-raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert YAML to binary: {e}",
            file_path=yaml_input_path,
            original_error=e
        )
    finally:
        if temp_json_path is not None:
            os.remove(temp_json_path)

def yaml_to_pyobj(yaml_input_path):
    """
    Converts a YAML file to an in-memory Python object using Zserio deserialization.

    Args:
        yaml_input_path (str): Path to the input YAML file.

    Returns:
        object: The deserialized Python object.
    """
    temp_json_path = None
    try:
        zserio_object, temp_json_path, _ = _yaml_to_zserio_object(yaml_input_path)
        return zserio_object
    except TransformationError:
        raise  # Already has file context, just re-raise
    except Exception as e:
        raise TransformationError(
            f"Failed to convert YAML to Python object: {e}",
            file_path=yaml_input_path,
            original_error=e
        )
    finally:
        if temp_json_path is not None:
            os.remove(temp_json_path)

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

        module = importlib.import_module(schema_module)
        ImportedType = getattr(module, schema_type)
        if ImportedType is None:
            raise ValueError(f"Type {schema_type} not found in module {schema_module}")

        zserio_object = zserio.deserialize_from_file(ImportedType, bin_input_path, *init_args)
        json_data = zserio.to_json_string(zserio_object)

        data = json.loads(json_data)

        # Create a new dictionary to ensure _meta comes first
        final_data = {'_meta': meta['_meta']}
        final_data.update(data)

        with open(yaml_output_path, 'w') as yaml_file:
            yaml.safe_dump(final_data, yaml_file, default_flow_style=False, sort_keys=False)
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

        # Convert the object to JSON
        json_data = zserio.to_json_string(zserio_object)
        data = json.loads(json_data)

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
