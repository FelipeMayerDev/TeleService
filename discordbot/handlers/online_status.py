import logging
from typing import Set

logger = logging.getLogger(__name__)


def get_online_users_with_status(message) -> str:
    """
    Lista todos os usuários online no canal de voz com seus status atuais.

    Icons:
    - 🔴 = Compartilhando tela (streaming)
    - 🎤 = Mutado (muted)
    - 🔇 = Surdado (deafened/muted by server)
    """
    if not message.guild:
        return "Não há canais de voz disponíveis."

    # Encontrar o canal de voz com membros
    voice_channel = None
    for vc in message.guild.voice_channels:
        if vc.members:
            voice_channel = vc
            break

    if not voice_channel:
        return "Não há ninguém online nos canais de voz."

    lines = [f"📢 **Canal: {voice_channel.name}**\n"]
    lines.append("Usuários online:\n")

    for member in sorted(voice_channel.members, key=lambda m: m.display_name.lower()):
        if member.bot:
            continue

        voice = member.voice
        if not voice:
            continue

        status_icon = ""
        if voice.self_stream:
            status_icon = "🔴"  # Streaming
        elif voice.self_deaf:
            status_icon = "🔇"  # Deafened
        elif voice.self_mute:
            status_icon = "🎤"  # Muted

        status_text = f" {status_icon}" if status_icon else ""
        lines.append(f"- {member.display_name}{status_text}")

    return "".join(lines)