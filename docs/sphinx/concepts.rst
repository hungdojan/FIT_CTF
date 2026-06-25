Core concepts
=============

This page defines the domain objects FIT-CTF manages and how they relate.

Project
-------

A **project** is a CTF competition or classroom assignment. It defines:

- A unique name (lowercase letters, digits, underscores)
- Maximum number of participants (``max_nof_users``)
- A port range for participant SSH access (``starting_port_bind``)

Creating a project also:

- Initializes a directory under ``{PROJECT_SHARE_DIR}/{name}/``
- Creates a **project cluster** record in MongoDB for shared infrastructure

.. code-block:: text

   {PROJECT_SHARE_DIR}/demo_project/
   ├── users/          ← per-enrolled-user directories
   ├── logs/
   └── scenarios/      ← compiled project-cluster scenarios

User
----

A **user** is a participant or administrator account:

- ``username``, hashed ``password``, ``role`` (``user`` or ``admin``), optional ``email``
- Filesystem tree under ``{USER_SHARE_DIR}/{username}/``:

  .. code-block:: text

     user/alice/
     ├── shadow              ← generated credentials for container login
     ├── home/.ssh/          ← uploaded public keys
     └── rendezvous_settings.json

Enrollment
----------

An **enrollment** links a user to a project. It tracks:

- Assigned ``container_port`` and ``forwarded_port`` from the project's port range
- **User progress**: solved secrets, submission log, timestamps

A user must be enrolled before they can select the project in Rendezvous or receive a
user cluster instance.

Module
------

A **module** is a reusable container image definition stored under
``{MODULE_SHARE_DIR}/{module_name}/``. Each module contains a ``Containerfile`` (and
supporting scripts).

Bundled modules:

- ``template`` — minimal example
- ``ssh_debian`` — Debian-based SSH login image
- ``ssh_ubi`` — UBI-based SSH login image

Modules are built and tagged as ``fit-ctf/{module_name}``. Scenarios reference modules
by name in their Compose templates.

Scenario
--------

A **scenario** is a Jinja2 Compose template that describes one or more services
(challenge containers). Global templates live under ``{SCENARIO_SHARE_DIR}/{name}/``:

.. code-block:: text

   scenario/login_node/
   ├── scenario_compose.yaml.j2
   └── volumes/
       └── config.template

Bundled scenarios:

- ``template`` — minimal example
- ``login_node`` — SSH entry point for participants
- ``admin_node`` — administrative shared service

Scenarios are **compiled** into concrete ``scenario_compose.yaml`` files with all
variables resolved. See :doc:`scenarios`.

Project cluster vs user cluster
-------------------------------

FIT-CTF runs containers in two scopes:

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * -
     - Project cluster
     - User cluster
   * - **Scope**
     - One per project; shared by all enrolled users
     - One per enrollment; private to each participant
   * - **Typical use**
     - Login node, scoreboard proxy, shared services
     - Individual challenge instance
   * - **Compile destination**
     - ``{project}/scenarios/{scenario}/``
     - ``{project}/users/{user}/{scenario}/``
   * - **Networks**
     - ``{project}_shared_net``, ``{project}_operational_net``
     - Above + ``{project}_{user}_private_net``
   * - **Default cluster name**
     - Project name
     - ``{project}_{username}``
   * - **CLI group**
     - ``fit-ctf project-cluster``
     - ``fit-ctf user-cluster``

Cluster lifecycle
~~~~~~~~~~~~~~~~~

Both cluster types follow the same operational stages:

1. **Add scenario** — attach a scenario template to the cluster
2. **Configure** — set secrets, environment variables, ports, volumes per service
3. **Compile** — render Jinja2 templates into Compose files
4. **Build** — build container images referenced by the Compose file
5. **Start / stop / restart** — manage running containers
6. **Status / health / logs** — inspect running state

Secrets and progress
--------------------

**Secrets** (flags) are defined in scenario configuration. When a participant submits a
secret through Rendezvous or the CLI, ``EnrollmentManager`` checks it against the
configured values for both user and project clusters.

**User progress** records:

- ``solved_secrets`` — correctly submitted flags
- ``submission_log`` — history of attempts
- ``found_secrets`` — discovered but not yet submitted
- ``last_submit_time`` — rate limiting / auditing

View progress via ``fit-ctf user-progress`` or the Rendezvous leaderboard.

Object relationships
--------------------

.. code-block:: text

   Project ─────┬──── Enrollment ──── User
                │           │
                │           └── UserCluster (per enrollment)
                │
                └── ProjectCluster (per project)

   Scenario (template) ──referenced by──► ProjectCluster / UserCluster
   Module (image)      ──referenced by──► Scenario services
