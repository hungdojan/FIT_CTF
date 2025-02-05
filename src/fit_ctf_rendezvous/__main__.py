import os
import sys

from dotenv import load_dotenv

from fit_ctf_rendezvous.actions import Actions
from fit_ctf_rendezvous.view import View


def main():
    load_dotenv()

    db_host = os.getenv("DB_HOST")
    if not db_host:
        sys.exit("Environment variable `DB_HOST` is not set.")

    # start frontend
    act = Actions(db_host)
    v = View(act)
    v.render_view()


if __name__ == "__main__":
    main()
