"""
Actualización automática desde GitHub Releases.

Al abrir la app (en segundo plano) consulta la última versión publicada en
https://github.com/sebtegno/gestor-negocio/releases . Si es más nueva:
- Ejecutando como .exe: descarga GestorNegocio.exe del release y lo reemplaza
  (la base de datos y demás datos NO se tocan: viven junto al .exe).
- Ejecutando con `python run.py` desde una carpeta con git: hace `git pull`.
Si no hay internet, no pasa nada: sigue funcionando normalmente.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QApplication

from .rutas import ejecutando_como_exe
from .version import VERSION

REPO = "sebtegno/gestor-negocio"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
NOMBRE_ASSET = "GestorNegocio.exe"


def _tupla(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4]) or (0,)


class _Consulta(QThread):
    hay_nueva = Signal(str, str)  # version, url de descarga del .exe ("" si no hay)

    def run(self):
        try:
            r = requests.get(API, timeout=6, headers={"Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                return
            datos = r.json()
            tag = datos.get("tag_name", "")
            if _tupla(tag) <= _tupla(VERSION):
                return
            url = ""
            for a in datos.get("assets", []):
                if a.get("name", "").lower() == NOMBRE_ASSET.lower():
                    url = a.get("browser_download_url", "")
            self.hay_nueva.emit(tag.lstrip("vV"), url)
        except Exception:
            pass  # sin internet u otro problema: seguir normal


class Actualizador:
    def __init__(self, ventana):
        self.ventana = ventana
        self._hilo = _Consulta()
        self._hilo.hay_nueva.connect(self._ofrecer)

    def comprobar(self):
        self._hilo.start()

    # ------------------------------------------------------------------
    def _ofrecer(self, version: str, url: str):
        if ejecutando_como_exe():
            if not url:
                return
            r = QMessageBox.question(
                self.ventana, "Actualización disponible",
                f"Hay una versión nueva ({version}). Tu versión: {VERSION}.\n\n"
                "¿Actualizar ahora? La app se va a reiniciar. Tus datos no se tocan.")
            if r == QMessageBox.Yes:
                self._actualizar_exe(url)
        else:
            raiz = Path(__file__).resolve().parent.parent
            if (raiz / ".git").exists():
                r = QMessageBox.question(
                    self.ventana, "Actualización disponible",
                    f"Hay una versión nueva ({version}). Tu versión: {VERSION}.\n\n"
                    "¿Descargarla ahora (git pull)?")
                if r == QMessageBox.Yes:
                    self._git_pull(raiz)

    def _git_pull(self, raiz: Path):
        try:
            p = subprocess.run(["git", "pull", "--ff-only"], cwd=raiz, capture_output=True,
                               text=True, timeout=60)
            if p.returncode == 0:
                QMessageBox.information(self.ventana, "Actualizado",
                                        "Listo. Cerrá y volvé a abrir la app para usar la nueva versión.")
            else:
                QMessageBox.warning(self.ventana, "No se pudo actualizar",
                                    (p.stderr or p.stdout)[:600])
        except Exception as e:
            QMessageBox.warning(self.ventana, "No se pudo actualizar", str(e))

    def _actualizar_exe(self, url: str):
        exe = Path(sys.executable)
        nuevo = exe.with_name("GestorNegocio_nuevo.exe")
        dlg = QProgressDialog("Descargando actualización...", None, 0, 0, self.ventana)
        dlg.setWindowTitle("Actualizando")
        dlg.setMinimumDuration(0)
        dlg.show()
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(nuevo, "wb") as f:
                    for trozo in r.iter_content(1024 * 256):
                        f.write(trozo)
                        QApplication.processEvents()
            if nuevo.stat().st_size < 1_000_000:
                raise RuntimeError("La descarga quedó incompleta.")
        except Exception as e:
            dlg.close()
            try:
                nuevo.unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.warning(self.ventana, "No se pudo actualizar", str(e))
            return
        dlg.close()

        bat = exe.with_name("_actualizar.bat")
        bat.write_text(
            "@echo off\r\n"
            "set PYINSTALLER_RESET_ENVIRONMENT=1\r\n"
            "set _MEIPASS2=\r\n"
            "set N=0\r\n"
            ":esperar\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'move /Y "{nuevo}" "{exe}" >nul 2>&1\r\n'
            "if errorlevel 1 (\r\n"
            "  set /a N+=1\r\n"
            "  if %N% LSS 15 goto esperar\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            f'start "" "{exe}"\r\n'
            'del "%~f0"\r\n', encoding="ascii", errors="replace")
        flags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
        # El nuevo .exe NO debe heredar el entorno de PyInstaller de este proceso
        # (si no, busca la carpeta temporal de esta instancia, ya borrada).
        env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True, env=env)
        QApplication.quit()
        os._exit(0)
