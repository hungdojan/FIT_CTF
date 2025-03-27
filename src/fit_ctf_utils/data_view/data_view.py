from abc import ABC, abstractmethod


class DataView(ABC):

    @staticmethod
    @abstractmethod
    def print_data(headers: list, values: list[list], **kw):  # pragma: no cover
        """Prints data in table format to STDOUT."""
        raise NotImplementedError()
