# `zs-yaml`

*Your Easy Path to zserio Test Data*

<img src="doc/zs-yaml.png" alt="" height="100">

**zs-yaml** adds YAML as a text format to be used with zserio in order to improve the user experience when manually creating or analyzing test data for zserio.

- **YAML Format**: Uses YAML's human-readable format instead of JSON as the primary format for editing, making data handling and transformation more intuitive and less cluttered.
- **Metadata Inclusion**: Automatically includes metadata in the YAML, eliminating the need for users to manually identify the correct type when importing JSON data, ensuring seamless (de-)serialization.
- **Custom Transformations**: Allows for hooking in custom transformations so that users can work with familiar formats (e.g., dates or coordinate representations) instead of thinking in unfamiliar formats.

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
# 2) User are free to use their preferred date format
#    for the birth data as the a normalization function
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
# Install zs-yaml if not already installed,
# there is not yet a pip package so follow the instructions below

# Create the binary representation from the YAML file
zs-yaml person.yaml person.bin
```

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

- `setup.py`: Script for setting up the project and installing dependencies.
- `zs_yaml/`: Directory containing the actual `zs-yaml` implementation.

## Reference

This project references the zserio serialization framework. For more information about zserio, visit the [zserio GitHub project](https://github.com/ndsev/zserio).
