FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run espera que escuchemos en el puerto 8080
ENV PORT 8080

EXPOSE 8080

# Crear script de arranque
RUN printf '#!/bin/sh\npython manage.py migrate --no-input\nexec daphne -b 0.0.0.0 -p ${PORT} proyecto_colegio.asgi:application\n' > /start.sh && chmod +x /start.sh

# Usar shell form para que se expanda la variable $PORT
CMD ["/start.sh"]
