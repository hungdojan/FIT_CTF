from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Generic, TypeVar

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient

log = logging.getLogger()


@dataclass
class Base(object):
    """A base class that all entities derive from.

    :param _id: Object ID.
    :type _id: ObjectId
    :param active: Active status of the object. When an object is set as `False`, the
        object is considered as deleted and can be only used for displaying information.
    :type active: bool
    """

    _id: ObjectId
    active: bool = field(default=True)

    @property
    def id(self) -> ObjectId:
        return self._id


T = TypeVar("T", bound=Base)


class BaseManager(ABC, Generic[T]):
    """A base manager class that all CTF managers derive from."""

    def __init__(
        self, db: Database, coll: Collection, c_client: type[BaseContainerClient]
    ):
        """Constructor method.

        :param db: MongoDB database object.
        :type db: Database
        :param coll: MongoDB collection object.
        :type coll: Collection
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[BaseContainerClient]
        """
        self._db = db
        self._coll = coll
        self.c_client = c_client

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
        pass

    @abstractmethod
    def get_doc_by_id_raw(self, _id: ObjectId):  # pragma: no cover
        """Search for a document using ObjectId in raw format.

        :param _id: ID of the document.
        :type _id: ObjectId
        :return: Result of query.
        """
        pass

    @abstractmethod
    def get_doc_by_filter(self, **kw) -> T | None:  # pragma: no cover
        """Search for a document with filter.

        :return: A document object (subclass of `Base`) if found.
        :rtype: T | None
        """
        pass

    @abstractmethod
    def get_docs(self, **filter) -> list[T]:  # pragma: no cover
        """Search for all documents using filter.

        :return: A list of found documents.
        :rtype: T | None.
        """
        pass

    @abstractmethod
    def create_and_insert_doc(self, **kw) -> T:  # pragma no cover
        """Insert a document of a given class.

        :return: A new document.
        :rtype: T
        """
        pass

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
        log.info(f"Inserting {asdict(doc)}")
        self._coll.insert_one(asdict(doc))

    def update_doc(self, doc: T):
        """Update the whole document.

        :param doc: A new version of the document.
        :type doc: T
        """
        log.info(f"Updating {asdict(doc)}")
        self._coll.replace_one({"_id": doc._id}, asdict(doc))

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
