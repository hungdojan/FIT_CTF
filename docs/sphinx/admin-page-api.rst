Admin page (``fit_ctf_admin``)
===================================

The admin TUI is layered: content pages call an async **gateway** (one protocol, two
implementations — live over ``CTFApp`` and an in-memory preview), which returns typed
**DTO** rows and raises only ``AdminError``. Scenario authoring and assignment live in
plain-Python services under ``fit_ctf_admin.scenario`` with no Textual imports.

Core facade and gateways
------------------------

.. automodule:: fit_ctf_admin.core.admin_core
   :members:

.. automodule:: fit_ctf_admin.core.protocols
   :members:

.. automodule:: fit_ctf_admin.core.live_gateway
   :members: guard, LiveGateway

.. automodule:: fit_ctf_admin.core.preview_gateway
   :members: PreviewGateway

DTOs and errors
---------------

.. automodule:: fit_ctf_admin.dto
   :members:

.. automodule:: fit_ctf_admin.exceptions
   :members:

Scenario designer services
--------------------------

.. automodule:: fit_ctf_admin.scenario.design_model
   :members: ScenarioDesign, ServiceBlock, VolumeSlot, CustomNetwork

.. automodule:: fit_ctf_admin.scenario.writer
   :members:

.. automodule:: fit_ctf_admin.scenario.assignment
   :members:

.. automodule:: fit_ctf_admin.scenario.draft
   :members:
