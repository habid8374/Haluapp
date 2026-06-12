"""
Comando de respaldo de la base de datos PostgreSQL.

Uso:
    python manage.py backup_database
    python manage.py backup_database --destino /ruta/backups
    python manage.py backup_database --retener 30

El comando:
1. Genera un dump comprimido (.sql.gz) con pg_dump.
2. Guarda el archivo en BACKUP_DIR (configurable vía env BACKUP_DIR) o --destino.
3. Elimina backups más antiguos que --retener días (default 30).
4. Si BACKUP_S3_BUCKET está configurado, sube el backup a S3 automáticamente.
"""

import gzip
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genera un backup comprimido de PostgreSQL y elimina backups antiguos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destino',
            type=str,
            default=None,
            help='Directorio donde guardar el backup. Default: BACKUP_DIR env o BASE_DIR/backups/',
        )
        parser.add_argument(
            '--retener',
            type=int,
            default=30,
            help='Días de retención. Backups más antiguos se eliminan. Default: 30.',
        )
        parser.add_argument(
            '--solo-listar',
            action='store_true',
            help='Solo lista los backups existentes sin crear uno nuevo.',
        )

    def handle(self, *args, **options):
        destino = Path(
            options['destino']
            or os.environ.get('BACKUP_DIR', '')
            or settings.BASE_DIR / 'backups'
        )
        destino.mkdir(parents=True, exist_ok=True)

        if options['solo_listar']:
            self._listar_backups(destino)
            return

        # ── 1. Obtener credenciales de la DB ────────────────────────────────
        db = settings.DATABASES['default']
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url:
            parsed = urlparse(db_url)
            host = parsed.hostname or 'localhost'
            port = str(parsed.port or 5432)
            name = parsed.path.lstrip('/')
            user = parsed.username or ''
            password = parsed.password or ''
        else:
            host = db.get('HOST', 'localhost')
            port = str(db.get('PORT', 5432))
            name = db.get('NAME', '')
            user = db.get('USER', '')
            password = db.get('PASSWORD', '')

        if db.get('ENGINE', '') == 'django.db.backends.sqlite3':
            # Para SQLite: copiamos el archivo directamente
            self._backup_sqlite(db['NAME'], destino)
        else:
            self._backup_postgres(host, port, name, user, password, destino)

        # ── 2. Limpiar backups antiguos ──────────────────────────────────────
        eliminados = self._limpiar_antiguos(destino, options['retener'])
        if eliminados:
            self.stdout.write(f'  Eliminados {len(eliminados)} backup(s) antiguos.')

        # ── 3. Subir a S3 si está configurado ───────────────────────────────
        bucket = os.environ.get('BACKUP_S3_BUCKET', '')
        if bucket:
            self._subir_s3(destino, bucket)

    def _backup_sqlite(self, db_path, destino):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre = f'halu_backup_{ts}.sqlite3.gz'
        archivo_final = destino / nombre
        with open(db_path, 'rb') as f_in, gzip.open(archivo_final, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        size_mb = archivo_final.stat().st_size / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup SQLite guardado: {archivo_final} ({size_mb:.1f} MB)'
        ))

    def _backup_postgres(self, host, port, name, user, password, destino):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre = f'halu_backup_{ts}.sql.gz'
        archivo_final = destino / nombre

        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            self.stderr.write(self.style.ERROR(
                'pg_dump no encontrado. Instala postgresql-client.'
            ))
            return

        cmd = [
            pg_dump,
            '-h', host, '-p', port, '-U', user,
            '--no-password', '--format=plain', '--encoding=UTF8',
            name,
        ]

        self.stdout.write(f'Generando backup de {name}@{host}:{port} ...')
        with gzip.open(archivo_final, 'wb') as gz_file:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            if result.returncode != 0:
                archivo_final.unlink(missing_ok=True)
                self.stderr.write(self.style.ERROR(
                    f'pg_dump falló: {result.stderr.decode()}'
                ))
                return
            gz_file.write(result.stdout)

        size_mb = archivo_final.stat().st_size / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup guardado: {archivo_final} ({size_mb:.1f} MB)'
        ))

    def _limpiar_antiguos(self, destino, dias):
        limite = datetime.now() - timedelta(days=dias)
        eliminados = []
        for archivo in destino.glob('halu_backup_*'):
            if archivo.stat().st_mtime < limite.timestamp():
                archivo.unlink()
                eliminados.append(archivo.name)
        return eliminados

    def _listar_backups(self, destino):
        archivos = sorted(destino.glob('halu_backup_*'), reverse=True)
        if not archivos:
            self.stdout.write('No hay backups en ' + str(destino))
            return
        self.stdout.write(f'\n{"Archivo":<45} {"Tamaño":>10}  Fecha')
        self.stdout.write('-' * 75)
        for a in archivos:
            size = a.stat().st_size / 1024 / 1024
            fecha = datetime.fromtimestamp(a.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            self.stdout.write(f'{a.name:<45} {size:>8.1f} MB  {fecha}')

    def _subir_s3(self, destino, bucket):
        try:
            import boto3
            # AWS_S3_ENDPOINT_URL permite usar proveedores compatibles con S3
            # (Cloudflare R2, MinIO, etc.). Sin ella, usa AWS estándar.
            endpoint = os.environ.get('AWS_S3_ENDPOINT_URL', '') or None
            s3 = boto3.client('s3', endpoint_url=endpoint)
            for archivo in sorted(destino.glob('halu_backup_*'))[-1:]:  # solo el último
                key = f'backups/{archivo.name}'
                s3.upload_file(str(archivo), bucket, key)
                self.stdout.write(self.style.SUCCESS(f'☁️  Subido a s3://{bucket}/{key}'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'No se pudo subir a S3: {e}'))
