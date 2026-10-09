FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and pandas
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# Start command using gunicorn with uvicorn workers.
# The forwarded header trust below is restricted to loopback deliberately,
# rather than set to '*' or left to uvicorn's default.
#
# Why not the '*' form: always_trust makes ProxyHeadersMiddleware copy the
# *left-most* X-Forwarded-For entry into scope["client"], and the left-most
# entry is written by whoever connected. uvicorn would then hand the app a
# client address the caller controls, and the rate limiter keys on it - a
# header rewrite per request is a fresh bucket.
#
# Why not the default: it is the same loopback list, but saying so here keeps
# the intent next to the command rather than in uvicorn's source. UvicornWorker
# forwards gunicorn's forwarded_allow_ips setting (itself defaulted from
# $FORWARDED_ALLOW_IPS) straight into uvicorn's Config, so this flag is what
# reaches ProxyHeadersMiddleware.
#
# The app resolves the real client itself, from the same header, using
# dependencies.get_client_key and TRUSTED_PROXY_COUNT - that logic is the single
# source of truth for client identity, so the server layer does not need to
# duplicate it. Loopback-only keeps scope["client"] the true transport peer for
# any request that came through a router; a proxy on the same host (local dev)
# is still trusted. Nothing in the app reads request.url / X-Forwarded-Proto,
# so this costs no absolute-URL generation (verified by grep).
CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${PORT:-8000} --forwarded-allow-ips=127.0.0.1,::1"]
