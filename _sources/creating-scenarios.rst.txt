Creating scenarios
==================

A **scenario** is a CTF challenge template: a Jinja2 Compose file plus optional volume
templates. Scenarios are **global** (shared across projects). Per-user or per-project
**values** (secrets, ports, paths) are stored on the cluster when you attach a scenario.

Directory layout
----------------

After ``fit-ctf scenario create -n my_challenge``:

.. code-block:: text

   scenario/my_challenge/
   ├── scenario_compose.yaml.j2   ← main Compose template
   └── volumes/
       └── file_example.template    ← seeded example (secrets / config injection)

Volume files ending in ``.template`` are rendered at compile time. Static files without
``.template`` are copied as-is.

Create a scenario
-----------------

.. code-block:: sh

   fit-ctf scenario create -n buffer_overflow

The command renders a scaffold from ``scenario_base_compose.yaml.j2`` and copies the
example ``volumes/`` tree.

List and inspect
----------------

.. code-block:: sh

   fit-ctf scenario ls
   fit-ctf scenario info -n buffer_overflow
   fit-ctf scenario view -n buffer_overflow

Edit the Compose template
-------------------------

Requires ``$EDITOR`` to be set.

.. code-block:: sh

   fit-ctf scenario edit -n buffer_overflow

Saving the template **automatically recompiles** user clusters that use this scenario
(unless you pass ``--skip-recompile``).

Compose template basics
~~~~~~~~~~~~~~~~~~~~~~~

New scenarios start from a scaffold that demonstrates the variable naming convention.
A minimal service referencing your module:

.. code-block:: yaml

   ---
   name: "{{ project_name }}_{{ username }}_buffer_overflow"

   services:
     challenge:
       build:
         context: {{ paths__modules }}/my_challenge
         dockerfile: Containerfile
       image: fit-ctf/my_challenge:latest
       restart: unless-stopped
       networks:
         {{ network_map__private }}:
       ports:
         - "{{ challenge__port_map__web }}:8080"
       volumes:
         - "{{ challenge__volume_map__data }}:/challenge/data:ro"

   networks:
     {{ network_map__private }}:
       external: true
     {{ network_map__shared }}:
       external: true

Variable naming rules
~~~~~~~~~~~~~~~~~~~~~

FIT-CTF derives configuration slots from Jinja placeholders in the template:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Placeholder in template
     - Filled from scenario config
   * - ``{{ service__env_map__KEY }}``
     - ``service_configs.service.env_map.KEY``
   * - ``{{ service__port_map__name }}``
     - ``service_configs.service.port_map.name`` (host port, integer)
   * - ``{{ service__volume_map__vol }}``
     - ``service_configs.service.volume_map.vol.src_path`` (and ``template_params``)
   * - ``{{ paths__modules }}``, ``{{ paths__users }}``, …
     - Injected automatically at compile time
   * - ``{{ network_map__shared }}``, ``{{ network_map__private }}``
     - Project/user network names (automatic)

Discover required slots
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

   fit-ctf scenario vars-template -n buffer_overflow

Example output shape:

.. code-block:: yaml

   secrets: {}
   service_configs:
     challenge:
       port_map:
         web: 0
       env_map: {}
       volume_map:
         data:
           src_path: ""
           template_params: {}

Flags and secrets
-----------------

Secrets are **not** hard-coded in ``scenario_compose.yaml.j2``. Define flag slots in
volume templates and set values on the cluster.

Volume template example
~~~~~~~~~~~~~~~~~~~~~~~

File: ``volumes/flag.txt.template``

.. code-block:: text

   {{ secret_map__flag }}

The name ``flag`` becomes a required secret key. At compile time the platform injects
the value from the cluster's ``secrets.flag`` field.

You can also reference ``secret_map__<name>`` in ``scenario_compose.yaml.j2`` if needed.
Secret names **must not contain** ``__``.

Set secrets on a cluster
~~~~~~~~~~~~~~~~~~~~~~~~

After adding the scenario to a user cluster:

.. code-block:: sh

   fit-ctf user-cluster add-secret \
       -p demo -u alice -s buffer_overflow -k flag -v "FITCTF{example}"

   fit-ctf user-cluster update-secret -p demo -u alice -s buffer_overflow -k flag -v "NEW"
   fit-ctf user-cluster list-secrets -p demo -u alice -s buffer_overflow
   fit-ctf user-cluster remove-secret -p demo -u alice -s buffer_overflow -k flag -y

Participants submit matching values through Rendezvous (**Submit Secret**).

Attach a scenario to a cluster
------------------------------

User cluster (per participant)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Interactive editor (opens ``$EDITOR`` with a pre-filled YAML document):

.. code-block:: sh

   fit-ctf user-cluster add-scenario \
       -p demo -u alice -s buffer_overflow --interactive

From a configuration file:

.. code-block:: sh

   fit-ctf user-cluster add-scenario \
       -p demo -u alice -s buffer_overflow --file challenge_config.yaml

Example ``challenge_config.yaml``:

.. code-block:: yaml

   secrets:
     flag: "FITCTF{buffer_overflow_flag}"
   service_configs:
     challenge:
       port_map:
         web: 18080
       volume_map:
         data:
           src_path: "{{ scenario_dir }}/volumes/flag.txt.template"
           template_params: {}

``src_path`` supports Jinja with ``scenario_dir``, ``paths__*``, and ``username``.

Project cluster (shared)
~~~~~~~~~~~~~~~~~~~~~~~~

Same pattern with ``fit-ctf project-cluster``:

.. code-block:: sh

   fit-ctf project-cluster add-scenario -p demo -s admin_node --interactive

Fine-tune service configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

   fit-ctf user-cluster edit-service \
       -p demo -u alice -s buffer_overflow --service challenge

Opens ``env_map``, ``port_map``, and ``volume_map`` in ``$EDITOR``.

Deploy the challenge
--------------------

After the scenario is attached and configured:

.. code-block:: sh

   # 1. Build module images (if not already built)
   fit-ctf module build my_challenge

   # 2. Render templates to scenario_compose.yaml on disk
   fit-ctf user-cluster compile -p demo -u alice

   # 3. Build compose services
   fit-ctf user-cluster build -p demo -u alice

   # 4. Start containers
   fit-ctf user-cluster start -p demo -u alice

Check runtime state:

.. code-block:: sh

   fit-ctf user-cluster status -p demo -u alice
   fit-ctf user-cluster health -p demo -u alice
   fit-ctf user-cluster logs -p demo -u alice

Stop or restart:

.. code-block:: sh

   fit-ctf user-cluster stop -p demo -u alice
   fit-ctf user-cluster restart -p demo -u alice

Compiled output location
------------------------

For user ``alice`` in project ``demo``:

.. code-block:: text

   ~/.local/share/fit-ctf/project/demo/users/alice/buffer_overflow/
   ├── scenario_compose.yaml        ← rendered, ready for podman-compose
   ├── scenario_compose.yaml.j2
   └── volumes/
       └── flag.txt                 ← rendered from .template (flag injected)

See :doc:`scenarios` for the full compilation pipeline.

Maintain scenarios
------------------

.. code-block:: sh

   fit-ctf scenario usage -n buffer_overflow
   fit-ctf scenario delete -n buffer_overflow    # prompts for confirmation

Deleting a scenario fails if clusters still depend on it.

Multi-challenge projects
------------------------

A single enrollment can run **multiple scenarios** (login node + several challenges):

.. code-block:: sh

   fit-ctf user-cluster add-scenario -p demo -u alice -s login_node --file login.yaml
   fit-ctf user-cluster add-scenario -p demo -u alice -s buffer_overflow --interactive
   fit-ctf user-cluster add-scenario -p demo -u alice -s sql_injection --interactive

Compile/build/start operate on the **whole cluster** (all attached scenarios).

Example from bulk setup
-----------------------

The repository includes ``connected_data.yaml`` with enrollments that attach several
scenarios and pre-set secrets — useful as a reference when writing your own configs:

.. code-block:: sh

   fit-ctf data-mgmt setup -i connected_data.yaml

See :doc:`configuration` for the ``setup.yaml`` schema.
