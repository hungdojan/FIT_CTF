import logging
import shutil
from typing import Any

from bson import ObjectId
from passlib.hash import sha512_crypt
from pymongo.database import Database

import fit_ctf_models.user_enrollment as _ue
from fit_ctf_models.base import Base, BaseManagerInterface
from fit_ctf_templates import JINJA_TEMPLATE_DIRPATHS, get_template
from fit_ctf_utils.auth.auth_interface import AuthInterface
from fit_ctf_utils.auth.local_auth import LocalAuth
from fit_ctf_utils.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.exceptions import (
    ComposeFileNotExist,
    ShadowPathNotExistException,
    UserExistsException,
    UserNotExistsException,
)
from fit_ctf_utils.mongo_queries import MongoQueries
from fit_ctf_utils.types import PathDict, UserRole

log = logging.getLogger()
log.disabled = False


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
    email: str = ""


class UserManager(BaseManagerInterface[User]):
    """A manager class that handles operations with `User` objects."""

    def __init__(
        self, db: Database, c_client: type[ContainerClientInterface], paths: PathDict
    ):
        """Constructor method.

        :param db: A MongoDB database object.
        :type db: Database
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[ContainerClientInterface]
        :param paths: A list of content paths.
        :type paths: PathDict
        """
        super().__init__(db, db["user"], c_client, paths)

    @property
    def _ue_mgr(self) -> "_ue.UserEnrollmentManager":
        """Returns a user enroll manager.

        :return: A user enrollment manager initialized in UserManager.
        :rtype: user_enrollment.UserEnrollmentManager
        """
        return _ue.UserEnrollmentManager(self._db, self.c_client, self._paths)

    def get_doc_by_id(self, _id: ObjectId) -> User | None:
        res = self._coll.find_one({"_id": _id})
        return User(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId, projection: dict | None = None):
        projection = {} if projection is None else projection
        return self._coll.find_one({"_id": _id}, projection=projection)

    def get_doc_by_filter(self, **kw) -> User | None:
        res = self._coll.find_one(filter=kw)
        return User(**res) if res else None

    def get_doc_by_filter_raw(
        self, filter: dict | None = None, projection: dict | None = None
    ):
        filter = {} if filter is None else filter
        projection = {} if projection is None else projection
        res = self._coll.find_one(filter=filter, projection=projection)
        return User(**res) if res else None

    def get_docs(self, **filter) -> list[User]:
        res = self._coll.find(filter=filter)
        return [User(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> User:
        doc = User(**kw)
        self._coll.insert_one(doc.model_dump())
        return doc

    def get_user(self, user_or_username: str | User, active: bool = True) -> User:
        """Retrieve a user from the database.

        :param user_or_username: User username or user object.
        :type user_or_username: str | User
        :param active: The document is valid and still in use. Defaults to True
        :type active: bool
        :raises UserNotExistsException: User with the given username was not found.
        :return: A found user object.
        :rtype: User
        """
        if isinstance(user_or_username, User):
            return user_or_username
        username = user_or_username
        user = self.get_doc_by_filter(username=username, active=active)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exists.")
        return user

    def get_user_raw(self, user_or_username: str | User) -> dict:
        """Return a dictionary of a user object.

        :param user_or_username: A username or a User object.
        :type user_or_username: str | User
        :return: A user object in dict format.
        :rtype: dict
        """
        user = self.get_user(user_or_username)
        user = user.model_dump()
        user.pop("password", "")
        user.pop("_id", "")
        return user

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
        template = get_template("shadow.j2", str(JINJA_TEMPLATE_DIRPATHS["v1"]))
        with open(f"{shadow_path}", "w") as f:
            f.write(template.render(hash=crypt_hash))
        return crypt_hash

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
        shadow_path = self._paths["users"] / user.username / "shadow"
        if not shadow_path.exists():
            raise ShadowPathNotExistException(
                f"Could not locate shadow file of the user `{user.username}`."
            )

        # calculate and update hash for shadow
        log.info(f"Updating `{shadow_path.resolve()}`")
        self._generate_shadow(user.username, password, str(shadow_path.resolve()))

        # calculate hash to store to the database
        user.password = LocalAuth(self).get_password_hash(password)

        self.update_doc(user)
        return user

    def create_new_user(
        self,
        username: str,
        password: str,
        role: UserRole = UserRole.USER,
        email: str = "",
        **kw,
    ) -> tuple[User, dict[str, str]]:
        """Create a new user.

        If user already exists function will raise an exception.

        :param username: User's username.
        :type username: str
        :param password: User's password.
        :type password: str
        :param role: User's role.
        :type role: UserRole
        :param email: User's email.
        :type email: str
        :raises UserExistsException: A user with given `username` already exists.
        :return: Newly created user object and a directory containing
            `username` and `password` in plain-text format.
        :rtype: tuple[User, dict[str, str]]
        """
        # TODO: activate inactive user
        user = self.get_doc_by_filter(username=username, active=True)
        if user:
            raise UserExistsException(f"User `{username}` already exists.")

        root_dir = self._paths["users"] / username
        root_dir.mkdir(parents=True)
        shadow_file = root_dir / "shadow"
        (root_dir / "home").mkdir(parents=True, mode=0o777)

        # generate shadow from file
        log.info(f"Generating `{str(shadow_file.resolve())}`")
        self._generate_shadow(username, password, str(shadow_file.resolve()))

        user = self.create_and_insert_doc(
            username=username,
            password=AuthInterface.get_password_hash(password),
            role=role,
            email=email,
        )
        return user, {username: password}

    def create_multiple_users(
        self,
        lof_usernames: list[str],
        default_password: str | None = None,
    ) -> dict[str, str]:
        """Generate new users from the given list of usernames.

        Ignores usernames that already has an account.

        :param lof_username: List of usernames.
        :type lof_username: list[str]
        :param default_password: A default password that will be set to all new users.
            If set to None, the password will be randomly generated. Defaults to None.
        :type default_password: str | None
        :return: Dictionary of usernames and passwords in plain-text format (not a hash).
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
            else AuthInterface.generate_password(DEFAULT_PASSWORD_LENGTH)
        )
        # generate random passwords for each new user
        lof_user_info = {username: password for username in new_usernames}
        users = {}

        # create new users
        for username, password in lof_user_info.items():
            user, data = self.create_new_user(username, password)
            users[user.username] = data[user.username]

        return users

    def get_list_users_raw(self, _all: bool) -> list[dict]:
        """Get a list of user in raw data.

        :param _all: If set to True it displays all users (including inactive).
        :type _all: bool
        :return: A list of user data in dictionary.
        :rtype: list[dict]
        """
        filter = {} if _all else {"active": True}
        users = self.get_docs_raw(filter, {"password": 0})
        return users

    def get_users(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        """Get list of all users.

        Creates a query that look up all users in the database and their assigned project
        names.

        The final directory has the following format:
        {
            "name": <username>,
            "projects": [
                {"name": <project1_name>},
                {"name": <project2_name>},
                ...
            ],
            "active": <active_state>
        }

        :param include_inactive: When set to `True`, the query result will also
            include inactive users.
        :type include_inactive: bool
        :return: A list of users with aditional information.
        :rtype: list[dict[str, Any]]
        """
        pipeline = MongoQueries.user_get_users(include_inactive)
        return [i for i in self.collection.aggregate(pipeline)]

    def disable_user(self, username: str):
        """Set user as inactive in the database.

        The user data and files will be preserve for future references.
        :param username: User's username.
        :type username: str
        """
        user = self.get_user(username)

        lof_projects = self._ue_mgr.get_enrolled_projects(user.username)
        for project in lof_projects:
            try:
                self._ue_mgr.stop_user_cluster(user, project)
            except ComposeFileNotExist:
                continue

        self._ue_mgr.cancel_user_from_all_projects(user)
        user.active = False
        self.update_doc(user)

    def flush_user(self, username: str):
        """Completely remove user data from the host machine.

        Only works if the user is not active.
        :param username: User's username.
        :type username: str
        """
        user = self.get_doc_by_filter(username=username, active=True)
        if user:
            raise UserExistsException("Cannot flush files of an active user.")

        path = self._paths["users"] / username
        if path.exists():
            shutil.rmtree(path)

    def delete_a_user(self, username: str):
        """Completely remove user from the host machine.

        :param username: Account's username.
        :type username: str
        :raises UserNotExistsException: Given user could not be found in the database.
        """
        user = self.get_user(username)
        self.disable_user(username)
        self.flush_user(username)
        self.remove_doc_by_id(user.id)

    def delete_users(self, lof_usernames: list[str]):
        """Deletes users from the list.

        :param lof_usernames: List of usernames to delete.
        :type lof_usernames: list[str]
        """

        users = self.get_docs(username={"$in": list(lof_usernames)}, active=True)

        ids = [u.id for u in users]

        for user in users:
            self.disable_user(user.username)
            self.flush_user(user.username)

        self.remove_docs_by_id(ids)

    def delete_all(self):
        """Remove all users from the host system and clear the database."""

        users = [u["username"] for u in self.get_users()]
        self.delete_users(users)
