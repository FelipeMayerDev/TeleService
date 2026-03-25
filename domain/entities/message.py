from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MessageEntity:
    platform: str
    platform_message_id: int
    text: str
    chat_id: int
    from_user: str
    to_user: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    reply_text: Optional[str] = None
    message_type: Optional[str] = None
    created_at: Optional[datetime] = None

    def with_created_at(self, created_at: datetime) -> "MessageEntity":
        return MessageEntity(
            platform=self.platform,
            platform_message_id=self.platform_message_id,
            text=self.text,
            chat_id=self.chat_id,
            from_user=self.from_user,
            to_user=self.to_user,
            reply_to_message_id=self.reply_to_message_id,
            reply_text=self.reply_text,
            message_type=self.message_type,
            created_at=created_at,
        )
