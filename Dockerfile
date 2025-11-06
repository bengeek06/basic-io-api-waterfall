###############################
# Base builder layer (deps)   #
###############################
FROM python:3.13.7-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps (only what we actually need runtime + build for psycopg if used later)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY requirements.txt requirements.txt
COPY requirements-dev.txt requirements-dev.txt

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

###############################
# Development image           #
###############################
FROM base AS development

# Install dev dependencies (separate layer for cache reuse if only app code changes)
RUN pip install -r requirements-dev.txt

# Copy the rest of the source
COPY . .
COPY wait-for-it.sh /wait-for-it.sh
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /wait-for-it.sh /docker-entrypoint.sh

# Env vars (dev)
ENV FLASK_ENV=development \
    APP_MODE=development \
    WAIT_FOR_DB=true \
    RUN_MIGRATIONS=true

EXPOSE 5000
ENTRYPOINT ["/docker-entrypoint.sh"]

###############################
# Test stage                  #
###############################
FROM base AS test

# Install dev + test deps
RUN pip install -r requirements-dev.txt

WORKDIR /app

# Copy all needed files for testing (tests folder should NOT be in .dockerignore)
COPY . .

# Variables minimales de test
ENV FLASK_ENV=testing \
    APP_MODE=testing \
    PYTEST_ADDOPTS="-v" \
    DATABASE_URL=sqlite:///:memory: \
    JWT_SECRET=test-jwt-secret-key

# Pas d'entrypoint, juste exécuter pytest directement
CMD ["pytest"]

###############################
# Production runtime          #
###############################
FROM python:3.13.7-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only runtime system deps (no build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages from base (dependencies) to slim runtime
COPY --from=base /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application code
COPY . .
COPY wait-for-it.sh /wait-for-it.sh
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Install only production extra (gunicorn) - separate to keep cache if code changes
RUN pip install gunicorn

RUN chmod +x /wait-for-it.sh /docker-entrypoint.sh

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV FLASK_ENV=production \
    APP_MODE=production \
    WAIT_FOR_DB=true \
    RUN_MIGRATIONS=true

EXPOSE 5000
ENTRYPOINT ["/docker-entrypoint.sh"]
