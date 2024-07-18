import importlib
import importlib.util
import json
import os
import yaml
import zs_yaml.built_in_transformations
from string import Template

class YamlTransformer:
    """
    Encapsulates the transformation of yaml data using
    invocations of registered transformation functions.
    """

    # Class-level cache for loaded modules
    _loaded_modules = {}

    def __init__(self, yaml_file_path, template_args=None, initial_transformations=None):
        self.yaml_file_path = yaml_file_path
        self.yaml_dir = os.path.dirname(os.path.abspath(yaml_file_path))
        self.transformations = initial_transformations or {}
        self._load_functions(zs_yaml.built_in_transformations)
        self.meta = {}
        self.template_args = template_args
        self.yaml_data = None

    def resolve_path(self, path):
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.yaml_dir, path))

    def transform(self):
        if self.yaml_data is None:
            self._load_yaml()

        transformation_module = self.meta.get('transformation_module')

        if transformation_module:
            self._load_functions(transformation_module)

        return self._process(self.yaml_data)

    def to_json(self):
        processed_data = self.transform()
        return json.dumps(processed_data, indent=2)

    def get_meta(self):
        if self.yaml_data is None:
            self._load_yaml()
        return self.meta

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
                args = data['_a']
                if func and callable(func):
                    if isinstance(args, dict):
                        return func(self, **args)
                    else:
                        return func(self, args)
                else:
                    raise ValueError(f"Function {data['_f']} not found or is not callable")
            else:
                return {key: self._process(value) for key, value in data.items()}
        return data

    def _load_yaml(self):
        with open(self.yaml_file_path, 'r') as yaml_file:
            content = yaml_file.read()

        if self.template_args:
            content = Template(content).safe_substitute(self.template_args)

        self.yaml_data = yaml.safe_load(content)
        self.meta = self.yaml_data.pop('_meta', {})
