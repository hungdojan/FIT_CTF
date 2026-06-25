# Changelog

All notable changes to FIT-CTF are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Sphinx documentation: installation, architecture, challenge authoring, Rendezvous SSH
  setup, and CLI reference.
- Unit tests for `PodmanClient.compose_ps` (`ps -q` parsing).

### Changed

- Local MongoDB tasks (`inv db-start`, `db-stop`, `db-shell`) use Podman instead of Docker.
- `PodmanClient.compose_ps` uses `podman-compose ps -q` to avoid false positives when no
  containers are running.

### Fixed

- Sphinx CLI docs updated from obsolete `fit_ctf_backend` to `fit_ctf_cli`.

## [1.0.0] - 2025

### Added

- Consolidated packages: `fit_ctf`, `fit_ctf_cli`, `fit_ctf_rendezvous`.
- Scenario compile and build pipeline (Jinja2 templates → Compose).
- Scenario management CLI (`fit-ctf scenario`).
- Module management CLI (`fit-ctf module create`, `build`, `referenced`, `rm`).
- User and project cluster lifecycle (compile, build, start, stop, logs, health).
- Secret submission, progress tracking, and leaderboard.
- Rendezvous TUI with English and Czech translations.
- Optional login node scenario; enrollment without mandatory login node.
- Manager dependency injection and `EntityRepository`.
- Separate MongoDB admin credentials for local development.
- Data export/import (`fit-ctf data-mgmt export` / `import`).
- Bulk environment setup (`fit-ctf data-mgmt setup`).
- SSH node ownership configuration and sshd setup task (`inv setup-sshd`).
- Podman and Docker container client backends.

### Changed

- MongoDB image pinned to 7.0 for compatibility.
- Base module images updated to UBI 9 and Debian 13.
- Package consolidation from legacy `fit_ctf_backend` layout.

### Fixed

- Database configuration and import edge cases.
- Export archive correctness.
- Port forwarding messages in Rendezvous.
- Shell autocompletion performance.

[Unreleased]: https://github.com/hungdojan/fit-ctf/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/hungdojan/fit-ctf/releases/tag/v1.0.0
