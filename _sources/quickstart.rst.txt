Quickstart
==========

TL;DR command cookbook for FIT-CTF. Each section below is **collapsible** — expand only
what you need. For explanations, see :doc:`installation`, :doc:`concepts`, and
:doc:`challenge-authoring`.

**Prerequisites:** :doc:`installation` completed (Poetry, ``.env``, Podman, MongoDB).

.. raw:: html

   <details class="quickstart-panel">
   <summary>Minimal local path (database → project → user → enroll → login node → Rendezvous)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run inv db-start

   poetry run fit-ctf project create -pn demo -mu 10
   poetry run fit-ctf user create -u alice --generate-password
   poetry run fit-ctf enrollment enroll -u alice --project-name demo --login-node-type ssh_ubi

   poetry run fit-ctf user-cluster compile -p demo -u alice
   poetry run fit-ctf user-cluster build -p demo -u alice

   poetry run fit-rendezvous

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Database (Podman Compose)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   # .env must include DB_* and DB_ADMIN_* (see configuration)
   poetry run inv generate-env --db-username=ctf_user --db-password=changeme --db-name=ctf_db

   poetry run inv db-start
   poetry run inv db-stop
   poetry run inv db-restart
   poetry run inv db-shell

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Project, user, enrollment</summary>
   <div class="quickstart-body">

**Project**

.. code-block:: sh

   poetry run fit-ctf project create -pn demo -mu 10 -p 10000

   poetry run fit-ctf project ls

**User**

.. code-block:: sh

   poetry run fit-ctf user create -u alice --generate-password
   poetry run fit-ctf user create -u alice --password 'KnownPass123!'
   poetry run fit-ctf user ls

**Enrollment**

.. code-block:: sh

   # Basic enroll
   poetry run fit-ctf enrollment enroll -u alice --project-name demo

   # Enroll and attach bundled login_node scenario (ssh_ubi or ssh_debian)
   poetry run fit-ctf enrollment enroll \
       -u alice --project-name demo --login-node-type ssh_ubi

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Modules (container images)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-ctf module create my_challenge
   cd "$(poetry run fit-ctf module get-path -mn my_challenge)"
   # edit Containerfile, then:
   poetry run fit-ctf module build my_challenge -v
   poetry run fit-ctf module ls
   poetry run fit-ctf module referenced -pn demo

See :doc:`modules`.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Scenarios (Compose templates)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-ctf scenario create -n web_challenge
   poetry run fit-ctf scenario edit -n web_challenge          # $EDITOR
   poetry run fit-ctf scenario vars-template -n web_challenge # required config slots
   poetry run fit-ctf scenario info -n web_challenge
   poetry run fit-ctf scenario ls

Bundled templates (seeded on first run): ``template``, ``login_node``, ``admin_node``.

See :doc:`creating-scenarios`.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Attach scenario, services, and secrets (user cluster)</summary>
   <div class="quickstart-body">

**Add scenario** (interactive YAML editor — pre-fills ``secrets`` and ``service_configs``):

.. code-block:: sh

   poetry run fit-ctf user-cluster add-scenario \
       -p demo -u alice -s web_challenge --interactive

**Or from a config file:**

.. code-block:: sh

   poetry run fit-ctf user-cluster add-scenario \
       -p demo -u alice -s web_challenge --file challenge_config.yaml

Example ``challenge_config.yaml``:

.. code-block:: yaml

   secrets:
     flag: "FITCTF{example}"
   service_configs:
     web:
       port_map:
         http: 18080
       volume_map:
         data:
           src_path: "{{ scenario_dir }}/volumes/flag.txt.template"
           template_params: {}

**Edit one service** (``env_map``, ``port_map``, ``volume_map``):

.. code-block:: sh

   poetry run fit-ctf user-cluster edit-service \
       -p demo -u alice -s web_challenge --service web

**Secrets**

.. code-block:: sh

   poetry run fit-ctf user-cluster add-secret \
       -p demo -u alice -s web_challenge -k flag -v "FITCTF{...}"
   poetry run fit-ctf user-cluster list-secrets -p demo -u alice -s web_challenge
   poetry run fit-ctf user-cluster update-secret \
       -p demo -u alice -s web_challenge -k flag -v "FITCTF{new}"
   poetry run fit-ctf user-cluster remove-secret \
       -p demo -u alice -s web_challenge -k flag -y

**Project cluster** (shared infra): same commands with ``fit-ctf project-cluster`` and ``-p demo`` only.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Compile, build, start (deploy challenge)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-ctf module build my_challenge    # if scenario uses a custom module

   poetry run fit-ctf user-cluster compile -p demo -u alice
   poetry run fit-ctf user-cluster build -p demo -u alice -v
   poetry run fit-ctf user-cluster start -p demo -u alice -v

   poetry run fit-ctf user-cluster status -p demo -u alice
   poetry run fit-ctf user-cluster health -p demo -u alice
   poetry run fit-ctf user-cluster logs -p demo -u alice
   poetry run fit-ctf user-cluster stop -p demo -u alice
   poetry run fit-ctf user-cluster restart -p demo -u alice -v

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Rendezvous TUI (local)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-rendezvous

Log in with FIT-CTF credentials (not the Linux user). In the TUI:

1. **Select Project** → choose enrolled project
2. **Project Info** → start/stop instance, read tasks, leaderboard
3. **Submit Secret** → submit flags

Optional: ``export FIT_RENDEZVOUS_LANG=cs`` before launch.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Rendezvous over SSH (participant access)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   sudo apt install -y openssh-server
   sudo adduser --disabled-password --gecos "" ctfparticipant

   poetry run inv setup-sshd \
       --user=ctfparticipant \
       --rdz-port=2222 \
       --fitctf-dirpath=/absolute/path/to/fit-ctf

   sudo cp 99-ctf-rule.conf /etc/ssh/sshd_config.d/
   sudo sshd -t && sudo systemctl reload sshd

   # participant:
   ssh -p 2222 ctfparticipant@<host>

SSH uses a Linux gatekeeper account; the TUI then asks for FIT-CTF username/password.

Full guide: :doc:`rendezvous`.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Bulk setup (YAML)</summary>
   <div class="quickstart-body">

Bootstrap projects, users, enrollments, and scenario configs in one step:

.. code-block:: sh

   poetry run fit-ctf data-mgmt setup -i connected_data.yaml
   poetry run fit-ctf data-mgmt setup -i connected_data.yaml --dry-run
   poetry run fit-ctf data-mgmt setup -i connected_data.yaml --exist-ok

Full guide: :doc:`setup-file` (schema, ``connected_data.yaml`` examples, post-setup
compile/build/start). ZIP migration: ``data-mgmt export`` / ``import``.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Import / export (migrate a project)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-ctf data-mgmt export -p demo -o demo_backup.zip
   poetry run fit-ctf data-mgmt import -i demo_backup.zip

Export includes database dump and filesystem trees from the share directory.

.. raw:: html

   </div></details>

.. raw:: html

   <details class="quickstart-panel">
   <summary>Operator commands (while event is running)</summary>
   <div class="quickstart-body">

.. code-block:: sh

   poetry run fit-ctf user-progress -u alice -p demo info
   poetry run fit-ctf user-progress -u alice -p demo list-secrets
   poetry run fit-ctf project enrolled-users -pn demo
   poetry run fit-ctf project leaderboard -pn demo

   poetry run fit-ctf user-cluster status -p demo -u alice
   poetry run fit-ctf project-cluster -pn demo status

.. raw:: html

   </div></details>

Next steps
----------

- :doc:`concepts` — projects, clusters, enrollments
- :doc:`challenge-authoring` — end-to-end challenge workflow
- :doc:`setup-file` — bulk YAML setup (`connected_data.yaml`) and ZIP import/export
- :doc:`deployment` — production (fit-ctf-virt, SSH)
- :doc:`click-commands` — full CLI reference
