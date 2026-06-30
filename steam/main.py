import asyncio
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from datetime import datetime

from bs4 import BeautifulSoup

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
    STEAM_COOKIE_PATH,
)

sys.path.append(str(Path(__file__).parent.parent))
from providers import SerpProvider
from shared import send_telegram_message
from domain import init_database, SteamProfileState

active_check_interval = int(ACTIVE_CHECK_INTERVAL)
offline_check_interval = int(OFFLINE_CHECK_INTERVAL)
profiles_to_watch = PROFILES.split(",") if PROFILES else []

IMAGE_CACHE: dict[str, str] = {}

_scrape_session: requests.Session | None = None


def _get_scrape_session() -> requests.Session | None:
    """Retorna uma sessão requests com o cookie Steam carregado (singleton).

    Carrega o cookie uma única vez no startup. Se o cookie for atualizado,
    basta reiniciar o container para recarregar.
    """
    global _scrape_session
    if _scrape_session is not None:
        return _scrape_session
    try:
        jar = MozillaCookieJar()
        jar.load(STEAM_COOKIE_PATH, ignore_discard=True, ignore_expires=True)
        _scrape_session = requests.Session()
        for cookie in jar:
            _scrape_session.cookies.set_cookie(cookie)
        print("Steam cookie loaded for web scraping")
        return _scrape_session
    except Exception as e:
        print(f"Could not load Steam cookie (non-Steam detection disabled): {e}")
        return None


def get_non_steam_game(steam_id: str) -> str | None:
    """Faz scraping da página do perfil para detectar jogos non-Steam.

    A Steam API (GetPlayerSummaries) não reporta jogos non-Steam de forma
    confiável. Esta função consulta a página web do perfil, que mostra o
    status real de jogo (incluindo non-Steam).

    Retorna o nome do jogo, ou None se o perfil não estiver jogando.
    """
    session = _get_scrape_session()
    if session is None:
        return None

    url = f"https://steamcommunity.com/profiles/{steam_id}"
    try:
        resp = session.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # So considerar como jogando se o container tiver a classe 'in-game'.
        # Perfis offline/online (sem jogar) tambem tem profile_in_game_name,
        # mas com textos como "Last Online X ago" — precisamos filtrar.
        in_game_container = soup.select_one("div.profile_in_game.in-game")
        if not in_game_container:
            return None

        name = soup.select_one("div.profile_in_game_name")
        if name:
            return name.get_text(strip=True)
        return None
    except Exception as e:
        print(f"Error scraping profile {steam_id}: {e}")
        return None


def get_game_image(game: str, gameid: str | None) -> str | None:
    if game in IMAGE_CACHE:
        return IMAGE_CACHE[game]

    # Counter-Strike 2: usa fotos locais aleatórias
    if game.lower() in ["counter-strike 2", "counter-strike2", "cs2"]:
        import random
        cs2_images = [
            "/app/steam/cs2_1.jpg",
            "/app/steam/cs2_2.jpg"
        ]
        selected_image = random.choice(cs2_images)
        IMAGE_CACHE[game] = selected_image
        return selected_image

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
        url = SerpProvider().search_image(image=f"Gameplay {game}", use_cache=True)
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


def get_profile_state(profile: str) -> dict | None:
    """Get current state of a profile from database."""
    try:
        state = SteamProfileState.get_or_none(SteamProfileState.profile == profile)
        if state:
            return {
                "is_playing": state.is_playing,
                "game": state.game,
                "game_id": state.game_id,
                "last_notified_at": state.last_notified_at,
                "updated_at": state.updated_at,
            }
        return None
    except Exception as e:
        print(f"Error getting profile state: {e}")
        return None


def update_profile_state(profile: str, is_playing: bool, game: str | None, game_id: int | None, notified: bool = False) -> None:
    """Update state of a profile in database."""
    try:
        state, created = SteamProfileState.get_or_create(
            profile=profile,
            defaults={
                "is_playing": is_playing,
                "game": game,
                "game_id": game_id,
                "updated_at": datetime.now(),
            }
        )

        if not created:
            # Update existing record
            state.is_playing = is_playing
            state.game = game
            state.game_id = game_id
            state.updated_at = datetime.now()
            if notified:
                state.last_notified_at = datetime.now()
            state.save()
        elif notified:
            # First creation and already notified
            state.last_notified_at = datetime.now()
            state.save()
    except Exception as e:
        print(f"Error updating profile state: {e}")


async def get_playing_profiles(profiles: list[str]) -> None:
    """Check which profiles are playing games and notify on state change."""
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
        return

    player_data = get_player_summaries(steam_ids)
    if not player_data:
        await asyncio.sleep(offline_check_interval)
        return

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

        # Fallback: a Steam API nao reporta jogos non-Steam de forma confiavel.
        # Se a API nao detectou jogo, faz scraping da pagina web do perfil.
        if not is_playing:
            scraped_game = get_non_steam_game(steam_id)
            if scraped_game:
                game = scraped_game
                is_playing = True
                someone_playing = True
                print(f"Non-Steam game detected via scraping for {profile}: {scraped_game}")

        # Get current state from database
        current_state = get_profile_state(profile)
        old_is_playing = current_state["is_playing"] if current_state else False
        old_game = current_state["game"] if current_state else None
        last_notified_at = current_state["last_notified_at"] if current_state else None

        # Check if state changed
        state_changed = False
        if old_is_playing != is_playing:
            state_changed = True
        elif is_playing and old_game != game:
            # Changed to a different game
            state_changed = True

        # Anti-spam: if already notified for same game recently, don't notify again
        should_notify = state_changed and is_playing
        if last_notified_at and is_playing and old_game == game:
            time_since_notif = (datetime.now() - last_notified_at).total_seconds()
            if time_since_notif < 60:  # Don't notify more than once per minute for same game
                should_notify = False
                print(f"Skipping notification for {profile} (notified {int(time_since_notif)}s ago for same game)")

        if should_notify:
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
            # Update state with notified=True
            update_profile_state(profile, is_playing, game, gameid, notified=True)
        else:
            # Just update state without notification
            update_profile_state(profile, is_playing, game, gameid, notified=False)

    check_interval = (
        active_check_interval if someone_playing else offline_check_interval
    )
    await asyncio.sleep(check_interval)


def _format_game_message(game: str, profiles: set[str]) -> str:
    if len(profiles) == 1:
        return f"🎮 {next(iter(profiles))} está jogando {game}"
    names = ", ".join(sorted(profiles)[:-1]) + " e " + sorted(profiles)[-1]
    return f"🎮 {names} estão jogando {game}"


async def _try_edit_last_steam(game: str, new_text: str, image_url: str | None) -> bool:
    """Try to edit the last steam_notification message if it's for the same game and in last 5 messages.
    Otherwise, delete the old message and send a new one."""
    import os
    from telegram import Bot
    from domain.repositories.message_repository import MessageRepository

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
        # Message is too old, delete it and return False to send new one
        print(f"Old steam notification not in last 5 messages, deleting reference from DB")
        try:
            repo.delete_by_platform_message_id(last.platform_message_id)
        except Exception:
            pass
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