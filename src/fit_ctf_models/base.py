import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from bson import ObjectId
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from pymongo.database import Database

from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.types import PathDict

log = logging.getLogger()


class Base(ABC, BaseModel):
    """A base class that all entities derive from.

    :param _id: Object ID.
    :type _id: ObjectId
    :param active: Active status of the object. When an object is set as `False`, the
        object is considered as deleted and can be only used for displaying information.
    :type active: bool
    :param config: Some additional options that is used by the app but will not be
        stored in the database. Defaults to an empty dictionary.
    :type config:dict
    :type active: dict[str, str]
    """

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    active: bool = True

    def model_dump(self, by_alias: bool = True, **kw) -> dict[str, Any]:
        return super().model_dump(by_alias=by_alias, **kw)

    def validate_dict(self) -> dict[str, Any]:
        model = self.model_dump()
        model["_id"] = str(model["_id"])
        return model


T = TypeVar("T", bound=Base)


class BaseManagerInterface(ABC, Generic[T]):
    """A base manager class that all CTF managers derive from."""

    def __init__(
        self,
        db: Database,
        coll: Collection,
        c_client: type[ContainerClientInterface],
        paths: PathDict,
    ):
        """Constructor method.

        :param db: MongoDB database object.
        :type db: Database
        :param coll: MongoDB collection object.
        :type coll: Collection
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[ContainerClientInterface]
        :param path: A path to a directory where contents of <T> are stored.
        :type path: pathlib.Path
        """
        self._db = db
        self._coll = coll
        self.c_client = c_client
        self._paths = paths

    @property
    def collection(self) -> Collection:
        """Return collection of the manager.

        :return: Collection of the manager.
        :rtype: Collection
        """
        return self._coll

    @abstractmethod
    def get_doc_by_id(self, _id: ObjectId) -> T | None:  # pragma: no cover
        """Search for a document using ObjectId.

        :param _id: ID of the document.
        :type _id: ObjectId
        :return: A document object (subclass of `Base`) if found.
        :rtype: T | None
        """
        raise NotImplementedError()

    @abstractmethod
    def get_doc_by_id_raw(
        self, _id: ObjectId, projection: dict | None = None
    ):  # pragma: no cover
        """Search for a document using ObjectId in raw format.

        :param _id: ID of the document.
        :type _id: ObjectId
        :param projection: A projection query.
        :type projection: dict[str, Any] | None
        :return: Result of query.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_doc_by_filter(self, **kw) -> T | None:  # pragma: no cover
        """Search for a document with filter.

        :return: A document object (subclass of `Base`) if found.
        :rtype: T | None
        """
        raise NotImplementedError()

    @abstractmethod
    def get_doc_by_filter_raw(
        self, filter: dict | None = None, projection: dict | None = None
    ):
        """Search for a document with filter and project in raw format.

        :param filter: A filter query.
        :type filter: dict | None
        :param projection: A projection query.
        :type projection: dict | None
        :return: Result of query.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_docs(self, **filter) -> list[T]:  # pragma: no cover
        """Search for all documents using filter.

        :return: A list of found documents.
        :rtype: T | None.
        """
        raise NotImplementedError()

    @abstractmethod
    def create_and_insert_doc(self, **kw) -> T:  # pragma no cover
        """Insert a document of a given class.

        :return: A new document.
        :rtype: T
        """
        raise NotImplementedError()

    def get_docs_raw(self, filter: dict[str, Any], projection: dict[str, Any]) -> list:
        """Search for all documents using filter and return results in raw format.

        :param filter: A filter query.
        :type filter: dict[str, Any]
        :param projection: A projection query.
        :type projection: dict[str, Any]
        :return: List of found documents in raw format.
        :rtype: list
        """
        return [i for i in self._coll.find(filter=filter, projection=projection)]

    def insert_doc(self, doc: T):
        """Insert one document.

        :param doc: A document to insert into the database.
        :type doc: T
        """
        dict_obj = doc.model_dump()
        log.info(f"Inserting {dict_obj}")
        self._coll.insert_one(dict_obj)

    def update_doc(self, doc: T):
        """Update the whole document.

        :param doc: A new version of the document.
        :type doc: T
        """
        dict_obj = doc.model_dump()
        log.info(f"Updating {dict_obj}")
        self._coll.replace_one({"_id": doc.id}, dict_obj)

    def remove_doc_by_id(self, _id: ObjectId) -> bool:
        """Remove a document using ObjectId.

        :param _id: ID of a document to remove.
        :type _id: ObjectId

        :return: `True` if a document was found and successfully deleted.
        :rtype: bool
        """
        log.info(f"Deleting document `{_id}`")
        res = self._coll.delete_one({"_id": _id})
        return res.deleted_count > 0

    def remove_doc_by_filter(self, **filter) -> bool:
        """Remove a document using filter.

        :return: `True` if a document was found and successfully deleted.
        :rtype: bool
        """
        log.info(f"Deleting document using filter {filter}")
        res = self._coll.delete_one(filter=filter)
        return res.deleted_count > 0

    def remove_docs_by_id(self, ids: list[ObjectId]) -> int:
        """Remove multiple documents by ObjectIDs.

        :param ids: List of document IDs.
        :type ids: list[ObjectId]
        :return: Number of removed documents.
        :rtype: int
        """
        res = self._coll.delete_many({"_id": {"$in": ids}})
        return res.deleted_count

    def remove_docs_by_filter(self, **filter) -> int:
        """Remove multiple documents by filter.

        :return: Number of removed documents.
        :rtype: int
        """
        res = self._coll.delete_many(filter=filter)
        return res.deleted_count
