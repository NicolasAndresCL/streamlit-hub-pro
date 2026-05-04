"""
hub_app.py — Entry point del Streamlit Hub.

Arquitectura de este archivo:
  Este módulo es SOLO UI. No contiene lógica de negocio ni SQL.
  Cada vista es una función privada (_view_home, _view_config, etc.)
  lo que permite:
    - Leer el flujo principal de un vistazo (ver bloque main)
    - Testear vistas individualmente
    - Reordenar vistas sin riesgo de romper nada

Separación de responsabilidades:
  hub_app.py      → Render de UI
  database.py     → Acceso a datos
  process_manager → Lógica de procesos
  config.py       → Constantes
  logger_config   → Logging
"""

import sqlite3

import pandas as pd
import streamlit as st

from config import AUTOMATION_CARDS
from database import AppRecord, AppRepository
from logger_config import get_logger
from process_manager import launch_automation, start_channel, stop_channel

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPONENTES REUTILIZABLES
# ═══════════════════════════════════════════════════════════════════════════════

def _render_channel_card(record: AppRecord) -> None:
    """
    Renderiza la tarjeta de un canal individual.
    
    Extraído a función propia para no repetir la lógica en el loop de Home.
    Recibe un AppRecord (dataclass tipado), no un dict — más seguro.
    """
    with st.container(border=True):
        st.subheader(f":yellow[{record.name}]")
        st.caption(f"📍 Script: `{record.script_path}`")
        st.caption(f"🐍 Entorno: `{record.env_path}`")
        st.text(f"🔌 Puerto: {record.port}")

        if not record.is_running:
            if st.button("▶️ Iniciar Canal", key=f"start_{record.id}", use_container_width=True):
                result = start_channel(record.id, record.script_path, record.env_path, record.port)
                if result.ok:
                    st.success(result.message)
                else:
                    st.error(result.message)
                st.rerun()
        else:
            st.success("🟢 En ejecución")
            st.markdown(f"**[🔗 Abrir App]({record.local_url})** — `localhost:{record.port}`")
            if st.button("⏹️ Detener Canal", key=f"stop_{record.id}", use_container_width=True):
                result = stop_channel(record.id, record.pid)
                if result.ok:
                    st.warning(result.message)
                else:
                    st.error(result.message)
                st.rerun()


def _render_metrics(stats: dict) -> None:
    """
    Renderiza las métricas del hub usando st.metric (novedad vs versión original).
    Proporciona un snapshot visual del estado del sistema al instante.
    """
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Canales Registrados", stats["total"])
    col2.metric("🟢 En Ejecución", stats["running"])
    col3.metric("🔴 Detenidos", stats["stopped"])


# ═══════════════════════════════════════════════════════════════════════════════
#  VISTAS
# ═══════════════════════════════════════════════════════════════════════════════

def _view_home() -> None:
    st.header("🏠 :red[Mis Canales Activos]")

    stats = AppRepository.get_stats()
    _render_metrics(stats)
    st.divider()

    records = AppRepository.get_all()

    if not records:
        st.info("No hay canales registrados. Ve a **⚙️ Configuración** para agregar el primero.")
        return

    cols = st.columns(3)
    for idx, record in enumerate(records):
        with cols[idx % 3]:
            _render_channel_card(record)


def _view_config() -> None:
    st.header("⚙️ :red[Registrar Nuevo Canal]")
    st.markdown(
        "Agrega una nueva aplicación al Hub. "
        "Usa **rutas absolutas** si las apps están en carpetas distintas."
    )

    with st.form("new_app_form", clear_on_submit=True):
        new_name = st.text_input(
            "Nombre del Canal",
            placeholder="Ej: Workshift Analytics",
        )
        new_script = st.text_input(
            "Ruta del script principal (.py)",
            placeholder=r"Ej: C:/dev/proyectos/mi_app/app.py",
        )
        new_env = st.text_input(
            "Ruta de la carpeta del entorno (venv/env)",
            placeholder=r"Ej: C:/dev/proyectos/mi_app/env",
        )
        submitted = st.form_submit_button("💾 Guardar y Registrar Canal", type="primary")

    if submitted:
        # Validación de campos vacíos
        missing = [label for label, val in [
            ("Nombre", new_name),
            ("Script", new_script),
            ("Entorno", new_env),
        ] if not val.strip()]

        if missing:
            st.error(f"⚠️ Campos requeridos incompletos: {', '.join(missing)}")
            return

        next_port = AppRepository.get_next_port()
        try:
            AppRepository.insert(new_name.strip(), new_script.strip(), new_env.strip(), next_port)
            st.success(f"✅ Canal **{new_name}** registrado en el puerto `{next_port}`.")
            logger.info("Canal registrado via UI: '%s'", new_name)
        except sqlite3.IntegrityError:
            st.error("❌ Ya existe un canal con ese nombre. Usa un nombre único.")

    # ── Lista de canales actuales (solo lectura, como referencia) ─────────────
    st.divider()
    st.subheader("📋 Canales registrados actualmente")
    records = AppRepository.get_all()
    if records:
        # Comprensión de listas: genera tabla resumen
        summary_data = [
            {"Canal": r.name, "Puerto": r.port, "Estado": "🟢 Activo" if r.is_running else "🔴 Detenido"}
            for r in records
        ]
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
    else:
        st.caption("Sin canales registrados aún.")


def _view_db() -> None:
    st.header("🗄️ :red[Gestión de Base de Datos]")
    st.write("Visualiza, edita o elimina los registros directamente desde la tabla.")

    df_apps = AppRepository.get_as_dataframe()

    edited_df = st.data_editor(
        df_apps,
        num_rows="dynamic",
        use_container_width=True,
        key="db_editor",
        hide_index=True,
        column_config={
            "id":          st.column_config.NumberColumn("ID", disabled=True),
            "name":        st.column_config.TextColumn("Nombre"),
            "script_path": st.column_config.TextColumn("Script (.py)"),
            "env_path":    st.column_config.TextColumn("Entorno Virtual"),
            "port":        st.column_config.NumberColumn("Puerto", min_value=1024, max_value=65535),
            "pid":         st.column_config.NumberColumn("PID (proceso)", disabled=True),
        },
    )

    col_save, col_export = st.columns([2, 1])

    with col_save:
        if st.button("💾 Guardar Cambios en DB", type="primary", use_container_width=True):
            AppRepository.sync_from_dataframe(edited_df)
            st.success("✅ Base de datos sincronizada.")
            st.rerun()

    with col_export:
        # NOVEDAD: Exportación CSV directa desde la UI
        csv_data = df_apps.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Exportar CSV",
            data=csv_data,
            file_name="canales_hub_backup.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── Log del hub ───────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Log del Hub (últimas 50 líneas)")
    try:
        with open("hub.log", "r", encoding="utf-8") as f:
            # Comprensión de listas: últimas 50 líneas del log
            lines = [line.rstrip() for line in f.readlines()]
            last_lines = lines[-50:] if len(lines) > 50 else lines
        st.code("\n".join(last_lines), language=None)
    except FileNotFoundError:
        st.caption("El archivo `hub.log` aún no existe. Se creará al primer evento.")


def _view_automations() -> None:
    st.header("💻 :red[Scripts y Automatizaciones]")
    st.markdown(
        "Lanza scripts en consolas independientes. "
        "El Hub seguirá funcionando sin interrupciones."
    )

    # NOVEDAD: la cuadrícula de cards se genera dinámicamente desde AUTOMATION_CARDS
    # Para añadir una nueva automatización: solo edita config.py — aquí no hay que tocar nada.
    # Esto es el principio Open/Closed: abierto para extensión, cerrado para modificación.
    cols = st.columns(2)
    for idx, card in enumerate(AUTOMATION_CARDS):
        with cols[idx % 2]:
            with st.container(border=True):
                st.subheader(f":yellow[{card.title}]")
                st.caption(card.caption)
                st.caption(f"📍 `{card.path_hint}`")

                if st.button("▶️ Lanzar", key=card.key, use_container_width=True):
                    # Callbacks: inyectamos st.success y st.error como callbacks
                    # launch_automation no sabe nada de Streamlit —
                    # recibe funciones genéricas Callable[[str], None]
                    launch_automation(
                        cwd=card.cwd,
                        python_exe=card.python_exe,
                        script=card.script,
                        on_success=st.success,   # ← callback de éxito
                        on_error=st.error,       # ← callback de error
                    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

MENU_OPTIONS = {
    "**:blue[🏠 Home]**":              _view_home,
    "**:green[⚙️ Configuración]**":    _view_config,
    "**:orange[🗄️ DB]**":             _view_db,
    "**:violet[💻 Automatizaciones]**": _view_automations,
}


# Diccionario de despacho (Dispatch Table / Strategy Pattern).

# En lugar de if/elif/elif/elif, mapeamos cada opción del menú
# directamente a su función de vista. El bloque `main` llama
# `MENU_OPTIONS[menu]()` — una sola línea para todas las vistas.

# Ventaja: agregar una vista nueva = agregar una entrada al dict.



def _render_sidebar() -> str:
    """Renderiza el sidebar y retorna la opción seleccionada."""
    st.sidebar.title("Navegación")
    menu = st.sidebar.radio("Ir a:", list(MENU_OPTIONS.keys()))
    st.sidebar.divider()
    st.sidebar.caption(":green[Panel de Control Centralizado]")
    st.sidebar.markdown(
        "<p style='color:#17A2B8;font-weight:bold;font-size:0.85em;'>"
        "Nicolás Andrés Cano Leal — 2026"
        "</p>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(":green[Desarrollado con ❤️ en Streamlit y Python]")
    st.sidebar.divider()
    return menu


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Punto de entrada principal del Hub.
    
    Responsabilidades:
      1. Configurar la página
      2. Inicializar la DB (idempotente)
      3. Renderizar sidebar y obtener selección
      4. Despachar a la vista correspondiente
    
    Este bloque es tan limpio que puedes entender toda la app en 5 líneas.
    """
    st.set_page_config(
        page_title="Streamlit Hub",
        layout="wide",
        page_icon="🚀",
    )
    st.title("🚀 :blue[Hub de Aplicaciones]")

    # Inicializar schema de DB (idempotente — seguro llamar siempre)
    AppRepository.init_schema()

    # Sidebar → selección de vista
    selected_menu = _render_sidebar()

    # Dispatch table: llamamos la vista correspondiente
    # Sin if/elif — el dict hace el despacho directamente
    view_fn = MENU_OPTIONS.get(selected_menu)
    if view_fn:
        view_fn()


if __name__ == "__main__":
    main()
