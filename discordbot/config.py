import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PROFILES = tuple(
    profile.strip() for profile in os.getenv("PROFILES", "").split(",") if profile.strip()
)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# /issue: token fine-grained só com Issues read/write no repositório abaixo.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ISSUE_REPO = os.getenv("GITHUB_ISSUE_REPO", "FelipeMayerDev/fockytv-vencord-plugin")
