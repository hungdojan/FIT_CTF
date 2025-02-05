from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from bson import DBRef, ObjectId


@dataclass
class UserProgress:
    _id: ObjectId
    user_id: DBRef
    project_id: DBRef
    flags: dict[str, datetime] = field(default_factory=dict)
