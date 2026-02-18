import os

from dotenv import load_dotenv

load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
PROFILES = os.getenv("PROFILES")
ACTIVE_CHECK_INTERVAL = os.getenv("ACTIVE_CHECK_INTERVAL")
OFFLINE_CHECK_INTERVAL = os.getenv("OFFLINE_CHECK_INTERVAL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STEAM_API_BASE = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
COMMUNITY_RESOLVE_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
