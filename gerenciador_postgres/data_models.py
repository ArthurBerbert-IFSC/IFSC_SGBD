from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    username: str
    oid: int
    valid_until: Optional[datetime]
    can_login: bool

@dataclass
class Group:
    group_name: str
    oid: int
