FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY agent ./agent
COPY business ./business
COPY config ./config
COPY knowledge ./knowledge
COPY observability ./observability
COPY persistence ./persistence
COPY providers ./providers
COPY security ./security
COPY tools ./tools
COPY alembic.ini ./

RUN pip install --no-cache-dir ".[dev]"

ENV PYTHONUNBUFFERED=1

CMD ["python", "agent/main.py", "start"]
