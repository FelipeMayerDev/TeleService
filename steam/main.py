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

            message = f"🎮 {profile} está jogando {game}"
            print(message)
            await send_telegram_message(
                text=message,
                photo=image_url,
                save_to_db=True,
                message_type="steam_notification",
            )

        playing_profiles[profile] = {
            "is_playing": is_playing,
            "game": game,
        }

    check_interval = (
        active_check_interval if someone_playing else offline_check_interval
    )
    await asyncio.sleep(check_interval)

    return playing_profiles


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
