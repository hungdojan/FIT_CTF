Scenarios
=========

.. note::

   For a step-by-step guide to **creating** challenges (templates, secrets, deployment),
   start with :doc:`challenge-authoring` and :doc:`creating-scenarios`. This page
   documents **compilation internals**.

Scenarios are the building blocks of challenge environments. Each scenario is a
**Jinja2 template** that compiles into a Docker Compose file with all paths, networks,
secrets, and per-service settings resolved.

Directory layout
----------------

Global template (before compilation):

.. code-block:: text

   {SCENARIO_SHARE_DIR}/login_node/
   ├── scenario_compose.yaml.j2    ← Jinja2 Compose template
   └── volumes/
       └── config.template         ← volume file templates (secrets injected here)

After compilation for a user cluster:

.. code-block:: text

   {PROJECT_SHARE_DIR}/demo/users/alice/login_node/
   ├── scenario_compose.yaml       ← rendered Compose file
   ├── scenario_compose.yaml.j2    ← copy of template
   └── volumes/
       └── config                  ← rendered volume files

Compilation pipeline
--------------------

Handled by ``ScenarioCompiler`` (``src/fit_ctf/models/infra/scenario_compile.py``):

1. **Copy template trees** — ``volumes/`` and ``modules/`` directories are copied to
   the destination.
2. **Build parameter map** — merges base paths, network names, config parameters,
   per-service environment/port/volume maps, and secret values.
3. **Render Compose** — Jinja2 renders ``scenario_compose.yaml.j2`` →
   ``scenario_compose.yaml``.
4. **Render volume templates** — ``.template`` files in ``volumes/`` are processed with
   secret injection.

Trigger compilation from the CLI:

.. code-block:: sh

   fit-ctf user-cluster compile -p demo -u alice
   fit-ctf project-cluster compile -p demo

Parameter map
-------------

The compiler builds a flat dictionary of Jinja2 variables:

Base parameters
~~~~~~~~~~~~~~~

- ``paths__projects``, ``paths__users``, ``paths__modules``, ``paths__scenarios``
- ``network_map__shared``, ``network_map__private``, ``network_map__operational``
- ``config_params`` — scenario-level custom parameters

Per-service parameters
~~~~~~~~~~~~~~~~~~~~~~

For each service ``S`` in the scenario config:

- ``S__env_map__{key}`` — environment variables
- ``S__port_map__{key}`` — port mappings
- ``S__volume_map__{vol}`` — volume source paths

Secrets
~~~~~~~

Secrets are **not** placed directly in the Compose template. Instead they are injected
into volume template files (``volumes/*.template``) as ``secret_map__{key}`` variables
during volume rendering.

Example scenario config (conceptual)
------------------------------------

.. code-block:: yaml

   secrets:
     flag_main: "FITCTF{example_flag}"
   service_configs:
     challenge:
       env_map:
         DEBUG: "0"
       port_map:
         web: "8080:8080"
       volume_map:
         data:
           src_path: "./volumes/data"
           template_params: {}

Bundled scenarios
-----------------

``template``
~~~~~~~~~~~~

Minimal example for learning the compilation pipeline.

``login_node``
~~~~~~~~~~~~~~

SSH entry point for participants. References ``ssh_debian`` or ``ssh_ubi`` modules.
Used as the default login node type during enrollment.

``admin_node``
~~~~~~~~~~~~~~

Shared administrative service, typically deployed in a **project cluster**.

See :doc:`creating-scenarios` for CLI commands to create and attach scenarios.

Modules
-------

Scenarios reference **modules** for container images. See :doc:`modules` for how to
create and build modules.

.. code-block:: sh

   fit-ctf module build ssh_debian
   fit-ctf user-cluster build -p demo -u alice

Module images are tagged ``fit-ctf/{module_name}``.

Authoring a new scenario
------------------------

See :doc:`creating-scenarios` for the full workflow. Summary:

1. ``fit-ctf scenario create -n my_challenge``
2. Edit ``scenario_compose.yaml.j2`` and ``volumes/*.template``
3. ``fit-ctf user-cluster add-scenario ...``
4. ``compile`` → ``build`` → ``start``

Compose runtime
---------------

Compiled ``scenario_compose.yaml`` files are managed by the container client
(``podman-compose`` or ``docker compose``). Cluster running state is detected via
``compose ps -q`` — see :doc:`container-client`.
