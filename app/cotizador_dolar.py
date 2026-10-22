"""
Punto único para obtener "el dólar de hoy" en el resto de la app.
Cachea el valor en la base de datos para no golpear la web del BNA en
cada operación: se actualiza automáticamente una vez por día.
"""
from __future__ import annotations

import datetime as dt

from . import repositorio as repo
from .servicios.dolar_bna import obtener_cotizacion_dolar_bna


def valor_dolar_del_dia(forzar_actualizacion: bool = False):
    """
    Devuelve un objeto ValorDolar (compra, venta, fecha) correspondiente
    a hoy. Si ya se consultó hoy y no se pide forzar, usa el valor
    cacheado. Si falla la conexión a internet, cae al último valor
    disponible en caché (por ejemplo, fin de semana o sin conexión) y
    avisa mediante la excepción `DolarNoDisponibleError` solo si no hay
    ningún valor cacheado.
    """
    cacheado = repo.obtener_valor_dolar_cacheado()
    if not forzar_actualizacion:
        if cacheado and cacheado.obtenido_en and \
                dt.datetime.now() - cacheado.obtenido_en < dt.timedelta(hours=1):
            return cacheado  # el BNA actualiza durante el día: se renueva cada hora

    try:
        cot = obtener_cotizacion_dolar_bna()
        # se guarda bajo la fecha de HOY (la fecha del BNA puede ser la del cierre anterior)
        return repo.guardar_valor_dolar(cot.compra, cot.venta, cot.fuente, dt.date.today())
    except Exception:
        ultimo = cacheado or repo.obtener_ultimo_valor_dolar()
        if ultimo:
            return ultimo
        raise DolarNoDisponibleError(
            "No se pudo obtener la cotización del dólar del BNA (revisá tu "
            "conexión a internet) y todavía no hay ningún valor guardado "
            "en la base de datos."
        )


class DolarNoDisponibleError(Exception):
    pass
