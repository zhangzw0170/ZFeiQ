from pydantic import BaseModel
from typing import Optional


class FileOffer(BaseModel):
    id: Optional[int] = None
    filename: str
    size: int
    from_user: str
    to: str
    ts: float = 0.0
