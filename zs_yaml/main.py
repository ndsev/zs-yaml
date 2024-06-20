import argparse
import traceback
import sys
import os
from zs_yaml.transformation import (
    TransformationRegistry,
    yaml_to_zs_json,
    yaml_to_bin,
    bin_to_yaml,
    json_to_yaml
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Convert between YAML, JSON, and binary formats.\n'
        'To convert from binary to YAML, the target YAML file must already exist with metadata.\n'
        'The metadata is required to identify the correct Python type for deserialization.\n'
        'The minimal metadata content in the target YAML file should be:\n'
        ' _meta:\n'
        ' schema_module: <module_name>\n'
        ' schema_type: <type_name>',
        usage='%(prog)s <input_path> [output_path]\n\n'
        'Example usage:\n'
        ' %(prog)s input.yaml output.bin\n'
        ' %(prog)s input.bin output.yaml\n'
        ' %(prog)s input.yaml output.json\n'
        ' %(prog)s input.json output.yaml\n'
        ' %(prog)s input.yaml (output will be inferred as binary if not specified)'
    )
    parser.add_argument('input_path', type=str, help='Path to the input file (YAML, JSON, or binary)')
    parser.add_argument('output_path', type=str, nargs='?', help='Path to the output file (YAML, JSON, or binary)')

    if len(sys.argv) < 2:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()

def get_file_extensions(input_path, output_path):
    input_extension = os.path.splitext(input_path)[1].lower()
    output_extension = os.path.splitext(output_path)[1].lower() if output_path else None
    return input_extension, output_extension

def process_yaml_input(input_path, output_path, registry):
    if not output_path:
        output_extension = '.bin'
        output_path = os.path.splitext(input_path)[0] + output_extension
    else:
        output_extension = os.path.splitext(output_path)[1].lower()

    if output_extension == '.bin' or output_extension == '':
        yaml_to_bin(input_path, output_path, registry)
    elif output_extension == '.json':
        yaml_to_zs_json(input_path, output_path, registry)
    else:
        raise ValueError("Unsupported output file extension for YAML input")

def process_binary_input(input_path, output_path):
    if not output_path:
        raise ValueError("Output path must be specified for binary input")
    bin_to_yaml(input_path, output_path)

def process_json_input(input_path, output_path, registry):
    if not output_path:
        output_extension = '.yaml'
        output_path = os.path.splitext(input_path)[0] + output_extension
    else:
        output_extension = os.path.splitext(output_path)[1].lower()

    if output_extension == '.yaml':
        json_to_yaml(input_path, output_path, registry)
    else:
        raise ValueError("Unsupported output file extension for JSON input")

def main():
    args = parse_arguments()
    registry = TransformationRegistry()
    input_extension, output_extension = get_file_extensions(args.input_path, args.output_path)

    try:
        if input_extension == '.yaml':
            process_yaml_input(args.input_path, args.output_path, registry)
        elif input_extension == '.bin' or input_extension == '':
            process_binary_input(args.input_path, args.output_path)
        elif input_extension == '.json':
            process_json_input(args.input_path, args.output_path, registry)
        else:
            raise ValueError("Unsupported input file extension")
    except Exception as e:
        print(f"Error processing file: {e}")
        traceback.print_exc()
        sys.exit(1)

    print("Finished successfully :)")

if __name__ == "__main__":
    main()