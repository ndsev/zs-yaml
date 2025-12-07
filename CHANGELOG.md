# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.3] - 2025-12-07

### Added
- `bin_to_dict` function to deserialize binary directly to dict

### Changed
- Use `guess-next-dev` version scheme for pre-release uploads from main

### Note
- v0.8.2 was published to PyPI without the `bin_to_dict` export due to a release process issue; use v0.8.3 instead

## [0.8.2] - 2025-12-06

_Superseded by v0.8.3 - missing `bin_to_dict` export_

## [0.8.1] - 2025-12-03

### Added
- Cache management: `YamlTransformer.clear_cache()` method for explicit cache invalidation

### Changed
- Performance: Skip transformation processing entirely when YAML contains no function invocations

## [0.8.0] - 2025-07-03

### Added
- `pyobj_to_yaml` conversion function for dumping Python objects to YAML files
- Dedicated exceptions and more informative error messages

## [0.7.0] - 2024-12-09

### Added
- `py_eval` transformation function for generating node values via Python snippets
- `extract_extern_as_yaml` supports compressed externals (gzip, zstd, lz4, brotli)
- `extract_extern_as_yaml` supports generating YAMLs without null-value fields

## [0.6.1] - 2024-12-04

### Changed
- Minimum zserio version updated to 2.15.0

## [0.6.0] - 2024-11-08

### Fixed
- Crash that hid zserio exception messages in some cases

## [0.5.0] - 2024-10-07

### Added
- `yaml_to_pyobj` conversion function (library API only)

## [0.4.0] - 2024-08-10

### Added
- Initial release
- YAML format support for zserio serialization
- Automatic metadata inclusion in YAML
- Bidirectional conversion between YAML, JSON, and binary formats
- Template substitution for flexible YAML content generation
- Built-in transformations: `insert_yaml_as_extern`, `insert_yaml`, `repeat_node`
- Custom transformation hooks
