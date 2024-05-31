import argparse
import sys
import os
from zs_yaml.transformation import TransformationRegistry, yaml_to_zs_json, json_to_zs_bin, bin_to_yaml, json_to_yaml


def main():
    parser = argparse.ArgumentParser(
        description='Convert between YAML, JSON, and binary formats.\n'
                    'To convert from binary to YAML, the target YAML file must already exist with metadata.\n'
                    'The metadata is required to identify the correct Python type for deserialization.\n'
                    'The minimal metadata content in the target YAML file should be:\n'
                    '  _meta:\n'
                    '    schema_module: <module_name>\n'
                    '    schema_type: <type_name>',
        usage='%(prog)s <input_path> [output_path]\n\n'
              'Example usage:\n'
              '  %(prog)s input.yaml output.bin\n'
              '  %(prog)s input.bin output.yaml\n'
              '  %(prog)s input.yaml output.json\n'
              '  %(prog)s input.json output.yaml\n'
              '  %(prog)s input.yaml (output will be inferred as binary if not specified)'
    )
    parser.add_argument('input_path', type=str, help='Path to the input file (YAML, JSON, or binary)')
    parser.add_argument('output_path', type=str, nargs='?', help='Path to the output file (YAML, JSON, or binary)')

    if len(sys.argv) < 2:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    registry = TransformationRegistry()

    input_extension = os.path.splitext(args.input_path)[1].lower()
    output_extension = os.path.splitext(args.output_path)[1].lower() if args.output_path else None

    try:
        if input_extension == '.yaml':
            if not args.output_path:
                output_extension = '.bin'
                args.output_path = os.path.splitext(args.input_path)[0] + output_extension

            if output_extension == '.bin' or output_extension == '':
                # Convert YAML to binary
                meta = yaml_to_zs_json(args.input_path, 'temp.json', registry)
                schema_module = meta.get('schema_module')
                schema_type = meta.get('schema_type')
                if not schema_module or not schema_type:
                    print("Error: schema_module and schema_type must be specified in the _meta section for binary output")
                    sys.exit(1)
                json_to_zs_bin('temp.json', args.output_path, schema_module, schema_type)
            elif output_extension == '.json':
                # Convert YAML to JSON
                yaml_to_zs_json(args.input_path, args.output_path, registry)
            else:
                print("Error: Unsupported output file extension for YAML input")
                sys.exit(1)
        elif input_extension == '.bin' or input_extension == '':
            if not args.output_path:
                print("Error: Output path must be specified for binary input")
                sys.exit(1)
            # Convert binary to YAML
            bin_to_yaml(args.input_path, args.output_path)
        elif input_extension == '.json':
            if not args.output_path:
                output_extension = '.yaml'
                args.output_path = os.path.splitext(args.input_path)[0] + output_extension
            if output_extension == '.yaml':
                # Convert JSON to YAML
                json_to_yaml(args.input_path, args.output_path, registry)
            else:
                print("Error: Unsupported output file extension for JSON input")
                sys.exit(1)
        else:
            print("Error: Unsupported input file extension")
            sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

    print("Finished successfully :)")


if __name__ == "__main__":
    main()