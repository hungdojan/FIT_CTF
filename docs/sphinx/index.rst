FIT-CTF documentation
=====================

**FIT-CTF** is a container-oriented Capture The Flag (CTF) platform developed at
`FIT BUT <https://www.fit.vut.cz/>`__ (Brno University of Technology). It lets
operators run classroom or competition-style CTF events where each participant gets
isolated container instances, while shared infrastructure (login nodes, admin services)
runs at the project level.

The platform is built around **Podman** and **podman-compose** (Docker is also supported
as a container backend). State is stored in **MongoDB**; challenge environments are
defined as **scenarios** compiled from Jinja2 templates into Docker Compose files.


Documentation map
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   introduction
   requirements
   installation
   configuration
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Concepts and architecture

   architecture
   concepts

.. toctree::
   :maxdepth: 2
   :caption: Challenge authoring

   challenge-authoring
   modules
   creating-scenarios
   scenarios

.. toctree::
   :maxdepth: 2
   :caption: Operations

   deployment
   fit-ctf-virt
   rendezvous
   setup-file
   click-commands
   container-client

.. toctree::
   :maxdepth: 1
   :caption: Project

   changelog
   roadmap

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`
