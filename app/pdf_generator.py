"""
Generación de PDF para remitos, usando reportlab.

Instalación: pip install reportlab
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from . import marca
from .database import Remito, Cotizacion


def generar_pdf_cotizacion(cotizacion: Cotizacion, ruta_destino: str) -> None:
    """
    cotizacion: instancia obtenida con repositorio.obtener_cotizacion(id),
    que ya trae cargados cliente e items.producto.
    ruta_destino: ruta completa del archivo .pdf a generar.
    """
    doc = SimpleDocTemplate(
        ruta_destino, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloCotizacion", parent=estilos["Heading1"], fontSize=18, spaceAfter=4,
        textColor=colors.HexColor(marca.COLOR_OSCURO),
    )
    estilo_normal = estilos["Normal"]

    elementos = []

    elementos.append(Paragraph(f"COTIZACIÓN {cotizacion.numero}", estilo_titulo))
    elementos.append(Paragraph(
        f"Fecha: {cotizacion.fecha.strftime('%d/%m/%Y')}  —  "
        f"Válida por {cotizacion.validez_dias} días", estilo_normal
    ))
    elementos.append(Spacer(1, 0.6 * cm))

    cliente = cotizacion.cliente
    elementos.append(Paragraph(f"<b>Cliente:</b> {cliente.razon_social}", estilo_normal))
    elementos.append(Paragraph(f"<b>CUIT:</b> {cliente.cuit or '-'}", estilo_normal))
    elementos.append(Spacer(1, 0.8 * cm))

    encabezado = ["Código", "Descripción", "Cantidad", "Precio unit.", "Subtotal"]
    filas = [encabezado]
    for item in cotizacion.items:
        filas.append([
            item.producto.codigo,
            item.producto.descripcion,
            f"{item.cantidad:g}",
            f"${item.precio_unitario:,.2f}",
            f"${item.subtotal:,.2f}",
        ])
    filas.append(["", "", "", "Subtotal", f"${cotizacion.subtotal_neto:,.2f}"])
    if cotizacion.incluye_iva:
        filas.append(["", "", "", "IVA", f"${cotizacion.monto_iva:,.2f}"])
    filas.append(["", "", "", "TOTAL", f"${cotizacion.total:,.2f}"])
    filas_totales = 2 if cotizacion.incluye_iva else 1
    filas_totales += 1  # la fila de subtotal

    tabla = Table(filas, colWidths=[2.5 * cm, 6.5 * cm, 2.2 * cm, 3 * cm, 3 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(marca.COLOR_OSCURO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -(filas_totales + 1)), 0.5, colors.grey),
        ("LINEABOVE", (0, -filas_totales), (-1, -filas_totales), 1, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -(filas_totales + 1)),
         [colors.white, colors.HexColor("#f2f2f2")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla)

    if cotizacion.notas:
        elementos.append(Spacer(1, 0.8 * cm))
        elementos.append(Paragraph(f"<b>Notas:</b> {cotizacion.notas}", estilo_normal))

    doc.build(elementos)


def generar_pdf_remito(remito: Remito, ruta_destino: str) -> None:
    """
    remito: instancia obtenida con repositorio.obtener_remito(id), que ya
    trae cargados cliente e items.producto.
    ruta_destino: ruta completa del archivo .pdf a generar.
    """
    doc = SimpleDocTemplate(
        ruta_destino, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloRemito", parent=estilos["Heading1"], fontSize=18, spaceAfter=4,
        textColor=colors.HexColor(marca.COLOR_OSCURO),
    )
    estilo_normal = estilos["Normal"]

    elementos = []

    elementos.append(Paragraph(f"REMITO {remito.numero}", estilo_titulo))
    elementos.append(Paragraph(
        f"Fecha: {remito.fecha.strftime('%d/%m/%Y')}", estilo_normal
    ))
    elementos.append(Spacer(1, 0.6 * cm))

    cliente = remito.cliente
    datos_cliente = [
        f"<b>Cliente:</b> {cliente.razon_social}",
        f"<b>CUIT:</b> {cliente.cuit or '-'}",
    ]
    if remito.domicilio_entrega:
        datos_cliente.append(f"<b>Domicilio de entrega:</b> {remito.domicilio_entrega}")
    for linea in datos_cliente:
        elementos.append(Paragraph(linea, estilo_normal))
    elementos.append(Spacer(1, 0.8 * cm))

    encabezado = ["Código", "Descripción", "Cantidad", "Unidad"]
    filas = [encabezado]
    for item in remito.items:
        filas.append([
            item.producto.codigo,
            item.producto.descripcion,
            f"{item.cantidad:g}",
            item.producto.unidad,
        ])

    tabla = Table(filas, colWidths=[3 * cm, 8 * cm, 3 * cm, 3 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(marca.COLOR_OSCURO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla)

    if remito.observaciones:
        elementos.append(Spacer(1, 0.8 * cm))
        elementos.append(Paragraph(f"<b>Observaciones:</b> {remito.observaciones}", estilo_normal))

    elementos.append(Spacer(1, 2 * cm))
    elementos.append(Paragraph("Firma y aclaración de quien recibe:", estilo_normal))
    elementos.append(Spacer(1, 1.5 * cm))
    elementos.append(Paragraph("_" * 40, estilo_normal))

    doc.build(elementos)
