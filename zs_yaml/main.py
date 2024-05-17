import argparse
import sys
from zs_yaml.transformation import TransformationRegistry, yaml_to_zs_json, json_to_zs_bin, bin_to_yaml


def main():
    parser = argparse.ArgumentParser(
        description='Convert between YAML and binary formats.\n'
                    'To convert from binary to YAML, the target YAML file must already exist with metadata.\n'
                    'The metadata is required to identify the correct Python type for deserialization.\n'
                    'The minimal metadata content in the target YAML file should be:\n'
                    '  _meta:\n'
                    '    schema_module: <module_name>\n'
                    '    schema_type: <type_name>',
        usage='%(prog)s <input_path> <output_path>\n\n'
              'Example usage:\n'
              '  %(prog)s input.yaml output.bin\n'
              '  %(prog)s input.bin output.yaml\n'
              '  %(prog)s input.yaml output (output without extension will be treated as binary)'
    )
    parser.add_argument('input_path', type=str, help='Path to the input file (YAML or binary)')
    parser.add_argument('output_path', type=str, help='Path to the output file (YAML or binary)')

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    registry = TransformationRegistry()

    try:
        if args.input_path.endswith('.yaml'):
            # Convert YAML to binary
            meta = yaml_to_zs_json(args.input_path, 'temp.json', registry)
            schema_module = meta.get('schema_module')
            schema_type = meta.get('schema_type')
            if not schema_module or not schema_type:
                print("Error: schema_module and schema_type must be specified in the _meta section for binary output")
                sys.exit(1)
            json_to_zs_bin('temp.json', args.output_path, schema_module, schema_type)
        else:
            # Convert binary to YAML
            bin_to_yaml(args.input_path, args.output_path)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

    print("Finished successfully :)")


if __name__ == "__main__":
    main()
