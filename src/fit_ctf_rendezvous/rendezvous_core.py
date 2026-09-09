import re
from typing import Any, Callable

from fit_ctf.components.auth.auth_interface import AuthInterface
from fit_ctf.components.auth.local_auth import LocalAuth
from fit_ctf.components.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf.components.exceptions import CTFBaseException, LoginException
from fit_ctf.ctf_base import CTFBase
from fit_ctf.models.core.enrollment import Enrollment
from fit_ctf.models.core.project import Project
from fit_ctf.models.core.user import User
from fit_ctf.models.utils.exceptions import (
    PublicKeyUploadFail,
    SecretAlreadySubmittedException,
    SecretNotFoundException,
)
from fit_ctf_rendezvous.exceptions import (
    CannotChangePassword,
    IncorrectCredentials,
    InvalidAction,
    SecretSubmitFail,
    UserNotLoggedIn,
)
from fit_ctf_rendezvous.utils import LeaderboardDataTableItem

REGEX_IS_LOWER_CASE = re.compile("[a-z]")
REGEX_IS_UPPER_CASE = re.compile("[A-Z]")
REGEX_IS_DIGIT = re.compile("[0-9]")


class _VariableRegistry:
    _active_user: User | None = None
    _selected_project: Project | None = None

    _callbacks: dict[str, dict[str, Callable[[Any | None], None]]] = {
        "active_user": {},
        "selected_project": {},
    }

    @property
    def active_user(self) -> User | None:
        """Get signed user.

        :return: User object if user is signed; `None` otherwise.
        :rtype: User | None
        """
        return self._active_user

    @active_user.setter
    def active_user(self, value: User | None):
        for _, _callback in self._callbacks["active_user"].items():
            _callback(value)
        self._active_user = value

    @property
    def selected_project(self) -> Project | None:
        return self._selected_project

    @selected_project.setter
    def selected_project(self, value: Project | None):
        for _, callback in self._callbacks["selected_project"].items():
            callback(value)
        self._selected_project = value

    def register_hook(self, variable_name: str, name: str, callback: Callable[[Any | None], None]):
        self._callbacks[variable_name][name] = callback

    def unregister_hook(self, variable_name: str, name: str):
        self._callbacks[variable_name].pop(name)

    def unregister_from_all(self, name: str):
        for callbacks in self._callbacks.values():
            callbacks.pop(name)


class RendezvousCore(_VariableRegistry):
    def __init__(self, ctf_base: CTFBase, auth_client: AuthInterface | None = None):
        self._ctf_base = ctf_base
        # TODO: config
        self.auth_client = auth_client if auth_client else LocalAuth(ctf_base.user_mgr)

    @property
    def ctf_base(self) -> CTFBase:
        return self._ctf_base

    def validate_login(self, username: str, password: str):
        """Validate user's login attempt.

        :param username: Given username.
        :type username: str
        :param password: Given password.
        :type password: str
        :return: `True` if given credentials are valid; False otherwise.
        :rtype: bool
        """
        try:
            user = self.auth_client.validate_credentials(username, password)
            self._active_user = user
            self.ctf_base.user_mgr.record_login(user)
        except LoginException as e:
            raise IncorrectCredentials(str(e))

    @staticmethod
    def check_password_strength(password: str) -> bool:
        """Validate password strength.

        :return: `True` if the password meet all the password requirements.
        :rtype: bool
        """
        return AuthInterface.validate_password_strength(password)

    def generate_password(self) -> str:
        """Generate a basic password.

        :return: New password.
        :rtype: str
        """
        return AuthInterface.generate_password(DEFAULT_PASSWORD_LENGTH)

    def change_password(self, password: str):
        """Change user password.

        :param password: New password.
        :type password: str
        """
        if not self._active_user:
            return
        if not self.auth_client.local_login:
            raise CannotChangePassword("The Auth client does not support password update.")
        self._active_user = self.ctf_base.user_mgr.change_password(
            self._active_user.username, password
        )

    def get_active_projects(self) -> list[Project]:
        """Get a list of enrolled projects.

        :return: A list of enrolled projects for the given user.
        :rtype: list[Project]
        """
        if not self.active_user:
            return []
        return self.ctf_base.enroll_mgr.get_enrolled_projects(self.active_user.username)

    def submit_secret(self, value: str, project_name: str) -> None:
        """Wrapper function for submitting project secrets.

        :param value: A submitted secret value.
        :type value: str
        :param project_name: A name of the selected project.
        :type project_name: str
        :raise UserNotLoggedIn: In case a submission of secret by anonymous user.
        :raise InvalidAction: Unable to perform action.
        :raise SecretSubmitFail: The submitted secret was not successful.
        """
        if not self.active_user:
            raise UserNotLoggedIn("Cannot submit a secret.")
        try:
            project = self.ctf_base.prj_mgr.get_project(project_name)
            enrollment = self.ctf_base.enroll_mgr.get_enrollment(self.active_user, project)
        except CTFBaseException as e:
            raise InvalidAction(e)

        try:
            self.ctf_base.enroll_mgr.submit_secret(enrollment, value, self.ctf_base.prj_mgr)
        except SecretAlreadySubmittedException as e:
            raise SecretSubmitFail(e)
        except SecretNotFoundException:
            raise SecretSubmitFail("Invalid secret.")

    def get_leaderboard(self) -> list[LeaderboardDataTableItem]:
        """Fetch leaderboard from the backend."""
        if not self.selected_project:
            raise InvalidAction("Cannot fetch leaderboard without selected project.")
        leaderboard_items = self.ctf_base.enroll_mgr.get_leaderboard(self.selected_project)
        return [
            LeaderboardDataTableItem(
                {
                    "position": pos + 1,
                    "username": item["user"],
                    "found_secrets": item["found_secrets"],
                    "last_submit_time": (
                        item["last_submit_time"].astimezone().strftime("%x %X")
                        if item["last_submit_time"]
                        else ""
                    ),
                    "percentage_score": "{:.2f} %".format(
                        item["found_secrets"] / item["total_secrets"] * 100
                        if item["total_secrets"] > 0
                        else 0
                    ),
                }
            )
            for pos, item in enumerate(leaderboard_items)
        ]

    def upload_public_key(self, pub_key: bytes):
        if not self.active_user:
            raise UserNotLoggedIn("Cannot submit a secret.")
        try:
            self.ctf_base.user_mgr.upload_public_key(self.active_user, pub_key)
        except PublicKeyUploadFail as e:
            raise InvalidAction(e)

    async def start_user_instance(self) -> Enrollment:
        """Start user login nodes.

        :return: Enrollment for the running instance.
        :rtype: Enrollment
        :raise InvalidAction: If user or project is missing, enrollment lookup fails,
            or the cluster fails to start.
        """
        if not self.active_user or not self.selected_project:
            raise InvalidAction("Select a project before starting an instance.")
        try:
            enrollment = self.ctf_base.enroll_mgr.get_enrollment(
                self.active_user, self.selected_project
            )
            cluster = self.ctf_base.user_cluster_mgr.get_cluster(enrollment)
        except CTFBaseException as e:
            raise InvalidAction(str(e)) from e

        try:
            await self.ctf_base.user_cluster_mgr.start_cluster(cluster, self.ctf_base.enroll_mgr)
        except Exception as e:
            raise InvalidAction(str(e)) from e
        return enrollment

    async def stop_user_instance(self):
        """Stop user login nodes.

        :param project_name: Project name.
        :type project_name: str
        """
        if not self.active_user or not self.selected_project:
            return

        try:
            enrollment = self.ctf_base.enroll_mgr.get_enrollment(
                self.active_user, self.selected_project
            )
            cluster = self.ctf_base.user_cluster_mgr.get_cluster(enrollment)
        except CTFBaseException:
            return

        try:
            await self.ctf_base.user_cluster_mgr.stop_cluster(cluster, self.ctf_base.enroll_mgr)
        except Exception as e:
            raise InvalidAction(str(e)) from e

    async def instance_is_running(self) -> bool:
        if not self.active_user or not self.selected_project:
            return False
        try:
            enrollment = self.ctf_base.enroll_mgr.get_enrollment(
                self.active_user, self.selected_project
            )
            cluster = self.ctf_base.user_cluster_mgr.get_cluster(enrollment)
        except CTFBaseException:
            return False
        return await self.ctf_base.user_cluster_mgr.cluster_is_running(cluster)

    async def cleanup(self):
        if self.active_user is None:
            return
        await self.ctf_base.user_cluster_mgr.stop_all_clusters_of_a_user(
            self.active_user, self.ctf_base.enroll_mgr
        )
