from string import Template
import importlib
import importlib.util
import json
import os
import yaml
import zs_yaml.built_in_transformations


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
    """

    # Class-level caches (modules and transformed yamls)
    _loaded_modules = {}
    _transformed_yaml_cache = {}

    def __init__(self, yaml_file_path, template_args=None, initial_transformations=None):
        self.yaml_file_path = os.path.abspath(yaml_file_path)
        self.transformations = initial_transformations or {}
        self._load_functions(zs_yaml.built_in_transformations)
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

        try:
            self.original_data = yaml.load(content, Loader=yaml.CLoader)
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

        self.data = self._process(self.original_data)

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
    def get_or_create(cls, yaml_file_path, template_args=None, initial_transformations=None):
        abs_path = os.path.abspath(yaml_file_path)
        cache_key = (abs_path, frozenset(template_args.items()) if template_args else None)

        cache = YamlTransformer._transformed_yaml_cache
        if cache_key in cache:
            return cache[cache_key]

        transformed_yaml = cls(abs_path, template_args, initial_transformations)
        cache[cache_key] = transformed_yaml
        return transformed_yaml