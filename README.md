<img src="doc/zs-yaml.png" height="100">

**zs-yaml** adds YAML as a text format to be used with zserio in order to improve the user experience when manually creating or analyzing test data for zserio.

- **YAML Format**: Uses YAML's human-readable format instead of JSON as the primary format for editing, making data handling and transformation more intuitive and less cluttered.
- **Metadata Inclusion**: Automatically includes metadata in the YAML, eliminating the need for users to manually identify the correct type when importing JSON data, ensuring seamless (de-)serialization.
- **Custom Transformations**: Allows for hooking in custom transformations so that users can work with familiar formats (e.g., dates or coordinate representations) instead of thinking in unfamiliar formats.

### JSON vs YAML Example

#### JSON Input Example
Consider a data structure where we have a person object with basic data,
location of birth, current job, income, and a list of experience levels.
Note that the JSON example does not include metadata, requiring users to
manually find and set the correct type, when serializing the data.
In addition no comments are supported and `{...}` and `"..."` add must-have
clutter.

```json
{
  "name": "John Doe",
  "birthdate": "1990-01-01",
  "birth_location": "Springfield, USA",
  "current_job": "Software Engineer",
  "income": 75000,
  "experience": [
    {
      "role": "Intern",
      "years": 1
    },
    {
      "role": "Junior Developer",
      "years": 2
    },
    {
      "role": "Senior Developer",
      "years": 3
    }
  ]
}
```

#### YAML Input Example with Metadata and Transformations
Using **zs-yaml**, you can define the same data in a more human-readable YAML format and include necessary metadata along with a custom transformation for the birthdate:

```yaml
_meta:
  schema_module: "installed.zserio.schema.module"
  schema_type: "Person"
  transformation_module: "./transformations.py"

name: John Doe
birthdate:
  # Users are free to use their prefered date format
  # The transformation logic will take care about
  # converting to the expected format.
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

#### Creating the binary representation

After you have installed `zs-yaml`(see below), call `zs-yaml person.yaml person.bin`

## Features

- **YAML Transformation**: Core functionality for transforming YAML data structures defined by zserio schemas.
- **zserio Integration**: Converts YAML data into zserio's binary format.
- **Custom Transformations**: Allows for custom transformation functions to be applied to YAML nodes to simplify data creation.

## Installation

You can install the package in development mode by cloning the repository and using `pip3`:

```bash
git clone https://github.com/yourusername/zs-yaml.git
cd zs-yaml
pip3 install -e .
```

## Usage

The main entry point for the application is `main.py`. It accepts arguments for specifying the input and output file paths. You can run the application as follows:

```bash
zs-yaml input.yaml output.bin
zs-yaml input.bin output.yaml
```

### Notes

- When converting from binary to YAML, the target YAML file must already exist and contain the necessary metadata.
- The minimal metadata content in the target YAML file should be:

```yaml
_meta:
  schema_module: <module_name>
  schema_type: <type_name>
```

### Example Usage

To convert from YAML to binary:

```bash
zs-yaml mydata.yaml mydata.bin
```

To convert from binary to YAML (ensure the YAML file exists with the necessary metadata):

```bash
zs-yaml mydata.bin mydata.yaml
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
```

### Summary of Changes:
1. Removed references to JSON output paths and JSON conversion.
2. Updated usage examples to show converting between YAML and binary formats.
3. Added notes on the requirement for metadata when converting from binary to YAML.
4. Ensured the example YAML input and transformation module are aligned with the current functionality.
5. Updated the example usage section to reflect the new command-line interface.
