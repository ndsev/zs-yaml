<img src="doc/zs-yaml.png" height="100">

**zs-yaml** is a Python library designed to transform YAML representations of objects defined within zserio schemas to either the natively supported zserio text/debugging format (using JSON) and/or the binary format. This project aims to make data handling and transformation more intuitive and less cluttered, using YAML's human-readable format.

## Features

- **YAML Transformation**: Core functionality for transforming YAML data structures defined by zserio schemas.
- **zserio Integration**: Converts YAML data into zserio's text/debugging (JSON) and binary formats.
- **Custom Transformations**: Allows for custom transformation functions to be applied to YAML nodes to simplify data creation.

## Installation

You can install the package in development mode by cloning the repository and using `pip3`:

```bash
git clone https://github.com/yourusername/zs-yaml.git
cd zs-yaml
pip3 install -e .
```

## Usage

The main entry point for the application is `main.py`. It accepts arguments for specifying output paths and the input YAML file. You can run the application as follows:

```bash
zs-yaml --json_output_path out.json --bin_output_path out.bin myzsobject.yaml
```

### Custom Transformation Approach

**zs-yaml** supports custom transformations using a flexible approach. You can define transformations in a module and specify them in your YAML file using the `_f` and `_a` keys:

- `_f`: The name of the transformation function.
- `_a`: The arguments for the transformation function.

#### Example YAML Input

Here's an example YAML file that uses custom transformations:

```yaml
_meta:
  schema_module: "your.schema.module"
  schema_type: "YourSchemaType"
  transformation_module: "./transformations.py"

temperature:
  _f: to_fahrenheit
  _a: 20

values:
  _f: increment_list
  _a: [1, 2, 3]
```

#### Example Transformation Module (transformations.py)

```python
def to_fahrenheit(celsius):
    return celsius * 9/5 + 32

def increment_list(values):
    return [v + 1 for v in values]
```

In this example, the `temperature` value will be transformed using the `to_fahrenheit` function, and the `values` list will be processed by the `increment_list` function. The transformation module specified in `_meta` is loaded and used to apply these transformations.

### Future Considerations

In the future, we may consider using YAML tags for a more integrated approach to handling transformations directly within the YAML files, simplifying syntax and enhancing readability.

## Project Structure

- `main.py`: Main script to run the application.
- `setup.py`: Script for setting up the project and installing dependencies.
- `zs_yaml/`: Directory containing the core library for YAML transformations.

## Reference

This project references the zserio serialization framework. For more information about zserio, visit the [zserio GitHub project](https://github.com/ndsev/zserio).
