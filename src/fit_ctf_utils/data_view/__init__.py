from typing import Type

from fit_ctf_utils.data_view import csv_view, data_view, tabulate_view


def get_view(name: str) -> Type[data_view.DataView]:
    if name == "csv":
        return csv_view.CSVView
    elif name == "tabulate":
        return tabulate_view.TabulateView
    raise ValueError("Unknown DataView.")


__all__ = ["get_view"]
