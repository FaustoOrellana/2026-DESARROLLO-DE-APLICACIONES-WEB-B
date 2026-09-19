import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carga las variables del archivo .env automáticamente
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "techmanager_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD")
}

def obtener_conexion():
    """Retorna una conexión activa con PostgreSQL."""
    try:
        conn = psycopg2.connect(
            **DB_CONFIG,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error al conectar con PostgreSQL: {e}")
        return None