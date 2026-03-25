import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Set

from telegram import Bot

from domain import MessageService
from shared import edit_telegram_message, send_telegram_message

message_service = MessageService()

logger = logging.getLogger(__name__)


@dataclass
class VoiceStateHandler:
    cooldown: int = 5
    bot: Optional[Bot] = None
    telegram_chat_id: Optional[int] = None
    ignored_bot_names: Set[str] = field(default_factory=set)

    _pending_changes: dict = field(
        default_factory=lambda: {"joined": set(), "left": set()}
    )
    _timer_task: Optional[asyncio.Task] = None
    _voice_channel_before: Optional[object] = None
    _voice_channel_after: Optional[object] = None

    async def handle_voice_state(self, member, before, after) -> None:
        if member.bot:
            return

        if member.display_name in self.ignored_bot_names:
            logger.debug(f"Ignoring music bot: {member.display_name}")
            return

        is_in_voice_before = before.channel is not None
        is_in_voice_after = after.channel is not None

        self._voice_channel_before = before.channel
        self._voice_channel_after = after.channel

        if not is_in_voice_before and is_in_voice_after:
            self._pending_changes["joined"].add(member.display_name)
            logger.debug(f"{member.display_name} joined voice")
        elif is_in_voice_before and not is_in_voice_after:
            self._pending_changes["left"].add(member.display_name)
            logger.debug(f"{member.display_name} left voice")
        else:
            return

        await self._schedule_notification()

    async def _schedule_notification(self) -> None:
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()

        self._timer_task = asyncio.create_task(self._wait_and_notify())

    async def _wait_and_notify(self) -> None:
        await asyncio.sleep(self.cooldown)

        if not self._pending_changes["joined"] and not self._pending_changes["left"]:
            return

        await self._send_notification()

    async def _send_notification(self) -> None:
        text = self._format_message()

        if not text:
            self._clear_pending_changes()
            return

        last_message_id = await self._get_last_voice_state_message_id()

        if last_message_id and await self._is_message_in_last_5(last_message_id):
            edited = await self._edit_last_message(last_message_id, text)
            if edited:
                self._clear_pending_changes()
                return

        await self._send_new_message(text)
        self._clear_pending_changes()

    def _format_message(self) -> str:
        lines = []

        if self._pending_changes["joined"]:
            names = ", ".join(sorted(self._pending_changes["joined"]))
            prefix = (
                "entrou" if len(self._pending_changes["joined"]) == 1 else "entraram"
            )
            lines.append(f"{names} {prefix} no Discord")

        if self._pending_changes["left"]:
            names = ", ".join(sorted(self._pending_changes["left"]))
            prefix = "saiu" if len(self._pending_changes["left"]) == 1 else "saíram"
            lines.append(f"{names} {prefix} do Discord")

        if lines:
            lines.append("")

        online_users = self._get_online_users()
        if online_users:
            lines.append("Usuários online:")
            for user in sorted(online_users):
                lines.append(f"- {user}")
        else:
            lines.append("Não há usuários online")

        return "\n".join(lines)

    def _get_online_users(self) -> Set[str]:
        channel = self._voice_channel_after or self._voice_channel_before
        if not channel or not hasattr(channel, "members"):
            return set()

        online_users = set()
        for member in channel.members:
            if member.bot:
                continue
            if member.display_name in self.ignored_bot_names:
                continue
            online_users.add(member.display_name)

        return online_users

    async def _get_last_voice_state_message_id(self) -> Optional[int]:
        if self.telegram_chat_id is None:
            return None

        try:
            msg = message_service.get_last_message_by_type(
                chat_id=self.telegram_chat_id,
                message_type="voice_state",
                platform="telegram",
            )

            return msg.platform_message_id if msg else None
        except Exception as e:
            logger.error(f"Error getting last voice state message: {e}")
            return None

    async def _is_message_in_last_5(self, message_id: int) -> bool:
        if self.telegram_chat_id is None:
            return False

        try:
            last_5_messages = message_service.get_last_messages(
                chat_id=self.telegram_chat_id,
                platform="telegram",
                limit=5,
                from_users=["System", "Discord"],
            )

            for msg in last_5_messages:
                if msg.platform_message_id == message_id:
                    return True

            logger.info(f"Message {message_id} not in last 5 bot messages of the chat")
            return False
        except Exception as e:
            logger.error(f"Error checking if message is in last 5: {e}")
            return False

    async def _edit_last_message(self, message_id: int, text: str) -> bool:
        if self.bot is None or self.telegram_chat_id is None:
            return False

        try:
            success = await edit_telegram_message(
                token=self.bot.token,
                chat_id=str(self.telegram_chat_id),
                message_id=message_id,
                text=text,
            )
            if success:
                self._update_message_in_db(message_id, text)
            return success
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return False

    async def _send_new_message(self, text: str) -> None:
        if self.bot is None or self.telegram_chat_id is None:
            return

        try:
            result = await send_telegram_message(
                token=self.bot.token,
                chat_id=str(self.telegram_chat_id),
                text=text,
                save_to_db=True,
                message_type="voice_state",
            )

            if result:
                message_id, chat_id = result
        except Exception as e:
            logger.error(f"Error sending new message: {e}")

    def _update_message_in_db(self, message_id: int, text: str) -> None:
        try:
            updated = message_service.update_message_text(
                platform_message_id=message_id,
                text=text,
                platform="telegram",
            )
            if updated:
                logger.debug(f"Updated message {message_id} in database")
            else:
                logger.warning(f"Message {message_id} not found in database")
        except Exception as e:
            logger.warning(f"Error updating message {message_id}: {e}")

    def _save_message_to_db(self, message_id: int, chat_id: int, text: str) -> None:
        try:
            message_service.add_telegram_message(
                telegram_message_id=message_id,
                text=text,
                chat_id=chat_id,
                from_user="Discord",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type="voice_state",
            )
        except Exception as e:
            logger.error(f"Error saving message to database: {e}")

    def _clear_pending_changes(self) -> None:
        self._pending_changes["joined"].clear()
        self._pending_changes["left"].clear()
