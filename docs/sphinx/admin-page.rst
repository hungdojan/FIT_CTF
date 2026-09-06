Admin page (TUI)
================

The **admin page** (``fit-admin-page``) is the operator-facing Textual TUI. It covers the
day-to-day administration that otherwise requires a series of ``fit-ctf`` CLI commands:
managing users, projects, and enrollments; designing and assigning scenarios (including
service configuration and secrets); starting, stopping, and health-checking clusters;
building modules; and inspecting progress, logs, and user activity.

It talks to the same MongoDB and manager layer as the CLI — anything created in the TUI
is visible to ``fit-ctf`` commands and vice versa.

Running
-------

From the repository root (where ``.env`` lives), with MongoDB running:

.. code-block:: sh

   poetry run fit-admin-page

To explore the UI without a database or container runtime, use **preview mode** — every
page works against in-memory sample data and nothing is persisted:

.. code-block:: sh

   poetry run fit-admin-page --preview

Trust model
-----------

The admin page has **no login of its own**: like the ``fit-ctf`` CLI, anyone who can run
it on the host (and can read ``.env``) has full administrative control. Run it only on a
trusted operator host. No special OS permissions are required beyond what the CLI
already needs: read access to ``.env``, network access to MongoDB, and the ability to
run ``podman`` / ``podman-compose`` as the invoking user (rootless podman is fine).
The Sessions page's SSH-activity view only reads container logs through
``podman-compose logs`` — no sudo, no extra roles. The service layer is deliberately decoupled from application
bootstrapping so a later release can embed the admin screens into Rendezvous, gated by
the ``admin`` user role.

Pages
-----

Navigate with the sidebar, the ``1``–``9`` keys, or by clicking. ``Ctrl+R`` reloads the
current page. Every destructive action (delete, disable, cancel, stop-all, overwrite)
asks for confirmation first.

Dashboard
   Backend mode (connected / preview), entity counts (users, projects,
   enrollments, scenarios, modules), and a project overview table showing
   enrollment fill, whether the project cluster is running, and the scenarios
   assigned to it.

Users
   List, create (with optional password generation — the password is shown exactly once
   in a dialog), disable, and delete users. The *Show inactive* toggle includes disabled
   accounts.

Projects
   List, create, disable, and delete projects (a project's cluster and networks are
   created with it, as with ``fit-ctf project create``). *Export* writes the selected
   project as a ZIP archive (database dump + user, module, and scenario files — the
   same format as ``fit-ctf export``), to a path you choose.

Enrollments
   Per-project (or global) enrollment listing, enrolling users through a picker that
   only offers valid candidates, and cancelling enrollments.

Clusters
   Start / stop / restart project clusters and per-user clusters, live running status
   (polled while the page is visible), health checks, and *Stop all* for a project's
   user clusters. Status and health need the container runtime selected by
   ``CONTAINER_CLIENT`` (podman/podman-compose or docker) on the PATH; if the
   runtime is missing or its command fails, an error notification says so.

Scenarios
   Scenario templates with usage counts and deletion of unused ones (new scenarios are
   created in the **Designer**); *View template* shows the selected scenario's
   ``scenario_compose.yaml.j2`` read-only. The assignment section picks a target cluster
   (project, or user + project) and assigns or **edits** a scenario config: secrets and
   free config params as key/value rows, service ``env_map``/``port_map``/``volume_map``
   as YAML — the same canonical document ``fit-ctf cluster add-scenario --interactive``
   opens in an editor. Secret rows have a *Gen* button that fills a random
   ``FLAG{…}`` value (32 characters). Secret values also support a runtime macro:
   ``<gen>`` expands to 32 random alphanumeric characters when the config is saved
   (``<gen:16>`` for a custom length, ``FLAG{<gen>}`` for a wrapped flag) — the
   resolved value is what gets stored on the cluster, and every occurrence gets
   fresh randomness. *Validate* checks the config against the scenario templates
   without saving; *Preview compiled* renders the compose template with the current
   values (compile-time values such as ``{{ project_name }}``, ``{{ username }}``,
   paths, and networks appear as ``<placeholder>`` markers); *Save & compile* persists
   the config on the cluster and compiles the scenario. Template warnings (for example
   unused secrets) surface as notifications, and the compiled compose file is linted
   for constructs the container engine rejects — most notably unquoted list-form
   environment entries: always write ``- "KEY=value"`` (quoted), never ``- KEY: value``,
   in ``scenario_compose.yaml.j2``.

   **Config params** are the "free" Jinja variables of a compose template — anything
   that is not a service map (``svc__env_map__X``…), a ``secret_map__*`` slot, a
   path/network placeholder, or a value the compile step supplies itself. The bundled
   ``login_node`` scenario's ``login_node_module`` is the typical example. Their values
   are stored in ``ScenarioConfig.config_params`` and injected at compile time.

Designer
   Form-first scenario authoring with labeled fields: services (module, service key,
   container name, networks, ports, env variables managed via add/remove buttons,
   volume slots incl. Jinja volume templates that may
   reference ``secret_map__<name>`` slots), name-only secrets, and the target kind
   (user-cluster vs project-cluster scenario — this decides whether the compose
   ``name:`` line may use ``{{ username }}``). The *Compose preview* tab shows the
   generated ``scenario_compose.yaml.j2``; the *Layout* tab is an optional visual
   arrangement of the services.

   Saving writes a real scenario directory (compose template, ``volumes/`` files, and
   an ``admin_design.json`` sidecar). Scenarios saved by the designer reopen with exact
   fidelity; hand-written scenarios are loaded through a best-effort importer and are
   clearly marked, or can be edited as raw template text via *Raw edit*. A scenario
   that was edited outside the designer is never overwritten silently.

Modules
   Container module registry: create a module from the template, view and edit its
   files (Containerfile, entrypoint.sh, …) in a built-in editor, build its image —
   the full build output is shown in a dialog — and delete it (guarded by the
   compiled-scenario reference count).

Progress
   Per-project leaderboard with a per-user drill-down: solved secrets and the raw
   submission log.

Logs
   Recent compose logs of a project cluster or a user's cluster (bounded tail).

Sessions
   User activity merged from the database: Rendezvous logins/logouts and instance
   START/STOP records. *SSH activity* additionally greps the user's login-node
   container logs for sshd lines (accepted logins, session open/close, failures) —
   this is best-effort and only available while the cluster is running.

Relationship to the CLI
-----------------------

The TUI wraps the same managers the CLI uses; nothing is TUI-only in the data model.
The scenario assignment flow is the exact pipeline of ``cluster add-scenario`` /
``edit-service`` / ``add-secret`` (validation included), and compiled output is
identical. For scripted or bulk operations (``setup``, ``export``/``import``), keep
using the CLI (:doc:`click-commands`).

API reference
-------------

See :doc:`admin-page-api` for the service-layer API (gateways, DTOs, scenario
designer services).
