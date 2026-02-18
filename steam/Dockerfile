FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

COPY shared.py ./shared.py
COPY database/ ./database/
COPY providers/ ./providers/

FROM base AS steam

WORKDIR /app/steam

COPY steam/ ./

CMD ["python", "main.py"]
