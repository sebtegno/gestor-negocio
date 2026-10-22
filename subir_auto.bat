@echo off
cd /d "%~dp0"
echo Subiendo cambios a GitHub (automatico)...
git add .
git commit -m "Actualizacion %date% %time:~0,5%"
git push
echo.
echo TERMINADO. Cerra esta ventana.
pause
