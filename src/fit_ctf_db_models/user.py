from __future__ import annotations
import fit_ctf_db_models.project as _project
import fit_ctf_db_models.user_config as _user_config
import hashlib
import logging
import os
import re
import secrets
import string
import subprocess

from bson import ObjectId
from dataclasses import asdict, dataclass
from enum import Enum
from fit_ctf_backend import (
    ProjectNotExistsException,
    UserNotExistsException,
    DirNotExistsException,
    CONFIG_PATH,
    TEMPLATE_FILES,
    DEFAULT_PASSWORD_LENGTH,
    get_template,
)
from fit_ctf_db_models.base import Base, BaseManager
from passlib.hash import sha512_crypt
from pymongo.database import Database
from typing import Any

log = logging.getLogger()
log.disabled = False


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


@dataclass
class User(Base):
    username: str
    password: str
    role: UserRole
    shadow_path: str
    shadow_hash: str = ""
    email: str = ""


    def start(self) -> subprocess.CompletedProcess:
        raise NotImplemented()

    def stop(self) -> subprocess.CompletedProcess:
        raise NotImplemented()

    def is_running(self) -> subprocess.CompletedProcess:
        raise NotImplemented()


class UserManager(BaseManager[User]):
    def __init__(self, db: Database):
        super().__init__(db, db["user"])

    def get_doc_by_id(self, _id: ObjectId) -> User | None:
        res = self._coll.find_one({"_id": _id})
        return User(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> User | None:
        res = self._coll.find_one(filter=kw)
        return User(**res) if res else None

    def get_docs(self, filter: dict[str, Any]) -> list[User]:
        res = self._coll.find(filter=filter)
        return [User(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> User:
        doc = User(_id=ObjectId(), **kw)
        self._coll.insert_one(asdict(doc))
        return doc

    @staticmethod
    def generate_password(len: int) -> str:
        """Generate a random password.

        Params:
            len (int): Number of characters.

        Return:
            str: Generated password.
        """
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(len))
        return password

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Check if the password is strong enough.

        Strong password is at least 8 characters long, has at least one upper,
        lower character and a digit.

        Params:
            password (str): Password to check.

        Return:
            bool: `True` if password met all the criteria.
        """
        return (
            len(password) >= 8
            and re.search(r"[a-z]", password) is not None
            and re.search(r"[A-Z]", password) is not None
            and re.search(r"[0-9]", password) is not None
        )

    @staticmethod
    def validate_username_format(username: str) -> bool:
        raise NotImplemented()

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Calculates SHA256 hash of the given password."""
        hash_obj = hashlib.sha256(password.encode("utf-8"))
        return hash_obj.hexdigest()

    def validate_user_login(self, username: str, password: str) -> bool:
        """Validate user credentials."""
        user = self.get_doc_by_filter(username=username)
        # user not found
        if not user:
            return False
        return user.password == self.get_password_hash(password)

    def change_password(self, username: str, password: str) -> User:
        """Change password for a user.

        Update password hash in the database and user's shadow file content.

        Params:
            username (str): User's username.
            password (str): User's password.

        Raises:
            UserNotFound: Given user could not be found in the database.

        Return:
            User: Updated `User` object.
        """
        user = self.get_doc_by_filter(username=username)
        if not user:
            raise UserNotExistsException(f"User `{username}` not found in the database")

        # calculate and update hash for shadow
        log.info(f"Updating `{user.shadow_path}`")
        crypt_hash = sha512_crypt.using(salt="randomText").hash(password)
        template = get_template(TEMPLATE_FILES["shadow"], f"{CONFIG_PATH}/templates")
        with open(f"{user.shadow_path}", "w") as f:
            f.write(template.render(user={"name": "student", "hash": crypt_hash}))

        # calculate hash to store to the database
        user.password = self.get_password_hash(password)
        user.shadow_hash = crypt_hash

        self.update_doc(user)
        return user

    def create_new_user(self, username: str, password: str, shadow_dir: str) -> User:
        """Create a new user.

        If user already exists function will return an instance of the old user
        account (searches by username).

        Params:
            username (str): User's username.
            password (str): User's password.
            shadow_dir (str): Destination directory where a shadow file will be generated.

        Raises:
            DirNotExistsException: `shadow_dir` does not exists.

        Return:
            User: Newly created user object.
        """
        user = self.get_doc_by_filter(username=username)
        if user:
            return user

        if not os.path.isdir(shadow_dir):
            raise DirNotExistsException("Directory `{shadow_dir}` does not exists.")

        # generate shadow from file
        log.info(f"Generating `{shadow_dir}{username}`")
        template = get_template(TEMPLATE_FILES["shadow"], f"{CONFIG_PATH}/templates")
        shadow_dir += "/" if not shadow_dir.endswith("/") else ""
        crypt_hash = sha512_crypt.using(salt=username).hash(password)
        with open(f"{shadow_dir}{username}", "w") as f:
            f.write(template.render(user={"name": "student", "hash": crypt_hash}))

        user = User(
            _id=ObjectId(),
            username=username,
            password=self.get_password_hash(password),
            role=UserRole.USER,
            shadow_path=f"{shadow_dir}{username}",
            shadow_hash=crypt_hash,
        )

        self.insert_doc(user)
        return user

    def start_user_instance(self, username: str, project_name: str):
        user = self.get_doc_by_filter(username=username)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exists.")

        project = _project.ProjectManager(self._db).get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"User `{username}` does not exists.")
        raise NotImplemented()

    def get_active_projects_for_user(self, username: str) -> list[_project.Project]:
        """Return list of projects that a user is assigned to."""
        user = self.get_doc_by_filter(username=username)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exists.")

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

    def generate_users(
        self, lof_usernames: list[str], shadow_dir: str, default_password: str = ""
    ) -> dict[str, str]:
        """Generate new users from the given list of usernames.

        Ignores usernames that already has an account.

        Params:
            lof_username (list[str]): List of usernames.
            shadow_dir (str): Path to a directory with shadow files.

        Return:
            dict[str, str]: Dictionary of usernames and passwords
                            in raw format (not a hash).
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
            if default_password
            else self.generate_password(DEFAULT_PASSWORD_LENGTH)
        )
        # generate random passwords for each new user
        users = {username: password for username in new_usernames}

        # create new users
        for username, password in users.items():
            self.create_new_user(username, password, shadow_dir)

        return users

    def delete_users(self, lof_usernames: list[str]) -> int:
        """Deletes users from the list.

        Params:
            lof_usernames (list[str]): List of usernames to delete.

        Return:
            int: Number of deleted users.
        """
        users = self.get_docs(
            filter={"username": {"$in": lof_usernames}}
        )

        ids = [u.id for u in users]

        for u in users:
            projects = self.get_active_projects_for_user(u.username)
            volume_dirs = [p.volume_mount_root_dir for p in projects]
            log.debug(f"Deleting `{u.shadow_path}`")
            # os.remove(u.shadow_path)
            for d in volume_dirs:
                d += "/" if not d.endswith("/") else ""
                if os.path.isdir(f"{d}{u.username}"):
                    # os.remove(f"{d}{u.username}")
                    pass

        return self.remove_docs_by_id(ids)
