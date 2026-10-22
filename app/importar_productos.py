"""
Importación de productos desde Excel (.xlsx).

Formatos que entiende:
1) Lista de precios de Bombas Leys (hoja "Lista de precios": columnas ART. /
   DESCRIPCION / DÓLAR - OFICIAL, con celdas combinadas). Precio en USD.
2) Tabla simple con encabezados: Código, Descripción, Precio (USD o ARS),
   Moneda, Stock, Stock mínimo, Unidad, IVA.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import openpyxl


@dataclass
class ProductoImportado:
    codigo: str
    descripcion: str
    precio: float = 0.0
    en_dolares: bool = True
    stock: float = 0.0
    stock_minimo: float = 0.0
    unidad: str = "unidad"
    alicuota_iva: float = 21.0
    codigo_provisorio: bool = False


@dataclass
class ResultadoLectura:
    productos: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _norm(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def _numero(v):
    """Número desde 14.12 o '$ 6,00'. None si no es un precio."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("$", "").replace("USD", "").strip()
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _codigo_txt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


# ---------------------------------------------------------------------------
def _spans(ws, col):
    """Celdas con valor de una columna como (fila_ini, fila_fin, valor), con combinadas."""
    rangos = {}
    for r in ws.merged_cells.ranges:
        if r.min_col <= col <= r.max_col:
            rangos[(r.min_row, r.min_col)] = r.max_row
    res = []
    for row in range(1, ws.max_row + 1):
        v = ws.cell(row, col).value
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        res.append((row, rangos.get((row, col), row), v))
    return res


def _es_lista_leys(ws) -> bool:
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 15)):
        textos = [_norm(c.value) for c in row]
        if "art." in textos and "descripcion" in textos:
            return True
    return False


def _leer_lista_leys(ws) -> ResultadoLectura:
    res = ResultadoLectura()
    col_art = col_desc = col_precio = None
    filas_encabezado = set()
    for row in ws.iter_rows():
        textos = {c.column: _norm(c.value) for c in row if c.value is not None}
        if "art." in textos.values():
            filas_encabezado.add(row[0].row)
            for col, t in textos.items():
                if t == "art.":
                    col_art = col_art or col
                elif t in ("descripcion",) or t.startswith("**"):
                    col_desc = col_desc or col
                elif "oficial" in t or "ofical" in t:
                    col_precio = col_precio or col
    if not (col_art and col_desc and col_precio):
        raise ValueError("No se encontraron las columnas ART., DESCRIPCION y DÓLAR - OFICIAL.")

    ruido = ("hoja n", "bombas leys", "mail:", "www.", "lista de precios", "**")
    arts = [a for a in _spans(ws, col_art) if a[0] not in filas_encabezado]
    descs = [d for d in _spans(ws, col_desc)
             if d[0] not in filas_encabezado and isinstance(d[2], str)
             and not any(_norm(d[2]).startswith(x) for x in ruido)]
    precios = [p for p in _spans(ws, col_precio) if p[0] not in filas_encabezado]

    # Agrupar código y descripción que comparten filas.
    anclas = [("a", *x) for x in arts] + [("d", *x) for x in descs]
    anclas.sort(key=lambda t: (t[1], t[0]))
    grupos = []
    for tipo, r0, r1, v in anclas:
        for g in grupos:
            if r0 <= g["r1"] and r1 >= g["r0"]:
                g["r0"], g["r1"] = min(g["r0"], r0), max(g["r1"], r1)
                g[tipo] = v
                break
        else:
            grupos.append({"r0": r0, "r1": r1, tipo: v})

    usados = set()
    for g in grupos:
        precio = None
        for i, (p0, p1, pv) in enumerate(precios):
            if p0 <= g["r1"] and p1 >= g["r0"]:
                n = _numero(pv)
                if n is not None:
                    precio, _ = n, usados.add(i)
                    break
                usados.add(i)  # p. ej. "Consultar"
        desc = (g.get("d") or "").strip()
        codigo = _codigo_txt(g["a"]) if "a" in g else ""
        if not desc:
            res.avisos.append(f"Artículo {codigo} (fila {g['r0']}) no tiene descripción: se importó con la descripción vacía y se salteó.")
            continue
        p = ProductoImportado(codigo=codigo, descripcion=desc,
                              precio=round(precio, 2) if precio is not None else 0.0,
                              en_dolares=True, codigo_provisorio=not codigo)
        if precio is None:
            res.avisos.append(f"«{desc}» no tiene precio en la lista: queda en 0.")
        if not codigo:
            res.avisos.append(f"«{desc}» no tiene número de artículo: se le asignó un código provisorio.")
        res.productos.append(p)

    for i, (p0, p1, pv) in enumerate(precios):
        if i not in usados and _numero(pv) is not None:
            res.avisos.append(f"Precio sin artículo ni descripción en la fila {p0} (USD {_numero(pv):,.2f}): no se importó.")
    return res


# ---------------------------------------------------------------------------
_ALIAS = {
    "codigo": ("codigo", "cod", "art", "art.", "articulo"),
    "descripcion": ("descripcion", "producto", "detalle", "nombre"),
    "precio": ("precio", "precio venta", "venta", "dolar oficial", "dolar - oficial", "usd", "precio usd"),
    "moneda": ("moneda",),
    "stock": ("stock", "stock inicial", "cantidad"),
    "stock_minimo": ("stock minimo", "minimo"),
    "unidad": ("unidad",),
    "iva": ("iva", "alicuota iva", "% iva"),
}


def _leer_tabla_simple(ws) -> ResultadoLectura:
    res = ResultadoLectura()
    filas = list(ws.iter_rows(values_only=True))
    cab_idx = None
    mapa = {}
    for i, fila in enumerate(filas[:15]):
        m = {}
        for j, v in enumerate(fila):
            n = _norm(v)
            for campo, alias in _ALIAS.items():
                if n in alias and campo not in m:
                    m[campo] = j
        if "descripcion" in m:
            cab_idx, mapa = i, m
            break
    if cab_idx is None:
        raise ValueError("No se encontró una columna «Descripción». Revisá los encabezados del Excel.")
    for fila in filas[cab_idx + 1:]:
        def g(c):
            return fila[mapa[c]] if c in mapa and mapa[c] < len(fila) else None
        desc = str(g("descripcion") or "").strip()
        if not desc:
            continue
        codigo = _codigo_txt(g("codigo")) if g("codigo") not in (None, "") else ""
        moneda = _norm(g("moneda"))
        en_usd = moneda in ("usd", "u$s", "dolar", "dolares", "us$") or \
            ("precio" in mapa and "dolar" in _norm(ws.cell(cab_idx + 1, mapa["precio"] + 1).value))
        res.productos.append(ProductoImportado(
            codigo=codigo, descripcion=desc, precio=_numero(g("precio")) or 0.0,
            en_dolares=bool(en_usd), stock=_numero(g("stock")) or 0.0,
            stock_minimo=_numero(g("stock_minimo")) or 0.0,
            unidad=str(g("unidad") or "unidad").strip(),
            alicuota_iva=_numero(g("iva")) if _numero(g("iva")) is not None else 21.0,
            codigo_provisorio=not codigo))
    return res


def leer_excel(ruta: str) -> ResultadoLectura:
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hoja = None
    for ws in wb.worksheets:
        if _norm(ws.title) == "lista de precios":
            hoja = ws
            break
    hoja = hoja or wb.worksheets[0]
    res = _leer_lista_leys(hoja) if _es_lista_leys(hoja) else _leer_tabla_simple(hoja)

    # Códigos duplicados dentro del archivo.
    vistos = {}
    for p in res.productos:
        if p.codigo and p.codigo in vistos:
            res.avisos.append(f"Código repetido en el archivo: {p.codigo} ({p.descripcion}); se le asignó un código provisorio.")
            p.codigo, p.codigo_provisorio = "", True
        vistos[p.codigo] = True
    return res


def asignar_codigos_provisorios(productos, codigos_existentes: set) -> None:
    n = 0
    for p in productos:
        if p.codigo:
            continue
        while True:
            n += 1
            c = f"SIN-CODIGO-{n:03d}"
            if c not in codigos_existentes:
                break
        p.codigo, p.codigo_provisorio = c, True
        codigos_existentes.add(c)
