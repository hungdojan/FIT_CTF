import pathlib

import yaml
from jsonschema.validators import validator_for
from referencing import Registry, Resource

from fit_ctf_utils.data_parser.data_parser_interface import DataParserInterface
from fit_ctf_utils.exceptions import (
    DataFileNotExistException,
    SchemaFileNotExistException,
)


class YamlParser(DataParserInterface):

    registry: Registry

    class IndentDumper(yaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(YamlParser.IndentDumper, self).increase_indent(flow, False)

    @classmethod
    def init_parser(cls):
        cls._validators = {}
        cls._schema_registery = {}
        schema_root_path = cls.get_schema_dirpath() / "v1"
        if not schema_root_path.exists():
            return

        registry = {}
        validator_mapping = {}

        for filepath in schema_root_path.iterdir():
            if filepath.name.endswith(".yaml"):
                schema = cls.load_data_file(filepath)
                registry[schema["$id"]] = Resource.from_contents(schema)
                validator_mapping[filepath.name.rstrip(".yaml")] = schema

        cls.registry = Registry().with_resources(list(registry.items()))

        for name, s in validator_mapping.items():
            cls._validators[name] = validator_for(s)(s, registry=cls.registry)

    @classmethod
    def register_validator(
        cls, validator_name: str, schema_filepath: str | pathlib.Path
    ):
        if isinstance(schema_filepath, str):
            schema_filepath = pathlib.Path(schema_filepath)
        if not schema_filepath.exists():
            raise SchemaFileNotExistException(
                f"Schema `{str(schema_filepath)}` not found."
            )
        schema = yaml.safe_load(schema_filepath.resolve().read_text())
        cls._validators[validator_name] = validator_for(schema)(
            schema, registry=cls.registry
        )

    @classmethod
    def load_data_stream(
        cls,
        stream,
        validator_name: str | None = None,
        **kw,
    ) -> dict:
        obj = yaml.safe_load(stream)

        if validator_name is not None:
            cls.validate_data(obj, validator_name)
        return obj

    @classmethod
    def load_data_file(
        cls,
        file: pathlib.Path,
        validator_name: str | None = None,
        **kw,
    ) -> dict:
        if not file.exists():
            raise DataFileNotExistException(
                f"Config file `{file.resolve()}` not found."
            )
        obj = yaml.safe_load(file.read_text())

        if validator_name is not None:
            cls.validate_data(obj, validator_name)
        return obj

    @classmethod
    def validate_data(cls, data: dict, validator_name: str):
        validator = cls.get_validator(validator_name)
        validator.validate(data)

    @classmethod
    def dump_data(cls, data: dict, **kw) -> str:
        return yaml.dump(data, Dumper=cls.IndentDumper, indent=2)
