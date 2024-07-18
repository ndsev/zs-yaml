import json
import importlib
import zserio
import yaml
import copy

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

def insert_yaml(transformer, file, template_args=None):
    """
    Insert YAML content directly without converting to binary.

    Args:
        transformer (YamlTransformer): The transformer instance.
        file (str): Path to the external YAML file.
        template_args (dict, optional): A dictionary of template arguments for placeholder replacement.

    Returns:
        dict: The processed YAML data.
    """
    abs_path = transformer.resolve_path(file)
    external_transformer = transformer.__class__(abs_path, template_args, initial_transformations=transformer.transformations)
    processed_data = external_transformer.transform()
    return processed_data

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