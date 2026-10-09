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
# --forwarded-allow-ips='*': the app runs behind exactly one reverse proxy (the
# platform router) whose address is not known in advance, so its X-Forwarded-*
# headers must be trusted. UvicornWorker forwards gunicorn's forwarded_allow_ips
# setting (itself defaulted from $FORWARDED_ALLOW_IPS) straight into uvicorn's
# Config, so this flag is what makes request.client.host the real client instead
# of the router. Quoting '*' keeps the shell from glob-expanding it.
CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${PORT:-8000} --forwarded-allow-ips='*'"]
