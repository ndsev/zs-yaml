import json
import importlib
import zserio

def insert_yaml_as_extern(file, transformer):
    """
    Include external YAML by transforming it to JSON and using zserio.
    The function reads an external YAML file specified by 'file', processes it,
    and includes its binary stream in the resulting JSON output using the meta
    information defined in the external YAML file.
    """
    abs_path = transformer.resolve_path(file)

    # Create a new transformer for the external file
    external_transformer = transformer.__class__(abs_path)

    # Process the external YAML file
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

def insert_yaml(file, transformer):
    """
    Insert YAML content directly without converting to binary.
    """
    abs_path = transformer.resolve_path(file)

    # Create a new transformer for the external file
    external_transformer = transformer.__class__(abs_path)

    # Process the external YAML file
    return external_transformer.transform()

def repeat_node(node, count, transformer):
    """
    Repeat a specific node n times and return as a list.
    """
    return [node] * count