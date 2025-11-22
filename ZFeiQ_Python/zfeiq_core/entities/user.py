from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    username: str
    ip: str
    hostname: Optional[str] = None
    status: Optional[str] = "online"
    is_local: bool = False
