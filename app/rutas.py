"""
Ubicación de los archivos que la app lee y escribe (base de datos, logo,
certificados, log de errores).

- Ejecutando con `python run.py`: todo vive en la carpeta del proyecto.
- Ejecutando como .exe (PyInstaller): todo vive junto al .exe, NO dentro de
  la carpeta temporal donde PyInstaller descomprime el programa (esa se
  borra al cerrar y se perdería la base de datos).
  Si la carpeta del .exe no permite escribir (por ejemplo Archivos de
  programa), usa %LOCALAPPDATA%\\GestorNegocio.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def ejecutando_como_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def _es_escribible(carpeta: Path) -> bool:
    try:
        prueba = carpeta / ".prueba_escritura"
        prueba.write_text("ok")
        prueba.unlink()
        return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def carpeta_datos() -> Path:
    if not ejecutando_como_exe():
        return Path(__file__).resolve().parent.parent

    junto_al_exe = Path(sys.executable).resolve().parent
    if _es_escribible(junto_al_exe):
        return junto_al_exe

    respaldo = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GestorNegocio"
    respaldo.mkdir(parents=True, exist_ok=True)
    return respaldo


def carpeta_assets() -> Path:
    carpeta = carpeta_datos() / "assets"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_certs() -> Path:
    carpeta = carpeta_datos() / "certs"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_base_de_datos() -> Path:
    return carpeta_datos() / "negocio.db"


def ruta_logo() -> Path:
    return carpeta_assets() / "logo.png"
