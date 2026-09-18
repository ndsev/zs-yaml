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

There is an optional `fast` extra that speeds up YAML parsing, and installing
it is the whole opt-in — see [Faster YAML parsing](#faster-yaml-parsing).

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

### Caching and Batch Conversion

While a document is being transformed, each YAML file it pulls in via
`insert_yaml` is transformed once and reused, so a file included several times
costs one parse. That cache is dropped when the conversion returns: converting
many documents in one process does not accumulate their expanded trees, and
there is nothing a caller has to remember to clear.

If several documents share the same includes and you want that work done once,
open a session around the batch. Everything cached inside is released when the
block exits:

```python
from zs_yaml import YamlTransformer, yaml_to_bin

with YamlTransformer.cache_session():
    for src, dst in jobs:
        yaml_to_bin(src, dst)
```

A session assumes the files it reads do not change while it is open. If a
transformation writes a YAML file that a later include reads back — as
`extract_extern_as_yaml` does — call `YamlTransformer.clear_cache()` at that
point, or keep the session narrower. Outside a session `clear_cache()` has
nothing to clear and does nothing.

### Faster YAML parsing

Parsing the YAML is the largest single cost of a `yaml -> bin` conversion. The
`fast` extra swaps PyYAML for [rapidyaml](https://github.com/biojppm/rapidyaml)
on that step:

```bash
python -m pip install --upgrade 'zs-yaml[fast]'
```

That is the whole opt-in. The default loader setting is `auto`: rapidyaml when
it is importable, PyYAML when it is not. Nothing else to set, and an install
without the extra is not an error — `auto` never raises and never warns about a
missing rapidyaml.

To take the choice out of `auto`'s hands, name a loader. For a run:

```bash
ZS_YAML_LOADER=pyyaml zs-yaml input.yaml output.bin   # never rapidyaml
ZS_YAML_LOADER=ryml   zs-yaml input.yaml output.bin   # rapidyaml or fail
```

or from Python, per transformer or as a process-wide default:

```python
from zs_yaml import YamlTransformer

YamlTransformer("input.yaml", loader="pyyaml")   # this document and its includes
YamlTransformer.LOADER = "ryml"                  # every document from here on
```

`ZS_YAML_LOADER` outranks both, so a person can override for one run what the
calling code chose. The three names are `auto` (the default), `pyyaml` and
`ryml`; anything else raises, because a typo should not silently get you a
loader you did not ask for.

**What you get.** On a 1.07 MiB generated document (5000 records, Apple
silicon, CPython 3.14, rapidyaml 0.15.2), the parse step goes from 230 ms to
93 ms and the whole `yaml_to_bin` from 0.279 s to 0.140 s — a little under 2x
end to end. The gain scales with document size and with how repetitive the
scalars are; on a small file it is not worth measuring. Measure your own
documents before deciding.

**What it costs.**

- Another dependency, and a binary one. rapidyaml publishes wheels for CPython
  3.8 through 3.14 on macOS, manylinux and Windows, so a supported interpreter
  installs a wheel and compiles nothing. Anything outside that matrix builds
  rapidyaml from its sdist, which needs a C++ compiler.
- A second YAML parser in the stack, on the default path once the extra is
  installed. The output is pinned against PyYAML by
  `examples/team/test_ryml_loader.py` and by the byte-identical perf reference,
  both run in CI under both loaders.
- Memory: coerced plain scalars are memoized for the life of the process, up to
  about a million distinct values.

**What it does not change.** The loader builds the same Python tree PyYAML
builds — same values, same types, same key order. Anchors, aliases, merge keys,
explicit tags, multi-document streams and documents nested deeper than the
Python recursion limit are not reimplemented; a document using them is handed
to PyYAML, as is any input rapidyaml cannot parse, so syntax errors keep
PyYAML's wording, line and column.

**If rapidyaml is not installed.** The default, `auto`, uses PyYAML and says
nothing — not installing an optional extra is not a mistake. Naming `ryml`
outright is a different statement, so that one is reported: through the
environment variable it raises `ImportError`, because whoever set it asked for
that loader by name; from Python it warns and falls back to PyYAML, so a tool
built on `zs-yaml` can pin the fast loader without a missing wheel breaking
someone's build.

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

- `insert_yaml_as_extern`: Includes external YAML content by transforming it to JSON and using zserio. Optionally compresses the produced bytes via `compression_type` (`zlib`, `zstd`, `lz4`, `brotli`; omit or set to `no_compression` for raw). Example:
  ```yaml
  data:
    _f: insert_yaml_as_extern
    _a:
      file: payload.yaml
      compression_type: zstd   # enum name, integer (0-4) or CompressionType member
  ```
- `insert_yaml`: Inserts YAML content directly from an external file.
- `repeat_node`: Repeats a specific node a specified number of times.
- `extract_extern_as_yaml`: Extracts binary data and saves it as an external YAML file. Accepts the same `compression_type` values as `insert_yaml_as_extern` and decompresses the buffer before deserialization.
- `py_eval`: Allows to write small snippets like `myArray: {_f: py_eval, _a: "list(range(1, 100))"}` to generate the value for a yaml node.

For more detailed information about these functions and their usage, please refer to the [built_in_transformations.py](https://github.com/ndsev/zs-yaml/blob/main/zs_yaml/built_in_transformations.py) source file.

Note: We plan to implement automatic source documentation generation in a future release, which will provide more comprehensive information about these functions and their parameters.

## Project Structure

- `pyproject.toml`: Modern Python project configuration file containing all package metadata and dependencies.
- `zs_yaml/`: Directory containing the actual `zs-yaml` implementation.

## Release Procedure

This project uses automatic version management through `setuptools-scm`, which derives version numbers from git tags:

### Version Numbering

- **Tagged releases**: Git tags like `v0.8.1` produce clean version numbers: `0.8.1`
- **Development versions**: Commits on main branch produce versions like `0.8.1.dev5` (5 commits after v0.8.0)

### Creating a Release

1. **Create a GitHub Release**:
   - Go to the repository's "Releases" page on GitHub
   - Click "Create a new release"
   - Create a new tag (e.g., `v0.9.0`) targeting the main branch
   - Add release notes describing the changes
   - Publish the release

2. **Automatic Publication**:
   - GitHub Actions will automatically:
     - Build the package with the correct version number
     - Run all tests
     - Publish to PyPI if tests pass

### Manual Release (if needed)

If you need to create a release locally:

```bash
# Ensure you're on main with latest changes
git checkout main
git pull

# Create and push a tag
git tag -a v0.9.0 -m "Release version 0.9.0"
git push origin v0.9.0
```

The CI/CD pipeline will handle the rest automatically.

## Reference

This project references the zserio serialization framework. For more information about zserio, visit the [zserio GitHub project](https://github.com/ndsev/zserio).