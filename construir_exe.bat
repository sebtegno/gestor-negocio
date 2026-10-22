@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================================
echo  Construyendo GestorNegocio.exe
echo  (hace falta Python 3.10 o superior instalado, SOLO en esta
echo   PC donde se arma el .exe; despues el .exe corre en
echo   cualquier PC con Windows sin instalar nada)
echo ==========================================================
echo.

echo [1/5] Buscando una instalacion real de Python...
set PYCMD=

rem --- Opcion 1: el lanzador "py" (el mas confiable, lo instala python.org)
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set PYCMD=py -3
    goto :encontrado
)

rem --- Opcion 2: "python", pero validando que no sea el alias falso de la
rem     Microsoft Store (ese "se encuentra" en el PATH pero no funciona)
for /f "delims=" %%v in ('python --version 2^>^&1') do set SALIDA=%%v
echo !SALIDA! | find "Python" >nul
if not errorlevel 1 (
    set PYCMD=python
    goto :encontrado
)

rem --- Opcion 3: "python3"
for /f "delims=" %%v in ('python3 --version 2^>^&1') do set SALIDA=%%v
echo !SALIDA! | find "Python" >nul
if not errorlevel 1 (
    set PYCMD=python3
    goto :encontrado
)

echo.
echo ERROR: no encontre una instalacion real de Python.
echo.
echo Lo mas probable es que Windows tenga activado el acceso directo
echo que abre la Microsoft Store en vez de Python. Para solucionarlo:
echo.
echo   1) Instala Python desde https://www.python.org/downloads/
echo      (boton grande amarillo "Download Python"). Durante la
echo      instalacion, TILDA la casilla "Add python.exe to PATH".
echo.
echo   2) Si ya lo instalaste y segui viendo este error, anda a Windows:
echo      Configuracion ^> Aplicaciones ^> Configuracion avanzada de
echo      aplicaciones ^> Alias de ejecucion de aplicaciones, y APAGA
echo      los alias "python.exe" y "python3.exe".
echo.
echo   3) Cerra esta ventana, volve a abrir una consola nueva (para que
echo      tome el PATH actualizado) y ejecuta este archivo de nuevo.
echo.
pause
exit /b 1

:encontrado
echo       Usando: %PYCMD%
echo.

if not exist venv_build (
    echo [2/5] Creando entorno de compilacion...
    %PYCMD% -m venv venv_build
    if errorlevel 1 goto :error
)
call venv_build\Scripts\activate.bat

echo [3/5] Instalando dependencias...
python -m pip install --upgrade pip
pip install PySide6 SQLAlchemy reportlab requests beautifulsoup4 openpyxl pyinstaller
if errorlevel 1 goto :error

set ICONO=
if exist assets\icono.ico set ICONO=--icon assets\icono.ico

echo [4/5] Generando el .exe (puede tardar varios minutos)...
pyinstaller --noconfirm --clean --onefile --windowed --name GestorNegocio ^
    --hidden-import sqlalchemy.dialects.sqlite ^
    --collect-data reportlab ^
    --collect-data certifi ^
    %ICONO% ^
    run.py
if errorlevel 1 goto :error

echo [5/5] Preparando carpetas junto al .exe...
if not exist dist\assets mkdir dist\assets
if not exist dist\certs mkdir dist\certs
if exist assets\logo.png copy /Y assets\logo.png dist\assets\logo.png >nul
if exist assets\remito_fondo.png copy /Y assets\remito_fondo.png dist\assets\remito_fondo.png >nul
if exist assets\LEEME.txt copy /Y assets\LEEME.txt dist\assets\LEEME.txt >nul

echo.
echo ==========================================================
echo  LISTO. Tu programa esta en la carpeta "dist":
echo     dist\GestorNegocio.exe
echo  Copia esa carpeta donde quieras (por ejemplo C:\GestorNegocio).
echo  Para conservar tus datos actuales, copia tu negocio.db
echo  al lado del .exe.
echo ==========================================================
pause
exit /b 0

:error
echo.
echo ERROR: algo fallo. Revisa los mensajes de arriba.
pause
exit /b 1
