import os
import re

from fit_ctf_utils.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.exceptions import ProjectNotExistException
from fit_ctf_db_models import User, UserManager
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user_enrollment import UserEnrollment

REGEX_IS_LOWER_CASE = re.compile("[a-z]")
REGEX_IS_UPPER_CASE = re.compile("[A-Z]")
REGEX_IS_DIGIT = re.compile("[0-9]")


class Actions:
    def __init__(self, host: str):
        self.ctf_mgr = CTFManager(host, os.getenv("DB_NAME", "ctf-db"))
        self._user: User | None = None

    @property
    def user(self) -> User | None:
        """Get signed user.

        :return: User object if user is signed; `None` otherwise.
        :rtype: User | None
        """
        return self._user

    def check_login(self, username: str, password: str) -> bool:
        """Validate user's login attempt.

        :param username: Given username.
        :type username: str
        :param password: Given password.
        :type password: str
        :return: `True` if given credentials are valid; False otherwise.
        :rtype: bool
        """
        if not self.ctf_mgr.user_mgr.validate_user_login(username, password):
            return False

        self._user = self.ctf_mgr.user_mgr.get_doc_by_filter(username=username)
        return True

    @staticmethod
    def check_password_strength(password: str) -> bool:
        """Validate password strength.

        :return: `True` if the password meet all the password requirements.
        :rtype: bool
        """
        return UserManager.validate_password_strength(password)

    def generate_password(self) -> str:
        """Generate a basic password.

        :return: New password.
        :rtype: str
        """
        return UserManager.generate_password(DEFAULT_PASSWORD_LENGTH)

    def get_active_projects(self) -> list[Project]:
        """Get a list of enrolled projects.

        :return: A list of enrolled projects for the given user.
        :rtype: list[Project]
        """
        if not self.user:
            return []
        return self.ctf_mgr.user_enrollment_mgr.get_enrolled_projects(
            self.user.username
        )

    def start_user_instance(self, project_name: str) -> UserEnrollment | None:
        """Start user login nodes.

        :param project_name: Project name.
        :type project_name: str
        :return: Found user enrollment object; `None` otherwise.
        :rtype: UserEnrollment | None
        """
        if not self.user:
            return None
        try:
            project = self.ctf_mgr.prj_mgr.get_project(project_name)
        except ProjectNotExistException:
            return None
        self.ctf_mgr.user_enrollment_mgr.start_user_instance(self.user, project)
        user_enrollment = self.ctf_mgr.user_enrollment_mgr.get_doc_by_filter(
            **{
                "user_id.$id": self.user.id,
                "project_id.$id": project.id,
                "active": True,
            }
        )
        return user_enrollment

    def stop_user_instance(self, project_name: str):
        """Stop user login nodes.

        :param project_name: Project name.
        :type project_name: str
        """
        if not self.user:
            return

        try:
            project = self.ctf_mgr.prj_mgr.get_project(project_name)
        except ProjectNotExistException:
            return

        self.ctf_mgr.user_enrollment_mgr.stop_user_instance(self.user, project)

    def change_password(self, password: str):
        """Change user password.

        :param password: New password.
        :type password: str
        """
        if not self._user:
            return
        self.ctf_mgr.user_mgr.change_password(self._user.username, password)
