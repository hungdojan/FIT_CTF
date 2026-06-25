Rendezvous (SSH and TUI)
=========================

**Rendezvous** (``fit-rendezvous``) is the participant-facing Textual TUI. Participants
use it to log in, select a project, start or stop their personal cluster instance,
submit secrets, and view the leaderboard.

There are two ways to run it:

1. **Local** — operator or developer runs ``poetry run fit-rendezvous`` directly (no SSH).
2. **Over SSH** — participants connect to a dedicated SSH port; sshd launches the TUI
   automatically (typical for classroom / competition setups).

How login works
---------------

Rendezvous uses **two separate authentication steps** when accessed over SSH:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Step
     - What happens
   * - 1. SSH
     - Participant connects as a **Linux account** on the Rendezvous port. sshd runs
       ``fit-rendezvous`` via ``ForceCommand`` (see below).
   * - 2. TUI login
     - Inside the TUI, the participant signs in with their **FIT-CTF username and
       password** (created with ``fit-ctf user create``). Credentials are checked
       against MongoDB via ``LocalAuth``.

The Linux SSH account is only a gate into the TUI; challenge access and progress tracking
use FIT-CTF user accounts.

Prerequisites
-------------

Before setting up Rendezvous (local or SSH):

- FIT-CTF installed (:doc:`installation`) with a working ``.env``
- MongoDB running (``poetry run inv db-start`` or production equivalent)
- At least one project, user, and enrollment (:doc:`quickstart`)
- For SSH: ``openssh-server`` on the host

.. code-block:: sh

   sudo apt install -y openssh-server

Local setup (no SSH)
--------------------

Use this for development or when the operator runs the TUI on the same machine as the
backend.

From the repository root (where ``.env`` lives):

.. code-block:: sh

   poetry run fit-rendezvous

The TUI loads ``.env``, connects to MongoDB, and opens the login screen. Press
``Ctrl+C`` to exit.

Optional: set the UI language before login:

.. code-block:: sh

   export FIT_RENDEZVOUS_LANG=cs   # Czech; default is ``en``
   poetry run fit-rendezvous

After login, locale and dark-theme preferences are saved per user in:

.. code-block:: text

   ~/.local/share/fit-ctf/user/<username>/rendezvous_settings.json

SSH setup
---------

Participants connect with SSH; sshd starts Rendezvous for them. FIT-CTF ships an Invoke
task that renders an sshd ``Match`` rule from ``config/setup/99-ctf-rule.conf``.

Step 1 — Create a Linux gatekeeper account
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a dedicated OS user that participants use for SSH (example name
``ctfparticipant``):

.. code-block:: sh

   sudo adduser --disabled-password --gecos "" ctfparticipant

The generated sshd rule sets ``PermitEmptyPasswords yes`` for the Rendezvous port, so
participants can SSH without a Linux password. If you prefer password-based SSH for this
account, set a password with ``sudo passwd ctfparticipant`` and adjust the sshd rule
accordingly.

Ensure this user can read the FIT-CTF repository and run Poetry (or run the TUI as a user
that owns the install — often the same account that deployed FIT-CTF).

Step 2 — Generate the sshd snippet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From the FIT-CTF repository root:

.. code-block:: sh

   poetry run inv setup-sshd \
       --user=ctfparticipant \
       --rdz-port=2222 \
       --fitctf-dirpath=/home/operator/fit-ctf

Arguments:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Meaning
   * - ``--user``
     - Linux account allowed on the Rendezvous port
   * - ``--rdz-port``
     - TCP port for participant SSH (must not conflict with the main SSH port)
   * - ``--fitctf-dirpath``
     - Absolute path to the FIT-CTF repo (must contain ``.env`` and ``pyproject.toml``)

This writes ``99-ctf-rule.conf`` in the repository root. The effective forced command is:

.. code-block:: text

   cd <fitctf_dirpath> && poetry run fit-rendezvous

Step 3 — Install the rule and reload sshd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

   sudo cp 99-ctf-rule.conf /etc/ssh/sshd_config.d/99-ctf-rule.conf
   sudo sshd -t && sudo systemctl reload sshd

Open the Rendezvous port in the firewall if needed:

.. code-block:: sh

   sudo ufw allow 2222/tcp

Step 4 — Smoke test
~~~~~~~~~~~~~~~~~~~

From another machine (or the same host):

.. code-block:: sh

   ssh -p 2222 ctfparticipant@<server-host>

You should land in the Rendezvous login screen. Sign in with a FIT-CTF user that is
enrolled in a project (e.g. ``alice`` and the password from ``fit-ctf user create``).

Using the TUI
-------------

After signing in:

1. **Select Project** — choose an enrolled competition (sidebar turns green when your
   instance is running, yellow when idle).
2. **Project Info** — task text, SSH help for your instance, start/stop controls,
   leaderboard.
3. **Submit Secret** — submit a flag for the selected project.
4. **Upload Key** — upload an SSH public key for container access.
5. **Settings** — language (``en`` / ``cs``) and dark theme (saved per user).

Sidebar pages **Welcome** and **Help / About** describe the same flow for participants.

Operator checklist
------------------

.. list-table::
   :header-rows: 1
   :widths: 5 45 50

   * - #
     - Task
     - Command / note
   * - 1
     - FIT-CTF users exist
     - ``fit-ctf user create -u alice --generate-password``
   * - 2
     - Users enrolled
     - ``fit-ctf enrollment enroll -u alice --project-name demo``
   * - 3
     - User cluster compiled and built
     - ``fit-ctf user-cluster compile/build/start``
   * - 4
     - Rendezvous reachable
     - Local: ``poetry run fit-rendezvous``; SSH: port open and sshd reloaded
   * - 5
     - Participant can start instance
     - **Project Info** → start; verify with ``fit-ctf user-cluster status``

Production note
---------------

In a fit-ctf-virt deployment, the playground Ansible role runs ``inv setup-sshd`` and
installs ``99-ctf-rule.conf`` automatically (default Rendezvous port ``5555``, Linux
user ``user``). You still need to publish that port from the Incus host so
participants can reach it. See :doc:`fit-ctf-virt` for the full production setup.

This page covers the Rendezvous SSH entry point and TUI on the application host.

Troubleshooting
---------------

**``fit-rendezvous`` exits immediately over SSH**

- Check ``fitctf-dirpath`` points to the repo with a valid ``.env``.
- Ensure the SSH user can run ``poetry run fit-rendezvous`` in that directory (Poetry
  and venv installed for that user, or use a system-wide install).
- Inspect ``journalctl -u ssh`` / ``/var/log/auth.log`` for ForceCommand errors.

**TUI login fails with correct-looking credentials**

- Confirm MongoDB is running and ``DB_*`` variables in ``.env`` are correct.
- Verify the user exists: ``fit-ctf user list`` (or equivalent CLI command).

**Connection refused on Rendezvous port**

- Confirm ``sshd`` is listening: ``ss -tlnp | grep 2222``
- Check firewall rules and that ``99-ctf-rule.conf`` is loaded.

**Wrong language on login screen**

- Set ``FIT_RENDEZVOUS_LANG=en`` or ``cs`` in the environment before Rendezvous starts
  (e.g. in the ForceCommand wrapper or operator shell profile).
