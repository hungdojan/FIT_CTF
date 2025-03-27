import csv
import sys

import fit_ctf_utils.data_view.data_view as data_view


class CSVView(data_view.DataView):

    @staticmethod
    def print_data(headers: list, values: list[list], **kw):
        csv_writer = csv.writer(sys.stdout)
        csv_writer.writerow(headers)
        csv_writer.writerows(values)
