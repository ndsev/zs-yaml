from contextlib import contextmanager
from contextvars import ContextVar
from string import Template
import importlib
import importlib.util
import json
import os
import warnings
import yaml
import zs_yaml.built_in_transformations

# Cache of already-transformed YAML files for the transform currently in
# progress. It is a ContextVar rather than a module global so that concurrent
# transforms in different threads or asyncio tasks never share entries.
# ``None`` means no transform is in progress and nothing is cached.
_active_cache = ContextVar("zs_yaml_transform_cache", default=None)


# Name of the environment variable a person sets to pick a YAML loader for a
# run. It outranks anything the calling code selected: the loaders produce the
# same data, so the choice is the operator's to make or to undo.
LOADER_ENV_VAR = "ZS_YAML_LOADER"


def _load_pyyaml(content):
    """The default loader, and the reference every other loader matches."""
    return yaml.load(content, Loader=yaml.CLoader)


def _resolve_loader(loader):
    """Return the load function to use, given a per-instance `loader` request.

    Precedence is environment variable, then the `loader` argument, then
    :attr:`YamlTransformer.LOADER`. The environment variable comes first
    because it is how a person overrides what the calling code chose.

    Which of those selected the loader also decides what happens when the
    optional `rapidyaml` dependency is not installed. Setting the environment
    variable is a deliberate act by whoever runs the conversion, so a missing
    dependency is an error they asked to hear about. Selecting it from code is
    a library's default, which must not turn a missing wheel into a broken
    build, so that path warns and uses PyYAML.
    """
    from_env = os.environ.get(LOADER_ENV_VAR)
    selected_by_env = bool(from_env)
    name = (from_env or loader or YamlTransformer.LOADER).lower()

    if name == "pyyaml":
        return _load_pyyaml
    if name != "ryml":
        # A name neither path recognises is a typo, not a missing wheel, and
        # falling back would hide it. Both paths raise.
        raise ValueError(
            f"Unknown YAML loader '{name}'. Expected 'pyyaml' or 'ryml' "
            f"(install rapidyaml with: pip install zs-yaml[fast])."
        )

    from zs_yaml import _ryml_loader
    try:
        _ryml_loader.ensure_available()
    except ImportError:
        if selected_by_env:
            raise
        warnings.warn(
            f"YAML loader 'ryml' was selected in code but rapidyaml is not "
            f"installed; falling back to PyYAML. Install it with "
            f"'pip install zs-yaml[fast]', or set {LOADER_ENV_VAR}=pyyaml to "
            f"silence this.",
            RuntimeWarning,
            stacklevel=3,
        )
        return _load_pyyaml
    return _ryml_loader.load


def _loader_kwarg(loader):
    """`loader=` as keyword arguments, empty when no loader was requested.

    `YamlTransformer` is subclassed with the three-parameter `__init__` it had
    before `loader` existed — `examples/team/test_all_conversions.py` does it.
    Forwarding the parameter only when a loader was actually selected leaves
    those subclasses working on the default path.
    """
    return {"loader": loader} if loader is not None else {}


class TransformationError(Exception):
    """Exception raised during YAML transformation with file context."""
    def __init__(self, message, file_path=None, original_error=None):
        self.file_path = file_path
        self.original_error = original_error
        if file_path:
            message = f"Error in file '{file_path}': {message}"
        super().__init__(message)


class YamlTransformer:
    """
    Encapsulates a transformed yaml and allows
    accessing the transformed data, original data and metadata..

    Transformed files are cached only for the duration of one transform, so
    converting many documents in one process does not accumulate expanded
    trees. See :meth:`cache_session` to widen that window deliberately.
    """

    # Loaded transformation modules, keyed by absolute file path. Bounded by
    # the number of distinct transformation modules a process imports, the
    # same way `sys.modules` is; deliberately not per-transform, because
    # re-executing a module would produce new function objects and trip the
    # duplicate-name check in `_register_function`.
    _loaded_modules = {}

    # Which YAML loader to use when the caller names none: "pyyaml" (the
    # default, PyYAML's CLoader) or "ryml" (rapidyaml, from the optional
    # [fast] extra). Both build the same Python tree; see the module-level
    # `_resolve_loader` for how a selection is made and what happens when
    # rapidyaml is missing.
    LOADER = "pyyaml"

    def __init__(self, yaml_file_path, template_args=None, initial_transformations=None,
                 loader=None):
        self.yaml_file_path = os.path.abspath(yaml_file_path)
        self.transformations = initial_transformations or {}
        # The requested name is kept alongside the resolved function so that
        # included documents can be transformed with the same selection.
        self._loader_name = loader
        self._load_yaml = _resolve_loader(loader)
        self._load_functions(zs_yaml.built_in_transformations)
        # Opening a session here is what makes repeated includes inside this
        # document share one transformer. When a session is already open
        # (nested include, or one opened by the caller) this joins it.
        with self.cache_session():
            self._load_and_transform(template_args)

    def _load_and_transform(self, template_args):
        try:
            with open(self.yaml_file_path, 'r') as yaml_file:
                content = yaml_file.read()
        except Exception as e:
            raise TransformationError(
                f"Failed to read file: {e}",
                file_path=self.yaml_file_path,
                original_error=e
            )

        if template_args:
            content = Template(content).safe_substitute(template_args)

        # Check if transformation is needed (optimization to skip _process if no function calls)
        needs_transformation = "_f:" in content

        try:
            self.original_data = self._load_yaml(content)
        except yaml.YAMLError as e:
            # Extract line/column info if available
            line_info = ""
            if hasattr(e, 'problem_mark') and e.problem_mark:
                line_info = f" at line {e.problem_mark.line + 1}, column {e.problem_mark.column + 1}"
            raise TransformationError(
                f"YAML parsing error{line_info}: {e}",
                file_path=self.yaml_file_path,
                original_error=e
            )
        
        if ('_meta' in self.original_data):
            self.metadata = self.original_data.pop('_meta', {})
            transformation_module = self.metadata.get('transformation_module')
            if transformation_module:
                self._load_functions(transformation_module)
        else:
            self.metadata = None

        # Skip transformation processing if no function calls detected
        if needs_transformation:
            self.data = self._process(self.original_data)
        else:
            self.data = self.original_data

    def resolve_path(self, path):
        yaml_dir = os.path.dirname(self.yaml_file_path)
        return os.path.normpath(os.path.join(yaml_dir, path))

    def to_json(self):
        return json.dumps(self.data, indent=2)

    def get_meta(self):
        return self.metadata

    @classmethod
    def _load_module_from_file(cls, module_name, file_path):
        abs_path = os.path.abspath(file_path)
        if abs_path in cls._loaded_modules:
            return cls._loaded_modules[abs_path]

        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls._loaded_modules[abs_path] = module
        return module

    def _load_functions(self, transformation_module):
        if isinstance(transformation_module, str):
            if transformation_module.endswith('.py'):
                abs_path = self.resolve_path(transformation_module)
                transformation_module = self._load_module_from_file('custom_transformations', abs_path)
            else:
                transformation_module = importlib.import_module(transformation_module)

        for name, func in vars(transformation_module).items():
            if callable(func):
                self._register_function(name, func)

    def _register_function(self, name, func):
        if name in self.transformations:
            if self.transformations[name] != func:
                raise ValueError(f"Attempting to register a different function with an existing name: {name}")
        else:
            self.transformations[name] = func

    def _get_function(self, name):
        return self.transformations.get(name)

    def _process(self, data):
        if isinstance(data, list):
            return [self._process(item) for item in data]
        elif isinstance(data, dict):
            if '_f' in data and '_a' in data:
                func = self._get_function(data['_f'])
                args = self._process(data['_a'])  # Process the arguments recursively
                if func and callable(func):
                    try:
                        if isinstance(args, dict):
                            return func(self, **args)
                        else:
                            return func(self, args)
                    except TransformationError:
                        # Re-raise TransformationError as-is to preserve context
                        raise
                    except Exception as e:
                        # Wrap other exceptions with context
                        raise TransformationError(
                            f"Error in transformation '{data['_f']}': {e}",
                            file_path=self.yaml_file_path,
                            original_error=e
                        )
                else:
                    raise ValueError(f"Function {data['_f']} not found or is not callable")
            else:
                return {key: self._process(value) for key, value in data.items()}
        return data

    @classmethod
    @contextmanager
    def cache_session(cls):
        """Share one transform cache across everything done inside the block.

        Without it, each top-level transform gets its own cache and drops it
        on return, so a process converting many documents retains none of
        them. Open a session when several documents pull in the same
        includes and that work should be done once::

            with YamlTransformer.cache_session():
                for src, dst in jobs:
                    yaml_to_bin(src, dst)

        Everything cached inside is released when the block exits. Files are
        assumed not to change while a session is open; if a transformation
        rewrites a file that an earlier include already read (as
        `extract_extern_as_yaml` can), call :meth:`clear_cache` or keep the
        session narrower.

        Nesting joins the outer session rather than starting a second one, so
        only the outermost block releases the cache.
        """
        existing = _active_cache.get()
        if existing is not None:
            yield existing
            return

        cache = {}
        token = _active_cache.set(cache)
        try:
            yield cache
        finally:
            _active_cache.reset(token)
            cache.clear()

    @classmethod
    def get_or_create(cls, yaml_file_path, template_args=None, initial_transformations=None,
                      loader=None):
        """Return the transformer for `yaml_file_path`, reusing a cached one.

        Reuse is limited to the cache of the enclosing session (see
        :meth:`cache_session`). Outside any session nothing is cached and
        every call builds a fresh transformer.

        `loader` is not part of the cache key: both loaders build the same
        tree, so a cached entry is valid whichever one produced it.
        """
        abs_path = os.path.abspath(yaml_file_path)
        cache_key = (abs_path, frozenset(template_args.items()) if template_args else None)

        cache = _active_cache.get()
        if cache is not None and cache_key in cache:
            return cache[cache_key]

        transformed_yaml = cls(abs_path, template_args, initial_transformations,
                               **_loader_kwarg(loader))
        if cache is not None:
            cache[cache_key] = transformed_yaml
        return transformed_yaml

    @classmethod
    def clear_cache(cls):
        """Drop what the enclosing cache session has cached so far.

        Call this inside a :meth:`cache_session` when YAML files or their
        output files (created by transformations like
        `extract_extern_as_yaml`) are written or deleted while the session is
        open, since cached entries would otherwise be stale. Outside a
        session there is nothing to clear and the call does nothing.
        """
        cache = _active_cache.get()
        if cache is not None:
            cache.clear()