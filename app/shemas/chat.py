from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ChatSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='forbid')

    id: int
    telegram_id: int
    title: str
    language: str
    is_active: bool
    is_approved: bool
    to_send_summary: bool
    created_at: datetime