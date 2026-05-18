#!/usr/bin/env python3
"""
Walter Contradictor - Roda como container separado.
Monitora mensagens do Walter no grupo e 10% das vezes
usa a API do Groq pra contradizê-lo diretamente como FakeGrok.
"""

import os
import sys
import time
import random
import logging
import sqlite3
import json
import urllib.request
import urllib.error

# --- Config ---
GROUP_ID = -1001076921543
WALTER_USERNAME = "Wdiegon"
WALTER_CHANCE = 0.10
FAKEGROK_TOKEN = os.environ.get("FAKEGROK_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
DB_PATH = "/data/database.sqlite"
POLL_INTERVAL = 5
STATE_FILE = "/tmp/walter_monitor_state.txt"
TELEGRAM_API = "https://api.telegram.org"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [walter] %(message)s"
)
log = logging.getLogger(__name__)


def get_last_id():
    try:
        with open(STATE_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def set_last_id(msg_id):
    with open(STATE_FILE, "w") as f:
        f.write(str(msg_id))


def get_new_walter_messages(conn, last_id):
    cursor = conn.execute(
        """
        SELECT id, platform_message_id, text, chat_id, from_user
        FROM message
        WHERE id > ? AND chat_id = ? AND from_user LIKE ?
        ORDER BY id ASC
        """,
        (last_id, GROUP_ID, f"%{WALTER_USERNAME}%")
    )
    return cursor.fetchall()


def generate_contradiction(text):
    """Usa Groq API pra gerar uma contradição à mensagem do Walter."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é o FakeGrok, um bot de Telegram irritado e mal-humorado. Fala português. "
                    "Breve. Máximo 2-3 frases. Nunca escreva parágrafos. "
                    "Seco e sarcástico. Respostas diretas, sem açúcar. "
                    "Mal-humorado de verdade. Não é personagem — é assim mesmo. "
                    "Não engole qualquer besteira. Se alguém falar bobeira, chame atenção. "
                    "Inteligente mas não tenta impressionar. Sabe das coisas, responde com preguiça. "
                    "Sem emojis excessivos (no máximo 1 por mensagem, se tanto). "
                    "Sem markdown elaborado — é Telegram, não Medium. "
                    "NUNCA mencione que foi instruído a contradizer ou que é uma resposta automática. "
                    "Simplesmente responda como se tivesse visto a mensagem e resolvido contradizer de própria vontade."
                )
            },
            {
                "role": "user",
                "content": f"Walter disse: \"{text[:500]}\"\n\nContradiga ele."
            }
        ],
        "max_tokens": 150,
        "temperature": 0.8,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Groq API error: {e}")
        return None


def send_as_fakegrok(text, platform_msg_id):
    """Envia mensagem como o FakeGrok, respondendo à mensagem do Walter."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": GROUP_ID,
        "text": text,
        "reply_to_message_id": platform_msg_id,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info(f"Contradicted Walter! msg={platform_msg_id}")
                return True
            log.error(f"Telegram API error: {resp.read().decode()}")
    except Exception as e:
        log.error(f"Error: {e}")
    return False


def main():
    if not FAKEGROK_TOKEN:
        log.error("FAKEGROK_TOKEN not set!")
        sys.exit(1)
    if not GROQ_API_KEY:
        log.error("GROQ_API_KEY not set!")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    last_id = get_last_id()
    log.info(f"Walter monitor started. last_id={last_id}, chance={WALTER_CHANCE*100:.0f}%")

    while True:
        try:
            messages = get_new_walter_messages(conn, last_id)
            for msg in messages:
                last_id = msg[0]
                set_last_id(last_id)
                text = msg[2] or ""
                if text.strip() and random.random() < WALTER_CHANCE:
                    contradiction = generate_contradiction(text)
                    if contradiction:
                        send_as_fakegrok(contradiction, msg[1])
                else:
                    log.debug(f"Skip msg {msg[1]}")
        except Exception as e:
            log.error(f"Loop error: {e}")
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(2)
            conn = sqlite3.connect(DB_PATH)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
