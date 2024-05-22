from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Generic, TypeVar

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

log = logging.getLogger()


@dataclass
class Base(object):
    _id: ObjectId

    @property
    def id(self) -> ObjectId:
        return self._id


T = TypeVar("T", bound=Base)


class BaseManager(ABC, Generic[T]):
    def __init__(self, db: Database, coll: Collection):
        """Manager constructor.

        Params:
            db (Database):     MongoDB database object.
            coll (Collection): MongoDB collection object.
        """
        self._db = db
        self._coll = coll

    @property
    def collection(self) -> Collection:
        return self._coll

    @abstractmethod
    def get_doc_by_id(self, _id: ObjectId) -> T | None:
        """Search for a document using ObjectId.

        Params:
            _id (ObjectId): ID of the document.

        Return:
            T | None: A document object (subclass of Base) if found.
        """
        pass

    @abstractmethod
    def get_doc_by_id_raw(self, _id: ObjectId):
        """Search for a document using ObjectId in raw format.

        Params:
            _id (ObjectId): ID of the document.

        Return:
            dict[str, Any]: Result of search.
        """
        pass

    @abstractmethod
    def get_doc_by_filter(self, **kw) -> T | None:
        """Search for a document with filter."""
        pass

    @abstractmethod
    def get_docs(self, **filter) -> list[T]:
        """Search for all documents using filter."""
        pass

    @abstractmethod
    def create_and_insert_doc(self, **kw) -> T:
        """Insert a document of a given class."""
        pass

    def get_docs_raw(self, filter: dict[str, Any], projection: dict[str, Any]) -> list:
        """Search for all documents using filter and return results in raw format."""
        return [i for i in self._coll.find(filter=filter, projection=projection)]

    def insert_doc(self, doc: T):
        """Insert one document."""
        log.info(f"Inserting {asdict(doc)}")
        self._coll.insert_one(asdict(doc))

    def update_doc(self, doc: T):
        """Update the whole document.

        Params:
            doc (T): A new version of the document.
        """
        log.info(f"Updating {asdict(doc)}")
        self._coll.replace_one({"_id": doc._id}, asdict(doc))

    def remove_doc_by_id(self, _id: ObjectId) -> bool:
        """Remove a document using ObjectId.

        Params:
            _id (ObjectId): ID of a document to remove.

        Return:
            bool: `True` if a document was found and successfully deleted.
        """
        log.info(f"Deleting document `{_id}`")
        res = self._coll.delete_one({"_id": _id})
        return res.deleted_count > 0

    def remove_doc_by_filter(self, **filter) -> bool:
        """Remove a document using filter.

        Return:
            bool: `True` if a document was found and successfully deleted.
        """
        log.info(f"Deleting document using filter {filter}")
        res = self._coll.delete_one(filter=filter)
        return res.deleted_count > 0

    def remove_docs_by_id(self, ids: list[ObjectId]) -> int:
        res = self._coll.delete_many({"_id": {"$in": ids}})
        return res.deleted_count

    def remove_docs_by_filter(self, **filter) -> int:
        res = self._coll.delete_many(filter=filter)
        return res.deleted_count
