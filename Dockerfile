FROM python:3.10-slim

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
