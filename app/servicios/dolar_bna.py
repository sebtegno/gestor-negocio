"""
Obtiene la cotización del dólar (divisa) publicada por el Banco de la
Nación Argentina, desde su página oficial.

Requiere: pip install requests beautifulsoup4

Fuente: https://www.bna.com.ar/Cotizador/MonedasHistorico
Esa página devuelve una tabla HTML simple (sin JavaScript) con la fecha
del último cierre y la cotización de compra/venta de varias monedas.
"""
from __future__ import annotations

import re
import datetime as dt
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

URL_BNA = "https://www.bna.com.ar/Personas"  # portada: tabla "Billetes" (la que ves en el BNA)
URL_BNA_DIVISAS = "https://www.bna.com.ar/Cotizador/MonedasHistorico"  # respaldo (divisas, cierre anterior)


@dataclass
class CotizacionDolar:
    compra: float
    venta: float
    fecha: dt.date
    fuente: str = "BNA"


def _parsear_numero(texto: str) -> float:
    return float(texto.strip().replace(".", "").replace(",", ".")) if "," in texto \
        else float(texto.strip())


def _buscar_dolar_en_tablas(soup, tipo: str):
    """Devuelve (compra, venta, fecha|None) de la primera tabla con fila 'Dolar U.S.A'."""
    for tabla in soup.find_all("table"):
        for fila in tabla.find_all("tr"):
            celdas = [c.get_text(strip=True) for c in fila.find_all(["td", "th"])]
            if len(celdas) >= 3 and "dolar" in celdas[0].lower() and "u.s.a" in celdas[0].lower():
                try:
                    compra = _parsear_numero(celdas[1])
                    venta = _parsear_numero(celdas[2])
                except ValueError:
                    continue
                m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", tabla.get_text(" ", strip=True))
                fecha = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
                return compra, venta, fecha
    return None


def obtener_cotizacion_dolar_bna(timeout: int = 8) -> CotizacionDolar:
    """
    Dólar BILLETE del BNA (el que se ve en la portada del banco). Si esa
    página cambia, cae a la tabla de divisas.
    """
    errores = []
    for url, tipo in ((URL_BNA, "billete"), (URL_BNA_DIVISAS, "divisa")):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            res = _buscar_dolar_en_tablas(BeautifulSoup(r.text, "html.parser"), tipo)
            if res:
                compra, venta, fecha = res
                return CotizacionDolar(compra=compra, venta=venta,
                                       fecha=fecha or dt.date.today(),
                                       fuente=f"BNA {tipo}")
            errores.append(f"{url}: no se encontró la fila 'Dolar U.S.A'")
        except Exception as e:
            errores.append(f"{url}: {e}")
    raise RuntimeError("No se pudo obtener el dólar del BNA. " + " | ".join(errores))
