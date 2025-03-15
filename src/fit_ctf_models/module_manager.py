import pathlib
from shutil import copytree, rmtree

from pymongo.database import Database

from fit_ctf_models.project import ProjectManager
from fit_ctf_models.user_enrollment import UserEnrollmentManager
from fit_ctf_templates import TEMPLATE_DIRNAME
from fit_ctf_utils import log_print
from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.exceptions import (
    ModuleExistsException,
    ModuleInUseException,
    ModuleNotExistsException,
)
from fit_ctf_utils.types import PathDict


class ModuleManager:

    def __init__(
        self, db: Database, c_client: type[ContainerClientInterface], paths: PathDict
    ):
        self._paths = paths
        self._ue_mgr = UserEnrollmentManager(db, c_client, paths)
        self._prj_mgr = ProjectManager(db, c_client, paths)
        self.c_client = c_client

    def create_module(self, module_name: str):
        """Create a template module.

        :param module_name: A name of the module.
        :type module_name: str
        """
        dst_path = self._paths["modules"] / module_name
        if dst_path.is_dir():
            raise ModuleExistsException(f"Module `{module_name}` already exists.")

        src_path = pathlib.Path(TEMPLATE_DIRNAME) / "v1" / "modules"
        copytree(src_path, dst_path)

    def list_modules(self) -> dict[str, pathlib.Path]:
        """Get a listing of modules on the host."""
        out = {}
        for path in self._paths["modules"].iterdir():
            if path.is_dir():
                out[path.name] = str(path.resolve())
        return out

    def get_path(self, module_name: str) -> pathlib.Path:
        """Get path to the module."""
        dir_path = self._paths["modules"] / module_name
        if not dir_path.is_dir():
            raise ModuleNotExistsException(
                f"Cannot locate a path to module `{module_name}`."
            )
        return dir_path

    def reference_count(self, project_name: str | None) -> dict[str, int]:
        """Get the number of occurences of each active module in services."""
        module_count = {
            item["_id"]: item["count"]
            for item in self._ue_mgr.get_modules_count(project_name)
        }
        for mc in self._prj_mgr.get_modules_count(None):
            module_count.setdefault(mc["_id"], 0)
            module_count[mc["_id"]] += mc["count"]
        return module_count

    def remove_module(self, module_name: str):
        """Remove module from the host."""
        module_path = self.get_path(module_name)
        module_count = self.reference_count(None)
        if module_count.get(module_name, 0) > 0:
            raise ModuleInUseException(
                f"Module `{module_name}` is still used by some services."
            )
        self.c_client.rm_images(log_print, module_name, True)
        rmtree(module_path)
