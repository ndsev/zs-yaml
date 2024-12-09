# `zs-yaml`

*Your Easy Path to zserio Test Data*

<img src="doc/zs-yaml.png" alt="" height="100">

**zs-yaml** adds YAML as a text format to be used with zserio in order to improve the user experience when manually creating or analyzing test data for zserio.

- **YAML Format**: Uses YAML's human-readable format instead of JSON as the primary format for editing, making data handling and transformation more intuitive and less cluttered.
- **Metadata Inclusion**: Automatically includes metadata in the YAML, eliminating the need for users to manually identify the correct type when importing JSON data, ensuring seamless (de-)serialization.
- **Custom Transformations**: Allows for hooking in custom transformations so that users can work with familiar formats (e.g., dates or coordinate representations) instead of thinking in unfamiliar formats.

## Design Principles

1. **Transparency Over Magic**:
   - Prioritize clear and understandable processes. For example, users can fully render the YAML to see the actual data conforming to the underlying zserio schema.
   - This approach avoids black-box conversions, simplifying debugging and ensuring user confidence in the data.

2. **Accessibility and Simplicity**:
   - Make the tool easy to use and understand, even for beginners.
   - Features are designed with simplicity in mind. For instance, we use string-only templates as one way to keep things straightforward.

3. **Performance for Trusted Sources**:
   - Optimize for performance, assuming trusted YAML sources.
   - Faster processing is crucial for rapid iterations and maintaining workflow.

4. **Flexibility Within Simplicity**:
   - While maintaining a simple core, provide powerful features like YAML imports, built-in and custom transformations, and basic templating.
   - This balance allows for adaptability to various use cases without compromising ease of use.

## Installation

Install `zs-yaml` using pip:

```bash
python -m pip install --upgrade zs-yaml
```

## Usage

The main entry point for the application is `zs-yaml`. It accepts arguments for specifying the input and output file paths. You can run the application as follows:

```bash
zs-yaml input.yaml output.bin
zs-yaml input.bin output.yaml
```

### Programmatic Usage

In addition to the command-line interface, `zs-yaml` provides the conversion functions for use within Python scripts. In addition to the ones available to the CLI, there are also functions for programmatic use, e.g. `yaml_to_pyobj` for deserializing YAML files to Python objects:

```python
from zs_yaml.convert import yaml_to_pyobj

# Convert a YAML file to a Python object
# (instance of the zserio object defined by the schema)
zserio_object = yaml_to_pyobj('input.yaml')

# Use the zserio_object as needed in your application
```

### Notes

- You have to use the exact same order of fields in the YAML as defined by the zserio schema, because zserio expects this.
- When converting from binary to YAML, the target YAML file must already exist and contain the necessary metadata.
- The minimal metadata content in the target YAML file should be:

```yaml
_meta:
  schema_module: <module_name>
  schema_type: <type_name>
```

### Initialization Arguments

Some Zserio types require additional arguments during initialization, either when deserializing from binary or when creating objects from JSON. To support these types, you can specify initialization arguments in the `_meta` section of your YAML file:

```yaml
_meta:
  schema_module: <module_name>
  schema_type: <type_name>
  initialization_args:
    - <arg1>
    - <arg2>
    # ... more arguments as needed
```

**Hint:** At the moment only plain values are supported, although zserio supports also compound values as args.
Support for these may be added in the future.

These arguments will be passed to the appropriate Zserio functions:
- `zserio.deserialize_from_file()` when converting from binary to YAML
- `zserio.from_json_file()` when converting from YAML to binary

For example:

```yaml
_meta:
  schema_module: my_schema
  schema_type: MyType
  initialization_args:
    - 0xAB
    - 42

# ... rest of your YAML data
```

In this example, `0xAB` and `42` will be passed as additional arguments to the initialization functions.

This feature ensures that types requiring additional initialization parameters can be properly handled in both directions of conversion (YAML to binary and binary to YAML).

## Example

### Zserio Schema Module Creation

1. **Create the Zserio schema**:
   - Create a file named `person.zs` with the following content:

     ```zserio
     package person;

     struct Person
     {
         string name;
         string birthdate;
         string birth_location;
         string current_job;
         int32 income;
         RoleExperience experience[];
     };

     struct RoleExperience
     {
         string role;
         int32 years;
     };
     ```

2. **Compile the Zserio schema and generate Python APIs**:
   - Run the following command to compile the schema and generate Python sources:

     ```sh
     # Generated sources needs type infos so that 'json <-> bin'
     # conversion works, which is utilized by zs-yaml
     zserio person.zs -withTypeInfoCode -python zs_gen_api
     ```

3. **Ensure that the schema modules are available in the Python environment**:
   - Export the `PYTHONPATH` to include the directory containing the generated Python sources:

     ```sh
     export PYTHONPATH="zs_gen_api"
     ```

### Use zs-yaml to create data

Using **zs-yaml**, you can define the same data in a more human-readable YAML format and include necessary metadata along with a custom transformation for the birthdate:

```yaml
# 1) Metadata is used to specify the type needed for
#    (de-)serialization and custom transform functions
# 2) Users are free to use their preferred date format
#    for the birth data as the a normalization function
#    (defined in the referenced `transformations.py`)
#    get invoked.
# 3) Yaml allows avoiding clutter and adding comments
#    like this one :)

_meta:
  schema_module: person.api
  schema_type: Person
  transformation_module: "./transformations.py"

name: John Doe

birthdate:
  _f: normalize_date
  _a: "01/01/1990"
birth_location: Springfield, USA

current_job: Software Engineer
income: 75000

experience:
  - role: Intern
    years: 1
  - role: Junior Developer
    years: 2
  - role: Senior Developer
    years: 3
```

#### Example Transformation Module (transformations.py)

```python
def normalize_date(date_str):
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"Date {date_str} is not in a recognized format")
```

#### Creating the Binary Representation

After you have installed `zs-yaml`, call `zs-yaml` to convert your YAML file to a binary representation:

```sh
# Install zs-yaml if not already installed.

# Create the binary representation from the YAML file
zs-yaml person.yaml person.bin
```

## Built-in Transformations

zs-yaml comes with several built-in transformation functions that can be used in your YAML files. Here's a brief overview of the available functions:

- `insert_yaml_as_extern`: Includes external YAML content by transforming it to JSON and using zserio.
- `insert_yaml`: Inserts YAML content directly from an external file.
- `repeat_node`: Repeats a specific node a specified number of times.
- `extract_extern_as_yaml`: Extracts binary data and saves it as an external YAML file.
- `py_eval`: Allows to write small snippets like `myArray: {_f: py_eval, _a: "list(range(1, 100))"}` to generate the value for a yaml node.

For more detailed information about these functions and their usage, please refer to the [built_in_transformations.py](https://github.com/ndsev/zs-yaml/blob/main/zs_yaml/built_in_transformations.py) source file.

Note: We plan to implement automatic source documentation generation in a future release, which will provide more comprehensive information about these functions and their parameters.

## Project Structure

- `setup.py`: Script for setting up the project and installing dependencies.
- `zs_yaml/`: Directory containing the actual `zs-yaml` implementation.

## Reference

This project references the zserio serialization framework. For more information about zserio, visit the [zserio GitHub project](https://github.com/ndsev/zserio).