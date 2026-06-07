# HALU Platform — Guía de Producción

> Referencia rápida para despliegue, capacidad y escalado en Hostinger VPS.
> **Plan de producción elegido: KVM 4 — 16 GB RAM / 6 vCPU**

---

## 1. Capacidad por configuración

La plataforma es multiusuario pero **no todos los usuarios están activos al mismo tiempo**.
En una plataforma escolar el pico real es del **10–15 % del total matriculado**
(hora de entrada, cierre de periodo, entrega de boletines).

### Tabla de referencia

| VPS Hostinger | RAM / CPU | Workers Daphne | Celery hilos | Alumnos matriculados | Usuarios simultáneos pico |
|---|---|---|---|---|---|
| KVM 1 | 4 GB / 2 vCPU | 1 | 2 | hasta 600 | ~70 |
| KVM 2 | 8 GB / 4 vCPU | 2 | 4 | hasta 1 500 | ~180 |
| ✅ **KVM 4 ← ELEGIDO** | **16 GB / 6 vCPU** | **3** | **6** | **hasta 3 000** | **~360** |
| KVM 8 | 32 GB / 8 vCPU | 4–5 | 8 | hasta 6 000+ | ~700 |

> **Con KVM 4 arrancas con los 3 workers activos desde el primer día.**
> Cuando llegues al 70 % de CPU sostenido, haces resize a KVM 8 desde el panel
> de Hostinger — sin reinstalar, en ~10 minutos.

### ¿Qué cuenta como "usuario simultáneo"?

| Tipo de usuario | Conexiones que genera |
|---|---|
| Alumno viendo su dashboard | 1 HTTP + 1 WS notificaciones |
| Familiar leyendo mensajes | 1 HTTP + 1 WS mensajería + 1 WS notificaciones |
| Docente registrando notas | ráfaga de HTTP (sin WS activo) |
| Coordinador en Sentinel | 1 HTTP |

---

## 2. Distribución de Redis (KVM 4)

```
Redis db 0 → Celery broker        (tareas en cola)
Redis db 1 → Celery results       (resultados de tareas)
Redis db 2 → Caché + Sesiones     (django-redis)
Redis db 3 → Channel Layer        (WebSockets)
```

Con 16 GB de RAM en el VPS, Redis puede usar hasta **2 GB** sin problema
(el resto lo usan PostgreSQL, los 3 workers Daphne y el sistema operativo).

Límite de memoria recomendado para Redis en KVM 4:

```bash
# En /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

---

## 3. Archivos de configuración listos para KVM 4

### `/etc/systemd/system/halu@.service`

Template que genera los 3 workers. El `%i` se reemplaza por el número (1, 2, 3).

```ini
[Unit]
Description=HALU Platform — Daphne worker %i
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/halu_plataform
EnvironmentFile=/var/www/halu_plataform/.env
ExecStart=/var/www/halu_plataform/.venv/bin/daphne \
    -b 127.0.0.1 \
    -p 800%i \
    --proxy-headers \
    --access-log /var/www/halu_plataform/logs/daphne_%i.log \
    proyecto_colegio.asgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Habilitar los 3 workers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable halu@1 halu@2 halu@3
sudo systemctl start  halu@1 halu@2 halu@3
```

---

### `/etc/systemd/system/halu-celery.service`

```ini
[Unit]
Description=HALU Platform — Celery Worker
After=network.target redis.service
Wants=redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/halu_plataform
EnvironmentFile=/var/www/halu_plataform/.env
ExecStart=/var/www/halu_plataform/.venv/bin/celery \
    -A proyecto_colegio worker \
    --loglevel=info \
    --concurrency=6 \
    --logfile=/var/www/halu_plataform/logs/celery.log
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable halu-celery
sudo systemctl start  halu-celery
```

---

### `/etc/nginx/sites-available/halu`

Los 3 workers activos desde el inicio, con load balancing `least_conn`
(el worker con menos conexiones activas recibe el siguiente request).

```nginx
upstream halu_app {
    least_conn;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    # Cuando hagas resize a KVM 8, agrega:
    # server 127.0.0.1:8004;
    # server 127.0.0.1:8005;
}

server {
    listen 443 ssl http2;
    server_name tu-dominio.com;

    ssl_certificate     /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Archivos estáticos — Nginx los sirve directamente (Django no interviene)
    location /static/ {
        alias /var/www/halu_plataform/staticfiles_collected/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        gzip_static on;
    }

    location /media/ {
        alias /var/www/halu_plataform/media/;
        expires 7d;
    }

    # WebSockets (mensajería + notificaciones en tiempo real)
    location /ws/ {
        proxy_pass http://halu_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       $host;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Todo lo demás → Django
    location / {
        proxy_pass         http://halu_app;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 20M;     # para subida de archivos/evidencias
    }
}

# HTTP → HTTPS
server {
    listen 80;
    server_name tu-dominio.com;
    return 301 https://$host$request_uri;
}
```

---

## 4. Variables de entorno `.env` para producción

```env
# ── Django ──────────────────────────────────────────────
DEBUG=False
SECRET_KEY=<genera una con: python -c "import secrets; print(secrets.token_urlsafe(60))">
ALLOWED_HOSTS=tu-dominio.com
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com

# ── Base de datos ────────────────────────────────────────
DB_HOST=localhost
DB_NAME=halu_db
DB_USER=halu_user
DB_PASSWORD=<contraseña fuerte>
DB_PORT=5432
DB_CONN_MAX_AGE=60

# ── Redis ────────────────────────────────────────────────
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
REDIS_CACHE_URL=redis://127.0.0.1:6379/2
REDIS_URL=redis://127.0.0.1:6379/3

# ── Email ────────────────────────────────────────────────
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-correo@gmail.com
EMAIL_HOST_PASSWORD=<app password de Google>
```

---

## 5. Checklist de deploy inicial — KVM 4

```
PREPARACIÓN
[ ] VPS KVM 4 creado en Hostinger (Ubuntu 22.04 LTS)
[ ] IP del VPS anotada
[ ] Dominio con registro DNS A apuntando al IP del VPS
    (esperar propagación: 5 min – 24 h)

SISTEMA BASE
[ ] sudo apt update && sudo apt upgrade -y
[ ] sudo apt install -y \
      nginx python3-pip python3-venv git \
      redis-server \
      postgresql postgresql-contrib \
      certbot python3-certbot-nginx \
      build-essential libpq-dev

POSTGRESQL
[ ] sudo -u postgres psql
      CREATE USER halu_user WITH PASSWORD 'contraseña_fuerte';
      CREATE DATABASE halu_db OWNER halu_user;
      \q

CÓDIGO
[ ] mkdir -p /var/www/halu_plataform
[ ] Subir el código (git clone o scp)
[ ] cd /var/www/halu_plataform
[ ] python3 -m venv .venv
[ ] source .venv/bin/activate
[ ] pip install -r requirements.txt
[ ] Crear .env con las variables de la sección 4
[ ] python manage.py migrate --no-input
[ ] python manage.py collectstatic --no-input
[ ] python manage.py createsuperuser
[ ] mkdir -p logs media
[ ] chown -R www-data:www-data /var/www/halu_plataform

REDIS
[ ] Editar /etc/redis/redis.conf:
      maxmemory 2gb
      maxmemory-policy allkeys-lru
[ ] sudo systemctl restart redis
[ ] redis-cli ping   →  debe responder PONG

SERVICIOS SYSTEMD
[ ] Crear /etc/systemd/system/halu@.service (sección 3)
[ ] Crear /etc/systemd/system/halu-celery.service (sección 3)
[ ] sudo systemctl daemon-reload
[ ] sudo systemctl enable halu@{1,2,3} halu-celery
[ ] sudo systemctl start  halu@{1,2,3} halu-celery
[ ] sudo systemctl status halu@1   →  debe decir "active (running)"

NGINX
[ ] Crear /etc/nginx/sites-available/halu (sección 3)
[ ] sudo ln -s /etc/nginx/sites-available/halu /etc/nginx/sites-enabled/
[ ] sudo rm -f /etc/nginx/sites-enabled/default
[ ] sudo nginx -t   →  debe decir "syntax is ok"
[ ] sudo systemctl reload nginx

SSL
[ ] sudo certbot --nginx -d tu-dominio.com
[ ] Verificar renovación automática: sudo certbot renew --dry-run

FIREWALL
[ ] sudo ufw allow 22/tcp
[ ] sudo ufw allow 80/tcp
[ ] sudo ufw allow 443/tcp
[ ] sudo ufw --force enable
[ ] sudo ufw status

VERIFICACIÓN FINAL
[ ] Abrir https://tu-dominio.com en el navegador
[ ] Iniciar sesión con el superusuario
[ ] Enviar un mensaje → verificar tiempo real (WS)
[ ] sudo systemctl status halu@{1,2,3} halu-celery  →  todos "active"
```

---

## 6. Comandos del día a día

```bash
# Estado general de todos los servicios HALU
sudo systemctl status halu@{1,2,3} halu-celery

# Logs en tiempo real (Ctrl+C para salir)
sudo journalctl -u halu@1 -f
sudo journalctl -u halu@2 -f
sudo journalctl -u halu-celery -f

# Errores de las últimas 2 horas
sudo journalctl -u halu@1 --since "2 hours ago" -p err

# Reiniciar todos los workers (tras un deploy)
sudo systemctl restart halu@{1,2,3} halu-celery

# Aplicar migraciones tras actualizar el código
cd /var/www/halu_plataform
source .venv/bin/activate
python manage.py migrate --no-input
python manage.py collectstatic --no-input
sudo systemctl restart halu@{1,2,3}

# Monitoreo de carga
htop                                          # CPU / RAM general
sudo journalctl -u halu@1 -n 50             # últimas 50 líneas
ss -tnp | grep -E '800[1-3]' | wc -l        # conexiones activas en workers
redis-cli info clients                        # clientes conectados a Redis
redis-cli info memory                         # RAM usada por Redis
sudo -u postgres psql -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state='active';"
```

---

## 7. Señales para escalar a KVM 8

Cuando veas **dos o más** de estas durante horas pico:

| Métrica | Umbral de alerta |
|---|---|
| CPU total del VPS | > 80 % sostenido 15 min |
| RAM usada | > 12 GB (75 % de 16 GB) |
| Tiempo de respuesta HTTP | > 800 ms promedio |
| Conexiones PG activas | > 40 |
| Redis `connected_clients` | > 500 |
| Errores en logs | `TimeoutError` o `Connection reset` |

**Proceso de resize (sin pérdida de datos):**
1. Panel Hostinger → VPS → Upgrade Plan → KVM 8
2. El VPS reinicia (~10 min)
3. Todos los servicios arrancan solos (están habilitados en systemd)
4. Agregar workers 4 y 5:
   ```bash
   sudo systemctl enable halu@4 halu@5
   sudo systemctl start  halu@4 halu@5
   # Editar /etc/nginx/sites-available/halu y descomentar los puertos 8004 y 8005
   sudo nginx -s reload
   ```

---

## 8. Estructura de archivos en el VPS

```
/var/www/halu_plataform/
├── .env                           ← NUNCA subir a git
├── .venv/
├── manage.py
├── proyecto_colegio/
├── staticfiles_collected/         ← python manage.py collectstatic
├── media/                         ← archivos subidos por usuarios
└── logs/
    ├── daphne_1.log
    ├── daphne_2.log
    ├── daphne_3.log
    └── celery.log

/etc/systemd/system/
├── halu@.service                  ← template workers
└── halu-celery.service

/etc/nginx/sites-available/
└── halu
```

---

*HALU Platform — KVM 4 como plan de producción base.*
*Actualizar este documento si cambia la arquitectura o el plan de VPS.*
