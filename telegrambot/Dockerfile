FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-cache

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH"

COPY shared.py ./shared.py
COPY database/ ./database/
COPY providers/ ./providers/

FROM base AS telegrambot

WORKDIR /app/telegrambot

COPY telegrambot/ ./

CMD ["python", "main.py"]
