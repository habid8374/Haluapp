FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    pkg-config \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libglib2.0-0 \
    libglib2.0-dev \
    libharfbuzz0b \
    libfontconfig1 \
    shared-mime-info \
    fonts-liberation \
    libmagic1t64 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pg_dump 18 desde el repo oficial de PostgreSQL: el cliente de Debian (17)
# rechaza respaldar el servidor Postgres 18 de Railway (version mismatch).
RUN install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSo /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

EXPOSE 8080

RUN printf '#!/bin/sh\npython manage.py migrate --no-input\npython manage.py collectstatic --no-input\nexec daphne -b 0.0.0.0 -p ${PORT} proyecto_colegio.asgi:application\n' > /start.sh && chmod +x /start.sh

CMD ["/start.sh"]
