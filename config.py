"""
config.py — Configuración centralizada del Hub.

Principio: Single Source of Truth.
Cualquier constante que se use en más de un módulo vive aquí.
"""

import os
from dataclasses import dataclass, field
from typing import List


# ─── Base de datos ────────────────────────────────────────────────────────────
DB_NAME: str = "canales_hub.db"  # ⚠️ Nombre preservado intencionalmente

# ─── Puertos ──────────────────────────────────────────────────────────────────
HUB_PORT: int = 8501
BASE_APP_PORT: int = 8502  # Los canales arrancan desde aquí

# ─── Sistema operativo ────────────────────────────────────────────────────────
IS_WINDOWS: bool = os.name == "nt"

# Python executable relativo al venv según SO
PYTHON_EXEC: str = os.path.join("Scripts", "python.exe") if IS_WINDOWS else os.path.join("bin", "python")


@dataclass(frozen=True)
class AutomationCard:
    """
    Representa una automatización registrada.
    
    Usar dataclass frozen=True garantiza inmutabilidad —
    estas tarjetas son configuración, no estado mutable.
    """
    key: str
    title: str
    caption: str
    path_hint: str
    cwd: str
    python_exe: str
    script: str


# ─── Automatizaciones registradas ─────────────────────────────────────────────
# Para añadir una nueva: simplemente agrega otro AutomationCard a la lista.
# La UI se genera dinámicamente desde esta lista (Open/Closed Principle).
AUTOMATION_CARDS: List[AutomationCard] = [
    AutomationCard(
        key="run_login",
        title="🎓 Login Automático",
        caption="Abre menú para sesiones de Cisco y Sence.",
        path_hint=r"C:\dev\projects\logs_santotomas",
        cwd=r"C:\dev\projects\logs_santotomas",
        python_exe=r"C:\dev\projects\logs_santotomas\env\Scripts\python.exe",
        script=r"C:\dev\projects\logs_santotomas\launcher.py",
    ),
    AutomationCard(
        key="run_auto",
        title="⚙️ Automatizador (Mouse/Web)",
        caption="Activa el menú de simulación de actividad.",
        path_hint=r"C:\dev\projects\automatizacion",
        cwd=r"C:\dev\projects\automatizacion",
        python_exe=r"C:\dev\projects\automatizacion\env\Scripts\python.exe",
        script=r"C:\dev\projects\automatizacion\automatizador.py",
    ),
]
