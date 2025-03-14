import pathlib

import yaml
from jsonschema.validators import validator_for

from fit_ctf_utils.exceptions import (
    DataFileNotExistException,
    SchemaFileNotExistException,
)
from fit_ctf_utils.config_loader.data_parser_interface import DataParserInterface


class YamlParser(DataParserInterface):

    def __init__(self) -> None:
        super().__init__()

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
        cls._validators[validator_name] = validator_for(schema)(schema)

    @classmethod
    def load_data(
        cls, data_filepath: str | pathlib.Path, validator_name: str | None = None, **kw
    ) -> dict:
        if isinstance(data_filepath, str):
            data_filepath = pathlib.Path(data_filepath)
        if not data_filepath.exists():
            raise DataFileNotExistException(
                f"Config file `{data_filepath.resolve()}` not found."
            )
        obj = yaml.safe_load(data_filepath.read_text())

        if validator_name is not None:
            validator = cls.get_validator(validator_name)
            validator.validate(obj)
        return obj

    @classmethod
    def write_data(cls, data: dict, output_file: str | pathlib.Path, **kw):
        with open(output_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)
