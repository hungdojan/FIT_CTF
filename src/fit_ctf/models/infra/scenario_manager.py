"""Scenario management for CTF platform."""

import pathlib
import re
import shutil
from typing import TYPE_CHECKING

from fit_ctf.models.infra.config_models import ScenarioConfig
from fit_ctf.models.infra.utils import (
    validate_secrets_vs_templates,
    validate_service_configs_vs_scaffold,
)
from fit_ctf.models.utils.exceptions import (
    CTFModelException,
    ScenarioExistException,
    ScenarioNotExistException,
)
from fit_ctf.models.utils.mongo_queries import MongoQueries
from fit_ctf.path_mgmt import PathManagement
from fit_ctf.templates import TEMPLATE_PATH_MAP, get_jinja_variables, get_template

if TYPE_CHECKING:
    import fit_ctf.models.core.project as project
    import fit_ctf.models.infra.user_cluster as user_cluster

# `volumes/*.template`: `{service}__volume_map__{volume}__{param}` (four segments).
_VOL_MAP_TPL_PARAM_RE = re.compile(r"^(.+?)__volume_map__(.+?)__(.+)$")
# `{service}__port_map__`, `__env_map__`, `__volume_map__{volume}` (three segments).
_SC_TRIPLE_RE = re.compile(r"^(.*)__(.*)__(.*)$")
_SECRET_MAP_RE = re.compile(r"^secret_map__(.+)$")

_SCENARIO_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# Variables that the cluster compile step supplies without any config entry
# (see ``ClusterManagerMixin`` subclasses' ``_compose_template_extras``).
_COMPILE_SUPPLIED_VARIABLES = frozenset(
    {
        "project_name",
        "username",
        "container_port",
        "forwarded_port",
        "login_node_module",
    }
)


class ScenarioManager:
    """Manager for CTF scenario templates and configurations."""

    def __init__(self, paths: PathManagement):
        """Initialize ScenarioManager.

        :param paths: Path management instance
        :type paths: PathManagement
        """
        self._paths = paths

    @property
    def scenario_root(self) -> pathlib.Path:
        """Get root directory for scenario templates.

        :return: Path to scenario root directory
        :rtype: pathlib.Path
        """
        return self._paths.scenario_global

    @staticmethod
    def validate_scenario_name(scenario_name: str) -> None:
        """Raise :class:`CTFModelException` unless the name is a safe slug.

        Restricting names to ``[a-z0-9_]+`` also rules out path traversal in
        every place that joins the name onto the scenario root.

        :param scenario_name: Name to validate.
        :type scenario_name: str
        :raises CTFModelException: If the name is empty or contains other characters.
        """
        if not _SCENARIO_NAME_RE.fullmatch(scenario_name):
            raise CTFModelException(
                f"Invalid scenario name {scenario_name!r}: use lowercase letters, "
                "digits, and underscores only."
            )

    def create_scenario(self, scenario_name: str):
        """Create a new scenario template.

        Creates directory structure and base template files for a new scenario.

        :param scenario_name: Name for the new scenario
        :type scenario_name: str
        :raises CTFModelException: If the scenario name is not a valid slug
        :raises ScenarioExistException: If scenario already exists
        """
        self.validate_scenario_name(scenario_name)
        path = self.scenario_root / scenario_name
        if path.exists():
            raise ScenarioExistException(f"Scenario {scenario_name} already exists.")

        path.mkdir(parents=True)
        try:
            with open(path / "scenario_compose.yaml.j2", "w") as f:
                template = get_template("scenario_base_compose.yaml.j2")
                f.write(template.render(name=scenario_name))
            shutil.copytree(TEMPLATE_PATH_MAP["volumes"], path / "volumes")

        except Exception as e:
            # Clean up created directory if template creation fails
            if path.exists():
                shutil.rmtree(path)
            raise e

    def get_scenario_dir(self, scenario_name: str) -> pathlib.Path:
        """Get directory path for a scenario.

        :param scenario_name: Name of the scenario
        :type scenario_name: str
        :return: Path to scenario directory
        :rtype: pathlib.Path
        :raises CTFModelException: If the scenario name is not a valid slug
        :raises ScenarioNotExistException: If scenario does not exist
        """
        self.validate_scenario_name(scenario_name)
        path = self.scenario_root / scenario_name
        if not path.exists():
            raise ScenarioNotExistException(f"Scenario {scenario_name} does not exist")
        return path

    def read_compose_template(self, scenario_name: str) -> str:
        """Return the raw ``scenario_compose.yaml.j2`` text of a scenario.

        :param scenario_name: Name of the scenario
        :type scenario_name: str
        :return: Template file content
        :rtype: str
        :raises ScenarioNotExistException: If scenario does not exist
        """
        path = self.get_scenario_dir(scenario_name) / "scenario_compose.yaml.j2"
        if not path.is_file():
            raise ScenarioNotExistException(
                f"Scenario {scenario_name} has no scenario_compose.yaml.j2"
            )
        return path.read_text(encoding="utf-8")

    def save_scenario_files(
        self,
        scenario_name: str,
        compose_text: str,
        volume_files: dict[str, str] | None = None,
        extra_files: dict[str, str] | None = None,
        *,
        overwrite: bool = False,
    ) -> pathlib.Path:
        """Write a scenario directory from in-memory file contents.

        Centralized write-back used by tooling (e.g. the admin TUI designer):
        creates ``<scenario_root>/<name>/scenario_compose.yaml.j2``, files under
        ``volumes/`` from ``volume_files`` (keyed by file name), and arbitrary
        top-level ``extra_files`` (e.g. a design sidecar). Existing files that
        are not part of the given mappings are left untouched.

        :param scenario_name: Target scenario name (validated slug).
        :type scenario_name: str
        :param compose_text: Content for ``scenario_compose.yaml.j2``.
        :type compose_text: str
        :param volume_files: Mapping of ``volumes/`` file names to contents.
        :type volume_files: dict[str, str] | None
        :param extra_files: Mapping of scenario-root file names to contents.
        :type extra_files: dict[str, str] | None
        :param overwrite: Allow writing into an existing scenario directory.
        :type overwrite: bool
        :return: The scenario directory path.
        :rtype: pathlib.Path
        :raises CTFModelException: If the scenario name is not a valid slug or
            a target file name escapes the scenario directory.
        :raises ScenarioExistException: If the scenario exists and ``overwrite``
            is not set.
        """
        self.validate_scenario_name(scenario_name)
        path = self.scenario_root / scenario_name
        created = not path.exists()
        if not created and not overwrite:
            raise ScenarioExistException(f"Scenario {scenario_name} already exists.")

        def _safe_target(root: pathlib.Path, file_name: str) -> pathlib.Path:
            target = (root / file_name).resolve()
            if root.resolve() not in target.parents:
                raise CTFModelException(f"Invalid scenario file name {file_name!r}")
            return target

        try:
            path.mkdir(parents=True, exist_ok=True)
            (path / "scenario_compose.yaml.j2").write_text(compose_text, encoding="utf-8")
            if volume_files:
                volume_root = path / "volumes"
                volume_root.mkdir(exist_ok=True)
                for file_name, content in volume_files.items():
                    _safe_target(volume_root, file_name).write_text(content, encoding="utf-8")
            for file_name, content in (extra_files or {}).items():
                _safe_target(path, file_name).write_text(content, encoding="utf-8")
        except BaseException:  # CTFModelException derives from BaseException
            if created and path.exists():
                shutil.rmtree(path)
            raise
        return path

    def fetch_unmapped_variables(self, scenario_name: str) -> set[str]:
        """Compose variables that must come from ``ScenarioConfig.config_params``.

        Returns every variable of ``scenario_compose.yaml.j2`` that is neither
        a path/network placeholder, a service map triple, a secret slot, nor a
        variable the cluster compile step supplies itself (``project_name``,
        ``username``, ``container_port``, ``forwarded_port``,
        ``login_node_module``). Missing entries only fail late inside
        ``write_compose``; callers can require values for these up front.

        :param scenario_name: Name of the scenario
        :type scenario_name: str
        :return: Set of free variable names.
        :rtype: set[str]
        """
        scenario_dir = self.get_scenario_dir(scenario_name)
        unmapped: set[str] = set()
        for variable in get_jinja_variables("scenario_compose.yaml.j2", scenario_dir):
            if variable in _COMPILE_SUPPLIED_VARIABLES:
                continue
            if variable.startswith("paths__") or variable.startswith("network_map__"):
                continue
            if _SECRET_MAP_RE.fullmatch(variable):
                continue
            if _VOL_MAP_TPL_PARAM_RE.fullmatch(variable) or _SC_TRIPLE_RE.fullmatch(variable):
                continue
            unmapped.add(variable)
        return unmapped

    def fetch_variables(self, scenario_name: str) -> dict[str, dict]:
        """Fetch Jinja2 template variables from scenario templates.

        Parses scenario compose templates and volume templates to extract
        required variables for configuration.

        :param scenario_name: Name of the scenario
        :type scenario_name: str
        :return: Dictionary of variables organized by service and type
        :rtype: dict[str, str]
        """
        scenario_dir = self.get_scenario_dir(scenario_name)
        vars_ = get_jinja_variables("scenario_compose.yaml.j2", scenario_dir)
        var_dict: dict = {}
        for v in vars_:
            m4 = _VOL_MAP_TPL_PARAM_RE.fullmatch(v)
            if m4:
                svc, vol, pkey = m4.group(1), m4.group(2), m4.group(3)
                var_dict.setdefault(svc, {}).setdefault("volume_map", {}).setdefault(
                    vol, {}
                ).setdefault("template_params", {})[pkey] = ""
                continue
            m = _SC_TRIPLE_RE.fullmatch(v)
            if m:
                svc, m_type, m_key = m.group(1), m.group(2), m.group(3)
                if m_type != "volume_map":
                    var_dict.setdefault(svc, {}).setdefault(m_type, {})[m_key] = ""
                else:
                    var_dict.setdefault(svc, {}).setdefault(m_type, {}).setdefault(m_key, {})[
                        "src_path"
                    ] = ""

        if (scenario_dir / "volumes").exists():
            for file in (scenario_dir / "volumes").iterdir():
                if not file.name.endswith(".template"):
                    continue
                for v in get_jinja_variables(file.name, scenario_dir / "volumes"):
                    m4 = _VOL_MAP_TPL_PARAM_RE.fullmatch(v)
                    if m4:
                        var_dict.setdefault(m4.group(1), {}).setdefault(
                            "volume_map", {}
                        ).setdefault(m4.group(2), {}).setdefault("template_params", {})[
                            m4.group(3)
                        ] = ""

        return var_dict

    @staticmethod
    def _secret_names_from_jinja_vars(variables: set[str]) -> set[str]:
        keys: set[str] = set()
        for v in variables:
            m = _SECRET_MAP_RE.fullmatch(v)
            if not m:
                continue
            name = m.group(1)
            if not name or "__" in name:
                continue
            keys.add(name)
        return keys

    def fetch_secret_keys(self, scenario_name: str) -> list[str]:
        """Secret names used as ``secret_map__<name>`` in compose and volume templates."""
        scenario_dir = self.get_scenario_dir(scenario_name)
        keys = self._secret_names_from_jinja_vars(
            get_jinja_variables("scenario_compose.yaml.j2", scenario_dir)
        )
        vol_root = scenario_dir / "volumes"
        if vol_root.is_dir():
            for item in vol_root.iterdir():
                if not item.name.endswith(".template"):
                    continue
                keys |= self._secret_names_from_jinja_vars(get_jinja_variables(item.name, vol_root))
        return sorted(keys)

    def validate_scenario_config_against_templates(
        self, scenario_name: str, config: ScenarioConfig
    ) -> list[str]:
        """Raise :class:`CTFModelException` if required template slots are missing.

        Returns warning strings for unused config keys.
        """
        required_secrets = frozenset(self.fetch_secret_keys(scenario_name))
        scaffold = self.fetch_variables(scenario_name)
        se, sw = validate_secrets_vs_templates(required_secrets, config.secrets)
        ve, vw = validate_service_configs_vs_scaffold(scaffold, config.service_configs)
        errors = se + ve
        if errors:
            raise CTFModelException(
                "Scenario config does not satisfy templates: " + "; ".join(errors)
            )
        return sw + vw

    def list_scenarios(self) -> list[str]:
        """List all available scenario templates.

        :return: List of scenario names
        :rtype: list[str]
        """
        return [item.name for item in self.scenario_root.iterdir() if item.is_dir()]

    def scenario_usage_for_project(
        self, project: "project.Project", enroll_mgr, include_users: bool = False
    ) -> list[str]:
        """Get scenarios used in a project.

        :param project: Project to check
        :param enroll_mgr: EnrollmentManager for enrollment queries
        :param include_users: Include user-specific scenarios
        :return: List of scenario names used in the project
        """

        def _fetch_scenarios(path: pathlib.Path) -> set[str]:
            if not path.exists():
                return set()
            return set(d.name for d in path.iterdir() if d.is_dir)

        usage = _fetch_scenarios(self._paths.project_scenarios(project))
        if include_users:
            enrolled_users = enroll_mgr.get_enrollments_for_project(project)
            for user in enrolled_users:
                usage.update(_fetch_scenarios(self._paths.enrolled_user_path(user, project)))
        return list(usage)

    def scenario_overview(
        self, user_cluster_mgr: "user_cluster.UserClusterManager"
    ) -> dict[str, list[int]]:
        """Get overview of scenario usage across clusters.

        :param user_cluster_mgr: UserClusterManager for cluster queries
        :return: Dictionary mapping scenario names to cluster IDs
        :rtype: dict[str, list[int]]
        """
        scenarios_map = {scenario_name: [] for scenario_name in self.list_scenarios()}
        data = list(user_cluster_mgr.collection.aggregate(MongoQueries.scenario_usage_overview()))
        for item in data:
            scenarios_map[item["_id"]] = item["clusters"]
        return scenarios_map

    def scenario_usage(
        self, scenario_name: str, user_cluster_mgr: "user_cluster.UserClusterManager"
    ) -> list:
        """Get all clusters using a specific scenario.

        :param scenario_name: Name of the scenario
        :param user_cluster_mgr: UserClusterManager for cluster queries
        :type scenario_name: str
        :return: List of UserCluster objects using the scenario
        :rtype: list
        """
        return list(
            user_cluster_mgr.collection.find(
                {f"scenario_configs.{scenario_name}": {"$exists": True}}
            )
        )

    def delete_scenario(self, scenario_name: str):
        """Delete a scenario template.

        :param scenario_name: Name of scenario to delete
        :type scenario_name: str
        :raises ScenarioNotExistException: If scenario does not exist
        """
        path = self.get_scenario_dir(scenario_name)
        shutil.rmtree(path)
