import yaml
import json
import importlib
import zserio


class TransformationRegistry:
    def __init__(self):
        self.transformations = {}

    def register(self, name, func):
        self.transformations[name] = func

    def get(self, name):
        return self.transformations.get(name)

    def process_data(self, data):
        if isinstance(data, list):
            return [self.process_data(item) for item in data]
        elif isinstance(data, dict):
            if '_f' in data and '_a' in data:
                func = self.get(data['_f'])
                args = data['_a']
                if func and callable(func):
                    # If the function accepts a registry argument, pass this
                    # this allows recursive invocation of process_data
                    if isinstance(args, dict):
                        return func(**args, registry=self) if 'registry' in func.__code__.co_varnames else func(**args)
                    else:
                        return func(args, registry=self) if 'registry' in func.__code__.co_varnames else func(args)
                else:
                    raise ValueError(f"Function {data['_f']} not found or is not callable")
            else:
                return {key: self.process_data(value) for key, value in data.items()}
        return data


def _load_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def yaml_to_zs_json(yaml_input_path, json_output_path, registry=None):
    with open(yaml_input_path, 'r') as yaml_file:
        data = yaml.safe_load(yaml_file)

    meta = data.pop('_meta', {})
    transformation_module = meta.get('transformation_module')

    if transformation_module and registry:
        if transformation_module.endswith('.py'):
            transformation_module = _load_module_from_file('custom_transformations', transformation_module)
            for name, func in vars(transformation_module).items():
                if callable(func):
                    registry.register(name, func)
        else:
            transformation_module = importlib.import_module(transformation_module)
            for name, func in vars(transformation_module).items():
                if callable(func):
                    registry.register(name, func)

    if registry:
        data = registry.process_data(data)

    with open(json_output_path, 'w') as json_file:
        json.dump(data, json_file, indent=2)

    return meta


def json_to_zs_bin(json_input_path, bin_output_path, module_name, type_name):
    module = importlib.import_module(module_name)
    ImportedType = getattr(module, type_name)
    if (ImportedType is None):
        raise ValueError(f"Type {type_name} not found in module {module_name}")
    zserio_object = zserio.from_json_file(ImportedType, json_input_path)
    zserio.serialize_to_file(zserio_object, bin_output_path)


