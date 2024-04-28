from __future__ import annotations
from bson import ObjectId, DBRef
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class UserProgress:
    _id: ObjectId
    user_id: DBRef
    project_id: DBRef
    flags: dict[str, datetime] = field(default_factory=dict)

