import json
import importlib
import zserio
import yaml
import copy
from functools import reduce
import operator

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
    processed_data = external_transformer.transform()
    meta = external_transformer.get_meta()

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

    def load_file(file_path):
        if cache_file and file_path in _file_cache:
            return _file_cache[file_path]

        abs_path = transformer.resolve_path(file_path)
        if file_path.lower().endswith(('.yaml', '.yml')):
            with open(abs_path, 'r') as f:
                content = f.read()
                if template_args:
                    content = Template(content).safe_substitute(template_args)
                data = yaml.safe_load(content)
        elif file_path.lower().endswith('.json'):
            with open(abs_path, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format for {file_path}. Only YAML and JSON are supported.")

        if cache_file:
            _file_cache[file_path] = data

        # Deep copy is not good from performance point of
        # view but it still avoids loading the file again and
        # again and the nodes don't appear as alias but are
        # are really copies when used multiple times
        return copy.deepcopy(data)

    # Load the external data
    external_data = load_file(file)

    # If no specific node is requested, return the entire content
    if not node_path:
        return external_data

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
    print(f"parsed_path: {parsed_path}")

    try:
        return get_from_dict(external_data, parsed_path)
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