FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

COPY shared.py ./shared.py
COPY database/ ./database/
COPY providers/ ./providers/

FROM base AS discordbot

WORKDIR /app/discordbot

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY discordbot/ ./

CMD ["python", "main.py"]
