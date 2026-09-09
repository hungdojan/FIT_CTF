Architecture
============

High-level overview
-------------------

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                        Operator host                        │
   │                                                             │
   │  ┌──────────────┐     ┌───────────────┐     ┌─────────────┐ │
   │  │  fit-ctf     │     │ fit-rendezvous│     │  MongoDB    │ │
   │  │  (CLI)       │     │ (Textual TUI) │     │  (database) │ │
   │  └──────┬───────┘     └──────┬────────┘     └──────▲──────┘ │
   │         │                    │                     │        │
   │         └────────┬───────────┘                     │        │
   │                  │                                 │        │
   │         ┌────────▼────────┐                        │        │
   │         │    fit_ctf      │◄───────────────────────┘        │
   │         │  (core library) │                                 │
   │         └────────┬────────┘                                 │
   │                  │                                          │
   │         ┌────────▼─────────┐     ┌───────────────────────┐  │
   │         │ Container client │────►│ Podman (+ Docker exp.)│  │
   │         │ (compose API)    │     │ + compose             │  │
   │         └──────────────────┘     └──────────┬────────────┘  │
   │                                             │               │
   │                              ┌──────────────▼────────────┐  │
   │                              │  Challenge containers     │  │
   │                              │  (project + user clusters)│  │
   │                              └───────────────────────────┘  │
   │                                                             │
   │  ~/.local/share/fit-ctf/  ← projects, users, modules,       │
   │                              scenarios, compiled compose    │
   └─────────────────────────────────────────────────────────────┘

Services
--------

MongoDB
~~~~~~~

Stores all persistent metadata:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Collection
     - Contents
   * - ``project``
     - Competition definitions (name, capacity, port range)
   * - ``user``
     - Accounts (username, hashed password, role, email)
   * - ``enrollment``
     - User ↔ project links, container ports, progress
   * - ``project_cluster``
     - Shared cluster state and scenario configs per project
   * - ``user_cluster``
     - Per-enrollment cluster state and scenario configs

Local development uses ``podman compose`` via ``poetry run inv db-start``
(``db/compose.yaml``). Production can use a Podman Quadlet unit via
``poetry run inv db-deploy``.

Container engine
~~~~~~~~~~~~~~~~

Selected by ``CONTAINER_CLIENT``:

- **podman** — uses ``podman`` and ``podman-compose`` (recommended; primary backend).
- **docker** — uses ``docker`` and ``docker compose`` (**experimental** — less tested than
  Podman; set ``CONTAINER_CLIENT=docker`` in ``.env``).
- **mock** — no real containers; for automated tests.

The container client wraps compose lifecycle operations: ``up``, ``down``, ``build``,
``ps``, ``logs``, and image/network management. See :doc:`container-client`.

Share directory
~~~~~~~~~~~~~~~

Default root: ``$HOME/.local/share/fit-ctf/``

Four top-level directories (overridable via environment variables):

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Directory
     - Purpose
   * - ``project/``
     - Per-project trees (users, logs, compiled scenarios)
   * - ``user/``
     - Global user data (shadow file, SSH keys, Rendezvous settings)
   * - ``module/``
     - Reusable container image definitions (Containerfiles)
   * - ``scenario/``
     - Global scenario templates (Jinja2 Compose + volumes)

On first run, ``CTFApp.init_tool`` copies bundled templates from
``src/fit_ctf/templates/v1/`` into the share directories.

Core managers
-------------

The ``CTFBase`` class wires together managers used by both CLI and Rendezvous:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Manager
     - Responsibility
   * - ``ProjectManager``
     - CRUD for projects, filesystem init
   * - ``UserManager``
     - CRUD for users, password hashing, SSH key storage
   * - ``EnrollmentManager``
     - Enroll users into projects, track progress and secrets
   * - ``ScenarioManager``
     - Global scenario templates on disk
   * - ``ModuleManager``
     - Global module images, build via container client
   * - ``ProjectClusterManager``
     - Shared per-project container clusters
   * - ``UserClusterManager``
     - Per-enrollment container clusters

Cluster networking
------------------

FIT-CTF uses two layers of networking: **platform networks** (shared across a project or
enrollment) and **scenario-local networks** (defined by the operator inside a scenario
Compose template).

Platform networks (external)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Created when a project is initialized and referenced as ``external: true`` in compiled
Compose files. Names are injected at compile time via ``network_map__*`` variables.

Each project gets:

- ``{project}_shared_net`` — reachable by all enrolled users (e.g. login node, shared
  services)
- ``{project}_operational_net`` — operator/admin traffic (e.g. ``admin_node``)

Each enrolled user additionally gets:

- ``{project}_{username}_private_net`` — isolated network for that participant's
  challenge instances

Typical attachment:

- **Login node** — ``shared`` + ``private`` so participants can SSH in and reach services
  on their private net.
- **User challenge** — often ``private`` (and sometimes ``shared``) for participant-
  facing services.
- **Project cluster admin service** — ``operational`` (and ``shared`` where needed).

Scenario-local networks (internal)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to the platform networks, operators can define **extra networks inside
``scenario_compose.yaml.j2``** that exist only for that scenario's Compose stack. These
are **not** part of ``network_map__*``; Podman Compose creates them when the scenario
starts and removes them when it stops.

Use scenario-local networks to **hide backend services** from participant-reachable
networks. A common pattern is a web challenge with a database:

- ``web`` joins the participant network (``network_map__private``) **and** an internal
  ``backend`` network.
- ``db`` joins **only** ``backend``.

Participants can reach the web service (published port or via login node), but the
database is not attached to ``shared`` or ``private``, so it is not exposed on those
platform networks.

Example excerpt for a ``sql_injection`` scenario:

.. code-block:: yaml

   services:
     web:
       image: fit-ctf/web_challenge:latest
       networks:
         - participant
         - backend
       ports:
         - "{{ web__port_map__http }}:80"

     db:
       image: fit-ctf/mariadb:latest
       networks:
         - backend          # not on participant — hidden from shared/private

   networks:
     participant:
       external: true
       name: {{ network_map__private }}
     backend:
       driver: bridge       # scenario-only; created per compile/start

.. code-block:: text

   {project}_{user}_private_net          backend (scenario-local)
          │                                      │
          │    ┌─────────┐      SQL (internal)   │    ┌─────────┐
          └───►│   web   │◄──────────────────────┼───►│   db    │
               └─────────┘                       │    └─────────┘
            participant port                     └── db not on private_net

Guidelines:

- Declare platform nets as ``external: true`` with ``name: {{ network_map__... }}``.
- Use a non-external ``driver: bridge`` (or default) network for scenario-only traffic.
- Only attach sensitive services (databases, flag stores, admin APIs) to the internal
  network.
- Publish **only** the services participants should reach (``ports:`` on ``web``, not on
  ``db``).

Scenario-local networks are scoped to **one scenario's** ``scenario_compose.yaml``. They
do not connect two different scenarios unless both services are in the same Compose file.

Network names are injected into scenario templates at compile time via
``network_map__*`` variables for the platform layer. See :doc:`creating-scenarios` for
how to author multi-service templates.

Port allocation
---------------

Projects define ``starting_port_bind`` and ``max_nof_users``. Each enrollment receives
a ``container_port`` and ``forwarded_port`` from this range, used for SSH access to
participant instances. The default starting port constant is ``10000``.

Rendezvous over SSH
-------------------

In production, participants SSH to a dedicated port. An sshd ``Match`` rule
(``config/setup/99-ctf-rule.conf``) forces the command to launch ``fit-rendezvous``:

.. code-block:: text

   Match LocalPort <rdz_port>
       AllowUsers <user>
       ForceCommand cd <fitctf_dirpath> && poetry run fit-rendezvous

Generate this file with ``poetry run inv setup-sshd``.
