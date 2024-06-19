from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import string
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

from bson import ObjectId
from passlib.hash import sha512_crypt
from pymongo.database import Database

import fit_ctf_db_models.project as _project
import fit_ctf_db_models.user_config as _user_config
from fit_ctf_backend.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_backend.exceptions import (
    DirNotExistsException,
    UserExistsException,
    UserNotExistsException,
)
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_templates import TEMPLATE_FILES, get_template

log = logging.getLogger()
log.disabled = False


class UserRole(str, Enum):
    """Enumeration of user roles."""

    USER = "user"
    ADMIN = "admin"


@dataclass(init=False)
class User(Base):
    """A class that represents a user document.

    :param username: A string used to identify a user chosen by the user.
    :type username: str
    :param password: A hashed password used for user authentication.
    :type password: str
    :param role: User role defines account's capabilities.
    :type role: UserRole
    :param shadow_path: A path to the user shadow file.
    :type shadow_path: str
    :param shadow_hash: A hash string that is passed to the shadow file.
    :type shadow_hash: str
    :param email: User email.
    :type email: str
    """

    username: str
    password: str
    role: UserRole
    shadow_path: str
    shadow_hash: str = field(default="")
    email: str = field(default="")

    def __init__(self, **kwargs):
        # set default values
        self.active = True
        self.shadow_hash = ""
        self.email = ""
        # ignore extra fields
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


class UserManager(BaseManager[User]):
    """A manager class that handles operations with `User` objects."""

    def __init__(self, db: Database):
        """Constructor method.

        :param db: A MongoDB database object.
        :type db: Database
        """
        super().__init__(db, db["user"])

    @property
    def _uc_mgr(self) -> _user_config.UserConfigManager:
        """Returns a user config manager.

        :return: A user config manager initialized in UserManager.
        :rtype: _user_config.UserConfigManager
        """
        return _user_config.UserConfigManager(self._db)

    def get_doc_by_id(self, _id: ObjectId) -> User | None:
        res = self._coll.find_one({"_id": _id})
        return User(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> User | None:
        res = self._coll.find_one(filter=kw)
        return User(**res) if res else None

    def get_docs(self, **filter) -> list[User]:
        res = self._coll.find(filter=filter)
        return [User(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> User:
        doc = User(_id=ObjectId(), **kw)
        self._coll.insert_one(asdict(doc))
        return doc

    def get_user(self, username: str) -> User:
        """Retrieve a user from the database.

        :param username: User username.
        :type username: str
        :raises UserNotExistsException: User with the given username was not found.
        :return: A found user object.
        :rtype: User
        """
        user = self.get_doc_by_filter(username=username, active=True)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exists.")
        return user

    @staticmethod
    def generate_password(len: int) -> str:
        """Generate a random password.

        :param len: The length of the final password.
        :type len: int
        :return: Generated password.
        :rtype: str
        """
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(len))
        return password

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Check if the password is strong enough.

        Strong password is at least 8 characters long, has at least one upper,
        lower character and a digit.

        :param password: Password to validate.
        :type passowrd: str
        :return: `True` if password meet all the criteria.
        :rtype: bool
        """
        return re.search(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).{8,}$", password) is not None

    @staticmethod
    def validate_username_format(username: str) -> bool:
        """Validate the username format.

        The username must not contain any special characters and has to be at least
        4 characters long.

        :param username: A username to validate.
        :type username: str
        :return: `True` if username meet all the criteria.
        :rtype: bool
        """
        return re.search(r"^[a-zA-Z0-9]{4,}$", username) is not None

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Calculates SHA256 hash of the given password.

        :param password: Base string from which the hash value is calculated.
        :type password: str
        :return: Generated hash digest.
        :rtype: str
        """
        hash_obj = hashlib.sha256(password.encode("utf-8"))
        return hash_obj.hexdigest()

    @staticmethod
    def _generate_shadow(username: str, password: str, shadow_path: str) -> str:
        """Generate a shadow hash.

        The function both calculates shadow hash and generated the shadow file.

        :param username: User username.
        :type username: str
        :param password: User password (NOT its hash digest).
        :type password: str
        :param shadow_path: Path to the destination file where the shadow file will be
            written.
        :type shadow_path: str
        :return: Calculated shadow hash.
        :rtype: str
        """
        crypt_hash = sha512_crypt.using(salt=username).hash(password)
        template = get_template(TEMPLATE_FILES["shadow"])
        with open(f"{shadow_path}", "w") as f:
            f.write(template.render(hash=crypt_hash))
        return crypt_hash

    def validate_user_login(self, username: str, password: str) -> bool:
        """Validate user credentials."""
        try:
            user = self.get_user(username)
        except UserNotExistsException:
            return False
        return user.password == self.get_password_hash(password)

    def change_password(self, username: str, password: str) -> User:
        """Change password for a user.

        Update password hash in the database and user's shadow file content.

        :param username: User username.
        :type username: str
        :param password: User password.
        :type password: str
        :raises UserNotExistsException: Given user could not be found in the database.
        :return: Updated `User` object.
        :rtype: User
        """
        user = self.get_user(username)

        # calculate and update hash for shadow
        log.info(f"Updating `{user.shadow_path}`")
        crypt_hash = self._generate_shadow(user.username, password, user.shadow_path)

        # calculate hash to store to the database
        user.password = self.get_password_hash(password)
        user.shadow_hash = crypt_hash

        self.update_doc(user)
        return user

    def create_new_user(
        self, username: str, password: str, shadow_dir: str, email: str = ""
    ) -> tuple[User, dict[str, str]]:
        """Create a new user.

        If user already exists function will return an instance of the old user
        account (searches by username).

        :param username: User's username.
        :type username: str
        :param password: User's password.
        :type password: str
        :param shadow_dir: Destination directory where a shadow file will be generated.
        :type shadow_dir: str
        :param email: User's email.
        :type email: str
        :raises DirNotExistsException: `shadow_dir` does not exists.
        :raises UserExistsException: A user with given `username` already exists.
        :return: Newly created user object.
        :rtype: User
        """
        user = self.get_doc_by_filter(username=username, active=True)
        if user:
            raise UserExistsException(f"User `{username}` already exists.")

        shadow_dirpath = Path(shadow_dir)

        if not os.path.isdir(shadow_dirpath):
            raise DirNotExistsException(f"Directory `{shadow_dir}` does not exists.")

        shadow_file = shadow_dirpath / username

        # generate shadow from file
        log.info(f"Generating `{str(shadow_file)}`")
        crypt_hash = self._generate_shadow(
            username, password, str(shadow_file.resolve())
        )

        user = User(
            _id=ObjectId(),
            username=username,
            password=self.get_password_hash(password),
            role=UserRole.USER,
            shadow_path=str(shadow_file.resolve()),
            shadow_hash=crypt_hash,
            email=email,
        )

        self.insert_doc(user)
        return user, {"username": username, "password": password}

    def create_multiple_users(
        self,
        lof_usernames: list[str],
        shadow_dir: str,
        default_password: str | None = None,
    ) -> dict[str, str]:
        """Generate new users from the given list of usernames.

        Ignores usernames that already has an account.

        :param lof_username: List of usernames.
        :type lof_username: list[str]
        :param shadow_dir: Path to a directory with shadow files.
        :type shadow_dir: str
        :return: Dictionary of usernames and passwords in raw format (not a hash).
        :rtype: dict[str, str]
        """
        # eliminate duplicates
        existing_users = [
            u["username"]
            for u in self.get_docs_raw(
                filter={"username": {"$in": lof_usernames}},
                projection={"_id": 0, "username": 1},
            )
        ]

        new_usernames = set(lof_usernames).difference(set(existing_users))
        password = (
            default_password
            if default_password is not None
            else self.generate_password(DEFAULT_PASSWORD_LENGTH)
        )
        # generate random passwords for each new user
        lof_user_info = {username: password for username in new_usernames}
        users = {}

        # create new users
        for username, password in lof_user_info.items():
            user, data = self.create_new_user(username, password, shadow_dir)
            users[user.username] = data

        return users

    def get_active_projects_for_user(self, username: str) -> list[_project.Project]:
        """Return list of projects that a user has enrolled to.

        :param username: User username.
        :type username: str
        :raises UserNotExistsException: Given user could not be found in the database.
        :return: A list of enrolled projects for the given user.
        :rtype: list[_project.Project]
        """
        user = self.get_user(username)

        uc_coll = _user_config.UserConfigManager(self._db).collection
        pipeline = [
            {
                # search only user_config for the given user
                "$match": {"user_id.$id": user.id}
            },
            {
                # get project info
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$project"
            },
            {"$project": {"project": 1, "_id": 0}},
        ]
        return [_project.Project(**i["project"]) for i in uc_coll.aggregate(pipeline)]

    def get_active_projects_for_user_raw(self, username: str) -> list[dict[str, Any]]:
        """Return list of projects that a user has enrolled to.

        The output of the function is in raw format
        :param username: User username.
        :type username: str
        :raises UserNotExistsException: Given user could not be found in the database.
        :return: A list of enrolled projects for the given user.
        :rtype: list[dict[str, Any]]
        """
        user = self.get_user(username)

        uc_coll = _user_config.UserConfigManager(self._db).collection
        project_pipeline = [
            {"$match": {"active": True}},
            {
                "$lookup": {
                    "from": "user_config",
                    "localField": "_id",
                    "foreignField": "project_id.$id",
                    "as": "user_configs",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {
                "$project": {
                    "name": 1,
                    "active": 1,
                    "max_nof_users": 1,
                    "active_users": {"$size": "$user_configs"},
                }
            },
        ]
        pipeline = [
            {
                # search only user_config for the given user
                "$match": {"user_id.$id": user.id, "active": True}
            },
            {
                # get project info
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": project_pipeline,
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$project"
            },
            {"$project": {"project": 1, "_id": 0}},
        ]
        return [i["project"] for i in uc_coll.aggregate(pipeline)]

    def delete_a_user(self, username: str):
        """Delete the given user.

        :param username: Account's username.
        :type username: str
        :raises UserNotExistsException: Given user could not be found in the database.
        """
        user = self.get_user(username)

        # stop instances
        lof_projects = self.get_active_projects_for_user(user.username)
        for project in lof_projects:
            self._uc_mgr.stop_user_instance(user, project)

        self._uc_mgr.cancel_user_enrollments_from_all_projects(user)

        # remove shadow file
        Path(user.shadow_path).unlink()

        user.active = False
        self.update_doc(user)

    def delete_users(self, lof_usernames: list[str]):
        """Deletes users from the list.

        :param lof_usernames: List of usernames to delete.
        :type lof_usernames: list[str]
        """

        users = self.get_docs(username={"$in": lof_usernames}, active=True)

        ids = [u.id for u in users]

        for user in users:
            projects = self.get_active_projects_for_user(user.username)
            for project in projects:
                self._uc_mgr.stop_user_instance(user, project)

            self._uc_mgr.cancel_user_enrollments_from_all_projects(user)

            # remove shadow file
            Path(user.shadow_path).unlink()

        self._coll.update_many({"_id": {"$in": ids}}, {"$set": {"active": False}})
