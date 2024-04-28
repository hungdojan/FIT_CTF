from __future__ import annotations

import os
import re

from fit_ctf_backend import DEFAULT_PASSWORD_LENGTH
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models import User, UserManager

REGEX_IS_LOWER_CASE = re.compile("[a-z]")
REGEX_IS_UPPER_CASE = re.compile("[A-Z]")
REGEX_IS_DIGIT = re.compile("[0-9]")


class Actions:
    def __init__(self, host: str):
        self.backend = CTFManager(host, os.getenv("DB_NAME", "ctf-db"))
        self._user: User | None = None

    @property
    def user(self) -> User | None:
        return self._user

    def check_login(self, username: str, password: str) -> bool:
        """Validate user's login attempt.

        Args:
            username (str): Given username.
            password (str): Given password.

        Returns:
            bool: True if given credentials are valid; False otherwise.
        """
        if not self.backend.user_mgr.validate_user_login(username, password):
            return False

        self._user = self.backend.user_mgr.get_doc_by_filter(username=username)
        return True

    @staticmethod
    def check_password_strength(password: str) -> bool:
        return UserManager.validate_password_strength(password)

    def generate_password(self) -> str:
        """Generate a basic password.

        Returns:
            str: New password.
        """
        return UserManager.generate_password(DEFAULT_PASSWORD_LENGTH)

    def get_active_projects(self):
        raise NotImplemented()

    def start_user_instance(self) -> tuple[bool, dict[str, str]]:
        """Fire up user instance"""
        # TODO:
        # start instance from the backend
        # wait if successful
        # return bool if successful
        # return command for them
        return True, {}

    def change_password(self, password):
        if not self._user:
            return
        self.backend.user_mgr.change_password(self._user.username, password)
