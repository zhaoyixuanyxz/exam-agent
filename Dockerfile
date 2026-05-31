# exam-agent: single container (FastAPI + built React), data on volume
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
RUN pip install --no-cache-dir .

COPY --from=frontend /build/frontend/dist /app/static

ENV EXAM_AGENT_SERVE_STATIC=1 \
    EXAM_AGENT_STATIC_DIR=/app/static \
    DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
VOLUME ["/app/data"]
EXPOSE 8000

# SSE 长连接：单 worker；前置 Nginx/Caddy 时调大 proxy_read_timeout
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
