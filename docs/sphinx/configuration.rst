Configuration
=============

FIT-CTF reads configuration from a ``.env`` file at the repository root (loaded via
``python-dotenv``). Generate it with ``poetry run inv generate-env`` or create it
manually from the template at ``config/setup/env_example``.

Required variables
------------------

The application exits on startup if any of these are missing:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Variable
     - Example
     - Description
   * - ``DB_USERNAME``
     - ``ctf_user``
     - MongoDB application user (created by init script)
   * - ``DB_PASSWORD``
     - ``changeme``
     - Password for the application user
   * - ``DB_HOST``
     - ``localhost``
     - MongoDB hostname
   * - ``DB_PORT``
     - ``27017``
     - MongoDB port
   * - ``DB_NAME``
     - ``ctf_db``
     - Database name (optional in code but should always be set)

MongoDB admin credentials (local dev)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When using ``poetry run inv db-start``, Podman Compose needs root credentials for
the MongoDB container. Add these to ``.env`` (not written by ``generate-env``):

.. code-block:: ini

   DB_ADMIN_USERNAME=admin
   DB_ADMIN_PASSWORD=admin_secret

The init script at ``db/mongodb-quadlet/init-mongo.js`` creates the application user
with ``readWrite`` on ``DB_NAME``.

Optional variables
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``CONTAINER_CLIENT``
     - ``podman``
     - Container backend: ``podman``, ``docker``, or ``mock``
   * - ``DB_CONNECTION_TIMEOUT``
     - ``30``
     - Seconds to wait for MongoDB on connect
   * - ``LOG_DEST``
     - ``/tmp``
     - Directory for log files (one file per logger name)
   * - ``PROJECT_SHARE_DIR``
     - ``$HOME/.local/share/fit-ctf/project``
     - Root directory for project data
   * - ``USER_SHARE_DIR``
     - ``$HOME/.local/share/fit-ctf/user``
     - Root directory for user data
   * - ``MODULE_SHARE_DIR``
     - ``$HOME/.local/share/fit-ctf/module``
     - Root directory for module definitions
   * - ``SCENARIO_SHARE_DIR``
     - ``$HOME/.local/share/fit-ctf/scenario``
     - Root directory for scenario templates

.. note::

   The comments in ``config/setup/env_example`` use plural directory names
   (``projects``, ``users``). The **code defaults** use singular names
   (``project``, ``user``, ``module``, ``scenario``). Follow the code defaults unless
   you explicitly override the environment variables.

Rendezvous
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``FIT_RENDEZVOUS_LANG``
     - ``en``
     - UI language: ``en`` or ``cs``

Per-user Rendezvous preferences (locale, dark theme) are stored in:

.. code-block:: text

   ~/.local/share/fit-ctf/user/<username>/rendezvous_settings.json

CLI path overrides
------------------

The ``fit-ctf`` CLI accepts global options that override share directories for a single
invocation (without changing ``.env``):

.. code-block:: sh

   fit-ctf --project-dir /data/projects --user-dir /data/users project list

Options: ``--project-dir`` (``-pd``), ``--user-dir`` (``-ud``), ``--module-dir`` (``-md``),
``--scenario-dir`` (``-sd``).

Project-level settings
----------------------

Stored in MongoDB when a project is created:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Description
   * - ``name``
     - Lowercase alphanumeric + underscores only
   * - ``max_nof_users``
     - Maximum enrollments
   * - ``starting_port_bind``
     - First port in the SSH port range (default constant: ``10000``)
   * - ``description``
     - Free-text project description

Each enrollment receives ports from the range
``starting_port_bind .. starting_port_bind + max_nof_users - 1``.

Scenario and service configuration
-----------------------------------

Scenario configs (secrets, environment variables, port maps, volume maps) are stored in
cluster documents in MongoDB and edited via CLI commands such as
``fit-ctf user-cluster edit-service`` and ``fit-ctf user-cluster secrets``.

JSON schemas for validation live in ``src/fit_ctf/components/schemas/v1/``.

Bulk setup file
~~~~~~~~~~~~~~~

For bootstrapping multiple projects, users, and enrollments at once, use a YAML file
validated against ``setup.yaml``:

.. code-block:: sh

   poetry run fit-ctf data-mgmt setup -i connected_data.yaml

See :doc:`setup-file` for how to author the file, ``connected_data.yaml`` examples, and
how this differs from ``data-mgmt import`` (ZIP).

Logging
-------

Loggers write to ``$LOG_DEST/<logger_name>.log``. Cluster operations use the logger name
``fit_ctf.cluster``.

Example minimal ``.env``
------------------------

.. code-block:: ini

   DB_USERNAME=ctf_user
   DB_PASSWORD=changeme
   DB_NAME=ctf_db
   DB_HOST=localhost
   DB_PORT=27017

   DB_ADMIN_USERNAME=admin
   DB_ADMIN_PASSWORD=admin_secret

   CONTAINER_CLIENT=podman
   DB_CONNECTION_TIMEOUT=30
   LOG_DEST=/tmp
