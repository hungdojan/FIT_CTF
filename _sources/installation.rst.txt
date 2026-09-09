Installation
============

Install system dependencies
---------------------------

Debian
~~~~~~

On Debian 12 (bookworm) or newer:

.. code-block:: sh

   sudo apt update
   sudo apt install -y git python3 python3-venv pipx podman podman-compose

Install Poetry (if not already available):

.. code-block:: sh

   pipx install poetry
   pipx ensurepath
   # reopen the shell, then continue below

Fedora / RHEL
~~~~~~~~~~~~~

.. code-block:: sh

   sudo dnf install podman podman-compose

Install and verify Podman
-------------------------

Local MongoDB and challenge containers both run through Podman. Confirm the tools are
available before continuing:

.. code-block:: sh

   podman --version
   podman compose version
   podman-compose --version

``inv db-start`` uses ``podman compose`` to run ``db/compose.yaml``. Challenge clusters
use ``podman-compose`` when ``CONTAINER_CLIENT=podman`` (the default).

Clone and install
-----------------

.. code-block:: sh

   git clone https://github.com/hungdojan/fit-ctf.git
   cd fit-ctf
   poetry install --only main

This installs three packages from ``src/``:

- ``fit_ctf`` — core library
- ``fit_ctf_cli`` — operator CLI (``fit-ctf`` command)
- ``fit_ctf_rendezvous`` — participant TUI (``fit-rendezvous`` command)

Generate environment file
-------------------------

Create a ``.env`` file at the repository root with database credentials and paths:

.. code-block:: sh

   poetry run inv generate-env \
       --db-username=ctf_user \
       --db-password=changeme \
       --db-name=ctf_db

Optional flags: ``--db-host`` (default ``localhost``), ``--db-port`` (default ``27017``).

The template is rendered from ``config/setup/env_example``. See :doc:`configuration` for
all variables.

Set ``CONTAINER_CLIENT=podman`` in ``.env`` (this is the default).

Start MongoDB (local development)
---------------------------------

FIT-CTF's Invoke task starts MongoDB via **Podman Compose** (requires Podman from the
previous step):

.. code-block:: sh

   poetry run inv db-start

This reads ``db/compose.yaml`` and expects ``DB_ADMIN_USERNAME`` and
``DB_ADMIN_PASSWORD`` for the MongoDB root user. Add them to ``.env`` before starting
if they are not already present:

.. code-block:: sh

   DB_ADMIN_USERNAME=admin
   DB_ADMIN_PASSWORD=admin_secret

Other database tasks:

.. code-block:: sh

   poetry run inv db-stop      # stop MongoDB container
   poetry run inv db-restart   # restart
   poetry run inv db-shell     # open mongosh shell

Verify installation
-------------------

.. code-block:: sh

   poetry run fit-ctf --help
   poetry run fit-rendezvous   # launches TUI (Ctrl+C to exit)

On first use, FIT-CTF creates the share directory tree and copies bundled templates:

.. code-block:: text

   ~/.local/share/fit-ctf/
   ├── project/
   ├── user/
   ├── module/      ← template, ssh_debian, ssh_ubi
   └── scenario/    ← template, login_node, admin_node

Development installation
------------------------

For contributors, install all dependency groups:

.. code-block:: sh

   poetry install
   poetry run pre-commit install   # optional hooks

Run the test suite:

.. code-block:: sh

   poetry run pytest

Build documentation:

.. code-block:: sh

   cd docs/sphinx
   poetry run make html
   xdg-open _build/html/index.html

Next steps
----------

Continue with :doc:`quickstart` for a minimal end-to-end setup, :doc:`rendezvous` for SSH
and participant TUI setup, or :doc:`configuration` to customize paths and logging.
