from typing import Optional

from ..models import Message
from ..entities.message import MessageEntity
from .base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self):
        super().__init__(Message)

    def get_by_platform_message_id(
        self, platform_message_id: int, platform: str = "telegram"
    ) -> Optional[Message]:
        try:
            return self.model.get(
                (self.model.platform_message_id == platform_message_id)
                & (self.model.platform == platform)
            )
        except Message.DoesNotExist:
            return None

    def create_message(self, entity: MessageEntity) -> Message:
        return self.create(
            platform=entity.platform,
            platform_message_id=entity.platform_message_id,
            text=entity.text,
            chat_id=entity.chat_id,
            from_user=entity.from_user,
            to_user=entity.to_user,
            reply_to_message_id=entity.reply_to_message_id,
            reply_text=entity.reply_text,
            message_type=entity.message_type,
            created_at=entity.created_at,
        )

    def get_last_messages(
        self,
        chat_id: int,
        platform: str = "telegram",
        limit: int = 5,
        from_users: Optional[list[str]] = None,
    ) -> list[Message]:
        query = self.model.select().where(
            (self.model.chat_id == chat_id) & (self.model.platform == platform)
        )

        if from_users:
            query = query.where(self.model.from_user.in_(from_users))

        return list(query.order_by(self.model.created_at.desc()).limit(limit))

    def get_last_message_by_type(
        self, chat_id: int, message_type: str, platform: str = "telegram"
    ) -> Optional[Message]:
        try:
            return (
                self.model.select()
                .where(
                    (self.model.chat_id == chat_id)
                    & (self.model.platform == platform)
                    & (self.model.message_type == message_type)
                )
                .order_by(self.model.created_at.desc())
                .first()
            )
        except Message.DoesNotExist:
            return None

    def update_message_text(
        self, platform_message_id: int, text: str, platform: str = "telegram"
    ) -> bool:
        message = self.get_by_platform_message_id(platform_message_id, platform)
        if message:
            self.update(message, text=text)
            return True
        return False
