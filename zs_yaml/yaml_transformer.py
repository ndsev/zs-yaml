import importlib
import importlib.util
import os
import yaml
import json
import zs_yaml.built_in_transformations

class YamlTransformer:
    """
    Encapsulates the transformation of yaml data using
    invocations of registered transformation functions.
    """

    def __init__(self, yaml_file_path):
        self.yaml_file_path = yaml_file_path
        self.yaml_dir = os.path.dirname(os.path.abspath(yaml_file_path))
        self.transformations = {}
        self.load_functions(zs_yaml.built_in_transformations)
        self.meta = {}

    def _load_module_from_file(self, module_name, file_path):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_functions(self, transformation_module):
        if isinstance(transformation_module, str):
            if transformation_module.endswith('.py'):
                abs_path = self.resolve_path(transformation_module)
                transformation_module = self._load_module_from_file('custom_transformations', abs_path)
            else:
                transformation_module = importlib.import_module(transformation_module)

        for name, func in vars(transformation_module).items():
            if callable(func):
                self.register_function(name, func)

    def register_function(self, name, func):
        self.transformations[name] = func

    def get_function(self, name):
        return self.transformations.get(name)

    def resolve_path(self, path):
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.yaml_dir, path))

    def process(self, data):
        if isinstance(data, list):
            return [self.process(item) for item in data]
        elif isinstance(data, dict):
            if '_f' in data and '_a' in data:
                func = self.get_function(data['_f'])
                args = data['_a']
                if func and callable(func):
                    if isinstance(args, dict):
                        return func(**args, transformer=self) if 'transformer' in func.__code__.co_varnames else func(**args)
                    else:
                        return func(args, transformer=self) if 'transformer' in func.__code__.co_varnames else func(args)
                else:
                    raise ValueError(f"Function {data['_f']} not found or is not callable")
            else:
                return {key: self.process(value) for key, value in data.items()}
        return data

    def transform(self):
        with open(self.yaml_file_path, 'r') as yaml_file:
            data = yaml.safe_load(yaml_file)

        self.meta = data.pop('_meta', {})
        transformation_module = self.meta.get('transformation_module')

        if transformation_module:
            self.load_functions(transformation_module)

        return self.process(data)

    def to_json(self):
        processed_data = self.transform()
        return json.dumps(processed_data, indent=2)

    def get_meta(self):
        return self.meta