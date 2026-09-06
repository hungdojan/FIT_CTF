import pathlib
import re
from collections import defaultdict
from shutil import copytree, rmtree
from typing import TYPE_CHECKING

import yaml

from fit_ctf.components.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf.components.types import ErrorCode
from fit_ctf.models.utils import flatten
from fit_ctf.models.utils.exceptions import (
    ModuleExistsException,
    ModuleInUseException,
    ModuleNotExistsException,
)
from fit_ctf.path_mgmt import PathManagement
from fit_ctf.templates import TEMPLATE_PATH_MAP

if TYPE_CHECKING:
    import fit_ctf.models.core.enrollment as enroll
    import fit_ctf.models.core.project as prj
    import fit_ctf.models.core.user as _user


class ModuleManager:
    def __init__(
        self,
        c_client: ContainerClientInterface,
        paths: PathManagement,
    ):
        self._c_client = c_client
        self._paths = paths

    def create_module(self, module_name: str):
        """Create a template module.

        :param module_name: A name of the module.
        :type module_name: str
        """
        dst_path = self._paths.module_global / module_name
        if dst_path.is_dir():
            raise ModuleExistsException(f"Module `{module_name}` already exists.")

        src_path = TEMPLATE_PATH_MAP["modules"] / "template"
        copytree(src_path, dst_path)

    def list_modules(self) -> dict[str, pathlib.Path]:
        """Get a listing of modules on the host."""
        out = {}
        for path in self._paths.module_global.iterdir():
            if path.is_dir():
                out[path.name] = path.resolve()
        return out

    def get_path(self, module_name: str) -> pathlib.Path:
        """Get path to the module."""
        dir_path = self._paths.module_global / module_name
        if not dir_path.is_dir():
            raise ModuleNotExistsException(f"Cannot locate a path to module `{module_name}`.")
        return dir_path

    async def build_module(self, module_name: str, to_stdout: bool = False) -> ErrorCode:
        """Build a module's container image.

        :param module_name: Name of the module to build
        :type module_name: str
        :param to_stdout: Pipe build output to stdout
        :type to_stdout: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        dir_path = self.get_path(module_name)
        image_name = f"fit-ctf/{module_name}"
        return await self._c_client.build_image(
            logger_name=__name__,
            context_path=dir_path,
            image_name=image_name,
            containerfile="Containerfile",
            to_stdout=to_stdout,
        )

    async def build_module_text(self, module_name: str) -> "tuple[ErrorCode, str]":
        """Build a module's image and return ``(exit_code, build output)``.

        :param module_name: Name of the module to build
        :type module_name: str
        :return: Exit code and the combined build output text.
        :rtype: tuple[ErrorCode, str]
        """
        dir_path = self.get_path(module_name)
        return await self._c_client.build_image_text(
            context_path=dir_path,
            image_name=f"fit-ctf/{module_name}",
            containerfile="Containerfile",
        )

    def reference_count(
        self,
        project_name: str | None,
        prj_mgr: "prj.ProjectManager",
        enroll_mgr: "enroll.EnrollmentManager",
        all_images: bool = False,
    ) -> dict[str, int]:
        """Count module directory usage from compiled ``scenario_compose.yaml`` files.

        Scans project-level scenarios under ``project_scenarios`` and per-user
        scenarios under ``project_users/<user>/``. A hit is counted when
        ``services.*.build.context`` resolves under ``module_global``; the key is
        the first path segment (module folder name).

        :param project_name: Limit to one project, or ``None`` for all projects.
        :param all_images: If True, also count ``services.*.image`` strings (keys
            are full image references, not module directory names — useful for
            reporting only; ``remove_module`` does not use this mode).
        """

        def _project_usage(prj: "prj.Project") -> dict[str, int]:
            module_acc = defaultdict(int)
            for s in self._paths.project_scenarios(prj).iterdir():
                if not s.is_dir() or not (s / "scenario_compose.yaml").exists():
                    continue
                for module_name, count in _fetch_modules(s / "scenario_compose.yaml").items():
                    module_acc[module_name] += count
            return module_acc

        def _user_usage(user: "_user.User", project: "prj.Project") -> dict[str, int]:
            module_acc = defaultdict(int)
            user_root = self._paths.enrolled_user_path(user, project)
            if not user_root.is_dir():
                return module_acc
            for s in user_root.iterdir():
                if not s.is_dir() or not (s / "scenario_compose.yaml").exists():
                    continue
                for module_name, count in _fetch_modules(s / "scenario_compose.yaml").items():
                    module_acc[module_name] += count
            return module_acc

        def _fetch_modules(file_path: pathlib.Path) -> dict[str, int]:
            out = defaultdict(int)
            context_parser = re.compile(r"^services.[^.]*.build.context$")
            image_parser = re.compile(r"^services.[^.]*.image$")
            module_root = str(self._paths.module_global.resolve())

            try:
                raw = yaml.safe_load(file_path.read_text())
            except OSError:
                return out
            except yaml.YAMLError:
                return out
            if not isinstance(raw, dict):
                return out
            data = flatten(raw)
            for k, v in data.items():
                if not isinstance(v, str):
                    continue
                if context_parser.match(k) and v.startswith(module_root):
                    module_name = v.removeprefix(module_root).lstrip("/")
                    if module_name:
                        out[module_name] += 1
                elif all_images and image_parser.match(k):
                    out[v] += 1
            return out

        if project_name:
            prjs = [prj_mgr.get_project(project_name)]
        else:
            prjs = prj_mgr.get_docs()
        modules = defaultdict(int)
        for p in prjs:
            if self._paths.project_scenarios(p).exists():
                for k, v in _project_usage(p).items():
                    modules[k] += v
            for u in enroll_mgr.get_enrollments_for_project(p):
                for k, v in _user_usage(u, p).items():
                    modules[k] += v

        return dict(modules)

    async def remove_module(
        self,
        module_name: str,
        prj_mgr: "prj.ProjectManager",
        enroll_mgr: "enroll.EnrollmentManager",
    ):
        """Remove module from the host."""
        module_path = self.get_path(module_name)
        module_count = self.reference_count(None, prj_mgr, enroll_mgr)
        if module_count.get(module_name, 0) > 0:
            raise ModuleInUseException(f"Module `{module_name}` is still used by some services.")
        _ = await self._c_client.rm_images(__name__, module_name, True)
        rmtree(module_path)
