Deployment
==========

FIT-CTF supports three deployment modes, from simplest to full production.

Local development
-----------------

Best for operators learning the platform or developing scenarios.

1. Install dependencies (:doc:`installation`).
2. Generate ``.env`` and start MongoDB:

   .. code-block:: sh

      poetry run inv generate-env --db-username=ctf_user --db-password=changeme --db-name=ctf_db
      # add DB_ADMIN_USERNAME / DB_ADMIN_PASSWORD to .env
      poetry run inv db-start

3. Run CLI commands directly from the repository:

   .. code-block:: sh

      poetry run fit-ctf project create --project-name demo
      poetry run fit-rendezvous

4. Data accumulates under ``~/.local/share/fit-ctf/``.

Podman/Docker runs challenge containers on the same host. No SSH forwarding is required
if you launch Rendezvous locally.

User-level systemd (MongoDB via Quadlet)
----------------------------------------

For a single-server setup where MongoDB should survive reboots without Docker Compose,
deploy a Podman Quadlet unit:

.. code-block:: sh

   poetry run inv db-deploy \
       --db-admin-username=admin \
       --db-admin-password=admin_secret \
       --db-username=ctf_user \
       --db-password=changeme \
       --db-name=ctf_db

This renders ``mongodb.container`` and ``mongodb.volume`` into
``~/.config/containers/systemd/`` and runs ``systemctl --user daemon-reload``.

Start the database:

.. code-block:: sh

   systemctl --user start mongodb.container

Production VM (fit-ctf-virt)
----------------------------

For a full CTF event with multiple participants connecting over SSH, use the
**fit-ctf-virt** companion repository. It provisions Incus instances (playground VM,
MongoDB container, optional monitoring) and runs Ansible to install FIT-CTF in
production layout.

See :doc:`fit-ctf-virt` for architecture, configuration, and the full installation
workflow.

FIT-CTF (this repo) remains the application layer; fit-ctf-virt handles infrastructure.

Rendezvous over SSH
-------------------

See :doc:`rendezvous` for the full guide (gatekeeper Linux user, ``inv setup-sshd``,
installing ``99-ctf-rule.conf``, firewall, TUI usage, and troubleshooting).

Short version:

.. code-block:: sh

   poetry run inv setup-sshd \
       --user=ctfparticipant \
       --rdz-port=2222 \
       --fitctf-dirpath=/home/operator/fit-ctf

   sudo cp 99-ctf-rule.conf /etc/ssh/sshd_config.d/
   sudo sshd -t && sudo systemctl reload sshd

Participants connect with ``ssh -p 2222 ctfparticipant@<host>`` and then log into the
TUI with their FIT-CTF username and password.

Container engine in production
------------------------------

Set ``CONTAINER_CLIENT=podman`` in ``.env``. Ensure ``podman-compose`` is on ``PATH``
for the user running ``fit-ctf`` commands.

Rootless Podman is supported; volume mounts in compiled scenarios use paths under the
share directory.

Pre-event checklist
-------------------

.. list-table::
   :header-rows: 1
   :widths: 5 45 50

   * - #
     - Task
     - Command / note
   * - 1
     - MongoDB running and reachable
     - ``inv db-start`` or ``systemctl --user start mongodb.container``
   * - 2
     - ``.env`` complete
     - All required DB variables set
   * - 3
     - Share directories initialized
     - First ``fit-ctf`` command seeds templates
   * - 4
     - Project created and scenarios compiled
     - ``fit-ctf project-cluster compile``, ``fit-ctf user-cluster compile``
   * - 5
     - Module images built
     - ``fit-ctf user-cluster build`` / ``project-cluster build``
   * - 6
     - Shared infrastructure started
     - ``fit-ctf project-cluster start``
   * - 7
     - Users enrolled
     - ``fit-ctf enrollment enroll``
   * - 8
     - SSH / Rendezvous configured
     - ``inv setup-sshd`` (automated by fit-ctf-virt on playground); publish port
       :doc:`fit-ctf-virt`
   * - 9
     - Smoke test
     - Enroll a test user, start instance, submit a secret

Backup and migration
--------------------

Export a project's filesystem data and database records:

.. code-block:: sh

   fit-ctf data-mgmt export -p <project_name> -o backup.zip

Import on another host:

.. code-block:: sh

   fit-ctf data-mgmt import -i backup.zip

Hosted documentation
--------------------

Documentation is built with Sphinx and published to GitHub Pages on pushes to ``main``
(``.github/workflows/build-documentation.yaml``).

Build locally:

.. code-block:: sh

   cd docs/sphinx && poetry run make html

Hosted: `hungdojan.github.io/fit-ctf <https://hungdojan.github.io/fit-ctf/>`__
