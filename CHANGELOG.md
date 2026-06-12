# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- `insert_yaml_as_extern` builds the zserio object directly from the transformed tree via `data_to_zserio_object` instead of a `json.dumps` + `zserio.from_json_string` round-trip — the JSON text detour dominated this transform's cost on large referenced documents.

### Added
- `set_extern_bytes_provider(provider)`: optional session cache hook for `insert_yaml_as_extern`. Embedding tools that already compile referenced documents standalone (e.g. parallel map builders) can serve the compiled bytes so the same document is not parsed and serialized twice per build.
- `bin_to_yaml` / `json_to_yaml` dump through libyaml (`CSafeDumper`) when available instead of the pure-python emitter, falling back transparently. ~3x faster on large documents. Note: long double-quoted scalars (non-ASCII content) may fold/escape at different positions than before — the parsed content is unchanged.

### Fixed
- The compound-descriptor cache is now keyed on the generated class instead of the `TypeInfo` object. Generated `type_info()` builds a fresh `TypeInfo` graph on every call, so the previous key never hit across top-level conversions — every `bin_to_dict` / `data_to_zserio_object` call silently rebuilt all descriptors (and the cache grew with dead `TypeInfo` graphs). On a 584-layer NDS.Live filestore this cuts the reverse tree-walk time by ~40%.

### Changed
- `insert_yaml` / `repeat_node`: replaced `copy.deepcopy` of cached trees with a specialized plain-YAML-tree copier (falls back to `deepcopy` on cyclic anchors). Significantly cheaper for multi-megabyte included fragments.

### Added
- `bin_to_dict(..., skip_nulls=True)`: omit unset optional fields during the reverse walk instead of emitting `None` entries, saving callers a separate null-stripping pass over the produced tree.
- `YamlTransformer.has_function_invocations`: public flag telling downstream tools whether the document contained any `_f:` invocations, so they can skip their own post-transform scans for plain documents.

### Changed
- rapidyaml loader: plain-scalar coercion is memoized per unique string (capped), replacing a regex tag resolution plus numeric parse per occurrence with a dict hit. Mapping keys and enum-like values repeat millions of times in large documents; on a 500 MB map load this removes ~25% of total build CPU.
- `data_to_zserio_object(data, imported_type, init_args=None)` public API: builds a Zserio object directly from an in-memory dict tree, with no JSON detour. Same fast path that `yaml_to_bin` / `yaml_to_pyobj` already use internally — exposed so downstream tools holding a transformed Python tree (e.g. SmartLayer wrappers with embedded extern buffers) can avoid the `json.dump` + `zserio.from_json_stream` roundtrip.
- Opt-in `rapidyaml`-backed YAML loader for ~5x faster parsing on large fragments. Output is byte-identical to the default PyYAML loader (scalar resolution delegates to PyYAML's own resolver patterns). Activate with `pip install zs-yaml[fast]` and either `ZS_YAML_LOADER=ryml` or `YamlTransformer(loader="ryml")`. Default loader remains PyYAML.

## [0.11.0] - 2026-06-09

### Added
- `bin -> yaml` can now take the zserio type directly via `--type <module.TypeName>` (and optional `--init-args`), so the target YAML no longer has to be pre-created with a `_meta` block. Fully backward compatible: when `--type` is omitted, the existing read-target-`_meta` behavior (including any `transformation_module`) is unchanged. `bin_to_yaml(...)` gains matching optional `schema_module`/`schema_type`/`init_args` parameters. Fixes #30

## [0.10.1] - 2026-05-07

### Fixed
- `bin_to_dict` / `bin_to_yaml`: the per-`TypeInfo` descriptor cache used `id(type_info)` as its key while only holding a weak hold on the type. After garbage collection, CPython could reuse that memory address for an unrelated zserio class and the cache would return a stale descriptor, surfacing as spurious `'X' object has no attribute 'y'` errors in long-running processes (e.g. multi-test suites that load several schemas). The cache now keys on the `TypeInfo` object itself.

## [0.10.0] - 2026-05-07

### Changed
- Conversion is significantly faster: `yaml_to_bin` ~10x and `bin_to_dict` ~3x on the perf benchmark (5,000 records). Drop-in upgrade — output is byte-identical to 0.9.x. Fixes #21

### Added
- `examples/perf` benchmark plus CI guards to catch future performance regressions

## [0.9.1] - 2026-04-27

### Changed
- Improved API documentation: clearer top-level entry points and a landing-page overview

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
