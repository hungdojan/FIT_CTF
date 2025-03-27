from tabulate import tabulate

import fit_ctf_utils.data_view.data_view as data_view


class TabulateView(data_view.DataView):

    @staticmethod
    def print_data(headers: list, values: list[list], **kw):  # pragma: no cover
        print(tabulate(values, headers, tablefmt="pipe", stralign="center", **kw))
