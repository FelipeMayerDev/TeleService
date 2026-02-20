FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg supervisor && \
    rm -rf /var/lib/apt/lists/*

COPY shared.py ./shared.py
COPY database/ ./database/
COPY providers/ ./providers/

COPY discordbot/ ./discordbot/
COPY steam/ ./steam/
COPY telegrambot/ ./telegrambot/

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
