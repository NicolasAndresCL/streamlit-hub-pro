@echo off
REM Activar el entorno virtual
call C:\dev\projects\hub\env\Scripts\activate.bat

REM Ir a la carpeta del proyecto
cd C:\dev\projects\hub

REM Ejecutar la aplicación Streamlit
start "" /b streamlit run hub_app.py
pause
