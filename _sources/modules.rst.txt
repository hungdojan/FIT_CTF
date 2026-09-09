Creating modules
================

A **module** is a container image definition that scenarios reference when declaring
services. Modules live on disk under ``{MODULE_SHARE_DIR}/{module_name}/`` (default:
``~/.local/share/fit-ctf/module/``).

After building, images are tagged ``fit-ctf/{module_name}``.

Directory layout
----------------

A new module contains a copy of the bundled ``template`` module:

.. code-block:: text

   module/my_challenge/
   ├── Containerfile      ← image build instructions
   └── entrypoint.sh      ← container entrypoint (customize as needed)

Bundled reference modules (``ssh_debian``, ``ssh_ubi``) also include ``init_script.sh``
and are a good starting point for SSH-based challenges.

Create a module
---------------

.. code-block:: sh

   fit-ctf module create my_challenge

This copies ``template/`` from ``src/fit_ctf/templates/v1/modules/template/``. The module
name must not already exist.

List and locate modules
-----------------------

.. code-block:: sh

   fit-ctf module ls
   fit-ctf module get-path -mn my_challenge
   cd "$(fit-ctf module get-path -mn my_challenge)"

Edit the Containerfile
----------------------

Open the module directory and edit ``Containerfile``. Example structure (from the
template):

.. code-block:: dockerfile

   FROM registry.access.redhat.com/ubi9:latest

   RUN dnf update \
       && dnf install vim curl iproute \
       && dnf clean all

   COPY ./entrypoint.sh /entrypoint.sh
   RUN chmod +x /entrypoint.sh

   ENTRYPOINT ["/entrypoint.sh"]

For Debian-based challenges, compare with the bundled ``ssh_debian`` module, which
installs ``openssh-server``, creates a ``user`` account, and exposes port 22.

.. note::

   Scenarios reference modules by **directory name** in the ``build.context`` path, e.g.
   ``{{ paths__modules }}/my_challenge``. The image name in the Compose file should match:
   ``fit-ctf/my_challenge:latest``.

Build the image
---------------

.. code-block:: sh

   fit-ctf module build my_challenge
   fit-ctf module build my_challenge -v    # show build log

Building uses ``podman build`` (or Docker when ``CONTAINER_CLIENT=docker``).

Verify the image exists:

.. code-block:: sh

   podman images | grep fit-ctf

Use the module in a scenario
----------------------------

In ``scenario_compose.yaml.j2``, reference the module in a service:

.. code-block:: yaml

   services:
     web:
       build:
         context: {{ paths__modules }}/my_challenge
         dockerfile: Containerfile
       image: fit-ctf/my_challenge:latest
       networks:
         {{ network_map__private }}:

Use ``network_map__shared``, ``network_map__private``, or ``network_map__operational``
depending on whether the service should sit on the shared project network, the
per-user private network, or the operational network. See :doc:`creating-scenarios`.

Check usage before removing
---------------------------

.. code-block:: sh

   fit-ctf module referenced
   fit-ctf module referenced -pn demo_project

Remove an unused module
-----------------------

.. code-block:: sh

   fit-ctf module rm my_challenge

Removal fails if compiled ``scenario_compose.yaml`` files still reference the module.

Workflow checklist
------------------

1. ``fit-ctf module create <name>``
2. Edit ``Containerfile`` and ``entrypoint.sh`` (add challenge files, packages, flags)
3. ``fit-ctf module build <name>``
4. Reference ``fit-ctf/<name>`` in a scenario template (:doc:`creating-scenarios`)
5. After changing the Containerfile, rebuild the module **and** re-run
   ``user-cluster build`` / ``project-cluster build`` for affected clusters

Common pitfalls
---------------

- **Forgot to rebuild** — scenario ``build`` uses the module context; image layers are
  cached until you run ``fit-ctf module build`` again.
- **Wrong image tag** — keep ``image: fit-ctf/{module_name}:latest`` aligned with the
  module folder name.
- **Module in use** — ``module rm`` scans compiled compose files; remove scenarios from
  clusters first if needed.
