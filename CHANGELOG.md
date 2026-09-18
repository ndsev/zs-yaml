# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `data_to_zserio_object(data, imported_type, init_args=None)`: builds a zserio object from an in-memory Python `dict` tree, exported from the top-level `zs_yaml` package. It is the path `yaml_to_bin` already took internally once the YAML was transformed; callers holding the tree no longer have to route it through `json.dumps` + `zserio.from_json_string`. Fixes #33
- `set_extern_bytes_provider(provider)` and the scoped `extern_bytes_provider(provider)` context manager: an embedding tool that already serializes the documents it references as externs can answer `insert_yaml_as_extern` from its own cache. The provider receives `(abs_yaml_path, compression_type)` with `compression_type` already resolved to a `CompressionType` or `None`, and returns `(buffer, bit_size)` or `None` to decline. Consulted only for references without `template_args`.
- `bin_to_dict(..., skip_nulls=True)`: leaves unset optional fields out of the returned tree instead of emitting `None` entries. Defaults to `False`, so existing output is unchanged.
- `YamlTransformer.has_function_invocations`: whether the source document contained any `_f:` call, so a downstream tool can skip its own post-transform walk for plain documents.
- `examples/team/test_descriptor_cache.py` counts descriptor builds to pin that the cache hits across top-level conversions, and `examples/team/test_data_to_zserio_object.py` pins the new API against the JSON detour and `yaml_to_bin`. Both run in CI.
- `YamlTransformer.cache_session()`: a context manager that shares one transform cache across everything inside the block, for batches whose documents pull in the same includes. The cache is released when the block exits.

### Fixed
- The compound descriptor cache never hit across top-level conversions. It keyed on the `TypeInfo` object, but a generated `type_info()` builds a fresh `TypeInfo` graph on every call, so every conversion rebuilt the whole descriptor tree and left the dead graphs alive as cache keys. It now keys on the generated class, which is stable for the process. Conversion output is unchanged.

### Changed
- `insert_yaml_as_extern` builds the zserio object straight from the transformed tree instead of dumping it to a JSON string for zserio to re-parse. Output is unchanged.
- `insert_yaml` and `repeat_node` copy the transformed tree with a plain recursive walk instead of `copy.deepcopy`, falling back to `copy.deepcopy` for self-referential trees. The copies are still independent; only the route changed.
- `examples/team/team.zs` gains two structs, `Contact` and `Profile`, that `Team` does not reference. They carry the optional fields the `skip_nulls` test needs; `Team`'s wire format is untouched.
- The transform cache is no longer a process-lifetime global. `YamlTransformer` cached every transformed document in a class-level dict that nothing in zs-yaml ever cleared, so a consumer converting many documents in one process retained every expanded tree until it called `clear_cache()` itself. The cache now lives for the duration of one transform and is released when that transform returns. Repeated `insert_yaml` includes of the same file inside one document still share a single transformer. Fixes #35
- `YamlTransformer.clear_cache()` now clears the enclosing cache session instead of a global dict; outside a session it does nothing. Existing calls stay valid.
- `examples/perf/benchmark.py` reports a higher `yaml_to_bin` median than before: its repeated runs over the same input used to hit the process-wide cache from run 2 on, so only the first run measured a conversion. Every run now measures one. Output is unchanged and still byte-identical to `perf_reference.bin`.

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
