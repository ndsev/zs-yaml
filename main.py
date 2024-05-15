import argparse
from zs_yaml.transformation import TransformationRegistry, yaml_to_zs_json, json_to_zs_bin

def main():
    parser = argparse.ArgumentParser(description='Transform a YAML file with function calls to a JSON file.')
    parser.add_argument('yaml_input_path', type=str, help='Path to the input YAML file')
    parser.add_argument('--json_output_path', type=str, help='Path to the output JSON file')
    parser.add_argument('--bin_output_path', type=str, help='Path to the output binary file')

    args = parser.parse_args()

    registry = TransformationRegistry()

    try:
        meta = yaml_to_zs_json(args.yaml_input_path, args.json_output_path, registry)
    except Exception as e:
        print(f"Error processing YAML file: {e}")
        exit(1)

    if args.bin_output_path:
        schema_module = meta.get('schema_module')
        schema_type = meta.get('schema_type')
        if not schema_module or not schema_type:
            print("Error: schema_module and schema_type must be specified in the _meta section when --bin_output_path is used")
            exit(1)
        try:
            json_to_zs_bin(args.json_output_path, args.bin_output_path, schema_module, schema_type)
        except Exception as e:
            print(f"Error during binary serialization: {e}")
            exit(1)

    print("Finished successfully :)")


if __name__ == "__main__":
    main()
