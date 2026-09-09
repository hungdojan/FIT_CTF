Production infrastructure (fit-ctf-virt)
========================================

`fit-ctf-virt <https://github.com/hungdojan/fit-ctf-virt>`__ is a companion
repository that provisions and configures FIT-CTF on a production-style host using
`Incus <https://linuxcontainers.org/incus/>`__ (the LXD successor). It is **not**
the CTF application itself — it handles infrastructure automation while this
repository remains the application layer.

Use fit-ctf-virt when you need:

- A dedicated playground **virtual machine** for Podman challenge containers
- A separate **MongoDB** instance on a private network
- Optional **Prometheus + Grafana** monitoring
- Participant access over SSH into :doc:`rendezvous`

For local development or a single-server setup without Incus, see :doc:`deployment`
instead.

Relationship to FIT-CTF
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Repository
     - Responsibility
   * - **fit-ctf** (this repo)
     - ``fit-ctf`` CLI, ``fit-rendezvous`` TUI, MongoDB schema, scenarios/modules,
       Podman clusters, ``inv generate-env``, ``inv setup-sshd``, ``inv db-deploy``
   * - **fit-ctf-virt**
     - Incus storage/network/profile/instances, Ansible provisioning, monitoring
       stack, production directory layout on the playground VM

During playground initialization, fit-ctf-virt clones FIT-CTF to ``/opt/fit-ctf`` and
runs FIT-CTF's own Invoke tasks to generate ``.env`` and configure SSH/Rendezvous.

Architecture
------------

fit-ctf-virt deploys three Incus instances on a private bridge network:

.. code-block:: text

   Incus host (Rocky Linux 10)
   └── fitctfbr0  (10.100.0.1/24, NAT)
       ├── fit-ctf-playground   VM         10.100.0.2
       │   FIT-CTF, Podman, SSH :5555, node-exporter :9100
       ├── fit-ctf-database     container  10.100.0.3
       │   MongoDB 7
       └── fit-ctf-monitoring   container  10.100.0.4
           Prometheus :9090, Grafana :3000

**Why a VM for the playground?** Nested Podman workloads, disk resize, and fuller
kernel isolation are easier on a virtual machine. Database and monitoring run as
lighter containers.

Instance names resolve as DNS hostnames on the Incus bridge (for example,
``fit-ctf-database`` from the playground VM).

Requirements
------------

**Incus host** (bare metal or VM):

- Rocky Linux 10 (tested)
- Incus ``>= 0.5.1`` (tested on 6.21)
- ``mkisofs`` and ``qemu-system-x86_64`` — required for the playground VM
- Python 3.12+ with Poetry

**Inside each instance** (installed automatically by Ansible):

- ``ansible-core``, Podman or Docker (depending on role), and Galaxy collections
  ``community.general``, ``community.mongodb``, ``community.docker``

Repository layout
-----------------

.. code-block:: text

   fit-ctf-virt/
   ├── tasks.py                 # Invoke entry point
   ├── env-example.yaml         # Configuration template
   ├── env-config.yaml          # Active config (gitignored — contains secrets)
   ├── scripts/init.sh          # One-time host bootstrap
   └── resources/
       ├── init.sh              # In-instance bootstrap (Ansible install)
       ├── ansible_extra_vals.yaml.j2
       ├── playground/ansible/  # FIT-CTF + node-exporter roles
       ├── database/ansible/    # MongoDB 7 role
       └── monitoring/ansible/  # Prometheus + Grafana via Docker

Installation workflow
---------------------

The deployment has two phases: create Incus objects on the host, then configure each
instance with Ansible.

Phase 1 — Host bootstrap
~~~~~~~~~~~~~~~~~~~~~~~~

On a fresh Rocky Linux 10 host, install Incus and clone fit-ctf-virt. The repository
ships ``scripts/init.sh`` as a reference bootstrap script; you can run it or perform
equivalent steps manually:

.. code-block:: sh

   # On the Incus host
   git clone https://github.com/hungdojan/fit-ctf-virt
   cd fit-ctf-virt
   cp env-example.yaml env-config.yaml   # edit secrets and sizing
   poetry install

``scripts/init.sh`` additionally installs Incus from the ``neelc/incus`` COPR,
configures firewall masquerade rules, runs ``incus admin init --minimal``, and calls
``inv setup``.

Phase 2 — Create Incus infrastructure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

   poetry run inv setup

This task is idempotent — existing storage pools, networks, profiles, and instances
are skipped. It creates:

1. Storage pool ``fit-ctf-pool`` (btrfs)
2. Bridge network ``fitctfbr0`` (``10.100.0.1/24``, NAT)
3. Profile ``fit-ctf-profile`` (NIC on bridge + root disk)
4. Three instances via ``incus init`` (playground as ``--vm``, database and
   monitoring as containers)

Instances are created but **not yet configured** after ``setup``.

Phase 3 — Initialize instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run in this order — the database must exist before the playground generates ``.env``:

.. code-block:: sh

   poetry run inv init_database
   poetry run inv init_monitoring    # optional
   poetry run inv init_playground

Each ``init_*`` task:

1. Starts the Incus instance if stopped
2. Waits until the configured static IP is assigned (up to 120 seconds)
3. Renders Ansible extra-vars from ``env-config.yaml`` into ``resources/<instance>/vals.yaml``
4. Pushes ``resources/<instance>/*`` to ``/tmp/setup/`` inside the instance
5. Runs ``resources/init.sh`` (installs Ansible and Galaxy collections)
6. Runs ``ansible-playbook`` with the rendered ``vals.yaml``
7. Removes ``/tmp/setup``

Verify instances:

.. code-block:: sh

   incus list

Configuration reference
-----------------------

Copy ``env-example.yaml`` to ``env-config.yaml`` and fill in credentials. The file
is gitignored.

Common infrastructure
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Purpose
   * - ``common.storage``
     - Btrfs pool name, driver, and size (default ``10GiB``)
   * - ``common.network``
     - Bridge name ``fitctfbr0``, IPv4 subnet ``10.100.0.1/24``, NAT enabled
   * - ``common.profile``
     - Default NIC and root-disk devices attached to every instance

Playground
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Purpose
   * - ``playground.config.limits.cpu``
     - vCPU limit for the VM
   * - ``playground.config.limits.memory``
     - RAM limit (e.g. ``4096MiB``)
   * - ``playground.config.devices.root.size``
     - Root disk size (default ``20GiB``)
   * - ``playground.envs.db_host``
     - MongoDB hostname — use ``fit-ctf-database`` (Incus DNS)
   * - ``playground.envs.db_name``
     - Application database name
   * - ``playground.envs.db_username`` / ``db_password``
     - MongoDB credentials for FIT-CTF

Database
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Purpose
   * - ``database.envs.mongo_admin_user`` / ``mongo_admin_pass``
     - MongoDB admin account
   * - ``database.envs.mongo_app_db``
     - Application database (must match ``playground.envs.db_name``)
   * - ``database.envs.mongo_app_user`` / ``mongo_app_pass``
     - Application user (must match playground ``db_username`` / ``db_password``)

Monitoring
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Purpose
   * - ``monitoring.envs.prometheus_port``
     - Prometheus listen port (default ``9090``)
   * - ``monitoring.envs.grafana_port``
     - Grafana listen port (default ``3000``)
   * - ``monitoring.envs.grafana_admin_user`` / ``grafana_admin_password``
     - Grafana admin credentials
   * - ``monitoring.envs.playground_ip``
     - IP scraped for node-exporter metrics (default ``10.100.0.2``)
   * - ``monitoring.envs.node_exporter_port``
     - node-exporter port on the playground (default ``9100``)

Invoke tasks
------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Task
     - Description
   * - ``inv setup``
     - Create Incus storage, network, profile, and all three instances
   * - ``inv init_database``
     - Install and configure MongoDB 7 on the database container
   * - ``inv init_monitoring``
     - Deploy Prometheus and Grafana via Docker Compose
   * - ``inv init_playground``
     - Install FIT-CTF, configure production paths, set up SSH/Rendezvous
   * - ``inv teardown``
     - Delete instances, profile, network, and storage (reverse order)

List all tasks:

.. code-block:: sh

   poetry run inv --list

What each instance receives
---------------------------

Playground VM
~~~~~~~~~~~~~

The Ansible ``fit-ctf`` role on the playground:

1. Resizes the VM root disk
2. Raises kernel keyring limits (needed for many Podman containers)
3. Installs ``openssh-server``, ``git``, ``pipx``, ``podman``, ``podman-compose``
4. Creates Linux user ``user`` (passwordless SSH login)
5. Clones FIT-CTF ``main`` → ``/opt/fit-ctf`` and runs ``poetry install``
6. Runs ``poetry run inv generate-env`` with database credentials from ``vals.yaml``
7. Sets production share directories under ``/opt/fit-ctf-data/``
8. Runs ``poetry run inv setup-sshd`` and installs ``99-ctf-rule.conf``
9. Deploys node-exporter as a rootless Podman Quadlet unit on port ``9100``

Production paths on the playground:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Path
     - Purpose
   * - ``/opt/fit-ctf``
     - Cloned FIT-CTF application
   * - ``/opt/fit-ctf/.env``
     - Generated by ``inv generate-env``
   * - ``/opt/fit-ctf-data/projects``
     - ``PROJECT_SHARE_DIR``
   * - ``/opt/fit-ctf-data/users``
     - ``USER_SHARE_DIR``
   * - ``/opt/fit-ctf-data/modules``
     - ``MODULE_SHARE_DIR``
   * - ``/opt/fit-ctf-data/scenarios``
     - ``SCENARIO_SHARE_DIR``

Database container
~~~~~~~~~~~~~~~~~~

Installs MongoDB 7 natively (not containerized):

- Adds the MongoDB 7.0 yum repository
- Binds ``mongod`` to ``0.0.0.0``
- Creates admin and application users from ``env-config.yaml``
- Enables authentication

Monitoring container
~~~~~~~~~~~~~~~~~~~~

- Installs Docker CE
- Renders Prometheus config scraping ``playground_ip:node_exporter_port``
- Runs Prometheus ``v3.5.1`` and Grafana ``12.3`` via Docker Compose
- Provisions a Grafana datasource and the ``fit-ctf_graphs.json`` dashboard
- Enables a systemd unit that starts the stack at boot

Participant access
------------------

After ``init_playground``, participants connect to Rendezvous over SSH:

.. code-block:: sh

   ssh -p 5555 user@<playground-public-ip>

The playground must be reachable on port ``5555`` from participant networks. Publish
the port from the Incus host (for example ``incus config device add`` or host
firewall/NAT rules) — fit-ctf-virt does not automate public port forwarding today.

Inside the TUI, participants sign in with their FIT-CTF username and password. See
:doc:`rendezvous` for the full SSH and TUI guide.

Operator workflow
-----------------

After infrastructure is ready, operators manage the event from the playground VM.
Use the :doc:`deployment` pre-event checklist — adapted for the production paths
above:

.. code-block:: sh

   # Shell into the playground
   incus exec fit-ctf-playground -- bash

   # Or SSH after port publishing is configured
   ssh -p 5555 user@<playground-ip>

   cd /opt/fit-ctf

   poetry run fit-ctf project create --project-name demo
   poetry run fit-ctf user-cluster compile
   poetry run fit-ctf user-cluster build
   poetry run fit-ctf project-cluster compile
   poetry run fit-ctf project-cluster start
   poetry run fit-ctf enrollment enroll -u alice --project-name demo

fit-ctf-virt does **not** author or compile scenarios — that remains operator work
using FIT-CTF commands and content under ``/opt/fit-ctf-data/``.

Monitoring access
-----------------

From the Incus host or a machine that can reach the private bridge:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Service
     - Default endpoint
   * - Prometheus
     - ``http://10.100.0.4:9090``
   * - Grafana
     - ``http://10.100.0.4:3000`` (credentials from ``env-config.yaml``)
   * - node-exporter
     - ``http://10.100.0.2:9100/metrics``

Teardown
--------

To destroy all Incus objects created by fit-ctf-virt:

.. code-block:: sh

   poetry run inv teardown

This stops running instances and deletes monitoring → database → playground, then
the profile, network, and storage pool.

Security notes
--------------

- ``env-config.yaml`` holds plaintext database and Grafana passwords — never commit
  it to version control.
- The playground SSH user ``user`` has its password removed with
  ``PermitEmptyPasswords yes`` — use only behind appropriate network controls.
- MongoDB on the database instance binds ``0.0.0.0``; it should be reachable only
  on the private Incus bridge.

Troubleshooting
---------------

**``init_*`` times out waiting for IP**

- Check ``incus list`` — the instance may still be booting or failed cloud-init.
- Verify the static IP in ``env-config.yaml`` matches the device configuration.

**Playground ``generate-env`` fails**

- Ensure ``init_database`` completed successfully and credentials in
  ``playground.envs`` match ``database.envs``.
- From the playground VM, test connectivity: ``nc -zv fit-ctf-database 27017``.

**Ansible Galaxy collection install fails inside an instance**

- ``resources/init.sh`` prefers IPv4 in ``/etc/gai.conf`` as a workaround for IPv6
  routing issues on Incus bridges.

**VM disk resize fails**

- The resize role uses ``resize2fs`` (ext4). Verify the root filesystem type on Rocky
  Linux 10 if resize errors occur.

**MongoDB version conflicts**

- The database role pins MongoDB 7.x and rejects MongoDB 8.x packages.

See also
--------

- :doc:`deployment` — deployment modes and pre-event checklist
- :doc:`rendezvous` — SSH gatekeeper setup and TUI usage
- :doc:`configuration` — FIT-CTF ``.env`` variables
- `fit-ctf-virt repository <https://github.com/hungdojan/fit-ctf-virt>`__
