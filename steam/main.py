import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import requests
from config import (
    ACTIVE_CHECK_INTERVAL,
    COMMUNITY_RESOLVE_URL,
    OFFLINE_CHECK_INTERVAL,
    PROFILES,
    STEAM_API_BASE,
    STEAM_API_KEY,
)

sys.path.append(str(Path(__file__).parent.parent))
from providers import SerpProvider
from shared import send_telegram_message
from domain import init_database

active_check_interval = int(ACTIVE_CHECK_INTERVAL)
offline_check_interval = int(OFFLINE_CHECK_INTERVAL)
profiles_to_watch = PROFILES.split(",") if PROFILES else []


playing_profiles = {}

IMAGE_CACHE: dict[str, str] = {}




def get_game_image(game: str, gameid: str | None) -> str | None:
    if game in IMAGE_CACHE:
        return IMAGE_CACHE[game]

    if gameid:
        cdn_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{gameid}/header.jpg"
        try:
            resp = requests.head(cdn_url, timeout=5, allow_redirects=True)
            if resp.status_code == 200:
                IMAGE_CACHE[game] = cdn_url
                return cdn_url
        except Exception:
            pass

    try:
        url = SerpProvider().search_image(image=f"Gameplay {game}")
        if url:
            IMAGE_CACHE[game] = url
            return url
    except Exception as e:
        print(f"Error searching image: {e}")

    return None


def resolve_vanity_url(vanity_url: str) -> str | None:
    """Resolve vanity URL to Steam64 ID."""
    try:
        response = requests.get(
            COMMUNITY_RESOLVE_URL,
            params={"key": STEAM_API_KEY, "vanityurl": vanity_url},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if data["response"]["success"] == 1:
            return data["response"]["steamid"]
        return None
    except Exception as e:
        print(f"Error resolving vanity URL {vanity_url}: {e}")
        return None


def get_steam_id(profile: str) -> str | None:
    """Get Steam64 ID from profile (vanity URL or numeric ID)."""
    profile = profile.strip()
    if profile.isdigit():
        return profile
    return resolve_vanity_url(profile)


def get_player_summaries(steam_ids: list[str]) -> dict:
    """Get player summaries from Steam API."""
    try:
        response = requests.get(
            STEAM_API_BASE,
            params={"key": STEAM_API_KEY, "steamids": ",".join(steam_ids)},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        players = data.get("response", {}).get("players", [])
        return {player["steamid"]: player for player in players}
    except Exception as e:
        print(f"Error fetching player summaries: {e}")
        return {}


async def get_playing_profiles(profiles: list[str]) -> dict:
    """Check which profiles are playing games."""
    steam_ids = []
    profile_map = {}

    for profile in profiles:
        steam_id = get_steam_id(profile)
        if steam_id:
            steam_ids.append(steam_id)
            profile_map[steam_id] = profile

    if not steam_ids:
        print("No valid Steam profiles")
        await asyncio.sleep(offline_check_interval)
        return playing_profiles

    player_data = get_player_summaries(steam_ids)
    if not player_data:
        await asyncio.sleep(offline_check_interval)
        return playing_profiles

    someone_playing = False

    for steam_id, data in player_data.items():
        profile = profile_map[steam_id]
        game = None
        gameid = None
        is_playing = False

        if "gameextrainfo" in data:
            is_playing = True
            game = data["gameextrainfo"]
            gameid = data.get("gameid")
            someone_playing = True

        old_status = playing_profiles.get(profile, {}).get("is_playing", False)
        if old_status != is_playing and is_playing:
            image_url = get_game_image(game, gameid)
            message = _format_game_message(game, {profile})
            edited = await _try_edit_last_steam(game, message, image_url)
            if not edited:
                await send_telegram_message(
                    text=message,
                    photo=image_url,
                    save_to_db=True,
                    message_type="steam_notification",
                )
            print(message)

        playing_profiles[profile] = {
            "is_playing": is_playing,
            "game": game,
        }

    check_interval = (
        active_check_interval if someone_playing else offline_check_interval
    )
    await asyncio.sleep(check_interval)

    return playing_profiles


def _format_game_message(game: str, profiles: set[str]) -> str:
    if len(profiles) == 1:
        return f"🎮 {next(iter(profiles))} está jogando {game}"
    names = ", ".join(sorted(profiles)[:-1]) + " e " + sorted(profiles)[-1]
    return f"🎮 {names} estão jogando {game}"


async def _try_edit_last_steam(game: str, new_text: str, image_url: str | None) -> bool:
    """Try to edit the last steam_notification message if it's for the same game."""
    import os
    from telegram import Bot
    from domain.repositories.message_repository import MessageRepository
    from database.main import init_database
    from database.models import Message as MessageModel

    init_database()
    repo = MessageRepository()
    chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
    if not chat_id:
        return False

    last = repo.get_last_message_by_type(
        chat_id=chat_id,
        message_type="steam_notification",
        platform="telegram",
    )
    if not last:
        return False

    # Check if last notification was for the same game
    last_text = last.text or ""
    if game not in last_text:
        return False

    # Check if it's among the last 5 messages
    recent = repo.get_last_messages(
        chat_id=chat_id,
        platform="telegram",
        limit=5,
    )
    recent_ids = {m.platform_message_id for m in recent}
    if last.platform_message_id not in recent_ids:
        return False

    # Extract current profiles from the message
    # Add new profile to the list
    current_profiles = _extract_profiles(last_text)
    current_profiles.add(new_text.split("🎮 ", 1)[1].split(" estão jogando ")[0].split(" está jogando ")[0])
    updated_text = _format_game_message(game, current_profiles)

    # Try to edit caption
    try:
        bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=last.platform_message_id,
            caption=updated_text,
        )
        print(f"Edited steam notification: {updated_text}")
        # Update DB
        repo.update_message_text(last.platform_message_id, updated_text)
        return True
    except Exception as e:
        print(f"Edit failed for steam notification: {e}")
        # Remove stale reference
        try:
            repo.delete_by_platform_message_id(last.platform_message_id)
        except Exception:
            pass
        return False


def _extract_profiles(text: str) -> set[str]:
    """Extract profile names from a steam notification message."""
    if "🎮 " not in text:
        return set()
    content = text.split("🎮 ", 1)[1]
    if " estão jogando " in content:
        names_str = content.split(" estão jogando ")[0]
    elif " está jogando " in content:
        names_str = content.split(" está jogando ")[0]
    else:
        return set()

    # Handle "X, Y e Z" format: split by ", " then split last item by " e "
    names = [n.strip() for n in names_str.split(", ")]
    if len(names) > 1 and " e " in names[-1]:
        names = names[:-1] + names[-1].split(" e ")
    elif " e " in names_str:
        names = names_str.split(" e ")
    return {n.strip() for n in names}


async def main():
    """Main loop."""
    init_database()

    if not profiles_to_watch:
        print("No profiles configured")
        return

    print(f"Starting Steam monitor for {len(profiles_to_watch)} profiles")
    print(
        f"Active check: {active_check_interval}s, Offline check: {offline_check_interval}s"
    )

    while True:
        await get_playing_profiles(profiles_to_watch)


if __name__ == "__main__":
    asyncio.run(main())
