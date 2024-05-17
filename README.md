<img src="doc/zs-yaml.png" height="100">

**zs-yaml** adds YAML as a text format to be used with zserio in order to improve the user experience when manually creating or analyzing test data for zserio.

- **YAML Format**: Uses YAML's human-readable format instead of JSON as the primary format for editing, making data handling and transformation more intuitive and less cluttered.
- **Metadata Inclusion**: Automatically includes metadata in the YAML, eliminating the need for users to manually identify the correct type when importing JSON data, ensuring seamless (de-)serialization.
- **Custom Transformations**: Allows for hooking in custom transformations so that users can work with familiar formats (e.g., dates or coordinate representations) instead of thinking in unfamiliar formats.

### Example

#### Zserio schema module creation

1. Create the zserio schema
2. Create the Python APIs.
3. Ensure that the schema modules are available in the Python env your are using.

#### YAML Example with Metadata and Transformations

Using **zs-yaml**, you can define the same data in a more human-readable YAML format and include necessary metadata along with a custom transformation for the birthdate:

```yaml
# 1) Metadata is used to specify the type needed for
#    (de-)serialization and custom transform functions
# 2) User are free to use their preferred date format
#    for the birth data as the a normalization function
#    get invoked.
# 3) Yaml allows avoiding clutter and adding comments
#    like this one :)

_meta:
  schema_module: "installed.zserio.schema.module"
  schema_type: "Person"
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

#### Creating the binary representation

After you have installed `zs-yaml`(see below), call `zs-yaml person.yaml person.bin`

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

- You have to use the exact same order of field in the yaml as defined by the zserio schema, because zserio expects this
- When converting from binary to YAML, the target YAML file must already exist and contain the necessary metadata.
- The minimal metadata content in the target YAML file should be:

```yaml
_meta:
  schema_module: <module_name>
  schema_type: <type_name>
```

### Future Considerations

In the future, we may consider using YAML tags for a more integrated approach to handling transformations directly within the YAML files, simplifying syntax and enhancing readability.

## Project Structure

- `main.py`: Main script to run the application.
- `setup.py`: Script for setting up the project and installing dependencies.
- `zs_yaml/`: Directory containing the core library for YAML transformations.

## Reference

This project references the zserio serialization framework. For more information about zserio, visit the [zserio GitHub project](https://github.com/ndsev/zserio).
