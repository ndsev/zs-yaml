"""
All the yaml transformation functions that are built-in.
"""

import yaml
import json
import importlib
import zserio

def include_external(file, transformer):
    """
    Include external YAML by transforming it to JSON and using zserio.
    The function reads an external YAML file specified by 'file', processes it,
    and includes its binary stream in the resulting JSON output using the meta
    information defined in the external YAML file.
    """
    with open(file, 'r') as yaml_file:
        yaml_data = yaml.safe_load(yaml_file)

    # Extract meta information for schema_module and schema_type
    meta = yaml_data.pop('_meta', {})
    schema_module = meta.get('schema_module')
    schema_type = meta.get('schema_type')

    if not schema_module or not schema_type:
        raise ValueError("Error: schema_module and schema_type must be specified in the _meta section of the YAML file")

    # Process the YAML data using the transformer
    processed_data = transformer.transform(yaml_data)
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

def repeat_node(node, count, transformer):
    """
    Repeat a specific node n times and return as a list.
    """
    return [node] * count
