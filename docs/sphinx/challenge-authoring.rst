Challenge authoring
===================

This section explains how to **create CTF challenges** in FIT-CTF: container images
(**modules**), Compose templates (**scenarios**), per-cluster configuration (secrets,
ports, volumes), and deployment to participants.

How the pieces fit together
---------------------------

.. code-block:: text

   Module (Containerfile)          Scenario (Jinja2 Compose template)
          │                                    │
          │  fit-ctf/module build              │  fit-ctf scenario create / edit
          ▼                                    ▼
   Image fit-ctf/{name}              scenario_compose.yaml.j2 + volumes/
          │                                    │
          └──────────── referenced ────────────┘
                              │
                              ▼
              Cluster config (secrets, env_map, port_map, volume_map)
                              │
                   fit-ctf user-cluster add-scenario
                              │
                              ▼
              compile → build → start (per user or project cluster)
                              │
                              ▼
              Participant solves challenge → submits secret in Rendezvous

Terminology
-----------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Term
     - Meaning
   * - **Module**
     - A reusable container image definition (``Containerfile`` + scripts) under
       ``{MODULE_SHARE_DIR}/{name}/``. Built as ``fit-ctf/{name}``.
   * - **Scenario**
     - A Jinja2 Compose template describing one or more services for a challenge.
       Lives under ``{SCENARIO_SHARE_DIR}/{name}/``.
   * - **Scenario config**
     - Per-cluster values: secrets, ``service_configs`` (env/ports/volumes). Stored in
       MongoDB on the project or user cluster — not in the scenario template directory.
   * - **Compile**
     - Render templates into a concrete ``scenario_compose.yaml`` on disk for one
       enrollment or project.
   * - **User cluster**
     - Per-participant challenge instances (typical for flags).
   * - **Project cluster**
     - Shared infrastructure (login node, admin services).

End-to-end workflow
-------------------

1. **Create a module** — :doc:`modules`
   ``fit-ctf module create my_challenge`` → edit ``Containerfile`` → ``fit-ctf module build my_challenge``

2. **Create a scenario** — :doc:`creating-scenarios`
   ``fit-ctf scenario create -n my_challenge`` → edit ``scenario_compose.yaml.j2`` and
   ``volumes/*.template``

3. **Discover required variables**
   ``fit-ctf scenario vars-template -n my_challenge``

4. **Attach to a cluster** (example: one enrolled user)

   .. code-block:: sh

      fit-ctf user-cluster add-scenario \
          -p demo -u alice -s my_challenge --interactive

   Or pass a YAML file with ``--file``. Use ``project-cluster`` for shared scenarios.

5. **Tune configuration** (optional)

   .. code-block:: sh

      fit-ctf user-cluster edit-service -p demo -u alice -s my_challenge --service web
      fit-ctf user-cluster add-secret -p demo -u alice -s my_challenge -k flag -v "FITCTF{...}"

6. **Deploy**

   .. code-block:: sh

      fit-ctf user-cluster compile -p demo -u alice
      fit-ctf user-cluster build -p demo -u alice
      fit-ctf user-cluster start -p demo -u alice

7. **Verify**

   .. code-block:: sh

      fit-ctf user-cluster status -p demo -u alice
      fit-ctf user-cluster logs -p demo -u alice

Bundled examples
----------------

FIT-CTF seeds templates on first run. Study these before writing your own:

**Modules** (``{MODULE_SHARE_DIR}/``):

- ``template`` — minimal UBI-based image
- ``ssh_debian`` / ``ssh_ubi`` — SSH login images for ``login_node``

**Scenarios** (``{SCENARIO_SHARE_DIR}/``):

- ``template`` — minimal single-service example
- ``login_node`` — participant SSH entry (uses ``ssh_debian`` or ``ssh_ubi``)
- ``admin_node`` — shared admin service (project cluster)

Paths default to ``~/.local/share/fit-ctf/module`` and ``.../scenario``.

Project-wide vs per-user challenges
------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Goal
     - Use
     - CLI group
   * - Same service for all users (login, scoreboard)
     - Project cluster
     - ``fit-ctf project-cluster``
   * - Isolated instance per participant (typical flag)
     - User cluster
     - ``fit-ctf user-cluster``

The compile/build/start commands are parallel; only the target cluster differs.

Compilation details
-------------------

For how Jinja2 variables, secrets, and volume templates are resolved at compile time,
see :doc:`scenarios`.

Further reading
---------------

- :doc:`modules` — authoring container images
- :doc:`creating-scenarios` — Compose templates, flags, and cluster configuration
- :doc:`concepts` — projects, enrollments, clusters
- :doc:`quickstart` — minimal operator setup before authoring
