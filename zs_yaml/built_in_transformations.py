from functools import reduce
import copy
import importlib
import json
import operator
import os
import zserio
import yaml

# Cache to store loaded YAML/JSON files
_file_cache = {}

def insert_yaml_as_extern(transformer, file, template_args=None):
    """
    Include external YAML by transforming it to JSON and using zserio.

    Args:
        transformer (YamlTransformer): The transformer instance.
        file (str): Path to the external YAML file.
        template_args (dict, optional): A dictionary of template arguments for placeholder replacement.

    Returns:
        dict: A dictionary containing the binary data and its bit size.
    """
    abs_path = transformer.resolve_path(file)
    external_transformer = transformer.__class__(abs_path, template_args, initial_transformations=transformer.transformations)
    processed_data = external_transformer.data
    meta = external_transformer.metadata

    schema_module = meta.get('schema_module')
    schema_type = meta.get('schema_type')

    if not schema_module or not schema_type:
        raise ValueError(f"Error: schema_module and schema_type must be specified in the _meta section of the YAML file: {file}")

    json_string = json.dumps(processed_data)

    # Convert JSON to binary using zserio
    module = importlib.import_module(schema_module)
    ImportedType = getattr(module, schema_type)
    zserio_object = zserio.from_json_string(ImportedType, json_string)
    writer = zserio.BitStreamWriter()
    zserio_object.write(writer)
    bits = zserio.BitBuffer(writer.byte_array, writer.bitposition)

    # Encode the binary data
    encoded_bytes = list(bits.buffer)
    data = {"buffer": encoded_bytes, "bitSize": bits.bitsize}

    return data

def insert_yaml(transformer, file, node_path='', template_args=None, cache_file=True):
    """
    Insert content from an external YAML or JSON file, optionally selecting a specific node.
    Uses a cache to avoid reloading the same file multiple times if caching is enabled.

    Args:
        transformer (YamlTransformer): The transformer instance.
        file (str): Path to the external YAML or JSON file.
        node_path (str, optional): Dot-separated path to the node to be inserted.
                                   Defaults to '', which selects the entire file content.
        template_args (dict, optional): A dictionary of template arguments for placeholder replacement.
        cache_file (bool, optional): Whether to cache the file content. Defaults to True.

    Returns:
        The selected content from the external file.
    """
    def get_from_dict(data_dict, map_list):
        return reduce(operator.getitem, map_list, data_dict)

    abs_path = os.path.abspath(os.path.join(os.path.dirname(transformer.yaml_file_path), file))
    transformed_yaml = transformer.__class__.get_or_create(abs_path, template_args, transformer.transformations)

    data = transformed_yaml.data

    if not node_path:
        # Deep copy is not good from performance point of
        # view but it still avoids loading the file again and
        # again and the nodes don't appear as alias but are
        # are really copies when used multiple times
        return copy.deepcopy(data)

    # Parse the path and extract the node
    parsed_path = []
    current_key = ""
    for char in node_path:
        if char == '.':
            if current_key:
                parsed_path.append(current_key)
                current_key = ""
        elif char == '[':
            if current_key:
                parsed_path.append(current_key)
                current_key = ""
        elif char == ']':
            if current_key:
                parsed_path.append(int(current_key))
                current_key = ""
        else:
            current_key += char
    if current_key:
        parsed_path.append(current_key)

    try:
        return get_from_dict(data, parsed_path)
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"Invalid path: {node_path} in file {file}")

def repeat_node(transformer, node, count):
    """
    Repeat a specific node n times and return as a list.

    Args:
        transformer (YamlTransformer): The transformer instance.
        node: The node to be repeated.
        count (int): The number of times to repeat the node.

    Returns:
        list: A list containing the repeated node.
    """
    return [copy.deepcopy(node) for _ in range(count)]


def extract_extern_as_yaml(transformer, buffer, bitSize, schema_module, schema_type, file_name):
    """
    Extract binary data and save as an external YAML file.

    Note: This function contains some redundancy with the bin_to_yaml function
    in zs_yaml.convert to avoid circular imports. If modifying this function,
    please consider updating bin_to_yaml as well, and vice versa.

    Args:
        transformer (YamlTransformer): The transformer instance.
        buffer (bytes): The binary data to be extracted.
        bitSize (int): The size of the binary data in bits.
        schema_module (str): The name of the schema module.
        schema_type (str): The name of the schema type.
        file_name (str): The name of the file to save the extracted data.

    Returns:
        dict: A reference to the extracted file.
    """
    # Ensure the output directory exists
    output_dir = os.path.dirname(transformer.yaml_file_path)
    os.makedirs(output_dir, exist_ok=True)

    # Generate the full path for the new file
    yaml_file_path = os.path.join(output_dir, file_name)

    # Extract binary data
    buffer = bytes(buffer)

    # Import the module and get the type
    module = importlib.import_module(schema_module)
    ImportedType = getattr(module, schema_type)

    # Deserialize the binary data
    zserio_object = zserio.deserialize_from_bytes(ImportedType, buffer)

    # Convert to JSON, then to a Python dict
    json_data = json.loads(zserio.to_json_string(zserio_object))

    # Prepare the data to be written
    data_to_write = {
        '_meta': {
            'schema_module': schema_module,
            'schema_type': schema_type
        },
        **json_data
    }

    # Save the extracted data to the new file
    with open(yaml_file_path, 'w') as f:
        yaml.dump(data_to_write, f, default_flow_style=False, sort_keys=False)

    # Return a reference to the extracted file
    return {
        '_f': 'insert_yaml_as_extern',
        '_a': {
            'file': file_name
        }
    }
