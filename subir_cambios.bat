@echo off
cd /d "%~dp0"
echo Subiendo cambios a GitHub...
set /p MSG=Describi el cambio (Enter para usar "Actualizacion"): 
if "%MSG%"=="" set MSG=Actualizacion
git add .
git commit -m "%MSG%"
git push
echo.
echo Listo. Revisa arriba que no haya errores.
pause
