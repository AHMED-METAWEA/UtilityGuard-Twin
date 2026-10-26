# Base images are pinned by digest (the multi-architecture index, read on 2026-10-25).
# Refresh them deliberately: a new digest is a reviewed change, not an automatic update.
FROM node:22-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS web
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377 AS api
WORKDIR /app
COPY deploy/requirements-api.lock deploy/requirements-api.lock
RUN pip install --no-cache-dir --require-hashes -r deploy/requirements-api.lock
COPY platform/ug_api platform/ug_api
RUN pip install --no-cache-dir --no-deps ./platform/ug_api
# The packaging tools are not needed at run time and carry known vulnerabilities (T-B1-002).
RUN python -m pip uninstall --yes pip setuptools wheel
COPY --from=web /build/frontend/dist /srv/web
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001
ENV UG_API_HOST=0.0.0.0 UG_API_PORT=8080 UG_STATIC_DIR=/srv/web PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).close()"]
CMD ["python", "-m", "ug_api"]
