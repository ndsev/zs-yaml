# API Docs Review — `zs_yaml`

Purpose: classify every public symbol in `zs_yaml` as user-facing, advanced, or
internal so the docs build renders a curated surface instead of every public-named
helper. Modeled on `ndslive-yaml/api_docs_review.md`.

This file is descriptive. The actual curation lives in two places:
1. `__all__` declarations inside the package (metadata only — no behavior change).
2. The `apidoc.packages` entry for `zs_yaml` in the parent SDK's `devportal.yaml`,
   which now uses `mode: curated` so Sphinx respects `__all__` and skips
   undocumented public-named symbols.

---

## Audience model

1. **YAML author** — writes `.yaml` files that use `_f:` transformations
   (`!from_wgs84_2d`, `!insert_yaml`, …). Doesn't import from `zs_yaml` at all.
   Read USAGE/README, not API docs.
2. **Python API consumer** — calls `zs_yaml.yaml_to_bin(...)` or instantiates
   `YamlTransformer` from a script. Primary docs audience.
3. **Contributor** — reads the source. Fine with sparse module-level docstrings;
   not the docs target.

---

## Philosophy

- The curated public API is what `__init__.py` already re-exports. Promote that
  list to `__all__` so it becomes the documented contract.
- `convert.py` exposes 9 functions. Only the 5 already re-exported are
  user-facing; the rest (`yaml_to_yaml`, `yaml_to_pyobj`, `pyobj_to_yaml`) are
  advanced — useful but rarely needed.
- `built_in_transformations.py` is *YAML-side* API. The functions are invoked
  via `_f:` markers in YAML files, not by Python `import`. Render them under a
  separate "YAML Transformations" heading (like `ndslive-yaml` does), or omit
  from this round and link to USAGE.md.
- `main.py` is CLI-only — exclude entirely.

---

## Per-module review

Legend: 🟢 user-facing · 🟡 advanced · 🔴 internal/CLI/not-Python-API

### `zs_yaml` (top-level, from `__init__.py`)

Curated public surface. All 🟢.

| Symbol | Source module | Notes |
|---|---|---|
| `yaml_to_json` | `convert` | Plain YAML → JSON conversion |
| `yaml_to_bin` | `convert` | YAML → zserio binary (primary entry point) |
| `bin_to_yaml` | `convert` | zserio binary → YAML (primary entry point) |
| `bin_to_dict` | `convert` | Binary → in-memory dict (programmatic inspection) |
| `json_to_yaml` | `convert` | Plain JSON → YAML |
| `YamlTransformer` | `yaml_transformer` | Programmatic transformation engine |
| `TransformationError` | `yaml_transformer` | Exception type for error handling |
| `get_version_info` | `__init__` | Version helper |
| `__version__` | `__init__` | Version constant |

### `zs_yaml.convert`

| Symbol | Category | Notes |
|---|---|---|
| `yaml_to_bin` | 🟢 | Already at top level — don't re-render |
| `bin_to_yaml` | 🟢 | Same |
| `yaml_to_json` | 🟢 | Same |
| `json_to_yaml` | 🟢 | Same |
| `bin_to_dict` | 🟢 | Same |
| `yaml_to_yaml` | 🟡 | Apply transformations and write YAML |
| `yaml_to_pyobj` | 🟡 | YAML → in-memory zserio object |
| `pyobj_to_yaml` | 🟡 | zserio object → YAML |
| `_yaml_to_zserio_object` | 🔴 | Already underscore-prefixed |

### `zs_yaml.yaml_transformer`

| Symbol | Category | Notes |
|---|---|---|
| `YamlTransformer` | 🟢 | Already at top level |
| `TransformationError` | 🟢 | Already at top level |

### `zs_yaml.built_in_transformations`

YAML-side transformations invoked from `.yaml` via `_f:`. Not Python-import API.

| Symbol | Category | Notes |
|---|---|---|
| `insert_yaml`, `insert_yaml_as_extern`, `extract_extern_as_yaml` | 🟢 (as YAML) | YAML transformation |
| `repeat_node`, `py_eval` | 🟢 (as YAML) | YAML transformation |
| `CompressionType` | 🟡 | Enum used by extern transformations |
| `_compress`, `_decompress`, `_resolve_compression_type` | 🔴 | Already underscore-prefixed |

**Recommendation:** exclude this submodule from the Python API docs in this
round. A future "YAML Transformations" page (matching `ndslive-yaml`) is the
right place. USAGE.md already covers them from the YAML-author perspective.

### `zs_yaml.main`

All symbols are CLI plumbing. **Exclude the entire submodule.**

| Symbol | Category | Notes |
|---|---|---|
| `parse_arguments`, `process_yaml_input`, `process_binary_input`, `process_json_input`, `get_file_size`, `print_summary`, `main` | 🔴 | CLI only |

---

## Summary: what to render

Top-level `zs_yaml` page only — populated by `__all__`. Two submodule pages
(`convert`, `yaml_transformer`) appear in the toctree, also driven by their own
`__all__`. `main` and `built_in_transformations` are excluded via
`exclude: [main, built_in_transformations]` in `devportal.yaml`.

Estimated visible surface: 9 top-level entries + 3 advanced entries in
`convert` = 12 documented symbols (down from ~30 if everything were rendered).
