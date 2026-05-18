import sys
import subprocess
import signal
import os
from dataclasses import dataclass
from typing import Callable, Optional

from config import IS_WINDOWS, PYTHON_EXEC
from database import AppRepository
from logger_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessResult:
    ok: bool
    message: str
    pid: Optional[int] = None


OnSuccess = Callable[[str], None]
OnError = Callable[[str], None]


def _get_python_executable(env_path: str) -> Optional[str]:
    python_exe = os.path.join(env_path, PYTHON_EXEC)
    return python_exe if os.path.exists(python_exe) else None


def _is_process_alive(pid: int) -> bool:
    """
    Verifica si el proceso existe SIN enviar señales.
    
    Windows: usa tasklist para consultar el PID de forma segura.
    Unix:    os.kill(pid, 0) — señal nula, solo consulta existencia.
    """
    if IS_WINDOWS:
        # tasklist /FI filtra por PID — si aparece en stdout, vive
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def _kill_process(pid: int) -> bool:
    """
    Mata un proceso de forma segura según el SO.
    
    Windows: taskkill /F /PID — fuerza cierre SOLO del proceso indicado.
             NO usa os.kill() porque SIGTERM en Windows es impredecible
             y puede propagar la señal al proceso padre (el Hub).
    
    Unix:    SIGTERM estándar — cooperativo, permite cleanup.
             Si no responde en 3s → SIGKILL.
    
    Returns:
        True si el proceso fue terminado exitosamente.
    """
    if IS_WINDOWS:
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
        )
        # taskkill retorna 0 si mató el proceso, >0 si no lo encontró
        success = result.returncode == 0
        if not success:
            logger.warning("taskkill falló para PID=%d: %s", pid, result.stderr.strip())
        return success
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            # Esperar hasta 3 segundos antes de SIGKILL
            import time
            for _ in range(6):
                time.sleep(0.5)
                if not _is_process_alive(pid):
                    return True
            # Si sigue vivo → forzar
            os.kill(pid, signal.SIGKILL)
            return True
        except ProcessLookupError:
            return True  # Ya no existe, objetivo cumplido
        except Exception as e:
            logger.error("Error matando PID=%d: %s", pid, e)
            return False


def start_channel(app_id: int, script_path: str, env_path: str, port: int) -> ProcessResult:
    python_exe = _get_python_executable(env_path)

    if not python_exe:
        msg = f"Ejecutable Python no encontrado en: {os.path.join(env_path, PYTHON_EXEC)}"
        logger.error(msg)
        return ProcessResult(ok=False, message=f"❌ {msg}")

    if not os.path.isfile(script_path):
        msg = f"Script no encontrado: {script_path}"
        logger.error(msg)
        return ProcessResult(ok=False, message=f"❌ {msg}")

    app_dir = os.path.dirname(script_path)
    cmd = [
        python_exe, "-m", "streamlit", "run", script_path,
        "--server.port", str(port),
        "--server.headless", "true",
    ]

    # En Windows: CREATE_NEW_PROCESS_GROUP aísla el proceso del Hub
    # Esto evita que señales del Hub se propaguen a los canales y viceversa
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP |  # grupo propio
            subprocess.CREATE_NO_WINDOW  # sin la consola del Hub
        )


    try:
        process = subprocess.Popen(cmd, cwd=app_dir, **kwargs)
        AppRepository.update_pid(app_id, process.pid)
        logger.info("Canal iniciado: app_id=%d, pid=%d, port=%d", app_id, process.pid, port)
        return ProcessResult(
            ok=True,
            message=f"✅ Canal iniciado en el puerto {port} (PID: {process.pid})",
            pid=process.pid,
        )
    except Exception as exc:
        logger.exception("Error al iniciar subproceso para app_id=%d", app_id)
        return ProcessResult(ok=False, message=f"❌ Error al iniciar el proceso: {exc}")


def stop_channel(app_id: int, pid: int) -> ProcessResult:
    """
    Detiene un canal de forma segura sin afectar al Hub ni a otros canales.
    """
    if not _is_process_alive(pid):
        logger.warning("PID=%d ya no existe, limpiando DB.", pid)
        AppRepository.update_pid(app_id, None)
        return ProcessResult(
            ok=True,
            message="⚠️ El proceso ya no existía. PID limpiado.",
        )

    killed = _kill_process(pid)
    AppRepository.update_pid(app_id, None)

    if killed:
        logger.info("Canal detenido correctamente: app_id=%d, pid=%d", app_id, pid)
        return ProcessResult(ok=True, message=f"⏹️ Canal detenido (PID: {pid}).")
    else:
        return ProcessResult(ok=False, message=f"❌ No se pudo detener el proceso (PID: {pid}).")


def launch_automation(
    cwd: str,
    python_exe: str,
    script: str,
    on_success: OnSuccess,
    on_error: OnError,
) -> None:
    if not os.path.exists(python_exe):
        on_error(f"❌ Python no encontrado: {python_exe}")
        return

    if not os.path.isfile(script):
        on_error(f"❌ Script no encontrado: {script}")
        return

    kwargs = {"cwd": cwd}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

    try:
        subprocess.Popen([python_exe, script], **kwargs)
        on_success("✅ Lanzado en nueva ventana.")
    except Exception as exc:
        on_error(f"❌ Error al lanzar: {exc}")