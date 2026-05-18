# 🚀 Streamlit Hub Pro

> 🇨🇱 [Español](#español) · 🇺🇸 [English](#english)

---

<a name="español"></a>
## 🇨🇱 Español

**Panel de control centralizado para gestionar múltiples aplicaciones Streamlit desde una sola interfaz.**  
Inicia, detiene y monitorea canales independientes con aislamiento de procesos, estado persistente y arquitectura por capas.

### ✨ Características

- 🟢 **Inicio / Detención de canales** de forma independiente sin afectar al Hub
- 📦 **Persistencia en SQLite** — el registro de canales sobrevive reinicios
- 🔌 **Asignación automática de puertos** — sin configuración manual
- 📊 **Dashboard de métricas en vivo** — canales activos y detenidos de un vistazo
- 🗄️ **Data Editor** — CRUD directo sobre la tabla + exportación CSV
- 💻 **Lanzador de automatizaciones** — ejecuta scripts externos en consolas aisladas
- 📋 **Visor de logs integrado** — últimas 50 líneas de `hub.log` dentro de la UI
- 🪟 **Gestión de procesos segura en Windows** — usa `taskkill` en lugar de `os.kill`

### 🏗️ Arquitectura

```
streamlit-hub-pro/
├── hub_app.py           # Entry point — solo UI (Streamlit)
├── database.py          # Repository Pattern + Context Manager (SQLite)
├── process_manager.py   # Lógica de procesos + Result Pattern + Callbacks
├── config.py            # Constantes centralizadas & AutomationCards
├── logger_config.py     # Logger rotativo en disco
├── HubPro.bat           # Lanzador Windows (activa venv + corre el hub)
├── canales_hub.db       # Generado automáticamente en el primer run
└── hub.log              # Generado automáticamente en el primer run
```

### Patrones de diseño aplicados

| Patrón | Módulo | Por qué |
|---|---|---|
| Repository | `database.py` | La UI nunca escribe SQL directamente |
| Context Manager | `get_connection()` | Cierre de conexión garantizado siempre |
| Result Pattern | `ProcessResult` | Lógica de negocio desacoplada de la UI |
| Callbacks | `launch_automation()` | `process_manager` no importa Streamlit |
| Dispatch Table | dict `MENU_OPTIONS` | Sin cadenas if/elif para el routing |
| Open/Closed | lista `AUTOMATION_CARDS` | Nuevas automatizaciones sin tocar la UI |

### ⚙️ Instalación

**Requisitos**
- Python 3.10+
- Windows (la gestión de procesos usa `taskkill`) — Linux/macOS soportado con adaptación menor

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/streamlit-hub-pro.git
cd streamlit-hub-pro

# 2. Crear y activar entorno virtual
python -m venv env
env\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar
streamlit run hub_app.py
```

**O simplemente usa el lanzador (Windows)**
```
HubPro.bat
```
Doble clic o ejecutar desde terminal. Activa el venv y lanza el Hub automáticamente.

### 🖥️ Uso

**🏠 Home — Dashboard de canales**  
Visualiza todos los canales registrados. Inicia o detiene cada uno de forma independiente. Los canales activos muestran un enlace directo a su puerto.

**⚙️ Configuración — Registrar canal**  
Ingresa el nombre, la ruta absoluta al `.py` del canal y la ruta a su entorno virtual. El Hub asigna el siguiente puerto disponible automáticamente.

**🗄️ DB — Gestión de base de datos**  
Edita el registro de canales directamente en una tabla. Exporta a CSV como respaldo.

**💻 Automatizaciones — Lanzador de scripts**  
Ejecuta scripts Python externos en consolas aisladas. Agrega nuevas automatizaciones editando solo `config.py`.

### 🔧 Agregar una nueva automatización

Edita `config.py` y agrega un `AutomationCard` a la lista:

```python
AutomationCard(
    key="run_mi_script",
    title="🤖 Mi Script",
    caption="Hace algo útil.",
    path_hint=r"C:\dev\projects\mi_script",
    cwd=r"C:\dev\projects\mi_script",
    python_exe=r"C:\dev\projects\mi_script\env\Scripts\python.exe",
    script=r"C:\dev\projects\mi_script\main.py",
)
```

La tarjeta aparece automáticamente en la UI en el siguiente reload.

### 📋 Dependencias

```
streamlit
pandas
```

### 👤 Autor

**Nicolás Andrés Cano Leal**  
2026 — Desarrollado con ❤️ en Streamlit y Python

---

<a name="english"></a>
## 🇺🇸 English

**Centralized control panel to manage multiple Streamlit applications from a single interface.**  
Start, stop and monitor independent channels with process isolation, persistent state, and a layered architecture.

### ✨ Features

- 🟢 **Start / Stop channels** independently without affecting the Hub
- 📦 **SQLite persistence** — channel registry survives restarts
- 🔌 **Auto port assignment** — no manual configuration needed
- 📊 **Live metrics dashboard** — active/stopped channel count at a glance
- 🗄️ **Data Editor** — CRUD directly on the DB table + CSV export
- 💻 **Automation launcher** — run external scripts in isolated consoles
- 📋 **Integrated log viewer** — last 50 lines of `hub.log` inside the UI
- 🪟 **Windows-safe process management** — uses `taskkill` instead of `os.kill`

### 🏗️ Architecture

```
streamlit-hub-pro/
├── hub_app.py           # Entry point — UI only (Streamlit)
├── database.py          # Repository Pattern + Context Manager (SQLite)
├── process_manager.py   # Process logic + Result Pattern + Callbacks
├── config.py            # Centralized constants & AutomationCards
├── logger_config.py     # Rotating file logger
├── HubPro.bat           # Windows launcher (activates venv + runs hub)
├── canales_hub.db       # Auto-generated on first run
└── hub.log              # Auto-generated on first run
```

### Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| Repository | `database.py` | UI never writes raw SQL |
| Context Manager | `get_connection()` | Guaranteed connection cleanup |
| Result Pattern | `ProcessResult` | Business logic decoupled from UI |
| Callbacks | `launch_automation()` | `process_manager` has zero Streamlit imports |
| Dispatch Table | `MENU_OPTIONS` dict | No if/elif chains for routing |
| Open/Closed | `AUTOMATION_CARDS` list | Add automations without touching UI code |

### ⚙️ Installation

**Requirements**
- Python 3.10+
- Windows (process management uses `taskkill`) — Linux/macOS supported with minor adaptation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/streamlit-hub-pro.git
cd streamlit-hub-pro

# 2. Create and activate virtual environment
python -m venv env
env\Scripts\activate       # Windows
# source env/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run hub_app.py
```

**Or just use the launcher (Windows)**
```
HubPro.bat
```
Double-click or run from terminal. Activates the venv and launches the Hub automatically.

### 🖥️ Usage

**🏠 Home — Channel Dashboard**  
View all registered channels. Start or stop each one independently. Running channels show a direct link to their port.

**⚙️ Configuración — Register a Channel**  
Provide the channel name, absolute path to the `.py` script, and the path to its virtual environment. The Hub assigns the next available port automatically.

**🗄️ DB — Database Management**  
Edit the channel registry directly in a table. Export to CSV as backup.

**💻 Automatizaciones — Script Launcher**  
Launch external Python scripts in isolated console windows. Add new automations by editing only `config.py` — no UI code changes needed.

### 🔧 Adding a New Automation

Edit `config.py` and append to `AUTOMATION_CARDS`:

```python
AutomationCard(
    key="run_my_script",
    title="🤖 My Script",
    caption="Does something useful.",
    path_hint=r"C:\dev\projects\my_script",
    cwd=r"C:\dev\projects\my_script",
    python_exe=r"C:\dev\projects\my_script\env\Scripts\python.exe",
    script=r"C:\dev\projects\my_script\main.py",
)
```

The UI card appears automatically on next reload.

### 📋 Requirements

```
streamlit
pandas
```

### 👤 Author

**Nicolás Andrés Cano Leal**  
2026 — Built with ❤️ in Streamlit and Python