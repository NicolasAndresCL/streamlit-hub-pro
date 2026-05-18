import logging
import sqlite3
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
import psutil
import streamlit as st

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("hub.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("hub")


# ---------------------------------------------------------------------------
# Database Manager
# ---------------------------------------------------------------------------
class DatabaseManager:
    _DB_NAME = "canales_hub.db"
    _BASE_PORT = 8501

    def __init__(self):
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._DB_NAME)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    UNIQUE,
                    script_path TEXT,
                    env_path    TEXT,
                    port        INTEGER UNIQUE,
                    pid         INTEGER
                )
            """)
        logger.info("Base de datos inicializada.")

    # --- Getters ---

    def get_all_apps(self) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query("SELECT * FROM apps", conn)

    def get_next_port(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(port) FROM apps").fetchone()
            max_port = row[0] if row[0] is not None else self._BASE_PORT
            return max_port + 1

    # --- Setters ---

    def set_pid(self, app_id: int, pid: Optional[int]) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE apps SET pid = ? WHERE id = ?", (pid, app_id))
        logger.info(f"PID de app id={app_id} actualizado a {pid}.")

    def add_app(self, name: str, script_path: str, env_path: str) -> None:
        port = self.get_next_port()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO apps (name, script_path, env_path, port) VALUES (?, ?, ?, ?)",
                (name, script_path, env_path, port),
            )
        logger.info(f"App '{name}' registrada en puerto {port}.")

    def save_dataframe(self, df: pd.DataFrame) -> None:
        with self._connect() as conn:
            df.to_sql("apps", conn, if_exists="replace", index=False)
        logger.info("DataFrame guardado en DB.")

    # --- PID Cleanup ---

    def cleanup_stale_pids(self) -> None:
        """Borra PIDs de procesos que ya no existen en el sistema."""
        df = self.get_all_apps()
        stale_ids = [
            int(row["id"])
            for _, row in df.iterrows()
            if pd.notna(row["pid"]) and not ProcessManager.is_running(int(row["pid"]))
        ]
        if stale_ids:
            placeholders = ",".join("?" * len(stale_ids))
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE apps SET pid = NULL WHERE id IN ({placeholders})",
                    stale_ids,
                )
            logger.warning(f"PIDs obsoletos limpiados para app ids: {stale_ids}")


# ---------------------------------------------------------------------------
# Process Manager
# ---------------------------------------------------------------------------
class ProcessManager:

    @staticmethod
    def is_running(pid: int) -> bool:
        """Verifica si un proceso con ese PID está activo (confiable en Windows)."""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
        except Exception as e:
            logger.debug(f"Error verificando PID {pid}: {e}")
            return False

    @staticmethod
    def start(app_id: int, script_path: str, env_path: str, port: int, db: DatabaseManager) -> None:
        python_exe = Path(env_path) / "Scripts" / "python.exe"

        if not python_exe.exists():
            msg = f"No se encontró Python en: {python_exe}"
            logger.error(msg)
            st.error(f"❌ {msg}")
            return

        app_dir = str(Path(script_path).parent)
        cmd = [
            str(python_exe), "-m", "streamlit", "run", script_path,
            "--server.port", str(port),
            "--server.headless", "true",
        ]

        try:
            process = subprocess.Popen(cmd, cwd=app_dir)
            db.set_pid(app_id, process.pid)
            logger.info(f"App id={app_id} iniciada — PID {process.pid}, puerto {port}.")
            st.success(f"✅ App iniciada en puerto {port} (PID: {process.pid})")
        except Exception as e:
            logger.exception(f"Error iniciando app id={app_id}: {e}")
            st.error(f"❌ Error al iniciar el proceso: {e}")

    @staticmethod
    def stop(app_id: int, pid: int, db: DatabaseManager) -> None:
        try:
            if not ProcessManager.is_running(pid):
                st.warning("⚠️ El proceso ya no estaba activo.")
                logger.warning(f"PID {pid} inactivo al intentar detenerlo.")
                return

            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
            logger.info(f"PID {pid} terminado correctamente.")
            st.warning("⏹️ Proceso detenido.")

        except psutil.NoSuchProcess:
            logger.warning(f"PID {pid} no encontrado en el sistema.")
            st.error("⚠️ El proceso ya no existe en el sistema.")
        except psutil.TimeoutExpired:
            proc.kill()
            logger.warning(f"PID {pid} forzado a cerrar (timeout).")
            st.warning("⏹️ Proceso forzado a cerrar.")
        except Exception as e:
            logger.exception(f"Error deteniendo PID {pid}: {e}")
            st.error(f"❌ Error al detener el proceso: {e}")
        finally:
            db.set_pid(app_id, None)


# ---------------------------------------------------------------------------
# Automation Runner
# ---------------------------------------------------------------------------
class AutomationRunner:
    def __init__(self, label: str, icon: str, caption: str, cwd: str, python_exe: str, script: str):
        self._label = label
        self._icon = icon
        self._caption = caption
        self._cwd = Path(cwd)
        self._python_exe = Path(python_exe)
        self._script = Path(script)

    # --- Properties ---

    @property
    def label(self) -> str:
        return self._label

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def caption(self) -> str:
        return self._caption

    @property
    def path_hint(self) -> str:
        return str(self._cwd)

    @property
    def is_valid(self) -> bool:
        return self._python_exe.exists() and self._script.exists()

    # --- Callback ---

    def launch(self) -> None:
        if not self.is_valid:
            msg = f"Archivos no encontrados para '{self._label}': {self._python_exe} / {self._script}"
            logger.error(msg)
            st.error(f"❌ {msg}")
            return
        try:
            subprocess.Popen(
                [str(self._python_exe), str(self._script)],
                cwd=str(self._cwd),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            logger.info(f"Automatización '{self._label}' lanzada.")
            st.success(f"✅ {self._label} abierto en una nueva ventana.")
        except Exception as e:
            logger.exception(f"Error lanzando '{self._label}': {e}")
            st.error(f"❌ Error al abrir {self._label}: {e}")


# ---------------------------------------------------------------------------
# UI Builder
# ---------------------------------------------------------------------------
class HubUI:
    _AUTOMATIONS = [
        AutomationRunner(
            label="Login Automático",
            icon="🎓",
            caption="Abre menú para sesiones de Cisco y Sence.",
            cwd=r"C:\dev\projects\logs_santotomas",
            python_exe=r"C:\dev\projects\logs_santotomas\env\Scripts\python.exe",
            script=r"C:\dev\projects\logs_santotomas\launcher.py",
        ),
        AutomationRunner(
            label="Automatizador (Mouse/Web)",
            icon="⚙️",
            caption="Activa el menú de simulación de actividad.",
            cwd=r"C:\dev\projects\automatizacion",
            python_exe=r"C:\dev\projects\automatizacion\env\Scripts\python.exe",
            script=r"C:\dev\projects\automatizacion\automatizador.py",
        ),
    ]

    _MENU_OPTIONS = [
        "**:blue[🏠 Home]**",
        "**:green[⚙️ Configuración]**",
        "**:orange[🗄️ DB]**",
        "**:violet[💻 Automatizaciones]**",
    ]

    def __init__(self, db: DatabaseManager):
        self._db = db

    # --- Sidebar ---

    def render_sidebar(self) -> str:
        st.sidebar.title("Navegación")
        menu = st.sidebar.radio("Ir a:", self._MENU_OPTIONS)
        st.sidebar.divider()
        st.sidebar.caption(":green[Panel de Control Centralizado]")
        st.sidebar.markdown(
            '<p style="color:#17A2B8;font-weight:bold;font-size:0.85em;">'
            "Nicolás Andrés Cano Leal - 2026</p>",
            unsafe_allow_html=True,
        )
        st.sidebar.caption(":green[Desarrollado con ❤️ en Streamlit y Python]")
        st.sidebar.divider()
        return menu

    # --- Views ---

    def render_home(self) -> None:
        st.header("🏠 :red[Mis Canales Activos]")
        df = self._db.get_all_apps()

        if df.empty:
            st.info("No hay aplicaciones registradas. Ve a 'Configuración' para agregar tu primer canal.")
            return

        cols = st.columns(3)
        for index, row in df.iterrows():
            with cols[index % 3]:
                with st.container(border=True):
                    self._render_app_card(row)

    def _render_app_card(self, row) -> None:
        """Callback: renderiza la tarjeta de una app con su estado real de PID."""
        st.subheader(f":yellow[{row['name']}]")
        st.caption(f"📍 Script: `{row['script_path']}`")
        st.caption(f"🐍 Entorno: `{row['env_path']}`")
        st.text(f"🔌 Puerto: {row['port']}")

        pid_value = row["pid"]
        is_alive = pd.notna(pid_value) and ProcessManager.is_running(int(pid_value))

        if is_alive:
            st.success("🟢 En ejecución")
            st.markdown(
                f"**[🔗 Abrir Aplicación (localhost:{row['port']})](http://localhost:{row['port']})**"
            )
            if st.button("⏹️ Detener Canal", key=f"stop_{row['id']}", use_container_width=True):
                ProcessManager.stop(row["id"], int(pid_value), self._db)
                st.rerun()
        else:
            if pd.notna(pid_value):
                self._db.set_pid(row["id"], None)
            if st.button("▶️ Iniciar Canal", key=f"start_{row['id']}", use_container_width=True):
                ProcessManager.start(
                    row["id"], row["script_path"], row["env_path"], row["port"], self._db
                )
                st.rerun()

    def render_config(self) -> None:
        st.header("⚙️ :red[Registrar Nuevo Canal]")
        st.markdown("Agrega una nueva aplicación. Usa **rutas absolutas** si los proyectos están en carpetas diferentes.")

        with st.form("new_app_form"):
            name = st.text_input("Nombre de la Aplicación", placeholder="Ej: Workshift Analytics")
            script = st.text_input("Ruta del script principal (.py)", placeholder="Ej: C:/dev/proyectos/mi_app/app.py")
            env = st.text_input("Ruta del entorno virtual (venv/env)", placeholder="Ej: C:/dev/proyectos/mi_app/env")

            if st.form_submit_button("Guardar y Registrar App", type="primary"):
                self._on_register_app(name, script, env)

    def _on_register_app(self, name: str, script: str, env: str) -> None:
        """Callback: valida y registra una nueva app en la DB."""
        fields = [name, script, env]
        if not all(fields):
            st.error("⚠️ Completa todos los campos antes de registrar.")
            return
        try:
            self._db.add_app(name, script, env)
            st.success(f"✅ Canal '{name}' registrado exitosamente.")
        except sqlite3.IntegrityError:
            st.error("❌ Ya existe una aplicación registrada con ese nombre.")
            logger.warning(f"Nombre duplicado al registrar: '{name}'")

    def render_db_view(self) -> None:
        st.header("🗄️ :red[Gestión de Base de Datos]")
        st.write("Visualiza, edita o elimina registros directamente desde la tabla.")

        df = self._db.get_all_apps()
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key="db_editor",
            hide_index=True,
        )

        if st.button("💾 Guardar Cambios en DB", type="primary"):
            self._on_save_db(edited_df)

    def _on_save_db(self, df: pd.DataFrame) -> None:
        """Callback: persiste el DataFrame editado en la DB."""
        try:
            self._db.save_dataframe(df)
            st.success("✅ Base de datos sincronizada correctamente.")
        except Exception as e:
            logger.exception(f"Error guardando DB: {e}")
            st.error(f"❌ Error al guardar: {e}")

    def render_automations(self) -> None:
        st.header("💻 :red[Scripts y Automatizaciones]")
        st.markdown("Lanza tus scripts en una consola independiente. El Hub seguirá funcionando.")

        cols = st.columns(len(self._AUTOMATIONS))
        for col, runner in zip(cols, self._AUTOMATIONS):
            with col:
                with st.container(border=True):
                    st.subheader(f"{runner.icon} :yellow[{runner.label}]")
                    st.caption(runner.caption)
                    st.caption(f"📍 `{runner.path_hint}`")
                    btn_label = "▶️ Abrir " + runner.label.split()[0]
                    if st.button(btn_label, key=f"run_{runner.label}", use_container_width=True):
                        runner.launch()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Streamlit Hub", layout="wide", page_icon="🚀")
    st.title("🚀 :blue[Hub de Aplicaciones]")

    db = DatabaseManager()
    db.cleanup_stale_pids()

    ui = HubUI(db)
    menu = ui.render_sidebar()

    views = {
        "**:blue[🏠 Home]**":              ui.render_home,
        "**:green[⚙️ Configuración]**":    ui.render_config,
        "**:orange[🗄️ DB]**":             ui.render_db_view,
        "**:violet[💻 Automatizaciones]**": ui.render_automations,
    }

    render_fn = views.get(menu)
    if render_fn:
        render_fn()


if __name__ == "__main__":
    main()
