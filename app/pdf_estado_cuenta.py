"""PDF del estado de cuenta (cuenta corriente) de un cliente."""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from . import marca


def _pesos(x: float) -> str:
    return "$ " + f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def generar_pdf_estado_cuenta(cliente, movimientos, ruta_destino: str) -> None:
    """
    cliente: Cliente (razon_social, cuit, domicilio, condicion_iva).
    movimientos: lista de MovimientoCuentaCorriente (en cualquier orden).
    """
    movs = sorted(movimientos, key=lambda m: (m.fecha, m.id or 0))
    oscuro = colors.HexColor(marca.COLOR_OSCURO)
    est = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=est["Heading1"], fontSize=18, spaceAfter=2, textColor=oscuro)
    chico = ParagraphStyle("c", parent=est["Normal"], fontSize=8.5, leading=10.5)
    normal = est["Normal"]

    doc = SimpleDocTemplate(ruta_destino, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            title=f"Estado de cuenta - {cliente.razon_social}")
    el = [
        Paragraph(marca.NOMBRE_EMPRESA, titulo),
        Paragraph("ESTADO DE CUENTA", ParagraphStyle("s", parent=normal, fontSize=12, textColor=oscuro)),
        Paragraph(f"Emitido el {dt.date.today():%d/%m/%Y}", normal),
        Spacer(1, 0.5 * cm),
        Paragraph(f"<b>Cliente:</b> {cliente.razon_social}", normal),
    ]
    if getattr(cliente, "cuit", None):
        el.append(Paragraph(f"<b>CUIT:</b> {cliente.cuit}", normal))
    if getattr(cliente, "domicilio", None):
        el.append(Paragraph(f"<b>Domicilio:</b> {cliente.domicilio}", normal))
    el.append(Spacer(1, 0.5 * cm))

    filas = [["Fecha", "Concepto", "Debe", "Haber", "Saldo"]]
    saldo = total_debe = total_haber = 0.0
    for m in movs:
        debe = m.importe if m.tipo == "debe" else 0.0
        haber = m.importe if m.tipo != "debe" else 0.0
        saldo += debe - haber
        total_debe += debe
        total_haber += haber
        concepto = m.concepto or ""
        if m.tipo != "debe" and m.medio_pago:
            concepto += f" ({m.medio_pago})"
        filas.append([f"{m.fecha:%d/%m/%Y}", Paragraph(concepto, chico),
                      _pesos(debe) if debe else "", _pesos(haber) if haber else "", _pesos(saldo)])
    if not movs:
        filas.append(["", Paragraph("Sin movimientos", chico), "", "", _pesos(0)])
    filas.append(["", Paragraph("<b>TOTALES</b>", chico), _pesos(total_debe), _pesos(total_haber), _pesos(saldo)])

    t = Table(filas, colWidths=[2.2 * cm, 7.0 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), oscuro),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F8")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBE1")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, oscuro),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.6 * cm))

    if saldo > 0.005:
        texto = f"<b>Saldo adeudado: {_pesos(saldo)}</b>"
    elif saldo < -0.005:
        texto = f"<b>Saldo a favor del cliente: {_pesos(-saldo)}</b>"
    else:
        texto = "<b>Cuenta al día: saldo $ 0,00</b>"
    el.append(Paragraph(texto, ParagraphStyle("sal", parent=normal, fontSize=12, textColor=oscuro)))
    doc.build(el)
