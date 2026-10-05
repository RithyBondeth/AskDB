# AskDB API (FastAPI). Used by Railway and any other container host:
#   docker build -t askdb-api backend && docker run -p 8000:8000 askdb-api
FROM python:3.13-slim

RUN pip install --no-cache-dir "uv>=0.8,<1"
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH" PORT=8000
EXPOSE 8000
# Listen on "::" (IPv6 and IPv4, which Railway's private network needs) where the host
# has IPv6, else on 0.0.0.0. HOST overrides.
CMD ["sh", "-c", "H=${HOST:-$(python -c 'import socket; socket.socket(socket.AF_INET6).bind((\"::\", 0))' 2>/dev/null && echo :: || echo 0.0.0.0)}; exec uvicorn api.main:app --host $H --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
