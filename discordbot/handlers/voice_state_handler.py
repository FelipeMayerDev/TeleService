import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Set

from peewee import DoesNotExist
from telegram import Bot

from database.models import Message
from shared import edit_telegram_message, send_telegram_message

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
    _last_message_ids: List[int] = field(default_factory=list)

    async def handle_voice_state(self, member, before, after) -> None:
        if member.bot:
            return

        if member.display_name in self.ignored_bot_names:
            logger.debug(f"Ignoring music bot: {member.display_name}")
            return

        is_in_voice_before = before.channel is not None
        is_in_voice_after = after.channel is not None

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

        if last_message_id:
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
                "Entrou" if len(self._pending_changes["joined"]) == 1 else "Entraram"
            )
            lines.append(f"• {names} {prefix} no Discord")

        if self._pending_changes["left"]:
            names = ", ".join(sorted(self._pending_changes["left"]))
            prefix = "Saiu" if len(self._pending_changes["left"]) == 1 else "Saíram"
            lines.append(f"• {names} {prefix} do Discord")

        return "\n".join(lines)

    async def _get_last_voice_state_message_id(self) -> Optional[int]:
        if self.telegram_chat_id is None:
            return None

        try:
            messages = (
                Message.select()
                .where(
                    (Message.chat_id == self.telegram_chat_id)
                    & (Message.message_type == "voice_state")
                )
                .order_by(Message.created_at.desc())
                .limit(3)
            )

            for msg in messages:
                if msg.telegram_message_id in self._last_message_ids:
                    return msg.telegram_message_id

            return None
        except Exception as e:
            logger.error(f"Error getting last voice state message: {e}")
            return None

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
            )

            if result:
                message_id, chat_id = result
                self._last_message_ids.append(message_id)
                if len(self._last_message_ids) > 3:
                    self._last_message_ids.pop(0)

                self._save_message_to_db(message_id, chat_id, text)
        except Exception as e:
            logger.error(f"Error sending new message: {e}")

    def _update_message_in_db(self, message_id: int, text: str) -> None:
        try:
            msg = Message.get(Message.telegram_message_id == message_id)
            msg.text = text
            msg.save()
            logger.debug(f"Updated message {message_id} in database")
        except DoesNotExist:
            logger.warning(f"Message {message_id} not found in database")
        except Exception as e:
            logger.error(f"Error updating message in database: {e}")

    def _save_message_to_db(self, message_id: int, chat_id: int, text: str) -> None:
        try:
            Message.create(
                telegram_message_id=message_id,
                text=text,
                chat_id=chat_id,
                from_user="Discord",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type="voice_state",
            )
            logger.debug(f"Saved message {message_id} to database")
        except Exception as e:
            logger.error(f"Error saving message to database: {e}")

    def _clear_pending_changes(self) -> None:
        self._pending_changes["joined"].clear()
        self._pending_changes["left"].clear()
