"""
Lectura de facturas de proveedores (PDF con texto) y sugerencia de a qué
producto del stock corresponde cada renglón.

Es una lectura aproximada: la pantalla de revisión permite corregir todo
antes de guardar. Los PDF escaneados o las fotos no tienen texto que leer;
para esos la factura se carga a mano mirando la imagen.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from difflib import SequenceMatcher

EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

_NUM = r"\d{1,3}(?:\.\d{3})*,\d{1,4}|\d+,\d{1,4}|\d+(?:\.\d+)?"
_RE_NUM = re.compile(rf"(?<![\w.,-])({_NUM})(?![\w,]|\.\d)")
_PALABRAS_NO_ITEM = (
    "total", "subtotal", "iva", "cae", "cuit", "importe", "fecha", "domicilio",
    "condicion", "ingresos brutos", "razon social", "punto de venta", "comp.",
    "factura", "remito", "percep", "otros tributos", "son pesos", "pagina",
    "periodo", "vencimiento", "cliente", "telefono", "inicio de actividades",
)
_UNIDADES = r"\b(unidades?|unid\.?|un\.?|u\.?|kg|kgs|mts?|metros?|lts?|litros?|pares?|juegos?|jgo\.?|cajas?|docenas?|otras? unidades|cm)\b"


def norm(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower()).strip()


def numero_ar(s):
    """'1.234,56' -> 1234.56 ; '12.5' -> 12.5. None si no es número."""
    s = str(s).strip().replace("$", "").replace(" ", "")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
def extraer_texto_pdf(ruta: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Falta el módulo pypdf (pip install pypdf).") from e
    lector = PdfReader(ruta)
    partes = []
    for pagina in lector.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:
            partes.append("")
    return "\n".join(partes)


def analizar_factura(texto: str) -> dict:
    """Devuelve numero, fecha, cuits, total y lineas (aproximados)."""
    res = {"numero": "", "fecha": None, "cuits": [], "total": None, "lineas": []}

    m = re.search(r"(\d{4,5})\s*[-–]\s*(\d{8})", texto)
    if m:
        res["numero"] = f"{int(m.group(1)):04d}-{int(m.group(2)):08d}"
    else:
        pv = re.search(r"punto de venta\D{0,6}(\d{1,5})", texto, re.I)
        nro = re.search(r"comp\.?\s*nro\.?\D{0,6}(\d{1,8})", texto, re.I)
        if pv and nro:
            res["numero"] = f"{int(pv.group(1)):04d}-{int(nro.group(1)):08d}"

    m = re.search(r"fecha de emisi[oó]n\D{0,6}(\d{2})/(\d{2})/(\d{4})", texto, re.I) \
        or re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        try:
            res["fecha"] = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    res["cuits"] = [re.sub(r"\D", "", c) for c in re.findall(r"\b\d{2}-?\d{8}-?\d\b", texto)]

    totales = re.findall(r"importe total\D{0,6}\$?\s*(" + _NUM + ")", texto, re.I) \
        or re.findall(r"(?<!sub)total\D{0,6}\$?\s*(" + _NUM + ")", texto, re.I)
    if totales:
        res["total"] = numero_ar(totales[-1])

    for linea in texto.splitlines():
        it = _linea_a_item(linea)
        if it:
            res["lineas"].append(it)
    return res


def _linea_a_item(linea: str):
    original = linea.strip()
    bajo = norm(original)
    if len(bajo) < 4 or any(p in bajo for p in _PALABRAS_NO_ITEM):
        return None
    nums = [(m.start(), m.group(1), numero_ar(m.group(1))) for m in _RE_NUM.finditer(original)]
    nums = [(p, s, v) for p, s, v in nums if v is not None]
    if len(nums) < 3:
        return None

    valores = [v for _, _, v in nums]
    importe = valores[-1]
    # Buscar cantidad x precio = importe entre los números de la línea.
    mejor = None
    for i in range(len(valores) - 1):
        for j in range(len(valores) - 1):
            if i == j:
                continue
            q, p = valores[i], valores[j]
            if q > 0 and p > 0 and importe > 0 and abs(q * p - importe) <= max(0.02 * importe, 0.05):
                if mejor is None or i < mejor[0]:
                    mejor = (i, j, q, p)
    if mejor is None:
        # Sin coincidencia exacta: primer número = cantidad, segundo = precio.
        i, j, q, p = 0, 1, valores[0], valores[1]
    else:
        i, j, q, p = mejor

    primer_pos = min(nums[i][0], nums[j][0])
    texto_desc = original[:primer_pos]
    texto_desc = re.sub(_UNIDADES, " ", texto_desc, flags=re.I)
    texto_desc = re.sub(r"\s+", " ", texto_desc).strip(" -–|:")
    if len(re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]", texto_desc)) < 3:
        return None

    codigo = ""
    partes = texto_desc.split(" ", 1)
    if len(partes) == 2 and re.fullmatch(r"[A-Za-z0-9./-]{1,14}", partes[0]) and re.search(r"\d", partes[0]) \
            and len(re.findall(r"[A-Za-z]{3,}", partes[1])) >= 1:
        codigo, texto_desc = partes[0], partes[1].strip()

    return {"codigo": codigo, "descripcion": texto_desc, "cantidad": q, "precio_unitario": p}


# ---------------------------------------------------------------------------
def sugerir_producto(descripcion: str, codigo: str, productos, alias: dict | None = None):
    """
    Devuelve (producto_id | None, puntaje 0..1).
    Prioridad: alias recordado de este proveedor > código igual > parecido de texto.
    """
    clave = norm(descripcion)
    if alias and clave in alias:
        return alias[clave], 1.0
    cod = norm(codigo).replace(" ", "")
    if cod:
        for p in productos:
            if norm(p.codigo).replace(" ", "") == cod:
                return p.id, 1.0
    palabras = set(clave.split())
    mejor_id, mejor = None, 0.0
    for p in productos:
        texto_p = norm(f"{p.codigo} {p.descripcion}")
        desc_p = norm(p.descripcion)
        if not desc_p:
            continue
        pp = set(desc_p.split())
        jac = len(palabras & pp) / len(palabras | pp) if palabras | pp else 0.0
        ratio = SequenceMatcher(None, clave, desc_p).ratio()
        contiene = 0.85 if (clave and (clave in desc_p or desc_p in clave) and min(len(clave), len(desc_p)) >= 6) else 0.0
        puntaje = max(jac, ratio, contiene)
        if puntaje > mejor:
            mejor_id, mejor = p.id, puntaje
    return (mejor_id, mejor) if mejor >= 0.55 else (None, mejor)
