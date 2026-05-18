"""
database.py — Capa de acceso a datos (Repository Pattern).

Conceptos aplicados:
  ┌─────────────────────────────────────────────────────────────┐
  │  Context Manager  → garantiza cierre de conexión siempre    │
  │  Repository Pattern → la UI nunca escribe SQL directamente  │
  │  dataclass         → modelo de datos tipado y limpio        │
  │  Comprensión de listas → transformación de rows a objetos   │
  └─────────────────────────────────────────────────────────────┘

Por qué Repository Pattern:
  Si mañana migramos de SQLite a PostgreSQL, solo tocamos este archivo.
  La UI y la lógica de negocio no saben qué motor de DB usamos.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, List, Optional

import pandas as pd

from config import DB_NAME, BASE_APP_PORT
from logger_config import get_logger

logger = get_logger(__name__)


# ─── Modelo de datos ──────────────────────────────────────────────────────────

@dataclass
class AppRecord:
    """
    Representa una fila de la tabla `apps`.
    
    Usar dataclass en lugar de dict evita typos como row["nme"]
    y hace el código autodocumentado.
    """
    id: Optional[int]
    name: str
    script_path: str
    env_path: str
    port: int
    pid: Optional[int] = None

    @property
    def is_running(self) -> bool:
        """Propiedad computada: el canal está activo si tiene PID."""
        return self.pid is not None

    @property
    def local_url(self) -> str:
        return f"http://localhost:{self.port}"


# ─── Context Manager de conexión ──────────────────────────────────────────────

@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager que garantiza cierre de conexión incluso ante excepciones.
    
    Uso:
        with get_connection() as conn:
            conn.execute(...)
        # conn.close() llamado automáticamente — siempre.
    
    Yield vs Return:
        `yield` convierte esta función en un generador que el bloque `with`
        puede pausar y reanudar → perfectamente intuitivo para recursos.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Acceso por nombre de columna
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("DB error, rollback ejecutado: %s", e)
        raise
    finally:
        conn.close()


# ─── Repository ───────────────────────────────────────────────────────────────

class AppRepository:
    """
    Repositorio único de acceso a la tabla `apps`.
    
    Cada método encapsula exactamente una operación de negocio.
    La UI solo llama métodos semánticos, nunca SQL crudo.
    """

    @staticmethod
    def init_schema() -> None:
        """Crea la tabla si no existe. Idempotente."""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    UNIQUE NOT NULL,
                    script_path TEXT    NOT NULL,
                    env_path    TEXT    NOT NULL,
                    port        INTEGER UNIQUE NOT NULL,
                    pid         INTEGER
                )
            """)
        logger.info("Schema verificado/inicializado correctamente.")

    @staticmethod
    def get_next_port() -> int:
        """
        Obtiene el próximo puerto disponible de forma atómica.
        
        Usa MAX(port) en la misma transacción para evitar race conditions
        en escenarios de uso concurrente.
        """
        with get_connection() as conn:
            row = conn.execute("SELECT MAX(port) FROM apps").fetchone()
            max_port = row[0]
        return (max_port + 1) if max_port else BASE_APP_PORT

    @staticmethod
    def get_all() -> List[AppRecord]:
        """
        Retorna todos los registros como lista de AppRecord.
        
        Comprensión de listas: transforma cada sqlite3.Row
        en un AppRecord tipado de forma concisa y pythónica.
        """
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM apps ORDER BY port").fetchall()

        # Comprensión de listas → rows a dataclasses
        return [
            AppRecord(
                id=row["id"],
                name=row["name"],
                script_path=row["script_path"],
                env_path=row["env_path"],
                port=row["port"],
                pid=row["pid"],
            )
            for row in rows
        ]

    @staticmethod
    def get_as_dataframe() -> pd.DataFrame:
        """Versión DataFrame para el Data Editor de Streamlit."""
        with get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM apps ORDER BY port", conn)

    @staticmethod
    def insert(name: str, script_path: str, env_path: str, port: int) -> None:
        """Inserta un nuevo canal. Lanza IntegrityError si el nombre ya existe."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO apps (name, script_path, env_path, port) VALUES (?, ?, ?, ?)",
                (name, script_path, env_path, port),
            )
        logger.info("Canal registrado: '%s' en puerto %d", name, port)

    @staticmethod
    def update_pid(app_id: int, pid: Optional[int]) -> None:
        """Actualiza el PID de un canal (None = detenido)."""
        with get_connection() as conn:
            conn.execute("UPDATE apps SET pid = ? WHERE id = ?", (pid, app_id))
        logger.debug("PID actualizado → app_id=%d, pid=%s", app_id, pid)

    @staticmethod
    def delete(app_id: int) -> None:
        """Elimina un canal por ID."""
        with get_connection() as conn:
            conn.execute("DELETE FROM apps WHERE id = ?", (app_id,))
        logger.info("Canal eliminado: id=%d", app_id)

    @staticmethod
    def sync_from_dataframe(df: pd.DataFrame) -> None:
        """
        Sobreescribe la tabla completa desde un DataFrame editado.
        Usado por el Data Editor de Streamlit.
        """
        with get_connection() as conn:
            df.to_sql("apps", conn, if_exists="replace", index=False)
        logger.info("Tabla 'apps' sincronizada desde Data Editor.")

    @staticmethod
    def get_stats() -> dict:
        """
        Agrega métricas del hub para el dashboard de Home.
        Una sola query en lugar de N queries.
        """
        with get_connection() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                        AS total,
                    COUNT(pid)                      AS running,
                    COUNT(*) - COUNT(pid)           AS stopped,
                    COALESCE(MIN(port), 0)          AS min_port,
                    COALESCE(MAX(port), 0)          AS max_port
                FROM apps
            """).fetchone()
        return dict(row)
