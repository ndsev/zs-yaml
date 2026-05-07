# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-05-07

### Changed
- `yaml_to_bin` / `yaml_to_pyobj` no longer use `zserio.creator.ZserioTreeCreator` or `zserio.walker.Walker`. Both directions now use a per-compound `TypeInfo` descriptor cache and drive object construction (`py_type(*args)` + `setattr`) and traversal (`getattr`) directly. Parameterized types, choice/union, optional, and conditional fields are handled. Output is byte-identical in all cases; measured ~10x faster end-to-end for `yaml_to_bin` and ~3x for `bin_to_dict` on the perf harness (5000-record dataset) compared to the original JSON-string round-trip path. Fixes #21

### Added
- `examples/perf` harness (`perf.zs`, `generate_perf_yaml.py`, `benchmark.py`) for performance regression testing of both conversion directions (`yaml_to_bin` and `bin_to_dict`)
- `examples/perf/test_fast_path.py` structural assertion that the fast path is exercised (no `ZserioTreeCreator` / `Walker` instantiation), wired into CI to catch accidental regressions independent of wall-clock timing

## [0.9.1] - 2026-04-27

### Changed
- Curated `__all__` and added a landing-page docstring to improve the public API documentation surface

## [0.9.0] - 2026-04-23

### Added
- `insert_yaml_as_extern` supports compressing the produced extern bytes via a new `compression_type` argument (zlib, zstd, lz4, brotli). Fixes #19
- `extern_compression` example schema plus `test_compression.py` covering unit and end-to-end round-trips for all compression types

### Changed
- `extract_extern_as_yaml` and `insert_yaml_as_extern` now share a single `_decompress` / `_compress` helper pair so new algorithms plug in one place
- `extract_extern_as_yaml` default for `compression_type` aligned to `None` (was `0`); behavior is unchanged for all callers

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
- `extract_extern_as_yaml` supports compressed externals (zlib, zstd, lz4, brotli)
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
