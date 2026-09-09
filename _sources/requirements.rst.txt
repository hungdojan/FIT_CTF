Requirements
============

Software
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Component
     - Version / notes
   * - Python
     - 3.10 or newer (tested on 3.10–3.14 in CI)
   * - Poetry
     - For dependency management and virtualenv
   * - Podman
     - Container runtime for challenge environments
   * - podman-compose
     - Compose orchestration for Podman (`GitHub <https://github.com/containers/podman-compose>`__)
   * - Docker + Docker Compose
     - Optional alternative container backend for challenge clusters (``CONTAINER_CLIENT=docker``)
   * - MongoDB
     - Provided by ``db/compose.yaml`` for local dev, or external instance for production
   * - Invoke
     - Installed as a Poetry dependency; provides ``inv`` tasks for DB and setup

Optional
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Purpose
   * - ``$EDITOR``
     - Required when editing scenario service configs from the CLI
   * - systemd (user session)
     - For ``inv db-deploy`` (Podman Quadlet MongoDB unit)
   * - OpenSSH server
     - For Rendezvous access via ``inv setup-sshd``
   * - pre-commit
     - Development hook runner (``poetry install`` with dev group)

Development dependencies
------------------------

Install the full dev environment (tests, linters, docs):

.. code-block:: sh

   poetry install

Production install (runtime only):

.. code-block:: sh

   poetry install --only main

Documentation build requires the ``docs`` dependency group (Sphinx, sphinx-click,
sphinx-rtd-theme), included in a full ``poetry install``.
