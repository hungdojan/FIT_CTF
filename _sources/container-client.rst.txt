Container client
================

FIT-CTF talks to Podman or Docker through :class:`~fit_ctf.components.container_client.container_client_interface.ContainerClientInterface`.
The concrete implementation is selected at runtime via the ``CONTAINER_CLIENT`` environment variable
(``podman``, ``docker``, or ``mock``).

Compose helpers
---------------

``compose_ps``
~~~~~~~~~~~~~~~~

Lists containers managed by a compose project. Implementations call ``compose ps -q`` so the
result is a list of **container IDs** (one ID per line), not service names or table output.

An empty compose file list or a project with no running containers returns ``[]``.

This method is used by cluster managers to answer "is this cluster running?":

.. code-block:: python

   running = len(await c_client.compose_ps(compose_files)) > 0

``compose_down``
~~~~~~~~~~~~~~~~

Tears down a compose project. The method first runs ``compose ps -q``; if there is no output it
returns ``(0, False)`` without calling ``down``. Otherwise it runs ``compose down`` and returns
``(exit_code, True)`` on success.

Podman implementation
---------------------

.. autoclass:: fit_ctf.components.container_client.podman_client.PodmanClient
   :members: compose_ps, compose_down, compose_states, compose_ps_json
   :show-inheritance:

Interface
---------

.. autoclass:: fit_ctf.components.container_client.container_client_interface.ContainerClientInterface
   :members: compose_ps, compose_down, compose_states, compose_ps_json
   :show-inheritance:
