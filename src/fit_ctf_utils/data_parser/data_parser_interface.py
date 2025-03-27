import os
import pathlib
from abc import ABC, abstractmethod

from jsonschema.protocols import Validator

from fit_ctf_utils.exceptions import ValidatorNotExistException


class DataParserInterface(ABC):
    """A base class for loading and validating structured data files."""

    _validators: dict[str, Validator] = dict()

    @staticmethod
    def get_schema_dirpath() -> pathlib.Path:
        return (
            pathlib.Path(
                os.path.dirname(os.path.realpath(__file__))
            ).parent.parent.parent
            / "schemas"
        )

    @classmethod
    @abstractmethod
    def init_parser(cls):
        """Run the initial configuration to setup the parser.

        Each class will define their own setup.
        """
        pass

    @classmethod
    @abstractmethod
    def register_validator(
        cls, validator_name: str, schema_filepath: str | pathlib.Path
    ):
        """Initialize and register the schema validator.

        :param validator_name: An identification name for the validator.
        :type validator_name: str
        :param schema_filepath: A path to the schema file.
        :type schema_filepath: str | pathlib.Path
        :raises SchemaFileNotExistException: When the schema file could not be located.
        """
        raise NotImplementedError()

    @classmethod
    def get_validator(cls, validator_name: str) -> Validator:
        """Returns a registered validator.

        If the validator with the given name does not exist
        the function raises ValidatorNotExistException exception.

        :param validator_name: An identification name for the validator.
        :type validator_name: str
        :raises ValidatorNotExistException: When the validator is not registered.
        :return: The registered validator.
        :rtype: Validator.
        """
        validator = cls._validators.get(validator_name)
        if not validator:
            raise ValidatorNotExistException(
                f"Validator `{validator_name}` does not exist."
            )
        return validator

    @classmethod
    @abstractmethod
    def load_data_stream(
        cls,
        stream,
        validator_name: str | None = None,
        **kw,
    ) -> dict:
        """Load and validate the given data file.

        If the user does not pass a validator name, the function will only load
        the content of the file.

        :param stream: A data stream.
        :param validator_name: An identification name of the validator. When set
            to None, the function will not run the data against the schema file.
            The default value is None.
        :type validator_name: str | None
        :raises DataFileNotExistException: When the data file could not be located.
        :raises ValidatorNotExistException: When the validator is not registered.
        :return: The loaded configuration data.
        :rtype: dict.
        """

        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def load_data_file(
        cls,
        file: pathlib.Path,
        validator_name: str | None = None,
        **kw,
    ) -> dict:
        """Load and validate the given data file.

        If the user does not pass a validator name, the function will only load
        the content of the file.

        :param file: A path to the data file.
        :type file: pathlib.Path
        :param validator_name: An identification name of the validator. When set
            to None, the function will not run the data against the schema file.
            The default value is None.
        :type validator_name: str | None
        :raises DataFileNotExistException: When the data file could not be located.
        :raises ValidatorNotExistException: When the validator is not registered.
        :return: The loaded configuration data.
        :rtype: dict.
        """

        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def validate_data(cls, data: dict, validator_name: str):
        """Run JSON Schema validation against the data.

        :param data: Object in question.
        :type data: dict
        :param validator_name: A validator ID name.
        :type validator_name: str
        """
        pass

    @classmethod
    @abstractmethod
    def dump_data(cls, data: dict, **kw) -> str:
        """Convert serialized data to string.

        :param data: Data to be serialized.
        :type data: dict
        :return: Serialized data in string format.
        :rtype output_file: str
        """
        raise NotImplementedError()
