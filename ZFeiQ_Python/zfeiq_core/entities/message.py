from pydantic import BaseModel
from typing import Optional
import time


class Message(BaseModel):
    id: Optional[int] = None
    from_user: str
    to: str
    text: str
    ts: float = time.time()
    # optional: file_offer_id etc.
