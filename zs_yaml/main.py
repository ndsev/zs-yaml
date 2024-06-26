import argparse
import traceback
import sys
import os
from zs_yaml.convert import (
    yaml_to_bin,
    bin_to_yaml,
    yaml_to_json,
    json_to_yaml
    )
from zs_yaml import get_version_info

def parse_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,

        description=
        f'%(prog)s {get_version_info()}\n\n'
        'Converts between YAML, JSON, and binary formats. '
        'To convert from binary to YAML, the target YAML file must already exist with metadata. '
        'The metadata is required to identify the correct Python type for deserialization.\n\n'
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
    parser.add_argument('--version', action='version', version=f'%(prog)s {get_version_info()}')

    if len(sys.argv) < 2:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()

def process_yaml_input(input_path, output_path):
    if not output_path:
        output_extension = '.bin'
        output_path = os.path.splitext(input_path)[0] + output_extension
    else:
        output_extension = os.path.splitext(output_path)[1].lower()

    if output_extension == '.bin' or output_extension == '':
        yaml_to_bin(input_path, output_path)
    elif output_extension == '.json':
        yaml_to_json(input_path, output_path)
    else:
        raise ValueError("Unsupported output file extension for YAML input")

def process_binary_input(input_path, output_path):
    if not output_path:
        raise ValueError("Output path must be specified for binary input")
    bin_to_yaml(input_path, output_path)

def process_json_input(input_path, output_path):
    if not output_path:
        output_extension = '.yaml'
        output_path = os.path.splitext(input_path)[0] + output_extension
    else:
        output_extension = os.path.splitext(output_path)[1].lower()

    if output_extension == '.yaml':
        json_to_yaml(input_path, output_path)
    else:
        raise ValueError("Unsupported output file extension for JSON input")

def main():
    args = parse_arguments()

    input_extension = os.path.splitext(args.input_path)[1].lower()

    try:
        if input_extension == '.yaml':
            process_yaml_input(args.input_path, args.output_path)
        elif input_extension == '.bin' or input_extension == '':
            process_binary_input(args.input_path, args.output_path)
        elif input_extension == '.json':
            process_json_input(args.input_path, args.output_path)
        else:
            raise ValueError("Unsupported input file extension")
    except Exception as e:
        print(f"Error processing file: {e}")
        traceback.print_exc()
        sys.exit(1)

    print("Finished successfully :)")

if __name__ == "__main__":
    main()