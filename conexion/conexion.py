import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "techmanager_db",
    "user": "postgres",
    "password": "faly051996"
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