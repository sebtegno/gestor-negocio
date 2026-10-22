"""Ejecutar con: python run.py  (o abrir GestorNegocio.exe)"""
import datetime as dt
import os
import sys
import traceback


def _instalar_registro_de_errores():
    """
    Sin consola (.exe), un error inesperado no se ve en ningún lado.
    Se anota en error.log, junto a la base de datos, para poder revisarlo.
    """
    from app.rutas import carpeta_datos

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    ruta = carpeta_datos() / "error.log"

    def registrar(tipo, valor, tb):
        try:
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(f"\n[{dt.datetime.now():%Y-%m-%d %H:%M:%S}]\n")
                f.write("".join(traceback.format_exception(tipo, valor, tb)))
        except OSError:
            pass
        sys.__excepthook__(tipo, valor, tb)

    sys.excepthook = registrar


if __name__ == "__main__":
    _instalar_registro_de_errores()
    from app.main import main
    main()
