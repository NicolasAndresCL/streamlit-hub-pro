@echo off
title 🚀 Hub Pro - Iniciando...
color 0A

echo.
echo  ============================================
echo   🚀  HUB PRO - Panel de Control
echo   Nicolás Andrés Cano Leal - 2026
echo  ============================================
echo.
echo  [1/3] Activando entorno virtual...
call C:\dev\projects\Hub_Pro\env\Scripts\activate.bat

echo  [2/3] Verificando dependencias...
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo.
    echo  ❌ Streamlit no encontrado. Instalando...
    pip install streamlit pandas
)

echo  [3/3] Lanzando Hub Pro...
echo.
echo  ✅ Abriendo en: http://localhost:8501
echo  ⚠️  No cierres esta ventana mientras uses el Hub.
echo  ============================================
echo.

cd C:\dev\projects\Hub_Pro
streamlit run hub_app.py --server.port 8501 --server.headless false

echo.
echo  Hub Pro cerrado. Presiona cualquier tecla para salir.
pause > nul