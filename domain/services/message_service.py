from datetime import datetime
from typing import Optional

from ..entities.message import MessageEntity
from ..repositories.message_repository import MessageRepository


class MessageService:
    def __init__(self, repository: Optional[MessageRepository] = None):
        self.repository = repository or MessageRepository()

    def add_message(
        self,
        platform: str,
        platform_message_id: int,
        text: str,
        chat_id: int,
        from_user: str,
        to_user: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_text: Optional[str] = None,
        message_type: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> bool:
        entity = MessageEntity(
            platform=platform,
            platform_message_id=platform_message_id,
            text=text,
            chat_id=chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type=message_type,
            created_at=created_at or datetime.now(),
        )

        try:
            self.repository.create_message(entity)
            return True
        except Exception:
            return False

    def get_message(self, message_id: int) -> Optional[MessageEntity]:
        message = self.repository.get_by_id(message_id)
        if message:
            return MessageEntity(
                platform=message.platform,
                platform_message_id=message.platform_message_id,
                text=message.text,
                chat_id=message.chat_id,
                from_user=message.from_user,
                to_user=message.to_user,
                reply_to_message_id=message.reply_to_message_id,
                reply_text=message.reply_text,
                message_type=message.message_type,
                created_at=message.created_at,
            )
        return None

    def get_last_messages(
        self,
        chat_id: int,
        platform: str = "telegram",
        limit: int = 5,
        from_users: Optional[list[str]] = None,
    ) -> list[MessageEntity]:
        messages = self.repository.get_last_messages(
            chat_id=chat_id, platform=platform, limit=limit, from_users=from_users
        )

        return [
            MessageEntity(
                platform=msg.platform,
                platform_message_id=msg.platform_message_id,
                text=msg.text,
                chat_id=msg.chat_id,
                from_user=msg.from_user,
                to_user=msg.to_user,
                reply_to_message_id=msg.reply_to_message_id,
                reply_text=msg.reply_text,
                message_type=msg.message_type,
                created_at=msg.created_at,
            )
            for msg in messages
        ]

    def get_last_message_by_type(
        self, chat_id: int, message_type: str, platform: str = "telegram"
    ) -> Optional[MessageEntity]:
        message = self.repository.get_last_message_by_type(
            chat_id=chat_id, message_type=message_type, platform=platform
        )

        if message:
            return MessageEntity(
                platform=message.platform,
                platform_message_id=message.platform_message_id,
                text=message.text,
                chat_id=message.chat_id,
                from_user=message.from_user,
                to_user=message.to_user,
                reply_to_message_id=message.reply_to_message_id,
                reply_text=message.reply_text,
                message_type=message.message_type,
                created_at=message.created_at,
            )
        return None

    def update_message_text(
        self, platform_message_id: int, text: str, platform: str = "telegram"
    ) -> bool:
        return self.repository.update_message_text(
            platform_message_id=platform_message_id, text=text, platform=platform
        )

    def add_telegram_message(
        self,
        telegram_message_id: int,
        text: str,
        chat_id: int,
        from_user: str,
        to_user: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_text: Optional[str] = None,
        message_type: Optional[str] = None,
    ) -> bool:
        return self.add_message(
            platform="telegram",
            platform_message_id=telegram_message_id,
            text=text,
            chat_id=chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type=message_type,
        )

    def add_discord_message(
        self,
        discord_message_id: int,
        text: str,
        chat_id: int,
        from_user: str,
        to_user: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_text: Optional[str] = None,
        message_type: Optional[str] = None,
    ) -> bool:
        return self.add_message(
            platform="discord",
            platform_message_id=discord_message_id,
            text=text,
            chat_id=chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type=message_type,
        )
