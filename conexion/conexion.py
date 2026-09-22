import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carga las variables del archivo .env automáticamente en local
load_dotenv()

def obtener_conexion():
    """Retorna una conexión activa con PostgreSQL (compatible con Local y Render)."""
    try:
        # 1. Si existe DATABASE_URL (usado por Render en producción)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Corrección por si Render usa el prefijo antiguo postgres://
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

        # 2. Si no hay DATABASE_URL, usa la configuración local del .env
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "techmanager_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            cursor_factory=RealDictCursor
        )
        return conn

    except psycopg2.Error as e:
        print(f"Error al conectar con PostgreSQL: {e}")
        return None