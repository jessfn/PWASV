from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, HTMLResponse
from urllib.parse import quote
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
import os
import re
import bcrypt
import pytz
import json
from typing import List, Optional
import unicodedata
import io
import zipfile
import base64
from io import BytesIO

# ReportLab para generación de PDFs
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

app = FastAPI()

# Permitir requests desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3003", 
        "http://127.0.0.1:3003",
        "https://app.sembrandodatos.com",
        "https://apipwa.sembrandodatos.com",
        "https://admin.sembrandodatos.com",
        "https://ubicacion.sembrandodatos.com",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Comprime respuestas JSON grandes (ej. /registros, /asistencias con miles
# de filas para el mapa) antes de enviarlas — reduce drásticamente el tiempo
# de transferencia en el visor de mapa sin cambiar los datos devueltos.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configuración para autenticación JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-por-una-clave-muy-larga-y-unica")

# ── Bóveda de contraseñas ────────────────────────────────────────────────────
# Copia CIFRADA (Fernet) de la contraseña de cada administrador, para que solo
# "admin" y "Jess" puedan entregar el PDF de acceso sin restablecerla.
# La clave vive solo en el servidor (variable de entorno PWD_VAULT_KEY).
from cryptography.fernet import Fernet, InvalidToken
_VAULT_KEY = os.environ.get("PWD_VAULT_KEY", "")
_vault = Fernet(_VAULT_KEY.encode()) if _VAULT_KEY else None
VAULT_VISORES = {"admin", "jess"}

def _cifrar_pwd(pwd):
    return _vault.encrypt(pwd.encode("utf-8")).decode("utf-8") if (_vault and pwd) else None

def _descifrar_pwd(token):
    if not (_vault and token):
        return None
    try:
        return _vault.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None

def _jwt_admin(request: Request, solo_visores: bool = False) -> dict:
    """Valida el JWT del panel admin. Con solo_visores=True exige ser admin o Jess."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sesión requerida")
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    if payload.get("tipo") != "admin_user":
        raise HTTPException(status_code=403, detail="No autorizado")
    if solo_visores and str(payload.get("sub", "")).strip().lower() not in VAULT_VISORES:
        raise HTTPException(status_code=403, detail="Solo admin y Jess pueden consultar accesos")
    return payload


def _admin_jwt_valido(request: Request) -> bool:
    """True si la petición trae un token válido de administrador del panel."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET_KEY, algorithms=["HS256"])
        return payload.get("tipo") == "admin_user"
    except Exception:
        return False

# ── Recuperación de contraseña por correo ────────────────────────────────────
import smtplib
import hashlib as _hl
import secrets as _sc
import asyncio as _aio
import time as _tm
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

APP_URL = os.environ.get("APP_URL", "https://app.sembrandodatos.com").rstrip("/")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Sembrando Vida")
RESET_MINUTOS = 30
_reset_ip_hits = {}

def _enviar_correo_sync(destino, asunto, texto, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    msg["To"] = destino
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_FROM, [destino], msg.as_string())

async def _enviar_correo(destino, asunto, texto, html):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        print("⚠️ SMTP no configurado: no se envió el correo de recuperación")
        return False
    try:
        await _aio.get_event_loop().run_in_executor(None, _enviar_correo_sync, destino, asunto, texto, html)
        print(f"✉️ Correo enviado a {destino}: {asunto}")
        return True
    except Exception as e:
        print(f"❌ Error enviando correo a {destino}: {e}")
        return False

import emails as _emails

class OlvidePasswordRequest(BaseModel):
    correo: str

class RestablecerPasswordRequest(BaseModel):
    token: str
    nueva_contrasena: str

_err_cli_hits = {}

@app.post("/errores-cliente")
async def errores_cliente(request: Request):
    """Recibe errores de la app del teléfono (sin datos personales) para diagnosticar pantallas que no cargan."""
    ip = request.client.host if request.client else "?"
    ahora = _tm.time()
    hits = [t for t in _err_cli_hits.get(ip, []) if ahora - t < 3600]
    if len(hits) >= 30:
        return {"ok": False}
    hits.append(ahora)
    _err_cli_hits[ip] = hits
    try:
        d = json.loads((await request.body())[:4000] or b"{}")
        cursor.execute(
            "INSERT INTO client_errors (tipo, mensaje, ruta, usuario_id, ua, version, sw, ip) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(d.get("tipo", ""))[:30], str(d.get("mensaje", ""))[:1000], str(d.get("ruta", ""))[:200],
             d.get("usuario_id") if isinstance(d.get("usuario_id"), int) else None,
             str(d.get("ua", ""))[:250], str(d.get("version", ""))[:40], bool(d.get("sw")), ip))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    return {"ok": True}

@app.post("/auth/olvide-password")
async def olvide_password(datos: OlvidePasswordRequest, request: Request):
    """Envía al correo una liga de un solo uso. Siempre responde igual (no revela si el correo existe)."""
    generico = {"ok": True, "mensaje": "Si el correo está registrado, te enviamos una liga para crear una nueva contraseña. Revisa también tu carpeta de spam."}
    ip = request.client.host if request.client else "?"
    ahora = _tm.time()
    hits = [t for t in _reset_ip_hits.get(ip, []) if ahora - t < 900]
    if len(hits) >= 8:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
    hits.append(ahora)
    _reset_ip_hits[ip] = hits

    correo = (datos.correo or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
        raise HTTPException(status_code=400, detail="Escribe un correo electrónico válido")
    try:
        cursor.execute("SELECT id, nombre_completo, activo FROM usuarios WHERE LOWER(correo) = %s LIMIT 1", (correo,))
        row = cursor.fetchone()
        if row and row[2] is not False:
            cursor.execute("SELECT COUNT(*) FROM password_resets WHERE usuario_id = %s AND created_at > NOW() - INTERVAL '1 hour'", (row[0],))
            if cursor.fetchone()[0] >= 5:
                print(f"⚠️ Recuperación omitida: límite por hora alcanzado para usuario {row[0]}")
            else:
                token = _sc.token_urlsafe(32)
                huella = _hl.sha256(token.encode()).hexdigest()
                cursor.execute("UPDATE password_resets SET used_at = NOW() WHERE usuario_id = %s AND used_at IS NULL", (row[0],))
                cursor.execute(
                    "INSERT INTO password_resets (usuario_id, token_hash, expires_at, ip) VALUES (%s, %s, NOW() + INTERVAL '30 minutes', %s)",
                    (row[0], huella, ip))
                conn.commit()
                link = f"{APP_URL}/reset-password?token={token}"
                asunto, texto, html = _emails.correo_reset(row[1], link, RESET_MINUTOS, datetime.now().year)
                _aio.create_task(_enviar_correo(correo, asunto, texto, html))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ Error en olvide-password: {e}")
    return generico

@app.get("/auth/reset-password/validar")
async def validar_token_reset(token: str):
    huella = _hl.sha256(token.encode()).hexdigest()
    cursor.execute(
        "SELECT u.correo FROM password_resets r JOIN usuarios u ON u.id = r.usuario_id "
        "WHERE r.token_hash = %s AND r.used_at IS NULL AND r.expires_at > NOW()", (huella,))
    row = cursor.fetchone()
    if not row:
        return {"valido": False}
    correo = row[0] or ""
    usuario, _, dominio = correo.partition("@")
    oculto = (usuario[:1] + "***@" + dominio) if dominio else ""
    return {"valido": True, "correo_oculto": oculto}

@app.post("/auth/restablecer-password")
async def restablecer_password(datos: RestablecerPasswordRequest):
    """Cambia la contraseña usando la liga enviada al correo."""
    nueva = datos.nueva_contrasena or ""
    if len(nueva) < 6 or len(nueva) > 100:
        raise HTTPException(status_code=400, detail="La contraseña debe tener entre 6 y 100 caracteres")
    huella = _hl.sha256(datos.token.encode()).hexdigest()
    try:
        cursor.execute("SELECT id, usuario_id FROM password_resets WHERE token_hash = %s AND used_at IS NULL AND expires_at > NOW()", (huella,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="La liga no es válida o ya venció. Solicita una nueva.")
        cursor.execute("UPDATE usuarios SET contrasena = %s WHERE id = %s", (nueva, row[1]))
        cursor.execute("UPDATE password_resets SET used_at = NOW() WHERE usuario_id = %s AND used_at IS NULL", (row[1],))
        cursor.execute("SELECT correo, nombre_completo FROM usuarios WHERE id = %s", (row[1],))
        u = cursor.fetchone()
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error restableciendo contraseña: {e}")
        raise HTTPException(status_code=500, detail="No se pudo cambiar la contraseña. Inténtalo de nuevo.")
    if u and u[0]:
        ahora_mx = datetime.now(pytz.timezone("America/Mexico_City"))
        asunto, texto, html = _emails.correo_cambio(u[1], ahora_mx.strftime("%d/%m/%Y a las %H:%M"), ahora_mx.year)
        _aio.create_task(_enviar_correo(u[0], asunto, texto, html))
    return {"ok": True, "mensaje": "Contraseña actualizada correctamente"}

# Conexión a PostgreSQL con manejo robusto
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "app_registros")
DB_USER = os.environ.get("DB_USER", "jesus")
DB_PASS = os.environ.get("DB_PASS", "")

# Variables globales para la conexión
conn = None
cursor = None

def conectar_base_datos():
    """Función para establecer/reestablecer conexión a la base de datos"""
    global conn, cursor
    try:
        if conn:
            conn.close()
        
        conn = psycopg2.connect(
            host=DB_HOST, 
            database=DB_NAME, 
            user=DB_USER, 
            password=DB_PASS,
            # Configuraciones para mejor manejo de conexiones
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=5,
            keepalives_count=5
        )
        cursor = conn.cursor()
        print("✅ Conexión a la base de datos exitosa")
        return True
    except Exception as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        conn = None
        cursor = None
        return False

def abrir_conexion_aislada():
    """
    Abre una conexión y cursor propios, independientes del cursor global
    compartido (`cursor`). El cursor global es compartido por TODOS los
    endpoints; cuando dos requests concurrentes (ej. /estadisticas/dia-actual
    y /registros) hacen cursor.execute()/fetchone() en threads distintos
    sobre el MISMO objeto cursor, un request puede terminar leyendo los
    resultados de la consulta de otro — provocando estadísticas en cero de
    forma intermitente bajo carga concurrente.
    Los endpoints de estadísticas (llamados en paralelo con /registros y
    /asistencias desde el visor de mapa) usan esta conexión aislada para
    eliminar esa condición de carrera sin tener que tocar el resto de
    endpoints que aún usan el cursor global.
    """
    conexion = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=10
    )
    return conexion, conexion.cursor()

def verificar_conexion_db():
    """Verificar y reestablecer conexión si es necesario"""
    global conn, cursor
    try:
        if not conn or conn.closed:
            print("🔄 Reestableciendo conexión cerrada...")
            return conectar_base_datos()
        
        # Test de conexión simple
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True
    except (psycopg2.Error, psycopg2.OperationalError, AttributeError):
        print("🔄 Conexión perdida, reestableciendo...")
        return conectar_base_datos()

def ejecutar_consulta_segura(query, params=None, fetch_type='all'):
    """Ejecutar consulta con manejo robusto de errores y reconexión"""
    global conn, cursor
    max_reintentos = 3
    
    for intento in range(1, max_reintentos + 1):
        try:
            # Verificar conexión antes de ejecutar
            if not verificar_conexion_db():
                raise HTTPException(status_code=500, detail="No se pudo establecer conexión a la base de datos")
            
            # Ejecutar la consulta
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Obtener resultados según el tipo
            if fetch_type == 'one':
                result = cursor.fetchone()
            elif fetch_type == 'all':
                result = cursor.fetchall()
            else:  # fetch_type == 'none' para INSERT/UPDATE/DELETE
                result = None
            
            # Commit si es necesario
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                conn.commit()
            
            return result
            
        except psycopg2.Error as e:
            print(f"❌ Error de PostgreSQL en intento {intento}: {e}")
            
            # Hacer rollback para limpiar la transacción corrupta
            try:
                if conn and not conn.closed:
                    conn.rollback()
                    print("🔄 Rollback ejecutado para limpiar transacción")
            except Exception as rollback_error:
                print(f"⚠️ Error en rollback: {rollback_error}")
            
            if intento == max_reintentos:
                raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
            
            # Intentar reconectar para el siguiente intento
            conectar_base_datos()
            
        except Exception as e:
            print(f"❌ Error general en intento {intento}: {e}")
            
            # Hacer rollback también para errores generales
            try:
                if conn and not conn.closed:
                    conn.rollback()
                    print("🔄 Rollback ejecutado para error general")
            except Exception as rollback_error:
                print(f"⚠️ Error en rollback: {rollback_error}")
            
            if intento == max_reintentos:
                raise HTTPException(status_code=500, detail=f"Error al ejecutar consulta: {str(e)}")

# Establecer conexión inicial
try:
    conectar_base_datos()
    
    # Crear tabla admin_users si no existe
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            rol VARCHAR(20) DEFAULT 'admin' CHECK (rol IN ('admin', 'user')),
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """, fetch_type='none')
    
    # Errores reportados por la app del teléfono (diagnóstico)
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS client_errors (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            tipo VARCHAR(30), mensaje TEXT, ruta VARCHAR(200), usuario_id INTEGER,
            ua VARCHAR(250), version VARCHAR(40), sw BOOLEAN, ip VARCHAR(64)
        )
    """, fetch_type='none')

    # Recuperación de contraseña por correo (token guardado como huella SHA-256)
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            token_hash VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            ip VARCHAR(64),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """, fetch_type='none')
    ejecutar_consulta_segura("CREATE INDEX IF NOT EXISTS idx_password_resets_usuario ON password_resets(usuario_id, created_at)", fetch_type='none')

    # "Enterado" de notificaciones (constancia por persona) y opción de que la notificación lo requiera
    ejecutar_consulta_segura("ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS requiere_enterado BOOLEAN DEFAULT FALSE", fetch_type='none')
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS notificacion_enterados (
            id BIGSERIAL PRIMARY KEY,
            notificacion_id INTEGER NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            device_id VARCHAR(120),
            enterado_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'America/Mexico_City'),
            UNIQUE (notificacion_id, usuario_id)
        )
    """, fetch_type='none')
    ejecutar_consulta_segura("CREATE INDEX IF NOT EXISTS idx_enterados_notif ON notificacion_enterados(notificacion_id)", fetch_type='none')

    # Notificaciones push (un registro por dispositivo) y bitácora de envíos
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS push_suscripciones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            endpoint TEXT UNIQUE NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            ua VARCHAR(300),
            plataforma VARCHAR(20),
            activa BOOLEAN DEFAULT TRUE,
            fallos INTEGER DEFAULT 0,
            ultimo_error VARCHAR(300),
            creada_at TIMESTAMPTZ DEFAULT NOW(),
            ultima_vez TIMESTAMPTZ DEFAULT NOW(),
            ultimo_envio TIMESTAMPTZ
        )
    """, fetch_type='none')
    ejecutar_consulta_segura("CREATE INDEX IF NOT EXISTS idx_push_susc_usuario ON push_suscripciones(usuario_id) WHERE activa", fetch_type='none')
    ejecutar_consulta_segura("""
        CREATE TABLE IF NOT EXISTS push_envios (
            id BIGSERIAL PRIMARY KEY,
            notificacion_id INTEGER REFERENCES notificaciones(id) ON DELETE CASCADE,
            usuario_id INTEGER,
            suscripcion_id INTEGER REFERENCES push_suscripciones(id) ON DELETE SET NULL,
            estado VARCHAR(12) NOT NULL,
            codigo INTEGER,
            error VARCHAR(300),
            creado_at TIMESTAMPTZ DEFAULT NOW()
        )
    """, fetch_type='none')
    ejecutar_consulta_segura("CREATE INDEX IF NOT EXISTS idx_push_envios_notif ON push_envios(notificacion_id, estado)", fetch_type='none')

    # Un técnico solo puede tener UN facilitador activo (si ya hay duplicados, se avisa y no se crea)
    try:
        ejecutar_consulta_segura(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_fta_tecnico_activo ON facilitador_tecnico_asignaciones(tecnico_usuario_id) WHERE activo = TRUE",
            fetch_type='none')
    except Exception as e:
        print(f"⚠️ No se pudo crear uq_fta_tecnico_activo (¿aún existen duplicados o la tabla?): {e}")

    # Copia cifrada de la contraseña (bóveda)
    ejecutar_consulta_segura("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS password_enc TEXT", fetch_type='none')

    # Verificar si existen usuarios admin, si no crear uno por defecto
    count_result = ejecutar_consulta_segura("SELECT COUNT(*) FROM admin_users", fetch_type='one')
    count = count_result[0] if count_result else 0
    
    if count == 0:
        # Crear usuario admin por defecto
        default_password = pwd_context.hash("admin123")
        ejecutar_consulta_segura(
            "INSERT INTO admin_users (username, password, rol) VALUES (%s, %s, %s)",
            ("admin", default_password, "admin"),
            fetch_type='none'
        )
        print("✅ Usuario administrador por defecto creado: admin/admin123")
    
    # ===== MIGRACIÓN: Agregar columna permisos a tabla admin_users =====
    try:
        ejecutar_consulta_segura("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'admin_users' AND column_name = 'permisos'
                ) THEN
                    ALTER TABLE admin_users ADD COLUMN permisos TEXT DEFAULT NULL;
                    RAISE NOTICE 'Columna permisos agregada a admin_users';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Migración de columna permisos verificada")
    except Exception as e:
        print(f"⚠️ Error en migración de permisos: {e}")
    
    # ===== MIGRACIÓN: Agregar columna activo a tabla admin_users =====
    try:
        ejecutar_consulta_segura("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'admin_users' AND column_name = 'activo'
                ) THEN
                    ALTER TABLE admin_users ADD COLUMN activo BOOLEAN DEFAULT TRUE;
                    RAISE NOTICE 'Columna activo agregada a admin_users';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Migración de columna activo verificada")
    except Exception as e:
        print(f"⚠️ Error en migración de activo: {e}")
    
    # ===== MIGRACIÓN: Agregar columnas es_territorial y territorio a tabla admin_users =====
    try:
        ejecutar_consulta_segura("""
            DO $$ 
            BEGIN
                -- Agregar columna es_territorial
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'admin_users' AND column_name = 'es_territorial'
                ) THEN
                    ALTER TABLE admin_users ADD COLUMN es_territorial BOOLEAN DEFAULT FALSE;
                    RAISE NOTICE 'Columna es_territorial agregada a admin_users';
                END IF;
                
                -- Agregar columna territorio
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'admin_users' AND column_name = 'territorio'
                ) THEN
                    ALTER TABLE admin_users ADD COLUMN territorio VARCHAR(100) DEFAULT NULL;
                    RAISE NOTICE 'Columna territorio agregada a admin_users';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Migración de columnas es_territorial y territorio verificada")
    except Exception as e:
        print(f"⚠️ Error en migración de es_territorial/territorio: {e}")
    
    # ===== MIGRACIÓN: Agregar columnas categoria_actividad a tabla registros =====
    try:
        # Verificar si la columna categoria_actividad existe
        ejecutar_consulta_segura("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'registros' AND column_name = 'categoria_actividad'
                ) THEN
                    ALTER TABLE registros ADD COLUMN categoria_actividad VARCHAR(100);
                    RAISE NOTICE 'Columna categoria_actividad agregada a registros';
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'registros' AND column_name = 'categoria_actividad_otro'
                ) THEN
                    ALTER TABLE registros ADD COLUMN categoria_actividad_otro VARCHAR(255);
                    RAISE NOTICE 'Columna categoria_actividad_otro agregada a registros';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Verificación de columnas categoria_actividad completada")
    except Exception as migration_error:
        print(f"⚠️ Advertencia en migración de categoria_actividad: {migration_error}")
    
    # ===== MIGRACIÓN: Agregar columna territorio a tabla usuarios =====
    try:
        ejecutar_consulta_segura("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'usuarios' AND column_name = 'territorio'
                ) THEN
                    ALTER TABLE usuarios ADD COLUMN territorio VARCHAR(100) DEFAULT NULL;
                    RAISE NOTICE 'Columna territorio agregada a usuarios';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Migración de columna territorio verificada")
    except Exception as e:
        print(f"⚠️ Error en migración de territorio: {e}")

    # ===== MIGRACIÓN: usuario_id en admin_users (vínculo con tabla usuarios) =====
    try:
        ejecutar_consulta_segura("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='admin_users' AND column_name='usuario_id'
                ) THEN
                    ALTER TABLE admin_users ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id);
                    RAISE NOTICE 'Columna usuario_id agregada a admin_users';
                END IF;
            END $$;
        """, fetch_type='none')
        print("✅ Migración usuario_id en admin_users verificada")
    except Exception as e:
        print(f"⚠️ Error en migración usuario_id: {e}")

    # ===== MIGRACIÓN: Tabla facilitador_tecnico_asignaciones =====
    try:
        ejecutar_consulta_segura("""
            CREATE TABLE IF NOT EXISTS facilitador_tecnico_asignaciones (
                id                       BIGSERIAL PRIMARY KEY,
                facilitador_usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
                tecnico_usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
                origen                   VARCHAR(10) NOT NULL DEFAULT 'csv'
                                             CHECK (origen IN ('csv', 'manual')),
                activo                   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by_admin_user_id INTEGER REFERENCES admin_users(id),
                UNIQUE (facilitador_usuario_id, tecnico_usuario_id)
            );
        """, fetch_type='none')
        ejecutar_consulta_segura("""
            CREATE INDEX IF NOT EXISTS idx_fta_facilitador
                ON facilitador_tecnico_asignaciones(facilitador_usuario_id) WHERE activo = TRUE;
            CREATE INDEX IF NOT EXISTS idx_fta_tecnico
                ON facilitador_tecnico_asignaciones(tecnico_usuario_id) WHERE activo = TRUE;
        """, fetch_type='none')
        print("✅ Tabla facilitador_tecnico_asignaciones verificada")
    except Exception as e:
        print(f"⚠️ Error en migración facilitador_tecnico_asignaciones: {e}")

    # ===== MIGRACIÓN: agregar facilitador_admin_id y hacer facilitador_usuario_id nullable =====
    # Permite asociar técnicos a facilitadores que NO tienen usuario_id en la tabla usuarios
    try:
        ejecutar_consulta_segura("""
            DO $$
            BEGIN
                -- Agregar columna facilitador_admin_id si no existe
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='facilitador_tecnico_asignaciones'
                      AND column_name='facilitador_admin_id'
                ) THEN
                    ALTER TABLE facilitador_tecnico_asignaciones
                    ADD COLUMN facilitador_admin_id INTEGER REFERENCES admin_users(id);
                    RAISE NOTICE 'Columna facilitador_admin_id agregada';
                END IF;

                -- Hacer facilitador_usuario_id nullable
                BEGIN
                    ALTER TABLE facilitador_tecnico_asignaciones
                    ALTER COLUMN facilitador_usuario_id DROP NOT NULL;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END;

                -- Eliminar el UNIQUE constraint antiguo para permitir NULLs
                BEGIN
                    ALTER TABLE facilitador_tecnico_asignaciones
                    DROP CONSTRAINT IF EXISTS facilitador_tecnico_asignaciones_facilitador_usuario_id_tecnico_usuario_id_key;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END;
                BEGIN
                    ALTER TABLE facilitador_tecnico_asignaciones
                    DROP CONSTRAINT IF EXISTS facilitador_tecnico_asignaciones_facilitador_usuario_id_t_key;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END;

                -- Check: al menos uno de los dos IDs del facilitador debe estar presente
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name='chk_fta_facilitador_ref'
                      AND table_name='facilitador_tecnico_asignaciones'
                ) THEN
                    ALTER TABLE facilitador_tecnico_asignaciones
                    ADD CONSTRAINT chk_fta_facilitador_ref
                    CHECK (facilitador_usuario_id IS NOT NULL OR facilitador_admin_id IS NOT NULL);
                END IF;
            END $$;
        """, fetch_type='none')

        # Índices únicos parciales (para permitir ON CONFLICT)
        ejecutar_consulta_segura("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fta_usuario_tecnico_uq
                ON facilitador_tecnico_asignaciones (facilitador_usuario_id, tecnico_usuario_id)
                WHERE facilitador_usuario_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fta_admin_tecnico_uq
                ON facilitador_tecnico_asignaciones (facilitador_admin_id, tecnico_usuario_id)
                WHERE facilitador_admin_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_fta_admin
                ON facilitador_tecnico_asignaciones(facilitador_admin_id) WHERE activo = TRUE;
        """, fetch_type='none')

        # Backfill: para asignaciones existentes, poblar facilitador_admin_id desde admin_users
        ejecutar_consulta_segura("""
            UPDATE facilitador_tecnico_asignaciones fta
            SET facilitador_admin_id = au.id
            FROM admin_users au
            WHERE fta.facilitador_admin_id IS NULL
              AND fta.facilitador_usuario_id IS NOT NULL
              AND au.usuario_id = fta.facilitador_usuario_id;
        """, fetch_type='none')

        print("✅ Migración facilitador_admin_id aplicada")
    except Exception as e:
        print(f"⚠️ Error en migración facilitador_admin_id: {e}")

except Exception as e:
    print(f"❌ Error en inicialización de base de datos: {e}")
    conn = None
    cursor = None

# Carpeta para guardar fotos
FOTOS_DIR = "fotos"
os.makedirs(FOTOS_DIR, exist_ok=True)

# ==================== ENDPOINT DE SALUD ====================

@app.get("/health")
async def health_check():
    """Endpoint para verificar el estado de la API y la base de datos"""
    try:
        # Verificar conexión a la base de datos
        if not verificar_conexion_db():
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "message": "No se pudo conectar a la base de datos",
                "timestamp": datetime.now().isoformat()
            }
        
        # Prueba simple de consulta
        test_result = ejecutar_consulta_segura("SELECT 1 as test", fetch_type='one')
        
        if test_result and test_result[0] == 1:
            return {
                "status": "healthy",
                "database": "connected",
                "message": "API y base de datos funcionando correctamente",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unhealthy", 
                "database": "error",
                "message": "Error en consulta de prueba",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "error",
            "message": f"Error en health check: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# ==================== FIN ENDPOINT DE SALUD ====================

# Modelos para autenticación
class UserCreate(BaseModel):
    correo: str
    nombre_completo: str
    cargo: str
    supervisor: str = None
    contrasena: str
    curp: str  # CURP obligatoria
    telefono: str  # Teléfono obligatorio
    territorio: str = None  # Estado de México (opcional pero recomendado)
    rol: str = 'user'  # Rol por defecto es user
    facilitador_admin_id: int = None  # ID del facilitador en admin_users (para técnicos)

class UserLogin(BaseModel):
    correo: str
    contrasena: str

class PasswordChange(BaseModel):
    usuario_id: int
    nueva_contrasena: str

# Modelo para actualizar información personal (sin contraseña)
class UserInfoUpdate(BaseModel):
    nombre_completo: str
    correo: str
    cargo: str
    supervisor: Optional[str] = None
    curp: Optional[str] = None
    telefono: Optional[str] = None
    territorio: Optional[str] = None

class TerminosAceptados(BaseModel):
    usuario_id: int

# ==================== MODELOS PARA NOTIFICACIONES ====================

class NotificacionCreate(BaseModel):
    titulo: str
    subtitulo: Optional[str] = None
    descripcion: Optional[str] = None
    enlace_url: Optional[str] = None
    enviada_a_todos: bool = True
    usuario_ids: Optional[List[int]] = None  # Solo si enviada_a_todos = False

class NotificacionLeer(BaseModel):
    usuario_id: int
    device_id: Optional[str] = None

class NotificacionResponse(BaseModel):
    id: int
    titulo: str
    subtitulo: Optional[str] = None
    descripcion: Optional[str] = None
    enlace_url: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tipo: Optional[str] = None
    enviada_a_todos: bool
    fecha_creacion: datetime
    fecha_envio: Optional[datetime] = None
    destinatarios: Optional[List[dict]] = None

class DispositivoUpdate(BaseModel):
    usuario_id: int
    dispositivo: str  # 'Android', 'iOS', 'Desktop', 'Desconocido'
    user_agent: Optional[str] = None

# ==================== FIN MODELOS NOTIFICACIONES ====================

# ==================== ENDPOINT PROXY PARA IMÁGENES (SOLUCIONA CORS EN MÓVILES) ====================

@app.get("/fotos-base64/{nombre_archivo:path}")
async def obtener_foto_base64(nombre_archivo: str):
    """
    Endpoint proxy para obtener imágenes como base64.
    Soluciona problemas de CORS en dispositivos móviles (iOS Safari, Android).
    """
    try:
        # Construir ruta segura
        ruta_archivo = os.path.join(FOTOS_DIR, nombre_archivo)
        
        # Validar que el archivo exista y esté dentro de FOTOS_DIR
        ruta_absoluta = os.path.abspath(ruta_archivo)
        ruta_base = os.path.abspath(FOTOS_DIR)
        
        if not ruta_absoluta.startswith(ruta_base):
            raise HTTPException(status_code=403, detail="Acceso denegado")
        
        if not os.path.exists(ruta_archivo):
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        
        # Leer archivo y convertir a base64
        with open(ruta_archivo, "rb") as f:
            contenido = f.read()
        
        # Detectar tipo MIME
        extension = os.path.splitext(nombre_archivo)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        mime_type = mime_types.get(extension, 'image/jpeg')
        
        # Convertir a base64 con prefijo data URI
        base64_data = base64.b64encode(contenido).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{base64_data}"
        
        return {
            "success": True,
            "data": data_uri,
            "mime_type": mime_type,
            "size_bytes": len(contenido)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo foto base64: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando imagen: {str(e)}")

# ==================== FIN ENDPOINT PROXY IMÁGENES ====================

# Montar carpeta de fotos para servir estáticamente
app.mount("/fotos", StaticFiles(directory="fotos"), name="fotos")

# ==================== NUEVOS ENDPOINTS DE TÉRMINOS ====================

@app.get("/usuarios/{user_id}/terminos")
async def verificar_terminos_usuario(user_id: int):
    """Verificar si un usuario ha aceptado los términos y condiciones"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
            
        print(f"🔍 Verificando términos para usuario {user_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, correo FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            print(f"❌ Usuario {user_id} no encontrado")
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar si ha aceptado términos
        cursor.execute(
            "SELECT aceptado, fecha_aceptado FROM usuarios_terminos WHERE usuario_id = %s",
            (user_id,)
        )
        terminos = cursor.fetchone()
        
        resultado = {
            "usuario_id": user_id,
            "ha_aceptado_terminos": terminos is not None and terminos[0] if terminos else False,
            "fecha_aceptacion": terminos[1].isoformat() if terminos and terminos[1] else None
        }
        
        print(f"✅ Términos verificados para usuario {user_id}: {resultado['ha_aceptado_terminos']}")
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error verificando términos: {e}")
        raise HTTPException(status_code=500, detail=f"Error al verificar términos: {str(e)}")

@app.post("/usuarios/aceptar_terminos")
async def aceptar_terminos(terminos: TerminosAceptados):
    """Registrar la aceptación de términos y condiciones de un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
            
        print(f"📝 Registrando términos para usuario {terminos.usuario_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, correo FROM usuarios WHERE id = %s", (terminos.usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            print(f"❌ Usuario {terminos.usuario_id} no encontrado")
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar si ya existe un registro para este usuario
        cursor.execute("SELECT id FROM usuarios_terminos WHERE usuario_id = %s", (terminos.usuario_id,))
        existe = cursor.fetchone()
        
        if existe:
            # Actualizar registro existente
            cursor.execute("""
                UPDATE usuarios_terminos 
                SET aceptado = %s, fecha_aceptado = NOW()
                WHERE usuario_id = %s
            """, (True, terminos.usuario_id))
            print(f"✅ Términos actualizados para usuario {terminos.usuario_id}")
        else:
            # Insertar nuevo registro
            cursor.execute("""
                INSERT INTO usuarios_terminos (usuario_id, aceptado, fecha_aceptado) 
                VALUES (%s, %s, NOW())
            """, (terminos.usuario_id, True))
            print(f"✅ Términos creados para usuario {terminos.usuario_id}")
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "Términos y condiciones aceptados exitosamente",
            "usuario_id": terminos.usuario_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error aceptando términos: {e}")
        raise HTTPException(status_code=500, detail=f"Error al registrar aceptación de términos: {str(e)}")

@app.post("/usuarios")
async def crear_usuario(usuario: UserCreate):
    """Crear usuario con rol y automáticamente registrar aceptación de términos"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
            
        print(f"👤 Creando usuario: {usuario.correo} con rol {usuario.rol}")
        
        # Validación de rol
        if usuario.rol not in ['admin', 'user']:
            raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'user'")
        
        # Validación de CURP obligatoria
        if not usuario.curp or not usuario.curp.strip():
            raise HTTPException(status_code=400, detail="La CURP es obligatoria")
        
        # Convertir CURP a mayúsculas y validar
        curp_upper = usuario.curp.upper().strip()
        if len(curp_upper) != 18:
            raise HTTPException(status_code=400, detail="La CURP debe tener exactamente 18 caracteres")
        
        # Validación básica de formato CURP
        if not re.match(r'^[A-Z0-9]{18}$', curp_upper):
            raise HTTPException(status_code=400, detail="La CURP debe contener solo letras mayúsculas y números")
        
        # Validación de teléfono obligatorio
        if not usuario.telefono or not usuario.telefono.strip():
            raise HTTPException(status_code=400, detail="El número de teléfono es obligatorio")
        
        # Validación básica de formato de teléfono (permitir números, +, espacios y -)
        if not re.match(r'^[0-9\+\s\-]+$', usuario.telefono):
            raise HTTPException(status_code=400, detail="El número de teléfono contiene caracteres no válidos")
            
        # Validar que el formato general sea correcto (al menos debe tener un + y números)
        if not re.match(r'^\+[0-9]+\s*[0-9]+$', usuario.telefono.strip()):
            raise HTTPException(status_code=400, detail="El formato del teléfono debe incluir código de país con + y números")
        
        # Validación de territorio (estado de México)
        territorio_value = None
        if usuario.territorio and usuario.territorio.strip():
            territorio_value = usuario.territorio.strip()
            print(f"📍 Territorio asignado: {territorio_value}")
        
        # Comprobar si el correo ya existe
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (usuario.correo,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El correo ya está registrado")
        
        # Comprobar si la CURP ya existe
        cursor.execute("SELECT id FROM usuarios WHERE curp = %s", (curp_upper,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="La CURP ya está registrada")
        
        # Verificar si la columna 'rol' existe, si no, agregarla
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """)
        
        if not cursor.fetchone():
            print("📝 Agregando columna 'rol' a la tabla usuarios")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(10) DEFAULT 'user'")
            conn.commit()
        
        # Insertar usuario con CURP, teléfono, territorio y rol (contraseña sin encriptar)
        cursor.execute(
            "INSERT INTO usuarios (correo, nombre_completo, cargo, supervisor, contrasena, curp, telefono, territorio, rol) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (usuario.correo, usuario.nombre_completo, usuario.cargo, usuario.supervisor, usuario.contrasena, curp_upper, usuario.telefono, territorio_value, usuario.rol)
        )
        
        user_id = cursor.fetchone()[0]
        print(f"✅ Usuario creado con ID: {user_id}")
        
        # ==================== REGISTRO AUTOMÁTICO DE TÉRMINOS ====================
        
        # Registrar automáticamente la aceptación de términos al crear el usuario
        try:
            cursor.execute(
                "INSERT INTO usuarios_terminos (usuario_id, aceptado, fecha_aceptado) VALUES (%s, %s, NOW())",
                (user_id, True)
            )
            print(f"✅ Términos registrados automáticamente para usuario {user_id}")
        except psycopg2.IntegrityError as e:
            print(f"⚠️ Usuario {user_id} ya tiene términos registrados: {e}")
            # No es un error crítico, continuar
        except Exception as e:
            print(f"❌ Error registrando términos para usuario {user_id}: {e}")
            # No hacer rollback completo, solo advertir
        
        # ==================== ASIGNACIÓN DE FACILITADOR (para técnicos) ====================
        facilitador_asignado = False
        if usuario.facilitador_admin_id:
            cargo_upper = (usuario.cargo or '').upper()
            if 'TECNICO' in cargo_upper:
                try:
                    # Verificar que el facilitador exista en admin_users
                    cursor.execute(
                        "SELECT id, usuario_id, nombre_completo FROM admin_users WHERE id = %s AND activo = TRUE AND UPPER(COALESCE(cargo, '')) LIKE '%%FACILITADOR%%'",
                        (usuario.facilitador_admin_id,)
                    )
                    fac_row = cursor.fetchone()
                    if fac_row:
                        fac_usuario_id = fac_row[1]  # puede ser None
                        fac_nombre = fac_row[2]
                        
                        # Un técnico = un solo facilitador activo: desactiva cualquier otro
                        cursor.execute("""
                            UPDATE facilitador_tecnico_asignaciones
                            SET activo = FALSE, updated_at = NOW()
                            WHERE tecnico_usuario_id = %s AND activo = TRUE
                              AND facilitador_admin_id IS DISTINCT FROM %s
                        """, (user_id, usuario.facilitador_admin_id))

                        # Crear asignación formal usando admin_id (y usuario_id si está vinculado)
                        cursor.execute("""
                            INSERT INTO facilitador_tecnico_asignaciones
                                (facilitador_admin_id, facilitador_usuario_id, tecnico_usuario_id, origen, activo)
                            VALUES (%s, %s, %s, 'manual', TRUE)
                            ON CONFLICT (facilitador_admin_id, tecnico_usuario_id)
                            WHERE facilitador_admin_id IS NOT NULL
                            DO UPDATE SET activo = TRUE, origen = 'manual', updated_at = NOW(),
                                          facilitador_usuario_id = EXCLUDED.facilitador_usuario_id
                        """, (usuario.facilitador_admin_id, fac_usuario_id, user_id))
                        print(f"✅ Asignación formal creada: admin_id={usuario.facilitador_admin_id} usuario_id={fac_usuario_id} → técnico {user_id}")
                        
                        # Siempre actualizar campo supervisor con el nombre del facilitador
                        cursor.execute(
                            "UPDATE usuarios SET supervisor = %s WHERE id = %s",
                            (fac_nombre, user_id)
                        )
                        facilitador_asignado = True
                        print(f"✅ Facilitador {fac_nombre} asignado al técnico {user_id}")
                    else:
                        print(f"⚠️ Facilitador admin_id {usuario.facilitador_admin_id} no encontrado")
                except Exception as e_fac:
                    print(f"⚠️ Error asignando facilitador: {e_fac}")
        
        conn.commit()
        
        return {
            "id": user_id, 
            "mensaje": "Usuario creado exitosamente con términos aceptados automáticamente", 
            "curp": curp_upper,
            "terminos_registrados": True,
            "facilitador_asignado": facilitador_asignado
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error completo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

# ==================== ENDPOINTS DE HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Endpoint para verificar la salud del servidor"""
    try:
        if not verificar_conexion_db():
            return {"status": "warning", "message": "Servidor en línea pero sin conexión a base de datos"}
        return {"status": "ok", "message": "Servidor en línea y conectado a base de datos"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.options("/{path:path}")
async def preflight(path: str):
    """Manejar solicitudes CORS preflight"""
    return {"message": "OK"}

@app.post("/login")
async def login(usuario: UserLogin):
    # Buscar usuario por correo incluyendo territorio, curp, supervisor y activo
    cursor.execute("SELECT id, correo, nombre_completo, cargo, contrasena, territorio, curp, supervisor, activo FROM usuarios WHERE correo = %s", (usuario.correo,))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    # Verificar contraseña (comparación directa sin encriptación)
    if usuario.contrasena != user[4]:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    # Verificar si el usuario está activo
    activo = user[8] if len(user) > 8 else True
    if activo is False:
        raise HTTPException(status_code=403, detail="Tu cuenta ha sido desactivada. Contacta al administrador para más información.")
    
    # Actualizar último acceso
    try:
        cursor.execute("""
            UPDATE usuarios 
            SET ultimo_acceso = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user[0],))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Error al actualizar último acceso: {e}")
    
    # Devolver datos del usuario (sin la contraseña)
    return {
        "id": user[0],
        "correo": user[1],
        "nombre_completo": user[2],
        "cargo": user[3],
        "territorio": user[5] if len(user) > 5 else None,
        "curp": user[6] if len(user) > 6 else None,
        "supervisor": user[7] if len(user) > 7 else None,
        "activo": activo if activo is not None else True
    }

# ==================== ENDPOINTS PARA TRACKING DE DISPOSITIVOS ====================

@app.post("/actualizar_dispositivo")
async def actualizar_dispositivo(datos: DispositivoUpdate):
    """Actualiza el dispositivo del usuario al hacer login"""
    try:
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="Error de conexión a base de datos")
        
        cursor.execute("""
            UPDATE usuarios 
            SET dispositivo = %s, 
                user_agent = %s,
                ultimo_acceso = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (datos.dispositivo, datos.user_agent, datos.usuario_id))
        
        conn.commit()
        
        return {"success": True, "message": "Dispositivo actualizado"}
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al actualizar dispositivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estadisticas/dispositivos")
async def estadisticas_dispositivos():
    """Obtiene estadísticas de dispositivos en tiempo real"""
    try:
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="Error de conexión a base de datos")
        
        # Total de usuarios
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        total = cursor.fetchone()[0]
        
        # Por dispositivo
        cursor.execute("""
            SELECT 
                COALESCE(dispositivo, 'desconocido') as dispositivo,
                COUNT(*) as cantidad,
                ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM usuarios), 0), 2) as porcentaje
            FROM usuarios
            GROUP BY dispositivo
            ORDER BY cantidad DESC
        """)
        dispositivos = cursor.fetchall()
        
        # Por cargo (puesto)
        cursor.execute("""
            SELECT 
                COALESCE(cargo, 'Sin cargo') as cargo,
                COUNT(*) as cantidad,
                ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM usuarios), 0), 2) as porcentaje
            FROM usuarios
            GROUP BY cargo
            ORDER BY cantidad DESC
            LIMIT 10
        """)
        por_cargo = cursor.fetchall()
        
        # Usuarios activos (último acceso en últimos 30 días)
        cursor.execute("""
            SELECT 
                COALESCE(dispositivo, 'desconocido') as dispositivo,
                COUNT(*) as cantidad
            FROM usuarios
            WHERE ultimo_acceso >= NOW() - INTERVAL '30 days'
            GROUP BY dispositivo
            ORDER BY cantidad DESC
        """)
        activos = cursor.fetchall()
        
        # Estado de usuarios (activo/inactivo basado en campo 'activo')
        cursor.execute("""
            SELECT 
                CASE WHEN activo = true THEN 'Activos' ELSE 'Inactivos' END as estado,
                COUNT(*) as cantidad,
                ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM usuarios), 0), 2) as porcentaje
            FROM usuarios
            GROUP BY activo
            ORDER BY activo DESC
        """)
        estado_usuarios = cursor.fetchall()
        
        return {
            "total_usuarios": total,
            "por_dispositivo": [
                {
                    "dispositivo": d[0],
                    "cantidad": d[1],
                    "porcentaje": float(d[2])
                }
                for d in dispositivos
            ],
            "por_cargo": [
                {
                    "cargo": c[0],
                    "cantidad": c[1],
                    "porcentaje": float(c[2])
                }
                for c in por_cargo
            ],
            "activos_30_dias": [
                {
                    "dispositivo": a[0],
                    "cantidad": a[1]
                }
                for a in activos
            ],
            "estado_usuarios": [
                {
                    "estado": e[0],
                    "cantidad": e[1],
                    "porcentaje": float(e[2])
                }
                for e in estado_usuarios
            ]
        }
    except Exception as e:
        print(f"❌ Error al obtener estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ENDPOINT PARA VERIFICAR CONTRASEÑA ====================

@app.post("/verificar_contrasena")
async def verificar_contrasena(datos: dict):
    """Verifica si la contraseña actual es correcta"""
    try:
        usuario_id = datos.get('usuario_id')
        contrasena = datos.get('contrasena')
        
        if not usuario_id or not contrasena:
            raise HTTPException(status_code=400, detail="usuario_id y contrasena son obligatorios")
        
        # Verificar que el usuario existe y obtener su contraseña
        cursor.execute("SELECT id, contrasena FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Comparar contraseña (sin encriptación, verificar si está encriptada primero)
        contrasena_almacenada = usuario[1]
        
        # Intentar comparar directamente primero (por si no está encriptada)
        if contrasena == contrasena_almacenada:
            return {"success": True, "message": "Contraseña verificada"}
        
        # Si no coincide, intentar con bcrypt (por si está encriptada)
        try:
            if bcrypt.checkpw(contrasena.encode('utf-8'), contrasena_almacenada.encode('utf-8')):
                return {"success": True, "message": "Contraseña verificada"}
        except Exception:
            pass
        
        # Contraseña incorrecta
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al verificar contraseña: {e}")
        raise HTTPException(status_code=500, detail=f"Error al verificar contraseña: {str(e)}")

@app.post("/cambiar_contrasena")
async def cambiar_contrasena(datos: PasswordChange):
    try:
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (datos.usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Validar que la nueva contraseña no esté vacía
        if not datos.nueva_contrasena or len(datos.nueva_contrasena.strip()) < 6:
            raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres")
        
        # Hash de la nueva contraseña
        hashed_password = bcrypt.hashpw(datos.nueva_contrasena.encode('utf-8'), bcrypt.gensalt())
        
        # Actualizar la contraseña en la base de datos
        cursor.execute(
            "UPDATE usuarios SET contrasena = %s WHERE id = %s",
            (hashed_password.decode('utf-8'), datos.usuario_id)
        )
        
        conn.commit()
        
        return {"success": True, "message": "Contraseña actualizada exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al cambiar contraseña: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar contraseña: {str(e)}")

@app.post("/registro")
async def registrar(
    usuario_id: str = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    descripcion: str = Form(""),
    tipo_actividad: str = Form("campo"),  # Campo con valor por defecto para compatibilidad con registros offline antiguos
    categoria_actividad: str = Form(""),  # Campo con valor vacío por defecto para compatibilidad
    categoria_actividad_otro: str = Form(None),  # Campo opcional: especificación cuando se selecciona "Otro"
    foto: UploadFile = File(...),
    timestamp_offline: str = Form(None)  # Nuevo campo opcional para registro offline
):
    print(f"🔍 REGISTRO - Datos recibidos:")
    print(f"   usuario_id: {usuario_id}")
    print(f"   latitud: {latitud}")
    print(f"   longitud: {longitud}")
    print(f"   descripcion: {descripcion}")
    print(f"   tipo_actividad: {tipo_actividad}")
    print(f"   categoria_actividad: {categoria_actividad}")
    print(f"   categoria_actividad_otro: {categoria_actividad_otro}")
    print(f"   foto: {foto.filename}")
    print(f"   timestamp_offline: {timestamp_offline}")
    
    # Validar y corregir tipo de actividad con valor por defecto
    if not tipo_actividad or tipo_actividad not in ['campo', 'gabinete']:
        print(f"⚠️ tipo_actividad inválido o vacío ('{tipo_actividad}'), usando valor por defecto 'campo'")
        tipo_actividad = 'campo'
    
    # Validar categoría de actividad
    categorias_validas = [
        'Acompañamiento técnico',
        'Productivas directas',
        'Ahorro y trámites financieros',
        'Capacitación / talleres / cursos',
        'Difusión y comunicación',
        'Eventos comunitarios / ferias / tianguis',
        'Reuniones y asambleas',
        'Trabajo administrativo y captura',
        'Viveros y biofábricas',
        'Otro'
    ]
    
    # MEJORA: Asignar valor por defecto si categoria_actividad está vacía o es inválida
    if not categoria_actividad or categoria_actividad not in categorias_validas:
        # Inferir categoría basada en tipo de actividad
        if tipo_actividad == 'gabinete':
            categoria_actividad_default = 'Trabajo administrativo y captura'
        else:
            categoria_actividad_default = 'Acompañamiento técnico'
        print(f"⚠️ categoria_actividad inválida o vacía ('{categoria_actividad}'), usando valor por defecto '{categoria_actividad_default}'")
        categoria_actividad = categoria_actividad_default
    
    # Si la categoría es "Otro", se requiere especificación
    if categoria_actividad == 'Otro' and not categoria_actividad_otro:
        raise HTTPException(status_code=400, detail="Cuando categoria_actividad es 'Otro', se requiere especificar en categoria_actividad_otro")
    
    print(f"✅ Categoría de actividad válida: {categoria_actividad}" + (f" (Otro: {categoria_actividad_otro})" if categoria_actividad == 'Otro' else ""))
    
    print(f"✅ Tipo de actividad válido: {tipo_actividad}")
    
    # ✅ SOLUCIÓN: Usar la misma función que asistencias para manejar zona horaria CDMX
    if timestamp_offline:
        # Usar la función especializada que maneja correctamente CDMX
        fecha_cdmx, hora_cdmx_datetime, timestamp_for_filename = obtener_fecha_hora_cdmx(timestamp_offline)
        # ✅ CORRECCIÓN: Guardar en CDMX (igual que asistencias), no convertir a UTC
        fecha_hora = hora_cdmx_datetime.replace(tzinfo=None)
        print(f"📅 ✅ Usando timestamp offline con zona CDMX: {fecha_hora}")
    else:
        # ✅ SOLUCIÓN: Usar función CDMX en lugar de datetime.utcnow()
        fecha_cdmx, hora_cdmx_datetime, timestamp_for_filename = obtener_fecha_hora_cdmx()
        # ✅ CORRECCIÓN: Guardar en CDMX (igual que asistencias), no convertir a UTC
        fecha_hora = hora_cdmx_datetime.replace(tzinfo=None)
        print(f"📅 ⏰ Usando timestamp actual CDMX: {fecha_hora}")

    # Guardar la foto en disco usando el timestamp correcto
    # ✅ MEJORA: Añadir identificador único (milisegundos + random) para evitar colisiones
    # si se crean múltiples registros en el mismo segundo
    import random
    unique_id = f"{int(datetime.now().timestamp() * 1000) % 100000}_{random.randint(1000, 9999)}"
    ext = os.path.splitext(foto.filename)[1]
    nombre_archivo = f"{usuario_id}_{timestamp_for_filename}_{unique_id}{ext}"
    ruta_archivo = os.path.join(FOTOS_DIR, nombre_archivo)
    print(f"📁 Guardando foto como: {nombre_archivo}")
    
    with open(ruta_archivo, "wb") as f:
        contenido = await foto.read()
        f.write(contenido)

    # Guardar registro en la base usando consulta segura
    ejecutar_consulta_segura(
        "INSERT INTO registros (usuario_id, latitud, longitud, descripcion, foto_url, fecha_hora, tipo_actividad, categoria_actividad, categoria_actividad_otro) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (usuario_id, latitud, longitud, descripcion, ruta_archivo, fecha_hora, tipo_actividad, categoria_actividad, categoria_actividad_otro),
        fetch_type='none'
    )
    print(f"✅ Registro guardado en BD con fecha_hora: {fecha_hora}, tipo_actividad: {tipo_actividad}, categoria_actividad: {categoria_actividad}")

    return {"status": "ok", "foto_url": ruta_archivo, "tipo_actividad": tipo_actividad, "categoria_actividad": categoria_actividad}

# ENDPOINT CORREGIDO - Esta es la parte importante que debe actualizarse
@app.get("/registros")
def obtener_registros(usuario_id: int = None, limit: int = None, page: int = 1, page_size: int = 1000, territorio: str = None):
    try:
        # Aplicar límite de seguridad para evitar saturación del servidor
        if limit is None or limit > 5000:
            limit = 5000  # Límite máximo de seguridad
            print(f"⚠️ Aplicando límite de seguridad: {limit} registros")
        
        # Calcular offset para paginación
        offset = (page - 1) * page_size if page > 1 else 0
        
        print(f"🔍 Obteniendo registros - Usuario: {usuario_id}, Límite: {limit}, Página: {page}, Offset: {offset}, Territorio: {territorio}")
        
        # Construir query base con JOIN si hay filtro de territorio
        base_select = """SELECT r.id, r.usuario_id, r.latitud, r.longitud, r.descripcion, r.foto_url, r.fecha_hora, r.tipo_actividad, r.categoria_actividad, r.categoria_actividad_otro 
                        FROM registros r"""
        
        if territorio:
            base_select += " INNER JOIN usuarios u ON r.usuario_id = u.id"
        
        # Construir condiciones WHERE
        conditions = []
        params = []
        
        if usuario_id:
            conditions.append("r.usuario_id = %s")
            params.append(usuario_id)
        
        if territorio:
            conditions.append("u.territorio = %s")
            params.append(territorio)
        
        # Construir query completa
        query = base_select
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY r.fecha_hora DESC LIMIT %s OFFSET %s"
        
        effective_limit = min(limit, page_size) if limit else page_size
        params.extend([effective_limit, offset])
        
        # Ejecutar consulta con manejo seguro y timeout
        try:
            resultados = ejecutar_consulta_segura(query, tuple(params), fetch_type='all')
        except Exception as db_error:
            print(f"❌ Error de base de datos al obtener registros: {db_error}")
            # Si hay error, devolver respuesta vacía en lugar de fallar
            return {
                "registros": [],
                "total": 0,
                "error": "Error temporal de base de datos",
                "page": page,
                "page_size": page_size
            }
        
        if not resultados:
            resultados = []
        
        print(f"📊 Encontrados {len(resultados)} registros")
        
        # Obtener total de registros para paginación (solo si es necesario)
        total_registros = len(resultados)
        if page == 1 and len(resultados) == page_size:
            # Solo calcular total si podría haber más páginas
            try:
                count_query = "SELECT COUNT(*) FROM registros r"
                if territorio:
                    count_query += " INNER JOIN usuarios u ON r.usuario_id = u.id"
                count_conditions = []
                count_params = []
                if usuario_id:
                    count_conditions.append("r.usuario_id = %s")
                    count_params.append(usuario_id)
                if territorio:
                    count_conditions.append("u.territorio = %s")
                    count_params.append(territorio)
                if count_conditions:
                    count_query += " WHERE " + " AND ".join(count_conditions)
                cursor.execute(count_query, tuple(count_params) if count_params else None)
                total_registros = cursor.fetchone()[0]
            except Exception:
                total_registros = len(resultados)  # Fallback al conteo actual
        
        # Convertir tuplas a diccionarios manualmente con manejo de errores
        registros = []
        for i, row in enumerate(resultados):
            try:
                # ✅ SOLUCIÓN: Agregar zona horaria CDMX al ISO format para que JavaScript lo interprete correctamente
                fecha_iso = None
                if row[6]:
                    # row[6] es un datetime sin zona horaria (CDMX)
                    # Agregamos explícitamente la zona horaria CDMX (-06:00)
                    fecha_iso = row[6].isoformat() + "-06:00"
                    print(f"📅 Fecha con zona CDMX: {fecha_iso}")
                
                registro = {
                    "id": row[0],
                    "usuario_id": row[1],
                    "latitud": float(row[2]) if row[2] is not None else None,
                    "longitud": float(row[3]) if row[3] is not None else None,
                    "descripcion": row[4] if row[4] is not None else "",
                    "foto_url": row[5] if row[5] is not None else None,
                    "fecha_hora": fecha_iso,
                    "tipo_actividad": row[7] if len(row) > 7 and row[7] is not None else "campo",
                    "categoria_actividad": row[8] if len(row) > 8 and row[8] is not None else None,
                    "categoria_actividad_otro": row[9] if len(row) > 9 and row[9] is not None else None
                }
                registros.append(registro)
            except Exception as row_error:
                print(f"⚠️ Error procesando registro {i}: {row_error}")
                continue  # Saltar registros problemáticos
        
        print(f"✅ {len(registros)} registros procesados correctamente")
        
        # Respuesta con información de paginación
        response_data = {
            "registros": registros,
            "total": total_registros,
            "page": page,
            "page_size": page_size,
            "has_more": len(registros) == page_size
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener registros: {str(e)}")

# NUEVO ENDPOINT OPTIMIZADO PARA ADMIN-PWA
@app.get("/admin/registros")
def obtener_registros_admin(page: int = 1, page_size: int = 50, usuario_id: int = None, territorio: str = None, fecha_inicio: str = None, fecha_fin: str = None):
    """Endpoint optimizado para el admin-pwa con paginación obligatoria, filtro territorial y filtros por fecha"""
    try:
        # Límites de seguridad para admin
        max_page_size = 2000  # Aumentado para permitir cargas grandes con filtros de fecha
        page_size = min(page_size, max_page_size)
        page = max(1, page)  # Asegurar página mínima
        
        offset = (page - 1) * page_size
        
        print(f"🔍 [ADMIN] Obteniendo registros - Página: {page}, Tamaño: {page_size}, Offset: {offset}, Usuario: {usuario_id}, Territorio: {territorio}, Fechas: {fecha_inicio} a {fecha_fin}")
        
        # Verificar conexión antes de continuar
        if not verificar_conexion_db():
            raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
        
        # Construir consulta optimizada con JOIN si hay filtro territorial
        if territorio:
            base_query = """
                SELECT r.id, r.usuario_id, r.latitud, r.longitud, r.descripcion, r.foto_url, r.fecha_hora, r.tipo_actividad, r.categoria_actividad, r.categoria_actividad_otro 
                FROM registros r
                INNER JOIN usuarios u ON r.usuario_id = u.id
            """
            count_query = "SELECT COUNT(*) FROM registros r INNER JOIN usuarios u ON r.usuario_id = u.id"
        else:
            base_query = """
                SELECT id, usuario_id, latitud, longitud, descripcion, foto_url, fecha_hora, tipo_actividad, categoria_actividad, categoria_actividad_otro 
                FROM registros 
            """
            count_query = "SELECT COUNT(*) FROM registros"
        
        # Construir condiciones WHERE
        conditions = []
        params = []
        
        if usuario_id:
            if territorio:
                conditions.append("r.usuario_id = %s")
            else:
                conditions.append("usuario_id = %s")
            params.append(usuario_id)
        
        if territorio:
            conditions.append("u.territorio = %s")
            params.append(territorio)
        
        # Filtros por fecha
        if fecha_inicio:
            if territorio:
                conditions.append("r.fecha_hora >= %s")
            else:
                conditions.append("fecha_hora >= %s")
            params.append(fecha_inicio + " 00:00:00")
        
        if fecha_fin:
            if territorio:
                conditions.append("r.fecha_hora <= %s")
            else:
                conditions.append("fecha_hora <= %s")
            params.append(fecha_fin + " 23:59:59")
        
        # Agregar WHERE clause si hay condiciones
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
            base_query += where_clause
            count_query += where_clause
        
        # Obtener total de registros primero (para paginación)
        try:
            total_registros = ejecutar_consulta_segura(count_query, tuple(params) if params else None, fetch_type='one')[0]
        except Exception as count_error:
            print(f"⚠️ Error obteniendo conteo: {count_error}")
            total_registros = 0
        
        # Consulta principal con paginación y orden optimizado
        if territorio:
            main_query = base_query + " ORDER BY r.id DESC LIMIT %s OFFSET %s"
        else:
            main_query = base_query + " ORDER BY id DESC LIMIT %s OFFSET %s"
        
        pagination_params = tuple(params) + (page_size, offset) if params else (page_size, offset)
        
        try:
            resultados = ejecutar_consulta_segura(main_query, pagination_params, fetch_type='all')
        except Exception as query_error:
            print(f"❌ Error en consulta principal: {query_error}")
            return {
                "registros": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "has_more": False,
                "error": "Error temporal de base de datos"
            }
        
        if not resultados:
            resultados = []
        
        # Procesar resultados de forma segura
        registros = []
        for row in resultados:
            try:
                registro = {
                    "id": row[0],
                    "usuario_id": row[1],
                    "latitud": float(row[2]) if row[2] is not None else 0.0,
                    "longitud": float(row[3]) if row[3] is not None else 0.0,
                    "descripcion": row[4] if row[4] is not None else "",
                    "foto_url": row[5] if row[5] is not None else None,
                    "fecha_hora": row[6].isoformat() if row[6] else None,
                    "tipo_actividad": row[7] if len(row) > 7 and row[7] is not None else "campo",
                    "categoria_actividad": row[8] if len(row) > 8 and row[8] is not None else None,
                    "categoria_actividad_otro": row[9] if len(row) > 9 and row[9] is not None else None
                }
                registros.append(registro)
            except Exception as row_error:
                print(f"⚠️ Error procesando registro: {row_error}")
                continue
        
        # Calcular paginación
        total_pages = (total_registros + page_size - 1) // page_size if total_registros > 0 else 0
        has_more = page < total_pages
        
        print(f"✅ [ADMIN] {len(registros)} registros procesados - Total: {total_registros}, Páginas: {total_pages}")
        
        return {
            "registros": registros,
            "total": total_registros,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_more": has_more
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [ADMIN] Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener registros: {str(e)}")

# NUEVO ENDPOINT PARA ESTADÍSTICAS COMPLETAS (SIN LÍMITES)
@app.get("/estadisticas")
def obtener_estadisticas(territorio: str = None):
    """Obtener estadísticas completas del sistema sin límites.
    Si se proporciona territorio, filtra las estadísticas solo para usuarios de ese territorio."""
    try:
        print(f"🔍 Obteniendo estadísticas completas del sistema (territorio: {territorio or 'TODOS'})")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Si hay filtro por territorio, obtener los IDs de usuarios de ese territorio
        usuario_ids_territorio = None
        if territorio:
            cursor.execute("SELECT id FROM usuarios WHERE territorio = %s", (territorio,))
            usuario_ids_territorio = [row[0] for row in cursor.fetchall()]
            print(f"📊 Usuarios en territorio '{territorio}': {len(usuario_ids_territorio)}")
            
            if not usuario_ids_territorio:
                # Si no hay usuarios en el territorio, devolver estadísticas en cero
                return {"estadisticas": {
                    "total_registros": 0,
                    "total_usuarios": 0,
                    "registros_hoy": 0,
                    "total_asistencias": 0,
                    "asistencias_hoy": 0,
                    "usuarios_presentes": 0,
                    "territorio": territorio
                }}
        
        # Obtener total real de registros (actividades)
        if territorio and usuario_ids_territorio:
            cursor.execute("SELECT COUNT(*) FROM registros WHERE usuario_id = ANY(%s)", (usuario_ids_territorio,))
        else:
            cursor.execute("SELECT COUNT(*) FROM registros")
        total_registros = cursor.fetchone()[0]
        
        # Obtener total de usuarios
        if territorio:
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE territorio = %s", (territorio,))
        else:
            cursor.execute("SELECT COUNT(*) FROM usuarios")
        total_usuarios = cursor.fetchone()[0]
        
        # Obtener registros de hoy
        if territorio and usuario_ids_territorio:
            cursor.execute("SELECT COUNT(*) FROM registros WHERE DATE(fecha_hora) = CURRENT_DATE AND usuario_id = ANY(%s)", (usuario_ids_territorio,))
        else:
            cursor.execute("SELECT COUNT(*) FROM registros WHERE DATE(fecha_hora) = CURRENT_DATE")
        registros_hoy = cursor.fetchone()[0]
        
        # Obtener total de asistencias
        if territorio and usuario_ids_territorio:
            cursor.execute("SELECT COUNT(*) FROM asistencias WHERE usuario_id = ANY(%s)", (usuario_ids_territorio,))
        else:
            cursor.execute("SELECT COUNT(*) FROM asistencias")
        total_asistencias = cursor.fetchone()[0]
        
        # Obtener asistencias de hoy (usando zona horaria de Ciudad de México)
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE fecha = (CURRENT_DATE AT TIME ZONE 'America/Mexico_City')::date
                AND usuario_id = ANY(%s)
            """, (usuario_ids_territorio,))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE fecha = (CURRENT_DATE AT TIME ZONE 'America/Mexico_City')::date
            """)
        asistencias_hoy = cursor.fetchone()[0]
        
        # Obtener usuarios presentes AHORA (con entrada pero SIN salida) - tiempo real CDMX
        # Solo cuenta usuarios que marcaron entrada hoy pero aún NO han marcado salida
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(DISTINCT usuario_id) FROM asistencias 
                WHERE fecha = (CURRENT_DATE AT TIME ZONE 'America/Mexico_City')::date
                AND hora_entrada IS NOT NULL
                AND hora_salida IS NULL
                AND usuario_id = ANY(%s)
            """, (usuario_ids_territorio,))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT usuario_id) FROM asistencias 
                WHERE fecha = (CURRENT_DATE AT TIME ZONE 'America/Mexico_City')::date
                AND hora_entrada IS NOT NULL
                AND hora_salida IS NULL
            """)
        usuarios_presentes = cursor.fetchone()[0]
        
        estadisticas = {
            "total_registros": total_registros,
            "total_usuarios": total_usuarios,
            "registros_hoy": registros_hoy,
            "total_asistencias": total_asistencias,
            "asistencias_hoy": asistencias_hoy,
            "usuarios_presentes": usuarios_presentes
        }
        
        # Agregar info de territorio si se filtró
        if territorio:
            estadisticas["territorio"] = territorio
        
        print(f"✅ Estadísticas obtenidas (tiempo real CDMX){' para territorio: ' + territorio if territorio else ''}:")
        print(f"   - Total asistencias: {total_asistencias:,}")
        print(f"   - Asistencias hoy: {asistencias_hoy}")
        print(f"   - Usuarios PRESENTES ahora (con entrada, sin salida): {usuarios_presentes}")
        print(f"   - Total registros: {total_registros:,}")
        print(f"   - Registros hoy: {registros_hoy}")
        print(f"   - Total usuarios: {total_usuarios}")
        
        return {"estadisticas": estadisticas}
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

# ENDPOINT ULTRA-OPTIMIZADO PARA CONTADORES EN TIEMPO REAL (APPLE-STYLE)
@app.get("/estadisticas/rapidas")
def obtener_estadisticas_rapidas(territorio: str = None):
    """Endpoint ultra-optimizado para obtener estadísticas de contadores en < 50ms.
    Usa una sola query optimizada con índices para máxima velocidad (Apple-style).
    Cache recomendado: 3-5 segundos en frontend."""
    try:
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Obtener fecha actual en zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        fecha_hoy_cdmx = datetime.now(cdmx_tz).date()
        
        # Query ultra-optimizada con una sola ejecución usando CTEs
        if territorio:
            # Con filtro de territorio
            query = """
            WITH usuarios_territorio AS (
                SELECT id FROM usuarios WHERE territorio = %s
            ),
            stats_hoy AS (
                SELECT 
                    COUNT(*) as asistencias_hoy,
                    COUNT(DISTINCT CASE WHEN hora_entrada IS NOT NULL AND hora_salida IS NULL 
                          THEN usuario_id END) as usuarios_presentes
                FROM asistencias
                WHERE fecha = %s
                AND usuario_id IN (SELECT id FROM usuarios_territorio)
            ),
            stats_totales AS (
                SELECT COUNT(*) as total_asistencias
                FROM asistencias
                WHERE usuario_id IN (SELECT id FROM usuarios_territorio)
            )
            SELECT 
                (SELECT asistencias_hoy FROM stats_hoy) as asistencias_hoy,
                (SELECT usuarios_presentes FROM stats_hoy) as usuarios_presentes,
                (SELECT total_asistencias FROM stats_totales) as total_asistencias
            """
            cursor.execute(query, (territorio, fecha_hoy_cdmx))
        else:
            # Sin filtro de territorio - aún más rápido
            query = """
            WITH stats_hoy AS (
                SELECT 
                    COUNT(*) as asistencias_hoy,
                    COUNT(DISTINCT CASE WHEN hora_entrada IS NOT NULL AND hora_salida IS NULL 
                          THEN usuario_id END) as usuarios_presentes
                FROM asistencias
                WHERE fecha = %s
            ),
            stats_totales AS (
                SELECT COUNT(*) as total_asistencias
                FROM asistencias
            )
            SELECT 
                (SELECT asistencias_hoy FROM stats_hoy) as asistencias_hoy,
                (SELECT usuarios_presentes FROM stats_hoy) as usuarios_presentes,
                (SELECT total_asistencias FROM stats_totales) as total_asistencias
            """
            cursor.execute(query, (fecha_hoy_cdmx,))
        
        resultado = cursor.fetchone()
        
        estadisticas = {
            "asistencias_hoy": resultado[0] or 0,
            "usuarios_presentes": resultado[1] or 0,
            "total_asistencias": resultado[2] or 0,
            "timestamp": datetime.now(cdmx_tz).isoformat()
        }
        
        if territorio:
            estadisticas["territorio"] = territorio
        
        return {"estadisticas": estadisticas, "cache_ttl": 5}
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas rápidas: {str(e)}")

# NUEVOS ENDPOINTS PARA ESTADÍSTICAS DEL DÍA EN HORARIO CDMX
@app.get("/estadisticas/dia-actual")
def obtener_estadisticas_dia_actual(territorio: str = None):
    """Obtener estadísticas del día actual en horario CDMX (America/Mexico_City).
    Si se proporciona territorio, filtra las estadísticas solo para usuarios de ese territorio."""
    conexion_local = None
    try:
        print(f"🔍 Obteniendo estadísticas del día actual en horario CDMX (territorio: {territorio or 'TODOS'})")

        # Cursor propio y aislado del global — ver abrir_conexion_aislada()
        conexion_local, cursor = abrir_conexion_aislada()

        # Configurar zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        print(f"📅 Calculando para fecha CDMX: {fecha_hoy_cdmx}")
        
        # Si hay filtro por territorio, obtener los IDs de usuarios de ese territorio
        usuario_ids_territorio = None
        if territorio:
            cursor.execute("SELECT id FROM usuarios WHERE territorio = %s", (territorio,))
            usuario_ids_territorio = [row[0] for row in cursor.fetchall()]
            print(f"📊 Usuarios en territorio '{territorio}': {len(usuario_ids_territorio)}")
            
            if not usuario_ids_territorio:
                # Si no hay usuarios en el territorio, devolver estadísticas en cero
                return {"estadisticas": {
                    "total_usuarios_dia": 0,
                    "entradas_dia": 0,
                    "salidas_dia": 0,
                    "actividades_dia": 0,
                    "fecha_cdmx": fecha_hoy_cdmx.isoformat(),
                    "territorio": territorio
                }}
        
        # Obtener rango de fechas en UTC para el día actual CDMX
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        # Convertir a UTC para consultar la BD
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        # 1. Total de usuarios únicos que tuvieron al menos un registro hoy
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(DISTINCT usuario_id) FROM (
                    SELECT usuario_id FROM registros 
                    WHERE fecha_hora >= %s AND fecha_hora <= %s AND usuario_id = ANY(%s)
                    UNION
                    SELECT usuario_id FROM asistencias 
                    WHERE ((hora_entrada >= %s AND hora_entrada <= %s) 
                       OR (hora_salida >= %s AND hora_salida <= %s))
                       AND usuario_id = ANY(%s)
                ) AS usuarios_activos
            """, (inicio_utc, fin_utc, usuario_ids_territorio, inicio_utc, fin_utc, inicio_utc, fin_utc, usuario_ids_territorio))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT usuario_id) FROM (
                    SELECT usuario_id FROM registros 
                    WHERE fecha_hora >= %s AND fecha_hora <= %s
                    UNION
                    SELECT usuario_id FROM asistencias 
                    WHERE (hora_entrada >= %s AND hora_entrada <= %s) 
                       OR (hora_salida >= %s AND hora_salida <= %s)
                ) AS usuarios_activos
            """, (inicio_utc, fin_utc, inicio_utc, fin_utc, inicio_utc, fin_utc))
        total_usuarios_dia = cursor.fetchone()[0]
        
        # 2. Total de entradas del día
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE hora_entrada >= %s AND hora_entrada <= %s AND usuario_id = ANY(%s)
            """, (inicio_utc, fin_utc, usuario_ids_territorio))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE hora_entrada >= %s AND hora_entrada <= %s
            """, (inicio_utc, fin_utc))
        entradas_dia = cursor.fetchone()[0]
        
        # 3. Total de salidas del día
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE hora_salida >= %s AND hora_salida <= %s AND usuario_id = ANY(%s)
            """, (inicio_utc, fin_utc, usuario_ids_territorio))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM asistencias 
                WHERE hora_salida >= %s AND hora_salida <= %s
            """, (inicio_utc, fin_utc))
        salidas_dia = cursor.fetchone()[0]
        
        # 4. Total de actividades/registros del día
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT COUNT(*) FROM registros 
                WHERE fecha_hora >= %s AND fecha_hora <= %s AND usuario_id = ANY(%s)
            """, (inicio_utc, fin_utc, usuario_ids_territorio))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM registros 
                WHERE fecha_hora >= %s AND fecha_hora <= %s
            """, (inicio_utc, fin_utc))
        actividades_dia = cursor.fetchone()[0]
        
        estadisticas_dia = {
            "total_usuarios_dia": total_usuarios_dia,
            "entradas_dia": entradas_dia,
            "salidas_dia": salidas_dia,
            "actividades_dia": actividades_dia,
            "fecha_cdmx": fecha_hoy_cdmx.isoformat()
        }
        
        # Agregar info de territorio si se filtró
        if territorio:
            estadisticas_dia["territorio"] = territorio
        
        print(f"✅ Estadísticas del día CDMX obtenidas{' para territorio: ' + territorio if territorio else ''}: {estadisticas_dia}")
        return {"estadisticas": estadisticas_dia}
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas del día: {str(e)}")
    finally:
        if conexion_local:
            conexion_local.close()

@app.get("/estadisticas/usuarios-dia")
def obtener_usuarios_activos_dia():
    """Obtener total de usuarios únicos activos del día actual en horario CDMX"""
    try:
        print("👥 Obteniendo usuarios únicos activos del día CDMX")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Configurar zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        # Obtener rango de fechas en UTC para el día actual CDMX
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        # Convertir a UTC para consultar la BD
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        # Obtener usuarios únicos que tuvieron actividad hoy
        cursor.execute("""
            SELECT COUNT(DISTINCT usuario_id) FROM (
                SELECT usuario_id FROM registros 
                WHERE fecha_hora >= %s AND fecha_hora <= %s
                UNION
                SELECT usuario_id FROM asistencias 
                WHERE (hora_entrada >= %s AND hora_entrada <= %s) 
                   OR (hora_salida >= %s AND hora_salida <= %s)
            ) AS usuarios_activos
        """, (inicio_utc, fin_utc, inicio_utc, fin_utc, inicio_utc, fin_utc))
        
        total_usuarios = cursor.fetchone()[0]
        
        return {
            "total_usuarios_dia": total_usuarios,
            "fecha_cdmx": fecha_hoy_cdmx.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo usuarios del día: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/estadisticas/entradas-dia")
def obtener_entradas_dia():
    """Obtener total de entradas del día actual en horario CDMX"""
    try:
        print("🚪➡️ Obteniendo entradas del día CDMX")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Configurar zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        # Obtener rango de fechas en UTC para el día actual CDMX
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        # Convertir a UTC para consultar la BD
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        cursor.execute("""
            SELECT COUNT(*) FROM asistencias 
            WHERE hora_entrada >= %s AND hora_entrada <= %s
        """, (inicio_utc, fin_utc))
        
        entradas = cursor.fetchone()[0]
        
        return {
            "entradas_dia": entradas,
            "fecha_cdmx": fecha_hoy_cdmx.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo entradas del día: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/estadisticas/salidas-dia")
def obtener_salidas_dia():
    """Obtener total de salidas del día actual en horario CDMX"""
    try:
        print("🚪⬅️ Obteniendo salidas del día CDMX")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Configurar zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        # Obtener rango de fechas en UTC para el día actual CDMX
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        # Convertir a UTC para consultar la BD
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        cursor.execute("""
            SELECT COUNT(*) FROM asistencias 
            WHERE hora_salida >= %s AND hora_salida <= %s
        """, (inicio_utc, fin_utc))
        
        salidas = cursor.fetchone()[0]
        
        return {
            "salidas_dia": salidas,
            "fecha_cdmx": fecha_hoy_cdmx.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo salidas del día: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/estadisticas/actividades-dia")
def obtener_actividades_dia():
    """Obtener total de actividades/registros del día actual en horario CDMX"""
    try:
        print("📝 Obteniendo actividades del día CDMX")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Configurar zona horaria CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        # Obtener rango de fechas en UTC para el día actual CDMX
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        # Convertir a UTC para consultar la BD
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        cursor.execute("""
            SELECT COUNT(*) FROM registros 
            WHERE fecha_hora >= %s AND fecha_hora <= %s
        """, (inicio_utc, fin_utc))
        
        actividades = cursor.fetchone()[0]
        
        return {
            "actividades_dia": actividades,
            "fecha_cdmx": fecha_hoy_cdmx.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo actividades del día: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# NUEVO ENDPOINT PARA ESTADÍSTICAS POR TIPO DE ACTIVIDAD
@app.get("/estadisticas/tipo-actividad")
def obtener_estadisticas_tipo_actividad(territorio: str = None):
    """Obtener estadísticas de registros por tipo de actividad.
    Si se proporciona territorio, filtra las estadísticas solo para usuarios de ese territorio."""
    conexion_local = None
    try:
        print(f"📊 Obteniendo estadísticas por tipo de actividad (territorio: {territorio or 'TODOS'})")

        # Cursor propio y aislado del global — ver abrir_conexion_aislada()
        conexion_local, cursor = abrir_conexion_aislada()

        # Si hay filtro por territorio, obtener los IDs de usuarios de ese territorio
        usuario_ids_territorio = None
        filtro_usuarios_sql = ""
        if territorio:
            cursor.execute("SELECT id FROM usuarios WHERE territorio = %s", (territorio,))
            usuario_ids_territorio = [row[0] for row in cursor.fetchall()]
            print(f"📊 Usuarios en territorio '{territorio}': {len(usuario_ids_territorio)}")
            
            if not usuario_ids_territorio:
                # Si no hay usuarios en el territorio, devolver estadísticas en cero
                return {"estadisticas_tipo": {
                    "total": {
                        "campo": 0,
                        "gabinete": 0,
                        "total_general": 0
                    },
                    "dia_actual": {
                        "campo": 0,
                        "gabinete": 0,
                        "total_dia": 0,
                        "fecha_cdmx": datetime.now(pytz.timezone('America/Mexico_City')).date().isoformat()
                    },
                    "territorio": territorio
                }}
        
        # Obtener estadísticas generales por tipo
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT 
                    COALESCE(tipo_actividad, 'campo') as tipo,
                    COUNT(*) as total
                FROM registros 
                WHERE usuario_id = ANY(%s)
                GROUP BY COALESCE(tipo_actividad, 'campo')
                ORDER BY total DESC
            """, (usuario_ids_territorio,))
        else:
            cursor.execute("""
                SELECT 
                    COALESCE(tipo_actividad, 'campo') as tipo,
                    COUNT(*) as total
                FROM registros 
                GROUP BY COALESCE(tipo_actividad, 'campo')
                ORDER BY total DESC
            """)
        tipos_general = cursor.fetchall()
        
        # Obtener estadísticas del día actual por tipo en CDMX
        cdmx_tz = pytz.timezone('America/Mexico_City')
        ahora_cdmx = datetime.now(cdmx_tz)
        fecha_hoy_cdmx = ahora_cdmx.date()
        
        inicio_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.min.time()))
        fin_dia_cdmx = cdmx_tz.localize(datetime.combine(fecha_hoy_cdmx, datetime.max.time()))
        
        inicio_utc = inicio_dia_cdmx.astimezone(pytz.UTC)
        fin_utc = fin_dia_cdmx.astimezone(pytz.UTC)
        
        if territorio and usuario_ids_territorio:
            cursor.execute("""
                SELECT 
                    COALESCE(tipo_actividad, 'campo') as tipo,
                    COUNT(*) as total_dia
                FROM registros 
                WHERE fecha_hora >= %s AND fecha_hora <= %s AND usuario_id = ANY(%s)
                GROUP BY COALESCE(tipo_actividad, 'campo')
                ORDER BY total_dia DESC
            """, (inicio_utc, fin_utc, usuario_ids_territorio))
        else:
            cursor.execute("""
                SELECT 
                    COALESCE(tipo_actividad, 'campo') as tipo,
                    COUNT(*) as total_dia
                FROM registros 
                WHERE fecha_hora >= %s AND fecha_hora <= %s
                GROUP BY COALESCE(tipo_actividad, 'campo')
                ORDER BY total_dia DESC
            """, (inicio_utc, fin_utc))
        tipos_dia = cursor.fetchall()
        
        # Convertir resultados
        estadisticas_general = {tipo[0]: tipo[1] for tipo in tipos_general}
        estadisticas_dia = {tipo[0]: tipo[1] for tipo in tipos_dia}
        
        # Asegurar que ambos tipos estén presentes
        for tipo in ['campo', 'gabinete']:
            if tipo not in estadisticas_general:
                estadisticas_general[tipo] = 0
            if tipo not in estadisticas_dia:
                estadisticas_dia[tipo] = 0
        
        resultado = {
            "total": {
                "campo": estadisticas_general['campo'],
                "gabinete": estadisticas_general['gabinete'],
                "total_general": sum(estadisticas_general.values())
            },
            "dia_actual": {
                "campo": estadisticas_dia['campo'],
                "gabinete": estadisticas_dia['gabinete'],
                "total_dia": sum(estadisticas_dia.values()),
                "fecha_cdmx": fecha_hoy_cdmx.isoformat()
            }
        }
        
        # Agregar info de territorio si se filtró
        if territorio:
            resultado["territorio"] = territorio
        
        print(f"📊 Estadísticas por tipo de actividad obtenidas{' para territorio: ' + territorio if territorio else ''}: {resultado}")
        return {"estadisticas_tipo": resultado}
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas por tipo: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if conexion_local:
            conexion_local.close()

# ==================== ENDPOINTS PARA REPORTES GENERADOS ====================

@app.post("/reportes/guardar")
async def guardar_reporte(datos: dict):
    """
    Guardar un reporte generado en la base de datos.
    
    NUEVO FLUJO:
    - Se guardan los DATOS del reporte (JSON) + firma del usuario
    - NO se genera el PDF aquí, se genera al descargar
    - El supervisor puede firmar después
    - El PDF final se genera con ambas firmas cuando se descarga
    """
    try:
        # Verificar conexión a la base de datos
        verificar_conexion_db()
        
        usuario_id = datos.get('usuario_id')
        nombre_reporte = datos.get('nombre_reporte')
        mes = datos.get('mes')
        anio = datos.get('anio')
        tipo = datos.get('tipo')  # PDF o CSV
        
        # NUEVO: Datos estructurados del reporte
        datos_reporte = datos.get('datos_reporte')  # JSON con actividades, info usuario, etc.
        firma_usuario_base64 = datos.get('firma_usuario_base64')  # Firma del usuario
        
        # Mantener compatibilidad con el flujo anterior
        pdf_base64 = datos.get('pdf_base64')  # PDF en formato base64 (opcional ahora)
        
        print(f"📥 Recibiendo reporte para guardar:")
        print(f"   - usuario_id: {usuario_id}")
        print(f"   - nombre_reporte: {nombre_reporte}")
        print(f"   - mes: {mes}, anio: {anio}")
        print(f"   - tipo: {tipo}")
        print(f"   - datos_reporte: {'Sí' if datos_reporte else 'No'}")
        print(f"   - firma_usuario_base64: {'Sí (' + str(len(firma_usuario_base64)) + ' chars)' if firma_usuario_base64 else 'No'}")
        print(f"   - pdf_base64: {'Sí (' + str(len(pdf_base64)) + ' chars)' if pdf_base64 else 'No'}")
        
        if not all([usuario_id, nombre_reporte, tipo]):
            raise HTTPException(status_code=400, detail="Faltan datos requeridos")
        
        # Verificar si ya existe un reporte para este mes/año
        if mes and anio:
            cursor.execute("""
                SELECT id, nombre_reporte, fecha_generacion 
                FROM reportes_generados 
                WHERE usuario_id = %s AND mes = %s AND anio = %s
            """, (usuario_id, mes, anio))
            existente = cursor.fetchone()
            if existente:
                print(f"⚠️ Ya existe reporte para {mes} {anio}: ID {existente[0]}")
                raise HTTPException(
                    status_code=409, 
                    detail=f"Ya existe un reporte firmado para {mes} {anio}. Solo puedes generar un reporte por mes."
                )
        
        print(f"💾 Guardando reporte: {nombre_reporte} para usuario {usuario_id}")
        
        # Convertir datos_reporte a JSON si es dict
        import json as json_module
        datos_reporte_json = json_module.dumps(datos_reporte) if datos_reporte else None
        
        cursor.execute("""
            INSERT INTO reportes_generados 
            (usuario_id, nombre_reporte, mes, anio, tipo, fecha_generacion, pdf_base64, datos_reporte, firma_usuario_base64)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
            RETURNING id, fecha_generacion
        """, (usuario_id, nombre_reporte, mes, anio, tipo, pdf_base64, datos_reporte_json, firma_usuario_base64))
        
        resultado = cursor.fetchone()
        conn.commit()
        
        print(f"✅ Reporte guardado exitosamente con ID: {resultado[0]}")
        
        return {
            "success": True,
            "reporte_id": resultado[0],
            "fecha_generacion": resultado[1].isoformat() if resultado[1] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando reporte: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar reporte: {str(e)}")


@app.get("/reportes/verificar/{usuario_id}")
async def verificar_reporte_existente(usuario_id: int, mes: str, anio: int):
    """Verificar si ya existe un reporte para el mes/año especificado"""
    try:
        print(f"🔍 Verificando reporte existente para usuario {usuario_id}: {mes} {anio}")
        
        cursor.execute("""
            SELECT id, nombre_reporte, fecha_generacion,
                   COALESCE(firmado_supervisor, false) as firmado_supervisor,
                   nombre_supervisor
            FROM reportes_generados 
            WHERE usuario_id = %s AND mes = %s AND anio = %s
        """, (usuario_id, mes, anio))
        
        existente = cursor.fetchone()
        
        if existente:
            print(f"✅ Reporte encontrado: ID {existente[0]}")
            return {
                "success": True,
                "existe": True,
                "reporte": {
                    "id": existente[0],
                    "nombre": existente[1],
                    "fecha_generacion": existente[2].isoformat() if existente[2] else None,
                    "firmado_supervisor": existente[3],
                    "firmado_territorial": existente[3],  # alias para compatibilidad
                    "nombre_supervisor": existente[4]
                }
            }
        else:
            print(f"ℹ️ No existe reporte para {mes} {anio}")
            return {
                "success": True,
                "existe": False
            }
            
    except Exception as e:
        print(f"❌ Error verificando reporte: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/reportes/historial/{usuario_id}")
async def obtener_historial_reportes(usuario_id: int, limite: int = 50):
    """Obtener el historial de reportes generados por un usuario"""
    try:
        # Verificar conexión a la base de datos
        verificar_conexion_db()
        
        print(f"📋 Obteniendo historial de reportes para usuario {usuario_id}")
        
        cursor.execute("""
            SELECT 
                id,
                nombre_reporte,
                mes,
                anio,
                tipo,
                fecha_generacion,
                CASE WHEN pdf_base64 IS NOT NULL AND pdf_base64 != '' THEN true ELSE false END as tiene_pdf,
                COALESCE(firmado_supervisor, false) as firmado_supervisor,
                fecha_firma_supervisor,
                nombre_supervisor
            FROM reportes_generados
            WHERE usuario_id = %s
            ORDER BY fecha_generacion DESC
            LIMIT %s
        """, (usuario_id, limite))
        
        reportes = cursor.fetchall()
        
        resultado = []
        for reporte in reportes:
            resultado.append({
                "id": reporte[0],
                "nombre": reporte[1],
                "mes": reporte[2],
                "anio": reporte[3],
                "tipo": reporte[4],
                "fecha": reporte[5].isoformat() if reporte[5] else None,
                "tiene_pdf": reporte[6] if len(reporte) > 6 else False,
                "firmado_supervisor": reporte[7] if len(reporte) > 7 else False,
                "fecha_firma_supervisor": reporte[8].isoformat() if len(reporte) > 8 and reporte[8] else None,
                "nombre_supervisor": reporte[9] if len(reporte) > 9 else None
            })
        
        print(f"✅ {len(resultado)} reportes encontrados para usuario {usuario_id}")
        if resultado:
            print(f"   📄 Primer reporte: {resultado[0].get('nombre')}, tiene_pdf: {resultado[0].get('tiene_pdf')}")
        
        return {
            "success": True,
            "reportes": resultado,
            "total": len(resultado)
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo historial de reportes: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.delete("/reportes/eliminar/{reporte_id}")
async def eliminar_reporte(reporte_id: int):
    """Eliminar un reporte de la base de datos"""
    try:
        # Verificar conexión a la base de datos
        verificar_conexion_db()
        
        print(f"🗑️ Eliminando reporte ID: {reporte_id}")
        
        # Verificar que el reporte existe y si está firmado
        cursor.execute("""
            SELECT id, nombre_reporte, COALESCE(firmado_supervisor, false) as firmado
            FROM reportes_generados WHERE id = %s
        """, (reporte_id,))
        reporte = cursor.fetchone()
        
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
        # Eliminar el reporte (permitido incluso si está firmado)
        cursor.execute("DELETE FROM reportes_generados WHERE id = %s", (reporte_id,))
        conn.commit()
        
        print(f"✅ Reporte eliminado: {reporte[1]}")
        
        return {
            "success": True,
            "message": f"Reporte '{reporte[1]}' eliminado correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando reporte: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/reportes/descargar/{reporte_id}")
async def descargar_reporte(reporte_id: int):
    """
    Obtener los datos de un reporte guardado para generar el PDF en el frontend.
    
    NUEVO FLUJO:
    - Devuelve los datos estructurados del reporte (datos_reporte JSON)
    - Incluye la firma del usuario (firma_usuario_base64)
    - Incluye la firma del supervisor si existe (firma_supervisor_base64)
    - El frontend genera el PDF con las firmas disponibles
    - Si hay pdf_base64 guardado (compatibilidad), también lo devuelve
    - ACTUALIZADO: Obtiene la CURP actual del usuario desde la BD
    """
    try:
        print(f"📥 Descargando reporte ID: {reporte_id}")
        
        cursor.execute("""
            SELECT 
                r.id,
                r.nombre_reporte,
                r.mes,
                r.anio,
                r.tipo,
                r.fecha_generacion,
                r.pdf_base64,
                COALESCE(r.firmado_supervisor, false) as firmado_supervisor,
                r.fecha_firma_supervisor,
                r.firma_supervisor_base64,
                r.nombre_supervisor,
                r.supervisor_id,
                r.datos_reporte,
                r.firma_usuario_base64,
                r.usuario_id,
                u.curp as curp_actual,
                u.nombre_completo as nombre_actual,
                u.territorio as territorio_actual,
                COALESCE(au.nombre_completo, uf.nombre_completo) as facilitador_nombre
            FROM reportes_generados r
            LEFT JOIN usuarios u ON r.usuario_id = u.id
            LEFT JOIN facilitador_tecnico_asignaciones fta
                ON fta.tecnico_usuario_id = r.usuario_id AND fta.activo = TRUE
            LEFT JOIN admin_users au ON au.id = fta.facilitador_admin_id
            LEFT JOIN usuarios uf ON uf.id = fta.facilitador_usuario_id
            WHERE r.id = %s
        """, (reporte_id,))
        
        reporte = cursor.fetchone()
        
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
        pdf_base64 = reporte[6]
        datos_reporte = reporte[12]  # JSONB - puede ser dict o string
        firma_usuario_base64 = reporte[13]
        usuario_id = reporte[14]
        curp_actual = reporte[15]
        nombre_actual = reporte[16]
        territorio_actual = reporte[17]
        
        # Si no hay datos_reporte ni pdf_base64, no hay nada que descargar
        if not pdf_base64 and not datos_reporte:
            raise HTTPException(status_code=404, detail="El reporte no tiene datos disponibles para descarga")
        
        print(f"✅ Reporte encontrado: {reporte[1]}")
        print(f"   Firmado por supervisor: {reporte[7]}")
        print(f"   Tiene datos_reporte: {'Sí' if datos_reporte else 'No'}")
        print(f"   Tiene pdf_base64: {'Sí' if pdf_base64 else 'No'}")
        print(f"   Tiene firma_usuario: {'Sí' if firma_usuario_base64 else 'No'}")
        print(f"   Usuario ID: {usuario_id}")
        print(f"   CURP actual del usuario: {curp_actual}")
        
        # Actualizar datos_reporte con CURP actual del usuario
        if datos_reporte and curp_actual:
            # Si datos_reporte es string JSON, parsearlo
            if isinstance(datos_reporte, str):
                import json as json_module
                datos_reporte = json_module.loads(datos_reporte)
            
            # Actualizar o crear la sección usuario con CURP actual
            if isinstance(datos_reporte, dict):
                if 'usuario' not in datos_reporte:
                    datos_reporte['usuario'] = {}
                
                # Actualizar con los datos actuales de la BD
                datos_reporte['usuario']['curp'] = curp_actual
                if nombre_actual:
                    datos_reporte['usuario']['nombre'] = nombre_actual
                if territorio_actual:
                    datos_reporte['usuario']['territorio'] = territorio_actual
                
                print(f"   ✅ CURP actualizada en datos_reporte: {curp_actual}")
        
        return {
            "success": True,
            "reporte": {
                "id": reporte[0],
                "nombre": reporte[1],
                "mes": reporte[2],
                "anio": reporte[3],
                "tipo": reporte[4],
                "fecha": reporte[5].isoformat() if reporte[5] else None,
                "pdf_base64": pdf_base64,  # Para compatibilidad con reportes antiguos
                # Datos estructurados del reporte (NUEVO - con CURP actualizada)
                "datos_reporte": datos_reporte,
                "firma_usuario_base64": firma_usuario_base64,
                # Datos de firma del supervisor
                "firmado_supervisor": reporte[7] or False,
                "fecha_firma_supervisor": reporte[8].isoformat() if reporte[8] else None,
                "firma_supervisor_base64": reporte[9],
                "nombre_supervisor": reporte[10],
                "supervisor_id": reporte[11],
                "facilitador_nombre": reporte[18]  # Nombre del facilitador asignado (si existe)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error descargando reporte: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ============================================
# ENDPOINT PARA FIRMAR REPORTES (SUPERVISOR)
# ============================================

class FirmaReporteRequest(BaseModel):
    supervisor_id: int = 0          # mantenido por compatibilidad, se ignora si el firmante es facilitador
    nombre_supervisor: str = ""     # idem, se ignora si el firmante es facilitador
    firma_base64: Optional[str] = None
    admin_id: Optional[int] = None  # ID del admin firmante para validación de facilitador

@app.post("/reportes/firmar/{reporte_id}")
async def firmar_reporte_supervisor(reporte_id: int, firma_data: FirmaReporteRequest):
    """
    Permite firmar un reporte.
    - Si admin_id tiene permiso 'firmas' → flujo facilitador (validación BD estricta)
    - Si no → flujo legacy supervisor (sin cambios)
    """
    try:
        verificar_conexion_db()
        print(f"✍️ [FIRMA] Firmando reporte ID: {reporte_id}, admin_id: {firma_data.admin_id}")

        # ─── Flujo Facilitador ───────────────────────────────────────
        if firma_data.admin_id:
            cursor.execute(
                "SELECT id, usuario_id, permisos, nombre_completo FROM admin_users WHERE id = %s AND activo = TRUE",
                (firma_data.admin_id,)
            )
            admin = cursor.fetchone()
            if not admin:
                raise HTTPException(status_code=403, detail="Acceso denegado: usuario no encontrado")

            admin_db_id, usuario_id, permisos_raw, nombre_admin = admin

            # Verificar permiso 'firmas'
            import json as _json
            permisos = {}
            if permisos_raw:
                try:
                    permisos = _json.loads(permisos_raw)
                except Exception:
                    pass

            # Si no tiene permiso firmas y tampoco es admin, rechazar
            es_admin_rol = False
            cursor.execute("SELECT rol FROM admin_users WHERE id=%s", (admin_db_id,))
            rol_row = cursor.fetchone()
            if rol_row and rol_row[0] == 'admin':
                es_admin_rol = True

            if not permisos.get('firmas') and not es_admin_rol:
                raise HTTPException(status_code=403, detail="No tienes permiso para firmar reportes")

            if permisos.get('firmas') and not es_admin_rol:
                # Es facilitador: validar cargo en admin_users (no requerimos usuario_id)
                cursor.execute("SELECT cargo, nombre_completo FROM admin_users WHERE id = %s", (admin_db_id,))
                au_row = cursor.fetchone()
                if not au_row or 'FACILITADOR' not in (au_row[0] or '').upper():
                    raise HTTPException(status_code=403, detail="El admin no tiene el cargo de FACILITADOR")
                nombre_admin_db = au_row[1]

                # Obtener usuario_id del técnico del reporte
                cursor.execute("SELECT usuario_id FROM reportes_generados WHERE id = %s", (reporte_id,))
                rep = cursor.fetchone()
                if not rep:
                    raise HTTPException(status_code=404, detail="Reporte no encontrado")
                tecnico_uid = rep[0]

                # Verificar asignación activa (por admin_id O usuario_id)
                cursor.execute("""
                    SELECT 1 FROM facilitador_tecnico_asignaciones
                    WHERE tecnico_usuario_id = %s
                      AND activo = TRUE
                      AND (facilitador_admin_id = %s
                           OR (%s IS NOT NULL AND facilitador_usuario_id = %s))
                """, (tecnico_uid, admin_db_id, usuario_id, usuario_id))
                if not cursor.fetchone():
                    raise HTTPException(
                        status_code=403,
                        detail="No tienes asignado a este técnico para firmar sus reportes"
                    )

                # Usar nombre del admin (o del usuario vinculado si existe)
                if usuario_id:
                    cursor.execute("SELECT nombre_completo FROM usuarios WHERE id = %s", (usuario_id,))
                    u = cursor.fetchone()
                    nombre_firmante = u[0] if u else (nombre_admin_db or nombre_admin)
                else:
                    nombre_firmante = nombre_admin_db or nombre_admin
                id_firmante = usuario_id or 0
            else:
                # Admin total: usa datos del payload legacy
                nombre_firmante = firma_data.nombre_supervisor or nombre_admin
                id_firmante = usuario_id or firma_data.supervisor_id
        else:
            # ─── Flujo Legacy (supervisor territorial) ──────────────
            nombre_firmante = firma_data.nombre_supervisor
            id_firmante = firma_data.supervisor_id

        # ─── Verificar y firmar reporte ──────────────────────────────
        cursor.execute("""
            SELECT id, nombre_reporte, pdf_base64,
                   COALESCE(firmado_supervisor, false), usuario_id
            FROM reportes_generados WHERE id = %s
        """, (reporte_id,))
        reporte = cursor.fetchone()

        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")
        if reporte[3]:
            raise HTTPException(status_code=400, detail="Este reporte ya ha sido firmado")

        from zoneinfo import ZoneInfo
        fecha_firma = datetime.now(ZoneInfo("America/Mexico_City"))

        cursor.execute("""
            UPDATE reportes_generados SET
                firmado_supervisor       = TRUE,
                fecha_firma_supervisor   = %s,
                firma_supervisor_base64  = %s,
                nombre_supervisor        = %s,
                supervisor_id            = %s
            WHERE id = %s
        """, (fecha_firma, firma_data.firma_base64, nombre_firmante, id_firmante, reporte_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el reporte")

        conn.commit()
        print(f"✅ Reporte {reporte_id} firmado por {nombre_firmante}")
        return {
            "success": True,
            "message": f"Reporte firmado exitosamente por {nombre_firmante}",
            "data": {
                "reporte_id": reporte_id,
                "firmado_supervisor": True,
                "fecha_firma": fecha_firma.isoformat(),
                "nombre_supervisor": nombre_firmante,
                "supervisor_id": id_firmante
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error firmando reporte: {e}")
        raise HTTPException(status_code=500, detail=f"Error al firmar el reporte: {str(e)}")

# ============================================================
# ENDPOINTS FACILITADORES
# ============================================================

@app.get("/reportes/facilitador/mis-reportes")
async def mis_reportes_facilitador(
    admin_id: int,
    estado: Optional[str] = None,
    limite: int = 50,
    offset: int = 0
):
    """
    Lista los reportes de los técnicos asignados al facilitador autenticado.
    estado: 'pendiente' | 'firmado' | None (todos)
    """
    try:
        verificar_conexion_db()
        # Obtener datos del admin facilitador
        cursor.execute(
            "SELECT id, usuario_id, nombre_completo FROM admin_users WHERE id = %s AND activo = TRUE",
            (admin_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Admin no encontrado")
        facilitador_uid = row[1]  # puede ser None
        facilitador_nombre = row[2]

        # Construir filtro de estado
        estado_filter = ""
        if estado == 'pendiente':
            estado_filter = "AND COALESCE(r.firmado_supervisor, FALSE) = FALSE"
        elif estado == 'firmado':
            estado_filter = "AND COALESCE(r.firmado_supervisor, FALSE) = TRUE"

        query = f"""
            SELECT
                r.id,
                r.nombre_reporte,
                r.fecha_generado,
                COALESCE(r.firmado_supervisor, FALSE) as firmado,
                r.fecha_firma_supervisor,
                r.nombre_supervisor,
                u.nombre_completo as tecnico_nombre,
                u.cargo as tecnico_cargo,
                u.territorio as tecnico_territorio
            FROM reportes_generados r
            JOIN facilitador_tecnico_asignaciones fta
                ON fta.tecnico_usuario_id = r.usuario_id
                AND fta.activo = TRUE
                AND (fta.facilitador_admin_id = %s
                     OR (%s IS NOT NULL AND fta.facilitador_usuario_id = %s))
            JOIN usuarios u ON u.id = r.usuario_id
            WHERE r.activo = TRUE
            {estado_filter}
            ORDER BY r.fecha_generado DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (admin_id, facilitador_uid, facilitador_uid, limite, offset))
        rows = cursor.fetchall()

        reportes = []
        for r in rows:
            reportes.append({
                "id": r[0],
                "nombre_reporte": r[1],
                "fecha_generado": r[2].isoformat() if r[2] else None,
                "firmado_supervisor": r[3],
                "fecha_firma_supervisor": r[4].isoformat() if r[4] else None,
                "nombre_supervisor": r[5],
                "tecnico_nombre": r[6],
                "tecnico_cargo": r[7],
                "tecnico_territorio": r[8]
            })

        # Contar totales para paginación
        count_query = f"""
            SELECT COUNT(*)
            FROM reportes_generados r
            JOIN facilitador_tecnico_asignaciones fta
                ON fta.tecnico_usuario_id = r.usuario_id
                AND fta.activo = TRUE
                AND (fta.facilitador_admin_id = %s
                     OR (%s IS NOT NULL AND fta.facilitador_usuario_id = %s))
            WHERE r.activo = TRUE {estado_filter}
        """
        cursor.execute(count_query, (admin_id, facilitador_uid, facilitador_uid))
        total = cursor.fetchone()[0]

        return {
            "success": True,
            "reportes": reportes,
            "total": total,
            "limite": limite,
            "offset": offset,
            "facilitador": facilitador_nombre
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en mis-reportes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/facilitadores/mis-tecnicos")
async def mis_tecnicos_facilitador(admin_id: int):
    """
    Lista los técnicos asignados al facilitador.
    Match por facilitador_admin_id O facilitador_usuario_id (si el admin tiene uno).
    """
    try:
        verificar_conexion_db()
        cursor.execute(
            "SELECT usuario_id FROM admin_users WHERE id = %s AND activo = TRUE",
            (admin_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Admin no encontrado")
        facilitador_uid = row[0]  # puede ser None

        cursor.execute("""
            SELECT
                u.id, u.nombre_completo, u.cargo, u.territorio, u.curp,
                fta.origen, fta.created_at
            FROM facilitador_tecnico_asignaciones fta
            JOIN usuarios u ON u.id = fta.tecnico_usuario_id
            WHERE fta.activo = TRUE
              AND (fta.facilitador_admin_id = %s
                   OR (%s IS NOT NULL AND fta.facilitador_usuario_id = %s))
            ORDER BY u.nombre_completo
        """, (admin_id, facilitador_uid, facilitador_uid))
        rows = cursor.fetchall()

        tecnicos = [{
            "id": r[0],
            "nombre_completo": r[1],
            "cargo": r[2],
            "territorio": r[3],
            "curp": r[4],
            "origen": r[5],
            "asignado_desde": r[6].isoformat() if r[6] else None
        } for r in rows]

        return {"success": True, "tecnicos": tecnicos, "total": len(tecnicos)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS: Asignación manual de técnicos a facilitadores
# (para que un facilitador pueda asociar nuevos técnicos desde ReportesView)
# ============================================================

class AsignarTecnicoRequest(BaseModel):
    admin_id: int            # id de admin_users (facilitador)
    tecnico_usuario_id: int  # id de usuarios (técnico en pwasuper)


def _validar_facilitador(admin_id: int):
    """
    Verifica que el admin_id corresponda a un FACILITADOR activo.
    Devuelve (usuario_id, admin_id). usuario_id puede ser None si no está vinculado.
    """
    cursor.execute(
        """
        SELECT usuario_id, cargo
        FROM admin_users
        WHERE id = %s AND activo = TRUE
        """,
        (admin_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin no encontrado o inactivo")
    cargo = (row[1] or "").upper()
    if "FACILITADOR" not in cargo:
        raise HTTPException(status_code=403, detail="Solo los facilitadores pueden asignar técnicos")
    return row[0], admin_id  # (usuario_id puede ser None, admin_id)


@app.get("/facilitadores/tecnicos-disponibles")
async def tecnicos_disponibles_facilitador(
    admin_id: int,
    q: Optional[str] = None,
    territorio: Optional[str] = None,
    limite: int = 50
):
    """
    Lista técnicos de pwasuper disponibles para que un facilitador los asocie.
    Reglas:
      - Solo usuarios con cargo que contenga 'TECNICO' (social o productivo).
      - Que NO tengan asignación activa a ningún facilitador.
      - Permite búsqueda por nombre/CURP y filtro por territorio.
    """
    try:
        verificar_conexion_db()
        _validar_facilitador(admin_id)

        limite = max(1, min(limite, 200))

        # Usamos un parámetro para el patrón de cargo (evita problemas con
        # los '%' literales al pasar parámetros a psycopg2).
        params = ['%TECNICO%']
        where_extra = ""
        if q:
            where_extra += " AND (UPPER(u.nombre_completo) LIKE %s OR UPPER(u.curp) LIKE %s)"
            like = f"%{q.strip().upper()}%"
            params.extend([like, like])
        if territorio:
            where_extra += " AND UPPER(u.territorio) = %s"
            params.append(territorio.strip().upper())

        sql = f"""
            SELECT u.id, u.nombre_completo, u.cargo, u.territorio, u.curp
            FROM usuarios u
            WHERE UPPER(COALESCE(u.cargo, '')) LIKE %s
              AND NOT EXISTS (
                  SELECT 1 FROM facilitador_tecnico_asignaciones fta
                  WHERE fta.tecnico_usuario_id = u.id AND fta.activo = TRUE
              )
              {where_extra}
            ORDER BY u.nombre_completo
            LIMIT %s
        """
        params.append(limite)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        tecnicos = [{
            "id": r[0],
            "nombre_completo": r[1],
            "cargo": r[2],
            "territorio": r[3],
            "curp": r[4],
        } for r in rows]

        return {"success": True, "tecnicos": tecnicos, "total": len(tecnicos)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en tecnicos-disponibles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/facilitadores/asignar-tecnico")
async def asignar_tecnico_facilitador(payload: AsignarTecnicoRequest):
    """
    Asocia manualmente un técnico de pwasuper a un facilitador.
    Reglas:
      - Solo facilitadores activos con usuario_id vinculado.
      - El técnico no debe tener otro facilitador activo asignado.
      - Se registra con origen='manual'.
    """
    try:
        verificar_conexion_db()
        facilitador_uid, facilitador_admin_id = _validar_facilitador(payload.admin_id)

        # Validar que el técnico exista y sea TECNICO
        cursor.execute(
            "SELECT id, nombre_completo, cargo, territorio, curp FROM usuarios WHERE id = %s",
            (payload.tecnico_usuario_id,)
        )
        tec = cursor.fetchone()
        if not tec:
            raise HTTPException(status_code=404, detail="Técnico no encontrado en pwasuper")
        cargo_tec = (tec[2] or "").upper()
        if "TECNICO" not in cargo_tec:
            raise HTTPException(status_code=400, detail="El usuario seleccionado no es técnico")

        # Verificar que no tenga otro facilitador activo (cualquier asignación)
        cursor.execute(
            """
            SELECT fta.facilitador_admin_id, fta.facilitador_usuario_id,
                   COALESCE(au.nombre_completo, uf.nombre_completo) AS fac_nombre
            FROM facilitador_tecnico_asignaciones fta
            LEFT JOIN admin_users au ON au.id = fta.facilitador_admin_id
            LEFT JOIN usuarios uf ON uf.id = fta.facilitador_usuario_id
            WHERE fta.tecnico_usuario_id = %s AND fta.activo = TRUE
            LIMIT 1
            """,
            (payload.tecnico_usuario_id,)
        )
        existente = cursor.fetchone()
        if existente:
            ex_admin_id, ex_usuario_id, ex_nombre = existente
            ya_es_mio = (ex_admin_id == facilitador_admin_id) or \
                        (facilitador_uid is not None and ex_usuario_id == facilitador_uid)
            if ya_es_mio:
                raise HTTPException(status_code=409, detail="El técnico ya está asignado a ti")
            raise HTTPException(
                status_code=409,
                detail=f"El técnico ya está asignado al facilitador: {ex_nombre}"
            )

        # Insertar/reactivar con origen manual (siempre usamos admin_id)
        cursor.execute(
            """
            INSERT INTO facilitador_tecnico_asignaciones
                (facilitador_admin_id, facilitador_usuario_id, tecnico_usuario_id, origen, activo,
                 created_by_admin_user_id)
            VALUES (%s, %s, %s, 'manual', TRUE, %s)
            ON CONFLICT (facilitador_admin_id, tecnico_usuario_id)
            WHERE facilitador_admin_id IS NOT NULL
            DO UPDATE SET
                activo = TRUE,
                origen = 'manual',
                updated_at = NOW(),
                created_by_admin_user_id = EXCLUDED.created_by_admin_user_id,
                facilitador_usuario_id = EXCLUDED.facilitador_usuario_id
            RETURNING id
            """,
            (facilitador_admin_id, facilitador_uid, payload.tecnico_usuario_id, payload.admin_id)
        )
        asign_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "success": True,
            "asignacion_id": asign_id,
            "tecnico": {
                "id": tec[0],
                "nombre_completo": tec[1],
                "cargo": tec[2],
                "territorio": tec[3],
                "curp": tec[4],
            },
            "mensaje": "Técnico asociado correctamente"
        }
    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ Error en asignar-tecnico: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/facilitadores/asignar-tecnico")
async def desasignar_tecnico_facilitador(admin_id: int, tecnico_usuario_id: int):
    """
    Desasocia (soft delete) un técnico de un facilitador.
    Permite quitar cualquier asignación activa (manual o CSV).
    """
    try:
        verificar_conexion_db()
        facilitador_uid, facilitador_admin_id = _validar_facilitador(admin_id)

        cursor.execute(
            """
            SELECT id, origen, activo
            FROM facilitador_tecnico_asignaciones
            WHERE tecnico_usuario_id = %s
              AND (facilitador_admin_id = %s
                   OR (%s IS NOT NULL AND facilitador_usuario_id = %s))
            ORDER BY activo DESC, updated_at DESC
            LIMIT 1
            """,
            (tecnico_usuario_id, facilitador_admin_id, facilitador_uid, facilitador_uid)
        )
        row = cursor.fetchone()
        if not row or not row[2]:
            raise HTTPException(status_code=404, detail="Asignación no encontrada o ya inactiva")
        cursor.execute(
            """
            UPDATE facilitador_tecnico_asignaciones
            SET activo = FALSE, updated_at = NOW()
            WHERE id = %s
            """,
            (row[0],)
        )
        conn.commit()
        return {"success": True, "mensaje": "Técnico desasociado correctamente"}
    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ Error en desasignar-tecnico: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS PÚBLICOS: Búsqueda de facilitadores (para registro y perfil)
# ============================================================

@app.get("/facilitadores/buscar-publico")
async def buscar_facilitadores_publico(q: str = "", limite: int = 20):
    """
    Endpoint PÚBLICO (sin auth) para buscar facilitadores.
    Devuelve admin_users cuyo cargo contenga 'FACILITADOR', activos.
    Búsqueda por nombre_completo o curp. Mínimo 2 caracteres para buscar.
    Devuelve admin_id (siempre) y usuario_id (si está vinculado).
    """
    try:
        verificar_conexion_db()
        limite = max(1, min(limite, 50))
        q = (q or "").strip()
        if len(q) < 2:
            return {"success": True, "facilitadores": [], "total": 0}

        like = f"%{q.upper()}%"
        cursor.execute("""
            SELECT au.id, au.usuario_id, au.nombre_completo, au.curp, au.territorio
            FROM admin_users au
            WHERE UPPER(COALESCE(au.cargo, '')) LIKE '%%FACILITADOR%%'
              AND au.activo = TRUE
              AND (
                  UPPER(COALESCE(au.nombre_completo, '')) LIKE %s
                  OR UPPER(COALESCE(au.curp, '')) LIKE %s
              )
            ORDER BY au.nombre_completo
            LIMIT %s
        """, (like, like, limite))
        rows = cursor.fetchall()

        facilitadores = [{
            "admin_id": r[0],
            "usuario_id": r[1],
            "nombre_completo": r[2],
            "curp": r[3],
            "territorio": r[4]
        } for r in rows]

        return {"success": True, "facilitadores": facilitadores, "total": len(facilitadores)}
    except Exception as e:
        print(f"❌ Error en buscar-facilitadores-publico: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CambiarFacilitadorRequest(BaseModel):
    facilitador_admin_id: int  # ID en tabla admin_users del facilitador


@app.post("/usuarios/{user_id}/cambiar-facilitador")
async def cambiar_facilitador(user_id: int, payload: CambiarFacilitadorRequest):
    """
    Permite a un técnico cambiar su facilitador asignado.
    Recibe facilitador_admin_id (admin_users.id).
    Si el facilitador tiene usuario_id vinculado, crea asignación en la tabla.
    Siempre actualiza el campo supervisor con el nombre del facilitador.
    """
    try:
        verificar_conexion_db()

        # Verificar que el usuario exista y sea técnico
        cursor.execute(
            "SELECT id, nombre_completo, cargo FROM usuarios WHERE id = %s",
            (user_id,)
        )
        tec = cursor.fetchone()
        if not tec:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        cargo_upper = (tec[2] or "").upper()
        if "TECNICO" not in cargo_upper:
            raise HTTPException(status_code=400, detail="Solo los técnicos pueden elegir facilitador")

        # Verificar que el facilitador exista en admin_users
        cursor.execute("""
            SELECT au.id, au.usuario_id, au.nombre_completo
            FROM admin_users au
            WHERE au.id = %s AND au.activo = TRUE
              AND UPPER(COALESCE(au.cargo, '')) LIKE '%%FACILITADOR%%'
        """, (payload.facilitador_admin_id,))
        fac = cursor.fetchone()
        if not fac:
            raise HTTPException(status_code=404, detail="Facilitador no encontrado o inactivo")

        fac_usuario_id = fac[1]  # puede ser None
        fac_nombre = fac[2]

        # Desactivar asignaciones manuales anteriores de este técnico
        cursor.execute("""
            UPDATE facilitador_tecnico_asignaciones
            SET activo = FALSE, updated_at = NOW()
            WHERE tecnico_usuario_id = %s AND activo = TRUE
        """, (user_id,))

        # Crear/reactivar nueva asignación usando admin_id (y usuario_id si existe)
        cursor.execute("""
            INSERT INTO facilitador_tecnico_asignaciones
                (facilitador_admin_id, facilitador_usuario_id, tecnico_usuario_id, origen, activo)
            VALUES (%s, %s, %s, 'manual', TRUE)
            ON CONFLICT (facilitador_admin_id, tecnico_usuario_id)
            WHERE facilitador_admin_id IS NOT NULL
            DO UPDATE SET activo = TRUE, origen = 'manual', updated_at = NOW(),
                          facilitador_usuario_id = EXCLUDED.facilitador_usuario_id
        """, (payload.facilitador_admin_id, fac_usuario_id, user_id))
        print(f"✅ Asignación creada: admin_id={payload.facilitador_admin_id} usuario_id={fac_usuario_id} → técnico {user_id}")

        # Siempre actualizar campo supervisor en tabla usuarios
        cursor.execute(
            "UPDATE usuarios SET supervisor = %s WHERE id = %s",
            (fac_nombre, user_id)
        )
        conn.commit()

        return {
            "success": True,
            "mensaje": f"Facilitador cambiado a {fac_nombre}",
            "facilitador_nombre": fac_nombre
        }
    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ Error en cambiar-facilitador: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/reportes/quitar-firma/{reporte_id}")
async def quitar_firma_reporte(reporte_id: int, supervisor_id: int):
    """
    Permite quitar la firma de un reporte (solo el mismo supervisor que firmó o un admin).
    """
    try:
        print(f"🔓 [FIRMA] Quitando firma del reporte ID: {reporte_id}")
        
        # Verificar que el reporte existe y está firmado
        cursor.execute("""
            SELECT 
                id,
                nombre_reporte,
                firmado_supervisor,
                supervisor_id
            FROM reportes_generados
            WHERE id = %s
        """, (reporte_id,))
        
        reporte = cursor.fetchone()
        
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
        if not reporte[2]:
            raise HTTPException(status_code=400, detail="Este reporte no tiene firma de supervisor")
        
        # Quitar la firma
        cursor.execute("""
            UPDATE reportes_generados
            SET 
                firmado_supervisor = FALSE,
                fecha_firma_supervisor = NULL,
                firma_supervisor_base64 = NULL,
                nombre_supervisor = NULL,
                supervisor_id = NULL
            WHERE id = %s
        """, (reporte_id,))
        
        conn.commit()
        
        print(f"✅ Firma del reporte removida exitosamente")
        
        return {
            "success": True,
            "message": "Firma del reporte removida exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error quitando firma: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/reportes/admin/todos")
async def obtener_todos_reportes_admin(
    limite: int = 100,
    offset: int = 0,
    mes: str = None,
    anio: int = None,
    territorio: str = None,
    tipo: str = None,
    usuario_id: int = None,
    facilitador_admin_id: int = None
):
    """
    Obtener todos los reportes de todos los usuarios (para admin-pwa)
    Incluye información del usuario que generó cada reporte
    """
    try:
        print(f"📋 [ADMIN] Obteniendo todos los reportes...")
        print(f"   Filtros: mes={mes}, anio={anio}, territorio={territorio}, usuario_id={usuario_id}")
        
        # Construir query con JOINs para obtener info del usuario
        query = """
            SELECT 
                r.id,
                r.usuario_id,
                r.nombre_reporte,
                r.mes,
                r.anio,
                r.tipo,
                r.fecha_generacion,
                CASE WHEN r.pdf_base64 IS NOT NULL AND r.pdf_base64 != '' THEN true ELSE false END as tiene_pdf,
                u.nombre_completo,
                u.correo,
                u.territorio,
                u.cargo,
                COALESCE(r.firmado_supervisor, false) as firmado_supervisor,
                r.fecha_firma_supervisor,
                r.nombre_supervisor,
                r.supervisor_id,
                CASE WHEN r.datos_reporte IS NOT NULL THEN true ELSE false END as tiene_datos_reporte,
                COALESCE(au.nombre_completo, uf.nombre_completo) as facilitador_nombre
            FROM reportes_generados r
            LEFT JOIN usuarios u ON r.usuario_id = u.id
            LEFT JOIN facilitador_tecnico_asignaciones fta ON fta.tecnico_usuario_id = u.id AND fta.activo = TRUE
            LEFT JOIN admin_users au ON au.id = fta.facilitador_admin_id
            LEFT JOIN usuarios uf ON uf.id = fta.facilitador_usuario_id
            WHERE 1=1
        """
        params = []
        
        # Filtros opcionales
        if mes:
            query += " AND r.mes = %s"
            params.append(mes)
        
        if anio:
            query += " AND r.anio = %s"
            params.append(anio)
            
        if territorio:
            query += " AND u.territorio = %s"
            params.append(territorio)

        if tipo:
            query += " AND r.tipo = %s"
            params.append(tipo)

        if usuario_id:
            query += " AND r.usuario_id = %s"
            params.append(usuario_id)

        if facilitador_admin_id:
            # Obtener usuario_id del facilitador en admin_users (puede ser None)
            cursor.execute(
                "SELECT usuario_id FROM admin_users WHERE id = %s AND activo = TRUE",
                (facilitador_admin_id,)
            )
            fac_row = cursor.fetchone()
            if fac_row:
                fac_uid = fac_row[0]  # puede ser None
                cursor.execute("""
                    SELECT tecnico_usuario_id FROM facilitador_tecnico_asignaciones
                    WHERE activo = TRUE
                      AND (facilitador_admin_id = %s
                           OR (%s IS NOT NULL AND facilitador_usuario_id = %s))
                """, (facilitador_admin_id, fac_uid, fac_uid))
                tecnicos = [r[0] for r in cursor.fetchall()]
                if tecnicos:
                    placeholders = ','.join(['%s'] * len(tecnicos))
                    query += f" AND r.usuario_id IN ({placeholders})"
                    params.extend(tecnicos)
                else:
                    # Facilitador sin técnicos asignados → ningún reporte
                    query += " AND 1=0"
            else:
                query += " AND 1=0"
        
        # Ordenar por fecha más reciente
        query += " ORDER BY r.fecha_generacion DESC"
        
        # Primero obtener el total
        count_query = query.replace(
            """SELECT 
                r.id,
                r.usuario_id,
                r.nombre_reporte,
                r.mes,
                r.anio,
                r.tipo,
                r.fecha_generacion,
                CASE WHEN r.pdf_base64 IS NOT NULL AND r.pdf_base64 != '' THEN true ELSE false END as tiene_pdf,
                u.nombre_completo,
                u.correo,
                u.territorio,
                u.cargo,
                COALESCE(r.firmado_supervisor, false) as firmado_supervisor,
                r.fecha_firma_supervisor,
                r.nombre_supervisor,
                r.supervisor_id,
                CASE WHEN r.datos_reporte IS NOT NULL THEN true ELSE false END as tiene_datos_reporte,
                uf.nombre_completo as facilitador_nombre""",
            "SELECT COUNT(*)"
        ).replace(" ORDER BY r.fecha_generacion DESC", "")
        
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Ahora con paginación
        query += " LIMIT %s OFFSET %s"
        params.extend([limite, offset])
        
        cursor.execute(query, params)
        reportes = cursor.fetchall()
        
        resultado = []
        for r in reportes:
            resultado.append({
                "id": r[0],
                "usuario_id": r[1],
                "nombre_reporte": r[2],
                "mes": r[3],
                "anio": r[4],
                "tipo": r[5],
                "fecha_generacion": r[6].isoformat() if r[6] else None,
                "tiene_pdf": r[7],
                "usuario": {
                    "nombre_completo": r[8],
                    "correo": r[9],
                    "territorio": r[10],
                    "cargo": r[11]
                },
                "firmado_supervisor": r[12],
                "fecha_firma_supervisor": r[13].isoformat() if r[13] else None,
                "nombre_supervisor": r[14],
                "supervisor_id": r[15],
                "datos_reporte": r[16],  # true/false si tiene datos_reporte
                "facilitador_nombre": r[17] if len(r) > 17 else None
            })
        
        print(f"✅ [ADMIN] {len(resultado)} reportes encontrados de {total} totales")
        
        return {
            "success": True,
            "reportes": resultado,
            "total": total,
            "pagina_actual": offset // limite + 1 if limite > 0 else 1,
            "total_paginas": (total + limite - 1) // limite if limite > 0 else 1
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo reportes admin: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


def generar_pdf_desde_datos(datos_reporte, firma_usuario_base64=None, firma_supervisor_base64=None, nombre_supervisor=None):
    """
    Genera un PDF desde los datos estructurados del reporte usando ReportLab
    """
    try:
        # Parsear datos si es string
        if isinstance(datos_reporte, str):
            datos = json.loads(datos_reporte)
        else:
            datos = datos_reporte
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        margin = 15 * mm
        current_y = height - 20 * mm
        
        # ========== ENCABEZADO ==========
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, current_y, "SECRETARÍA DE BIENESTAR")
        current_y -= 5 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(width / 2, current_y, "SUBSECRETARÍA DE INCLUSIÓN PRODUCTIVA Y DESARROLLO RURAL")
        current_y -= 5 * mm
        c.drawCentredString(width / 2, current_y, "FORMATO DE SEGUIMIENTO A ACTIVIDADES PROGRAMADAS")
        current_y -= 10 * mm
        
        # Fecha
        fecha_gen = datos.get('fechaGeneracion', datetime.now().strftime('%Y-%m-%d'))
        if isinstance(fecha_gen, str) and 'T' in fecha_gen:
            fecha_gen = fecha_gen.split('T')[0]
        c.setFont("Helvetica", 8)
        c.drawRightString(width - margin, current_y, f"Fecha: {fecha_gen}")
        current_y -= 8 * mm
        
        # ========== INFORMACIÓN DEL USUARIO ==========
        usuario = datos.get('usuario', {})
        periodo = datos.get('periodo', {})
        
        # Recuadro de información
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, current_y, "Nombre del prestador de Servicios:")
        c.setFont("Helvetica", 8)
        c.drawString(margin + 55 * mm, current_y, usuario.get('nombre', 'N/A'))
        current_y -= 5 * mm
        
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, current_y, "CURP:")
        c.setFont("Helvetica", 8)
        c.drawString(margin + 15 * mm, current_y, usuario.get('curp', 'N/A'))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(width / 2, current_y, "Cargo:")
        c.setFont("Helvetica", 8)
        c.drawString(width / 2 + 15 * mm, current_y, usuario.get('cargo', 'N/A'))
        current_y -= 5 * mm
        
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, current_y, "Territorio:")
        c.setFont("Helvetica", 8)
        c.drawString(margin + 20 * mm, current_y, usuario.get('territorio', 'N/A'))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(width / 2, current_y, "Período:")
        c.setFont("Helvetica", 8)
        c.drawString(width / 2 + 18 * mm, current_y, f"{periodo.get('mes', 'N/A')} {periodo.get('anio', 'N/A')}")
        current_y -= 10 * mm
        
        # ========== TABLA DE ACTIVIDADES ==========
        actividades = datos.get('actividades', [])
        
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, current_y, "ACTIVIDADES REALIZADAS:")
        current_y -= 6 * mm
        
        # Encabezados de tabla
        headers = ["No.", "Fecha", "Tipo", "Descripción", "Evidencia"]
        col_widths = [8 * mm, 22 * mm, 30 * mm, 85 * mm, 20 * mm]
        
        # Dibujar encabezados
        c.setFont("Helvetica-Bold", 7)
        x_pos = margin
        for i, header in enumerate(headers):
            c.drawString(x_pos + 1 * mm, current_y, header)
            x_pos += col_widths[i]
        current_y -= 5 * mm
        
        # Línea separadora
        c.line(margin, current_y + 3 * mm, width - margin, current_y + 3 * mm)
        
        # Dibujar actividades
        c.setFont("Helvetica", 6)
        for idx, act in enumerate(actividades, 1):
            if current_y < 40 * mm:
                c.showPage()
                current_y = height - 20 * mm
                c.setFont("Helvetica", 6)
            
            x_pos = margin
            
            # Número
            c.drawString(x_pos + 1 * mm, current_y, str(idx))
            x_pos += col_widths[0]
            
            # Fecha
            fecha = act.get('fecha', 'N/A')
            if isinstance(fecha, str) and 'T' in fecha:
                fecha = fecha.split('T')[0]
            c.drawString(x_pos + 1 * mm, current_y, str(fecha)[:10])
            x_pos += col_widths[1]
            
            # Tipo
            tipo = act.get('tipo', act.get('tipo_actividad', 'N/A'))
            c.drawString(x_pos + 1 * mm, current_y, str(tipo)[:20])
            x_pos += col_widths[2]
            
            # Descripción (truncada)
            descripcion = act.get('descripcion', 'N/A')
            desc_truncada = str(descripcion)[:80] + ('...' if len(str(descripcion)) > 80 else '')
            c.drawString(x_pos + 1 * mm, current_y, desc_truncada)
            x_pos += col_widths[3]
            
            # Evidencia
            tiene_foto = 'Sí' if act.get('foto') or act.get('tiene_foto') else 'No'
            c.drawString(x_pos + 1 * mm, current_y, tiene_foto)
            
            current_y -= 4 * mm
        
        current_y -= 5 * mm
        
        # ========== FIRMAS ==========
        if current_y < 50 * mm:
            c.showPage()
            current_y = height - 30 * mm
        
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, current_y, "FIRMAS:")
        current_y -= 15 * mm
        
        # Firma del usuario
        firma_x = margin + 20 * mm
        c.line(firma_x, current_y, firma_x + 50 * mm, current_y)
        c.setFont("Helvetica", 7)
        c.drawCentredString(firma_x + 25 * mm, current_y - 4 * mm, "Firma del Prestador de Servicios")
        c.drawCentredString(firma_x + 25 * mm, current_y - 8 * mm, usuario.get('nombre', ''))
        
        # Si hay imagen de firma del usuario, agregarla
        if firma_usuario_base64:
            try:
                firma_data = base64.b64decode(firma_usuario_base64)
                from PIL import Image
                firma_img = Image.open(BytesIO(firma_data))
                firma_path = BytesIO()
                firma_img.save(firma_path, format='PNG')
                firma_path.seek(0)
                c.drawImage(firma_path, firma_x + 5 * mm, current_y + 2 * mm, width=40 * mm, height=15 * mm, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"⚠️ Error agregando firma usuario: {e}")
        
        # Firma del supervisor
        firma_sup_x = width / 2 + 10 * mm
        c.line(firma_sup_x, current_y, firma_sup_x + 50 * mm, current_y)
        c.setFont("Helvetica", 7)
        c.drawCentredString(firma_sup_x + 25 * mm, current_y - 4 * mm, "Firma del Supervisor")
        if nombre_supervisor:
            c.drawCentredString(firma_sup_x + 25 * mm, current_y - 8 * mm, nombre_supervisor)
        
        # Si hay imagen de firma del supervisor, agregarla
        if firma_supervisor_base64:
            try:
                firma_sup_data = base64.b64decode(firma_supervisor_base64)
                from PIL import Image
                firma_sup_img = Image.open(BytesIO(firma_sup_data))
                firma_sup_path = BytesIO()
                firma_sup_img.save(firma_sup_path, format='PNG')
                firma_sup_path.seek(0)
                c.drawImage(firma_sup_path, firma_sup_x + 5 * mm, current_y + 2 * mm, width=40 * mm, height=15 * mm, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"⚠️ Error agregando firma supervisor: {e}")
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        print(f"❌ Error generando PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.get("/reportes/admin/descargar-zip")
async def descargar_reportes_zip(
    mes: str = None,
    anio: int = None,
    tipo_descarga: str = "todos"  # "todos", "firmados", "pendientes"
):
    """
    Descargar múltiples reportes en formato ZIP
    Tipos de descarga: todos, firmados, pendientes
    Genera PDFs desde datos_reporte si no hay pdf_base64
    """
    try:
        print(f"📦 Generando ZIP de reportes...")
        print(f"   Mes: {mes}, Año: {anio}, Tipo: {tipo_descarga}")
        
        # Construir query según filtros - incluir datos_reporte y firmas
        query = """
            SELECT 
                r.id,
                r.nombre_reporte,
                r.pdf_base64,
                r.firmado_supervisor,
                r.mes,
                r.anio,
                u.nombre_completo,
                u.territorio,
                r.datos_reporte,
                r.firma_usuario_base64,
                r.firma_supervisor_base64,
                r.nombre_supervisor
            FROM reportes_generados r
            LEFT JOIN usuarios u ON r.usuario_id = u.id
            WHERE 1=1
        """
        params = []
        
        # Filtros
        if mes:
            query += " AND r.mes = %s"
            params.append(mes)
        
        if anio:
            query += " AND r.anio = %s"
            params.append(anio)
        
        # Filtro por tipo de descarga
        if tipo_descarga == "firmados":
            query += " AND r.firmado_supervisor = true"
        elif tipo_descarga == "pendientes":
            query += " AND (r.firmado_supervisor = false OR r.firmado_supervisor IS NULL)"
        
        query += " ORDER BY r.fecha_generacion DESC"
        
        cursor.execute(query, params)
        reportes = cursor.fetchall()
        
        if not reportes:
            raise HTTPException(status_code=404, detail="No se encontraron reportes con los filtros seleccionados")
        
        print(f"   📄 Encontrados {len(reportes)} reportes")
        
        # Crear ZIP en memoria
        zip_buffer = BytesIO()
        pdfs_agregados = 0
        pdfs_omitidos = 0
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for reporte in reportes:
                reporte_id = reporte[0]
                nombre_reporte = reporte[1]
                pdf_base64 = reporte[2]
                mes_rep = reporte[4]
                anio_rep = reporte[5]
                usuario = reporte[6] or "Usuario"
                territorio = reporte[7] or "Sin_Territorio"
                datos_reporte = reporte[8]
                firma_usuario = reporte[9]
                firma_supervisor = reporte[10]
                nombre_supervisor = reporte[11]
                
                pdf_bytes = None
                
                # Intentar obtener PDF de diferentes fuentes
                if pdf_base64:
                    # Si hay PDF guardado, usarlo directamente
                    try:
                        pdf_bytes = base64.b64decode(pdf_base64)
                        print(f"   ✅ PDF de BD para reporte {reporte_id}")
                    except Exception as e:
                        print(f"   ⚠️ Error decodificando PDF base64 del reporte {reporte_id}: {e}")
                
                # Si no hay PDF pero hay datos_reporte, generar PDF
                if not pdf_bytes and datos_reporte:
                    try:
                        print(f"   🔄 Generando PDF desde datos_reporte para reporte {reporte_id}...")
                        pdf_bytes = generar_pdf_desde_datos(
                            datos_reporte, 
                            firma_usuario, 
                            firma_supervisor, 
                            nombre_supervisor
                        )
                        if pdf_bytes:
                            print(f"   ✅ PDF generado para reporte {reporte_id}")
                        else:
                            print(f"   ❌ No se pudo generar PDF para reporte {reporte_id}")
                    except Exception as e:
                        print(f"   ❌ Error generando PDF para reporte {reporte_id}: {e}")
                
                if not pdf_bytes:
                    print(f"   ⚠️ Reporte {reporte_id} sin PDF ni datos, omitiendo...")
                    pdfs_omitidos += 1
                    continue
                
                try:
                    # Sanitizar nombre de archivo
                    usuario_safe = re.sub(r'[<>:"/\\|?*]', '_', usuario)
                    territorio_safe = re.sub(r'[<>:"/\\|?*]', '_', territorio)
                    nombre_safe = re.sub(r'[<>:"/\\|?*]', '_', nombre_reporte)
                    
                    # Nombre de archivo descriptivo
                    filename = f"{territorio_safe}/{mes_rep}_{anio_rep}/{nombre_safe}.pdf"
                    
                    # Agregar al ZIP
                    zip_file.writestr(filename, pdf_bytes)
                    pdfs_agregados += 1
                    print(f"   ✅ Agregado: {filename}")
                    
                except Exception as e:
                    print(f"   ❌ Error procesando reporte {reporte_id}: {e}")
                    pdfs_omitidos += 1
                    continue
        
        print(f"📊 Resumen: {pdfs_agregados} PDFs agregados, {pdfs_omitidos} omitidos")
        
        if pdfs_agregados == 0:
            raise HTTPException(status_code=404, detail="No se pudo generar ningún PDF para los reportes seleccionados")
        
        # Preparar respuesta
        zip_buffer.seek(0)
        
        # Nombre del archivo ZIP
        tipo_label = {
            "todos": "Todos",
            "firmados": "Firmados",
            "pendientes": "Pendientes"
        }.get(tipo_descarga, "Reportes")
        
        filename_zip = f"Reportes_{tipo_label}"
        if mes:
            filename_zip += f"_{mes}"
        if anio:
            filename_zip += f"_{anio}"
        filename_zip += ".zip"
        
        print(f"✅ ZIP generado: {filename_zip} ({pdfs_agregados} archivos)")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename_zip}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generando ZIP: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando ZIP: {str(e)}")

@app.get("/reportes/admin/estadisticas")
async def obtener_estadisticas_reportes_admin(
    territorio: str = None,
    facilitador_admin_id: int = None,
    mes: str = None,
    anio: int = None,
    tipo: str = None
):
    """
    Obtener estadísticas de reportes para el dashboard admin
    Opcionalmente filtrar por territorio, mes, año o tipo (mismos filtros que /reportes/admin/todos)
    """
    try:
        # Resolver filtro de IDs de técnicos si es facilitador
        tecnicos_ids = None
        if facilitador_admin_id:
            cursor.execute(
                "SELECT usuario_id FROM admin_users WHERE id = %s AND activo = TRUE",
                (facilitador_admin_id,)
            )
            fac_row = cursor.fetchone()
            if fac_row:
                fac_uid = fac_row[0]  # puede ser None
                cursor.execute("""
                    SELECT tecnico_usuario_id FROM facilitador_tecnico_asignaciones
                    WHERE activo = TRUE
                      AND (facilitador_admin_id = %s
                           OR (%s IS NOT NULL AND facilitador_usuario_id = %s))
                """, (facilitador_admin_id, fac_uid, fac_uid))
                tecnicos_ids = [r[0] for r in cursor.fetchall()] or [-1]
            else:
                tecnicos_ids = [-1]

        def build_filter(extra_where="", extra_params=None):
            """Construye WHERE + params para el filtro activo (territorio, facilitador, mes, año, tipo)"""
            wheres = []
            p = list(extra_params or [])
            if territorio:
                wheres.append("u.territorio = %s")
                p.append(territorio)
            if tecnicos_ids is not None:
                placeholders = ','.join(['%s'] * len(tecnicos_ids))
                wheres.append(f"r.usuario_id IN ({placeholders})")
                p.extend(tecnicos_ids)
            if mes:
                wheres.append("r.mes = %s")
                p.append(mes)
            if anio:
                wheres.append("r.anio = %s")
                p.append(anio)
            if tipo:
                wheres.append("r.tipo = %s")
                p.append(tipo)
            if extra_where:
                wheres.append(extra_where)
            clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
            return clause, p

        territorio_filter = ""
        territorio_param = None
        
        if territorio:
            print(f"🌎 [ADMIN] Filtrando estadísticas por territorio: {territorio}")
            territorio_filter = " AND u.territorio = %s"
            territorio_param = territorio
        
        print(f"📊 [ADMIN] Obteniendo estadísticas de reportes...")

        base_join = "FROM reportes_generados r LEFT JOIN usuarios u ON r.usuario_id = u.id"

        # Total de reportes
        clause, p = build_filter()
        cursor.execute(f"SELECT COUNT(*) {base_join} {clause}", p)
        total_reportes = cursor.fetchone()[0]
        
        # Reportes firmados
        clause, p = build_filter("COALESCE(r.firmado_supervisor, false) = true")
        cursor.execute(f"SELECT COUNT(*) {base_join} {clause}", p)
        reportes_firmados = cursor.fetchone()[0]
        
        # Reportes pendientes (sin firmar)
        clause, p = build_filter("COALESCE(r.firmado_supervisor, false) = false")
        cursor.execute(f"SELECT COUNT(*) {base_join} {clause}", p)
        reportes_pendientes = cursor.fetchone()[0]
        
        # Reportes este mes
        clause, p = build_filter(
            "EXTRACT(MONTH FROM r.fecha_generacion) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM r.fecha_generacion) = EXTRACT(YEAR FROM CURRENT_DATE)"
        )
        cursor.execute(f"SELECT COUNT(*) {base_join} {clause}", p)
        reportes_mes = cursor.fetchone()[0]
        
        # Reportes por tipo
        clause, p = build_filter()
        cursor.execute(f"SELECT r.tipo, COUNT(*) {base_join} {clause} GROUP BY r.tipo", p)
        por_tipo = {r[0]: r[1] for r in cursor.fetchall()}
        
        # Usuarios con reportes
        clause, p = build_filter()
        cursor.execute(f"SELECT COUNT(DISTINCT r.usuario_id) {base_join} {clause}", p)
        usuarios_con_reportes = cursor.fetchone()[0]
        
        # Reportes por territorio (solo si no hay filtro de territorio ni facilitador)
        if not territorio and tecnicos_ids is None:
            cursor.execute("""
                SELECT u.territorio, COUNT(r.id)
                FROM reportes_generados r
                LEFT JOIN usuarios u ON r.usuario_id = u.id
                WHERE u.territorio IS NOT NULL
                GROUP BY u.territorio
                ORDER BY COUNT(r.id) DESC
            """)
            por_territorio = {r[0]: r[1] for r in cursor.fetchall()}
        else:
            por_territorio = {territorio: total_reportes} if territorio else {}

        # Reportes por mes (últimos 6 meses)
        clause, p = build_filter("r.fecha_generacion >= CURRENT_DATE - INTERVAL '6 months'")
        cursor.execute(
            f"SELECT TO_CHAR(r.fecha_generacion, 'YYYY-MM') as mes, COUNT(*) {base_join} {clause} GROUP BY TO_CHAR(r.fecha_generacion, 'YYYY-MM') ORDER BY mes DESC",
            p
        )
        por_mes = {r[0]: r[1] for r in cursor.fetchall()}
        
        print(f"✅ [ADMIN] Estadísticas obtenidas - Total: {total_reportes}, Firmados: {reportes_firmados}, Pendientes: {reportes_pendientes}, Usuarios: {usuarios_con_reportes}" + (f" (Territorio: {territorio})" if territorio else ""))
        
        return {
            "success": True,
            "estadisticas": {
                "total_reportes": total_reportes,
                "reportes_firmados": reportes_firmados,
                "reportes_pendientes": reportes_pendientes,
                "reportes_mes_actual": reportes_mes,
                "por_tipo": por_tipo,
                "usuarios_con_reportes": usuarios_con_reportes,
                "por_territorio": por_territorio,
                "por_mes": por_mes
            }
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/reportes/admin/estadisticas-pdf")
async def obtener_estadisticas_reportes_pdf(
    mes: str = None,
    anio: int = None,
    territorio: str = None,
    agrupar_por: str = "territorio"  # "territorio" o "individual"
):
    """
    Obtener estadísticas detalladas de reportes para generar PDF.
    """
    try:
        # Usar año actual si no se proporciona
        if anio is None:
            from datetime import datetime
            anio = datetime.now().year
        
        print(f"📊 [ADMIN] Obteniendo estadísticas para PDF...")
        print(f"   Filtros: mes={mes}, anio={anio}, territorio={territorio}, agrupar_por={agrupar_por}")
        
        # Verificar conexión
        verificar_conexion_db()
        
        resultado = {
            "periodo": {
                "mes": mes,
                "anio": anio
            },
            "territorio_filtro": territorio,  # Territorio seleccionado para filtrar
            "territorios": [],
            "resumen_general": {
                "total_tecnicos_social": 0,
                "total_tecnicos_productivo": 0,
                "total_facilitadores": 0,
                "total_reportes": 0,
                "reportes_firmados": 0,
                "reportes_pendientes": 0
            }
        }
        
        # Query para obtener territorios con técnicos y facilitadores
        # IMPORTANTE: %% escapa el % para que psycopg2 no lo interprete como placeholder
        query_territorios = """
            SELECT 
                u.territorio,
                COUNT(DISTINCT CASE WHEN UPPER(COALESCE(u.cargo, '')) LIKE '%%SOCIAL%%' THEN u.id END) as tecnicos_social,
                COUNT(DISTINCT CASE WHEN UPPER(COALESCE(u.cargo, '')) LIKE '%%PRODUCTIVO%%' THEN u.id END) as tecnicos_productivo,
                COUNT(DISTINCT CASE WHEN UPPER(COALESCE(u.cargo, '')) LIKE '%%FACILITADOR%%' THEN u.id END) as facilitadores,
                COUNT(DISTINCT u.id) as total_personal
            FROM usuarios u
            WHERE u.territorio IS NOT NULL 
            AND u.territorio != ''
            AND COALESCE(u.activo, true) = TRUE
        """
        params_territorios = []
        
        if territorio:
            query_territorios += " AND u.territorio = %s"
            params_territorios.append(territorio)
        
        query_territorios += " GROUP BY u.territorio ORDER BY u.territorio"
        
        print(f"🔍 Query territorios: {query_territorios}")
        print(f"🔍 Params: {params_territorios}")
        
        params_to_use = tuple(params_territorios) if params_territorios else None
        territorios_data = ejecutar_consulta_segura(query_territorios, params_to_use, 'all')
        
        print(f"🔍 Territorios encontrados: {len(territorios_data) if territorios_data else 0}")
        
        if not territorios_data:
            print("⚠️ No se encontraron territorios")
            return {"success": True, "data": resultado}
        
        # Para cada territorio
        for t in territorios_data:
            if not t or len(t) < 5:
                continue
                
            territorio_nombre = t[0]
            tecnicos_social = t[1] or 0
            tecnicos_productivo = t[2] or 0
            facilitadores = t[3] or 0
            total_personal = t[4] or 0
            
            # Query para reportes del territorio
            reportes_query = """
                SELECT 
                    COUNT(r.id) as total_reportes,
                    COUNT(CASE WHEN COALESCE(r.firmado_supervisor, false) = true THEN 1 END) as firmados,
                    COUNT(CASE WHEN COALESCE(r.firmado_supervisor, false) = false THEN 1 END) as pendientes
                FROM reportes_generados r
                INNER JOIN usuarios u ON r.usuario_id = u.id
                WHERE u.territorio = %s
            """
            reportes_params = [territorio_nombre]
            
            if mes:
                reportes_query += " AND r.mes = %s"
                reportes_params.append(mes)
            if anio:
                reportes_query += " AND r.anio = %s"
                reportes_params.append(anio)
            
            print(f"🔍 Query reportes: params={reportes_params}")
            report_params_tuple = tuple(reportes_params) if reportes_params else None
            reportes_stats = ejecutar_consulta_segura(reportes_query, report_params_tuple, 'one')
            print(f"🔍 Reportes stats: {reportes_stats}")
            
            total_reportes = 0
            firmados = 0
            pendientes = 0
            if reportes_stats and len(reportes_stats) >= 3:
                total_reportes = reportes_stats[0] or 0
                firmados = reportes_stats[1] or 0
                pendientes = reportes_stats[2] or 0
            
            territorio_info = {
                "nombre": territorio_nombre,
                "tecnicos_social": tecnicos_social,
                "tecnicos_productivo": tecnicos_productivo,
                "facilitadores": facilitadores,
                "total_personal": total_personal,
                "reportes_total": total_reportes,
                "reportes_firmados": firmados,
                "reportes_pendientes": pendientes,
                "datos_por_mes": []
            }
            
            # Si no hay mes especificado, obtener datos por cada mes del año
            if not mes and anio:
                meses_orden = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                
                for mes_nombre in meses_orden:
                    query_mes = """
                        SELECT 
                            COUNT(r.id) as total_reportes,
                            COUNT(CASE WHEN COALESCE(r.firmado_supervisor, false) = true THEN 1 END) as firmados,
                            COUNT(CASE WHEN COALESCE(r.firmado_supervisor, false) = false THEN 1 END) as pendientes
                        FROM reportes_generados r
                        INNER JOIN usuarios u ON r.usuario_id = u.id
                        WHERE u.territorio = %s AND r.mes = %s AND r.anio = %s
                    """
                    stats_mes = ejecutar_consulta_segura(query_mes, (territorio_nombre, mes_nombre, anio), 'one')
                    
                    mes_total = 0
                    mes_firmados = 0
                    mes_pendientes = 0
                    if stats_mes and len(stats_mes) >= 3:
                        mes_total = stats_mes[0] or 0
                        mes_firmados = stats_mes[1] or 0
                        mes_pendientes = stats_mes[2] or 0
                    
                    # Solo agregar el mes si tiene reportes
                    if mes_total > 0:
                        territorio_info["datos_por_mes"].append({
                            "mes": mes_nombre,
                            "reportes_total": mes_total,
                            "reportes_firmados": mes_firmados,
                            "reportes_pendientes": mes_pendientes
                        })
            
            # Si se agrupa por individual, obtener lista de técnicos
            if agrupar_por == "individual":
                try:
                    # Query más simple para técnicos
                    query_tecnicos = """
                        SELECT 
                            u.id,
                            u.nombre_completo,
                            COALESCE(u.cargo, '-') as cargo,
                            COALESCE(u.correo, '-') as correo
                        FROM usuarios u
                        WHERE u.territorio = %s
                        AND COALESCE(u.activo, true) = TRUE
                        ORDER BY u.nombre_completo
                    """
                    
                    tecnicos_list = ejecutar_consulta_segura(query_tecnicos, (territorio_nombre,), 'all')
                    
                    territorio_info["tecnicos"] = []
                    if tecnicos_list:
                        for tec in tecnicos_list:
                            if not tec or len(tec) < 4:
                                continue
                                
                            usuario_id = tec[0]
                            
                            # Query separada para contar reportes de este técnico
                            query_reportes_tec = """
                                SELECT 
                                    COUNT(*) as total,
                                    COUNT(CASE WHEN COALESCE(firmado_supervisor, false) = true THEN 1 END) as firmados
                                FROM reportes_generados
                                WHERE usuario_id = %s
                            """
                            params_reportes = [usuario_id]
                            
                            # Añadir filtros de forma segura
                            filtros_extra = []
                            if mes:
                                filtros_extra.append("mes = %s")
                                params_reportes.append(mes)
                            if anio:
                                filtros_extra.append("anio = %s")
                                params_reportes.append(anio)
                            
                            if filtros_extra:
                                query_reportes_tec = query_reportes_tec.rstrip() + " AND " + " AND ".join(filtros_extra)
                            
                            rep_params_tuple = tuple(params_reportes) if params_reportes else None
                            rep_stats = ejecutar_consulta_segura(query_reportes_tec, rep_params_tuple, 'one')
                            
                            rep_total = 0
                            rep_firmados = 0
                            if rep_stats and len(rep_stats) >= 2:
                                rep_total = rep_stats[0] or 0
                                rep_firmados = rep_stats[1] or 0
                            
                            territorio_info["tecnicos"].append({
                                "id": usuario_id,
                                "nombre": tec[1] or "Sin nombre",
                                "cargo": tec[2] or "-",
                                "correo": tec[3] or "-",
                                "reportes_total": rep_total,
                                "reportes_firmados": rep_firmados,
                                "reportes_pendientes": rep_total - rep_firmados
                            })
                except Exception as e_tec:
                    import traceback
                    print(f"⚠️ Error obteniendo técnicos para {territorio_nombre}: {e_tec}")
                    print(traceback.format_exc())
                    territorio_info["tecnicos"] = []
            
            resultado["territorios"].append(territorio_info)
            
            # Acumular resumen general
            resultado["resumen_general"]["total_tecnicos_social"] += tecnicos_social
            resultado["resumen_general"]["total_tecnicos_productivo"] += tecnicos_productivo
            resultado["resumen_general"]["total_facilitadores"] += facilitadores
            resultado["resumen_general"]["total_reportes"] += total_reportes
            resultado["resumen_general"]["reportes_firmados"] += firmados
            resultado["resumen_general"]["reportes_pendientes"] += pendientes
        
        print(f"✅ [ADMIN] Estadísticas PDF generadas: {len(resultado['territorios'])} territorios")
        
        return {
            "success": True,
            "data": resultado
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error obteniendo estadísticas PDF: {e}")
        print(f"📋 Traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e) or type(e).__name__} - {error_trace[:200]}")


# Nuevo endpoint para obtener usuarios (para el panel de administración)
@app.get("/usuarios")
async def obtener_usuarios(request: Request, territorio: str = None):
    _pwd_ok = _admin_jwt_valido(request)
    try:
        print(f"🔍 Obteniendo usuarios... (filtro territorio: {territorio})")
        
        # Verificar si la columna 'rol' existe
        rol_check = ejecutar_consulta_segura("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """, fetch_type='one')
        
        tiene_columna_rol = bool(rol_check)
        
        # Construir query base con subquery que toma SOLO la asignación más reciente
        # por técnico (DISTINCT ON evita filas duplicadas por múltiples asignaciones activas)
        fta_subquery = """
            LEFT JOIN LATERAL (
                SELECT fta2.facilitador_admin_id, fta2.facilitador_usuario_id
                FROM facilitador_tecnico_asignaciones fta2
                WHERE fta2.tecnico_usuario_id = u.id AND fta2.activo = TRUE
                ORDER BY fta2.id DESC
                LIMIT 1
            ) fta ON UPPER(COALESCE(u.cargo,'')) IN ('TECNICO SOCIAL','TECNICO PRODUCTIVO')
            LEFT JOIN admin_users au ON au.id = fta.facilitador_admin_id
            LEFT JOIN usuarios uf ON uf.id = fta.facilitador_usuario_id
        """

        if tiene_columna_rol:
            base_query = f"""
                SELECT u.id, u.correo, u.nombre_completo, u.cargo, u.supervisor,
                       u.curp, u.contrasena, u.telefono, u.rol, u.territorio, u.activo,
                       COALESCE(au.nombre_completo, uf.nombre_completo) AS facilitador_nombre
                FROM usuarios u
                {fta_subquery}
            """
        else:
            base_query = f"""
                SELECT u.id, u.correo, u.nombre_completo, u.cargo, u.supervisor,
                       u.curp, u.contrasena, u.telefono, u.territorio, u.activo,
                       COALESCE(au.nombre_completo, uf.nombre_completo) AS facilitador_nombre
                FROM usuarios u
                {fta_subquery}
            """

        # Agregar filtro de territorio si se proporciona
        if territorio:
            query = f"{base_query} WHERE u.territorio = %s ORDER BY u.id DESC"
            resultados = ejecutar_consulta_segura(query, (territorio,), fetch_type='all')
        else:
            query = f"{base_query} ORDER BY u.id DESC"
            resultados = ejecutar_consulta_segura(query, fetch_type='all')

        if not resultados:
            resultados = []

        print(f"📊 Encontrados {len(resultados)} usuarios")

        # Convertir tuplas a diccionarios manualmente
        # facilitador_nombre es siempre el último campo (índice 11 con rol / 10 sin rol)
        usuarios = []
        for row in resultados:
            if tiene_columna_rol:
                facilitador_nombre = row[11] if len(row) > 11 else None
                cargo = row[3] or ''
                es_tecnico = cargo.upper() in ('TECNICO SOCIAL', 'TECNICO PRODUCTIVO')
                usuario = {
                    "id": row[0],
                    "correo": row[1],
                    "nombre_completo": row[2],
                    "cargo": row[3],
                    "supervisor": facilitador_nombre if (es_tecnico and facilitador_nombre) else row[4],
                    "supervisor_es_facilitador": bool(es_tecnico and facilitador_nombre),
                    "curp": row[5],
                    "contrasena": (row[6] if _pwd_ok else None),
                    "telefono": row[7] if len(row) > 7 else None,
                    "rol": row[8] if len(row) > 8 else 'user',
                    "territorio": row[9] if len(row) > 9 else None,
                    "activo": row[10] if len(row) > 10 else True
                }
            else:
                facilitador_nombre = row[10] if len(row) > 10 else None
                cargo = row[3] or ''
                es_tecnico = cargo.upper() in ('TECNICO SOCIAL', 'TECNICO PRODUCTIVO')
                usuario = {
                    "id": row[0],
                    "correo": row[1],
                    "nombre_completo": row[2],
                    "cargo": row[3],
                    "supervisor": facilitador_nombre if (es_tecnico and facilitador_nombre) else row[4],
                    "supervisor_es_facilitador": bool(es_tecnico and facilitador_nombre),
                    "curp": row[5],
                    "contrasena": (row[6] if _pwd_ok else None),
                    "telefono": row[7] if len(row) > 7 else None,
                    "rol": 'user',
                    "territorio": row[8] if len(row) > 8 else None,
                    "activo": row[9] if len(row) > 9 else True
                }
            usuarios.append(usuario)
        
        print(f"✅ Usuarios procesados correctamente con información de roles")
        return {"usuarios": usuarios}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios: {str(e)}")

# NUEVO ENDPOINT PARA EXPORTACIÓN COMPLETA CON CONTRASEÑAS
@app.get("/usuarios/exportacion-completa")
async def obtener_usuarios_exportacion_completa(request: Request):
    _pwd_ok = _admin_jwt_valido(request)
    """
    Endpoint especial para exportar usuarios con contraseñas incluidas.
    Solo para uso en exportación de base de datos completa.
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Obtener TODOS los campos de usuarios incluyendo contraseñas y teléfono
        cursor.execute(
            "SELECT id, correo, nombre_completo, cargo, supervisor, contrasena, curp, telefono FROM usuarios ORDER BY id DESC"
        )
        
        resultados = cursor.fetchall()
        print(f"📊 Exportación completa: {len(resultados)} usuarios con contraseñas")
        
        # Convertir tuplas a diccionarios manualmente
        usuarios = []
        for row in resultados:
            usuario = {
                "id": row[0],
                "correo": row[1],
                "nombre_completo": row[2],
                "cargo": row[3],
                "supervisor": row[4],
                "contrasena": (row[5] if _pwd_ok else None),  # INCLUIR LA CONTRASEÑA REAL
                "curp": row[6],
                "telefono": row[7] if len(row) > 7 else None  # Incluir teléfono si existe
            }
            usuarios.append(usuario)
        
        print(f"✅ Exportación completa procesada correctamente")
        return {"usuarios": usuarios}
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios para exportación: {str(e)}")

# Endpoint para obtener un usuario específico por ID
@app.get("/usuarios/{user_id}")
async def obtener_usuario(user_id: int, request: Request):
    _pwd_ok = _admin_jwt_valido(request)
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Buscar usuario por ID con CURP, teléfono, contraseña, territorio y activo
        cursor.execute(
            "SELECT id, correo, nombre_completo, cargo, supervisor, curp, contrasena, telefono, territorio, activo FROM usuarios WHERE id = %s",
            (user_id,)
        )
        
        resultado = cursor.fetchone()        
        if not resultado:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario = {
            "id": resultado[0],
            "correo": resultado[1],
            "nombre_completo": resultado[2],
            "cargo": resultado[3],
            "supervisor": resultado[4],
            "curp": resultado[5],
            "contrasena": (resultado[6] if _pwd_ok else None),  # Incluir contraseña
            "telefono": resultado[7] if len(resultado) > 7 else None,  # Incluir teléfono si existe
            "territorio": resultado[8] if len(resultado) > 8 else None,  # Incluir territorio si existe
            "activo": resultado[9] if len(resultado) > 9 else True  # Incluir estado activo
        }
        
        print(f"✅ Usuario {user_id} obtenido correctamente")
        return usuario
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuario: {str(e)}")

# Endpoint para actualizar un usuario específico
class UserUpdate(BaseModel):
    correo: str
    nombre_completo: str
    cargo: str
    supervisor: Optional[str] = None
    curp: Optional[str] = None
    telefono: Optional[str] = None
    rol: str = 'user'
    territorio: Optional[str] = None
    nueva_contrasena: Optional[str] = None  # Contraseña opcional para actualización

@app.put("/usuarios/{user_id}")
async def actualizar_usuario(user_id: int, usuario: UserUpdate, request: Request):
    _pwd_ok = _admin_jwt_valido(request)
    """Actualiza los datos de un usuario específico incluyendo rol y contraseña opcional"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"✏️ Actualizando usuario {user_id}...")
        
        # Validación de rol
        if usuario.rol not in ['admin', 'user']:
            raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'user'")
        
        # Validación de CURP si se proporciona
        if usuario.curp and usuario.curp.strip():
            curp_upper = usuario.curp.upper().strip()
            if len(curp_upper) != 18:
                raise HTTPException(status_code=400, detail="La CURP debe tener exactamente 18 caracteres")
            
            if not re.match(r'^[A-Z0-9]{18}$', curp_upper):
                raise HTTPException(status_code=400, detail="La CURP tiene un formato inválido")
            
            # Verificar que la CURP no esté en uso por otro usuario
            cursor.execute("SELECT id FROM usuarios WHERE curp = %s AND id != %s", (curp_upper, user_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Esta CURP ya está registrada por otro usuario")
        else:
            curp_upper = None
        
        # Verificar que el correo no esté en uso por otro usuario
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s AND id != %s", (usuario.correo, user_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Este correo ya está registrado por otro usuario")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, contrasena FROM usuarios WHERE id = %s", (user_id,))
        usuario_actual = cursor.fetchone()
        if not usuario_actual:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar si la columna 'rol' existe, si no, agregarla
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """)
        
        if not cursor.fetchone():
            print("📝 Agregando columna 'rol' a la tabla usuarios")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(10) DEFAULT 'user'")
            conn.commit()
        
        # Determinar la contraseña a usar
        contrasena_final = usuario_actual[1]  # Mantener la actual por defecto
        if usuario.nueva_contrasena and usuario.nueva_contrasena.strip():
            contrasena_final = usuario.nueva_contrasena.strip()
            print("🔑 Actualizando contraseña del usuario")
        
        # Actualizar usuario con rol y territorio
        cursor.execute(
            """UPDATE usuarios 
               SET correo = %s, nombre_completo = %s, cargo = %s, 
                   supervisor = %s, contrasena = %s, curp = %s, telefono = %s, rol = %s, territorio = %s 
               WHERE id = %s""",
            (usuario.correo, usuario.nombre_completo, usuario.cargo, 
             usuario.supervisor, contrasena_final, curp_upper, usuario.telefono, usuario.rol, usuario.territorio, user_id)
        )
        
        conn.commit()
        
        # Obtener usuario actualizado
        cursor.execute(
            "SELECT id, correo, nombre_completo, cargo, supervisor, contrasena, curp, telefono, rol, territorio FROM usuarios WHERE id = %s",
            (user_id,)
        )
        
        resultado = cursor.fetchone()
        usuario_actualizado = {
            "id": resultado[0],
            "correo": resultado[1],
            "nombre_completo": resultado[2],
            "cargo": resultado[3],
            "supervisor": resultado[4],
            "contrasena": (resultado[5] if _pwd_ok else None),
            "curp": resultado[6],
            "telefono": resultado[7],
            "rol": resultado[8] if len(resultado) > 8 else 'user',
            "territorio": resultado[9] if len(resultado) > 9 else None
        }
        
        print(f"✅ Usuario {user_id} actualizado exitosamente con rol {usuario.rol}")
        return {"mensaje": "Usuario actualizado exitosamente", "usuario": usuario_actualizado}
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")

# Endpoint para actualizar solo información personal de un usuario (sin contraseña)
@app.patch("/usuarios/{user_id}/info")
async def actualizar_info_usuario(user_id: int, info: UserInfoUpdate):
    """Actualiza solo la información personal de un usuario (sin modificar contraseña)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"✏️ Actualizando información personal del usuario {user_id}...")
        
        # Validación de CURP si se proporciona
        curp_upper = None
        if info.curp and info.curp.strip():
            curp_upper = info.curp.upper().strip()
            if len(curp_upper) != 18:
                raise HTTPException(status_code=400, detail="La CURP debe tener exactamente 18 caracteres")
            
            if not re.match(r'^[A-Z0-9]{18}$', curp_upper):
                raise HTTPException(status_code=400, detail="La CURP tiene un formato inválido")
            
            # Verificar que la CURP no esté en uso por otro usuario
            cursor.execute("SELECT id FROM usuarios WHERE curp = %s AND id != %s", (curp_upper, user_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Esta CURP ya está registrada por otro usuario")
        
        # Verificar que el correo no esté en uso por otro usuario
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s AND id != %s", (info.correo, user_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Este correo ya está registrado por otro usuario")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Actualizar solo información personal (sin modificar contraseña)
        cursor.execute(
            """UPDATE usuarios 
               SET correo = %s, nombre_completo = %s, cargo = %s, 
                   supervisor = %s, curp = %s, telefono = %s, territorio = %s 
               WHERE id = %s""",
            (info.correo, info.nombre_completo, info.cargo, 
             info.supervisor, curp_upper, info.telefono, info.territorio, user_id)
        )
        
        conn.commit()
        
        # Obtener usuario actualizado
        cursor.execute(
            "SELECT id, correo, nombre_completo, cargo, supervisor, curp, telefono, territorio FROM usuarios WHERE id = %s",
            (user_id,)
        )
        
        resultado = cursor.fetchone()
        usuario_actualizado = {
            "id": resultado[0],
            "correo": resultado[1],
            "nombre_completo": resultado[2],
            "cargo": resultado[3],
            "supervisor": resultado[4],
            "curp": resultado[5],
            "telefono": resultado[6],
            "territorio": resultado[7]
        }
        
        print(f"✅ Información personal del usuario {user_id} actualizada exitosamente")
        return {"success": True, "mensaje": "Información personal actualizada exitosamente", "usuario": usuario_actualizado}
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar información personal: {str(e)}")

# ==================== ENDPOINT PARA ACTUALIZAR TERRITORIO ====================

# Lista de territorios de Sembrando Vida
TERRITORIOS_SEMBRANDO_VIDA = [
    "Acapulco - Centro - Norte - Tierra Caliente",
    "Acayucan",
    "Balancán",
    "Chihuahua / Sonora",
    "Colima",
    "Comalcalco",
    "Córdoba",
    "Costa Chica - Montaña",
    "Costa Grande - Sierra",
    "Durango / Zacatecas",
    "Hidalgo",
    "Istmo",
    "Michoacán",
    "Mixteca",
    "Morelos",
    "Nayarit / Jalisco",
    "Ocosingo",
    "Palenque",
    "Papantla",
    "Pichucalco",
    "Puebla",
    "San Luis Potosí",
    "Sinaloa",
    "Tamaulipas",
    "Tantoyuca",
    "Tapachula",
    "Teapa",
    "Tlaxcala / Estado de México",
    "Tzucacab / Opb",
    "Xpujil",
    "Oficinas Centrales"
]

# ==================== NORMALIZACIÓN DE CARGOS ====================
# Catálogo oficial de cargos para admin_users (MAYÚSCULAS SIN TILDES)
CARGOS_ADMIN_CATALOGO = [
    "FACILITADOR",
    "COORDINACION TERRITORIAL",
    "COORDINACION TERRITORIAL A",
    "COORDINACION TERRITORIAL B",
    "COORDINACION TERRITORIAL C",
    "ESPECIALISTAS PRODUCTIVOS Y SOCIALES",
    "DIRECTOR GENERAL",
    "DIRECTORA DE AREA",
    "DIRECTOR",
    "ADMINISTRACION Y DESARROLLO",
    "COORDINADOR REGIONAL",
    "SECRETARIA TECNICA",
    "ADMIN",
]


def normalizar_mayus_sin_tildes(texto):
    """
    Devuelve el texto en MAYÚSCULAS, sin tildes/diéresis y sin espacios
    repetidos. Preserva la 'Ñ'. Si la entrada es None o vacía, devuelve None.
    """
    if texto is None:
        return None
    s = str(texto).strip()
    if not s:
        return None
    # Separar caracteres base + diacríticos; preservamos Ñ/ñ
    s = s.replace('Ñ', '\x00').replace('ñ', '\x01')
    s = unicodedata.normalize('NFD', s)
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    s = s.replace('\x00', 'Ñ').replace('\x01', 'Ñ')
    s = s.upper()
    # Colapsar espacios múltiples
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# Migración una sola vez al iniciar: normalizar cargos existentes
try:
    cursor.execute("""
        SELECT DISTINCT cargo FROM admin_users
        WHERE cargo IS NOT NULL AND cargo <> ''
    """)
    _rows_cargo = cursor.fetchall()
    _actualizados = 0
    for _r in _rows_cargo:
        _cargo_orig = _r[0]
        _cargo_norm = normalizar_mayus_sin_tildes(_cargo_orig)
        if _cargo_norm and _cargo_norm != _cargo_orig:
            cursor.execute(
                "UPDATE admin_users SET cargo = %s WHERE cargo = %s",
                (_cargo_norm, _cargo_orig)
            )
            _actualizados += cursor.rowcount
    conn.commit()
    if _actualizados:
        print(f"✅ Cargos normalizados en admin_users: {_actualizados} filas")
except Exception as _e_norm:
    print(f"⚠️ Error normalizando cargos existentes: {_e_norm}")
    try:
        conn.rollback()
    except Exception:
        pass


@app.get("/admin/cargos-catalogo")
async def obtener_cargos_catalogo():
    """Devuelve el catálogo oficial de cargos (mayúsculas sin tildes)."""
    return {"success": True, "cargos": CARGOS_ADMIN_CATALOGO}


@app.patch("/usuarios/{user_id}/estado")
async def cambiar_estado_usuario_regular(user_id: int, datos: dict):
    """Activar o desactivar una cuenta de usuario de la tabla usuarios"""
    try:
        print(f"🔄 Cambiando estado de usuario ID: {user_id}")
        
        activo = datos.get("activo")
        if activo is None:
            raise HTTPException(status_code=400, detail="El campo 'activo' es requerido")
        
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo, correo FROM usuarios WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
        
        nombre = row[1] or row[2]
        
        # Actualizar estado
        cursor.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, user_id))
        conn.commit()
        
        estado_texto = "activado" if activo else "desactivado"
        print(f"✅ Usuario {nombre} (ID: {user_id}) {estado_texto}")
        return {
            "message": f"Usuario {estado_texto} exitosamente",
            "id": user_id,
            "activo": activo
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error cambiando estado de usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar estado: {str(e)}")

class TerritorioUpdate(BaseModel):
    territorio: str

@app.patch("/usuarios/{user_id}/territorio")
async def actualizar_territorio(user_id: int, data: TerritorioUpdate):
    """Actualiza el territorio de un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Validar que el territorio sea uno de los territorios de Sembrando Vida
        if data.territorio not in TERRITORIOS_SEMBRANDO_VIDA:
            raise HTTPException(status_code=400, detail=f"Territorio inválido. Debe ser uno de los territorios de Sembrando Vida.")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Actualizar territorio
        cursor.execute(
            "UPDATE usuarios SET territorio = %s WHERE id = %s",
            (data.territorio, user_id)
        )
        conn.commit()
        
        print(f"✅ Territorio del usuario {user_id} actualizado a: {data.territorio}")
        return {
            "success": True,
            "mensaje": "Territorio actualizado exitosamente",
            "territorio": data.territorio
        }
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar territorio: {str(e)}")

# Endpoint para obtener lista de territorios de Sembrando Vida
@app.get("/territorios-sembrando-vida")
async def obtener_territorios():
    """Devuelve la lista de territorios de Sembrando Vida"""
    return {"territorios": TERRITORIOS_SEMBRANDO_VIDA}

# Mantener endpoint antiguo por compatibilidad (redirige a territorios)
@app.get("/estados-mexico")
async def obtener_estados_mexico():
    """DEPRECADO: Usar /territorios-sembrando-vida en su lugar"""
    return {"territorios": TERRITORIOS_SEMBRANDO_VIDA}

# Endpoint para resetear todos los territorios de usuarios (para migración)
@app.post("/admin/reset-territorios")
async def reset_todos_territorios():
    """Resetea el campo territorio de todos los usuarios a NULL para que vuelvan a seleccionar"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Contar cuántos usuarios tienen territorio asignado
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE territorio IS NOT NULL")
        usuarios_con_territorio = cursor.fetchone()[0]
        
        # Resetear todos los territorios a NULL
        cursor.execute("UPDATE usuarios SET territorio = NULL WHERE territorio IS NOT NULL")
        conn.commit()
        
        print(f"✅ Se resetearon {usuarios_con_territorio} territorios de usuarios")
        return {
            "success": True,
            "mensaje": f"Se resetearon {usuarios_con_territorio} territorios de usuarios",
            "usuarios_afectados": usuarios_con_territorio
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al resetear territorios: {str(e)}")

# Endpoint para eliminar un usuario específico con todos sus datos
@app.delete("/usuarios/{user_id}")
async def eliminar_usuario(user_id: int):
    """Elimina completamente un usuario y todos sus datos asociados"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🗑️ Iniciando eliminación completa del usuario {user_id}...")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, correo, nombre_completo FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
        
        usuario_info = {
            "id": usuario[0],
            "correo": usuario[1], 
            "nombre_completo": usuario[2]
        }
        
        print(f"👤 Usuario encontrado: {usuario_info}")
        
        # Contadores para el reporte
        registros_eliminados = 0
        asistencias_eliminadas = 0
        fotos_eliminadas = 0
        
        # 1. Obtener y eliminar fotos asociadas a registros del usuario
        try:
            cursor.execute("SELECT foto_url FROM registros WHERE usuario_id = %s AND foto_url IS NOT NULL", (user_id,))
            fotos_registros = cursor.fetchall()
            
            for foto_row in fotos_registros:
                foto_path = foto_row[0]
                if foto_path and os.path.exists(foto_path):
                    try:
                        os.remove(foto_path)
                        fotos_eliminadas += 1
                        print(f"📸 Foto eliminada: {foto_path}")
                    except Exception as e:
                        print(f"⚠️ Error eliminando foto {foto_path}: {e}")
                        
        except Exception as e:
            print(f"⚠️ Error obteniendo fotos de registros: {e}")
        
        # 2. Obtener y eliminar fotos asociadas a asistencias del usuario
        try:
            cursor.execute(
                "SELECT foto_entrada_url, foto_salida_url FROM asistencias WHERE usuario_id = %s", 
                (user_id,)
            )
            fotos_asistencias = cursor.fetchall()
            
            for foto_row in fotos_asistencias:
                # Foto de entrada
                if foto_row[0] and os.path.exists(foto_row[0]):
                    try:
                        os.remove(foto_row[0])
                        fotos_eliminadas += 1
                        print(f"📸 Foto de entrada eliminada: {foto_row[0]}")
                    except Exception as e:
                        print(f"⚠️ Error eliminando foto de entrada {foto_row[0]}: {e}")
                
                # Foto de salida
                if foto_row[1] and os.path.exists(foto_row[1]):
                    try:
                        os.remove(foto_row[1])
                        fotos_eliminadas += 1
                        print(f"📸 Foto de salida eliminada: {foto_row[1]}")
                    except Exception as e:
                        print(f"⚠️ Error eliminando foto de salida {foto_row[1]}: {e}")
                        
        except Exception as e:
            print(f"⚠️ Error obteniendo fotos de asistencias: {e}")
        
        # 3. Eliminar registros del usuario
        try:
            cursor.execute("SELECT COUNT(*) FROM registros WHERE usuario_id = %s", (user_id,))
            registros_eliminados = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM registros WHERE usuario_id = %s", (user_id,))
            print(f"📋 {registros_eliminados} registros eliminados")
            
        except Exception as e:
            print(f"❌ Error eliminando registros: {e}")
            raise HTTPException(status_code=500, detail=f"Error eliminando registros: {str(e)}")
        
        # 4. Eliminar asistencias del usuario
        try:
            cursor.execute("SELECT COUNT(*) FROM asistencias WHERE usuario_id = %s", (user_id,))
            asistencias_eliminadas = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM asistencias WHERE usuario_id = %s", (user_id,))
            print(f"⏰ {asistencias_eliminadas} asistencias eliminadas")
            
        except Exception as e:
            print(f"❌ Error eliminando asistencias: {e}")
            raise HTTPException(status_code=500, detail=f"Error eliminando asistencias: {str(e)}")
        
        # 5. Finalmente, eliminar el usuario
        try:
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
            print(f"👤 Usuario {user_id} eliminado")
            
        except Exception as e:
            print(f"❌ Error eliminando usuario: {e}")
            raise HTTPException(status_code=500, detail=f"Error eliminando usuario: {str(e)}")
        
        # Confirmar todos los cambios
        conn.commit()
        
        # Resumen de eliminación
        resultado = {
            "status": "success",
            "message": f"Usuario {user_id} eliminado completamente",
            "usuario_eliminado": usuario_info,
            "datos_eliminados": {
                "registros": registros_eliminados,
                "asistencias": asistencias_eliminadas,
                "fotos": fotos_eliminadas
            }
        }
        
        print(f"✅ ELIMINACIÓN COMPLETA EXITOSA:")
        print(f"   👤 Usuario: {usuario_info['correo']}")
        print(f"   📋 Registros: {registros_eliminados}")
        print(f"   ⏰ Asistencias: {asistencias_eliminadas}")
        print(f"   📸 Fotos: {fotos_eliminadas}")
        
        return resultado
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al eliminar usuario {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al eliminar usuario {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")

# Endpoint de autenticación para administradores con información de usuario
@app.post("/admin/login")
def admin_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # IP real detrás de nginx
    _login_ip = (request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
                 or (request.client.host if request.client else None))
    if _login_ip and "," in _login_ip:
        _login_ip = _login_ip.split(",")[0].strip()
    _login_ua = request.headers.get("user-agent")
    try:
        username = form_data.username
        password = form_data.password

        print(f"🔐 Intento de login para usuario: {username}")

        # Buscar usuario administrador en la base de datos incluyendo permisos, estado activo, es_territorial, territorio, nombre_completo, curp y cargo
        cursor.execute("SELECT id, password, rol, permisos, activo, es_territorial, territorio, nombre_completo, curp, cargo, password_enc FROM admin_users WHERE username = %s", (username,))
        row = cursor.fetchone()

        if not row or not pwd_context.verify(password, row[1]):
            print(f"❌ Credenciales incorrectas para usuario: {username}")
            _tel_log(usr=username, action_type="login_fallido", module="acceso",
                     detail=f"Intento de acceso FALLIDO con el usuario '{username}'",
                     http_method="POST", http_path="/admin/login", http_status=400,
                     ip_hint=_login_ip, ua=_login_ua, source="backend")
            raise HTTPException(status_code=400, detail="Credenciales incorrectas")
        
        user_id = row[0]
        user_rol = row[2] or 'admin'  # rol por defecto admin
        user_activo = row[4] if row[4] is not None else True  # activo por defecto True
        es_territorial = row[5] if row[5] is not None else False
        territorio = row[6]
        nombre_completo = row[7] or ''
        curp = row[8] or ''
        cargo = row[9] or ''
        
        # Verificar si el usuario está activo
        if not user_activo:
            print(f"❌ Usuario inactivo intentando acceder: {username}")
            _tel_log(usr=username, usr_id=user_id, usr_nombre=row[7], usr_rol=user_rol,
                     usr_territorio=row[6], usr_cargo=row[9],
                     action_type="login_bloqueado", module="acceso",
                     detail=f"Acceso BLOQUEADO (cuenta desactivada): '{username}'",
                     http_method="POST", http_path="/admin/login", http_status=403,
                     ip_hint=_login_ip, ua=_login_ua, source="backend")
            raise HTTPException(status_code=403, detail="Tu cuenta ha sido desactivada. Contacta al administrador.")
        
        # Bóveda: el login correcto confirma la contraseña real; guarda o corrige la copia cifrada
        if _vault:
            try:
                if _descifrar_pwd(row[10]) != password:
                    cursor.execute("UPDATE admin_users SET password_enc = %s WHERE id = %s", (_cifrar_pwd(password), user_id))
                    conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"⚠️ No se pudo actualizar la bóveda de contraseñas: {e}")

        # Parsear permisos
        permisos_str = row[3]
        if permisos_str:
            try:
                permisos = json.loads(permisos_str)
            except:
                permisos = PERMISOS_ADMIN_DEFAULT if user_rol == 'admin' else PERMISOS_USER_DEFAULT
        else:
            permisos = PERMISOS_ADMIN_DEFAULT if user_rol == 'admin' else PERMISOS_USER_DEFAULT
        
        # Generar token JWT con información del usuario incluyendo territorio
        token_data = {
            "sub": username, 
            "role": user_rol,
            "user_id": user_id,
            "tipo": "admin_user",
            "es_territorial": es_territorial,
            "territorio": territorio
        }
        token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
        
        print(f"✅ Login exitoso para usuario: {username} con rol: {user_rol}" + (f" (territorial: {territorio})" if es_territorial else ""))

        _tel_log(usr=username, usr_id=user_id, usr_nombre=nombre_completo, usr_rol=user_rol,
                 usr_territorio=territorio, usr_cargo=cargo,
                 action_type="login", module="acceso",
                 detail=f"Inició sesión correctamente en el admin-pwa" + (f" (territorial: {territorio})" if es_territorial else ""),
                 http_method="POST", http_path="/admin/login", http_status=200,
                 ip_hint=_login_ip, ua=_login_ua, source="backend")

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_info": {
                "id": user_id,
                "username": username,
                "rol": user_rol,
                "tipo": "admin_user",
                "permisos": permisos,
                "activo": user_activo,
                "es_territorial": es_territorial,
                "territorio": territorio,
                "nombre_completo": nombre_completo,
                "curp": curp,
                "cargo": cargo
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en admin login: {e}")
        raise HTTPException(status_code=500, detail=f"Error en autenticación: {str(e)}")

# Nuevo endpoint para obtener información del usuario actual
@app.get("/auth/me")
async def get_current_user():
    """Obtener información del usuario actualmente logueado"""
    try:
        # Este endpoint simula obtener la información del usuario desde el token
        # En una implementación real, se verificaría el token JWT
        print("🔍 Obteniendo información del usuario actual")
        
        # Por ahora devuelve información por defecto de admin
        return {
            "id": 1,
            "username": "admin",
            "rol": "admin",
            "tipo": "admin_user",
            "is_authenticated": True
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo usuario actual: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuario: {str(e)}")

# Endpoint para verificar si un usuario está activo (para verificación en tiempo real)
@app.get("/auth/check-active/{username}")
async def check_user_active(username: str):
    """Verificar si un usuario específico está activo"""
    try:
        print(f"🔍 Verificando estado activo de usuario: {username}")
        
        cursor.execute("SELECT id, activo FROM admin_users WHERE username = %s", (username,))
        row = cursor.fetchone()
        
        if not row:
            return {"active": False, "exists": False, "message": "Usuario no encontrado"}
        
        activo = row[1] if row[1] is not None else True
        
        return {
            "active": activo,
            "exists": True,
            "user_id": row[0],
            "username": username
        }
        
    except Exception as e:
        print(f"❌ Error verificando estado de usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al verificar usuario: {str(e)}")

# Endpoint para verificación completa de sesión (activo, rol, permisos) - TIEMPO REAL
@app.get("/auth/check-session/{username}")
async def check_user_session(username: str):
    """Verificar estado completo de sesión de un usuario (activo, rol, permisos, territorio)"""
    try:
        print(f"🔍 Verificando sesión completa de usuario: {username}")
        
        cursor.execute("""
            SELECT id, rol, permisos, activo, es_territorial, territorio, cargo, usuario_id
            FROM admin_users 
            WHERE username = %s
        """, (username,))
        row = cursor.fetchone()
        
        if not row:
            return {
                "active": False, 
                "exists": False, 
                "message": "Usuario no encontrado"
            }
        
        user_id = row[0]
        user_rol = row[1] or 'user'
        permisos_str = row[2]
        activo = row[3] if row[3] is not None else True
        es_territorial = row[4] if row[4] is not None else False
        territorio = row[5]
        cargo = row[6] or ''
        usuario_id_vinculado = row[7]
        
        # Parsear permisos
        if permisos_str:
            try:
                permisos = json.loads(permisos_str)
            except:
                permisos = PERMISOS_ADMIN_DEFAULT if user_rol == 'admin' else PERMISOS_USER_DEFAULT
        else:
            permisos = PERMISOS_ADMIN_DEFAULT if user_rol == 'admin' else PERMISOS_USER_DEFAULT
        
        return {
            "active": activo,
            "exists": True,
            "user_id": user_id,
            "username": username,
            "rol": user_rol,
            "permisos": permisos,
            "es_territorial": es_territorial,
            "territorio": territorio,
            "cargo": cargo,
            "usuario_id_vinculado": usuario_id_vinculado
        }
        
    except Exception as e:
        print(f"❌ Error verificando sesión de usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al verificar sesión: {str(e)}")

# Endpoint para verificar permisos específicos
@app.get("/auth/check-permission/{permission}")
async def check_permission(permission: str):
    """Verificar si el usuario actual tiene un permiso específico"""
    try:
        print(f"🔐 Verificando permiso: {permission}")
        
        # Lista de permisos que requieren admin
        admin_permissions = [
            "usuarios.view",
            "usuarios.create", 
            "usuarios.edit",
            "usuarios.delete",
            "permisos.view",
            "permisos.manage",
            "configuracion.view",
            "configuracion.manage",
            "admin.access"
        ]
        
        # Por ahora siempre devolver admin = True
        # En implementación real se verificaría el token JWT
        user_role = "admin"  # Obtener del token
        
        has_permission = user_role == "admin" or permission not in admin_permissions
        
        return {
            "permission": permission,
            "granted": has_permission,
            "user_role": user_role
        }
        
    except Exception as e:
        print(f"❌ Error verificando permiso: {e}")
        raise HTTPException(status_code=500, detail=f"Error al verificar permiso: {str(e)}")

# Define el timezone de CDMX
CDMX_TZ = pytz.timezone("America/Mexico_City")

def obtener_fecha_hora_cdmx(timestamp_offline=None):
    """
    Función de utilidad para manejar correctamente las fechas y horas en zona CDMX.
    
    Args:
        timestamp_offline (str): Timestamp ISO string opcional desde el cliente
        
    Returns:
        tuple: (fecha_cdmx, hora_cdmx, timestamp_for_filename)
    """
    if timestamp_offline:
        try:
            print(f"🕐 Procesando timestamp offline: '{timestamp_offline}'")
            
            # NUEVA LÓGICA MÁS ROBUSTA PARA PARSEAR TIMESTAMPS
            fecha_hora_utc = None
            
            # Caso 1: Termina con Z (UTC)
            if timestamp_offline.endswith('Z'):
                fecha_hora_utc = datetime.fromisoformat(timestamp_offline.replace('Z', '+00:00'))
                print(f"   📝 Formato detectado: UTC con Z")
                
            # Caso 2: Ya tiene información de zona horaria (+ o -)
            elif '+' in timestamp_offline or timestamp_offline.count('-') > 2:
                fecha_hora_utc = datetime.fromisoformat(timestamp_offline)
                print(f"   📝 Formato detectado: Con zona horaria")
                
            # Caso 3: Solo fecha y hora, asumir UTC
            else:
                # Verificar si tiene microsegundos
                if '.' in timestamp_offline:
                    # Formato: 2025-07-27T23:30:45.123
                    fecha_hora_utc = datetime.fromisoformat(timestamp_offline).replace(tzinfo=pytz.UTC)
                else:
                    # Formato: 2025-07-27T23:30:45
                    fecha_hora_utc = datetime.fromisoformat(timestamp_offline).replace(tzinfo=pytz.UTC)
                print(f"   📝 Formato detectado: Sin zona, asumiendo UTC")
            
            print(f"   🌍 Timestamp parseado como UTC: {fecha_hora_utc}")
            
            # CLAVE: Convertir a zona horaria de CDMX PRIMERO
            hora_cdmx = fecha_hora_utc.astimezone(CDMX_TZ)
            
            # LUEGO extraer la fecha LOCAL de CDMX (no UTC)
            fecha_cdmx = hora_cdmx.date()
            
            print(f"📅 ✅ Conversión de timestamp completada:")
            print(f"   🌍 UTC original: {fecha_hora_utc}")
            print(f"   🇲🇽 CDMX convertido: {hora_cdmx}")
            print(f"   📆 Fecha LOCAL CDMX: {fecha_cdmx}")
            print(f"   📊 Día de la semana: {fecha_cdmx.strftime('%A')}")
            
            timestamp_for_filename = hora_cdmx.strftime('%Y%m%d%H%M%S')
            
            return fecha_cdmx, hora_cdmx, timestamp_for_filename
            
        except Exception as e:
            print(f"⚠️ ERROR parseando timestamp offline '{timestamp_offline}': {e}")
            print(f"🔄 Fallback a tiempo actual de CDMX")
            # Fallback a tiempo actual
            pass
    
    # Usar tiempo actual de CDMX
    now_cdmx = datetime.now(CDMX_TZ)
    fecha_cdmx = now_cdmx.date()
    timestamp_for_filename = now_cdmx.strftime('%Y%m%d%H%M%S')
    
    print(f"📅 ⏰ Usando timestamp actual CDMX:")
    print(f"   🇲🇽 Hora CDMX: {now_cdmx}")
    print(f"   📆 Fecha CDMX: {fecha_cdmx}")
    print(f"   📊 Día de la semana: {fecha_cdmx.strftime('%A')}")
    
    return fecha_cdmx, now_cdmx, timestamp_for_filename

@app.post("/asistencia/entrada")
async def marcar_entrada(
    usuario_id: int = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    descripcion: str = Form(""),
    foto: UploadFile = File(...),
    timestamp_offline: str = Form(None)  # Nuevo campo opcional para registro offline
):
    try:
        print(f"🔍 ENTRADA - Datos recibidos:")
        print(f"   usuario_id: {usuario_id} (tipo: {type(usuario_id)})")
        print(f"   latitud: {latitud}")
        print(f"   longitud: {longitud}")
        print(f"   descripcion: {descripcion}")
        print(f"   foto: {foto.filename}")
        print(f"   timestamp_offline: {timestamp_offline}")

        # Leer el archivo PRIMERO (único punto de await) para evitar que otros requests
        # corrompan el cursor global mientras esperamos el upload
        contenido = await foto.read()

        # Verificar/reconectar BD después del await - a partir de aquí todo es síncrono
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")

        # Usar timestamp personalizado si viene de offline, sino usar tiempo actual
        fecha, hora_entrada, timestamp_for_filename = obtener_fecha_hora_cdmx(timestamp_offline)

        # Revisa si ya existe asistencia para hoy para este usuario específico
        cursor.execute(
            "SELECT id FROM asistencias WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, fecha)
        )
        existe = cursor.fetchone()

        print(f"🔍 Verificando entrada para usuario {usuario_id} en fecha {fecha}")
        print(f"📊 Resultado de consulta: {existe}")

        if existe:
            raise HTTPException(
                status_code=400,
                detail=f"El usuario {usuario_id} ya tiene registro de entrada para el día {fecha}"
            )

        # Guardar la foto en disco usando el timestamp correcto
        ext = os.path.splitext(foto.filename)[1]
        nombre_archivo = f"entrada_{usuario_id}_{timestamp_for_filename}{ext}"
        ruta_archivo = os.path.join(FOTOS_DIR, nombre_archivo)

        with open(ruta_archivo, "wb") as f:
            f.write(contenido)

        # Insertar registro de asistencia con ubicación y foto
        cursor.execute(
            "INSERT INTO asistencias (usuario_id, fecha, hora_entrada, latitud_entrada, longitud_entrada, foto_entrada_url, descripcion_entrada) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (usuario_id, fecha, hora_entrada, latitud, longitud, ruta_archivo, descripcion)
        )
        conn.commit()
        print(f"✅ Entrada registrada para usuario {usuario_id} a las {hora_entrada}")

        return {
            "status": "ok",
            "mensaje": "Entrada registrada exitosamente",
            "hora_entrada": str(hora_entrada),
            "latitud": latitud,
            "longitud": longitud,
            "foto_url": ruta_archivo,
            "descripcion": descripcion
        }

    except HTTPException:
        raise
    except psycopg2.Error as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        print(f"❌ Error de PostgreSQL en entrada: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        print(f"❌ Error general en entrada: {e}")
        raise HTTPException(status_code=500, detail=f"Error al registrar entrada: {str(e)}")

@app.post("/asistencia/salida")
async def marcar_salida(
    usuario_id: int = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    descripcion: str = Form(""),
    foto: UploadFile = File(...),
    timestamp_offline: str = Form(None)  # Nuevo campo opcional para registro offline
):
    try:
        print(f"🔍 SALIDA - Datos recibidos:")
        print(f"   usuario_id: {usuario_id} (tipo: {type(usuario_id)})")
        print(f"   latitud: {latitud}")
        print(f"   longitud: {longitud}")
        print(f"   descripcion: {descripcion}")
        print(f"   foto: {foto.filename}")
        print(f"   timestamp_offline: {timestamp_offline}")

        # Leer el archivo PRIMERO (único punto de await) para evitar que otros requests
        # corrompan el cursor global mientras esperamos el upload
        contenido = await foto.read()

        # Verificar/reconectar BD después del await - a partir de aquí todo es síncrono
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")

        # Usar timestamp personalizado si viene de offline, sino usar tiempo actual
        fecha, hora_salida, timestamp_for_filename = obtener_fecha_hora_cdmx(timestamp_offline)

        # Busca el registro de asistencia de hoy para este usuario específico
        cursor.execute(
            "SELECT id, hora_salida FROM asistencias WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, fecha)
        )
        registro = cursor.fetchone()

        print(f"🔍 Verificando salida para usuario {usuario_id} en fecha {fecha}")
        print(f"📊 Resultado de consulta: {registro}")

        if not registro:
            raise HTTPException(
                status_code=400,
                detail=f"El usuario {usuario_id} no tiene registro de entrada para el día {fecha}"
            )
        if registro[1] is not None:
            raise HTTPException(
                status_code=400,
                detail=f"El usuario {usuario_id} ya registró la salida para el día {fecha}"
            )

        # Guardar la foto en disco usando el timestamp correcto
        ext = os.path.splitext(foto.filename)[1]
        nombre_archivo = f"salida_{usuario_id}_{timestamp_for_filename}{ext}"
        ruta_archivo = os.path.join(FOTOS_DIR, nombre_archivo)

        with open(ruta_archivo, "wb") as f:
            f.write(contenido)

        # Actualizar registro con salida, ubicación y foto
        cursor.execute(
            "UPDATE asistencias SET hora_salida = %s, latitud_salida = %s, longitud_salida = %s, foto_salida_url = %s, descripcion_salida = %s WHERE usuario_id = %s AND fecha = %s",
            (hora_salida, latitud, longitud, ruta_archivo, descripcion, usuario_id, fecha)
        )
        conn.commit()
        print(f"✅ Salida registrada para usuario {usuario_id} a las {hora_salida}")

        return {
            "status": "ok",
            "mensaje": "Salida registrada exitosamente",
            "hora_salida": str(hora_salida),
            "latitud": latitud,
            "longitud": longitud,
            "foto_url": ruta_archivo,
            "descripcion": descripcion
        }

    except HTTPException:
        raise
    except psycopg2.Error as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        print(f"❌ Error de PostgreSQL en salida: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        print(f"❌ Error general en salida: {e}")
        raise HTTPException(status_code=500, detail=f"Error al registrar salida: {str(e)}")

@app.get("/asistencia/hoy/{usuario_id}")
async def consultar_asistencia_hoy(usuario_id: int):
    """
    Consulta la asistencia del día actual para un usuario específico.
    Usa la zona horaria de CDMX para determinar correctamente qué es 'hoy'.
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔍 Consultando asistencia del día actual para usuario {usuario_id}")
        
        # CRUCIAL: Usar la fecha actual en zona horaria CDMX
        now_cdmx = datetime.now(CDMX_TZ)
        fecha_hoy_cdmx = now_cdmx.date()
        
        print(f"📅 Fecha actual en CDMX: {fecha_hoy_cdmx}")
        print(f"⏰ Hora actual en CDMX: {now_cdmx.strftime('%H:%M:%S')}")
        
        # Consultar asistencia para la fecha actual en CDMX
        cursor.execute(
            """SELECT id, usuario_id, fecha, hora_entrada, hora_salida, 
                      latitud_entrada, longitud_entrada, latitud_salida, longitud_salida,
                      foto_entrada_url, foto_salida_url, descripcion_entrada, descripcion_salida
               FROM asistencias 
               WHERE usuario_id = %s AND fecha = %s""",
            (usuario_id, fecha_hoy_cdmx)
        )
        
        registro = cursor.fetchone()
        
        print(f"📊 Registro encontrado: {registro is not None}")
        
        if registro:
            # Construir respuesta con datos encontrados
            resultado = {
                "id": registro[0],
                "usuario_id": registro[1],
                "fecha": registro[2].isoformat() if registro[2] else None,
                "entrada": registro[3].isoformat() if registro[3] else None,
                "salida": registro[4].isoformat() if registro[4] else None,
                "latitud_entrada": float(registro[5]) if registro[5] else None,
                "longitud_entrada": float(registro[6]) if registro[6] else None,
                "latitud_salida": float(registro[7]) if registro[7] else None,
                "longitud_salida": float(registro[8]) if registro[8] else None,
                "foto_entrada_url": registro[9],
                "foto_salida_url": registro[10],
                "descripcion_entrada": registro[11],
                "descripcion_salida": registro[12]
            }
        else:
            # No hay registro para hoy, devolver estructura vacía
            resultado = {
                "id": None,
                "usuario_id": usuario_id,
                "fecha": fecha_hoy_cdmx.isoformat(),
                "entrada": None,
                "salida": None,
                "latitud_entrada": None,
                "longitud_entrada": None,
                "latitud_salida": None,
                "longitud_salida": None,
                "foto_entrada_url": None,
                "foto_salida_url": None,
                "descripcion_entrada": None,
                "descripcion_salida": None
            }
        
        print(f"✅ Consulta de asistencia hoy completada: {resultado['entrada'] is not None}, {resultado['salida'] is not None}")
        return resultado
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL en consulta hoy: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general en consulta hoy: {e}")
        raise HTTPException(status_code=500, detail=f"Error al consultar asistencia de hoy: {str(e)}")

@app.get("/debug/tiempo-actual")
async def debug_tiempo_actual():
    """Endpoint para verificar la hora y fecha actual en diferentes zonas horarias"""
    try:
        import pytz
        from datetime import datetime
        
        # Hora UTC
        utc_now = datetime.utcnow()
        
        # Hora en CDMX
        cdmx_tz = pytz.timezone("America/Mexico_City")
        cdmx_now = datetime.now(cdmx_tz)
        
        # Fecha en CDMX (que es lo que usamos para comparar asistencias)
        fecha_cdmx = cdmx_now.date()
        
        resultado = {
            "utc": {
                "datetime": utc_now.isoformat(),
                "fecha": utc_now.date().isoformat(),
                "hora": utc_now.strftime("%H:%M:%S"),
                "timestamp_filename": utc_now.strftime('%Y%m%d%H%M%S')
            },
            "cdmx": {
                "datetime": cdmx_now.isoformat(),
                "fecha": fecha_cdmx.isoformat(),
                "hora": cdmx_now.strftime("%H:%M:%S"),
                "timestamp_filename": cdmx_now.strftime('%Y%m%d%H%M%S'),
                "timezone_name": str(cdmx_now.tzinfo),
                "timezone_offset": cdmx_now.strftime('%z')
            },
            "comparacion": {
                "misma_fecha": utc_now.date() == fecha_cdmx,
                "diferencia_horas": int((cdmx_now - utc_now.replace(tzinfo=pytz.UTC)).total_seconds() / 3600)
            },
            "mensaje": f"En CDMX son las {cdmx_now.strftime('%H:%M:%S')} del {fecha_cdmx.strftime('%Y-%m-%d')}"
        }
        
        return resultado
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/asistencias")
async def obtener_historial_asistencias(usuario_id: int = None, limit: int = None, offset: int = 0, territorio: str = None, fecha: str = None, fecha_inicio: str = None, fecha_fin: str = None):
    try:
        # Verificar y reconectar si es necesario
        if not verificar_conexion_db():
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Límite de seguridad: sin esto, la consulta trae la tabla completa de
        # asistencias en cada carga del visor de mapa, creciendo sin límite y
        # ralentizando cada vez más el mapa a medida que se acumulan datos.
        if limit is None or limit > 20000:
            limit = 20000

        print(f"🔍 Obteniendo historial de asistencias - Usuario: {usuario_id}, Límite: {limit}, Offset: {offset}, Territorio: {territorio}, Fecha: {fecha}, Rango: {fecha_inicio} - {fecha_fin}")

        # Construir la query base con JOIN a usuarios si hay filtro de territorio
        base_select = """SELECT a.id, a.usuario_id, a.fecha, a.hora_entrada, a.hora_salida, 
                         a.latitud_entrada, a.longitud_entrada, a.latitud_salida, a.longitud_salida,
                         a.foto_entrada_url, a.foto_salida_url, a.descripcion_entrada, a.descripcion_salida
                  FROM asistencias a"""
        
        if territorio:
            base_select += " INNER JOIN usuarios u ON a.usuario_id = u.id"
        
        # Construir condiciones WHERE
        conditions = []
        params = []
        
        if usuario_id:
            conditions.append("a.usuario_id = %s")
            params.append(usuario_id)
        
        if territorio:
            conditions.append("u.territorio = %s")
            params.append(territorio)
        
        # Filtro por fecha exacta
        if fecha:
            conditions.append("a.fecha = %s")
            params.append(fecha)
        
        # Filtro por rango de fechas
        if fecha_inicio:
            conditions.append("a.fecha >= %s")
            params.append(fecha_inicio)
        
        if fecha_fin:
            conditions.append("a.fecha <= %s")
            params.append(fecha_fin)
        
        # Construir query completa
        query = base_select
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY a.fecha DESC, a.hora_entrada DESC"
        
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        
        query += " OFFSET %s"
        params.append(offset)
        
        cursor.execute(query, tuple(params))
        
        resultados = cursor.fetchall()
        print(f"📊 Encontradas {len(resultados)} asistencias (limit: {limit}, offset: {offset}, territorio: {territorio})")
        
        # Convertir tuplas a diccionarios manualmente
        asistencias = []
        for row in resultados:
            # Procesar fecha correctamente (es DATE, no DATETIME)
            # No agregar timezone a la fecha, solo formatearla como YYYY-MM-DD
            fecha_str = row[2].isoformat() if row[2] else None
            
            # Procesar hora_entrada (es TIME o DATETIME)
            hora_entrada_str = None
            if row[3]:
                # Si es un objeto time, convertirlo a string simple
                if hasattr(row[3], 'isoformat'):
                    hora_entrada_str = row[3].isoformat()
                else:
                    hora_entrada_str = str(row[3])
            
            # Procesar hora_salida (es TIME o DATETIME)
            hora_salida_str = None
            if row[4]:
                if hasattr(row[4], 'isoformat'):
                    hora_salida_str = row[4].isoformat()
                else:
                    hora_salida_str = str(row[4])
            
            asistencia = {
                "id": row[0],
                "usuario_id": row[1],
                "fecha": fecha_str,
                "hora_entrada": hora_entrada_str,
                "hora_salida": hora_salida_str,
                "latitud_entrada": float(row[5]) if row[5] else None,
                "longitud_entrada": float(row[6]) if row[6] else None,
                "latitud_salida": float(row[7]) if row[7] else None,
                "longitud_salida": float(row[8]) if row[8] else None,
                "foto_entrada_url": row[9],
                "foto_salida_url": row[10],
                "descripcion_entrada": row[11],
                "descripcion_salida": row[12]
            }
            asistencias.append(asistencia)
        
        print(f"✅ Historial completo de {len(asistencias)} asistencias procesado correctamente")
        return {"asistencias": asistencias}
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")

# Endpoint de test para simular registro de asistencia
@app.post("/debug/test-asistencia-fecha")
async def test_asistencia_fecha(
    timestamp_offline: str = Form(None)
):
    """Test para verificar exactamente cómo se procesa una fecha en asistencia"""
    try:
        print(f"🧪 TEST ASISTENCIA - Timestamp recibido: {timestamp_offline}")
        
        # Usar la misma función que usan las asistencias reales
        fecha, hora, filename = obtener_fecha_hora_cdmx(timestamp_offline)
        
        # Simular lo que haría la base de datos
        registro_simulado = {
            "usuario_id": 999,  # ID de test
            "fecha": fecha.isoformat(),
            "hora_entrada": hora.isoformat(),
            "timestamp_filename": filename
        }
        
        # Información actual para comparar
        ahora_cdmx = datetime.now(CDMX_TZ)
        
        result = {
            "test_resultado": {
                "timestamp_input": timestamp_offline,
                "fecha_procesada": fecha.isoformat(),
                "dia_procesado": fecha.strftime('%A, %d de %B %Y'),
                "hora_procesada": hora.isoformat(),
                "filename_generado": filename
            },
            
            "comparacion_fecha": {
                "fecha_hoy_real": ahora_cdmx.date().isoformat(),
                "dia_hoy_real": ahora_cdmx.strftime('%A, %d de %B %Y'),
                "coincide_con_hoy": fecha == ahora_cdmx.date(),
                "diferencia_dias": (fecha - ahora_cdmx.date()).days
            },
            
            "registro_que_se_guardaria": registro_simulado,
            
            "diagnostico_final": {
                "problema_detectado": fecha != ahora_cdmx.date(),
                "mensaje": "FECHA CORRECTA ✅" if fecha == ahora_cdmx.date() else f"FECHA INCORRECTA ❌ - Diferencia: {(fecha - ahora_cdmx.date()).days} días"
            }
        }
        
        print(f"🧪 RESULTADO TEST ASISTENCIA:")
        print(f"   📅 Fecha que se guardará: {fecha} ({fecha.strftime('%A')})")
        print(f"   ✅ ¿Es correcto?: {fecha == ahora_cdmx.date()}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error en test asistencia: {e}")
        return {"error": f"Error en test: {e}"}

# Endpoint de debugging ESPECÍFICO para el problema de fechas
@app.get("/debug/problema-fecha-actual")
async def debug_problema_fecha():
    """Debugging específico para entender por qué se guarda un día antes"""
    try:
        import pytz
        from datetime import datetime
        
        # Hora actual real
        ahora_utc = datetime.utcnow()
        ahora_cdmx = datetime.now(CDMX_TZ)
        
        # Simular un timestamp que podría venir del frontend
        timestamp_simulado = ahora_cdmx.isoformat()
        
        # Probar nuestra función
        fecha_resultado, hora_resultado, filename_resultado = obtener_fecha_hora_cdmx(timestamp_simulado)
        
        # También probar sin timestamp (tiempo actual)
        fecha_actual, hora_actual, filename_actual = obtener_fecha_hora_cdmx(None)
        
        return {
            "analisis_completo": {
                "fecha_esperada_hoy": ahora_cdmx.date().isoformat(),
                "dia_esperado": ahora_cdmx.strftime('%A, %d de %B %Y'),
                
                "con_timestamp_simulado": {
                    "timestamp_input": timestamp_simulado,
                    "fecha_obtenida": fecha_resultado.isoformat(),
                    "dia_obtenido": fecha_resultado.strftime('%A, %d de %B %Y'),
                    "es_correcto": fecha_resultado == ahora_cdmx.date(),
                    "diferencia_dias": (fecha_resultado - ahora_cdmx.date()).days
                },
                
                "sin_timestamp_actual": {
                    "fecha_obtenida": fecha_actual.isoformat(), 
                    "dia_obtenido": fecha_actual.strftime('%A, %d de %B %Y'),
                    "es_correcto": fecha_actual == ahora_cdmx.date(),
                    "diferencia_dias": (fecha_actual - ahora_cdmx.date()).days
                },
                
                "referencias_tiempo": {
                    "utc_ahora": ahora_utc.isoformat(),
                    "cdmx_ahora": ahora_cdmx.isoformat(),
                    "diferencia_horas": (ahora_cdmx - ahora_utc.replace(tzinfo=pytz.UTC)).total_seconds() / 3600
                }
            },
            
            "diagnostico": {
                "problema_detectado": fecha_resultado != ahora_cdmx.date() or fecha_actual != ahora_cdmx.date(),
                "causa_probable": "Conversión de zona horaria incorrecta" if fecha_resultado != ahora_cdmx.date() else "Función trabajando correctamente",
                "accion_recomendada": "Revisar lógica de conversión de timestamps" if fecha_resultado != ahora_cdmx.date() else "No hay problema"
            }
        }
        
    except Exception as e:
        return {"error": f"Error en debugging: {e}"}

# Endpoint de debugging para fechas y zonas horarias
@app.get("/debug/fecha-zona-horaria")
async def debug_fecha_zona_horaria():
    """Endpoint para debugging de zonas horarias y fechas"""
    try:
        # Tiempo actual en diferentes zonas
        utc_now = datetime.utcnow()
        cdmx_now = datetime.now(CDMX_TZ)
        
        # Probar la función de utilidad
        fecha_util, hora_util, filename_util = obtener_fecha_hora_cdmx()
        
        return {
            "debug_info": {
                "utc_actual": {
                    "datetime": utc_now.isoformat(),
                    "fecha": utc_now.date().isoformat(),
                    "dia_semana": utc_now.strftime('%A')
                },
                "cdmx_actual": {
                    "datetime": cdmx_now.isoformat(),
                    "fecha": cdmx_now.date().isoformat(),
                    "dia_semana": cdmx_now.strftime('%A')
                },
                "funcion_utilidad": {
                    "fecha": fecha_util.isoformat(),
                    "hora": hora_util.isoformat(),
                    "filename": filename_util,
                    "dia_semana": fecha_util.strftime('%A')
                }
            },
            "problema_detectado": {
                "diferencia_fechas": utc_now.date() != cdmx_now.date(),
                "diferencia_horas": abs((cdmx_now - utc_now.replace(tzinfo=pytz.UTC)).total_seconds() / 3600),
                "recomendacion": "Siempre usar la fecha de CDMX para registros"
            }
        }
        
    except Exception as e:
        return {"error": f"Error en debug: {e}"}

# Endpoint de test para debugging de asistencias
@app.post("/debug/test-fecha-asistencia")
async def test_fecha_asistencia(
    timestamp_offline: str = Form(None)
):
    """Test para verificar cómo se procesan las fechas en asistencias"""
    try:
        print(f"🧪 TEST - Timestamp recibido: {timestamp_offline}")
        
        # Probar la función de utilidad
        fecha, hora, filename = obtener_fecha_hora_cdmx(timestamp_offline)
        
        # Información detallada
        result = {
            "test_info": {
                "timestamp_input": timestamp_offline,
                "fecha_procesada": fecha.isoformat(),
                "hora_procesada": hora.isoformat(),
                "filename_generado": filename,
                "dia_semana": fecha.strftime('%A, %d de %B %Y'),
                "zona_horaria": str(hora.tzinfo)
            },
            "verificaciones": {
                "es_hoy": fecha == datetime.now(CDMX_TZ).date(),
                "timestamp_valido": timestamp_offline is not None,
                "zona_correcta": str(hora.tzinfo) == "America/Mexico_City"
            }
        }
        
        print(f"🧪 RESULTADO DEL TEST:")
        print(f"   📅 Fecha: {fecha} ({fecha.strftime('%A')})")
        print(f"   🕐 Hora: {hora}")
        print(f"   ✅ Es hoy: {result['verificaciones']['es_hoy']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
        return {"error": f"Error en test: {e}"}

# Endpoint temporal para verificar la estructura de la tabla asistencias
@app.get("/debug/asistencias-estructura")
async def verificar_estructura_asistencias():
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar si la tabla existe
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'asistencias'
        """)
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            return {"error": "La tabla 'asistencias' no existe"}
        
        # Obtener la estructura de la tabla
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'asistencias' 
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        # Obtener algunos registros de ejemplo
        cursor.execute("SELECT * FROM asistencias LIMIT 3")
        registros_ejemplo = cursor.fetchall()
        
        return {
            "tabla_existe": True,
            "columnas": [{"nombre": col[0], "tipo": col[1], "nullable": col[2]} for col in columnas],
            "total_registros": len(registros_ejemplo),
            "registros_ejemplo": registros_ejemplo
        }
        
    except Exception as e:
        print(f"❌ Error verificando estructura: {e}")
        raise HTTPException(status_code=500, detail=f"Error verificando estructura: {str(e)}")

# Endpoints para eliminación masiva (ADMIN ONLY)
@app.delete("/admin/usuarios/all")
async def eliminar_todos_usuarios():
    """Elimina TODOS los usuarios de la base de datos. ¡USO EXTREMO!"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Contar usuarios antes de eliminar
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        total_usuarios = cursor.fetchone()[0]
        
        if total_usuarios == 0:
            return {
                "status": "info",
                "message": "No hay usuarios para eliminar",
                "usuarios_eliminados": 0
            }
        
        # Eliminar todos los usuarios
        cursor.execute("DELETE FROM usuarios")
        conn.commit()
        
        print(f"🗑️ ELIMINACIÓN MASIVA: {total_usuarios} usuarios eliminados")
        
        return {
            "status": "success",
            "message": f"Todos los usuarios han sido eliminados exitosamente",
            "usuarios_eliminados": total_usuarios
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al eliminar usuarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al eliminar usuarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuarios: {str(e)}")

# Modelo para actualización de registro
class RegistroUpdate(BaseModel):
    tipo_actividad: Optional[str] = None
    descripcion: Optional[str] = None
    categoria_actividad: Optional[str] = None
    categoria_actividad_otro: Optional[str] = None
    fecha_hora: Optional[str] = None

@app.put("/api/registros/{registro_id}")
async def actualizar_registro(registro_id: int, datos: RegistroUpdate):
    """Actualiza un registro de actividad específico"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar si el registro existe
        cursor.execute("SELECT id FROM registros WHERE id = %s", (registro_id,))
        registro = cursor.fetchone()
        
        if not registro:
            raise HTTPException(status_code=404, detail=f"Registro con ID {registro_id} no encontrado")
        
        # Construir la consulta de actualización dinámicamente
        campos_actualizar = []
        valores = []
        
        if datos.tipo_actividad is not None:
            campos_actualizar.append("tipo_actividad = %s")
            valores.append(datos.tipo_actividad)
        
        if datos.descripcion is not None:
            campos_actualizar.append("descripcion = %s")
            valores.append(datos.descripcion)
        
        if datos.categoria_actividad is not None:
            campos_actualizar.append("categoria_actividad = %s")
            valores.append(datos.categoria_actividad)
        
        if datos.categoria_actividad_otro is not None:
            campos_actualizar.append("categoria_actividad_otro = %s")
            valores.append(datos.categoria_actividad_otro)
        
        if datos.fecha_hora is not None:
            campos_actualizar.append("fecha_hora = %s")
            valores.append(datos.fecha_hora)
        
        if not campos_actualizar:
            raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
        
        # Agregar el ID al final de los valores
        valores.append(registro_id)
        
        query = f"UPDATE registros SET {', '.join(campos_actualizar)} WHERE id = %s"
        cursor.execute(query, tuple(valores))
        conn.commit()
        
        print(f"✏️ Registro #{registro_id} actualizado: tipo={datos.tipo_actividad}, categoria={datos.categoria_actividad}, fecha_hora={datos.fecha_hora}")
        
        return {
            "status": "success",
            "message": f"Registro #{registro_id} actualizado exitosamente",
            "registro_id": registro_id,
            "campos_actualizados": {
                "tipo_actividad": datos.tipo_actividad,
                "descripcion": datos.descripcion,
                "categoria_actividad": datos.categoria_actividad,
                "categoria_actividad_otro": datos.categoria_actividad_otro,
                "fecha_hora": datos.fecha_hora
            }
        }
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al actualizar registro: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al actualizar registro: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar registro: {str(e)}")

@app.delete("/admin/registros/{registro_id}")
async def eliminar_registro(registro_id: int):
    """Elimina un registro específico por su ID"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar si el registro existe
        cursor.execute("SELECT id, foto_url FROM registros WHERE id = %s", (registro_id,))
        registro = cursor.fetchone()
        
        if not registro:
            raise HTTPException(status_code=404, detail=f"Registro con ID {registro_id} no encontrado")
        
        foto_url = registro[1]
        
        # Eliminar el archivo de foto si existe
        if foto_url:
            try:
                # La ruta de la foto es relativa, construir ruta absoluta
                foto_path = os.path.join("fotos", os.path.basename(foto_url))
                if os.path.exists(foto_path):
                    os.remove(foto_path)
                    print(f"📷 Foto eliminada: {foto_path}")
            except Exception as foto_error:
                print(f"⚠️ Error al eliminar foto: {foto_error}")
                # Continuar aunque falle la eliminación de la foto
        
        # Eliminar el registro de la base de datos
        cursor.execute("DELETE FROM registros WHERE id = %s", (registro_id,))
        conn.commit()
        
        print(f"🗑️ Registro #{registro_id} eliminado exitosamente")
        
        return {
            "status": "success",
            "message": f"Registro #{registro_id} eliminado exitosamente",
            "registro_id": registro_id
        }
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al eliminar registro: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al eliminar registro: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar registro: {str(e)}")

@app.delete("/admin/registros/all")
async def eliminar_todos_registros():
    """Elimina TODOS los registros de la base de datos. ¡USO EXTREMO!"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Contar registros antes de eliminar
        cursor.execute("SELECT COUNT(*) FROM registros")
        total_registros = cursor.fetchone()[0]
        
        if total_registros == 0:
            return {
                "status": "info",
                "message": "No hay registros para eliminar",
                "registros_eliminados": 0
            }
        
        # Eliminar todos los registros
        cursor.execute("DELETE FROM registros")
        conn.commit()
        
        print(f"🗑️ ELIMINACIÓN MASIVA: {total_registros} registros eliminados")
        
        return {
            "status": "success",
            "message": f"Todos los registros han sido eliminados exitosamente",
            "registros_eliminados": total_registros
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al eliminar registros: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al eliminar registros: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar registros: {str(e)}")

# ================== ENDPOINTS INDIVIDUALES DE ASISTENCIAS ==================

@app.put("/admin/asistencias/{asistencia_id}")
async def editar_asistencia(asistencia_id: int, body: dict):
    """Edita los campos de una asistencia individual (fecha, hora_entrada, hora_salida, descripcion_entrada, descripcion_salida)"""
    try:
        if not verificar_conexion_db():
            raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")

        # Campos permitidos de editar
        campos_permitidos = {
            "fecha", "hora_entrada", "hora_salida",
            "descripcion_entrada", "descripcion_salida",
            "latitud_entrada", "longitud_entrada",
            "latitud_salida", "longitud_salida"
        }

        updates = {k: v for k, v in body.items() if k in campos_permitidos}
        if not updates:
            raise HTTPException(status_code=400, detail="No hay campos válidos para actualizar")

        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        valores = list(updates.values())
        valores.append(asistencia_id)

        cursor.execute(
            f"UPDATE asistencias SET {set_clause} WHERE id = %s RETURNING id",
            tuple(valores)
        )
        resultado = cursor.fetchone()
        conn.commit()

        if not resultado:
            raise HTTPException(status_code=404, detail="Asistencia no encontrada")

        print(f"✅ Asistencia {asistencia_id} actualizada: {list(updates.keys())}")
        return {"status": "success", "message": "Asistencia actualizada correctamente", "id": asistencia_id}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al editar asistencia {asistencia_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al editar asistencia: {str(e)}")


@app.delete("/admin/asistencias/{asistencia_id}")
async def eliminar_asistencia(asistencia_id: int):
    """Elimina una asistencia individual por su ID"""
    try:
        if not verificar_conexion_db():
            raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")

        # Obtener info de la asistencia para devolver en respuesta
        cursor.execute("SELECT id, usuario_id, fecha FROM asistencias WHERE id = %s", (asistencia_id,))
        asistencia = cursor.fetchone()

        if not asistencia:
            raise HTTPException(status_code=404, detail="Asistencia no encontrada")

        cursor.execute("DELETE FROM asistencias WHERE id = %s", (asistencia_id,))
        conn.commit()

        print(f"🗑️ Asistencia {asistencia_id} eliminada (usuario: {asistencia[1]}, fecha: {asistencia[2]})")
        return {"status": "success", "message": "Asistencia eliminada correctamente", "id": asistencia_id}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al eliminar asistencia {asistencia_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar asistencia: {str(e)}")


@app.delete("/admin/asistencias/all")
async def eliminar_todas_asistencias():
    """Elimina TODAS las asistencias de la base de datos. ¡USO EXTREMO!"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print("🚀 Iniciando eliminación masiva de asistencias...")
        
        # Contar asistencias antes de eliminar (RÁPIDO)
        cursor.execute("SELECT COUNT(*) FROM asistencias")
        total_asistencias = cursor.fetchone()[0]
        
        if total_asistencias == 0:
            return {
                "status": "info",
                "message": "No hay asistencias para eliminar",
                "asistencias_eliminadas": 0
            }
        
        print(f"📊 Eliminando {total_asistencias} asistencias...")
        
        # OPTIMIZACIÓN: Eliminar primero las asistencias (RÁPIDO)
        cursor.execute("DELETE FROM asistencias")
        conn.commit()
        
        print(f"🗑️ ELIMINACIÓN MASIVA COMPLETADA: {total_asistencias} asistencias eliminadas")
        
        # OPTIMIZACIÓN: Eliminar fotos en segundo plano (no bloquear la respuesta)
        try:
            # Obtener lista de archivos en el directorio fotos para eliminar en lote
            fotos_dir = os.path.join(os.getcwd(), "fotos")
            fotos_eliminadas = 0
            
            if os.path.exists(fotos_dir):
                archivos = os.listdir(fotos_dir)
                for archivo in archivos:
                    if archivo.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        try:
                            os.remove(os.path.join(fotos_dir, archivo))
                            fotos_eliminadas += 1
                        except:
                            pass  # Ignorar errores de archivos individuales
                            
                print(f"📸 {fotos_eliminadas} fotos eliminadas del directorio")
        except Exception as e:
            print(f"⚠️ Error al limpiar fotos (no crítico): {e}")
            fotos_eliminadas = 0
        
        return {
            "status": "success",
            "message": f"Todas las asistencias han sido eliminadas exitosamente",
            "asistencias_eliminadas": total_asistencias,
            "fotos_eliminadas": fotos_eliminadas
        }
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL al eliminar asistencias: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general al eliminar asistencias: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar asistencias: {str(e)}")

# Endpoint para verificar estructura de tabla usuarios y CURP
@app.get("/debug/usuarios-estructura")
async def verificar_estructura_usuarios():
    """Endpoint para verificar que la tabla usuarios tenga la columna CURP"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar si la tabla existe
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'usuarios'
        """)
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            return {"error": "La tabla 'usuarios' no existe"}
        
        # Obtener la estructura de la tabla
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' 
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        # Verificar específicamente si existe la columna CURP
        cursor.execute("""
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' 
            AND column_name = 'curp'
        """)
        curp_existe = cursor.fetchone() is not None
        
        # Obtener algunos registros de ejemplo (sin contraseñas)
        cursor.execute("SELECT id, correo, nombre_completo, curp FROM usuarios LIMIT 3")
        registros_ejemplo = cursor.fetchall()
        
        return {
            "tabla_existe": True,
            "curp_columna_existe": curp_existe,
            "columnas": [{"nombre": col[0], "tipo": col[1], "nullable": col[2], "default": col[3]} for col in columnas],
            "total_registros": len(registros_ejemplo),
            "registros_ejemplo": registros_ejemplo
        }
        
    except Exception as e:
        print(f"❌ Error verificando estructura: {e}")
        raise HTTPException(status_code=500, detail=f"Error verificando estructura: {str(e)}")

# ================== ENDPOINTS PARA HISTORIAL ==================

class HistorialCreate(BaseModel):
    usuario_id: int
    tipo: str  # 'entrada', 'salida', 'actividad'
    descripcion: str
    fecha: str = None  # Si no se proporciona, usa la fecha actual
    hora: str = None   # Si no se proporciona, usa la hora actual
    detalles: dict = None  # Para guardar ubicación, foto_url, etc.

@app.post("/historial")
async def crear_historial(historial: HistorialCreate):
    """Crear un nuevo registro en el historial"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (historial.usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Usar fecha y hora actuales si no se proporcionan
        fecha_actual = historial.fecha or datetime.now().date()
        hora_actual = historial.hora or datetime.now().time()
        
        cursor.execute("""
            INSERT INTO historial (usuario_id, tipo, descripcion, fecha, hora, detalles)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            historial.usuario_id,
            historial.tipo,
            historial.descripcion,
            fecha_actual,
            hora_actual,
            historial.detalles
        ))
        
        historial_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Historial creado con ID: {historial_id}")
        return {"id": historial_id, "message": "Historial creado exitosamente"}
        
    except Exception as e:
        print(f"❌ Error creando historial: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error creando historial: {str(e)}")

@app.get("/historial/{usuario_id}")
async def obtener_historial_usuario(
    usuario_id: int,
    fecha_inicio: str = None,
    fecha_fin: str = None,
    tipo: str = None,
    limit: int = 100
):
    """Obtener historial de un usuario con filtros opcionales"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Construir consulta con filtros
        query = """
            SELECT h.id, h.usuario_id, h.tipo, h.descripcion, h.fecha, h.hora, h.detalles, h.creado_en,
                   u.nombre_completo, u.correo, u.curp, u.cargo
            FROM historial h
            JOIN usuarios u ON h.usuario_id = u.id
            WHERE h.usuario_id = %s
        """
        params = [usuario_id]
        
        if fecha_inicio:
            query += " AND h.fecha >= %s"
            params.append(fecha_inicio)
        
        if fecha_fin:
            query += " AND h.fecha <= %s"
            params.append(fecha_fin)
        
        if tipo:
            query += " AND h.tipo = %s"
            params.append(tipo)
        
        query += " ORDER BY h.fecha DESC, h.hora DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        historial = []
        for row in resultados:
            registro = {
                "id": row[0],
                "usuario_id": row[1],
                "tipo": row[2],
                "descripcion": row[3],
                "fecha": row[4].isoformat() if row[4] else None,
                "hora": str(row[5]) if row[5] else None,
                "detalles": row[6],
                "creado_en": row[7].isoformat() if row[7] else None,
                "usuario_nombre": row[8],
                "usuario_correo": row[9],
                "usuario_curp": row[10],
                "usuario_cargo": row[11]
            }
            historial.append(registro)
        
        return {
            "historial": historial,
            "total": len(historial),
            "usuario": {
                "id": usuario[0],
                "nombre": usuario[1]
            }
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial: {str(e)}")

@app.get("/historial")
async def obtener_todos_historiales():
    """Obtener todos los historiales para propósitos de depuración"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute("""
            SELECT h.id, h.usuario_id, h.tipo, h.descripcion, h.fecha, h.hora, h.detalles, h.creado_en,
                   u.nombre_completo, u.correo, u.curp, u.cargo
            FROM historial h
            JOIN usuarios u ON h.usuario_id = u.id
            ORDER BY h.fecha DESC, h.hora DESC 
            LIMIT 50
        """)
        resultados = cursor.fetchall()
        
        historial = []
        for row in resultados:
            registro = {
                "id": row[0],
                "usuario_id": row[1],
                "tipo": row[2],
                "descripcion": row[3],
                "fecha": row[4].isoformat() if row[4] else None,
                "hora": str(row[5]) if row[5] else None,
                "detalles": row[6],
                "creado_en": row[7].isoformat() if row[7] else None,
                "usuario_nombre": row[8],
                "usuario_correo": row[9],
                "usuario_curp": row[10],
                "usuario_cargo": row[11]
            }
            historial.append(registro)
        
        return {
            "historial": historial,
            "total": len(historial)
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo todos los historiales: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo historiales: {str(e)}")

@app.get("/historial/resumen/{usuario_id}")
async def obtener_resumen_historial(usuario_id: int):
    """Obtener resumen del historial de un usuario (estadísticas)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT nombre_completo FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Obtener estadísticas
        cursor.execute("""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(CASE WHEN tipo = 'entrada' THEN 1 END) as entradas,
                COUNT(CASE WHEN tipo = 'salida' THEN 1 END) as salidas,
                COUNT(CASE WHEN tipo = 'actividad' THEN 1 END) as actividades,
                MIN(fecha) as primera_fecha,
                MAX(fecha) as ultima_fecha
            FROM historial 
            WHERE usuario_id = %s
        """, (usuario_id,))
        
        stats = cursor.fetchone()
        
        # Obtener actividad por mes (últimos 12 meses)
        cursor.execute("""
            SELECT 
                DATE_TRUNC('month', fecha) as mes,
                COUNT(*) as cantidad
            FROM historial 
            WHERE usuario_id = %s 
            AND fecha >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', fecha)
            ORDER BY mes DESC
        """, (usuario_id,))
        
        actividad_mensual = cursor.fetchall()
        
        return {
            "usuario_nombre": usuario[0],
            "estadisticas": {
                "total_registros": stats[0] or 0,
                "entradas": stats[1] or 0,
                "salidas": stats[2] or 0,
                "actividades": stats[3] or 0,
                "primera_fecha": stats[4].isoformat() if stats[4] else None,
                "ultima_fecha": stats[5].isoformat() if stats[5] else None
            },
            "actividad_mensual": [
                {
                    "mes": row[0].isoformat() if row[0] else None,
                    "cantidad": row[1]
                }
                for row in actividad_mensual
            ]
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo resumen de historial: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")

# ==================== ENDPOINT DE PRUEBA PARA TÉRMINOS ====================

@app.get("/test/terminos")
async def test_terminos():
    """Endpoint de prueba para verificar que la funcionalidad de términos está activa"""
    return {
        "status": "active",
        "message": "Los endpoints de términos están funcionando correctamente",
        "endpoints": {
            "verificar_terminos": "/usuarios/{user_id}/terminos",
            "aceptar_terminos": "/usuarios/aceptar_terminos",
            "crear_usuario_con_terminos": "/usuarios"
        },
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# ==================== ENDPOINTS DE NOTIFICACIONES ====================

# Define el timezone de CDMX para notificaciones
CDMX_TZ = pytz.timezone("America/Mexico_City")

def obtener_fecha_hora_cdmx_notificaciones():
    """Función de utilidad para obtener fecha y hora actual en zona CDMX para notificaciones"""
    return datetime.now(CDMX_TZ)

@app.post("/notificaciones")
async def crear_notificacion(
    titulo: str = Form(...),
    subtitulo: str = Form(None),
    descripcion: str = Form(None),
    enlace_url: str = Form(None),
    enviada_a_todos: bool = Form(True),
    usuario_ids: str = Form(None),  # JSON string con lista de IDs
    actividad_id: int = Form(None),  # ID de la actividad/reporte vinculado
    motivos_atencion: str = Form(None),  # JSON string con lista de motivos
    requiere_enterado: bool = Form(False),  # pide que cada persona marque 'Enterado'
    archivo: UploadFile = File(None)
):
    """Crear una nueva notificación"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔔 Creando notificación: {titulo}")
        
        # Validaciones básicas
        if len(titulo.strip()) == 0:
            raise HTTPException(status_code=400, detail="El título es obligatorio")
        
        if len(titulo) > 150:
            raise HTTPException(status_code=400, detail="El título no puede exceder 150 caracteres")
        
        if subtitulo and len(subtitulo) > 200:
            raise HTTPException(status_code=400, detail="El subtítulo no puede exceder 200 caracteres")
        
        # Validar usuarios si no es para todos
        usuarios_seleccionados = []
        if not enviada_a_todos:
            if not usuario_ids:
                raise HTTPException(status_code=400, detail="Debe especificar usuarios si no se envía a todos")
            
            try:
                usuarios_seleccionados = json.loads(usuario_ids)
                if not isinstance(usuarios_seleccionados, list) or len(usuarios_seleccionados) == 0:
                    raise HTTPException(status_code=400, detail="Debe seleccionar al menos un usuario")
                
                # Verificar que todos los usuarios existen
                cursor.execute("SELECT id FROM usuarios WHERE id = ANY(%s)", (usuarios_seleccionados,))
                usuarios_existentes = [row[0] for row in cursor.fetchall()]
                
                usuarios_inexistentes = set(usuarios_seleccionados) - set(usuarios_existentes)
                if usuarios_inexistentes:
                    raise HTTPException(status_code=400, detail=f"Usuarios no encontrados: {list(usuarios_inexistentes)}")
                
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Formato de usuarios inválido")
        
        # Procesar archivo si se proporciona
        archivo_bytes = None
        archivo_tipo = None
        archivo_nombre = None
        
        if archivo and archivo.filename:
            print(f"📎 Procesando archivo: {archivo.filename}")
            
            # Validar tipo de archivo
            ext = os.path.splitext(archivo.filename)[1].lower()
            tipos_permitidos = {
                '.jpg': 'imagen', '.jpeg': 'imagen', '.png': 'imagen', '.gif': 'imagen',
                '.pdf': 'pdf',
                '.doc': 'documento', '.docx': 'documento',
                '.xls': 'excel', '.xlsx': 'excel', '.csv': 'excel',
                '.ppt': 'presentacion', '.pptx': 'presentacion',
                '.txt': 'texto', '.zip': 'zip',
                '.mp4': 'video', '.avi': 'video', '.mov': 'video', '.wmv': 'video'
            }
            
            if ext not in tipos_permitidos:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo de archivo no permitido. Formatos válidos: {', '.join(tipos_permitidos.keys())}"
                )
            
            # Leer archivo
            archivo_bytes = await archivo.read()
            archivo_tipo = tipos_permitidos[ext]
            archivo_nombre = archivo.filename
            
            # Validar tamaño (50MB máximo)
            if len(archivo_bytes) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El archivo no debe exceder 50MB")
            
            print(f"📎 Archivo procesado: {archivo_nombre} ({archivo_tipo}, {len(archivo_bytes)} bytes)")
        
        # Procesar motivos de atención si se proporcionan
        motivos_array = None
        if motivos_atencion:
            try:
                motivos_array = json.loads(motivos_atencion)
                if not isinstance(motivos_array, list):
                    raise HTTPException(status_code=400, detail="Los motivos deben ser un array")
                print(f"⚠️ Motivos de atención: {motivos_array}")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Formato de motivos inválido")
        
        # Validar actividad_id si se proporciona (tabla registros)
        if actividad_id:
            cursor.execute("SELECT id FROM registros WHERE id = %s", (actividad_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Actividad con ID {actividad_id} no encontrada en registros")
            print(f"📊 Notificación vinculada a actividad (registro) ID: {actividad_id}")
        
        # Obtener fecha y hora actual en CDMX
        fecha_creacion = obtener_fecha_hora_cdmx_notificaciones()
        fecha_envio = fecha_creacion  # Se considera enviada inmediatamente
        
        # Insertar notificación
        cursor.execute("""
            INSERT INTO notificaciones (
                titulo, subtitulo, descripcion, enlace_url,
                archivo, archivo_tipo, archivo_nombre,
                enviada_a_todos, actividad_id, motivos_atencion,
                fecha_creacion, fecha_envio, requiere_enterado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            titulo, subtitulo, descripcion, enlace_url,
            archivo_bytes, archivo_tipo, archivo_nombre,
            enviada_a_todos, actividad_id, motivos_array,
            fecha_creacion, fecha_envio, bool(requiere_enterado)
        ))
        
        notificacion_id = cursor.fetchone()[0]
        
        # Si no es para todos, insertar relaciones con usuarios
        if not enviada_a_todos and usuarios_seleccionados:
            for usuario_id in usuarios_seleccionados:
                cursor.execute(
                    "INSERT INTO notificacion_usuarios (notificacion_id, usuario_id) VALUES (%s, %s)",
                    (notificacion_id, usuario_id)
                )
            print(f"👥 Notificación asignada a {len(usuarios_seleccionados)} usuarios específicos")
        
        conn.commit()
        
        print(f"✅ Notificación creada exitosamente con ID: {notificacion_id}")

        # Push al teléfono de los destinatarios (en segundo plano, aunque no tengan la app abierta)
        push_info = _push_conteo_destino(notificacion_id)
        _push_lanzar(notificacion_id)
        
        return {
            "id": notificacion_id,
            "status": "success",
            "message": "Notificación creada exitosamente",
            "push": {"disponible": _push_disponible(), **push_info},
            "titulo": titulo,
            "enviada_a_todos": enviada_a_todos,
            "usuarios_destinatarios": len(usuarios_seleccionados) if not enviada_a_todos else "todos",
            "tiene_archivo": archivo_nombre is not None,
            "fecha_envio": fecha_envio.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear notificación: {str(e)}")

@app.get("/notificaciones")
async def listar_notificaciones(limit: int = 50, offset: int = 0, tipo: str = 'todas', busqueda: str = ''):
    """Listar todas las notificaciones
    Args:
        limit: Número máximo de resultados
        offset: Desplazamiento para paginación
        tipo: Filtro por tipo - 'todas', 'individuales', 'grupales'
        busqueda: Texto de búsqueda para filtrar
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"\n{'='*60}")
        print(f"📋 LISTANDO NOTIFICACIONES")
        print(f"   - Limit: {limit}")
        print(f"   - Offset: {offset}")
        print(f"   - Tipo: '{tipo}'")
        print(f"   - Búsqueda: '{busqueda}'")
        print(f"{'='*60}\n")
        
        # Construir filtro WHERE según el tipo
        conditions = []
        params = []
        if tipo == 'individuales':
            conditions.append("n.enviada_a_todos = FALSE")
            print(f"🔍 FILTRO APLICADO: Solo notificaciones individuales (enviada_a_todos = FALSE)")
        elif tipo == 'grupales':
            conditions.append("n.enviada_a_todos = TRUE")
            print(f"🔍 FILTRO APLICADO: Solo notificaciones grupales (enviada_a_todos = TRUE)")
        else:
            print(f"🔍 SIN FILTRO: Mostrando todas las notificaciones")
        
        # Búsqueda por texto
        busqueda_clean = busqueda.strip() if busqueda else ''
        if busqueda_clean:
            if tipo == 'individuales':
                # Buscar en nombre o correo del destinatario
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM notificacion_usuarios nu2
                        LEFT JOIN usuarios u2 ON nu2.usuario_id = u2.id
                        WHERE nu2.notificacion_id = n.id
                        AND (LOWER(u2.nombre_completo) LIKE %s OR LOWER(u2.correo) LIKE %s)
                    )
                """)
                params.extend([f'%{busqueda_clean.lower()}%', f'%{busqueda_clean.lower()}%'])
            else:
                # Buscar en título o subtítulo
                conditions.append("(LOWER(n.titulo) LIKE %s OR LOWER(COALESCE(n.subtitulo, '')) LIKE %s)")
                params.extend([f'%{busqueda_clean.lower()}%', f'%{busqueda_clean.lower()}%'])
        
        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        # Obtener notificaciones con información de destinatarios
        query = f"""
            SELECT 
                n.id, n.titulo, n.subtitulo, n.descripcion, n.enlace_url,
                n.archivo_nombre, n.archivo_tipo, n.enviada_a_todos,
                n.fecha_creacion, n.fecha_envio,
                CASE 
                    WHEN n.enviada_a_todos THEN 'Todos los usuarios'
                    ELSE (
                        SELECT 
                            CASE 
                                WHEN COUNT(*) = 1 THEN MAX(u.nombre_completo) || '|' || MAX(u.correo)
                                ELSE COUNT(*)::text || ' usuarios seleccionados'
                            END
                        FROM notificacion_usuarios nu 
                        LEFT JOIN usuarios u ON nu.usuario_id = u.id
                        WHERE nu.notificacion_id = n.id
                    )
                END as destinatarios_texto,
                COALESCE(n.requiere_enterado, FALSE),
                (SELECT COUNT(*) FROM notificacion_enterados e WHERE e.notificacion_id = n.id),
                (SELECT COUNT(*) FROM notificacion_usuarios nu3 WHERE nu3.notificacion_id = n.id)
            FROM notificaciones n
            {where_clause}
            ORDER BY n.fecha_creacion DESC
            LIMIT %s OFFSET %s
        """
        
        query_params = params + [limit, offset]
        
        print(f"📝 Query SQL:\n{query}\n")
        
        cursor.execute(query, query_params)
        
        resultados = cursor.fetchall()
        
        print(f"✅ Resultados encontrados: {len(resultados)}")
        
        # Debug: Mostrar el valor de enviada_a_todos para cada resultado
        for row in resultados:
            print(f"   - ID: {row[0]}, Título: {row[1]}, enviada_a_todos: {row[7]}")
        
        # Obtener total de notificaciones con el mismo filtro
        count_query = f"SELECT COUNT(*) FROM notificaciones n {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE COALESCE(activo, TRUE) = TRUE")
        usuarios_activos_total = cursor.fetchone()[0]
        
        notificaciones = []
        for row in resultados:
            notificacion = {
                "id": row[0],
                "titulo": row[1],
                "subtitulo": row[2],
                "descripcion": row[3],
                "enlace_url": row[4],
                "archivo_nombre": row[5],
                "archivo_tipo": row[6],
                "enviada_a_todos": row[7],
                "fecha_creacion": row[8].isoformat() if row[8] else None,
                "fecha_envio": row[9].isoformat() if row[9] else None,
                "destinatarios_texto": row[10],
                "requiere_enterado": bool(row[11]),
                "enterados": int(row[12] or 0),
                "destinatarios_total": (usuarios_activos_total if row[7] else int(row[13] or 0))
            }
            notificaciones.append(notificacion)
        
        print(f"\n📦 RESPUESTA FINAL:")
        print(f"   - Notificaciones listadas: {len(notificaciones)}")
        print(f"   - Total en BD (con filtro): {total}")
        print(f"   - Tipo aplicado: '{tipo}'")
        print(f"{'='*60}\n")
        
        return {
            "notificaciones": notificaciones,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
        
    except Exception as e:
        print(f"❌ Error listando notificaciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error al listar notificaciones: {str(e)}")

# ==================== ENDPOINTS ESPECÍFICOS (DEBEN IR ANTES DEL GENÉRICO) ====================

@app.get("/notificaciones/unread_count")
async def obtener_conteo_no_leidas(usuario_id: int):
    """Obtener conteo de notificaciones no leídas para un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
            
        if not usuario_id:
            raise HTTPException(status_code=400, detail="usuario_id es obligatorio")
        
        print(f"📊 Obteniendo conteo de no leídas para usuario {usuario_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Configurar zona horaria para la sesión
        cursor.execute("SET TIME ZONE 'America/Mexico_City'")
        
        # Contar notificaciones visibles sin lectura
        cursor.execute("""
            SELECT COUNT(DISTINCT n.id)
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            LEFT JOIN notificacion_leidos nl ON n.id = nl.notificacion_id AND nl.usuario_id = %s
            WHERE (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
            AND n.fecha_envio IS NOT NULL
            AND nl.id IS NULL
        """, (usuario_id, usuario_id))
        
        count = cursor.fetchone()[0] or 0
        
        print(f"📊 Usuario {usuario_id} tiene {count} notificaciones no leídas")
        
        return {"count": count}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo conteo no leídas: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener conteo: {str(e)}")

@app.get("/notificaciones/list")
async def listar_notificaciones_usuario(
    usuario_id: int,
    filtro: str = "all",  # "unread" | "all"
    limit: int = 200,
    offset: int = 0
):
    """Listar notificaciones para un usuario con filtro de leídas/no leídas"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
            
        if not usuario_id:
            raise HTTPException(status_code=400, detail="usuario_id es obligatorio")
        
        if filtro not in ["unread", "all"]:
            raise HTTPException(status_code=400, detail="filtro debe ser 'unread' o 'all'")
        
        print(f"📋 Listando notificaciones para usuario {usuario_id} (filtro: {filtro})")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Configurar zona horaria para la sesión
        cursor.execute("SET TIME ZONE 'America/Mexico_City'")
        
        # Construir consulta base
        base_query = """
            SELECT DISTINCT n.id, n.titulo, n.subtitulo, n.descripcion, n.enlace_url,
                   n.archivo_nombre, n.archivo_tipo, n.enviada_a_todos,
                   n.fecha_creacion, n.fecha_envio,
                   CASE WHEN nl.id IS NOT NULL THEN TRUE ELSE FALSE END as leida
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            LEFT JOIN notificacion_leidos nl ON n.id = nl.notificacion_id AND nl.usuario_id = %s
            WHERE (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
            AND n.fecha_envio IS NOT NULL
        """
        
        # Agregar filtro si es solo no leídas
        if filtro == "unread":
            base_query += " AND nl.id IS NULL"
        
        # Agregar orden y límites
        query = base_query + """
            ORDER BY n.fecha_envio DESC NULLS LAST, n.fecha_creacion DESC
            LIMIT %s OFFSET %s
        """
        
        cursor.execute(query, (usuario_id, usuario_id, limit, offset))
        resultados = cursor.fetchall()
        
        # Obtener total sin límites para paginación
        count_query = """
            SELECT COUNT(DISTINCT n.id)
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            LEFT JOIN notificacion_leidos nl ON n.id = nl.notificacion_id AND nl.usuario_id = %s
            WHERE (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
            AND n.fecha_envio IS NOT NULL
        """
        
        if filtro == "unread":
            count_query += " AND nl.id IS NULL"
            
        cursor.execute(count_query, (usuario_id, usuario_id))
        total = cursor.fetchone()[0] or 0
        
        # Convertir resultados
        notificaciones = []
        for row in resultados:
            notificacion = {
                "id": row[0],
                "titulo": row[1],
                "subtitulo": row[2],
                "descripcion": row[3],
                "enlace_url": row[4],
                "archivo_nombre": row[5],
                "archivo_tipo": row[6],
                "enviada_a_todos": row[7],
                "fecha_creacion": row[8].isoformat() if row[8] else None,
                "fecha_envio": row[9].isoformat() if row[9] else None,
                "leida": bool(row[10]),
                "tiene_archivo": bool(row[5])
            }
            notificaciones.append(notificacion)
        
        print(f"📋 {len(notificaciones)} notificaciones listadas para usuario {usuario_id}")
        
        return {
            "notificaciones": notificaciones,
            "total": total,
            "filtro": filtro,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error listando notificaciones del usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al listar notificaciones: {str(e)}")

# ==================== ENDPOINTS GENÉRICOS (VAN DESPUÉS DE LOS ESPECÍFICOS) ====================

@app.get("/notificaciones/{notificacion_id}")
async def obtener_notificacion(notificacion_id: int):
    """Obtener detalles de una notificación específica"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔍 Obteniendo notificación {notificacion_id}")
        
        # Obtener notificación
        cursor.execute("""
            SELECT id, titulo, subtitulo, descripcion, enlace_url,
                   archivo_nombre, archivo_tipo, enviada_a_todos,
                   fecha_creacion, fecha_envio
            FROM notificaciones
            WHERE id = %s
        """, (notificacion_id,))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        
        notificacion = {
            "id": resultado[0],
            "titulo": resultado[1],
            "subtitulo": resultado[2],
            "descripcion": resultado[3],
            "enlace_url": resultado[4],
            "archivo_nombre": resultado[5],
            "archivo_tipo": resultado[6],
            "enviada_a_todos": resultado[7],
            "fecha_creacion": resultado[8].isoformat() if resultado[8] else None,
            "fecha_envio": resultado[9].isoformat() if resultado[9] else None
        }
        
        # Si no es para todos, obtener usuarios específicos
        destinatarios = []
        if not resultado[7]:  # Si enviada_a_todos es False
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo
                FROM notificacion_usuarios nu
                JOIN usuarios u ON nu.usuario_id = u.id
                WHERE nu.notificacion_id = %s
                ORDER BY u.nombre_completo
            """, (notificacion_id,))
            
            usuarios = cursor.fetchall()
            destinatarios = [
                {
                    "id": usuario[0],
                    "nombre_completo": usuario[1],
                    "correo": usuario[2]
                }
                for usuario in usuarios
            ]
        
        notificacion["destinatarios"] = destinatarios
        
        print(f"✅ Notificación {notificacion_id} obtenida exitosamente")
        return notificacion
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener notificación: {str(e)}")

@app.post("/notificaciones/{notificacion_id}/leer")
async def marcar_notificacion_leida(notificacion_id: int, data: NotificacionLeer):
    """Marcar una notificación como leída por un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"✅ Marcando notificación {notificacion_id} como leída para usuario {data.usuario_id}")
        
        # Verificar que la notificación existe
        cursor.execute("SELECT id FROM notificaciones WHERE id = %s", (notificacion_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (data.usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar que la notificación es visible para el usuario
        cursor.execute("""
            SELECT 1
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            WHERE n.id = %s 
            AND (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
        """, (notificacion_id, data.usuario_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Notificación no visible para este usuario")
        
        # Configurar zona horaria para la sesión
        cursor.execute("SET TIME ZONE 'America/Mexico_City'")
        
        # Insertar o actualizar el registro de lectura
        cursor.execute("""
            INSERT INTO notificacion_leidos (notificacion_id, usuario_id, device_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (notificacion_id, usuario_id) 
            DO UPDATE SET 
                leida_en = NOW() AT TIME ZONE 'America/Mexico_City',
                device_id = EXCLUDED.device_id
        """, (notificacion_id, data.usuario_id, data.device_id))
        
        conn.commit()
        
        print(f"✅ Notificación {notificacion_id} marcada como leída para usuario {data.usuario_id}")
        
        return {"ok": True}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error marcando notificación como leída: {e}")
        raise HTTPException(status_code=500, detail=f"Error al marcar como leída: {str(e)}")

_MIME_POR_EXT = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".wmv": "video/x-ms-wmv",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".pdf": "application/pdf",
    ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".csv": "text/csv",
    ".ppt": "application/vnd.ms-powerpoint", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain; charset=utf-8", ".zip": "application/zip",
}
_MIME_POR_TIPO = {"imagen": "image/jpeg", "pdf": "application/pdf", "video": "video/mp4", "documento": "application/msword",
                  "excel": "application/vnd.ms-excel", "presentacion": "application/vnd.ms-powerpoint", "texto": "text/plain; charset=utf-8", "zip": "application/zip"}
# Solo estos se muestran dentro del navegador; Word, Excel, PowerPoint y ZIP siempre se descargan
_MOSTRAR_EN_LINEA = ("application/pdf", "image/", "video/", "text/plain")


def _rango_bytes(cabecera, total):
    """Interpreta 'Range: bytes=a-b' (un solo rango). Devuelve (inicio, fin) o None si no hay / es inválido."""
    if not cabecera or not cabecera.lower().startswith("bytes=") or total <= 0:
        return None
    try:
        parte = cabecera.split("=", 1)[1].split(",")[0].strip()
        ini, fin = parte.split("-", 1)
        if ini == "":                                   # últimos N bytes
            n = int(fin)
            if n <= 0:
                return "invalido"
            return max(0, total - n), total - 1
        i = int(ini)
        f = int(fin) if fin != "" else total - 1
        if i >= total or i > f:
            return "invalido"
        return i, min(f, total - 1)
    except Exception:
        return None


@app.get("/notificaciones/{notificacion_id}/archivo")
@app.head("/notificaciones/{notificacion_id}/archivo")
async def descargar_archivo_notificacion(notificacion_id: int, request: Request, safe: bool = False):
    """Archivo adjunto de una notificación. Soporta solicitudes por rangos (206): imprescindible para que
    los videos se reproduzcan en iPhone/Safari y para poder adelantar o retroceder en cualquier navegador."""
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT octet_length(archivo), archivo_tipo, archivo_nombre FROM notificaciones WHERE id = %s AND archivo IS NOT NULL", (notificacion_id,))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Notificación no encontrada o sin archivo adjunto")
        total, tipo, nombre = int(fila[0] or 0), fila[1], fila[2] or f"archivo_{notificacion_id}"

        ext = os.path.splitext(nombre)[1].lower()
        mime = _MIME_POR_EXT.get(ext) or _MIME_POR_TIPO.get(tipo, "application/octet-stream")
        if safe:
            mime = "application/octet-stream"
        try:
            nombre.encode("ascii")
            nombre_seguro = nombre.replace('"', "")
        except UnicodeEncodeError:
            nombre_seguro = f"archivo_{notificacion_id}{ext or '.bin'}"
        from urllib.parse import quote as _q
        en_linea = mime.startswith(_MOSTRAR_EN_LINEA)
        disp = "attachment" if (safe or not en_linea or request.query_params.get("descargar")) else "inline"
        cab = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f"{disp}; filename=\"{nombre_seguro}\"; filename*=UTF-8''{_q(nombre)}",
            "Content-Encoding": "identity",   # evita que la compresión del servidor altere los rangos
            "ETag": f'"n{notificacion_id}-{total}"',
        }

        rango = _rango_bytes(request.headers.get("range"), total)
        if rango == "invalido":
            return Response(status_code=416, headers={**cab, "Content-Range": f"bytes */{total}"})
        if request.method == "HEAD":
            return Response(status_code=200, media_type=mime, headers={**cab, "Content-Length": str(total)})

        ini, fin = rango if rango else (0, total - 1)

        def trozos():
            """Lee el archivo de la base por pedazos de 512 KB (sin cargarlo completo en memoria)."""
            c2 = None
            try:
                c2, k = abrir_conexion_aislada()
                pos = ini
                while pos <= fin:
                    n = min(512 * 1024, fin - pos + 1)
                    k.execute("SELECT substring(archivo FROM %s FOR %s) FROM notificaciones WHERE id = %s", (pos + 1, n, notificacion_id))
                    dato = k.fetchone()
                    if not dato or dato[0] is None:
                        break
                    yield bytes(dato[0])
                    pos += n
            finally:
                try:
                    if c2:
                        c2.close()
                except Exception:
                    pass

        largo = fin - ini + 1
        cab["Content-Length"] = str(largo)
        if rango:
            cab["Content-Range"] = f"bytes {ini}-{fin}/{total}"
            return StreamingResponse(trozos(), status_code=206, media_type=mime, headers=cab)
        return StreamingResponse(trozos(), status_code=200, media_type=mime, headers=cab)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error enviando archivo de notificación {notificacion_id}: {e}")
        raise HTTPException(status_code=500, detail="No se pudo enviar el archivo")
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/notificaciones/{notificacion_id}/archivo/base64")
async def obtener_archivo_base64(notificacion_id: int):
    """Obtener el archivo como base64 para evitar problemas de encoding"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📎 Obteniendo archivo base64 de notificación {notificacion_id}")
        
        # Obtener archivo de la notificación
        cursor.execute("""
            SELECT archivo, archivo_tipo, archivo_nombre
            FROM notificaciones
            WHERE id = %s AND archivo IS NOT NULL
        """, (notificacion_id,))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            raise HTTPException(status_code=404, detail="Notificación no encontrada o sin archivo adjunto")
        
        archivo_bytes = resultado[0]
        archivo_tipo = resultado[1]
        archivo_nombre = resultado[2]
        
        # Convertir a base64
        import base64
        archivo_base64 = base64.b64encode(archivo_bytes).decode('ascii')
        
        # Determinar MIME type
        mime_types = {
            'imagen': 'image/jpeg',
            'pdf': 'application/pdf', 
            'video': 'video/mp4'
        }
        
        mime_type = mime_types.get(archivo_tipo, 'application/octet-stream')
        
        # Crear nombre seguro para el archivo
        try:
            nombre_seguro = archivo_nombre
            # Verificar que no tenga caracteres problemáticos
            nombre_seguro.encode('ascii')
        except:
            # Crear nombre seguro si hay problemas
            import hashlib
            hash_nombre = hashlib.md5(archivo_nombre.encode('utf-8', errors='replace')).hexdigest()[:8]
            ext = archivo_nombre.split('.')[-1] if '.' in archivo_nombre else 'bin'
            ext_segura = ''.join(c for c in ext if c.isalnum())[:10]
            nombre_seguro = f"archivo_{hash_nombre}.{ext_segura}"
        
        print(f"📎 Archivo convertido a base64: {nombre_seguro} ({len(archivo_base64)} chars)")
        
        return {
            "base64": archivo_base64,
            "mime_type": mime_type,
            "archivo_nombre": nombre_seguro,
            "archivo_tipo": archivo_tipo,
            "size": len(archivo_bytes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo archivo base64: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")

@app.get("/notificaciones/{notificacion_id}/archivo/mobile")
async def pagina_carga_archivo_mobile(notificacion_id: int):
    """Página de carga elegante que redirecciona automáticamente al archivo para móviles"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📱 Generando página de carga móvil para archivo de notificación {notificacion_id}")
        
        # Verificar que la notificación existe y tiene archivo
        cursor.execute("""
            SELECT archivo_nombre, archivo_tipo
            FROM notificaciones
            WHERE id = %s AND archivo IS NOT NULL
        """, (notificacion_id,))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            # Página de error elegante
            html_error = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Archivo no encontrado</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        margin: 0;
                        padding: 0;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        text-align: center;
                        padding: 2rem;
                        max-width: 400px;
                    }}
                    .error-icon {{
                        font-size: 4rem;
                        margin-bottom: 1rem;
                        opacity: 0.8;
                    }}
                    .title {{
                        font-size: 1.5rem;
                        margin-bottom: 1rem;
                        font-weight: 600;
                    }}
                    .message {{
                        opacity: 0.9;
                        line-height: 1.6;
                        margin-bottom: 2rem;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">📄❌</div>
                    <div class="title">Archivo no encontrado</div>
                    <div class="message">El archivo que intentas abrir no está disponible o ha sido eliminado.</div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_error, status_code=404)
        
        archivo_nombre = resultado[0]
        archivo_tipo = resultado[1]
        
        # Determinar ícono según tipo de archivo
        icono_archivo = "📄"
        if archivo_tipo:
            if "pdf" in archivo_tipo.lower():
                icono_archivo = "📑"
            elif "image" in archivo_tipo.lower():
                icono_archivo = "🖼️"
            elif "video" in archivo_tipo.lower():
                icono_archivo = "🎥"
            elif "audio" in archivo_tipo.lower():
                icono_archivo = "🎵"
            elif any(word in archivo_tipo.lower() for word in ["word", "doc"]):
                icono_archivo = "📝"
            elif any(word in archivo_tipo.lower() for word in ["excel", "sheet", "csv"]):
                icono_archivo = "📊"
            elif any(word in archivo_tipo.lower() for word in ["powerpoint", "presentation"]):
                icono_archivo = "📽️"
        
        # URL del archivo actual
        archivo_url = f"/notificaciones/{notificacion_id}/archivo"
        
        # Página HTML elegante de carga
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Abriendo archivo...</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    margin: 0;
                    padding: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    overflow: hidden;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    max-width: 400px;
                }}
                .file-icon {{
                    font-size: 4rem;
                    margin-bottom: 1rem;
                    animation: pulse 2s ease-in-out infinite;
                }}
                .title {{
                    font-size: 1.5rem;
                    margin-bottom: 1rem;
                    font-weight: 600;
                }}
                .filename {{
                    background: rgba(255, 255, 255, 0.1);
                    padding: 0.75rem 1.5rem;
                    border-radius: 25px;
                    margin-bottom: 1.5rem;
                    font-weight: 500;
                    word-break: break-word;
                }}
                .loading-text {{
                    opacity: 0.8;
                    margin-bottom: 2rem;
                    line-height: 1.6;
                }}
                .spinner {{
                    width: 40px;
                    height: 40px;
                    border: 3px solid rgba(255, 255, 255, 0.3);
                    border-top: 3px solid white;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                @keyframes pulse {{
                    0%, 100% {{ transform: scale(1); opacity: 1; }}
                    50% {{ transform: scale(1.1); opacity: 0.8; }}
                }}
                .fallback-button {{
                    background: rgba(255, 255, 255, 0.2);
                    border: 2px solid rgba(255, 255, 255, 0.3);
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: 25px;
                    text-decoration: none;
                    display: inline-block;
                    margin-top: 1rem;
                    font-weight: 500;
                    transition: all 0.3s ease;
                }}
                .fallback-button:hover {{
                    background: rgba(255, 255, 255, 0.3);
                    border-color: rgba(255, 255, 255, 0.5);
                    transform: translateY(-2px);
                }}
                .hidden {{
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="file-icon">{icono_archivo}</div>
                <div class="title">Abriendo archivo</div>
                <div class="filename">{archivo_nombre or f'Archivo {notificacion_id}'}</div>
                <div class="loading-text">Preparando para abrir con tu aplicación favorita...</div>
                <div class="spinner"></div>
                
                <!-- Botón de respaldo que aparece después de unos segundos -->
                <a href="{archivo_url}" class="fallback-button hidden" id="fallbackBtn">
                    💾 Descargar manualmente si no se abre automáticamente
                </a>
            </div>

            <script>
                // Función para intentar abrir el archivo automáticamente
                function abrirArchivo() {{
                    console.log('🔄 Intentando abrir archivo automáticamente...');
                    
                    // Crear enlace temporal
                    const link = document.createElement('a');
                    link.href = '{archivo_url}';
                    link.download = '{archivo_nombre or f'archivo_{notificacion_id}'}';
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    
                    // Agregar al DOM y hacer click
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    console.log('✅ Enlace de descarga activado');
                }}
                
                // Mostrar botón de respaldo después de 3 segundos
                setTimeout(() => {{
                    document.getElementById('fallbackBtn').classList.remove('hidden');
                }}, 3000);
                
                // Intentar cerrar la pestaña después de 5 segundos (solo funciona si fue abierta por script)
                setTimeout(() => {{
                    try {{
                        window.close();
                    }} catch (e) {{
                        console.log('No se pudo cerrar la pestaña automáticamente');
                    }}
                }}, 5000);
                
                // Ejecutar la descarga cuando la página cargue
                window.addEventListener('load', () => {{
                    setTimeout(abrirArchivo, 1000);
                }});
                
                // También intentar si el usuario hace click en cualquier lugar
                document.addEventListener('click', abrirArchivo);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generando página de carga móvil: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar solicitud: {str(e)}")

@app.put("/notificaciones/{notificacion_id}")
async def actualizar_notificacion(
    notificacion_id: int,
    titulo: str = Form(...),
    subtitulo: str = Form(None),
    descripcion: str = Form(None),
    enlace_url: str = Form(None),
    enviada_a_todos: bool = Form(True),
    usuario_ids: str = Form(None),
    requiere_enterado: bool = Form(None),
    archivo: UploadFile = File(None)
):
    """Actualizar una notificación existente"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"✏️ Actualizando notificación {notificacion_id}")
        
        # Verificar que la notificación existe
        cursor.execute("SELECT id, archivo_nombre FROM notificaciones WHERE id = %s", (notificacion_id,))
        notificacion_existente = cursor.fetchone()
        
        if not notificacion_existente:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        
        # Validaciones básicas
        if len(titulo.strip()) == 0:
            raise HTTPException(status_code=400, detail="El título es obligatorio")
        
        if len(titulo) > 150:
            raise HTTPException(status_code=400, detail="El título no puede exceder 150 caracteres")
        
        if subtitulo and len(subtitulo) > 200:
            raise HTTPException(status_code=400, detail="El subtítulo no puede exceder 200 caracteres")
        
        # Validar usuarios si no es para todos
        usuarios_seleccionados = []
        if not enviada_a_todos:
            if not usuario_ids:
                raise HTTPException(status_code=400, detail="Debe especificar usuarios si no se envía a todos")
            
            try:
                usuarios_seleccionados = json.loads(usuario_ids)
                if not isinstance(usuarios_seleccionados, list) or len(usuarios_seleccionados) == 0:
                    raise HTTPException(status_code=400, detail="Debe seleccionar al menos un usuario")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Formato de usuario_ids inválido")
        
        # Procesar archivo si se subió uno nuevo
        archivo_bytes = None
        archivo_tipo = None
        archivo_nombre = notificacion_existente[1]  # Mantener el archivo anterior por defecto
        
        if archivo and archivo.filename:
            print(f"📎 Procesando nuevo archivo: {archivo.filename}")
            
            # Validar tipo de archivo
            ext = os.path.splitext(archivo.filename)[1].lower()
            tipos_permitidos = {
                '.jpg': 'imagen', '.jpeg': 'imagen', '.png': 'imagen', '.gif': 'imagen',
                '.pdf': 'pdf',
                '.doc': 'documento', '.docx': 'documento',
                '.xls': 'excel', '.xlsx': 'excel', '.csv': 'excel',
                '.ppt': 'presentacion', '.pptx': 'presentacion',
                '.txt': 'texto', '.zip': 'zip',
                '.mp4': 'video', '.avi': 'video', '.mov': 'video', '.wmv': 'video'
            }
            
            if ext not in tipos_permitidos:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo de archivo no permitido. Formatos válidos: {', '.join(tipos_permitidos.keys())}"
                )
            
            # Leer archivo
            archivo_bytes = await archivo.read()
            archivo_tipo = tipos_permitidos[ext]
            archivo_nombre = archivo.filename
            
            # Validar tamaño (50MB máximo)
            if len(archivo_bytes) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El archivo no debe exceder 50MB")
            
            print(f"📎 Nuevo archivo procesado: {archivo_nombre} ({archivo_tipo}, {len(archivo_bytes)} bytes)")
        
        # Actualizar notificación en la base de datos
        update_query = """
            UPDATE notificaciones 
            SET titulo = %s, subtitulo = %s, descripcion = %s, 
                enlace_url = %s, enviada_a_todos = %s
        """
        update_params = [titulo, subtitulo, descripcion, enlace_url, enviada_a_todos]
        if requiere_enterado is not None:
            update_query += ", requiere_enterado = %s"
            update_params.append(bool(requiere_enterado))
        
        # Agregar campos de archivo si hay nuevo archivo
        if archivo and archivo.filename:
            update_query += ", archivo = %s, archivo_tipo = %s, archivo_nombre = %s"
            update_params.extend([archivo_bytes, archivo_tipo, archivo_nombre])
        
        update_query += " WHERE id = %s"
        update_params.append(notificacion_id)
        
        cursor.execute(update_query, update_params)
        
        # Actualizar destinatarios si cambió la configuración
        if not enviada_a_todos:
            # Eliminar destinatarios anteriores
            cursor.execute("DELETE FROM notificacion_usuarios WHERE notificacion_id = %s", (notificacion_id,))
            
            # Insertar nuevos destinatarios
            for usuario_id in usuarios_seleccionados:
                cursor.execute(
                    "INSERT INTO notificacion_usuarios (notificacion_id, usuario_id) VALUES (%s, %s)",
                    (notificacion_id, usuario_id)
                )
            print(f"👥 Notificación actualizada para {len(usuarios_seleccionados)} usuarios específicos")
        else:
            # Si ahora es para todos, eliminar registros específicos
            cursor.execute("DELETE FROM notificacion_usuarios WHERE notificacion_id = %s", (notificacion_id,))
        
        conn.commit()
        
        print(f"✅ Notificación {notificacion_id} actualizada exitosamente")
        
        return {
            "status": "success",
            "message": "Notificación actualizada exitosamente",
            "id": notificacion_id,
            "titulo": titulo
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error actualizando notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar la notificación: {str(e)}")

@app.delete("/notificaciones/{notificacion_id}")
async def eliminar_notificacion(notificacion_id: int):
    """Eliminar una notificación"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🗑️ Eliminando notificación {notificacion_id}")
        
        # Verificar que la notificación existe
        cursor.execute("SELECT id, titulo FROM notificaciones WHERE id = %s", (notificacion_id,))
        notificacion = cursor.fetchone()
        
        if not notificacion:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        
        # Eliminar notificación (las relaciones se eliminan automáticamente por CASCADE)
        cursor.execute("DELETE FROM notificaciones WHERE id = %s", (notificacion_id,))
        
        conn.commit()
        
        print(f"✅ Notificación {notificacion_id} eliminada exitosamente")
        
        return {
            "status": "success",
            "message": f"Notificación '{notificacion[1]}' eliminada exitosamente",
            "id": notificacion_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar notificación: {str(e)}")

@app.get("/notificaciones/{notificacion_id}/estadisticas")
async def obtener_estadisticas_notificacion(notificacion_id: int):
    """Obtener estadísticas de lectura de una notificación específica"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📊 Obteniendo estadísticas para notificación {notificacion_id}")
        
        # Verificar que la notificación existe
        cursor.execute("""
            SELECT id, titulo, subtitulo, enviada_a_todos, fecha_envio 
            FROM notificaciones 
            WHERE id = %s
        """, (notificacion_id,))
        
        notificacion = cursor.fetchone()
        if not notificacion:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        
        # Determinar el universo de usuarios que pueden ver esta notificación
        if notificacion[3]:  # enviada_a_todos
            # Obtener todos los usuarios (sin filtro de activo)
            cursor.execute("""
                SELECT COUNT(*) as total_usuarios
                FROM usuarios
            """)
            total_usuarios_objetivo = cursor.fetchone()[0]
            
            # Obtener usuarios que han leído la notificación
            cursor.execute("""
                SELECT COUNT(DISTINCT nl.usuario_id) as usuarios_leido
                FROM notificacion_leidos nl
                INNER JOIN usuarios u ON nl.usuario_id = u.id
                WHERE nl.notificacion_id = %s
            """, (notificacion_id,))
            usuarios_leido = cursor.fetchone()[0]
            
        else:  # enviada a usuarios específicos
            # Obtener usuarios específicos destinatarios
            cursor.execute("""
                SELECT COUNT(*) as total_usuarios
                FROM notificacion_usuarios nu
                INNER JOIN usuarios u ON nu.usuario_id = u.id
                WHERE nu.notificacion_id = %s
            """, (notificacion_id,))
            total_usuarios_objetivo = cursor.fetchone()[0]
            
            # Obtener usuarios específicos que han leído la notificación
            cursor.execute("""
                SELECT COUNT(DISTINCT nl.usuario_id) as usuarios_leido
                FROM notificacion_leidos nl
                INNER JOIN notificacion_usuarios nu ON nl.usuario_id = nu.usuario_id
                INNER JOIN usuarios u ON nl.usuario_id = u.id
                WHERE nl.notificacion_id = %s 
                AND nu.notificacion_id = %s
            """, (notificacion_id, notificacion_id))
            usuarios_leido = cursor.fetchone()[0]
        
        usuarios_no_leido = total_usuarios_objetivo - usuarios_leido
        
        # Calcular porcentajes
        porcentaje_leido = round((usuarios_leido / total_usuarios_objetivo * 100), 2) if total_usuarios_objetivo > 0 else 0
        porcentaje_no_leido = round((usuarios_no_leido / total_usuarios_objetivo * 100), 2) if total_usuarios_objetivo > 0 else 0
        
        # Obtener detalles de usuarios que han leído (máximo 20 para no sobrecargar)
        if notificacion[3]:  # enviada_a_todos
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo, u.curp, nl.leida_en
                FROM notificacion_leidos nl
                INNER JOIN usuarios u ON nl.usuario_id = u.id
                WHERE nl.notificacion_id = %s
                ORDER BY nl.leida_en DESC
                LIMIT 20
            """, (notificacion_id,))
        else:  # usuarios específicos
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo, u.curp, nl.leida_en
                FROM notificacion_leidos nl
                INNER JOIN notificacion_usuarios nu ON nl.usuario_id = nu.usuario_id
                INNER JOIN usuarios u ON nl.usuario_id = u.id
                WHERE nl.notificacion_id = %s 
                AND nu.notificacion_id = %s
                ORDER BY nl.leida_en DESC
                LIMIT 20
            """, (notificacion_id, notificacion_id))
        
        usuarios_que_leyeron = []
        for fila in cursor.fetchall():
            usuarios_que_leyeron.append({
                "id": fila[0],
                "nombre_completo": fila[1],
                "correo": fila[2],
                "curp": fila[3],
                "leida_en": fila[4].isoformat() if fila[4] else None
            })
        
        # Obtener detalles de usuarios que NO han leído (máximo 20 para no sobrecargar)
        if notificacion[3]:  # enviada_a_todos
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo, u.curp
                FROM usuarios u
                WHERE u.id NOT IN (
                    SELECT nl.usuario_id 
                    FROM notificacion_leidos nl 
                    WHERE nl.notificacion_id = %s
                )
                ORDER BY u.nombre_completo
                LIMIT 20
            """, (notificacion_id,))
        else:  # usuarios específicos
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo, u.curp
                FROM notificacion_usuarios nu
                INNER JOIN usuarios u ON nu.usuario_id = u.id
                WHERE nu.notificacion_id = %s 
                AND u.id NOT IN (
                    SELECT nl.usuario_id 
                    FROM notificacion_leidos nl 
                    WHERE nl.notificacion_id = %s
                )
                ORDER BY u.nombre_completo
                LIMIT 20
            """, (notificacion_id, notificacion_id))
        
        usuarios_que_no_leyeron = []
        for fila in cursor.fetchall():
            usuarios_que_no_leyeron.append({
                "id": fila[0],
                "nombre_completo": fila[1],
                "correo": fila[2],
                "curp": fila[3]
            })
        
        estadisticas = {
            "notificacion_id": notificacion_id,
            "titulo": notificacion[1],
            "subtitulo": notificacion[2],
            "enviada_a_todos": notificacion[3],
            "fecha_envio": notificacion[4].isoformat() if notificacion[4] else None,
            "resumen": {
                "total_usuarios_objetivo": total_usuarios_objetivo,
                "usuarios_leido": usuarios_leido,
                "usuarios_no_leido": usuarios_no_leido,
                "porcentaje_leido": porcentaje_leido,
                "porcentaje_no_leido": porcentaje_no_leido
            },
            "usuarios_que_leyeron": usuarios_que_leyeron,
            "usuarios_que_no_leyeron": usuarios_que_no_leyeron,
            "nota": "Solo se muestran los primeros 20 usuarios de cada categoría"
        }
        
        print(f"✅ Estadísticas obtenidas: {usuarios_leido}/{total_usuarios_objetivo} usuarios han leído la notificación")
        
        return estadisticas
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas de notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

# ENDPOINT OBSOLETO - COMENTADO PARA USAR EL MEJORADO CON DATOS DE ACTIVIDAD
# @app.get("/notificaciones/usuario/{usuario_id}")
# async def obtener_notificaciones_usuario(usuario_id: int, limit: int = 20, offset: int = 0):
#     """Obtener notificaciones específicas de un usuario (para PWASUPER)"""
#     try:
#         if not conn:
#             raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
#         
#         print(f"📱 Obteniendo notificaciones para usuario {usuario_id} (limit: {limit}, offset: {offset})")
#         
#         # Verificar que el usuario existe
#         cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (usuario_id,))
#         usuario = cursor.fetchone()
#         
#         if not usuario:
#             raise HTTPException(status_code=404, detail="Usuario no encontrado")
#         
#         # Obtener notificaciones del usuario (enviadas a todos + específicas del usuario)
#         cursor.execute("""
#             SELECT DISTINCT n.id, n.titulo, n.subtitulo, n.descripcion, n.enlace_url,
#                    n.archivo_nombre, n.archivo_tipo, n.enviada_a_todos,
#                    n.fecha_creacion, n.fecha_envio
#             FROM notificaciones n
#             LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
#             WHERE n.enviada_a_todos = TRUE 
#                OR nu.usuario_id = %s
#             ORDER BY n.fecha_creacion DESC
#             LIMIT %s OFFSET %s
#         """, (usuario_id, limit, offset))
#         
#         resultados = cursor.fetchall()
#         
#         # Obtener total de notificaciones del usuario
#         cursor.execute("""
#             SELECT COUNT(DISTINCT n.id)
#             FROM notificaciones n
#             LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
#             WHERE n.enviada_a_todos = TRUE 
#                OR nu.usuario_id = %s
#         """, (usuario_id,))
#         
#         total = cursor.fetchone()[0]
#         
#         notificaciones = []
#         for resultado in resultados:
#             notificacion = {
#                 "id": resultado[0],
#                 "titulo": resultado[1],
#                 "subtitulo": resultado[2],
#                 "descripcion": resultado[3],
#                 "enlace_url": resultado[4],
#                 "archivo_nombre": resultado[5],
#                 "archivo_tipo": resultado[6],
#                 "enviada_a_todos": resultado[7],
#                 "fecha_creacion": resultado[8].isoformat() if resultado[8] else None,
#                 "fecha_envio": resultado[9].isoformat() if resultado[9] else None,
#                 "tiene_archivo": bool(resultado[5])
#             }
#             notificaciones.append(notificacion)
#         
#         print(f"✅ {len(notificaciones)} notificaciones obtenidas para usuario {usuario[1]}")
#         
#         return {
#             "usuario": {
#                 "id": usuario[0],
#                 "nombre_completo": usuario[1]
#             },
#             "notificaciones": notificaciones,
#             "total": total,
#             "limit": limit,
#             "offset": offset
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error obteniendo notificaciones del usuario: {e}")
#         raise HTTPException(status_code=500, detail=f"Error al obtener notificaciones del usuario: {str(e)}")

# ==================== NUEVOS ENDPOINTS DE NOTIFICACIONES LEÍDAS/NO LEÍDAS ====================

# Función para crear tabla de notificación_leidos si no existe
def crear_tabla_notificacion_leidos():
    """Crear tabla notificacion_leidos si no existe"""
    try:
        if conn and cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notificacion_leidos (
                    id SERIAL PRIMARY KEY,
                    notificacion_id INTEGER NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
                    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                    leida_en TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'America/Mexico_City'),
                    device_id TEXT,
                    UNIQUE (notificacion_id, usuario_id)
                )
            """)
            
            # Crear índices si no existen
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_notif_leidos_usuario 
                ON notificacion_leidos(usuario_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_notif_leidos_notif 
                ON notificacion_leidos(notificacion_id)
            """)
            
            conn.commit()
            print("✅ Tabla notificacion_leidos verificada/creada correctamente")
            
    except Exception as e:
        print(f"❌ Error creando tabla notificacion_leidos: {e}")
        if conn:
            conn.rollback()

# Crear la tabla al inicializar
crear_tabla_notificacion_leidos()

# Endpoint mejorado para obtener notificaciones de usuario (compatibilidad con PWASUPER)
@app.get("/notificaciones/usuario/{usuario_id}")
async def obtener_notificaciones_usuario_mejorado(
    usuario_id: int, 
    limit: int = 20, 
    offset: int = 0
):
    """Obtener notificaciones específicas de un usuario con estado de lectura (compatibilidad con PWASUPER)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📱 Obteniendo notificaciones para usuario {usuario_id} (limit: {limit}, offset: {offset})")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Configurar zona horaria para la sesión
        cursor.execute("SET TIME ZONE 'America/Mexico_City'")
        
        # Obtener notificaciones del usuario con estado de lectura y datos de actividad si existe
        cursor.execute("""
            SELECT DISTINCT n.id, n.titulo, n.subtitulo, n.descripcion, n.enlace_url,
                   n.archivo_nombre, n.archivo_tipo, n.enviada_a_todos,
                   n.fecha_creacion, n.fecha_envio,
                   CASE WHEN nl.id IS NOT NULL THEN TRUE ELSE FALSE END as leida,
                   n.actividad_id, n.motivos_atencion,
                   r.tipo_actividad, r.categoria_actividad, r.categoria_actividad_otro,
                   r.foto_url, r.fecha_hora as actividad_fecha, r.descripcion as actividad_descripcion,
                   r.latitud, r.longitud,
                   COALESCE(n.requiere_enterado, FALSE) AS requiere_enterado, ne.enterado_at
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            LEFT JOIN notificacion_leidos nl ON n.id = nl.notificacion_id AND nl.usuario_id = %s
            LEFT JOIN notificacion_enterados ne ON ne.notificacion_id = n.id AND ne.usuario_id = %s
            LEFT JOIN registros r ON n.actividad_id = r.id
            WHERE (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
            AND n.fecha_envio IS NOT NULL
            ORDER BY n.fecha_envio DESC NULLS LAST, n.fecha_creacion DESC
            LIMIT %s OFFSET %s
        """, (usuario_id, usuario_id, usuario_id, limit, offset))
        
        resultados = cursor.fetchall()
        
        # Obtener total de notificaciones del usuario
        cursor.execute("""
            SELECT COUNT(DISTINCT n.id)
            FROM notificaciones n
            LEFT JOIN notificacion_usuarios nu ON n.id = nu.notificacion_id
            WHERE (n.enviada_a_todos = TRUE OR nu.usuario_id = %s)
            AND n.fecha_envio IS NOT NULL
        """, (usuario_id,))
        
        total = cursor.fetchone()[0] or 0
        
        notificaciones = []
        for resultado in resultados:
            # Construir objeto de actividad si existe
            actividad_data = None
            if resultado[11]:  # Si actividad_id existe
                # Formatear fecha de actividad con zona horaria CDMX
                fecha_actividad_iso = None
                if resultado[17]:  # actividad_fecha
                    fecha_actividad_iso = resultado[17].isoformat() + "-06:00"
                
                actividad_data = {
                    "id": resultado[11],  # actividad_id
                    "tipo_actividad": resultado[13],  # tipo_actividad
                    "categoria_actividad": resultado[14],  # categoria_actividad
                    "categoria_actividad_otro": resultado[15],  # categoria_actividad_otro
                    "foto_url": resultado[16],  # foto_url
                    "fecha": fecha_actividad_iso,  # actividad_fecha
                    "descripcion": resultado[18],  # actividad_descripcion
                    "latitud": float(resultado[19]) if resultado[19] is not None else None,
                    "longitud": float(resultado[20]) if resultado[20] is not None else None
                }
            
            notificacion = {
                "id": resultado[0],
                "titulo": resultado[1],
                "subtitulo": resultado[2],
                "descripcion": resultado[3],
                "enlace_url": resultado[4],
                "archivo_nombre": resultado[5],
                "archivo_tipo": resultado[6],
                "enviada_a_todos": resultado[7],
                "fecha_creacion": resultado[8].isoformat() if resultado[8] else None,
                "fecha_envio": resultado[9].isoformat() if resultado[9] else None,
                "tiene_archivo": bool(resultado[5]),
                "leida": bool(resultado[10]),  # Estado de lectura
                "actividad": actividad_data,  # Datos de la actividad vinculada
                "motivos_atencion": resultado[12],  # Motivos de atención
                "requiere_enterado": bool(resultado[21]),
                "enterado": resultado[22] is not None,
                "enterado_en": resultado[22].isoformat() if resultado[22] else None
            }
            notificaciones.append(notificacion)
        
        print(f"✅ {len(notificaciones)} notificaciones obtenidas para usuario {usuario[1]} (con estado de lectura)")
        
        return {
            "usuario": {
                "id": usuario[0],
                "nombre_completo": usuario[1]
            },
            "notificaciones": notificaciones,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo notificaciones del usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener notificaciones del usuario: {str(e)}")

# ==================== FIN ENDPOINTS DE NOTIFICACIONES LEÍDAS/NO LEÍDAS ====================

# ==================== ENDPOINTS PARA GESTIÓN DE ROLES Y PERMISOS ====================

class UsuarioRolUpdate(BaseModel):
    rol: str  # 'admin' o 'user'

class UsuarioPasswordUpdate(BaseModel):
    nueva_contrasena: str

@app.put("/usuarios/{user_id}/rol")
async def cambiar_rol_usuario(user_id: int, rol_data: UsuarioRolUpdate):
    """Cambiar el rol de un usuario (admin/user)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔄 Cambiando rol del usuario {user_id} a {rol_data.rol}")
        
        # Validar rol
        if rol_data.rol not in ['admin', 'user']:
            raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'user'")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar si la columna 'rol' existe, si no, agregarla
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """)
        
        if not cursor.fetchone():
            print("📝 Agregando columna 'rol' a la tabla usuarios")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(10) DEFAULT 'user'")
            conn.commit()
        
        # Actualizar rol
        cursor.execute("UPDATE usuarios SET rol = %s WHERE id = %s", (rol_data.rol, user_id))
        conn.commit()
        
        print(f"✅ Rol del usuario {usuario[1]} cambiado a {rol_data.rol}")
        return {"mensaje": f"Rol actualizado a {rol_data.rol}", "usuario_id": user_id}
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar rol: {str(e)}")

@app.put("/usuarios/{user_id}/password")
async def cambiar_contrasena_usuario(user_id: int, password_data: UsuarioPasswordUpdate):
    """Cambiar la contraseña de un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔄 Cambiando contraseña del usuario {user_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Actualizar contraseña (sin encriptar, como en el resto del sistema)
        cursor.execute("UPDATE usuarios SET contrasena = %s WHERE id = %s", (password_data.nueva_contrasena, user_id))
        conn.commit()
        
        print(f"✅ Contraseña del usuario {usuario[1]} actualizada")
        return {"mensaje": "Contraseña actualizada exitosamente", "usuario_id": user_id}
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar contraseña: {str(e)}")

# Modelo para actualizar cargo
class CargoUpdate(BaseModel):
    cargo: str

@app.put("/usuarios/{user_id}/cargo")
async def actualizar_cargo_usuario(user_id: int, cargo_data: CargoUpdate):
    """Actualizar el cargo de un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🔄 Actualizando cargo del usuario {user_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Validar que el cargo no esté vacío
        cargo = cargo_data.cargo.strip().upper()
        if not cargo:
            raise HTTPException(status_code=400, detail="El cargo no puede estar vacío")
        
        # Actualizar cargo
        cursor.execute("UPDATE usuarios SET cargo = %s WHERE id = %s", (cargo, user_id))
        conn.commit()
        
        print(f"✅ Cargo del usuario {usuario[1]} actualizado a: {cargo}")
        return {"success": True, "mensaje": "Cargo actualizado exitosamente", "usuario_id": user_id, "cargo": cargo}
        
    except HTTPException:
        raise
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error de PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error general: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar cargo: {str(e)}")

@app.get("/usuarios/estadisticas")
async def obtener_estadisticas_usuarios():
    """Obtener estadísticas de usuarios del sistema"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print("📊 Obteniendo estadísticas de usuarios...")
        
        # Verificar si la columna 'rol' existe
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """)
        
        tiene_columna_rol = bool(cursor.fetchone())
        
        if tiene_columna_rol:
            # Contar usuarios por rol
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN rol = 'admin' THEN 1 END) as admins,
                    COUNT(CASE WHEN rol = 'user' OR rol IS NULL THEN 1 END) as users
                FROM usuarios
            """)
            resultado = cursor.fetchone()
            total, admins, users = resultado
        else:
            # Si no existe la columna rol, todos son users
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            total = cursor.fetchone()[0]
            admins = 0
            users = total
        
        # Contar usuarios por cargo (top 5)
        cursor.execute("""
            SELECT cargo, COUNT(*) as cantidad 
            FROM usuarios 
            WHERE cargo IS NOT NULL AND cargo != ''
            GROUP BY cargo 
            ORDER BY cantidad DESC 
            LIMIT 5
        """)
        cargos = [{"cargo": row[0], "cantidad": row[1]} for row in cursor.fetchall()]
        
        # Obtener usuarios recientes (últimos 10)
        cursor.execute("""
            SELECT id, nombre_completo, correo, cargo, rol
            FROM usuarios 
            ORDER BY id DESC 
            LIMIT 10
        """)
        usuarios_recientes = []
        for row in cursor.fetchall():
            usuarios_recientes.append({
                "id": row[0],
                "nombre_completo": row[1],
                "correo": row[2],
                "cargo": row[3],
                "rol": row[4] if tiene_columna_rol and row[4] else 'user'
            })
        
        estadisticas = {
            "total_usuarios": total,
            "administradores": admins,
            "usuarios_normales": users,
            "cargos_populares": cargos,
            "usuarios_recientes": usuarios_recientes,
            "sistema_roles_activo": tiene_columna_rol
        }
        
        print(f"✅ Estadísticas obtenidas: {total} usuarios total")
        return estadisticas
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

@app.get("/usuarios/buscar")
async def buscar_usuarios(request: Request, correo: Optional[str] = None, nombre: Optional[str] = None, 
                         curp: Optional[str] = None, cargo: Optional[str] = None):
    _pwd_ok = _admin_jwt_valido(request)
    """Buscar usuarios por diferentes criterios con OR"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Construir consulta dinámica con OR
        condiciones = []
        parametros = []
        
        if correo:
            condiciones.append("correo ILIKE %s")
            parametros.append(f"%{correo}%")
        
        if nombre:
            condiciones.append("nombre_completo ILIKE %s")
            parametros.append(f"%{nombre}%")
        
        if curp:
            condiciones.append("curp ILIKE %s")
            parametros.append(f"%{curp.upper()}%")
        
        if cargo:
            condiciones.append("cargo ILIKE %s")
            parametros.append(f"%{cargo}%")
        
        if not condiciones:
            raise HTTPException(status_code=400, detail="Debe proporcionar al menos un criterio de búsqueda")
        
        # Verificar si existe columna rol
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'rol'
        """)
        tiene_rol = bool(cursor.fetchone())
        
        # CAMBIO CRÍTICO: Usar OR en lugar de AND para buscar en cualquier campo
        consulta = f"""
            SELECT id, correo, nombre_completo, cargo, supervisor, curp, telefono, contrasena
            {'rol' if tiene_rol else ''}
            FROM usuarios 
            WHERE {' OR '.join(condiciones)}
            ORDER BY id DESC
            LIMIT 100
        """
        
        if tiene_rol:
            consulta = consulta.replace("contrasena\n", "contrasena, ")
        
        print(f"🔍 Buscando usuarios con consulta: {consulta}")
        print(f"📝 Parámetros: {parametros}")
        cursor.execute(consulta, parametros)
        
        resultados = cursor.fetchall()
        usuarios = []
        
        for row in resultados:
            usuario = {
                "id": row[0],
                "correo": row[1],
                "nombre_completo": row[2],
                "cargo": row[3],
                "supervisor": row[4],
                "curp": row[5],
                "telefono": row[6],
                "contrasena": (row[7] if _pwd_ok else None),
                "rol": row[8] if tiene_rol and len(row) > 8 else 'user'
            }
            usuarios.append(usuario)
        
        print(f"✅ Búsqueda completada: {len(usuarios)} usuarios encontrados")
        if len(usuarios) > 0:
            print(f"   Primer resultado: {usuarios[0]['nombre_completo']} - CURP: {usuarios[0].get('curp', 'N/A')}")
        return {"usuarios": usuarios}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")

# ==================== MODELOS PARA ADMINISTRADORES ====================

# Permisos por defecto para cada rol
PERMISOS_ADMIN_DEFAULT = {
    "visor": True,
    "asistencia": True,
    "registros": True,
    "registros_acciones": True,
    "usuarios": True,
    "usuarios_acciones": True,
    "historiales": True,
    "notificaciones": True,
    "notificaciones_crear": True,
    "notificaciones_acciones": True,
    "permisos": True,
    "configuracion": True,
    "reportes": True,
    "manuales": True
}

PERMISOS_USER_DEFAULT = {
    "visor": False,
    "asistencia": False,
    "registros": False,
    "registros_acciones": False,
    "usuarios": False,
    "usuarios_acciones": False,
    "historiales": False,
    "notificaciones": False,
    "notificaciones_crear": False,
    "notificaciones_acciones": False,
    "permisos": False,
    "configuracion": False,
    "reportes": False,
    "manuales": False
}

class AdminUserCreate(BaseModel):
    username: str
    password: str
    rol: str = 'user'  # admin o user
    permisos: Optional[dict] = None  # Permisos personalizados
    es_territorial: bool = False  # Si es usuario territorial
    territorio: Optional[str] = None  # Territorio asignado (si es_territorial = True)
    nombre_completo: Optional[str] = None  # Nombre completo del usuario
    curp: Optional[str] = None  # CURP del usuario
    cargo: Optional[str] = None  # Cargo del usuario

class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    permisos: Optional[dict] = None  # Permisos personalizados
    activo: Optional[bool] = None  # Estado activo/inactivo
    es_territorial: Optional[bool] = None  # Si es usuario territorial
    territorio: Optional[str] = None  # Territorio asignado
    nombre_completo: Optional[str] = None  # Nombre completo del usuario
    curp: Optional[str] = None  # CURP del usuario
    cargo: Optional[str] = None  # Cargo del usuario

# ==================== ENDPOINTS PARA GESTIÓN DE USUARIOS ADMINISTRATIVOS ====================

@app.get("/admin/usuarios")
async def obtener_usuarios_admin():
    """Obtener todos los usuarios administrativos de la tabla admin_users"""
    try:
        print("🔄 Obteniendo usuarios administrativos...")
        
        # Verificar conexión a la base de datos
        if not conn or not cursor:
            raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
        
        # Obtener todos los usuarios administrativos incluyendo permisos, estado activo, es_territorial y territorio
        cursor.execute("""
            SELECT id, username, rol, permisos, activo, es_territorial, territorio, nombre_completo, curp, cargo
            FROM admin_users 
            ORDER BY id ASC
        """)
        
        rows = cursor.fetchall()
        usuarios = []
        
        for row in rows:
            # Parsear permisos JSON o usar defaults
            permisos_str = row[3]
            if permisos_str:
                try:
                    permisos = json.loads(permisos_str)
                except:
                    permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
            else:
                permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
            
            # Estado activo (por defecto True si es NULL)
            activo = row[4] if row[4] is not None else True
            
            # Es territorial y territorio
            es_territorial = row[5] if row[5] is not None else False
            territorio = row[6]
            
            usuario = {
                "id": row[0],
                "username": row[1],
                "rol": row[2],
                "permisos": permisos,
                "activo": activo,
                "es_territorial": es_territorial,
                "territorio": territorio,
                "nombre_completo": row[7] or '',
                "curp": row[8] or '',
                "cargo": row[9] or ''
            }
            usuarios.append(usuario)
        
        print(f"✅ {len(usuarios)} usuarios administrativos obtenidos")
        return {"usuarios": usuarios}
        
    except Exception as e:
        print(f"❌ Error obteniendo usuarios administrativos: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios: {str(e)}")

@app.post("/admin/usuarios")
async def crear_usuario_admin(usuario: AdminUserCreate):
    """Crear un nuevo usuario administrativo"""
    try:
        print(f"🔄 Creando usuario administrativo: {usuario.username}")
        
        # Verificar conexión
        if not conn or not cursor:
            raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
        
        # Verificar que el username no existe
        cursor.execute("SELECT id FROM admin_users WHERE username = %s", (usuario.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="El nombre de usuario ya existe")
        
        # Validar rol
        if usuario.rol not in ['admin', 'user']:
            raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'")
        
        # Hashear la contraseña
        hashed_password = pwd_context.hash(usuario.password)
        
        # Determinar permisos (usar los enviados o los por defecto según rol)
        if usuario.permisos:
            permisos_json = json.dumps(usuario.permisos)
        else:
            permisos_default = PERMISOS_ADMIN_DEFAULT if usuario.rol == 'admin' else PERMISOS_USER_DEFAULT
            permisos_json = json.dumps(permisos_default)
        
        # Validar territorio si es territorial
        territorio_valor = None
        if usuario.es_territorial:
            if not usuario.territorio:
                raise HTTPException(status_code=400, detail="Si es territorial, debe especificar un territorio")
            if usuario.territorio not in TERRITORIOS_SEMBRANDO_VIDA:
                raise HTTPException(status_code=400, detail="Territorio inválido. Debe ser uno de los territorios de Sembrando Vida.")
            territorio_valor = usuario.territorio
        
        # Preparar los nuevos campos (normalizar a MAYÚSCULAS SIN TILDES)
        nombre_completo_valor = normalizar_mayus_sin_tildes(usuario.nombre_completo)
        curp_valor = normalizar_mayus_sin_tildes(usuario.curp)
        cargo_valor = normalizar_mayus_sin_tildes(usuario.cargo)
        
        # Insertar nuevo usuario con permisos, es_territorial y territorio
        cursor.execute("""
            INSERT INTO admin_users (username, password, rol, permisos, activo, es_territorial, territorio, nombre_completo, curp, cargo, password_enc) 
            VALUES (%s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s) 
            RETURNING id
        """, (usuario.username, hashed_password, usuario.rol, permisos_json, usuario.es_territorial, territorio_valor, nombre_completo_valor, curp_valor, cargo_valor, _cifrar_pwd(usuario.password)))
        
        nuevo_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Usuario administrativo creado con ID: {nuevo_id}" + (f" (territorial: {territorio_valor})" if usuario.es_territorial else ""))
        return {
            "message": "Usuario administrativo creado exitosamente",
            "id": nuevo_id,
            "username": usuario.username,
            "rol": usuario.rol,
            "permisos": json.loads(permisos_json),
            "activo": True,
            "es_territorial": usuario.es_territorial,
            "territorio": territorio_valor,
            "nombre_completo": nombre_completo_valor or '',
            "curp": curp_valor or '',
            "cargo": cargo_valor or ''
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando usuario administrativo: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

@app.get("/admin/usuarios/{user_id}")
async def obtener_usuario_admin(user_id: int):
    """Obtener información de un usuario administrativo específico"""
    try:
        print(f"🔄 Obteniendo usuario administrativo ID: {user_id}")
        
        cursor.execute("""
            SELECT id, username, rol, permisos, activo, es_territorial, territorio, nombre_completo, curp, cargo
            FROM admin_users 
            WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        # Parsear permisos
        permisos_str = row[3]
        if permisos_str:
            try:
                permisos = json.loads(permisos_str)
            except:
                permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
        else:
            permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
        
        # Estado activo (por defecto True si es NULL)
        activo = row[4] if row[4] is not None else True
        
        # Es territorial y territorio
        es_territorial = row[5] if row[5] is not None else False
        territorio = row[6]
        
        usuario = {
            "id": row[0],
            "username": row[1],
            "rol": row[2],
            "permisos": permisos,
            "activo": activo,
            "es_territorial": es_territorial,
            "territorio": territorio,
            "nombre_completo": row[7] or '',
            "curp": row[8] or '',
            "cargo": row[9] or ''
        }
        
        print(f"✅ Usuario administrativo obtenido: {usuario['username']}")
        return usuario
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo usuario administrativo: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuario: {str(e)}")

@app.put("/admin/usuarios/{user_id}")
async def actualizar_usuario_admin(user_id: int, usuario: AdminUserUpdate):
    """Actualizar información de un usuario administrativo"""
    try:
        print(f"🔄 Actualizando usuario administrativo ID: {user_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM admin_users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        # Preparar campos a actualizar
        campos_actualizar = []
        valores = []
        
        if usuario.username:
            # Verificar que el nuevo username no existe (excepto el actual)
            cursor.execute("SELECT id FROM admin_users WHERE username = %s AND id != %s", 
                          (usuario.username, user_id))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="El nombre de usuario ya existe")
            campos_actualizar.append("username = %s")
            valores.append(usuario.username)
        
        if usuario.password:
            hashed_password = pwd_context.hash(usuario.password)
            campos_actualizar.append("password = %s")
            valores.append(hashed_password)
            campos_actualizar.append("password_enc = %s")
            valores.append(_cifrar_pwd(usuario.password))
        
        if usuario.rol:
            if usuario.rol not in ['admin', 'user']:
                raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'")
            campos_actualizar.append("rol = %s")
            valores.append(usuario.rol)
        
        if usuario.permisos is not None:
            permisos_json = json.dumps(usuario.permisos)
            campos_actualizar.append("permisos = %s")
            valores.append(permisos_json)
        
        # Campo activo (puede ser True o False)
        if usuario.activo is not None:
            campos_actualizar.append("activo = %s")
            valores.append(usuario.activo)
        
        # Campo es_territorial
        if usuario.es_territorial is not None:
            campos_actualizar.append("es_territorial = %s")
            valores.append(usuario.es_territorial)
            
            # Si se desactiva territorial, limpiar el territorio
            if not usuario.es_territorial:
                campos_actualizar.append("territorio = %s")
                valores.append(None)
        
        # Campo territorio (solo si es territorial)
        if usuario.territorio is not None:
            if usuario.territorio and usuario.territorio not in TERRITORIOS_SEMBRANDO_VIDA:
                raise HTTPException(status_code=400, detail="Territorio inválido. Debe ser uno de los territorios de Sembrando Vida.")
            campos_actualizar.append("territorio = %s")
            valores.append(usuario.territorio if usuario.territorio else None)
        
        # Campo nombre_completo (MAYÚSCULAS SIN TILDES)
        if usuario.nombre_completo is not None:
            campos_actualizar.append("nombre_completo = %s")
            valores.append(normalizar_mayus_sin_tildes(usuario.nombre_completo))
        
        # Campo curp (MAYÚSCULAS SIN TILDES)
        if usuario.curp is not None:
            campos_actualizar.append("curp = %s")
            valores.append(normalizar_mayus_sin_tildes(usuario.curp))
        
        # Campo cargo (MAYÚSCULAS SIN TILDES)
        if usuario.cargo is not None:
            campos_actualizar.append("cargo = %s")
            valores.append(normalizar_mayus_sin_tildes(usuario.cargo))
        
        if not campos_actualizar:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")
        
        # Actualizar usuario
        valores.append(user_id)
        query = f"UPDATE admin_users SET {', '.join(campos_actualizar)} WHERE id = %s"
        cursor.execute(query, valores)
        conn.commit()
        
        # Obtener usuario actualizado
        cursor.execute("SELECT id, username, rol, permisos, activo, es_territorial, territorio, nombre_completo, curp, cargo FROM admin_users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        
        # Parsear permisos
        permisos_str = row[3]
        if permisos_str:
            try:
                permisos = json.loads(permisos_str)
            except:
                permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
        else:
            permisos = PERMISOS_ADMIN_DEFAULT if row[2] == 'admin' else PERMISOS_USER_DEFAULT
        
        # Estado activo
        activo = row[4] if row[4] is not None else True
        
        # Es territorial y territorio
        es_territorial = row[5] if row[5] is not None else False
        territorio = row[6]
        
        usuario_actualizado = {
            "id": row[0],
            "username": row[1],
            "rol": row[2],
            "permisos": permisos,
            "activo": activo,
            "es_territorial": es_territorial,
            "territorio": territorio,
            "nombre_completo": row[7] or '',
            "curp": row[8] or '',
            "cargo": row[9] or ''
        }
        
        print(f"✅ Usuario administrativo actualizado: {usuario_actualizado['username']} (activo: {activo}, territorial: {es_territorial})")
        return {
            "message": "Usuario administrativo actualizado exitosamente",
            **usuario_actualizado
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error actualizando usuario administrativo: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")

@app.delete("/admin/usuarios/{user_id}")
async def eliminar_usuario_admin(user_id: int):
    """Eliminar un usuario administrativo"""
    try:
        print(f"🔄 Eliminando usuario administrativo ID: {user_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT username FROM admin_users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        username = row[0]
        
        # Eliminar usuario
        cursor.execute("DELETE FROM admin_users WHERE id = %s", (user_id,))
        conn.commit()
        
        print(f"✅ Usuario administrativo eliminado: {username}")
        return {
            "message": "Usuario administrativo eliminado exitosamente",
            "username": username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando usuario administrativo: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")

@app.put("/admin/usuarios/{user_id}/rol")
async def cambiar_rol_usuario_admin(user_id: int, datos: dict):
    """Cambiar el rol de un usuario administrativo"""
    try:
        print(f"🔄 Cambiando rol de usuario administrativo ID: {user_id}")
        
        rol = datos.get("rol")
        if not rol or rol not in ['admin', 'user']:
            raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT username FROM admin_users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        username = row[0]
        
        # Actualizar rol
        cursor.execute("UPDATE admin_users SET rol = %s WHERE id = %s", (rol, user_id))
        conn.commit()
        
        print(f"✅ Rol cambiado para usuario {username} a: {rol}")
        return {
            "message": f"Rol cambiado exitosamente a {rol}",
            "username": username,
            "nuevo_rol": rol
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error cambiando rol: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar rol: {str(e)}")

@app.patch("/admin/usuarios/{user_id}/estado")
async def cambiar_estado_usuario(user_id: int, datos: dict):
    """Activar o desactivar un usuario administrativo"""
    try:
        print(f"🔄 Cambiando estado de usuario administrativo ID: {user_id}")
        
        activo = datos.get("activo")
        if activo is None:
            raise HTTPException(status_code=400, detail="El campo 'activo' es requerido")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT username FROM admin_users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        username = row[0]
        
        # Actualizar estado
        cursor.execute("UPDATE admin_users SET activo = %s WHERE id = %s", (activo, user_id))
        conn.commit()
        
        estado_texto = "activado" if activo else "desactivado"
        print(f"✅ Usuario {username} {estado_texto}")
        return {
            "message": f"Usuario {estado_texto} exitosamente",
            "username": username,
            "activo": activo
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error cambiando estado de usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cambiar estado: {str(e)}")


@app.put("/admin/usuarios/{user_id}/password")
async def resetear_password_usuario_admin(user_id: int, datos: dict, request: Request):
    """Resetear la contraseña de un usuario administrativo"""
    _jwt_admin(request)
    try:
        print(f"🔄 Reseteando contraseña de usuario administrativo ID: {user_id}")
        
        password = datos.get("password")
        if not password:
            raise HTTPException(status_code=400, detail="La contraseña es requerida")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT username FROM admin_users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
        
        username = row[0]
        
        # Hashear nueva contraseña
        hashed_password = pwd_context.hash(password)
        
        # Actualizar contraseña
        cursor.execute("UPDATE admin_users SET password = %s, password_enc = %s WHERE id = %s", (hashed_password, _cifrar_pwd(password), user_id))
        conn.commit()
        
        print(f"✅ Contraseña reseteada para usuario: {username}")
        return {
            "message": "Contraseña reseteada exitosamente",
            "username": username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error reseteando contraseña: {e}")
        raise HTTPException(status_code=500, detail=f"Error al resetear contraseña: {str(e)}")

@app.get("/admin/usuarios/{user_id}/acceso")
async def obtener_acceso_usuario_admin(user_id: int, request: Request):
    """Datos para el PDF de acceso. Solo 'admin' y 'Jess'. La contraseña viene de la bóveda cifrada."""
    _jwt_admin(request, solo_visores=True)
    cursor.execute("SELECT username, nombre_completo, password_enc FROM admin_users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario administrativo no encontrado")
    pwd = _descifrar_pwd(row[2])
    return {
        "username": row[0],
        "nombre_completo": row[1] or "",
        "password": pwd,
        "disponible": pwd is not None,
        "boveda_activa": _vault is not None,
    }

@app.get("/admin/usuarios/estadisticas")
async def obtener_estadisticas_admin():
    """Obtener estadísticas de usuarios administrativos"""
    try:
        print("🔄 Obteniendo estadísticas de usuarios administrativos...")
        
        # Total de usuarios admin
        cursor.execute("SELECT COUNT(*) FROM admin_users")
        total_usuarios = cursor.fetchone()[0]
        
        # Usuarios por rol
        cursor.execute("SELECT rol, COUNT(*) FROM admin_users GROUP BY rol")
        roles_data = cursor.fetchall()
        
        usuarios_por_rol = {}
        for rol, count in roles_data:
            usuarios_por_rol[rol] = count
        
        estadisticas = {
            "total_usuarios": total_usuarios,
            "usuarios_por_rol": usuarios_por_rol,
            "roles_disponibles": ["admin", "user"]
        }
        
        print(f"✅ Estadísticas obtenidas: {estadisticas}")
        return estadisticas
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

@app.get("/admin/usuarios/buscar")
async def buscar_usuarios_admin(username: Optional[str] = None, rol: Optional[str] = None):
    """Buscar usuarios administrativos por criterios específicos"""
    try:
        print(f"🔄 Buscando usuarios administrativos: username={username}, rol={rol}")
        
        # Construir consulta base
        query = "SELECT id, username, rol FROM admin_users WHERE 1=1"
        params = []
        
        # Agregar filtros
        if username:
            query += " AND username ILIKE %s"
            params.append(f"%{username}%")
        
        if rol:
            if rol not in ['admin', 'user']:
                raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'")
            query += " AND rol = %s"
            params.append(rol)
        
        query += " ORDER BY id ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        usuarios = []
        for row in rows:
            usuario = {
                "id": row[0],
                "username": row[1],
                "rol": row[2]
            }
            usuarios.append(usuario)
        
        print(f"✅ Búsqueda completada: {len(usuarios)} usuarios encontrados")
        return {"usuarios": usuarios}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")

@app.get("/admin/auth/validar")
async def validar_permisos_admin():
    """Validar los permisos del usuario administrativo actual"""
    try:
        print("🔐 Validando permisos de usuario administrativo")
        
        # Este endpoint simula la validación de permisos para admin
        # En una implementación real, aquí se verificaría el token JWT
        return {
            "valido": True,
            "rol": "admin",
            "permisos": [
                "leer_usuarios_admin",
                "crear_usuarios_admin", 
                "editar_usuarios_admin",
                "eliminar_usuarios_admin",
                "cambiar_roles_admin",
                "gestionar_admin_sistema"
            ]
        }
        
    except Exception as e:
        print(f"❌ Error validando permisos admin: {e}")
        raise HTTPException(status_code=500, detail=f"Error al validar permisos: {str(e)}")

# ==================== FIN ENDPOINTS DE GESTIÓN DE USUARIOS ADMINISTRATIVOS ====================

# ==================== ENDPOINT BÚSQUEDA DE IMÁGENES SIMILARES ====================

@app.post("/admin/buscar-imagen-similar")
async def buscar_imagen_similar(
    file: UploadFile = File(...), 
    umbral: int = 15,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
):
    """
    Buscar imágenes similares en la base de datos usando perceptual hashing.
    - file: Imagen a buscar
    - umbral: Diferencia máxima permitida entre hashes (menor = más similar, default: 15)
    - fecha_inicio: Fecha inicio filtro ISO (opcional)
    - fecha_fin: Fecha fin filtro ISO (opcional)
    """
    try:
        from PIL import Image
        import imagehash
        from datetime import datetime
        
        print(f"🔍 Iniciando búsqueda de imagen similar...")
        print(f"   📁 Archivo: {file.filename}")
        print(f"   📊 Umbral de similitud: {umbral}")
        print(f"   📅 Fecha inicio: {fecha_inicio}")
        print(f"   📅 Fecha fin: {fecha_fin}")
        
        # Leer la imagen subida
        contenido = await file.read()
        imagen_subida = Image.open(BytesIO(contenido))
        
        # Calcular hash perceptual de la imagen subida
        hash_subido = imagehash.phash(imagen_subida)
        print(f"   🔑 Hash de imagen subida: {hash_subido}")
        
        # Construir consulta SQL con filtros de fecha opcionales
        query = """
            SELECT r.id, r.usuario_id, r.foto_url, r.fecha_hora, r.descripcion, r.tipo_actividad,
                   u.nombre_completo, u.correo, u.curp
            FROM registros r
            LEFT JOIN usuarios u ON r.usuario_id = u.id
            WHERE r.foto_url IS NOT NULL AND r.foto_url != ''
        """
        params = []
        
        # Agregar filtro de fecha inicio
        if fecha_inicio:
            try:
                # Parsear fecha ISO
                fecha_inicio_dt = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                query += " AND r.fecha_hora >= %s"
                params.append(fecha_inicio_dt)
                print(f"   📅 Filtro fecha inicio: {fecha_inicio_dt}")
            except Exception as e:
                print(f"   ⚠️ Error parseando fecha_inicio: {e}")
        
        # Agregar filtro de fecha fin
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                query += " AND r.fecha_hora <= %s"
                params.append(fecha_fin_dt)
                print(f"   📅 Filtro fecha fin: {fecha_fin_dt}")
            except Exception as e:
                print(f"   ⚠️ Error parseando fecha_fin: {e}")
        
        query += " ORDER BY r.fecha_hora DESC"
        
        # Ejecutar consulta
        cursor.execute(query, params if params else None)
        registros = cursor.fetchall()
        print(f"   📊 Total registros con fotos (filtrados): {len(registros)}")
        
        resultados_similares = []
        imagenes_procesadas = 0
        imagenes_con_error = 0
        
        for registro in registros:
            reg_id, usuario_id, foto_url, fecha_hora, descripcion, tipo_actividad, nombre_completo, correo, curp = registro
            
            try:
                # Construir ruta completa del archivo
                if foto_url.startswith('/fotos/'):
                    ruta_archivo = os.path.join(FOTOS_DIR, foto_url[7:])
                elif foto_url.startswith('fotos/'):
                    ruta_archivo = os.path.join(FOTOS_DIR, foto_url[6:])
                else:
                    ruta_archivo = os.path.join(FOTOS_DIR, foto_url)
                
                # Verificar que el archivo existe
                if not os.path.exists(ruta_archivo):
                    continue
                
                # Cargar imagen y calcular hash
                imagen_bd = Image.open(ruta_archivo)
                hash_bd = imagehash.phash(imagen_bd)
                
                # Calcular diferencia entre hashes
                diferencia = hash_subido - hash_bd
                
                imagenes_procesadas += 1
                
                # Si la diferencia es menor al umbral, es similar
                if diferencia <= umbral:
                    # Calcular porcentaje de similitud (0 = idéntico, umbral = límite)
                    similitud = max(0, 100 - (diferencia * 100 / 64))  # phash tiene 64 bits
                    
                    resultados_similares.append({
                        "registro_id": reg_id,
                        "usuario_id": usuario_id,
                        "foto_url": foto_url,
                        "fecha_hora": fecha_hora.isoformat() if fecha_hora else None,
                        "descripcion": descripcion,
                        "tipo_actividad": tipo_actividad,
                        "usuario": {
                            "nombre_completo": nombre_completo,
                            "correo": correo,
                            "curp": curp
                        },
                        "similitud": round(similitud, 2),
                        "diferencia_hash": diferencia
                    })
                    
            except Exception as e:
                imagenes_con_error += 1
                continue
        
        # Ordenar por similitud (mayor primero)
        resultados_similares.sort(key=lambda x: x['similitud'], reverse=True)
        
        print(f"   ✅ Búsqueda completada:")
        print(f"      - Imágenes procesadas: {imagenes_procesadas}")
        print(f"      - Imágenes con error: {imagenes_con_error}")
        print(f"      - Coincidencias encontradas: {len(resultados_similares)}")
        
        return {
            "success": True,
            "total_procesadas": imagenes_procesadas,
            "total_errores": imagenes_con_error,
            "total_coincidencias": len(resultados_similares),
            "umbral_usado": umbral,
            "resultados": resultados_similares
        }
        
    except ImportError as e:
        print(f"❌ Error: Librería imagehash no instalada. Ejecutar: pip install imagehash Pillow")
        raise HTTPException(status_code=500, detail="Librería imagehash no instalada en el servidor")
    except Exception as e:
        print(f"❌ Error en búsqueda de imagen similar: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al buscar imagen: {str(e)}")

# ==================== FIN ENDPOINT BÚSQUEDA IMÁGENES SIMILARES ====================

@app.get("/auth/validar")
async def validar_permisos_usuario():
    """Validar los permisos del usuario actual basado en el token"""
    try:
        # Este endpoint simula la validación de permisos
        # En una implementación real, aquí se verificaría el token JWT
        print("🔐 Validando permisos de usuario")
        
        return {
            "valido": True,
            "rol": "admin",  # Por ahora siempre admin para el panel de administración
            "permisos": [
                "leer_usuarios",
                "crear_usuarios", 
                "editar_usuarios",
                "eliminar_usuarios",
                "cambiar_roles",
                "gestionar_notificaciones"
            ]
        }
        
    except Exception as e:
        print(f"❌ Error validando permisos: {e}")
        raise HTTPException(status_code=500, detail=f"Error al validar permisos: {str(e)}")

@app.get("/health")
async def verificar_salud_api():
    """Endpoint para verificar que la API está funcionando"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "database_connected": bool(conn)
    }

# ==================== FIN ENDPOINTS DE GESTIÓN DE ROLES Y PERMISOS ====================

# ==================== ENDPOINT PARA ELIMINAR TODAS LAS IMÁGENES ====================

@app.delete("/imagenes/eliminar-todas")
async def eliminar_todas_imagenes():
    """
    Endpoint para eliminar TODAS las imágenes (fotos) almacenadas en la base de datos.
    Elimina:
    - Todas las fotos de registros de actividades
    - Todas las fotos de entrada/salida de asistencias
    - Los archivos físicos del directorio de fotos
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print("🗑️ INICIANDO ELIMINACIÓN DE TODAS LAS IMÁGENES...")
        
        # Contadores
        fotos_bd_eliminadas = 0
        fotos_archivo_eliminadas = 0
        fotos_no_encontradas = 0
        errores = 0
        
        # 1. Obtener todas las fotos de registros
        try:
            cursor.execute("SELECT DISTINCT foto_url FROM registros WHERE foto_url IS NOT NULL")
            fotos_registros = cursor.fetchall()
            print(f"📸 Se encontraron {len(fotos_registros)} fotos en registros")
            
            for foto_row in fotos_registros:
                foto_path = foto_row[0]
                if foto_path:
                    if os.path.exists(foto_path):
                        try:
                            os.remove(foto_path)
                            fotos_archivo_eliminadas += 1
                            print(f"   ✅ Eliminado: {foto_path}")
                        except Exception as e:
                            errores += 1
                            print(f"   ❌ Error eliminando {foto_path}: {e}")
                    else:
                        fotos_no_encontradas += 1
                        print(f"   ⚠️ Archivo no encontrado: {foto_path}")
        except Exception as e:
            print(f"⚠️ Error al obtener fotos de registros: {e}")
            errores += 1
        
        # 2. Obtener todas las fotos de asistencias (entrada y salida)
        try:
            cursor.execute("""
                SELECT DISTINCT foto_entrada_url, foto_salida_url 
                FROM asistencias 
                WHERE foto_entrada_url IS NOT NULL OR foto_salida_url IS NOT NULL
            """)
            fotos_asistencias = cursor.fetchall()
            print(f"📸 Se encontraron {len(fotos_asistencias)} registros de asistencia con fotos")
            
            for foto_row in fotos_asistencias:
                # Foto de entrada
                if foto_row[0]:
                    foto_path = foto_row[0]
                    if os.path.exists(foto_path):
                        try:
                            os.remove(foto_path)
                            fotos_archivo_eliminadas += 1
                            print(f"   ✅ Eliminado: {foto_path}")
                        except Exception as e:
                            errores += 1
                            print(f"   ❌ Error eliminando {foto_path}: {e}")
                    else:
                        fotos_no_encontradas += 1
                        print(f"   ⚠️ Archivo no encontrado: {foto_path}")
                
                # Foto de salida
                if foto_row[1]:
                    foto_path = foto_row[1]
                    if os.path.exists(foto_path):
                        try:
                            os.remove(foto_path)
                            fotos_archivo_eliminadas += 1
                            print(f"   ✅ Eliminado: {foto_path}")
                        except Exception as e:
                            errores += 1
                            print(f"   ❌ Error eliminando {foto_path}: {e}")
                    else:
                        fotos_no_encontradas += 1
                        print(f"   ⚠️ Archivo no encontrado: {foto_path}")
        except Exception as e:
            print(f"⚠️ Error al obtener fotos de asistencias: {e}")
            errores += 1
        
        # 3. Limpiar referencias en la base de datos
        try:
            # Actualizar registros estableciendo foto_url en NULL
            cursor.execute("UPDATE registros SET foto_url = NULL WHERE foto_url IS NOT NULL")
            registros_limpiados = cursor.rowcount
            print(f"🗑️ {registros_limpiados} registros limpios en la BD")
            
            # Actualizar asistencias estableciendo fotos en NULL
            cursor.execute("UPDATE asistencias SET foto_entrada_url = NULL WHERE foto_entrada_url IS NOT NULL")
            entrada_limpiadas = cursor.rowcount
            
            cursor.execute("UPDATE asistencias SET foto_salida_url = NULL WHERE foto_salida_url IS NOT NULL")
            salida_limpiadas = cursor.rowcount
            
            print(f"🗑️ {entrada_limpiadas} fotos de entrada limpias en la BD")
            print(f"🗑️ {salida_limpiadas} fotos de salida limpias en la BD")
            
            fotos_bd_eliminadas = registros_limpiados + entrada_limpiadas + salida_limpiadas
            
            conn.commit()
            print("✅ Cambios confirmados en la base de datos")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error limpiando la base de datos: {e}")
            errores += 1
        
        # 4. Limpiar archivos huérfanos en el directorio de fotos
        try:
            if os.path.exists(FOTOS_DIR):
                archivos_directorio = os.listdir(FOTOS_DIR)
                print(f"📁 Se encontraron {len(archivos_directorio)} archivos en el directorio de fotos")
                
                for archivo in archivos_directorio:
                    ruta_archivo = os.path.join(FOTOS_DIR, archivo)
                    if os.path.isfile(ruta_archivo):
                        try:
                            os.remove(ruta_archivo)
                            fotos_archivo_eliminadas += 1
                            print(f"   ✅ Eliminado archivo huérfano: {archivo}")
                        except Exception as e:
                            errores += 1
                            print(f"   ❌ Error eliminando archivo {archivo}: {e}")
        except Exception as e:
            print(f"⚠️ Error limpiando directorio de fotos: {e}")
            errores += 1
        
        # Preparar resumen
        resumen = {
            "status": "success",
            "message": "Eliminación de imágenes completada",
            "estadisticas": {
                "fotos_bd_limpiadas": fotos_bd_eliminadas,
                "archivos_eliminados": fotos_archivo_eliminadas,
                "archivos_no_encontrados": fotos_no_encontradas,
                "total_eliminado": fotos_archivo_eliminadas + fotos_no_encontradas,
                "errores_encontrados": errores
            },
            "timestamp": datetime.now().isoformat()
        }
        
        print("\n✅ ELIMINACIÓN COMPLETADA:")
        print(f"   📸 Fotos en BD limpiadas: {fotos_bd_eliminadas}")
        print(f"   🗑️ Archivos eliminados: {fotos_archivo_eliminadas}")
        print(f"   ⚠️ Archivos no encontrados: {fotos_no_encontradas}")
        print(f"   ❌ Errores: {errores}")
        
        return resumen
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error general en eliminación de imágenes: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar imágenes: {str(e)}")

# ==================== FIN ENDPOINT ELIMINAR IMÁGENES ====================

# ==================== ENDPOINT PARA ELIMINAR IMÁGENES POR FECHA ====================

class EliminarImagenesPorFechaRequest(BaseModel):
    mes: int  # 1-12
    anio: int  # Ejemplo: 2025
    solo_mes: bool = True  # Si True, solo el mes especificado. Si False, todo el año

@app.delete("/imagenes/eliminar-por-fecha")
@app.post("/imagenes/eliminar-por-fecha")
async def eliminar_imagenes_por_fecha(request: EliminarImagenesPorFechaRequest):
    """
    Endpoint para eliminar imágenes filtradas por mes/año.
    Elimina:
    - Fotos de registros de actividades del período especificado
    - Fotos de asistencias del período especificado
    - Los archivos físicos correspondientes
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        mes = request.mes
        anio = request.anio
        solo_mes = request.solo_mes
        
        # Validar mes
        if mes < 1 or mes > 12:
            raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
        
        # Validar año
        if anio < 2020 or anio > 2050:
            raise HTTPException(status_code=400, detail="El año debe estar entre 2020 y 2050")
        
        # Calcular rango de fechas
        if solo_mes:
            fecha_inicio = f"{anio}-{mes:02d}-01"
            # Calcular último día del mes
            if mes == 12:
                fecha_fin = f"{anio + 1}-01-01"
            else:
                fecha_fin = f"{anio}-{mes + 1:02d}-01"
            periodo_texto = f"{mes:02d}/{anio}"
        else:
            fecha_inicio = f"{anio}-01-01"
            fecha_fin = f"{anio + 1}-01-01"
            periodo_texto = f"año {anio}"
        
        print(f"🗑️ INICIANDO ELIMINACIÓN DE IMÁGENES POR FECHA...")
        print(f"📅 Período: {periodo_texto}")
        print(f"📅 Rango: {fecha_inicio} a {fecha_fin}")
        
        # Contadores
        fotos_registros_eliminadas = 0
        fotos_asistencias_eliminadas = 0
        archivos_eliminados = 0
        archivos_no_encontrados = 0
        errores = 0
        
        # 1. Obtener fotos de REGISTROS en el período
        try:
            cursor.execute("""
                SELECT id, foto_url FROM registros 
                WHERE foto_url IS NOT NULL 
                AND fecha_hora >= %s AND fecha_hora < %s
            """, (fecha_inicio, fecha_fin))
            fotos_registros = cursor.fetchall()
            print(f"📸 Se encontraron {len(fotos_registros)} fotos de registros en el período")
            
            # Eliminar archivos físicos
            for foto_row in fotos_registros:
                foto_path = foto_row[1]
                if foto_path:
                    try:
                        if os.path.exists(foto_path):
                            os.remove(foto_path)
                            archivos_eliminados += 1
                        else:
                            archivos_no_encontrados += 1
                    except Exception as e:
                        errores += 1
                        print(f"   ❌ Error eliminando {foto_path}: {e}")
            
            # Limpiar referencias en BD con una sola query batch
            cursor.execute("""
                UPDATE registros SET foto_url = NULL 
                WHERE foto_url IS NOT NULL 
                AND fecha_hora >= %s AND fecha_hora < %s
            """, (fecha_inicio, fecha_fin))
            fotos_registros_eliminadas = cursor.rowcount or 0
            conn.commit()
            print(f"   ✅ {fotos_registros_eliminadas} registros limpiados en batch")
            
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error al procesar fotos de registros: {e}")
            errores += 1
        
        # 2. Obtener fotos de ASISTENCIAS en el período
        try:
            cursor.execute("""
                SELECT id, foto_entrada_url, foto_salida_url FROM asistencias 
                WHERE (foto_entrada_url IS NOT NULL OR foto_salida_url IS NOT NULL)
                AND fecha >= %s AND fecha < %s
            """, (fecha_inicio, fecha_fin))
            fotos_asistencias = cursor.fetchall()
            print(f"📸 Se encontraron {len(fotos_asistencias)} registros de asistencia con fotos en el período")
            
            # Eliminar archivos físicos
            for foto_row in fotos_asistencias:
                foto_entrada = foto_row[1]
                foto_salida = foto_row[2]
                
                if foto_entrada:
                    try:
                        if os.path.exists(foto_entrada):
                            os.remove(foto_entrada)
                            archivos_eliminados += 1
                        else:
                            archivos_no_encontrados += 1
                    except Exception as e:
                        errores += 1
                
                if foto_salida:
                    try:
                        if os.path.exists(foto_salida):
                            os.remove(foto_salida)
                            archivos_eliminados += 1
                        else:
                            archivos_no_encontrados += 1
                    except Exception as e:
                        errores += 1
            
            # Limpiar referencias en BD con una sola query batch
            cursor.execute("""
                UPDATE asistencias 
                SET foto_entrada_url = NULL, foto_salida_url = NULL 
                WHERE (foto_entrada_url IS NOT NULL OR foto_salida_url IS NOT NULL)
                AND fecha >= %s AND fecha < %s
            """, (fecha_inicio, fecha_fin))
            fotos_asistencias_eliminadas = cursor.rowcount or 0
            conn.commit()
            print(f"   ✅ {fotos_asistencias_eliminadas} asistencias limpiadas en batch")
            
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error al procesar fotos de asistencias: {e}")
            errores += 1
        
        # Preparar resumen
        resumen = {
            "status": "success",
            "message": f"Eliminación de imágenes del período {periodo_texto} completada",
            "periodo": {
                "mes": mes,
                "anio": anio,
                "solo_mes": solo_mes,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            },
            "estadisticas": {
                "registros_limpiados": fotos_registros_eliminadas,
                "asistencias_limpiadas": fotos_asistencias_eliminadas,
                "archivos_eliminados": archivos_eliminados,
                "archivos_no_encontrados": archivos_no_encontrados,
                "total_procesado": fotos_registros_eliminadas + fotos_asistencias_eliminadas,
                "errores": errores
            },
            "timestamp": datetime.now().isoformat()
        }
        
        print("\n✅ ELIMINACIÓN POR FECHA COMPLETADA:")
        print(f"   📸 Registros limpiados: {fotos_registros_eliminadas}")
        print(f"   📸 Asistencias limpiadas: {fotos_asistencias_eliminadas}")
        print(f"   🗑️ Archivos eliminados: {archivos_eliminados}")
        print(f"   ⚠️ Archivos no encontrados: {archivos_no_encontrados}")
        print(f"   ❌ Errores: {errores}")
        
        return resumen
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error general en eliminación de imágenes por fecha: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar imágenes: {str(e)}")

# ==================== FIN ENDPOINT ELIMINAR IMÁGENES POR FECHA ====================

# ==================== NUEVO ENDPOINT: DESCARGAR BD COMPLETA RÁPIDA ====================

@app.get("/descargar-bd-completa", response_class=StreamingResponse)
async def descargar_bd_completa():
    """
    Endpoint optimizado para descargar TODA la base de datos en formato SQL de forma MUY RÁPIDA
    Usa streaming para manejo eficiente de memoria
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print("🚀 [BD COMPLETA] Iniciando descarga rápida de base de datos completa...")
        timestamp = datetime.now().isoformat().replace(':', '-')
        nombre_archivo = f"BASE_DATOS_COMPLETA_{timestamp}.sql"
        
        async def generar_sql():
            """Generador de SQL para streaming eficiente"""
            
            try:
                # Header
                yield f"""-- ===============================================
-- EXPORTACIÓN COMPLETA BASE DE DATOS app_registros
-- ===============================================
-- Generado: {datetime.now().isoformat()}
-- Servidor: app_registros (PostgreSQL)
-- ===============================================

"""
                
                # 1. TABLA USUARIOS - Crear e insertar datos de forma rápida
                print("📝 Procesando tabla usuarios...")
                yield """-- ======== TABLA: USUARIOS ========
DROP TABLE IF EXISTS usuarios CASCADE;

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    correo VARCHAR(255) UNIQUE NOT NULL,
    nombre_completo VARCHAR(255) NOT NULL,
    cargo VARCHAR(255),
    supervisor VARCHAR(255),
    contrasena VARCHAR(255) NOT NULL,
    curp VARCHAR(18) UNIQUE,
    telefono VARCHAR(20),
    rol VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""
                
                # Obtener usuarios de forma rápida
                cursor.execute("""
                    SELECT id, correo, nombre_completo, cargo, supervisor, 
                           contrasena, curp, telefono, rol
                    FROM usuarios 
                    ORDER BY id ASC
                """)
                
                usuarios_data = cursor.fetchall()
                print(f"📊 Obtenidos {len(usuarios_data)} usuarios")
                
                if usuarios_data:
                    yield "INSERT INTO usuarios (id, correo, nombre_completo, cargo, supervisor, contrasena, curp, telefono, rol) VALUES\n"
                    
                    for idx, row in enumerate(usuarios_data):
                        id_u, correo, nombre, cargo, supervisor, contrasena, curp, telefono, rol = row
                        
                        # Escapar comillas simples
                        correo = (correo or '').replace("'", "''")
                        nombre = (nombre or '').replace("'", "''")
                        cargo = (cargo or '').replace("'", "''")
                        supervisor = (supervisor or '').replace("'", "''")
                        contrasena = (contrasena or '').replace("'", "''")
                        curp = (curp or '').replace("'", "''")
                        telefono = (telefono or '').replace("'", "''")
                        rol = (rol or 'user').replace("'", "''")
                        
                        coma = "," if idx < len(usuarios_data) - 1 else ";"
                        yield f"({id_u}, '{correo}', '{nombre}', '{cargo}', '{supervisor}', '{contrasena}', '{curp}', '{telefono}', '{rol}'){coma}\n"
                
                yield "\n"
                
                # 2. TABLA REGISTROS - Insertar datos de forma rápida
                print("📋 Procesando tabla registros...")
                yield """-- ======== TABLA: REGISTROS ========
DROP TABLE IF EXISTS registros CASCADE;

CREATE TABLE registros (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    latitud DECIMAL(10, 8),
    longitud DECIMAL(11, 8),
    descripcion TEXT,
    foto_url VARCHAR(500),
    fecha_hora TIMESTAMP NOT NULL,
    tipo_actividad VARCHAR(50) DEFAULT 'campo',
    categoria_actividad VARCHAR(100),
    categoria_actividad_otro VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""
                
                # Obtener registros de forma rápida
                cursor.execute("""
                    SELECT id, usuario_id, latitud, longitud, descripcion, 
                           foto_url, fecha_hora, tipo_actividad, categoria_actividad, categoria_actividad_otro
                    FROM registros 
                    ORDER BY id ASC
                """)
                
                registros_data = cursor.fetchall()
                print(f"📊 Obtenidos {len(registros_data)} registros")
                
                if registros_data:
                    yield "INSERT INTO registros (id, usuario_id, latitud, longitud, descripcion, foto_url, fecha_hora, tipo_actividad, categoria_actividad, categoria_actividad_otro) VALUES\n"
                    
                    for idx, row in enumerate(registros_data):
                        id_r, usuario_id, lat, lon, desc, foto, fecha, tipo, cat_act, cat_act_otro = row
                        
                        # Escapar comillas simples
                        desc = (desc or '').replace("'", "''")
                        foto = (foto or '').replace("'", "''")
                        tipo = (tipo or 'campo').replace("'", "''")
                        cat_act = (cat_act or '').replace("'", "''")
                        cat_act_otro = (cat_act_otro or '').replace("'", "''")
                        
                        lat_str = str(lat) if lat is not None else "NULL"
                        lon_str = str(lon) if lon is not None else "NULL"
                        fecha_str = str(fecha) if fecha else "NOW()"
                        cat_act_str = f"'{cat_act}'" if cat_act else "NULL"
                        cat_act_otro_str = f"'{cat_act_otro}'" if cat_act_otro else "NULL"
                        
                        coma = "," if idx < len(registros_data) - 1 else ";"
                        yield f"({id_r}, {usuario_id}, {lat_str}, {lon_str}, '{desc}', '{foto}', '{fecha_str}', '{tipo}', {cat_act_str}, {cat_act_otro_str}){coma}\n"
                
                yield "\n"
                
                # 3. TABLA ASISTENCIAS - Insertar datos de forma rápida
                print("🕐 Procesando tabla asistencias...")
                yield """-- ======== TABLA: ASISTENCIAS ========
DROP TABLE IF EXISTS asistencias CASCADE;

CREATE TABLE asistencias (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    fecha DATE NOT NULL,
    hora_entrada TIMESTAMP,
    hora_salida TIMESTAMP,
    latitud_entrada DECIMAL(10, 8),
    longitud_entrada DECIMAL(11, 8),
    latitud_salida DECIMAL(10, 8),
    longitud_salida DECIMAL(11, 8),
    foto_entrada_url VARCHAR(500),
    foto_salida_url VARCHAR(500),
    descripcion_entrada TEXT,
    descripcion_salida TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""
                
                # Obtener asistencias de forma rápida
                cursor.execute("""
                    SELECT id, usuario_id, fecha, hora_entrada, hora_salida,
                           latitud_entrada, longitud_entrada, latitud_salida, 
                           longitud_salida, foto_entrada_url, foto_salida_url,
                           descripcion_entrada, descripcion_salida
                    FROM asistencias 
                    ORDER BY id ASC
                """)
                
                asistencias_data = cursor.fetchall()
                print(f"📊 Obtenidas {len(asistencias_data)} asistencias")
                
                if asistencias_data:
                    yield "INSERT INTO asistencias (id, usuario_id, fecha, hora_entrada, hora_salida, latitud_entrada, longitud_entrada, latitud_salida, longitud_salida, foto_entrada_url, foto_salida_url, descripcion_entrada, descripcion_salida) VALUES\n"
                    
                    for idx, row in enumerate(asistencias_data):
                        id_a, usuario_id, fecha, hora_ent, hora_sal, lat_ent, lon_ent, lat_sal, lon_sal, foto_ent, foto_sal, desc_ent, desc_sal = row
                        
                        # Escapar comillas simples
                        foto_ent = (foto_ent or '').replace("'", "''")
                        foto_sal = (foto_sal or '').replace("'", "''")
                        desc_ent = (desc_ent or '').replace("'", "''")
                        desc_sal = (desc_sal or '').replace("'", "''")
                        
                        fecha_str = str(fecha) if fecha else "CURRENT_DATE"
                        hora_ent_str = f"'{str(hora_ent)}'" if hora_ent else "NULL"
                        hora_sal_str = f"'{str(hora_sal)}'" if hora_sal else "NULL"
                        lat_ent_str = str(lat_ent) if lat_ent is not None else "NULL"
                        lon_ent_str = str(lon_ent) if lon_ent is not None else "NULL"
                        lat_sal_str = str(lat_sal) if lat_sal is not None else "NULL"
                        lon_sal_str = str(lon_sal) if lon_sal is not None else "NULL"
                        
                        coma = "," if idx < len(asistencias_data) - 1 else ";"
                        yield f"({id_a}, {usuario_id}, '{fecha_str}', {hora_ent_str}, {hora_sal_str}, {lat_ent_str}, {lon_ent_str}, {lat_sal_str}, {lon_sal_str}, '{foto_ent}', '{foto_sal}', '{desc_ent}', '{desc_sal}'){coma}\n"
                
                yield "\n"
                
                # 4. Crear índices para optimización
                print("🔍 Agregando índices...")
                yield """-- ======== ÍNDICES PARA OPTIMIZACIÓN ========
CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios(correo);
CREATE INDEX IF NOT EXISTS idx_usuarios_curp ON usuarios(curp);
CREATE INDEX IF NOT EXISTS idx_registros_usuario ON registros(usuario_id);
CREATE INDEX IF NOT EXISTS idx_registros_fecha ON registros(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_asistencias_usuario ON asistencias(usuario_id);
CREATE INDEX IF NOT EXISTS idx_asistencias_fecha ON asistencias(fecha);

-- ======== FIN DE EXPORTACIÓN ========
-- Total registros exportados: usuarios={}, registros={}, asistencias={}
-- Fecha: {}
-- ===============================================
""".format(len(usuarios_data), len(registros_data), len(asistencias_data), 
           datetime.now().isoformat())
                
                print("✅ Descarga de BD completa generada exitosamente")
                
            except Exception as e:
                print(f"❌ Error generando SQL: {e}")
                yield f"-- ERROR: {str(e)}\n"
        
        # Headers para descarga
        headers = {
            "Content-Disposition": f"attachment; filename={nombre_archivo}",
            "Content-Type": "application/sql; charset=utf-8"
        }
        
        print(f"📥 Iniciando descarga del archivo: {nombre_archivo}")
        return StreamingResponse(
            content=generar_sql(),
            media_type="application/sql; charset=utf-8",
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en descarga de BD completa: {e}")
        raise HTTPException(status_code=500, detail=f"Error al descargar base de datos: {str(e)}")

# ==================== FIN DESCARGA BD COMPLETA ====================

# ==================== NUEVO ENDPOINT: EXPORTAR REGISTROS A CSV ====================

@app.get("/exportar-registros-csv", response_class=StreamingResponse)
async def exportar_registros_csv():
    """
    Endpoint optimizado para exportar TODOS los registros de actividades en formato CSV
    Usa streaming para manejo eficiente de memoria
    Incluye: Modalidad (campo/gabinete), Tipo de Actividad y Tipo de Actividad Otro
    """
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print("📊 [ACTIVIDADES CSV] Iniciando exportación de actividades a CSV...")
        timestamp = datetime.now().isoformat().replace(':', '-')
        nombre_archivo = f"ACTIVIDADES_{timestamp}.csv"
        
        async def generar_csv():
            """Generador de CSV para streaming eficiente"""
            
            try:
                # Header CSV - Incluye Tipo_Actividad (modalidad) y Categoria_Actividad (tipo de actividad)
                header = "ID,Usuario_ID,Nombre_Usuario,Correo_Usuario,Cargo,Latitud,Longitud,Descripcion,Modalidad,Tipo_Actividad,Tipo_Actividad_Otro,Fecha_Hora,Foto_URL\n"
                yield header
                
                print("📝 Procesando registros...")
                
                # Obtener registros con información de usuarios de forma rápida
                # Incluye categoria_actividad (tipo de actividad) y categoria_actividad_otro
                cursor.execute("""
                    SELECT 
                        r.id, 
                        r.usuario_id, 
                        u.nombre_completo, 
                        u.correo, 
                        u.cargo,
                        r.latitud, 
                        r.longitud, 
                        r.descripcion, 
                        r.tipo_actividad,
                        r.categoria_actividad,
                        r.categoria_actividad_otro,
                        r.fecha_hora,
                        r.foto_url
                    FROM registros r
                    LEFT JOIN usuarios u ON r.usuario_id = u.id
                    ORDER BY r.id ASC
                """)
                
                # Procesar resultados en chunks
                chunk_size = 500
                registros_procesados = 0
                
                while True:
                    registros = cursor.fetchmany(chunk_size)
                    if not registros:
                        break
                    
                    for registro in registros:
                        # Ahora incluye categoria_actividad y categoria_actividad_otro
                        id_r, usuario_id, nombre, correo, cargo, lat, lon, desc, modalidad, tipo_actividad, tipo_actividad_otro, fecha, foto = registro
                        
                        # Escapar comillas y saltos de línea en campos de texto
                        nombre = (nombre or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        correo = (correo or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        cargo = (cargo or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        desc = (desc or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        modalidad = (modalidad or 'campo').replace('"', '""')
                        tipo_actividad = (tipo_actividad or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        tipo_actividad_otro = (tipo_actividad_otro or '').replace('"', '""').replace('\n', ' ').replace('\r', '')
                        foto = (foto or '').replace('"', '""')
                        
                        # Formatear fecha
                        fecha_str = str(fecha) if fecha else ''
                        
                        # Construir línea CSV con nuevos campos
                        # Columnas: ID,Usuario_ID,Nombre_Usuario,Correo_Usuario,Cargo,Latitud,Longitud,Descripcion,Modalidad,Tipo_Actividad,Tipo_Actividad_Otro,Fecha_Hora,Foto_URL
                        linea = f'{id_r},{usuario_id},"{nombre}","{correo}","{cargo}",{lat},{lon},"{desc}","{modalidad}","{tipo_actividad}","{tipo_actividad_otro}","{fecha_str}","{foto}"\n'
                        
                        yield linea
                        registros_procesados += 1
                        
                        # Log cada 1000 registros
                        if registros_procesados % 1000 == 0:
                            print(f"📊 {registros_procesados} registros procesados...")
                
                print(f"✅ {registros_procesados} registros exportados a CSV")
                
            except Exception as e:
                print(f"❌ Error generando CSV: {e}")
                yield f"# ERROR: {str(e)}\n"
        
        # Headers para descarga
        headers = {
            "Content-Disposition": f"attachment; filename={nombre_archivo}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        
        print(f"📥 Iniciando descarga del archivo: {nombre_archivo}")
        return StreamingResponse(
            content=generar_csv(),
            media_type="text/csv; charset=utf-8",
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en exportación CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Error al exportar registros: {str(e)}")

# ==================== FIN EXPORTAR REGISTROS A CSV ====================

# ==================== BUSCAR USUARIO POR CURP ====================

@app.get("/usuarios/buscar-curp/{curp}")
async def buscar_usuario_por_curp(curp: str):
    """
    Buscar usuario por CURP y devolver su información junto con conteo de actividades
    """
    try:
        print(f"🔍 Buscando usuario con CURP: {curp}")
        
        # Convertir CURP a mayúsculas y limpiar espacios
        curp_upper = curp.upper().strip()
        
        if len(curp_upper) != 18:
            raise HTTPException(status_code=400, detail="La CURP debe tener exactamente 18 caracteres")
        
        # Buscar usuario por CURP
        usuario = ejecutar_consulta_segura(
            "SELECT id, correo, nombre_completo, cargo, supervisor, curp, telefono, territorio, rol FROM usuarios WHERE curp = %s",
            (curp_upper,),
            fetch_type='one'
        )
        
        if not usuario:
            raise HTTPException(status_code=404, detail=f"No se encontró usuario con CURP: {curp_upper}")
        
        # Contar actividades (registros) del usuario
        conteo_actividades = ejecutar_consulta_segura(
            "SELECT COUNT(*) FROM registros WHERE usuario_id = %s",
            (usuario[0],),
            fetch_type='one'
        )
        
        # Contar asistencias del usuario
        conteo_asistencias = ejecutar_consulta_segura(
            "SELECT COUNT(*) FROM asistencias WHERE usuario_id = %s",
            (usuario[0],),
            fetch_type='one'
        )
        
        resultado = {
            "id": usuario[0],
            "correo": usuario[1],
            "nombre_completo": usuario[2],
            "cargo": usuario[3],
            "supervisor": usuario[4],
            "curp": usuario[5],
            "telefono": usuario[6],
            "territorio": usuario[7],
            "rol": usuario[8] if len(usuario) > 8 else 'user',
            "total_actividades": conteo_actividades[0] if conteo_actividades else 0,
            "total_asistencias": conteo_asistencias[0] if conteo_asistencias else 0
        }
        
        print(f"✅ Usuario encontrado: {resultado['nombre_completo']} - Actividades: {resultado['total_actividades']}")
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error buscando usuario por CURP: {e}")
        raise HTTPException(status_code=500, detail=f"Error al buscar usuario: {str(e)}")

# ==================== TRANSFERIR ACTIVIDADES ENTRE USUARIOS ====================

class TransferenciaActividades(BaseModel):
    curp_origen: str
    curp_destino: str
    incluir_asistencias: bool = False

@app.post("/usuarios/transferir-actividades")
async def transferir_actividades(datos: TransferenciaActividades):
    """
    Transferir todas las actividades (registros) de un usuario a otro por CURP.
    Opcionalmente también puede transferir asistencias.
    """
    try:
        print(f"🔄 Iniciando transferencia de actividades:")
        print(f"   Origen CURP: {datos.curp_origen}")
        print(f"   Destino CURP: {datos.curp_destino}")
        print(f"   Incluir asistencias: {datos.incluir_asistencias}")
        
        # Validar y limpiar CURPs
        curp_origen = datos.curp_origen.upper().strip()
        curp_destino = datos.curp_destino.upper().strip()
        
        if len(curp_origen) != 18 or len(curp_destino) != 18:
            raise HTTPException(status_code=400, detail="Las CURPs deben tener exactamente 18 caracteres")
        
        if curp_origen == curp_destino:
            raise HTTPException(status_code=400, detail="La CURP de origen y destino no pueden ser iguales")
        
        # Buscar usuario origen
        usuario_origen = ejecutar_consulta_segura(
            "SELECT id, nombre_completo, correo FROM usuarios WHERE curp = %s",
            (curp_origen,),
            fetch_type='one'
        )
        
        if not usuario_origen:
            raise HTTPException(status_code=404, detail=f"No se encontró usuario origen con CURP: {curp_origen}")
        
        # Buscar usuario destino
        usuario_destino = ejecutar_consulta_segura(
            "SELECT id, nombre_completo, correo FROM usuarios WHERE curp = %s",
            (curp_destino,),
            fetch_type='one'
        )
        
        if not usuario_destino:
            raise HTTPException(status_code=404, detail=f"No se encontró usuario destino con CURP: {curp_destino}")
        
        id_origen = usuario_origen[0]
        id_destino = usuario_destino[0]
        
        print(f"📊 Usuario origen ID: {id_origen} ({usuario_origen[1]})")
        print(f"📊 Usuario destino ID: {id_destino} ({usuario_destino[1]})")
        
        # Contar actividades antes de transferir
        conteo_antes = ejecutar_consulta_segura(
            "SELECT COUNT(*) FROM registros WHERE usuario_id = %s",
            (id_origen,),
            fetch_type='one'
        )
        actividades_a_transferir = conteo_antes[0] if conteo_antes else 0
        
        if actividades_a_transferir == 0 and not datos.incluir_asistencias:
            raise HTTPException(status_code=400, detail="El usuario origen no tiene actividades para transferir")
        
        # Transferir actividades (registros)
        ejecutar_consulta_segura(
            "UPDATE registros SET usuario_id = %s WHERE usuario_id = %s",
            (id_destino, id_origen),
            fetch_type='none'
        )
        
        print(f"✅ {actividades_a_transferir} actividades transferidas")
        
        # Transferir asistencias si se solicita
        asistencias_transferidas = 0
        if datos.incluir_asistencias:
            conteo_asistencias = ejecutar_consulta_segura(
                "SELECT COUNT(*) FROM asistencias WHERE usuario_id = %s",
                (id_origen,),
                fetch_type='one'
            )
            asistencias_a_transferir = conteo_asistencias[0] if conteo_asistencias else 0
            
            if asistencias_a_transferir > 0:
                ejecutar_consulta_segura(
                    "UPDATE asistencias SET usuario_id = %s WHERE usuario_id = %s",
                    (id_destino, id_origen),
                    fetch_type='none'
                )
                asistencias_transferidas = asistencias_a_transferir
                print(f"✅ {asistencias_transferidas} asistencias transferidas")
        
        resultado = {
            "status": "success",
            "mensaje": "Transferencia completada exitosamente",
            "detalles": {
                "usuario_origen": {
                    "id": id_origen,
                    "nombre": usuario_origen[1],
                    "correo": usuario_origen[2],
                    "curp": curp_origen
                },
                "usuario_destino": {
                    "id": id_destino,
                    "nombre": usuario_destino[1],
                    "correo": usuario_destino[2],
                    "curp": curp_destino
                },
                "actividades_transferidas": actividades_a_transferir,
                "asistencias_transferidas": asistencias_transferidas
            }
        }
        
        print(f"✅ Transferencia completada: {actividades_a_transferir} actividades, {asistencias_transferidas} asistencias")
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en transferencia de actividades: {e}")
        # Hacer rollback en caso de error
        try:
            if conn and not conn.closed:
                conn.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error al transferir actividades: {str(e)}")

# ==================== FIN TRANSFERIR ACTIVIDADES ====================

# ==================== SUPERVISOR AUTOMÁTICO POR TERRITORIO ====================

@app.get("/usuarios/{user_id}/facilitador-asignado")
async def obtener_facilitador_asignado(user_id: int):
    """
    Obtiene el nombre del facilitador comunitario asignado a un técnico.
    Usa la tabla facilitador_tecnico_asignaciones para la búsqueda.
    """
    try:
        print(f"🔍 Buscando facilitador asignado para usuario ID: {user_id}")
        cursor.execute("""
            SELECT
                COALESCE(au.nombre_completo, u.nombre_completo) AS facilitador_nombre,
                fta.facilitador_admin_id,
                fta.facilitador_usuario_id,
                COALESCE(au.curp, u.curp) AS facilitador_curp,
                fta.origen
            FROM facilitador_tecnico_asignaciones fta
            LEFT JOIN admin_users au ON au.id = fta.facilitador_admin_id
            LEFT JOIN usuarios u ON u.id = fta.facilitador_usuario_id
            WHERE fta.tecnico_usuario_id = %s AND fta.activo = TRUE
            ORDER BY fta.updated_at DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            print(f"   ✅ Facilitador encontrado: {row[0]}")
            return {
                "success": True,
                "facilitador_nombre": row[0],
                "facilitador_admin_id": row[1],
                "facilitador_usuario_id": row[2],
                "facilitador_curp": row[3],
                "origen": row[4]
            }
        else:
            print(f"   ℹ️ No hay facilitador asignado para usuario {user_id}")
            return {
                "success": True,
                "facilitador_nombre": None,
                "facilitador_admin_id": None,
                "facilitador_usuario_id": None,
                "mensaje": "Sin facilitador asignado"
            }
    except Exception as e:
        print(f"❌ Error obteniendo facilitador asignado: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/usuarios/{user_id}/supervisor-automatico")
async def obtener_supervisor_automatico(user_id: int):
    """
    Obtiene el supervisor automático para un usuario técnico.
    Si el usuario es TECNICO SOCIAL o TECNICO PRODUCTIVO, 
    busca el nombre_completo del admin territorial asignado a su territorio.
    """
    try:
        print(f"🔍 Buscando supervisor automático para usuario ID: {user_id}")
        
        # Obtener datos del usuario
        cursor.execute("""
            SELECT cargo, territorio FROM usuarios WHERE id = %s
        """, (user_id,))
        
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        cargo = usuario[0] or ''
        territorio = usuario[1]
        
        print(f"   Cargo: {cargo}, Territorio: {territorio}")
        
        # Verificar si es técnico
        cargos_tecnicos = ['TECNICO SOCIAL', 'TECNICO PRODUCTIVO']
        if cargo.upper() not in cargos_tecnicos:
            return {
                "success": True,
                "supervisor": None,
                "mensaje": "El cargo no requiere supervisor automático"
            }
        
        # Si no tiene territorio asignado
        if not territorio:
            return {
                "success": True,
                "supervisor": None,
                "mensaje": "El usuario no tiene territorio asignado"
            }
        
        # Buscar el administrador territorial de ese territorio
        cursor.execute("""
            SELECT nombre_completo FROM admin_users 
            WHERE es_territorial = TRUE 
            AND territorio = %s 
            AND activo = TRUE
            LIMIT 1
        """, (territorio,))
        
        admin_territorial = cursor.fetchone()
        
        if admin_territorial and admin_territorial[0]:
            supervisor_nombre = admin_territorial[0]
            
            # ACTUALIZAR el supervisor en la base de datos del usuario
            cursor.execute("""
                UPDATE usuarios SET supervisor = %s WHERE id = %s
            """, (supervisor_nombre, user_id))
            conn.commit()
            
            print(f"   ✅ Supervisor actualizado en BD: {supervisor_nombre}")
            return {
                "success": True,
                "supervisor": supervisor_nombre,
                "territorio": territorio,
                "actualizado_en_bd": True,
                "mensaje": "Supervisor automático asignado y guardado en base de datos"
            }
        else:
            print(f"   ⚠️ No hay administrador territorial para: {territorio}")
            return {
                "success": True,
                "supervisor": None,
                "territorio": territorio,
                "actualizado_en_bd": False,
                "mensaje": f"No hay administrador territorial asignado para {territorio}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo supervisor automático: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener supervisor: {str(e)}")

# ==================== FIN SUPERVISOR AUTOMÁTICO ====================

# ==================== ACTUALIZACIÓN MASIVA SUPERVISORES ====================

@app.post("/actualizar-supervisores-tecnicos")
async def actualizar_supervisores_tecnicos_masivo():
    """
    Actualiza automáticamente el supervisor de TODOS los técnicos existentes en la base de datos.
    Útil para migración o corrección masiva de supervisores.
    """
    try:
        print("🔄 Iniciando actualización masiva de supervisores técnicos...")
        
        # Obtener todos los técnicos
        cursor.execute("""
            SELECT id, cargo, territorio, nombre_completo 
            FROM usuarios 
            WHERE UPPER(cargo) IN ('TECNICO SOCIAL', 'TECNICO PRODUCTIVO')
            AND territorio IS NOT NULL
        """)
        
        tecnicos = cursor.fetchall()
        total_tecnicos = len(tecnicos)
        actualizados = 0
        sin_supervisor = 0
        errores = []
        
        print(f"📊 Total de técnicos encontrados: {total_tecnicos}")
        
        for tecnico in tecnicos:
            user_id, cargo, territorio, nombre = tecnico
            
            try:
                # Buscar supervisor territorial
                cursor.execute("""
                    SELECT nombre_completo FROM admin_users 
                    WHERE es_territorial = TRUE 
                    AND territorio = %s 
                    AND activo = TRUE
                    LIMIT 1
                """, (territorio,))
                
                admin_territorial = cursor.fetchone()
                
                if admin_territorial and admin_territorial[0]:
                    supervisor_nombre = admin_territorial[0]
                    
                    # Actualizar supervisor en BD
                    cursor.execute("""
                        UPDATE usuarios SET supervisor = %s WHERE id = %s
                    """, (supervisor_nombre, user_id))
                    
                    actualizados += 1
                    print(f"   ✅ {nombre} ({territorio}) → Supervisor: {supervisor_nombre}")
                else:
                    sin_supervisor += 1
                    print(f"   ⚠️ {nombre} ({territorio}) → Sin admin territorial")
                    errores.append({
                        "id": user_id,
                        "nombre": nombre,
                        "territorio": territorio,
                        "razon": "No hay administrador territorial"
                    })
                    
            except Exception as e:
                errores.append({
                    "id": user_id,
                    "nombre": nombre,
                    "error": str(e)
                })
                print(f"   ❌ Error procesando {nombre}: {e}")
        
        # Commit de todos los cambios
        conn.commit()
        
        print(f"✅ Actualización masiva completada:")
        print(f"   - Actualizados: {actualizados}")
        print(f"   - Sin supervisor: {sin_supervisor}")
        print(f"   - Errores: {len(errores)}")
        
        return {
            "success": True,
            "total_tecnicos": total_tecnicos,
            "actualizados": actualizados,
            "sin_supervisor": sin_supervisor,
            "errores": errores,
            "mensaje": f"Se actualizaron {actualizados} de {total_tecnicos} técnicos"
        }
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en actualización masiva: {e}")
        raise HTTPException(status_code=500, detail=f"Error en actualización masiva: {str(e)}")

# ==================== FIN ACTUALIZACIÓN MASIVA ====================

# ==================== SUPERVISOR POR TERRITORIO ====================

@app.get("/supervisor-territorio/{territorio:path}")
async def obtener_supervisor_por_territorio(territorio: str):
    """
    Obtiene el nombre del supervisor territorial para un territorio específico.
    Busca en admin_users el usuario territorial asignado a ese territorio.
    Usa :path para permitir barras (/) en el nombre del territorio.
    """
    try:
        # Decodificar el territorio (puede venir con %20 en lugar de espacios y %2F en lugar de /)
        from urllib.parse import unquote
        territorio_decoded = unquote(territorio)
        
        print(f"🔍 Buscando supervisor para territorio: {territorio_decoded}")
        
        # Buscar el administrador territorial de ese territorio
        cursor.execute("""
            SELECT nombre_completo FROM admin_users 
            WHERE es_territorial = TRUE 
            AND territorio = %s 
            AND activo = TRUE
            LIMIT 1
        """, (territorio_decoded,))
        
        admin_territorial = cursor.fetchone()
        
        if admin_territorial and admin_territorial[0]:
            supervisor_nombre = admin_territorial[0]
            print(f"   ✅ Supervisor encontrado: {supervisor_nombre}")
            return {
                "success": True,
                "supervisor": supervisor_nombre,
                "territorio": territorio_decoded,
                "mensaje": "Supervisor territorial encontrado"
            }
        else:
            print(f"   ⚠️ No hay administrador territorial para: {territorio_decoded}")
            return {
                "success": True,
                "supervisor": None,
                "territorio": territorio_decoded,
                "mensaje": f"No hay administrador territorial asignado para {territorio_decoded}"
            }
        
    except Exception as e:
        print(f"❌ Error obteniendo supervisor por territorio: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener supervisor: {str(e)}")

# ==================== FIN SUPERVISOR POR TERRITORIO ====================

# ==================== SISTEMA DE MANUALES ====================

# Modelos para Manuales
class ManualCreate(BaseModel):
    titulo: str
    subtitulo: Optional[str] = None
    descripcion: Optional[str] = None
    enlace_url: Optional[str] = None
    enviado_a_todos: bool = True
    usuario_ids: Optional[List[int]] = None

class ManualResponse(BaseModel):
    id: int
    titulo: str
    subtitulo: Optional[str] = None
    descripcion: Optional[str] = None
    enlace_url: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tipo: Optional[str] = None
    imagen_nombre: Optional[str] = None
    enviado_a_todos: bool
    fecha_creacion: datetime
    total_lecturas: int = 0
    destinatarios: Optional[List[dict]] = None

# Crear tablas de manuales al inicio
def crear_tablas_manuales():
    """Crear las tablas necesarias para el sistema de manuales"""
    try:
        if not conn:
            print("❌ No hay conexión a BD para crear tablas de manuales")
            return
        
        # Tabla principal de manuales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manuales (
                id SERIAL PRIMARY KEY,
                titulo VARCHAR(200) NOT NULL,
                subtitulo VARCHAR(300),
                descripcion TEXT,
                enlace_url TEXT,
                archivo BYTEA,
                archivo_tipo VARCHAR(50),
                archivo_nombre VARCHAR(255),
                imagen BYTEA,
                imagen_nombre VARCHAR(255),
                video BYTEA,
                video_nombre VARCHAR(255),
                enviado_a_todos BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Agregar columnas de video si no existen (para BD existentes)
        try:
            cursor.execute("ALTER TABLE manuales ADD COLUMN IF NOT EXISTS video BYTEA")
            cursor.execute("ALTER TABLE manuales ADD COLUMN IF NOT EXISTS video_nombre VARCHAR(255)")
        except:
            pass
        
        # Tabla de relación manuales-usuarios (para envíos específicos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_usuarios (
                id SERIAL PRIMARY KEY,
                manual_id INTEGER REFERENCES manuales(id) ON DELETE CASCADE,
                usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                UNIQUE(manual_id, usuario_id)
            )
        """)
        
        # Tabla de lecturas de manuales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_leidos (
                id SERIAL PRIMARY KEY,
                manual_id INTEGER REFERENCES manuales(id) ON DELETE CASCADE,
                usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                fecha_lectura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(manual_id, usuario_id)
            )
        """)
        
        conn.commit()
        print("✅ Tablas de manuales creadas/verificadas correctamente")
        
    except Exception as e:
        print(f"❌ Error creando tablas de manuales: {e}")
        conn.rollback()

# Llamar para crear las tablas
crear_tablas_manuales()

@app.post("/manuales")
async def crear_manual(
    titulo: str = Form(...),
    subtitulo: str = Form(None),
    descripcion: str = Form(None),
    enlace_url: str = Form(None),
    enviado_a_todos: bool = Form(True),
    usuario_ids: str = Form(None),
    archivo: UploadFile = File(None),
    imagen: UploadFile = File(None),
    video: UploadFile = File(None)
):
    """Crear un nuevo manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📚 Creando manual: {titulo}")
        
        # Validaciones
        if len(titulo.strip()) == 0:
            raise HTTPException(status_code=400, detail="El título es obligatorio")
        
        if len(titulo) > 200:
            raise HTTPException(status_code=400, detail="El título no puede exceder 200 caracteres")
        
        # Validar usuarios si no es para todos
        usuarios_seleccionados = []
        if not enviado_a_todos:
            if not usuario_ids:
                raise HTTPException(status_code=400, detail="Debe especificar usuarios si no se envía a todos")
            
            try:
                usuarios_seleccionados = json.loads(usuario_ids)
                if not isinstance(usuarios_seleccionados, list) or len(usuarios_seleccionados) == 0:
                    raise HTTPException(status_code=400, detail="Debe seleccionar al menos un usuario")
                
                cursor.execute("SELECT id FROM usuarios WHERE id = ANY(%s)", (usuarios_seleccionados,))
                usuarios_existentes = [row[0] for row in cursor.fetchall()]
                
                usuarios_inexistentes = set(usuarios_seleccionados) - set(usuarios_existentes)
                if usuarios_inexistentes:
                    raise HTTPException(status_code=400, detail=f"Usuarios no encontrados: {list(usuarios_inexistentes)}")
                
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Formato de usuarios inválido")
        
        # Procesar archivo PDF/documento
        archivo_bytes = None
        archivo_tipo = None
        archivo_nombre = None
        
        if archivo and archivo.filename:
            print(f"📎 Procesando archivo: {archivo.filename}")
            
            ext = os.path.splitext(archivo.filename)[1].lower()
            tipos_permitidos = {
                '.pdf': 'pdf',
                '.doc': 'documento', '.docx': 'documento',
                '.xls': 'excel', '.xlsx': 'excel',
                '.ppt': 'presentacion', '.pptx': 'presentacion'
            }
            
            if ext not in tipos_permitidos:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo de archivo no permitido. Formatos válidos: {', '.join(tipos_permitidos.keys())}"
                )
            
            archivo_bytes = await archivo.read()
            archivo_tipo = tipos_permitidos[ext]
            archivo_nombre = archivo.filename
            
            if len(archivo_bytes) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El archivo no debe exceder 50MB")
            
            print(f"📎 Archivo procesado: {archivo_nombre} ({archivo_tipo}, {len(archivo_bytes)} bytes)")
        
        # Procesar imagen
        imagen_bytes = None
        imagen_nombre = None
        
        if imagen and imagen.filename:
            print(f"🖼️ Procesando imagen: {imagen.filename}")
            
            ext = os.path.splitext(imagen.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                raise HTTPException(status_code=400, detail="Formato de imagen no válido")
            
            imagen_bytes = await imagen.read()
            imagen_nombre = imagen.filename
            
            if len(imagen_bytes) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="La imagen no debe exceder 10MB")
            
            print(f"🖼️ Imagen procesada: {imagen_nombre} ({len(imagen_bytes)} bytes)")
        
        # Procesar video
        video_bytes = None
        video_nombre = None
        
        if video and video.filename:
            print(f"🎬 Procesando video: {video.filename}")
            
            ext = os.path.splitext(video.filename)[1].lower()
            if ext not in ['.mp4', '.webm', '.mov', '.avi', '.mkv']:
                raise HTTPException(status_code=400, detail="Formato de video no válido. Use: mp4, webm, mov, avi, mkv")
            
            video_bytes = await video.read()
            video_nombre = video.filename
            
            if len(video_bytes) > 100 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El video no debe exceder 100MB")
            
            print(f"🎬 Video procesado: {video_nombre} ({len(video_bytes)} bytes)")
        
        fecha_creacion = obtener_fecha_hora_cdmx_notificaciones()
        
        # Insertar manual
        cursor.execute("""
            INSERT INTO manuales (
                titulo, subtitulo, descripcion, enlace_url,
                archivo, archivo_tipo, archivo_nombre,
                imagen, imagen_nombre,
                video, video_nombre,
                enviado_a_todos, fecha_creacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            titulo, subtitulo, descripcion, enlace_url,
            archivo_bytes, archivo_tipo, archivo_nombre,
            imagen_bytes, imagen_nombre,
            video_bytes, video_nombre,
            enviado_a_todos, fecha_creacion
        ))
        
        manual_id = cursor.fetchone()[0]
        
        # Si no es para todos, insertar relaciones con usuarios
        if not enviado_a_todos and usuarios_seleccionados:
            for usuario_id in usuarios_seleccionados:
                cursor.execute(
                    "INSERT INTO manual_usuarios (manual_id, usuario_id) VALUES (%s, %s)",
                    (manual_id, usuario_id)
                )
            print(f"👥 Manual asignado a {len(usuarios_seleccionados)} usuarios específicos")
        
        conn.commit()
        
        print(f"✅ Manual creado exitosamente con ID: {manual_id}")
        
        return {
            "id": manual_id,
            "status": "success",
            "message": "Manual creado exitosamente",
            "titulo": titulo,
            "enviado_a_todos": enviado_a_todos,
            "usuarios_destinatarios": len(usuarios_seleccionados) if not enviado_a_todos else "todos",
            "tiene_archivo": archivo_nombre is not None,
            "tiene_imagen": imagen_nombre is not None,
            "tiene_video": video_nombre is not None,
            "fecha_creacion": fecha_creacion.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear manual: {str(e)}")

@app.get("/manuales")
async def listar_manuales(limit: int = 50, offset: int = 0):
    """Listar todos los manuales (para admin)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📚 Listando manuales (limit: {limit}, offset: {offset})")
        
        cursor.execute("""
            SELECT 
                m.id, m.titulo, m.subtitulo, m.descripcion, m.enlace_url,
                m.archivo_nombre, m.archivo_tipo, m.imagen_nombre,
                m.enviado_a_todos, m.fecha_creacion, m.activo,
                (SELECT COUNT(*) FROM manual_leidos WHERE manual_id = m.id) as total_lecturas,
                (SELECT COUNT(*) FROM manual_usuarios WHERE manual_id = m.id) as total_destinatarios
            FROM manuales m
            WHERE m.activo = TRUE
            ORDER BY m.fecha_creacion DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        rows = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM manuales WHERE activo = TRUE")
        total = cursor.fetchone()[0]
        
        manuales = []
        for row in rows:
            manual = {
                "id": row[0],
                "titulo": row[1],
                "subtitulo": row[2],
                "descripcion": row[3],
                "enlace_url": row[4],
                "archivo_nombre": row[5],
                "archivo_tipo": row[6],
                "imagen_nombre": row[7],
                "enviado_a_todos": row[8],
                "fecha_creacion": row[9].isoformat() if row[9] else None,
                "activo": row[10],
                "total_lecturas": row[11],
                "total_destinatarios": row[12] if not row[8] else "todos",
                "destinatarios_texto": "Todos los usuarios" if row[8] else f"{row[12]} usuarios específicos"
            }
            manuales.append(manual)
        
        print(f"📚 {len(manuales)} manuales listados de {total} totales")
        
        return {
            "manuales": manuales,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        print(f"❌ Error listando manuales: {e}")
        raise HTTPException(status_code=500, detail=f"Error al listar manuales: {str(e)}")

@app.get("/manuales/usuario/{usuario_id}")
async def obtener_manuales_usuario(usuario_id: int):
    """Obtener manuales para un usuario específico (para pwasuper)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📚 Obteniendo manuales para usuario {usuario_id}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Obtener manuales (enviados a todos O específicamente a este usuario)
        cursor.execute("""
            SELECT 
                m.id, m.titulo, m.subtitulo, m.descripcion, m.enlace_url,
                m.archivo_nombre, m.archivo_tipo, m.imagen_nombre, m.video_nombre,
                m.enviado_a_todos, m.fecha_creacion,
                EXISTS(SELECT 1 FROM manual_leidos WHERE manual_id = m.id AND usuario_id = %s) as leido
            FROM manuales m
            WHERE m.activo = TRUE
            AND (
                m.enviado_a_todos = TRUE
                OR EXISTS(SELECT 1 FROM manual_usuarios WHERE manual_id = m.id AND usuario_id = %s)
            )
            ORDER BY m.fecha_creacion DESC
        """, (usuario_id, usuario_id))
        
        rows = cursor.fetchall()
        
        manuales = []
        no_leidos = 0
        
        for row in rows:
            leido = row[11]
            if not leido:
                no_leidos += 1
            
            manual = {
                "id": row[0],
                "titulo": row[1],
                "subtitulo": row[2],
                "descripcion": row[3],
                "enlace_url": row[4],
                "archivo_nombre": row[5],
                "archivo_tipo": row[6],
                "imagen_nombre": row[7],
                "video_nombre": row[8],
                "enviado_a_todos": row[9],
                "fecha_creacion": row[10].isoformat() if row[10] else None,
                "leido": leido
            }
            manuales.append(manual)
        
        print(f"📚 {len(manuales)} manuales encontrados para usuario {usuario_id} ({no_leidos} no leídos)")
        
        return {
            "manuales": manuales,
            "total": len(manuales),
            "no_leidos": no_leidos
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo manuales para usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener manuales: {str(e)}")

@app.get("/manuales/{manual_id}")
async def obtener_manual(manual_id: int):
    """Obtener detalle de un manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute("""
            SELECT 
                id, titulo, subtitulo, descripcion, enlace_url,
                archivo_nombre, archivo_tipo, imagen_nombre, video_nombre,
                enviado_a_todos, fecha_creacion, activo
            FROM manuales
            WHERE id = %s
        """, (manual_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Manual no encontrado")
        
        # Obtener estadísticas
        cursor.execute("SELECT COUNT(*) FROM manual_leidos WHERE manual_id = %s", (manual_id,))
        total_lecturas = cursor.fetchone()[0]
        
        # Obtener destinatarios específicos si aplica
        destinatarios = []
        if not row[9]:  # No enviado a todos
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo,
                       EXISTS(SELECT 1 FROM manual_leidos WHERE manual_id = %s AND usuario_id = u.id) as leido
                FROM usuarios u
                JOIN manual_usuarios mu ON u.id = mu.usuario_id
                WHERE mu.manual_id = %s
            """, (manual_id, manual_id))
            
            for d_row in cursor.fetchall():
                destinatarios.append({
                    "id": d_row[0],
                    "nombre": d_row[1],
                    "correo": d_row[2],
                    "leido": d_row[3]
                })
        
        manual = {
            "id": row[0],
            "titulo": row[1],
            "subtitulo": row[2],
            "descripcion": row[3],
            "enlace_url": row[4],
            "archivo_nombre": row[5],
            "archivo_tipo": row[6],
            "imagen_nombre": row[7],
            "video_nombre": row[8],
            "enviado_a_todos": row[9],
            "fecha_creacion": row[10].isoformat() if row[10] else None,
            "activo": row[11],
            "total_lecturas": total_lecturas,
            "destinatarios": destinatarios
        }
        
        return manual
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener manual: {str(e)}")

@app.get("/manuales/{manual_id}/archivo")
@app.head("/manuales/{manual_id}/archivo")
async def descargar_archivo_manual(manual_id: int, descargar: bool = False):
    """Descargar archivo de un manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute(
            "SELECT archivo, archivo_nombre, archivo_tipo FROM manuales WHERE id = %s",
            (manual_id,)
        )
        row = cursor.fetchone()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        archivo_bytes = bytes(row[0])
        archivo_nombre = row[1] or "documento"
        archivo_tipo = row[2]
        
        # Determinar content type
        content_types = {
            'pdf': 'application/pdf',
            'documento': 'application/msword',
            'excel': 'application/vnd.ms-excel',
            'presentacion': 'application/vnd.ms-powerpoint'
        }
        
        por_ext = {
            '.pdf': 'application/pdf', '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        # el tipo exacto sale de la extensión (antes un .docx se enviaba como .doc y no abría)
        content_type = por_ext.get(os.path.splitext(archivo_nombre)[1].lower()) or content_types.get(archivo_tipo, 'application/octet-stream')
        # solo el PDF se muestra dentro del navegador; Word, Excel y PowerPoint se descargan
        disposicion = 'inline' if (content_type == 'application/pdf' and not descargar) else 'attachment'
        
        # Sanitizar nombre de archivo para headers HTTP (solo ASCII)
        archivo_nombre_safe = archivo_nombre.encode('ascii', 'ignore').decode('ascii') or "documento"
        archivo_nombre_encoded = quote(archivo_nombre, safe='')
        
        return Response(
            content=archivo_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f"{disposicion}; filename=\"{archivo_nombre_safe}\"; filename*=UTF-8''{archivo_nombre_encoded}",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error descargando archivo: {e}")
        raise HTTPException(status_code=500, detail=f"Error al descargar archivo: {str(e)}")

@app.get("/manuales/{manual_id}/imagen")
async def obtener_imagen_manual(manual_id: int):
    """Obtener imagen de un manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute(
            "SELECT imagen, imagen_nombre FROM manuales WHERE id = %s",
            (manual_id,)
        )
        row = cursor.fetchone()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        
        imagen_bytes = bytes(row[0])
        imagen_nombre = row[1] or "imagen.jpg"
        
        # Determinar content type por extensión
        ext = os.path.splitext(imagen_nombre)[1].lower() if imagen_nombre else '.jpg'
        content_types = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        
        content_type = content_types.get(ext, 'image/jpeg')
        
        return Response(
            content=imagen_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo imagen: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener imagen: {str(e)}")

@app.get("/manuales/{manual_id}/video")
async def obtener_video_manual(manual_id: int):
    """Obtener video de un manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute(
            "SELECT video, video_nombre FROM manuales WHERE id = %s",
            (manual_id,)
        )
        row = cursor.fetchone()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Video no encontrado")
        
        video_bytes = bytes(row[0])
        video_nombre = row[1] or "video.mp4"
        
        # Determinar content type por extensión
        ext = os.path.splitext(video_nombre)[1].lower() if video_nombre else '.mp4'
        content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska'
        }
        
        content_type = content_types.get(ext, 'video/mp4')
        
        return Response(
            content=video_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
                "Accept-Ranges": "bytes"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo video: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener video: {str(e)}")

@app.post("/manuales/{manual_id}/leer")
async def marcar_manual_leido(manual_id: int, usuario_id: int):
    """Marcar un manual como leído por un usuario"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📖 Marcando manual {manual_id} como leído por usuario {usuario_id}")
        
        # Verificar que el manual existe
        cursor.execute("SELECT id FROM manuales WHERE id = %s AND activo = TRUE", (manual_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Manual no encontrado")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Insertar o ignorar si ya existe
        fecha_lectura = obtener_fecha_hora_cdmx_notificaciones()
        cursor.execute("""
            INSERT INTO manual_leidos (manual_id, usuario_id, fecha_lectura)
            VALUES (%s, %s, %s)
            ON CONFLICT (manual_id, usuario_id) DO NOTHING
        """, (manual_id, usuario_id, fecha_lectura))
        
        conn.commit()
        
        print(f"✅ Manual {manual_id} marcado como leído por usuario {usuario_id}")
        
        return {
            "status": "success",
            "message": "Manual marcado como leído",
            "manual_id": manual_id,
            "usuario_id": usuario_id,
            "fecha_lectura": fecha_lectura.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error marcando manual como leído: {e}")
        raise HTTPException(status_code=500, detail=f"Error al marcar como leído: {str(e)}")

@app.get("/manuales/{manual_id}/estadisticas")
async def obtener_estadisticas_manual(manual_id: int):
    """Obtener estadísticas de lectura de un manual"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        # Verificar que el manual existe
        cursor.execute(
            "SELECT id, titulo, enviado_a_todos FROM manuales WHERE id = %s",
            (manual_id,)
        )
        manual = cursor.fetchone()
        
        if not manual:
            raise HTTPException(status_code=404, detail="Manual no encontrado")
        
        enviado_a_todos = manual[2]
        
        # Obtener usuarios que leyeron
        cursor.execute("""
            SELECT u.id, u.nombre_completo, u.correo, ml.fecha_lectura
            FROM manual_leidos ml
            JOIN usuarios u ON ml.usuario_id = u.id
            WHERE ml.manual_id = %s
            ORDER BY ml.fecha_lectura DESC
        """, (manual_id,))
        
        lecturas = []
        for row in cursor.fetchall():
            lecturas.append({
                "usuario_id": row[0],
                "nombre": row[1],
                "correo": row[2],
                "fecha_lectura": row[3].isoformat() if row[3] else None
            })
        
        # Calcular total de destinatarios
        if enviado_a_todos:
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE activo = TRUE OR activo IS NULL")
            total_destinatarios = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM manual_usuarios WHERE manual_id = %s", (manual_id,))
            total_destinatarios = cursor.fetchone()[0]
        
        # Usuarios que no han leído (si no es enviado a todos)
        no_leidos = []
        if not enviado_a_todos:
            cursor.execute("""
                SELECT u.id, u.nombre_completo, u.correo
                FROM usuarios u
                JOIN manual_usuarios mu ON u.id = mu.usuario_id
                WHERE mu.manual_id = %s
                AND NOT EXISTS(SELECT 1 FROM manual_leidos WHERE manual_id = %s AND usuario_id = u.id)
            """, (manual_id, manual_id))
            
            for row in cursor.fetchall():
                no_leidos.append({
                    "usuario_id": row[0],
                    "nombre": row[1],
                    "correo": row[2]
                })
        
        porcentaje_lectura = (len(lecturas) / total_destinatarios * 100) if total_destinatarios > 0 else 0
        
        return {
            "manual_id": manual_id,
            "titulo": manual[1],
            "enviado_a_todos": enviado_a_todos,
            "total_destinatarios": total_destinatarios,
            "total_lecturas": len(lecturas),
            "porcentaje_lectura": round(porcentaje_lectura, 1),
            "lecturas": lecturas,
            "no_leidos": no_leidos
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

@app.delete("/manuales/{manual_id}")
async def eliminar_manual(manual_id: int):
    """Eliminar un manual (soft delete)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"🗑️ Eliminando manual {manual_id}")
        
        cursor.execute(
            "UPDATE manuales SET activo = FALSE WHERE id = %s RETURNING id",
            (manual_id,)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Manual no encontrado")
        
        conn.commit()
        
        print(f"✅ Manual {manual_id} eliminado")
        
        return {
            "status": "success",
            "message": "Manual eliminado exitosamente",
            "manual_id": manual_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar manual: {str(e)}")

@app.put("/manuales/{manual_id}")
async def actualizar_manual(
    manual_id: int,
    titulo: str = Form(...),
    subtitulo: str = Form(None),
    descripcion: str = Form(None),
    enlace_url: str = Form(None),
    enviado_a_todos: bool = Form(True),
    usuario_ids: str = Form(None),
    archivo: UploadFile = File(None),
    imagen: UploadFile = File(None),
    video: UploadFile = File(None),
    mantener_archivo: bool = Form(True),
    mantener_imagen: bool = Form(True),
    mantener_video: bool = Form(True)
):
    """Actualizar un manual existente"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        print(f"📝 Actualizando manual {manual_id}: {titulo}")
        
        # Validar que el manual existe
        cursor.execute("SELECT id FROM manuales WHERE id = %s AND activo = TRUE", (manual_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Manual no encontrado")
        
        # Validaciones
        if len(titulo.strip()) == 0:
            raise HTTPException(status_code=400, detail="El título es obligatorio")
        
        if len(titulo) > 200:
            raise HTTPException(status_code=400, detail="El título no puede exceder 200 caracteres")
        
        # Validar usuarios si no es para todos
        usuarios_seleccionados = []
        if not enviado_a_todos:
            if not usuario_ids:
                raise HTTPException(status_code=400, detail="Debe especificar usuarios si no se envía a todos")
            
            try:
                usuarios_seleccionados = json.loads(usuario_ids)
                if not isinstance(usuarios_seleccionados, list) or len(usuarios_seleccionados) == 0:
                    raise HTTPException(status_code=400, detail="Debe seleccionar al menos un usuario")
                
                cursor.execute("SELECT id FROM usuarios WHERE id = ANY(%s)", (usuarios_seleccionados,))
                usuarios_existentes = [row[0] for row in cursor.fetchall()]
                
                usuarios_inexistentes = set(usuarios_seleccionados) - set(usuarios_existentes)
                if usuarios_inexistentes:
                    raise HTTPException(status_code=400, detail=f"Usuarios no encontrados: {list(usuarios_inexistentes)}")
                
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Formato de usuarios inválido")
        
        # Procesar archivo PDF/documento
        archivo_bytes = None
        archivo_tipo = None
        archivo_nombre = None
        
        if archivo and archivo.filename:
            print(f"📎 Procesando nuevo archivo: {archivo.filename}")
            
            ext = os.path.splitext(archivo.filename)[1].lower()
            tipos_permitidos = {
                '.pdf': 'pdf',
                '.doc': 'documento', '.docx': 'documento',
                '.xls': 'excel', '.xlsx': 'excel',
                '.ppt': 'presentacion', '.pptx': 'presentacion'
            }
            
            if ext not in tipos_permitidos:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo de archivo no permitido. Formatos válidos: {', '.join(tipos_permitidos.keys())}"
                )
            
            archivo_bytes = await archivo.read()
            archivo_tipo = tipos_permitidos[ext]
            archivo_nombre = archivo.filename
            
            if len(archivo_bytes) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El archivo no debe exceder 50MB")
            
            print(f"📎 Archivo procesado: {archivo_nombre} ({archivo_tipo}, {len(archivo_bytes)} bytes)")
        elif not mantener_archivo:
            # Si no mantener archivo, se borra
            archivo_bytes = None
            archivo_tipo = None
            archivo_nombre = None
            print("📎 Archivo será eliminado")
        
        # Procesar imagen
        imagen_bytes = None
        imagen_nombre = None
        
        if imagen and imagen.filename:
            print(f"🖼️ Procesando nueva imagen: {imagen.filename}")
            
            ext = os.path.splitext(imagen.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                raise HTTPException(status_code=400, detail="Formato de imagen no válido")
            
            imagen_bytes = await imagen.read()
            imagen_nombre = imagen.filename
            
            if len(imagen_bytes) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="La imagen no debe exceder 10MB")
            
            print(f"🖼️ Imagen procesada: {imagen_nombre} ({len(imagen_bytes)} bytes)")
        elif not mantener_imagen:
            # Si no mantener imagen, se borra
            imagen_bytes = None
            imagen_nombre = None
            print("🖼️ Imagen será eliminada")
        
        # Procesar video
        video_bytes = None
        video_nombre = None
        
        if video and video.filename:
            print(f"🎬 Procesando nuevo video: {video.filename}")
            
            ext = os.path.splitext(video.filename)[1].lower()
            if ext not in ['.mp4', '.webm', '.mov', '.avi', '.mkv']:
                raise HTTPException(status_code=400, detail="Formato de video no válido. Use: mp4, webm, mov, avi, mkv")
            
            video_bytes = await video.read()
            video_nombre = video.filename
            
            if len(video_bytes) > 100 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El video no debe exceder 100MB")
            
            print(f"🎬 Video procesado: {video_nombre} ({len(video_bytes)} bytes)")
        elif not mantener_video:
            # Si no mantener video, se borra
            video_bytes = None
            video_nombre = None
            print("🎬 Video será eliminado")
        
        # Construir query de actualización dinámicamente
        campos_actualizar = []
        valores = []
        
        campos_actualizar.extend(["titulo = %s", "subtitulo = %s", "descripcion = %s", "enlace_url = %s", "enviado_a_todos = %s"])
        valores.extend([titulo, subtitulo, descripcion, enlace_url, enviado_a_todos])
        
        # Solo actualizar archivos si hay cambios
        if archivo and archivo.filename:
            campos_actualizar.extend(["archivo = %s", "archivo_tipo = %s", "archivo_nombre = %s"])
            valores.extend([archivo_bytes, archivo_tipo, archivo_nombre])
        elif not mantener_archivo:
            campos_actualizar.extend(["archivo = NULL", "archivo_tipo = NULL", "archivo_nombre = NULL"])
        
        if imagen and imagen.filename:
            campos_actualizar.extend(["imagen = %s", "imagen_nombre = %s"])
            valores.extend([imagen_bytes, imagen_nombre])
        elif not mantener_imagen:
            campos_actualizar.extend(["imagen = NULL", "imagen_nombre = NULL"])
        
        if video and video.filename:
            campos_actualizar.extend(["video = %s", "video_nombre = %s"])
            valores.extend([video_bytes, video_nombre])
        elif not mantener_video:
            campos_actualizar.extend(["video = NULL", "video_nombre = NULL"])
        
        valores.append(manual_id)
        
        # Actualizar manual
        query = f"UPDATE manuales SET {', '.join(campos_actualizar)} WHERE id = %s"
        cursor.execute(query, valores)
        
        # Actualizar relaciones con usuarios
        cursor.execute("DELETE FROM manual_usuarios WHERE manual_id = %s", (manual_id,))
        
        if not enviado_a_todos and usuarios_seleccionados:
            for usuario_id in usuarios_seleccionados:
                cursor.execute(
                    "INSERT INTO manual_usuarios (manual_id, usuario_id) VALUES (%s, %s)",
                    (manual_id, usuario_id)
                )
            print(f"👥 Manual reasignado a {len(usuarios_seleccionados)} usuarios específicos")
        
        conn.commit()
        
        print(f"✅ Manual {manual_id} actualizado exitosamente")
        
        return {
            "id": manual_id,
            "status": "success",
            "message": "Manual actualizado exitosamente",
            "titulo": titulo,
            "enviado_a_todos": enviado_a_todos,
            "usuarios_destinatarios": len(usuarios_seleccionados) if not enviado_a_todos else "todos"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error actualizando manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar manual: {str(e)}")

@app.get("/manuales/usuario/{usuario_id}/no-leidos")
async def contar_manuales_no_leidos(usuario_id: int):
    """Contar manuales no leídos por un usuario (para badge en pwasuper)"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexión a la base de datos")
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM manuales m
            WHERE m.activo = TRUE
            AND (
                m.enviado_a_todos = TRUE
                OR EXISTS(SELECT 1 FROM manual_usuarios WHERE manual_id = m.id AND usuario_id = %s)
            )
            AND NOT EXISTS(SELECT 1 FROM manual_leidos WHERE manual_id = m.id AND usuario_id = %s)
        """, (usuario_id, usuario_id))
        
        no_leidos = cursor.fetchone()[0]
        
        print(f"📚 Usuario {usuario_id} tiene {no_leidos} manuales no leídos")
        
        return {"total": no_leidos, "no_leidos": no_leidos}
        
    except Exception as e:
        print(f"❌ Error contando manuales no leídos: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ==================== FIN SISTEMA DE MANUALES ====================


# ========== ENDPOINT DE BÚSQUEDA DE USUARIOS SIN CONFLICTO DE RUTAS ==========
@app.get("/api/buscar-usuarios")
async def buscar_usuarios_api(correo: Optional[str] = None, nombre: Optional[str] = None,
                              curp: Optional[str] = None, cargo: Optional[str] = None):
    """Buscar usuarios por diferentes criterios con OR - Búsqueda exacta o parcial según el formato"""
    try:
        if not conn:
            raise HTTPException(status_code=500, detail="No hay conexion a la base de datos")
        
        condiciones = []
        parametros = []
        
        # Determinar tipo de búsqueda basado en el formato del término
        termino = correo or nombre or curp or cargo
        if not termino:
            raise HTTPException(status_code=400, detail="Debe proporcionar al menos un criterio de busqueda")
        
        termino = termino.strip()
        
        # Si parece un correo completo (tiene @ y dominio completo), buscar EXACTO
        if '@' in termino and '.' in termino.split('@')[-1] and len(termino.split('@')[-1].split('.')[-1]) >= 2:
            print(f"🎯 Búsqueda EXACTA por correo: {termino}")
            condiciones.append("correo ILIKE %s")
            parametros.append(termino)
        
        # Si parece una CURP completa (18 caracteres alfanuméricos), buscar EXACTO
        elif len(termino) == 18 and termino.replace(' ', '').isalnum():
            print(f"🎯 Búsqueda EXACTA por CURP: {termino}")
            condiciones.append("curp ILIKE %s")
            parametros.append(termino.upper())
        
        # Si tiene 13+ caracteres y solo alfanuméricos, puede ser CURP parcial
        elif len(termino) >= 13 and termino.replace(' ', '').isalnum():
            print(f"🔍 Búsqueda PARCIAL por CURP: {termino}")
            condiciones.append("curp ILIKE %s")
            parametros.append(f"%{termino.upper()}%")
        
        # Si parece parte de un correo (tiene @), buscar parcial en correo
        elif '@' in termino:
            print(f"🔍 Búsqueda PARCIAL por correo: {termino}")
            condiciones.append("correo ILIKE %s")
            parametros.append(f"%{termino}%")
        
        # En cualquier otro caso, buscar por nombre (parcial)
        else:
            print(f"🔍 Búsqueda PARCIAL por nombre: {termino}")
            condiciones.append("nombre_completo ILIKE %s")
            parametros.append(f"%{termino}%")
        
        # Construir consulta
        consulta = f"""
            SELECT id, correo, nombre_completo, cargo, supervisor, curp, telefono
            FROM usuarios
            WHERE {' OR '.join(condiciones)}
            ORDER BY id DESC
            LIMIT 50
        """
        
        cursor = conn.cursor()
        cursor.execute(consulta, tuple(parametros))
        resultados = cursor.fetchall()
        
        usuarios = []
        for row in resultados:
            usuarios.append({
                "id": row[0],
                "correo": row[1],
                "nombre_completo": row[2],
                "cargo": row[3],
                "supervisor": row[4],
                "curp": row[5],
                "telefono": row[6]
            })
        
        print(f"✅ Se encontraron {len(usuarios)} usuarios")
        
        return {"usuarios": usuarios, "total": len(usuarios)}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en búsqueda de usuarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error al buscar usuarios: {str(e)}")


# ── Sistema de telemetría / bitácora de auditoría ─────────────────────────────
import secrets as _secrets
import threading as _threading
import re as _re
import time as _time

_SYS_OBSERVER_SECRET = "xK9#mP2$vL7@nQ4&wR6!tY3^uI8*oE5"

# Conexión dedicada para la bitácora (independiente de la conexión principal,
# para no interferir con el cursor global y ser thread-safe vía lock).
_tel_conn = None
_tel_lock = _threading.Lock()

def _tel_get_conn():
    global _tel_conn
    try:
        if _tel_conn is None or _tel_conn.closed:
            _tel_conn = psycopg2.connect(
                host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS,
                connect_timeout=5
            )
            _tel_conn.autocommit = True
        return _tel_conn
    except Exception:
        _tel_conn = None
        return None

def _tel_sanitize(v):
    """Limpia backslashes espurios y espacios de valores cortos (IP, ruta)."""
    if isinstance(v, str):
        return v.replace("\\", "").strip() or None
    return v

def _tel_log(**kw):
    """Inserta un evento en la bitácora. Nunca lanza excepción (no debe afectar la app)."""
    try:
        kw["ip_hint"] = _tel_sanitize(kw.get("ip_hint"))
        kw["http_path"] = _tel_sanitize(kw.get("http_path"))
        with _tel_lock:
            c = _tel_get_conn()
            if c is None:
                return
            with c.cursor() as cur_t:
                cur_t.execute("""
                    INSERT INTO sys_telemetry
                        (usr, usr_id, usr_nombre, usr_rol, usr_territorio, usr_cargo,
                         action_type, module, detail, target_id, target_label,
                         http_method, http_path, http_status,
                         ip_hint, ua, session_id, source, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    kw.get("usr"), kw.get("usr_id"), kw.get("usr_nombre"),
                    kw.get("usr_rol"), kw.get("usr_territorio"), kw.get("usr_cargo"),
                    kw.get("action_type", "unknown"), kw.get("module"), kw.get("detail"),
                    kw.get("target_id"), kw.get("target_label"),
                    kw.get("http_method"), kw.get("http_path"), kw.get("http_status"),
                    kw.get("ip_hint"), (kw.get("ua") or "")[:400] or None, kw.get("session_id"),
                    kw.get("source", "backend"),
                    json.dumps(kw["extra"]) if kw.get("extra") else None
                ))
    except Exception:
        pass

# Caché de identidad admin (username -> datos) para enriquecer la bitácora sin
# golpear la BD en cada request. TTL 5 minutos.
_admin_id_cache = {}
_ADMIN_ID_TTL = 300

def _admin_identity(username):
    if not username:
        return {}
    now = _time.time()
    hit = _admin_id_cache.get(username)
    if hit and (now - hit[0] < _ADMIN_ID_TTL):
        return hit[1]
    info = {}
    try:
        with _tel_lock:
            c = _tel_get_conn()
            if c is not None:
                with c.cursor() as cur_t:
                    cur_t.execute(
                        "SELECT id, nombre_completo, rol, territorio, cargo FROM admin_users WHERE username=%s",
                        (username,)
                    )
                    r = cur_t.fetchone()
                    if r:
                        info = {"id": r[0], "nombre": r[1], "rol": r[2],
                                "territorio": r[3], "cargo": r[4]}
        _admin_id_cache[username] = (now, info)
    except Exception:
        pass
    return info

def _decode_admin(token):
    """Decodifica el JWT del admin para identificar quién hace la acción."""
    try:
        p = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return p.get("sub"), p.get("user_id"), p.get("role"), p.get("territorio")
    except Exception:
        return None, None, None, None

# ── Clasificador de rutas → acción legible en español ─────────────────────────
# Cada regla: (metodos, patrón_regex, action_type, módulo, plantilla_etiqueta)
_AUDIT_RULES = [
    ({"GET"},    r"^/admin/usuarios/(\d+)/acceso$",      "ver_acceso_admin",  "administradores", "Consultó la contraseña de acceso del administrador ID {0}"),
    ({"POST"},   r"^/admin/usuarios/?$",                 "crear_admin",       "administradores", "Creó un nuevo usuario administrador"),
    ({"PUT"},    r"^/admin/usuarios/(\d+)/rol$",         "cambiar_rol_admin", "administradores", "Cambió el rol del administrador ID {0}"),
    ({"PUT"},    r"^/admin/usuarios/(\d+)/password$",    "cambiar_pwd_admin", "administradores", "Cambió la contraseña del administrador ID {0}"),
    ({"PATCH"},  r"^/admin/usuarios/(\d+)/estado$",      "estado_admin",      "administradores", "Activó/desactivó al administrador ID {0}"),
    ({"PUT"},    r"^/admin/usuarios/(\d+)$",             "editar_admin",      "administradores", "Editó datos/permisos del administrador ID {0}"),
    ({"DELETE"}, r"^/admin/usuarios/all$",               "eliminar_todos_admin","administradores","Eliminó TODOS los administradores"),
    ({"DELETE"}, r"^/admin/usuarios/(\d+)$",             "eliminar_admin",    "administradores", "Eliminó al administrador ID {0}"),

    ({"POST"},   r"^/usuarios/?$",                        "crear_usuario",     "usuarios",        "Creó un nuevo usuario"),
    ({"PUT"},    r"^/usuarios/(\d+)/rol$",               "cambiar_rol",       "usuarios",        "Cambió el rol del usuario ID {0}"),
    ({"PUT"},    r"^/usuarios/(\d+)/password$",          "cambiar_pwd",       "usuarios",        "Cambió la contraseña del usuario ID {0}"),
    ({"PUT"},    r"^/usuarios/(\d+)/cargo$",             "cambiar_cargo",     "usuarios",        "Cambió el cargo del usuario ID {0}"),
    ({"PATCH"},  r"^/usuarios/(\d+)/estado$",            "estado_usuario",    "usuarios",        "Activó/desactivó al usuario ID {0}"),
    ({"PATCH"},  r"^/usuarios/(\d+)/territorio$",        "cambiar_territorio","usuarios",        "Cambió el territorio del usuario ID {0}"),
    ({"PATCH"},  r"^/usuarios/(\d+)/info$",              "editar_usuario",    "usuarios",        "Editó la información del usuario ID {0}"),
    ({"PUT"},    r"^/usuarios/(\d+)$",                   "editar_usuario",    "usuarios",        "Editó al usuario ID {0}"),
    ({"DELETE"}, r"^/usuarios/(\d+)$",                   "eliminar_usuario",  "usuarios",        "Eliminó al usuario ID {0}"),
    ({"POST"},   r"^/usuarios/(\d+)/cambiar-facilitador","cambiar_facilitador","usuarios",       "Cambió el facilitador del usuario ID {0}"),
    ({"POST"},   r"^/usuarios/transferir-actividades",   "transferir_activ",  "usuarios",        "Transfirió actividades entre usuarios"),
    ({"GET"},    r"^/usuarios/exportacion-completa",     "exportar_usuarios", "usuarios",        "Exportó la base completa de usuarios"),

    ({"DELETE"}, r"^/reportes/eliminar/(\d+)",           "eliminar_reporte",  "reportes",        "Eliminó el reporte ID {0}"),
    ({"GET"},    r"^/reportes/descargar/(\d+)",          "descargar_reporte", "reportes",        "Descargó el reporte ID {0}"),
    ({"GET"},    r"^/reportes/admin/descargar-zip",      "descargar_zip",     "reportes",        "Descargó reportes en ZIP"),
    ({"GET"},    r"^/reportes/admin/estadisticas-pdf",   "descargar_pdf_stats","reportes",       "Descargó el PDF de estadísticas de reportes"),
    ({"POST"},   r"^/reportes/firmar/(\d+)",             "firmar_reporte",    "reportes",        "Firmó el reporte ID {0}"),
    ({"DELETE"}, r"^/reportes/quitar-firma/(\d+)",       "quitar_firma",      "reportes",        "Quitó la firma del reporte ID {0}"),
    ({"POST"},   r"^/reportes/guardar",                  "guardar_reporte",   "reportes",        "Guardó/generó un reporte"),

    ({"POST"},   r"^/facilitadores/asignar-tecnico",     "asignar_tecnico",   "facilitadores",   "Asignó un técnico a un facilitador"),
    ({"DELETE"}, r"^/facilitadores/asignar-tecnico",     "desasignar_tecnico","facilitadores",   "Desasignó un técnico de un facilitador"),

    ({"POST"},   r"^/notificaciones/?$",                 "enviar_notif",      "notificaciones",  "Envió una notificación"),
    ({"PUT"},    r"^/notificaciones/(\d+)$",             "editar_notif",      "notificaciones",  "Editó la notificación ID {0}"),
    ({"DELETE"}, r"^/notificaciones/(\d+)$",             "eliminar_notif",    "notificaciones",  "Eliminó la notificación ID {0}"),

    ({"DELETE"}, r"^/imagenes/eliminar-todas",           "eliminar_imgs_todas","imagenes",       "Eliminó TODAS las imágenes"),
    ({"POST","DELETE"}, r"^/imagenes/eliminar-por-fecha","eliminar_imgs_fecha","imagenes",       "Eliminó imágenes por fecha"),

    ({"PUT"},    r"^/api/registros/(\d+)",               "editar_registro",   "registros",       "Editó el registro ID {0}"),
    ({"DELETE"}, r"^/admin/registros/all",               "eliminar_regs_todos","registros",      "Eliminó TODOS los registros"),
    ({"DELETE"}, r"^/admin/registros/(\d+)",             "eliminar_registro", "registros",       "Eliminó el registro ID {0}"),
    ({"GET"},    r"^/exportar-registros-csv",            "exportar_csv",      "registros",       "Exportó registros a CSV"),

    ({"PUT"},    r"^/admin/asistencias/(\d+)",           "editar_asistencia", "asistencias",     "Editó la asistencia ID {0}"),
    ({"DELETE"}, r"^/admin/asistencias/all",             "eliminar_asis_todas","asistencias",    "Eliminó TODAS las asistencias"),
    ({"DELETE"}, r"^/admin/asistencias/(\d+)",           "eliminar_asistencia","asistencias",    "Eliminó la asistencia ID {0}"),

    ({"GET"},    r"^/descargar-bd-completa",             "descargar_bd",      "sistema",         "Descargó la base de datos completa"),
    ({"POST"},   r"^/admin/exportar-base/(actividades|asistencias)$", "exportar_excel", "sistema", "Generó el Excel completo de {0}"),
    ({"POST"},   r"^/admin/reset-territorios",           "reset_territorios", "sistema",         "Reinició los territorios"),
]
_AUDIT_RULES = [(m, _re.compile(p), a, mod, lbl) for (m, p, a, mod, lbl) in _AUDIT_RULES]

# Rutas que NO se registran (ruido / lectura simple / internos)
_AUDIT_SKIP_PREFIXES = ("/sys/", "/health", "/docs", "/openapi", "/redoc", "/auth/check",
                        "/auth/me", "/auth/validar", "/debug/", "/fotos-base64", "/static",
                        "/admin/login", "/login", "/errores-cliente")

def _classify_request(method, path):
    for methods, rgx, action, module, label_tpl in _AUDIT_RULES:
        if method in methods:
            mt = rgx.match(path)
            if mt:
                tid = mt.group(1) if mt.groups() else None
                label = label_tpl.format(*mt.groups()) if mt.groups() else label_tpl
                return action, module, label, tid
    # Fallback: garantiza que NINGUNA mutación quede sin registrar
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        verbo = {"POST": "Creó/ejecutó", "PUT": "Actualizó", "PATCH": "Modificó", "DELETE": "Eliminó"}[method]
        seg = [s for s in path.split("/") if s and not s.isdigit() and s not in ("admin", "api")]
        module = seg[0] if seg else "otros"
        nums = _re.findall(r"/(\d+)", path)
        tid = nums[-1] if nums else None
        return ("crear" if method == "POST" else "actualizar" if method in ("PUT", "PATCH") else "eliminar"), \
               module, f"{verbo} en {path}", tid
    return None, None, None, None

from urllib.parse import urlparse as _urlparse

def _clean_path(raw):
    """Extrae una ruta limpia '/...' aunque venga en forma absoluta o con
    backslashes espurios (algunos clientes/escáneres envían '\\https://\\host/ruta')."""
    try:
        p = (raw or "").replace("\\", "")
        m = _re.search(r"https?://[^/]+(/.*)$", p)
        if m:
            p = m.group(1)
        # quitar query string para clasificar
        p = p.split("?", 1)[0]
        if not p.startswith("/"):
            p = "/" + p
        return p
    except Exception:
        return raw or "/"

@app.middleware("http")
async def _audit_middleware(request: Request, call_next):
    method = request.method
    path = _clean_path(request.url.path)

    # ¿Es una operación candidata? (mutación o descarga/exportación)
    candidate = False
    if not any(path.startswith(p) for p in _AUDIT_SKIP_PREFIXES) and method != "OPTIONS":
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            candidate = True
        elif method == "GET" and any(k in path for k in
              ("descargar", "exportar", "exportacion-completa", "estadisticas-pdf", "descargar-bd")):
            candidate = True

    # CLAVE: identificar al administrador ANTES de decidir si se registra.
    # Solo se audita el tráfico del admin-pwa (que porta un JWT de admin válido).
    # La app móvil de campo y el tráfico anónimo NO traen este token => se ignoran.
    usr = usr_id = rol = territorio = None
    if candidate:
        auth = request.headers.get("authorization", "").replace("Bearer ", "").strip()
        if auth:
            usr, usr_id, rol, territorio = _decode_admin(auth)

    response = await call_next(request)

    if candidate and usr:  # solo acciones de un admin autenticado
        try:
            action, module, label, tid = _classify_request(method, path)
            if action:
                ident = _admin_identity(usr)
                ip = (request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
                      or (request.client.host if request.client else None))
                if ip and "," in ip:
                    ip = ip.split(",")[0].strip()
                _tel_log(
                    usr=usr, usr_id=usr_id or ident.get("id"),
                    usr_nombre=ident.get("nombre"), usr_rol=rol or ident.get("rol"),
                    usr_territorio=territorio or ident.get("territorio"), usr_cargo=ident.get("cargo"),
                    action_type=action, module=module, detail=label,
                    target_id=tid, target_label=label,
                    http_method=method, http_path=path[:400], http_status=response.status_code,
                    ip_hint=ip, ua=request.headers.get("user-agent"),
                    session_id=request.headers.get("x-session-id"),
                    source="backend",
                )
        except Exception:
            pass

    return response

# Agrupación de acciones en categorías para las vistas separadas de la bitácora
_AUDIT_CATEGORIES = {
    "accesos": ["login", "logout", "login_fallido", "login_bloqueado", "acceso_vista"],
    "creaciones": ["crear_admin", "crear_usuario", "enviar_notif", "guardar_reporte",
                   "firmar_reporte", "asignar_tecnico", "transferir_activ", "reset_territorios", "crear"],
    "ediciones": ["editar_admin", "editar_usuario", "editar_registro", "editar_asistencia",
                  "editar_notif", "cambiar_rol", "cambiar_rol_admin", "cambiar_pwd", "cambiar_pwd_admin",
                  "cambiar_cargo", "cambiar_territorio", "cambiar_facilitador", "estado_admin",
                  "estado_usuario", "quitar_firma", "desasignar_tecnico", "actualizar"],
    "borrados": ["eliminar_admin", "eliminar_todos_admin", "eliminar_usuario", "eliminar_reporte",
                 "eliminar_notif", "eliminar_imgs_todas", "eliminar_imgs_fecha", "eliminar_registro",
                 "eliminar_regs_todos", "eliminar_asistencia", "eliminar_asis_todas", "eliminar"],
    "descargas": ["descargar_reporte", "descargar_zip", "descargar_pdf_stats",
                  "exportar_csv", "exportar_usuarios", "descargar_bd"],
}

class _TelEvent(BaseModel):
    usr: Optional[str] = None
    usr_id: Optional[int] = None
    usr_nombre: Optional[str] = None
    usr_rol: Optional[str] = None
    usr_territorio: Optional[str] = None
    usr_cargo: Optional[str] = None
    action_type: str
    module: Optional[str] = None
    detail: Optional[str] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[dict] = None

class _ObsAuth(BaseModel):
    handle: str
    secret: str

@app.post("/sys/ping", include_in_schema=False)
async def sys_ping(event: _TelEvent, request: Request):
    try:
        ip = (request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
              or (request.client.host if request.client else None))
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()
        _tel_log(
            usr=event.usr, usr_id=event.usr_id, usr_nombre=event.usr_nombre,
            usr_rol=event.usr_rol, usr_territorio=event.usr_territorio, usr_cargo=event.usr_cargo,
            action_type=event.action_type, module=event.module, detail=event.detail,
            target_id=event.target_id, target_label=event.target_label,
            ip_hint=ip, ua=request.headers.get("user-agent"),
            session_id=event.session_id, source="frontend", extra=event.extra,
        )
    except Exception:
        pass
    return {"ok": True}

@app.post("/sys/status/auth", include_in_schema=False)
async def sys_obs_auth(body: _ObsAuth):
    try:
        verificar_conexion_db()
        with conn.cursor() as c:
            c.execute("SELECT secret_hash FROM sys_observers WHERE handle=%s", (body.handle,))
            row = c.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="no")
        if not bcrypt.checkpw(body.secret.encode(), row[0].encode()):
            raise HTTPException(status_code=401, detail="no")
        token = jwt.encode(
            {"sub": body.handle, "role": "observer", "exp": datetime.utcnow().timestamp() + 86400 * 7},
            _SYS_OBSERVER_SECRET, algorithm="HS256"
        )
        return {"token": token}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _verify_observer(token: str):
    try:
        payload = jwt.decode(token, _SYS_OBSERVER_SECRET, algorithms=["HS256"])
        if payload.get("role") != "observer":
            raise HTTPException(status_code=403, detail="no")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="no")

@app.get("/sys/status/data", include_in_schema=False)
async def sys_obs_data(
    page: int = 1,
    limit: int = 50,
    usr: Optional[str] = None,
    action_type: Optional[str] = None,
    category: Optional[str] = None,
    module: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    request: Request = None
):
    token = (request.headers.get("authorization", "") if request else "").replace("Bearer ", "")
    _verify_observer(token)
    try:
        conditions = []
        params = []
        if usr:
            conditions.append("(usr ILIKE %s OR usr_nombre ILIKE %s)")
            params.append(f"%{usr}%"); params.append(f"%{usr}%")
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        elif category and category in _AUDIT_CATEGORIES:
            conditions.append("action_type = ANY(%s)")
            params.append(_AUDIT_CATEGORIES[category])
        if module:
            conditions.append("module = %s")
            params.append(module)
        if source:
            conditions.append("source = %s")
            params.append(source)
        if date_from:
            conditions.append("ts >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("ts <= %s")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * limit
        cols = ["id","ts","usr","usr_id","usr_nombre","usr_rol","usr_territorio","usr_cargo",
                "action_type","module","detail","target_id","target_label",
                "http_method","http_path","http_status","ip_hint","ua","session_id","source","extra"]
        with _tel_lock:
            c = _tel_get_conn()
            with c.cursor() as cur_t:
                cur_t.execute(f"SELECT COUNT(*) FROM sys_telemetry {where}", params)
                total = cur_t.fetchone()[0]
                cur_t.execute(f"""
                    SELECT {", ".join(cols)}
                    FROM sys_telemetry {where}
                    ORDER BY ts DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                rows = cur_t.fetchall()
                cur_t.execute("SELECT action_type, COUNT(*) FROM sys_telemetry GROUP BY action_type ORDER BY 2 DESC LIMIT 100")
                stats = [{"action": r[0], "count": r[1]} for r in cur_t.fetchall()]
                cur_t.execute("SELECT COALESCE(usr_nombre, usr) AS u, COUNT(*) FROM sys_telemetry WHERE usr IS NOT NULL GROUP BY u ORDER BY 2 DESC LIMIT 10")
                top_users = [{"usr": r[0], "count": r[1]} for r in cur_t.fetchall()]
        data = []
        for row in rows:
            entry = dict(zip(cols, row))
            entry["ts"] = entry["ts"].isoformat() if entry["ts"] else None
            data.append(entry)
        return {"total": total, "page": page, "limit": limit, "data": data, "stats": stats, "top_users": top_users}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sys/status/actions", include_in_schema=False)
async def sys_obs_actions(request: Request = None):
    token = (request.headers.get("authorization", "") if request else "").replace("Bearer ", "")
    _verify_observer(token)
    try:
        with _tel_lock:
            c = _tel_get_conn()
            with c.cursor() as cur_t:
                cur_t.execute("SELECT DISTINCT action_type FROM sys_telemetry ORDER BY 1")
                actions = [r[0] for r in cur_t.fetchall()]
                cur_t.execute("SELECT DISTINCT module FROM sys_telemetry WHERE module IS NOT NULL ORDER BY 1")
                modules = [r[0] for r in cur_t.fetchall()]
        return {"actions": actions, "modules": modules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EXPORTAR BASE COMPLETA A EXCEL (modal del admin-pwa) ====================
# Flujo: POST inicia un trabajo en segundo plano -> GET estado (progreso) -> GET descargar (URL firmada).
# Usa una conexión aislada (no el cursor global compartido) y una transacción REPEATABLE READ de solo
# lectura, así el archivo es una foto consistente "hasta ese momento" aunque entren registros nuevos.
import threading as _th
import tempfile as _tmp
import uuid as _uuid
import shutil as _shutil
import time as _time
import datetime as _dt
from fastapi.responses import FileResponse as _FileResponse

_EXPORT_DIR = os.path.join(_tmp.gettempdir(), "psv_exports")
_EXPORT_MAX_FILAS_HOJA = 1_000_000          # Excel admite 1,048,576 filas por hoja (incluye encabezados)
_EXPORT_TIPOS = ("actividades", "asistencias")
_EXPORT_FOTO_BASE = os.environ.get("PUBLIC_API_URL", "https://apipwa.sembrandodatos.com").rstrip("/") + "/"
_EXPORT_RETENCION_SEG = 3 * 3600
_export_activos = {}                          # tipo -> job_id en ejecución (dentro de este proceso)
_export_lock = _th.Lock()

_EXPORT_COLS = {
    "actividades": [
        ("ID", 10), ("Fecha y hora", 19), ("ID usuario", 11), ("Nombre del usuario", 38), ("Cargo", 24),
        ("Territorio", 26), ("Tipo de actividad", 16), ("Categoría", 32), ("Categoría (otro)", 24),
        ("Descripción", 70), ("Latitud", 12), ("Longitud", 12),
        ("Correo", 30), ("CURP", 22), ("Teléfono", 16), ("Supervisor", 30), ("URL de la foto", 60),
    ],
    "asistencias": [
        ("ID", 10), ("Fecha", 12), ("ID usuario", 11), ("Nombre del usuario", 38), ("Cargo", 24),
        ("Territorio", 26), ("Hora de entrada", 14), ("Hora de salida", 14), ("Horas trabajadas (h:mm)", 16),
        ("Descripción entrada", 60), ("Descripción salida", 60), ("Lat. entrada", 12), ("Long. entrada", 12),
        ("Lat. salida", 12), ("Long. salida", 12),
        ("Correo", 30), ("CURP", 22), ("Teléfono", 16), ("Supervisor", 30), ("URL foto entrada", 60), ("URL foto salida", 60),
    ],
}


def _export_ruta(job_id, nombre):
    return os.path.join(_EXPORT_DIR, job_id, nombre)


def _export_job_valido(job_id):
    return bool(job_id) and bool(_re.fullmatch(r"[0-9a-f]{32}", job_id))


def _export_leer_estado(job_id):
    try:
        with open(_export_ruta(job_id, "estado.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _export_guardar_estado(job_id, **cambios):
    est = _export_leer_estado(job_id) or {}
    est.update(cambios)
    est["actualizado"] = _time.time()
    tmp = _export_ruta(job_id, "estado.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(est, f)
    os.replace(tmp, _export_ruta(job_id, "estado.json"))


def _export_limpiar_viejos():
    try:
        ahora = _time.time()
        for nombre in os.listdir(_EXPORT_DIR):
            ruta = os.path.join(_EXPORT_DIR, nombre)
            if os.path.isdir(ruta) and ahora - os.path.getmtime(ruta) > _EXPORT_RETENCION_SEG:
                _shutil.rmtree(ruta, ignore_errors=True)
    except Exception:
        pass


def _export_url_foto(v):
    if not v:
        return None
    v = str(v).strip()
    return v if v.lower().startswith("http") else _EXPORT_FOTO_BASE + v.lstrip("/")


def _export_num(v):
    try:
        return None if v is None else float(v)
    except Exception:
        return None


def _export_fila(tipo, r):
    """Devuelve la fila como lista de valores (datetime/float/str/None) en el orden de _EXPORT_COLS."""
    if tipo == "actividades":
        return [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9],
                _export_num(r[10]), _export_num(r[11]), r[13], r[14], r[15], r[16], _export_url_foto(r[12])]
    ent, sal = r[6], r[7]
    horas = None
    if isinstance(ent, _dt.datetime) and isinstance(sal, _dt.datetime):
        try:
            h = (sal - ent).total_seconds() / 3600
            horas = round(h, 2) if 0 <= h <= 24 else None
        except Exception:
            horas = None
    return [r[0], r[1], r[2], r[3], r[4], r[5], ent, sal, horas, r[8], r[9],
            _export_num(r[10]), _export_num(r[11]), _export_num(r[12]), _export_num(r[13]),
            r[16], r[17], r[18], r[19], _export_url_foto(r[14]), _export_url_foto(r[15])]


_EXPORT_N_FOTOS = {"actividades": 1, "asistencias": 2}


def _export_escribir_xlsx(ruta, tipo, filas, total, filtros_txt, max_filas_hoja=_EXPORT_MAX_FILAS_HOJA, progreso=None, con_fotos=False):
    """Escribe el Excel por streaming (memoria constante). `filas` es un iterable de filas ya convertidas.
    Divide en varias hojas cuando se supera `max_filas_hoja`. Devuelve (filas_escritas, hojas)."""
    import xlsxwriter
    cols = _EXPORT_COLS[tipo]
    if not con_fotos:   # las URL de fotos son las últimas columnas: solo las ven los usuarios con rol admin
        cols = cols[:-_EXPORT_N_FOTOS[tipo]]
    ncols = len(cols)
    titulo = "Actividades" if tipo == "actividades" else "Asistencias"
    wb = xlsxwriter.Workbook(ruta, {"constant_memory": True, "remove_timezone": True, "strings_to_urls": False,
                                    "strings_to_numbers": False, "strings_to_formulas": False})
    f_t1 = wb.add_format({"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#1F6F43", "valign": "vcenter", "indent": 1})
    f_t2 = wb.add_format({"italic": True, "font_size": 10, "font_color": "#D7EBDD", "bg_color": "#14492D", "valign": "vcenter", "indent": 1})
    f_hd = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F6F43", "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1, "border_color": "#C9D6CE"})
    f_dt = wb.add_format({"num_format": "dd/mm/yyyy hh:mm:ss"})
    f_d = wb.add_format({"num_format": "dd/mm/yyyy"})
    f_h = wb.add_format({"num_format": "[h]:mm", "align": "center"})   # horas trabajadas como h:mm (se pueden sumar en Excel)
    f_hora = wb.add_format({"num_format": "hh:mm:ss", "align": "center"})   # hora del día, sin repetir la fecha
    f_c = wb.add_format({"num_format": "0.000000"})
    f_k = wb.add_format({"bold": True, "font_size": 22, "font_color": "#1F6F43", "bg_color": "#E6F2EA", "align": "center", "valign": "vcenter", "num_format": "#,##0", "border": 1, "border_color": "#C9D6CE"})
    f_kl = wb.add_format({"bold": True, "font_size": 9, "font_color": "#14492D", "bg_color": "#E6F2EA", "align": "center", "valign": "vcenter", "border": 1, "border_color": "#C9D6CE"})
    f_n = wb.add_format({"font_size": 9, "italic": True, "font_color": "#6B7C72"})

    # Hoja Resumen (primera): se escribe completa antes de las hojas de datos (constant_memory exige orden).
    n_hojas_prev = max(1, -(-int(total) // (max_filas_hoja - 5))) if total else 1
    ws0 = wb.add_worksheet("Resumen")
    ws0.hide_gridlines(2)
    ws0.set_column(0, 4, 26)
    ws0.set_row(0, 34); ws0.set_row(1, 20)
    ws0.merge_range(0, 0, 0, 4, "PLATAFORMA DE SEGUIMIENTO DE PSV", f_t1)
    ws0.merge_range(1, 0, 1, 4, f"Base completa de {tipo} · extraída el {_dt.datetime.now().strftime('%d/%m/%Y %H:%M')}", f_t2)
    ws0.set_row(4, 22); ws0.set_row(5, 40)
    ws0.write(4, 0, "REGISTROS", f_kl); ws0.write_number(5, 0, int(total), f_k)
    ws0.write(4, 1, "HOJAS DE DATOS", f_kl); ws0.write_number(5, 1, n_hojas_prev, f_k)
    ws0.write(7, 0, "Filtros: " + filtros_txt, f_n)
    ws0.write(8, 0, f"Cada hoja admite hasta {max_filas_hoja - 5:,} registros; si hay más, continúan en la siguiente hoja.", f_n)
    ws0.write(9, 0, "Contiene datos personales. No compartir.", f_n)

    estado = {"ws": None, "n": 0, "en_hoja": 0, "hojas": 0}

    def nueva_hoja():
        cerrar_hoja()
        estado["hojas"] += 1
        nombre = titulo if n_hojas_prev == 1 else f"{titulo} {estado['hojas']}"
        ws = wb.add_worksheet(nombre)
        ws.hide_gridlines(2)
        ws.set_row(0, 34); ws.set_row(1, 20); ws.set_row(3, 30)
        ws.merge_range(0, 0, 0, ncols - 1, "PLATAFORMA DE SEGUIMIENTO DE PSV", f_t1)
        ws.merge_range(1, 0, 1, ncols - 1, f"{titulo} · todos los registros hasta {_dt.datetime.now().strftime('%d/%m/%Y %H:%M')}", f_t2)
        for i, (nombre_col, ancho) in enumerate(cols):
            ws.set_column(i, i, ancho)
            ws.write(3, i, nombre_col, f_hd)
        ws.freeze_panes(4, 2)
        estado["ws"] = ws
        estado["en_hoja"] = 0

    def cerrar_hoja():
        ws = estado["ws"]
        if ws is not None and estado["en_hoja"] > 0:
            ws.autofilter(3, 0, 3 + estado["en_hoja"], ncols - 1)

    idx_dt = {"actividades": {1}, "asistencias": {6, 7}}[tipo]
    idx_d = {"actividades": set(), "asistencias": {1}}[tipo]
    idx_h = {"actividades": set(), "asistencias": {8}}[tipo]
    idx_c = {"actividades": {10, 11}, "asistencias": {11, 12, 13, 14}}[tipo]

    for fila in filas:
        if estado["ws"] is None or estado["en_hoja"] >= max_filas_hoja - 5:   # margen para título y encabezado
            nueva_hoja()
        ws = estado["ws"]
        r = 4 + estado["en_hoja"]
        for i, v in enumerate(fila[:ncols]):
            if v is None or v == "":
                continue
            if i in idx_dt or i in idx_d:
                if isinstance(v, _dt.datetime):
                    ws.write_datetime(r, i, v, (f_hora if (tipo == "asistencias" and i in idx_dt) else f_dt) if i in idx_dt else f_d)
                elif isinstance(v, _dt.date):
                    ws.write_datetime(r, i, _dt.datetime(v.year, v.month, v.day), f_d)
                else:
                    ws.write_string(r, i, str(v))
            elif i in idx_c:
                ws.write_number(r, i, v, f_c)
            elif i in idx_h:
                ws.write_number(r, i, v / 24.0, f_h)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                ws.write_number(r, i, v)
            else:
                ws.write_string(r, i, str(v))
        estado["en_hoja"] += 1
        estado["n"] += 1
        if progreso and estado["n"] % 5000 == 0:
            progreso(estado["n"])
    if estado["ws"] is None:
        nueva_hoja()
    cerrar_hoja()
    wb.close()
    return estado["n"], estado["hojas"]


def _export_alcance(payload, tipo):
    """Qué puede exportar quien lo pide, leído de la base (no del token, que puede estar desfasado):
    - admin: todo.  - con permiso del módulo (asistencia / registros): solo lo suyo.
    - territorial: solo su territorio.  - facilitador: solo los técnicos que tiene asignados.
    Devuelve (territorio, facilitador, es_admin) donde facilitador es (admin_id, usuario_id) o None."""
    usuario = str(payload.get("sub", "")).strip()
    conexion = None
    try:
        conexion, _c = abrir_conexion_aislada()
        cur = conexion.cursor()
        cur.execute("SELECT id, rol, permisos, activo, es_territorial, territorio, cargo, usuario_id FROM admin_users WHERE username = %s", (usuario,))
        row = cur.fetchone()
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    if not row or not row[3]:
        raise HTTPException(status_code=403, detail="Tu cuenta está desactivada o no existe")
    admin_id, rol, permisos_raw, _act, es_terr, terr, cargo, uid = row
    if str(rol or "").lower() != "admin":
        try:
            permisos = json.loads(permisos_raw) if permisos_raw else {}
        except Exception:
            permisos = {}
        modulo = "asistencia" if tipo == "asistencias" else "registros"
        if permisos.get(modulo) is not True:
            raise HTTPException(status_code=403, detail=f"No tienes permiso para exportar {tipo}")
    territorio = terr if (es_terr and terr) else None
    facilitador = (admin_id, uid) if "FACILITADOR" in str(cargo or "").upper() else None
    return territorio, facilitador, str(rol or "").lower() == "admin"


def _export_trabajo(job_id, tipo, territorio, fecha_inicio, fecha_fin, solicitante, facilitador=None, con_fotos=False):
    """Hilo en segundo plano: consulta con conexión aislada y genera el .xlsx."""
    conexion = None
    try:
        conexion, _c = abrir_conexion_aislada()
        conexion.set_session(isolation_level="REPEATABLE READ", readonly=True)
        cur = conexion.cursor()
        cond, prm = [], []
        if tipo == "actividades":
            if territorio:
                cond.append("u.territorio = %s"); prm.append(territorio)
            if fecha_inicio:
                cond.append("r.fecha_hora >= %s"); prm.append(fecha_inicio)
            if fecha_fin:
                cond.append("r.fecha_hora < (%s::date + 1)"); prm.append(fecha_fin)
            frm = "FROM registros r LEFT JOIN usuarios u ON u.id = r.usuario_id"
            sel = ("SELECT r.id, r.fecha_hora, r.usuario_id, u.nombre_completo, u.cargo, u.territorio, r.tipo_actividad, "
                   "r.categoria_actividad, r.categoria_actividad_otro, r.descripcion, r.latitud, r.longitud, r.foto_url, "
                   "u.correo, u.curp, u.telefono, u.supervisor ")
            orden = " ORDER BY r.id DESC"
        else:
            if territorio:
                cond.append("u.territorio = %s"); prm.append(territorio)
            if fecha_inicio:
                cond.append("a.fecha >= %s"); prm.append(fecha_inicio)
            if fecha_fin:
                cond.append("a.fecha <= %s"); prm.append(fecha_fin)
            frm = "FROM asistencias a LEFT JOIN usuarios u ON u.id = a.usuario_id"
            sel = ("SELECT a.id, a.fecha, a.usuario_id, u.nombre_completo, u.cargo, u.territorio, a.hora_entrada, a.hora_salida, "
                   "a.descripcion_entrada, a.descripcion_salida, a.latitud_entrada, a.longitud_entrada, a.latitud_salida, "
                   "a.longitud_salida, a.foto_entrada_url, a.foto_salida_url, u.correo, u.curp, u.telefono, u.supervisor ")
            orden = " ORDER BY a.fecha DESC, a.id DESC"
        if facilitador:
            col = "r.usuario_id" if tipo == "actividades" else "a.usuario_id"
            cond.append(f"{col} IN (SELECT tecnico_usuario_id FROM facilitador_tecnico_asignaciones "
                        "WHERE activo = TRUE AND (facilitador_admin_id = %s OR (%s IS NOT NULL AND facilitador_usuario_id = %s)))")
            prm.extend([facilitador[0], facilitador[1], facilitador[1]])
        where = (" WHERE " + " AND ".join(cond)) if cond else ""
        cur.execute("SELECT COUNT(*) " + frm + where, tuple(prm))
        total = cur.fetchone()[0]
        _export_guardar_estado(job_id, estado="procesando", total=int(total), procesadas=0)

        filtros = []
        filtros.append(f"territorio = {territorio}" if territorio else "todos los territorios")
        if facilitador:
            filtros.append("solo los técnicos asignados a tu cuenta de facilitador")
        filtros.append(f"desde {fecha_inicio}" if fecha_inicio else "desde el inicio")
        filtros.append(f"hasta {fecha_fin}" if fecha_fin else "hasta el momento de la extracción")
        filtros_txt = " · ".join(filtros)

        cur_stream = conexion.cursor(name="exp_" + job_id[:12])
        cur_stream.itersize = 20000
        cur_stream.execute(sel + frm + where + orden, tuple(prm))

        def filas():
            for r in cur_stream:
                yield _export_fila(tipo, r)

        ruta_tmp = _export_ruta(job_id, "base.xlsx.part")
        n, hojas = _export_escribir_xlsx(
            ruta_tmp, tipo, filas(), total, filtros_txt,
            progreso=lambda k: _export_guardar_estado(job_id, procesadas=k), con_fotos=con_fotos)
        os.replace(ruta_tmp, _export_ruta(job_id, "base.xlsx"))
        _export_guardar_estado(job_id, estado="listo", procesadas=n, total=max(int(total), n), hojas=hojas,
                               bytes=os.path.getsize(_export_ruta(job_id, "base.xlsx")))
        print(f"✅ [EXPORT] {tipo}: {n} filas en {hojas} hoja(s) por {solicitante}")
    except Exception as e:
        print(f"❌ [EXPORT] Error exportando {tipo}: {e}")
        _export_guardar_estado(job_id, estado="error", error=str(e)[:300])
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
        with _export_lock:
            if _export_activos.get(tipo) == job_id:
                _export_activos.pop(tipo, None)


def _export_fecha(v):
    if not v:
        return None
    try:
        return _dt.datetime.strptime(str(v)[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa el formato AAAA-MM-DD")


@app.post("/admin/exportar-base/{tipo}")
async def iniciar_exportacion_base(tipo: str, request: Request):
    """Inicia (en segundo plano) la generación del Excel completo de 'actividades' o 'asistencias'."""
    payload = _jwt_admin(request)
    if tipo not in _EXPORT_TIPOS:
        raise HTTPException(status_code=404, detail="Tipo de base no válido")
    try:
        datos = await request.json()
    except Exception:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    fecha_inicio = _export_fecha(datos.get("fecha_inicio"))
    fecha_fin = _export_fecha(datos.get("fecha_fin"))
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(status_code=400, detail="La fecha de inicio no puede ser posterior a la fecha final")
    # Alcance según permisos reales de la cuenta: módulo permitido, territorio propio, técnicos asignados
    territorio, facilitador, es_admin = _export_alcance(payload, tipo)
    if not territorio and datos.get("territorio"):
        territorio = str(datos.get("territorio")).strip() or None

    os.makedirs(_EXPORT_DIR, exist_ok=True)
    _export_limpiar_viejos()
    solicitante = str(payload.get("sub", ""))
    with _export_lock:
        activo = _export_activos.get(tipo)
        if activo:
            est = _export_leer_estado(activo)
            if est and est.get("estado") in ("iniciando", "procesando"):
                return {"job_id": activo, "estado": est.get("estado"), "reutilizado": True}
        job_id = _uuid.uuid4().hex
        os.makedirs(os.path.join(_EXPORT_DIR, job_id), exist_ok=True)
        _export_guardar_estado(job_id, estado="iniciando", tipo=tipo, solicitante=solicitante,
                               territorio=territorio, procesadas=0, total=0, creado=_time.time())
        _export_activos[tipo] = job_id
    _th.Thread(target=_export_trabajo, args=(job_id, tipo, territorio, fecha_inicio, fecha_fin, solicitante, facilitador, es_admin), daemon=True).start()
    return {"job_id": job_id, "estado": "iniciando", "reutilizado": False}


@app.get("/admin/exportar-base/estado/{job_id}")
async def estado_exportacion_base(job_id: str, request: Request):
    payload = _jwt_admin(request)
    if not _export_job_valido(job_id):
        raise HTTPException(status_code=404, detail="Exportación no encontrada")
    est = _export_leer_estado(job_id)
    if not est or est.get("solicitante") != str(payload.get("sub", "")):
        raise HTTPException(status_code=404, detail="Exportación no encontrada")
    # Si el hilo murió (reinicio del servidor), no dejar la barra colgada
    if est.get("estado") in ("iniciando", "procesando") and _time.time() - est.get("actualizado", 0) > 600:
        _export_guardar_estado(job_id, estado="error", error="La exportación se interrumpió. Inténtalo de nuevo.")
        est = _export_leer_estado(job_id)
    resp = {k: est.get(k) for k in ("estado", "tipo", "procesadas", "total", "hojas", "bytes", "error")}
    if est.get("estado") == "listo":
        tk = jwt.encode({"tipo": "export_dl", "job": job_id, "sub": est.get("solicitante"),
                         "exp": int(_time.time()) + 900}, SECRET_KEY, algorithm="HS256")
        resp["descarga_url"] = f"/admin/exportar-base/descargar/{job_id}?t={tk}"
    return resp


@app.get("/admin/exportar-base/descargar/{job_id}")
async def descargar_exportacion_base(job_id: str, t: str = ""):
    """Descarga directa del Excel con enlace firmado de corta duración (para que el navegador lo baje en streaming)."""
    try:
        data = jwt.decode(t, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Enlace de descarga inválido o vencido. Genera la exportación de nuevo.")
    if data.get("tipo") != "export_dl" or data.get("job") != job_id or not _export_job_valido(job_id):
        raise HTTPException(status_code=403, detail="No autorizado")
    est = _export_leer_estado(job_id)
    ruta = _export_ruta(job_id, "base.xlsx")
    if not est or est.get("estado") != "listo" or not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="El archivo ya no está disponible. Genera la exportación de nuevo.")
    nombre = f"PSV_{est.get('tipo', 'base')}_completo_{_dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    # Content-Encoding explícito evita que GZipMiddleware recomprima un .xlsx que ya viene comprimido
    return _FileResponse(ruta, filename=nombre,
                         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         headers={"Content-Encoding": "identity"})

# ==================== FIN EXPORTAR BASE COMPLETA A EXCEL ====================


# ==================== NOTIFICACIONES PUSH (Web Push / VAPID) ====================
# Los avisos llegan al teléfono aunque la app esté cerrada (solo necesita estar instalada).
# Tablas: push_suscripciones (un registro por dispositivo) y push_envios (bitácora de cada envío).
from concurrent.futures import ThreadPoolExecutor as _PushPool

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY_FILE = os.environ.get("VAPID_PRIVATE_KEY_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vapid_private.pem"))
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:notificaciones@sembrandodatos.com")
_push_prueba_hits = {}


def _push_disponible():
    return bool(VAPID_PUBLIC_KEY) and os.path.exists(VAPID_PRIVATE_KEY_FILE)


def _push_plataforma(ua):
    u = (ua or "").lower()
    if "iphone" in u or "ipad" in u or "ipod" in u:
        return "ios"
    if "android" in u:
        return "android"
    if "windows" in u:
        return "windows"
    if "mac os" in u or "macintosh" in u:
        return "mac"
    if "linux" in u:
        return "linux"
    return "otro"


class PushKeysIn(BaseModel):
    p256dh: str
    auth: str


class PushSuscripcionIn(BaseModel):
    usuario_id: int
    endpoint: str
    keys: PushKeysIn
    ua: Optional[str] = None


class PushBajaIn(BaseModel):
    endpoint: str


class PushUsuarioIn(BaseModel):
    usuario_id: int


def _push_payload(titulo, cuerpo, notificacion_id=None, url="/notificaciones"):
    return json.dumps({
        "titulo": str(titulo or "Sembrando Vida")[:100],
        "cuerpo": str(cuerpo or "")[:180],
        "url": url,
        "id": notificacion_id,
        "tag": f"notif-{notificacion_id}" if notificacion_id else "aviso",
        "ts": int(_tm.time()),
    }, ensure_ascii=False)


def _push_suscripciones_de(conexion, usuario_ids=None):
    """Dispositivos activos de usuarios activos. usuario_ids=None -> todos."""
    cur = conexion.cursor()
    sql = ("SELECT s.id, s.usuario_id, s.endpoint, s.p256dh, s.auth FROM push_suscripciones s "
           "JOIN usuarios u ON u.id = s.usuario_id WHERE s.activa = TRUE AND COALESCE(u.activo, TRUE) = TRUE")
    prm = []
    if usuario_ids is not None:
        if not usuario_ids:
            return []
        sql += " AND s.usuario_id = ANY(%s)"
        prm.append(list(usuario_ids))
    cur.execute(sql, tuple(prm))
    return cur.fetchall()


def _push_enviar(subs, payload, notificacion_id=None):
    """Envía el payload a cada dispositivo (en paralelo), actualiza su estado y deja bitácora.
    Devuelve {'enviados': n, 'fallidos': n, 'expirados': n}."""
    resumen = {"enviados": 0, "fallidos": 0, "expirados": 0}
    if not subs or not _push_disponible():
        return resumen
    try:
        from pywebpush import webpush, WebPushException
    except Exception as e:
        print(f"⚠️ [PUSH] pywebpush no disponible: {e}")
        return resumen

    def uno(s):
        sid, uid, ep, p256, au = s
        try:
            webpush(subscription_info={"endpoint": ep, "keys": {"p256dh": p256, "auth": au}}, data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY_FILE, vapid_claims={"sub": VAPID_SUBJECT}, ttl=86400, timeout=12)
            return (sid, uid, "enviado", 201, None)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            return (sid, uid, "expirado" if code in (404, 410) else "fallido", code, str(e)[:250])
        except Exception as e:
            return (sid, uid, "fallido", None, str(e)[:250])

    with _PushPool(max_workers=8) as ex:
        resultados = list(ex.map(uno, subs))

    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        for sid, uid, estado, codigo, error in resultados:
            resumen[{"enviado": "enviados", "fallido": "fallidos", "expirado": "expirados"}[estado]] += 1
            cur.execute("INSERT INTO push_envios (notificacion_id, usuario_id, suscripcion_id, estado, codigo, error) VALUES (%s,%s,%s,%s,%s,%s)",
                        (notificacion_id, uid, sid, estado, codigo, error))
            if estado == "enviado":
                cur.execute("UPDATE push_suscripciones SET ultimo_envio = NOW(), fallos = 0, ultimo_error = NULL WHERE id = %s", (sid,))
            elif estado == "expirado":
                cur.execute("UPDATE push_suscripciones SET activa = FALSE, ultimo_error = %s WHERE id = %s", ("Suscripción vencida o desinstalada", sid))
            else:
                cur.execute("UPDATE push_suscripciones SET fallos = fallos + 1, ultimo_error = %s, activa = (fallos + 1 < 5) WHERE id = %s", (error, sid))
        conexion.commit()
    except Exception as e:
        print(f"⚠️ [PUSH] no se pudo guardar la bitácora: {e}")
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    print(f"📲 [PUSH] notif={notificacion_id} enviados={resumen['enviados']} fallidos={resumen['fallidos']} expirados={resumen['expirados']}")
    return resumen


def _push_destinatarios_notificacion(conexion, notificacion_id):
    """(titulo, cuerpo, ids de usuarios destino o None si es para todos)."""
    cur = conexion.cursor()
    cur.execute("SELECT titulo, subtitulo, descripcion, enviada_a_todos FROM notificaciones WHERE id = %s", (notificacion_id,))
    fila = cur.fetchone()
    if not fila:
        return None
    titulo, subtitulo, descripcion, a_todos = fila
    cuerpo = (subtitulo or "").strip() or (descripcion or "").strip()
    if a_todos:
        return titulo, cuerpo, None
    cur.execute("SELECT usuario_id FROM notificacion_usuarios WHERE notificacion_id = %s", (notificacion_id,))
    return titulo, cuerpo, [r[0] for r in cur.fetchall()]


def _push_para_notificacion(notificacion_id, solo_no_leidos=False):
    """Hilo: envía el push de una notificación a los dispositivos de sus destinatarios."""
    conexion = None
    try:
        conexion, _c = abrir_conexion_aislada()
        datos = _push_destinatarios_notificacion(conexion, notificacion_id)
        if not datos:
            return {"enviados": 0, "fallidos": 0, "expirados": 0}
        titulo, cuerpo, ids = datos
        subs = _push_suscripciones_de(conexion, ids)
        if solo_no_leidos and subs:
            cur = conexion.cursor()
            cur.execute("SELECT usuario_id FROM notificacion_leidos WHERE notificacion_id = %s", (notificacion_id,))
            leyeron = {r[0] for r in cur.fetchall()}
            subs = [s for s in subs if s[1] not in leyeron]
        conexion.close()
        conexion = None
        return _push_enviar(subs, _push_payload(titulo, cuerpo, notificacion_id), notificacion_id)
    except Exception as e:
        print(f"❌ [PUSH] error enviando notificación {notificacion_id}: {e}")
        return {"enviados": 0, "fallidos": 0, "expirados": 0}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


def _push_lanzar(notificacion_id):
    """Dispara el envío en segundo plano para no hacer esperar a quien crea la notificación."""
    if _push_disponible():
        _th.Thread(target=_push_para_notificacion, args=(notificacion_id,), daemon=True).start()


def _push_conteo_destino(notificacion_id):
    """Cuántos usuarios y dispositivos recibirán el push de una notificación."""
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        datos = _push_destinatarios_notificacion(conexion, notificacion_id)
        if not datos:
            return {"dispositivos": 0, "usuarios": 0}
        subs = _push_suscripciones_de(conexion, datos[2])
        return {"dispositivos": len(subs), "usuarios": len({s[1] for s in subs})}
    except Exception:
        return {"dispositivos": 0, "usuarios": 0}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/push/clave-publica")
async def push_clave_publica():
    return {"disponible": _push_disponible(), "clave": VAPID_PUBLIC_KEY if _push_disponible() else ""}


@app.post("/push/suscribir")
async def push_suscribir(datos: PushSuscripcionIn):
    """Registra (o reasigna) el dispositivo del usuario para recibir avisos push."""
    if not _push_disponible():
        raise HTTPException(status_code=503, detail="Las notificaciones push no están configuradas")
    ep = (datos.endpoint or "").strip()
    if not ep.startswith("https://") or len(ep) > 1000 or len(datos.keys.p256dh) > 200 or len(datos.keys.auth) > 100:
        raise HTTPException(status_code=400, detail="Suscripción inválida")
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT 1 FROM usuarios WHERE id = %s", (datos.usuario_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        ua = (datos.ua or "")[:300]
        cur.execute("""
            INSERT INTO push_suscripciones (usuario_id, endpoint, p256dh, auth, ua, plataforma)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE SET usuario_id = EXCLUDED.usuario_id, p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth, ua = EXCLUDED.ua, plataforma = EXCLUDED.plataforma,
                activa = TRUE, fallos = 0, ultimo_error = NULL, ultima_vez = NOW()
        """, (datos.usuario_id, ep, datos.keys.p256dh, datos.keys.auth, ua, _push_plataforma(ua)))
        cur.execute("SELECT COUNT(*) FROM push_suscripciones WHERE usuario_id = %s AND activa = TRUE", (datos.usuario_id,))
        n = cur.fetchone()[0]
        conexion.commit()
        return {"ok": True, "dispositivos": n}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [PUSH] suscribir: {e}")
        raise HTTPException(status_code=500, detail="No se pudo registrar el dispositivo")
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.post("/push/baja")
async def push_baja(datos: PushBajaIn):
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("UPDATE push_suscripciones SET activa = FALSE, ultimo_error = 'Desactivada por el usuario' WHERE endpoint = %s", (datos.endpoint,))
        conexion.commit()
        return {"ok": True}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/push/estado")
async def push_estado(usuario_id: int, endpoint: str = ""):
    """¿Este dispositivo (endpoint) está activo? ¿Cuántos dispositivos tiene el usuario?"""
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT COUNT(*) FROM push_suscripciones WHERE usuario_id = %s AND activa = TRUE", (usuario_id,))
        n = cur.fetchone()[0]
        este = False
        if endpoint:
            cur.execute("SELECT 1 FROM push_suscripciones WHERE usuario_id = %s AND endpoint = %s AND activa = TRUE", (usuario_id, endpoint))
            este = cur.fetchone() is not None
        return {"disponible": _push_disponible(), "dispositivos": n, "este_dispositivo": este}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.post("/push/probar")
async def push_probar(datos: PushUsuarioIn):
    """El propio usuario manda una prueba a sus dispositivos (máx. 1 cada 15 s)."""
    ahora = _tm.time()
    if ahora - _push_prueba_hits.get(datos.usuario_id, 0) < 15:
        raise HTTPException(status_code=429, detail="Espera unos segundos antes de otra prueba")
    _push_prueba_hits[datos.usuario_id] = ahora
    return await _push_probar_usuario(datos.usuario_id, "Aviso de prueba", "Así llegarán tus notificaciones, aunque la app esté cerrada.")


async def _push_probar_usuario(usuario_id, titulo, cuerpo):
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        subs = _push_suscripciones_de(conexion, [usuario_id])
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    if not subs:
        raise HTTPException(status_code=404, detail="Este usuario no tiene dispositivos con avisos activados")
    res = await _aio.get_event_loop().run_in_executor(None, _push_enviar, subs, _push_payload(titulo, cuerpo, None), None)
    return {"ok": res["enviados"] > 0, **res}


# ---------- Panel administrador ----------
@app.get("/admin/push/resumen")
async def admin_push_resumen(request: Request):
    _jwt_admin(request)
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("""SELECT COUNT(*) FILTER (WHERE s.activa), COUNT(DISTINCT s.usuario_id) FILTER (WHERE s.activa),
                              COUNT(*) FILTER (WHERE s.activa AND s.plataforma = 'ios'),
                              COUNT(*) FILTER (WHERE s.activa AND s.plataforma = 'android')
                       FROM push_suscripciones s""")
        d, u, ios, andr = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE COALESCE(activo, TRUE) = TRUE")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FILTER (WHERE estado = 'enviado'), COUNT(*) FILTER (WHERE estado <> 'enviado') FROM push_envios WHERE creado_at > NOW() - INTERVAL '7 days'")
        ok7, mal7 = cur.fetchone()
        return {"disponible": _push_disponible(), "dispositivos": d, "usuarios_con_push": u, "usuarios_total": total,
                "ios": ios, "android": andr, "enviados_7d": ok7, "fallidos_7d": mal7}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/admin/push/usuarios")
async def admin_push_usuarios(request: Request):
    """Dispositivos activos por usuario: {usuario_id: {dispositivos, ultima_vez, plataformas}}."""
    _jwt_admin(request)
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("""SELECT usuario_id, COUNT(*), MAX(ultima_vez), ARRAY_AGG(DISTINCT plataforma)
                       FROM push_suscripciones WHERE activa = TRUE GROUP BY usuario_id""")
        return {str(r[0]): {"dispositivos": r[1], "ultima_vez": r[2].isoformat() if r[2] else None,
                            "plataformas": [p for p in (r[3] or []) if p]} for r in cur.fetchall()}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/admin/push/notificacion/{notificacion_id}")
async def admin_push_notificacion(notificacion_id: int, request: Request):
    """Cómo salió el push de una notificación: llegada por dispositivo y usuarios sin push."""
    _jwt_admin(request)
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        datos = _push_destinatarios_notificacion(conexion, notificacion_id)
        if not datos:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        ids = datos[2]
        cur.execute("""SELECT COUNT(*) FILTER (WHERE estado = 'enviado'), COUNT(*) FILTER (WHERE estado = 'fallido'),
                              COUNT(*) FILTER (WHERE estado = 'expirado'), COUNT(DISTINCT usuario_id) FILTER (WHERE estado = 'enviado')
                       FROM push_envios WHERE notificacion_id = %s""", (notificacion_id,))
        enviados, fallidos, expirados, usuarios_ok = cur.fetchone()
        if ids is None:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE COALESCE(activo, TRUE) = TRUE")
        else:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE id = ANY(%s)", (ids,))
        destinatarios = cur.fetchone()[0]
        subs = _push_suscripciones_de(conexion, ids)
        con_push = len({s[1] for s in subs})
        return {"destinatarios": destinatarios, "usuarios_con_push": con_push, "usuarios_sin_push": max(0, destinatarios - con_push),
                "dispositivos_activos": len(subs), "enviados": enviados, "fallidos": fallidos, "expirados": expirados,
                "usuarios_entregados": usuarios_ok, "push_disponible": _push_disponible()}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.post("/admin/push/reenviar/{notificacion_id}")
async def admin_push_reenviar(notificacion_id: int, request: Request):
    """Vuelve a mandar el push solo a quienes aún no han leído la notificación."""
    _jwt_admin(request)
    res = await _aio.get_event_loop().run_in_executor(None, _push_para_notificacion, notificacion_id, True)
    return {"ok": True, **res}


@app.post("/admin/push/prueba/{usuario_id}")
async def admin_push_prueba(usuario_id: int, request: Request):
    _jwt_admin(request)
    return await _push_probar_usuario(usuario_id, "Aviso de prueba", "Tu administrador comprobó que tus avisos llegan correctamente.")

# ==================== FIN NOTIFICACIONES PUSH ====================


# ==================== ENTERADO DE NOTIFICACIONES ====================
# Cada persona puede marcar "Enterado" en una notificación (queda constancia con fecha y hora).
# Estados por persona: sin leer -> vista (abrió el detalle) -> enterado (tocó el botón).
import io as _io
_recordar_hits = {}


class EnteradoIn(BaseModel):
    usuario_id: int
    device_id: Optional[str] = None


@app.post("/notificaciones/{notificacion_id}/enterado")
async def marcar_enterado(notificacion_id: int, datos: EnteradoIn):
    """Marca la notificación como 'Enterado' (una sola vez por persona; repetir la petición no duplica)."""
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT 1 FROM usuarios WHERE id = %s", (datos.usuario_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        cur.execute("""SELECT 1 FROM notificaciones n LEFT JOIN notificacion_usuarios nu ON nu.notificacion_id = n.id AND nu.usuario_id = %s
                       WHERE n.id = %s AND (n.enviada_a_todos = TRUE OR nu.usuario_id IS NOT NULL)""", (datos.usuario_id, notificacion_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Notificación no visible para este usuario")
        dev = (datos.device_id or "")[:120] or None
        cur.execute("""INSERT INTO notificacion_enterados (notificacion_id, usuario_id, device_id, enterado_at)
                       VALUES (%s, %s, %s, NOW() AT TIME ZONE 'America/Mexico_City')
                       ON CONFLICT (notificacion_id, usuario_id) DO NOTHING""", (notificacion_id, datos.usuario_id, dev))
        # quien se da por enterado también la vio
        cur.execute("""INSERT INTO notificacion_leidos (notificacion_id, usuario_id, device_id)
                       VALUES (%s, %s, %s) ON CONFLICT (notificacion_id, usuario_id) DO NOTHING""", (notificacion_id, datos.usuario_id, dev))
        cur.execute("SELECT enterado_at FROM notificacion_enterados WHERE notificacion_id = %s AND usuario_id = %s", (notificacion_id, datos.usuario_id))
        fecha = cur.fetchone()[0]
        conexion.commit()
        return {"ok": True, "enterado": True, "enterado_en": fecha.isoformat() if fecha else None}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [ENTERADO] {e}")
        raise HTTPException(status_code=500, detail="No se pudo registrar el enterado")
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


def _notif_alcance(payload):
    """Admin que consulta enterados: administrador, o con permiso de Notificaciones. Si es territorial, solo su territorio."""
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT rol, permisos, activo, es_territorial, territorio FROM admin_users WHERE username = %s", (str(payload.get("sub", "")).strip(),))
        fila = cur.fetchone()
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    if not fila or not fila[2]:
        raise HTTPException(status_code=403, detail="Tu cuenta está desactivada o no existe")
    rol, permisos_raw, _a, es_terr, terr = fila
    if str(rol or "").lower() != "admin":
        try:
            permisos = json.loads(permisos_raw) if permisos_raw else {}
        except Exception:
            permisos = {}
        if permisos.get("notificaciones") is not True:
            raise HTTPException(status_code=403, detail="No tienes permiso para ver las notificaciones")
    return terr if (es_terr and terr) else None


_ENT_BASE = """
    WITH dest AS (
        SELECT u.id, u.nombre_completo, u.correo, u.cargo, u.territorio
        FROM usuarios u
        WHERE COALESCE(u.activo, TRUE) = TRUE
          AND ((SELECT enviada_a_todos FROM notificaciones WHERE id = %(nid)s) = TRUE
               OR u.id IN (SELECT usuario_id FROM notificacion_usuarios WHERE notificacion_id = %(nid)s))
          {terr}
    ), est AS (
        SELECT d.*, l.leida_en, e.enterado_at,
               CASE WHEN e.id IS NOT NULL THEN 'enterado' WHEN l.id IS NOT NULL THEN 'vieron' ELSE 'sin_leer' END AS estado
        FROM dest d
        LEFT JOIN notificacion_leidos l ON l.notificacion_id = %(nid)s AND l.usuario_id = d.id
        LEFT JOIN notificacion_enterados e ON e.notificacion_id = %(nid)s AND e.usuario_id = d.id
    )
"""


def _ent_sql(territorio):
    return _ENT_BASE.format(terr="AND u.territorio = %(terr)s" if territorio else "")


@app.get("/admin/notificaciones/{notificacion_id}/enterados")
async def admin_enterados(notificacion_id: int, request: Request, estado: str = "enterado", q: str = "", limit: int = 50, offset: int = 0):
    payload = _jwt_admin(request)
    territorio = _notif_alcance(payload)
    estado = estado if estado in ("enterado", "vieron", "sin_leer") else "enterado"
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT titulo, requiere_enterado, enviada_a_todos, fecha_envio FROM notificaciones WHERE id = %s", (notificacion_id,))
        n = cur.fetchone()
        if not n:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        prm = {"nid": notificacion_id, "terr": territorio}
        base = _ent_sql(territorio)
        cur.execute(base + "SELECT COUNT(*), COUNT(*) FILTER (WHERE estado='enterado'), COUNT(*) FILTER (WHERE estado='vieron'), COUNT(*) FILTER (WHERE estado='sin_leer') FROM est", prm)
        total, ent, vie, sin = cur.fetchone()
        filtro = "WHERE estado = %(estado)s"
        prm["estado"] = estado
        if q.strip():
            filtro += " AND (LOWER(nombre_completo) LIKE %(q)s OR LOWER(COALESCE(correo,'')) LIKE %(q)s OR LOWER(COALESCE(territorio,'')) LIKE %(q)s)"
            prm["q"] = f"%{q.strip().lower()}%"
        cur.execute(base + f"SELECT COUNT(*) FROM est {filtro}", prm)
        n_filtrados = cur.fetchone()[0]
        orden = {"enterado": "enterado_at DESC", "vieron": "leida_en DESC NULLS LAST", "sin_leer": "nombre_completo"}[estado]
        prm["lim"], prm["off"] = limit, offset
        cur.execute(base + f"SELECT id, nombre_completo, correo, cargo, territorio, leida_en, enterado_at FROM est {filtro} ORDER BY {orden} LIMIT %(lim)s OFFSET %(off)s", prm)
        filas = [{"id": r[0], "nombre": r[1], "correo": r[2], "cargo": r[3], "territorio": r[4],
                  "vista_en": r[5].isoformat() if r[5] else None, "enterado_en": r[6].isoformat() if r[6] else None} for r in cur.fetchall()]
        pct = lambda x: round(x * 100.0 / total, 1) if total else 0
        return {"titulo": n[0], "requiere_enterado": bool(n[1]), "enviada_a_todos": bool(n[2]),
                "resumen": {"destinatarios": total, "enterados": ent, "vieron": vie, "sin_leer": sin,
                            "pct_enterados": pct(ent), "pct_vieron": pct(vie), "pct_sin_leer": pct(sin)},
                "estado": estado, "total_filtrados": n_filtrados, "usuarios": filas, "limit": limit, "offset": offset,
                "solo_territorio": territorio}
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass


@app.get("/admin/notificaciones/{notificacion_id}/enterados/excel")
async def admin_enterados_excel(notificacion_id: int, request: Request):
    payload = _jwt_admin(request)
    territorio = _notif_alcance(payload)
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT titulo FROM notificaciones WHERE id = %s", (notificacion_id,))
        n = cur.fetchone()
        if not n:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        cur.execute(_ent_sql(territorio) + "SELECT nombre_completo, correo, cargo, territorio, estado, leida_en, enterado_at FROM est ORDER BY CASE estado WHEN 'enterado' THEN 0 WHEN 'vieron' THEN 1 ELSE 2 END, nombre_completo",
                    {"nid": notificacion_id, "terr": territorio})
        filas = cur.fetchall()
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    import xlsxwriter
    buf = _io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "remove_timezone": True, "strings_to_formulas": False})
    ws = wb.add_worksheet("Enterados")
    f_t = wb.add_format({"bold": True, "font_size": 14, "font_color": "#FFFFFF", "bg_color": "#1F6F43"})
    f_h = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F6F43", "border": 1, "align": "center"})
    f_dt = wb.add_format({"num_format": "dd/mm/yyyy hh:mm"})
    ws.merge_range(0, 0, 0, 6, f"Enterados · {n[0]}", f_t)
    cols = [("Nombre", 36), ("Correo", 32), ("Cargo", 22), ("Territorio", 24), ("Estado", 12), ("Vista el", 18), ("Enterado el", 18)]
    nombres = {"enterado": "Enterado", "vieron": "Solo vio", "sin_leer": "Sin leer"}
    for i, (c, w) in enumerate(cols):
        ws.set_column(i, i, w)
        ws.write(2, i, c, f_h)
    for r, f in enumerate(filas, start=3):
        ws.write(r, 0, f[0] or ""); ws.write(r, 1, f[1] or ""); ws.write(r, 2, f[2] or ""); ws.write(r, 3, f[3] or "")
        ws.write(r, 4, nombres.get(f[4], f[4]))
        if f[5]: ws.write_datetime(r, 5, f[5], f_dt)
        if f[6]: ws.write_datetime(r, 6, f[6], f_dt)
    ws.freeze_panes(3, 1)
    ws.autofilter(2, 0, 2 + len(filas), len(cols) - 1)
    wb.close()
    nombre = f"Enterados_{notificacion_id}_{_dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    return Response(content=buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.post("/admin/notificaciones/{notificacion_id}/recordar")
async def admin_recordar_enterado(notificacion_id: int, request: Request):
    """Recordatorio push solo a quienes aún no marcan 'Enterado' (máx. 1 cada 10 minutos por notificación)."""
    payload = _jwt_admin(request)
    territorio = _notif_alcance(payload)
    ahora = _time.time()
    if ahora - _recordar_hits.get(notificacion_id, 0) < 600:
        raise HTTPException(status_code=429, detail="Ya se envió un recordatorio hace poco. Espera unos minutos.")
    conexion = None
    try:
        conexion, cur = abrir_conexion_aislada()
        cur.execute("SELECT titulo FROM notificaciones WHERE id = %s", (notificacion_id,))
        n = cur.fetchone()
        if not n:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        cur.execute(_ent_sql(territorio) + "SELECT id FROM est WHERE estado <> 'enterado'", {"nid": notificacion_id, "terr": territorio})
        pendientes = [r[0] for r in cur.fetchall()]
        subs = _push_suscripciones_de(conexion, pendientes) if pendientes else []
    finally:
        try:
            if conexion:
                conexion.close()
        except Exception:
            pass
    _recordar_hits[notificacion_id] = ahora
    res = await _aio.get_event_loop().run_in_executor(None, _push_enviar, subs, _push_payload("Recordatorio: " + n[0], "Abre el aviso y toca Enterado.", notificacion_id), notificacion_id)
    return {"ok": True, "pendientes": len(pendientes), "con_push": len({s[1] for s in subs}), **res}

# ==================== FIN ENTERADO DE NOTIFICACIONES ====================


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
