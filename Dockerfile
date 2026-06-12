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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

EXPOSE 8080

RUN printf '#!/bin/sh\npython manage.py migrate --no-input\npython manage.py collectstatic --no-input\nexec daphne -b 0.0.0.0 -p ${PORT} proyecto_colegio.asgi:application\n' > /start.sh && chmod +x /start.sh

CMD ["/start.sh"]
