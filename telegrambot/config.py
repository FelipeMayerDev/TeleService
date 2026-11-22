import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# /issue: só o dono abre issue pelo Telegram (no Discord é aberto a todos).
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ISSUE_REPO = os.getenv("GITHUB_ISSUE_REPO", "FelipeMayerDev/fockytv-vencord-plugin")
ISSUE_OWNER_ID = 138317474  # @fockytheguy


