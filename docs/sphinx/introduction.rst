Introduction
============

What FIT-CTF does
-----------------

FIT-CTF orchestrates the full lifecycle of a container-based CTF event:

1. **Define a competition** as a *project* with a capacity limit and port range.
2. **Register participants** as *users* and *enroll* them into projects.
3. **Author challenge environments** as reusable *scenarios* (Jinja2 Compose templates)
   built from *modules* (container images).
4. **Deploy containers** in two scopes:

   - **Project clusters** — shared services visible to all enrolled users (e.g. a login
     node or admin dashboard).
   - **User clusters** — per-participant instances with private networks and secrets.

5. **Track progress** — participants submit flags/secrets; the platform records solves and
   maintains a leaderboard.

Typical workflow
----------------

.. code-block:: text

   Operator                          Participant
   --------                          -------------
   fit-ctf project create
   fit-ctf user create
   fit-ctf enrollment enroll
   fit-ctf user-cluster compile
   fit-ctf user-cluster start
                                     SSH → fit-rendezvous
                                     Select project
                                     Start instance
                                     Submit secret
   fit-ctf user-progress list        View leaderboard

Two front-end programs
----------------------

``fit-ctf`` (operator CLI)
~~~~~~~~~~~~~~~~~~~~~~~~~~

A Click-based command-line tool for administrators. It talks to MongoDB and the
container engine to manage projects, users, enrollments, modules, scenarios, and both
cluster types. Database connections are opened lazily — only commands that need the DB
trigger a connection.

Entry point: ``fit-ctf`` (Poetry script → ``fit_ctf_cli``).

``fit-rendezvous`` (participant TUI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Textual terminal UI launched over SSH. After login, participants can:

- Select an enrolled project
- Read task instructions and connection details
- Start or stop their personal cluster instance
- Submit secrets and view the leaderboard
- Upload an SSH public key

Entry point: ``fit-rendezvous`` (Poetry script → ``fit_ctf_rendezvous``).

Supported languages: English (``en``) and Czech (``cs``), controlled by the
``FIT_RENDEZVOUS_LANG`` environment variable.

Backend library
~~~~~~~~~~~~~~~

The shared Python package ``fit_ctf`` contains managers, models, scenario compilation,
container client abstractions, and database access. Both front-ends import from this
library; operators rarely interact with it directly.
