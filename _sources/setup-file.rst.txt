Bulk setup file
===============

A **setup file** is a YAML document that creates projects, users, enrollments, and
scenario configurations in one step. Use it to bootstrap a classroom or competition
instead of running dozens of CLI commands.

Apply a setup file with:

.. code-block:: sh

   poetry run fit-ctf data-mgmt setup -i my_setup.yaml

This is **not** the same as ``data-mgmt import`` (which restores a **ZIP** archive from
``data-mgmt export``). See :ref:`setup-vs-import` below.

Schema
------

The file is validated against ``src/fit_ctf/components/schemas/v1/setup.yaml``. Top-level
keys (all optional, but typically you use all three):

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Key
     - Purpose
   * - ``users``
     - FIT-CTF accounts to create
   * - ``projects``
     - Competitions / projects and **project-cluster** scenario configs
   * - ``enrollments``
     - Link users to projects, restore progress, and set **user-cluster** scenario configs

Processing order
~~~~~~~~~~~~~~~~

FIT-CTF applies sections in this order:

1. **projects** — creates each project and attaches scenarios to the **project cluster**
2. **users** — creates accounts (prints generated passwords when requested)
3. **enrollments** — enrolls users, restores ``progress``, attaches scenarios to each
   **user cluster**

Users and projects referenced in ``enrollments`` must be defined in the same file (or
already exist in the database when using ``--exist-ok``).

Prerequisites
-------------

- MongoDB running and ``.env`` configured (:doc:`installation`)
- Global **scenario templates** must exist for every scenario name you reference
  (bundled: ``template``, ``login_node``, ``admin_node``; or create your own with
  ``fit-ctf scenario create``)
- Custom **modules** built if scenarios reference them (``fit-ctf module build``)

After ``data-mgmt setup``, you still need **compile / build / start** on clusters unless
you only needed database metadata.

Minimal example
---------------

.. code-block:: yaml

   users:
     - username: alice
       password: AlicePass123!

   projects:
     - name: demo
       max_nof_users: 10
       cluster.scenario_configs: {}

   enrollments:
     - user: alice
       project: demo
       progress:
         solved_secrets: {}
         submission_log: []
         found_secrets: 0
         last_submit_time: null
       cluster.scenario_configs:
         login_node:
           secrets: {}
           service_configs:
             login_node:
               volume_map:
                 home:
                   src_path: "{{ paths__users }}/{{ username }}/home/"
                   template_params: {}
                 shadow:
                   src_path: "{{ paths__users }}/{{ username }}/shadow"
                   template_params: {}

Save as ``my_setup.yaml``, then:

.. code-block:: sh

   poetry run fit-ctf data-mgmt setup -i my_setup.yaml
   poetry run fit-ctf user-cluster compile -p demo -u alice
   poetry run fit-ctf user-cluster build -p demo -u alice
   poetry run fit-ctf user-cluster start -p demo -u alice

Users section
-------------

Each entry requires ``username`` and either ``password`` or ``generate_password: true``.

.. code-block:: yaml

   users:
     - username: user1
       password: user1Password
     - username: user2
       generate_password: true    # printed after setup
     - username: admin1
       password: AdminPass123!
       role: admin
       email: admin@example.com

Projects section
----------------

Each project requires ``name``, ``max_nof_users``, and ``cluster.scenario_configs``.

``cluster.scenario_configs`` is a map of scenario name → config for the **shared project
cluster** (e.g. ``admin_node``).

.. code-block:: yaml

   projects:
     - name: prj1
       max_nof_users: 30
       starting_port_bind: 10000
       description: "Spring 2026 CTF"
       cluster.scenario_configs:
         admin_node:
           secrets: {}
           service_configs:
             admin_node:
               port_map:
                 http: 8080

Use ``cluster.scenario_configs: {}`` when the project has no shared scenarios yet.

Enrollments section
-------------------

Each enrollment requires ``user``, ``project``, ``progress``, and
``cluster.scenario_configs``.

``cluster.scenario_configs`` configures the **per-user cluster** for that enrollment
(login node, challenges, flags).

Progress
~~~~~~~~

Required shape (use empty values for a fresh event):

.. code-block:: yaml

   progress:
     solved_secrets: {}
     submission_log: []
     found_secrets: 0
     last_submit_time: null

To restore solved flags from a backup, populate ``solved_secrets`` and ``submission_log``
(see ``tests/fixtures/connected_data.yaml`` for an example with a solved secret).

Login node
~~~~~~~~~~

If ``login_node`` appears under ``cluster.scenario_configs``, FIT-CTF enrolls the user
**and** attaches the bundled login scenario. Default module: ``ssh_ubi``. Override via
``config_params``:

.. code-block:: yaml

   cluster.scenario_configs:
     login_node:
       config_params:
         login_node_module: ssh_debian
       secrets: {}
       service_configs:
         login_node:
           volume_map:
             home:
               src_path: "{{ paths__users }}/{{ username }}/home/"
               template_params: {}
             shadow:
               src_path: "{{ paths__users }}/{{ username }}/shadow"
               template_params: {}

Challenge scenarios
~~~~~~~~~~~~~~~~~~~

Add more scenarios under the same ``cluster.scenario_configs`` map. Each needs
``service_configs`` (and ``secrets`` for flags).

Discover required slots for a scenario:

.. code-block:: sh

   poetry run fit-ctf scenario vars-template -n buffer-overflow

Example with flags (from ``connected_data.yaml`` in the repository):

.. code-block:: yaml

   cluster.scenario_configs:
     login_node:
       secrets: {}
       service_configs:
         login_node:
           volume_map:
             home:
               src_path: "{{ paths__users }}/{{ username }}/home/"
               template_params: {}
             shadow:
               src_path: "{{ paths__users }}/{{ username }}/shadow"
               template_params: {}
     buffer-overflow:
       secrets:
         flag: "FLAG_lfHMTJjbwen5veCt"
       service_configs:
         node:
           volume_map:
             flagfile:
               src_path: "{{ scenario_dir }}/volumes/flag.txt.template"
               template_params: {}

Jinja variables in ``src_path``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Common placeholders (resolved at **compile** time):

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Meaning
   * - ``{{ paths__users }}``
     - Global user share directory
   * - ``{{ username }}``
     - Enrolled user's name
   * - ``{{ scenario_dir }}``
     - Global scenario template directory for this scenario name
   * - ``{{ paths__projects }}``
     - Global project share directory

Secret names must **not** contain ``__``. Values are injected into ``volumes/*.template``
as ``secret_map__<name>`` at compile time.

Full repository examples
------------------------

- ``connected_data.yaml`` — multi-user project with several challenges per enrollment
- ``tests/fixtures/connected_data.yaml`` — test fixture with project-cluster ``template``
  scenario and progress restoration example

Apply either after scenarios exist globally:

.. code-block:: sh

   poetry run fit-ctf data-mgmt setup -i connected_data.yaml

Apply the setup file
--------------------

.. code-block:: sh

   # validate + apply
   poetry run fit-ctf data-mgmt setup -i my_setup.yaml

   # show what would be created (no changes)
   poetry run fit-ctf data-mgmt setup -i my_setup.yaml --dry-run

   # skip errors when project/user already exists
   poetry run fit-ctf data-mgmt setup -i my_setup.yaml --exist-ok

When ``generate_password: true`` users are created, the command prints a table of
usernames and passwords.

Post-setup deployment
~~~~~~~~~~~~~~~~~~~~~

``data-mgmt setup`` writes to MongoDB and configures cluster metadata. It does **not**
compile Compose files or start containers:

.. code-block:: sh

   poetry run fit-ctf user-cluster compile -p demo -u alice
   poetry run fit-ctf user-cluster build -p demo -u alice
   poetry run fit-ctf user-cluster start -p demo -u alice

   poetry run fit-ctf project-cluster -pn demo compile
   poetry run fit-ctf project-cluster -pn demo build
   poetry run fit-ctf project-cluster -pn demo start

.. _setup-vs-import:

Setup file vs ZIP import
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Mechanism
     - Input
     - Command
   * - **Setup file**
     - YAML (``setup.yaml`` schema)
     - ``fit-ctf data-mgmt setup -i file.yaml``
   * - **ZIP import**
     - Archive from ``data-mgmt export``
     - ``fit-ctf data-mgmt import -i backup.zip``

Use a **setup file** to declaratively create a new environment from scratch (or extend
with ``--exist-ok``).

Use **ZIP import** to clone an existing project's database records and filesystem trees
from another host.

Export for migration:

.. code-block:: sh

   poetry run fit-ctf data-mgmt export -p demo -o demo_backup.zip
   poetry run fit-ctf data-mgmt import -i demo_backup.zip

Troubleshooting
---------------

**Validation error on load**

- Compare your file to ``setup.yaml`` schema; common mistakes: missing ``progress`` on
  enrollments, missing ``service_configs`` under a scenario, invalid ``role`` value.

**Enrollment skipped**

- User or project name typo; scenario template does not exist under ``scenario/``; invalid
  scenario config vs template (run ``scenario vars-template``).

**Scenario config does not satisfy templates**

- A ``service_configs`` or ``secrets`` key does not match what
  ``scenario_compose.yaml.j2`` expects. Use ``fit-ctf scenario vars-template -n <name>``.

**Project already exists**

- Use ``--exist-ok`` or pick a new project name.

See also
--------

- :doc:`quickstart` — collapsible command reference (bulk setup panel)
- :doc:`creating-scenarios` — authoring scenarios referenced in setup files
- :doc:`configuration` — environment variables and paths
