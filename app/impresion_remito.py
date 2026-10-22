"""Impresión de remitos SOBRE el formulario preimpreso (solo los datos).

El formulario mide 185 x 250 mm. Todas las coordenadas están en mm,
con origen en la esquina superior izquierda del papel. La posición se
puede corregir con offsets (impresoras que desplazan) y existe el modo
"hoja A4" (el formulario se coloca arriba a la izquierda de una A4).
"""
import json
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from .rutas import carpeta_datos, carpeta_assets

ANCHO_MM, ALTO_MM = 185.0, 250.0
A4_MM = (210.0, 297.0)

# --- Plantilla medida sobre el escaneo del formulario -----------------
PLANTILLA = {
    # (x_izq, x_der, y_base) de cada casillero de la fecha
    "fecha_dia": (126.7, 135.9, 39.0),
    "fecha_mes": (135.9, 145.8, 39.0),
    "fecha_anio": (145.8, 161.5, 39.0),
    "senor": (36.0, 135.0, 67.7),
    "domicilio": (36.0, 135.0, 75.0),
    "cuit": (36.0, 135.0, 82.0),
    "iva": (28.0, 135.0, 92.9),
    "orden_compra": (140.5, 174.0, 71.0),
    "expreso": (140.5, 174.0, 89.0),
    # tabla
    "col_cantidad": (14.0, 28.3),   # alineada a la derecha
    "col_codigo": (32.3, 42.5),
    "col_desc": (46.0, 173.0),
    "tabla_y0": 107.0,              # base de la 1ª fila
    "tabla_paso": 5.0,
    "tabla_filas": 22,
}
FUENTE, TAM = "Helvetica", 10

_CFG_DEFECTO = {"offset_x_mm": 0.0, "offset_y_mm": 0.0, "hoja_a4": False}


def _ruta_cfg() -> Path:
    return carpeta_datos() / "impresion_remito.json"


def cargar_config() -> dict:
    cfg = dict(_CFG_DEFECTO)
    try:
        cfg.update(json.loads(_ruta_cfg().read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def guardar_config(cfg: dict) -> None:
    _ruta_cfg().write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def ruta_fondo() -> Path | None:
    for p in (carpeta_assets() / "remito_fondo.png",
              Path(__file__).resolve().parent.parent / "assets" / "remito_fondo.png"):
        if p.exists():
            return p
    return None


class _Lienzo:
    def __init__(self, ruta, cfg, con_fondo):
        self.cfg = cfg
        self.pag = A4_MM if cfg["hoja_a4"] else (ANCHO_MM, ALTO_MM)
        self.c = canvas.Canvas(str(ruta), pagesize=(self.pag[0] * mm, self.pag[1] * mm))
        self.fondo = ruta_fondo() if con_fondo else None

    def nueva_pagina(self):
        if self.fondo:
            self.c.drawImage(str(self.fondo), self._x(0), self._y(ALTO_MM),
                             ANCHO_MM * mm, ALTO_MM * mm)
        self.c.setFont(FUENTE, TAM)

    def _x(self, x):
        return (x + self.cfg["offset_x_mm"]) * mm

    def _y(self, y_desde_arriba):
        return (self.pag[1] - y_desde_arriba - self.cfg["offset_y_mm"]) * mm

    def texto(self, x, y, s, ancho_max=None, derecha=False, tam=TAM):
        s = str(s or "")
        if not s:
            return
        if ancho_max:
            while tam > 6 and self.c.stringWidth(s, FUENTE, tam) > ancho_max * mm:
                tam -= 0.5
            while len(s) > 1 and self.c.stringWidth(s, FUENTE, tam) > ancho_max * mm:
                s = s[:-1]
        self.c.setFont(FUENTE, tam)
        if derecha:
            self.c.drawRightString(self._x(x), self._y(y), s)
        else:
            self.c.drawString(self._x(x), self._y(y), s)

    def cerrar(self):
        self.c.save()


def _cabecera(L, remito):
    P = PLANTILLA
    cli = remito.cliente
    f = remito.fecha
    for clave, valor in (("fecha_dia", f"{f.day:02d}"), ("fecha_mes", f"{f.month:02d}"),
                         ("fecha_anio", str(f.year))):
        x0, x1, y = P[clave]
        L.texto((x0 + x1) / 2 - L.c.stringWidth(valor, FUENTE, TAM) / mm / 2, y, valor)
    dom = remito.domicilio_entrega or cli.domicilio or ""
    # remitos viejos: si es el domicilio de envío sin localidad/provincia, se completa
    if dom and dom == (getattr(cli, "domicilio_envio", None) or ""):
        extra = [x.strip() for x in (getattr(cli, "localidad_envio", "") or "",
                                     getattr(cli, "provincia_envio", "") or "") if x and x.strip()]
        dom = ", ".join([dom] + extra)
    for clave, valor in (
        ("senor", cli.razon_social),
        ("domicilio", dom),
        ("cuit", f"CUIT: {cli.cuit}" if cli.cuit else ""),
        ("iva", cli.condicion_iva or ""),
        ("orden_compra", getattr(remito, "orden_compra", "") or ""),
        ("expreso", getattr(remito, "expreso", "") or ""),
    ):
        x0, x1, y = P[clave]
        L.texto(x0, y, valor, ancho_max=x1 - x0)


def _items(L, items):
    P = PLANTILLA
    for i, it in enumerate(items):
        y = P["tabla_y0"] + i * P["tabla_paso"]
        cant = it.cantidad
        cant = f"{cant:g}" if isinstance(cant, float) else str(cant)
        L.texto(P["col_cantidad"][1], y, cant, derecha=True)
        a, b = P["col_codigo"]
        L.texto(a, y, it.producto.codigo, ancho_max=b - a)
        a, b = P["col_desc"]
        L.texto(a, y, it.producto.descripcion, ancho_max=b - a)


def generar_pdf_remito_preimpreso(remito, ruta, con_fondo=False, cfg=None) -> int:
    """Genera el PDF con solo los datos. Devuelve la cantidad de hojas."""
    cfg = cfg or cargar_config()
    L = _Lienzo(ruta, cfg, con_fondo)
    n = PLANTILLA["tabla_filas"]
    items = list(remito.items) or []
    bloques = [items[i:i + n] for i in range(0, max(len(items), 1), n)]
    for k, bloque in enumerate(bloques):
        if k:
            L.c.showPage()
        L.nueva_pagina()
        _cabecera(L, remito)
        _items(L, bloque)
        if len(bloques) > 1:
            L.texto(150, 245, f"Hoja {k + 1}/{len(bloques)}", tam=7)
    L.cerrar()
    return len(bloques)


def generar_pdf_prueba_alineacion(ruta, con_fondo=True, cfg=None) -> None:
    """Hoja de prueba: imprime marcas en todos los campos y la grilla de filas."""
    cfg = cfg or cargar_config()
    L = _Lienzo(ruta, cfg, con_fondo)
    L.nueva_pagina()
    P = PLANTILLA
    for clave in ("fecha_dia", "fecha_mes", "fecha_anio", "senor", "domicilio",
                  "cuit", "iva", "orden_compra", "expreso"):
        x0, x1, y = P[clave]
        L.texto(x0 + 1, y, clave.upper().replace("_", " "), ancho_max=x1 - x0 - 1)
    for i in range(P["tabla_filas"]):
        y = P["tabla_y0"] + i * P["tabla_paso"]
        L.texto(P["col_cantidad"][1], y, str(i + 1), derecha=True)
        L.texto(P["col_codigo"][0], y, f"COD{i + 1:02d}")
        L.texto(P["col_desc"][0], y, f"Descripcion de prueba, fila {i + 1}")
    L.cerrar()
