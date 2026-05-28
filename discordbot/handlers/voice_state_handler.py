import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Set

from telegram import Bot

from domain import MessageService
from shared import edit_telegram_message, send_telegram_message, is_telegram_message_recent

message_service = MessageService()

logger = logging.getLogger(__name__)


@dataclass
class VoiceStateHandler:
    cooldown: int = 2
    bot: Optional[Bot] = None
    telegram_chat_id: Optional[int] = None
    ignored_bot_names: Set[str] = field(default_factory=set)

    _pending_changes: dict = field(
        default_factory=lambda: {
            "joined": set(), "left": set(),
            "muted": set(), "unmuted": set(),
            "deafened": set(), "undeafened": set(),
            "streaming": set(), "stopped_streaming": set(),
        }
    )
    _timer_task: Optional[asyncio.Task] = None
    _voice_channel_before: Optional[object] = None
    _voice_channel_after: Optional[object] = None
    _last_member = None

    async def handle_voice_state(self, member, before, after) -> None:
        if member.bot:
            return

        self._last_member = member

        logger.info(f"Voice state: {member.display_name} | ch_before={before.channel} ch_after={after.channel} | mute={before.self_mute}->{after.self_mute} deaf={before.self_deaf}->{after.self_deaf} stream={getattr(before,'self_stream',False)}->{getattr(after,'self_stream',False)}")

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
        elif is_in_voice_after:
            # Removidas notificações de mute/unmute/deaf/streaming por padrão
            # Apenas mudanças de canal são notificadas
            changed = False
            if before.channel and after.channel and before.channel != after.channel:
                # Usuário mudou de canal
                logger.debug(f"{member.display_name} moved voice channel")
                changed = True
            if not changed:
                return
        else:
            return

        await self._schedule_notification()

    async def _schedule_notification(self) -> None:
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()

        self._timer_task = asyncio.create_task(self._wait_and_notify())

    async def _wait_and_notify(self) -> None:
        await asyncio.sleep(self.cooldown)

        # Cancel opposing actions per user
        self._cancel_opposing("muted", "unmuted")
        self._cancel_opposing("deafened", "undeafened")
        self._cancel_opposing("streaming", "stopped_streaming")

        if not any(self._pending_changes.values()):
            return

        await self._send_notification()

    def _cancel_opposing(self, key_a: str, key_b: str) -> None:
        """Remove users that appear in both opposing action sets."""
        common = self._pending_changes[key_a] & self._pending_changes[key_b]
        self._pending_changes[key_a] -= common
        self._pending_changes[key_b] -= common

    async def _send_notification(self) -> None:
        text = self._format_message()

        if not text:
            self._clear_pending_changes()
            return

        # Try to edit the last voice_state message (if within the last 5 messages)
        last_voice_msg_id = self._get_last_voice_state_message_id()
        if last_voice_msg_id:
            is_recent = await is_telegram_message_recent(
                chat_id=self.telegram_chat_id,
                message_id=last_voice_msg_id,
                recent_limit=5,
            )
            if is_recent:
                edited = await self._edit_last_message(last_voice_msg_id, text)
                if edited:
                    self._clear_pending_changes()
                    return
                else:
                    logger.info(f"Message {last_voice_msg_id} edit failed, sending new one")
                    self._delete_message_from_db(last_voice_msg_id)
            else:
                logger.info(f"Message {last_voice_msg_id} not in recent 5, sending new one")

        # For mute/unmute/deaf/stream without a voice channel, fetch it from guild
        channel = self._voice_channel_after or self._voice_channel_before
        if not channel:
            try:
                guild = self._last_member.guild if self._last_member else None
                if guild:
                    for vc in guild.voice_channels:
                        if vc.members:
                            channel = vc
                            break
                    self._voice_channel_after = channel
            except Exception as e:
                logger.debug(f"Could not find voice channel: {e}")

        await self._send_new_message(text)
        self._clear_pending_changes()

    def _get_last_voice_state_message_id(self) -> Optional[int]:
        """Get the last voice_state message ID from DB."""
        if self.telegram_chat_id is None:
            return None
        try:
            last = message_service.get_last_message_by_type(
                chat_id=self.telegram_chat_id,
                message_type="voice_state",
                platform="telegram",
            )
            return last.platform_message_id if last else None
        except Exception as e:
            logger.error(f"Error getting voice state message: {e}")
            return None

    def _delete_message_from_db(self, message_id: int):
        try:
            message_service.repository.delete_by_platform_message_id(
                platform_message_id=message_id, platform="telegram"
            )
            logger.info(f"Deleted stale message {message_id} from DB")
        except Exception as e:
            logger.warning(f"Could not delete message {message_id}: {e}")

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

        # Notificações de mute/unmute/deaf/streaming foram removidas
        # Use !online_agora para ver o status atual

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

            icon = self._get_voice_status_icon(member)
            if icon:
                online_users.add(f"{member.display_name} {icon}")
            else:
                online_users.add(member.display_name)

        return online_users

    @staticmethod
    def _get_voice_status_icon(member) -> str:
        voice = member.voice
        if not voice:
            logger.info(f"No voice state for {member.display_name}")
            return ""
        logger.info(f"Icon check {member.display_name}: mute={voice.mute} self_mute={voice.self_mute} self_deaf={voice.self_deaf} self_stream={voice.self_stream}")
        if voice.mute:
            return "🔇"
        if voice.self_stream:
            return "🔴"
        if voice.self_deaf:
            return "🔇"
        if voice.self_mute:
            return "🎤"
        return ""

    def _get_voice_state_message_id_to_edit(self) -> Optional[int]:
        if self.telegram_chat_id is None:
            return None

        try:
            return message_service.get_last_message_by_type(
                chat_id=self.telegram_chat_id,
                message_type="voice_state",
                platform="telegram",
            )
        except Exception as e:
            logger.error(f"Error getting voice state message to edit: {e}")
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
            logger.debug(f"Edit failed for message {message_id}: {e}")
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
        for v in self._pending_changes.values():
            v.clear()
